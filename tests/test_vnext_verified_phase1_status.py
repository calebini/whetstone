"""Read-only scheduler progress through genuine canonical V journals."""
from dataclasses import asdict
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime


def clean_response(packet):
    packet['feedback']['feedback'] = []
    packet['classifications'] = []
    return canonical_json_bytes(packet)


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedPhase1StatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    files = runtime.VerifiedReviewTests.files
    reopen = runtime.VerifiedReviewTests.reopen

    def status(self, f):
        before = self.files(f)
        result = f.run.phase1_status()
        self.assertEqual(self.files(f), before)
        return result

    def test_clean_profiles_are_bound_detached_readonly_observations_not_phase_readiness(self):
        f, client = self.start(status_contract=True, profiles=[
            {'name':'structural_integrity','budget':1}, {'name':'determinism','budget':1}])
        view = self.status(f)
        self.assertEqual((view.review_gate, view.review_round, view.selected_profile),
                         ('review', 1, 'structural_integrity'))
        self.assertFalse(view.all_profiles_clean)
        self.assertEqual([p.rounds_used for p in view.profiles], [0, 0])
        client.callback = clean_response
        for _ in range(2): self.assertEqual(f.run.review_next(client=client).status, 'complete')
        self.reopen(f)
        # A status reader does not acquire the authority writer lock or repair.
        with f.store.locked(f.run._history().validate_authority): view = self.status(f)
        self.assertEqual((view.review_gate, view.review_round, view.selected_profile), ('review_complete', None, None))
        self.assertTrue(view.all_profiles_clean)
        self.assertEqual([p.rounds_used for p in view.profiles], [1, 1])
        self.assertFalse(any(p.exhausted for p in view.profiles))
        for profile in view.profiles:
            self.assertEqual(profile.clean_base_pointer['hash'], sha256_bytes(canonical_json_bytes(view.current_pointer)))
            self.assertEqual(profile.clean_review_receipt['hash'], sha256_bytes(f.store.read(profile.clean_review_receipt['path'])))
        self.assertNotIn('terminal_state', asdict(view))
        self.assertNotIn('ready_for_phase_2', asdict(view))
        view.profiles[0].clean_base_pointer['hash'] = 'a' * 64
        view.current_pointer['verified_draft_hash'] = 'b' * 64
        self.assertNotEqual(self.status(f), view)
        self.assertEqual(client.calls, 2)

    def test_incomplete_review_does_not_spend_logical_budget_or_publish_clean_evidence(self):
        f, client = self.start(status_contract=True, budget=1)
        def timeout(packet): raise TimeoutError('fictional Reviewer timeout')
        client.callback = timeout
        self.assertEqual(f.run.review_next(client=client).status, 'timeout')
        pending = self.status(f)
        self.assertEqual((pending.review_gate, pending.review_round, pending.pending_review_attempts), ('pending', 1, 1))
        self.assertEqual(pending.profiles[0].rounds_used, 0)
        self.assertFalse(pending.profiles[0].clean)
        self.assertIsNone(pending.profiles[0].clean_review_receipt)
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client, continuation=True).status, 'complete')
        complete = self.status(f)
        self.assertEqual(complete.profiles[0].rounds_used, 1)
        self.assertTrue(complete.all_profiles_clean)
        self.assertEqual(client.calls, 2)

    def test_promotion_invalidates_clean_evidence_preserves_budgets_and_gates_mirror_repair(self):
        f, client = self.start(status_contract=True, profiles=[
            {'name':'structural_integrity','budget':2}, {'name':'determinism','budget':1}])
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        client.callback = None
        self.review(f, client)
        self.assertEqual(f.run.request(round_number=2, client=f.editor).value.status, 'complete')
        creation = f.run.register(round_number=2, created_at=STAMP).value
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=creation['candidate_id'])
        verifier = runtime.history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        before = self.status(f)
        self.assertEqual(before.work_outcome, 'promotion_required')
        self.assertEqual(before.current_pointer['promotion_ordinal'], 0)
        self.assertEqual(before.latest_candidate, creation)
        self.assertEqual(before.promotion_candidate, creation)
        self.assertTrue(before.profiles[0].clean)
        self.assertFalse(before.all_profiles_clean)
        f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        after = self.status(f)
        self.assertEqual(after.current_pointer['promotion_ordinal'], 1)
        self.assertEqual([p.rounds_used for p in after.profiles], [1, 1])
        self.assertFalse(any(p.clean for p in after.profiles))
        self.assertTrue(after.profiles[1].exhausted)
        self.assertEqual(after.selected_profile, 'structural_integrity')
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        exhausted = self.status(f)
        self.assertEqual(exhausted.review_gate, 'budget_exhausted')
        self.assertIsNone(exhausted.review_round)
        self.assertEqual([p.rounds_used for p in exhausted.profiles], [2, 1])
        # A damaged future claim must not mask committed mirror recovery.
        (f.root / 'spec.md').unlink()
        (f.root / 'rounds/review_index/request-4.json').write_bytes(b'not json')
        pending = self.status(f)
        self.assertEqual(pending.work_outcome, 'materialization_required')
        self.assertIn('spec.md', pending.pending_paths)
        self.assertIsNone(pending.profiles)
        self.assertIsNone(pending.orphan_directories)
        self.assertIsNone(pending.all_profiles_clean)
        (f.root / 'spec.md').write_bytes(f.store.read(pending.current_pointer['verified_draft_path']))
        with self.assertRaises(ValueError): self.status(f)
        self.assertEqual((client.calls, f.editor.calls, verifier.calls), (3, 1, 1))

    def test_new_status_pin_and_original_review_evidence_are_required(self):
        f, client = self.start()
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'status algorithm'): f.run.phase1_status()
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 0)
        g, reviewer = self.start(status_contract=True)
        reviewer.callback = clean_response
        self.assertEqual(g.run.review_next(client=reviewer).status, 'complete')
        header = json.loads(g.store.read('rounds/review_index/request-1.json'))
        (g.root / f"rounds/client_requests/{header['request_id']}/attempts/1/response.json").write_bytes(b'{}')
        before = self.files(g)
        with self.assertRaises(ValueError): g.run.phase1_status()
        self.assertEqual(self.files(g), before)
        self.assertEqual(reviewer.calls, 1)

    def test_orphan_registration_is_reported_without_recovery_or_extra_review(self):
        f, client = self.start(status_contract=True)
        self.review(f, client)
        self.assertEqual(f.run.request(round_number=1, client=f.editor).value.status, 'complete')
        publish = f.store.publish
        def stop(token, path, value):
            if path == 'rounds/candidate_index/creation-1.json': raise OSError('before registration commit')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'before registration commit'):
                f.run.register(round_number=1, created_at=STAMP)
        self.reopen(f)
        view = self.status(f)
        self.assertEqual(view.work_outcome, 'registration_recovery_required')
        self.assertEqual(len(view.orphan_directories), 1)
        self.assertIsNone(view.latest_candidate)
        self.assertEqual(view.review_gate, 'finding_admission')
        self.assertEqual(view.profiles[0].rounds_used, 1)
        self.assertEqual((client.calls, f.editor.calls), (1, 1))
