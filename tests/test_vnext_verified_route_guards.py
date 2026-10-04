"""Focused command success cannot become whole-phase acceptance."""
from copy import deepcopy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from whetstone.vnext_verified_cli import command_succeeded


class RouteOutcomeGuards(unittest.TestCase):
    def focused(self):
        return dict(gate='phase1_stopped', phase='phase_1', recovery=None, continuation=None,
                    operator=dict(accepted=False, state_current=True,
                                  terminal_report=dict(terminal_state='FOCUSED_PROFILE_STABLE')))

    def test_focused_stability_succeeds_only_for_focused_command(self):
        packet = self.focused()
        self.assertTrue(command_succeeded('live-focused-phase1', packet))
        for command in ('live-phase1', 'live-phase2', 'promote-phase2'):
            with self.subTest(command=command):
                self.assertFalse(command_succeeded(command, packet))
        self.assertFalse(packet['operator']['accepted'])

    def test_focused_residual_failure_or_pending_repair_cannot_report_success(self):
        for terminal in ('PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS', 'TARGET_NOT_REACHED',
                         'HALTED_CLIENT_TIMEOUT', 'HALTED_ARTIFACT_INVALID', None):
            packet = self.focused(); packet['operator']['terminal_report']['terminal_state'] = terminal
            self.assertFalse(command_succeeded('live-focused-phase1', packet))
        original = self.focused()
        for changes in (dict(gate='review'), dict(phase='phase_2'),
                        dict(recovery='phase1_projection'), dict(continuation='reviewer')):
            packet = deepcopy(original); packet.update(changes)
            self.assertFalse(command_succeeded('live-focused-phase1', packet))
        packet = self.focused(); packet['operator']['state_current'] = False
        self.assertFalse(command_succeeded('live-focused-phase1', packet))

    def test_ordinary_success_and_distinct_entry_completion_remain_separate(self):
        for gate in ('phase1_complete', 'phase2_complete'):
            self.assertTrue(command_succeeded('live-phase1' if gate == 'phase1_complete' else 'live-phase2', dict(gate=gate)))
        self.assertFalse(command_succeeded('promote-phase2', dict(gate='phase2_complete')))
        self.assertFalse(command_succeeded('promote-phase2', dict(committed=True, state_current=False)))
        self.assertTrue(command_succeeded('promote-phase2', dict(committed=True, state_current=True)))
        self.assertTrue(command_succeeded('live-phase2', dict(phase_complete=True)))


class VerticalMergeSelectionGuards(unittest.TestCase):
    def test_pending_actionable_and_noop_merges_bind_exact_commit_before_operator_work(self):
        from whetstone.vnext_verified_command_state import pending_vertical_merge
        proof = Mock(); proof.seed_values = dict(review=dict(review_mode='vertical'))
        for gate in ('finding_admission', 'merge_required'):
            packet = dict(round_number=3, source='original')
            state = SimpleNamespace(gate=gate, number=3, merges=[(packet, {}, True, False)])
            with patch('whetstone.vnext_verified_vertical_phase1.sequence', return_value=state):
                first = pending_vertical_merge(proof)
                self.assertEqual(first['gate'], 'merge_required')
                self.assertEqual(first['round_number'], 3)
                packet['source'] = 'changed'
                self.assertNotEqual(first['merge'], pending_vertical_merge(proof)['merge'])
                state.merges = [(packet, {}, True, True)]
                self.assertIsNone(pending_vertical_merge(proof))
        proof.seed_values['review']['review_mode'] = 'horizontal'
        with patch('whetstone.vnext_verified_vertical_phase1.sequence', side_effect=AssertionError('horizontal replay')):
            self.assertIsNone(pending_vertical_merge(proof))


class VerticalMergeFenceGuards(unittest.TestCase):
    def test_merge_selection_is_rechecked_under_fence_before_any_operator_or_client(self):
        import sys
        if sys.platform != 'darwin': self.skipTest('D8 requires macOS/APFS')
        from test_vnext_local_storage import LocalStorageTests
        from whetstone.vnext_verified_commands import phase1, SelectionChanged
        from whetstone.vnext_verified_run import VerifiedRun
        fixture = LocalStorageTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        for race in (False, True):
            run = Mock(spec=VerifiedRun); run.store = fixture.store; events = []
            run.state = dict(gate='merge_required', phase='phase_1', recovery=None, continuation=None,
                             merge=dict(path='rounds/round-3/vertical_merge.json', hash='a'*64))
            def consolidate():
                if race: run.state['merge']['hash'] = 'b'*64
                with run.store.locked(lambda read: events.append('owner')):
                    run.state = dict(gate='phase1_stopped', phase='phase_1', recovery=None, continuation=None)
            run.consolidate_phase1_review.side_effect = consolidate
            with patch('whetstone.vnext_verified_commands.inspect_command', side_effect=lambda r: deepcopy(r.state)), \
                 patch('whetstone.vnext_verified_commands._client', side_effect=AssertionError('merge called a client')):
                if race:
                    with self.assertRaises(SelectionChanged): phase1(run, SimpleNamespace(), {}, {})
                    self.assertEqual(events, [])
                else:
                    self.assertEqual(phase1(run, SimpleNamespace(), {}, {})['gate'], 'phase1_stopped')
                    self.assertEqual(events, ['owner'])
            run.admit_reviewed_round.assert_not_called()
