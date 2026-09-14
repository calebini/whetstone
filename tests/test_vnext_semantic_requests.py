from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes
from whetstone.vnext_proposal_closeout import ProposalDecisionJournal
from whetstone.vnext_identity import binding_id
from whetstone.vnext_local_storage import Publication, StorageWriteError
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_semantic_admission import SEMANTIC_SCHEMAS, SEMANTIC_ALGORITHMS, load_registered_semantic_context
from whetstone.vnext_semantic_protocol import POLICY_VERSION, RULES
from whetstone.vnext_semantic_requests import (
    REQUEST_SCHEMAS, SemanticRequestJournal, finish_semantic_request, inspect_semantic_request, run_semantic_request,
)
from vnext_consuming_suite_fixture import consuming_suite
from vnext_fixtures import STAMP
import test_vnext_semantic_admission as admission_tests
import test_vnext_semantic_protocol as protocol_tests


def request_suite(test, directory):
    return consuming_suite(test, directory, additional_schemas=SEMANTIC_SCHEMAS | REQUEST_SCHEMAS,
        additional_algorithms=(*SEMANTIC_ALGORITHMS, 'vnext_semantic_requests_v1'),
        algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})


class Client:
    def __init__(self, context, responses=()):
        self.identity = deepcopy(context.packet['review_configuration']['verifier'])
        self.transport = dict(verifier=deepcopy(self.identity), command='scripted-verifier', cwd='/tmp', timeout_seconds=3,
            output_schema_hash=sha256_bytes((CONTRACT_ROOT/'schemas/semantic_verification_client_v2.codex.schema.json').read_bytes()))
        helper = protocol_tests.SemanticProtocolTests()
        helper.context = context
        self.valid = canonical_json_bytes(helper.response())
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []
        self.last_telemetry = None

    @property
    def transport_binding(self):
        return deepcopy(self.transport)

    def verify(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        response = self.responses.pop(0) if self.responses else self.valid
        if isinstance(response, Exception): raise response
        return response


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        admission_tests.SemanticAdmissionTests.setUpClass()

    def setUp(self):
        helper = admission_tests.SemanticAdmissionTests()
        self.addCleanup(helper.doCleanups)
        self.fixture, self.creation, self.editor = helper.fixture(request_suite)
        self.store = self.fixture.store
        self.admission = self.fixture.admission
        self.identifier = self.creation['candidate_id']
        self.registry = registry_for_proposal_requests(self.store, load_inputs=self.admission.load_inputs,
                                                       validate_authority=self.admission.validate_authority)
        self.decisions = ProposalDecisionJournal(self.registry)
        self.decisions.commit(self.identifier, decided_at=STAMP)
        self.context = load_registered_semantic_context(self.store, admission=self.admission, candidate_id=self.identifier)
        self.client = Client(self.context)
        self.directory = 'rounds/client_requests/' + SemanticRequestJournal(self.store, admission=self.admission,
                                                                          candidate_id=self.identifier).id

    def run_request(self, **kwargs):
        return run_semantic_request(self.store, admission=self.admission, candidate_id=self.identifier,
                                    client=kwargs.pop('client', self.client), **kwargs)

    def inspect(self):
        return inspect_semantic_request(self.store, admission=self.admission, candidate_id=self.identifier)

    def finish(self):
        return finish_semantic_request(self.store, admission=self.admission, candidate_id=self.identifier)

    def path(self, name):
        return self.fixture.root / self.directory / name

    def test_pass_completes_receipt_without_changing_candidate_or_seed_and_reentry_needs_no_client(self):
        seed = self.store.read('rounds/current_verified.json')
        result = self.run_request()
        self.assertEqual((result.status, result.attempts, result.receipt['verdict']), ('complete', 1, 'pass'))
        self.assertEqual(self.store.read(result.receipt['verification']['path']), canonical_json_bytes(result.result.verification))
        self.assertEqual(self.decisions.inspect(self.identifier).decision['candidate_disposition'], 'CANDIDATE_UNVERIFIED')
        self.assertEqual(self.store.read('rounds/current_verified.json'), seed)
        self.assertEqual(self.run_request(client=object()).receipt, result.receipt)
        self.assertEqual((self.client.calls, self.editor.calls), (1, 1))
        before = {p: p.read_bytes() for p in self.fixture.root.rglob('*') if p.is_file()}
        self.assertEqual(self.inspect().receipt, result.receipt)
        self.assertEqual({p: p.read_bytes() for p in self.fixture.root.rglob('*') if p.is_file()}, before)

    def test_valid_semantic_rejection_is_complete_without_editor_or_verifier_repair(self):
        response = json.loads(self.client.valid)
        response.update(verdict='reject', unrelated_semantic_change='detected')
        self.client.responses = [canonical_json_bytes(response)]
        result = self.run_request()
        self.assertEqual((result.status, result.receipt['verdict']), ('complete', 'reject'))
        self.assertEqual(self.run_request(continuation=True, client=None).receipt, result.receipt)
        self.assertEqual((self.client.calls, self.editor.calls), (1, 1))

    def test_shape_retry_has_two_linked_markers_and_exhaustion_cannot_reset(self):
        self.client.responses = [b'{', b'{}']
        result = self.run_request()
        self.assertEqual((result.status, result.attempts, self.client.calls), ('attempts_exhausted', 2, 2))
        first = json.loads(self.path('attempts/1/outcome.json').read_bytes())
        second = json.loads(self.path('attempts/2/invocation.json').read_bytes())
        self.assertEqual(second['reason'], 'shape_retry')
        self.assertEqual(second['previous_outcome_hash'], sha256_bytes(canonical_json_bytes(first)))
        self.assertIn('Correct only response JSON/schema shape', self.client.prompts[1])
        replacement = Client(self.context)
        self.assertEqual(self.run_request(client=replacement, continuation=True).status, 'attempts_exhausted')
        self.assertEqual(replacement.calls, 0)

    def test_one_shape_retry_can_complete_but_invalid_bindings_cannot_retry(self):
        self.client.responses = [b'{', self.client.valid]
        result = self.run_request()
        self.assertEqual((result.status, result.attempts), ('complete', 2))
        self.assertEqual(self.client.calls, 2)

    def test_invalid_semantic_binding_remains_technical_without_automatic_or_explicit_retry(self):
        response = json.loads(self.client.valid)
        response['context_hash'] = 'f' * 64
        self.client.responses = [canonical_json_bytes(response)]
        result = self.run_request()
        self.assertEqual((result.status, result.attempts), ('invalid_semantic', 1))
        self.assertIsNone(result.result)
        self.assertFalse(self.path('result.json').exists())
        self.assertEqual(self.run_request(client=object(), continuation=True).status, 'invalid_semantic')
        self.assertEqual(self.client.calls, 1)

    def test_timeout_requires_explicit_continuation_and_allows_only_timeout_change(self):
        self.client.responses = [TimeoutError('scripted deadline')]
        self.assertEqual(self.run_request().status, 'timeout')
        self.assertEqual(self.run_request().status, 'continuation_required')
        self.assertEqual(self.client.calls, 1)
        self.client.transport['command'] = 'different-command'
        with self.assertRaisesRegex(ValueError, 'transport identity changed'):
            self.run_request(continuation=True)
        self.client.transport['command'] = 'scripted-verifier'
        self.client.transport['timeout_seconds'] = 10
        result = self.run_request(continuation=True)
        self.assertEqual((result.status, result.attempts, self.client.calls), ('complete', 2, 2))
        marker = json.loads(self.path('attempts/2/invocation.json').read_bytes())
        self.assertEqual(marker['reason'], 'technical_continuation')
        self.assertEqual(marker['transport']['timeout_seconds'], 10)

    def test_raw_capture_interruption_is_materialized_without_new_client(self):
        original = self.store.publish
        def stop(token, path, value):
            result = original(token, path, value)
            if path == self.directory + '/attempts/1/response.json': raise OSError('scripted capture interruption')
            return result
        with patch.object(self.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'capture interruption'): self.run_request()
        self.assertEqual(self.inspect().status, 'valid_response')
        self.assertFalse(self.path('attempts/1/outcome.json').exists())
        result = self.finish()
        self.assertEqual((result.status, result.attempts, self.client.calls), ('complete', 1, 1))
        self.assertEqual(self.run_request(client=None).receipt, result.receipt)

    def test_derived_output_prefixes_recover_exactly_without_another_invocation(self):
        original = self.store.publish
        targets = [self.directory + '/attempts/1/outcome.json',
                   self.creation['candidate_path'].rsplit('/', 1)[0] + '/semantic_verification.json',
                   self.directory + '/result.json']
        for index, target in enumerate(targets):
            def stop(token, path, value):
                result = original(token, path, value)
                if path == target: raise OSError('scripted result interruption')
                return result
            with patch.object(self.store, 'publish', side_effect=stop):
                with self.assertRaisesRegex(OSError, 'result interruption'):
                    self.run_request() if index == 0 else self.finish()
            self.assertEqual(self.client.calls, 1)
        self.assertEqual(self.finish().status, 'complete')

    def test_invocation_marker_consumes_slot_even_when_client_was_never_started(self):
        original = self.store.publish
        def stop(token, path, value):
            result = original(token, path, value)
            if path == self.directory + '/attempts/1/invocation.json': raise OSError('scripted before process start')
            return result
        with patch.object(self.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'before process start'): self.run_request()
        self.assertEqual(self.client.calls, 0)
        self.assertEqual((self.inspect().status, self.inspect().attempts), ('interrupted', 1))
        self.assertEqual(self.run_request().status, 'continuation_required')
        result = self.run_request(continuation=True)
        self.assertEqual((result.status, result.attempts, self.client.calls), ('complete', 2, 1))

    def test_uninvoked_header_keeps_original_timeout_and_needs_explicit_continuation(self):
        original = self.store.publish
        def stop(token, path, value):
            result = original(token, path, value)
            if path == self.directory + '/request.json': raise OSError('scripted request preparation')
            return result
        with patch.object(self.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'request preparation'): self.run_request()
        self.assertEqual(self.inspect().status, 'prepared')
        self.client.transport['timeout_seconds'] = 10
        with self.assertRaisesRegex(ValueError, 'claimed timeout'): self.run_request(continuation=True)
        self.assertEqual(self.client.calls, 0)
        self.client.transport['timeout_seconds'] = 3
        self.assertEqual(self.run_request(continuation=True).status, 'complete')

    def test_missing_bound_predecessor_or_raw_response_refuses_without_call(self):
        self.client.responses = [b'{', self.client.valid]
        self.run_request()
        path = self.path('attempts/1/outcome.json')
        before = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'bound predecessor'): self.run_request(continuation=True)
        path.write_bytes(before)
        self.path('attempts/2/response.json').unlink()
        with self.assertRaisesRegex(ValueError, 'lacks its response'): self.run_request(continuation=True)
        self.assertEqual(self.client.calls, 2)

    def test_changed_derived_report_and_unknown_attempt_refuse_before_reentry_writes(self):
        result = self.run_request()
        path = self.fixture.root / result.receipt['verification']['path']
        before = path.read_bytes()
        value = json.loads(before);value['verdict'] = 'reject';path.write_bytes(canonical_json_bytes(value))
        with self.assertRaisesRegex(ValueError, 'matching raw evidence'): self.run_request()
        path.write_bytes(before)
        self.path('attempts/3').mkdir()
        with self.assertRaisesRegex(ValueError, 'allowance extension'): self.run_request(continuation=True)
        self.assertEqual(self.client.calls, 1)

    def test_missing_initial_decision_refuses_before_request_or_client(self):
        for path in self.fixture.root.rglob('candidate_verification*.json'): path.unlink()
        (self.fixture.root / self.creation['candidate_path']).parent.joinpath('disposition_events/event-2.json').unlink()
        with self.assertRaisesRegex(ValueError, 'committed nonfinal'): self.run_request()
        self.assertFalse(self.path('request.json').exists())
        self.assertEqual(self.client.calls, 0)

    def test_unbound_candidate_report_cannot_create_a_fresh_request(self):
        path = (self.fixture.root / self.creation['candidate_path']).parent / 'semantic_verification.json'
        path.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'lack their durable request'): self.run_request()
        self.assertFalse(self.path('request.json').exists())
        self.assertEqual(self.client.calls, 0)

    def test_uncertain_marker_publication_invalidates_writer_and_consumes_attempt(self):
        original = self.store._tree.write
        def lost(path, raw, **kwargs):
            result = original(path, raw, **kwargs)
            if path == self.directory + '/attempts/1/invocation.json':
                raise StorageWriteError(Publication('outcome_requires_reconciliation', path, result.hash), 'scripted lost marker acknowledgement')
            return result
        with patch.object(self.store._tree, 'write', side_effect=lost):
            with self.assertRaises(StorageWriteError): self.run_request()
        self.assertIsNone(self.store._token)
        self.assertEqual((self.inspect().status, self.client.calls), ('interrupted', 0))
        result = self.run_request(continuation=True)
        self.assertEqual((result.status, result.attempts, self.client.calls), ('complete', 2, 1))


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticOperatorRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SemanticRequestTests.setUpClass()

    def make_subject(self):
        fixtures = admission_tests.admission_tests.fixtures
        original_setup = fixtures.UnitPreflightTests.setUp
        def with_authority(test):
            original_setup(test)
            fixture = test.c.f
            content = b'Queue waiting applies to each work start.\n'
            reference = fixture.save('inputs/waiting-authority.md', content)
            target = next(row for row in fixture.authority['bindings'] if row['role'] == 'mutable_target')
            authority = dict(path=reference['path'], content_hash=reference['hash'], role='normative_authority',
                authority_scopes=target['authority_scopes'], effective_horizon='current', mutable=False, may_introduce_requirements=True)
            authority['binding_id'] = binding_id(authority)
            fixture.authority['bindings'].append(authority)
            fixture.authority['precedence'] = [{'authority_scope': scope, 'ordered_binding_ids': [authority['binding_id'], target['binding_id']],
                                               'conflict_policy': 'pause'}
                                               for scope in target['authority_scopes']]
            fixture.rebind()
        subject = SemanticRequestTests()
        self.addCleanup(subject.doCleanups)
        with patch.object(fixtures.UnitPreflightTests, 'setUp', with_authority):
            subject.setUp()
        packet = subject.context.packet
        target = next(row for row in packet['authority_map']['bindings'] if row['role'] == 'mutable_target')
        authority = packet['dependency_context'][0]
        def alternative(identifier, text, interpretation):
            raw = text.encode()
            return dict(authority_binding_id=identifier, interpretation=interpretation,
                evidence=dict(byte_start=0, byte_end=len(raw), content_hash=sha256_bytes(raw), text=text))
        response = json.loads(subject.client.valid)
        response.update(authority_compliance='uncertain', operator_decision_required=True, verdict='operator_decision_required',
            authority_choice=dict(question='Which interpretation should a new transaction address?', authority_scope=target['authority_scopes'][0],
                alternatives=[alternative(target['binding_id'], packet['seed'], 'Waiting is scoped to queue startup.'),
                              alternative(authority['binding']['binding_id'], authority['content'], 'Waiting is scoped to every work start.')]),
            uncertainty_resolutions=[dict(field_path='authority_compliance', policy_rule_id=RULES['authority_choice'],
                                           disposition='operator_decision_required', decision_id=None)])
        subject.client.responses = [canonical_json_bytes(response)]
        return subject

    def test_real_admitted_authority_choice_commits_request_before_report_and_replays_without_client(self):
        subject = self.make_subject()
        original = subject.store.publish
        def stop(token, path, value):
            result = original(token, path, value)
            if '/semantic_decisions/' in path and path.endswith('/request.json'):
                raise OSError('scripted authority request interruption')
            return result
        with patch.object(subject.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'authority request interruption'): subject.run_request()
        self.assertEqual(subject.inspect().status, 'valid_response')
        self.assertFalse((subject.fixture.root / subject.creation['candidate_path']).parent.joinpath('semantic_verification.json').exists())
        result = subject.finish()
        self.assertEqual(result.receipt['verdict'], 'operator_decision_required')
        request = result.result.authority_request
        self.assertEqual(subject.store.read(result.receipt['authority_request']['path']), canonical_json_bytes(request))
        self.assertEqual(request['resolution_scope'], 'new_transaction_only_no_authority_change')
        self.assertEqual((subject.client.calls, subject.editor.calls), (1, 1))
        self.assertFalse(subject.decisions.inspect(subject.identifier).decision['decision_final'])
        self.assertEqual(subject.run_request(client=None).receipt, result.receipt)


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticRequestAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        admission_tests.SemanticAdmissionTests.setUpClass()

    def test_core_semantic_support_does_not_infer_durable_request_schema_or_algorithm_support(self):
        def missing_algorithm(test, directory):
            return consuming_suite(test, directory, additional_schemas=SEMANTIC_SCHEMAS | REQUEST_SCHEMAS,
                additional_algorithms=SEMANTIC_ALGORITHMS,
                algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})
        for factory, message in ((protocol_tests.semantic_suite, 'request schemas'), (missing_algorithm, 'request algorithm')):
            with self.subTest(message=message):
                helper = admission_tests.SemanticAdmissionTests()
                self.addCleanup(helper.doCleanups)
                fixture, creation, _ = helper.fixture(factory)
                context = load_registered_semantic_context(fixture.store, admission=fixture.admission,
                                                          candidate_id=creation['candidate_id'])
                client = Client(context)
                before = {p: p.read_bytes() for p in fixture.root.rglob('*') if p.is_file()}
                with self.assertRaisesRegex(ValueError, message):
                    run_semantic_request(fixture.store, admission=fixture.admission, candidate_id=creation['candidate_id'], client=client)
                self.assertEqual(client.calls, 0)
                self.assertEqual({p: p.read_bytes() for p in fixture.root.rglob('*') if p.is_file()}, before)


if __name__ == '__main__':
    unittest.main()
