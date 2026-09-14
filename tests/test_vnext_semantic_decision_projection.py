"""Pure decision projection; fixture claims do not qualify a runtime mode."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal, derive_semantic_decision
from vnext_fixtures import Bundle


class SemanticDecisionProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.suite = validate_contract_suite()

    def inputs(self, mode='verified_promotion', verdict='pass'):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        bundle = Bundle(Path(directory.name), self.suite, mode=mode)
        previous = {**bundle.decision, 'semantic_verification_hash': None, 'semantic_result': 'not_run',
                    'candidate_disposition': 'CANDIDATE_UNVERIFIED', 'promotion_permitted': False,
                    'decision_final': False, 'rejection_codes': [], 'outstanding_decision_ids': []}
        initial = {**previous, 'decided_at': '2030-01-01T00:00:00Z'}
        semantic = {**bundle.semantic, 'verdict': verdict}
        question = {'decision_id': 'dec_' + '1' * 64} if verdict == 'operator_decision_required' else None
        return dict(initial=initial, previous=previous, report=bundle.preservation,
                    result=SimpleNamespace(verification=semantic, authority_request=question),
                    job=bundle.job, schemas=self.suite.registry)

    def test_permission_depends_on_pinned_mode_and_final_semantic_pass(self):
        for mode in ('proposal_only', 'verified_promotion'):
            for verdict in ('pass', 'reject', 'operator_decision_required'):
                with self.subTest(mode=mode, verdict=verdict):
                    inputs = self.inputs(mode, verdict)
                    initial, previous = deepcopy(inputs['initial']), deepcopy(inputs['previous'])
                    result = derive_semantic_decision(**inputs)
                    self.assertEqual(result['promotion_permitted'], mode == 'verified_promotion' and verdict == 'pass')
                    self.assertEqual(result['candidate_disposition'], 'CANDIDATE_VERIFIED' if verdict == 'pass' else 'CANDIDATE_REJECTED')
                    self.assertTrue(result['decision_final'])
                    self.assertEqual(result['decision_ordinal'], 2)
                    self.assertEqual(result['previous_decision_hash'], sha256_bytes(canonical_json_bytes(previous)))
                    self.assertEqual(result['decided_at'], initial['decided_at'])
                    self.assertEqual(inputs['initial'], initial)
                    self.assertEqual(inputs['previous'], previous)
                    self.assertEqual(result['outstanding_decision_ids'],
                                     ['dec_' + '1' * 64] if verdict == 'operator_decision_required' else [])

    def test_changed_predecessor_is_not_reinterpreted_under_new_deterministic_evidence(self):
        inputs = self.inputs()
        for field, value in (('candidate_hash', 'f' * 64), ('base_draft_hash', 'f' * 64),
                             ('preservation_report_hash', 'f' * 64), ('candidate_creation_ordinal', 2)):
            with self.subTest(field=field):
                modified = {**inputs, 'previous': {**inputs['previous'], field: value}}
                with self.assertRaisesRegex(ValueError, 'predecessor differs'):
                    derive_semantic_decision(**modified)

    def test_final_or_later_predecessor_cannot_be_reopened(self):
        inputs = self.inputs()
        for changes in ({'decision_final': True},
                        {'decision_ordinal': 2, 'previous_decision_hash': 'f' * 64},
                        {'semantic_result': 'reject'}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'cannot reopen'):
                derive_semantic_decision(**{**inputs, 'previous': {**inputs['previous'], **changes}})

    def test_readonly_or_mismatched_job_cannot_derive_an_editing_decision(self):
        inputs = self.inputs()
        for changes in ({'editing_mode': 'reviewer_only'}, {'job_id': 'job_' + 'f' * 64}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'editing mode|job binding'):
                derive_semantic_decision(**{**inputs, 'job': {**inputs['job'], **changes}})

    def test_projection_does_not_enable_verified_mode_in_the_existing_journal(self):
        inputs = self.inputs()
        with self.assertRaisesRegex(ValueError, 'requires proposal_only mode'):
            SemanticDecisionJournal(SimpleNamespace(job=inputs['job']), admission=object())


if __name__ == '__main__': unittest.main()
