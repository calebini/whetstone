"""Isolated registration over actual APFS, with scripted immutable inputs.

The fixture suite is intentionally not registered for public runtime admission.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from whetstone import vnext_identity as ids
from whetstone.vnext_assembly import ASSEMBLER_VERSION, NORMALIZATION_VERSION
from whetstone.vnext_candidate_registry import CandidateRegistry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS, VNextSchemaRegistry, canonical_json_bytes, decode_json, derive_job_id, sha256_bytes
from whetstone.vnext_inventory import INVENTORY_VERSION, seed_inventory
from whetstone.vnext_local_storage import LocalAuthorityStore, StorageBusy, StorageWriteError, initialize_storage
from whetstone.vnext_sections import seed_section_map
from whetstone.vnext_unit_proposals import build_unit_plan, payload_units, prepare_unit_patch
from vnext_fixtures import ACTOR, ISSUE, STAMP


class RegistrationFixture:
    def __init__(self,parent):
        self.root=parent/'run';self.payload_root=parent/'payload';self.payload_root.mkdir()
        self.base=b'# Queue\n\n## Timing\nQueue MUST wait.\nQueue MUST report.\n## Reports\nReport.\n'
        seed_ref={'path':'inputs/seed.md','hash':sha256_bytes(self.base)}
        binding={'path':seed_ref['path'],'content_hash':seed_ref['hash'],'role':'mutable_target','authority_scopes':['queue'],
            'effective_horizon':'current','mutable':True,'may_introduce_requirements':False}
        binding['binding_id']=ids.binding_id(binding)
        self.authority={'schema_version':'authority-map-v1','bindings':[binding],'precedence':[],
            'prospective_rules':{'report_ratification_delta':False,'introduce_compatibility_policy':'forbid'}}
        self.invariants={'schema_version':'protected-invariants-v1','base_draft_hash':seed_ref['hash'],'assertions':[]}
        self.review={'schema_version':'review-configuration-v1','workflow':'standard','review_mode':'horizontal',
            'profile_set':'stateful_system','profiles':[{'name':'structural_integrity','budget':1}],
            'reviewer':ACTOR,'editor':ACTOR,'verifier':ACTOR}
        self.job={'schema_version':'job-descriptor-v2','job_id':'','created_at':STAMP,'editing_mode':'proposal_only',
            'contract_suite_version':'isolated-registration-fixture-v1',**ALGORITHM_VERSIONS,
            'assembler_version':ASSEMBLER_VERSION,'normalization_version':NORMALIZATION_VERSION,'inventory_version':INVENTORY_VERSION,
            'seed_draft':seed_ref,'authority_map_path':'inputs/authority.json','authority_map_hash':sha256_bytes(canonical_json_bytes(self.authority)),
            'scope_contract_path':None,'scope_contract_hash':None,'protected_invariants_path':'inputs/invariants.json',
            'protected_invariants_hash':sha256_bytes(canonical_json_bytes(self.invariants)),
            'review_configuration_hash':sha256_bytes(canonical_json_bytes(self.review)),'source_spec':{'path':None,'expected_hash':None}}
        self.job['job_id']=derive_job_id(self.job,'0'*64)
        self.mapping=seed_section_map(self.base,self.job,binding['binding_id'])
        self.inventory=seed_inventory(self.base,self.mapping,self.job)
        self.pointer={'schema_version':'isolated-registry-seed-pointer','job_id':self.job['job_id'],'seed_hash':seed_ref['hash']}
        artifacts={'job_descriptor.json':canonical_json_bytes(self.job),'inputs/seed.md':self.base,
            'inputs/authority.json':canonical_json_bytes(self.authority),'inputs/invariants.json':canonical_json_bytes(self.invariants),
            'inputs/review.json':canonical_json_bytes(self.review),'inputs/sections.json':canonical_json_bytes(self.mapping),
            'inputs/inventory.json':canonical_json_bytes(self.inventory),'rounds/current_verified.json':canonical_json_bytes(self.pointer)}
        initialize_storage(self.root,job_id=self.job['job_id'],
            descriptor_ref={'path':'job_descriptor.json','hash':sha256_bytes(artifacts['job_descriptor.json'])},artifacts=artifacts)
        self.store=LocalAuthorityStore(self.root,job_id=self.job['job_id'])
        self.registry=CandidateRegistry(self.store,job=self.job,validate_authority=self.validate_authority,load_inputs=self.load_inputs)

    def validate_authority(self,read):
        assert read('job_descriptor.json')==canonical_json_bytes(self.job)
        assert read('rounds/current_verified.json')==canonical_json_bytes(self.pointer)
        assert read('inputs/seed.md')==self.base

    def load_inputs(self,read,round_number,proposal_id):
        mapping=decode_json(read('inputs/sections.json'));base=read('inputs/seed.md')
        return {'authority':decode_json(read('inputs/authority.json')),'invariants':decode_json(read('inputs/invariants.json')),
            'review':decode_json(read('inputs/review.json')),'seed':base,'seed_map':mapping,'base':base,'base_map':mapping,
            'base_inventory':decode_json(read('inputs/inventory.json'))}

    def prepare(self,round_number=1,payload=b'Queue MUST wait and report.\n',graph=True):
        target=next(s for s in self.mapping['sections'] if s['heading_text']=='Timing')
        findings=[{'finding_id':ISSUE,'source_feedback_ids':['fixture-feedback'],'classification':'editor_fixable',
                   'target_section_ids':[target['stable_section_id']]}]
        constraints={'allowed_operation_types':['replace_section_body'],'max_operations':1,'max_changed_sections':2,
            'max_changed_normative_units':10,'required_context_binding_ids':[self.authority['bindings'][0]['binding_id']]}
        plan,_,_=build_unit_plan(inventory=self.inventory,job=self.job,authority=self.authority,section_map=self.mapping,
            findings=findings,constraints=constraints,suite=SimpleNamespace(registry=VNextSchemaRegistry()))
        path=self.payload_root/'body.md';path.write_bytes(payload)
        units=payload_units(payload,job_id=self.job['job_id'],parser_version=self.job['parser_contract_version'])
        group={'base_unit_ids':[u['unit_id'] for u in self.inventory['units'] if u['primary'] and u['normative']],
            'payload_units':[{'kind':u['kind'],'ordinal':i+1,'content_hash':u['content_hash']}
                for i,u in enumerate(units) if u['primary'] and u['normative']]}
        packet={'schema_version':'patch-set-v2','job_id':self.job['job_id'],'transaction_id':plan['transaction_id'],'proposal_id':None,
            'base_draft_hash':sha256_bytes(self.base),'mutation_plan_hash':sha256_bytes(canonical_json_bytes(plan)),'editor':ACTOR,
            'operations':[{'operation_id':'one','operation_type':'replace_section_body','target_stable_section_id':target['stable_section_id'],
                'expected_target_hash':target['section_hash'],'payload':{'path':'body.md','hash':sha256_bytes(payload)},
                'addressed_finding_ids':[ISSUE],'reason':'Clarify both obligations.','normative_change':'clarification',
                'preserve_target_identity':True,'depends_on_operation_ids':[],'unit_correspondence':[group] if graph else []}],
            'declined_findings':[],'editor_claims':{'addressed_finding_ids':[ISSUE],'normative_change_summary':'Fixture claim.'}}
        proposal=prepare_unit_patch(canonical_json_bytes(packet),payload_root=self.payload_root,plan=plan,
            base=self.base,section_map=self.mapping,inventory=self.inventory,editor=ACTOR)
        prefix=f"rounds/round-{round_number}/proposals/{proposal.patch['proposal_id']}"
        with self.store.locked(self.validate_authority) as token:
            self.store.publish(token,f'rounds/round-{round_number}/mutation_plan.json',plan)
            self.store.publish(token,prefix+'/proposed_patch.json',proposal.patch)
            for name,raw in proposal.payloads.items():self.store.publish(token,prefix+'/'+name,raw)
        return {'round_number':round_number,'proposal_id':proposal.patch['proposal_id'],'created_at':STAMP}


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class CandidateRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.f=RegistrationFixture(Path(self.temp.name));self.addCleanup(self.f.store.close)

    def json(self,path):return json.loads((self.f.root/path).read_bytes())
    def save(self,path,value):(self.f.root/path).write_bytes(canonical_json_bytes(value))
    def interrupt(self,request,after):
        original=self.f.store.publish;calls=[]
        def interrupted(*args):
            result=original(*args);calls.append(args[1])
            if len(calls)==after:raise RuntimeError('scripted process stop')
            return result
        with patch.object(self.f.store,'publish',side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError,'scripted process stop'):self.f.registry.register(**request)
        return calls

    def test_registered_creation_is_unverified_and_replay_reuses_timestamp_and_ordinal(self):
        request=self.f.prepare();event=self.f.registry.register(**request)
        self.assertEqual(event['candidate_creation_ordinal'],1)
        initial=self.json(event['initial_disposition_event_path'])
        self.assertEqual(initial['new_disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(self.f.registry.inspect().latest,event)
        replay=self.f.registry.register(**{**request,'created_at':'2026-09-14T00:00:00Z'})
        self.assertEqual(replay,event);self.assertEqual(len(self.f.registry.inspect().events),1)
        self.assertEqual(self.json('rounds/current_verified.json'),self.f.pointer)
        self.assertFalse(list(self.f.root.rglob('draft_after.md')))

    def test_identical_candidate_in_another_round_reuses_original_registration(self):
        first=self.f.registry.register(**self.f.prepare())
        again=self.f.registry.register(**self.f.prepare(2))
        self.assertEqual(again,first)
        self.assertFalse((self.f.root/'rounds/round-2/candidates').exists())

    def test_latest_uses_creation_ordinal_not_round_timestamp_or_identifier(self):
        first=self.f.registry.register(**self.f.prepare(9))
        request=self.f.prepare(2,b'Queue MUST both wait and report.\n')
        second=self.f.registry.register(**{**request,'created_at':'2020-01-01T00:00:00Z'})
        self.assertEqual(second['candidate_creation_ordinal'],2)
        self.assertEqual(second['previous_creation_event_hash'],sha256_bytes(canonical_json_bytes(first)))
        self.assertEqual(self.f.registry.inspect().latest,second)

    def test_complete_orphan_is_not_latest_and_recovers_before_later_registration(self):
        request=self.f.prepare();self.interrupt(request,6)
        view=self.f.registry.inspect();self.assertIsNone(view.latest);self.assertEqual(len(view.orphans),1)
        later=self.f.prepare(2,b'Queue MUST both wait and report.\n')
        event=self.f.registry.register(**later)
        self.assertEqual(event['candidate_creation_ordinal'],2)
        view=self.f.registry.inspect();self.assertEqual(len(view.events),2);self.assertEqual(view.orphans,())
        self.assertEqual(view.events[0]['proposal_id'],request['proposal_id'])

    def test_all_registration_publication_prefixes_preserve_or_reconcile_evidence(self):
        for prefix in range(1,8):
            with self.subTest(prefix=prefix),TemporaryDirectory() as directory:
                f=RegistrationFixture(Path(directory));old=self.f;self.f=f
                try:
                    request=f.prepare();self.interrupt(request,prefix)
                    before={str(p.relative_to(f.root)):p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
                    if prefix<6:
                        with self.assertRaises((ValueError,FileNotFoundError)):f.registry.reconcile()
                        after={str(p.relative_to(f.root)):p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
                        self.assertEqual(before,after);self.assertIsNone(f.registry.inspect().latest)
                    else:
                        view=f.registry.reconcile();self.assertEqual(len(view.events),1);self.assertEqual(view.orphans,())
                        self.assertEqual(f.registry.register(**request),view.latest)
                finally:f.store.close();self.f=old

    def test_failed_deterministic_report_remains_registered_unverified(self):
        for round_number,payload,graph in [(1,b'Queue SHOULD wait and report.\n',True),(2,b'Queue MUST wait and report.\n',False)]:
            with self.subTest(round=round_number):
                event=self.f.registry.register(**self.f.prepare(round_number,payload,graph))
                directory=Path(event['candidate_path']).parent
                report=self.json(str(directory/'preservation_report.json'))
                self.assertEqual(report['result'],'fail')
                self.assertEqual(self.json(event['initial_disposition_event_path'])['new_disposition'],'CANDIDATE_UNVERIFIED')
                self.assertTrue((self.f.root/event['candidate_path']).is_file())
                if not graph:
                    self.assertIsNone(report['candidate_inventory_hash'])
                    self.assertFalse((self.f.root/directory/'preservation_inventory_candidate.json').exists())

    def test_committed_candidate_map_report_and_inventory_tampering_refuses(self):
        event=self.f.registry.register(**self.f.prepare());directory=Path(event['candidate_path']).parent
        for path in [event['candidate_path'],event['candidate_section_identity_map_path'],
                     str(directory/'preservation_report.json'),str(directory/'preservation_inventory_candidate.json')]:
            target=self.f.root/path;raw=target.read_bytes()
            try:
                target.write_bytes(raw+b' ')
                with self.subTest(path=path),self.assertRaises(ValueError):self.f.registry.inspect()
            finally:target.write_bytes(raw)

    def test_rehashed_preparation_cannot_make_altered_candidate_authoritative(self):
        event=self.f.registry.register(**self.f.prepare());directory=Path(event['candidate_path']).parent
        target=self.f.root/event['candidate_path'];target.write_bytes(target.read_bytes()+b'Unexpected.\n')
        prep_path=str(directory/'registration_preparation.json');prep=self.json(prep_path)
        for ref in prep['artifacts']:
            if ref['path']==event['candidate_path']:ref['hash']=sha256_bytes(target.read_bytes())
        self.save(prep_path,prep)
        with self.assertRaisesRegex(ValueError,'independent replay'):self.f.registry.inspect()

    def test_gap_alias_and_previous_hash_corruption_are_not_ordering_hints(self):
        self.f.registry.register(**self.f.prepare());self.f.registry.register(**self.f.prepare(2,b'Queue MUST both wait and report.\n'))
        path=self.f.root/'rounds/candidate_index/creation-1.json';raw=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(ValueError,'gap'):self.f.registry.inspect()
        path.write_bytes(raw);path.rename(path.with_name('creation-01.json'))
        with self.assertRaisesRegex(ValueError,'invalid creation journal'):self.f.registry.inspect()
        path.with_name('creation-01.json').rename(path)
        event=self.json('rounds/candidate_index/creation-2.json');event['previous_creation_event_hash']='f'*64
        event['creation_event_id']=ids.creation_id(event);self.save('rounds/candidate_index/creation-2.json',event)
        with self.assertRaises(ValueError):self.f.registry.inspect()

    def test_multiple_orphans_halt_without_selecting_by_enumeration(self):
        self.interrupt(self.f.prepare(),6)
        unrelated=self.f.root/'rounds/round-2/candidates'/('can_'+'f'*64);unrelated.mkdir(parents=True)
        self.assertEqual(len(self.f.registry.inspect().orphans),2)
        with self.assertRaisesRegex(ValueError,'multiple unresolved'):self.f.registry.reconcile()
        self.assertFalse((self.f.root/'rounds/candidate_index').exists())

    def test_wrong_orphan_ordinal_predecessor_or_initial_event_halts(self):
        self.interrupt(self.f.prepare(),6)
        directory=Path(self.f.registry.inspect().orphans[0]);path=str(directory/'registration_preparation.json')
        original=self.json(path)
        for key,value in [('candidate_creation_ordinal',2),('previous_creation_event_hash','f'*64)]:
            preparation=deepcopy(original);preparation['creation_event'][key]=value
            preparation['creation_event']['creation_event_id']=ids.creation_id(preparation['creation_event']);self.save(path,preparation)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'ordinal/predecessor'):self.f.registry.reconcile()
        self.save(path,original)
        initial=original['creation_event']['initial_disposition_event_path'];event=self.json(initial)
        event['new_disposition']='CANDIDATE_VERIFIED';event['event_id']=ids.disposition_id(event);self.save(initial,event)
        with self.assertRaises(ValueError):self.f.registry.reconcile()
        self.assertFalse((self.f.root/'rounds/candidate_index').exists())

    def test_competing_store_cannot_register_while_authority_is_held(self):
        request=self.f.prepare()
        with LocalAuthorityStore(self.f.root,job_id=self.f.job['job_id']) as other:
            registry=CandidateRegistry(other,job=self.f.job,validate_authority=self.f.validate_authority,load_inputs=self.f.load_inputs)
            with self.f.store.locked(self.f.validate_authority):
                with self.assertRaises(StorageBusy):registry.register(**request)
            self.assertEqual(registry.register(**request)['candidate_creation_ordinal'],1)

    def test_registration_commit_acknowledgement_loss_reuses_committed_event(self):
        request=self.f.prepare();original=self.f.store._tree.write
        def lost(relative,raw,**kwargs):
            result=original(relative,raw,**kwargs)
            if relative=='rounds/candidate_index/creation-1.json':
                from whetstone.vnext_local_storage import Publication
                raise StorageWriteError(Publication('outcome_requires_reconciliation',relative,result.hash),OSError('lost acknowledgement'))
            return result
        with patch.object(self.f.store._tree,'write',side_effect=lost):
            with self.assertRaises(StorageWriteError):self.f.registry.register(**request)
        self.assertIsNone(self.f.store._lock_fd)
        committed=self.f.registry.inspect().latest
        self.assertEqual(self.f.registry.register(**request),committed)
        self.assertEqual(len(self.f.registry.inspect().events),1)

    def test_uncertain_visible_creation_requires_successful_replay_barrier(self):
        request=self.f.prepare();original=os.link
        def lost(source,destination,**kwargs):
            original(source,destination,**kwargs)
            if destination=='creation-1.json':raise OSError('creation link acknowledgement lost')
        with patch('whetstone.vnext_local_storage.os.link',side_effect=lost):
            with self.assertRaises(StorageWriteError):self.f.registry.register(**request)
        event=self.f.registry.inspect().latest;self.assertIsNotNone(event)
        from whetstone import vnext_local_storage as kernel
        flush=kernel._full_flush
        def failed_barrier(fd):
            if os.fstat(fd).st_ino==(self.f.root/'rounds/candidate_index/creation-1.json').stat().st_ino:
                raise OSError('replayed creation barrier failed')
            return flush(fd)
        with patch.object(kernel,'_full_flush',side_effect=failed_barrier):
            with self.assertRaises(StorageWriteError) as error:self.f.registry.register(**request)
        self.assertEqual(error.exception.result.outcome,'outcome_requires_reconciliation')
        self.assertEqual(self.f.registry.register(**request),event)
        self.assertEqual(len(self.f.registry.inspect().events),1)

    def test_two_processes_register_in_one_contiguous_chain(self):
        requests=[self.f.prepare(),self.f.prepare(2,b'Queue MUST both wait and report.\n')]
        source='''import json,sys
from pathlib import Path
from test_vnext_candidate_registry import RegistrationFixture
from whetstone.vnext_candidate_registry import CandidateRegistry
from whetstone.vnext_local_storage import LocalAuthorityStore,StorageBusy
f=object.__new__(RegistrationFixture);f.root=Path(sys.argv[1])
f.job=json.loads((f.root/'job_descriptor.json').read_bytes())
f.base=(f.root/'inputs/seed.md').read_bytes()
f.pointer=json.loads((f.root/'rounds/current_verified.json').read_bytes())
request=json.loads(sys.argv[2]);sys.stdin.readline()
with LocalAuthorityStore(f.root,job_id=f.job['job_id']) as store:
 registry=CandidateRegistry(store,job=f.job,validate_authority=f.validate_authority,load_inputs=f.load_inputs)
 try:result={'event':registry.register(**request)}
 except StorageBusy:result={'busy':True}
 print(json.dumps(result))
'''
        environment=dict(os.environ);environment['PYTHONPATH']=str(Path('src').resolve())+os.pathsep+str(Path('tests').resolve())
        children=[]
        try:
            for request in requests:
                children.append(subprocess.Popen([sys.executable,'-c',source,str(self.f.root),json.dumps(request)],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment))
            for child in children:child.stdin.write(b'go\n');child.stdin.flush()
            results=[]
            for child in children:
                stdout,stderr=child.communicate(timeout=15)
                self.assertEqual(child.returncode,0,stderr.decode());results.append(json.loads(stdout))
            self.assertTrue(any('event' in result for result in results))
            for request,result in zip(requests,results):
                if result.get('busy'):self.f.registry.register(**request)
            view=self.f.registry.inspect()
            self.assertEqual([e['candidate_creation_ordinal'] for e in view.events],[1,2])
            self.assertEqual({e['proposal_id'] for e in view.events},{r['proposal_id'] for r in requests})
        finally:
            for child in children:
                if child.poll() is None:child.kill()
                child.communicate(timeout=5)

    def test_missing_storage_control_file_is_not_an_empty_journal(self):
        (self.f.root/'rounds/.vnext-authority.lock').unlink()
        with self.assertRaises(FileNotFoundError):self.f.registry.inspect()

    def test_frozen_suite_wrong_mode_and_wrong_algorithms_refuse_registration_adapter(self):
        for index,(key,value) in enumerate([('contract_suite_version','vnext-contracts-1'),
                ('editing_mode','reviewer_only'),('assembler_version','patch-assembler-v1')]):
            with self.subTest(key=key):
                job={**self.f.job,key:value};raw=canonical_json_bytes(job)
                root=self.f.root.parent/f'unsupported-{index}'
                initialize_storage(root,job_id=job['job_id'],descriptor_ref={'path':'job.json','hash':sha256_bytes(raw)},artifacts={'job.json':raw})
                with LocalAuthorityStore(root,job_id=job['job_id']) as store:
                    with self.assertRaises(ValueError):
                        CandidateRegistry(store,job=job,validate_authority=lambda read:None,load_inputs=lambda *args:None)

    def test_missing_committed_map_is_invalid_even_when_candidate_bytes_survive(self):
        event=self.f.registry.register(**self.f.prepare())
        (self.f.root/event['candidate_section_identity_map_path']).unlink()
        with self.assertRaises(FileNotFoundError):self.f.registry.reconcile()
        self.assertTrue((self.f.root/event['candidate_path']).is_file())

    def test_foreign_base_lineage_refuses_before_any_candidate_artifact(self):
        request=self.f.prepare();loader=self.f.load_inputs
        def foreign(*args):
            inputs=loader(*args);inputs['base_map']['job_id']='job_'+'f'*64
            return inputs
        self.f.registry.load_inputs=foreign
        with self.assertRaisesRegex(ValueError,'another job'):self.f.registry.register(**request)
        self.assertFalse((self.f.root/'rounds/round-1/candidates').exists())

    def test_changed_seed_authority_stops_before_candidate_mutation(self):
        request=self.f.prepare();self.save('rounds/current_verified.json',{'changed':True})
        with self.assertRaises(AssertionError):self.f.registry.register(**request)
        self.assertFalse((self.f.root/'rounds/round-1/candidates').exists())

    def test_storage_listing_is_confined_and_read_only(self):
        self.f.prepare();before={str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        self.f.registry.inspect();self.f.store.list_directory('rounds')
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()})
        (self.f.root/'rounds/outside').symlink_to(self.f.root.parent,target_is_directory=True)
        with self.assertRaises(ValueError):self.f.store.list_directory('rounds')


if __name__=='__main__':unittest.main()
