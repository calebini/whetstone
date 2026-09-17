"""Batch C checkpoint: real process handoff and partial runtime mirror repair."""
import json
import select
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_local_storage import StorageBusy
from whetstone.vnext_verified_materialization import STATE_FIELD, STATE_PATH
from vnext_fixtures import STAMP
import test_vnext_verified_runtime_faults as batch_a


POINTER = 'rounds/current_verified.json'
SNAPSHOT = 'rounds/verified_history/current-verified-2.json'
MIRRORS = ('spec.md', 'rounds/round-2/draft_after.md', STATE_PATH)

# Register only the fictional suite in this process. Production run reopening
# resolves its own round selectors; the parent supplies no historical selectors.
WRITER = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_local_storage import OwnershipLost
from whetstone.vnext_verified_materialization import VerifiedMaterialization
from whetstone.vnext_verified_run import open_verified_run
root,suite,point,stamp=sys.argv[1:]
manifest=json.loads(Path(suite).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite) as run:
    assert not run._staged
    if point == 'handoff':
        tokens=[]
        replace=run.store.replace_pointer
        def capture(token,path,**options):
            tokens.append(token)
            return replace(token,path,**options)
        run.store.replace_pointer=capture
        repair=VerifiedMaterialization.repair
        synchronized=[]
        def paused_repair(owner):
            assert owner.store is run.store
            assert run.store._token is None and run.store._lock_fd is None
            assert len(tokens) == 1
            try: run.store.publish(tokens[0],'rounds/stale-handoff-write',b'forbidden')
            except OwnershipLost: pass
            else: raise AssertionError('released promotion token still writes')
            print(json.dumps(dict(point=point,released=True,stale_token_refused=True)),flush=True)
            assert sys.stdin.readline() == 'resume\\n'
            synchronize=run.store.synchronize_existing
            def trace(token,path,**options):
                synchronized.append(path)
                return synchronize(token,path,**options)
            def forbidden(*args,**kwargs): raise AssertionError('fresh matching authority must not be rewritten')
            run.store.synchronize_existing=trace
            run.store.materialize=forbidden
            run.store.publish=forbidden
            run.store.replace_pointer=forbidden
            return repair(owner)
        VerifiedMaterialization.repair=paused_repair
        result=run.promote(prepared_at=stamp)
        print(json.dumps(dict(outcome=result.outcome,committed=result.committed_pointer['promotion_ordinal'],
            current=result.current_pointer['promotion_ordinal'],synchronized=synchronized)),flush=True)
    else:
        materialize=run.store.materialize
        def interrupt(token,path,raw,**options):
            result=materialize(token,path,raw,**options)
            if path == point:
                run.store._check_owner(token)
                print(json.dumps(dict(point=point,locked=True)),flush=True)
                sys.stdin.readline()
                raise AssertionError('partial mirror writer must be killed, not resumed')
            return result
        run.store.materialize=interrupt
        run.promote(prepared_at=stamp)
'''


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimeMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): batch_a.RuntimePromotionFaultTests.setUpClass()
    files = batch_a.RuntimePromotionFaultTests.files
    fixture = batch_a.RuntimePromotionFaultTests.fixture
    start = batch_a.RuntimePromotionFaultTests.start
    review = batch_a.RuntimePromotionFaultTests.review
    reopen = batch_a.RuntimePromotionFaultTests.reopen
    candidate = batch_a.RuntimePromotionFaultTests.candidate
    verify = batch_a.RuntimePromotionFaultTests.verify
    second = batch_a.RuntimePromotionFaultTests.second
    assert_counts = batch_a.RuntimePromotionFaultTests.assert_counts
    eligible_second = batch_a.RuntimePromotionFaultTests.eligible_second

    def prepared(self):
        f, reviewer = self.eligible_second()
        state = json.loads(f.store.read(STATE_PATH))
        state['operator_note'] = {'text': 'retain across recovery', 'sequence': [1, 2]}
        (f.root / STATE_PATH).write_text(json.dumps(state, indent=2) + '\n')
        return f, reviewer, {key: value for key, value in state.items() if key != STATE_FIELD}

    def child(self, f, point):
        child = subprocess.Popen([sys.executable, '-u', '-c', WRITER, str(f.root),
            str(f.admission.suite_path), point, STAMP], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if child.poll() is None: child.kill()
            child.communicate(timeout=10)
        self.addCleanup(cleanup)
        readable, _, _ = select.select([child.stdout], [], [], 180)
        self.assertTrue(readable, 'runtime writer did not reach selected materialization boundary')
        line = child.stdout.readline()
        diagnostic = child.stderr.read().decode() if child.poll() is not None else repr(line)
        self.assertTrue(line, diagnostic)
        expected = dict(point=point, released=True, stale_token_refused=True) if point == 'handoff' else dict(point=point, locked=True)
        self.assertEqual(json.loads(line), expected)
        return child

    def readonly(self, f, pending):
        before = self.files(f)
        self.reopen(f)
        for view in (f.run.inspect(), f.run.review_status()):
            self.assertEqual(view.outcome, 'materialization_required')
            self.assertEqual(view.current_pointer['promotion_ordinal'], 2)
            self.assertEqual(view.pending_paths, pending)
        self.assertEqual(self.files(f), before)
        return before

    def mirrors_match(self, f, ordinal, unrelated):
        pointer = json.loads(f.store.read(POINTER))
        self.assertEqual(pointer['promotion_ordinal'], ordinal)
        self.assertEqual(f.store.read(POINTER), f.store.read(f'rounds/verified_history/current-verified-{ordinal}.json'))
        raw = f.store.read(pointer['verified_draft_path'])
        self.assertEqual(f.store.read('spec.md'), raw)
        self.assertEqual(f.store.read(f'rounds/round-{ordinal}/draft_after.md'), raw)
        state = json.loads(f.store.read(STATE_PATH))
        self.assertEqual(state[STATE_FIELD], pointer)
        self.assertEqual({key: value for key, value in state.items() if key != STATE_FIELD}, unrelated)

    def test_released_promoter_repairs_fresh_head_after_another_runtime_advances(self):
        f, reviewer, unrelated = self.prepared()
        child = self.child(f, 'handoff')
        before = self.readonly(f, MIRRORS)
        second_pointer = f.store.read(SNAPSHOT)
        # The promotion fence was normally released: another process can repair
        # ordinal 2, complete round 3 and promote before the first writer resumes.
        self.assertEqual(f.run.review_next(client=reviewer).outcome, 'materialization_recovered')
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)
        self.mirrors_match(f, 2, unrelated)
        self.review(f, reviewer)
        third = self.candidate(f, number=3, content='Queue always waits before work begins.\n')
        self.verify(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 3)
        self.assert_counts(f, reviewer, reviews=3, editors=3, verifiers=3)
        self.mirrors_match(f, 3, unrelated)
        self.assertNotEqual(f.store.read(POINTER), second_pointer)
        self.assertEqual(json.loads(f.store.read(POINTER))['source_candidate_id'], third['candidate_id'])
        current_files = self.files(f)
        child.stdin.write(b'resume\n'); child.stdin.flush()
        stdout, stderr = child.communicate(timeout=180)
        self.assertEqual(child.returncode, 0, stderr.decode())
        result = json.loads(stdout)
        self.assertEqual((result['outcome'], result['committed'], result['current']), ('promoted', 2, 3))
        self.assertEqual(set(result['synchronized']), {'rounds/verified_history/current-verified-3.json', POINTER,
                                                     'spec.md', 'rounds/round-3/draft_after.md', STATE_PATH})
        self.assertEqual(self.files(f), current_files)
        self.assertEqual(f.store.read(SNAPSHOT), second_pointer)
        for path, raw in before.items():
            if path not in {POINTER, 'spec.md', STATE_PATH}: self.assertEqual(f.store.read(path), raw, path)
        self.assertFalse((f.root / 'rounds/verified_history/current-verified-4.json').exists())
        self.assertFalse((f.root / 'rounds/stale-handoff-write').exists())
        self.assert_counts(f, reviewer, reviews=3, editors=3, verifiers=3)
        self.reopen(f)
        self.assertEqual(f.run.inspect().current_pointer['promotion_ordinal'], 3)
        self.assertEqual(self.files(f), current_files)

    def test_killed_partial_mirror_writer_repairs_only_remaining_targets(self):
        for point in MIRRORS[:2]:
            with self.subTest(point=point):
                f, reviewer, unrelated = self.prepared()
                child = self.child(f, point)
                completed = MIRRORS[:MIRRORS.index(point) + 1]
                pending = MIRRORS[len(completed):]
                before = self.readonly(f, pending)
                committed = f.store.read(POINTER)
                self.assertEqual(committed, f.store.read(SNAPSHOT))
                draft = f.store.read(json.loads(committed)['verified_draft_path'])
                for path in completed: self.assertEqual(f.store.read(path), draft)
                self.assertEqual(json.loads(f.store.read(STATE_PATH))[STATE_FIELD]['promotion_ordinal'], 1)
                for action in (lambda: f.run.review_next(client=reviewer), lambda: f.run.promote(prepared_at=STAMP)):
                    with self.assertRaises(StorageBusy): action()
                    self.assertEqual(self.files(f), before)
                child.kill()
                _, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode, -signal.SIGKILL, stderr.decode())
                self.assertEqual(self.files(f), before)
                self.readonly(f, pending)
                synchronized, written = [], []
                sync, materialize = f.store.synchronize_existing, f.store.materialize
                def trace_sync(token, path, **options):
                    synchronized.append(path)
                    return sync(token, path, **options)
                def trace_write(token, path, raw, **options):
                    written.append(path)
                    return materialize(token, path, raw, **options)
                with patch.object(f.store, 'synchronize_existing', side_effect=trace_sync), \
                        patch.object(f.store, 'materialize', side_effect=trace_write), \
                        patch.object(f.store, 'publish', side_effect=AssertionError('new authority during repair')), \
                        patch.object(f.store, 'replace_pointer', side_effect=AssertionError('recommit during repair')):
                    self.assertEqual(f.run.review_next(client=reviewer).outcome, 'materialization_recovered')
                self.assertEqual(tuple(written), pending)
                self.assertLessEqual({SNAPSHOT, POINTER, *completed}, set(synchronized))
                self.mirrors_match(f, 2, unrelated)
                self.assertEqual(f.store.read(POINTER), committed)
                for path, raw in before.items():
                    if path not in pending: self.assertEqual(f.store.read(path), raw, path)
                after = self.files(f)
                self.assertLessEqual(set(after) - set(before), set(pending))
                self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
                self.reopen(f)
                self.assertEqual(f.run.review_status().round_number, 3)
                self.assertEqual(self.files(f), after)
                self.assertFalse((f.root / 'rounds/verified_history/current-verified-3.json').exists())
                self.assertFalse((f.root / 'rounds/review_index/request-3.json').exists())
                self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)


if __name__ == '__main__': unittest.main()
