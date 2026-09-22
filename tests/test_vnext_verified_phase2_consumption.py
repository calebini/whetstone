"""First-result accounting and fail-closed finding consumption."""
from copy import deepcopy
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_phase2_consumption import PATH
from whetstone.vnext_verified_phase2_client import JOURNAL_PATH
import test_vnext_verified_phase2_client as client_tests


@unittest.skipUnless(sys.platform=='darwin', 'Local storage targets macOS/APFS')
class Phase2ConsumptionTests(unittest.TestCase):
    setUpClass = client_tests.VerifiedPhase2ClientTests.setUpClass
    fixture = client_tests.VerifiedPhase2ClientTests.fixture
    files = client_tests.VerifiedPhase2ClientTests.files
    reopen = client_tests.VerifiedPhase2ClientTests.reopen
    config = client_tests.VerifiedPhase2ClientTests.config
    ready = client_tests.VerifiedPhase2ClientTests.ready

    def start(self, **kwargs):
        kwargs['phase2_consumption_contract'] = True
        return client_tests.VerifiedPhase2ClientTests.start(self, **kwargs)

    def test_result_required_and_retry_counts_once_with_fail_closed_findings(self):
        f, client, _ = self.ready()
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'committed result'):
            f.run.consume_phase2_result()
        self.assertEqual(self.files(f), before)
        client.callback = lambda owner, feedback: b'{' if owner.calls == 1 else canonical_json_bytes(feedback)
        f.run.run_phase2_review(client=client)
        before = self.files(f)
        with patch.object(f.store, 'locked', side_effect=AssertionError('read-only lock')):
            view = f.run.phase2_consumption_status()
        self.assertFalse(view['committed'])
        self.assertEqual(self.files(f), before)
        packet = f.run.consume_phase2_result()
        self.assertEqual(client.calls, 2)
        self.assertEqual([r['rounds_used'] for r in packet['profiles']], [1,0,0])
        self.assertEqual([r['step_index'] for r in packet['profiles']], [1,2,3])
        self.assertEqual(packet['profiles'][0]['profile'], packet['profiles'][2]['profile'])
        self.assertTrue(packet['profiles'][0]['exhausted'])
        self.assertEqual(packet['next_gate'], 'finding_admission')
        self.assertTrue(packet['findings'])
        self.assertTrue(all(r['classification'] != 'editor_fixable' for r in packet['findings']))
        self.assertTrue(all('missing_advice' in r['reasons'] for r in packet['evidence'].values()))
        after = self.files(f)
        self.assertEqual(set(after)-set(before), {PATH})
        for path, raw in before.items(): self.assertEqual(after[path], raw)
        packet['profiles'][0]['rounds_used'] = 99
        self.reopen(f)
        replay = f.run.consume_phase2_result()
        self.assertEqual(replay['profiles'][0]['rounds_used'], 1)
        self.assertEqual(self.files(f), after)
        self.assertTrue(f.run.phase2_consumption_status()['committed'])
        # A visible consumption cannot reconstruct a deleted result dependency.
        (f.root/JOURNAL_PATH/'reviewer_feedback.json').unlink()
        with self.assertRaises(ValueError): f.run.consume_phase2_result()

    def test_clean_result_uncertain_publication_and_replay_barrier(self):
        f, client, _ = self.ready()
        def clean(owner, feedback):
            feedback['feedback'] = []
            return canonical_json_bytes(feedback)
        client.callback = clean
        f.run.run_phase2_review(client=client)
        synchronize = f.store.synchronize_existing
        def blocked(token, path, **kwargs):
            if path == JOURNAL_PATH+'/result.json': raise OSError('before consumption')
            return synchronize(token, path, **kwargs)
        with patch.object(f.store, 'synchronize_existing', side_effect=blocked):
            with self.assertRaisesRegex(OSError, 'before consumption'): f.run.consume_phase2_result()
        self.assertFalse((f.root/PATH).exists())
        publish = f.store.publish
        def uncertain(token, path, value):
            result = publish(token, path, value)
            if path == PATH:
                f.store._check_owner(token)
                raise OSError('lost acknowledgement')
            return result
        with patch.object(f.store, 'publish', side_effect=uncertain):
            with self.assertRaisesRegex(OSError, 'lost acknowledgement'): f.run.consume_phase2_result()
        self.reopen(f)
        packet = f.run.consume_phase2_result()
        self.assertTrue(packet['profiles'][0]['clean'])
        self.assertFalse(packet['profiles'][2]['clean'])
        self.assertFalse(packet['phase_complete'])
        self.assertFalse(packet['next_review_authorized'])
        self.assertFalse(packet['candidate_authorized'])
        self.assertEqual(packet['next_gate'], 'subsequent_request_not_implemented')
        self.assertEqual(client.calls, 1)
        sync = f.store.synchronize_existing
        def failure(token, path, **kwargs):
            if path == JOURNAL_PATH+'/result.json': raise OSError('result barrier')
            return sync(token, path, **kwargs)
        with patch.object(f.store, 'synchronize_existing', side_effect=failure):
            with self.assertRaisesRegex(OSError, 'result barrier'): f.run.consume_phase2_result()
        raw = (f.root/PATH).read_bytes()
        altered = deepcopy(packet); altered['profiles'][0]['rounds_used'] = 0
        (f.root/PATH).write_bytes(canonical_json_bytes(altered))
        with self.assertRaisesRegex(ValueError, 'exact result replay'): f.run.phase2_consumption_status()
        with self.assertRaisesRegex(ValueError, 'exact result replay'): f.run.consume_phase2_result()
        (f.root/PATH).write_bytes(raw)

    def test_uncommitted_valid_response_and_missing_pin_refuse(self):
        f, client, _ = self.ready()
        publish = f.store.publish
        def before_result(token, path, value):
            if path == JOURNAL_PATH+'/result.json': raise OSError('before result')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=before_result):
            with self.assertRaises(OSError): f.run.run_phase2_review(client=client)
        self.assertEqual(f.run.phase2_review_status().status, 'valid_response')
        with self.assertRaisesRegex(ValueError, 'committed result'): f.run.consume_phase2_result()
        f.run.run_phase2_review(continuation=True)
        self.assertEqual(f.run.consume_phase2_result()['accepted_passes'], 1)
        self.assertEqual(client.calls, 1)
        with patch.object(self, 'start', side_effect=lambda **kw: client_tests.VerifiedPhase2ClientTests.start(self, **kw)):
            other, _, _ = self.ready()
        with self.assertRaisesRegex(ValueError, 'outside supported suite'): other.run.consume_phase2_result()


    def test_mirror_recovery_ends_call_and_changed_rubric_refuses(self):
        f, client, config = self.ready()
        f.run.run_phase2_review(client=client)
        (f.root/'spec.md').unlink()
        self.assertEqual(f.run.phase2_consumption_status().outcome, 'materialization_required')
        self.assertEqual(f.run.consume_phase2_result().outcome, 'materialization_recovered')
        self.assertFalse((f.root/PATH).exists())
        rubric = f.root/config['rubric']['artifact']['path']
        raw = rubric.read_bytes()
        rubric.write_bytes(raw+b'changed')
        before = self.files(f)
        with self.assertRaises(ValueError): f.run.consume_phase2_result()
        self.assertEqual(self.files(f), before)
        rubric.write_bytes(raw)
        self.assertEqual(f.run.consume_phase2_result()['accepted_passes'], 1)
        self.assertEqual(client.calls, 1)


if __name__ == '__main__': unittest.main()
