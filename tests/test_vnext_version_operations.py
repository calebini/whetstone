from copy import deepcopy
import unittest
from unittest.mock import patch

from whetstone.vnext_version_operations import anchors, project, ASSEMBLER
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_section_lineage import candidate_section_map
from whetstone.vnext_candidate_validation import assess_candidate
from whetstone.vnext_semantic_coverage import prepare_semantic_obligations
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_unit_protocol import exercise_unit_proposal
import test_vnext_unit_preflight as fixtures


class VersionOperationTests(unittest.TestCase):
    def test_numeric_lifecycle_and_exact_adjacent_bytes(self):
        for phase,transition,before,after in (
            ('phase_1','round','0.17','0.18'),('phase_1','round','0.99','1.00'),
            ('phase_1','round','0.1.1','0.1.2'),('phase_2','round','1.9','1.10'),
            ('phase_2','round','1.0.3','1.0.4'),('phase_2','phase2_entry','0.17','1.0'),
            ('phase_2','phase2_entry','1.7','2.0'),('phase_2','phase2_entry','2.0','2.0'),
            ('phase_2','phase2_entry','2','2.0')):
            with self.subTest(phase=phase,before=before):
                base=f'# Café v{before}\n\n## Rules\nKeep.\n'.encode()
                proposed=base if transition=='phase2_entry' else base.replace(b'Keep.',b'Keep exactly.')
                final,record=project(base,proposed,phase=phase,transition=transition)
                self.assertEqual(final,proposed.replace(before.encode(),after.encode(),1))
                self.assertEqual((record['before'],record['after']),(before,after))

    def test_precedence_synchronization_status_and_fenced_examples(self):
        base=b'---\nVersion: 0.17\n---\n# Queue v0.17\nStatus: Accepted v0.17\nVersion: 0.17\n```md\nVersion: 9.9\n```\n## Rules\nVersion: 7.7\nKeep.\n'
        self.assertEqual([a.kind for a in anchors(base)[0]],['frontmatter','version','heading','status'])
        final,record=project(base,base.replace(b'Keep.',b'Keep exactly.'),phase='phase_1',transition='round')
        self.assertEqual(final.count(b'0.18'),4)
        self.assertIn(b'Status: Draft v0.18',final)
        self.assertIn(b'Version: 9.9',final);self.assertIn(b'Version: 7.7',final)
        self.assertEqual(len(record['edits']),5)

    def test_noop_unversioned_and_long_labels_do_not_increment(self):
        for base in (b'# Queue\n',b'# Queue 1.2.3.4\n',b'# Queue 0.17\nStatus: Accepted v0.17\n'):
            final,record=project(base,base,phase='phase_1',transition='round')
            self.assertEqual(final,base);self.assertEqual(record['edits'],[])
        final,record=project(b'# Queue\n',b'# Queue\n',phase='phase_2',transition='phase2_entry')
        self.assertEqual(record['before'],'');self.assertEqual(final,b'# Queue\n')

    def test_conflicts_and_editor_anchor_changes_refuse(self):
        for raw in (b'Version: 0.17\n# Queue 0.18\n',b'# Queue 0.17 and 1.0\n'):
            with self.assertRaises(ValueError): anchors(raw)
        base=b'# Queue 0.17\nStatus: Accepted v0.17\n## Rule\nKeep.\n'
        for proposed in (base.replace(b'0.17',b'0.18'),base.replace(b'Accepted',b'Draft'),
                         base.replace(b' 0.17',b''),b'Version: 0.17\n'+base):
            with self.assertRaisesRegex(ValueError,'Editor changed'): project(base,proposed,phase='phase_1',transition='round')
        with self.assertRaisesRegex(ValueError,'unchanged Phase 1'):
            project(base,base+b'changed',phase='phase_2',transition='phase2_entry')


class VersionCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixtures.UnitPreflightTests.setUpClass()

    def fixture(self):
        f=fixtures.UnitPreflightTests();f.setUp();self.addCleanup(f.doCleanups)
        f.c.f.base=f.c.f.base.replace(b'# Queue\n',b'# Queue 0.17\nStatus: Accepted v0.17\n')
        f.c.f.job['assembler_version']=ASSEMBLER;f.c.f.rebind()
        return f

    def candidate(self,f):
        # Pure protocol test: pin admission itself is exercised by runtime tests.
        with patch('whetstone.vnext_version_operations.pins'):
            preflight,proposal,_=exercise_unit_proposal(f.directory,load_inputs=f.inputs,client=fixtures.Client())
        values=f.inputs()
        assembled=assemble_bytes(base=values['base'],section_map=values['base_map'],plan=preflight.plan,proposal=proposal)
        mapping=candidate_section_map(base=values['base'],base_map=values['base_map'],proposal=proposal,assembled=assembled)
        inputs={key:values[key] for key in ('job','authority','invariants','seed','seed_map','base','base_map')}
        inputs.update(base_inventory=preflight.inventory,plan=preflight.plan,proposal=proposal,
                      candidate_bytes=assembled.raw,candidate_map=mapping,rules=preflight.rules)
        return assembled,inputs

    def test_combined_candidate_has_stamp_before_preservation_and_semantic_obligations(self):
        f=self.fixture();assembled,inputs=self.candidate(f)
        self.assertIn(b'# Queue 0.18',assembled.raw);self.assertIn(b'Status: Draft v0.18',assembled.raw)
        self.assertEqual(assembled.version_operation['candidate_hash'],sha256_bytes(assembled.raw))
        result=assess_candidate(**inputs)
        self.assertEqual(result.report['result'],'pass',result.report['failures'])
        self.assertEqual(result.report['assembler_version'],ASSEMBLER)
        system=[r for r in result.report['unit_changes'] if r['operation_id']==assembled.version_operation['operation_id']]
        self.assertTrue(system);self.assertTrue(all(r['authorized'] and r['semantic_required'] and not r['source_finding_ids'] for r in system))
        obligations=prepare_semantic_obligations(report=result.report,inventory=result.inventory,**inputs)
        texts=[u['text'] for o in obligations['obligations'] for u in o['candidate_units']]
        self.assertTrue(any('Draft v0.18' in text for text in texts))
        self.assertEqual([r['stable_section_id'] for r in inputs['base_map']['sections']],
                         [r['stable_section_id'] for r in inputs['candidate_map']['sections']])

    def test_tampered_final_bytes_and_unpinned_preflight_refuse(self):
        f=self.fixture()
        with self.assertRaisesRegex(ValueError,'contract absent'): prepare_unit_preflight(**f.inputs())
        assembled,inputs=self.candidate(f)
        changed={**inputs,'candidate_bytes':assembled.raw.replace(b'0.18',b'0.19')}
        result=assess_candidate(**changed)
        self.assertEqual(result.report['result'],'fail')
        self.assertIn('candidate_bytes_mismatch',{r['code'] for r in result.report['failures']})

    def test_frontmatter_and_all_synchronized_anchors_keep_complete_lineage(self):
        f=self.fixture()
        f.c.f.base=b'---\nVersion: 0.17\n---\n'+f.c.f.base.replace(b'Status: Accepted v0.17\n',b'Status: Accepted v0.17\nVersion: 0.17\n')
        f.c.f.rebind()
        assembled,inputs=self.candidate(f)
        self.assertEqual(assembled.raw.count(b'0.18'),4)
        result=assess_candidate(**inputs)
        self.assertEqual(result.report['result'],'pass',result.report['failures'])
        self.assertEqual(len(result.inventory['units']),len(inputs['base_inventory']['units']))

    def test_system_operation_cannot_waive_a_blocking_invariant(self):
        from whetstone.vnext_identity import assertion_id
        f=self.fixture()
        assertion=dict(assertion_id='',assertion_type='heading_present',target_scope='document',
            matcher=dict(kind='exact',value='Queue 0.17'),enforcement='deterministic',severity='blocking',
            rationale='Fixture forbids demotion.',source_authority_binding_ids=[])
        assertion['assertion_id']=assertion_id(sha256_bytes(f.c.f.base),assertion)
        f.c.f.invariants['assertions']=[assertion];f.c.f.rebind()
        _,inputs=self.candidate(f)
        assessment=assess_candidate(**inputs)
        self.assertEqual(assessment.report['result'],'fail')
        self.assertIn('blocking_assertion_failed',{r['code'] for r in assessment.report['failures']})


if __name__=='__main__': unittest.main()
