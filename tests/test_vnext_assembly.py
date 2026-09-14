"""Assembly expectations are literal candidate bytes, not assembler-derived oracles."""
from copy import deepcopy
import unittest

from whetstone.vnext_assembly import assemble_bytes
import test_vnext_patch_operations as operation_tests


class AssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):operation_tests.PatchOperationTests.setUpClass()
    def setUp(self):
        self.case=operation_tests.PatchOperationTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
    def assemble(self,packet):
        c=self.case
        return assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=c.prepare(packet))

    def test_each_operation_reproduces_literal_bytes_and_preserves_unrelated_sections(self):
        c=self.case
        prefix=b'# Queue\n\n';timing=b'## Timing\nWait at least 30 seconds.\n### Details\nKeep precision.\n'
        reports=b'## Reports\nReport the outcome.\n'
        cases=[
            ('replace_section_body',b'Wait 30 seconds or longer.\n',prefix+b'## Timing\nWait 30 seconds or longer.\n### Details\nKeep precision.\n'+reports),
            ('replace_section_subtree',b'## Timing rule\nWait 30 seconds or longer.\n',prefix+b'## Timing rule\nWait 30 seconds or longer.\n'+reports),
            ('insert_section_before',b'## Before\nExample.\n',prefix+b'## Before\nExample.\n'+timing+reports),
            ('insert_section_after',b'## After\nExample.\n',prefix+timing+b'## After\nExample.\n'+reports),
            ('append_child_section',b'### Example\nDetails.\n',prefix+timing+b'### Example\nDetails.\n'+reports),
        ]
        for kind,payload,expected in cases:
            with self.subTest(kind=kind):
                packet=c.packet(kind,payload)
                result=self.assemble(packet)
                self.assertEqual(result.raw,expected)
                self.assertEqual(self.assemble(deepcopy(packet)),result)
                self.assertEqual(result.heading_origins[-1].base_section_id,c.a.mapping['sections'][-1]['stable_section_id'])

    def test_same_anchor_insertion_order_is_not_reversed_or_taken_from_array_order(self):
        c=self.case
        for kind,payload1,payload2 in [('insert_section_after',b'## One\n',b'## Two\n'),
                                     ('append_child_section',b'### One\n',b'### Two\n')]:
            packet=c.packet(kind,payload1)
            second=c.packet(kind,payload2,label='second')['operations'][0]
            second['depends_on_operation_ids']=['first'];packet['operations'].append(second)
            result=self.assemble(packet)
            self.assertIn(payload1+payload2,result.raw)
            packet['operations'].reverse()
            self.assertEqual(self.assemble(packet),result)

    def test_authorized_deletion_removes_exact_subtree_and_keeps_other_origins(self):
        c=self.case;c.authorize_timing_deletion()
        result=self.assemble(c.packet('delete_section_subtree',None))
        self.assertEqual(result.raw,b'# Queue\n\n## Reports\nReport the outcome.\n')
        self.assertEqual([h.base_section_id for h in result.heading_origins],
                         [c.a.mapping['sections'][0]['stable_section_id'],c.a.mapping['sections'][-1]['stable_section_id']])

    def test_body_replacement_cannot_adopt_an_existing_descendant_under_a_new_heading(self):
        c=self.case;c.f.base=c.f.base.replace(b'### Details',b'#### Details');c.f.rebind();c.refresh()
        with self.assertRaisesRegex(ValueError,'reparented a retained'):
            self.assemble(c.packet('replace_section_body',b'Wait 30 seconds.\n### New parent\n'))

    def test_local_payload_validity_cannot_hide_global_fence_or_missing_newline_damage(self):
        c=self.case
        for payload in [b'Wait 30 seconds.',b'```\nExample\n']:
            with self.subTest(payload=payload),self.assertRaisesRegex(ValueError,'heading boundaries'):
                self.assemble(c.packet('replace_section_body',payload))

    def test_shared_anchor_order_cannot_move_a_child_under_an_inserted_sibling(self):
        c=self.case;packet=c.packet('insert_section_after',b'## Sibling\n')
        child=c.packet('append_child_section',b'### Child\n',label='child')['operations'][0]
        child['depends_on_operation_ids']=['first'];packet['operations'].append(child)
        with self.assertRaisesRegex(ValueError,'declared payload parent'):self.assemble(packet)
        # The inverse explicit order preserves both declared relationships.
        child['depends_on_operation_ids']=[];packet['operations'][0]['depends_on_operation_ids']=['child']
        result=self.assemble(packet)
        self.assertIn(b'### Child\n## Sibling\n',result.raw)

    def test_normalize_once_after_assembly_and_reject_altered_payload_bytes(self):
        c=self.case;packet=c.packet('replace_section_body',b'Wait 30 seconds.  \r\n')
        result=self.assemble(packet)
        self.assertIn(b'Wait 30 seconds.  \r\n',result.before_normalization)
        self.assertIn(b'Wait 30 seconds.\n### Details',result.raw)
        proposal=c.prepare(packet)
        path=proposal.patch['operations'][0]['payload']['path'];proposal.payloads[path]=b'Changed after preparation.\n'
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        self.assertFalse(hasattr(result,'candidate_id'))

if __name__=='__main__':unittest.main()
