"""Batch C: actual Verifier death on a canonical round above a promoted base."""
import json
import select
import signal
import subprocess
import sys
import unittest

from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_local_storage import StorageBusy
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from vnext_fixtures import STAMP
import test_vnext_semantic_requests as semantic
import test_vnext_verified_runtime_recovery as recovery


VERIFIER_PROCESS = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_run import open_verified_run
from test_vnext_semantic_requests import Client
from vnext_fixtures import STAMP
root,suite,point,candidate_id=sys.argv[1:]
manifest=json.loads(Path(suite).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite) as run:
    assert not run._staged
    context=load_registered_semantic_context(run.store,admission=run._history(),candidate_id=candidate_id)
    client=Client(context)
    publish=run.store.publish
    def interrupt(token,path,value):
        if client.calls != 1 or not path.endswith('/attempts/1/response.json'):
            return publish(token,path,value)
        if point == 'after': publish(token,path,value)
        print(json.dumps(dict(point=point,calls=client.calls,path=path)),flush=True)
        sys.stdin.readline()
        raise AssertionError('Verifier writer must be killed, not resumed')
    run.store.publish=interrupt
    run.verify(client=client,decided_at=STAMP)
'''


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimeVerifierFaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): recovery.RuntimeRecoveryTests.setUpClass()
    files = recovery.RuntimeRecoveryTests.files
    fixture = recovery.RuntimeRecoveryTests.fixture
    start = recovery.RuntimeRecoveryTests.start
    review = recovery.RuntimeRecoveryTests.review
    reopen = recovery.RuntimeRecoveryTests.reopen
    candidate = recovery.RuntimeRecoveryTests.candidate
    verify = recovery.RuntimeRecoveryTests.verify
    promoted = recovery.RuntimeRecoveryTests.promoted
    assert_retained = recovery.RuntimeRecoveryTests.assert_retained
    assert_no_later_authority = recovery.RuntimeRecoveryTests.assert_no_later_authority

    def test_killed_verifier_before_and_after_durable_raw_preserves_slots_and_authority(self):
        for point in ('before', 'after'):
            with self.subTest(point=point):
                f, reviewer = self.promoted()
                self.review(f, reviewer)
                creation = self.candidate(f, number=2)
                baseline = self.files(f)
                current = f.store.read(recovery.POINTER)
                candidate_directory = creation['candidate_path'].rsplit('/', 1)[0]
                pointer_path = candidate_directory + '/candidate_verification_current.json'
                child = subprocess.Popen([sys.executable, '-u', '-c', VERIFIER_PROCESS,
                    str(f.root), str(f.admission.suite_path), point, f.identifier],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                def cleanup(process=child):
                    if process.poll() is None: process.kill()
                    process.communicate(timeout=10)
                self.addCleanup(cleanup)
                readable, _, _ = select.select([child.stdout], [], [], 180)
                self.assertTrue(readable, 'Verifier did not reach raw publication boundary')
                line = child.stdout.readline()
                diagnostic = child.stderr.read().decode() if child.poll() is not None else repr(line)
                self.assertTrue(line, diagnostic)
                ready = json.loads(line)
                self.assertEqual((ready['point'], ready['calls']), (point, 1))
                raw_path = ready['path']
                directory = raw_path.rsplit('/attempts/', 1)[0]
                header = json.loads(f.store.read(directory + '/request.json'))
                self.assertEqual(header['candidate_id'], f.identifier)
                self.assertTrue((f.root / directory / 'attempts/1/invocation.json').exists())
                self.assertEqual((f.root / raw_path).exists(), point == 'after')
                self.assertFalse((f.root / directory / 'attempts/1/outcome.json').exists())
                initial = json.loads(f.store.read(candidate_directory + '/candidate_verification-attempt-1.json'))
                self.assertFalse(initial['decision_final'])
                self.assertEqual(initial['candidate_disposition'], 'CANDIDATE_UNVERIFIED')
                before = self.files(f)
                self.reopen(f)
                f.run.inspect()
                with self.assertRaises(StorageBusy): f.run.verify(decided_at=STAMP, continuation=True)
                with self.assertRaises(StorageBusy): f.run.promote(prepared_at=STAMP)
                self.assertEqual(self.files(f), before)
                child.kill()
                _, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode, -signal.SIGKILL, stderr.decode())
                self.reopen(f)
                context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=f.identifier)
                retry = semantic.Client(context)
                paused = f.run.verify(client=retry, decided_at=recovery.RETRY_STAMP)
                self.assertEqual(paused.outcome, 'continuation_required')
                self.assertEqual(paused.value.status, 'valid_response' if point == 'after' else 'interrupted')
                self.assertEqual(paused.value.attempts, 1)
                self.assertEqual(retry.calls, 0)
                self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
                self.assertEqual(self.files(f), before)
                result = f.run.verify(decided_at=recovery.RETRY_STAMP, continuation=True,
                    **({'client': retry} if point == 'before' else {}))
                self.assertEqual(result.outcome, 'candidate_final')
                self.assertEqual(result.value.decision['candidate_disposition'], 'CANDIDATE_VERIFIED')
                self.assertEqual(result.value.decision['semantic_result'], 'pass')
                self.assertEqual(result.value.decision['decision_ordinal'], 2)
                self.assertEqual(result.value.decision['decided_at'], recovery.RETRY_STAMP)
                self.assertEqual(retry.calls, 1 if point == 'before' else 0)
                outcome = json.loads(f.store.read(directory + '/attempts/1/outcome.json'))
                self.assertEqual(outcome['classification'], 'interrupted' if point == 'before' else 'valid_semantic')
                receipt = json.loads(f.store.read(directory + '/result.json'))
                attempt = 2 if point == 'before' else 1
                self.assertEqual(receipt['response']['path'], directory + f'/attempts/{attempt}/response.json')
                if point == 'before':
                    marker = json.loads(f.store.read(directory + '/attempts/2/invocation.json'))
                    self.assertEqual(marker['reason'], 'technical_continuation')
                    self.assertEqual(marker['previous_outcome_hash'], sha256_bytes(f.store.read(directory + '/attempts/1/outcome.json')))
                    self.assertFalse((f.root / raw_path).exists())
                else:
                    self.assertFalse((f.root / directory / 'attempts/2').exists())
                self.assertFalse((f.root / directory / 'attempts/3').exists())
                self.assert_retained(f, {path: raw for path, raw in before.items() if path != pointer_path})
                self.assert_retained(f, baseline)
                self.assert_no_later_authority(f, current)
                after = self.files(f)
                self.reopen(f)
                self.assertEqual(f.run.verify(client=retry, decided_at=STAMP).outcome, 'promotion_required')
                self.assertEqual(f.run.review_next(client=reviewer).outcome, 'promotion_required')
                self.assertEqual(self.files(f), after)
                self.assertEqual(retry.calls, 1 if point == 'before' else 0)
                self.assertEqual(reviewer.calls, 2)
                self.assertEqual(sum(client.calls for client in f.editors), 2)
                # One baseline Verifier call, one killed child call, plus only
                # the explicit retry above when no response was retained.
                self.assertEqual(sum(client.calls for client in f.verifiers), 1)


if __name__ == '__main__': unittest.main()
