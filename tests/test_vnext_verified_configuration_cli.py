"""Finite Q1 selector qualification; real CLI/owners, no model requests."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.cli import main
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_run import open_verified_run
from whetstone import vnext_verified_cli as routing
from vnext_q1_command_fixtures import CommandCase


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class ConfigurationCommandTests(CommandCase):
    def setUp(self):
        super().setUp()
        self.patch('whetstone.cli.load_config', side_effect=AssertionError('legacy fallback'))
        self.patch('whetstone.cli.LivePhase2Runner', side_effect=AssertionError('legacy Phase 2'))
        self.patch('whetstone.cli.apply_back', side_effect=AssertionError('legacy source writer'))

    def check_refusal(self, command='vnext-admit', *args):
        before = self.files()
        with patch.object(LocalAuthorityStore, 'acquire', side_effect=AssertionError('refusal took writer fence')):
            code, result = self.invoke(command, *args)
        self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.reviewer.calls, 0)
        return result

    def admit(self):
        self.qualify()
        code, result = self.invoke('vnext-admit')
        self.assertEqual(code, 0, result)

    def test_unknown_and_orphan_top_level_selectors_never_fall_back(self):
        for config in ({'editing_mode': value} for value in ('unknown', None, '', 'proposal_only', 'reviewer_only')):
            with self.subTest(config=config):
                self.config = config; self.save_config()
                self.check_refusal('live-phase1')
                self.assertFalse(self.root.exists())
        for config in ({'contract_suite_version': self.suite.version}, {'vnext_phase2_configuration': None}):
            with self.subTest(config=config):
                self.config = config; self.save_config(); self.check_refusal('live-phase1')
                self.assertFalse(self.root.exists())

    def test_fresh_mode_suite_package_and_bound_setting_matrix(self):
        self.qualify(); original = deepcopy(self.config)
        variants = [
            ('missing suite', {'contract_suite_version': None}),
            ('empty suite', {'contract_suite_version': ''}),
            ('unknown suite', {'contract_suite_version': 'unknown'}),
            ('other suite', {'contract_suite_version': 'vnext-contracts-1'}),
            ('null package', {'vnext_input_package': None}),
            ('malformed package', {'vnext_input_package': {}}),
            ('wrong package hash', {'vnext_input_package': {**original['vnext_input_package'], 'hash': 'f'*64}}),
            ('extra package field', {'vnext_input_package': {**original['vnext_input_package'], 'extra': 1}}),
            ('bridge mix', {'preservation_bridge': {}}),
            ('unknown control', {'automatic_apply': True}),
            ('workflow', {'workflow': 'governance'}),
            ('review mode', {'review': {'mode': 'vertical'}}),
            ('profile set', {'review': {'profile_set': 'utility_mvp'}}),
            ('budget', {'review': {'profile_budgets': {}}}),
            ('client', {'clients': {'reviewer': {'model': 'different'}}}),
            ('timeout', {'timeouts': {'reviewer_seconds': 0}}),
            ('closed vnext', {'vnext': {'vnext_phase2_configuration': {}}}),
        ]
        for name, update in variants:
            with self.subTest(case=name):
                self.config = {**deepcopy(original), **update}; self.save_config()
                self.check_refusal(); self.assertFalse(self.root.exists())
        for missing in ('contract_suite_version', 'vnext_input_package'):
            self.config = deepcopy(original); del self.config[missing]; self.save_config()
            self.check_refusal(); self.assertFalse(self.root.exists())

    def test_package_relative_locator_and_corroborating_cli_selectors(self):
        self.qualify()
        import os
        package = self.fixture.source/'proposal_package.json'
        self.config['vnext_input_package']['path'] = os.path.relpath(package, self.config_path.parent)
        self.save_config(); source = self.fixture.files(self.fixture.source)
        code, result = self.invoke('vnext-admit', '--dry-run', '--vnext-input-package', str(package),
            '--vnext-job-descriptor', self.f.job_ref['path'],
            '--vnext-review-configuration', self.f.original.review_ref['path'])
        self.assertEqual(code, 0, result); self.assertFalse(self.root.exists())
        self.assertEqual(self.fixture.files(self.fixture.source), source)
        self.check_refusal('vnext-admit', '--vnext-job-descriptor', self.f.job_ref['path'])
        other = self.config_path.parent/'other-package.json'
        packet = deepcopy(self.fixture.package)
        packet['mutation_constraints']['hash'] = 'f'*64
        other.write_bytes(canonical_json_bytes(packet))
        self.check_refusal('vnext-admit', '--vnext-input-package', str(other))
        self.config.pop('editing_mode'); self.config.pop('contract_suite_version'); self.save_config()
        self.check_refusal('vnext-admit', '--vnext-input-package', str(package))
        self.assertFalse(self.root.exists())

    def test_duplicate_json_and_yaml_selectors_refuse(self):
        for raw in ('{"editing_mode":"verified_promotion","editing_mode":"unknown"}',
                    'editing_mode: verified_promotion\nediting_mode: unknown\n'):
            with self.subTest(raw=raw):
                self.config_path.write_text(raw); self.check_refusal('live-phase1')
                self.assertFalse(self.root.exists())

    def test_retained_mode_rejects_edited_selectors_and_accepts_omission(self):
        self.admit(); original = deepcopy(self.config)
        for update in ({'editing_mode': None}, {'editing_mode': 'proposal_only'}, {'editing_mode': 'unknown'},
                       {'contract_suite_version': None}, {'contract_suite_version': 'vnext-contracts-1'},
                       {'vnext_input_package': None}, {'preservation_bridge': {}},
                       {'clients': {'editor': {'model': 'different'}}}):
            with self.subTest(update=update):
                self.config = {**deepcopy(original), **update}; self.save_config()
                self.check_refusal('status', '--format', 'json')
        self.config = {}; self.save_config(); before = self.files()
        with patch.object(LocalAuthorityStore, 'acquire', side_effect=AssertionError('inspection took fence')):
            for command, args in (('status', ('--format','json')), ('resume', ('--dry-run',))):
                code, result = self.invoke(command, *args); self.assertEqual(code, 0, result)
        self.assertEqual(self.files(), before)
        for command in ('live-phase1', 'promote-phase2', 'live-phase2'):
            self.check_refusal(command)
        self.config_path.unlink()
        code, result = self.invoke('status', '--format', 'json'); self.assertEqual(code, 0, result)
        self.assertEqual(self.files(), before)

    def test_retained_package_and_descriptor_edits_cannot_convert_the_job(self):
        self.admit()
        package = self.fixture.source/'proposal_package.json'; original = package.read_bytes()
        packet = json.loads(original); packet['mutation_constraints']['hash'] = 'f'*64
        package.write_bytes(canonical_json_bytes(packet))
        self.config['vnext_input_package']['hash'] = sha256_bytes(package.read_bytes()); self.save_config()
        self.check_refusal('status', '--format', 'json')
        package.write_bytes(original); self.config.pop('vnext_input_package'); self.save_config()
        path = self.root/'job_descriptor.json'; raw = path.read_bytes()
        try:
            for packet in ([], {**json.loads(raw), 'editing_mode':'proposal_only'}):
                with self.subTest(packet=packet):
                    path.write_bytes(canonical_json_bytes(packet)); self.check_refusal('status', '--format', 'json')
        finally: path.write_bytes(raw)

    def test_phase2_ref_shape_paths_bytes_schema_and_job_matrix(self):
        self.admit(); self.stage_phase2()
        reference = deepcopy(self.config['vnext_phase2_configuration'])
        path = self.root/reference['path']; original = path.read_bytes(); packet = json.loads(original)
        link = self.root/'inputs/phase2/alias.json'; link.symlink_to(path.resolve())
        refs = [None, {}, {**reference, 'extra':1}, {**reference,'hash':'f'*64},
                {**reference,'path':'../outside.json'}, {**reference,'path':str(path.resolve())},
                {**reference,'path':'inputs/phase2/alias.json'}, {**reference,'path':'missing.json'}]
        for ref in refs:
            with self.subTest(ref=ref):
                self.config['vnext_phase2_configuration'] = ref; self.save_config()
                self.check_refusal('status', '--format', 'json')
        variants = [b'[]\n', b'null', b'[]', original+b' ',
            canonical_json_bytes({**packet,'schema_version':'vnext-phase2-configuration-v1'}),
            canonical_json_bytes({**packet,'extra':True}),
            canonical_json_bytes({**packet,'job_id':'f'*64}),
            canonical_json_bytes({**packet,'job_id':'job_'+'f'*64}),
            canonical_json_bytes({**packet,'review_configuration':{**packet['review_configuration'],'hash':'f'*64}})]
        for raw in variants:
            with self.subTest(raw=raw[:100]):
                path.write_bytes(raw)
                self.config['vnext_phase2_configuration'] = {**reference,'hash':sha256_bytes(raw)}; self.save_config()
                self.check_refusal('status', '--format', 'json')
        path.write_bytes(original); self.config['vnext_phase2_configuration'] = reference; self.save_config()
        before = self.files()
        code,result = self.invoke('status','--format','json'); self.assertEqual(code,0,result)
        self.assertEqual(self.files(),before)
        # Prerequisites are revalidated under the real D8 fence, without writes.
        code,result = self.invoke('promote-phase2'); self.assertEqual(code,2,result)
        self.assertIn('Phase 1 prerequisites',result['reason'])
        self.assertEqual(self.files(),before)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())
        self.assertEqual(self.phase2_reviewer.calls,0)

    def test_bound_phase2_replacement_refuses_without_entry_or_clients(self):
        self.qualify()
        code,result = self.invoke('live-phase1'); self.assertEqual(code,0,result)
        self.stage_phase2()
        path = self.root/self.config['vnext_phase2_configuration']['path']
        packet = json.loads(path.read_bytes())
        with open_verified_run(self.root) as run: run.bind_phase2_entry(packet)
        packet['target_mode'] = 'permissive'
        other = self.root/'inputs/phase2/other.json'; other.write_bytes(canonical_json_bytes(packet))
        self.config['vnext_phase2_configuration'] = {'path':'inputs/phase2/other.json','hash':sha256_bytes(other.read_bytes())}
        self.save_config(); before = self.files(); calls = self.reviewer.calls
        for command,args in (('status',('--format','json')),('promote-phase2',()),('live-phase2',())):
            code,result = self.invoke(command,*args); self.assertEqual(code,2,result)
            self.assertIn('committed binding',result['reason'])
        self.assertEqual(self.files(),before); self.assertEqual(self.reviewer.calls,calls)
        self.assertEqual(self.phase2_reviewer.calls,0)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())

    def test_phase2_entry_revalidates_client_profile_rubric_and_input_barriers(self):
        self.qualify()
        code,result = self.invoke('live-phase1'); self.assertEqual(code,0,result)
        self.stage_phase2()
        reference = deepcopy(self.config['vnext_phase2_configuration'])
        path = self.root/reference['path']; raw = path.read_bytes(); original = json.loads(raw)
        variants = []
        for role in ('reviewer','editor','verifier'):
            packet = deepcopy(original); packet[role]['model'] = 'different'; variants.append(packet)
        packet = deepcopy(original)
        packet['profiles'][0], packet['profiles'][1] = packet['profiles'][1], packet['profiles'][0]
        variants.append(packet)
        packet = deepcopy(original); packet['review_mode'] = 'vertical'; variants.append(packet)
        packet = deepcopy(original); packet['rubric']['artifact']['hash'] = 'f'*64; variants.append(packet)
        calls = self.reviewer.calls
        for packet in variants:
            with self.subTest(packet=packet):
                value = canonical_json_bytes(packet); path.write_bytes(value)
                self.config['vnext_phase2_configuration'] = {**reference,'hash':sha256_bytes(value)}
                self.save_config(); before = self.files()
                code,result = self.invoke('promote-phase2'); self.assertEqual(code,2,result)
                self.assertEqual(self.files(),before)
        path.write_bytes(raw); self.config['vnext_phase2_configuration'] = reference; self.save_config()
        before = self.files(); acquire = LocalAuthorityStore.acquire; hits = []
        def changed(store,validate):
            if store.root == self.root.resolve() and not hits:
                path.write_bytes(raw+b' '); hits.append(True)
            return acquire(store,validate)
        try:
            with patch.object(LocalAuthorityStore,'acquire',changed):
                code,result = self.invoke('promote-phase2')
            self.assertEqual(code,2,result); self.assertEqual(hits,[True])
            self.assertIn('configuration hash differs',result['reason'])
        finally: path.write_bytes(raw)
        self.assertEqual(self.files(),before); self.assertEqual(self.reviewer.calls,calls)
        self.assertEqual(self.phase2_reviewer.calls,0)
        self.assertFalse((self.root/'rounds/phase2/entry_request.json').exists())
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())

    def test_unsupported_commands_and_controls_cannot_reach_legacy(self):
        self.admit()
        for command,args in (('live-round',('--profile','structural_integrity')),
            ('fixture-script',('--script','absent.json')), ('live-phase1',('--overwrite',)),
            ('resume',('--extend-review-budget','1','--continue')), ('resume',('--vnext-round','0'))):
            with self.subTest(command=command,args=args): self.check_refusal(command,*args)
        before=self.files(); output=StringIO()
        with redirect_stdout(output):
            code=main(['strop','--run-root',str(self.root),'--config',str(self.config_path),
                '--source',str(self.root.parent/'unused.md'),'--allow-non-converged'])
        self.assertEqual(code,2,output.getvalue()); self.assertEqual(self.files(),before)

    def test_registered_suite_and_wrong_digest_do_not_activate_fresh_or_retained(self):
        for gate in ({},{self.suite.version:'f'*64}):
            with self.subTest(gate=gate),patch.dict(routing.QUALIFIED_VERIFIED_SUITES,gate,clear=True):
                self.check_refusal(); self.assertFalse(self.root.exists())
        self.admit(); self.config={}; self.save_config()
        for gate in ({},{self.suite.version:'f'*64}):
            with self.subTest(gate=gate),patch.dict(routing.QUALIFIED_VERIFIED_SUITES,gate,clear=True):
                result=self.check_refusal('status','--format','json')
                self.assertEqual(result['reason_code'],'vnext_mode_unavailable')


if __name__ == '__main__': unittest.main()
