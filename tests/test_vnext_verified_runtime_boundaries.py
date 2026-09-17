"""Remaining canonical-runtime publication and operator boundary proofs."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone import vnext_local_storage as storage
from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_verified_materialization import STATE_FIELD, STATE_PATH
from vnext_fixtures import STAMP
import test_vnext_verified_runtime_materialization as mirrors
import test_vnext_verified_runtime_followup as followup


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): mirrors.RuntimeMaterializationTests.setUpClass()
    files = mirrors.RuntimeMaterializationTests.files
    fixture = mirrors.RuntimeMaterializationTests.fixture
    start = mirrors.RuntimeMaterializationTests.start
    review = mirrors.RuntimeMaterializationTests.review
    reopen = mirrors.RuntimeMaterializationTests.reopen
    candidate = mirrors.RuntimeMaterializationTests.candidate
    verify = mirrors.RuntimeMaterializationTests.verify
    second = mirrors.RuntimeMaterializationTests.second
    assert_counts = mirrors.RuntimeMaterializationTests.assert_counts
    eligible_second = mirrors.RuntimeMaterializationTests.eligible_second
    prepared = mirrors.RuntimeMaterializationTests.prepared
    readonly = mirrors.RuntimeMaterializationTests.readonly
    mirrors_match = mirrors.RuntimeMaterializationTests.mirrors_match

    def assert_poisoned(self, store, token):
        # Called inside the failing primitive's caller, before locked() unwinds.
        self.assertIsNone(store._token)
        self.assertIsNone(store._lock_fd)
        with self.assertRaises(storage.OwnershipLost):
            store.publish(token, 'rounds/stale-mirror-owner', b'forbidden')

    def test_uncertain_final_state_requires_barriers_even_when_all_mirrors_match(self):
        f, reviewer, unrelated = self.prepared()
        replace, flush = storage.os.replace, storage._full_flush
        materialize = f.store.materialize
        renamed, poisoned = [], []

        def observe_replace(source, destination, **options):
            result = replace(source, destination, **options)
            if destination == 'run_state.json': renamed.append(destination)
            return result

        def fail_final_flush(fd):
            if renamed: raise OSError('uncertain final runtime state flush')
            return flush(fd)

        def observe_write(token, path, raw, **options):
            try: return materialize(token, path, raw, **options)
            except storage.StorageWriteError:
                self.assert_poisoned(f.store, token)
                poisoned.append(token)
                raise

        with patch.object(storage.os, 'replace', side_effect=observe_replace), \
                patch.object(storage, '_full_flush', side_effect=fail_final_flush), \
                patch.object(f.store, 'materialize', side_effect=observe_write):
            with self.assertRaises(storage.StorageWriteError) as error:
                f.run.promote(prepared_at=STAMP)
        self.assertEqual(error.exception.result.path, STATE_PATH)
        self.assertEqual(error.exception.result.outcome, 'outcome_requires_reconciliation')
        self.assertEqual(error.exception.result.hash, sha256_bytes(f.store.read(STATE_PATH)))
        self.assertEqual(len(poisoned), 1)
        self.mirrors_match(f, 2, unrelated)
        before = self.files(f)
        self.reopen(f)
        self.assertEqual(f.run.inspect().pending_paths, ())
        self.assertEqual(f.run.review_status().round_number, 3)
        self.assertEqual(self.files(f), before)

        # Both promotion and the shared work/operator owner must repeat the
        # barriers even though readonly classification finds no pending bytes.
        for route in ('promote', 'review'):
            with self.subTest(route=route):
                synchronize = f.store.synchronize_existing
                active, seen = [], []

                def fail_replay(fd):
                    if active == [STATE_PATH]: raise OSError('final state replay flush failed')
                    return flush(fd)

                def observe_sync(token, path, **options):
                    seen.append(path)
                    active[:] = [path]
                    try: return synchronize(token, path, **options)
                    except storage.StorageWriteError:
                        self.assert_poisoned(f.store, token)
                        raise
                    finally: active.clear()

                with patch.object(storage, '_full_flush', side_effect=fail_replay), \
                        patch.object(f.store, 'synchronize_existing', side_effect=observe_sync):
                    with patch.object(reviewer, 'review', side_effect=AssertionError('client before mirror barriers')):
                        with self.assertRaises(storage.StorageWriteError):
                            if route == 'promote': f.run.promote(prepared_at=STAMP)
                            else: f.run.review_next(client=reviewer)
                self.assertEqual(seen, [mirrors.SNAPSHOT, mirrors.POINTER, *mirrors.MIRRORS])
                self.assertEqual(self.files(f), before)
                self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)
                self.reopen(f)

        seen = []
        synchronize = f.store.synchronize_existing
        def trace(token, path, **options):
            seen.append(path)
            return synchronize(token, path, **options)
        with patch.object(f.store, 'synchronize_existing', side_effect=trace), \
                patch.object(f.store, 'materialize', side_effect=AssertionError('matching mirror rewrite')), \
                patch.object(f.store, 'publish', side_effect=AssertionError('unexpected authority publication')):
            self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertEqual(seen, [mirrors.SNAPSHOT, mirrors.POINTER, *mirrors.MIRRORS])
        self.assertEqual(self.files(f), before)
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)

    question = followup.RuntimeFollowupTests.question

    def test_uncertain_operator_receipt_and_selection_replay_exactly_without_clients(self):
        for boundary in ('/receipts/', '/followup_transaction.json'):
            with self.subTest(boundary=boundary):
                f, reviewer, parent, answer = self.question()
                reference = None
                if boundary == '/followup_transaction.json':
                    reference = f.run.submit_answer(packet=answer).value['reference']
                current = f.store.read(mirrors.POINTER)
                baseline = self.files(f)
                publish, link = f.store.publish, storage.os.link
                active, failed_paths = [], []
                def fail_link(source, destination, **options):
                    result = link(source, destination, **options)
                    if active and boundary in active[0]:
                        raise OSError('lost operator publication acknowledgement')
                    return result
                def observe(token, path, value):
                    active[:] = [path]
                    try: return publish(token, path, value)
                    except storage.StorageWriteError:
                        failed_paths.append(path)
                        self.assertIsNone(f.store._token)
                        self.assertIsNone(f.store._lock_fd)
                        with self.assertRaises(storage.OwnershipLost):
                            publish(token, 'rounds/stale-operator-owner', b'forbidden')
                        raise
                    finally: active.clear()
                def act():
                    if reference is None: return f.run.submit_answer(packet=answer)
                    return f.run.select_followup(candidate_id=parent['candidate_id'], answer_reference=reference)
                with patch.object(storage.os, 'link', side_effect=fail_link), \
                        patch.object(f.store, 'publish', side_effect=observe):
                    with self.assertRaises(storage.StorageWriteError) as error: act()
                self.assertEqual(error.exception.result.outcome, 'outcome_requires_reconciliation')
                self.assertEqual(failed_paths, [error.exception.result.path])
                retained = f.store.read(failed_paths[0])
                self.assertEqual(sha256_bytes(retained), error.exception.result.hash)
                visible = self.files(f)
                self.reopen(f)
                f.run.answers(candidate_id=parent['candidate_id'])
                f.run.submit_answer(packet=answer, dry_run=True)
                self.assertEqual(self.files(f), visible)

                # Replaying the visible artifact must retry its actual barrier;
                # failure must not report the receipt/selection as acknowledged.
                publish, flush = f.store.publish, storage._full_flush
                active, seen = [], []
                def trace(token, path, value):
                    seen.append(path)
                    active[:] = [path]
                    try: return publish(token, path, value)
                    finally: active.clear()
                def fail_replay(fd):
                    if active == failed_paths: raise OSError('operator replay barrier failed')
                    return flush(fd)
                with patch.object(f.store, 'publish', side_effect=trace), \
                        patch.object(storage, '_full_flush', side_effect=fail_replay):
                    with self.assertRaises(storage.StorageWriteError): act()
                self.assertIn(failed_paths[0], seen)
                # A pre-publication temporary may remain, but retained evidence
                # and authority cannot change, and no client is invoked.
                for path, raw in visible.items(): self.assertEqual((f.root / path).read_bytes(), raw, path)
                self.assert_counts(f, reviewer, reviews=1, editors=1, verifiers=1)
                self.reopen(f)
                completed = act()
                self.assertEqual(completed.outcome, 'answer_recorded' if reference is None else 'followup_selected')
                self.assertEqual(f.store.read(failed_paths[0]), retained)
                after = self.files(f)
                self.assertEqual(act().value, completed.value)
                self.assertEqual(self.files(f), after)
                for path, raw in baseline.items(): self.assertEqual(f.store.read(path), raw, path)
                self.assertEqual(f.store.read(mirrors.POINTER), current)
                self.assertFalse((f.root / 'rounds/candidate_index/creation-2.json').exists())
                self.assertFalse((f.root / 'rounds/stale-operator-owner').exists())
                self.assert_counts(f, reviewer, reviews=1, editors=1, verifiers=1)
