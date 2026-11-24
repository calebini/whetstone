"""Pure shared-obligation policy tests; no model or storage calls."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.scope import scope_contract_from_notes
from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import validate_contract_suite, CONTRACT_ROOT, VNextSchemaRegistry
from whetstone.vnext_phase1_policy import POLICY, dispositions, blocking_rows
from whetstone.vnext_review_configuration import validate
from whetstone.vocabulary import PROFILE_SETS
from vnext_mutation_fixtures import MutationFixture


def scope_packet():
    scope = scope_contract_from_notes('# Core Outcome\nQueue tasks.\n', approved=True)
    scope['generated_at'] = '2026-11-22T00:00:00Z'
    scope['approval']['approved_at'] = '2026-11-22T00:00:00Z'
    core = scope['scope_surfaces'][0]
    core['status'] = 'in_scope'
    later = deepcopy(core); later.update(id='future-hardening', status='deferred')
    scope['scope_surfaces'].append(later)
    return scope


class SharedPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.suite = validate_contract_suite()

    def setUp(self):
        tmp = TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.f = MutationFixture(Path(tmp.name), self.suite)
        self.f.scope = scope_packet()
        self.review = dict(schema_version='review-configuration-v3', completion_policy=POLICY)
        self.f.hint.update(classification='deferable', scope_surface_ids=['future-hardening'])
        self.f.rebind()

    def result(self):
        findings, evidence = classify_feedback(**self.f.classification_arguments(), review=self.review)
        return dict(feedback=self.f.feedback, advice=self.f.advice, findings=findings, evidence=evidence)

    def test_approved_deferral_is_nonblocking_even_when_reviewer_marks_in_scope(self):
        result = self.result()
        self.assertTrue(next(dispositions(result))[1])
        self.assertEqual(blocking_rows(self.review, result), [])
        self.assertEqual(len(blocking_rows({}, result, global_acceptance=True)), 1)

    def test_bare_out_of_scope_flag_cannot_waive_major(self):
        self.f.hint['scope_surface_ids'] = [self.f.scope['scope_surfaces'][0]['id']]
        self.f.feedback['feedback'][0]['in_scope'] = False; self.f.rebind()
        result = self.result()
        self.assertEqual(result['findings'][0]['classification'], 'operator_decision_required')
        self.assertEqual(len(blocking_rows(self.review, result)), 1)

    def test_mixed_scope_surfaces_do_not_authorize_deferral(self):
        self.f.hint['scope_surface_ids'].append(self.f.scope['scope_surfaces'][0]['id']); self.f.rebind()
        self.assertEqual(len(blocking_rows(self.review, self.result())), 1)

    def test_dependency_and_authority_decisions_override_deferred_surface(self):
        for classification in ('scope_change', 'operator_decision_required', 'authority_conflict'):
            with self.subTest(classification=classification):
                self.f.hint['classification'] = classification; self.f.rebind()
                result = self.result()
                self.assertEqual(result['findings'][0]['classification'], classification)
                self.assertEqual(len(blocking_rows(self.review, result)), 1)

    def test_scope_change_effect_cannot_hide_behind_deferable_label(self):
        self.f.hint['requested_effects'] = ['scope_change']; self.f.rebind()
        self.assertEqual(len(blocking_rows(self.review, self.result())), 1)

    def test_blocking_invariant_overrides_deferral_at_minor_severity(self):
        self.f.invariants['assertions'] = [dict(assertion_id='', assertion_type='section_unchanged',
            target_scope='queue', matcher=dict(kind='canonical_id', value='queue'), enforcement='deterministic',
            severity='blocking', rationale='Keep the requirement.', source_authority_binding_ids=[])]
        self.f.rebind()
        item = self.f.feedback['feedback'][0]
        item.update(invariant_violated=self.f.invariants['assertions'][0]['assertion_id'], baseline_severity='minor')
        self.f.rebind()
        result = self.result()
        self.assertEqual(result['findings'][0]['classification'], 'authority_conflict')
        self.assertEqual(len(blocking_rows(self.review, result)), 1)

    def test_minor_optional_observation_is_nonblocking_but_not_approved_deferral(self):
        self.f.hint['scope_surface_ids'] = [self.f.scope['scope_surfaces'][0]['id']]
        self.f.feedback['feedback'][0]['baseline_severity'] = 'minor'; self.f.rebind()
        _, deferred, blocking = next(dispositions(self.result()))
        self.assertFalse(deferred); self.assertFalse(blocking)

    def test_missing_and_unknown_scope_cannot_waive_major(self):
        self.f.hint['scope_surface_ids'] = ['missing']; self.f.rebind()
        self.assertEqual(len(blocking_rows(self.review, self.result())), 1)
        self.f.scope = None
        self.f.job.update(scope_contract_hash=None, scope_contract_path=None)
        self.f.hint['scope_surface_ids'] = []; self.f.rebind()
        self.assertEqual(len(blocking_rows(self.review, self.result())), 1)

    def test_same_policy_for_every_selected_profile_and_both_workflows(self):
        actor = dict(name='fixture', version='1', model='scripted')
        for workflow in ('standard','mvp'):
            for name in ('stateful_system','balanced_mvp','utility_mvp'):
                preset=PROFILE_SETS[name]
                review=dict(schema_version='review-configuration-v3', completion_policy=POLICY,
                    workflow=workflow, profile_set=name, review_mode='horizontal',
                    profiles=[dict(name=p,budget=preset.phase_1_default_budgets[p]) for p in preset.phase_1_profiles],
                    reviewer=actor,editor=actor,verifier=actor)
                validate(review,VNextSchemaRegistry())
                for profile in preset.phase_1_profiles:
                    self.f.feedback['profile']=profile; self.f.rebind()
                    self.assertEqual(blocking_rows(review,self.result()),[])

    def test_profile_mismatch_and_unknown_workflows_refuse(self):
        review=deepcopy(self.f.original.review)
        review.update(schema_version='review-configuration-v3', completion_policy=POLICY, profile_set='utility_mvp')
        with self.assertRaisesRegex(ValueError,'outside selected'): validate(review,VNextSchemaRegistry())
        review.update(profile_set='stateful_system',workflow='custom')
        with self.assertRaisesRegex(ValueError,'workflow'): validate(review,VNextSchemaRegistry())
        review.update(workflow='mvp',review_mode='vertical',phase1_selection=dict(kind='focused',profile='structural_integrity'))
        with self.assertRaisesRegex(ValueError,'requires horizontal review'): validate(review,VNextSchemaRegistry())

    def test_new_suite_validates_without_changing_old_digests(self):
        old=validate_contract_suite(CONTRACT_ROOT/'suites/vnext-verified-consumer-1.json')
        self.assertEqual(old.digest,'7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58')
        new=validate_contract_suite(CONTRACT_ROOT/'suites/vnext-verified-consumer-2.json')
        self.assertNotEqual(new.digest,old.digest)

    def test_deferred_surface_cannot_hide_non_normative_authority(self):
        binding=deepcopy(self.f.authority['bindings'][0])
        binding.update(path='inputs/donor.md',role='donor_reference',mutable=False)
        self.f.authority['bindings'].append(binding);self.f.rebind()
        self.f.advice['findings'][0]['source_authority_binding_ids']=[self.f.authority['bindings'][1]['binding_id']]
        result=self.result()
        self.assertEqual(result['findings'][0]['classification'],'authority_conflict')
        self.assertEqual(len(blocking_rows(self.review,result)),1)

    def test_repeated_issue_disagreement_cannot_be_hidden_by_one_deferral(self):
        repeated=deepcopy(self.f.feedback['feedback'][0]);repeated['feedback_id']='fb-2'
        repeated['recommended_change']='Use a different minimum interval.'
        self.f.feedback['feedback'].append(repeated);self.f.rebind()
        hint=deepcopy(self.f.advice['findings'][0]);hint['feedback_id']='fb-2'
        self.f.advice['findings'].append(hint)
        self.assertEqual(len(blocking_rows(self.review,self.result())),2)

    def test_policy_requires_its_own_pinned_contracts(self):
        from whetstone.vnext_phase1_policy import pins
        old=validate_contract_suite(CONTRACT_ROOT/'suites/vnext-verified-consumer-1.json')
        with self.assertRaisesRegex(ValueError,'absent or changed'): pins(old)
        pins(validate_contract_suite(CONTRACT_ROOT/'suites/vnext-verified-consumer-2.json'))

    def test_optional_editor_fixable_minor_does_not_force_work_but_major_does(self):
        from whetstone.vnext_phase1_policy import requires_work
        self.f.hint.update(classification='editor_fixable',scope_surface_ids=[self.f.scope['scope_surfaces'][0]['id']])
        self.f.feedback['feedback'][0]['baseline_severity']='minor';self.f.rebind()
        result=self.result()
        self.assertFalse(requires_work(self.review,result))
        self.assertTrue(requires_work({},result))
        self.f.feedback['feedback'][0]['baseline_severity']='major';self.f.rebind()
        self.assertTrue(requires_work(self.review,self.result()))
