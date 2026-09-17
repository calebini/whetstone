"""Representative runtime publication prefixes above a committed promotion."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone import vnext_local_storage as storage
from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_verified_materialization import STATE_FIELD, STATE_PATH
from vnext_fixtures import STAMP
import test_vnext_verified_runtime_recovery as recovery
import test_vnext_verified_runtime_faults as promotion


POINTER = 'rounds/current_verified.json'
SNAPSHOT = 'rounds/verified_history/current-verified-2.json'


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimePublicationPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): recovery.RuntimeRecoveryTests.setUpClass()
    files = recovery.RuntimeRecoveryTests.files
    fixture = recovery.RuntimeRecoveryTests.fixture
    start = recovery.RuntimeRecoveryTests.start
    review = recovery.RuntimeRecoveryTests.review
    reopen = recovery.RuntimeRecoveryTests.reopen
    candidate = recovery.RuntimeRecoveryTests.candidate
    verify = recovery.RuntimeRecoveryTests.verify
    assert_counts = recovery.RuntimeRecoveryTests.assert_counts
    promoted = recovery.RuntimeRecoveryTests.promoted
    second = promotion.RuntimePromotionFaultTests.second
    eligible_second = promotion.RuntimePromotionFaultTests.eligible_second

    def assert_retained(self, f, before, *, mutable=()):
        for path, raw in before.items():
            if path not in mutable: self.assertEqual((f.root / path).read_bytes(), raw, path)

    def assert_poisoned(self, store, token):
        self.assertIsNone(store._token)
        self.assertIsNone(store._lock_fd)
        with self.assertRaises(storage.OwnershipLost):
            store.publish(token, 'rounds/stale-prefix-owner', b'forbidden')

    def assert_second_promotion(self, f, reviewer, before, *, stamp):
        pointer = json.loads(f.store.read(POINTER))
        self.assertEqual(pointer['promotion_ordinal'], 2)
        self.assertEqual(pointer['promoted_at'], stamp)
        self.assertEqual(pointer['source_candidate_id'], f.identifier)
        self.assertEqual(f.store.read(POINTER), f.store.read(SNAPSHOT))
        draft = f.store.read(pointer['verified_draft_path'])
        self.assertEqual(f.store.read('spec.md'), draft)
        self.assertEqual(f.store.read('rounds/round-2/draft_after.md'), draft)
        self.assertEqual(json.loads(f.store.read(STATE_PATH))[STATE_FIELD], pointer)
        self.assert_retained(f, before, mutable={POINTER, 'spec.md', 'rounds/round-2/draft_after.md', STATE_PATH})
        after = self.files(f)
        self.assertEqual(f.run.promote(prepared_at=recovery.RETRY_STAMP).outcome, 'not_eligible')
        self.reopen(f)
        self.assertEqual(f.run.review_status().round_number, 3)
        self.assertEqual(self.files(f), after)
        for path in ('rounds/verified_history/current-verified-3.json', 'rounds/review_index/request-3.json',
                     'rounds/candidate_index/creation-3.json', 'rounds/stale-prefix-owner'):
            self.assertFalse((f.root / path).exists(), path)
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)

    def test_incomplete_registration_preparation_refuses_without_manufacturing_artifacts(self):
        f, reviewer = self.promoted()
        self.review(f, reviewer)
        editor = recovery.followup.history.verified.fixtures.Client()
        f.editors.append(editor)
        self.assertEqual(f.run.request(round_number=2, client=editor).value.status, 'complete')
        current = f.store.read(POINTER)
        baseline = self.files(f)
        publish = f.store.publish
        prepared = []
        def stop(token, path, value):
            boundary = self.files(f) if path.endswith('/registration_preparation.json') else None
            result = publish(token, path, value)
            if boundary is not None:
                prepared.append((path, deepcopy(value), boundary))
                raise OSError('after early runtime registration preparation')
            return result
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'early runtime registration'):
                f.run.register(round_number=2, created_at=STAMP)
        self.assertEqual(len(prepared), 1)
        path, package, handed_off = prepared[0]
        creation = package['creation_event']
        self.assertEqual(creation['candidate_creation_ordinal'], 2)
        self.assertEqual(creation['created_at'], STAMP)
        handoff = json.loads(handed_off['rounds/round-2/proposal_handoff.json'])
        self.assertEqual(handoff['base_pointer']['path'], 'rounds/verified_history/current-verified-1.json')
        self.assertEqual(set(self.files(f)) - set(handed_off), {path})
        self.assert_retained(f, handed_off)
        self.assert_retained(f, baseline)
        before = self.files(f)
        self.reopen(f)
        self.assertEqual(f.run.inspect().outcome, 'registration_recovery_required')
        self.assertEqual(f.run.inspect().latest_candidate['candidate_creation_ordinal'], 1)
        self.assertEqual(f.run.review_status().outcome, 'registration_recovery_required')
        for action in (lambda: f.run.request(round_number=2, client=editor),
                       lambda: f.run.register(round_number=2, created_at=recovery.RETRY_STAMP),
                       lambda: f.run.verify(decided_at=STAMP), lambda: f.run.review_next(client=reviewer)):
            self.assertEqual(action().outcome, 'registration_recovery_required')
            self.assertEqual(self.files(f), before)
        with self.assertRaises(FileNotFoundError): f.run.recover_registration()
        with self.assertRaisesRegex(ValueError, 'registration recovery'): f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        self.assertEqual(f.run.inspect().outcome, 'registration_recovery_required')
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.store.read(POINTER), current)
        self.assertFalse((f.root / creation['candidate_path']).exists())
        self.assertFalse((f.root / creation['initial_disposition_event_path']).exists())
        self.assertFalse((f.root / 'rounds/candidate_index/creation-2.json').exists())
        self.assertFalse((f.root / SNAPSHOT).exists())
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=1)

    def test_candidate_pointer_ack_loss_repeats_barrier_before_global_promotion(self):
        f, reviewer = self.promoted()
        self.review(f, reviewer)
        creation = self.candidate(f, number=2)
        directory = creation['candidate_path'].rsplit('/', 1)[0]
        target = directory + '/candidate_verification_current.json'
        candidate_snapshot = directory + '/candidate_verification_pointer-attempt-2.json'
        current = f.store.read(POINTER)
        replace, syscall = f.store.replace_pointer, storage.os.replace
        poisoned = []
        def lose_ack(source, destination, **options):
            result = syscall(source, destination, **options)
            if destination == 'candidate_verification_current.json':
                raise OSError('lost final candidate pointer acknowledgement')
            return result
        def observe(token, path, **options):
            if path != target or options['snapshot']['path'] != candidate_snapshot:
                return replace(token, path, **options)
            try:
                with patch.object(storage.os, 'replace', side_effect=lose_ack):
                    return replace(token, path, **options)
            except storage.StorageWriteError:
                self.assert_poisoned(f.store, token)
                poisoned.append(token)
                raise
        with patch.object(f.store, 'replace_pointer', side_effect=observe):
            with self.assertRaises(storage.StorageWriteError) as error: self.verify(f)
        self.assertEqual(error.exception.result.outcome, 'outcome_requires_reconciliation')
        self.assertEqual(error.exception.result.path, target)
        self.assertEqual(error.exception.result.hash, sha256_bytes(f.store.read(target)))
        self.assertEqual(len(poisoned), 1)
        self.assertEqual(f.store.read(target), f.store.read(candidate_snapshot))
        decision = json.loads(f.store.read(directory + '/candidate_verification-attempt-2.json'))
        self.assertEqual(decision['candidate_disposition'], 'CANDIDATE_VERIFIED')
        self.assertEqual(decision['decided_at'], STAMP)
        before = self.files(f)
        self.reopen(f)
        self.assertEqual(f.run.inspect().outcome, 'promotion_required')
        self.assertEqual(f.run.verify(client=f.verifiers[-1], decided_at=recovery.RETRY_STAMP).outcome, 'promotion_required')
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.store.read(POINTER), current)
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)

        synchronize, flush = f.store.synchronize_existing, storage._full_flush
        active, checked = [], []
        def fail_flush(fd):
            if active == [target]: raise OSError('candidate pointer synchronization failed')
            return flush(fd)
        def check(token, path, **options):
            active[:] = [path]
            try: return synchronize(token, path, **options)
            except storage.StorageWriteError:
                checked.append(path)
                self.assert_poisoned(f.store, token)
                raise
            finally: active.clear()
        with patch.object(f.store, 'synchronize_existing', side_effect=check), \
                patch.object(storage, '_full_flush', side_effect=fail_flush):
            with self.assertRaises(storage.StorageWriteError): f.run.promote(prepared_at=recovery.RETRY_STAMP)
        self.assertEqual(checked, [target])
        self.assertEqual(self.files(f), before)
        self.assertFalse((f.root / SNAPSHOT).exists())
        self.assertFalse((f.root / directory / 'promotion_intents/promotion-intent-2.json').exists())
        self.reopen(f)
        order = []
        synchronize, publish = f.store.synchronize_existing, f.store.publish
        def trace_sync(token, path, **options):
            result = synchronize(token, path, **options)
            order.append(('sync', path))
            return result
        def trace_publish(token, path, value):
            order.append(('publish', path))
            return publish(token, path, value)
        with patch.object(f.store, 'synchronize_existing', side_effect=trace_sync), \
                patch.object(f.store, 'publish', side_effect=trace_publish):
            self.assertEqual(f.run.promote(prepared_at=recovery.RETRY_STAMP).outcome, 'promoted')
        intent = directory + '/promotion_intents/promotion-intent-2.json'
        self.assertLess(order.index(('sync', target)), order.index(('publish', intent)))
        self.assert_second_promotion(f, reviewer, before, stamp=recovery.RETRY_STAMP)

    def test_intent_only_preparation_recovers_original_claimant_and_timestamp(self):
        f, reviewer = self.eligible_second()
        directory = f.creation['candidate_path'].rsplit('/', 1)[0]
        intent = directory + '/promotion_intents/promotion-intent-2.json'
        event = directory + '/disposition_events/event-4.json'
        current = f.store.read(POINTER)
        baseline = self.files(f)
        publish = f.store.publish
        def stop(token, path, value):
            result = publish(token, path, value)
            if path == intent: raise OSError('after runtime intent-only preparation')
            return result
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'intent-only preparation'): f.run.promote(prepared_at=STAMP)
        prepared = f.store.read(intent)
        self.assertEqual(json.loads(prepared)['candidate_id'], f.identifier)
        self.assertEqual(json.loads(prepared)['prepared_at'], STAMP)
        self.assertEqual(set(self.files(f)) - set(baseline), {intent})
        self.assert_retained(f, baseline)
        self.assertFalse((f.root / event).exists())
        self.assertFalse((f.root / SNAPSHOT).exists())
        before = self.files(f)
        self.reopen(f)
        self.assertEqual(f.run.inspect().outcome, 'promotion_required')
        self.assertEqual(f.run.inspect().promotion_candidate['candidate_id'], f.identifier)
        for action in (lambda: f.run.review_next(client=reviewer),
                       lambda: f.run.request(round_number=2, client=f.editors[-1]),
                       lambda: f.run.verify(client=f.verifiers[-1], decided_at=recovery.RETRY_STAMP)):
            self.assertEqual(action().outcome, 'promotion_required')
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.store.read(POINTER), current)
        seen = []
        publish = f.store.publish
        def trace(token, path, value):
            seen.append(path)
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=trace):
            self.assertEqual(f.run.promote(prepared_at=recovery.RETRY_STAMP).outcome, 'promoted')
        self.assertEqual([path for path in seen if path in {intent, event, SNAPSHOT}], [intent, event, SNAPSHOT])
        self.assertEqual(f.store.read(intent), prepared)
        self.assertEqual(json.loads(f.store.read(event))['recorded_at'], STAMP)
        self.assert_second_promotion(f, reviewer, before, stamp=STAMP)


if __name__ == '__main__': unittest.main()
