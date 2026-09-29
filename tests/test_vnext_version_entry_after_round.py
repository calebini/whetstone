"""Entry must consume a proven non-seed Phase 1 pointer too."""
import json
import sys
import unittest

import test_vnext_verified_versions as versions
import test_vnext_verified_phase2_binding as binding
from test_vnext_verified_phase1_status import clean_response
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform == 'darwin', 'D8 local storage requires macOS/APFS')
class VersionEntryAfterRoundTests(unittest.TestCase):
    setUpClass = versions.VerifiedVersionTests.setUpClass
    fixture = versions.VerifiedVersionTests.fixture
    start = versions.VerifiedVersionTests.start
    review = versions.VerifiedVersionTests.review
    promote = versions.VerifiedVersionTests.promote
    reopen = versions.VerifiedVersionTests.reopen
    files = versions.VerifiedVersionTests.files

    def test_entry_after_phase1_promotion_uses_original_proven_prefix(self):
        f, reviewer = self.start(phase2_entry_contract=True)
        self.review(f, reviewer)
        first_verifier = self.promote(f)
        self.assertIn(b'# Queue 0.18', f.store.read('spec.md'))
        reviewer.callback = clean_response
        self.assertEqual(f.run.review_next(client=reviewer).status, 'complete')
        f.run.finish_phase1(); f.run.reconcile_phase1_state()
        before = json.loads(f.store.read('rounds/current_verified.json'))
        f.run.bind_phase2_entry(binding.VerifiedPhase2BindingTests.config(self, f))
        creation = f.run.prepare_phase2_version(created_at=STAMP)
        context = load_registered_semantic_context(f.store, admission=f.run._history(),
                                                   candidate_id=creation['candidate_id'])
        verifier = versions.runtime.history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        promoted = f.run.promote(prepared_at=STAMP).current_pointer
        self.assertEqual(promoted['promotion_ordinal'], 2)
        self.assertEqual(before['promotion_ordinal'], 1)
        self.reopen(f)
        entry = f.run.enter_phase2()
        self.assertTrue(entry.committed and entry.state_current)
        self.assertEqual(entry.entry['version'], dict(before='0.18', after='1.0', changed=True))
        history = f.store.read('spec.history.md')
        self.assertEqual(history.count(b'`0.17` -> `0.18`'), 1)
        self.assertEqual(history.count(b'`0.18` -> `1.0`'), 1)
        self.assertEqual((reviewer.calls, f.editor.calls, first_verifier.calls, verifier.calls), (2, 1, 1, 1))


if __name__ == '__main__': unittest.main()
