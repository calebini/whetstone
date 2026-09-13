"""Deterministic plan construction and exact derived-task provenance."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, validate_contract_suite
from whetstone.vnext_plans import build_plan
from vnext_fixtures import Bundle, ISSUE
import test_vnext_decisions as decision_tests


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.suite=validate_contract_suite()

    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.b=Bundle(Path(self.tmp.name),self.suite)
        self.finding={'finding_id':ISSUE,'source_feedback_ids':['fb-1'],'classification':'editor_fixable',
                      'target_section_ids':self.b.plan['allowed_section_ids']}
        self.constraints={key:deepcopy(self.b.plan[key]) for key in ('allowed_operation_types','max_operations',
            'max_changed_sections','max_changed_normative_units','required_context_binding_ids')}

    def build(self,findings=None,decisions=()):
        return build_plan(job=self.b.job,authority=self.b.authority,section_map=self.b.base_map,
            findings=findings or [self.finding],constraints=self.constraints,suite=self.suite,decisions=decisions)

    def test_one_bounded_correction_has_traceable_exact_union(self):
        plan,provenance,responses=self.build()
        self.assertEqual(plan,self.b.plan)
        self.assertEqual(provenance,[]);self.assertEqual(responses,[])
        self.assertEqual({f for sl in plan['slices'] for f in sl['admitted_finding_ids']},{ISSUE})

    def test_input_order_cannot_change_plan_and_shared_targets_merge(self):
        other={**deepcopy(self.finding),'finding_id':'iss_'+'2'*16,'source_feedback_ids':['fb-2']}
        a=self.build([self.finding,other])[0];b=self.build([other,self.finding])[0]
        self.assertEqual(canonical_json_bytes(a),canonical_json_bytes(b))
        self.assertEqual(len(a['slices']),1)
        self.assertEqual(len(a['slices'][0]['admitted_finding_ids']),2)

    def test_unresolved_choice_authority_and_scope_gates_block(self):
        for classification in ('operator_decision_required','authority_conflict','scope_change'):
            other={**deepcopy(self.finding),'finding_id':'iss_'+'2'*16,'classification':classification}
            with self.subTest(classification=classification),self.assertRaisesRegex(ValueError,'unresolved'):
                self.build([self.finding,other])

    def test_deferable_original_remains_visible_but_is_not_admitted(self):
        other={**deepcopy(self.finding),'finding_id':'iss_'+'2'*16,'classification':'deferable'}
        plan,_,_=self.build([self.finding,other])
        self.assertEqual(len(plan['finding_dispositions']),2)
        self.assertFalse(next(f for f in plan['finding_dispositions'] if f['finding_id']==other['finding_id'])['admitted_to_editing'])
        self.assertNotIn(other['finding_id'],plan['slices'][0]['admitted_finding_ids'])
        with self.assertRaisesRegex(ValueError,'no admitted'):self.build([other])

    def test_bound_response_creates_new_task_and_retains_original_classification(self):
        helper=decision_tests.MutationDecisionTests();helper.suite=self.suite;helper.setUp();self.addCleanup(helper.doCleanups)
        original={**helper.finding,'target_section_ids':helper.targets}
        decision={'finding_id':ISSUE,'request':helper.request,'response':helper.response,'feedback_refs':helper.refs}
        plan,provenance,responses=self.build([original],[decision])
        self.assertEqual(len(provenance),1);self.assertEqual(len(responses),1)
        old=next(f for f in plan['finding_dispositions'] if f['finding_id']==ISSUE)
        self.assertEqual(old['classification'],'operator_decision_required');self.assertFalse(old['admitted_to_editing'])
        self.assertEqual(plan['slices'][0]['admitted_finding_ids'],[provenance[0]['finding_id']])
        self.assertEqual(provenance[0]['original_finding_id'],ISSUE)
        with self.assertRaisesRegex(ValueError,'duplicate'):self.build([original],[decision,decision])

    def test_bad_targets_duplicate_ids_and_unbound_constraints_refuse(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):self.build([self.finding,self.finding])
        bad={**self.finding,'target_section_ids':['sec_'+'f'*64]}
        with self.assertRaisesRegex(ValueError,'unknown'):self.build([bad])
        self.constraints['max_changed_sections']=0
        with self.assertRaisesRegex(ValueError,'budget'):self.build()
        self.constraints['max_changed_sections']=1;self.constraints['allow_everything']=True
        with self.assertRaisesRegex(ValueError,'constraints'):self.build()


if __name__=='__main__':unittest.main()
