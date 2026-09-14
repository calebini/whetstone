import sys
import unittest

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_proposal_closeout import run_proposal_round
from vnext_fixtures import STAMP
import test_vnext_proposal_closeout as closeout


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class ProposalTerminalOutputRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):closeout.ProposalCloseoutTests.setUpClass()

    def test_invalid_and_exhausted_output_materialize_terminal_without_editor(self):
        def invalid(packet):
            packet['patch']['transaction_id']='txn_'+'f'*64
            return canonical_json_bytes(packet)
        for expected,callback,calls in [('invalid_proposal',invalid,1),('attempts_exhausted',lambda packet:b'{}',2)]:
            fixture=closeout.ProposalCloseoutTests();fixture.setUp()
            try:
                with self.subTest(status=expected):
                    client=closeout.Client(callback)
                    self.assertEqual(fixture.request(client).status,expected)
                    report,reference=run_proposal_round(fixture.store,admission=fixture.admission,
                        round_number=1,client=None,decided_at=STAMP)
                    self.assertEqual(report['terminal_state'],'HALTED_ARTIFACT_INVALID')
                    self.assertFalse(report['resume']['permitted'])
                    self.assertEqual(fixture.store.read(reference['path']),canonical_json_bytes(report))
                    self.assertIsNone(report['latest_candidate']['candidate_id'])
                    self.assertEqual(client.calls,calls)
            finally:fixture.doCleanups()


if __name__=='__main__':unittest.main()
