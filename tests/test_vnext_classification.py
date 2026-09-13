from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import validate_contract_suite
from whetstone.scope import scope_contract_from_notes
from vnext_mutation_fixtures import MutationFixture


class ClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.suite=validate_contract_suite()
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.f=MutationFixture(Path(self.tmp.name),self.suite)
    def classify(self,**overrides):return classify_feedback(**{**self.f.classification_arguments(),**overrides})

    def test_bounded_correction_resolves_display_anchor_to_stable_identity(self):
        findings,evidence=self.classify();record=findings[0]
        self.assertEqual(record['classification'],'editor_fixable')
        self.assertEqual(record['target_section_ids'],[self.f.mapping['sections'][0]['stable_section_id']])
        self.assertEqual(evidence[record['finding_id']]['feedback_refs'],[self.f.feedback_ref])
        self.assertEqual(record['source_feedback_ids'],['fb-1'])

    def test_missing_or_stale_advice_cannot_admit_editor_work(self):
        self.assertEqual(self.classify(advice=None)[0][0]['classification'],'operator_decision_required')
        advice=deepcopy(self.f.advice);advice['base_draft_hash']='f'*64
        with self.assertRaisesRegex(ValueError,'stale'):self.classify(advice=advice)
        advice=deepcopy(self.f.advice);advice['findings']=[]
        with self.assertRaisesRegex(ValueError,'coverage'):self.classify(advice=advice)

    def test_destructive_or_policy_triggers_override_editor_fixable_advice(self):
        for words in ['Weaken the minimum interval.','Delete the requirement.','Choose whether timeouts are required.']:
            self.f.feedback['feedback'][0]['recommended_change']=words;self.f.rebind()
            with self.subTest(words=words):self.assertEqual(self.classify()[0][0]['classification'],'operator_decision_required')
        self.f.feedback['feedback'][0]['recommended_change']='Clarify the interval.';self.f.hint['requested_effects']=['weaken'];self.f.rebind()
        self.assertEqual(self.classify()[0][0]['classification'],'operator_decision_required')

    def test_prospective_compatibility_introduction_is_forbidden_but_cleanup_is_distinct(self):
        self.f.hint['compatibility_change']='introduce';self.f.feedback['feedback'][0]['recommended_change']='Introduce compatibility aliases.';self.f.rebind()
        findings,evidence=self.classify();self.assertEqual(findings[0]['classification'],'authority_conflict')
        self.assertTrue(evidence[findings[0]['finding_id']]['requires_new_job'])
        self.f.hint.update(compatibility_change='remove',requested_effects=['remove'])
        self.f.feedback['feedback'][0]['recommended_change']='Remove legacy compatibility aliases.';self.f.rebind()
        findings,evidence=self.classify();self.assertEqual(findings[0]['classification'],'operator_decision_required')
        self.assertFalse(evidence[findings[0]['finding_id']]['requires_new_job'])

    def test_non_normative_reference_cannot_supply_requirement_authority(self):
        b=deepcopy(self.f.authority['bindings'][0]);b.update(path='inputs/donor.md',role='donor_reference',mutable=False)
        self.f.authority['bindings'].append(b);self.f.rebind()
        self.f.advice['findings'][0]['source_authority_binding_ids']=[self.f.authority['bindings'][1]['binding_id']]
        self.assertEqual(self.classify()[0][0]['classification'],'authority_conflict')

    def test_blocking_frozen_section_requires_a_new_job(self):
        self.f.invariants['assertions']=[{'assertion_id':'','assertion_type':'section_unchanged','target_scope':'queue',
            'matcher':{'kind':'canonical_id','value':'queue'},'enforcement':'deterministic','severity':'blocking',
            'rationale':'Frozen contract.','source_authority_binding_ids':[]}];self.f.rebind()
        findings,evidence=self.classify();self.assertEqual(findings[0]['classification'],'authority_conflict')
        self.assertTrue(evidence[findings[0]['finding_id']]['requires_new_job'])

    def test_unknown_targets_and_scope_surfaces_do_not_expand_scope(self):
        self.f.feedback['feedback'][0]['affected_sections']=['not-present'];self.f.rebind()
        self.assertEqual(self.classify()[0][0]['classification'],'scope_change')
        self.f.feedback['feedback'][0]['affected_sections']=['queue']
        self.f.scope=scope_contract_from_notes('# Core Outcome\nQueue tasks.\n',approved=True)
        self.f.hint['scope_surface_ids']=['missing'];self.f.rebind()
        self.assertEqual(self.classify()[0][0]['classification'],'scope_change')
        surface=self.f.scope['scope_surfaces'][0];surface['status']='deferred';self.f.hint['scope_surface_ids']=[surface['id']];self.f.rebind()
        self.assertEqual(self.classify()[0][0]['classification'],'deferable')

    def test_repeated_issue_retains_sources_and_conflicting_recommendations_pause(self):
        repeated=deepcopy(self.f.feedback['feedback'][0]);repeated['feedback_id']='fb-2'
        repeated['recommended_change']='Use a different interval wording.'
        self.f.feedback['feedback'].append(repeated);self.f.rebind()
        hint=deepcopy(self.f.advice['findings'][0]);hint['feedback_id']='fb-2';self.f.advice['findings'].append(hint)
        findings,evidence=self.classify();self.assertEqual(len(findings),1)
        self.assertEqual(findings[0]['source_feedback_ids'],['fb-1','fb-2'])
        self.assertEqual(findings[0]['classification'],'operator_decision_required')

    def test_deferred_destructive_work_stays_excluded_unless_it_conflicts_with_a_blocking_invariant(self):
        self.f.scope=scope_contract_from_notes('# Core Outcome\nQueue tasks.\n',approved=True)
        surface=self.f.scope['scope_surfaces'][0];surface['status']='deferred'
        self.f.hint.update(scope_surface_ids=[surface['id']],requested_effects=['remove'])
        self.f.feedback['feedback'][0]['recommended_change']='Remove the deferred behavior.'
        self.f.invariants['assertions']=[{'assertion_id':'','assertion_type':'section_unchanged','target_scope':'queue',
            'matcher':{'kind':'canonical_id','value':'queue'},'enforcement':'deterministic','severity':'blocking',
            'rationale':'Keep this section frozen.','source_authority_binding_ids':[]}]
        self.f.rebind()
        findings,evidence=self.classify()
        self.assertEqual(findings[0]['classification'],'deferable')
        self.assertFalse(evidence[findings[0]['finding_id']]['requires_new_job'])
        self.f.feedback['feedback'][0]['invariant_violated']=self.f.invariants['assertions'][0]['assertion_id']
        self.f.rebind()
        findings,evidence=self.classify()
        self.assertEqual(findings[0]['classification'],'authority_conflict')
        self.assertTrue(evidence[findings[0]['finding_id']]['requires_new_job'])

if __name__=='__main__':unittest.main()
