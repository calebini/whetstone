"""Selection is rechecked under every D8 fence, before any authority mutation."""
import sys
import unittest

from test_vnext_local_storage import LocalStorageTests


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class InvocationGuardTests(unittest.TestCase):
    setUp = LocalStorageTests.setUp
    open_store = LocalStorageTests.open_store

    def test_guard_runs_inside_each_fence_and_before_owner_validation(self):
        events = []
        def guard(read):
            self.assertIsNotNone(self.store._lock_fd)
            self.assertIsNone(self.store._token)
            events.append('guard')
        with self.store.guard_invocation(guard):
            for _ in range(2):
                with self.store.locked(lambda read: events.append('owner')):
                    events.append('body')
        self.assertEqual(events, ['guard','owner','body'] * 2)
        with self.store.locked(lambda read: events.append('unguarded')): pass
        self.assertEqual(events[-1], 'unguarded')

    def test_changed_selection_refuses_before_owner_and_releases_fence(self):
        def changed(read): raise ValueError('selection changed')
        def forbidden(read): self.fail('owner entered after stale selection')
        with self.assertRaisesRegex(ValueError, 'selection changed'):
            with self.store.guard_invocation(changed):
                with self.store.locked(forbidden): self.fail('writer entered')
        self.assertIsNone(self.store._token)
        self.assertIsNone(self.store._lock_fd)
        with self.store.locked(lambda read: None): pass

    def test_nested_selection_cannot_replace_outer_guard(self):
        with self.store.guard_invocation(lambda read: None):
            with self.assertRaisesRegex(ValueError, 'cannot nest'):
                with self.store.guard_invocation(lambda read: self.fail('replacement')): pass
