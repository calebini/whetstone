"""Bounded acceptance and terminal publication through genuine V journals."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_work import VerifiedWorkView
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedPhase1CloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    promote = runtime.VerifiedReviewTests.promote
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def inspect(self, f):
        before = self.files(f)
        view = f.run.phase1_closeout()
        self.assertEqual(self.files(f), before)
        return view

    def clean(self, **options):
        f, client = self.start(closeout_contract=True, **options)
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        return f, client

    def test_seed_acceptance_requires_every_profile_and_publishes_bound_terminal_without_phase2(self):
        f, client = self.start(closeout_contract=True, profiles=[
            {'name':'structural_integrity','budget':1}, {'name':'determinism','budget':1}])
        incomplete = self.inspect(f)
        self.assertFalse(incomplete.accepted)
        self.assertEqual(len(incomplete.missing_review_profiles), 2)
        self.assertIsNone(incomplete.report)
        with self.assertRaisesRegex(ValueError, 'no eligible review terminal'): f.run.finish_phase1()
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        self.assertFalse(self.inspect(f).accepted)
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        expected = self.inspect(f)
        self.assertTrue(expected.accepted)
        self.assertEqual(expected.report['terminal_state'], 'PHASE_1_STABLE')
        self.assertFalse(expected.materialized)
        authority = f.store.read('rounds/current_verified.json')
        state = f.store.read('rounds/run_state.json')
        final = f.run.finish_phase1()
        self.assertTrue(final.materialized)
        self.assertEqual(final.evidence['terminal_report'], final.report_ref)
        self.assertEqual(final.evidence['current_verified_pointer']['hash'], sha256_bytes(authority))
        self.assertEqual([r['round_number'] for r in final.evidence['review_receipts']], [1, 2])
        self.assertTrue(all(v is None for v in final.report['latest_candidate'].values()))
        self.assertFalse(final.report['apply_back_permitted'])
        self.assertFalse(final.report['resume']['permitted'])
        before = self.files(f)
        self.reopen(f)
        self.assertEqual(f.run.finish_phase1(), final)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.store.read('rounds/current_verified.json'), authority)
        self.assertEqual(f.store.read('rounds/run_state.json'), state)
        self.assertEqual(client.calls, 2)

    def test_profile_cleanliness_cannot_erase_global_nonfocus_major_debt(self):
        f, client = self.start(closeout_contract=True, status_contract=True)
        def outside(packet):
            packet['feedback']['feedback'][0]['in_scope'] = False
            packet['classifications'][0]['classification'] = 'deferable'
            return canonical_json_bytes(packet)
        client.callback = outside
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        self.assertTrue(f.run.phase1_status().all_profiles_clean)
        view = self.inspect(f)
        self.assertFalse(view.accepted)
        self.assertEqual(len(view.global_blocking_findings), 1)
        self.assertEqual(view.report['terminal_state'], 'TARGET_NOT_REACHED')
        self.assertEqual(view.report['resume']['reason'], 'vnext_global_acceptance_not_established')
        self.assertTrue(f.run.finish_phase1().materialized)
        self.assertEqual(client.calls, 1)

    def test_promotion_requires_new_review_and_budget_failure_uses_committed_promotion_event(self):
        for budget in (1, 2):
            with self.subTest(budget=budget):
                f, client = self.start(closeout_contract=True, budget=budget)
                self.review(f, client)
                self.assertIsNone(self.inspect(f).report)
                verifier = self.promote(f)
                view = self.inspect(f)
                self.assertFalse(view.accepted)
                self.assertEqual(view.missing_review_profiles, ('structural_integrity',))
                if budget == 2:
                    self.assertIsNone(view.report)
                    client.callback = clean_response
                    self.assertEqual(f.run.review_next(client=client).status, 'complete')
                final = f.run.finish_phase1()
                self.assertEqual(final.report['terminal_state'], 'TARGET_NOT_REACHED' if budget == 1 else 'PHASE_1_STABLE')
                self.assertEqual(final.report['latest_candidate']['disposition'], 'CANDIDATE_PROMOTED')
                pointer = json.loads(f.store.read('rounds/current_verified.json'))
                self.assertEqual(final.report['latest_candidate']['disposition_event_hash'], pointer['promotion_disposition_event_hash'])
                self.assertEqual(final.evidence['current_verified_pointer']['hash'], sha256_bytes(canonical_json_bytes(pointer)))
                self.assertEqual((client.calls, f.editor.calls, verifier.calls), (budget, 1, 1))

    def test_publication_prefixes_and_lost_final_ack_replay_without_clients(self):
        for boundary in ('report', 'evidence', 'after_evidence'):
            with self.subTest(boundary=boundary):
                f, client = self.clean()
                expected = self.inspect(f)
                path = expected.report_ref['path'] if boundary == 'report' else expected.evidence_ref['path']
                publish = f.store.publish
                def stop(token, target, value):
                    if target != path: return publish(token, target, value)
                    if boundary == 'after_evidence': publish(token, target, value)
                    raise OSError('closeout interruption')
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'closeout interruption'): f.run.finish_phase1()
                self.reopen(f)
                visible = self.inspect(f)
                self.assertEqual(visible.materialized, boundary == 'after_evidence')
                # Even visible final evidence must replay its publication barrier.
                if boundary == 'after_evidence':
                    publish = f.store.publish
                    with patch.object(f.store, 'publish', side_effect=stop):
                        with self.assertRaisesRegex(OSError, 'closeout interruption'): f.run.finish_phase1()
                final = f.run.finish_phase1()
                self.assertTrue(final.materialized)
                self.assertEqual(final.evidence, expected.evidence)
                self.assertEqual(client.calls, 1)

    def test_source_barrier_failure_and_corrupt_committed_evidence_do_not_fabricate_success(self):
        f, client = self.clean()
        expected = self.inspect(f)
        receipt_path = expected.evidence['review_receipts'][0]['receipt']['path']
        publish = f.store.publish
        def stop(token, path, value):
            if path == receipt_path: raise OSError('source barrier')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'source barrier'): f.run.finish_phase1()
        self.assertFalse((f.root / expected.report_ref['path']).exists())
        final = f.run.finish_phase1()
        report_bytes = f.store.read(final.report_ref['path'])
        (f.root / final.report_ref['path']).unlink()
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'missing its report'): f.run.finish_phase1()
        self.assertEqual(self.files(f), before)
        (f.root / final.report_ref['path']).write_bytes(report_bytes)
        (f.root / final.evidence_ref['path']).write_bytes(b'{}')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'evidence conflicts'): f.run.finish_phase1()
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 1)

    def test_materialization_recovery_ends_before_closeout_and_missing_pin_refuses(self):
        f, client = self.clean()
        expected = self.inspect(f)
        (f.root / 'spec.md').unlink()
        blocked = self.inspect(f)
        self.assertIsInstance(blocked, VerifiedWorkView)
        self.assertEqual(blocked.outcome, 'materialization_required')
        self.assertEqual(f.run.finish_phase1().outcome, 'materialization_recovered')
        self.assertFalse((f.root / expected.report_ref['path']).exists())
        self.assertTrue(f.run.finish_phase1().materialized)
        self.assertEqual(client.calls, 1)
        g, other = self.start()
        before = self.files(g)
        with self.assertRaisesRegex(ValueError, 'closeout contracts'): g.run.finish_phase1()
        self.assertEqual(self.files(g), before)
        self.assertEqual(other.calls, 0)
