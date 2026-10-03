"""Phase 1 retained output, terminal repair and budget admission stop boundaries."""
import json
import sys
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_run import open_verified_run
from test_vnext_proposal_requests import Client as Editor
from test_vnext_semantic_requests import Client as Verifier
from vnext_fixtures import STAMP
from vnext_q1_command_fixtures import CommandCase


class Phase1BoundaryCommands(CommandCase):
    def test_retained_verifier_terminal_projection_and_explicit_budget_stop(self):
        if sys.platform!='darwin':self.skipTest('D8 requires macOS/APFS')
        self.f.original.review['profiles'][0]['budget']=1
        self.f.original.review_ref=self.f.save('inputs/review.json',self.f.original.review)
        self.f.rebind();self.fixture.package.update(job_descriptor=self.f.job_ref,review_configuration=self.f.original.review_ref)
        self.fixture.save_package()
        self.config['vnext_input_package']['hash']=sha256_bytes((self.fixture.source/'proposal_package.json').read_bytes());self.save_config()
        self.qualify();code,result=self.call('vnext-admit');self.assertEqual(code,0,result)
        self.reviewer.callback=canonical_json_bytes;editor=Editor()
        with open_verified_run(self.root) as run:
            run.review_next(client=self.reviewer);run.admit_reviewed_round();run.request(round_number=1,client=editor)
            creation=run.register(round_number=1,created_at=STAMP).value
            context=load_registered_semantic_context(run.store,admission=run._history(),candidate_id=creation['candidate_id'])
            verifier=Verifier(context)
            with self.lost_publication(lambda p:p.endswith('/attempts/1/response.json')):
                with self.assertRaises(OSError):run.verify(client=verifier,decided_at=STAMP)
        self.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient',return_value=verifier)
        state=self.inspect_readonly();self.assertEqual(state['continuation'],'verifier')
        self.assertEqual(state['request_status'],'valid_response')
        self.readonly_resume('--vnext-round','1');self.refuses('live-phase1')
        code,result=self.call('resume','--vnext-round','1');self.assertEqual(code,0,result)
        self.assertTrue(result['value']['decision']['promotion_permitted']);self.assertEqual(verifier.calls,1)
        with open_verified_run(self.root) as run:
            self.assertEqual(run.inspect().current_pointer['promotion_ordinal'],0)
            run.promote(prepared_at=STAMP);run.reconcile_phase1_state()
            closeout=run.phase1_closeout()
        with self.lost_publication(lambda p:p==closeout.evidence_ref['path'],after=False):
            code,result=self.call('resume','--continue')
        self.assertEqual(code,2,result);self.assertEqual(self.inspect_readonly()['recovery'],'phase1_publication')
        self.readonly_resume('--continue')
        code,result=self.call('resume','--continue');self.assertEqual(code,0,result)
        self.assertEqual(self.inspect_readonly()['recovery'],'phase1_projection')
        materialize=LocalAuthorityStore.materialize;hits=[]
        def lost(store,token,path,raw,**kwargs):
            result=materialize(store,token,path,raw,**kwargs)
            if path=='rounds/run_state.json':hits.append(path);raise OSError('lost phase1 state acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'materialize',lost):code,result=self.call('resume','--continue')
        self.assertEqual(code,2,result);self.assertTrue(hits)
        state=self.inspect_readonly();self.assertEqual(state['gate'],'phase1_stopped')
        self.refuses('resume','--continue')
        self.readonly_resume('--extend-review-budget','1')
        with self.lost_publication(lambda p:'/phase1_budget_extensions/' in p):
            code,result=self.call('resume','--extend-review-budget','1')
        self.assertEqual(code,2,result)
        self.readonly_resume('--extend-review-budget','1')
        self.refuses('resume','--extend-review-budget','2','--dry-run')
        self.refuses('resume','--extend-review-budget','2')
        # The same explicit grant must also recover when its state write landed
        # but the caller never received the acknowledgement.
        with patch.object(LocalAuthorityStore,'materialize',lost):
            code,result=self.call('resume','--extend-review-budget','1')
        self.assertEqual(code,2,result)
        self.assertEqual(self.inspect_readonly()['gate'],'review')
        self.readonly_resume('--extend-review-budget','1')
        code,result=self.call('resume','--extend-review-budget','1');self.assertEqual(code,0,result)
        self.assertEqual(result['outcome'],'budget_extension_recovered')
        self.assertEqual(len(list((self.root/'rounds/phase1_budget_extensions').glob('extension-*.json'))),1)
        self.assertEqual((self.reviewer.calls,editor.calls,verifier.calls),(1,1,1))
        self.assertFalse((self.root/'rounds/review_index/request-2.json').exists())
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())
