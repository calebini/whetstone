"""Public opt-in journeys: real config/CLI, scripted model transports only."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import test_preservation_runtime as fixtures
from test_preservation_continuation import ScriptedReviewer
from whetstone.cli import main
from whetstone.config import load_config
from whetstone.preservation_contracts import BridgeContractError


def bridge_yaml(surface, predecessor="null"):
    text = ("preservation_bridge:\n"
            "  mode: enforce\n"
            "  capability_version: preservation-bridge-v1\n"
            "  allowed_change_surface:\n"
            f"    path: {surface['path']}\n"
            f"    sha256: \"{surface['sha256']}\"\n")
    if predecessor is not None:
        text += f"  predecessor_report: {predecessor}\n"
    return text


class ActivationConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'orchestrator_config.yaml'
        self.surface = {'path': './rounds/intake/surface.json', 'sha256': 'a' * 64}

    def test_documented_opt_in_and_optional_null_load_without_gate_override(self):
        for predecessor in (None, 'null', 'Null', 'NULL', '~'):
            with self.subTest(predecessor=predecessor):
                self.path.write_text(bridge_yaml(self.surface, predecessor))
                config = load_config(self.path)
                self.assertEqual(config.preservation_bridge.mode, 'enforce')
                self.assertEqual(config.preservation_bridge.capability_version, 'preservation-bridge-v1')
                self.assertEqual(config.preservation_bridge.allowed_change_surface, self.surface)
                self.assertIsNone(config.preservation_bridge.predecessor_report)

    def test_explicit_predecessor_ref_is_retained(self):
        self.path.write_text(bridge_yaml(self.surface, None) +
                             '  predecessor_report:\n    path: previous/report.json\n    sha256: "' + 'b'*64 + '"\n')
        self.assertEqual(load_config(self.path).preservation_bridge.predecessor_report,
                         {'path': 'previous/report.json', 'sha256': 'b'*64})

    def test_omission_keeps_legacy_defaults(self):
        self.assertIsNone(load_config(self.path).preservation_bridge)
        self.path.write_text('workflow: standard\n')
        self.assertIsNone(load_config(self.path).preservation_bridge)

    def test_invalid_opt_in_fails_public_cli_before_client_creation(self):
        valid = bridge_yaml(self.surface)
        cases = [
            'preservation_bridge: null\n', 'preservation_bridge: {}\n',
            'preservation_bridge:\n  mode: enforce\n  capability_version: preservation-bridge-v1\n',
            valid.replace('mode: enforce', 'mode: report_only'),
            valid.replace('preservation-bridge-v1', 'vNext'),
            valid + '  bypass: true\n',
            valid + 'editing_mode: verified_promotion\n',
            valid + 'contract_suite_version: vNext\n',
            valid.replace('./rounds/intake/surface.json', '../surface.json'),
            valid.replace('./rounds/intake/surface.json', '/tmp/surface.json'),
            valid.replace('a'*64, 'wrong'),
            valid.replace('    sha256:', '    extra: value\n    sha256:'),
            valid.replace('predecessor_report: null', 'predecessor_report: "null"'),
            valid + 'preservation_bridge: null\n',
            valid + '  mode: enforce\n',
            valid.replace('    path:', '    path: ignored.json\n    path:'),
        ]
        with patch('whetstone.live.create_reviewer_client') as reviewer, patch('whetstone.live.create_editor_client') as editor:
            for text in cases:
                with self.subTest(text=text):
                    self.path.write_text(text)
                    with self.assertRaisesRegex(ValueError, 'CONFIG_INVALID'):
                        main(['live-phase1', '--root', str(self.root)])
            reviewer.assert_not_called()
            editor.assert_not_called()
        self.assertFalse((self.root/'rounds/run_state.json').exists())


class PublicActivationJourneyTests(unittest.TestCase):
    setUp = fixtures.RuntimeTests.setUp
    setup_run = fixtures.RuntimeTests.setup_run
    snapshot = fixtures.RuntimeTests.snapshot

    def write_config(self):
        (self.root/'orchestrator_config.yaml').write_text(
            'scope_contract:\n  path: scope.json\n'
            'clients:\n  reviewer:\n    name: codex\n    command: unused\n    version: "1"\n    model: fixture\n'
            '  editor:\n    name: codex\n    command: unused\n    version: "1"\n    model: fixture\n'
            'review:\n  profile_budgets:\n    structural_integrity: 1\n    determinism: 1\n    operability: 1\n'
            + bridge_yaml(self.p.surface_ref))

    def cli(self, command, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main([command, '--root', str(self.root), *args])
        self.assertEqual(code, 0, output.getvalue())
        return json.loads(output.getvalue())

    def test_opt_in_pending_approval_and_continuation_through_public_cli(self):
        self.setup_run(serious=True)
        self.write_config()
        reviewer = ScriptedReviewer(self.root, self.p.feedback, [
            (1, 'structural_integrity', self.p.feedback['feedback']),
            (2, 'structural_integrity', []),
        ])
        with patch('whetstone.live.create_reviewer_client', return_value=reviewer), \
             patch('whetstone.live.create_editor_client', return_value=self.editor):
            result = self.cli('live-focused-phase1', '--profile', 'structural_integrity', '--budget', '1')
            self.assertEqual(result['terminal_state'], 'PAUSED_DECISION')
            self.assertEqual((self.root/'spec.md').read_bytes(), self.p.raw)
            status = self.cli('status', '--format', 'json')
            self.assertEqual(status['preservation_bridge']['mode'], 'enforce')
            proposal = status['preservation_bridge']['latest_proposal']['path']
            self.cli('preservation-review', '--proposal', proposal)
            self.cli('preservation-attest', '--proposal', proposal, '--output', 'effect.json',
                     '--kind', 'attest_equivalence', '--base-lines', '9', '--output-lines', '9',
                     '--disposition', 'reworded_equivalent', '--change-type', 'clarify', '--finding', 'fb-1',
                     '--effect', 'Same retry requirement.', '--rationale', 'Explicit fictional fixture review.',
                     '--operator', 'fixture-operator', '--approve')
            self.cli('preservation-request', '--proposal', proposal, '--evidence', 'effect.json', '--output', 'request.json')
            before = self.snapshot()
            self.assertEqual(self.cli('preservation-accept', '--request', 'request.json', '--dry-run')['outcome'], 'eligible')
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.cli('preservation-accept', '--request', 'request.json')['outcome'], 'accepted')
            self.assertEqual((self.root/'spec.md').read_bytes(), self.p.after)
            self.assertEqual((reviewer.calls, self.editor.calls), (1, 1))
            before = self.snapshot()
            self.cli('preservation-accept', '--request', 'request.json')
            self.cli('resume', '--continue', '--dry-run')
            self.assertEqual(self.snapshot(), before)
            result = self.cli('resume', '--continue')
            self.assertEqual(result['terminal_state'], 'FOCUSED_PROFILE_STABLE')
            self.assertEqual((reviewer.calls, self.editor.calls), (2, 1))
            status = self.cli('status', '--format', 'json')
            self.assertFalse(status['ready_for_phase_2'])
            self.assertIsNone(status['preservation_bridge']['pending_outcome'])
        # Neither removal nor omission can downgrade an admitted root.
        path = self.root/'orchestrator_config.yaml'
        path.write_text('workflow: standard\n')
        with self.assertRaisesRegex(ValueError, 'CONFIG_INVALID.*downgrade'):
            load_config(path)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'CONFIG_INVALID.*omit'):
            load_config(path)

    def test_public_phase1_noop_is_enforced_without_editor(self):
        self.setup_run(noop=True)
        self.write_config()
        reviewer = ScriptedReviewer(self.root, self.p.feedback, [
            (1, 'structural_integrity', []), (2, 'determinism', []), (3, 'operability', []),
        ])
        with patch('whetstone.live.create_reviewer_client', return_value=reviewer), \
             patch('whetstone.live.create_editor_client') as editor:
            result = self.cli('live-phase1')
            self.assertEqual(result['terminal_state'], 'PHASE_1_STABLE')
            self.assertTrue(result['ready_for_phase_2'])
            editor.assert_not_called()
        self.assertEqual(reviewer.calls, 3)
        self.assertEqual((self.root/'spec.md').read_bytes(), self.p.raw)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))), 3)
        self.assertEqual(self.cli('status', '--format', 'json')['preservation_bridge']['mode'], 'enforce')

    def test_invalid_surface_or_legacy_root_refused_before_clients(self):
        for problem in ('missing', 'corrupt', 'unapproved', 'stale_base', 'scope_mismatch', 'legacy_root'):
            with self.subTest(problem=problem), TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                self.setup_run()
                if problem == 'missing':
                    (self.root/'surface.json').unlink()
                elif problem == 'corrupt':
                    (self.root/'surface.json').write_bytes(b'{}')
                elif problem == 'unapproved':
                    self.p.surface['approval']['approved'] = False
                    self.p.surface_ref = self.p.save('surface.json', self.p.surface)
                elif problem == 'stale_base':
                    (self.root/'spec.md').write_bytes(self.p.raw + b'\nChanged base.\n')
                elif problem == 'scope_mismatch':
                    scope = json.loads((self.root/'scope.json').read_bytes())
                    scope['core_outcome'] = 'Changed scope.'
                    self.p.save('scope.json', scope)
                else:
                    (self.root/'rounds').mkdir()
                    (self.root/'rounds/run_state.json').write_text('{}')
                self.write_config()
                before = (self.root/'spec.md').read_bytes()
                with patch('whetstone.live.create_reviewer_client') as reviewer, patch('whetstone.live.create_editor_client') as editor:
                    with self.assertRaises((BridgeContractError, OSError)):
                        self.cli('live-phase1')
                    reviewer.assert_not_called()
                    editor.assert_not_called()
                self.assertEqual((self.root/'spec.md').read_bytes(), before)
                self.assertFalse(list(self.root.rglob('acceptance.json')))


if __name__ == '__main__':
    unittest.main()
