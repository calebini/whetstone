"""Exhaustion maintains a declaration, reports failure and stays stopped."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_run import open_verified_run
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_closeout import STATE_FIELD
import test_vnext_verified_first_review_commands as first


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class TerminalCommandTests(unittest.TestCase):
    setUpClass=first.FirstReviewCommandTests.setUpClass
    setUp=first.FirstReviewCommandTests.setUp
    patch=first.FirstReviewCommandTests.patch
    qualify=first.FirstReviewCommandTests.qualify
    save_config=first.FirstReviewCommandTests.save_config
    clean=staticmethod(first.FirstReviewCommandTests.clean)
    invoke=first.FirstReviewCommandTests.invoke
    files=first.FirstReviewCommandTests.files
    ready=first.FirstReviewCommandTests.ready
    call=first.FirstReviewCommandTests.call
    entered=first.FirstReviewCommandTests.entered
    inspect_readonly=first.FirstReviewCommandTests.inspect_readonly

    def stage_phase2(self):
        first.FirstReviewCommandTests.stage_phase2(self)
        # Publish a distinct configuration before entry; never edit bound inputs.
        with open_verified_run(self.root) as run:
            packet=json.loads(run.store.read(self.config['vnext_phase2_configuration']['path']))
            packet['profiles'][0]['budget']=1
            raw=canonical_json_bytes(packet);path='inputs/phase2/exhaustion-configuration.json'
            with run.store.locked(run._history().validate_authority) as token:run.store.publish(token,path,raw)
        self.config['vnext_phase2_configuration']=dict(path=path,hash=sha256_bytes(raw))
        self.save_config()

    def deferred_major(self,client,packet):
        inputs=json.loads(client.prompts[-1].splitlines()[-1])
        packet['draft_hash']=sha256_bytes(inputs['draft'].encode())
        for row in packet['feedback']:
            row.update(baseline_severity='major',normalized_severity='major',authority_impact=None,
                determinism_impact=None,rubric_impact=None,invariant_violated=None,
                claim='Clarify the waiting description.',recommended_change='Clarify the wording.')
        mutable=next(r for r in inputs['authority']['bindings'] if r['role']=='mutable_target')
        hints=[dict(feedback_id=r['feedback_id'],classification='deferable',
            authority_scope_ids=mutable['authority_scopes'],source_authority_binding_ids=[mutable['binding_id']],
            scope_surface_ids=[],compatibility_change='none',requested_effects=['clarification']) for r in packet['feedback']]
        return canonical_json_bytes(dict(review=packet,rubric_findings=[],classifications=hints))

    def test_exhaustion_repairs_terminal_after_partial_maintenance_and_lost_final_ack(self):
        self.entered()
        def timeout(client,packet):raise TimeoutError('fixture retained Reviewer failure')
        self.phase2_reviewer.callback=timeout
        code,result=self.call('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(result['recovery'],'failure_projection',result)
        code,result=self.call('resume');self.assertEqual(code,0,result)
        self.assertTrue(result['state_current'] and result['mirrors_current'])
        historical={p:raw for p,raw in self.files().items() if '/execution/failures/' in p}
        self.assertTrue(historical)
        old_mirror=(self.root/'rounds/convergence_failure_report.json').read_bytes()
        self.phase2_reviewer.callback=self.deferred_major
        code,result=self.call('resume');self.assertEqual(code,0,result)
        self.assertEqual(result['status'],'complete');self.assertEqual(self.phase2_reviewer.calls,2)

        publish=LocalAuthorityStore.publish;faults=[]
        def interrupted(store,token,path,value):
            result=publish(store,token,path,value)
            if '/halt/declaration/' in path and path.endswith('/unresolved_issues.json'):
                faults.append(path);raise OSError('fixture halt declaration acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'publish',interrupted):code,result=self.call('live-phase2')
        self.assertEqual(code,2,result);self.assertEqual(len(faults),1,result)
        state=self.inspect_readonly()
        self.assertEqual(state['gate'],'declaration_maintenance_required',state)
        self.assertEqual(state['sequence']['gate'] if 'gate' in state['sequence'] else state['closeout']['sequence_gate'],
                         'budget_exhausted')
        self.assertFalse(state['declaration']['committed']);self.assertIsNone(state['recovery'])
        before=self.files()
        for args in [('--dry-run',),()]:
            code,result=self.call('resume',*args);self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before)

        def report_lost(store,token,path,value):
            result=publish(store,token,path,value)
            if '/halt/terminal/' in path and path.endswith('/convergence_failure_report.json'):
                faults.append(path);raise OSError('fixture halt report acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'publish',report_lost):code,result=self.call('live-phase2')
        self.assertEqual(code,2,result);self.assertEqual(len(faults),2,result)
        state=self.inspect_readonly();self.assertEqual(state['recovery'],'closeout_publication',state)
        declaration=state['closeout']['packet']['declaration_binding']
        declaration_raw=(self.root/declaration['path']).read_bytes()
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('inspection took a writer fence')):
            code,result=self.call('resume','--dry-run');self.assertEqual(code,0,result)
            code,result=self.call('live-phase2');self.assertEqual(code,2,result)
            code,result=self.call('resume','--continue');self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before)

        materialize=LocalAuthorityStore.materialize
        def lost_state(store,token,path,raw,**kwargs):
            result=materialize(store,token,path,raw,**kwargs)
            if path==STATE_PATH and json.loads(raw).get(STATE_FIELD):
                faults.append(path);raise OSError('fixture halt state acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'materialize',lost_state):code,result=self.call('resume')
        self.assertEqual(code,2,result);self.assertEqual(faults[-1],STATE_PATH,result)
        state=self.inspect_readonly();self.assertEqual(state['gate'],'phase2_stopped',state)
        self.assertIsNone(state['recovery']);self.assertIsNone(state['continuation'])
        closeout=state['closeout'];self.assertTrue(closeout['halt_complete']);self.assertFalse(closeout['phase_complete'])
        self.assertEqual(closeout['packet']['terminal_state'],'TARGET_NOT_REACHED')
        self.assertFalse(closeout['packet']['apply_back_permitted'])
        report=(self.root/closeout['packet']['failure_report']['path']).read_bytes()
        self.assertEqual((self.root/'rounds/convergence_failure_report.json').read_bytes(),report)
        self.assertNotEqual(report,old_mirror)
        self.assertTrue(json.loads(report)['unresolved_major_issues'])
        before=self.files()
        code,result=self.call('resume');self.assertEqual(code,2,result)
        code,result=self.call('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(result['gate'],'phase2_stopped')
        self.assertEqual(self.files(),before);self.assertEqual(self.phase2_reviewer.calls,2)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),self.head)
        self.assertEqual((self.root/'rounds/phase2/entry.json').read_bytes(),self.entry)
        self.assertEqual((self.root/declaration['path']).read_bytes(),declaration_raw)
        for path,raw in historical.items():self.assertEqual((self.root/path).read_bytes(),raw)


if __name__=='__main__':unittest.main()
