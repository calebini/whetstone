import json
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_unit_protocol import ProposalShapeError, exercise_unit_proposal
from whetstone.vnext_storage import publish
import test_vnext_unit_preflight as preflight_tests


class ProposalRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):preflight_tests.UnitPreflightTests.setUpClass()
    def setUp(self):
        self.fixture=preflight_tests.UnitPreflightTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.directory=self.fixture.directory
    def run_client(self,client):return exercise_unit_proposal(self.directory,load_inputs=self.fixture.inputs,client=client)

    def test_one_shape_retry_keeps_identical_inputs_and_precise_errors(self):
        def response(packet):return b'{}' if client.calls==1 else canonical_json_bytes(packet)
        client=preflight_tests.Client(response);preflight,proposal,_=self.run_client(client)
        self.assertEqual(client.calls,2)
        self.assertTrue(client.prompts[1].endswith(preflight.prompt))
        self.assertIn('Previous shape validation errors:',client.prompts[1])
        first=json.loads((self.directory/'attempts/invocation-1.json').read_bytes())
        second=json.loads((self.directory/'attempts/invocation-2.json').read_bytes())
        self.assertEqual(first['input_hash'],second['input_hash'])
        self.assertEqual(first['original_prompt_hash'],second['original_prompt_hash'])
        self.assertNotEqual(first['attempt_prompt_hash'],second['attempt_prompt_hash'])
        self.assertEqual((self.directory/'attempts/proposal-attempt-1.json').read_bytes(),b'{}')
        self.assertEqual(json.loads((self.directory/'attempts/outcome-1.json').read_bytes())['classification'],'shape_invalid')
        self.assertEqual(json.loads((self.directory/'attempts/outcome-2.json').read_bytes())['proposal_hash'],proposal.digest)

    def test_second_shape_failure_exhausts_allowance_and_new_process_cannot_reset_it(self):
        client=preflight_tests.Client(lambda packet:b'not JSON')
        with self.assertRaises(ProposalShapeError):self.run_client(client)
        self.assertEqual(client.calls,2)
        self.assertTrue((self.directory/'attempts/failure-2.txt').exists())
        self.assertFalse(json.loads((self.directory/'attempts/outcome-2.json').read_bytes())['automatic_retry_permitted'])
        restarted=preflight_tests.Client()
        with self.assertRaises(FileExistsError):self.run_client(restarted)
        self.assertEqual(restarted.calls,0)

    def test_binding_and_payload_semantics_receive_no_automatic_repair(self):
        def stale(packet):packet['patch']['base_draft_hash']='f'*64;return canonical_json_bytes(packet)
        client=preflight_tests.Client(stale)
        with self.assertRaises(ValueError) as caught:self.run_client(client)
        self.assertNotIsInstance(caught.exception,ProposalShapeError)
        self.assertEqual(client.calls,1);self.assertFalse((self.directory/'attempts/invocation-2.json').exists())

    def test_changed_transport_after_a_call_cannot_use_shape_retry(self):
        class BoundClient(preflight_tests.Client):
            generation=1
            @property
            def transport_binding(self):return {'generation':self.generation}
        def change(packet):client.generation+=1;return b'{}'
        client=BoundClient(change)
        with self.assertRaisesRegex(ValueError,'transport changed'):self.run_client(client)
        self.assertEqual(client.calls,1)
        self.assertTrue((self.directory/'attempts/proposal-attempt-1.json').exists())

    def test_persistence_failure_after_invocation_never_retries(self):
        def fail(root,path,value,**kwargs):
            if path=='attempts/proposal-attempt-1.json':raise OSError('fictional full disk')
            return publish(root,path,value,**kwargs)
        client=preflight_tests.Client()
        with patch('whetstone.vnext_unit_protocol.publish',side_effect=fail):
            with self.assertRaises(OSError):self.run_client(client)
        self.assertEqual(client.calls,1)
        self.assertTrue((self.directory/'attempts/invocation-1.json').exists())
        self.assertFalse((self.directory/'attempts/invocation-2.json').exists())
        restarted=preflight_tests.Client()
        with self.assertRaises(FileExistsError):self.run_client(restarted)
        self.assertEqual(restarted.calls,0)

    def test_timeout_and_other_client_errors_are_not_shape_failures(self):
        for index,error in enumerate((TimeoutError('deadline'),RuntimeError('provider failed'),ValueError('client transport decode failed'))):
            self.directory=self.fixture.directory.with_name('error-'+str(index))
            def fail(packet):raise error
            client=preflight_tests.Client(fail)
            with self.subTest(error=type(error).__name__),self.assertRaises(type(error)):self.run_client(client)
            self.assertEqual(client.calls,1)
            self.assertTrue((self.directory/'attempts/failure-1.txt').exists())


if __name__=='__main__':unittest.main()
