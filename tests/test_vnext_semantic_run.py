import json
from copy import deepcopy
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_proposal_run import ProposalRun, RUN_INPUT_PATH, run_input_record, open_proposal_run
from whetstone.vnext_semantic_admission import SEMANTIC_ALGORITHMS, SEMANTIC_SCHEMAS
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from whetstone.vnext_semantic_protocol import POLICY_VERSION
from whetstone.vnext_semantic_requests import REQUEST_SCHEMAS
from vnext_consuming_suite_fixture import consuming_suite
from vnext_fixtures import STAMP
import test_vnext_semantic_requests as requests


def run_suite(test, directory):
    return consuming_suite(test, directory, additional_schemas=SEMANTIC_SCHEMAS | REQUEST_SCHEMAS,
        additional_algorithms=(*SEMANTIC_ALGORITHMS, 'vnext_semantic_requests_v1',
                               'vnext_semantic_decisions_v1', 'vnext_semantic_run_v1'),
        algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})


def stored_run(subject):
    fixture = subject.fixture
    record = run_input_record(fixture.f.job, dict(descriptor_ref=fixture.f.job_ref,
        review_ref=fixture.f.original.review_ref, seed_map_ref=fixture.f.map_ref, round_refs={1: fixture.record_ref}))
    with subject.store.locked(subject.admission.validate_authority) as token:
        subject.store.publish(token, RUN_INPUT_PATH, record)
    return ProposalRun(subject.store, suite_path=fixture.path)


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests.SemanticRequestTests.setUpClass()

    def setUp(self):
        self.subject = requests.SemanticRequestTests()
        self.addCleanup(self.subject.doCleanups)
        with patch.object(requests, 'request_suite', run_suite):
            self.subject.setUp()
        self.run = stored_run(self.subject)

    def status(self):
        return self.run.semantic_status(round_number=1)

    def invoke(self, **kwargs):
        return self.run.verify_round(round_number=1, decided_at=STAMP,
            client=kwargs.pop('client', self.subject.client), **kwargs)

    def files(self):
        return {path.relative_to(self.subject.fixture.root): path.read_bytes()
                for path in self.subject.fixture.root.rglob('*') if path.is_file()}

    def test_selected_stored_round_verifies_and_reopens_without_clients_or_seed_change(self):
        before = self.files()
        status = self.status()
        self.assertEqual((status['processing_gate'], status['request_status']), ('semantic_verification', 'not_started'))
        self.assertFalse(status['resume']['permitted'])
        with self.run.store.locked(self.run.validate_authority):
            self.assertEqual(self.status(), status)
        self.assertEqual(before, self.files())
        report, reference = self.invoke()
        self.assertEqual(report['resume']['reason'], 'vnext_proposal_only_complete')
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_VERIFIED')
        self.assertEqual(self.subject.store.read(reference['path']), canonical_json_bytes(report))
        after = self.files()
        for path, raw in before.items():
            if path.name != 'candidate_verification_current.json':
                self.assertEqual(after[path], raw, str(path))
        self.run.close()
        self.run = open_proposal_run(self.subject.fixture.root, suite_path=self.subject.fixture.path)
        self.addCleanup(self.run.close)
        self.assertEqual(self.status()['processing_gate'], 'complete')
        self.assertEqual((self.status()['request_status'], self.status()['request_attempts']), ('complete', 1))
        self.assertIsNotNone(self.status()['request_id'])
        self.assertEqual(self.invoke(client=object())[0], report)
        with self.assertRaisesRegex(ValueError, 'not technically resumable'):
            self.invoke(client=object(), continuation=True)
        self.assertEqual((self.subject.client.calls, self.subject.editor.calls), (1, 1))

    def test_timeout_continuation_preserves_cause_and_exhaustion_never_opens_another_slot(self):
        self.subject.client.responses = [TimeoutError('first deadline'), TimeoutError('second deadline')]
        report, _ = self.invoke()
        self.assertEqual(report['terminal_state'], 'HALTED_CLIENT_TIMEOUT')
        self.assertTrue(self.status()['resume']['permitted'])
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'requires explicit continuation'): self.invoke()
        self.assertEqual(self.files(), before)
        report, _ = self.invoke(continuation=True)
        self.assertEqual(report['terminal_state'], 'HALTED_CLIENT_TIMEOUT')
        self.assertIn('second deadline', report['resume']['reason'])
        self.assertFalse(report['resume']['permitted'])
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_UNVERIFIED')
        self.assertEqual(self.invoke(client=object())[0], report)
        with self.assertRaisesRegex(ValueError, 'not technically resumable'): self.invoke(continuation=True)
        self.assertEqual(self.subject.client.calls, 2)

    def test_valid_raw_and_prepared_decision_recover_without_verifier_or_editor(self):
        original = self.subject.store.publish
        def stop_raw(token, path, value):
            result = original(token, path, value)
            if path.endswith('/attempts/1/response.json') and path.startswith(self.subject.directory):
                raise OSError('scripted raw publication stop')
            return result
        with patch.object(self.subject.store, 'publish', side_effect=stop_raw):
            with self.assertRaisesRegex(OSError, 'raw publication stop'): self.invoke()
        before = self.files()
        self.assertEqual(self.status()['processing_gate'], 'verification_commit')
        self.assertEqual(self.files(), before)
        def stop_decision(token, path, value):
            result = original(token, path, value)
            if path.endswith('/candidate_verification-attempt-2.json'):
                raise OSError('scripted semantic decision stop')
            return result
        with patch.object(self.subject.store, 'publish', side_effect=stop_decision):
            with self.assertRaisesRegex(OSError, 'semantic decision stop'):
                self.invoke(client=object(), continuation=True)
        status = self.status()
        self.assertEqual(status['processing_gate'], 'verification_commit')
        self.assertEqual(status['terminal_report']['latest_candidate']['disposition'], 'CANDIDATE_UNVERIFIED')
        report, _ = self.invoke(client=object(), continuation=True)
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_VERIFIED')
        self.assertEqual((self.subject.client.calls, self.subject.editor.calls), (1, 1))

    def test_missing_terminal_recovers_only_materialization_and_corrupt_evidence_refuses(self):
        original = self.subject.store.publish
        def stop(token, path, value):
            if path.startswith('rounds/terminal_reports/'):
                raise OSError('scripted terminal stop')
            return original(token, path, value)
        with patch.object(self.subject.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'terminal stop'): self.invoke()
        self.assertEqual(self.status()['processing_gate'], 'materialization')
        before = self.files()
        report, _ = self.invoke(client=object(), continuation=True)
        for path, raw in before.items(): self.assertEqual(self.files()[path], raw)
        decision = self.subject.fixture.root / report['latest_candidate']['verification_decision_path']
        value = json.loads(decision.read_bytes());value['previous_decision_hash'] = 'f' * 64
        decision.write_bytes(canonical_json_bytes(value))
        before = self.files()
        with self.assertRaises(ValueError): self.status()
        with self.assertRaises(ValueError): self.invoke(client=object())
        self.assertEqual(self.files(), before)
        self.assertEqual(self.subject.client.calls, 1)

    def test_invalid_semantic_output_is_nonfinal_and_cannot_retry(self):
        response = json.loads(self.subject.client.valid);response['context_hash'] = 'f' * 64
        self.subject.client.responses = [canonical_json_bytes(response)]
        report, _ = self.invoke()
        self.assertFalse(report['resume']['permitted'])
        self.assertEqual(report['terminal_state'], 'HALTED_ARTIFACT_INVALID')
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_UNVERIFIED')
        self.assertFalse(report['latest_candidate']['verification_decision_final'])
        self.assertEqual(self.invoke(client=object())[0], report)
        self.assertEqual(self.subject.client.calls, 1)

    def test_unselected_round_refuses_before_writes(self):
        before = self.files()
        with self.assertRaises(ValueError): self.run.semantic_status(round_number=99)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.subject.client.calls, 0)

    def test_initial_decision_recovery_ends_before_any_verifier_call(self):
        journal = SemanticDecisionJournal(self.subject.registry, admission=self.run)
        for path in journal.paths(self.subject.creation, 1)[1:]:
            (self.subject.fixture.root / path).unlink()
        self.assertEqual(self.status()['processing_gate'], 'verification_commit')
        report, _ = self.invoke(client=object(), continuation=True)
        self.assertEqual(report['resume']['reason'], 'vnext_semantic_not_started')
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_UNVERIFIED')
        self.assertEqual(self.subject.client.calls, 0)
        self.assertEqual(self.status()['request_status'], 'not_started')
        self.assertEqual(self.invoke()[0]['latest_candidate']['disposition'], 'CANDIDATE_VERIFIED')

    def test_new_registration_between_selection_and_lock_prevents_stale_verifier_invocation(self):
        from whetstone.clients import canonicalize_reviewer_input
        import whetstone.vnext_semantic_run as runtime
        fixture = self.subject.fixture
        feedback = deepcopy(fixture.f.feedback)
        feedback['round_number'] = 2
        feedback['feedback'][0]['claim'] += ' Another fictional clarification.'
        canonicalize_reviewer_input(feedback)
        feedback_ref = fixture.save_input('inputs/feedback-2.json', feedback)
        advice_ref = fixture.save_input('inputs/advice-2.json', {**deepcopy(fixture.f.advice), 'feedback': feedback_ref})
        record = {**deepcopy(fixture.record), 'round_number': 2, 'feedback': feedback_ref, 'advice': advice_ref}
        self.run.admit_round(record)
        original = runtime.run_semantic_request
        def race(*args, **kwargs):
            self.run.run_round(round_number=2, client=requests.admission_tests.Client(), decided_at=STAMP)
            return original(*args, **kwargs)
        with patch.object(runtime, 'run_semantic_request', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'active semantic round changed'):
                self.invoke()
        self.assertEqual(self.subject.client.calls, 0)
        self.assertFalse(self.subject.path('request.json').exists())
        with self.assertRaisesRegex(ValueError, 'historical candidate'): self.status()


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticRunAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests.SemanticRequestTests.setUpClass()

    def test_decision_support_does_not_infer_round_consumer_support(self):
        from test_vnext_semantic_decisions import decision_suite
        subject = requests.SemanticRequestTests()
        self.addCleanup(subject.doCleanups)
        with patch.object(requests, 'request_suite', decision_suite): subject.setUp()
        run = stored_run(subject)
        before = {path: path.read_bytes() for path in subject.fixture.root.rglob('*') if path.is_file()}
        with self.assertRaisesRegex(ValueError, 'round algorithm'):
            run.semantic_status(round_number=1)
        with self.assertRaisesRegex(ValueError, 'round algorithm'):
            run.verify_round(round_number=1, decided_at=STAMP, client=subject.client)
        self.assertEqual(subject.client.calls, 0)
        self.assertEqual({path: path.read_bytes() for path in subject.fixture.root.rglob('*') if path.is_file()}, before)

    def test_deterministic_rejection_recovery_never_opens_semantic_work(self):
        import test_vnext_proposal_closeout as closeout
        helper = closeout.ProposalCloseoutTests()
        self.addCleanup(helper.doCleanups)
        with patch.object(closeout.fixtures, 'consuming_suite', run_suite): helper.setUp()
        editor = helper.failing_client()
        helper.request(editor)
        helper.register()
        run = stored_run(SimpleNamespace(fixture=helper.f, store=helper.store, admission=helper.admission))
        self.assertEqual(run.semantic_status(round_number=1)['processing_gate'], 'verification_commit')
        report, _ = run.verify_round(round_number=1, decided_at=STAMP, client=object(), continuation=True)
        self.assertEqual((report['terminal_state'], report['resume']['reason']),
                         ('HALTED_ARTIFACT_INVALID', 'vnext_preservation_failed'))
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_REJECTED')
        self.assertEqual(run.verify_round(round_number=1, decided_at=STAMP, client=object())[0], report)
        self.assertFalse(list(helper.f.root.rglob('semantic_verification.json')))
        self.assertEqual(editor.calls, 1)


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticOperatorRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests.SemanticRequestTests.setUpClass()

    def test_real_authority_choice_pauses_with_final_rejection_and_exact_request_id(self):
        helper = requests.SemanticOperatorRequestTests()
        self.addCleanup(helper.doCleanups)
        with patch.object(requests, 'request_suite', run_suite):
            subject = helper.make_subject()
        run = stored_run(subject)
        seed = subject.store.read('rounds/current_verified.json')
        report, _ = run.verify_round(round_number=1, decided_at=STAMP, client=subject.client)
        request = subject.inspect().result.authority_request
        self.assertEqual(report['terminal_state'], 'PAUSED_DECISION')
        self.assertEqual(report['resume']['reason'], 'vnext_operator_decision_required')
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_REJECTED')
        self.assertTrue(report['latest_candidate']['verification_decision_final'])
        self.assertEqual(report['outstanding_decision_ids'], [request['decision_id']])
        self.assertFalse(report['resume']['permitted'])
        self.assertEqual(run.verify_round(round_number=1, decided_at=STAMP, client=object())[0], report)
        with self.assertRaisesRegex(ValueError, 'not technically resumable'):
            run.verify_round(round_number=1, decided_at=STAMP, client=object(), continuation=True)
        self.assertEqual(subject.store.read('rounds/current_verified.json'), seed)
        self.assertEqual((subject.client.calls, subject.editor.calls), (1, 1))
