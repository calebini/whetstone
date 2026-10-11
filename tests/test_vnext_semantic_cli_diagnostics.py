"""Failure capture for the Q3 native command/reentry qualification journey."""
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_vnext_semantic_cli as cli


class NativeReentryDiagnosticTests(unittest.TestCase):
    def test_failed_readback_retains_full_packets_and_fixture_before_cleanup(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            for command, expected_code in [('status', 0), ('live-phase1', 2)]:
                with self.subTest(command=command):
                    output = base / command
                    output.mkdir()
                    with TemporaryDirectory() as fixture:
                        root = Path(fixture) / 'run'
                        root.mkdir()
                        (root / 'evidence.json').write_bytes(b'{"retained":true}')
                        case = unittest.TestCase()
                        case.subject = SimpleNamespace(root=root)
                        expected = (expected_code, {'terminal_state': 'TARGET_NOT_REACHED'})
                        actual = (2, {'terminal_state': 'HALTED_ARTIFACT_INVALID',
                                      'reason': 'full diagnostic ' * 100 + 'END-OF-DIAGNOSTIC'})
                        with patch.object(cli.tempfile, 'mkdtemp', return_value=str(output)):
                            with self.assertRaises(AssertionError) as error:
                                cli.assert_native_reentry(case, command, expected, actual)
                        self.assertIn(str(output), str(error.exception))
                        self.assertIn('END-OF-DIAGNOSTIC', str(error.exception))
                        self.assertNotIn('Set self.maxDiff', str(error.exception))
                    self.assertFalse(root.exists())
                    packets = json.loads((output / 'packets.json').read_text())
                    self.assertEqual(packets['actual'], list(actual))
                    self.assertEqual(packets['expected'], list(expected))
                    with tarfile.open(output / 'fixture.tar.gz') as archive:
                        self.assertEqual(archive.extractfile('forensic-fixture/run/evidence.json').read(),
                                         b'{"retained":true}')

    def test_success_creates_no_diagnostics_and_exit_code_is_part_of_comparison(self):
        case = unittest.TestCase()
        with patch.object(cli.tempfile, 'mkdtemp') as create:
            for command, code in [('status', 0), ('live-phase1', 2)]:
                cli.assert_native_reentry(case, command, (code, {'same': True}), (code, {'same': True}))
            create.assert_not_called()
        with TemporaryDirectory() as directory:
            case.subject = SimpleNamespace(root=Path(directory) / 'fixture' / 'run')
            with patch.object(cli.tempfile, 'mkdtemp', return_value=directory), \
                    patch.object(cli.tarfile, 'open', side_effect=OSError('archive unavailable')):
                with self.assertRaisesRegex(AssertionError, 'readback evidence retained'):
                    cli.assert_native_reentry(case, 'status', (0, {'same': True}), (2, {'same': True}))
            self.assertEqual((Path(directory) / 'archive-error.txt').read_text(), 'archive unavailable\n')
            self.assertEqual(json.loads((Path(directory) / 'packets.json').read_text())['actual'][0], 2)


if __name__ == '__main__':
    unittest.main()
