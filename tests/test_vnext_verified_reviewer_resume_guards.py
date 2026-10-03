"""Continuation may project only its own unconsumed Reviewer result."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import test_vnext_local_storage as storage
from whetstone.vnext_review_requests import ReviewStep
from whetstone.vnext_verified_commands import resume, SelectionChanged


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class ReviewerResumeGuardTests(unittest.TestCase):
    setUp = storage.LocalStorageTests.setUp
    open_store = storage.LocalStorageTests.open_store

    def scenario(self):
        request = dict(path='requests/first.json', hash='a'*64)
        result = ReviewStep('complete', 1, 'convergence_strict_check', 'req_fixture', 2,
            dict(request=request), {}, dict(classification='valid_review', attempt=2))
        before = dict(gate='pending_review', phase='phase_2', recovery=None,
            continuation='phase2_reviewer', pass_number=1, request=request,
            sequence=dict(current_pointer=dict(path='head', hash='b'*64)))
        after = dict(before, gate='failure_projection', recovery='failure_projection', continuation=None,
            review_evidence=dict(request=request, pass_number=1, request_id=result.request_id,
                attempts=2, last_outcome=result.last_outcome, receipt=result.receipt, consumed=False))
        run = SimpleNamespace(store=self.store, state=deepcopy(before), calls=[])
        def execute(**kwargs):
            self.assertTrue(kwargs['continuation'])
            with self.store.locked(lambda read: None) as token:
                run.calls.append('execute')
                self.store.publish(token, 'outcomes/result.json', result.receipt)
                run.state = deepcopy(after)
            return result
        def project():
            with self.store.locked(lambda read: None) as token:
                run.calls.append('project')
                self.store.publish(token, 'outcomes/state.json', result.receipt)
            return dict(state_current=True)
        run.run_phase2_review = execute
        run.reconcile_phase2_failure_state = project
        return run, before, result

    def invoke(self, run, state):
        with (patch('whetstone.vnext_verified_commands.inspect_command', side_effect=lambda run: deepcopy(run.state)),
              patch('whetstone.vnext_verified_commands.phase2_client', return_value=object())):
            return resume(run, state=state, args=SimpleNamespace(dry_run=False), config={}, review={})

    def test_continuation_projects_exact_result_and_returns_without_consumption(self):
        run, state, result = self.scenario()
        self.assertEqual(self.invoke(run, state), result)
        self.assertEqual(run.calls, ['execute', 'project'])

    def test_changed_result_refuses_before_projection(self):
        run, state, _ = self.scenario()
        execute = run.run_phase2_review
        def raced(**kwargs):
            result = execute(**kwargs)
            run.state['review_evidence']['receipt'] = dict(request='another outcome')
            return result
        run.run_phase2_review = raced
        with self.assertRaisesRegex(ValueError, 'Reviewer outcome changed'):
            self.invoke(run, state)
        self.assertEqual(run.calls, ['execute'])

    def test_peer_consumption_is_rechecked_inside_projection_fence(self):
        run, state, _ = self.scenario()
        project = run.reconcile_phase2_failure_state
        def raced():
            run.state['review_evidence']['consumed'] = True
            return project()
        run.reconcile_phase2_failure_state = raced
        with self.assertRaises(SelectionChanged): self.invoke(run, state)
        self.assertEqual(run.calls, ['execute'])

    def test_peer_advancement_to_another_role_refuses_before_projection(self):
        run, state, _ = self.scenario()
        execute = run.run_phase2_review
        def raced(**kwargs):
            result = execute(**kwargs)
            run.state = dict(gate='proposal', phase='phase_2', recovery=None,
                             continuation='unsupported_phase2_continuation')
            return result
        run.run_phase2_review = raced
        with self.assertRaisesRegex(ValueError, 'Reviewer outcome changed'):
            self.invoke(run, state)
        self.assertEqual(run.calls, ['execute'])


if __name__ == '__main__': unittest.main()
