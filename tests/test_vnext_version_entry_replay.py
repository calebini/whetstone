"""Fresh system-entry prerequisites without duplicate closeout reconstruction."""
import json
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_versions as versions
import test_vnext_verified_phase2_binding as binding_tests
from test_vnext_verified_phase1_status import clean_response
from whetstone import vnext_version_entry as entry
from whetstone.vnext_verified_phase1_closeout import _Closeout


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class EntryReplayTests(unittest.TestCase):
    setUpClass = versions.VerifiedVersionTests.setUpClass
    fixture = versions.VerifiedVersionTests.fixture
    start = versions.VerifiedVersionTests.start

    def ready(self):
        f, client = self.start(phase2_entry_contract=True)
        client.callback = clean_response
        f.run.review_next(client=client)
        f.run.finish_phase1(); f.run.reconcile_phase1_state()
        config = binding_tests.VerifiedPhase2BindingTests.config(self, f)
        binding = f.run.bind_phase2_entry(config)
        proof = f.run._history()._prove(f.store.read)
        return f, client, binding, proof

    def test_each_call_revalidates_and_returns_isolated_exact_closeout(self):
        f, client, binding, proof = self.ready()
        original = _Closeout.evaluate
        before = {str(p.relative_to(f.root)): p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        with patch.object(_Closeout, 'evaluate', autospec=True, side_effect=original) as evaluate:
            first = entry.inputs(proof)[0]
            expected = json.loads(f.store.read(binding.request['phase1_closeout']['path']))
            self.assertEqual(first['system_entry']['closeout'], expected)
            first['system_entry']['closeout']['review_receipts'].clear()
            second = entry.inputs(proof)[0]
            self.assertEqual(second['system_entry']['closeout'], expected)
            self.assertEqual(evaluate.call_count, 2)
        self.assertEqual((client.calls, f.editor.calls), (1, 0))
        self.assertEqual(before, {str(p.relative_to(f.root)): p.read_bytes() for p in f.root.rglob('*') if p.is_file()})

    def test_reused_proof_still_refuses_changed_prerequisites(self):
        f, _, binding, proof = self.ready()
        values = entry.inputs(proof)[0]
        closeout = values['system_entry']['closeout']
        receipt = values['system_entry']['review_receipt']
        paths = [binding.request_ref['path'], binding.configuration_ref['path'],
                 binding.configuration['rubric']['artifact']['path'],
                 binding.request['phase1_closeout']['path'], closeout['terminal_report']['path'],
                 receipt['path'], values['feedback_ref']['path'],
                 f.run._record['review_configuration']['path'],
                 f.run._record['descriptor']['path'], 'rounds/current_verified.json']
        for path in paths:
            with self.subTest(path=path):
                target = f.root / path
                raw = target.read_bytes()
                try:
                    target.write_bytes(raw + b' ')
                    with self.assertRaises(ValueError): entry.inputs(proof)
                finally:
                    target.write_bytes(raw)
        # Even a previously used proof rereads installed contract pins.
        with patch.object(entry, 'confined_file') as confined:
            confined.return_value.read_bytes.return_value = b'changed installed contract'
            with self.assertRaisesRegex(ValueError, 'absent or changed'): entry.inputs(proof)

    def test_change_between_binding_and_consumption_refuses(self):
        f, _, binding, proof = self.ready()
        values = entry.inputs(proof)[0]
        paths = [binding.request['phase1_closeout']['path'], values['system_entry']['review_receipt']['path'],
                 values['feedback_ref']['path'], 'rounds/current_verified.json',
                 f.run._record['descriptor']['path']]
        original = entry.binding_at
        for path in paths:
            with self.subTest(path=path):
                target = f.root / path
                raw = target.read_bytes()
                def change(current):
                    result = original(current)
                    target.write_bytes(raw + b' ')
                    return result
                try:
                    with patch.object(entry, 'binding_at', side_effect=change):
                        with self.assertRaises(ValueError): entry.inputs(proof)
                finally:
                    target.write_bytes(raw)


if __name__ == '__main__':
    unittest.main()
