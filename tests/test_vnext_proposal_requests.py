from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from whetstone.vnext_assembly import ASSEMBLER_VERSION,NORMALIZATION_VERSION
from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_inventory import INVENTORY_VERSION
from whetstone.vnext_local_storage import LocalAuthorityStore,initialize_storage
from whetstone.vnext_proposal_requests import inspect_proposal_request,logical_request_id,run_proposal_request
import test_vnext_unit_preflight as fixtures


class Client(fixtures.Client):
    def __init__(self,callback=None):
        super().__init__(callback);self.identity=deepcopy(fixtures.ACTOR);self.timeout=5;self.command='scripted-editor'
    @property
    def transport_binding(self):
        return {'editor':deepcopy(self.identity),'command':self.command,'cwd':'/scripted/fixture',
                'timeout_seconds':self.timeout,'output_schema_hash':'a'*64}


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class ProposalRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.UnitPreflightTests.setUpClass()
    def setUp(self):
        self.fixture=fixtures.UnitPreflightTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture.c.f;old_suite=self.fixture.c.suite
        self.fixture.c.suite=f.suite=SimpleNamespace(version='isolated-request-fixture-v1',digest=old_suite.digest,registry=old_suite.registry)
        f.job.update(contract_suite_version=f.suite.version,assembler_version=ASSEMBLER_VERSION,
            normalization_version=NORMALIZATION_VERSION,inventory_version=INVENTORY_VERSION)
        f.rebind()
        self.initialize_store('request-store')
        self.load_count=0;self.change=None

    def initialize_store(self,name):
        f=self.fixture.c.f
        self.root=Path(self.fixture.c.tmp.name)/name
        paths={'job_descriptor.json','rounds/current_verified.json',f.pointer_ref['path'],f.map_ref['path'],
            f.job['seed_draft']['path'],f.job['authority_map_path'],f.job['protected_invariants_path'],
            f.feedback_ref['path'],f.advice_ref['path'],f.original.review_ref['path']}
        artifacts={path:(f.root/path).read_bytes() for path in paths}
        initialize_storage(self.root,job_id=f.job['job_id'],descriptor_ref=f.job_ref,artifacts=artifacts)
        self.store=LocalAuthorityStore(self.root,job_id=f.job['job_id']);self.addCleanup(self.store.close)

    def load(self,read):
        self.load_count+=1;f=self.fixture.c.f
        inputs=self.fixture.inputs();inputs={**deepcopy({k:v for k,v in inputs.items() if k!='suite'}),'suite':inputs['suite']}
        for key,path in [('job','job_descriptor.json'),('authority',f.job['authority_map_path']),
            ('invariants',f.job['protected_invariants_path']),('review',f.original.review_ref['path']),
            ('feedback',f.feedback_ref['path']),('advice',f.advice_ref['path']),('seed_map',f.map_ref['path']),('base_map',f.map_ref['path'])]:
            inputs[key]=json.loads(read(path))
        inputs['seed']=inputs['base']=read(f.job['seed_draft']['path'])
        if self.change is not None:self.change(inputs)
        return inputs

    def authority(self,read):
        f=self.fixture.c.f
        self.assertEqual(read('job_descriptor.json'),canonical_json_bytes(f.job))
        self.assertEqual(sha256_bytes(read('rounds/current_verified.json')),f.pointer_ref['hash'])

    def run_request(self,client,continuation=False):
        return run_proposal_request(self.store,load_inputs=self.load,validate_authority=self.authority,client=client,continuation=continuation)
    def directory(self,result):return self.root/'rounds/client_requests'/result.request_id
    def read(self,result,name):return json.loads((self.directory(result)/name).read_bytes())

    def test_success_replays_without_another_call_or_candidate(self):
        first=Client();result=self.run_request(first)
        self.assertEqual((result.status,result.attempts,first.calls),('complete',1,1))
        replay=Client();again=self.run_request(replay)
        self.assertEqual(again.proposal,result.proposal);self.assertEqual(replay.calls,0)
        self.assertEqual(result.request_id,logical_request_id(self.fixture.c.f.job['job_id'],result.proposal.patch['transaction_id']))
        self.assertFalse(list(self.root.rglob('candidate_unverified.md')))

    def test_one_shape_retry_is_hash_chained_and_exhaustion_cannot_reset(self):
        bad=Client(lambda packet:b'{}');result=self.run_request(bad)
        self.assertEqual((result.status,result.attempts,bad.calls),('attempts_exhausted',2,2))
        first=self.read(result,'attempts/1/outcome.json');second=self.read(result,'attempts/2/invocation.json')
        self.assertEqual(second['reason'],'shape_retry')
        self.assertEqual(second['previous_outcome_hash'],sha256_bytes(canonical_json_bytes(first)))
        restarted=Client()
        self.assertEqual(self.run_request(restarted,True).status,'attempts_exhausted');self.assertEqual(restarted.calls,0)
        self.assertEqual(self.run_request(restarted).status,'attempts_exhausted')

    def test_timeout_requires_explicit_continuation_and_can_change_only_timeout(self):
        def timeout(packet):raise TimeoutError('scripted deadline')
        client=Client(timeout);failed=self.run_request(client)
        self.assertEqual((failed.status,client.calls),('timeout',1))
        restarted=Client();restarted.timeout=10
        self.assertEqual(self.run_request(restarted).status,'continuation_required');self.assertEqual(restarted.calls,0)
        result=self.run_request(restarted,True)
        self.assertEqual((result.status,result.attempts,restarted.calls),('complete',2,1))
        marker=self.read(result,'attempts/2/invocation.json')
        self.assertEqual(marker['reason'],'technical_continuation');self.assertEqual(marker['transport']['timeout_seconds'],10)
        self.assertEqual(self.read(result,'request.json')['transport']['timeout_seconds'],5)

    def test_provider_value_error_is_not_automatically_repaired(self):
        def fail(packet):raise ValueError('transport decoder failed')
        client=Client(fail);result=self.run_request(client)
        self.assertEqual((result.status,result.attempts,client.calls),('transport_failure',1,1))
        self.assertFalse((self.directory(result)/'attempts/2').exists())

    def test_last_attempt_timeout_keeps_its_cause_when_budget_prevents_continuation(self):
        def respond(packet):
            if client.calls==1:return b'{}'
            raise TimeoutError('last attempt deadline')
        client=Client(respond);result=self.run_request(client)
        self.assertEqual((result.status,result.attempts),('timeout',2))
        status=inspect_proposal_request(self.store,load_inputs=self.load,validate_authority=self.authority)
        self.assertEqual(status.status,'attempts_exhausted')
        self.assertEqual(status.last_outcome['classification'],'timeout')
        self.assertIn('last attempt deadline',status.last_outcome['error'])
        resumed=Client();again=self.run_request(resumed,True)
        self.assertEqual(again.status,'attempts_exhausted');self.assertEqual(resumed.calls,0)

    def test_missing_outcome_already_bound_by_second_invocation_is_not_reconstructed(self):
        def respond(packet):return b'{}' if client.calls==1 else canonical_json_bytes(packet)
        client=Client(respond);result=self.run_request(client)
        (self.directory(result)/'attempts/1/outcome.json').unlink()
        resumed=Client()
        with self.assertRaisesRegex(ValueError,'committed predecessor'):self.run_request(resumed,True)
        self.assertEqual(resumed.calls,0)

    def test_orphan_telemetry_cannot_reset_a_lost_invocation_marker(self):
        def fail(packet):raise TimeoutError('scripted deadline')
        client=Client(fail);client.last_telemetry={'timed_out':True}
        result=self.run_request(client)
        directory=self.directory(result)/'attempts/1'
        (directory/'invocation.json').unlink();(directory/'outcome.json').unlink()
        resumed=Client()
        with self.assertRaisesRegex(ValueError,'invocation evidence'):self.run_request(resumed,True)
        self.assertEqual(resumed.calls,0)

    def test_invalid_bindings_never_reopen_on_explicit_continuation(self):
        def invalid(packet):packet['patch']['base_draft_hash']='f'*64;return canonical_json_bytes(packet)
        client=Client(invalid);result=self.run_request(client)
        self.assertEqual((result.status,client.calls),('invalid_proposal',1))
        resumed=Client();self.assertEqual(self.run_request(resumed,True).status,'invalid_proposal')
        self.assertEqual(self.run_request(resumed).status,'invalid_proposal');self.assertEqual(resumed.calls,0)

    def test_completed_response_is_reused_after_interrupted_output_publication(self):
        original=self.store.publish
        def stop(token,path,value):
            result=original(token,path,value)
            if path.endswith('/response.json'):raise OSError('scripted interruption after response')
            return result
        first=Client()
        with patch.object(self.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.run_request(first)
        second=Client();self.assertEqual(self.run_request(second).status,'continuation_required')
        result=self.run_request(second,True)
        self.assertEqual((result.status,result.attempts,first.calls,second.calls),('complete',1,1,0))

    def test_shape_repair_allowance_survives_a_restart(self):
        original=self.store.publish
        def stop(token,path,value):
            result=original(token,path,value)
            if path.endswith('/outcome.json') and value['classification']=='shape_invalid':raise OSError('scripted stop')
            return result
        first=Client(lambda packet:b'{}')
        with patch.object(self.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.run_request(first)
        second=Client();result=self.run_request(second,True)
        self.assertEqual((result.status,result.attempts,first.calls,second.calls),('complete',2,1,1))
        self.assertIn('Previous shape validation errors:',second.prompts[0])

    def test_durable_invocation_without_response_consumes_one_call(self):
        original=self.store.publish
        def stop(token,path,value):
            result=original(token,path,value)
            if path.endswith('/invocation.json'):raise OSError('scripted stop before client')
            return result
        first=Client()
        with patch.object(self.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.run_request(first)
        self.assertEqual(first.calls,0)
        second=Client();result=self.run_request(second,True)
        self.assertEqual((result.status,result.attempts,second.calls),('complete',2,1))
        self.assertEqual(self.read(result,'attempts/1/outcome.json')['classification'],'interrupted')

    def test_changed_transport_or_inputs_cannot_create_a_fresh_allowance(self):
        first=Client(lambda packet:b'{}');result=self.run_request(first)
        changed=Client();changed.command='another-command'
        with self.assertRaisesRegex(ValueError,'transport identity'):self.run_request(changed,True)
        self.assertEqual(changed.calls,0)
        def drift(inputs):inputs['suite']=SimpleNamespace(version=inputs['suite'].version,digest='f'*64,registry=inputs['suite'].registry)
        self.change=drift
        with self.assertRaisesRegex(ValueError,'frozen inputs'):self.run_request(Client(),True)
        self.assertEqual(len(list((self.root/'rounds/client_requests').iterdir())),1)

    def test_tampered_outcome_and_third_attempt_refuse_before_a_call(self):
        result=self.run_request(Client(lambda packet:b'{}'));path=self.directory(result)/'attempts/1/outcome.json'
        original=path.read_bytes();outcome=json.loads(original);outcome['classification']='timeout';outcome['response_hash']=None
        path.write_bytes(canonical_json_bytes(outcome));restarted=Client()
        with self.assertRaisesRegex(ValueError,'contradicts'):self.run_request(restarted,True)
        path.write_bytes(original);(self.directory(result)/'attempts/3').mkdir()
        with self.assertRaisesRegex(ValueError,'allowance extension'):self.run_request(restarted,True)
        self.assertEqual(restarted.calls,0)

    def test_read_only_inspection_never_consumes_attempts_or_repairs_missing_outcome(self):
        original=self.store.publish
        def stop(token,path,value):
            result=original(token,path,value)
            if path.endswith('/response.json'):raise OSError('scripted interruption')
            return result
        with patch.object(self.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.run_request(Client())
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=inspect_proposal_request(self.store,load_inputs=self.load,validate_authority=self.authority)
        self.assertEqual((result.status,result.attempts),('valid_response',1))
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertFalse((self.directory(result)/'attempts/1/outcome.json').exists())

    def test_current_base_change_refuses_before_another_client_call(self):
        first=Client(lambda packet:b'{}');self.run_request(first)
        (self.root/'rounds/current_verified.json').write_bytes(b'changed')
        resumed=Client()
        with self.assertRaises(AssertionError):self.run_request(resumed,True)
        self.assertEqual(resumed.calls,0)

    def native_client(self):
        from whetstone.vnext_native_editor import NativePatchProposalClient
        self.store.close();f=self.fixture.c.f
        f.original.review['editor']={'name':'codex','version':'scripted-1','model':'scripted-model'}
        f.original.review_ref=f.save(f.original.review_ref['path'],f.original.review)
        f.job['review_configuration_hash']=f.original.review_ref['hash'];f.rebind()
        self.initialize_store('native-request-store')
        command=Path(self.fixture.c.tmp.name)/'native-editor';count=command.with_name('native-count')
        source_root=Path('src').resolve();test_root=Path('tests').resolve()
        command.write_text(f'''#!{sys.executable}
import json,sys
from pathlib import Path
sys.path[:0]=[{str(source_root)!r},{str(test_root)!r}]
from test_vnext_unit_preflight import Client
prompt=sys.stdin.read();packet=json.loads(prompt.splitlines()[-1])
counter=Path({str(count)!r});n=int(counter.read_text())+1 if counter.exists() else 1;counter.write_text(str(n))
response=json.loads(Client().propose(prompt));response['patch']['editor']=packet['editor']
raw=b'{{}}' if n==1 else json.dumps(response).encode()
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_bytes(raw)
print('tokens used\\n23')
''')
        command.chmod(0o700)
        client=NativePatchProposalClient(review=f.original.review,command=str(command),cwd=command.parent,timeout_seconds=5)
        return client,count

    def test_native_scripted_editor_flows_through_durable_shape_retry_and_telemetry(self):
        client,count=self.native_client()
        result=self.run_request(client)
        self.assertEqual((result.status,result.attempts),('complete',2));self.assertEqual(count.read_text(),'2')
        self.assertEqual(self.read(result,'attempts/2/telemetry.json')['usage']['total_tokens'],23)
        again=self.run_request(client);self.assertEqual(again.reference,result.reference);self.assertEqual(count.read_text(),'2')


if __name__=='__main__':unittest.main()
