"""Dependency replay and isolation for invocation-local historical reuse."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import confined_file
from whetstone.vnext_replay_memo import ReplayMemo, observed_read, _collectors, _contract_roots


class Source:
    def __init__(self):
        self.files = {'input': b'first'}
        self.reads = 0

    @observed_read
    def read(self, path):
        self.reads += 1
        if path not in self.files: raise FileNotFoundError(path)
        return self.files[path]

    @observed_read
    def list_directory(self, path):
        return tuple(sorted(self.files))


class ReplayMemoTests(unittest.TestCase):
    def test_hit_rereads_bytes_runs_guards_and_isolates_returned_data(self):
        source = Source(); memo = ReplayMemo(); calls = []; guards = []
        def build():
            calls.append(1)
            return {'rows': [source.read('input')]}
        first = memo.call('key', build, lambda: guards.append(1))
        first['rows'].clear(); before = source.reads
        self.assertEqual(memo.call('key', build, lambda: guards.append(1)), {'rows': [b'first']})
        self.assertGreater(source.reads, before)
        self.assertEqual((len(calls), len(guards)), (1, 4))
        source.files['input'] = b'second'
        self.assertEqual(memo.call('key', build, lambda: None), {'rows': [b'second']})
        self.assertEqual(len(calls), 2)
        with self.assertRaisesRegex(RuntimeError, 'owner lost'):
            memo.call('key', build, lambda: (_ for _ in ()).throw(RuntimeError('owner lost')))

    def test_nested_hits_propagate_missing_files_and_directory_dependencies(self):
        source = Source(); memo = ReplayMemo(); calls = []
        def child():
            calls.append('child')
            listing = source.list_directory('root')
            try: optional = source.read('optional')
            except FileNotFoundError: optional = None
            return listing, optional
        def parent():
            calls.append('parent')
            return memo.call('child', child, lambda: None)
        memo.call('child', child, lambda: None)
        self.assertEqual(memo.call('parent', parent, lambda: None)[1], None)
        source.files['optional'] = b'new'
        self.assertEqual(memo.call('parent', parent, lambda: None)[1], b'new')
        self.assertEqual(calls.count('parent'), 2)
        self.assertEqual(calls.count('child'), 2)
        del source.files['optional']
        self.assertEqual(memo.call('parent', parent, lambda: None)[1], None)

    def test_failures_and_unstable_reads_are_not_cached_or_leaked(self):
        source = Source(); memo = ReplayMemo()
        def unstable():
            source.read('input'); source.files['input'] = b'changed'; source.read('input')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            memo.call('key', unstable, lambda: None)
        self.assertFalse(memo.entries)
        self.assertEqual(_collectors.get(), ())
        self.assertEqual(_contract_roots.get(), ())
        def failed():
            source.read('input'); raise RuntimeError('build failed')
        with self.assertRaisesRegex(RuntimeError, 'build failed'):
            memo.call('key', failed, lambda: None)
        self.assertFalse(memo.entries)
        self.assertEqual(_collectors.get(), ())
        calls = []
        def changing_at_seal(path):
            calls.append(path)
            if len(calls) == 2: source.files[path] = b'changed again'
            return original(path)
        original = source.read
        with patch.object(source, 'read', side_effect=changing_at_seal):
            with self.assertRaisesRegex(ValueError, 'source changed'):
                memo.call('key', lambda: source.read('input'), lambda: None)
        self.assertFalse(memo.entries)

    def test_confined_contract_bytes_and_symlinks_are_rechecked(self):
        calls = []
        with TemporaryDirectory() as tmp:
            root = Path(tmp); target = root/'contract'; target.write_bytes(b'one')
            memo = ReplayMemo(contract_roots=(root,))
            def build():
                calls.append(1)
                return confined_file(root, 'contract').read_bytes()
            self.assertEqual(memo.call('contract', build, lambda: None), b'one')
            self.assertEqual(memo.call('contract', build, lambda: None), b'one')
            self.assertEqual(len(calls), 1)
            target.write_bytes(b'two')
            self.assertEqual(memo.call('contract', build, lambda: None), b'two')
            target.unlink(); (root/'other').write_bytes(b'two'); target.symlink_to(root/'other')
            with self.assertRaisesRegex(ValueError, 'symlinks'):
                memo.call('contract', build, lambda: None)

    def test_disposable_payload_replay_is_not_a_persistent_source(self):
        source = Source(); calls = []
        with TemporaryDirectory() as contracts:
            memo = ReplayMemo(contract_roots=(contracts,))
            def build():
                calls.append(1)
                raw = source.read('input')
                with TemporaryDirectory() as scratch:
                    root = Path(scratch)
                    (root/'edit.md').write_bytes(raw)
                    return confined_file(root, 'edit.md').read_bytes()
            self.assertEqual(memo.call('payload', build, lambda: None), b'first')
            self.assertEqual(memo.call('payload', build, lambda: None), b'first')
            self.assertEqual(len(calls), 1)
            source.files['input'] = b'second'
            self.assertEqual(memo.call('payload', build, lambda: None), b'second')
            self.assertEqual(len(calls), 2)

    def test_context_eviction_and_process_boundary_do_not_reuse_other_results(self):
        source = Source(); memo = ReplayMemo(limit=1); calls = []
        def build():
            calls.append(1); return source.read('input')
        for key in ('base1', 'base2', 'base1'): memo.call(key, build, lambda: None)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(memo.entries), 1)
        with patch('whetstone.vnext_replay_memo.os.getpid', return_value=memo.pid+1):
            with self.assertRaisesRegex(ValueError, 'another process'):
                memo.call('base1', build, lambda: None)




import sys
import test_vnext_local_storage as storage_tests
from whetstone.vnext_verified_work import _BorrowedFence


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class StorageReplayMemoTests(unittest.TestCase):
    setUp = storage_tests.LocalStorageTests.setUp
    open_store = storage_tests.LocalStorageTests.open_store
    lineage = storage_tests.LocalStorageTests.lineage

    def test_warm_entry_cannot_outlive_borrowed_ownership(self):
        memo = ReplayMemo()
        with self.store.locked(self.lineage) as token:
            fence = _BorrowedFence(self.store, token)
            build = lambda: fence.read('rounds/seed.md')
            guard = lambda: fence.read_descriptor()
            self.assertEqual(memo.call('seed', build, guard), b'# Seed\n')
            self.assertEqual(memo.call('seed', build, guard), b'# Seed\n')
        with self.assertRaises(RuntimeError): memo.call('seed', build, guard)

    def test_warm_entry_rejects_symlink_even_when_target_bytes_match(self):
        memo = ReplayMemo(); path = self.root/'rounds/seed.md'
        build = lambda: self.store.read('rounds/seed.md')
        guard = self.store.read_descriptor
        memo.call('seed', build, guard)
        raw = path.read_bytes(); path.unlink()
        target = self.base/'outside'; target.write_bytes(raw); path.symlink_to(target)
        with self.assertRaises((OSError, ValueError)): memo.call('seed', build, guard)

    def test_warm_entry_cannot_reuse_identical_bytes_from_replaced_root(self):
        import shutil
        memo = ReplayMemo()
        build = lambda: self.store.read('rounds/seed.md')
        memo.call('seed', build, self.store.read_descriptor)
        moved = self.base/'old'; self.root.rename(moved); shutil.copytree(moved, self.root)
        with self.assertRaises(RuntimeError): memo.call('seed', build, self.store.read_descriptor)


if __name__ == '__main__': unittest.main()
