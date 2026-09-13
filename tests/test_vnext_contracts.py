"""Offline vNext conformance, without live clients or runtime promotion."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from whetstone.contracts import SchemaValidationError
from whetstone.vnext_contracts import (
    CONTRACT_ROOT, ContractSuiteError, IdentityRegistry, VNextSchemaRegistry,
    canonical_json_bytes, decode_json, derive_job_id, sha256_bytes, validate_contract_suite, validate_job_descriptor,
)
from whetstone.vnext_conformance import check_fixture
from whetstone import vnext_identity as ids
from whetstone import vnext_validation as checks
from vnext_fixtures import Bundle


class SuiteTests(unittest.TestCase):
    def test_published_suite_and_all_fixed_vectors(self):
        suite=validate_contract_suite()
        self.assertEqual(suite.version,'vnext-contracts-1')
        self.assertEqual(len(suite.manifest['schemas']),25)
        self.assertEqual(len(suite.manifest['fixtures']),52)

    def test_canonical_fixed_bytes_and_invalid_json(self):
        self.assertEqual(canonical_json_bytes({'z':[1,True,None],'a':'é'}),b'{"a":"\xc3\xa9","z":[1,true,null]}')
        for value in [1.5,float('inf'),float('nan'),{'bad':'\ud800'},{1:'bad'}]:
            with self.subTest(value=repr(value)),self.assertRaises(ValueError):canonical_json_bytes(value)
        for raw in [b'{"a":1,"a":2}',b'\xef\xbb\xbf{}',b'{"a":NaN}',b'{"a":1.5}',b'"\\ud800"']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):decode_json(raw)

    def test_suite_relocation_and_tampering(self):
        for change in ['none','schema','algorithm','fixture','missing','unknown_version','symlink']:
            with self.subTest(change=change),TemporaryDirectory() as tmp:
                root=Path(tmp)/'contracts';shutil.copytree(CONTRACT_ROOT,root)
                path=root/'suites/vnext-contracts-1.json';manifest=json.loads(path.read_bytes())
                if change in {'schema','algorithm','fixture'}:
                    group={'schema':'schemas','algorithm':'algorithms','fixture':'fixtures'}[change]
                    target=root/manifest[group][0]['path'];target.write_bytes(target.read_bytes()+b' ')
                if change=='missing':(root/manifest['fixtures'][0]['path']).unlink()
                if change=='unknown_version':
                    manifest['suite_version']='unknown';manifest['suite_digest']=sha256_bytes(canonical_json_bytes({k:v for k,v in manifest.items() if k!='suite_digest'}));path.write_bytes(canonical_json_bytes(manifest))
                if change=='symlink':
                    target=root/manifest['schemas'][0]['path'];raw=target.read_bytes();target.unlink();outside=Path(tmp)/'outside.json';outside.write_bytes(raw);target.symlink_to(outside)
                if change=='none':self.assertEqual(validate_contract_suite(path).digest,validate_contract_suite().digest)
                else:
                    with self.assertRaises((ValueError,OSError)):validate_contract_suite(path)

    def test_rehashed_manifest_cannot_replace_registered_suite(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/'contracts';shutil.copytree(CONTRACT_ROOT,root);path=root/'suites/vnext-contracts-1.json'
            m=json.loads(path.read_bytes());m['fixtures'].pop();m['suite_digest']=sha256_bytes(canonical_json_bytes({k:v for k,v in m.items() if k!='suite_digest'}));path.write_bytes(canonical_json_bytes(m))
            with self.assertRaisesRegex(ValueError,'registry digest'):validate_contract_suite(path)

    def test_schema_keyword_audit_and_typed_additional_properties(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            for key,value in [('maxLength',2),('oneOf',[{'type':'string'}]),('format','email')]:
                (root/'test.schema.json').write_text(json.dumps({'type':'string',key:value}))
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'unsupported'):VNextSchemaRegistry(root).validate('test','test')
            (root/'test.schema.json').write_text(json.dumps({'type':'object','additionalProperties':{'type':'integer','minimum':0}}))
            r=VNextSchemaRegistry(root);r.validate({'a':2},'test')
            for value in ['2',-1,True]:
                with self.assertRaises(SchemaValidationError):r.validate({'a':value},'test')

    def test_local_reference_uses_own_schema_and_json_pointer_escaping(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'local.schema.json').write_text(json.dumps({'$defs':{'a/b~c':{'const':True}},'$ref':'#/$defs/a~1b~0c'}))
            r=VNextSchemaRegistry(root);r.validate(True,'local')
            with self.assertRaises(SchemaValidationError):r.validate(1,'local')

    def test_utc_timestamps_are_strict_even_through_shared_definitions(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'time.schema.json').write_text(json.dumps({'type':'string','format':'date-time'}))
            registry=VNextSchemaRegistry(root);registry.validate('2026-09-13T00:00:00Z','time')
            for value in ['2026-09-13','2026-09-13T00:00:00+00:00','2026-09-13T00:00:00.1Z','2026-02-30T00:00:00Z']:
                with self.subTest(value=value),self.assertRaises(SchemaValidationError):registry.validate(value,'time')

    def test_negative_vector_must_reject_and_expected_output_must_match(self):
        r=VNextSchemaRegistry()
        vector={'name':'deliberate-mismatch','operation':'canonical','input':{'a':1},'expected_result':'reject','expected':None}
        with self.assertRaisesRegex(ValueError,'negative.*accepted'):check_fixture(vector,r)
        vector.update(expected_result='pass',expected='wrong')
        with self.assertRaisesRegex(ValueError,'output mismatch'):check_fixture(vector,r)

    def test_identity_registry_replay_and_role_collision(self):
        preimage=['domain','é',None];identifier='example_'+sha256_bytes(canonical_json_bytes(preimage));registry=IdentityRegistry()
        registry.record('job',identifier,'example',preimage);registry.record('job',identifier,'example',preimage)
        with self.assertRaisesRegex(ValueError,'collision'):registry.record('job',identifier,'different',preimage)
        with self.assertRaisesRegex(ValueError,'preimage'):registry.record('job',identifier,'example',['other'])


class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.suite=validate_contract_suite()

    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.b=Bundle(self.root,self.suite)
        self.reader=checks.ArtifactReader(self.root,self.suite)

    def test_all_fixture_artifact_shapes(self):
        for name,value in vars(self.b).items():
            if isinstance(value,dict) and 'schema_version' in value:
                with self.subTest(name=name):self.suite.registry.validate(value,value['schema_version'].replace('-','_'))

    def test_bootstrap_is_acyclic_and_descriptor_identity_ignores_locator_timestamp(self):
        b=self.b
        checks.validate_bootstrap(self.root,b.job_ref,self.suite,review_configuration_ref=b.review_ref)
        self.assertNotIn('job_id',b.authority);self.assertNotIn('job_id',b.invariants)
        changed=deepcopy(b.job);changed['created_at']='2030-01-01T00:00:00Z';changed['seed_draft']['path']='/another/host/seed.md'
        self.assertEqual(derive_job_id(changed,self.suite.digest),b.job['job_id']);validate_job_descriptor(changed,self.suite)
        changed['authority_map_hash']='f'*64
        with self.assertRaisesRegex(ValueError,'identity'):validate_job_descriptor(changed,self.suite)

    def test_nullable_pairs_algorithms_and_untrusted_digest_reject(self):
        for field in ['scope','source','algorithm']:
            changed=deepcopy(self.b.job)
            if field=='scope':changed['scope_contract_path']='scope.json'
            elif field=='source':changed['source_spec']['path']='external.md'
            else:changed['assembler_version']='installed-latest'
            changed['job_id']=derive_job_id(changed,self.suite.digest)
            with self.subTest(field=field),self.assertRaises(ValueError):validate_job_descriptor(changed,self.suite)
        with self.assertRaisesRegex(ValueError,'validated supported suite'):validate_job_descriptor(self.b.job,'e'*64)

    def test_bootstrap_rejects_changed_prejob_bytes_before_artifact_consumption(self):
        (self.root/self.b.review_ref['path']).write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):checks.validate_bootstrap(self.root,self.b.job_ref,self.suite,review_configuration_ref=self.b.review_ref)

    def test_closed_prejob_inputs_reject_job_backreference(self):
        for value in [self.b.authority,self.b.invariants,self.b.review]:
            with self.assertRaises(SchemaValidationError):self.suite.registry.validate({**value,'job_id':self.b.job['job_id']},value['schema_version'].replace('-','_'))

    def test_readonly_joined_candidate_verification_and_promotion_evidence(self):
        b=self.b;before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        reader,job,authority,invariants=checks.validate_bootstrap(self.root,b.job_ref,self.suite,review_configuration_ref=b.review_ref)
        sections=checks.validate_section_map(b.base_map,job,expected_hash=b.seed['hash'],seed_binding=b.binding['binding_id'])
        checks.validate_section_map(b.candidate_map,job,expected_hash=b.candidate_ref['hash'])
        admitted=checks.validate_plan(b.plan,job,authority,b.base_map,[])
        checks.validate_patch(b.patch,b.plan,sections,reader,proposal_directory=b.proposal_dir)
        checks.validate_reports(b.preservation,b.semantic,b.plan,job,b.candidate,b.candidate_map_ref,b.patch_ref['hash'],admitted,invariants,operations=b.patch['operations'])
        checks.validate_decision(b.decision,b.preservation,b.semantic,job)
        self.assertEqual(checks.validate_creation_chain(reader,b.index,job),[b.creation])
        events=checks.validate_disposition_chain(reader,[b.initial_ref,b.verification_event_ref,b.promotion_event_ref],b.creation)
        checks.validate_verification_pointer(b.verification_pointer,b.decision,b.decision_ref,events[1],b.verification_event_ref,b.creation)
        checks.validate_seed_pointer(b.seed_pointer,job,b.base_map_ref)
        self.promotion()
        checks.validate_terminal(b.terminal,b.pointer,b.creation,b.creation_ref,events[-1],b.promotion_event_ref,b.decision,b.decision_ref)
        self.assertEqual(before,{str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertFalse((self.root/'rounds/current_verified.json').exists())
        self.assertFalse((self.root/'rounds/run_state.json').exists())

    def test_mutation_admission_and_slice_coverage_reject(self):
        for change in ['classification','coverage','base','deletion']:
            p=deepcopy(self.b.plan)
            if change=='classification':p['finding_dispositions'][0]['classification']='operator_decision_required'
            elif change=='coverage':p['slices']=[]
            elif change=='base':p['base_draft_hash']='f'*64
            else:p['authorized_deletion_unit_ids']=['unit_'+'f'*64]
            p['transaction_id']=ids.transaction_id(p,{})
            self.suite.registry.validate(p,'mutation_plan_v1')
            with self.subTest(change=change),self.assertRaises(ValueError):checks.validate_plan(p,self.b.job,self.b.authority,self.b.base_map,[])

    def test_patch_rejects_stale_target_unadmitted_work_and_sensitive_claim(self):
        b=self.b;sections={s['stable_section_id']:s for s in b.base_map['sections']}
        for change in ['target','finding','weakening']:
            p=deepcopy(b.patch);op=p['operations'][0]
            if change=='target':op['expected_target_hash']='f'*64
            elif change=='finding':op['addressed_finding_ids']=['iss_'+'f'*16]
            else:op['normative_change']='weaken'
            op['operation_id']=ids.operation_id(b.plan['transaction_id'],op);p['proposal_id']=ids.proposal_id(p)
            directory='rounds/round-1/proposals/'+p['proposal_id'];b.save(directory+'/'+op['payload']['path'],b'Wait 30 seconds or longer.\n')
            self.suite.registry.validate(p,'patch_set_v1')
            with self.subTest(change=change),self.assertRaises(ValueError):checks.validate_patch(p,b.plan,sections,self.reader,proposal_directory=directory)

    def test_model_patch_labels_are_not_persisted_identifiers(self):
        p=deepcopy(self.b.patch);p['proposal_id']=None;p['operations'][0]['operation_id']='edit_a'
        self.suite.registry.validate(p,'patch_set_client_v1')
        with self.assertRaises(SchemaValidationError):self.suite.registry.validate(p,'patch_set_v1')
        p['proposal_id']=self.b.patch['proposal_id']
        with self.assertRaises(SchemaValidationError):self.suite.registry.validate(p,'patch_set_client_v1')

    def test_verifier_envelope_cannot_inject_persisted_bindings(self):
        schema=self.suite.registry.load('semantic_verification_client_v1');p={k:v for k,v in self.b.semantic.items() if k in schema['properties']}
        self.suite.registry.validate(p,'semantic_verification_client_v1')
        with self.assertRaises(SchemaValidationError):self.suite.registry.validate({**p,'candidate_hash':'f'*64},'semantic_verification_client_v1')

    def reports(self,semantic):
        b=self.b;checks.validate_reports(b.preservation,semantic,b.plan,b.job,b.candidate,b.candidate_map_ref,b.patch_ref['hash'],{b.plan['finding_dispositions'][0]['finding_id']},b.invariants,operations=b.patch['operations'])

    def test_schema_valid_semantic_coverage_and_uncertainty_fail_closed(self):
        for change in ['missing','duplicate','partial','uncertain','wrong_map']:
            s=deepcopy(self.b.semantic)
            if change=='missing':s['finding_results']=[]
            elif change=='duplicate':s['finding_results']*=2
            elif change=='partial':s['finding_results'][0]['disposition']='partially_resolved'
            elif change=='uncertain':s['lost_or_weakened_semantics']='uncertain'
            else:s['candidate_section_identity_map_hash']='f'*64
            self.suite.registry.validate(s,'semantic_verification_v1')
            with self.subTest(change=change),self.assertRaises(ValueError):self.reports(s)

    def test_uncertainty_rejection_has_exact_mapping(self):
        s=deepcopy(self.b.semantic);s.update(lost_or_weakened_semantics='uncertain',verdict='reject',uncertainty_resolutions=[{'field_path':'lost_or_weakened_semantics','policy_rule_id':'loss-default','disposition':'reject','decision_id':None}])
        self.reports(s)
        s['uncertainty_resolutions'][0]['disposition']='operator_decision_required';s['uncertainty_resolutions'][0]['decision_id']='decision';s['verdict']='operator_decision_required'
        with self.assertRaises(ValueError):self.reports(s)

    def test_verified_decision_requires_exact_semantic_evidence_and_mode(self):
        b=self.b
        with self.assertRaises(ValueError):checks.validate_decision(b.decision,b.preservation,None,b.job)
        with self.assertRaises(ValueError):checks.validate_decision(b.decision,b.preservation,b.semantic,{**b.job,'editing_mode':'proposal_only'})
        decision={**b.decision,'promotion_permitted':False}
        checks.validate_decision(decision,b.preservation,b.semantic,{**b.job,'editing_mode':'proposal_only'})

    def test_candidate_index_and_disposition_chains_reject_gaps(self):
        b=self.b;index=deepcopy(b.index);index['entries'][0]['candidate_creation_ordinal']=2
        with self.assertRaises(ValueError):checks.validate_creation_chain(self.reader,index,b.job)
        with self.assertRaises(ValueError):checks.validate_disposition_chain(self.reader,[b.initial_ref,b.promotion_event_ref],b.creation)

    def test_candidate_map_bytes_must_match_registration(self):
        (self.root/self.b.candidate_map_ref['path']).write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):checks.validate_creation_chain(self.reader,self.b.index,self.b.job)

    def test_candidate_identity_cannot_disagree_with_registered_patch(self):
        b=self.b;event=deepcopy(b.creation);event['candidate_id']='can_'+'f'*64;event['creation_event_id']=ids.creation_id(event)
        reference=b.save(b.creation_ref['path'],event);index=deepcopy(b.index);index['entries'][0].update(reference)
        with self.assertRaisesRegex(ValueError,'candidate identity'):checks.validate_creation_chain(self.reader,index,b.job)

    def test_operation_count_and_normative_assessment_coverage_are_exact(self):
        b=self.b;report=deepcopy(b.preservation);report['mutation_budget']['operations_observed']=0
        with self.assertRaisesRegex(ValueError,'operation count'):checks.validate_reports(report,None,b.plan,b.job,b.candidate,b.candidate_map_ref,b.patch_ref['hash'],{b.plan['finding_dispositions'][0]['finding_id']},b.invariants,operations=b.patch['operations'])
        semantic=deepcopy(b.semantic);semantic['normative_change_assessment']=[]
        with self.assertRaisesRegex(ValueError,'assessment coverage'):self.reports(semantic)

    def test_ratification_delta_cannot_invent_authority_or_operator_response(self):
        b=self.b;delta={'schema_version':'ratification-delta-v1','job_id':b.job['job_id'],'mutable_target_binding_id':b.binding['binding_id'],'target_draft_hash':b.seed['hash'],'compared_binding_ids':[],'deltas':[],'compatibility_policy':{'status':'not_needed','decision_response_id':None}}
        self.suite.registry.validate(delta,'ratification_delta_v1');checks.validate_ratification_delta(delta,b.job,b.authority,b.seed['hash'],{})
        delta['compared_binding_ids']=['bind_'+'f'*64]
        with self.assertRaises(ValueError):checks.validate_ratification_delta(delta,b.job,b.authority,b.seed['hash'],{})
        delta['compared_binding_ids']=[];delta['compatibility_policy']={'status':'authorized','decision_response_id':'resp_'+'f'*64}
        with self.assertRaises(ValueError):checks.validate_ratification_delta(delta,b.job,b.authority,b.seed['hash'],{})

    def test_current_pointer_requires_identical_ordinal_snapshot(self):
        b=self.b;ref=b.save('rounds/current_verified.json',b.seed_pointer)
        self.assertEqual(checks.validate_pointer_snapshot(self.reader,ref),b.seed_pointer)
        changed={**b.seed_pointer,'promoted_at':'2026-09-14T00:00:00Z'};b.save(b.seed_pointer_ref['path'],changed)
        with self.assertRaisesRegex(ValueError,'same-ordinal'):checks.validate_pointer_snapshot(self.reader,ref)

    def test_verification_pointer_cannot_swap_a_decision_or_event(self):
        b=self.b;p={**b.verification_pointer,'current_decision_hash':'f'*64}
        with self.assertRaises(ValueError):checks.validate_verification_pointer(p,b.decision,b.decision_ref,b.verification_event,b.verification_event_ref,b.creation)

    def promotion(self,pointer=None,intent=None,job=None):
        b=self.b;checks.validate_promotion(pointer or b.pointer,intent or b.intent,b.intent_ref,b.seed_pointer,b.seed_pointer_ref,b.creation,b.creation_ref,b.decision,b.decision_ref,b.promotion_event,b.promotion_event_ref,job or b.job)

    def test_promotion_pointer_predecessor_and_mode_cannot_be_substituted(self):
        for field in ['promotion_ordinal','previous_verified_pointer_hash','verified_section_identity_map_hash']:
            p=deepcopy(self.b.pointer);p[field]=2 if field=='promotion_ordinal' else 'f'*64
            self.suite.registry.validate(p,'current_verified_pointer_v1')
            with self.subTest(field=field),self.assertRaises(ValueError):self.promotion(pointer=p)
        with self.assertRaisesRegex(ValueError,'mode'):self.promotion(job={**self.b.job,'editing_mode':'proposal_only'})

    def test_terminal_cannot_take_unbound_prepared_event_as_effective(self):
        b=self.b
        with self.assertRaises(ValueError):checks.validate_terminal(b.terminal,b.seed_pointer,b.creation,b.creation_ref,b.verification_event,b.verification_event_ref,b.decision,b.decision_ref)

    def test_exact_canonical_artifacts_and_confined_paths(self):
        b=self.b;p=self.root/b.job_ref['path'];p.write_bytes(p.read_bytes()+b'\n');ref={'path':b.job_ref['path'],'hash':sha256_bytes(p.read_bytes())}
        with self.assertRaisesRegex(ValueError,'canonical'):self.reader.json(ref)
        for path in ['../outside','inputs/../job_descriptor.json']:
            with self.assertRaises(ValueError):self.reader.raw({'path':path,'hash':'f'*64})
        link=self.root/'alias.json';link.symlink_to(self.root/b.job_ref['path'])
        with self.assertRaisesRegex(ValueError,'symlink'):self.reader.raw({'path':'alias.json','hash':ref['hash']})


if __name__=='__main__':unittest.main()
