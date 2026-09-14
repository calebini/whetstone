import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_followup_admission import SemanticFollowupAdmission
from vnext_fixtures import STAMP
import test_vnext_semantic_followup_workflow as fixtures


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class SemanticFollowupWorkflowRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.SemanticFollowupWorkflowTests.setUpClass()

    def test_initial_raw_final_decision_and_terminal_recovery_preserve_call_allowances(self):
        owner=fixtures.SemanticFollowupWorkflowTests();owner.setUp();self.addCleanup(owner.doCleanups)
        run=owner.run;store=owner.store
        seed=store.read('rounds/current_verified.json')
        reference=run.admit_followup(candidate_id=owner.subject.identifier,answer_reference=owner.answer['reference'])
        admission=SemanticFollowupAdmission(store,original=run.original,selected_ref=reference)
        editor=fixtures.admission.proposals.Client()
        self.assertEqual(admission.request(client=editor).status,'complete')
        creation=admission.register(created_at=STAMP)
        # Registration has committed, but normal closeout has not yet written
        # the initial deterministic decision. Recover that gate on its own.
        before=owner.files()
        status=run.status(round_number=1)
        self.assertEqual(status['processing_gate'],'verification_commit')
        self.assertTrue(status['resume']['permitted'])
        self.assertEqual(owner.files(),before)
        with self.assertRaisesRegex(ValueError,'explicit continuation'):
            run.verify_round(round_number=1,client=object(),decided_at=STAMP)
        self.assertEqual(owner.files(),before)
        report,_=run.verify_round(round_number=1,client=object(),decided_at=STAMP,continuation=True)
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(run.semantic_status(round_number=1)['request_status'],'not_started')
        print('follow-up initial decision recovery completed without Verifier',flush=True)
        context=load_registered_semantic_context(store,admission=run.command_view(1),candidate_id=creation['candidate_id'])
        verifier=fixtures.admission.answers.requests.Client(context)
        publish=store.publish
        def stop_raw(token,path,value):
            result=publish(token,path,value)
            if path.endswith('/attempts/1/response.json'):raise OSError('captured follow-up Verifier output')
            return result
        with patch.object(store,'publish',side_effect=stop_raw):
            with self.assertRaisesRegex(OSError,'captured follow-up Verifier'):
                run.verify_round(round_number=1,client=verifier,decided_at=STAMP)
        before=owner.files();status=run.semantic_status(round_number=1)
        self.assertEqual((status['processing_gate'],status['request_status']),('verification_commit','valid_response'))
        self.assertEqual(owner.files(),before)
        def stop_decision(token,path,value):
            result=publish(token,path,value)
            if path.endswith('/candidate_verification-attempt-2.json'):
                raise OSError('prepared follow-up final decision')
            return result
        with patch.object(store,'publish',side_effect=stop_decision):
            with self.assertRaisesRegex(OSError,'prepared follow-up final decision'):
                run.verify_round(round_number=1,client=object(),decided_at=STAMP,continuation=True)
        before=owner.files();status=run.semantic_status(round_number=1)
        self.assertEqual(status['processing_gate'],'verification_commit')
        self.assertTrue(status['resume']['permitted'])
        self.assertEqual(owner.files(),before)
        report,terminal=run.verify_round(round_number=1,client=object(),decided_at=STAMP,continuation=True)
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_VERIFIED')
        print('follow-up retained Verifier output and final decision recovered',flush=True)
        terminal_path=owner.subject.fixture.root/terminal['path'];terminal_bytes=terminal_path.read_bytes()
        terminal_path.unlink()
        before=owner.files();status=run.status(round_number=1)
        self.assertEqual(status['processing_gate'],'materialization')
        self.assertEqual(owner.files(),before)
        with self.assertRaisesRegex(ValueError,'explicit continuation'):
            run.verify_round(round_number=1,client=object(),decided_at=STAMP)
        self.assertEqual(owner.files(),before)
        self.assertEqual(run.verify_round(round_number=1,client=object(),decided_at=STAMP,continuation=True)[0],report)
        self.assertEqual(terminal_path.read_bytes(),terminal_bytes)
        self.assertEqual((editor.calls,verifier.calls),(1,1))
        self.assertEqual(store.read('rounds/current_verified.json'),seed)


if __name__=='__main__':unittest.main()
