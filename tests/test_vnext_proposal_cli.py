from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from whetstone.cli import main
from whetstone import vnext_proposal_cli as routing
from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_proposal_run import open_proposal_run
import test_vnext_proposal_package as package_tests
from test_vnext_proposal_requests import Client as Editor
from test_vnext_review_requests import Reviewer


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class ProposalCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):package_tests.ProposalPackageTests.setUpClass()
    def setUp(self):
        self.fixture=package_tests.ProposalPackageTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f.f;self.root=self.fixture.destination;self.suite=self.fixture.f.suite
        self.package=self.fixture.source/'proposal_package.json'
        self.config=self.root.parent/'command-config.json';self.config.write_text('{}')
        for module in ('vnext_proposal_package','vnext_proposal_run'):
            self.patch('whetstone.'+module+'.CONTRACT_ROOT',self.suite.root)
        self.qualifier=patch.dict(routing.QUALIFIED_PROPOSAL_SUITES,{self.suite.version:self.suite.digest})
        self.qualifier.start();self.addCleanup(self.qualifier.stop)
        self.reviewer=Reviewer(self.f);self.editor=Editor()
        self.review_factory=self.patch('whetstone.vnext_proposal_cli.NativeProposalReviewerClient',return_value=self.reviewer)
        self.editor_factory=self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=self.editor)
    def patch(self,*args,**kwargs):
        p=patch(*args,**kwargs);value=p.start();self.addCleanup(p.stop);return value
    def invoke(self,command,*args,package=False):
        arguments=[command,'--root',str(self.root),'--config',str(self.config),*args]
        if package:arguments+=['--vnext-input-package',str(self.package)]
        out=StringIO()
        with redirect_stdout(out):code=main(arguments)
        return code,json.loads(out.getvalue())
    def files(self):return self.fixture.files(self.root) if self.root.exists() else {}
    def clean(self,packet):
        packet['feedback']['feedback']=[];packet['classifications']=[]
        return canonical_json_bytes(packet)

    def test_fresh_dry_run_then_admission_and_read_only_status(self):
        before=self.fixture.files(self.fixture.source)
        code,packet=self.invoke('vnext-admit','--dry-run',package=True)
        self.assertEqual(code,0);self.assertFalse(packet['vnext']['admitted']);self.assertFalse(self.root.exists())
        code,packet=self.invoke('vnext-admit',package=True)
        self.assertEqual(code,0);self.assertTrue(packet['vnext']['admitted'])
        self.assertIn('proposal_only',packet['vnext']['available_modes'])
        before_run=self.files();code,packet=self.invoke('status')
        self.assertEqual(code,0);self.assertEqual(packet['proposal_status']['request_status'],'not_started')
        self.assertEqual(before_run,self.files());self.assertEqual(before,self.fixture.files(self.fixture.source))
        self.assertEqual((self.reviewer.calls,self.editor.calls),(0,0))

    def test_shipping_gate_and_digest_mismatch_never_create_authority(self):
        for registration in ({},{self.suite.version:'f'*64}):
            with self.subTest(registration=registration),patch.dict(routing.QUALIFIED_PROPOSAL_SUITES,registration,clear=True):
                code,packet=self.invoke('vnext-admit',package=True)
                self.assertEqual(code,2);self.assertEqual(packet['vnext']['reason_code'],'vnext_gate_unavailable')
                self.assertNotIn('proposal_only',packet['vnext']['available_modes']);self.assertFalse(self.root.exists())
        self.review_factory.assert_not_called();self.editor_factory.assert_not_called()

    def test_config_package_selector_and_conflicts_are_checked_before_creation(self):
        raw=self.package.read_bytes()
        self.config.write_text(json.dumps({'vnext_input_package':{'path':str(self.package),'hash':sha256_bytes(raw)}}))
        code,_=self.invoke('vnext-admit','--dry-run');self.assertEqual(code,0)
        code,_=self.invoke('vnext-admit','--dry-run',package=True);self.assertEqual(code,0)
        self.config.write_text(json.dumps({'vnext_input_package':{'path':str(self.package),'hash':'f'*64}}))
        code,packet=self.invoke('vnext-admit',package=True)
        self.assertEqual((code,packet['vnext']['reason_code']),(2,'vnext_config_invalid'))
        self.config.write_text(json.dumps({'vnext_input_package':None}))
        self.assertEqual(self.invoke('vnext-admit')[0],2);self.assertFalse(self.root.exists())

    def test_round_selectors_and_legacy_controls_refuse_before_mutation(self):
        for arguments in [('--vnext-round','0'),('--vnext-round','2'),('--overwrite',)]:
            with self.subTest(arguments=arguments):
                self.assertEqual(self.invoke('live-phase1',*arguments,package=True)[0],2)
                self.assertFalse(self.root.exists())
        self.invoke('vnext-admit',package=True);before=self.files()
        for command,args in [('resume',('--extend-review-budget','3','--continue')),('live-phase2',())]:
            with self.subTest(command=command):self.assertEqual(self.invoke(command,*args)[0],2)
        self.assertEqual(before,self.files());self.assertEqual((self.reviewer.calls,self.editor.calls),(0,0))

    def test_descriptor_and_suite_failures_have_distinct_reason_codes(self):
        for kind in ('descriptor','suite'):
            job=deepcopy(self.f.job)
            if kind=='descriptor':job['job_id']='bad'
            else:job['contract_suite_version']='unsupported-suite'
            self.fixture.package['job_descriptor']=self.f.save('job_descriptor.json',job);self.fixture.save_package()
            code,packet=self.invoke('vnext-admit',package=True)
            self.assertEqual(code,2)
            self.assertEqual(packet['vnext']['reason_code'],
                             'vnext_descriptor_invalid' if kind=='descriptor' else 'vnext_suite_unsupported')
            self.assertFalse(self.root.exists())

    def test_live_proposal_endpoint_is_unverified_and_reentry_calls_no_clients(self):
        code,packet=self.invoke('live-phase1',package=True)
        self.assertEqual(code,2);self.assertEqual((self.reviewer.calls,self.editor.calls),(1,1))
        self.assertEqual(packet['proposal_status']['processing_gate'],'semantic_verification')
        self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(packet['vnext']['reason_code'],'vnext_gate_unavailable')
        before=self.files();self.review_factory.reset_mock();self.editor_factory.reset_mock()
        self.assertEqual(self.invoke('live-phase1')[1],packet);self.assertEqual(self.files(),before)
        self.review_factory.assert_not_called();self.editor_factory.assert_not_called()

    def test_clean_seed_reentry_and_missing_terminal_recovery_need_no_adapter(self):
        self.reviewer.callback=self.clean
        code,packet=self.invoke('live-phase1',package=True)
        self.assertEqual((code,self.reviewer.calls,self.editor.calls),(0,1,0))
        self.review_factory.reset_mock();self.editor_factory.reset_mock()
        before=self.files();self.assertEqual(self.invoke('live-phase1')[0],0);self.assertEqual(before,self.files())
        report=next((self.root/'rounds/terminal_reports').glob('terminal-*.json'));raw=report.read_bytes();report.unlink()
        before=self.files();code,status=self.invoke('resume','--dry-run')
        self.assertEqual(code,0);self.assertEqual(status['proposal_status']['resume']['next_gate'],'materialization')
        self.assertEqual(before,self.files());self.assertEqual(self.invoke('resume','--continue')[0],0)
        self.assertEqual(report.read_bytes(),raw);self.review_factory.assert_not_called();self.editor_factory.assert_not_called()

    def test_proposal_terminal_recovery_reuses_evidence_without_adapter(self):
        self.invoke('live-phase1',package=True)
        report=next((self.root/'rounds/terminal_reports').glob('terminal-*.json'));raw=report.read_bytes();report.unlink()
        self.review_factory.reset_mock();self.editor_factory.reset_mock();before=self.files()
        self.assertEqual(self.invoke('status')[1]['proposal_status']['resume']['next_gate'],'materialization')
        self.assertEqual(before,self.files());self.assertEqual(self.invoke('resume','--continue')[0],2)
        self.assertEqual(report.read_bytes(),raw);self.review_factory.assert_not_called();self.editor_factory.assert_not_called()

    def test_timeout_requires_explicit_continuation_and_keeps_attempt_budget(self):
        def timeout(packet):raise TimeoutError('fictional CLI timeout')
        self.reviewer.callback=timeout
        code,packet=self.invoke('live-phase1',package=True)
        self.assertEqual(code,2);self.assertEqual(packet['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        self.assertEqual(self.reviewer.calls,1);before=self.files()
        self.assertEqual(self.invoke('live-phase1')[1]['vnext']['next_action'],'resume')
        self.assertEqual(self.invoke('resume')[0],2);self.assertEqual(self.invoke('resume','--dry-run')[0],0)
        self.assertEqual(before,self.files());self.assertEqual(self.reviewer.calls,1)
        self.reviewer.callback=self.clean;self.reviewer.timeout=10
        self.assertEqual(self.invoke('resume','--continue','--reviewer-timeout-seconds','10')[0],0)
        self.assertEqual(self.reviewer.calls,2);self.assertEqual(self.invoke('resume','--continue')[0],2)
        self.assertEqual(self.reviewer.calls,2)

    def test_sensitive_finding_reports_waiting_without_editor_or_fabricated_decision(self):
        def unsafe(packet):packet['classifications'][0]['requested_effects']=['weaken'];return canonical_json_bytes(packet)
        self.reviewer.callback=unsafe
        code,packet=self.invoke('live-phase1',package=True)
        self.assertEqual(code,2);self.assertIsNone(packet['terminal_state'])
        self.assertEqual(packet['vnext']['next_action'],'inspect_findings')
        self.assertEqual(packet['proposal_status']['processing_gate'],'finding_admission')
        self.assertEqual((self.reviewer.calls,self.editor.calls),(1,0));before=self.files()
        self.invoke('live-phase1');self.assertEqual(before,self.files())
        self.assertFalse((self.root/'rounds/round-1/proposal_input.json').exists())

    def test_corrupt_stored_input_halts_without_legacy_fallback_or_clients(self):
        self.invoke('vnext-admit',package=True)
        path=self.root/self.fixture.constraint_ref['path'];path.write_bytes(path.read_bytes()+b' ')
        before=self.files();code,packet=self.invoke('live-phase1')
        self.assertEqual((code,packet['terminal_state']),(2,'HALTED_ARTIFACT_INVALID'))
        self.assertEqual(packet['vnext']['reason_code'],'vnext_lineage_invalid')
        self.assertEqual(before,self.files());self.assertEqual((self.reviewer.calls,self.editor.calls),(0,0))

    def test_native_scripted_clients_complete_cli_journey_and_replay(self):
        from whetstone.vnext_native_editor import NativePatchProposalClient
        from whetstone.vnext_native_reviewer import NativeProposalReviewerClient
        f=self.f
        for role in ('reviewer','editor'):
            f.original.review[role]={'name':'codex','version':'scripted-1','model':'scripted-model'}
        f.original.review_ref=f.save(f.original.review_ref['path'],f.original.review)
        f.job['review_configuration_hash']=f.original.review_ref['hash'];f.rebind()
        self.fixture.package.update(job_descriptor=f.job_ref,review_configuration=f.original.review_ref)
        self.fixture.package['mutation_constraints']=f.save(self.fixture.constraint_ref['path'],
            {'schema_version':'vnext-mutation-constraints-v1','constraints':f.constraints})
        self.fixture.save_package();template=json.dumps({'feedback':f.feedback,'hint':f.hint})
        commands={}
        for role in ('reviewer','editor'):
            command=self.root.parent/('cli-scripted-'+role);counter=command.with_suffix('.count')
            command.write_text(f'''#!{sys.executable}
import json,sys
from pathlib import Path
sys.path[:0]=[{str(Path('src').resolve())!r},{str(Path('tests').resolve())!r}]
prompt=sys.stdin.read();packet=json.loads(prompt.splitlines()[-1])
counter=Path({str(counter)!r});counter.write_text(str(int(counter.read_text())+1 if counter.exists() else 1))
if {role!r}=='reviewer':
    template=json.loads({template!r});feedback=template['feedback']
    feedback.update(round_number=packet['round_number'],profile=packet['profile'],reviewer=packet['review']['reviewer'])
    response={{'schema_version':'vnext-review-response-v1','feedback':feedback,'classifications':[template['hint']]}}
else:
    from test_vnext_unit_preflight import Client
    response=json.loads(Client().propose(prompt));response['patch']['editor']=packet['editor']
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_bytes(json.dumps(response).encode())
print('tokens used\\n23')
''');command.chmod(0o700);commands[role]={'command':str(command)}
        self.config.write_text(json.dumps({'clients':commands,'timeouts':{'reviewer_seconds':10,'editor_seconds':10}}))
        with patch.object(routing,'NativeProposalReviewerClient',NativeProposalReviewerClient), \
             patch.object(routing,'NativePatchProposalClient',NativePatchProposalClient):
            code,packet=self.invoke('live-phase1',package=True)
            self.assertEqual(code,2,packet)
            self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
            before=self.files();self.assertEqual(self.invoke('live-phase1')[1],packet);self.assertEqual(before,self.files())
        self.assertEqual((self.root.parent/'cli-scripted-reviewer.count').read_text(),'1')
        self.assertEqual((self.root.parent/'cli-scripted-editor.count').read_text(),'1')
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),
                         (self.root/'rounds/verified_history/current-verified-0.json').read_bytes())

    def test_original_descriptor_only_proposal_selection_keeps_mode_unavailable_diagnostic(self):
        import test_vnext_admission as admission_tests
        from whetstone.vnext_contracts import derive_job_id
        f=admission_tests.AdmissionTests();f.setUp();self.addCleanup(f.doCleanups)
        job=deepcopy(f.bundle.job);job['editing_mode']='proposal_only';job['job_id']=derive_job_id(job,f.suite.digest)
        raw=canonical_json_bytes(job);(f.root/'job_descriptor.json').write_bytes(raw)
        config=deepcopy(f.config);config['vnext']['job_descriptor']['hash']=sha256_bytes(raw)
        self.root=f.root;self.config.write_text(json.dumps(config));before=self.files()
        code,packet=self.invoke('vnext-admit','--dry-run')
        self.assertEqual((code,packet['vnext']['reason_code']),(2,'vnext_mode_unavailable'))
        self.assertEqual(packet['vnext']['requested_mode'],'proposal_only');self.assertEqual(before,self.files())


if __name__=='__main__':unittest.main()
