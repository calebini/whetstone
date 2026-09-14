from copy import deepcopy
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_inventory import seed_inventory, validate_seed_inventory
import test_vnext_patch_operations as operation_tests


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):operation_tests.PatchOperationTests.setUpClass()
    def setUp(self):
        self.c=operation_tests.PatchOperationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
    def inventory(self,raw,**kwargs):
        self.c.f.base=raw;self.c.f.rebind()
        return seed_inventory(raw,self.c.f.mapping,self.c.f.job,**kwargs)
    def contents(self,inventory,raw,kind):
        return [raw[u['byte_start']:u['byte_end']].decode() for u in inventory['units'] if u['kind']==kind]

    def test_primary_units_partition_preamble_unicode_crlf_and_missing_final_newline(self):
        raw='Preamble MUST remain.\r\n# Queue\r\n## Timing\r\nCafé SHALL wait.\r\n## Reports\r\nReport'.encode()
        inventory=self.inventory(raw)
        primary=[u for u in inventory['units'] if u['primary']]
        self.assertEqual(b''.join(raw[u['byte_start']:u['byte_end']] for u in primary),raw)
        self.assertEqual(primary[0]['owning_section_id'],inventory['frontmatter_section_id'])
        self.assertEqual(sum(u['normative'] for u in primary),2)
        self.assertEqual(len({u['unit_id'] for u in inventory['units']}),len(inventory['units']))
        self.assertEqual(canonical_json_bytes(inventory),canonical_json_bytes(seed_inventory(raw,self.c.f.mapping,self.c.f.job)))

    def test_typed_lexical_facts_cover_lists_tables_identifiers_conditions_and_links(self):
        raw=b'# Queue\n## Timing\n- READY: the `queue` MUST accept `--wait`.\nPrecondition: state is READY.\nPostcondition: report `E_TIMEOUT`.\nAcceptance criteria: report failures.\n| State | Meaning |\n| READY | a \\| b |\nSee [policy](policy.md#timeout).\n'
        inventory=self.inventory(raw)
        kinds={u['kind'] for u in inventory['units']}
        self.assertTrue({'enumerated_member','identifier','precondition','postcondition','acceptance_criterion','table_row','table_cell','cross_reference'}<=kinds)
        self.assertIn('a \\| b',self.contents(inventory,raw,'table_cell'))
        self.assertEqual(self.contents(inventory,raw,'cross_reference'),['policy.md#timeout'])
        self.assertIn('--wait',self.contents(inventory,raw,'identifier'))
        self.assertEqual(sum(u['normative'] for u in inventory['units']),1)

    def test_json_schema_fields_required_and_enum_members_have_exact_spans(self):
        raw='# Queue\n## Timing\n```json\n{"properties":{"café":{"enum":["READY","STOP"]}},"required":["café"]}\n```\n'.encode()
        inventory=self.inventory(raw)
        self.assertEqual(inventory['diagnostics'],[])
        self.assertEqual(self.contents(inventory,raw,'schema_required_member'),['"café"'])
        self.assertEqual(self.contents(inventory,raw,'schema_enum_member'),['"READY"','"STOP"'])
        self.assertIn('"café"',self.contents(inventory,raw,'schema_field'))

    def test_yaml_block_flow_quoted_commas_and_indentless_members(self):
        raw=b'# Queue\n## Timing\n```yaml\nrequired:\n- id\n- mode\nproperties:\n  mode:\n    enum: [READY, "A,B", \'[literal]\'] # retained\n```\n'
        inventory=self.inventory(raw)
        self.assertEqual(inventory['diagnostics'],[])
        self.assertEqual(self.contents(inventory,raw,'schema_required_member'),['id','mode'])
        self.assertEqual(self.contents(inventory,raw,'schema_enum_member'),['READY','"A,B"',"'[literal]'"])

    def test_configured_exact_patterns_are_bound_and_work_inside_schema_fences(self):
        raw=b'# Queue\n## Timing\nThe worker always reports failure.\n```yaml\nstate: READY\n```\n'
        rules=[{'rule_id':'required-report','text':'always reports failure','normative':True,'kind':'normative_pattern'},
               {'rule_id':'ready-state','text':'READY','normative':False,'kind':'state'}]
        inventory=self.inventory(raw,rules=rules)
        self.assertEqual(inventory['rules_hash'],sha256_bytes(canonical_json_bytes(rules)))
        self.assertEqual(self.contents(inventory,raw,'configured_state'),['READY'])
        self.assertEqual(sum(u['normative'] for u in inventory['units']),1)
        self.assertEqual(next(u for u in inventory['units'] if u['normative'])['normative_sources'],['rule:required-report'])
        with self.assertRaisesRegex(ValueError,'duplicate'):self.inventory(raw,rules=rules+rules)

    def test_invalid_or_opaque_schema_and_open_fence_are_inspectable_diagnostics(self):
        cases=[(b'```json\n{"required":["id"],"required":[]}\n```\n','schema_json_invalid'),
               (b'```yaml\nrequired: [*alias]\n```\n','schema_yaml_opaque_members'),
               (b'```\nunfinished\n','unclosed_fence')]
        for suffix,code in cases:
            raw=b'# Queue\n## Timing\n'+suffix
            with self.subTest(code=code):
                inventory=self.inventory(raw)
                self.assertIn(code,{d['code'] for d in inventory['diagnostics']})
                self.assertEqual(sum(u['byte_end']-u['byte_start'] for u in inventory['units'] if u['primary']),len(raw))

    def test_current_bytes_cannot_be_reseeded_with_a_changed_job_hash(self):
        raw=b'# Queue\n## Timing\nWait.\n';self.inventory(raw)
        job=deepcopy(self.c.f.job);job['seed_draft']['hash']='f'*64
        with self.assertRaisesRegex(ValueError,'exact seed'):seed_inventory(raw,self.c.f.mapping,job)

    def test_seed_inventory_readback_rejects_rehashed_or_reclassified_claims(self):
        raw=b'# Queue\n## Timing\nThe queue MUST wait.\n';packet=self.inventory(raw)
        validate_seed_inventory(packet,raw,self.c.f.mapping,self.c.f.job)
        for field,value in [('normative',False),('unit_id','unit_'+'f'*64),('content_hash','f'*64)]:
            changed=deepcopy(packet);next(u for u in changed['units'] if u['normative'])[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'reproduce'):
                validate_seed_inventory(changed,raw,self.c.f.mapping,self.c.f.job)

if __name__=='__main__':unittest.main()
