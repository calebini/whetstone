"""Genuine promoted history must recheck dependencies on transaction reuse."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_versions as versions
from whetstone.vnext_contracts import CONTRACT_ROOT
from whetstone.vnext_verified_history import _VerifiedTransactions
from whetstone.vnext_version_entry import preflight


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class HistoryReplayMemoTests(unittest.TestCase):
    setUpClass = versions.VersionPhase2Tests.setUpClass
    fixture = versions.VersionPhase2Tests.fixture
    start = versions.VersionPhase2Tests.start
    config = versions.VersionPhase2Tests.config
    ready = versions.VersionPhase2Tests.ready

    def test_promoted_transaction_reuse_rereads_sources_and_keeps_output_isolated(self):
        f, client, _ = self.ready()
        owner = f.run._history()
        from whetstone.vnext_verified_history import _Proof
        from whetstone.vnext_version_entry import prefix_at
        ascending = _Proof(owner, f.store.read)
        prefix = prefix_at(ascending, ascending.latest)
        self.assertEqual(ascending.latest, prefix.latest)
        self.assertNotEqual(ascending.memo_context(), prefix.memo_context())
        proof = owner._prove(f.store.read)
        creation = proof.view.creations[0]
        def load():
            return proof.router.load_inputs.for_proposal(proof.store.read, creation['round_number'], creation['proposal_id'])
        first = load(); expected = preflight(first).plan
        with patch.object(_VerifiedTransactions, '_replay_transaction', autospec=True,
                          side_effect=AssertionError('same transaction rebuilt')):
            first['system_entry']['closeout']['review_receipts'].clear()
            self.assertEqual(preflight(load()).plan, expected)
        values = load(); entry = values['system_entry']
        with self.assertRaises(ValueError):
            proof.router._transaction(proof.store.read, True, creation['transaction_id'])
        paths = [entry['request_ref']['path'], entry['request']['configuration']['path'],
                 entry['configuration']['rubric']['artifact']['path'],
                 entry['request']['phase1_closeout']['path'], entry['review_receipt']['path'],
                 values['feedback_ref']['path'], f.run._record['review_configuration']['path'],
                 f.run._record['descriptor']['path'], 'rounds/current_verified.json']
        for path in paths:
            with self.subTest(path=path):
                raw = (f.root/path).read_bytes()
                try:
                    (f.root/path).write_bytes(raw+b' ')
                    with self.assertRaises(ValueError): load()
                finally:
                    (f.root/path).write_bytes(raw)
                load()  # Warm it again before the next independent fault.
        path = f.root/'rounds/review_index/request-99.json'
        try:
            path.write_bytes(b'{}')
            with self.assertRaises(ValueError): load()
        finally:
            path.unlink()
        load()
        read = Path.read_bytes
        target = CONTRACT_ROOT/'algorithms/vnext_version_entry_v1.md'
        def changed(path):
            return b'changed installed contract' if path == target else read(path)
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaises(ValueError): load()
        load()
        before = len(proof.memo.entries)
        self.assertGreater(before, 0)
        self.assertEqual(client.calls, 0)
        f.store.close()
        with self.assertRaises((ValueError, RuntimeError, OSError)): load()


if __name__ == '__main__': unittest.main()
