import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_local_storage import LocalAuthorityStore
import test_vnext_proposal_cli as fixtures


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class ProposalOutputRecoveryCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ProposalCLITests.setUpClass()

    def test_captured_editor_output_resumes_without_constructing_any_adapter(self):
        subject=fixtures.ProposalCLITests();subject.setUp();self.addCleanup(subject.doCleanups)
        publish=LocalAuthorityStore.publish
        def stop(store,token,path,value):
            result=publish(store,token,path,value)
            if subject.editor.calls and path.endswith('/attempts/1/response.json'):
                raise OSError('scripted captured Editor response')
            return result
        with patch.object(LocalAuthorityStore,'publish',new=stop):
            code,packet=subject.invoke('live-phase1',package=True)
        self.assertEqual(code,2)
        self.assertEqual(packet['terminal_state'],'HALTED_ARTIFACT_INVALID')
        self.assertEqual((subject.reviewer.calls,subject.editor.calls),(1,1))
        subject.review_factory.reset_mock();subject.editor_factory.reset_mock()
        before=subject.files()
        code,status=subject.invoke('status')
        self.assertEqual(code,0)
        self.assertEqual(status['proposal_status']['request_status'],'valid_response')
        self.assertTrue(status['proposal_status']['resume']['permitted'])
        self.assertEqual(subject.files(),before)
        self.assertEqual(subject.invoke('live-phase1')[0],2)
        self.assertEqual(subject.files(),before)
        subject.review_factory.assert_not_called();subject.editor_factory.assert_not_called()
        with patch.object(fixtures.routing,'_client',side_effect=AssertionError('Recovery must not construct adapters')):
            code,packet=subject.invoke('resume','--continue')
        self.assertEqual(code,2)  # This proposal-only fixture has no semantic consumer.
        self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertFalse(packet['proposal_status']['resume']['permitted'])
        self.assertEqual((subject.reviewer.calls,subject.editor.calls),(1,1))
        subject.review_factory.assert_not_called();subject.editor_factory.assert_not_called()


if __name__=='__main__':unittest.main()
