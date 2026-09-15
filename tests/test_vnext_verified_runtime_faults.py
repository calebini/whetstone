"""Bounded runtime second-promotion process death and uncertain-commit checks."""
import json
import select
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone import vnext_local_storage as storage
from whetstone.vnext_proposal_run import RUN_INPUT_PATH
from vnext_fixtures import STAMP
import test_vnext_verified_runtime_followup as followup


POINTER = 'rounds/current_verified.json'
SNAPSHOT = 'rounds/verified_history/current-verified-2.json'
RETRY_STAMP = '2031-01-01T00:00:00Z'

# The child receives only root/suite locators, not caller-supplied round selectors.
# Registering the fictional suite is process-local and never activates shipping.
WRITER = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry, vnext_local_storage as storage
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite,point,stamp=sys.argv[1:]
manifest=json.loads(Path(suite).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite) as run:
    assert not run._staged
    replace=storage.os.replace
    def interrupt(source,destination,**options):
        if destination != 'current_verified.json':
            return replace(source,destination,**options)
        if point == 'after': replace(source,destination,**options)
        print('paused-'+point,flush=True)
        sys.stdin.readline()
        raise AssertionError('paused writer must be killed, never resumed')
    storage.os.replace=interrupt
    run.promote(prepared_at=stamp)
'''


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimePromotionFaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): followup.RuntimeFollowupTests.setUpClass()
    files = followup.RuntimeFollowupTests.files
    fixture = followup.RuntimeFollowupTests.fixture
    start = followup.RuntimeFollowupTests.start
    review = followup.RuntimeFollowupTests.review
    reopen = followup.RuntimeFollowupTests.reopen
    candidate = followup.RuntimeFollowupTests.candidate
    verify = followup.RuntimeFollowupTests.verify
    second = followup.RuntimeFollowupTests.second
    assert_counts = followup.RuntimeFollowupTests.assert_counts

    def eligible_second(self):
        f, reviewer = self.start()
        self.review(f, reviewer)
        self.candidate(f, number=1)
        self.verify(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 1)
        self.reopen(f)
        self.second(f, reviewer)
        self.assertEqual(json.loads(f.store.read(RUN_INPUT_PATH))['staged_rounds'], [])
        self.assertEqual(json.loads(f.store.read('rounds/round-2/proposal_input.json'))['base_pointer']['path'],
                         'rounds/verified_history/current-verified-1.json')
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)
        return f, reviewer

    def readback(self, f, *, committed):
        before = self.files(f)
        self.reopen(f)
        view = f.run.inspect()
        self.assertEqual(view.current_pointer['promotion_ordinal'], 2 if committed else 1)
        expected = 'materialization_required' if committed else 'promotion_required'
        self.assertEqual(view.outcome, expected)
        self.assertEqual(f.run.review_status().outcome, expected)
        self.assertEqual(self.files(f), before)
        return before

    def recover(self, f, reviewer, before, *, committed):
        prepared = f.store.read(SNAPSHOT)
        self.assertEqual(json.loads(prepared)['promoted_at'], STAMP)
        self.assertEqual(json.loads(prepared)['source_candidate_id'], f.identifier)
        if committed:
            # Repair must end this invocation, even with a Reviewer available.
            with patch.object(f.store, 'replace_pointer', side_effect=AssertionError('repair cannot recommit')):
                result = f.run.review_next(client=reviewer)
            self.assertEqual(result.outcome, 'materialization_recovered')
        else:
            result = f.run.promote(prepared_at=RETRY_STAMP)
            self.assertEqual(result.outcome, 'promoted')
        self.assertEqual(f.store.read(POINTER), prepared)
        pointer = json.loads(prepared)
        draft = f.store.read(pointer['verified_draft_path'])
        self.assertEqual(f.store.read('spec.md'), draft)
        self.assertEqual(f.store.read('rounds/round-2/draft_after.md'), draft)
        self.assertEqual(json.loads(f.store.read('rounds/run_state.json'))['vnext_current_verified'], pointer)
        mutable = {POINTER, 'spec.md', 'rounds/run_state.json', 'rounds/round-2/draft_after.md'}
        for path, raw in before.items():
            if path not in mutable and not path.rsplit('/', 1)[-1].startswith('.vnext-tmp-'):
                self.assertEqual(f.store.read(path), raw, path)
        # No new review claim, client request or candidate/event/ordinal is allowed.
        after = self.files(f)
        self.assertLessEqual(set(after) - set(before), mutable)
        self.assertFalse((f.root / 'rounds/verified_history/current-verified-3.json').exists())
        self.assertFalse((f.root / 'rounds/review_index/request-3.json').exists())
        self.assertEqual(f.run.promote(prepared_at=RETRY_STAMP).outcome, 'not_eligible')
        self.assertEqual(self.files(f), after)
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)
        self.reopen(f)
        self.assertEqual(f.run.review_status().round_number, 3)
        self.assertEqual(self.files(f), after)

    def test_killed_runtime_writer_before_and_after_second_pointer_rename(self):
        for point in ('before', 'after'):
            with self.subTest(point=point):
                f, reviewer = self.eligible_second()
                child = subprocess.Popen([sys.executable, '-u', '-c', WRITER, str(f.root),
                    str(f.admission.suite_path), point, STAMP], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                def cleanup(process=child):
                    if process.poll() is None: process.kill()
                    process.communicate(timeout=10)
                self.addCleanup(cleanup)
                readable, _, _ = select.select([child.stdout], [], [], 180)
                self.assertTrue(readable, 'runtime writer did not reach the pointer rename')
                line = child.stdout.readline()
                diagnostic = child.stderr.read().decode() if child.poll() is not None else repr(line)
                self.assertEqual(line, ('paused-' + point + '\n').encode(), diagnostic)
                before = self.readback(f, committed=point == 'after')
                # Parent and child are separate processes contending on the same
                # root; exercise cross-role work/registration as well as promotion.
                for name, operation in (
                    ('request', lambda: f.run.request(round_number=2, client=f.editors[-1])),
                    ('register', lambda: f.run.register(round_number=2, created_at=RETRY_STAMP)),
                    ('promote', lambda: f.run.promote(prepared_at=RETRY_STAMP)),
                ):
                    with self.subTest(contender=name), self.assertRaises(storage.StorageBusy): operation()
                    self.assertEqual(self.files(f), before)
                self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)
                child.kill()
                _, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode, -signal.SIGKILL, stderr.decode())
                self.assertEqual(self.files(f), before)
                recovered = self.readback(f, committed=point == 'after')
                self.recover(f, reviewer, recovered, committed=point == 'after')

    def test_uncertain_second_rename_poisoned_owner_requires_fresh_runtime_readback(self):
        f, reviewer = self.eligible_second()
        replace = storage.os.replace
        pointer = f.store.replace_pointer
        stale = []
        faults = []
        def lose_ack(source, destination, **options):
            result = replace(source, destination, **options)
            if destination == 'current_verified.json':
                faults.append(destination)
                raise OSError('lost runtime second rename acknowledgement')
            return result
        def observe(token, path, **options):
            stale.append(token)
            try:
                return pointer(token, path, **options)
            except storage.StorageWriteError:
                # Check poisoning before the enclosing locked() context unwinds;
                # ordinary context-manager release cannot satisfy this assertion.
                self.assertIsNone(f.store._token)
                self.assertIsNone(f.store._lock_fd)
                with self.assertRaises(storage.OwnershipLost):
                    f.store.publish(token, 'rounds/stale-owner-must-not-write', b'forbidden')
                raise
        with patch.object(storage.os, 'replace', side_effect=lose_ack), \
                patch.object(f.store, 'replace_pointer', side_effect=observe):
            with self.assertRaises(storage.StorageWriteError) as error:
                f.run.promote(prepared_at=STAMP)
        self.assertEqual(error.exception.result.outcome, 'outcome_requires_reconciliation')
        self.assertEqual(error.exception.result.path, POINTER)
        self.assertEqual(faults, ['current_verified.json'])
        self.assertEqual(len(stale), 1)
        self.assertEqual(f.store.read(POINTER), f.store.read(SNAPSHOT))
        failed_store = f.store
        before = self.readback(f, committed=True)
        with self.assertRaises(storage.OwnershipLost):
            failed_store.publish(stale[0], 'rounds/stale-owner-must-not-write', b'forbidden')
        self.assertEqual(self.files(f), before)
        self.recover(f, reviewer, before, committed=True)


if __name__ == '__main__': unittest.main()
