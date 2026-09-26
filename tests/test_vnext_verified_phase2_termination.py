"""Final-step terminal journeys, precedence guards and publication recovery."""
from copy import deepcopy
import json
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_blocked as blocked
import test_vnext_verified_phase2_closeout as closeout
import test_vnext_verified_phase2_findings as findings
from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_closeout import STATE_FIELD, MIRROR as DECLARATION_MIRROR
from whetstone.vnext_verified_phase2_termination import MIRROR
from whetstone.vnext_verified_phase2_review import INPUT_PATH
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class FinalTerminationTests(unittest.TestCase):
    setUpClass=blocked.BlockedReportTests.setUpClass
    fixture=blocked.BlockedReportTests.fixture
    files=blocked.BlockedReportTests.files
    reopen=blocked.BlockedReportTests.reopen
    ready=blocked.BlockedReportTests.ready
    review=blocked.BlockedReportTests.review
    next_client=blocked.BlockedReportTests.next_client
    advance=blocked.BlockedReportTests.advance
    clean_start=blocked.BlockedReportTests.clean_start
    final_ready=blocked.BlockedReportTests.final_ready
    consumed=blocked.BlockedReportTests.consumed
    residuals=staticmethod(blocked.BlockedReportTests.residuals)
    serious=staticmethod(blocked.BlockedReportTests.serious)
    lose=staticmethod(closeout.Phase2CloseoutTests.lose)
    final_budget=1
    advice=closeout.Phase2CloseoutTests.advice
    candidate=closeout.Phase2CloseoutTests.candidate

    def start(self,**kwargs):
        return findings.FinalFindingsTests.start(self,phase2_termination_contract=True,**kwargs)

    def config(self,f):
        config=blocked.BlockedReportTests.config(self,f)
        config['profiles'][-1]['budget']=self.final_budget
        return config

    def failure(self,callback=None):
        data=self.consumed(callback or self.serious)
        data[0].run.reconcile_phase2_findings()
        return data

    def child(self,f,*,recover=False):
        script="""import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path,recover=sys.argv[1:];manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(run.reconcile_phase2_state() if recover=='yes' else run.phase2_closeout()))
"""
        child=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path),'yes' if recover else 'no'],
                             capture_output=True,timeout=180)
        self.assertEqual(child.returncode,0,child.stderr.decode())
        return json.loads(child.stdout)

    def test_exhaustion_publishes_full_failure_and_recovers_without_acceptance(self):
        f,reviewer,client,package,bound,_,_=self.failure()
        before=self.files(f);draft=f.store.read('spec.md');pointer=f.store.read('rounds/current_verified.json')
        with patch.object(f.store,'locked',side_effect=AssertionError('status took fence')):
            preview=f.run.phase2_closeout()
        self.assertEqual(preview['gate'],'failure_report_publication_required')
        self.assertEqual(preview['remaining_step_budget'],0)
        self.assertFalse(preview['committed']);self.assertNotIn('packet',preview)
        self.assertEqual(self.files(f),before)
        finished=f.run.finish_phase2()
        self.assertTrue(finished['committed']);self.assertFalse(finished['phase_complete'])
        self.assertFalse(finished['halt_complete'])
        packet=finished['packet']
        self.assertEqual((packet['terminal_state'],packet['accepted']),('TARGET_NOT_REACHED',False))
        report=json.loads(f.store.read(packet['failure_report']['path']))
        self.assertEqual(report['reviewer_final_status'],'rejected')
        self.assertEqual(report['final_declaration_path'],package['declaration']['declaration']['path'])
        self.assertEqual(report['last_accepted_draft_hash'],draft_hash(draft.decode()))
        self.assertEqual(len(report['unresolved_major_issues']),1)
        self.assertEqual(report['profile_status']['unverified_profiles'],['convergence_strict_check'])
        self.assertEqual(report['profile_status']['exhausted_profiles'],['convergence_strict_check'])
        self.assertEqual([r['rounds_used'] for r in report['profile_status']['profiles']],[1,1,1])
        self.assertEqual(report['recommendation'],'manual_review_required')
        terminal=json.loads(f.store.read(packet['terminal_report']['path']))
        self.assertFalse(terminal['resume']['permitted']);self.assertFalse(terminal['apply_back_permitted'])
        self.assertFalse((f.root/MIRROR).exists());self.assertFalse((f.root/DECLARATION_MIRROR).exists())
        recovered=f.run.reconcile_phase2_state()
        self.assertTrue(recovered['halt_complete']);self.assertFalse(recovered['phase_complete'])
        self.assertEqual(f.store.read(MIRROR),f.store.read(packet['failure_report']['path']))
        self.assertEqual(json.loads(f.store.read(STATE_PATH))[STATE_FIELD],finished['reference'])
        self.assertEqual(f.store.read(package['declaration']['declaration']['path']),before[package['declaration']['declaration']['path']])
        after=self.files(f)
        self.assertTrue(self.child(f)['halt_complete'])
        self.assertTrue(f.run.finish_phase2()['halt_complete'])
        self.assertTrue(f.run.reconcile_phase2_state()['halt_complete'])
        self.assertEqual(f.run.bind_phase2_next_review(client.transport_binding)['gate'],'declaration_closeout_required')
        self.assertEqual(self.files(f),after)
        self.assertEqual((f.store.read('spec.md'),f.store.read('rounds/current_verified.json')),(draft,pointer))
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))

    def test_last_reviewer_summary_filters_ids_without_dropping_preserved_findings(self):
        expected=[]
        def response(client,packet):
            packet=json.loads(self.serious(client,packet))
            expected.append(packet['feedback'][0]['feedback_id'])
            minor=deepcopy(packet['feedback'][0])
            minor.update(feedback_id='fb_minor',normalized_severity='minor',baseline_severity='minor',
                         claim='Optional declaration wording clarification.')
            minor['oscillation_key']['concern_type']='clarity_gap'
            outside=deepcopy(packet['feedback'][0])
            outside.update(feedback_id='fb_outside',in_scope=False,
                           claim='A separate out-of-scope declaration concern.')
            outside['oscillation_key']['concern_type']='scope_violation'
            packet['feedback'].extend([minor,outside])
            return canonical_json_bytes(packet)
        f,*_=self.failure(response)
        self.assertNotIn('oscillation_resolution_required',f.run.phase2_final_findings()['packet']['blocking_reasons'])
        finished=f.run.finish_phase2()
        report=json.loads(f.store.read(finished['packet']['failure_report']['path']))
        summary=report['last_reviewer_findings']
        self.assertEqual(summary['feedback_ids'],expected)
        self.assertEqual((summary['blocker_count'],summary['major_count']),(0,1))
        residual=json.loads(f.store.read(finished['packet']['unresolved_issues']['path']))['unresolved_issues']
        self.assertEqual(len(residual),3)
        self.assertEqual(len(report['unresolved_major_issues']),2)
        self.assertTrue(f.run.reconcile_phase2_state()['halt_complete'])
        self.assertEqual(json.loads(f.store.read(MIRROR)),report)
        self.assertTrue(self.child(f)['halt_complete'])

    def test_clean_last_budgeted_review_keeps_convergence(self):
        f,reviewer,client,_,_,_,_=self.failure(lambda c,p:canonical_json_bytes({**p,'feedback':[]}))
        finished=f.run.finish_phase2()
        self.assertEqual(finished['packet']['terminal_state'],'CONVERGED')
        self.assertEqual(finished['packet']['schema_version'],'vnext-phase2-closeout-v2')
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertFalse((f.root/MIRROR).exists())
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))

    def test_failure_after_verified_phase2_promotion_binds_current_draft_and_prior_acceptance(self):
        f,reviewer,client=self.clean_start()
        accepted_hash=draft_hash(f.store.read('spec.md').decode())
        old=f.run.prepare_phase2_declaration()
        old_raw=f.store.read(old['declaration']['declaration']['path'])
        client=self.next_client(reviewer,clean=False)
        bound,result,_=self.advance(f,client)
        f.run.continue_phase2_pass(2,action='advice',advice=self.advice(bound,result))
        f.run.continue_phase2_pass(2,action='admit')
        _,verifier=self.candidate(f,bound.request['round_number'])
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        client=self.next_client(reviewer);self.advance(f,client)
        package=f.run.prepare_phase2_declaration()
        def response(c,p):
            packet=json.loads(self.serious(c,p))
            packet['draft_hash']=sha256_bytes(json.loads(c.prompts[-1].splitlines()[-1])['draft'].encode())
            return canonical_json_bytes(packet)
        client.callback=response;self.advance(f,client);f.run.reconcile_phase2_findings()
        finished=f.run.finish_phase2()
        report=json.loads(f.store.read(finished['packet']['failure_report']['path']))
        pointer=json.loads(f.store.read('rounds/current_verified.json'))
        self.assertEqual(report['final_draft_path'],pointer['verified_draft_path'])
        self.assertEqual(report['last_accepted_draft_hash'],accepted_hash)
        self.assertNotEqual(report['last_draft_hash'],accepted_hash)
        self.assertEqual(report['last_draft_hash'],draft_hash(f.store.read('spec.md').decode()))
        self.assertEqual(report['final_declaration_path'],package['declaration']['declaration']['path'])
        terminal=json.loads(f.store.read(finished['packet']['terminal_report']['path']))
        self.assertEqual(terminal['latest_candidate']['candidate_id'],pointer['source_candidate_id'])
        self.assertTrue(f.run.reconcile_phase2_state()['halt_complete'])
        self.assertEqual(f.store.read(old['declaration']['declaration']['path']),old_raw)
        self.assertEqual((f.editor.calls,verifier.calls),(1,1))

    def test_unused_budget_and_higher_resolution_gates_cannot_publish_exhaustion(self):
        self.final_budget=3
        f,*_=self.failure()
        before=self.files(f)
        self.assertEqual(f.run.phase2_closeout()['gate'],'declaration_reconciliation_required')
        with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
        self.assertEqual(self.files(f),before)
        self.final_budget=1
        for field,route in (('authority_impact','authority_resolution_required'),('rubric_impact','rubric_resolution_required')):
            def response(c,p,field=field):
                packet=json.loads(self.serious(c,p));packet['feedback'][0][field]='major'
                return canonical_json_bytes(packet)
            with self.subTest(field=field):
                f,*_=self.failure(response);before=self.files(f)
                self.assertIn(route,f.run.phase2_closeout()['blockers'])
                with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
                self.assertEqual(self.files(f),before)

    def test_observed_oscillation_does_not_get_hidden_by_exhaustion(self):
        f,reviewer,_=self.ready()
        def response(c,p,*,final=False):
            packet=json.loads(self.serious(c,p) if final else self.residuals(c,p))
            row=packet['feedback'][0]
            inputs=json.loads(c.prompts[-1].splitlines()[-1])
            row['affected_sections']=[inputs['base_map']['sections'][0]['canonical_section_id']]
            row.update(claim='Clarify queue wording.',recommended_change='Clarify the wording.')
            row['oscillation_key'].update(section_id=row['affected_sections'][0],
                                           direction='remove' if final else 'add')
            return canonical_json_bytes(packet)
        reviewer.callback=response
        result=f.run.run_phase2_review(client=reviewer)
        self.assertEqual(result.status,'complete',result.last_outcome)
        f.run.consume_phase2_result()
        advice=self.advice(SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH))),result)
        for row in advice['findings']:row['classification']='deferable'
        attached=f.run.bind_phase2_advice(advice)
        self.assertTrue(all(r['classification']=='deferable' for r in attached['binding']['findings']))
        client=self.next_client(reviewer);self.advance(f,client)
        f.run.prepare_phase2_declaration();client.callback=lambda c,p:response(c,p,final=True)
        self.advance(f,client);f.run.reconcile_phase2_findings()
        before=self.files(f)
        self.assertIn('oscillation_resolution_required',f.run.phase2_final_findings()['packet']['blocking_reasons'])
        with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
        self.assertEqual(self.files(f),before)

    def test_interrupted_reports_commit_mirror_and_final_state_recover_exactly(self):
        f,reviewer,client,_,_,_,_=self.failure()
        for suffix in ('/convergence_failure_report.json','/terminal_report.json','/commit.json'):
            publish=f.store.publish
            def before_write(token,path,value,suffix=suffix):
                if path.endswith(suffix):raise OSError('before publication')
                return publish(token,path,value)
            with patch.object(f.store,'publish',side_effect=before_write):
                with self.assertRaisesRegex(OSError,'before publication'):f.run.finish_phase2()
            self.reopen(f)
            with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,suffix)):
                with self.assertRaisesRegex(OSError,'lost acknowledgement'):f.run.finish_phase2()
            self.reopen(f)
        committed=f.run.phase2_closeout();report=f.store.read(committed['packet']['failure_report']['path'])
        sync=f.store.synchronize_existing
        def fail(token,path,**kwargs):
            if path==committed['packet']['finding_reconciliation']['path']:raise OSError('source barrier')
            return sync(token,path,**kwargs)
        before=self.files(f)
        with patch.object(f.store,'synchronize_existing',side_effect=fail):
            with self.assertRaisesRegex(OSError,'source barrier'):f.run.reconcile_phase2_state()
        self.assertEqual(self.files(f),before)
        with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,MIRROR)):
            with self.assertRaises(OSError):f.run.reconcile_phase2_state()
        materialize=f.store.materialize
        def lost(token,path,raw,**kwargs):
            result=materialize(token,path,raw,**kwargs)
            if path==STATE_PATH:raise OSError('final state acknowledgement')
            return result
        with patch.object(f.store,'materialize',side_effect=lost):
            with self.assertRaisesRegex(OSError,'final state acknowledgement'):f.run.reconcile_phase2_state()
        self.assertTrue(self.child(f,recover=True)['halt_complete'])
        after=self.files(f)
        with patch.object(f.store,'synchronize_existing',side_effect=fail):
            with self.assertRaisesRegex(OSError,'source barrier'):f.run.reconcile_phase2_state()
        self.assertEqual(self.files(f),after)
        self.assertEqual(f.store.read(MIRROR),report)
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))

    def test_missing_reconciliation_corrupt_sources_and_unowned_mirror_refuse(self):
        f,_,_,package,bound,_,_=self.consumed(self.serious)
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
        self.assertEqual(self.files(f),before)
        receipt=f.run.reconcile_phase2_findings()
        declaration=f.root/package['declaration']['declaration']['path'];raw=declaration.read_bytes()
        sync=f.store.synchronize_existing
        def drift(token,path,**kwargs):
            result=sync(token,path,**kwargs)
            if path==bound.request_ref['path']:declaration.write_bytes(raw+b' ')
            return result
        with patch.object(f.store,'synchronize_existing',side_effect=drift):
            with self.assertRaises(ValueError):f.run.finish_phase2()
        declaration.write_bytes(raw)
        state=json.loads(f.store.read(STATE_PATH));state[STATE_FIELD]={'path':'fake','hash':'0'*64}
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        self.assertFalse(f.run.phase2_closeout()['committed'])
        finished=f.run.finish_phase2()
        for ref in (receipt['reference'],finished['packet']['failure_report'],finished['packet']['terminal_report'],finished['reference']):
            path=f.root/ref['path'];raw=path.read_bytes();path.write_bytes(raw+b' ')
            before=self.files(f)
            with self.assertRaises(ValueError):f.run.reconcile_phase2_state()
            self.assertEqual(self.files(f),before);path.write_bytes(raw)
        path=f.root/finished['packet']['failure_report']['path'];raw=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(ValueError,'lacks report'):f.run.phase2_closeout()
        path.write_bytes(raw)
        (f.root/MIRROR).write_bytes(b'unowned report')
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'conflicts'):f.run.reconcile_phase2_state()
        self.assertEqual(self.files(f),before)

    def test_unpinned_exhausted_final_review_and_pending_result_keep_existing_gates(self):
        f,_,client,_=self.final_ready()
        f.run.bind_phase2_next_review(client.transport_binding)
        before=self.files(f)
        self.assertEqual(f.run.phase2_closeout()['gate'],'declaration_review_not_completed')
        with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
        self.assertEqual(self.files(f),before)
        with patch.object(self,'start',side_effect=lambda **kw:findings.FinalFindingsTests.start(self,**kw)):
            old,*_=self.failure()
        before=self.files(old)
        with self.assertRaisesRegex(ValueError,'no terminal'):old.run.finish_phase2()
        self.assertEqual(self.files(old),before)
