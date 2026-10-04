"""Historical seed validation reuse keeps fresh bytes and live authority guards."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_review as runtime
import test_vnext_verified_semantics as semantics
from vnext_q2_fixtures import suite
from whetstone.vnext_contracts import CONTRACT_ROOT
from whetstone.vnext_proposal_run import RUN_INPUT_PATH, round_input_path
from whetstone.vnext_verified_review_requests import _ReviewInputs
from whetstone.vnext_verified_run import VerifiedRun
from whetstone.vnext_verified_work import _BorrowedFence


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class ReviewSeedReplayTests(unittest.TestCase):
    setUpClass = runtime.VerifiedReviewTests.setUpClass
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    files = runtime.VerifiedReviewTests.files

    def setUp(self):
        selected = patch.object(semantics, 'consuming_suite', suite)
        selected.start(); self.addCleanup(selected.stop)

    def inputs(self):
        f, client = self.start(status_contract=True)
        proof = f.run._history()._prove(f.store.read)
        return f, client, proof, _ReviewInputs(proof.store, proof, proof.latest)

    def test_reuse_returns_isolated_values_and_new_invocation_validates_fresh(self):
        f, client, proof, inputs = self.inputs()
        before = self.files(f)
        with patch.object(proof.owner, '_seed_inputs', wraps=proof.owner._seed_inputs) as rebuild:
            _, first, pointer = inputs.values()
            expected = deepcopy(first['base_map'])
            first['base_map']['sections'].clear(); first['review']['profiles'].clear()
            _, second, current = inputs.values()
            self.assertEqual(second['base_map'], expected)
            self.assertTrue(second['review']['profiles'])
            self.assertEqual(current, pointer)
            self.assertEqual(rebuild.call_count, 1)
            another = proof.owner._prove(f.store.read)
            self.assertIsNot(another.memo, proof.memo)
            self.assertEqual(rebuild.call_count, 2)
        self.assertEqual(self.files(f), before)
        self.assertEqual((client.calls, f.editor.calls), (0, 0))

    def test_warm_seed_rejects_changed_missing_and_symlinked_sources_and_contracts(self):
        f, client, proof, inputs = self.inputs()
        job = proof.seed_values['job']; refs = proof.owner._refs
        paths = [job['seed_draft']['path'], refs['seed_map']['path'], refs['descriptor']['path'],
                 refs['review']['path'], job['authority_map_path'], job['protected_invariants_path'],
                 'rounds/verified_history/current-verified-0.json', RUN_INPUT_PATH,
                 'rounds/current_verified.json']
        before = self.files(f)
        for name in paths:
            with self.subTest(path=name):
                inputs.values()
                path = f.root / name; raw = path.read_bytes()
                try:
                    path.write_bytes(raw + b' ')
                    with self.assertRaises(ValueError): inputs.values()
                finally:
                    path.write_bytes(raw)
        seed = f.root / job['seed_draft']['path']; raw = seed.read_bytes()
        for kind in ('missing', 'symlink'):
            with self.subTest(kind=kind):
                inputs.values(); seed.unlink()
                alternate = f.root / 'inputs/seed-copy.md'
                try:
                    if kind == 'symlink':
                        alternate.write_bytes(raw); seed.symlink_to(alternate)
                    with self.assertRaises((OSError, ValueError)): inputs.values()
                finally:
                    if seed.is_symlink(): seed.unlink()
                    seed.write_bytes(raw)
                    if alternate.exists(): alternate.unlink()
        manifest = proof.reader.suite.manifest
        targets = [CONTRACT_ROOT / 'suites/vnext-verified-consumer-1.json']
        targets += [CONTRACT_ROOT / manifest[group][0]['path'] for group in ('schemas', 'algorithms', 'fixtures')]
        original = Path.read_bytes
        for target in targets:
            with self.subTest(contract=str(target)):
                inputs.values()
                def changed(path):
                    return b'corrupt contract' if path == target else original(path)
                with patch.object(Path, 'read_bytes', changed):
                    with self.assertRaises(ValueError): inputs.values()
        # Manifest whitespace is valid under the existing contract. Changed
        # bytes must trigger fresh validation, not introduce a new refusal rule.
        inputs.values()
        manifest_path = CONTRACT_ROOT / 'suites/vnext-verified-consumer-1.json'
        def whitespace(path):
            return original(path) + b' ' if path == manifest_path else original(path)
        with patch.object(Path, 'read_bytes', whitespace), \
             patch.object(proof.owner, '_seed_inputs', wraps=proof.owner._seed_inputs) as fresh:
            inputs.values(); inputs.values()
            self.assertEqual(fresh.call_count, 1)
        self.assertEqual(self.files(f), before)
        self.assertEqual((client.calls, f.editor.calls), (0, 0))

    def test_rounds_resolved_after_warming_still_have_live_guards(self):
        f, _, proof, inputs = self.inputs()
        inputs.values()
        path = f.root / round_input_path(99); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'{}')
        # Unselected later evidence does not invent a new validation dependency.
        inputs.values()
        proof.owner._refs['rounds'][99]
        inputs.values()
        path.write_bytes(b'{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'resolved V round input changed'):
            inputs.values()

    def test_changed_head_during_hit_and_expired_fence_refuse_live_reads_stay_fresh(self):
        f, _, proof, inputs = self.inputs()
        inputs.values()
        original = proof.memo._unchanged
        head = f.root / 'rounds/current_verified.json'; raw = head.read_bytes()
        def change_after_readback(observations):
            result = original(observations)
            head.write_bytes(raw + b' ')
            return result
        try:
            with patch.object(proof.memo, '_unchanged', side_effect=change_after_readback):
                with self.assertRaisesRegex(ValueError, 'authority changed'): inputs.values()
        finally:
            head.write_bytes(raw)
        with f.store.locked(f.run._history().validate_authority) as token:
            fence = _BorrowedFence(f.store, token)
            owner = VerifiedRun(fence, suite_path=f.run.suite_path)._history()
            bound = owner._prove(fence.read)
            historical = _ReviewInputs(bound.store, bound, bound.latest)
            historical.values(); historical.values()
            live = _ReviewInputs(fence, bound, bound.latest)
            with patch.object(owner, '_recheck_review_seed', side_effect=AssertionError('live path used memo')), \
                 patch.object(owner, '_seed_inputs', wraps=owner._seed_inputs) as fresh:
                live.values(); live.values()
                self.assertEqual(fresh.call_count, 2)
        with self.assertRaises(RuntimeError): historical.values()
        with self.assertRaises(RuntimeError): live.values()


if __name__ == '__main__':
    unittest.main()
