"""First-review preparation, interruption and selection races through Q1 commands."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_run import open_verified_run
from whetstone.vnext_verified_command_state import inspect_command
from whetstone.vnext_verified_commands import SelectionChanged
from whetstone.vnext_verified_phase2_review import INPUT_PATH, REQUEST_PATH
import test_vnext_verified_reviewer_handoff as handoff


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class FirstReviewCommandTests(unittest.TestCase):
    setUpClass = handoff.ReviewerHandoffTests.setUpClass
    setUp = handoff.ReviewerHandoffTests.setUp
    patch = handoff.ReviewerHandoffTests.patch
    qualify = handoff.ReviewerHandoffTests.qualify
    save_config = handoff.ReviewerHandoffTests.save_config
    clean = staticmethod(handoff.ReviewerHandoffTests.clean)
    invoke = handoff.ReviewerHandoffTests.invoke
    files = handoff.ReviewerHandoffTests.files
    stage_phase2 = handoff.ReviewerHandoffTests.stage_phase2
    ready = handoff.ReviewerHandoffTests.ready

    def call(self, command, *args):
        print('  command: '+command+' '+' '.join(args), file=sys.stderr, flush=True)
        code, result = self.invoke(command, *args)
        print('  result: '+str(code)+' '+str(result.get('gate', result.get('reason'))),
              file=sys.stderr, flush=True)
        return code, result

    def entered(self):
        self.ready(effect='weaken')
        self.patch('whetstone.live_phase2.LivePhase2Runner', side_effect=AssertionError('legacy executor'))
        code, result = self.call('promote-phase2'); self.assertEqual(code, 0, result)
        self.head = (self.root/'rounds/current_verified.json').read_bytes()
        self.entry = (self.root/'rounds/phase2/entry.json').read_bytes()

    def inspect_readonly(self):
        before = self.files()
        with patch.object(LocalAuthorityStore, 'acquire', side_effect=AssertionError('status took writer fence')):
            code, state = self.call('status', '--format', 'json')
        self.assertEqual(code, 0, state); self.assertEqual(self.files(), before)
        return state

    def test_partial_preparation_and_committed_request_reentry_invoke_only_once(self):
        self.entered()
        state = self.inspect_readonly()
        self.assertEqual(state['gate'], 'first_review_binding')
        self.assertFalse(state['declaration']['committed'])
        asset = state['declaration']['packet']['rubric_manifest']['path']
        publish = LocalAuthorityStore.publish
        # Lose acknowledgements after an asset, request inputs and request commit.
        # None is an interrupted invocation or a grant of technical continuation.
        for path in (asset, INPUT_PATH, REQUEST_PATH):
            faults = []
            def interrupted(store, token, target, value):
                result = publish(store, token, target, value)
                if target == path:
                    faults.append(target)
                    raise OSError('fixture interrupted first-review preparation')
                return result
            with patch.object(LocalAuthorityStore, 'publish', interrupted):
                code, result = self.call('live-phase2')
            self.assertEqual(code, 2, result); self.assertEqual(faults, [path], result)
            self.assertEqual(self.phase2_reviewer.calls, 0)
            state = self.inspect_readonly()
            self.assertIsNone(state['recovery']); self.assertIsNone(state['continuation'])
            if path == REQUEST_PATH:
                self.assertEqual(state['gate'], 'pending_review')
                self.assertEqual(state['request_status'], 'not_started')
            else:
                self.assertEqual(state['gate'], 'first_review_binding')
                self.assertEqual(state['declaration']['committed'], path == INPUT_PATH)
                if path == INPUT_PATH:
                    self.assertEqual([r['path'] for r in state['preparation']], [INPUT_PATH])
            before = self.files()
            code, result = self.call('resume', '--dry-run'); self.assertEqual(code, 2, result)
            code, result = self.call('resume'); self.assertEqual(code, 2, result)
            self.assertEqual(self.files(), before)
        request = (self.root/REQUEST_PATH).read_bytes()
        code, result = self.call('live-phase2'); self.assertEqual(code, 2, result)
        self.assertEqual(result['gate'], 'operator_or_advice_required', result)
        self.assertEqual(self.phase2_reviewer.calls, 1)
        before = self.files()
        code, result = self.call('live-phase2'); self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before); self.assertEqual(self.phase2_reviewer.calls, 1)
        self.assertEqual((self.root/REQUEST_PATH).read_bytes(), request)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(), self.head)
        self.assertEqual((self.root/'rounds/phase2/entry.json').read_bytes(), self.entry)

    def test_peer_advancement_at_each_first_review_fence_stops_stale_command(self):
        self.entered()
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_commands import execute_phase2
        args = SimpleNamespace()
        with open_verified_run(self.root) as run, open_verified_run(self.root) as peer:
            review = json.loads(run.store.read(run._record['review_configuration']['path']))
            actions = (
                peer.prepare_phase2_declaration,
                lambda: peer.bind_phase2_review(self.phase2_reviewer.transport_binding),
                lambda: peer.run_phase2_review(client=self.phase2_reviewer),
            )
            for index, action in enumerate(actions):
                selected = inspect_command(run)
                self.assertEqual(selected['gate'], 'pending_review' if index == 2 else 'first_review_binding')
                acquire = run.store.acquire
                peer_files = []
                def raced(validate):
                    action()
                    peer_files.append(self.files())
                    return acquire(validate)
                with patch.object(run.store, 'acquire', side_effect=raced):
                    with self.assertRaises(SelectionChanged):
                        execute_phase2(run, args, self.config, review)
                self.assertEqual(len(peer_files), 1)
                self.assertEqual(self.files(), peer_files[0])
                self.assertEqual(self.phase2_reviewer.calls, int(index == 2))
        state = self.inspect_readonly()
        self.assertEqual(state['gate'], 'result_consumption_required')
        code, result = self.call('live-phase2'); self.assertEqual(code, 2, result)
        self.assertEqual(result['gate'], 'operator_or_advice_required', result)
        self.assertEqual(self.phase2_reviewer.calls, 1)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(), self.head)


if __name__ == '__main__': unittest.main()
