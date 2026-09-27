"""Vertical V journeys use actual journals/promotions and injected local clients."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_vertical_phase1 import merge_packets
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerticalPhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def vertical(self, *, budget=2, **options):
        return self.start(mode='vertical', vertical_contract=True, status_contract=True,
            phase2_eligibility_contract=True, profiles=[{'name':'structural_integrity','budget':budget},
                                                       {'name':'determinism','budget':budget}], **options)

    def cycle(self, f, client):
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        self.assertEqual(f.run.review_next(client=client).status, 'complete')

    def promote(self, f, number=3, ordinal=1):
        self.assertEqual(f.run.request(round_number=number, client=f.editor).value.status, 'complete')
        f.creation = f.run.register(round_number=number, created_at=STAMP).value
        f.identifier = f.creation['candidate_id']
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=f.identifier)
        verifier = runtime.history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], ordinal)
        return verifier

    def test_clean_cycle_has_independent_assets_and_complete_phase1(self):
        f, client = self.vertical(phase2_binding_contract=True)
        client.callback = clean_response
        self.cycle(f, client)
        view = f.run.phase1_status()
        self.assertTrue(view.all_profiles_clean)
        self.assertIsNone(view.review_round)
        self.assertEqual(view.review_round_budget, 6)
        self.assertEqual([p.rounds_used for p in view.profiles], [1,1])
        for number, profile in [(1,'structural_integrity'), (2,'determinism')]:
            prefix = f'rounds/round-{number}'
            metadata = json.loads(f.store.read(prefix+'/profile_used.yaml'))
            self.assertEqual((metadata['profile'],metadata['round_kind']), (profile,'review_only'))
            self.assertEqual(f.store.read(prefix+'/draft_before.md'), f.store.read(prefix+'/draft_after.md'))
            self.assertTrue(metadata['resolved_focus_anchors'])
            self.assertEqual(json.loads(f.store.read(prefix+'/context_snapshot.json')), [])
        result = f.run.finish_phase1()
        self.assertTrue(result.accepted)
        self.assertEqual(result.report['terminal_state'], 'PHASE_1_STABLE')
        self.assertEqual(result.evidence['vertical_merges'], [])
        f.run.reconcile_phase1_state()
        self.assertTrue(f.run.phase2_eligibility().phase1_prerequisites_met)
        from test_vnext_verified_phase2_binding import VerifiedPhase2BindingTests
        config = VerifiedPhase2BindingTests.config(self, f)
        before = self.files(f)
        with self.assertRaises(ValueError): f.run.bind_phase2_entry(config)
        config['review_mode'] = 'vertical'
        with self.assertRaises(ValueError): f.run.bind_phase2_entry(config)
        self.assertEqual(self.files(f), before)
        self.reopen(f)
        self.assertEqual(f.run.finish_phase1(), result)
        self.assertEqual(client.calls, 2)
        self.assertEqual(f.editor.calls, 0)

    def test_consolidated_promotion_preserves_provenance_and_requires_full_rereview(self):
        f, client = self.vertical()
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'no completed V review'): f.run.admit_reviewed_round()
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.run.review_status().profile, 'determinism')
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        self.assertEqual(f.run.review_status().round_number, 3)
        admitted = f.run.admit_reviewed_round()
        self.assertEqual(admitted['path'], 'rounds/round-3/proposal_input.json')
        merge = json.loads(f.store.read('rounds/round-3/vertical_merge.json'))
        self.assertEqual([r['source_profile'] for r in merge['provenance']], ['structural_integrity','determinism'])
        feedback = json.loads(f.store.read(merge['feedback']['path']))
        self.assertEqual(len(set(r['feedback_id'] for r in feedback['feedback'])), 2)
        self.assertEqual(feedback['feedback'][0]['issue_id'], feedback['feedback'][1]['issue_id'])
        verifier = self.promote(f)
        self.assertEqual(json.loads(f.editor.prompts[0].splitlines()[-1])['vertical']['merge'], merge)
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=f.identifier)
        self.assertEqual(context.packet['vertical']['merge'], merge)
        self.reopen(f)
        view = f.run.phase1_status()
        self.assertEqual(view.review_round, 4)
        self.assertFalse(view.all_profiles_clean)
        self.assertEqual([p.rounds_used for p in view.profiles], [1,1])
        client.callback = clean_response
        self.cycle(f, client)
        result = f.run.finish_phase1()
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.evidence['vertical_merges']), 1)
        self.assertEqual((client.calls, f.editor.calls, verifier.calls), (4,1,1))
        self.assertEqual(f.store.read('rounds/round-3/draft_after.md'), f.store.read('spec.md'))
        self.assertEqual(f.run._history().load_inputs(f.store.read, 3)['vertical']['merge'], merge)

    def test_partial_cycle_timeout_and_retained_response_resume_without_losing_findings(self):
        f, client = self.vertical()
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        first = f.store.read('rounds/round-1/reviewer_feedback.json')
        def timeout(value): raise TimeoutError('vertical timeout')
        client.callback = timeout
        self.assertEqual(f.run.review_next(client=client).status, 'timeout')
        self.reopen(f)
        self.assertEqual(f.run.review_next(client=client).status, 'continuation_required')
        self.assertEqual([p.rounds_used for p in f.run.phase1_status().profiles], [1,0])
        client.callback = None
        publish = f.store.publish
        pending_id = json.loads(f.store.read('rounds/review_index/request-2.json'))['request_id']
        def stop(token, path, value):
            result = publish(token, path, value)
            if path == f'rounds/client_requests/{pending_id}/attempts/2/response.json':
                raise OSError('retained response interruption')
            return result
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'retained response'): f.run.review_next(client=client, continuation=True)
        self.reopen(f)
        self.assertEqual(f.run.review_next(continuation=True).status, 'complete')
        f.run.admit_reviewed_round()
        merged = json.loads(f.store.read('rounds/round-3/vertical_merge.json'))
        self.assertEqual([r['round_number'] for r in merged['sources']], [1,2])
        self.assertEqual(f.store.read('rounds/round-1/reviewer_feedback.json'), first)
        self.assertEqual(client.calls, 3)
        self.assertEqual([p.rounds_used for p in f.run.phase1_status().profiles], [1,1])

    def test_merge_and_round_commit_interruption_replay_exact_sources(self):
        for suffix in ('/finding_advice.json', '/vertical_merge.json', '/proposal_input.json'):
            with self.subTest(suffix=suffix):
                f, client = self.vertical()
                self.cycle(f, client)
                publish = f.store.publish
                def stop(token, path, value):
                    result = publish(token, path, value)
                    if path == 'rounds/round-3'+suffix: raise OSError('merge acknowledgement lost')
                    return result
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'merge acknowledgement'): f.run.admit_reviewed_round()
                self.reopen(f)
                result = f.run.admit_reviewed_round()
                before = self.files(f)
                self.assertEqual(f.run.admit_reviewed_round(), result)
                self.assertEqual(self.files(f), before)
                self.assertEqual((client.calls, f.editor.calls), (2,0))

    def test_exhaustion_after_promotion_reports_invalidated_profiles_and_recovers_final_state(self):
        f, client = self.vertical(budget=1)
        self.cycle(f, client)
        f.run.admit_reviewed_round()
        self.promote(f)
        result = f.run.finish_phase1()
        self.assertEqual(result.report['terminal_state'], 'TARGET_NOT_REACHED')
        self.assertFalse(result.accepted)
        self.assertEqual(result.technical_failure['profile_status']['unverified_profiles'],
                         ['structural_integrity','determinism'])
        self.assertEqual(result.technical_failure['profile_status']['total_round_budget'], 3)
        self.assertEqual(result.technical_failure['unresolved_major_issues'], [])
        self.assertFalse(f.run.phase2_eligibility().phase1_prerequisites_met)
        materialize = f.store.materialize
        def stop(token, path, raw, **options):
            out = materialize(token, path, raw, **options)
            if path == 'rounds/run_state.json': raise OSError('final state acknowledgement lost')
            return out
        with patch.object(f.store, 'materialize', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'final state'): f.run.reconcile_phase1_state()
        self.reopen(f)
        self.assertTrue(f.run.reconcile_phase1_state().value.state_current)
        self.assertEqual(f.run.finish_phase1(), result)
        self.assertEqual(f.run.review_next(client=client).status, 'budget_exhausted')
        self.assertEqual(client.calls, 2)
        state = json.loads(f.store.read('rounds/run_state.json'))
        self.assertEqual(state['terminal_state'], 'TARGET_NOT_REACHED')
        self.assertFalse(state['ready_for_phase_2'])
        self.assertEqual(state['current_round'], 3)
        self.assertEqual(result.technical_failure['round_number'], 3)
        self.assertIsNone(f.run.phase1_status().review_round)
        self.assertEqual(state['review_round_budget'], 3)

    def test_merge_source_and_provenance_tampering_refuse_before_editor(self):
        f, client = self.vertical()
        self.cycle(f, client)
        f.run.admit_reviewed_round()
        paths = ['rounds/round-1/reviewer_feedback.json','rounds/round-3/vertical_merge.json']
        for path in paths:
            original = f.store.read(path)
            value = json.loads(original)
            if 'provenance' in value: value['provenance'][0]['source_profile'] = 'determinism'
            else: value['feedback'][0]['claim'] += ' changed'
            (f.root/path).write_bytes(canonical_json_bytes(value))
            before = self.files(f)
            with self.assertRaises(ValueError): f.run.request(round_number=3, client=f.editor)
            self.assertEqual(self.files(f), before)
            self.assertEqual(f.editor.calls, 0)
            (f.root/path).write_bytes(original)
        # A selected original review cannot masquerade as the consolidated round.
        with self.assertRaises((ValueError,KeyError)): f.run.request(round_number=1, client=f.editor)
        self.assertEqual(f.editor.calls, 0)

    def test_deferable_feedback_has_noop_merge_and_global_debt_blocks_acceptance(self):
        f, client = self.vertical(budget=1)
        def defer(value):
            value['feedback']['feedback'][0]['in_scope'] = False
            value['classifications'][0]['classification'] = 'deferable'
            return canonical_json_bytes(value)
        client.callback = defer
        self.cycle(f, client)
        self.assertEqual(f.run.review_status().status, 'merge_required')
        self.assertEqual(f.run.review_next().status, 'merge_complete')
        self.assertEqual(f.run.review_status().status, 'review_complete')
        result = f.run.finish_phase1()
        self.assertFalse(result.accepted)
        self.assertEqual(result.report['terminal_state'], 'TARGET_NOT_REACHED')
        self.assertEqual(len(result.global_blocking_findings), 2)
        self.assertEqual(result.evidence['round_number'], 3)
        self.assertEqual(result.technical_failure['round_number'], 3)
        self.assertEqual(len(result.technical_failure['unresolved_major_issues']), 2)
        self.assertEqual(f.store.read('rounds/round-3/draft_before.md'), f.store.read('rounds/round-3/draft_after.md'))
        self.assertEqual(f.editor.calls, 0)

    def test_unequal_budgets_do_not_reuse_clean_evidence_after_promotion(self):
        f, client = self.start(mode='vertical', vertical_contract=True, status_contract=True,
            phase2_eligibility_contract=True, profiles=[{'name':'structural_integrity','budget':1},
                                                       {'name':'determinism','budget':2}])
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        client.callback = None
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        f.run.admit_reviewed_round()
        self.promote(f)
        view = f.run.phase1_status()
        self.assertEqual(view.selected_profile, 'determinism')
        self.assertTrue(view.profiles[0].exhausted)
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        result = f.run.finish_phase1()
        self.assertFalse(result.accepted)
        self.assertEqual(result.missing_review_profiles, ('structural_integrity',))
        self.assertEqual(result.technical_failure['profile_status']['unverified_profiles'], ['structural_integrity'])
        self.assertEqual(client.calls, 3)

    def test_shape_retry_stays_on_one_profile_and_authority_drift_prevents_next_client(self):
        f, client = self.vertical()
        client.callback = lambda value: b'{'
        self.assertEqual(f.run.review_next(client=client).status, 'attempts_exhausted')
        self.assertEqual(client.calls, 2)
        self.assertEqual([p.rounds_used for p in f.run.phase1_status().profiles], [0,0])
        self.reopen(f)
        self.assertEqual(f.run.review_next(continuation=True).status, 'attempts_exhausted')
        self.assertEqual(client.calls, 2)
        g, other = self.vertical()
        self.assertEqual(g.run.review_next(client=other).status, 'complete')
        path = g.admission._refs['review']['path']
        original = g.store.read(path)
        value = json.loads(original); value['profiles'][1]['budget'] += 1
        (g.root/path).write_bytes(canonical_json_bytes(value))
        before = self.files(g)
        with self.assertRaises(ValueError): g.run.review_next(client=other)
        self.assertEqual(self.files(g), before)
        self.assertEqual(other.calls, 1)

    def test_two_promotions_replay_distinct_consolidated_rounds_and_same_bytes_invalidate(self):
        f, client = self.vertical(budget=3)
        self.cycle(f, client); f.run.admit_reviewed_round(); self.promote(f)
        self.cycle(f, client)
        self.assertEqual(f.run.admit_reviewed_round()['path'], 'rounds/round-6/proposal_input.json')
        self.promote(f, number=6, ordinal=2)
        self.reopen(f)
        view = f.run.phase1_status()
        self.assertEqual(view.review_round, 7)
        self.assertFalse(view.all_profiles_clean)
        self.assertEqual([p.rounds_used for p in view.profiles], [2,2])
        client.callback = clean_response
        self.cycle(f, client)
        result = f.run.finish_phase1()
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.evidence['vertical_merges']), 2)
        self.assertEqual((client.calls,f.editor.calls), (6,2))
        self.assertEqual(f.store.read('rounds/round-3/draft_after.md'), f.store.read('rounds/round-6/draft_after.md'))

    def test_source_barrier_closeout_commit_and_final_ownership_loss_recover_without_clients(self):
        from whetstone.vnext_local_storage import OwnershipLost
        f, client = self.vertical()
        client.callback = clean_response
        self.cycle(f, client)
        closeout = f.run.phase1_closeout()
        receipt = closeout.evidence['review_receipts'][0]['receipt']['path']
        publish = f.store.publish
        def stop_source(token, path, value):
            if path == receipt: raise OSError('vertical source barrier')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=stop_source):
            with self.assertRaisesRegex(OSError, 'source barrier'): f.run.finish_phase1()
        self.assertFalse((f.root/closeout.evidence_ref['path']).exists())
        def lose_commit(token, path, value):
            result = publish(token, path, value)
            if path == closeout.evidence_ref['path']: raise OSError('vertical closeout acknowledgement')
            return result
        with patch.object(f.store, 'publish', side_effect=lose_commit):
            with self.assertRaisesRegex(OSError, 'closeout acknowledgement'): f.run.finish_phase1()
        self.reopen(f)
        self.assertTrue(f.run.finish_phase1().materialized)
        materialize = f.store.materialize
        def lose_owner(token, path, raw, **options):
            result = materialize(token, path, raw, **options)
            if path == 'rounds/run_state.json': f.store._invalidate()
            return result
        with patch.object(f.store, 'materialize', side_effect=lose_owner):
            with self.assertRaises(OwnershipLost): f.run.reconcile_phase1_state()
        self.reopen(f)
        self.assertTrue(f.run.reconcile_phase1_state().value.state_current)
        self.assertEqual((client.calls, f.editor.calls), (2,0))


class VerticalMergeTests(unittest.TestCase):
    def test_stable_slug_collisions_preserve_original_identity_and_input(self):
        packets = []
        for n, name in enumerate(['A B','a-b','a_b'], 1):
            packets.append(dict(feedback=dict(profile=name,round_number=n,draft_hash='a'*64,
                feedback=[dict(feedback_id='F1',issue_id='original',issue_fingerprint='b'*64)]),
                advice=dict(findings=[dict(feedback_id='F1',classification='editor_fixable')])))
        before = deepcopy(packets)
        feedback, advice, provenance = merge_packets(packets, 4)
        self.assertEqual([r['feedback_id'] for r in feedback['feedback']], ['a-b:F1','a-b:F1:2','a-b:F1:3'])
        self.assertEqual([r['feedback_id'] for r in advice['findings']], ['a-b:F1','a-b:F1:2','a-b:F1:3'])
        self.assertEqual([r['source_profile'] for r in provenance], ['A B','a-b','a_b'])
        self.assertTrue(all(r['issue_id'] == 'original' and r['issue_fingerprint'] == 'b'*64 for r in feedback['feedback']))
        self.assertEqual(packets, before)

    def test_unique_ids_are_preserved_and_literal_suffix_collisions_are_disambiguated(self):
        def packet(profile, ids):
            return dict(feedback=dict(profile=profile,round_number=1,draft_hash='a'*64,
                feedback=[dict(feedback_id=i) for i in ids]),advice=dict(findings=[dict(feedback_id=i) for i in ids]))
        a, b = packet('A',['x']), packet('B',['y'])
        self.assertEqual([r['feedback_id'] for r in merge_packets([a,b],3)[0]['feedback']], ['x','y'])
        a,b = packet('A',['x','x:2']), packet('a',['x'])
        ids = [r['feedback_id'] for r in merge_packets([a,b],3)[0]['feedback']]
        self.assertEqual(ids, ['a:x','a:x:2','a:x:3'])


if __name__ == '__main__': unittest.main()
