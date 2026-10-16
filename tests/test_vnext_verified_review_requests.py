from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_review_requests import _ReviewInputs, _VerifiedReviewRequest, _run_bound_review
from whetstone.vnext_verified_work import _BorrowedFence
from vnext_fixtures import STAMP
import test_vnext_verified_history as history
import test_vnext_verified_promotion as promotion


class Reviewer:
    def __init__(self, f, callback=None):
        self.identity = json.loads(f.store.read(f.admission._refs['review']['path']))['reviewer']
        record = json.loads(f.store.read(f.admission._refs['rounds'][1]['path']))
        self.feedback = json.loads(f.store.read(record['feedback']['path']))
        self.hints = json.loads(f.store.read(record['advice']['path']))['findings']
        self.calls, self.timeout, self.callback, self.prompts = 0, 5, callback, []

    @property
    def transport_binding(self):
        return dict(reviewer=deepcopy(self.identity), command='fictional-v-reviewer', cwd='/fictional',
                    timeout_seconds=self.timeout, output_schema_hash='a' * 64)

    def review(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        request = json.loads(prompt.splitlines()[-1])
        feedback = deepcopy(self.feedback)
        feedback.update(round_number=request['round_number'], profile=request['profile'],
                        draft_hash=request['base_draft_hash'], reviewer=deepcopy(self.identity))
        response = dict(schema_version='vnext-review-response-v1', feedback=feedback, classifications=deepcopy(self.hints))
        return self.callback(response) if self.callback else canonical_json_bytes(response)


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedReviewRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): history.VerifiedHistoryTests.setUpClass()
    files = promotion.VerifiedPromotionTests.files
    owner = promotion.VerifiedPromotionTests.owner
    ready = promotion.VerifiedPromotionTests.ready
    run_request = promotion.VerifiedPromotionTests.run_request
    verified = promotion.VerifiedPromotionTests.verified
    service = promotion.VerifiedPromotionTests.service
    materialize_seed = promotion.VerifiedPromotionTests.materialize_seed

    def fixture(self, *, register_candidate=True, reviewer_contract=True):
        algorithms = ('vnext_verified_materialization_v1', 'vnext_verified_promotion_v1', 'vnext_verified_work_v1')
        if reviewer_contract: algorithms += ('vnext_verified_review_requests_v1',)
        return history.VerifiedHistoryTests.fixture(self, extra_algorithms=algorithms,
            register_candidate=register_candidate, extra_schemas={'vnext_review_request_v2'})

    def seed(self):
        f = self.fixture(register_candidate=False)
        self.materialize_seed(f)
        return f

    def request(self, f, *, number=1, client=None, continuation=False, base=None, previous=None):
        owner = self.owner(f)
        with f.store.locked(owner.validate_authority) as token:
            proof = owner._prove(f.store.read)
            inputs = _ReviewInputs(_BorrowedFence(f.store, token), proof, base or proof.latest)
            request = _VerifiedReviewRequest(inputs, number, proof.seed_values['review']['profiles'][0]['name'])
            return _run_bound_review(request, token, previous=previous, client=client, continuation=continuation)

    def inspect(self, f, *, number=1, base=None, previous=None):
        proof = self.owner(f)._prove(f.store.read)
        inputs = _ReviewInputs(proof.store, proof, base or proof.latest)
        request = _VerifiedReviewRequest(inputs, number, proof.seed_values['review']['profiles'][0]['name'])
        return request, request.read_claim(previous)

    def test_seed_and_promoted_review_use_exact_base_and_keep_original_seed(self):
        for promoted in (False, True):
            with self.subTest(promoted=promoted):
                f = self.verified() if promoted else self.seed()
                if promoted:
                    self.materialize_seed(f)
                    self.service(f).promote(prepared_at=STAMP)
                before = self.files(f)
                current = json.loads(f.store.read('rounds/current_verified.json'))
                reviewer = Reviewer(f)
                result = self.request(f, number=2, client=reviewer)
                self.assertEqual((result.status, reviewer.calls), ('complete', 1))
                self.assertEqual(result.review['feedback']['draft_hash'], current['verified_draft_hash'])
                self.assertEqual(result.review['advice']['base_draft_hash'], current['verified_draft_hash'])
                prompt = json.loads(reviewer.prompts[0].splitlines()[-1])
                self.assertEqual(prompt['base'].encode(), f.store.read(current['verified_draft_path']))
                self.assertEqual(prompt['seed'].encode(), f.store.read(prompt['job']['seed_draft']['path']))
                self.assertEqual(prompt['base_pointer_ref']['path'], f"rounds/verified_history/current-verified-{current['promotion_ordinal']}.json")
                header = json.loads(f.store.read('rounds/review_index/request-2.json'))
                self.assertEqual(header['schema_version'], 'vnext-review-request-v2')
                self.assertEqual(header['base_pointer'], prompt['base_pointer_ref'])
                self.assertEqual(f.store.read('rounds/current_verified.json'), before['rounds/current_verified.json'])
                self.assertEqual(f.store.read('spec.md'), before['spec.md'])

    def test_original_base_replays_after_promotion_but_cannot_invoke(self):
        f = self.verified()
        self.materialize_seed(f)
        reference = self.owner(f)._prove(f.store.read).latest
        reviewer = Reviewer(f)
        result = self.request(f, client=reviewer)
        self.service(f).promote(prepared_at=STAMP)
        before = self.files(f)
        historical, (_, _, _, receipt) = self.inspect(f, base=reference)
        self.assertEqual(receipt, result.receipt)
        with self.assertRaisesRegex(ValueError, 'historical Reviewer evidence cannot'):
            _run_bound_review(historical, None, previous=None, client=reviewer)
        with self.assertRaisesRegex(ValueError, 'exact current base pointer'):
            self.request(f, client=reviewer, base=reference)
        self.assertEqual(reviewer.calls, 1)
        self.assertEqual(self.files(f), before)

    def test_scope_guidance_and_invalid_surface_advice_do_not_allow_retry(self):
        f = self.seed()
        def invalid(packet):
            packet['classifications'][0]['scope_surface_ids'] = ['sec_' + 'a' * 64]
            return canonical_json_bytes(packet)
        reviewer = Reviewer(f, invalid)
        result = self.request(f, client=reviewer)
        self.assertEqual(result.status, 'invalid_review')
        self.assertIn('scope surfaces supplied without a scope contract', result.last_outcome['error'])
        self.assertIn('every classification MUST use "scope_surface_ids": []', reviewer.prompts[0])
        self.assertIn('scope.scope_surfaces', reviewer.prompts[0])
        self.assertIn('canonical_section_id values from base_section_map', reviewer.prompts[0])
        before = self.files(f)
        self.assertEqual(self.request(f, client=reviewer, continuation=True).status, 'invalid_review')
        self.assertEqual(reviewer.calls, 1)
        self.assertEqual(self.files(f), before)

    def test_previous_prompt_replays_exactly_but_tampering_is_rejected(self):
        from whetstone import vnext_verified_review_protocol as protocol
        f = self.seed()
        reviewer = Reviewer(f)
        with patch.object(protocol, 'SCOPE_GUIDANCE', ''):
            result = self.request(f, client=reviewer)
        self.assertEqual(result.status, 'complete')
        before = self.files(f)
        request, (_, _, _, receipt) = self.inspect(f)
        self.assertEqual(receipt, result.receipt)
        self.assertEqual(request.preflight.prompt, reviewer.prompts[0])
        self.assertEqual(self.request(f, client=reviewer).status, 'complete')
        self.assertEqual(reviewer.calls, 1)
        self.assertEqual(self.files(f), before)
        path = f.store.root / request.directory / 'original_prompt.txt'
        path.write_bytes(path.read_bytes() + b'\nChanged guidance')
        with self.assertRaisesRegex(ValueError, 'Reviewer prompt changed'):
            self.inspect(f)

    def test_previous_prompt_continuation_keeps_original_instructions(self):
        from whetstone import vnext_verified_review_protocol as protocol
        f = self.seed()
        def timeout(packet):
            raise TimeoutError('fixture provider timeout')
        reviewer = Reviewer(f, timeout)
        with patch.object(protocol, 'SCOPE_GUIDANCE', ''):
            result = self.request(f, client=reviewer)
        self.assertEqual(result.status, 'timeout')
        original = reviewer.prompts[0]
        reviewer.callback = None
        self.assertEqual(self.request(f, client=reviewer, continuation=True).status, 'complete')
        self.assertEqual(reviewer.calls, 2)
        self.assertEqual(reviewer.prompts[1], original)

    def test_same_byte_promotion_cannot_alias_original_request_pointer(self):
        client_type = history.verified.fixtures.Client
        def unchanged(packet):
            content = 'Queue always waits.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        with patch.object(history.verified.fixtures, 'Client', side_effect=lambda callback=None: client_type(callback or unchanged)):
            f = self.verified()
        self.materialize_seed(f)
        reference = self.owner(f)._prove(f.store.read).latest
        self.request(f, client=Reviewer(f))
        original, _ = self.inspect(f)
        self.service(f).promote(prepared_at=STAMP)
        before = self.files(f)
        proof = self.owner(f)._prove(f.store.read)
        current = _VerifiedReviewRequest(_ReviewInputs(proof.store, proof, proof.latest), 1, original.profile)
        self.assertEqual(current.preflight.arguments['base'], original.preflight.arguments['base'])
        self.assertNotEqual(current.preflight.input_hash, original.preflight.input_hash)
        with self.assertRaisesRegex(ValueError, 'original base and inputs'): current.read_claim(None)
        self.assertIsNotNone(self.inspect(f, base=reference)[1][-1])
        self.assertEqual(self.files(f), before)

    def test_claim_and_raw_output_recover_without_resetting_slots_or_calling_again(self):
        for suffix in ('review_index/request-1.json', '/response.json', '/reviewer_feedback.json', '/result.json'):
            with self.subTest(suffix=suffix):
                f = self.seed()
                reviewer = Reviewer(f)
                publish = f.store.publish
                def stop(token, path, value):
                    result = publish(token, path, value)
                    if path.endswith(suffix): raise OSError('Reviewer interruption')
                    return result
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'Reviewer interruption'): self.request(f, client=reviewer)
                calls = reviewer.calls
                before = self.files(f)
                _, (_, outcomes, review, receipt) = self.inspect(f)
                self.assertEqual(self.files(f), before)
                if receipt is not None:
                    result = self.request(f)
                else:
                    self.assertEqual(self.request(f).status, 'continuation_required')
                    result = self.request(f, client=reviewer if review is None else None, continuation=True)
                self.assertEqual(result.status, 'complete')
                self.assertEqual(reviewer.calls, calls if calls else 1)
                self.assertEqual(result.attempts, 1)

    def test_shape_timeout_and_binding_failures_preserve_two_slot_policy(self):
        f = self.seed()
        reviewer = Reviewer(f)
        reviewer.callback = lambda response: b'{}' if reviewer.calls == 1 else canonical_json_bytes(response)
        result = self.request(f, client=reviewer)
        self.assertEqual((result.status, result.attempts, reviewer.calls), ('complete', 2, 2))
        g = self.seed()
        def timeout(response): raise TimeoutError('fictional V review timeout')
        first = Reviewer(g, timeout)
        self.assertEqual(self.request(g, client=first).status, 'timeout')
        resumed = Reviewer(g)
        resumed.timeout = 9
        self.assertEqual(self.request(g, client=resumed).status, 'continuation_required')
        self.assertEqual(resumed.calls, 0)
        self.assertEqual(self.request(g, client=resumed, continuation=True).attempts, 2)
        h = self.seed()
        def invalid(response):
            response['feedback']['draft_hash'] = 'f' * 64
            return canonical_json_bytes(response)
        bad = Reviewer(h, invalid)
        self.assertEqual(self.request(h, client=bad).status, 'invalid_review')
        self.assertEqual(self.request(h, continuation=True).status, 'invalid_review')
        self.assertEqual(bad.calls, 1)

    def test_changed_authority_during_call_retains_raw_but_refuses_result(self):
        f = self.seed()
        job = json.loads(f.store.read_descriptor())
        path = f.root / job['authority_map_path']
        def alter(response):
            path.write_bytes(path.read_bytes() + b' ')
            return canonical_json_bytes(response)
        reviewer = Reviewer(f, alter)
        with self.assertRaises(ValueError): self.request(f, client=reviewer)
        self.assertEqual(reviewer.calls, 1)
        self.assertTrue(list(f.root.glob('rounds/client_requests/*/attempts/1/response.json')))
        self.assertFalse(list(f.root.glob('rounds/client_requests/*/result.json')))

    def test_unproven_base_and_missing_contract_refuse_before_writes(self):
        f = self.seed()
        proof = self.owner(f)._prove(f.store.read)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'has not been proven'):
            _VerifiedReviewRequest(_ReviewInputs(proof.store, proof,
                dict(path='rounds/verified_history/current-verified-7.json', hash=proof.latest['hash'])), 1,
                proof.seed_values['review']['profiles'][0]['name'])
        self.assertEqual(self.files(f), before)
        g = self.fixture(register_candidate=False, reviewer_contract=False)
        before = self.files(g)
        with self.assertRaisesRegex(ValueError, 'Reviewer contracts are outside supported suite'):
            self.request(g, client=Reviewer(g))
        self.assertEqual(self.files(g), before)


if __name__ == '__main__': unittest.main()
