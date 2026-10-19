"""Projection tests; original transaction admission is exercised by integration tests."""
from copy import deepcopy
from types import SimpleNamespace
import json
import sys
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_reviewer_decision_history import promoted_decisions
from whetstone.vnext_verified_history import _Proof


class DecisionHistoryProjectionTests(unittest.TestCase):
    def fixture(self):
        def ref(path, value):
            return dict(path=path, hash=sha256_bytes(canonical_json_bytes(value)))
        request = dict(decision_id='decision', base_draft_hash='original-base')
        response = dict(response_id='response', authorized_effects=['add'])
        finding = dict(finding_id='derived', decision_response_id='response', admitted_to_editing=True)
        plan = dict(transaction_id='transaction', finding_dispositions=[finding])
        choice = dict(finding_id='original', request=ref('request.json', request),
                      response=ref('response.json', response))
        record = dict(decision_refs=[choice])
        record_ref = ref('round.json', record)
        objects = {'round.json': record, 'request.json': request, 'response.json': response}
        def read(reference, schema):
            value = objects[reference['path']]
            if sha256_bytes(canonical_json_bytes(value)) != reference['hash']:
                raise ValueError('source hash changed')
            return deepcopy(value)
        proof = SimpleNamespace(store=object(), reader=SimpleNamespace(json=read),
            owner=SimpleNamespace(_refs={'rounds': {1: record_ref}}))
        router = SimpleNamespace(load_inputs=SimpleNamespace(request_journal=lambda *args:
            SimpleNamespace(preflight=SimpleNamespace(plan=plan))))
        args = dict(base_pointer_ref={'path': 'base.json', 'hash': 'original'}, decisions=[
            dict(finding_id='original', request=request, response=response, feedback_refs=['feedback'])])
        creation = dict(round_number=1, proposal_id='proposal', candidate_id='candidate')
        pointer = dict(promotion_ordinal=1)
        return proof, router, creation, pointer, args, objects, plan

    def test_selected_approval_keeps_original_bindings_and_promotion_link(self):
        proof, router, creation, pointer, args, objects, plan = self.fixture()
        entry, = promoted_decisions(proof, router, creation, pointer, args)
        self.assertEqual(entry['source_base'], args['base_pointer_ref'])
        self.assertEqual(entry['request']['base_draft_hash'], 'original-base')
        self.assertEqual(entry['selected_effects'], ['add'])
        self.assertEqual(entry['promotion']['hash'], sha256_bytes(canonical_json_bytes(pointer)))
        self.assertEqual(entry['plan_hash'], sha256_bytes(canonical_json_bytes(plan)))
        entry['response']['authorized_effects'].clear()
        self.assertEqual(args['decisions'][0]['response']['authorized_effects'], ['add'])

    def test_missing_and_tampered_source_refuse_projection(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                proof, router, creation, pointer, args, objects, _ = self.fixture()
                if missing:
                    del objects['request.json']
                else:
                    objects['request.json']['base_draft_hash'] = 'changed-base'
                with self.assertRaises((ValueError, KeyError)):
                    promoted_decisions(proof, router, creation, pointer, args)

    def test_unused_decisions_are_not_projected(self):
        proof, router, creation, pointer, args, _, plan = self.fixture()
        plan['finding_dispositions'][0]['admitted_to_editing'] = False
        self.assertEqual(promoted_decisions(proof, router, creation, pointer, args), [])

    def test_incomplete_used_decisions_refuse_projection(self):
        proof, router, creation, pointer, args, _, plan = self.fixture()
        plan['finding_dispositions'].append(dict(finding_id='other', decision_response_id='missing',
                                                admitted_to_editing=True))
        with self.assertRaisesRegex(ValueError, 'history is incomplete'):
            promoted_decisions(proof, router, creation, pointer, args)

    def test_selected_base_reads_only_its_own_detached_history(self):
        proof = object.__new__(_Proof)
        reference = dict(path='seed', hash='seed-hash')
        proof.values = lambda ref: self.assertEqual(ref, reference)
        proof.guard = lambda read: None
        proof.store = SimpleNamespace(read=lambda path: b'')
        proof.reviewer_decisions = {'seed': canonical_json_bytes([]),
                                   'future': canonical_json_bytes([{'unpromoted': True}])}
        history = proof.decision_history(reference)
        history.append('mutated')
        self.assertEqual(proof.decision_history(reference), [])
        del proof.reviewer_decisions['seed']
        with self.assertRaisesRegex(ValueError, 'missing proven'):
            proof.decision_history(reference)


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class DecisionHistoryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_vnext_verified_runtime_decision_refs as decisions
        decisions.RuntimeDecisionReferenceTests.setUpClass()

    def test_promoted_approval_reaches_next_reviewer_and_tampering_refuses(self):
        import test_vnext_verified_runtime_decision_refs as decisions
        import test_vnext_verified_review as runtime
        helpers = decisions.RuntimeDecisionReferenceTests
        self.fixture = lambda **kw: helpers.fixture(self, **kw)
        self.start = lambda **kw: helpers.start(self, **kw)
        self.files = lambda f: helpers.files(self, f)
        f, reviewer, _, choice, response, _ = helpers.decision(self)
        f.run.admit_reviewed_round(decision_refs=[choice])
        from vnext_fixtures import STAMP
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        import test_vnext_verified_history as history
        # A real admitted and registered candidate is not promoted ancestry.
        self.assertEqual(f.run.request(round_number=1, client=f.editor).value.status, 'complete')
        creation = f.run.register(round_number=1, created_at=STAMP).value
        proof = f.run._history()._prove(f.store.read)
        self.assertEqual(proof.decision_history(proof.latest), [])
        context = load_registered_semantic_context(f.store, admission=f.run._history(),
                                                 candidate_id=creation['candidate_id'])
        verifier = history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 1)
        proof = f.run._history()._prove(f.store.read)
        seed = dict(path='rounds/verified_history/current-verified-0.json',
                    hash=sha256_bytes(f.store.read('rounds/verified_history/current-verified-0.json')))
        self.assertEqual(proof.decision_history(seed), [])
        self.assertEqual(f.run.review_next(client=reviewer).status, 'complete')
        packet = json.loads(reviewer.prompts[-1].splitlines()[-1])
        entry, = packet['historical_operator_decisions']
        self.assertEqual(entry['response'], response)
        self.assertEqual(entry['request_ref'], choice['request'])
        self.assertEqual(entry['response_ref'], choice['response'])
        self.assertEqual(entry['source_base'], seed)
        self.assertEqual(entry['promotion'], packet['base_pointer_ref'])
        # A previous approval does not authorize the new round's weakening.
        self.assertEqual(f.run.review_status().status, 'finding_admission')
        with self.assertRaises(ValueError):
            f.run.admit_reviewed_round(decision_refs=[choice])
        self.assertEqual(reviewer.calls, 2)
        # Removing history from the new retained prompt is not an eligible
        # historical rendering: its header still binds the new input packet.
        prompt_path = next(path for path in f.root.glob('rounds/client_requests/*/original_prompt.txt')
                           if path.read_text() == reviewer.prompts[-1])
        original_prompt = prompt_path.read_bytes()
        altered_packet = deepcopy(packet)
        del altered_packet['historical_operator_decisions']
        lines = reviewer.prompts[-1].splitlines()
        prompt_path.write_text('\n'.join(lines[:-1]) + '\n' + canonical_json_bytes(altered_packet).decode())
        before = self.files(f)
        with self.assertRaises(ValueError):
            f.run.review_status()
        self.assertEqual(self.files(f), before)
        prompt_path.write_bytes(original_prompt)
        # Missing and tampered committed approval evidence both refuse without
        # a client, repair, or silently dropping history from the request.
        response_path = f.root / choice['response']['path']
        original_response = response_path.read_bytes()
        for missing in (True, False):
            with self.subTest(missing=missing):
                if missing:
                    response_path.unlink()
                else:
                    response_path.write_bytes(b'{}')
                before = self.files(f)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    proof.decision_history(proof.latest)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    f.run.review_status()
                self.assertEqual(reviewer.calls, 2)
                self.assertEqual(self.files(f), before)
                response_path.write_bytes(original_response)
