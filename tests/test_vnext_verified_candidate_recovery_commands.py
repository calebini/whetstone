"""Exact candidate publication recovery through the public command adapter."""
import json
import sys
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_verified_run import open_verified_run
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from test_vnext_proposal_requests import Client as Editor
from test_vnext_semantic_requests import Client as Verifier
from vnext_fixtures import STAMP
from vnext_q1_command_fixtures import CommandCase


class CandidateRecoveryCommands(CommandCase):
    def test_registration_decision_and_claimant_recover_exactly_and_stop(self):
        if sys.platform!='darwin':self.skipTest('D8 requires macOS/APFS')
        self.qualify();code,result=self.call('vnext-admit');self.assertEqual(code,0,result)
        self.reviewer.callback=canonical_json_bytes
        editor=Editor()
        with open_verified_run(self.root) as run:
            run.review_next(client=self.reviewer);run.admit_reviewed_round()
            self.assertEqual(run.request(round_number=1,client=editor).value.status,'complete')
            with self.lost_publication(lambda p:p=='rounds/candidate_index/creation-1.json',after=False):
                with self.assertRaises(OSError):run.register(round_number=1,created_at=STAMP)
        head=(self.root/'rounds/current_verified.json').read_bytes()
        state=self.inspect_readonly();self.assertEqual(state['recovery'],'registration')
        self.assertEqual(state['round_number'],1)
        creation=state['candidate'];self.assertTrue(creation['candidate_id'].startswith('can_'))
        prep=state['preparation'];self.assertEqual(sha256_bytes((self.root/prep['path']).read_bytes()),prep['hash'])
        self.readonly_resume('--vnext-round','1','--continue')
        self.refuses('resume');self.refuses('resume','--vnext-round','2','--dry-run')
        self.refuses('resume','--vnext-round','2');self.refuses('live-phase1')
        self.refuses_drift_at_fence(prep['path'],'--vnext-round','1')
        before=self.files();code,result=self.call('resume','--vnext-round','1','--continue')
        self.assertEqual(code,0,result);self.assertEqual(result['outcome'],'registration_recovered')
        self.assertEqual(result['latest_candidate'],creation)
        self.assertEqual(set(self.files())-set(before),{'rounds/candidate_index/creation-1.json'})
        self.assertEqual((self.reviewer.calls,editor.calls),(1,1))
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),head)
        self.refuses('resume','--vnext-round','1')
        with open_verified_run(self.root) as run:
            context=load_registered_semantic_context(run.store,admission=run._history(),candidate_id=creation['candidate_id'])
            verifier=Verifier(context)
            directory=creation['candidate_path'].rsplit('/',1)[0]
            with self.lost_publication(lambda p:p==directory+'/disposition_events/event-3.json'):
                with self.assertRaises(OSError):run.verify(client=verifier,decided_at=STAMP)
        state=self.inspect_readonly();self.assertEqual(state['recovery'],'verification')
        pending=state['pending_decision'];raw=(self.root/pending['path']).read_bytes()
        self.assertEqual(sha256_bytes(raw),pending['hash'])
        self.assertEqual(json.loads(raw)['decided_at'],STAMP)
        self.readonly_resume('--vnext-round','1','--continue')
        self.refuses('resume');self.refuses('resume','--vnext-round','2');self.refuses('live-phase1')
        self.refuses_drift_at_fence(pending['path'],'--vnext-round','1')
        code,result=self.call('resume','--vnext-round','1','--continue')
        self.assertEqual(code,0,result);self.assertEqual(result['outcome'],'verification_recovered')
        self.assertEqual(result['value']['decision'],json.loads(raw));self.assertEqual(verifier.calls,1)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),head)
        self.assertEqual(self.inspect_readonly()['gate'],'promotion')
        with open_verified_run(self.root) as run:
            with self.lost_publication(lambda p:'/promotion_intents/' in p):
                with self.assertRaises(OSError):run.promote(prepared_at=STAMP)
        state=self.inspect_readonly();self.assertEqual(state['recovery'],'promotion')
        self.readonly_resume('--continue');self.refuses('live-phase1')
        code,result=self.call('resume','--continue');self.assertEqual(code,0,result)
        self.assertEqual(result['outcome'],'promoted');self.assertEqual(result['current_pointer']['promotion_ordinal'],1)
        self.assertEqual(result['current_pointer']['source_candidate_id'],creation['candidate_id'])
        self.assertEqual((self.reviewer.calls,editor.calls,verifier.calls),(1,1,1))
        self.assertFalse((self.root/'rounds/review_index/request-2.json').exists())
        self.assertFalse((self.root/'rounds/candidate_index/creation-2.json').exists())
        self.assertEqual(self.inspect_readonly()['recovery'],'phase1_projection')
        code,result=self.call('resume','--continue');self.assertEqual(code,0,result)
        self.assertEqual(result['outcome'],'phase1_state_synchronized')
        self.assertEqual((self.reviewer.calls,editor.calls,verifier.calls),(1,1,1))
