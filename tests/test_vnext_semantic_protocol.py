from copy import deepcopy
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import binding_id
from whetstone.vnext_semantic_context import SemanticContext, prepare_semantic_context
from whetstone.vnext_semantic_protocol import (
    POLICY_VERSION, RULES, SemanticShapeError, decode_semantic_response, validate_semantic_readback, semantic_verifier_prompt,
)
from vnext_consuming_suite_fixture import consuming_suite
import test_vnext_proposal_admission as admission_tests
import test_vnext_semantic_context as context_tests


def digest(value):
    return sha256_bytes(canonical_json_bytes(value))


def semantic_suite(test, directory):
    return consuming_suite(test, directory,
        additional_schemas=('semantic_verification_client_v2', 'semantic_verification_client_v2.codex', 'semantic_verification_v2',
                            'vnext_semantic_authority_request_v1', 'vnext_semantic_obligations_v1'),
        additional_algorithms=('vnext_semantic_context_v1', 'vnext_semantic_coverage_v1', 'vnext_semantic_policy_v2'),
        algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})


@unittest.skipUnless(sys.platform == 'darwin', 'Registered fixture uses proposed macOS/APFS kernel')
class SemanticProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(admission_tests, 'consuming_suite', semantic_suite):
            context_tests.SemanticContextTests.setUpClass()
        cls.addClassCleanup(context_tests.SemanticContextTests.doClassCleanups)
        cls.registered_context = prepare_semantic_context(**context_tests.SemanticContextTests.arguments)

    def setUp(self):
        self.context = self.registered_context

    def response(self):
        packet = self.context.packet
        return {
            'schema_version': 'semantic-verification-v2', 'context_hash': self.context.input_hash,
            'finding_results': [{'finding_id': row['finding_id'], 'disposition': 'resolved', 'evidence': 'Fictional exact finding assessment.'}
                                for row in packet['mutation_plan']['finding_dispositions'] if row['admitted_to_editing']],
            'unrelated_semantic_change': 'none', 'lost_or_weakened_semantics': 'none', 'authority_compliance': 'pass',
            'semantic_assertions': [{'assertion_id': row['assertion_id'], 'result': 'pass', 'evidence': 'Fictional semantic assertion assessment.'}
                                    for row in packet['protected_invariants']['assertions'] if row['enforcement'] == 'semantic'],
            'normative_change_assessment': [{'operation_id': row['operation_id'], 'editor_claim': row['normative_change'],
                                             'verifier_assessment': 'Independent fictional classification.', 'agrees': True}
                                            for row in packet['editor_proposal']['patch']['operations']],
            'operator_decision_required': False, 'uncertainty_resolutions': [], 'verdict': 'pass',
            'rationale': 'Fictional policy fixture, not a real semantic judgment.', 'authority_choice': None,
            'coverage': {'schema_version': 'vnext-semantic-coverage-v1', 'obligations_hash': digest(packet['semantic_obligations']),
                         'results': [{'obligation_id': row['obligation_id'], 'obligation_hash': digest(row),
                                      'result': 'pass', 'evidence': 'Fictional exact preservation assessment.'}
                                     for row in packet['semantic_obligations']['obligations']]},
        }

    def decode(self, response):
        return decode_semantic_response(canonical_json_bytes(response), self.context)

    def mapping(self, field, rule, disposition='reject'):
        return dict(field_path=field, policy_rule_id=rule, disposition=disposition, decision_id=None)

    def policy_context(self, change):
        """Local policy predicate variants, not claims of registered new jobs.

        The full integration case uses the reproduced registered_context. These
        variants isolate the policy's behavior given trusted authority/assertion
        context; runtime admission of them is deliberately not claimed.
        """
        packet = self.context.packet
        change(packet)
        self.context = SemanticContext(canonical_json_bytes(packet))

    def authority_choice(self):
        def add(packet):
            target = next(row for row in packet['authority_map']['bindings'] if row['role'] == 'mutable_target')
            raw = b'Queue waiting applies before starting any work.\n'
            authority = dict(path='inputs/authority-note.md', content_hash=sha256_bytes(raw), role='normative_authority',
                             authority_scopes=target['authority_scopes'], effective_horizon='current', mutable=False,
                             may_introduce_requirements=True)
            authority['binding_id'] = binding_id(authority)
            packet['authority_map']['bindings'].append(authority)
            packet['dependency_context'].append({'binding': authority, 'content': raw.decode()})
            packet['job']['authority_map_hash'] = digest(packet['authority_map'])
        self.policy_context(add)
        packet = self.context.packet
        target = next(row for row in packet['authority_map']['bindings'] if row['role'] == 'mutable_target')
        other = packet['dependency_context'][-1]
        def option(key, raw, interpretation):
            return dict(authority_binding_id=key, interpretation=interpretation,
                        evidence=dict(byte_start=0, byte_end=len(raw), content_hash=sha256_bytes(raw), text=raw.decode()))
        return dict(question='Which interpretation should the next transaction address?', authority_scope=target['authority_scopes'][0],
                    alternatives=[option(target['binding_id'], packet['seed'].encode(), 'Waiting is scoped to queue starts.'),
                                  option(other['binding']['binding_id'], other['content'].encode(), 'Waiting is scoped to every work start.')])

    def uncertain_authority(self):
        choice = self.authority_choice()
        response = self.response()
        response.update(authority_choice=choice, authority_compliance='uncertain', operator_decision_required=True,
                        verdict='operator_decision_required', uncertainty_resolutions=[
                            self.mapping('authority_compliance', RULES['authority_choice'], 'operator_decision_required')])
        return response

    def test_registered_context_pass_copies_only_frozen_identity_and_replays_exactly(self):
        response = self.response()
        result = self.decode(response)
        report = result.verification
        self.assertEqual(report['verdict'], 'pass')
        self.assertIsNone(result.authority_request)
        self.assertEqual(report['candidate_id'], self.context.packet['creation']['candidate_id'])
        self.assertEqual(report['verifier'], self.context.packet['review_configuration']['verifier'])
        self.assertEqual(report['creation_event_hash'], self.context.packet['creation_ref']['hash'])
        validate_semantic_readback(report, None, raw=canonical_json_bytes(response), context=self.context)
        changed = deepcopy(report)
        changed['verdict'] = 'reject'
        with self.assertRaisesRegex(ValueError, 'does not reproduce'):
            validate_semantic_readback(changed, None, raw=canonical_json_bytes(response), context=self.context)

    def test_missing_duplicate_or_foreign_finding_operation_or_coverage_refuses(self):
        for field in ('finding_results', 'normative_change_assessment'):
            for action in ('missing', 'duplicate', 'foreign'):
                response = self.response()
                if action == 'missing':
                    response[field] = []
                elif action == 'duplicate':
                    response[field] *= 2
                else:
                    key = 'finding_id' if field == 'finding_results' else 'operation_id'
                    response[field][0][key] = 'foreign' if key == 'finding_id' else 'op_' + 'f' * 64
                with self.subTest(field=field, action=action), self.assertRaisesRegex(ValueError, 'coverage differs'):
                    self.decode(response)
        response = self.response()
        response['coverage']['results'] = []
        with self.assertRaisesRegex(ValueError, 'omitted'):
            self.decode(response)

    def test_useful_fix_with_unrelated_regression_cannot_pass_but_can_validly_reject(self):
        response = self.response()
        response['unrelated_semantic_change'] = 'detected'
        with self.assertRaisesRegex(ValueError, 'aggregate assessment'):
            self.decode(response)
        response['verdict'] = 'reject'
        self.assertEqual(self.decode(response).verification['verdict'], 'reject')

    def test_partial_finding_and_failed_coverage_cannot_pass(self):
        response = self.response()
        response['finding_results'][0]['disposition'] = 'partially_resolved'
        with self.assertRaisesRegex(ValueError, 'unresolved findings'):
            self.decode(response)
        response = self.response()
        response['coverage']['results'][0]['result'] = 'fail'
        with self.assertRaisesRegex(ValueError, 'nonpassing preservation'):
            self.decode(response)

    def test_loss_and_coverage_uncertainty_require_exact_reject_rules(self):
        for field in ('lost_or_weakened_semantics', 'unrelated_semantic_change', 'coverage'):
            response = self.response()
            if field == 'coverage':
                row = response['coverage']['results'][0]
                row['result'] = 'uncertain'
                path = 'coverage/results/' + row['obligation_id']
            else:
                response[field] = 'uncertain'
                path = field
            response['uncertainty_resolutions'] = [self.mapping(path, RULES[field])]
            with self.assertRaisesRegex(ValueError, 'uncertainty verdict'):
                self.decode(response)
            response['verdict'] = 'reject'
            self.assertEqual(self.decode(response).verification['verdict'], 'reject')

    def test_incomplete_duplicate_foreign_and_version_mismatched_rules_refuse(self):
        response = self.response()
        response.update(lost_or_weakened_semantics='uncertain', verdict='reject',
                        uncertainty_resolutions=[self.mapping('lost_or_weakened_semantics', RULES['lost_or_weakened_semantics'])])
        for variant in ('missing', 'duplicate', 'foreign', 'version', 'disposition'):
            changed = deepcopy(response)
            if variant == 'missing': changed['uncertainty_resolutions'] = []
            elif variant == 'duplicate': changed['uncertainty_resolutions'] *= 2
            elif variant == 'foreign': changed['uncertainty_resolutions'][0]['field_path'] = 'unrelated_semantic_change'
            elif variant == 'version': changed['uncertainty_resolutions'][0]['policy_rule_id'] = RULES['lost_or_weakened_semantics'].replace('v2', 'v1')
            else: changed['uncertainty_resolutions'][0]['disposition'] = 'operator_decision_required'
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, 'uncertainty'):
                self.decode(changed)

    def test_authority_uncertainty_without_concrete_choice_rejects(self):
        response = self.response()
        response.update(authority_compliance='uncertain', verdict='reject',
                        uncertainty_resolutions=[self.mapping('authority_compliance', RULES['authority_reject'])])
        self.assertIsNone(self.decode(response).authority_request)
        response['operator_decision_required'] = True
        with self.assertRaisesRegex(ValueError, 'operator flag'):
            self.decode(response)

    def test_concrete_authority_request_binds_candidate_verifier_raw_and_exact_excerpts(self):
        response = self.uncertain_authority()
        result = self.decode(response)
        request = result.authority_request
        report = result.verification
        self.assertEqual(report['verdict'], 'operator_decision_required')
        self.assertEqual(request['context_hash'], self.context.input_hash)
        self.assertEqual(request['verifier_response_hash'], sha256_bytes(canonical_json_bytes(response)))
        self.assertEqual(report['authority_decision_request']['hash'], digest(request))
        self.assertEqual(report['uncertainty_resolutions'][0]['decision_id'], request['decision_id'])
        self.assertEqual(request['resolution_scope'], 'new_transaction_only_no_authority_change')
        self.assertNotIn('authorized_effects', request)
        validate_semantic_readback(report, request, raw=canonical_json_bytes(response), context=self.context)
        changed = deepcopy(request)
        changed['choice']['question'] = 'Changed question'
        with self.assertRaisesRegex(ValueError, 'does not reproduce'):
            validate_semantic_readback(report, changed, raw=canonical_json_bytes(response), context=self.context)

    def test_reject_uncertainty_dominates_valid_authority_choice(self):
        response = self.uncertain_authority()
        response.update(lost_or_weakened_semantics='uncertain', verdict='reject')
        response['uncertainty_resolutions'].append(self.mapping('lost_or_weakened_semantics', RULES['lost_or_weakened_semantics']))
        result = self.decode(response)
        self.assertEqual(result.verification['verdict'], 'reject')
        self.assertIsNotNone(result.authority_request)

    def test_invalid_scope_unknown_reused_or_stale_authority_excerpt_refuses(self):
        response = self.uncertain_authority()
        for variant in ('scope', 'unknown', 'duplicate', 'hash', 'text', 'offset', 'same_interpretation'):
            changed = deepcopy(response)
            choice = changed['authority_choice']
            option = choice['alternatives'][1]
            if variant == 'scope': choice['authority_scope'] = 'foreign'
            elif variant == 'unknown': option['authority_binding_id'] = 'bind_' + 'f' * 64
            elif variant == 'duplicate': option['authority_binding_id'] = choice['alternatives'][0]['authority_binding_id']
            elif variant == 'hash': option['evidence']['content_hash'] = 'f' * 64
            elif variant == 'text': option['evidence']['text'] += 'Changed'
            elif variant == 'offset': option['evidence']['byte_end'] += 10
            else: option['interpretation'] = choice['alternatives'][0]['interpretation']
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, 'authority'):
                self.decode(changed)

    def test_excluded_reference_only_or_changed_document_cannot_supply_authority_choice(self):
        response = self.uncertain_authority()
        original = self.context
        identifier = response['authority_choice']['alternatives'][1]['authority_binding_id']
        for variant in ('excluded', 'reference_context', 'changed_document'):
            self.context = original
            def change(packet):
                if variant == 'changed_document':
                    packet['dependency_context'][-1]['content'] += 'Substituted source.'
                else:
                    next(row for row in packet['authority_map']['bindings'] if row['binding_id'] == identifier)['role'] = variant
            self.policy_context(change)
            changed = deepcopy(response)
            changed['context_hash'] = self.context.input_hash
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, 'inapplicable authority|document binding'):
                self.decode(changed)

    def test_blocking_assertion_nonpass_and_all_assertion_uncertainty_fail_closed(self):
        key = 'assert_' + 'a' * 64
        def assertion(packet):
            packet['protected_invariants']['assertions'].append(dict(assertion_id=key, enforcement='semantic', severity='blocking'))
        self.policy_context(assertion)
        for value in ('fail', 'not_applicable'):
            response = self.response()
            response['semantic_assertions'][0]['result'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'blocking assertion'):
                self.decode(response)
        response = self.response()
        response['semantic_assertions'][0]['result'] = 'uncertain'
        response['uncertainty_resolutions'] = [self.mapping('semantic_assertions/' + key, RULES['assertion'])]
        response['verdict'] = 'reject'
        self.assertEqual(self.decode(response).verification['verdict'], 'reject')
        response['semantic_assertions'] = []
        with self.assertRaisesRegex(ValueError, 'assertion coverage'):
            self.decode(response)

    def test_advisory_failure_is_visible_but_uncertainty_still_requires_reject_mapping(self):
        key = 'assert_' + 'b' * 64
        self.policy_context(lambda packet: packet['protected_invariants']['assertions'].append(
            dict(assertion_id=key, enforcement='semantic', severity='advisory')))
        response = self.response()
        response['semantic_assertions'][0]['result'] = 'fail'
        self.assertEqual(self.decode(response).verification['verdict'], 'pass')
        response['semantic_assertions'][0]['result'] = 'uncertain'
        with self.assertRaisesRegex(ValueError, 'uncertainty coverage'):
            self.decode(response)
        response['uncertainty_resolutions'] = [self.mapping('semantic_assertions/' + key, RULES['assertion'])]
        response['verdict'] = 'reject'
        self.assertEqual(self.decode(response).verification['verdict'], 'reject')

    def test_schema_errors_are_distinct_from_contradictory_context_and_client_identity(self):
        for raw in (b'{', b'{}'):
            with self.assertRaises(SemanticShapeError): decode_semantic_response(raw, self.context)
        response = self.response()
        response['context_hash'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'frozen context') as caught:
            self.decode(response)
        self.assertNotIsInstance(caught.exception, SemanticShapeError)
        response = self.response()
        response['uncertainty_resolutions'] = [dict(field_path='authority_compliance', policy_rule_id=RULES['authority_choice'],
                                                  disposition='operator_decision_required', decision_id='dec_' + 'f' * 64)]
        with self.assertRaisesRegex(ValueError, 'Orchestrator-owned') as caught:
            self.decode(response)
        self.assertNotIsInstance(caught.exception, SemanticShapeError)

    def test_unsupported_policy_refuses_before_raw_shape_parsing(self):
        self.policy_context(lambda packet: packet['job'].update(semantic_verifier_policy_version='semantic-policy-v1'))
        with self.assertRaisesRegex(ValueError, 'unsupported semantic verifier policy') as caught:
            decode_semantic_response(b'{', self.context)
        self.assertNotIsInstance(caught.exception, SemanticShapeError)

    def test_verifier_prompt_is_separate_read_only_and_binds_complete_context(self):
        import json
        prompt = semantic_verifier_prompt(self.context)
        packet = json.loads(prompt.splitlines()[-1])
        self.assertEqual(packet['context_hash'], self.context.input_hash)
        self.assertEqual(packet['context'], self.context.packet)
        self.assertEqual(packet['uncertainty_rule_ids'], RULES)
        self.assertEqual(packet['response_schema_version'], 'semantic-verification-v2')
        self.assertIn('independent Semantic Verifier', prompt)
        self.assertIn('Do not edit files', prompt)
        self.assertIn('claims are untrusted evidence', prompt)
        self.assertNotIn('Produce one JSON object with schema_version = vnext-proposal-response-v2', prompt)

    def test_changed_editor_claim_blank_rationale_and_unbound_operator_verdict_refuse(self):
        for variant in ('claim', 'rationale', 'operator'):
            response = self.response()
            if variant == 'claim': response['normative_change_assessment'][0]['editor_claim'] = 'weaken'
            elif variant == 'rationale': response['rationale'] = ' \n\t'
            else: response['verdict'] = 'operator_decision_required'
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, 'Editor claim|blank|bound request'):
                self.decode(response)


if __name__ == '__main__':
    unittest.main()
