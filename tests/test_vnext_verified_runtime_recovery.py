"""Batch B: durable Reviewer slots and canonical-runtime recovery precedence."""
from copy import deepcopy
import json
import select
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_local_storage import StorageBusy
from whetstone.vnext_proposal_run import RUN_INPUT_PATH
from vnext_fixtures import STAMP
import test_vnext_verified_review_requests as journal
import test_vnext_verified_runtime_followup as followup


POINTER = 'rounds/current_verified.json'
RETRY_STAMP = '2031-01-01T00:00:00Z'


class ScriptedReviewer(journal.Reviewer):
    """Same fictional transport with response templates, not round selectors."""
    def __init__(self, config):
        self.identity = deepcopy(config['identity'])
        self.feedback = deepcopy(config['feedback'])
        self.hints = deepcopy(config['hints'])
        self.calls, self.timeout, self.callback, self.prompts = 0, 5, None, []


REVIEWER_PROCESS = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
from test_vnext_verified_runtime_recovery import ScriptedReviewer
root,suite,point,config=sys.argv[1:]
manifest=json.loads(Path(suite).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite) as run:
    assert not run._staged
    client=ScriptedReviewer(json.loads(config))
    publish=run.store.publish
    def interrupt(token,path,value):
        if client.calls != 1 or not path.endswith('/attempts/1/response.json'):
            return publish(token,path,value)
        if point == 'after': publish(token,path,value)
        print(json.dumps(dict(point=point,calls=client.calls)),flush=True)
        sys.stdin.readline()
        raise AssertionError('Reviewer writer must be killed, not resumed')
    run.store.publish=interrupt
    run.review_next(client=client)
'''


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimeRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): followup.RuntimeFollowupTests.setUpClass()
    files = followup.RuntimeFollowupTests.files
    fixture = followup.RuntimeFollowupTests.fixture
    start = followup.RuntimeFollowupTests.start
    review = followup.RuntimeFollowupTests.review
    reopen = followup.RuntimeFollowupTests.reopen
    candidate = followup.RuntimeFollowupTests.candidate
    verify = followup.RuntimeFollowupTests.verify
    assert_counts = followup.RuntimeFollowupTests.assert_counts

    def promoted(self):
        f, reviewer = self.start()
        self.review(f, reviewer)
        self.candidate(f, number=1)
        self.verify(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 1)
        self.reopen(f)
        self.assertEqual(json.loads(f.store.read(RUN_INPUT_PATH))['staged_rounds'], [])
        self.assertEqual(f.run.review_status().round_number, 2)
        return f, reviewer

    def raw_path(self, f, number):
        header = json.loads(f.store.read(f'rounds/review_index/request-{number}.json'))
        return f"rounds/client_requests/{header['request_id']}/attempts/1/response.json"

    def assert_retained(self, f, before):
        for path, raw in before.items(): self.assertEqual(f.store.read(path), raw, path)

    def refuses_altered_review(self, f, operation, *, number):
        path = f.root / self.raw_path(f, number)
        original = path.read_bytes()
        before = self.files(f)
        try:
            path.write_bytes(original + b' ')
            altered = self.files(f)
            with self.assertRaises(ValueError): operation()
            self.assertEqual(self.files(f), altered)
        finally:
            path.write_bytes(original)
        self.assertEqual(self.files(f), before)

    def assert_no_later_authority(self, f, current):
        self.assertEqual(f.store.read(POINTER), current)
        self.assertFalse((f.root / 'rounds/verified_history/current-verified-2.json').exists())
        self.assertFalse((f.root / 'rounds/review_index/request-3.json').exists())
        self.assertFalse((f.root / 'rounds/candidate_index/creation-3.json').exists())

    def test_killed_reviewer_before_and_after_durable_raw_preserves_slots(self):
        for point in ('before', 'after'):
            with self.subTest(point=point):
                f, reviewer = self.promoted()
                baseline = self.files(f)
                current = f.store.read(POINTER)
                config = {key: getattr(reviewer, key) for key in ('identity', 'feedback', 'hints')}
                child = subprocess.Popen([sys.executable, '-u', '-c', REVIEWER_PROCESS,
                    str(f.root), str(f.admission.suite_path), point, json.dumps(config)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                def cleanup(process=child):
                    if process.poll() is None: process.kill()
                    process.communicate(timeout=10)
                self.addCleanup(cleanup)
                readable, _, _ = select.select([child.stdout], [], [], 180)
                self.assertTrue(readable, 'Reviewer did not reach raw publication boundary')
                line = child.stdout.readline()
                diagnostic = child.stderr.read().decode() if child.poll() is not None else repr(line)
                self.assertTrue(line, diagnostic)
                self.assertEqual(json.loads(line), dict(point=point, calls=1))
                raw_path = self.raw_path(f, 2)
                directory = raw_path.rsplit('/attempts/', 1)[0]
                self.assertTrue((f.root / directory / 'attempts/1/invocation.json').exists())
                self.assertEqual((f.root / raw_path).exists(), point == 'after')
                self.assertFalse((f.root / directory / 'attempts/1/outcome.json').exists())
                before = self.files(f)
                self.reopen(f)
                self.assertEqual(f.run.review_status().status, 'valid_response' if point == 'after' else 'interrupted')
                with self.assertRaises(StorageBusy): f.run.review_next(client=reviewer, continuation=True)
                self.assertEqual(self.files(f), before)
                child.kill()
                _, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode, -signal.SIGKILL, stderr.decode())
                self.reopen(f)
                self.assertEqual(f.run.review_status().attempts, 1)
                self.assertEqual(f.run.review_next(client=reviewer).status, 'continuation_required')
                self.assertEqual(self.files(f), before)
                self.assertEqual(reviewer.calls, 1)
                # Retained raw needs no client at all; missing raw consumes only
                # the second allowed invocation after explicit continuation.
                result = f.run.review_next(continuation=True, **({'client': reviewer} if point == 'before' else {}))
                self.assertEqual(result.status, 'complete')
                self.assertEqual(result.attempts, 2 if point == 'before' else 1)
                self.assertEqual(reviewer.calls, 2 if point == 'before' else 1)
                outcome = json.loads(f.store.read(directory + '/attempts/1/outcome.json'))
                self.assertEqual(outcome['classification'], 'interrupted' if point == 'before' else 'valid_review')
                if point == 'before':
                    marker = json.loads(f.store.read(directory + '/attempts/2/invocation.json'))
                    self.assertEqual(marker['reason'], 'technical_continuation')
                    self.assertEqual(marker['previous_outcome_hash'], sha256_bytes(f.store.read(directory + '/attempts/1/outcome.json')))
                    self.assertFalse((f.root / raw_path).exists())
                else:
                    self.assertFalse((f.root / directory / 'attempts/2').exists())
                self.assertFalse((f.root / directory / 'attempts/3').exists())
                self.assert_retained(f, before)
                self.assertEqual(f.run.review_next(client=reviewer).status, 'finding_admission')
                ref = f.run.admit_reviewed_round()
                record = json.loads(f.store.read(ref['path']))
                self.assertEqual(record['base_pointer']['path'], 'rounds/verified_history/current-verified-1.json')
                self.assertEqual(ref['path'], 'rounds/round-2/proposal_input.json')
                self.assert_retained(f, baseline)
                self.assert_no_later_authority(f, current)
                self.assertEqual((sum(c.calls for c in f.editors), sum(c.calls for c in f.verifiers)), (1, 1))
                self.assertEqual(reviewer.calls, 2 if point == 'before' else 1)

    def test_runtime_registration_orphan_recovers_before_work_and_rechecks_original_review(self):
        f, reviewer = self.promoted()
        self.review(f, reviewer)
        current = f.store.read(POINTER)
        editor = followup.history.verified.fixtures.Client()
        f.editors.append(editor)
        self.assertEqual(f.run.request(round_number=2, client=editor).value.status, 'complete')
        publish = f.store.publish
        pending = []
        def interrupt(token, path, value):
            if path == 'rounds/candidate_index/creation-2.json':
                pending.append(deepcopy(value))
                raise OSError('before runtime creation event')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'before runtime creation'):
                f.run.register(round_number=2, created_at=STAMP)
        self.assertEqual(len(pending), 1)
        before = self.files(f)
        self.reopen(f)
        self.assertEqual(f.run.inspect().outcome, 'registration_recovery_required')
        for action in (lambda: f.run.request(round_number=2, client=editor),
                       lambda: f.run.register(round_number=2, created_at=RETRY_STAMP),
                       lambda: f.run.verify(decided_at=STAMP),
                       lambda: f.run.review_next(client=reviewer)):
            self.assertEqual(action().outcome, 'registration_recovery_required')
            self.assertEqual(self.files(f), before)
        self.refuses_altered_review(f, f.run.recover_registration, number=1)
        recovered = f.run.recover_registration()
        self.assertEqual(recovered.outcome, 'registration_recovered')
        self.assertEqual(recovered.latest_candidate, pending[0])
        self.assertEqual(recovered.latest_candidate['created_at'], STAMP)
        self.assertFalse(recovered.value.orphans)
        directory = pending[0]['candidate_path'].rsplit('/', 1)[0]
        self.assertFalse((f.root / directory / 'candidate_verification_current.json').exists())
        self.assertEqual(json.loads(f.store.read(pending[0]['initial_disposition_event_path']))['new_disposition'], 'CANDIDATE_UNVERIFIED')
        self.assert_retained(f, before)
        self.assertEqual(set(self.files(f)) - set(before), {'rounds/candidate_index/creation-2.json'})
        after = self.files(f)
        self.assertEqual(f.run.recover_registration().outcome, 'no_registration_recovery')
        self.assertEqual(self.files(f), after)
        self.assert_no_later_authority(f, current)
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=1)

    def test_runtime_prepared_verification_recovers_without_client_or_promotion(self):
        f, reviewer = self.promoted()
        self.review(f, reviewer)
        creation = self.candidate(f, number=2)
        current = f.store.read(POINTER)
        directory = creation['candidate_path'].rsplit('/', 1)[0]
        target = directory + '/disposition_events/event-3.json'
        publish = f.store.publish
        def interrupt(token, path, value):
            result = publish(token, path, value)
            if path == target: raise OSError('after runtime prepared verification event')
            return result
        with patch.object(f.store, 'publish', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'runtime prepared verification'): self.verify(f)
        decision = f.store.read(directory + '/candidate_verification-attempt-2.json')
        self.assertFalse((f.root / directory / 'candidate_verification_pointer-attempt-2.json').exists())
        before = self.files(f)
        self.reopen(f)
        result = f.run.verify(decided_at=RETRY_STAMP)
        self.assertEqual(result.outcome, 'continuation_required')
        self.assertTrue(result.value.prepared)
        self.assertEqual(result.value.decision['decision_ordinal'], 1)
        self.assertEqual(result.value.decision['candidate_disposition'], 'CANDIDATE_UNVERIFIED')
        self.assertEqual(f.run.promote(prepared_at=RETRY_STAMP).outcome, 'not_eligible')
        self.assertEqual(self.files(f), before)
        self.refuses_altered_review(f, lambda: f.run.verify(decided_at=RETRY_STAMP, continuation=True), number=2)
        recovered = f.run.verify(decided_at=RETRY_STAMP, continuation=True)
        self.assertEqual(recovered.outcome, 'verification_recovered')
        self.assertEqual(recovered.value.decision, json.loads(decision))
        self.assertEqual(recovered.value.decision['decided_at'], STAMP)
        self.assertEqual(recovered.value.decision['candidate_disposition'], 'CANDIDATE_VERIFIED')
        self.assertFalse(recovered.value.prepared)
        self.assertTrue(recovered.value.decision['promotion_permitted'])
        mutable = directory + '/candidate_verification_current.json'
        self.assert_retained(f, {path: raw for path, raw in before.items() if path != mutable})
        self.assertEqual(set(self.files(f)) - set(before), {directory + '/candidate_verification_pointer-attempt-2.json'})
        after = self.files(f)
        self.assertEqual(f.run.review_next(client=reviewer).outcome, 'promotion_required')
        self.assertEqual(f.run.verify(decided_at=RETRY_STAMP).outcome, 'promotion_required')
        self.assertEqual(self.files(f), after)
        self.assert_no_later_authority(f, current)
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)


if __name__ == '__main__': unittest.main()
