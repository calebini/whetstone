"""Controlled release smoke checks using the shipping V gate, never an injected one."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone import vnext_verified_cli as routing
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, validate_contract_suite
import test_vnext_verified_cli as helpers


class VerifiedReleasePinTests(unittest.TestCase):
    def test_shipping_map_matches_both_approved_manifests(self):
        expected = {
            'vnext-verified-consumer-1': '7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58',
            'vnext-verified-consumer-3': '46a7d73362aa8c1463e20978f2dc9803a588dae6e043c461321492d33c42313c',
        }
        self.assertEqual(routing.QUALIFIED_VERIFIED_SUITES, expected)
        for name, digest in expected.items():
            with self.subTest(suite=name):
                suite = validate_contract_suite(CONTRACT_ROOT / 'suites' / (name + '.json'))
                self.assertEqual(suite.digest, digest)


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class ActivatedVerifiedCLITests(unittest.TestCase):
    setUpClass = helpers.VerifiedCLITests.setUpClass
    setUp = helpers.VerifiedCLITests.setUp
    patch = helpers.VerifiedCLITests.patch
    save_config = helpers.VerifiedCLITests.save_config
    clean = staticmethod(helpers.VerifiedCLITests.clean)
    invoke = helpers.VerifiedCLITests.invoke
    files = helpers.VerifiedCLITests.files

    def admit(self):
        self.assertEqual(routing.QUALIFIED_VERIFIED_SUITES.get(self.suite.version), self.suite.digest)
        code, packet = self.invoke('vnext-admit')
        self.assertEqual(code, 0, packet)

    def test_shipping_admission_dry_run_retained_status_and_selected_recovery(self):
        source = self.fixture.files(self.fixture.source)
        code, packet = self.invoke('vnext-admit', '--dry-run')
        self.assertEqual(code, 0, packet)
        self.assertFalse(self.root.exists())
        self.admit()
        retained = self.files()
        code, packet = self.invoke('status', '--format', 'json')
        self.assertEqual(code, 0, packet)
        self.assertEqual(self.files(), retained)
        # Select an existing no-client materialization-recovery boundary.
        (self.root/'spec.md').unlink()
        missing = self.files()
        code, packet = self.invoke('status', '--format', 'json')
        self.assertEqual(code, 0, packet)
        self.assertEqual(packet['recovery'], 'materialization')
        code, packet = self.invoke('resume', '--dry-run')
        self.assertEqual(code, 0, packet)
        self.assertEqual(self.files(), missing)
        code, packet = self.invoke('resume')
        self.assertEqual(code, 0, packet)
        self.assertEqual(self.files(), retained)
        self.assertEqual(self.fixture.files(self.fixture.source), source)
        self.assertEqual(self.reviewer.calls, 0)

    def test_unknown_unqualified_and_conflicting_selection_refuse_before_writes(self):
        original = deepcopy(self.config)
        variants = [
            {'contract_suite_version': 'unknown-suite'},
            {'contract_suite_version': 'vnext-contracts-1'},
            {'vnext_input_package': {**original['vnext_input_package'], 'hash': 'f'*64}},
            {'preservation_bridge': {}},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                self.config = {**deepcopy(original), **variant}; self.save_config()
                code, packet = self.invoke('vnext-admit')
                self.assertEqual(code, 2, packet)
                self.assertFalse(self.root.exists())
        self.assertEqual(self.reviewer.calls, 0)

    def test_retained_mode_and_client_selection_cannot_be_changed(self):
        self.admit(); retained = self.files(); original = deepcopy(self.config)
        for variant in ({'editing_mode': 'reviewer_only'},
                        {'contract_suite_version': 'vnext-contracts-1'},
                        {'clients': {'reviewer': {'model': 'different'}}}):
            with self.subTest(variant=variant):
                self.config = {**deepcopy(original), **variant}; self.save_config()
                code, packet = self.invoke('status', '--format', 'json')
                self.assertEqual(code, 2, packet)
                self.assertEqual(self.files(), retained)
        self.config = {}; self.save_config()
        code, packet = self.invoke('status', '--format', 'json')
        self.assertEqual(code, 0, packet)
        self.assertEqual(self.files(), retained)
        self.assertEqual(self.reviewer.calls, 0)

    def test_installed_manifest_drift_refuses_with_the_real_shipping_gate(self):
        self.admit(); retained = self.files()
        # Corrupt only a disposable installed-manifest copy. Production pins and
        # the real qualification mapping stay untouched throughout the check.
        alternate = self.root.parent/'drifted-contracts'; (alternate/'suites').mkdir(parents=True)
        packet = deepcopy(self.suite.manifest); packet['suite_digest'] = '0'*64
        (alternate/'suites'/f'{self.suite.version}.json').write_bytes(canonical_json_bytes(packet))
        with patch.object(routing, 'CONTRACT_ROOT', alternate):
            code, packet = self.invoke('status', '--format', 'json')
        self.assertEqual(code, 2, packet)
        self.assertIn('manifest canonical digest mismatch', packet['reason'])
        self.assertEqual(self.files(), retained)
        self.assertEqual(self.reviewer.calls, 0)


if __name__ == '__main__': unittest.main()
