import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_proposal_requests import finish_proposal_request, inspect_proposal_request
from whetstone.vnext_proposal_closeout import run_proposal_round
from vnext_fixtures import STAMP
import test_vnext_proposal_requests as requests
import test_vnext_proposal_closeout as closeout


class ProposalRecoveryInputTests(unittest.TestCase):
    def test_closeout_rejects_nonboolean_continuation_before_reading_or_writing(self):
        for value in (None,1,'true'):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'explicit boolean'):
                run_proposal_round(object(),admission=object(),round_number=1,client=None,
                                   decided_at=STAMP,continuation=value)


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class ProposalOutputRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests.ProposalRequestTests.setUpClass()

    def test_recovery_requires_explicit_valid_output_and_never_allocates_a_call(self):
        fixture=requests.ProposalRequestTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        def files():return {p.relative_to(fixture.root):p.read_bytes() for p in fixture.root.rglob('*') if p.is_file()}
        def finish(**options):return finish_proposal_request(fixture.store,load_inputs=fixture.load,
            validate_authority=fixture.authority,**options)
        before=files()
        with self.assertRaisesRegex(ValueError,'explicit continuation'):finish()
        with self.assertRaisesRegex(ValueError,'no valid retained output'):finish(continuation=True)
        self.assertEqual(files(),before)
        client=requests.Client();publish=fixture.store.publish
        def stop(token,path,value):
            result=publish(token,path,value)
            if path.endswith('/attempts/1/response.json'):raise OSError('captured response interruption')
            return result
        with patch.object(fixture.store,'publish',side_effect=stop):
            with self.assertRaisesRegex(OSError,'captured response'):fixture.run_request(client)
        before=files()
        with self.assertRaisesRegex(ValueError,'explicit continuation'):finish()
        self.assertEqual(files(),before)
        result=finish(continuation=True)
        self.assertEqual(result.status,'complete')
        self.assertEqual(client.calls,1)
        self.assertEqual(sum(p.name=='invocation.json' for p in fixture.root.rglob('*')),1)
        self.assertEqual(inspect_proposal_request(fixture.store,load_inputs=fixture.load,
            validate_authority=fixture.authority),result)

    def test_normal_closeout_finishes_captured_output_with_no_editor(self):
        fixture=closeout.ProposalCloseoutTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        publish=fixture.store.publish
        def stop(token,path,value):
            result=publish(token,path,value)
            if path.endswith('/attempts/1/response.json'):raise OSError('captured closeout response')
            return result
        with patch.object(fixture.store,'publish',side_effect=stop):
            with self.assertRaisesRegex(OSError,'captured closeout'):fixture.request()
        def invoke(continuation=False):return run_proposal_round(fixture.store,admission=fixture.admission,
            round_number=1,client=None,decided_at=STAMP,continuation=continuation)
        before={p:p.read_bytes() for p in fixture.f.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'Editor client is required'):invoke()
        self.assertEqual(before,{p:p.read_bytes() for p in fixture.f.root.rglob('*') if p.is_file()})
        report,_=invoke(continuation=True)
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(invoke()[0],report)
        self.assertEqual(fixture.client.calls,1)


if __name__=='__main__':unittest.main()
