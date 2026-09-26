"""Final-review residuals must be documented without granting edits or extra passes."""
from copy import deepcopy
import json
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_closeout as closeout
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_phase2_closeout import MIRROR, STATE_FIELD
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_findings import _route
from whetstone.oscillation import canonicalize_phase2_feedback


class FinalFindingRouteTests(unittest.TestCase):
    def row(self,**changes):
        row=dict(issue_id='iss_'+'1'*16,issue_fingerprint='1'*64,feedback_id='fb_1',
            normalized_severity='minor',authority_impact=None,determinism_impact=None,rubric_impact=None,
            invariant_violated=None,affected_sections=['convergence_declaration.md'],
            oscillation_key=dict(section_id='convergence_declaration.md',concern_type='precision_gap',direction='clarify',scope='local'))
        row.update(changes)
        return canonicalize_phase2_feedback({'feedback':[row]},['convergence_declaration.md'])['feedback'][0]

    def state(self,reviews):
        owner=SimpleNamespace(binding=SimpleNamespace(configuration={'profiles':[{'name':'convergence_strict_check'},{'name':'adversarial'}]}))
        return dict(clean=['convergence_strict_check','adversarial'],frames=[dict(owner=owner,
            bound=SimpleNamespace(request={'round_number':i}),review={'feedback':{'feedback':rows}})
            for i,rows in enumerate(reviews,1)])

    def test_nonblocking_severity_does_not_override_authority_rubric_or_profile_gates(self):
        for field,route in [('authority_impact','authority_resolution_required'),
                            ('determinism_impact','authority_resolution_required'),
                            ('invariant_violated','authority_resolution_required'),
                            ('rubric_impact','rubric_resolution_required')]:
            row=self.row(**{field:'minor'})
            self.assertEqual(_route(self.state([[row]]),[row])[0],route)
        row=self.row(affected_sections=['rubric_gaps.json'])
        self.assertEqual(_route(self.state([[row]]),[row])[0],'rubric_resolution_required')
        row=self.row();state=self.state([[row]]);state['clean']=[]
        self.assertEqual(_route(state,[row]),['profile_verification_required'])

    def test_declaration_claim_is_not_repair_and_mixed_serious_source_takes_precedence(self):
        row=self.row(normalized_severity='major',issue_type='declaration_hash_mismatch')
        self.assertEqual(_route(self.state([[row]]),[row]),['declaration_revision_required'])
        source=self.row(normalized_severity='blocker',affected_sections=['spec.md'],in_scope=False)
        self.assertEqual(_route(self.state([[row,source]]),[row,source]),['source_revision_required'])

    def test_nonblocking_final_review_cannot_hide_observed_feedback_oscillation(self):
        first=self.row(oscillation_key=dict(section_id='convergence_declaration.md',concern_type='precision_gap',direction='add',scope='local'))
        final=self.row(oscillation_key=dict(section_id='convergence_declaration.md',concern_type='precision_gap',direction='remove',scope='local'))
        self.assertEqual(_route(self.state([[first],[final]]),[final]),['oscillation_resolution_required'])


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class FinalFindingsTests(unittest.TestCase):
    setUpClass=closeout.Phase2CloseoutTests.setUpClass
    fixture=closeout.Phase2CloseoutTests.fixture
    files=closeout.Phase2CloseoutTests.files
    reopen=closeout.Phase2CloseoutTests.reopen
    ready=closeout.Phase2CloseoutTests.ready
    review=closeout.Phase2CloseoutTests.review
    config=closeout.Phase2CloseoutTests.config
    next_client=closeout.Phase2CloseoutTests.next_client
    advance=closeout.Phase2CloseoutTests.advance
    clean_start=closeout.Phase2CloseoutTests.clean_start
    final_ready=closeout.Phase2CloseoutTests.final_ready
    lose=staticmethod(closeout.Phase2CloseoutTests.lose)

    def start(self,**kwargs):
        kwargs['phase2_findings_contract']=True
        return closeout.Phase2CloseoutTests.start(self,**kwargs)

    @staticmethod
    def residuals(client,packet):
        row=packet['feedback'][0]
        row.update(normalized_severity='minor',baseline_severity='minor',authority_impact=None,
                   determinism_impact=None,rubric_impact=None,invariant_violated=None,
                   affected_sections=['convergence_declaration.md'])
        row['oscillation_key']['section_id']='convergence_declaration.md'
        return canonical_json_bytes(packet)

    def consumed(self,callback=None):
        f,reviewer,client,package=self.final_ready()
        client.callback=callback or self.residuals
        bound,result,consumed=self.advance(f,client)
        return f,reviewer,client,package,bound,result,consumed

    def test_minor_and_nit_residuals_close_only_after_reconciliation_and_state_recovery(self):
        def response(client,packet):
            packet=json.loads(self.residuals(client,packet))
            row=deepcopy(packet['feedback'][0]);row.update(feedback_id='fb_final_nit',baseline_severity='nit',
                normalized_severity='nit',claim='Retain this optional wording suggestion.',in_scope=False)
            row['affected_sections']=['spec.md']
            row['oscillation_key']['section_id']=json.loads(client.prompts[-1].splitlines()[-1])['base_map']['sections'][0]['canonical_section_id']
            packet['feedback'].append(row)
            return canonical_json_bytes(packet)
        f,reviewer,client,package,bound,result,consumed=self.consumed(response)
        before=self.files(f);pointer=f.store.read('rounds/current_verified.json');draft=f.store.read('spec.md')
        with patch.object(f.store,'locked',side_effect=AssertionError('read took fence')):
            preview=f.run.phase2_final_findings()
        self.assertEqual(preview['packet']['route'],'closeout_eligible')
        self.assertFalse(preview['committed']);self.assertEqual(self.files(f),before)
        with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
        reconciled=f.run.reconcile_phase2_findings()
        self.assertTrue(reconciled['committed']);self.assertFalse(reconciled['phase_complete'])
        self.assertEqual(reconciled['packet']['remaining_step_budget'],2)
        residual=json.loads(f.store.read(reconciled['packet']['unresolved_issues']['path']))['unresolved_issues']
        self.assertEqual({r['normalized_severity'] for r in residual},{'minor','nit'})
        self.assertTrue(all(not r['blocking_acceptance'] for r in residual))
        self.assertEqual(f.store.read(package['declaration']['unresolved_issues']['path']),
                         before[package['declaration']['unresolved_issues']['path']])
        finished=f.run.finish_phase2()
        self.assertEqual(finished['packet']['schema_version'],'vnext-phase2-closeout-v2')
        self.assertEqual(finished['packet']['finding_reconciliation'],reconciled['reference'])
        self.assertEqual(finished['packet']['unresolved_issues'],reconciled['packet']['unresolved_issues'])
        self.assertFalse(finished['phase_complete'])
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual(f.store.read('rounds/current_verified.json'),pointer)
        self.assertEqual(f.store.read('spec.md'),draft)
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))
        after=self.files(f);self.reopen(f)
        self.assertEqual(f.run.reconcile_phase2_findings(),reconciled)
        self.assertTrue(f.run.phase2_closeout()['phase_complete'])
        self.assertEqual(self.files(f),after)
        script="""import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path=sys.argv[1:];manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(dict(findings=run.phase2_final_findings(),closeout=run.phase2_closeout())))
"""
        child=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path)],capture_output=True,timeout=180)
        self.assertEqual(child.returncode,0,child.stderr.decode())
        response=json.loads(child.stdout)
        self.assertTrue(response['closeout']['phase_complete'])
        self.assertEqual(response['findings'],json.loads(json.dumps(reconciled)))
        self.assertEqual(self.files(f),after)

    def test_serious_hash_claim_and_mixed_source_findings_remain_blocked(self):
        def response(client,packet):
            packet=json.loads(self.residuals(client,packet));row=packet['feedback'][0]
            row.update(normalized_severity='major',baseline_severity='major',issue_type='declaration_hash_mismatch',
                       claim='The declaration hash is wrong.')
            other=deepcopy(row);other.update(feedback_id='fb_source',claim='A source requirement remains incomplete.',
                affected_sections=['spec.md'],in_scope=False)
            packet['feedback'].append(other)
            return canonical_json_bytes(packet)
        f,reviewer,client,_,_,_,_=self.consumed(response)
        original=self.files(f)
        view=f.run.reconcile_phase2_findings()
        self.assertEqual(view['packet']['route'],'source_revision_required')
        self.assertEqual(view['packet']['repaired_issue_ids'],[])
        self.assertEqual(len(view['packet']['residual_issue_ids']),2)
        self.assertEqual(view['packet']['remaining_step_budget'],2)
        self.assertFalse(view['packet']['next_review_authorized'])
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
        with self.assertRaisesRegex(ValueError,'read-only'):f.run.continue_phase2_pass(3,action='admit')
        self.assertEqual(f.run.bind_phase2_next_review(client.transport_binding)['gate'],'declaration_closeout_required')
        self.assertEqual(self.files(f),before)
        self.assertTrue(all(before[p]==raw for p,raw in original.items()))
        self.assertFalse((f.root/MIRROR).exists())

    def test_reconciliation_and_closeout_lost_writes_repeat_exact_barriers(self):
        f,reviewer,client,_,_,_,_=self.consumed()
        for suffix in ('/unresolved_issues.json','/commit.json'):
            with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,suffix)):
                with self.assertRaises(OSError):f.run.reconcile_phase2_findings()
            self.reopen(f)
        receipt=f.run.reconcile_phase2_findings()
        sync=f.store.synchronize_existing
        def fail(token,path,**kwargs):
            if path==receipt['reference']['path']:raise OSError('reconciliation barrier')
            return sync(token,path,**kwargs)
        with patch.object(f.store,'synchronize_existing',side_effect=fail):
            with self.assertRaisesRegex(OSError,'reconciliation barrier'):f.run.finish_phase2()
        with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,'/commit.json')):
            with self.assertRaises(OSError):f.run.finish_phase2()
        self.reopen(f)
        materialize=f.store.materialize
        def lost_state(token,path,raw,**kwargs):
            result=materialize(token,path,raw,**kwargs)
            if path==STATE_PATH:raise OSError('state acknowledgement')
            return result
        with patch.object(f.store,'materialize',side_effect=lost_state):
            with self.assertRaisesRegex(OSError,'state acknowledgement'):f.run.reconcile_phase2_state()
        self.reopen(f)
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))
        self.assertFalse((f.root/'rounds/phase2/review_requests/pass-4').exists())

    def test_sources_caches_and_committed_dependencies_cannot_be_substituted(self):
        f,reviewer,client,package,bound,_,_=self.consumed()
        preview=f.run.phase2_final_findings();sync=f.store.synchronize_existing
        def drift(token,path,**kwargs):
            result=sync(token,path,**kwargs)
            if path==bound.request_ref['path']:
                (f.root/package['declaration']['declaration']['path']).write_text('tampered')
            return result
        declaration=f.root/package['declaration']['declaration']['path'];raw=declaration.read_bytes()
        with patch.object(f.store,'synchronize_existing',side_effect=drift):
            with self.assertRaises(ValueError):f.run.reconcile_phase2_findings()
        self.assertFalse((f.root/preview['reference']['path']).exists());declaration.write_bytes(raw)
        receipt=f.run.reconcile_phase2_findings()
        for ref in (receipt['packet']['feedback'],receipt['packet']['unresolved_issues'],receipt['reference']):
            path=f.root/ref['path'];raw=path.read_bytes();path.write_bytes(raw+b' ')
            before=self.files(f)
            with self.assertRaises(ValueError):f.run.finish_phase2()
            self.assertEqual(self.files(f),before);path.write_bytes(raw)
        path=f.root/receipt['packet']['unresolved_issues']['path'];raw=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(ValueError,'lacks dependencies'):f.run.reconcile_phase2_findings()
        path.write_bytes(raw)
        state=json.loads(f.store.read(STATE_PATH));state[STATE_FIELD]={'path':'fake','hash':'0'*64}
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        self.assertFalse(f.run.phase2_closeout()['committed'])
        self.assertEqual(client.calls,2)

    def test_empty_review_still_requires_new_pin_receipt_and_old_suite_refuses(self):
        f,reviewer,client,package,bound,result,consumed=self.consumed(lambda c,p:canonical_json_bytes({**p,'feedback':[]}))
        with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
        receipt=f.run.reconcile_phase2_findings()
        self.assertEqual(receipt['packet']['residual_issue_ids'],[])
        self.assertTrue(f.run.finish_phase2()['committed'])
        with patch.object(self,'start',side_effect=lambda **kw:closeout.Phase2CloseoutTests.start(self,**kw)):
            old,_,_,_=self.final_ready()
        before=self.files(old)
        for method in (old.run.phase2_final_findings,old.run.reconcile_phase2_findings):
            with self.assertRaisesRegex(ValueError,'outside supported suite'):method()
        self.assertEqual(self.files(old),before)
