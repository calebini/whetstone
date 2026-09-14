from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_local_storage import Publication,StorageWriteError
from whetstone.vnext_proposal_handoff import handoff_proposal_request,register_completed_proposal_request,registry_for_proposal_requests,validate_proposal_handoff
from vnext_fixtures import STAMP
import test_vnext_proposal_requests as request_tests
from test_vnext_proposal_requests import Client


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class ProposalHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):request_tests.ProposalRequestTests.setUpClass()
    def setUp(self):
        self.f=request_tests.ProposalRequestTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.client=Client();self.result=None
    def inputs(self,read,round_number):return self.f.load(read)
    def arguments(self):return dict(round_number=1,load_inputs=self.inputs,validate_authority=self.f.authority)
    def complete(self):self.result=self.f.run_request(self.client);self.assertEqual(self.result.status,'complete')
    def handoff(self):return handoff_proposal_request(self.f.store,**self.arguments())
    def register(self):return register_completed_proposal_request(self.f.store,created_at=STAMP,**self.arguments())
    def registry(self):return registry_for_proposal_requests(self.f.store,load_inputs=self.inputs,validate_authority=self.f.authority)
    def json(self,path):return json.loads((self.f.root/path).read_bytes())

    def test_completed_request_hands_off_exact_bytes_and_registers_once(self):
        self.complete();event=self.register()
        self.assertEqual(event['candidate_creation_ordinal'],1)
        receipt=self.json('rounds/round-1/proposal_handoff.json')
        self.assertEqual(receipt['request_id'],self.result.request_id)
        self.assertEqual((self.f.root/receipt['proposal']['path']).read_bytes(),
                         (self.f.root/self.result.reference['path']).read_bytes())
        self.assertEqual(self.json(event['initial_disposition_event_path'])['new_disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(self.register(),event);self.assertEqual(self.client.calls,1)
        self.assertEqual(len(self.registry().inspect().events),1)
        self.assertFalse(list(self.f.root.rglob('draft_after.md')))

    def test_handoff_alone_does_not_register_or_change_seed_authority(self):
        self.complete();before=(self.f.root/'rounds/current_verified.json').read_bytes()
        self.handoff();view=self.registry().inspect()
        self.assertIsNone(view.latest);self.assertEqual(view.orphans,())
        self.assertEqual(before,(self.f.root/'rounds/current_verified.json').read_bytes())

    def test_unfinished_request_cannot_be_substituted_for_a_completed_receipt(self):
        def timeout(packet):raise TimeoutError('scripted deadline')
        self.client=Client(timeout);self.f.run_request(self.client)
        with self.assertRaisesRegex(ValueError,'completed durable request'):self.handoff()
        self.assertEqual(self.client.calls,1);self.assertFalse((self.f.root/'rounds/round-1').exists())

    def test_valid_response_without_result_requires_request_finalization_first(self):
        original=self.f.store.publish
        def stop(token,path,value):
            result=original(token,path,value)
            if path.endswith('/response.json'):raise OSError('scripted stop')
            return result
        with patch.object(self.f.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.f.run_request(self.client)
        with self.assertRaisesRegex(ValueError,'completed durable request'):self.register()
        replay=Client();self.f.run_request(replay,True)
        self.register();self.assertEqual(replay.calls,0);self.assertEqual(self.client.calls,1)

    def test_wrong_round_refuses_before_copies(self):
        self.complete()
        with self.assertRaisesRegex(ValueError,'another round'):
            handoff_proposal_request(self.f.store,**{**self.arguments(),'round_number':2})
        self.assertFalse((self.f.root/'rounds/round-2').exists())

    def test_every_round_copy_prefix_is_replayed_without_a_client(self):
        for prefix in range(1,5):
            with self.subTest(prefix=prefix):
                old=self.f;self.f=request_tests.ProposalRequestTests();self.f.setUp()
                try:
                    self.client=Client();self.complete();original=self.f.store.publish;count=0
                    def stop(token,path,value):
                        nonlocal count
                        result=original(token,path,value)
                        if path.startswith('rounds/round-1/'):
                            count+=1
                            if count==prefix:raise OSError('scripted handoff interruption')
                        return result
                    with patch.object(self.f.store,'publish',side_effect=stop):
                        with self.assertRaises(OSError):self.handoff()
                    if prefix<4:
                        with self.assertRaisesRegex(ValueError,'handoff receipt'):
                            validate_proposal_handoff(self.f.store,**self.arguments())
                        self.assertFalse((self.f.root/'rounds/round-1/candidates').exists())
                    event=self.register();self.assertEqual(event['candidate_creation_ordinal'],1);self.assertEqual(self.client.calls,1)
                finally:self.f.doCleanups();self.f=old

    def test_conflicting_round_bytes_are_preserved_and_not_overwritten(self):
        self.complete();path='rounds/round-1/mutation_plan.json'
        with self.f.store.locked(self.f.authority) as token:self.f.store.publish(token,path,b'conflicting plan')
        with self.assertRaises(StorageWriteError):self.handoff()
        self.assertEqual((self.f.root/path).read_bytes(),b'conflicting plan')
        self.assertFalse((self.f.root/'rounds/round-1/proposal_handoff.json').exists())

    def test_rehashed_handoff_and_altered_round_patch_fail_exact_readback(self):
        self.complete();receipt=self.handoff();path=self.f.root/'rounds/round-1/proposal_handoff.json';raw=path.read_bytes()
        changed=deepcopy(receipt);changed['proposal']['hash']='f'*64;path.write_bytes(canonical_json_bytes(changed))
        with self.assertRaisesRegex(ValueError,'conflicting'):validate_proposal_handoff(self.f.store,**self.arguments())
        path.write_bytes(raw);patch_path=self.f.root/receipt['proposal']['path'];patch_path.write_bytes(patch_path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'differs'):validate_proposal_handoff(self.f.store,**self.arguments())
        with self.assertRaises(StorageWriteError):self.registry().register(round_number=1,proposal_id=self.result.proposal.patch['proposal_id'],created_at=STAMP)

    def test_read_only_handoff_validation_does_not_repair_or_invoke(self):
        self.complete();receipt=self.handoff()
        before={str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        self.assertEqual(validate_proposal_handoff(self.f.store,**self.arguments()),receipt)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()})
        self.assertEqual(self.client.calls,1)

    def test_source_durability_failure_prevents_round_publication(self):
        self.complete();original=self.f.store._tree.write
        def fail(path,raw,**kwargs):
            result=original(path,raw,**kwargs)
            if path.endswith('/proposal_result.json'):
                raise StorageWriteError(Publication('outcome_requires_reconciliation',path,result.hash),OSError('source barrier failed'))
            return result
        with patch.object(self.f.store._tree,'write',side_effect=fail):
            with self.assertRaises(StorageWriteError):self.handoff()
        self.assertIsNone(self.f.store._lock_fd)
        self.assertFalse((self.f.root/'rounds/round-1').exists());self.assertEqual(self.client.calls,1)
        self.register();self.assertEqual(self.client.calls,1)

    def test_handoff_acknowledgement_loss_is_reconciled_before_registration(self):
        self.complete();original=self.f.store._tree.write
        def fail(path,raw,**kwargs):
            result=original(path,raw,**kwargs)
            if path.endswith('/proposal_handoff.json'):
                raise StorageWriteError(Publication('outcome_requires_reconciliation',path,result.hash),OSError('lost handoff acknowledgement'))
            return result
        with patch.object(self.f.store._tree,'write',side_effect=fail):
            with self.assertRaises(StorageWriteError):self.handoff()
        self.assertIsNone(self.registry().inspect().latest)
        event=self.register();self.assertEqual(event['candidate_creation_ordinal'],1);self.assertEqual(self.client.calls,1)

    def test_source_receipt_tampering_invalidates_already_registered_candidate_readback(self):
        self.complete();self.register()
        path=self.f.directory(self.result)/'proposal_result.json';value=json.loads(path.read_bytes())
        value['proposal']['hash']='f'*64;path.write_bytes(canonical_json_bytes(value))
        with self.assertRaisesRegex(ValueError,'receipt differs'):self.registry().inspect()

    def test_direct_registry_entry_repeats_handoff_barrier_before_candidate_creation(self):
        self.complete();self.handoff();original=self.f.store._tree.write
        def fail(path,raw,**kwargs):
            result=original(path,raw,**kwargs)
            if path.endswith('/proposal_handoff.json'):
                raise StorageWriteError(Publication('outcome_requires_reconciliation',path,result.hash),OSError('handoff barrier failed'))
            return result
        with patch.object(self.f.store._tree,'write',side_effect=fail):
            with self.assertRaises(StorageWriteError):
                self.registry().register(round_number=1,proposal_id=self.result.proposal.patch['proposal_id'],created_at=STAMP)
        self.assertFalse((self.f.root/'rounds/round-1/candidates').exists())

    def test_wrong_proposal_selector_cannot_publish_a_different_handoff(self):
        self.complete()
        with self.assertRaisesRegex(ValueError,'different proposal'):
            self.registry().register(round_number=1,proposal_id='pro_'+'f'*64,created_at=STAMP)
        self.assertFalse((self.f.root/'rounds/round-1').exists())

    def test_native_request_shape_repair_handoff_and_registration_form_one_journey(self):
        client,count=self.f.native_client()
        self.result=self.f.run_request(client)
        self.assertEqual((self.result.status,self.result.attempts),('complete',2))
        event=self.register();again=self.register()
        self.assertEqual(again,event);self.assertEqual(event['candidate_creation_ordinal'],1)
        self.assertEqual(count.read_text(),'2')
        self.assertEqual(self.json(event['initial_disposition_event_path'])['new_disposition'],'CANDIDATE_UNVERIFIED')


if __name__=='__main__':unittest.main()
