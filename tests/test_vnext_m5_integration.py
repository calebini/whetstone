"""M5 scripted operator campaigns; no public dispatch or live source writes.

WHETSTONE_M5_EVIDENCE optionally records per-stage measurements and cProfile
samples. Set WHETSTONE_M5_PROFILE=0 to retain stage timings without profiling
extra replay calls. The same assertions run without instrumentation in unittest.
"""
from contextlib import contextmanager
import cProfile
import json
import os
from pathlib import Path
import pstats
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_vnext_apply_back as apply_tests
import test_vnext_verified_versions as versions
import test_vnext_verified_m2_routes as routes
from test_vnext_verified_phase1_status import clean_response
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import StorageWriteError
from whetstone.vnext_verified_phase2_review import INPUT_PATH
from vnext_fixtures import STAMP


class Measurements:
    @contextmanager
    def stage(self, name):
        directory = os.environ.get('WHETSTONE_M5_EVIDENCE')
        started = time.perf_counter()
        def record(event, **values):
            if directory:
                root = Path(directory); root.mkdir(parents=True, exist_ok=True)
                with (root / 'stages.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(test=self.id(), stage=name, event=event, **values)) + '\n')
        record('started')
        try:
            yield
        except BaseException:
            record('failed', seconds=time.perf_counter()-started)
            raise
        else:
            record('passed', seconds=time.perf_counter()-started)

    def sample(self, f, name):
        directory = os.environ.get('WHETSTONE_M5_EVIDENCE')
        if not directory or os.environ.get('WHETSTONE_M5_PROFILE') == '0':
            return
        root = Path(directory)
        for operation, call in [('history', lambda: f.run._history().inspect()),
                                ('phase_state', f.run.phase2_state if getattr(self, 'phase2_samples', True) else f.run.phase1_status)]:
            with self.stage(name + '-' + operation):
                profile = cProfile.Profile()
                profile.runcall(call)
                profile.dump_stats(str(root / (name + '-' + operation + '.prof')))
                with (root / (name + '-' + operation + '.txt')).open('w') as stream:
                    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(40)


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class JoinedVersionTests(Measurements, apply_tests.Fixture, unittest.TestCase):
    ready = versions.VersionPhase2Tests.ready
    config = versions.VersionPhase2Tests.config
    advice = versions.VersionPhase2Tests.advice
    candidate = versions.VersionPhase2Tests.candidate
    advance = versions.VersionPhase2Tests.advance
    response = versions.VersionPhase2Tests.response

    def test_two_promotions_timeout_reopen_convergence_and_uncertain_apply(self):
        self.versioned = True
        with patch('whetstone.live_phase2.LivePhase2Runner', side_effect=AssertionError('legacy Phase 2')),\
             patch('whetstone.apply_back.apply_back', side_effect=AssertionError('legacy apply-back')):
            with self.stage('system-entry'):
                f, client, _ = self.ready()
                self.assertIn(b'# Queue 1.0', f.store.read('spec.md'))
            self.sample(f, 'one-promotion')
            with self.stage('correction-review-and-registration'):
                client.callback = self.response()
                result = f.run.run_phase2_review(client=client)
                self.assertEqual(result.status, 'complete')
                f.run.consume_phase2_result()
                bound = SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
                f.run.bind_phase2_advice(self.advice(bound, result))
                ref = f.run.admit_phase2_round()
                number = json.loads(f.store.read(ref['path']))['round_number']
                creation, verifier = self.candidate(f, number)
                head_before = f.store.read('rounds/current_verified.json')
            with self.stage('verification-and-second-promotion'):
                self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
                self.assertEqual(f.store.read('rounds/current_verified.json'), head_before)
                self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 2)
                self.assertEqual(f.run.phase2_sequence_status()['gate'], 'resolution_publication_required')
                f.run.publish_phase2_resolutions()
                self.reopen(f)
                head = f.store.read('rounds/current_verified.json')
                history = f.store.read('spec.history.md')
                self.assertEqual(history.count(b'`0.17` -> `1.0`'), 1)
                self.assertEqual(history.count(b'`1.0` -> `1.1`'), 1)
            self.sample(f, 'two-promotions')
            with self.stage('timeout-and-uncertain-failure-state'):
                f.run.bind_phase2_next_review(client.transport_binding)
                def timeout(owner, packet):
                    raise TimeoutError('M5 joined interruption')
                client.callback = timeout
                self.assertEqual(f.run.continue_phase2_pass(2, action='execute', client=client).status, 'timeout')
                failure = f.run.phase2_failure_status()
                self.assertEqual(failure['terminal_state'], 'HALTED_CLIENT_TIMEOUT')
                self.assertTrue(failure['resume_permitted'])
                failure_bytes = f.store.read(failure['active']['path'])
                materialize = f.store.materialize
                def lose_state(token, path, raw, **options):
                    result = materialize(token, path, raw, **options)
                    if path == 'rounds/run_state.json':
                        raise OSError('M5 failure state acknowledgement lost')
                    return result
                with patch.object(f.store, 'materialize', side_effect=lose_state):
                    with self.assertRaisesRegex(OSError, 'acknowledgement lost'):
                        f.run.reconcile_phase2_failure_state()
            with self.stage('reopen-recovery-and-explicit-continuation'):
                calls = client.calls
                self.reopen(f)
                f.run.reconcile_phase2_failure_state()
                self.assertEqual(client.calls, calls)
                report = json.loads(f.store.read('rounds/convergence_failure_report.json'))
                self.assertEqual(report['unresolved_rubric_gaps'], [])
                client.callback = self.response(gaps=False)
                self.assertEqual(f.run.continue_phase2_pass(2, action='execute', client=client, continuation=True).status, 'complete')
                f.run.continue_phase2_pass(2, action='consume')
                f.run.reconcile_phase2_failure_state()
                self.assertEqual(f.store.read(failure['active']['path']), failure_bytes)
            with self.stage('declaration-and-convergence'):
                self.advance(f, client)
                package = f.run.prepare_phase2_declaration()
                gaps = json.loads(f.store.read(package['declaration']['rubric_gaps']['path']))['rubric_gaps']
                self.assertEqual(len(gaps), 1)
                self.assertEqual(gaps[0]['status'], 'resolved')
                self.assertFalse(gaps[0]['blocking_convergence'])
                self.advance(f, client)
                f.run.reconcile_phase2_findings()
                self.assertEqual(f.run.finish_phase2()['packet']['terminal_state'], 'CONVERGED')
                self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
                self.assertEqual(f.store.read('rounds/current_verified.json'), head)
                self.assertEqual(f.store.read('spec.history.md'), history)
                self.assertEqual(f.store.read('spec.md'), f.store.read(creation['candidate_path']))
                self.assertEqual((client.calls, f.editor.calls, verifier.calls), (5, 1, 1))
            with self.stage('apply-receipt-loss-and-recovery'):
                packet = self.approval(f)
                publish = f.store.publish
                def lose_receipt(token, path, value):
                    if path == apply_tests.module.RECEIPT:
                        raise OSError('M5 receipt not committed')
                    return publish(token, path, value)
                with patch.object(f.store, 'publish', side_effect=lose_receipt):
                    with self.assertRaises(StorageWriteError):
                        self.apply(f, packet)
                inode = self.source.stat().st_ino
                self.reopen(f)
                with patch.object(apply_tests.module.SourceFile, 'replace', side_effect=AssertionError('recovery rewrite')):
                    self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'], 'completed')
                    self.assertEqual(self.apply(f, packet)['outcome'], 'completed')
                self.assertEqual(self.source.stat().st_ino, inode)
                self.assertEqual(self.source.read_bytes(), f.store.read('spec.md'))
                self.assertEqual(sha256_bytes(self.source.read_bytes()), packet['verified_draft']['hash'])
                self.assertEqual(f.store.read('rounds/current_verified.json'), head)
                self.assertEqual(f.store.read('spec.history.md'), history)
                self.assertEqual(f.store.read(failure['active']['path']), failure_bytes)
                self.assertEqual((client.calls, f.editor.calls, verifier.calls), (5, 1, 1))


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class JoinedRouteTests(Measurements, apply_tests.Fixture, unittest.TestCase):
    exhausted = routes.M2RoutesTests.exhausted
    response = routes.M2RoutesTests.response
    advance = routes.M2RoutesTests.advance
    phase2 = routes.M2RoutesTests.phase2
    complete = routes.M2RoutesTests.complete
    target = ('final', 'strict')

    def test_extended_horizontal_and_vertical_promotions_converge_and_apply(self):
        for vertical in (False, True):
            with self.subTest(vertical=vertical), self.stage('vertical' if vertical else 'horizontal'):
                f, prior, old = self.exhausted(vertical=vertical, routes_contract=True)
                baseline = f.store.read(f.run._record['review_configuration']['path'])
                f.run.extend_phase1_budget(added_rounds_per_profile=1)
                prior.callback = clean_response
                for _ in range(2 if vertical else 1):
                    self.assertEqual(f.run.review_next(client=prior).status, 'complete')
                f.run.finish_phase1(); f.run.reconcile_phase1_state(); self.reopen(f)
                with patch('whetstone.live_phase2.LivePhase2Runner', side_effect=AssertionError('legacy Phase 2')):
                    client, bound = self.phase2(f, prior)
                    self.assertEqual(bound.request['round_number'], 6 if vertical else 3)
                    self.complete(f, client)
                head = f.store.read('rounds/current_verified.json')
                packet = self.approval(f)
                self.assertEqual(self.apply(f, packet)['outcome'], 'completed')
                self.reopen(f)
                self.assertEqual(f.run.apply_back_status()['outcome'], 'completed')
                self.assertEqual(self.source.read_bytes(), f.store.read('spec.md'))
                self.assertEqual(f.store.read('rounds/current_verified.json'), head)
                self.assertEqual(f.store.read(old.evidence_ref['path']), canonical_json_bytes(old.evidence))
                self.assertEqual(f.store.read(f.run._record['review_configuration']['path']), baseline)
                self.assertEqual(len(json.loads(f.store.read('rounds/run_state.json'))['budget_extensions']), 1)
                self.assertEqual((prior.calls, client.calls, f.editor.calls), (4 if vertical else 2, 2, 1))


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class LongerHistoryTests(Measurements, apply_tests.Fixture, unittest.TestCase):
    phase2_samples = False

    def test_four_versioned_promotions_replay_exact_history(self):
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        import test_vnext_verified_review as runtime
        self.versioned = True
        with self.stage('longer-history-initialization'):
            f, client = self.start(status_contract=True, budget=5)
        for number in range(1, 5):
            with self.stage('phase1-promotion-' + str(number)):
                self.review(f, client)
                content = 'Queue always waits before stage ' + str(number) + '.\n'
                def change(packet):
                    packet['payloads'][0]['content'] = content
                    packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
                    return canonical_json_bytes(packet)
                f.editor.callback = change
                self.assertEqual(f.run.request(round_number=number, client=f.editor).value.status, 'complete')
                creation = f.run.register(round_number=number, created_at=STAMP).value
                context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=creation['candidate_id'])
                verifier = runtime.history.verified.semantic.Client(context)
                self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
                self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], number)
                self.assertIn(('# Queue 0.' + str(17 + number)).encode(), f.store.read('spec.md'))
            if number in (1, 4):
                self.sample(f, 'phase1-' + str(number) + '-promotions')
        with self.stage('longer-history-reopen-and-clean-review'):
            before = f.store.read('spec.history.md')
            head = f.store.read('rounds/current_verified.json')
            self.reopen(f)
            client.callback = clean_response
            self.assertEqual(f.run.review_next(client=client).status, 'complete')
            f.run.finish_phase1(); f.run.reconcile_phase1_state()
            self.assertEqual(f.store.read('rounds/current_verified.json'), head)
            self.assertEqual(f.store.read('spec.history.md'), before)
            for minor in range(17, 21):
                self.assertEqual(before.count(('`0.' + str(minor) + '` -> `0.' + str(minor + 1) + '`').encode()), 1)
            self.assertEqual((client.calls, f.editor.calls), (5, 4))


if __name__ == '__main__':
    unittest.main()
