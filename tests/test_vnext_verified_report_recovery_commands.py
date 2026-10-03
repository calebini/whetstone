"""Correction failure and signal recovery stop at their selected report outcome."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_correction_failure import ROOT as CORRECTION_ROOT, STATE_FIELD as CORRECTION_FIELD
from whetstone.vnext_verified_phase2_signals import ROOT as SIGNAL_ROOT
import test_vnext_verified_first_review_commands as first


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class ReportRecoveryCommandTests(unittest.TestCase):
    setUpClass=first.FirstReviewCommandTests.setUpClass
    setUp=first.FirstReviewCommandTests.setUp
    patch=first.FirstReviewCommandTests.patch
    qualify=first.FirstReviewCommandTests.qualify
    save_config=first.FirstReviewCommandTests.save_config
    clean=staticmethod(first.FirstReviewCommandTests.clean)
    invoke=first.FirstReviewCommandTests.invoke
    files=first.FirstReviewCommandTests.files
    stage_phase2=first.FirstReviewCommandTests.stage_phase2
    ready=first.FirstReviewCommandTests.ready
    call=first.FirstReviewCommandTests.call
    inspect_readonly=first.FirstReviewCommandTests.inspect_readonly

    def entered(self):
        self.ready()
        self.patch('whetstone.live_phase2.LivePhase2Runner',side_effect=AssertionError('legacy executor'))
        code,result=self.call('promote-phase2');self.assertEqual(code,0,result)
        self.head=(self.root/'rounds/current_verified.json').read_bytes()
        self.entry=(self.root/'rounds/phase2/entry.json').read_bytes()

    def pending(self,family):
        state=self.inspect_readonly()
        self.assertEqual(state['recovery'],family+'_publication',state)
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('inspection took a writer fence')):
            code,result=self.call('resume','--dry-run');self.assertEqual(code,0,result)
            code,result=self.call('live-phase2');self.assertEqual(code,2,result)
            code,result=self.call('resume','--continue');self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before)

    def unchanged_authority(self):
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),self.head)
        self.assertEqual((self.root/'rounds/phase2/entry.json').read_bytes(),self.entry)

    def test_correction_failure_repair_lost_final_ack_cannot_retry_editor(self):
        from test_vnext_proposal_requests import Client as Editor
        self.entered()
        def timeout(packet):raise TimeoutError('fixture Editor timeout')
        editor=Editor(timeout)
        self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=editor)
        publish=LocalAuthorityStore.publish;faults=[]
        def lost(store,token,path,value):
            result=publish(store,token,path,value)
            if path.startswith(CORRECTION_ROOT+'/') and path.endswith('/terminal.json'):
                faults.append(path);raise OSError('fixture correction report acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'publish',lost):code,result=self.call('live-phase2')
        self.assertEqual(code,2,result);self.assertEqual(len(faults),1,result)
        self.assertEqual((self.phase2_reviewer.calls,editor.calls),(1,1))
        self.pending('correction_failure')
        materialize=LocalAuthorityStore.materialize
        def lost_state(store,token,path,raw,**kwargs):
            result=materialize(store,token,path,raw,**kwargs)
            if path==STATE_PATH and json.loads(raw).get(CORRECTION_FIELD,{}).get('active'):
                faults.append(path);raise OSError('fixture correction state acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'materialize',lost_state):code,result=self.call('resume')
        self.assertEqual(code,2,result);self.assertEqual(faults[-1],STATE_PATH,result)
        state=self.inspect_readonly()
        self.assertIsNone(state['recovery'],state)
        self.assertEqual(state['continuation'],'unsupported_phase2_continuation',state)
        projection=json.loads((self.root/STATE_PATH).read_bytes())[CORRECTION_FIELD]
        self.assertEqual(len(projection['history']),1)
        before=self.files()
        code,result=self.call('resume');self.assertEqual(code,2,result)
        code,result=self.call('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before)
        self.assertEqual((self.phase2_reviewer.calls,editor.calls),(1,1))
        self.unchanged_authority()

    def test_signal_publication_repairs_and_stops_at_conflict_without_clients(self):
        self.entered()
        def response(client,packet):
            inputs=json.loads(client.prompts[-1].splitlines()[-1])
            packet['draft_hash']=sha256_bytes(inputs['draft'].encode())
            direction,severity=('constrain','minor') if client.calls==1 else ('relax','blocker')
            self.assertLessEqual(client.calls,2,'report recovery invoked another Reviewer')
            row=packet['feedback'][0]
            row.update(baseline_severity=severity,normalized_severity=severity,authority_impact=None,
                determinism_impact=None,rubric_impact=None,invariant_violated=None,
                claim=f'Clarify the waiting description: {direction}, {severity}.',recommended_change='Clarify the wording.')
            row['oscillation_key']['direction']=direction
            mutable=next(r for r in inputs['authority']['bindings'] if r['role']=='mutable_target')
            hints=[dict(feedback_id=r['feedback_id'],classification='deferable',
                authority_scope_ids=mutable['authority_scopes'],source_authority_binding_ids=[mutable['binding_id']],
                scope_surface_ids=[],compatibility_change='none',requested_effects=['clarification']) for r in packet['feedback']]
            return canonical_json_bytes(dict(review=packet,rubric_findings=[],classifications=hints))
        self.phase2_reviewer.callback=response
        publish=LocalAuthorityStore.publish;faults=[]
        def lost(store,token,path,value):
            result=publish(store,token,path,value)
            if path.startswith(SIGNAL_ROOT+'/') and path.endswith('/conflict.json'):
                faults.append(path);raise OSError('fixture signal report acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'publish',lost):code,result=self.call('live-phase2')
        self.assertEqual(code,2,result);self.assertEqual(len(faults),1,result)
        self.assertEqual(self.phase2_reviewer.calls,2)
        self.pending('signal')
        retained={str(p.relative_to(self.root)):p.read_bytes() for p in (self.root/SIGNAL_ROOT).rglob('*.json')}
        code,result=self.call('resume');self.assertEqual(code,0,result)
        self.assertEqual(result['gate'],'signal_state_recovered',result)
        self.assertEqual(result['terminal_state'],'HALTED_CONFLICT',result)
        self.assertTrue(result['state_current'] and result['mirrors_current'],result)
        self.assertFalse(result['resume_permitted']);self.assertFalse(result['phase_complete'])
        state=self.inspect_readonly()
        self.assertIsNone(state['recovery']);self.assertIsNone(state['continuation'])
        self.assertEqual(state['gate'],'conflict_halt_required',state)
        before=self.files()
        code,result=self.call('resume');self.assertEqual(code,2,result)
        code,result=self.call('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before);self.assertEqual(self.phase2_reviewer.calls,2)
        for path,raw in retained.items():self.assertEqual((self.root/path).read_bytes(),raw)
        self.unchanged_authority()


if __name__=='__main__':unittest.main()
