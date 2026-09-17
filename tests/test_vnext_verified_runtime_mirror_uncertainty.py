"""Batch C: real adapter barrier failures during canonical-runtime repair."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone import vnext_local_storage as storage
from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_verified_materialization import STATE_FIELD, STATE_PATH
from vnext_fixtures import STAMP
import test_vnext_verified_runtime_materialization as mirrors


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimeMirrorUncertaintyTests(unittest.TestCase):
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

    def assert_uncertain(self, error, draft):
        self.assertEqual(error.result.outcome, 'outcome_requires_reconciliation')
        self.assertEqual(error.result.path, 'spec.md')
        self.assertEqual(error.result.hash, sha256_bytes(draft))

    def test_post_rename_flush_and_replay_barrier_failures_require_fresh_repair(self):
        f, reviewer, unrelated = self.prepared()
        baseline = self.files(f)
        old_spec = f.store.read('spec.md')
        draft = f.store.read(f.creation['candidate_path'])
        self.assertNotEqual(old_spec, draft)
        replace, flush = storage.os.replace, storage._full_flush
        materialize = f.store.materialize
        renamed, failed_tokens, writes = [], [], []

        def observe_replace(source, destination, **options):
            result = replace(source, destination, **options)
            if destination == 'spec.md': renamed.append(destination)
            return result

        def fail_after_rename(fd):
            if renamed:
                self.assertEqual(f.store.read('spec.md'), draft)
                raise OSError('post-rename mirror full flush failed')
            return flush(fd)

        def observe_write(token, path, raw, **options):
            writes.append(path)
            try: return materialize(token, path, raw, **options)
            except storage.StorageWriteError:
                failed_tokens.append(token)
                self.assert_poisoned(f.store, token)
                raise

        with patch.object(storage.os, 'replace', side_effect=observe_replace), \
                patch.object(storage, '_full_flush', side_effect=fail_after_rename), \
                patch.object(f.store, 'materialize', side_effect=observe_write):
            with self.assertRaises(storage.StorageWriteError) as first:
                f.run.promote(prepared_at=STAMP)
        self.assert_uncertain(first.exception, draft)
        self.assertEqual(renamed, ['spec.md'])
        self.assertEqual(writes, ['spec.md'])
        self.assertEqual(len(failed_tokens), 1)
        committed = f.store.read(mirrors.POINTER)
        self.assertEqual(committed, f.store.read(mirrors.SNAPSHOT))
        pointer = json.loads(committed)
        self.assertEqual(pointer['promotion_ordinal'], 2)
        self.assertEqual(pointer['promoted_at'], STAMP)
        self.assertEqual(f.store.read(pointer['verified_draft_path']), draft)
        self.assertEqual(json.loads(f.store.read(STATE_PATH))[STATE_FIELD]['promotion_ordinal'], 1)
        for path, raw in baseline.items():
            if path not in {mirrors.POINTER, 'spec.md'}: self.assertEqual(f.store.read(path), raw, path)
        failed_store = f.store
        before = self.readonly(f, mirrors.MIRRORS[1:])
        self.assert_poisoned(failed_store, failed_tokens[0])
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)

        # A visible matching mirror still needs its barriers repeated. Fail the
        # second full flush of synchronization, before either pending write.
        synchronize = f.store.synchronize_existing
        synchronized, active, mirror_flushes = [], [], []

        def fail_replay_flush(fd):
            if active == ['spec.md']:
                mirror_flushes.append(fd)
                if len(mirror_flushes) == 2: raise OSError('mirror replay final full flush failed')
            return flush(fd)

        def observe_sync(token, path, **options):
            synchronized.append(path)
            active[:] = [path]
            try: return synchronize(token, path, **options)
            except storage.StorageWriteError:
                failed_tokens.append(token)
                self.assert_poisoned(f.store, token)
                raise
            finally: active.clear()

        with patch.object(storage, '_full_flush', side_effect=fail_replay_flush), \
                patch.object(f.store, 'synchronize_existing', side_effect=observe_sync), \
                patch.object(f.store, 'materialize', side_effect=AssertionError('write after failed replay barrier')), \
                patch.object(f.store, 'replace_pointer', side_effect=AssertionError('recommit during repair')):
            with self.assertRaises(storage.StorageWriteError) as second:
                f.run.review_next(client=reviewer)
        self.assert_uncertain(second.exception, draft)
        self.assertEqual(synchronized, [mirrors.SNAPSHOT, mirrors.POINTER, 'spec.md'])
        self.assertEqual(len(mirror_flushes), 2)
        self.assertEqual(len(failed_tokens), 2)
        self.assertEqual(self.files(f), before)
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)
        second_store = f.store
        self.readonly(f, mirrors.MIRRORS[1:])
        self.assert_poisoned(second_store, failed_tokens[1])

        synchronized, writes = [], []
        synchronize, materialize = f.store.synchronize_existing, f.store.materialize

        def trace_sync(token, path, **options):
            synchronized.append(path)
            return synchronize(token, path, **options)

        def trace_write(token, path, raw, **options):
            writes.append(path)
            return materialize(token, path, raw, **options)

        with patch.object(f.store, 'synchronize_existing', side_effect=trace_sync), \
                patch.object(f.store, 'materialize', side_effect=trace_write), \
                patch.object(f.store, 'publish', side_effect=AssertionError('new authority during repair')), \
                patch.object(f.store, 'replace_pointer', side_effect=AssertionError('recommit during repair')):
            self.assertEqual(f.run.review_next(client=reviewer).outcome, 'materialization_recovered')
        self.assertEqual(synchronized, [mirrors.SNAPSHOT, mirrors.POINTER, 'spec.md'])
        self.assertEqual(tuple(writes), mirrors.MIRRORS[1:])
        self.mirrors_match(f, 2, unrelated)
        self.assertEqual(f.store.read(mirrors.POINTER), committed)
        for path, raw in before.items():
            if path not in mirrors.MIRRORS[1:]: self.assertEqual(f.store.read(path), raw, path)
        after = self.files(f)
        self.assertLessEqual(set(after) - set(before), set(mirrors.MIRRORS[1:]))
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.reopen(f)
        self.assertEqual(f.run.review_status().round_number, 3)
        self.assertEqual(self.files(f), after)
        self.assertFalse((f.root / 'rounds/verified_history/current-verified-3.json').exists())
        self.assertFalse((f.root / 'rounds/review_index/request-3.json').exists())
        self.assertFalse((f.root / 'rounds/stale-mirror-owner').exists())
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)


if __name__ == '__main__': unittest.main()
