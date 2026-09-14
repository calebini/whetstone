import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore, OwnershipLost, Publication, StorageBusy, StorageWriteError
from whetstone.vnext_verified_materialization import VerifiedMaterialization, STATE_FIELD, STATE_PATH
import test_vnext_verified_history as history


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): history.VerifiedHistoryTests.setUpClass()

    files = history.VerifiedHistoryTests.files
    owner = history.VerifiedHistoryTests.owner
    ready = history.VerifiedHistoryTests.ready
    run_request = history.VerifiedHistoryTests.run_request
    prepared_tail = history.VerifiedHistoryTests.prepared_tail
    promote_fixture = history.VerifiedHistoryTests.promote_fixture
    promoted = history.VerifiedHistoryTests.promoted

    def fixture(self, *, contract=True):
        return history.VerifiedHistoryTests.fixture(self,
            extra_algorithms=('vnext_verified_materialization_v1',) if contract else ())

    def service(self, f): return VerifiedMaterialization(f.store, history=self.owner(f))

    def test_seed_repair_stops_without_reading_next_ordinal_or_creating_a_round_draft(self):
        f = self.fixture()
        service = self.service(f)
        (f.root / 'rounds/verified_history/current-verified-1.json').write_bytes(b'not a pointer')
        state = {'terminal_state': 'PAUSED_DECISION', 'profile_counts': {'clarity': 3}}
        (f.root / STATE_PATH).write_bytes(canonical_json_bytes(state))
        before = self.files(f)
        with patch.object(f.store, 'list_directory', side_effect=AssertionError('Stage 2 scan')):
            status = service.inspect()
            self.assertEqual(status.recovery_kind, 'seed_materialization')
            self.assertEqual(status.pending_paths, ('spec.md', STATE_PATH))
            self.assertEqual(self.files(f), before)
            with patch.object(f.store, 'publish', side_effect=AssertionError('new authority artifact')):
                with patch.object(f.store, 'replace_pointer', side_effect=AssertionError('pointer write')):
                    result = service.repair()
        self.assertFalse(result.pending_paths)
        self.assertEqual(f.store.read('spec.md'), f.store.read(result.pointer['verified_draft_path']))
        self.assertFalse((f.root / 'rounds/round-1/draft_after.md').exists())
        materialized = json.loads(f.store.read(STATE_PATH))
        self.assertEqual({k: v for k, v in materialized.items() if k != STATE_FIELD}, state)
        self.assertEqual(materialized[STATE_FIELD], result.pointer)
        self.assertEqual(f.store.read('rounds/verified_history/current-verified-1.json'), b'not a pointer')

    def test_promoted_repair_and_reentry_preserve_all_authority_bytes(self):
        f, pointer = self.promoted()
        service = self.service(f)
        before = self.files(f)
        status = service.inspect()
        self.assertEqual(status.recovery_kind, 'post_commit_materialization')
        self.assertEqual(status.pending_paths, ('spec.md', 'rounds/round-1/draft_after.md', STATE_PATH))
        self.assertEqual(self.files(f), before)
        with patch.object(f.store, 'publish', side_effect=AssertionError('authority publication')):
            with patch.object(f.store, 'replace_pointer', side_effect=AssertionError('pointer replacement')):
                service.repair()
                after = self.files(f)
                with patch.object(f.store, 'materialize', side_effect=AssertionError('already materialized')):
                    service.repair()
        self.assertEqual(self.files(f), after)
        self.assertTrue(all(after[path] == raw for path, raw in before.items()))
        self.assertEqual(f.store.read('spec.md'), f.store.read(pointer['verified_draft_path']))
        self.assertEqual(f.store.read('rounds/round-1/draft_after.md'), f.store.read('spec.md'))

    def test_each_interrupted_mirror_prefix_recovers_without_another_promotion(self):
        for path in ('spec.md', 'rounds/round-1/draft_after.md', STATE_PATH):
            for after_write in (False, True):
                with self.subTest(path=path, after_write=after_write):
                    f, pointer = self.promoted()
                    service = self.service(f)
                    write = f.store.materialize
                    def interrupt(token, target, raw, **options):
                        if target == path and not after_write: raise OSError('before mirror')
                        result = write(token, target, raw, **options)
                        if target == path and after_write: raise OSError('after mirror')
                        return result
                    with patch.object(f.store, 'materialize', side_effect=interrupt):
                        with self.assertRaises(OSError): service.repair()
                    self.assertEqual(json.loads(f.store.read('rounds/current_verified.json')), pointer)
                    with patch.object(f.store, 'replace_pointer', side_effect=AssertionError('repeat promotion')):
                        self.assertFalse(service.repair().pending_paths)

    def test_visible_uncertain_mirror_is_synchronized_on_reentry(self):
        f = self.fixture()
        service = self.service(f)
        write = f.store._tree.write
        def uncertain(path, raw, **options):
            result = write(path, raw, **options)
            if path == STATE_PATH:
                raise StorageWriteError(Publication('outcome_requires_reconciliation', path, result.hash), OSError('lost mirror ack'))
            return result
        with patch.object(f.store._tree, 'write', side_effect=uncertain):
            with self.assertRaises(StorageWriteError): service.repair()
        self.assertIsNone(f.store._token)
        self.assertFalse(service.inspect().pending_paths)
        synchronized = []
        sync = f.store.synchronize_existing
        def record(token, path, **options):
            synchronized.append(path)
            return sync(token, path, **options)
        with patch.object(f.store, 'synchronize_existing', side_effect=record):
            with patch.object(f.store, 'materialize', side_effect=AssertionError('visible mirror rewrite')):
                service.repair()
        self.assertIn(STATE_PATH, synchronized)

    def test_missing_committed_snapshot_and_invalid_state_are_not_guessed(self):
        f = self.fixture()
        service = self.service(f)
        (f.root / STATE_PATH).write_bytes(b'[]')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'JSON object'): service.repair()
        self.assertEqual(self.files(f), before)
        (f.root / STATE_PATH).unlink()
        (f.root / 'rounds/verified_history/current-verified-0.json').unlink()
        before = self.files(f)
        with self.assertRaises(FileNotFoundError): service.repair()
        self.assertEqual(self.files(f), before)

    def test_repair_uses_fresh_head_after_an_earlier_seed_inspection(self):
        f = self.ready()
        service = self.service(f)
        self.assertEqual(service.inspect().pointer['promotion_ordinal'], 0)
        self.run_request(f)
        final = f.decisions.commit_semantic(f.identifier, decided_at=history.STAMP)
        pointer = self.promote_fixture(f, final)
        self.assertEqual(service.repair().pointer, pointer)
        self.assertEqual(f.store.read('spec.md'), f.store.read(pointer['verified_draft_path']))

    def test_materialization_requires_its_pin_and_shared_fence(self):
        f = self.fixture(contract=False)
        with self.assertRaisesRegex(ValueError, 'materialization algorithm is outside supported suite'):
            self.service(f).repair()
        f = self.fixture()
        service = self.service(f)
        other = LocalAuthorityStore(f.root, job_id=f.creation['job_id'])
        self.addCleanup(other.close)
        before = self.files(f)
        with other.locked(self.owner(f).validate_authority):
            self.assertTrue(service.inspect().pending_paths)
            with self.assertRaises(StorageBusy): service.repair()
        self.assertEqual(self.files(f), before)
        token = f.store.acquire(self.owner(f).validate_authority)
        f.store.release(token)
        with self.assertRaises(OwnershipLost):
            f.store.materialize(token, 'spec.md', b'changed', validate_target=lambda *args: None)
        with self.assertRaises(OwnershipLost):
            f.store.synchronize_existing(token, 'rounds/current_verified.json', expected=b'{}')

    def test_promoted_recovery_does_not_validate_a_later_candidate_or_next_intent(self):
        f, pointer = self.promoted()
        (f.root / 'rounds/candidate_index/creation-2.json').write_bytes(b'not a registered candidate')
        path = f.root / f.creation['candidate_path'].rsplit('/', 1)[0] / 'promotion_intents/promotion-intent-2.json'
        path.write_bytes(b'not a next intent')
        service = self.service(f)
        self.assertEqual(service.inspect().pointer, pointer)
        with self.assertRaises(ValueError): self.owner(f).inspect()
        self.assertFalse(service.repair().pending_paths)
        self.assertEqual(path.read_bytes(), b'not a next intent')

    def test_matching_run_state_format_and_unrelated_members_are_preserved(self):
        f = self.fixture()
        service = self.service(f)
        service.repair()
        state = json.loads(f.store.read(STATE_PATH))
        state['profile_counts'] = {'clarity': 2}
        raw = json.dumps(state, indent=4).encode()
        (f.root / STATE_PATH).write_bytes(raw)
        self.assertFalse(service.inspect().pending_paths)
        with patch.object(f.store, 'materialize', side_effect=AssertionError('unneeded rewrite')):
            service.repair()
        self.assertEqual(f.store.read(STATE_PATH), raw)

    def test_read_only_classification_rechecks_head_after_mirror_reads(self):
        f = self.fixture()
        service = self.service(f)
        service.repair()
        read = f.store.read
        triggered = []
        def change(path):
            raw = read(path)
            if path == 'spec.md' and not triggered:
                triggered.append(path)
                (f.root / 'rounds/current_verified.json').write_bytes(b'{}')
            return raw
        with patch.object(f.store, 'read', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'authority changed during replay'): service.inspect()
        self.assertTrue(triggered)
        self.assertEqual(f.store.read('rounds/current_verified.json'), b'{}')

    def test_durability_failure_invalidates_ownership_without_creating_mirrors(self):
        f = self.fixture()
        before = self.files(f)
        with patch('whetstone.vnext_local_storage._full_flush', side_effect=OSError('scripted durability failure')):
            with self.assertRaises(StorageWriteError) as failure: self.service(f).repair()
        self.assertEqual(failure.exception.result.outcome, 'outcome_requires_reconciliation')
        self.assertIsNone(f.store._token)
        self.assertEqual(self.files(f), before)
        self.assertFalse(self.service(f).repair().pending_paths)

    def test_mirror_primitive_cannot_replace_authority_or_bypass_validation(self):
        f = self.fixture()
        before = self.files(f)
        with f.store.locked(self.owner(f).validate_authority) as token:
            for path in ('job_descriptor.json', 'rounds/current_verified.json',
                         'rounds/verified_history/current-verified-1.json',
                         'rounds/round-01/draft_after.md', '../spec.md'):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'unsupported materialization'):
                    f.store.materialize(token, path, b'changed', validate_target=lambda *args: None)
            def refuse(*args): raise ValueError('target validation refused')
            with self.assertRaisesRegex(ValueError, 'target validation refused'):
                f.store.materialize(token, 'spec.md', b'changed', validate_target=refuse)
            with self.assertRaises(FileNotFoundError):
                f.store.synchronize_existing(token, 'missing-evidence.json', expected=b'{}')
        self.assertEqual(self.files(f), before)


if __name__ == '__main__': unittest.main()
