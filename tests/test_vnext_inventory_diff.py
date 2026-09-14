from copy import deepcopy
import unittest

from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_assertions import evaluate_assertions
from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_identity import assertion_id
from whetstone.vnext_inventory import seed_inventory
from whetstone.vnext_inventory_diff import compare_inventory
from whetstone.vnext_section_lineage import candidate_section_map
import test_vnext_patch_operations as operation_tests


class InventoryDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):operation_tests.PatchOperationTests.setUpClass()
    def setUp(self):
        self.c=operation_tests.PatchOperationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.base(b'# Queue\n\n## Timing\nQueue MUST wait at least 30 seconds.\n### Details\nKeep precision.\n## Reports\nReports MUST name failures.\n')
    def base(self,raw):
        c=self.c;c.f.base=raw;c.f.rebind();c.refresh()
        self.inventory=seed_inventory(raw,c.a.mapping,c.a.job)
    def compare(self,payload):
        c=self.c;proposal=c.prepare(c.packet('replace_section_body',payload))
        assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        mapping=candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,assembled=assembled)
        result=compare_inventory(base=c.a.base,base_map=c.a.mapping,base_inventory=self.inventory,
            proposal=proposal,assembled=assembled,candidate_map=mapping)
        return result,assembled,mapping

    def test_bounded_rewording_has_one_changed_normative_unit_and_real_budget_failure(self):
        diff,assembled,mapping=self.compare(b'Queue MUST wait 30 seconds or longer.\n')
        self.assertEqual(diff.failures,())
        changed=[d for d in diff.deltas if d.change!='unchanged']
        self.assertEqual(len(changed),1);self.assertEqual(changed[0].change,'modified')
        self.assertTrue(changed[0].semantic_obligation)
        self.assertEqual(len(diff.metrics.normative_unit_sections),1)
        a={'assertion_id':'','assertion_type':'max_changed_normative_units','target_scope':'document',
           'matcher':{'kind':'exact','value':'0'},'enforcement':'deterministic','severity':'blocking',
           'rationale':'No normative changes allowed.','source_authority_binding_ids':[]}
        a['assertion_id']=assertion_id(sha256_bytes(self.c.a.base),a)
        results=evaluate_assertions(invariants={'schema_version':'protected-invariants-v1',
            'base_draft_hash':sha256_bytes(self.c.a.base),'assertions':[a]},seed=self.c.a.base,seed_map=self.c.a.mapping,
            candidate=assembled.raw,candidate_map=mapping,frontmatter_id=self.inventory['frontmatter_section_id'],metrics=diff.metrics)
        self.assertEqual(results[0]['result'],'fail')

    def test_rfc_weakening_is_detected_even_when_the_editor_claims_clarification(self):
        diff,_,_=self.compare(b'Queue SHOULD wait at least 30 seconds.\n')
        weakened=[d for d in diff.deltas if d.change=='weakened']
        self.assertEqual(len(weakened),1);self.assertTrue(weakened[0].semantic_obligation)
        self.assertEqual(len(diff.metrics.normative_unit_sections),1)

    def test_missing_enum_member_has_its_exact_removed_base_unit_id(self):
        self.base(b'# Queue\n\n## Timing\n```json\n{"enum":["READY","STOP"]}\n```\n## Reports\nReport.\n')
        old=next(u for u in self.inventory['units'] if u['kind']=='schema_enum_member'
                 and self.c.a.base[u['byte_start']:u['byte_end']]==b'"STOP"')
        diff,_,_=self.compare(b'```json\n{"enum":["READY"]}\n```\n')
        self.assertIn(old['unit_id'],{key for d in diff.deltas if d.change=='removed' for key in d.base_unit_ids})

    def test_retained_duplicate_units_use_source_positions_but_ambiguous_rewrite_does_not_guess(self):
        self.base(b'# Queue\n\n## Timing\nQueue MUST wait.\nQueue MUST wait.\n## Reports\nReports MUST name failures.\nReports MUST name failures.\n')
        diff,_,_=self.compare(b'Queue MUST wait.\n')
        self.assertIn('ambiguous_unit_correspondence',diff.failures)
        report_ids={u['unit_id'] for u in self.inventory['units'] if u['owning_section_id']==self.c.a.mapping['sections'][-1]['stable_section_id']}
        unchanged={key for d in diff.deltas if d.change=='unchanged' for key in d.base_unit_ids}
        self.assertTrue(report_ids<=unchanged)

    def test_many_to_one_rewrite_requires_explicit_correspondence_instead_of_silent_identity_reuse(self):
        self.base(b'# Queue\n\n## Timing\nQueue MUST wait.\nQueue MUST report.\n## Reports\nReport.\n')
        diff,_,_=self.compare(b'Queue MUST wait and report.\n')
        self.assertIn('explicit_unit_correspondence_required',diff.failures)

    def test_normalization_does_not_turn_identical_statement_into_a_semantic_change(self):
        diff,_,_=self.compare(b'Queue MUST wait at least 30 seconds.  \r\n')
        self.assertEqual(diff.failures,())
        self.assertTrue(all(d.change=='unchanged' for d in diff.deltas))
        self.assertEqual(len(diff.metrics.normative_unit_sections),0)

    def test_forged_base_classification_cannot_reduce_observed_changes(self):
        changed=deepcopy(self.inventory)
        next(u for u in changed['units'] if u['normative'])['normative']=False
        self.inventory=changed
        with self.assertRaisesRegex(ValueError,'facts do not reproduce'):
            self.compare(b'Queue SHOULD wait.\n')

    def test_a_seed_syntax_defect_can_be_repaired_without_losing_baseline_uncertainty(self):
        self.base(b'# Queue\n\n## Timing\n```json\n{"enum":["READY" "STOP"]}\n```\n## Reports\nReport.\n')
        diff,_,_=self.compare(b'```json\n{"enum":["READY","STOP"]}\n```\n')
        self.assertEqual(diff.failures,())
        self.assertIn('schema_json_invalid',{d['code'] for d in diff.baseline_diagnostics})
        self.assertTrue(any(d.semantic_obligation for d in diff.deltas))

if __name__=='__main__':unittest.main()
