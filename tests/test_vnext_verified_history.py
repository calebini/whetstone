"""Genuine candidate evidence, fixture-only pointer publication, real replay.

The publisher below is test setup, not qualification of the promotion writer
or two-stage recovery protocol, which remain separate implementation work.
"""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_proposal_requests import _Journal, logical_request_id, run_proposal_request
from whetstone.vnext_proposal_handoff import register_completed_proposal_request, registry_for_proposal_requests
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_identity import binding_id
from whetstone.vnext_semantic_answers import ANSWER_SCHEMAS, prepare_answer
from whetstone.vnext_semantic_followup_preflight import _read_followup_evidence
from whetstone.vnext_semantic_protocol import RULES
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_verified_history import VerifiedHistoryAdmission, _VerifiedAnswerSource, _VerifiedTransactions
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal, VerifiedSemanticRequestJournal
from vnext_fixtures import STAMP
import test_vnext_verified_semantics as verified
import test_vnext_semantic_answers as answers


class _CurrentRoundFixture:
    """Test-only writer selection around the production historical reader."""
    def __init__(self, store, history, number):
        self.store, self.history, self.number = store, history, number
        self.suite_path, self._refs = history.suite_path, history._refs
        self.load_inputs = self.Inputs(self)

    def _base(self, read): return self.history._base(read)

    def validate_authority(self, read):
        proof = self.history._prove(read)
        values = proof.admission.load_inputs(read, self.number)
        require(values['base_pointer_ref'] == proof.latest, 'fixture writer requires its exact current base')
        proof.guard(read)

    class Inputs:
        def __init__(self, owner): self.owner = owner
        def __call__(self, read, number): return self.owner.history.load_inputs(read, number)
        def for_proposal(self, read, number, identifier):
            return self.owner.history.load_inputs.for_proposal(read, number, identifier)
        def request_journal(self, store, number, identifier):
            if identifier is None:
                return _Journal(store, lambda read: self(read, number))
            return self.owner.history.load_inputs.request_journal(store, number, identifier)


class _FollowupFixture(_CurrentRoundFixture):
    def __init__(self, store, history, reference):
        super().__init__(store, history, 1)
        self.reference = reference
        self.load_inputs = self.Inputs(self)

    class Inputs(_CurrentRoundFixture.Inputs):
        def __call__(self, read, number):
            proof = self.owner.history._prove(read)
            selected = _VerifiedTransactions(proof.store, original=proof.admission,
                                              selected_ref=self.owner.reference)
            return selected.load_inputs(read, number)


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): verified.VerifiedSemanticTests.setUpClass()

    files = verified.VerifiedSemanticTests.files
    prepared_tail = verified.VerifiedSemanticTests.prepared_tail
    run_request = verified.VerifiedSemanticTests.run_request
    ready = verified.VerifiedSemanticTests.ready

    def fixture(self, *, history_contract=True, extra_algorithms=(), register_candidate=True, extra_schemas=()):
        algorithms = ('vnext_semantic_answers_v1', 'vnext_semantic_followup_preflight_v1',
                      'vnext_semantic_followup_admission_v1')
        if history_contract: algorithms += ('vnext_verified_history_v1',)
        algorithms += tuple(extra_algorithms)
        return verified.VerifiedSemanticTests.fixture(self, extra_algorithms=algorithms, register_candidate=register_candidate,
            extra_schemas=ANSWER_SCHEMAS | set(extra_schemas) | {'mutation_plan_v3', 'vnext_semantic_followup_input_v1',
                                          'vnext_semantic_followup_selection_v1'})

    def owner(self, f):
        return VerifiedHistoryAdmission(f.store, suite_path=f.admission.suite_path,
            descriptor_ref=f.admission._refs['descriptor'], review_ref=f.admission._refs['review'],
            seed_map_ref=f.admission._refs['seed_map'], round_refs=f.admission._refs['rounds'])

    def promote_fixture(self, f, final):
        previous_raw = f.store.read('rounds/current_verified.json')
        previous = json.loads(previous_raw)
        intent_path, intent, event_path, event = self.prepared_tail(f, final)
        creation = f.creation
        pointer = {**previous, 'promotion_ordinal': intent['next_promotion_ordinal'],
            'verified_draft_path': creation['candidate_path'], 'verified_draft_hash': creation['candidate_hash'],
            'verified_section_identity_map_path': creation['candidate_section_identity_map_path'],
            'verified_section_identity_map_hash': creation['candidate_section_identity_map_hash'],
            'source_transaction_id': creation['transaction_id'], 'source_candidate_id': creation['candidate_id'],
            'source_candidate_creation_ordinal': creation['candidate_creation_ordinal'],
            'source_candidate_creation_event_path': intent['candidate_creation_event_path'],
            'source_candidate_creation_event_hash': intent['candidate_creation_event_hash'],
            'candidate_verification_path': final.pointer['current_decision_path'],
            'candidate_verification_hash': final.pointer['current_decision_hash'],
            'promotion_intent_path': intent_path, 'promotion_intent_hash': sha256_bytes(canonical_json_bytes(intent)),
            'promotion_disposition_event_path': event_path,
            'promotion_disposition_event_hash': sha256_bytes(canonical_json_bytes(event)),
            'previous_verified_draft_hash': previous['verified_draft_hash'],
            'previous_verified_pointer_path': f"rounds/verified_history/current-verified-{previous['promotion_ordinal']}.json",
            'previous_verified_pointer_hash': sha256_bytes(previous_raw), 'promoted_at': STAMP}
        raw = canonical_json_bytes(pointer)
        path = f"rounds/verified_history/current-verified-{pointer['promotion_ordinal']}.json"
        with f.store.locked(f.admission.validate_authority) as token:
            f.store.publish(token, path, pointer)
            def transition(old, new):
                self.assertEqual(old, previous_raw)
                self.assertEqual(new, raw)
            f.store.replace_pointer(token, 'rounds/current_verified.json', expected=previous_raw,
                snapshot={'path': path, 'hash': sha256_bytes(raw)}, validate_transition=transition)
        return pointer

    def promoted(self):
        f = self.ready()
        self.run_request(f)
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        pointer = self.promote_fixture(f, final)
        return f, pointer

    def test_genuine_promoted_history_replays_original_base_and_inventory_without_writes(self):
        f, pointer = self.promoted()
        owner = self.owner(f)
        before = self.files(f)
        with patch.object(f.store, 'publish', side_effect=AssertionError('read-only history')):
            view = owner.inspect()
            self.assertEqual([item['promotion_ordinal'] for item in view.pointers], [0, 1])
            self.assertEqual(view.creations, (f.creation,))
            self.assertFalse(view.orphans)
            _, current = owner._base(f.store.read)
            self.assertEqual(current['base'], f.store.read(pointer['verified_draft_path']))
            inventory_path = f.creation['candidate_path'].rsplit('/', 1)[0] + '/preservation_inventory_candidate.json'
            self.assertEqual(current['base_inventory'], json.loads(f.store.read(inventory_path)))
            original = owner.load_inputs(f.store.read, 1)
            self.assertEqual(original['base'], original['seed'])
            self.assertNotEqual(original['base_pointer_ref'], current['base_pointer_ref'])
            self.assertNotIn('base_inventory', original)
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))
        self.assertEqual(self.files(f), before)
        with self.assertRaisesRegex(ValueError, 'read-only'):
            with owner.store.locked(owner.validate_authority): pass

    def test_committed_pointer_cannot_hide_missing_original_verifier_response(self):
        f = self.ready()
        self.run_request(f)
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        request = VerifiedSemanticRequestJournal(f.store, admission=f.admission, candidate_id=f.identifier)
        self.promote_fixture(f, final)
        (f.root / request.directory / 'attempts/1/response.json').unlink()
        before = self.files(f)
        with self.assertRaises((ValueError, FileNotFoundError)): self.owner(f).inspect()
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.client.calls, 1)

    def test_history_requires_its_own_pinned_algorithm(self):
        f = self.fixture(history_contract=False)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'history algorithm is outside supported suite'):
            self.owner(f).inspect()
        self.assertEqual(self.files(f), before)

    def test_fresh_replay_rejects_altered_editor_source_after_an_earlier_success(self):
        f, _ = self.promoted()
        owner = self.owner(f)
        observed = owner.inspect()
        self.assertEqual(observed.pointers[-1]['promotion_ordinal'], 1)
        request_id = logical_request_id(f.creation['job_id'], f.creation['transaction_id'])
        path = f.root / f'rounds/client_requests/{request_id}/attempts/1/response.json'
        path.write_bytes(path.read_bytes() + b' ')
        before = self.files(f)
        with self.assertRaises(ValueError): owner.inspect()
        self.assertEqual(self.files(f), before)
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def test_promotion_cannot_use_itself_as_its_transaction_base(self):
        f, pointer = self.promoted()
        record = json.loads(f.store.read(f.admission._refs['rounds'][1]['path']))
        record['base_pointer'] = {'path': 'rounds/verified_history/current-verified-1.json',
                                  'hash': sha256_bytes(canonical_json_bytes(pointer))}
        path = 'inputs/self-dependent-history-round.json'
        (f.root / path).write_bytes(canonical_json_bytes(record))
        owner = VerifiedHistoryAdmission(f.store, suite_path=f.admission.suite_path,
            descriptor_ref=f.admission._refs['descriptor'], review_ref=f.admission._refs['review'],
            seed_map_ref=f.admission._refs['seed_map'], round_refs={
                1: {'path': path, 'hash': sha256_bytes(canonical_json_bytes(record))}})
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'base has not been proven'): owner.inspect()
        self.assertEqual(self.files(f), before)

    def test_changed_actual_head_during_replay_refuses_without_repair(self):
        f, _ = self.promoted()
        owner = self.owner(f)
        original = self.files(f)
        read = f.store.read
        triggered = []
        def change(path):
            raw = read(path)
            if path.endswith('/attempts/1/response.json') and not triggered:
                triggered.append(path)
                (f.root / 'rounds/current_verified.json').write_bytes(b'{}')
            return raw
        with patch.object(f.store, 'read', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'authority changed during replay'): owner.inspect()
        self.assertTrue(triggered)
        after = self.files(f)
        self.assertEqual(after['rounds/current_verified.json'], b'{}')
        self.assertEqual({path: raw for path, raw in after.items() if path != 'rounds/current_verified.json'},
                         {path: raw for path, raw in original.items() if path != 'rounds/current_verified.json'})

    def test_inventory_capture_remains_bound_after_semantic_replay(self):
        f, _ = self.promoted()
        owner = self.owner(f)
        path = f.root / (f.creation['candidate_path'].rsplit('/', 1)[0] + '/preservation_inventory_candidate.json')
        changed = json.loads(path.read_bytes())
        changed['seed_draft_hash'] = 'f' * 64
        raw = canonical_json_bytes(changed)
        inspect = VerifiedSemanticDecisionJournal.inspect
        def swap(journal, candidate_id):
            result = inspect(journal, candidate_id)
            path.write_bytes(raw)
            return result
        with patch.object(VerifiedSemanticDecisionJournal, 'inspect', swap):
            with self.assertRaisesRegex(ValueError, 'hash mismatch'): owner.inspect()
        self.assertEqual(path.read_bytes(), raw)

    def test_historical_request_factory_refuses_another_storage_owner(self):
        f = self.fixture()
        owner = self.owner(f)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'another storage owner'):
            owner.load_inputs.request_journal(object(), 1, f.creation['proposal_id'])
        self.assertEqual(self.files(f), before)

    def test_second_genuine_promotion_replays_both_original_bases(self):
        f, first_pointer = self.promoted()
        first_id = f.identifier
        first_calls = (f.editor.calls, f.client.calls)
        original = self.files(f)
        old_record = json.loads(f.store.read(f.admission._refs['rounds'][1]['path']))
        feedback = json.loads(f.store.read(old_record['feedback']['path']))
        feedback.update(round_number=2, draft_hash=first_pointer['verified_draft_hash'])
        advice = json.loads(f.store.read(old_record['advice']['path']))
        feedback_path = 'inputs/history-test-feedback-2.json'
        feedback_ref = {'path': feedback_path, 'hash': sha256_bytes(canonical_json_bytes(feedback))}
        advice.update(base_draft_hash=first_pointer['verified_draft_hash'], feedback=feedback_ref)
        advice_path = 'inputs/history-test-advice-2.json'
        record = {**old_record, 'round_number': 2, 'feedback': feedback_ref,
            'advice': {'path': advice_path, 'hash': sha256_bytes(canonical_json_bytes(advice))},
            'base_pointer': {'path': 'rounds/verified_history/current-verified-1.json',
                             'hash': sha256_bytes(canonical_json_bytes(first_pointer))}}
        record_path = 'inputs/history-test-round-2.json'
        history = self.owner(f)
        with f.store.locked(history.validate_authority) as token:
            for path, value in [(feedback_path, feedback), (advice_path, advice), (record_path, record)]:
                f.store.publish(token, path, value)
        history = VerifiedHistoryAdmission(f.store, suite_path=history.suite_path,
            descriptor_ref=history._refs['descriptor'], review_ref=history._refs['review'],
            seed_map_ref=history._refs['seed_map'], round_refs={**history._refs['rounds'],
                2: {'path': record_path, 'hash': sha256_bytes(canonical_json_bytes(record))}})
        f.admission = _CurrentRoundFixture(f.store, history, 2)
        def revise(packet):
            content = 'Queue always waits before processing begins.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        f.editor = verified.fixtures.Client(revise)
        request = run_proposal_request(f.store, load_inputs=lambda read: f.admission.load_inputs(read, 2),
            validate_authority=f.admission.validate_authority, client=f.editor)
        self.assertEqual(request.status, 'complete')
        print('Second proposal built against genuinely replayed promoted base', flush=True)
        f.creation = register_completed_proposal_request(f.store, round_number=2,
            load_inputs=f.admission.load_inputs, validate_authority=f.admission.validate_authority, created_at=STAMP)
        f.identifier = f.creation['candidate_id']
        f.registry = registry_for_proposal_requests(f.store, load_inputs=f.admission.load_inputs,
                                                    validate_authority=f.admission.validate_authority)
        f.decisions = VerifiedSemanticDecisionJournal(f.registry, admission=f.admission)
        f.decisions.commit(f.identifier, decided_at=STAMP)
        context = load_registered_semantic_context(f.store, admission=f.admission, candidate_id=f.identifier)
        f.client = verified.semantic.Client(context)
        self.assertEqual(self.run_request(f).status, 'complete')
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        self.assertTrue(final.decision['promotion_permitted'])
        print('Second candidate independently verified', flush=True)
        second_pointer = self.promote_fixture(f, final)
        before = self.files(f)
        view = history.inspect()
        self.assertEqual([p['promotion_ordinal'] for p in view.pointers], [0, 1, 2])
        self.assertEqual([c['candidate_id'] for c in view.creations], [first_id, f.identifier])
        first_args = history.load_inputs(f.store.read, 1)
        second_args = history.load_inputs(f.store.read, 2)
        self.assertEqual(first_args['base'], first_args['seed'])
        self.assertEqual(sha256_bytes(second_args['base']), first_pointer['verified_draft_hash'])
        self.assertNotEqual(first_args['base_pointer_ref'], second_args['base_pointer_ref'])
        self.assertEqual(view.pointers[-1], second_pointer)
        self.assertEqual(self.files(f), before)
        self.assertTrue(all(before[path] == raw for path, raw in original.items()
                            if path not in {'rounds/current_verified.json', 'spec.md', 'rounds/run_state.json'}))
        if 'spec.md' in original:
            self.assertEqual(f.store.read('spec.md'), f.store.read(second_pointer['verified_draft_path']))
            self.assertEqual(json.loads(f.store.read('rounds/run_state.json'))['vnext_current_verified'], second_pointer)
        self.assertEqual(first_calls, (1, 1))
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def followup_fixture(self, *, publish_selection=True):
        unit = verified.fixtures.fixtures.UnitPreflightTests
        setup = unit.setUp
        def with_authority(test):
            setup(test)
            fixture = test.c.f
            reference = fixture.save('inputs/waiting-authority.md', b'Queue waiting applies to each work start.\n')
            target = next(row for row in fixture.authority['bindings'] if row['role'] == 'mutable_target')
            authority = dict(path=reference['path'], content_hash=reference['hash'], role='normative_authority',
                authority_scopes=target['authority_scopes'], effective_horizon='current', mutable=False,
                may_introduce_requirements=True)
            authority['binding_id'] = binding_id(authority)
            fixture.authority['bindings'].append(authority)
            fixture.authority['precedence'] = [{'authority_scope': scope,
                'ordered_binding_ids': [authority['binding_id'], target['binding_id']], 'conflict_policy': 'pause'}
                for scope in target['authority_scopes']]
            fixture.rebind()
        with patch.object(unit, 'setUp', with_authority): f = self.ready()
        context = load_registered_semantic_context(f.store, admission=f.admission, candidate_id=f.identifier)
        packet = context.packet
        target = next(row for row in packet['authority_map']['bindings'] if row['role'] == 'mutable_target')
        authority = packet['dependency_context'][0]
        def alternative(identifier, text, interpretation):
            raw = text.encode()
            return dict(authority_binding_id=identifier, interpretation=interpretation,
                evidence=dict(byte_start=0, byte_end=len(raw), content_hash=sha256_bytes(raw), text=text))
        response = json.loads(f.client.valid)
        response.update(authority_compliance='uncertain', operator_decision_required=True,
            verdict='operator_decision_required', authority_choice=dict(question='Which interpretation should a new transaction address?',
                authority_scope=target['authority_scopes'][0], alternatives=[
                    alternative(target['binding_id'], packet['seed'], 'Waiting is scoped to queue startup.'),
                    alternative(authority['binding']['binding_id'], authority['content'], 'Waiting is scoped to every work start.')]),
            uncertainty_resolutions=[dict(field_path='authority_compliance', policy_rule_id=RULES['authority_choice'],
                disposition='operator_decision_required', decision_id=None)])
        f.client.responses = [canonical_json_bytes(response)]
        self.assertEqual(self.run_request(f).status, 'complete')
        parent = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        self.assertEqual(parent.decision['semantic_result'], 'operator_decision_required')
        parent_id = f.identifier
        if not publish_selection: return f, parent_id, None
        history = self.owner(f)
        source = _VerifiedAnswerSource(f.store, admission=history, candidate_id=parent_id, require_current=True)
        answer = prepare_answer(answers.input_for(source), request=source.request, context=source.context,
            request_ref=source.request_ref, decision_ref=source.decision_ref, suite=source.suite)
        receipt = source.receipt(answer)
        reference = source.receipt_ref(receipt)
        with f.store.locked(f.admission.validate_authority) as token:
            source.synchronize(token)
            f.store.publish(token, source.response_ref(answer)['path'], answer)
            f.store.publish(token, reference['path'], receipt)
        evidence = _read_followup_evidence(f.store, admission=history, candidate_id=parent_id,
                                           reference=reference, source_type=_VerifiedAnswerSource)
        arguments = history.load_inputs(f.store.read, 1)
        preflight = prepare_unit_preflight(**{**arguments, 'semantic_followup': evidence})
        record = dict(schema_version='vnext-semantic-followup-input-v1', job_id=f.creation['job_id'], round_number=1,
            transaction_id=preflight.plan['transaction_id'], base_pointer=arguments['base_pointer_ref'],
            source_creation=source.context.packet['creation_ref'], source_verification=source.decision_ref,
            answer_receipt=reference, editing_plan_hash=preflight.plan['semantic_origin']['editing_plan_hash'],
            mutation_plan_hash=sha256_bytes(canonical_json_bytes(preflight.plan)))
        path = f"rounds/round-1/transactions/{record['transaction_id']}/admission.json"
        selected_ref = {'path': path, 'hash': sha256_bytes(canonical_json_bytes(record))}
        selection = dict(schema_version='vnext-semantic-followup-selection-v1', job_id=f.creation['job_id'],
                         candidate_id=parent_id, transaction_input=selected_ref)
        with f.store.locked(f.admission.validate_authority) as token:
            f.store.publish(token, path, record)
            f.store.publish(token, f.creation['candidate_path'].rsplit('/', 1)[0] + '/followup_transaction.json', selection)
        return f, parent_id, selected_ref

    def test_promoted_same_round_followup_replays_rejected_parent_and_exact_answer(self):
        f, parent_id, selected_ref = self.followup_fixture()
        history = self.owner(f)
        print('V follow-up fixture retained an explicit answer and distinct transaction', flush=True)
        before = self.files(f)
        parent_calls = (f.editor.calls, f.client.calls)
        f.admission = _FollowupFixture(f.store, history, selected_ref)
        f.editor = verified.fixtures.Client()
        request = run_proposal_request(f.store, load_inputs=lambda read: f.admission.load_inputs(read, 1),
            validate_authority=f.admission.validate_authority, client=f.editor)
        self.assertEqual(request.status, 'complete')
        f.creation = register_completed_proposal_request(f.store, round_number=1,
            load_inputs=f.admission.load_inputs, validate_authority=f.admission.validate_authority, created_at=STAMP)
        f.identifier = f.creation['candidate_id']
        self.assertNotEqual(f.identifier, parent_id)
        f.registry = registry_for_proposal_requests(f.store, load_inputs=f.admission.load_inputs,
                                                    validate_authority=f.admission.validate_authority)
        f.decisions = VerifiedSemanticDecisionJournal(f.registry, admission=f.admission)
        f.decisions.commit(f.identifier, decided_at=STAMP)
        context = load_registered_semantic_context(f.store, admission=f.admission, candidate_id=f.identifier)
        f.client = verified.semantic.Client(context)
        self.assertEqual(self.run_request(f).status, 'complete')
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        self.assertTrue(final.decision['promotion_permitted'])
        self.promote_fixture(f, final)
        print('V follow-up independently verified and fixture pointer committed', flush=True)
        current = self.files(f)
        view = history.inspect()
        self.assertEqual([item['candidate_id'] for item in view.creations], [parent_id, f.identifier])
        self.assertEqual(view.pointers[-1]['source_candidate_id'], f.identifier)
        self.assertEqual([item['round_number'] for item in view.creations], [1, 1])
        self.assertTrue(all(current[path] == raw for path, raw in before.items()
                            if path != 'rounds/current_verified.json'))
        self.assertEqual(self.files(f), current)
        self.assertEqual(parent_calls, (1, 1))
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))


if __name__ == '__main__': unittest.main()
