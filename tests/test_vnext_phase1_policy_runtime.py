"""Shared Phase 1 policy through real journals with scripted clients."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vocabulary import PROFILE_SETS
import test_vnext_verified_review as runtime
import test_vnext_verified_vertical_phase1 as vertical
from test_vnext_verified_phase1_status import clean_response
from test_vnext_phase1_policy import scope_packet


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class PolicyRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    promote = runtime.VerifiedReviewTests.promote
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def begin(self, *, mode='horizontal', profile_set='utility_mvp', workflow='mvp', budget=1, focused=None, full=False):
        names = PROFILE_SETS[profile_set].phase_1_profiles
        profiles = [dict(name=name,budget=budget) for name in (names if full else names[:1])]
        return self.start(shared_policy=True, workflow=workflow, profile_set=profile_set,
            scope=scope_packet(), profiles=profiles, mode=mode, vertical_contract=mode=='vertical',
            focused_profile=focused, focused_contract=focused is not None, phase2_eligibility_contract=True, status_contract=True)

    @staticmethod
    def deferred(packet):
        packet['feedback']['feedback'][0]['in_scope'] = False
        packet['classifications'][0].update(classification='deferable', scope_surface_ids=['future-hardening'])
        return canonical_json_bytes(packet)

    def finish_reviews(self, f, client):
        for _ in range(30):
            state = f.run.review_status()
            if state.status in {'review_complete','budget_exhausted'}: return
            self.assertIn(state.status, {'not_started','merge_required'})
            f.run.review_next(client=client)
        self.fail('review did not reach a bounded terminal')

    def test_approved_deferrals_complete_both_routes_with_visible_evidence_and_replay(self):
        for mode, profile_set, workflow in [('horizontal','balanced_mvp','standard'),('vertical','utility_mvp','mvp')]:
            with self.subTest(mode=mode):
                f, client = self.begin(mode=mode,profile_set=profile_set,workflow=workflow,full=True)
                client.callback = self.deferred
                self.finish_reviews(f,client)
                self.assertTrue(f.run.phase1_status().all_profiles_clean)
                result=f.run.finish_phase1()
                self.assertTrue(result.accepted)
                self.assertEqual(result.report['terminal_state'],'PHASE_1_STABLE')
                self.assertEqual(result.evidence['schema_version'],'vnext-verified-phase1-closeout-v5')
                self.assertEqual(len(result.evidence['deferred_findings']),len(PROFILE_SETS[profile_set].phase_1_profiles))
                self.assertFalse(result.global_blocking_findings)
                count=client.calls; self.reopen(f)
                self.assertEqual(f.run.finish_phase1().evidence,result.evidence)
                self.assertEqual(client.calls,count)
                f.run.reconcile_phase1_state()
                self.assertFalse(json.loads(f.store.read('rounds/run_state.json'))['ready_for_phase_2'])
                self.assertEqual(f.editor.calls,0)
                self.assertIn('shared_phase1_policy_phase2_unsupported', f.run.phase2_eligibility().phase1_blockers)

    def test_unapproved_out_of_focus_major_requires_decision_not_completion(self):
        f,client=self.begin()
        def outside(packet):
            packet['feedback']['feedback'][0]['in_scope']=False
            packet['classifications'][0]['classification']='deferable'
            return canonical_json_bytes(packet)
        client.callback=outside
        result=f.run.review_next(client=client)
        self.assertEqual(result.review['findings'][0]['classification'],'operator_decision_required')
        self.assertFalse(f.run.phase1_status().all_profiles_clean)
        self.assertEqual(f.run.review_status().status,'finding_admission')
        self.assertFalse(f.run.phase1_closeout().accepted)
        with self.assertRaisesRegex(ValueError,'no eligible review terminal'):f.run.finish_phase1()

    def test_focused_deferrals_establish_only_focused_stability(self):
        f,client=self.begin(focused='buildability')
        client.callback=self.deferred;self.finish_reviews(f,client)
        result=f.run.finish_phase1()
        self.assertFalse(result.accepted)
        self.assertEqual(result.report['terminal_state'],'FOCUSED_PROFILE_STABLE')
        self.assertEqual(result.evidence['focused_profile'],'buildability')

    def test_mvp_edit_promote_requires_current_draft_review(self):
        f,client=self.begin(budget=2)
        self.review(f,client)
        self.promote(f)
        self.assertFalse(f.run.phase1_closeout().accepted)
        self.assertFalse(f.run.phase1_status().all_profiles_clean)
        client.callback=clean_response;self.finish_reviews(f,client)
        result=f.run.finish_phase1()
        self.assertTrue(result.accepted)
        self.assertEqual(result.evidence['deferred_findings'],[])
        self.reopen(f)
        self.assertTrue(f.run.finish_phase1().accepted)

    def test_interrupted_closeout_replays_without_more_model_calls(self):
        f,client=self.begin();client.callback=self.deferred;self.finish_reviews(f,client)
        expected=f.run.phase1_closeout();publish=f.store.publish
        def fail(token,path,value):
            publish(token,path,value)
            if path==expected.evidence_ref['path']:raise OSError('lost closeout acknowledgement')
        with patch.object(f.store,'publish',side_effect=fail):
            with self.assertRaisesRegex(OSError,'lost closeout'):f.run.finish_phase1()
        self.reopen(f)
        self.assertEqual(f.run.finish_phase1().evidence,expected.evidence)
        self.assertEqual(client.calls,1)

    def test_exhaustion_extension_replays_v5_closeout_without_implicit_success(self):
        f,client=self.begin(budget=1)
        self.review(f,client);self.promote(f)
        result=f.run.finish_phase1()
        self.assertFalse(result.accepted)
        self.assertEqual(result.report['terminal_state'],'TARGET_NOT_REACHED')
        f.run.reconcile_phase1_state()
        f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.reopen(f)
        client.callback=clean_response;self.finish_reviews(f,client)
        final=f.run.finish_phase1()
        self.assertTrue(final.accepted)
        self.assertEqual(len(final.evidence['budget_extensions']),1)
        self.reopen(f)
        self.assertEqual(f.run.finish_phase1().evidence,final.evidence)

    def test_vertical_mvp_promotion_requires_all_lighter_profiles_again(self):
        f,client=self.begin(mode='vertical',full=True,budget=2)
        for _ in range(4):self.assertEqual(f.run.review_next(client=client).status,'complete')
        self.assertEqual(f.run.review_status().status,'finding_admission')
        f.run.admit_reviewed_round()
        vertical.VerticalPhase1Tests.promote(self,f,number=5)
        self.assertFalse(f.run.phase1_status().all_profiles_clean)
        client.callback=clean_response;self.finish_reviews(f,client)
        self.assertEqual(client.calls,8)
        result=f.run.finish_phase1()
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.evidence['vertical_merges']),1)

    def test_optional_minor_reviews_complete_without_forced_edits_on_both_routes(self):
        for mode in ('horizontal','vertical'):
            with self.subTest(mode=mode):
                f,client=self.begin(mode=mode)
                def optional(packet):
                    packet['feedback']['feedback'][0]['baseline_severity']='minor'
                    return canonical_json_bytes(packet)
                client.callback=optional
                self.finish_reviews(f,client)
                result=f.run.finish_phase1()
                self.assertTrue(result.accepted)
                self.assertEqual(result.evidence['deferred_findings'],[])
                self.assertEqual(f.editor.calls,0)
                self.assertEqual(client.calls,1)
                self.assertTrue((f.root/'rounds/round-1/editor_summary.json').is_file())
                self.reopen(f)
                self.assertEqual(f.run.finish_phase1().evidence,result.evidence)
