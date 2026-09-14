from copy import deepcopy
import unittest

from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import response_id
from whetstone.vnext_inventory import seed_inventory
from whetstone.vnext_inventory_diff import compare_inventory
from whetstone.vnext_mutation_admission import inspect_admission
from whetstone.vnext_plans import build_plan
from whetstone.vnext_section_lineage import candidate_section_map
from whetstone.vnext_unit_authorization import unit_decision_request, bind_unit_response, unit_effect_failures
from vnext_fixtures import STAMP
import test_vnext_patch_operations as operation_tests


class UnitAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):operation_tests.PatchOperationTests.setUpClass()
    def setUp(self):
        self.c=operation_tests.PatchOperationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        c=self.c
        c.f.base=b'# Queue\n\n## Timing\nQueue MUST wait.\nQueue MUST report.\n## Reports\nReport.\n'
        c.f.feedback['feedback'][0]['recommended_change']='Weaken only the waiting requirement.'
        c.f.hint['requested_effects']=['weaken'];c.f.rebind()
        c.a=inspect_admission(c.f.root,**c.inputs());c.target=next(s for s in c.a.mapping['sections'] if s['heading_text']=='Timing')
        self.inventory=seed_inventory(c.a.base,c.a.mapping,c.a.job);self.finding=c.a.findings[0]
        self.normative=[u for u in self.inventory['units'] if u['normative']]
        self.arguments=dict(job=c.a.job,base_hash=sha256_bytes(c.a.base),finding=self.finding,
            targets=self.finding['target_section_ids'],feedback_refs=[c.f.feedback_ref],inventory=self.inventory,section_map=c.a.mapping)
        self.options=[{'option_id':'weaken_wait','description':'Permit only the named wait unit to become SHOULD.',
            'authorized_effects':['weaken'],'authorized_deletion_unit_ids':[],
            'authorized_unit_effects':[{'unit_id':self.normative[0]['unit_id'],'effects':['weaken']}]}]
        self.prepare_binding()
    def prepare_binding(self):
        c=self.c;self.request=unit_decision_request(options=self.options,**self.arguments)
        self.response={'schema_version':'operator-decision-response-v1','job_id':c.a.job['job_id'],'response_id':'',
            'decision_id':self.request['decision_id'],'decision_request_hash':sha256_bytes(canonical_json_bytes(self.request)),
            'base_draft_hash':sha256_bytes(c.a.base),'authority_map_hash':c.a.job['authority_map_hash'],
            'scope_contract_hash':c.a.job['scope_contract_hash'],'selected_option_id':self.request['options'][0]['option_id'],
            'authorized_effects':self.request['options'][0]['authorized_effects'],
            'authorized_deletion_unit_ids':self.request['options'][0]['authorized_deletion_unit_ids'],
            'rationale':'Explicit fictional unit-level approval.','decided_by':'fixture operator','decided_at':STAMP}
        self.response['response_id']=response_id(self.response)
        self.binding=bind_unit_response(self.response,self.request,**self.arguments,suite=c.suite)
        decision={'finding_id':self.finding['finding_id'],'request':self.request,'response':self.response,'feedback_refs':[c.f.feedback_ref]}
        c.plan,_,responses=build_plan(job=c.a.job,authority=c.a.authority,section_map=c.a.mapping,
            findings=[self.finding],constraints=c.f.constraints,suite=c.suite,decisions=[decision],unit_inventory=self.inventory)
        c.responses=[r for r,_ in responses]
    def evaluate(self,payload,*,kind='replace_section_body',bindings=None):
        c=self.c;proposal=c.prepare(c.packet(kind,payload))
        assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        mapping=candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,assembled=assembled)
        diff=compare_inventory(base=c.a.base,base_map=c.a.mapping,base_inventory=self.inventory,
            proposal=proposal,assembled=assembled,candidate_map=mapping)
        return unit_effect_failures(diff=diff,base_inventory=self.inventory,proposal=proposal,plan=c.plan,
            bindings=[self.binding] if bindings is None else bindings)

    def test_exact_weakening_grant_does_not_grant_removal_or_weaken_another_unit(self):
        self.assertEqual(self.binding.units_for('weaken'),{self.normative[0]['unit_id']})
        self.assertEqual(self.binding.units_for('remove'),set())
        self.assertEqual(self.evaluate(b'Queue SHOULD wait.\nQueue MUST report.\n'),[])
        failures=self.evaluate(b'Queue MUST wait.\nQueue SHOULD report.\n')
        self.assertEqual(failures[0]['code'],'unauthorized_weaken')
        self.assertEqual(failures[0]['unit_ids'],[self.normative[1]['unit_id']])
        failures=self.evaluate(b'Queue MUST report.\n')
        self.assertEqual(failures[0]['code'],'unauthorized_remove')

    def test_exact_removal_grants_cover_the_inventory_units_and_deletion_projection(self):
        keys=[u['unit_id'] for u in self.inventory['units'] if u['owning_section_id']==self.c.target['stable_section_id'] and u['protected']]
        self.options=[{'option_id':'remove_timing','description':'Remove these exact timing units.',
            'authorized_effects':['remove'],'authorized_deletion_unit_ids':keys,
            'authorized_unit_effects':[{'unit_id':key,'effects':['remove']} for key in keys]}]
        self.prepare_binding()
        self.assertEqual(self.evaluate(None,kind='delete_section_subtree'),[])

    def test_unknown_foreign_duplicate_and_unitless_sensitive_grants_refuse(self):
        foreign=next(u['unit_id'] for u in self.inventory['units'] if u['owning_section_id']==self.c.a.mapping['sections'][-1]['stable_section_id'])
        for key in ['unit_'+'f'*64,foreign]:
            options=deepcopy(self.options);options[0]['authorized_unit_effects'][0]['unit_id']=key
            with self.subTest(key=key),self.assertRaises(ValueError):unit_decision_request(options=options,**self.arguments)
        options=deepcopy(self.options);options[0]['authorized_unit_effects']*=2
        with self.assertRaisesRegex(ValueError,'duplicate'):unit_decision_request(options=options,**self.arguments)
        options=deepcopy(self.options);options[0]['authorized_unit_effects']=[]
        with self.assertRaisesRegex(ValueError,'named units'):unit_decision_request(options=options,**self.arguments)

    def test_inventory_drift_or_retargeted_request_invalidates_an_old_selection(self):
        inventory=deepcopy(self.inventory);inventory['units'][0]['features'].append('changed')
        with self.assertRaisesRegex(ValueError,'inventory or provenance'):
            bind_unit_response(self.response,self.request,**{**self.arguments,'inventory':inventory},suite=self.c.suite)
        options=deepcopy(self.options);options[0]['authorized_unit_effects'][0]['unit_id']=self.normative[1]['unit_id']
        request=unit_decision_request(options=options,**self.arguments)
        with self.assertRaisesRegex(ValueError,'stale'):
            bind_unit_response(self.response,request,**self.arguments,suite=self.c.suite)

    def test_mutating_or_omitting_a_bound_response_cannot_pass_effect_validation(self):
        with self.assertRaisesRegex(ValueError,'complete decision bindings'):
            self.evaluate(b'Queue SHOULD wait.\nQueue MUST report.\n',bindings=[])
        self.binding.response['rationale']='Changed after binding.'
        with self.assertRaisesRegex(ValueError,'response changed'):
            self.evaluate(b'Queue SHOULD wait.\nQueue MUST report.\n')

    def test_v1_request_cannot_be_reinterpreted_as_a_named_unit_grant(self):
        from whetstone.vnext_decisions import decision_request
        legacy=decision_request(options=[{k:v for k,v in self.options[0].items() if k!='authorized_unit_effects'}],
            **{k:v for k,v in self.arguments.items() if k not in {'inventory','section_map'}})
        with self.assertRaises(ValueError):bind_unit_response(self.response,legacy,**self.arguments,suite=self.c.suite)

if __name__=='__main__':unittest.main()
