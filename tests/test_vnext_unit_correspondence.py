from copy import deepcopy
import unittest

from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_inventory import seed_inventory
from whetstone.vnext_inventory_diff import compare_inventory
from whetstone.vnext_section_lineage import candidate_section_map
from whetstone.vnext_unit_proposals import build_unit_plan, payload_units, prepare_unit_patch
from vnext_fixtures import ACTOR
import test_vnext_patch_operations as operation_tests


class UnitCorrespondenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):operation_tests.PatchOperationTests.setUpClass()
    def setUp(self):
        self.c=operation_tests.PatchOperationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.base(b'# Queue\n\n## Timing\nQueue MUST wait.\nQueue MUST report.\n## Reports\nReport.\n')
    def base(self,raw):
        c=self.c;c.f.base=raw
        c.f.feedback['feedback'][0].update(claim='The waiting and reporting obligations need a concise statement.',
            recommended_change='Clarify both obligations without changing them.')
        c.f.rebind();c.refresh();self.inventory=seed_inventory(raw,c.a.mapping,c.a.job)
        self.plan_args=dict(job=c.a.job,authority=c.a.authority,section_map=c.a.mapping,
            findings=c.a.findings,constraints=c.f.constraints,suite=c.suite)
        c.plan,_,_=build_unit_plan(inventory=self.inventory,**self.plan_args)
    def group(self,payload):
        c=self.c;facts=payload_units(payload,job_id=c.a.job['job_id'],parser_version=c.a.mapping['parser_contract_version'])
        return {'base_unit_ids':[u['unit_id'] for u in self.inventory['units'] if u['primary'] and u['normative']],
                'payload_units':[{'kind':u['kind'],'ordinal':i+1,'content_hash':u['content_hash']}
                                 for i,u in enumerate(facts) if u['primary'] and u['normative']]}
    def packet(self,payload,group=None):
        packet=self.c.packet('replace_section_body',payload);packet['schema_version']='patch-set-v2'
        packet['operations'][0]['unit_correspondence']=[self.group(payload) if group is None else group]
        return packet
    def prepare(self,packet):
        c=self.c
        return prepare_unit_patch(canonical_json_bytes(packet),payload_root=c.payload_root,plan=c.plan,
            base=c.a.base,section_map=c.a.mapping,inventory=self.inventory,editor=ACTOR)
    def compare(self,packet):
        c=self.c;proposal=self.prepare(packet)
        assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        mapping=candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,assembled=assembled)
        diff=compare_inventory(base=c.a.base,base_map=c.a.mapping,base_inventory=self.inventory,proposal=proposal,
            assembled=assembled,candidate_map=mapping,plan=c.plan)
        return proposal,assembled,mapping,diff

    def test_many_to_one_is_structurally_bound_and_still_requires_semantic_evidence(self):
        packet=self.packet(b'Queue MUST wait and report.\n')
        proposal,assembled,_,diff=self.compare(packet)
        self.assertEqual(diff.failures,())
        group=next(d for d in diff.deltas if d.correspondence_group_id)
        self.assertEqual(len(group.base_unit_ids),2);self.assertEqual(len(group.candidate_unit_ordinals),1)
        self.assertTrue(group.semantic_obligation)
        self.assertEqual(len(diff.metrics.normative_unit_sections),2)
        self.assertIn(b'Queue MUST wait and report.',assembled.raw)
        reordered=deepcopy(packet);reordered['operations'][0]['unit_correspondence'][0]['base_unit_ids'].reverse()
        self.assertEqual(self.prepare(reordered).patch,proposal.patch)

    def test_one_to_many_is_an_explicit_group_without_double_counting_successors(self):
        self.base(b'# Queue\n\n## Timing\nQueue MUST wait and report.\n## Reports\nReport.\n')
        _,_,_,diff=self.compare(self.packet(b'Queue MUST wait.\nQueue MUST report.\n'))
        group=next(d for d in diff.deltas if d.correspondence_group_id)
        self.assertEqual((len(group.base_unit_ids),len(group.candidate_unit_ordinals)),(1,2))
        self.assertEqual(len(diff.metrics.normative_unit_sections),1)
        self.assertTrue(group.semantic_obligation)

    def test_a_correspondence_claim_does_not_hide_known_force_reduction(self):
        _,_,_,diff=self.compare(self.packet(b'Queue SHOULD wait and report.\n'))
        group=next(d for d in diff.deltas if d.correspondence_group_id)
        self.assertEqual(group.change,'weakened')
        self.assertTrue(group.semantic_obligation)

    def test_outside_reused_and_stale_endpoints_refuse_before_a_canonical_proposal(self):
        packet=self.packet(b'Queue MUST wait and report.\n')
        foreign=next(u['unit_id'] for u in self.inventory['units'] if u['owning_section_id']==self.c.a.mapping['sections'][-1]['stable_section_id'])
        bad=deepcopy(packet);bad['operations'][0]['unit_correspondence'][0]['base_unit_ids']=[foreign]
        with self.assertRaisesRegex(ValueError,'outside its operation'):self.prepare(bad)
        bad=deepcopy(packet);bad['operations'][0]['unit_correspondence']*=2
        with self.assertRaisesRegex(ValueError,'reused'):self.prepare(bad)
        bad=deepcopy(packet);bad['operations'][0]['unit_correspondence'][0]['payload_units'][0]['content_hash']='f'*64
        with self.assertRaisesRegex(ValueError,'selector differs'):self.prepare(bad)

    def test_inventory_lineage_and_correspondence_are_part_of_identity(self):
        packet=self.packet(b'Queue MUST wait and report.\n');first=self.prepare(packet)
        changed=deepcopy(packet);changed['operations'][0]['unit_correspondence'][0]['base_unit_ids'].pop()
        second=self.prepare(changed)
        self.assertNotEqual(first.patch['proposal_id'],second.patch['proposal_id'])
        self.assertNotEqual(first.patch['operations'][0]['operation_id'],second.patch['operations'][0]['operation_id'])
        inventory=deepcopy(self.inventory);old=inventory['units'][0]['unit_id'];new='unit_'+'f'*64
        for unit in inventory['units']:
            if unit['unit_id']==old:unit['unit_id']=new
            if unit['anchor_line_unit_id']==old:unit['anchor_line_unit_id']=new
        plan,_,_=build_unit_plan(inventory=inventory,**self.plan_args)
        self.assertNotEqual(plan['transaction_id'],self.c.plan['transaction_id'])

if __name__=='__main__':unittest.main()
