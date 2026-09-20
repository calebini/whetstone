"""Phase 2 prerequisite checks through genuine V review/decision/promotion journals."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import binding_id
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_protocol import RULES
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedPhase2EligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def inspect(self, f):
        before = self.files(f)
        result = f.run.phase2_eligibility()
        self.assertEqual(self.files(f), before)
        self.assertFalse(result.entry_permitted)
        self.assertFalse(result.resume_permitted)
        self.assertFalse(result.apply_back_permitted)
        self.assertEqual(result.phase2_blockers, ('phase2_configuration_unbound', 'phase2_execution_unavailable'))
        return result

    def complete(self, f, client):
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        f.run.finish_phase1()
        f.run.reconcile_phase1_state()

    def register(self, f):
        self.assertEqual(f.run.request(round_number=1, client=f.editor).value.status, 'complete')
        return f.run.register(round_number=1, created_at=STAMP).value

    def verifier(self, f, creation):
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=creation['candidate_id'])
        return runtime.history.verified.semantic.Client(context), context

    def test_complete_current_profile_coverage_committed_closeout_and_state_are_required(self):
        f, client = self.start(phase2_eligibility_contract=True, profiles=[
            {'name': 'structural_integrity', 'budget': 1}, {'name': 'determinism', 'budget': 1}])
        self.assertFalse(self.inspect(f).phase1_prerequisites_met)
        client.callback = clean_response
        f.run.review_next(client=client)
        self.assertIn('phase1_acceptance_not_established', self.inspect(f).phase1_blockers)
        f.run.review_next(client=client)
        self.assertEqual(self.inspect(f).phase1_blockers, ('phase1_closeout_required',))
        closeout = f.run.phase1_closeout()
        publish = f.store.publish
        def stop(token, path, value):
            if path == closeout.evidence_ref['path']: raise OSError('report only')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'report only'): f.run.finish_phase1()
        self.assertIsNone(self.inspect(f).closeout_ref)
        f.run.finish_phase1()
        self.assertEqual(self.inspect(f).phase1_blockers, ('phase1_state_recovery_required',))
        f.run.reconcile_phase1_state()
        self.reopen(f)
        # Inspection cannot depend on acquiring a mutation fence.
        with patch.object(f.store, 'locked', side_effect=AssertionError('reader acquired writer lock')):
            ready = self.inspect(f)
        self.assertTrue(ready.phase1_prerequisites_met)
        self.assertEqual(ready.phase1_blockers, ())
        self.assertEqual(ready.closeout_ref, closeout.evidence_ref)
        self.assertEqual(ready.review_configuration, f.run._record['review_configuration'])
        self.assertEqual(ready.current_pointer['hash'], sha256_bytes(f.store.read('rounds/current_verified.json')))
        for reference in (ready.current_verified_draft, ready.current_verified_map):
            self.assertEqual(reference['hash'], sha256_bytes(f.store.read(reference['path'])))
        ready.current_verified_draft['hash'] = '0' * 64
        self.assertNotEqual(self.inspect(f).current_verified_draft, ready.current_verified_draft)
        self.assertEqual(client.calls, 2)

    def test_global_nonfocus_debt_cannot_supply_phase2_prerequisites(self):
        f, client = self.start(phase2_eligibility_contract=True)
        def outside(packet):
            packet['feedback']['feedback'][0]['in_scope'] = False
            packet['classifications'][0]['classification'] = 'deferable'
            return canonical_json_bytes(packet)
        client.callback = outside
        f.run.review_next(client=client)
        f.run.finish_phase1()
        f.run.reconcile_phase1_state()
        result = self.inspect(f)
        self.assertEqual(result.review_gate, 'review_complete')
        self.assertTrue(result.state_current)
        self.assertEqual(result.phase1_blockers, ('phase1_acceptance_not_established',))
        self.assertFalse(result.phase1_prerequisites_met)
        self.assertEqual(client.calls, 1)

    def test_candidate_verification_and_promotion_do_not_replace_current_review_evidence(self):
        f, client = self.start(phase2_eligibility_contract=True, budget=2)
        seed = self.inspect(f).current_pointer
        self.review(f, client)
        creation = self.register(f)
        view = self.inspect(f)
        self.assertEqual(view.phase1_blockers, ('candidate_verification_required',))
        self.assertEqual(view.latest_candidate, creation)
        verifier, _ = self.verifier(f, creation)
        f.run.verify(client=verifier, decided_at=STAMP)
        view = self.inspect(f)
        self.assertEqual(view.current_pointer, seed)
        self.assertEqual(view.phase1_blockers, ('promotion_required',))
        self.assertIsNone(view.accepted)
        f.run.promote(prepared_at=STAMP)
        view = self.inspect(f)
        self.assertNotEqual(view.current_pointer, seed)
        self.assertIn('phase1_acceptance_not_established', view.phase1_blockers)
        self.complete(f, client)
        self.assertTrue(self.inspect(f).phase1_prerequisites_met)
        self.assertEqual((client.calls, f.editor.calls, verifier.calls), (2, 1, 1))

    def test_bound_operator_choice_is_exposed_and_final_rejection_cannot_grant_entry(self):
        original = runtime.unit.UnitPreflightTests.setUp
        def with_authority(owner):
            original(owner)
            fixture = owner.c.f
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
        with patch.object(runtime.unit.UnitPreflightTests, 'setUp', with_authority):
            f, client = self.start(phase2_eligibility_contract=True)
        self.review(f, client)
        creation = self.register(f)
        verifier, context = self.verifier(f, creation)
        packet = context.packet
        target = next(row for row in packet['authority_map']['bindings'] if row['role'] == 'mutable_target')
        authority = packet['dependency_context'][0]
        def alternative(identifier, text, interpretation):
            raw = text.encode()
            return dict(authority_binding_id=identifier, interpretation=interpretation,
                evidence=dict(byte_start=0, byte_end=len(raw), content_hash=sha256_bytes(raw), text=text))
        response = json.loads(verifier.valid)
        response.update(authority_compliance='uncertain', operator_decision_required=True,
            verdict='operator_decision_required', authority_choice=dict(question='Which interpretation should a new transaction address?',
                authority_scope=target['authority_scopes'][0], alternatives=[
                    alternative(target['binding_id'], packet['seed'], 'Waiting is scoped to queue startup.'),
                    alternative(authority['binding']['binding_id'], authority['content'], 'Waiting is scoped to every work start.')]),
            uncertainty_resolutions=[dict(field_path='authority_compliance', policy_rule_id=RULES['authority_choice'],
                disposition='operator_decision_required', decision_id=None)])
        verifier.responses = [canonical_json_bytes(response)]
        decision = f.run.verify(client=verifier, decided_at=STAMP).value.decision
        self.assertEqual(decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        view = self.inspect(f)
        self.assertEqual(view.phase1_blockers, ('operator_decision_required',))
        self.assertEqual(view.outstanding_decision_ids, tuple(decision['outstanding_decision_ids']))
        self.assertTrue(view.outstanding_decision_ids)
        self.assertIsNone(view.closeout_ref)
        self.assertEqual((client.calls, f.editor.calls, verifier.calls), (1, 1, 1))

        f, client = self.start(phase2_eligibility_contract=True)
        self.review(f, client)
        creation = self.register(f)
        verifier, _ = self.verifier(f, creation)
        response = json.loads(verifier.valid)
        response.update(authority_compliance='uncertain', verdict='reject', uncertainty_resolutions=[
            dict(field_path='authority_compliance', policy_rule_id=RULES['authority_reject'],
                 disposition='reject', decision_id=None)])
        verifier.responses = [canonical_json_bytes(response)]
        f.run.verify(client=verifier, decided_at=STAMP)
        view = self.inspect(f)
        self.assertEqual(view.phase1_blockers, ('candidate_rejected',))
        self.assertEqual(view.outstanding_decision_ids, ())
        self.assertEqual((client.calls, f.editor.calls, verifier.calls), (1, 1, 1))

    def test_exhausted_post_promotion_budget_and_pending_review_do_not_grant_readiness(self):
        f, client = self.start(phase2_eligibility_contract=True, budget=1)
        self.review(f, client)
        creation = self.register(f)
        verifier, _ = self.verifier(f, creation)
        f.run.verify(client=verifier, decided_at=STAMP)
        f.run.promote(prepared_at=STAMP)
        f.run.finish_phase1()
        f.run.reconcile_phase1_state()
        view = self.inspect(f)
        self.assertEqual(view.review_gate, 'budget_exhausted')
        self.assertIn('phase1_budget_exhausted', view.phase1_blockers)
        self.assertFalse(view.phase1_prerequisites_met)
        self.assertEqual((client.calls, f.editor.calls, verifier.calls), (1, 1, 1))
        f, client = self.start(phase2_eligibility_contract=True)
        def timeout(packet): raise TimeoutError('fictional timeout')
        client.callback = timeout
        f.run.review_next(client=client)
        view = self.inspect(f)
        self.assertEqual(view.review_gate, 'pending')
        self.assertIn('phase1_pending', view.phase1_blockers)
        self.assertFalse(view.phase1_prerequisites_met)
        self.assertEqual(client.calls, 1)

    def test_stale_success_and_corrupt_current_map_or_closeout_never_supply_readiness(self):
        f, client = self.start(phase2_eligibility_contract=True)
        state = json.loads(f.store.read('rounds/run_state.json'))
        state.update(terminal_state='PHASE_1_STABLE', ready_for_phase_2=True,
            convergence={'target_phase': 'final', 'target_mode': 'strict'},
            vnext_phase1_closeout={'path': '../forged-success.json', 'hash': '0' * 64})
        (f.root/'rounds/run_state.json').write_bytes(canonical_json_bytes(state))
        view = self.inspect(f)
        self.assertFalse(view.phase1_prerequisites_met)
        self.assertIn('phase1_state_recovery_required', view.phase1_blockers)
        self.complete(f, client)
        ready = self.inspect(f)
        self.assertTrue(ready.phase1_prerequisites_met)
        for reference in (ready.current_verified_map, ready.closeout_ref, ready.terminal_report_ref):
            path = f.root / reference['path']
            raw = path.read_bytes()
            path.write_bytes(b'{}')
            before = self.files(f)
            with self.assertRaises(ValueError): f.run.phase2_eligibility()
            self.assertEqual(self.files(f), before)
            path.write_bytes(raw)
        self.assertEqual(client.calls, 1)

    def test_mirror_and_orphan_recovery_precede_readiness_without_repair(self):
        f, client = self.start(phase2_eligibility_contract=True)
        self.complete(f, client)
        (f.root/'spec.md').unlink()
        view = self.inspect(f)
        self.assertEqual(view.phase1_blockers, ('materialization_required',))
        self.assertIsNone(view.accepted)
        self.assertIsNone(view.closeout_ref)
        f, client = self.start(phase2_eligibility_contract=True)
        self.review(f, client)
        f.run.request(round_number=1, client=f.editor)
        publish = f.store.publish
        def stop(token, path, value):
            if path == 'rounds/candidate_index/creation-1.json': raise OSError('registration interrupted')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'registration interrupted'): f.run.register(round_number=1, created_at=STAMP)
        self.reopen(f)
        view = self.inspect(f)
        self.assertEqual(view.phase1_blockers, ('registration_recovery_required',))
        self.assertIsNone(view.latest_candidate)
        self.assertEqual((client.calls, f.editor.calls), (1, 1))

    def test_missing_consumer_pin_and_unsupported_review_mode_refuse_readonly(self):
        f, client = self.start(operator_status_contract=True)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'Phase 2 eligibility contract'): f.run.phase2_eligibility()
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 0)
        f, client = self.start(phase2_eligibility_contract=True, mode='vertical')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'standard horizontal'): f.run.phase2_eligibility()
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 0)
