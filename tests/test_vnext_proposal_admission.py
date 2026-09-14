from copy import deepcopy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone import vnext_registry
from whetstone.vnext_contracts import (canonical_json_bytes, derive_job_id, sha256_bytes,
    validate_contract_suite, validate_job_descriptor)
from whetstone.vnext_proposal_admission import ProposalAdmission, initialize_proposal_storage
from whetstone.vnext_proposal_handoff import register_completed_proposal_request
from whetstone.vnext_proposal_requests import run_proposal_request
from whetstone.vnext_local_storage import initialize_storage,LocalAuthorityStore
from whetstone.vnext_validation import ArtifactReader
from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_discovery import discovery_rules
from whetstone.vnext_inventory import seed_inventory
from whetstone.vnext_identity import response_id
from whetstone.vnext_unit_authorization import unit_decision_request
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from vnext_consuming_suite_fixture import consuming_suite
import test_vnext_unit_preflight as fixtures
from test_vnext_proposal_requests import Client
from vnext_fixtures import STAMP,Bundle


class SuiteDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.suite,self.path,self.algorithms=consuming_suite(self,self.tmp.name)
        self.bundle=Bundle(Path(self.tmp.name)/'inputs',self.suite,mode='proposal_only')
        self.job={**deepcopy(self.bundle.job),**self.algorithms}
        self.job['job_id']=derive_job_id(self.job,self.suite.digest)

    def test_descriptor_selects_registered_algorithm_versions(self):
        validate_job_descriptor(self.job,self.suite)
        for field in self.algorithms:
            changed=deepcopy(self.job);changed[field]='unregistered-algorithm'
            changed['job_id']=derive_job_id(changed,self.suite.digest)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'algorithm version'):
                validate_job_descriptor(changed,self.suite)
        with self.assertRaisesRegex(ValueError,'suite version mismatch'):
            validate_job_descriptor(self.job,validate_contract_suite())

    def test_registered_digest_without_algorithm_dispatch_cannot_admit_job(self):
        del vnext_registry.SUITE_ALGORITHM_VERSIONS[self.suite.version]
        with self.assertRaisesRegex(ValueError,'algorithm dispatch'):validate_job_descriptor(self.job,self.suite)

    def test_mutated_cached_suite_or_changed_pins_do_not_create_trust(self):
        self.suite.manifest['suite_digest']='f'*64
        validate_job_descriptor(self.job,self.suite)  # Disk and registry remain authoritative.
        schema=self.suite.root/'schemas/mutation_plan_v2.schema.json'
        schema.write_bytes(schema.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'pinned file digest'):validate_job_descriptor(self.job,self.suite)

    def test_callback_reader_rejects_paths_before_invoking_storage(self):
        calls=[];reader=ArtifactReader(None,self.suite,read=lambda path:calls.append(path))
        for path in ('/outside','../outside','a/../b','a//b','a\\b',''):
            with self.subTest(path=path),self.assertRaises(ValueError):reader.raw({'path':path,'hash':'a'*64})
        self.assertEqual(calls,[])


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class ProposalAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.UnitPreflightTests.setUpClass()
    def setUp(self):
        self.fixture=fixtures.UnitPreflightTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.f=self.fixture.c.f
        self.suite,self.path,algorithms=consuming_suite(self,Path(self.fixture.c.tmp.name)/'consumer')
        f.suite=self.fixture.c.suite=self.suite
        f.job.update(contract_suite_version=self.suite.version,**algorithms);f.rebind()
        self.record=dict(schema_version='vnext-proposal-round-input-v1',job_id=f.job['job_id'],round_number=1,
            base_pointer=f.pointer_ref,feedback=f.feedback_ref,advice=f.advice_ref,
            decision_refs=[],constraints=f.constraints)
        self.record_ref=f.save('inputs/proposal-round-1.json',self.record)
        self.root=Path(self.fixture.c.tmp.name)/'admitted-run'
        artifacts={p.relative_to(f.root).as_posix():p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        initialize_storage(self.root,job_id=f.job['job_id'],descriptor_ref=f.job_ref,artifacts=artifacts)
        self.store=LocalAuthorityStore(self.root,job_id=f.job['job_id']);self.addCleanup(self.store.close)
        self.admission=self.make_admission()

    def make_admission(self,**overrides):
        f=self.f
        return ProposalAdmission(self.store,**{**dict(suite_path=self.path,descriptor_ref=f.job_ref,
            review_ref=f.original.review_ref,seed_map_ref=f.map_ref,round_refs={1:self.record_ref}),**overrides})

    def run_request(self,client,admission=None):
        admitted=admission or self.admission
        return run_proposal_request(self.store,load_inputs=lambda read:admitted.load_inputs(read,1),
            validate_authority=admitted.validate_authority,client=client)

    def test_retained_inputs_admit_request_and_registration_without_fixture_callbacks(self):
        client=Client();result=self.run_request(client)
        self.assertEqual((result.status,client.calls),('complete',1))
        registered=register_completed_proposal_request(self.store,round_number=1,
            load_inputs=self.admission.load_inputs,validate_authority=self.admission.validate_authority,created_at=STAMP)
        self.assertEqual(registered['candidate_creation_ordinal'],1)
        again=Client();self.assertEqual(self.run_request(again).status,'complete');self.assertEqual(again.calls,0)
        self.assertEqual(self.store.read('rounds/current_verified.json'),self.store.read(self.f.pointer_ref['path']))

    def test_changed_round_or_reviewer_evidence_refuses_before_client(self):
        for path in (self.record_ref['path'],self.f.feedback_ref['path'],self.f.advice_ref['path']):
            target=self.root/path;raw=target.read_bytes();target.write_bytes(raw+b' ')
            client=Client()
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'hash mismatch'):self.run_request(client)
            self.assertEqual(client.calls,0);target.write_bytes(raw)

    def test_wrong_round_and_base_are_rejected_even_with_rehashed_input_record(self):
        for key,value in [('round_number',2),('base_pointer',{'path':'rounds/current_verified.json','hash':self.f.pointer_ref['hash']})]:
            packet={**deepcopy(self.record),key:value};raw=canonical_json_bytes(packet)
            (self.root/self.record_ref['path']).write_bytes(raw)
            ref={**self.record_ref,'hash':sha256_bytes(raw)};admission=self.make_admission(round_refs={1:ref})
            client=Client()
            with self.subTest(key=key),self.assertRaises(ValueError):self.run_request(client,admission)
            self.assertEqual(client.calls,0)

    def test_promoted_or_changed_current_pointer_cannot_be_reseeded(self):
        target=self.root/'rounds/current_verified.json';target.write_bytes(b'{}')
        client=Client()
        with self.assertRaisesRegex(ValueError,'current committed seed pointer'):self.run_request(client)
        self.assertEqual(client.calls,0)

    def test_suite_tamper_and_unregistered_suite_refuse_before_client(self):
        del vnext_registry.SUPPORTED_SUITES[self.suite.version]
        client=Client()
        with self.assertRaisesRegex(ValueError,'registry digest'):self.run_request(client)
        self.assertEqual(client.calls,0)

    def save_input(self,path,packet):
        raw=canonical_json_bytes(packet);(self.root/path).write_bytes(raw)
        return {'path':path,'hash':sha256_bytes(raw)}

    def unit_decision(self):
        f=self.f;advice=deepcopy(f.advice);advice['findings'][0]['requested_effects']=['weaken']
        advice_ref=self.save_input('inputs/advice.json',advice)
        findings,evidence=classify_feedback(**{**f.classification_arguments(),'advice':advice})
        finding=findings[0];inventory=seed_inventory(f.base,f.mapping,f.job,rules=discovery_rules(f.invariants))
        unit=next(u for u in inventory['units'] if u['normative'] and u['owning_section_id'] in finding['target_section_ids'])
        request=unit_decision_request(job=f.job,base_hash=sha256_bytes(f.base),finding=finding,
            targets=finding['target_section_ids'],feedback_refs=evidence[finding['finding_id']]['feedback_refs'],
            inventory=inventory,section_map=f.mapping,options=[dict(option_id='named_weaken',description='Fictional approval.',
                authorized_effects=['weaken'],authorized_deletion_unit_ids=[],
                authorized_unit_effects=[dict(unit_id=unit['unit_id'],effects=['weaken'])])])
        request_ref=self.save_input('inputs/request.json',request)
        response=dict(schema_version='operator-decision-response-v1',job_id=f.job['job_id'],response_id='',
            decision_id=request['decision_id'],decision_request_hash=request_ref['hash'],base_draft_hash=sha256_bytes(f.base),
            authority_map_hash=f.job['authority_map_hash'],scope_contract_hash=f.job['scope_contract_hash'],
            selected_option_id='named_weaken',authorized_effects=['weaken'],authorized_deletion_unit_ids=[],
            rationale='Fictional selected unit.',decided_by='fixture operator',decided_at=STAMP)
        response['response_id']=response_id(response)
        response_ref=self.save_input('inputs/response.json',response)
        record={**deepcopy(self.record),'advice':advice_ref,'decision_refs':[
            dict(finding_id=finding['finding_id'],request=request_ref,response=response_ref)]}
        record_ref=self.save_input(self.record_ref['path'],record)
        return self.make_admission(round_refs={1:record_ref}),record,request,response,unit

    def test_named_unit_selection_is_reconstructed_from_exact_retained_decision(self):
        admission,_,_,response,unit=self.unit_decision()
        values=admission.load_inputs(self.store.read,1);preflight=prepare_unit_preflight(**values)
        self.assertEqual(preflight.bindings[0].units_for('weaken'),{unit['unit_id']})
        self.assertEqual(preflight.bindings[0].response,response)
        self.assertEqual(len(preflight.derived_tasks),1)
        client=Client();self.assertEqual(self.run_request(client,admission).status,'complete')

    def test_rehashed_request_cannot_reinterpret_existing_unit_approval(self):
        _,record,request,_,_=self.unit_decision()
        request['options'][0]['description']='A different decision request'
        record['decision_refs'][0]['request']=self.save_input('inputs/request.json',request)
        record_ref=self.save_input(self.record_ref['path'],record)
        client=Client()
        with self.assertRaisesRegex(ValueError,'identity, inventory or provenance'):
            self.run_request(client,self.make_admission(round_refs={1:record_ref}))
        self.assertEqual(client.calls,0)

    def test_registered_manifest_missing_consumer_schema_does_not_admit(self):
        import json
        manifest=json.loads(self.path.read_bytes())
        manifest['schemas']=[e for e in manifest['schemas'] if e['name']!='vnext_proposal_round_input_v1']
        manifest['suite_digest']=sha256_bytes(canonical_json_bytes({k:v for k,v in manifest.items() if k!='suite_digest'}))
        self.path.write_bytes(canonical_json_bytes(manifest))
        vnext_registry.SUPPORTED_SUITES[self.suite.version]=manifest['suite_digest']
        client=Client()
        # A removed schema may also be required transitively by a remaining
        # pinned consumer. Either gate must refuse before the client runs.
        with self.assertRaisesRegex(ValueError,'consumer schema|transitive schema reference is not pinned'):
            self.run_request(client)
        self.assertEqual(client.calls,0)

    def test_rehashed_seed_map_does_not_replace_reproduced_seed_lineage(self):
        import json
        packet=json.loads((self.root/self.f.map_ref['path']).read_bytes())
        packet['sections'][0]['heading_text']='Invented'
        raw=canonical_json_bytes(packet);(self.root/self.f.map_ref['path']).write_bytes(raw)
        ref={**self.f.map_ref,'hash':sha256_bytes(raw)}
        client=Client()
        with self.assertRaises(ValueError):self.run_request(client,self.make_admission(seed_map_ref=ref))
        self.assertEqual(client.calls,0)

    def staged(self, root, artifacts=None):
        f=self.f
        if artifacts is None:
            artifacts={p.relative_to(f.root).as_posix():p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        return initialize_proposal_storage(root,artifacts=artifacts,suite_path=self.path,
            descriptor_ref=f.job_ref,review_ref=f.original.review_ref,seed_map_ref=f.map_ref,round_refs={1:self.record_ref})

    def test_staged_package_initializes_new_root_and_runs_through_registration(self):
        destination=self.root.with_name('fresh-admitted-run')
        before={p.relative_to(self.f.root).as_posix():p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        store,admission=self.staged(destination);self.addCleanup(store.close)
        client=Client()
        result=run_proposal_request(store,load_inputs=lambda read:admission.load_inputs(read,1),
            validate_authority=admission.validate_authority,client=client)
        self.assertEqual((result.status,client.calls),('complete',1))
        event=register_completed_proposal_request(store,round_number=1,load_inputs=admission.load_inputs,
            validate_authority=admission.validate_authority,created_at=STAMP)
        self.assertEqual(event['candidate_creation_ordinal'],1)
        after={p.relative_to(self.f.root).as_posix():p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_bad_package_and_imported_runtime_evidence_refuse_before_root_creation(self):
        artifacts={p.relative_to(self.f.root).as_posix():p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        destination=self.root.with_name('invalid-stage')
        for key,value in [(self.f.feedback_ref['path'],b'{}'),('rounds/client_requests/imported/request.json',b'{}'),
                          ('inputs/../outside',b'{}')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.staged(destination,{**artifacts,key:value})
            self.assertFalse(destination.exists())

    def test_existing_empty_root_and_existing_reviewer_root_are_not_upgraded(self):
        destination=self.root.with_name('already-exists');destination.mkdir()
        for root in (destination,self.f.root):
            before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with self.subTest(root=root),self.assertRaises((ValueError,FileExistsError)):self.staged(root)
            after={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
