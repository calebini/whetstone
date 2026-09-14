from copy import deepcopy
import unittest

from whetstone.vnext_candidate_validation import assess_candidate, validate_assessment_readback
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import assertion_id
from whetstone.vnext_unit_proposals import build_unit_plan, prepare_unit_patch
from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_section_lineage import candidate_section_map
from vnext_fixtures import ACTOR
import test_vnext_unit_correspondence as correspondence_tests
import test_vnext_unit_authorization as authorization_tests


class CandidateValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):correspondence_tests.UnitCorrespondenceTests.setUpClass()
    def setUp(self):
        self.f=correspondence_tests.UnitCorrespondenceTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def inputs(self,payload=b'Queue MUST wait and report.\n',*,graph=True,kind='replace_section_body'):
        f=self.f;c=f.c
        c.plan,_,_=build_unit_plan(inventory=f.inventory,**f.plan_args)
        packet=f.packet(payload)
        packet['operations'][0]['operation_type']=kind
        if not graph:packet['operations'][0]['unit_correspondence']=[]
        proposal,assembled,mapping,_=f.compare(packet)
        return dict(job=c.a.job,authority=c.a.authority,invariants=c.f.invariants,seed=c.a.base,seed_map=c.a.mapping,
            base=c.a.base,base_map=c.a.mapping,base_inventory=f.inventory,plan=c.plan,proposal=proposal,
            candidate_bytes=assembled.raw,candidate_map=mapping)
    def codes(self,assessment):return {f['code'] for f in assessment.report['failures']}
    def assertion(self,kind,value,*,enforcement='deterministic',mode='exact',severity='blocking'):
        a={'assertion_id':'','assertion_type':kind,'target_scope':'document','matcher':{'kind':mode,'value':value},
            'enforcement':enforcement,'severity':severity,'rationale':'Fictional validation fixture.','source_authority_binding_ids':[]}
        a['assertion_id']=assertion_id(sha256_bytes(self.f.c.a.base),a)
        return a

    def test_passing_merge_reports_every_predecessor_and_pending_semantics(self):
        inputs=self.inputs();assessment=assess_candidate(**inputs);report=assessment.report
        self.assertEqual(report['result'],'pass');self.assertTrue(report['metrics_complete'])
        self.assertEqual(report['mutation_budget']['normative_units_observed'],2)
        self.assertIsNotNone(assessment.inventory)
        self.assertEqual(report['candidate_inventory_hash'],sha256_bytes(canonical_json_bytes(assessment.inventory)))
        base_ids={u['unit_id'] for u in inputs['base_inventory']['units']}
        self.assertEqual({r['unit_id'] for r in report['unit_changes'] if r['unit_id'] in base_ids},base_ids)
        changed=[r for r in report['unit_changes'] if r['correspondence_group_id'] and r['unit_id'] in base_ids]
        self.assertEqual(len(changed),2)
        self.assertTrue(all(r['semantic_required'] and r['authorized'] for r in changed))
        self.assertEqual(changed[0]['candidate_unit_ids'],changed[1]['candidate_unit_ids'])
        self.assertEqual(assess_candidate(**inputs).report,report)
        self.assertNotIn('verified',report)

    def test_actual_section_budget_counts_new_descendants(self):
        self.f.c.f.constraints['max_changed_sections']=1
        inputs=self.inputs(b'## Timing\n### Waiting\nQueue MUST wait.\n### Reporting\nQueue MUST report.\n',
                           kind='replace_section_subtree')
        assessment=assess_candidate(**inputs)
        self.assertIn('mutation_budget_exceeded',self.codes(assessment))
        self.assertEqual(assessment.report['mutation_budget']['sections_observed'],3)
        self.assertEqual(assessment.report['mutation_budget']['operations_observed'],1)

    def test_actual_unit_budget_fails_even_when_editor_declares_clarification(self):
        self.f.c.f.constraints['max_changed_normative_units']=1
        assessment=assess_candidate(**self.inputs())
        self.assertEqual(assessment.report['result'],'fail')
        self.assertIn('mutation_budget_exceeded',self.codes(assessment))
        self.assertEqual(assessment.report['mutation_budget']['normative_units_observed'],2)
        self.assertIsNotNone(assessment.inventory)

    def test_versioned_normalization_can_retire_unprotected_terminal_separators(self):
        self.f.base(self.f.c.a.base+b'\n\n')
        assessment=assess_candidate(**self.inputs())
        self.assertEqual(assessment.report['result'],'pass')
        cleanup=[r for r in assessment.report['unit_changes'] if r['change']=='removed' and r['operation_id'] is None]
        self.assertEqual(len(cleanup),2)
        self.assertTrue(all(r['authorized'] and not r['semantic_required'] for r in cleanup))

    def test_payload_readback_failure_still_produces_a_failed_report(self):
        inputs=self.inputs();proposal=deepcopy(inputs['proposal'])
        path=next(iter(proposal.payloads));proposal.payloads[path]+=b'Altered payload.\n'
        assessment=assess_candidate(**{**inputs,'proposal':proposal})
        self.assertEqual(assessment.report['result'],'fail')
        self.assertIn('candidate_reproduction_failed',self.codes(assessment))
        self.assertIsNone(assessment.report['reproduced_candidate_hash'])

    def test_known_weakening_and_silent_deletion_fail_with_exact_unit_ids(self):
        assessment=assess_candidate(**self.inputs(b'Queue SHOULD wait and report.\n'))
        self.assertIn('unauthorized_weaken',self.codes(assessment))
        denied=next(f for f in assessment.report['failures'] if f['code']=='unauthorized_weaken')['unit_ids']
        self.assertEqual(set(denied),{u['unit_id'] for u in self.f.inventory['units'] if u['normative']})
        assessment=assess_candidate(**self.inputs(b'Queue MUST report.\n',graph=False))
        self.assertIn('unauthorized_remove',self.codes(assessment))
        self.assertTrue(any(r['change']=='removed' and not r['authorized'] for r in assessment.report['unit_changes']))

    def test_altered_candidate_map_and_bytes_produce_bound_failed_reports(self):
        inputs=self.inputs()
        for name,value in [('candidate_bytes',inputs['candidate_bytes']+b'Unexpected.\n'),
                           ('candidate_map',{**inputs['candidate_map'],'draft_hash':'f'*64}),
                           ('candidate_map',None),('candidate_bytes',b'\xff')]:
            with self.subTest(name=name,value=type(value).__name__):
                assessment=assess_candidate(**{**inputs,name:value})
                self.assertEqual(assessment.report['result'],'fail');self.assertFalse(assessment.report['metrics_complete'])
                self.assertIsNone(assessment.report['mutation_budget']['normative_units_observed'])
                self.assertIsNone(assessment.inventory)
                self.assertEqual(assessment.report['candidate_hash'],sha256_bytes(value if name=='candidate_bytes' else inputs['candidate_bytes']))
                self.assertEqual(assessment.report['reproduced_candidate_hash'],sha256_bytes(inputs['candidate_bytes']))

    def test_ambiguous_correspondence_retains_failure_without_inventing_unit_ids(self):
        assessment=assess_candidate(**self.inputs(graph=False))
        self.assertIn('explicit_unit_correspondence_required',self.codes(assessment))
        self.assertEqual(assessment.report['result'],'fail');self.assertIsNone(assessment.inventory)
        self.assertFalse(assessment.report['metrics_complete'])
        self.assertNotIn('unauthorized_remove',self.codes(assessment))
        additions=[r for r in assessment.report['unit_changes'] if r['change']=='added']
        self.assertTrue(additions);self.assertTrue(all(r['unit_id'] is None and not r['authorized'] for r in additions))

    def test_ambiguity_does_not_hide_an_independently_known_deletion(self):
        self.f.base(b'# Queue\n## Timing\nQueue MUST wait.\nQueue MUST report.\nAnchor.\nQueue MUST log.\n## Reports\nReport.\n')
        assessment=assess_candidate(**self.inputs(b'Queue MUST wait and report.\nAnchor.\n',graph=False))
        self.assertIn('explicit_unit_correspondence_required',self.codes(assessment))
        failures=[f for f in assessment.report['failures'] if f['code']=='unauthorized_remove']
        self.assertEqual(len(failures),1)
        expected=next(u['unit_id'] for u in self.f.inventory['units']
                      if self.f.c.a.base[u['byte_start']:u['byte_end']]==b'Queue MUST log.\n')
        self.assertEqual(failures[0]['unit_ids'],[expected])

    def test_blocking_assertions_fail_and_semantic_assertions_remain_outstanding(self):
        c=self.f.c
        c.f.invariants['assertions']=[self.assertion('identifier_present','REQUIRED_ID'),
            self.assertion('concept_required','The original waiting semantics remain.',enforcement='semantic',mode='semantic')]
        self.f.base(c.a.base)
        assessment=assess_candidate(**self.inputs())
        self.assertIn('blocking_assertion_failed',self.codes(assessment))
        self.assertEqual(len(assessment.report['assertion_results']),1)
        self.assertEqual(assessment.report['assertion_results'][0]['result'],'fail')
        self.assertEqual(assessment.report['semantic_assertion_ids'],[c.f.invariants['assertions'][1]['assertion_id']])

    def test_text_corruption_patch_markers_and_placeholders_fail_even_with_correspondence(self):
        for marker,code in [(b'[...]\n','placeholder_content'),(b'[UNCHANGED sections]\n','placeholder_content'),
                            (b'<<<<<<< ours\n','unresolved_patch_marker'),(b'*** Begin Patch\n','unresolved_patch_marker'),
                            (b'\x00\n','corrupt_text')]:
            with self.subTest(marker=marker):
                inputs=self.inputs(b'Queue MUST wait and report.\n'+marker)
                assessment=assess_candidate(**inputs)
                self.assertEqual(assessment.report['result'],'fail');self.assertIn(code,self.codes(assessment))

    def test_invalid_immutable_bindings_refuse_before_candidate_assessment(self):
        inputs=self.inputs()
        bad=deepcopy(inputs['invariants']);bad['base_draft_hash']='f'*64
        with self.assertRaisesRegex(ValueError,'invariants changed'):assess_candidate(**{**inputs,'invariants':bad})
        bad=deepcopy(inputs['base_inventory']);bad['units'][0]['unit_id']='unit_'+'f'*64
        with self.assertRaises(ValueError):assess_candidate(**{**inputs,'base_inventory':bad})
        with self.assertRaisesRegex(ValueError,'another candidate'):
            assess_candidate(**inputs,candidate_map_path='candidates/can_'+'f'*64+'/section_identity_map_candidate.json')

    def test_persisted_report_cannot_hide_failures_or_semantic_obligations(self):
        inputs=self.inputs(b'Queue SHOULD wait and report.\n')
        assessment=assess_candidate(**inputs)
        validate_assessment_readback(assessment.report,assessment.inventory,**inputs)
        for change in ('verdict','failure','obligation','inventory'):
            report=deepcopy(assessment.report);inventory=deepcopy(assessment.inventory)
            if change=='verdict':report['result']='pass'
            elif change=='failure':report['failures']=[]
            elif change=='obligation':
                for row in report['unit_changes']:row['semantic_required']=False
            else:inventory['retired_unit_ids']=[]
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'does not reproduce'):
                validate_assessment_readback(report,inventory,**inputs)

    def test_exact_named_weakening_passes_deterministic_gate_but_requires_semantics(self):
        fixture=authorization_tests.UnitAuthorizationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        c=fixture.c
        decision={'finding_id':fixture.finding['finding_id'],'request':fixture.request,'response':fixture.response,'feedback_refs':[c.f.feedback_ref]}
        c.plan,_,_=build_unit_plan(inventory=fixture.inventory,job=c.a.job,authority=c.a.authority,
            section_map=c.a.mapping,findings=[fixture.finding],constraints=c.f.constraints,suite=c.suite,decisions=[decision])
        packet=c.packet('replace_section_body',b'Queue SHOULD wait.\nQueue MUST report.\n')
        packet['schema_version']='patch-set-v2';packet['operations'][0]['unit_correspondence']=[]
        proposal=prepare_unit_patch(canonical_json_bytes(packet),payload_root=c.payload_root,plan=c.plan,
            base=c.a.base,section_map=c.a.mapping,inventory=fixture.inventory,editor=ACTOR,responses=c.responses)
        assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        mapping=candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,assembled=assembled)
        assessment=assess_candidate(job=c.a.job,authority=c.a.authority,invariants=c.f.invariants,seed=c.a.base,
            seed_map=c.a.mapping,base=c.a.base,base_map=c.a.mapping,base_inventory=fixture.inventory,
            plan=c.plan,proposal=proposal,candidate_bytes=assembled.raw,candidate_map=mapping,bindings=[fixture.binding])
        self.assertEqual(assessment.report['result'],'pass')
        weakening=next(r for r in assessment.report['unit_changes'] if r['change']=='weakened')
        self.assertTrue(weakening['authorized']);self.assertTrue(weakening['semantic_required'])


if __name__=='__main__':unittest.main()
