"""One command journey through promoted correction, interruption and convergence."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_run import open_verified_run
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_phase2_entry import ENTRY_PATH, STATE_FIELD as ENTRY_FIELD
from whetstone.vnext_verified_phase2_closeout import STATE_FIELD as CLOSEOUT_FIELD
import test_vnext_verified_reviewer_handoff as handoff


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class PostPromotionCommandTests(unittest.TestCase):
    setUpClass=handoff.ReviewerHandoffTests.setUpClass
    setUp=handoff.ReviewerHandoffTests.setUp
    patch=handoff.ReviewerHandoffTests.patch
    qualify=handoff.ReviewerHandoffTests.qualify
    save_config=handoff.ReviewerHandoffTests.save_config
    clean=staticmethod(handoff.ReviewerHandoffTests.clean)
    invoke=handoff.ReviewerHandoffTests.invoke
    files=handoff.ReviewerHandoffTests.files
    stage_phase2=handoff.ReviewerHandoffTests.stage_phase2
    ready=handoff.ReviewerHandoffTests.ready

    def call(self, command, *args):
        print('  command: '+command+' '+' '.join(args),file=sys.stderr,flush=True)
        code,result=self.invoke(command,*args)
        print('  result: '+str(code)+' '+str(result.get('gate',result.get('reason'))),file=sys.stderr,flush=True)
        return code,result

    def test_post_correction_reports_recover_to_convergence_without_repeated_clients(self):
        from test_vnext_proposal_requests import Client as Editor
        from test_vnext_semantic_requests import Client as Verifier
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        self.ready()
        editor=Editor();verifiers=[]
        self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=editor)
        def verifier(**kwargs):
            with open_verified_run(self.root) as run:
                history=run._history();creation=history.inspect().creations[-1]
                context=load_registered_semantic_context(run.store,admission=history,candidate_id=creation['candidate_id'])
            client=Verifier(context);verifiers.append(client);return client
        self.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient',side_effect=verifier)
        def counts():return self.phase2_reviewer.calls,editor.calls,sum(c.calls for c in verifiers)
        publish=LocalAuthorityStore.publish
        faulted=[]
        def interrupt_resolution(store,token,path,packet):
            result=publish(store,token,path,packet)
            if path=='rounds/phase2/resolutions/pass-1/summary.json':
                faulted.append(path)
                raise OSError('fixture interrupted resolution publication')
            return result
        with patch.object(LocalAuthorityStore,'publish',interrupt_resolution):
            code,result=self.call('live-phase2')
        self.assertEqual(code,2,result);self.assertEqual(len(faulted),1,result)
        self.assertEqual(counts(),(1,1,1))
        head=(self.root/'rounds/current_verified.json').read_bytes()
        self.assertEqual(json.loads(head)['promotion_ordinal'],1)
        # Entry is historical after promotion; a missing derived reference must
        # repair that same entry, without replacing it or completing the report.
        entry=(self.root/ENTRY_PATH).read_bytes()
        projection=json.loads((self.root/STATE_PATH).read_bytes())
        projection.pop(ENTRY_FIELD)
        (self.root/STATE_PATH).write_bytes(canonical_json_bytes(projection))
        code,state=self.call('status','--format','json');self.assertEqual(code,0,state)
        self.assertEqual(state['recovery'],'entry',state)
        code,result=self.call('resume');self.assertEqual(code,0,result)
        self.assertEqual(result['outcome'],'phase2_entry_recovered',result)
        self.assertEqual((self.root/ENTRY_PATH).read_bytes(),entry)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),head)
        self.assertEqual(counts(),(1,1,1))
        before=self.files()
        code,state=self.call('status','--format','json');self.assertEqual(code,0,state)
        self.assertEqual(state['recovery'],'resolution_publication',state)
        code,result=self.call('resume','--dry-run');self.assertEqual(code,0,result)
        code,result=self.call('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(result['next_action'],'resume')
        self.assertEqual(self.files(),before);self.assertEqual(counts(),(1,1,1))
        code,result=self.call('resume');self.assertEqual(code,0,result)
        self.assertTrue(result['state_current'],result)
        self.assertEqual(counts(),(1,1,1))
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),head)

        def interrupt_closeout(store,token,path,packet):
            result=publish(store,token,path,packet)
            if path.startswith('rounds/phase2/closeouts/') and path.endswith('/terminal_report.json'):
                faulted.append(path)
                raise OSError('fixture interrupted closeout publication')
            return result
        with patch.object(LocalAuthorityStore,'publish',interrupt_closeout):
            code,result=self.call('live-phase2')
        self.assertEqual(code,2,result);self.assertEqual(len(faulted),2,result)
        calls=counts();self.assertEqual(calls,(3,1,1))
        before=self.files()
        code,state=self.call('status','--format','json');self.assertEqual(code,0,state)
        self.assertEqual(state['recovery'],'closeout_publication',state)
        self.assertFalse(state['closeout']['committed'])
        code,result=self.call('resume','--dry-run');self.assertEqual(code,0,result)
        code,result=self.call('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before);self.assertEqual(counts(),calls)

        materialize=LocalAuthorityStore.materialize
        def lose_final_ack(store,token,path,packet,**kwargs):
            result=materialize(store,token,path,packet,**kwargs)
            if path==STATE_PATH and CLOSEOUT_FIELD in json.loads(packet):
                faulted.append(path)
                raise OSError('fixture lost final state acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'materialize',lose_final_ack):
            code,result=self.call('resume')
        self.assertEqual(code,2,result);self.assertEqual(faulted[-1],STATE_PATH,result)
        self.assertEqual(counts(),calls)
        before=self.files()
        code,state=self.call('status','--format','json');self.assertEqual(code,0,state)
        self.assertEqual(state['gate'],'phase2_complete',state)
        self.assertEqual(state['closeout']['packet']['terminal_state'],'CONVERGED')
        self.assertTrue(state['closeout']['phase_complete'])
        code,result=self.call('live-phase2');self.assertEqual(code,0,result)
        code,result=self.call('resume');self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before);self.assertEqual(counts(),calls)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),head)
