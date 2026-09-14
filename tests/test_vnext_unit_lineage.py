from copy import deepcopy
from unittest.mock import patch
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import inserted_unit_id
from whetstone.vnext_unit_lineage import candidate_inventory, validate_candidate_inventory, validate_inventory_facts
from whetstone.vnext_unit_proposals import build_unit_plan, payload_units, prepare_unit_patch
from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_section_lineage import candidate_section_map
from vnext_fixtures import ACTOR
import test_vnext_unit_correspondence as correspondence_tests


class UnitLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):correspondence_tests.UnitCorrespondenceTests.setUpClass()
    def setUp(self):
        self.fixture=correspondence_tests.UnitCorrespondenceTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        c=self.fixture.c
        self.base=c.a.base;self.mapping=c.a.mapping;self.inventory=self.fixture.inventory
    def produce(self,payload,*,group=True,operation='replace_section_body'):
        f=self.fixture;c=f.c
        plan,_,_=build_unit_plan(inventory=self.inventory,**{**f.plan_args,'section_map':self.mapping})
        packet=c.packet(operation,payload)
        packet.update(schema_version='patch-set-v2',transaction_id=plan['transaction_id'],
            base_draft_hash=sha256_bytes(self.base),mutation_plan_hash=sha256_bytes(canonical_json_bytes(plan)))
        op=packet['operations'][0]
        op['expected_target_hash']=next(s['section_hash'] for s in self.mapping['sections'] if s['stable_section_id']==op['target_stable_section_id'])
        facts=payload_units(payload,job_id=plan['job_id'],parser_version=self.mapping['parser_contract_version'])
        op['unit_correspondence']=[{
            'base_unit_ids':[u['unit_id'] for u in self.inventory['units'] if u['primary'] and u['normative']],
            'payload_units':[{'kind':u['kind'],'ordinal':i+1,'content_hash':u['content_hash']} for i,u in enumerate(facts) if u['primary'] and u['normative']]
        }] if group else []
        proposal=prepare_unit_patch(canonical_json_bytes(packet),payload_root=c.payload_root,plan=plan,
            base=self.base,section_map=self.mapping,inventory=self.inventory,editor=ACTOR)
        inputs=dict(base=self.base,base_map=self.mapping,base_inventory=self.inventory,plan=plan,proposal=proposal)
        inventory=candidate_inventory(**inputs)
        assembled=assemble_bytes(base=self.base,section_map=self.mapping,plan=plan,proposal=proposal)
        mapping=candidate_section_map(base=self.base,base_map=self.mapping,proposal=proposal,assembled=assembled)
        return inventory,assembled.raw,mapping,inputs

    def test_merge_retires_predecessors_and_mints_from_full_payload_ordinal(self):
        inventory,raw,mapping,inputs=self.produce(b'Queue MUST wait and report.\n')
        before={u['unit_id'] for u in self.inventory['units'] if u['normative']}
        after=next(u for u in inventory['units'] if u['normative'])
        op=inputs['proposal'].patch['operations'][0]
        self.assertEqual(after['unit_id'],inserted_unit_id(inputs['plan']['transaction_id'],op['operation_id'],after['kind'],1))
        self.assertEqual(set(inventory['retired_unit_ids']),before)
        self.assertTrue(before.isdisjoint({u['unit_id'] for u in inventory['units']}))
        self.assertEqual(inventory['seed_draft_hash'],self.inventory['seed_draft_hash'])
        validate_inventory_facts(inventory,raw,mapping)
        validate_candidate_inventory(inventory,**inputs)
        self.assertEqual(canonical_json_bytes(candidate_inventory(**inputs)),canonical_json_bytes(inventory))

    def test_split_on_next_generation_keeps_tombstones_and_never_reseeds(self):
        first,raw,mapping,_=self.produce(b'Queue MUST wait and report.\n')
        retired=set(first['retired_unit_ids']);merged=next(u['unit_id'] for u in first['units'] if u['normative'])
        seed=self.inventory['seed_draft_hash']
        self.base,self.mapping,self.inventory=raw,mapping,first
        second,_,_,inputs=self.produce(b'Queue MUST wait.\nQueue MUST report.\n')
        successors={u['unit_id'] for u in second['units'] if u['normative']}
        self.assertEqual(len(successors),2)
        self.assertTrue(successors.isdisjoint(retired|{merged}))
        self.assertEqual(set(second['retired_unit_ids']),retired|{merged})
        self.assertEqual(second['base_inventory_hash'],sha256_bytes(canonical_json_bytes(first)))
        self.assertEqual(second['seed_draft_hash'],seed)
        validate_candidate_inventory(second,**inputs)

    def test_unambiguous_rewording_and_retained_duplicates_keep_identity(self):
        f=self.fixture
        f.base(b'Preface MUST remain.\n# Queue\n## Timing\nQueue MUST wait.\n## Reports\nRepeat.\nRepeat.\n')
        self.base=f.c.a.base;self.mapping=f.c.a.mapping;self.inventory=f.inventory
        inventory,raw,mapping,_=self.produce(b'Queue MUST wait before starting.\n',group=False)
        self.assertEqual([u['unit_id'] for u in inventory['units']],[u['unit_id'] for u in self.inventory['units']])
        self.assertEqual(inventory['retired_unit_ids'],[])
        validate_inventory_facts(inventory,raw,mapping)

    def test_inserted_heading_and_facets_have_distinct_payload_identities(self):
        inventory,raw,mapping,inputs=self.produce(b'### Examples\nQueue MUST emit `READY`.\n',group=False,operation='append_child_section')
        original={u['unit_id'] for u in self.inventory['units']}
        additions=[u for u in inventory['units'] if u['unit_id'] not in original]
        op=inputs['proposal'].patch['operations'][0]
        facts=payload_units(inputs['proposal'].payloads[op['payload']['path']],job_id=inputs['plan']['job_id'],parser_version=mapping['parser_contract_version'])
        self.assertEqual({u['unit_id'] for u in additions},
            {inserted_unit_id(inputs['plan']['transaction_id'],op['operation_id'],u['kind'],i+1) for i,u in enumerate(facts)})
        self.assertEqual(inventory['retired_unit_ids'],[])
        validate_inventory_facts(inventory,raw,mapping)

    def test_readback_rejects_changed_lineage_tombstones_and_anchors(self):
        inventory,_,_,inputs=self.produce(b'Queue MUST wait and report.\n')
        for change in ('identity','anchor','retired','base','proposal'):
            bad=deepcopy(inventory)
            if change=='identity':bad['units'][0]['unit_id']='unit_'+'f'*64
            elif change=='anchor':bad['units'][0]['anchor_line_unit_id']='unit_'+'f'*64
            elif change=='retired':bad['retired_unit_ids']=[]
            elif change=='base':bad['base_inventory_hash']='f'*64
            else:bad['proposal_hash']='f'*64
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'does not reproduce'):
                validate_candidate_inventory(bad,**inputs)

    def test_identity_collision_and_ambiguous_rewrite_cannot_publish_inventory(self):
        old=self.inventory['units'][0]['unit_id']
        with patch('whetstone.vnext_unit_lineage.inserted_unit_id',return_value=old):
            with self.assertRaisesRegex(ValueError,'collision or reuse'):self.produce(b'Queue MUST wait and report.\n')
        with self.assertRaisesRegex(ValueError,'explicit_unit_correspondence_required'):
            self.produce(b'Queue MUST wait and report.\n',group=False)


if __name__=='__main__':unittest.main()
