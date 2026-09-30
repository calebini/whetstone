"""Historical journal construction keeps fresh rechecks and authority barriers."""
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_versions as versions
from whetstone.vnext_verified_history import _VerifiedTransactions
from whetstone.vnext_version_entry import SystemJournal


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class HistoryJournalTests(unittest.TestCase):
    setUpClass = versions.VersionPhase2Tests.setUpClass
    fixture = versions.VersionPhase2Tests.fixture
    start = versions.VersionPhase2Tests.start
    config = versions.VersionPhase2Tests.config
    ready = versions.VersionPhase2Tests.ready

    def test_construction_handoff_keeps_fresh_sources_and_authority(self):
        f, client, _ = self.ready()
        proof = f.run._history()._prove(f.store.read)
        creation = proof.view.creations[0]
        router = proof.router
        load = router.load_inputs.for_proposal
        def journal(store=proof.store):
            return router._request_journal(store, creation['round_number'], creation['proposal_id'])
        def files():
            return {str(p.relative_to(f.root)): p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        before = files()
        with patch.object(router.load_inputs, 'for_proposal', wraps=load) as reads:
            first = journal()
            self.assertIsInstance(first, SystemJournal)
            self.assertEqual(reads.call_count, 1)
            first.inspect()
            self.assertEqual(reads.call_count, 2)
            first.recheck()
            self.assertEqual(reads.call_count, 3)
        # The handed-off result must not alias another journal or memo entry.
        expected = first.preflight
        first.arguments['system_entry']['closeout']['review_receipts'].clear()
        current = journal()
        self.assertEqual(current.preflight, expected)
        current.inspect()
        values = current.arguments; entry = values['system_entry']
        paths = [entry['request_ref']['path'], entry['request']['configuration']['path'],
                 entry['configuration']['rubric']['artifact']['path'],
                 entry['request']['phase1_closeout']['path'], entry['review_receipt']['path'],
                 values['feedback_ref']['path'], f.run._record['review_configuration']['path'],
                 f.run._record['descriptor']['path'], 'rounds/current_verified.json']
        for path in paths:
            with self.subTest(path=path):
                target = f.root/path; raw = target.read_bytes()
                try:
                    target.write_bytes(raw+b' ')
                    with self.assertRaises(ValueError): current.recheck()
                    with self.assertRaises(ValueError): journal()
                finally:
                    target.write_bytes(raw)
        # A head change after selection cannot be hidden by the handoff.
        head = f.root/'rounds/current_verified.json'; raw = head.read_bytes()
        def changed_selection(*args):
            result = load(*args)
            head.write_bytes(raw+b' ')
            return result
        try:
            with patch.object(router.load_inputs, 'for_proposal', side_effect=changed_selection):
                with self.assertRaisesRegex(ValueError, 'authority changed'): journal()
        finally:
            head.write_bytes(raw)
        # Nor may construction return after losing that authority.
        construct = SystemJournal.__init__
        def changed_construction(owner, *args):
            construct(owner, *args)
            head.write_bytes(raw+b' ')
        try:
            with patch.object(SystemJournal, '__init__', changed_construction):
                with self.assertRaisesRegex(ValueError, 'authority changed'): journal()
        finally:
            head.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'another storage owner'):
            journal(object())
        self.assertEqual(files(), before)
        self.assertEqual((client.calls, f.editor.calls), (0, 0))
        f.store.close()
        with self.assertRaises((ValueError, RuntimeError, OSError)): current.recheck()
        with self.assertRaises((ValueError, RuntimeError, OSError)): journal()


if __name__ == '__main__': unittest.main()
