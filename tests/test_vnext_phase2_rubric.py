"""Exact attribution, stable ordering and retained gap resolution rules."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from whetstone.vnext_phase2_rubric import attribute, catalogue, retained


class RubricRulesTests(unittest.TestCase):
    raw = b'# Rubric\n\n## Requirements\n\n- Define ownership.\n- Define recovery.\n'

    def feedback(self):
        return dict(feedback=[dict(feedback_id='fb_a', issue_id='iss_'+'a'*16,
            affected_sections=['second','first'], normalized_severity='major', rubric_impact='major',
            claim='Ownership is unclear.', evidence='Two owners can write.',
            recommended_change='Identify the owner.', in_scope=True)])

    def annotations(self):
        return [dict(feedback_id='fb_a', **{key:row[key] for key in ('rubric_anchor','requirement_hash')})
                for row in reversed(catalogue(self.raw))]

    def test_exact_requirement_and_canonical_order(self):
        result = attribute(self.annotations(), self.feedback(), self.raw, ['first','second'])
        self.assertEqual([row['requirement']['order'] for row in result], [0,1])
        self.assertTrue(all(row['gap']['affected_sections']==['first','second'] for row in result))
        self.assertTrue(all(row['gap']['status']=='unresolved' and row['gap']['blocking_convergence'] for row in result))
        self.assertEqual(result, attribute(list(reversed(self.annotations())), self.feedback(), self.raw, ['first','second']))

    def test_missing_duplicate_unknown_or_changed_attribution_refuses(self):
        original = self.annotations();cases = [[],original+original[:1]]
        for key,value in [('feedback_id','missing'),('rubric_anchor','missing'),('requirement_hash','0'*64)]:
            bad=deepcopy(original);bad[0][key]=value;cases.append(bad)
        for value in cases:
            with self.subTest(value=value),self.assertRaises(ValueError):
                attribute(value,self.feedback(),self.raw,['first','second'])

    def test_mid_target_rejects_inapplicable_requirements_without_severity_authority(self):
        self.assertEqual(catalogue(self.raw, target_phase='mid'), [])
        with self.assertRaises(ValueError):
            attribute(self.annotations(), self.feedback(), self.raw, ['first','second'], target_phase='mid')
        with self.assertRaises(ValueError):
            attribute([], self.feedback(), self.raw, ['first','second'], target_phase='mid')
        ordinary = self.feedback();ordinary['feedback'][0]['rubric_impact'] = None
        self.assertEqual(attribute([], ordinary, self.raw, ['first','second'], target_phase='mid'), [])

    def test_source_scope_cannot_waive_an_applicable_unresolved_requirement(self):
        feedback = self.feedback();feedback['feedback'][0]['in_scope'] = False
        gaps = attribute(self.annotations(), feedback, self.raw, ['first','second'])
        self.assertTrue(all(row['gap']['blocking_convergence'] for row in gaps))
        self.assertTrue(all(row['gap']['status']=='unresolved' for row in gaps))

    def test_retained_gap_prevents_review_only_plan_despite_out_of_scope_source(self):
        from whetstone.vnext_verified_phase2_review_only import plan
        feedback = self.feedback();feedback['feedback'][0]['in_scope'] = False
        gaps = attribute(self.annotations(), feedback, self.raw, ['first','second'])
        reference = {'ordinal': 0};profile = 'convergence_strict_check'
        reader = SimpleNamespace(json=lambda ref,schema:dict(promotion_ordinal=ref['ordinal']),
                                 suite=SimpleNamespace(manifest={'algorithms': []}))
        owner = SimpleNamespace(proof=SimpleNamespace(reader=reader), binding=SimpleNamespace(
            configuration={'profiles': [{'name': profile}, {'name': 'adversarial'}]}))
        frame = dict(consumed=True, owner=owner, clean_after=[profile],
            bound=SimpleNamespace(request={'schema_version':'vnext-phase2-review-request-v4',
                'base_pointer':reference,'step':{'profile':profile}}, request_ref={'path':'request','hash':'a'*64}),
            review={'feedback':feedback,'rubric_findings':gaps})
        scheduler = SimpleNamespace(index=2,steps=[profile,'adversarial'],
                                    states=[SimpleNamespace(residual_status=None)])
        self.assertIsNone(plan([frame],reference,scheduler))
        frame['review']['rubric_findings'] = []
        self.assertEqual(plan([frame],reference,scheduler)[1]['profiles'], ['adversarial'])

    def test_silence_partial_and_future_resolution_cannot_clear_debt(self):
        rows=attribute(self.annotations(),self.feedback(),self.raw,['first','second'])
        reader=SimpleNamespace(json=lambda ref,schema:dict(promotion_ordinal=ref['ordinal']))
        owner=SimpleNamespace(proof=SimpleNamespace(reader=reader))
        def frame(items, resolution=None):
            return dict(consumed=True,owner=owner,bound=SimpleNamespace(request={'base_pointer':{'ordinal':0}}),
                        review={'rubric_findings':items},resolution=resolution)
        first=frame(rows);silent=frame([])
        self.assertTrue(all(r['status']=='unresolved' for r in retained([first,silent],{'ordinal':0})))
        first['resolution']=dict(committed=True,packet={'promoted_pointer':{'ordinal':1}},resolved_issue_ids=['derived'])
        self.assertTrue(all(r['status']=='unresolved' for r in retained([first,silent],{'ordinal':1})))
        first['resolution']['resolved_issue_ids']=[rows[0]['source_issue_id']]
        self.assertTrue(all(r['status']=='unresolved' for r in retained([first,silent],{'ordinal':0})))
        self.assertTrue(all(r['status']=='resolved' and not r['blocking_convergence'] for r in retained([first,silent],{'ordinal':1})))
        recurrence=frame(rows)
        self.assertTrue(all(r['status']=='unresolved' for r in retained([first,silent,recurrence],{'ordinal':1})))

    def test_resolution_covers_only_requirements_in_that_verified_review(self):
        rows=attribute(self.annotations(),self.feedback(),self.raw,['first','second'])
        reader=SimpleNamespace(json=lambda ref,schema:dict(promotion_ordinal=ref['ordinal']))
        owner=SimpleNamespace(proof=SimpleNamespace(reader=reader))
        old=dict(consumed=True,owner=owner,bound=SimpleNamespace(request={'base_pointer':{'ordinal':0}}),
                 review={'rubric_findings':rows})
        current=dict(consumed=True,owner=owner,bound=old['bound'],review={'rubric_findings':rows[:1]},
                     resolution=dict(committed=True,packet={'promoted_pointer':{'ordinal':1}},
                                     resolved_issue_ids=[rows[0]['source_issue_id']]))
        self.assertEqual([row['status'] for row in retained([old,current],{'ordinal':1})],['resolved','unresolved'])
