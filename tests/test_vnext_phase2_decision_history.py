"""Phase 2 history visibility and exact pre-history request compatibility."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_phase2_review import INPUT_PATH, PROMPT_PATH, REQUEST_PATH, RESPONSE_SCHEMA
import test_vnext_verified_phase2_review as review
import test_vnext_verified_review as runtime
import test_vnext_verified_runtime_decision_refs as decisions
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class Phase2DecisionHistoryTests(unittest.TestCase):
    setUpClass = review.VerifiedPhase2ReviewTests.setUpClass
    fixture = runtime.VerifiedReviewTests.fixture
    files = runtime.VerifiedReviewTests.files
    reopen = runtime.VerifiedReviewTests.reopen
    config = review.VerifiedPhase2ReviewTests.config
    ready = review.VerifiedPhase2ReviewTests.ready

    def start(self, **options):
        return runtime.VerifiedReviewTests.start(self, **options)

    def test_legacy_partial_and_committed_request_replay_is_exact(self):
        f, client, _, transport = self.ready()
        from whetstone import vnext_reviewer_decision_history as history
        publish = f.store.publish
        def stop(token, path, value):
            if path == PROMPT_PATH:
                raise OSError('old inputs published before prompt')
            return publish(token, path, value)
        with patch.object(history, 'phase2_history', side_effect=lambda proof, inputs, prompt: (inputs, prompt)):
            expected = f.run.prepare_phase2_review(transport)
            with patch.object(f.store, 'publish', side_effect=stop):
                with self.assertRaisesRegex(OSError, 'old inputs'):
                    f.run.bind_phase2_review(transport)
        self.assertNotIn('historical_operator_decisions', expected.inputs)
        before = self.files(f)
        recovered = f.run.prepare_phase2_review(transport)
        self.assertEqual(recovered.request, expected.request)
        self.assertEqual(recovered.prompt, expected.prompt)
        self.assertEqual(self.files(f), before)
        bound = f.run.bind_phase2_review(transport)
        self.assertEqual(bound.request, expected.request)
        self.reopen(f)
        before = self.files(f)
        self.assertEqual(f.run.bind_phase2_review(transport).request, expected.request)
        self.assertEqual(self.files(f), before)
        # Missing committed inputs cannot be reconstructed just because the
        # old prompt is recognizable. Nor can arbitrary old prompt edits pass.
        for missing in (True, False):
            path = f.root / (INPUT_PATH if missing else PROMPT_PATH)
            raw = path.read_bytes()
            if missing: path.unlink()
            else: path.write_bytes(raw + b' altered')
            before = self.files(f)
            with self.assertRaises(ValueError): f.run.prepare_phase2_review(transport)
            self.assertEqual(self.files(f), before)
            path.write_bytes(raw)
        self.assertEqual(client.calls, 1)

    def test_legacy_execution_continuation_preserves_prompt_and_slots(self):
        import test_vnext_verified_phase2_client as clients
        from whetstone import vnext_reviewer_decision_history as history
        f, client, _ = clients.VerifiedPhase2ClientTests.ready(self, bind=False)
        def timeout(owner, feedback): raise TimeoutError('old request timeout')
        client.callback = timeout
        with patch.object(history, 'phase2_history', side_effect=lambda proof, inputs, prompt: (inputs, prompt)):
            original = f.run.bind_phase2_review(client.transport_binding)
            self.assertEqual(f.run.run_phase2_review(client=client).status, 'timeout')
        self.assertNotIn('historical_operator_decisions', original.inputs)
        self.reopen(f)
        self.assertEqual(f.run.run_phase2_review(client=client).status, 'continuation_required')
        self.assertEqual(client.calls, 1)
        client.callback = None
        result = f.run.run_phase2_review(client=client, continuation=True)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.receipt['attempt'], 2)
        self.assertEqual(client.prompts, [original.prompt, original.prompt])
        before = self.files(f)
        self.assertEqual(f.run.run_phase2_review(client=client).status, 'complete')
        self.assertEqual(client.calls, 2)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.run.prepare_phase2_review(client.transport_binding).request, original.request)

    def test_promoted_phase1_approval_reaches_phase2_and_sources_remain_guarded(self):
        # Real phase 1 decision/admission/promotion, then actual Phase 2 entry.
        self.start = lambda **options: runtime.VerifiedReviewTests.start(
            self, phase2_review_contract=True, budget=3, **options)
        f, client, _, choice, response, _ = decisions.RuntimeDecisionReferenceTests.decision(self)
        f.run.admit_reviewed_round(decision_refs=[choice])
        runtime.VerifiedReviewTests.promote(self, f)
        client.callback = clean_response
        f.run.review_next(client=client)
        f.run.finish_phase1(); f.run.reconcile_phase1_state()
        f.run.bind_phase2_entry(self.config(f)); f.run.enter_phase2()
        transport = deepcopy(client.transport_binding)
        transport['output_schema_hash'] = sha256_bytes((CONTRACT_ROOT/'schemas'/(RESPONSE_SCHEMA+'.schema.json')).read_bytes())
        from whetstone import vnext_reviewer_decision_history as history
        with patch.object(history, 'phase2_history', side_effect=lambda proof, inputs, prompt: (inputs, prompt)):
            legacy_preview = f.run.prepare_phase2_review(transport)
        preview = f.run.prepare_phase2_review(transport)
        entry, = preview.inputs['historical_operator_decisions']
        self.assertEqual(entry['response'], response)
        self.assertNotEqual(entry['source_base'], preview.request['base_pointer'])
        self.assertEqual(entry['promotion'], preview.request['base_pointer'])
        self.assertIn(choice['response'], preview.inputs['sources'])
        self.assertIn('not current mutation authority', preview.prompt)
        self.assertEqual(json.loads(preview.prompt.splitlines()[-1]), preview.inputs)
        sync = f.store.synchronize_existing
        def fail(token, path, **kwargs):
            if path == choice['response']['path']: raise OSError('historical response barrier')
            return sync(token, path, **kwargs)
        with patch.object(f.store, 'synchronize_existing', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'historical response barrier'):
                f.run.bind_phase2_review(transport)
        self.assertFalse((f.root/INPUT_PATH).exists())
        bound = f.run.bind_phase2_review(transport)
        self.assertEqual(bound.request, preview.request)
        # Replacing the new input packet with exact old-format bytes must not
        # downgrade a request whose immutable header binds the history packet.
        original = (f.root/INPUT_PATH).read_bytes()
        legacy = legacy_preview.inputs
        (f.root/INPUT_PATH).write_bytes(canonical_json_bytes(legacy))
        before = self.files(f)
        with self.assertRaises(ValueError): f.run.prepare_phase2_review(transport)
        self.assertEqual(self.files(f), before)
        (f.root/INPUT_PATH).write_bytes(original)
        source = f.root/choice['response']['path']; source.write_bytes(b'{}')
        before = self.files(f)
        with self.assertRaises(ValueError): f.run.prepare_phase2_review(transport)
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 2)
