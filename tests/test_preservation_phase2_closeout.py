"""Bounded closeout on a real accepted Phase 2 lineage; scripted clients only."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_preservation_maintenance as maintenance
import test_preservation_continuation as continuation
from test_live_phase2 import ScriptedPhase2ReviewerClient
from whetstone.hashing import draft_hash
from whetstone.live import LiveRoundRunner
from whetstone.live_phase2 import LivePhase2Runner
from whetstone.preservation_contracts import BridgeContractError, decode_json
from whetstone.preservation_maintenance import enter_phase2
from whetstone.preservation_proposals import json_bytes, ProposalStore
from whetstone.preservation_review import adopt_effect
from whetstone.preservation_runtime import BridgeHalt, state_packet, readback, guard_consumer
from whetstone.scheduler import profile_names_for_phase
from whetstone.rubrics import write_rubric_manifest


class CloseoutTests(unittest.TestCase):
    setUp = maintenance.MaintenanceTests.setUp
    setup_run = maintenance.MaintenanceTests.setup_run
    snapshot = maintenance.MaintenanceTests.snapshot
    stable = maintenance.MaintenanceTests.stable
    authorize_current_base = continuation.ContinuationTests.authorize_current_base

    def budget_stop(self):
        self.stable();enter_phase2(self.root,self.config)
        self.profiles = profile_names_for_phase(self.config.review_profile_set,'phase_2')
        start = self.handoff['current_round']+1
        for index, profile in enumerate(self.profiles[:-1]):
            number = start+index
            self.reviewer.events = [(number,profile,[])]
            LiveRoundRunner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run_round(
                round_number=number,profile=profile,phase='phase_2',apply=True)
        number, profile = start+len(self.profiles)-1, self.profiles[-1]
        base = (self.root/'spec.md').read_text()
        feedback = ScriptedPhase2ReviewerClient(self.root,['major']).review(f'Review profile: {profile}\n- round_number: {number}\n')
        self.finding = finding = feedback['feedback'][0]
        ref = self.p.save('closeout-finding.json',feedback)
        self.authorize_current_base(finding_sources=[{'artifact':ref,'feedback_ids':[finding['feedback_id']]}])
        revised = base.replace('at least 30 seconds','30 seconds or longer')
        summary = decode_json(self.editor.response)
        summary.update(round_number=number,draft_before_hash=draft_hash(base),draft_after_hash=draft_hash(revised),
            draft_after_content=revised,resolved_issue_ids=[finding['issue_id']])
        self.editor.response = json_bytes(summary)
        self.reviewer = continuation.ScriptedReviewer(self.root,feedback,[(number,profile,[finding])])
        with self.assertRaises(BridgeHalt):
            LiveRoundRunner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run_round(
                round_number=number,profile=profile,phase='phase_2',apply=True)
        proposal = readback(self.root,self.config)['latest_proposal']
        effect = adopt_effect(self.service,proposal_ref=proposal,surface_ref=self.config.preservation_bridge.allowed_change_surface,
            output='closeout-effect.json',kind='attest_equivalence',base_lines=[9],output_lines=[9],disposition='reworded_equivalent',
            change_types=['clarify'],finding_ids=[finding['feedback_id']],effect='Same retry requirement.',
            rationale='Explicit fixture approval.',operator='fixture-operator',approve=True)
        request = self.service.prepare_request(proposal_ref=proposal,evidence_refs=[effect],output='closeout-request.json')
        self.assertEqual(self.service.accept(request).outcome,'accepted')
        # Reproduce the ordinary orchestrator's budget-stop publication after the
        # accepted final round. Generic Phase 2 resume is deliberately unsupported.
        runner = LivePhase2Runner(self.root,self.config)
        runner.phase_1_rounds_completed = self.handoff['current_round']
        runner.rubric_manifest = write_rubric_manifest(self.config)
        current = draft_hash((self.root/'spec.md').read_bytes().decode())
        runner._write_failure_report(round_number=number,unresolved_issues=[],unresolved_rubric_gaps=[],
            last_accepted_draft_hash=current,declaration_path=None,terminal_state='TARGET_NOT_REACHED',
            exit_reason='Phase 2 profile round budgets exhausted before convergence')
        runner._write_state(current_round=number,active_profile=None,current_draft_hash=current,
            last_accepted_draft_hash=current,terminal_state='TARGET_NOT_REACHED',declaration_path=None)
        self.start = number+1
        self.profiles = list(dict.fromkeys(self.profiles))
        self.reviewer.events = [(self.start+i,p,[]) for i,p in enumerate(self.profiles)]
        self.calls = (self.reviewer.calls,self.editor.calls)

    def closeout(self):
        return LivePhase2Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run(closeout_existing=True)

    def test_closeout_converges_without_editor_and_repeats_without_writes(self):
        self.budget_stop()
        from whetstone.status import read_status
        before = self.snapshot()
        self.assertIn('--closeout-existing',read_status(root=self.root,config=self.config)['resume']['command'])
        self.assertEqual(before,self.snapshot())
        result = self.closeout()
        self.assertEqual(result.terminal_state,'CONVERGED')
        self.assertEqual(result.round_number,self.start+len(self.profiles)-1)
        self.assertEqual(self.editor.calls,self.calls[1])
        self.assertEqual(self.reviewer.calls,self.calls[0]+len(self.profiles))
        self.assertEqual(state_packet(self.root)['phase_2_rounds_completed'],5)
        guard_consumer(self.root,self.config)
        before = self.snapshot();self.assertEqual(self.closeout().terminal_state,'CONVERGED')
        self.assertEqual(before,self.snapshot())

    def test_timeout_retries_only_through_same_closeout_command(self):
        from whetstone.resume import resume_halted_run
        self.budget_stop();self.reviewer.events.insert(1,TimeoutError('closeout timeout'))
        self.assertEqual(self.closeout().terminal_state,'HALTED_CLIENT_TIMEOUT')
        before = self.snapshot()
        with self.assertRaises(BridgeContractError):resume_halted_run(self.root,self.config,continue_run=True)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.closeout().terminal_state,'CONVERGED')
        self.assertEqual(self.reviewer.prompts[2],self.reviewer.prompts[3])
        self.assertEqual(self.editor.calls,self.calls[1])

    def test_completed_feedback_survives_receipt_write_failure(self):
        self.budget_stop()
        original = ProposalStore._write
        def fail(store,path,data):
            if path == f'rounds/round-{self.start}/preservation/review_complete.json':
                raise OSError('closeout receipt')
            return original(store,path,data)
        with patch.object(ProposalStore,'_write',new=fail):
            with self.assertRaises(OSError):self.closeout()
        self.assertEqual(self.closeout().terminal_state,'CONVERGED')
        self.assertEqual(self.reviewer.calls,self.calls[0]+len(self.profiles))

    def test_serious_closeout_stops_and_cannot_be_washed_away_by_repeating(self):
        self.budget_stop();self.reviewer.events[0] = (self.start,self.profiles[0],[self.finding])
        self.assertEqual(self.closeout().terminal_state,'TARGET_NOT_REACHED')
        self.assertEqual(self.reviewer.calls,self.calls[0]+1)
        before = self.snapshot();self.assertEqual(self.closeout().terminal_state,'TARGET_NOT_REACHED')
        self.assertEqual(before,self.snapshot())
        self.assertFalse(self.config.declaration_path.exists())
        completion = self.root/'rounds/preservation/phase2-closeout/completed.json'
        packet = decode_json(completion.read_bytes());packet['terminal_state'] = 'CONVERGED'
        completion.write_bytes(json_bytes(packet));before = self.snapshot()
        with self.assertRaises(BridgeContractError):self.closeout()
        self.assertEqual(before,self.snapshot())

    def test_changed_settings_or_receipt_blocks_bounded_recovery(self):
        self.budget_stop();self.reviewer.events.insert(1,TimeoutError('closeout timeout'))
        self.assertEqual(self.closeout().terminal_state,'HALTED_CLIENT_TIMEOUT')
        self.config = replace(self.config,timeouts=replace(self.config.timeouts,reviewer_seconds=999))
        before = self.snapshot()
        with self.assertRaises(BridgeContractError):self.closeout()
        self.assertEqual(before,self.snapshot())

    def test_completion_write_failure_replays_committed_reviews_without_calls(self):
        self.budget_stop()
        original = ProposalStore._write
        def fail(store,path,data):
            if path == 'rounds/preservation/phase2-closeout/completed.json':raise OSError('closeout completion')
            return original(store,path,data)
        with patch.object(ProposalStore,'_write',new=fail):
            with self.assertRaises(OSError):self.closeout()
        self.assertEqual(state_packet(self.root)['terminal_state'],'CONVERGED')
        calls = self.reviewer.calls
        self.assertEqual(self.closeout().terminal_state,'CONVERGED')
        self.assertEqual(self.reviewer.calls,calls)
