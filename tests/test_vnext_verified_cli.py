"""Q1 command qualification uses fictional clients and an explicitly injected gate."""
from contextlib import redirect_stdout
from io import StringIO
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.cli import main
from whetstone import vnext_registry
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_verified_run import open_verified_run
from whetstone import vnext_verified_cli as routing
import test_vnext_proposal_package as packages
from test_vnext_review_requests import Reviewer


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class VerifiedCLITests(unittest.TestCase):
    setUpClass = packages.ProposalPackageTests.setUpClass

    def setUp(self):
        self.fixture = packages.ProposalPackageTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f.f
        self.suite = validate_contract_suite(CONTRACT_ROOT/'suites/vnext-verified-consumer-1.json')
        self.f.suite = self.suite
        self.f.job.update(contract_suite_version=self.suite.version, editing_mode='verified_promotion',
                          **vnext_registry.SUITE_ALGORITHM_VERSIONS[self.suite.version])
        self.f.rebind()
        self.fixture.package['job_descriptor'] = self.f.job_ref
        self.fixture.package['review_configuration'] = self.f.original.review_ref
        self.fixture.save_package()
        self.root = self.fixture.destination
        self.config_path = self.root.parent/'verified-config.json'
        self.config = dict(editing_mode='verified_promotion', contract_suite_version=self.suite.version,
            vnext_input_package=dict(path=str(self.fixture.source/'proposal_package.json'),
                hash=sha256_bytes((self.fixture.source/'proposal_package.json').read_bytes())))
        self.save_config()
        self.reviewer = Reviewer(self.f, self.clean)
        self.patch('whetstone.vnext_proposal_cli.NativeProposalReviewerClient', return_value=self.reviewer)
        from unittest.mock import Mock
        for role in ('NativePatchProposalClient', 'NativeSemanticVerifierClient'):
            self.patch('whetstone.vnext_proposal_cli.'+role,
                       return_value=Mock(propose=Mock(side_effect=AssertionError('unexpected Editor')),
                                         verify=Mock(side_effect=AssertionError('unexpected Verifier'))))
        self.patch('whetstone.vnext_native_editor._run_codex_exec', side_effect=AssertionError('live provider forbidden'))
        self.patch('whetstone.vnext_native_editor._run_claude_print', side_effect=AssertionError('live provider forbidden'))

    def patch(self, *args, **kwargs):
        value = patch(*args, **kwargs)
        result = value.start(); self.addCleanup(value.stop)
        return result

    def qualify(self):
        value = patch.dict(routing.QUALIFIED_VERIFIED_SUITES, {self.suite.version:self.suite.digest})
        value.start(); self.addCleanup(value.stop)

    def save_config(self): self.config_path.write_text(json.dumps(self.config))

    @staticmethod
    def clean(packet):
        packet['feedback']['feedback'] = []
        packet['classifications'] = []
        return canonical_json_bytes(packet)

    def invoke(self, command, *args):
        output = StringIO()
        with redirect_stdout(output):
            code = main([command, '--root', str(self.root), '--config', str(self.config_path), *args])
        return code, json.loads(output.getvalue())

    def files(self): return self.fixture.files(self.root) if self.root.exists() else {}

    def test_registered_suite_is_not_public_activation(self):
        code, result = self.invoke('vnext-admit')
        self.assertEqual(code, 2, result)
        self.assertEqual(result['reason_code'], 'vnext_mode_unavailable')
        self.assertFalse(self.root.exists())
        self.assertEqual(self.reviewer.calls, 0)

    def test_admission_dry_run_reopen_status_and_removed_selectors(self):
        self.qualify()
        before = self.fixture.files(self.fixture.source)
        code, result = self.invoke('vnext-admit', '--dry-run')
        self.assertEqual(code, 0, result)
        self.assertFalse(self.root.exists())
        code, result = self.invoke('vnext-admit')
        self.assertEqual(code, 0, result)
        with open_verified_run(self.root) as run:
            self.assertEqual(run.inspect().current_pointer['promotion_ordinal'], 0)
        self.assertEqual(self.fixture.files(self.fixture.source), before)
        files = self.files()
        self.config = {}; self.save_config()
        code, result = self.invoke('status', '--format', 'json')
        self.assertEqual(code, 0, result)
        self.assertEqual(self.files(), files)
        code, result = self.invoke('live-phase1')
        self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), files)
        self.assertEqual(self.reviewer.calls, 0)

    def test_config_conflict_and_existing_destination_refuse_before_writes(self):
        self.qualify()
        self.config['contract_suite_version'] = 'unknown-suite'; self.save_config()
        code, result = self.invoke('vnext-admit')
        self.assertEqual(code, 2, result)
        self.assertFalse(self.root.exists())
        self.config['contract_suite_version'] = self.suite.version; self.save_config()
        self.root.mkdir()
        code, result = self.invoke('vnext-admit')
        self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), {})

    def test_phase1_clean_journey_stops_before_entry(self):
        self.qualify()
        code, result = self.invoke('live-phase1')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['gate'], 'phase1_complete')
        self.assertGreater(self.reviewer.calls, 0)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())
        calls = self.reviewer.calls
        code, again = self.invoke('live-phase1')
        self.assertEqual(code, 0, again)
        self.assertEqual(self.reviewer.calls, calls)


    def stage_phase2(self):
        from copy import deepcopy
        from whetstone.vnext_verified_phase2_binding import PROFILE_ORDER
        with open_verified_run(self.root) as run:
            rubric = (CONTRACT_ROOT.parent/'rubrics/standard-v1.md').read_bytes()
            path = 'inputs/phase2/rubric.md'
            review = json.loads(run.store.read(run._record['review_configuration']['path']))
            packet = dict(schema_version='vnext-phase2-configuration-v3', job_id=self.f.job['job_id'],
                review_configuration=deepcopy(run._record['review_configuration']), workflow='standard',
                review_mode='horizontal', profile_set='stateful_system', target_phase='final', target_mode='strict',
                rubric=dict(profile='standard-v1', source='builtin', artifact=dict(path=path,hash=sha256_bytes(rubric))),
                profiles=[dict(name=name,budget=2) for name in PROFILE_ORDER],
                **{role:review[role] for role in ('reviewer','editor','verifier')})
            raw = canonical_json_bytes(packet)
            with run.store.locked(run._history().validate_authority) as token:
                run.store.publish(token,path,rubric)
                run.store.publish(token,'inputs/phase2/configuration.json',raw)
            self.config['vnext_phase2_configuration'] = dict(path='inputs/phase2/configuration.json',hash=sha256_bytes(raw))
        self.save_config()
        from test_vnext_verified_phase2_client import Client
        transport = deepcopy(self.reviewer.transport_binding)
        transport['output_schema_hash'] = sha256_bytes((CONTRACT_ROOT/'schemas/vnext_phase2_rubric_response_v2.schema.json').read_bytes())
        def clean(client, packet):
            inputs = json.loads(client.prompts[-1].splitlines()[-1])
            packet.update(feedback=[], draft_hash=inputs['draft_hash'] if 'draft_hash' in inputs else
                          sha256_bytes(inputs['draft'].encode()))
            return canonical_json_bytes(dict(review=packet,rubric_findings=[],classifications=[]))
        self.phase2_reviewer = Client(transport, self.f.feedback, clean)
        self.patch('whetstone.vnext_verified_commands.phase2_client', return_value=self.phase2_reviewer)
        self.patch('whetstone.vnext_verified_phase2_commands.phase2_client', return_value=self.phase2_reviewer)

    def test_clean_phase2_journey_has_distinct_entry_and_convergence(self):
        self.qualify()
        code, result = self.invoke('live-phase1'); self.assertEqual(code,0,result)
        self.stage_phase2()
        code, result = self.invoke('promote-phase2'); self.assertEqual(code,0,result)
        self.assertTrue(result['committed'],result)
        self.assertEqual(self.phase2_reviewer.calls,0)
        code, result = self.invoke('live-phase2'); self.assertEqual(code,0,result)
        self.assertTrue(result.get('phase_complete') or result.get('gate')=='phase2_complete',result)
        self.assertEqual(self.phase2_reviewer.calls,2)
        before = self.files()
        code, result = self.invoke('status','--format','json');self.assertEqual(code,0,result)
        self.assertEqual(self.files(),before)
        self.assertEqual(result['gate'],'phase2_complete')


    def test_phase1_timeout_requires_explicit_remaining_allowance_and_stops(self):
        self.qualify()
        def timeout(packet): raise TimeoutError('fictional reviewer timeout')
        self.reviewer.callback = timeout
        code, result = self.invoke('live-phase1')
        self.assertEqual(code,2,result)
        self.assertEqual(self.reviewer.calls,1)
        before = self.files()
        code, result = self.invoke('live-phase1')
        self.assertEqual(code,2,result)
        self.assertEqual(self.reviewer.calls,1)
        self.assertEqual(self.files(),before)
        code, result = self.invoke('resume','--dry-run')
        self.assertEqual(code,0,result)
        self.assertEqual(self.files(),before)
        self.reviewer.callback = self.clean
        code, result = self.invoke('resume')
        self.assertEqual(code,0,result)
        self.assertEqual(self.reviewer.calls,2)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())
        code, result = self.invoke('live-phase1')
        self.assertEqual(code,0,result)
        self.assertEqual(result['gate'],'phase1_complete')
        self.assertEqual(self.reviewer.calls,2)

    def test_changed_boundary_under_actual_fence_cannot_launch_next_review(self):
        from whetstone.vnext_verified_command_state import inspect_command
        from whetstone.vnext_verified_commands import guarded, SelectionChanged
        self.qualify()
        code,result = self.invoke('vnext-admit');self.assertEqual(code,0,result)
        with open_verified_run(self.root) as run, open_verified_run(self.root) as peer:
            run.reconcile_phase1_state()
            selected = inspect_command(run)
            self.assertEqual(selected['gate'],'review')
            acquire = run.store.acquire
            def raced(validate):
                peer.review_next(client=self.reviewer)
                return acquire(validate)
            with patch.object(run.store,'acquire',side_effect=raced):
                with self.assertRaises(SelectionChanged):
                    guarded(run,selected,lambda:run.review_next(client=self.reviewer))
            self.assertEqual(self.reviewer.calls,1)


    def test_bound_configuration_is_not_entry_and_changed_selector_refuses(self):
        self.qualify()
        code,result = self.invoke('live-phase1'); self.assertEqual(code,0,result)
        self.stage_phase2()
        with open_verified_run(self.root) as run:
            packet = json.loads(run.store.read('inputs/phase2/configuration.json'))
            run.bind_phase2_entry(packet)
        before = self.files()
        code,result = self.invoke('resume','--continue','--dry-run')
        self.assertEqual(code,2,result)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())
        self.assertEqual(self.files(),before)
        self.assertEqual(self.phase2_reviewer.calls,0)
        self.config['vnext_phase2_configuration']['hash'] = 'f'*64
        self.save_config()
        code,result = self.invoke('status','--format','json')
        self.assertEqual(code,2,result)
        self.assertIn('configuration hash differs',result['reason'])
        self.assertEqual(self.files(),before)


if __name__ == '__main__': unittest.main()
