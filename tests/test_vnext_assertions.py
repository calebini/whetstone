import unittest

from whetstone.vnext_assertions import MutationMetrics, evaluate_assertions, validate_assertion_program
from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_identity import assertion_id
from whetstone.vnext_inventory import frontmatter_section_id
from whetstone.vnext_section_lineage import candidate_section_map
import test_vnext_patch_operations as operation_tests


class AssertionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):operation_tests.PatchOperationTests.setUpClass()
    def setUp(self):
        self.c=operation_tests.PatchOperationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        c=self.c
        payload=b'Use `queue` and `--wait`.\n- READY: the queue accepts work.\n| State | Meaning |\n| READY | a \\| b |\n```json\n{"model":"single","enum":["READY","STOP"]}\n```\n'
        self.proposal=c.prepare(c.packet('replace_section_body',payload))
        self.assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=self.proposal)
        self.mapping=candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=self.proposal,assembled=self.assembled)
    def assertion(self,kind,value,mode='exact',scope='document',enforcement='deterministic'):
        a={'assertion_id':'','assertion_type':kind,'target_scope':scope,'matcher':{'kind':mode,'value':value},
           'enforcement':enforcement,'severity':'blocking','rationale':'Fictional assertion fixture.','source_authority_binding_ids':[]}
        a['assertion_id']=assertion_id(sha256_bytes(self.c.a.base),a)
        return a
    def packet(self,assertions):
        return {'schema_version':'protected-invariants-v1','base_draft_hash':sha256_bytes(self.c.a.base),'assertions':assertions}
    def evaluate(self,assertions,**kwargs):
        c=self.c
        return evaluate_assertions(invariants=self.packet(assertions),seed=c.a.base,seed_map=c.a.mapping,
            candidate=self.assembled.raw,candidate_map=self.mapping,frontmatter_id=frontmatter_section_id(c.a.job),**kwargs)

    def test_headings_identifiers_enums_and_ordered_table_cells_use_real_candidate_facts(self):
        assertions=[self.assertion('heading_present','Timing'),self.assertion('heading_absent','Missing'),
            self.assertion('identifier_present','--wait'),self.assertion('identifier_absent','--unsafe'),
            self.assertion('enum_member_present','STOP'),self.assertion('enum_member_present','READY'),
            self.assertion('table_row_present',{'cells':['READY','a | b']},'inventory_query'),
            self.assertion('canonical_model_count',{'kind':'schema_field','value':'model','count':1},'inventory_query')]
        self.assertTrue(all(r['result']=='pass' for r in self.evaluate(assertions)))
        failures=[self.assertion('identifier_absent','queue'),self.assertion('enum_member_present','LOST'),
                  self.assertion('table_row_present',{'cells':['READY','wrong']},'inventory_query')]
        self.assertTrue(all(r['result']=='fail' for r in self.evaluate(failures)))

    def test_scope_limits_search_and_freezing_uses_exact_immutable_seed_bytes(self):
        assertions=[self.assertion('identifier_absent','queue',scope='reports'),
                    self.assertion('section_unchanged','reports','canonical_id',scope='reports'),
                    self.assertion('section_unchanged','timing','canonical_id',scope='timing')]
        self.assertEqual([r['result'] for r in self.evaluate(assertions)],['pass','pass','fail'])

    def test_budgets_require_metrics_and_count_a_moved_unit_once(self):
        ids={s['heading_text']:s['stable_section_id'] for s in self.c.a.mapping['sections']}
        metrics=MutationMetrics(frozenset({ids['Timing'],ids['Reports']}),{'unit_'+'1'*64:frozenset({ids['Timing'],ids['Reports']})})
        assertions=[self.assertion('max_changed_sections','1'),
                    self.assertion('max_changed_normative_units',{'maximum':1},'inventory_query'),
                    self.assertion('max_changed_sections','1',scope='timing')]
        self.assertEqual([r['result'] for r in self.evaluate(assertions,metrics=metrics)],['fail','pass','pass'])
        self.assertTrue(all(r['result']=='fail' for r in self.evaluate(assertions)))

    def test_semantic_concepts_are_never_certified_by_lexical_matches(self):
        semantic=self.assertion('concept_forbidden','No hidden second recurrence model.','semantic',enforcement='semantic')
        self.assertEqual(self.evaluate([semantic]),[])
        lexical=self.assertion('concept_forbidden','legacy','regex')
        with self.assertRaisesRegex(ValueError,'semantic enforcement'):self.evaluate([lexical])

    def test_unknown_queries_stale_ids_and_boolean_count_limits_fail_preflight(self):
        for a in [self.assertion('identifier_absent',{'kind':'magic','value':'unsafe'},'inventory_query'),
                  self.assertion('max_changed_sections',{'maximum':True},'inventory_query'),
                  self.assertion('heading_present','Timing',scope='unknown'),
                  self.assertion('max_changed_sections','01')]:
            with self.subTest(assertion=a),self.assertRaises(ValueError):
                validate_assertion_program(self.packet([a]),self.c.a.base,self.c.a.mapping)
        a=self.assertion('heading_present','Timing');a['matcher']['value']='Different'
        with self.assertRaisesRegex(ValueError,'identity mismatch'):self.evaluate([a])

    def test_scope_survives_a_heading_rename_through_stable_identity(self):
        c=self.c;proposal=c.prepare(c.packet('replace_section_subtree',b'## Renamed timing\nUse `queue`.\n'))
        assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        self.assembled=assembled;self.mapping=candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,assembled=assembled)
        self.assertEqual(self.evaluate([self.assertion('identifier_present','queue',scope='timing')])[0]['result'],'pass')
        self.assertEqual(self.evaluate([self.assertion('section_unchanged','timing','canonical_id',scope='timing')])[0]['result'],'fail')

if __name__=='__main__':unittest.main()
