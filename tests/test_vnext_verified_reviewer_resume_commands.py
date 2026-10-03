"""Finite first/later Reviewer continuation and repair through Q1 commands."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_failure import STATE_FIELD
import test_vnext_verified_first_review_commands as first


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class ReviewerResumeCommandTests(unittest.TestCase):
    setUpClass = first.FirstReviewCommandTests.setUpClass
    setUp = first.FirstReviewCommandTests.setUp
    patch = first.FirstReviewCommandTests.patch
    qualify = first.FirstReviewCommandTests.qualify
    save_config = first.FirstReviewCommandTests.save_config
    clean = staticmethod(first.FirstReviewCommandTests.clean)
    invoke = first.FirstReviewCommandTests.invoke
    files = first.FirstReviewCommandTests.files
    stage_phase2 = first.FirstReviewCommandTests.stage_phase2
    ready = first.FirstReviewCommandTests.ready
    call = first.FirstReviewCommandTests.call
    entered = first.FirstReviewCommandTests.entered
    inspect_readonly = first.FirstReviewCommandTests.inspect_readonly

    def unchanged_inspection(self, *, recovery=None, continuation=None, calls):
        before = self.files()
        state = self.inspect_readonly()
        self.assertEqual(state['recovery'], recovery, state)
        self.assertEqual(state['continuation'], continuation, state)
        code, result = self.call('resume', '--dry-run'); self.assertEqual(code, 0, result)
        code, result = self.call('live-phase2'); self.assertEqual(code, 2, result)
        code, result = self.call('resume', '--continue'); self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before); self.assertEqual(self.phase2_reviewer.calls, calls)
        return state

    @staticmethod
    def timeout(client, packet): raise TimeoutError('fixture Reviewer timeout')

    def test_first_timeout_repairs_before_retry_and_lost_final_ack_does_not_repeat(self):
        self.entered()
        success = self.phase2_reviewer.callback
        self.phase2_reviewer.callback = self.timeout
        publish = LocalAuthorityStore.publish
        faults = []
        def interrupted(store, token, path, value):
            result = publish(store, token, path, value)
            if '/execution/failures/attempt-1/' in path and path.endswith('/failure.json'):
                faults.append(path); raise OSError('fixture interrupted Reviewer failure publication')
            return result
        with patch.object(LocalAuthorityStore, 'publish', interrupted):
            code, result = self.call('live-phase2')
        self.assertEqual(code, 2, result); self.assertEqual(len(faults), 1, result)
        state = self.unchanged_inspection(recovery='failure_publication', calls=1)
        code, result = self.call('resume'); self.assertEqual(code, 0, result)
        self.assertTrue(result['state_current'] and result['mirrors_current'], result)
        self.assertEqual(self.phase2_reviewer.calls, 1)
        state = self.unchanged_inspection(continuation='phase2_reviewer', calls=1)
        self.assertEqual(state['pass_number'], 1)
        request = state['request']; original = (self.root/request['path']).read_bytes()
        failure_state = json.loads((self.root/STATE_PATH).read_bytes())[STATE_FIELD]
        historical = {r['path']:(self.root/r['path']).read_bytes() for r in failure_state['history']}
        self.phase2_reviewer.callback = success
        materialize = LocalAuthorityStore.materialize
        def lost_ack(store, token, path, raw, **kwargs):
            result = materialize(store, token, path, raw, **kwargs)
            if path == STATE_PATH and json.loads(raw).get(STATE_FIELD, {}).get('active') is None:
                faults.append(path); raise OSError('fixture lost continuation state acknowledgement')
            return result
        with patch.object(LocalAuthorityStore, 'materialize', lost_ack):
            code, result = self.call('resume')
        self.assertEqual(code, 2, result); self.assertEqual(faults[-1], STATE_PATH, result)
        self.assertEqual(self.phase2_reviewer.calls, 2)
        state = self.inspect_readonly()
        self.assertEqual(state['gate'], 'result_consumption_required', state)
        self.assertIsNone(state['recovery']); self.assertIsNone(state['continuation'])
        self.assertFalse(state['review_evidence']['consumed'])
        before = self.files()
        code, result = self.call('resume'); self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before); self.assertEqual(self.phase2_reviewer.calls, 2)
        self.assertEqual((self.root/request['path']).read_bytes(), original)
        for path, raw in historical.items(): self.assertEqual((self.root/path).read_bytes(), raw)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(), self.head)

    def test_later_timeout_retry_exhausts_without_consumption_or_extra_allowance(self):
        self.entered()
        self.stage_phase2()  # Reuse the pinned inputs, with the clean scripted response.
        clean = self.phase2_reviewer.callback
        def response(client, packet):
            return clean(client, packet) if client.calls == 1 else self.timeout(client, packet)
        self.phase2_reviewer.callback = response
        code, result = self.call('live-phase2'); self.assertEqual(code, 2, result)
        self.assertEqual(self.phase2_reviewer.calls, 2)
        state = self.unchanged_inspection(recovery='failure_projection', calls=2)
        code, result = self.call('resume'); self.assertEqual(code, 0, result)
        self.assertTrue(result['state_current'] and result['mirrors_current'], result)
        state = self.unchanged_inspection(continuation='phase2_reviewer', calls=2)
        self.assertEqual(state['pass_number'], 2)
        request = state['request']; raw = (self.root/request['path']).read_bytes()
        code, result = self.call('resume'); self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'timeout')
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(self.phase2_reviewer.calls, 3)
        state = self.inspect_readonly()
        self.assertIsNone(state['recovery']); self.assertIsNone(state['continuation'])
        self.assertEqual(state['request_status'], 'attempts_exhausted')
        self.assertFalse(state['review_evidence']['consumed'])
        before = self.files()
        code, result = self.call('resume'); self.assertEqual(code, 2, result)
        code, result = self.call('live-phase2'); self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before); self.assertEqual(self.phase2_reviewer.calls, 3)
        self.assertEqual((self.root/request['path']).read_bytes(), raw)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(), self.head)

    def test_retained_valid_response_finishes_without_client_or_consumption(self):
        self.entered()
        publish = LocalAuthorityStore.publish
        faults = []
        def interrupted(store, token, path, value):
            if path.endswith('/execution/result.json'):
                faults.append(path); raise OSError('fixture interrupted result receipt')
            return publish(store, token, path, value)
        with patch.object(LocalAuthorityStore, 'publish', interrupted):
            code, result = self.call('live-phase2')
        self.assertEqual(code, 2, result); self.assertEqual(len(faults), 1, result)
        state = self.unchanged_inspection(continuation='phase2_reviewer', calls=1)
        self.assertEqual(state['request_status'], 'valid_response')
        def forbidden(client, packet): self.fail('retained response invoked Reviewer')
        self.phase2_reviewer.callback = forbidden
        code, result = self.call('resume'); self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'complete'); self.assertEqual(result['attempts'], 1)
        self.assertEqual(self.phase2_reviewer.calls, 1)
        state = self.inspect_readonly()
        self.assertEqual(state['gate'], 'result_consumption_required')
        self.assertFalse(state['review_evidence']['consumed'])
        before = self.files()
        code, result = self.call('resume'); self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before)


if __name__ == '__main__': unittest.main()
