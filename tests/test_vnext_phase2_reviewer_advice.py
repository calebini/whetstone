"""Reviewer hints bind exact evidence; classifications never grant authority."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_phase2_reviewer_advice import bind
import test_vnext_unit_preflight as fixtures


class ReviewerAdviceTests(unittest.TestCase):
    setUpClass = fixtures.UnitPreflightTests.setUpClass

    def setUp(self):
        owner = fixtures.UnitPreflightTests(); owner.setUp()
        self.addCleanup(owner.doCleanups)
        self.f = owner.c.f
        self.suite = validate_contract_suite(CONTRACT_ROOT/'suites/vnext-verified-consumer-1.json')
        self.inputs = dict(job=self.f.job, authority=self.f.authority, invariants=self.f.invariants,
            draft=self.f.base.decode(), base_map=self.f.mapping, scope=None)
        self.feedback = deepcopy(self.f.feedback)
        self.hints = deepcopy(self.f.advice['findings'])
        self.path = 'rounds/phase2/review/feedback.json'

    def bind(self, hints=None):
        return bind(self.suite,self.inputs,self.feedback,self.path,self.hints if hints is None else hints)

    def test_exact_run_bindings_and_no_aliasing(self):
        result = self.bind()
        self.assertEqual(result['base_draft_hash'],sha256_bytes(self.f.base))
        self.assertEqual(result['feedback'],dict(path=self.path,hash=sha256_bytes(canonical_json_bytes(self.feedback))))
        for key in ('job_id','authority_map_hash','scope_contract_hash','protected_invariants_hash'):
            self.assertEqual(result[key],self.f.job[key])
        self.hints.clear();self.assertTrue(result['findings'])

    def test_consuming_dispatch_uses_the_implemented_verifier_policy(self):
        from whetstone.vnext_registry import SUITE_ALGORITHM_VERSIONS
        from whetstone.vnext_semantic_protocol import POLICY_VERSION
        self.assertEqual(SUITE_ALGORITHM_VERSIONS[self.suite.version]['semantic_verifier_policy_version'],POLICY_VERSION)
        self.assertEqual(SUITE_ALGORITHM_VERSIONS['vnext-contracts-1']['semantic_verifier_policy_version'],'semantic-policy-v1')

    def test_exact_coverage_and_unknown_authority_refuse(self):
        unknown = deepcopy(self.hints);unknown[0]['source_authority_binding_ids']=['unknown']
        wrong = deepcopy(self.hints);wrong[0]['feedback_id']='missing'
        for hints in ([],self.hints*2,unknown,wrong):
            with self.subTest(hints=hints), self.assertRaises(ValueError):self.bind(hints)
        self.inputs['authority']=deepcopy(self.inputs['authority'])
        self.inputs['authority']['bindings'][0]['authority_scopes']=['different']
        with self.assertRaisesRegex(ValueError,'authority changed'):self.bind()

    def test_sensitive_effects_override_editor_fixable(self):
        for effect in ('weaken','remove','authority_change','scope_change'):
            self.hints[0].update(classification='editor_fixable',requested_effects=[effect])
            advice=self.bind()
            findings,_=classify_feedback(feedback=self.feedback,feedback_ref=advice['feedback'],advice=advice,
                job=self.f.job,authority=self.f.authority,invariants=self.f.invariants,
                base=self.f.base,section_map=self.f.mapping,scope=None)
            self.assertEqual(findings[0]['classification'],'operator_decision_required')

    def test_response_decoder_distinguishes_shape_from_contradictory_evidence(self):
        from whetstone.vnext_verified_phase2_client import _Journal
        from whetstone.vnext_review_protocol import ReviewShapeError
        review=deepcopy(self.feedback)
        review['profile']='convergence_strict_check'
        for row in review['feedback']:
            row['oscillation_key']=dict(section_id=row['affected_sections'][0],
                concern_type='precision_gap',direction='clarify',scope='local')
        inputs=dict(self.inputs,rubric_catalogue=[],rubric='# Rubric\n',
            configuration=dict(reviewer=review['reviewer'],target_phase='final'))
        journal=object.__new__(_Journal)
        journal.bound=SimpleNamespace(inputs=inputs,request=dict(schema_version='vnext-phase2-review-request-v6'))
        journal.proof=SimpleNamespace(reader=SimpleNamespace(suite=self.suite))
        journal.schemas=VNextSchemaRegistry()
        journal.number=review['round_number'];journal.profile=review['profile'];journal.feedback_path=self.path
        packet=dict(review=review,rubric_findings=[],classifications=self.hints)
        valid=journal.decode_review(canonical_json_bytes(packet))
        self.assertEqual(valid['advice']['feedback']['hash'],sha256_bytes(canonical_json_bytes(valid['feedback'])))
        for bad in (dict(review=review,rubric_findings=[]),dict(packet,unexpected=True)):
            with self.assertRaises(ReviewShapeError):journal.decode_review(canonical_json_bytes(bad))
        for bad in (dict(packet,classifications=[]),dict(packet,review=dict(review,draft_hash='f'*64))):
            with self.assertRaises(ValueError) as caught:journal.decode_review(canonical_json_bytes(bad))
            self.assertNotIsInstance(caught.exception,ReviewShapeError)
        # An older consuming suite still decodes precisely the v1 envelope and
        # does not add advice to its historical review hash.
        manifest=deepcopy(self.suite.manifest)
        manifest['algorithms']=[r for r in manifest['algorithms'] if r['name']!='vnext_phase2_reviewer_advice_v1']
        journal.proof.reader.suite=SimpleNamespace(manifest=manifest)
        old=journal.decode_review(canonical_json_bytes(dict(review=review,rubric_findings=[])))
        self.assertEqual(old, {k:v for k,v in valid.items() if k!='advice'})
        with self.assertRaises(ReviewShapeError):journal.decode_review(canonical_json_bytes(packet))
