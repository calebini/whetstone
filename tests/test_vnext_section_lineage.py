from copy import deepcopy
import unittest

from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_section_lineage import candidate_section_map, inserted_heading_id, validate_lineage_map
import test_vnext_patch_operations as operation_tests


class SectionLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):operation_tests.PatchOperationTests.setUpClass()
    def setUp(self):
        self.c=operation_tests.PatchOperationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
    def map(self,packet):
        c=self.c;proposal=c.prepare(packet)
        assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        mapping=candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,assembled=assembled)
        validate_lineage_map(mapping,assembled.raw)
        return mapping,proposal,assembled
    def ids(self,mapping):return {s['heading_text']:s['stable_section_id'] for s in mapping['sections'] if s['status']=='active'}

    def test_body_rewrite_retains_ids_and_multiple_inserted_descendants_get_distinct_ids(self):
        c=self.c;original=self.ids(c.a.mapping)
        mapping,_,_=self.map(c.packet('replace_section_body',b'Wait 30 seconds or longer.\n'))
        self.assertEqual(self.ids(mapping),original)
        packet=c.packet('append_child_section',b'### Examples\n#### First\nOne.\n#### Second\nTwo.\n')
        mapping,proposal,_=self.map(packet);op=proposal.patch['operations'][0]
        for ordinal,title in enumerate(('Examples','First','Second'),1):
            self.assertEqual(self.ids(mapping)[title],inserted_heading_id(c.plan['transaction_id'],op['operation_id'],ordinal))
        self.assertEqual(len(set(self.ids(mapping).values())),len(self.ids(mapping)))
        self.assertEqual(canonical_json_bytes(mapping),canonical_json_bytes(self.map(packet)[0]))

    def test_subtree_root_rename_and_unique_child_rewrite_preserve_lineage(self):
        c=self.c;original=self.ids(c.a.mapping)
        mapping,_,_=self.map(c.packet('replace_section_subtree',b'## Timing policy\nWait 30 seconds.\n### Details\nKeep exact precision.\n'))
        current=self.ids(mapping)
        self.assertEqual(current['Timing policy'],original['Timing'])
        self.assertEqual(current['Details'],original['Details'])
        self.assertEqual(current['Reports'],original['Reports'])

    def test_explicit_identity_replacement_and_deletion_keep_tombstones_after_active_rows(self):
        c=self.c;old=self.ids(c.a.mapping)
        packet=c.packet('replace_section_subtree',b'## Timing\nReplacement.\n')
        packet['operations'][0]['preserve_target_identity']=False
        mapping,_,_=self.map(packet)
        self.assertNotEqual(self.ids(mapping)['Timing'],old['Timing'])
        tombstones={s['stable_section_id'] for s in mapping['sections'] if s['status']=='retired'}
        self.assertEqual(tombstones,{old['Timing'],old['Details']})
        c.authorize_timing_deletion();old=self.ids(c.a.mapping)
        mapping,_,_=self.map(c.packet('delete_section_subtree',None))
        self.assertEqual(list(self.ids(mapping)),['Queue','Reports'])
        self.assertEqual([s['status'] for s in mapping['sections']],['active','active','retired','retired'])

    def test_unchanged_duplicate_children_keep_order_but_ambiguous_rewrite_refuses(self):
        c=self.c;c.f.base=b'# Queue\n\n## Timing\nWait.\n### Detail\nSame.\n### Detail\nSame.\n## Reports\nReport.\n'
        c.f.rebind();c.refresh()
        original=[s['stable_section_id'] for s in c.a.mapping['sections'] if s['heading_text']=='Detail']
        mapping,_,_=self.map(c.packet('replace_section_subtree',b'## Timing renamed\nWait longer.\n### Detail\nSame.\n### Detail\nSame.\n'))
        self.assertEqual([s['stable_section_id'] for s in mapping['sections'] if s['heading_text']=='Detail'],original)
        with self.assertRaisesRegex(ValueError,'ambiguous descendant'):
            self.map(c.packet('replace_section_subtree',b'## Timing\nWait.\n### Detail\nChanged.\n### Detail\nChanged.\n'))

    def test_exact_subtree_move_with_repeated_children_retains_all_identities(self):
        c=self.c
        c.f.base=b'# Queue\n\n## Timing\n### Left\n#### Moved\n##### Detail\nSame.\n##### Detail\nSame.\n### Right\n## Reports\nReport.\n'
        c.f.rebind();c.refresh()
        original=[s['stable_section_id'] for s in c.a.mapping['sections']]
        mapping,_,_=self.map(c.packet('replace_section_subtree',
            b'## Timing\n### Left\n### Right\n#### Moved\n##### Detail\nSame.\n##### Detail\nSame.\n'))
        self.assertEqual(set(original),{s['stable_section_id'] for s in mapping['sections']})
        moved=next(s for s in mapping['sections'] if s['heading_text']=='Moved')
        self.assertEqual(moved['parent_stable_section_id'],self.ids(mapping)['Right'])

    def test_map_tampering_and_origin_tampering_do_not_create_valid_lineage(self):
        c=self.c;packet=c.packet('replace_section_body',b'Wait 30 seconds.\n')
        mapping,proposal,assembled=self.map(packet)
        bad=deepcopy(mapping);bad['sections'][1]['heading_text']='Forged'
        with self.assertRaises(ValueError):validate_lineage_map(bad,assembled.raw)
        bad=deepcopy(mapping);bad['sections'][1]['stable_section_id']=bad['sections'][0]['stable_section_id']
        with self.assertRaisesRegex(ValueError,'collision'):validate_lineage_map(bad,assembled.raw)
        from dataclasses import replace
        origins=list(assembled.heading_origins);origins[1]=replace(origins[1],source_start=0)
        with self.assertRaisesRegex(ValueError,'source span'):
            candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,
                                  assembled=replace(assembled,heading_origins=tuple(origins)))

    def test_move_can_change_heading_depth_without_reassigning_identity(self):
        c=self.c
        c.f.base=b'# Queue\n\n## Timing\n### Parent\n#### Moved\nBody.\n##### Detail\nSame.\n##### Detail\nSame.\n## Reports\nReport.\n'
        c.f.rebind();c.refresh();original=self.ids(c.a.mapping)
        mapping,_,_=self.map(c.packet('replace_section_subtree',
            b'## Timing\n### Parent\n### Moved\nBody.\n#### Detail\nSame.\n#### Detail\nSame.\n'))
        moved=next(s for s in mapping['sections'] if s['heading_text']=='Moved')
        self.assertEqual(moved['stable_section_id'],original['Moved'])
        self.assertEqual(moved['heading_level'],3)
        self.assertEqual(moved['parent_stable_section_id'],original['Timing'])

if __name__=='__main__':unittest.main()
