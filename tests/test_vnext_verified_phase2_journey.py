"""Scripted integrated first Phase 2 correction with actual V runtime owners."""
import json
import sys
import subprocess
import unittest
from unittest.mock import patch
from copy import deepcopy

import test_vnext_verified_phase2_advice as advice_tests
import test_vnext_verified_phase2_client as clients
import test_vnext_verified_review as runtime
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class Phase2JourneyTests(unittest.TestCase):
    setUpClass = advice_tests.Phase2AdviceTests.setUpClass
    fixture = advice_tests.Phase2AdviceTests.fixture
    files = advice_tests.Phase2AdviceTests.files
    reopen = advice_tests.Phase2AdviceTests.reopen
    config = advice_tests.Phase2AdviceTests.config
    ready = advice_tests.Phase2AdviceTests.ready
    reviewed = advice_tests.Phase2AdviceTests.reviewed
    review = runtime.VerifiedReviewTests.review
    promote = runtime.VerifiedReviewTests.promote

    def start(self, **kwargs):
        kwargs['phase2_round_contract'] = True
        return clients.VerifiedPhase2ClientTests.start(self, **kwargs)

    def admitted(self, *, promoted=False):
        original = self.ready
        with patch.object(self, 'ready', side_effect=lambda **kw: original(promoted=promoted, **kw)):
            f, reviewer, config, advice = self.reviewed()
        f.run.bind_phase2_advice(advice)
        ref = f.run.admit_phase2_round()
        record = json.loads(f.store.read(ref['path']))
        return f, reviewer, config, advice, ref, record['round_number']

    def candidate(self, f, number):
        self.assertEqual(f.run.request(round_number=number, client=f.editor).value.status, 'complete')
        creation = f.run.register(round_number=number, created_at=STAMP).value
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=creation['candidate_id'])
        verifier = runtime.history.verified.semantic.Client(context)
        return creation, verifier

    def test_seed_entry_correction_promotes_and_reopens_without_duplicate_work(self):
        f, reviewer, _, _, ref, number = self.admitted()
        before = f.store.read('rounds/current_verified.json')
        self.assertEqual(f.run.admit_phase2_round(), ref)
        creation, verifier = self.candidate(f, number)
        self.assertEqual(f.store.read('rounds/current_verified.json'), before)
        final = f.run.verify(client=verifier, decided_at=STAMP)
        self.assertTrue(final.value.decision['promotion_permitted'])
        result = f.run.promote(prepared_at=STAMP)
        self.assertEqual(result.outcome, 'promoted')
        self.assertEqual(result.current_pointer['promotion_ordinal'], 1)
        before_files = self.files(f)
        script = """import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path,number=sys.argv[1:]; manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    original=run._history().load_inputs(run.store.read,int(number))
    print(json.dumps(dict(outcome=run.inspect().outcome,base=original['base_pointer_ref']['path'])))
"""
        child = subprocess.run([sys.executable, '-c', script, str(f.root), str(f.admission.suite_path), str(number)],
                               capture_output=True, timeout=120)
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        self.assertEqual(json.loads(child.stdout), dict(outcome='work_available',base='rounds/verified_history/current-verified-0.json'))
        self.assertEqual(self.files(f), before_files)
        self.reopen(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        with self.assertRaises(ValueError): f.run.request(round_number=number, client=f.editor)
        self.assertEqual((reviewer.calls, f.editor.calls, verifier.calls), (1,1,1))
        self.assertEqual(f.run._history().load_inputs(f.store.read, number)['base_pointer_ref']['path'],
                         'rounds/verified_history/current-verified-0.json')

    def test_promoted_entry_corrects_its_original_base_and_replays_after_second_promotion(self):
        f, reviewer, _, _, ref, number = self.admitted(promoted=True)
        before = json.loads(f.store.read('rounds/current_verified.json'))
        self.assertEqual(before['promotion_ordinal'], 1)
        def correction(packet):
            content = 'Queue always waits before beginning work.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        f.editor.callback = correction
        creation, verifier = self.candidate(f, number)
        self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        promoted = f.run.promote(prepared_at=STAMP).current_pointer
        self.assertEqual(promoted['promotion_ordinal'], 2)
        self.assertNotEqual(promoted['verified_draft_hash'], before['verified_draft_hash'])
        self.reopen(f)
        self.assertEqual(f.run._history().load_inputs(f.store.read, number)['base_pointer_ref']['path'],
                         'rounds/verified_history/current-verified-1.json')
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertEqual((reviewer.calls, f.editor.calls, verifier.calls), (1,2,1))

    def test_invalid_proposal_and_semantic_rejection_preserve_authority(self):
        f, reviewer, _, _, _, number = self.admitted()
        before = f.store.read('rounds/current_verified.json')
        def invalid(packet):
            packet['patch']['base_draft_hash'] = 'f'*64
            return canonical_json_bytes(packet)
        f.editor.callback = invalid
        self.assertEqual(f.run.request(round_number=number, client=f.editor).value.status, 'invalid_proposal')
        self.reopen(f)
        self.assertEqual(f.run.request(round_number=number, client=f.editor).value.status, 'invalid_proposal')
        with self.assertRaises(ValueError): f.run.register(round_number=number, created_at=STAMP)
        self.assertEqual(f.store.read('rounds/current_verified.json'), before)
        self.assertEqual(f.editor.calls, 1)
        g, reviewer, _, _, _, number = self.admitted()
        before = g.store.read('rounds/current_verified.json')
        _, verifier = self.candidate(g, number)
        response = json.loads(verifier.valid)
        response.update(verdict='reject', unrelated_semantic_change='detected')
        verifier.responses = [canonical_json_bytes(response)]
        decision = g.run.verify(client=verifier, decided_at=STAMP).value.decision
        self.assertEqual(decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        self.assertFalse(decision['promotion_permitted'])
        self.reopen(g)
        self.assertEqual(g.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertEqual(g.run.verify(decided_at=STAMP).value.decision, decision)
        self.assertEqual(g.store.read('rounds/current_verified.json'), before)
        self.assertEqual((reviewer.calls, g.editor.calls, verifier.calls), (1,1,1))

    def test_interrupted_publication_clients_promotion_and_final_state_recover(self):
        from whetstone.vnext_verified_materialization import STATE_PATH
        f, reviewer, _, advice = self.reviewed()
        f.run.bind_phase2_advice(advice)
        publish = f.store.publish
        def lose_round(token, path, value):
            result = publish(token, path, value)
            if path.endswith('/proposal_input.json'): raise OSError('round lost ack')
            return result
        with patch.object(f.store, 'publish', side_effect=lose_round):
            with self.assertRaisesRegex(OSError, 'round lost ack'): f.run.admit_phase2_round()
        self.reopen(f)
        ref = f.run.admit_phase2_round()
        number = json.loads(f.store.read(ref['path']))['round_number']
        original_pointer = f.store.read('rounds/current_verified.json')
        def lose_response(original):
            def wrapped(token, path, value):
                result = original(token, path, value)
                if path.endswith('/response.json'): raise OSError('response lost ack')
                return result
            return wrapped
        with patch.object(f.store, 'publish', side_effect=lose_response(f.store.publish)):
            with self.assertRaisesRegex(OSError, 'response lost ack'):
                f.run.request(round_number=number, client=f.editor)
        self.reopen(f)
        self.assertEqual(f.run.request(round_number=number).outcome, 'continuation_required')
        self.assertEqual(f.run.request(round_number=number, continuation=True).value.status, 'complete')
        creation = f.run.register(round_number=number, created_at=STAMP).value
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=creation['candidate_id'])
        verifier = runtime.history.verified.semantic.Client(context)
        with patch.object(f.store, 'publish', side_effect=lose_response(f.store.publish)):
            with self.assertRaisesRegex(OSError, 'response lost ack'): f.run.verify(client=verifier, decided_at=STAMP)
        self.reopen(f)
        self.assertTrue(f.run.verify(decided_at=STAMP, continuation=True).value.decision['promotion_permitted'])
        self.assertEqual(f.store.read('rounds/current_verified.json'), original_pointer)
        replace = f.store.replace_pointer
        def lose_pointer(token, path, **kwargs):
            result = replace(token, path, **kwargs)
            if path == 'rounds/current_verified.json': raise OSError('pointer lost ack')
            return result
        with patch.object(f.store, 'replace_pointer', side_effect=lose_pointer):
            with self.assertRaisesRegex(OSError, 'pointer lost ack'): f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        self.assertEqual(f.run.inspect().outcome, 'materialization_required')
        materialize = f.store.materialize
        def lose_state(token, path, value, **kwargs):
            result = materialize(token, path, value, **kwargs)
            if path == STATE_PATH: raise OSError('state lost ack')
            return result
        with patch.object(f.store, 'materialize', side_effect=lose_state):
            with self.assertRaisesRegex(OSError, 'state lost ack'): f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'], 1)
        self.assertEqual((reviewer.calls, f.editor.calls, verifier.calls), (1,1,1))

    def test_stale_constraints_evidence_and_unrelated_round_refuse(self):
        from whetstone.vnext_verified_phase2_advice import ADVICE_PATH
        f, reviewer, config, advice = self.reviewed()
        f.run.bind_phase2_advice(advice)
        ref = f.run.admit_phase2_round()
        original = f.store.read(ref['path'])
        record = json.loads(original)
        variants = []
        for key in ('advice', 'feedback', 'base_pointer'):
            bad = deepcopy(record);bad[key]['hash'] = 'f'*64;variants.append(bad)
        bad = deepcopy(record);bad['constraints']['max_operations'] += 1;variants.append(bad)
        bad = deepcopy(record);bad['round_number'] += 1;variants.append(bad)
        for bad in variants:
            (f.root/ref['path']).write_bytes(canonical_json_bytes(bad))
            with self.assertRaises(ValueError): f.run.request(round_number=record['round_number'], client=f.editor)
            self.assertEqual(f.editor.calls, 0)
            (f.root/ref['path']).write_bytes(original)
        # Use a fresh run so its invocation-local selector cache cannot hide substitution.
        self.reopen(f)
        other = 'rounds/round-99/proposal_input.json'
        (f.root/other).parent.mkdir();(f.root/other).write_bytes(original)
        with self.assertRaises(ValueError): f.run.request(round_number=99, client=f.editor)
        (f.root/other).unlink()
        raw = (f.root/ADVICE_PATH).read_bytes();(f.root/ADVICE_PATH).unlink()
        with self.assertRaises(ValueError): f.run.request(round_number=record['round_number'], client=f.editor)
        (f.root/ADVICE_PATH).write_bytes(raw)
        with self.assertRaises(ValueError): f.run.review_next()
        self.assertEqual((reviewer.calls, f.editor.calls), (1,0))

    def test_deterministically_invalid_candidate_never_calls_verifier_or_promotes(self):
        f, reviewer, _, _, _, number = self.admitted()
        before = f.store.read('rounds/current_verified.json')
        def weaken(packet):
            content = 'Queue sometimes waits.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        f.editor.callback = weaken
        self.assertEqual(f.run.request(round_number=number, client=f.editor).value.status, 'complete')
        f.run.register(round_number=number, created_at=STAMP)
        result = f.run.verify(decided_at=STAMP)
        self.assertEqual(result.value.decision['deterministic_result'], 'fail')
        self.assertEqual(result.value.decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        self.reopen(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertEqual(f.store.read('rounds/current_verified.json'), before)
        self.assertEqual((reviewer.calls, f.editor.calls), (1,1))
