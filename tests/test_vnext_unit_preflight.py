from copy import deepcopy
import json
from pathlib import Path
import unittest

from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_candidate_validation import assess_candidate
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_discovery import discovery_rules
from whetstone.vnext_identity import assertion_id
from whetstone.vnext_section_lineage import candidate_section_map
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_unit_protocol import exercise_unit_proposal
from whetstone.vnext_validation import validate_bootstrap
from vnext_fixtures import ACTOR
import test_vnext_patch_operations as operation_tests
import test_vnext_unit_authorization as authorization_tests


class Client:
    def __init__(self,callback=None):self.calls=0;self.callback=callback;self.prompts=[]
    def propose(self,prompt):
        self.calls+=1;self.prompts.append(prompt)
        packet=json.loads(prompt.splitlines()[-1]);plan=packet['mutation_plan'];target=packet['target_sections'][0]
        content='Queue always waits before starting.\n'
        findings=[f['finding_id'] for f in packet['admitted_findings']]
        op={'operation_id':'edit','operation_type':'replace_section_body','target_stable_section_id':target['stable_section_id'],
            'expected_target_hash':target['section_hash'],'payload':{'path':'edit.md','hash':sha256_bytes(content.encode())},
            'addressed_finding_ids':findings,'reason':'Fictional clarification.','normative_change':'clarification',
            'preserve_target_identity':True,'depends_on_operation_ids':[],'unit_correspondence':[]}
        patch={'schema_version':'patch-set-v2','job_id':plan['job_id'],'transaction_id':plan['transaction_id'],'proposal_id':None,
            'base_draft_hash':plan['base_draft_hash'],'mutation_plan_hash':packet['mutation_plan_hash'],'editor':ACTOR,
            'operations':[op],'declined_findings':[],'editor_claims':{'addressed_finding_ids':findings,'normative_change_summary':'Fixture only.'}}
        response={'schema_version':'vnext-proposal-response-v2','patch':patch,'payloads':[{'path':'edit.md','content':content}]}
        if self.callback is not None:return self.callback(response)
        return canonical_json_bytes(response)


class UnitPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):operation_tests.PatchOperationTests.setUpClass()
    def setUp(self):
        self.c=operation_tests.PatchOperationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        f=self.c.f
        f.base=b'Preamble MUST remain.\n# Queue\n## Timing\nQueue always waits.\n## Reports\nReport.\n'
        f.invariants.update(schema_version='protected-invariants-v2',discovery_rules=[
            {'rule_id':'wait','text':'always waits','normative':True,'kind':'normative_pattern'}])
        f.rebind()
        self.directory=Path(self.c.tmp.name)/'unit-exercise'
    def inputs(self):
        f=self.c.f
        return dict(job=f.job,authority=f.authority,invariants=f.invariants,seed=f.base,seed_map=f.mapping,
            base=f.base,base_map=f.mapping,review=f.original.review,feedback=f.feedback,feedback_ref=f.feedback_ref,
            advice=f.advice,constraints=f.constraints,context={},suite=self.c.suite,base_pointer_ref=f.pointer_ref)

    def test_full_inventory_rules_and_actual_findings_are_frozen_before_client(self):
        before=self.c.f.root.joinpath('rounds/current_verified.json').read_bytes()
        client=Client();preflight,proposal,reference=exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=client)
        self.assertEqual(client.calls,1)
        packet=json.loads(client.prompts[0].splitlines()[-1])
        self.assertEqual(packet['base_inventory'],preflight.inventory)
        self.assertEqual(packet['discovery_rules'],self.c.f.invariants['discovery_rules'])
        self.assertEqual(sum(u['byte_end']-u['byte_start'] for u in preflight.inventory['units'] if u['primary']),len(self.c.f.base))
        self.assertEqual(sum(u['normative'] for u in preflight.inventory['units']),2)
        self.assertEqual(packet['admitted_findings'][0]['source_findings'][0]['claim'],self.c.f.feedback['feedback'][0]['claim'])
        self.assertEqual(sha256_bytes((self.directory/reference['path']).read_bytes()),reference['hash'])
        assembled=assemble_bytes(base=self.c.f.base,section_map=self.c.f.mapping,plan=preflight.plan,proposal=proposal)
        mapping=candidate_section_map(base=self.c.f.base,base_map=self.c.f.mapping,proposal=proposal,assembled=assembled)
        assessment=assess_candidate(job=self.c.f.job,authority=self.c.f.authority,invariants=self.c.f.invariants,
            seed=self.c.f.base,seed_map=self.c.f.mapping,base=self.c.f.base,base_map=self.c.f.mapping,
            base_inventory=preflight.inventory,plan=preflight.plan,proposal=proposal,candidate_bytes=assembled.raw,candidate_map=mapping)
        self.assertEqual(assessment.report['result'],'pass')
        self.assertEqual(before,self.c.f.root.joinpath('rounds/current_verified.json').read_bytes())
        self.assertFalse((self.directory/'candidates').exists())

    def test_invalid_assertion_program_makes_zero_editor_calls(self):
        f=self.c.f
        assertion={'assertion_id':'','assertion_type':'identifier_present','target_scope':'document',
            'matcher':{'kind':'inventory_query','value':{'kind':'unknown','value':'wait'}},'enforcement':'deterministic',
            'severity':'blocking','rationale':'Fixture invalid query.','source_authority_binding_ids':[]}
        assertion['assertion_id']=assertion_id(sha256_bytes(f.base),assertion);f.invariants['assertions']=[assertion];f.rebind()
        client=Client()
        with self.assertRaisesRegex(ValueError,'unsupported inventory assertion'):
            exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=client)
        self.assertEqual(client.calls,0);self.assertFalse(self.directory.exists())

    def test_unbound_or_duplicate_discovery_rules_fail_before_client(self):
        f=self.c.f;client=Client();f.invariants['discovery_rules'][0]['text']='changed rule'
        with self.assertRaisesRegex(ValueError,'binding changed'):
            exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=client)
        f.invariants['discovery_rules']*=2;f.rebind()
        with self.assertRaisesRegex(ValueError,'duplicate'):
            exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=client)
        self.assertEqual(client.calls,0)

    def test_policy_and_role_gates_make_zero_calls(self):
        f=self.c.f;client=Client()
        f.hint['requested_effects']=['weaken'];f.rebind()
        with self.assertRaisesRegex(ValueError,'unresolved operator decisions'):
            exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=client)
        f.hint['requested_effects']=['clarification'];f.job['editing_mode']='reviewer_only';f.rebind()
        with self.assertRaisesRegex(ValueError,'prohibits Editor'):
            exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=client)
        self.assertEqual(client.calls,0)

    def test_mid_call_rule_drift_retains_raw_and_prevents_canonical_publication(self):
        def change(response):
            self.c.f.invariants['discovery_rules'][0]['text']='different'
            return canonical_json_bytes(response)
        with self.assertRaisesRegex(ValueError,'binding changed'):
            exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=Client(change))
        self.assertTrue((self.directory/'attempts/proposal-attempt-1.json').exists())
        self.assertTrue((self.directory/'attempts/failure-1.txt').exists())
        self.assertFalse((self.directory/'proposals').exists())

    def test_changed_plan_before_call_is_detected_without_invoking_editor(self):
        calls=0
        def load():
            nonlocal calls
            calls+=1
            if calls==2:self.c.f.constraints['max_changed_normative_units']+=1
            return self.inputs()
        client=Client()
        with self.assertRaisesRegex(ValueError,'changed before'):
            exercise_unit_proposal(self.directory,load_inputs=load,client=client)
        self.assertEqual(client.calls,0)
        self.assertTrue((self.directory/'attempts/failure-1.txt').exists())

    def test_bad_transport_and_timeout_are_retained_and_never_replayed(self):
        def malformed(response):response['payloads']*=2;return canonical_json_bytes(response)
        client=Client(malformed)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=client)
        self.assertTrue((self.directory/'attempts/proposal-attempt-1.json').exists())
        with self.assertRaises(FileExistsError):exercise_unit_proposal(self.directory,load_inputs=self.inputs,client=client)
        self.assertEqual(client.calls,1)
        def timeout(response):raise TimeoutError('fictional deadline')
        directory=self.directory.with_name('timeout');client=Client(timeout)
        with self.assertRaises(TimeoutError):exercise_unit_proposal(directory,load_inputs=self.inputs,client=client)
        self.assertTrue((directory/'attempts/failure-1.txt').exists())
        self.assertFalse((directory/'attempts/proposal-attempt-1.json').exists())

    def test_new_rule_content_changes_job_and_plan_without_upgrading_frozen_admission(self):
        first=prepare_unit_preflight(**self.inputs());old_job=self.c.f.job['job_id']
        self.c.f.invariants['discovery_rules'][0]['text']='Queue always';self.c.f.rebind()
        second=prepare_unit_preflight(**self.inputs())
        self.assertNotEqual(self.c.f.job['job_id'],old_job)
        self.assertNotEqual(second.plan['transaction_id'],first.plan['transaction_id'])
        with self.assertRaises(ValueError):
            validate_bootstrap(self.c.f.root,self.c.f.job_ref,self.c.suite,review_configuration_ref=self.c.f.original.review_ref)
        with self.assertRaisesRegex(ValueError,'job-bound'):
            discovery_rules(self.c.f.invariants,[])

    def test_candidate_base_cannot_be_silently_reseeded(self):
        inputs=self.inputs();inputs['base']=inputs['base']+b'Changed.\n'
        with self.assertRaisesRegex(ValueError,'committed inventory'):prepare_unit_preflight(**inputs)

    def test_exact_named_decision_reaches_the_editor_as_a_bound_derived_task(self):
        fixture=authorization_tests.UnitAuthorizationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        c=fixture.c;f=c.f
        decision={'finding_id':fixture.finding['finding_id'],'request':fixture.request,'response':fixture.response,
                  'feedback_refs':[f.feedback_ref]}
        arguments=dict(job=f.job,authority=f.authority,invariants=f.invariants,seed=f.base,seed_map=f.mapping,
            base=f.base,base_map=f.mapping,review=f.original.review,feedback=f.feedback,feedback_ref=f.feedback_ref,
            advice=f.advice,constraints=f.constraints,context={},suite=c.suite,base_pointer_ref=f.pointer_ref,
            base_inventory=fixture.inventory,decisions=[decision])
        preflight=prepare_unit_preflight(**arguments)
        packet=json.loads(preflight.prompt.splitlines()[-1])
        self.assertEqual(len(preflight.bindings),1)
        self.assertEqual(preflight.bindings[0].units_for('weaken'),{fixture.normative[0]['unit_id']})
        self.assertEqual(packet['operator_unit_decisions'][0]['request'],fixture.request)
        detail=packet['admitted_findings'][0]
        self.assertEqual(detail['original_finding_id'],fixture.finding['finding_id'])
        self.assertEqual(detail['finding_id'],fixture.binding.derived_finding_id)
        changed=deepcopy(arguments);changed['decisions'][0]['feedback_refs']=[{'path':'wrong','hash':'f'*64}]
        with self.assertRaisesRegex(ValueError,'source references changed'):prepare_unit_preflight(**changed)


if __name__=='__main__':unittest.main()
