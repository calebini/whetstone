"""Finite recovery selection includes exact pending evidence and preserves stops."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_commands import execute,resume
from whetstone.vnext_verified_command_state import candidate_state
import test_vnext_verified_report_selection as reports


class RecoveryBoundaryGuards(unittest.TestCase):
    def test_materialization_recovery_does_not_replay_scheduler_for_budget_metadata(self):
        from whetstone.vnext_verified_command_state import inspect_command,selected
        run=Mock();state=selected('materialization_required',recovery='materialization')
        with patch('whetstone.vnext_verified_command_state._inspect_command',return_value=state), \
             patch('whetstone.vnext_verified_phase1_budget.recovery_record',side_effect=AssertionError('scheduler replay')):
            self.assertEqual(inspect_command(run),state)
        run.store.read.assert_not_called();run._operator.assert_not_called()

    def test_budget_controls_reject_invalid_preview_amounts_and_combined_continuation(self):
        from whetstone.vnext_verified_cli import _controls
        for dry_run in (False,True):
            for amount in (0,-1,True,1.5):
                args=SimpleNamespace(command='resume',dry_run=dry_run,extend_review_budget=amount)
                with self.assertRaisesRegex(ValueError,'positive integer'):_controls(args,{},fresh=False)
            args=SimpleNamespace(command='resume',dry_run=dry_run,extend_review_budget=1)
            _controls(args,{},fresh=False)
            args.continue_run=True
            with self.assertRaisesRegex(ValueError,'cannot be combined'):_controls(args,{},fresh=False)

    def test_prepared_decision_identity_is_part_of_command_selection(self):
        creation=dict(candidate_id='parent',round_number=1,job_id='job')
        proof=Mock();proof.view.creations=[creation];proof.pointers=[]
        view=SimpleNamespace(prepared=True,decision=dict(decision_final=False))
        pending=dict(decision_ordinal=2,decided_at='first')
        with patch('whetstone.vnext_verified_semantics.VerifiedSemanticDecisionJournal') as journal:
            journal.return_value.paths.return_value=('directory','decision.json')
            journal.return_value._state.return_value=(view,None,None,pending)
            first=candidate_state(Mock(),proof)
            pending['decided_at']='changed'
            second=candidate_state(Mock(),proof)
        self.assertEqual(first['recovery'],'verification')
        self.assertEqual(first['candidate'],second['candidate'])
        self.assertNotEqual(first['pending_decision'],second['pending_decision'])
        canonical_json_bytes(first)

    def test_phase2_stopped_dispositions_never_become_generic_resume_or_live_work(self):
        select=reports.ReportSelectionTests().select
        for gate in ('oscillation_freeze_required','oscillation_halt_required','conflict_halt_required','declaration_closeout_required'):
            if gate=='declaration_closeout_required':
                state=select({},gate=gate,findings=dict(committed=True,packet=dict(blocking_reasons=['authority'])),blocked=dict(gate='blocked'))
            else:state=select({},gate=gate)
            run=Mock();args=SimpleNamespace(command='live-phase2',dry_run=False)
            with patch('whetstone.vnext_verified_commands.inspect_command',return_value=deepcopy(state)), \
                 patch('whetstone.vnext_verified_phase2_commands.inspect_command',return_value=deepcopy(state)), \
                 patch('whetstone.vnext_verified_phase2_commands.optional',return_value=b'entry'):
                self.assertEqual(execute(run,args,{},{}),state)
                with self.assertRaisesRegex(ValueError,'no supported recovery'):resume(run,args,{}, {},state)
            run.store.guard_invocation.assert_not_called()
            run.request.assert_not_called();run.verify.assert_not_called();run.run_phase2_review.assert_not_called()

    def test_pending_terminal_projection_preserves_terminal_identity_and_precedence(self):
        select=reports.ReportSelectionTests().select
        for terminal in ('HALTED_OSCILLATION','HALTED_CONFLICT','HALTED_CLIENT_TIMEOUT','TARGET_NOT_REACHED'):
            closeout=dict(committed=True,state_current=False,mirror_current=False,phase_complete=False,
                packet=dict(terminal_state=terminal))
            state=select(dict(signal=dict(mirrors_current=False)),gate='oscillation_freeze_required',closeout=closeout)
            self.assertEqual(state['recovery'],'closeout_projection')
            self.assertEqual(state['closeout']['packet']['terminal_state'],terminal)
