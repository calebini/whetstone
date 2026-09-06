"""End-to-end Phase 1 continuation journeys, using scripted clients only."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

import test_preservation_runtime as runtime_fixtures
from whetstone.hashing import draft_hash
from whetstone.live import LiveRoundRunner
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.scheduler import focused_phase_1_scheduler
from whetstone.preservation_runtime import BridgeHalt, acceptance_service, guard_consumer, readback
from whetstone.preservation_contracts import BridgeContractError, decode_json
from whetstone.preservation_inventory import build_inventory
from whetstone.preservation_continuation import continuation_context
from whetstone.resume import resume_halted_run, plan_resume_halted_run
from whetstone.status import read_status


class ScriptedReviewer:
    def __init__(self, root, template, events):
        self.root, self.template, self.events = root, template, list(events)
        self.calls, self.prompts = 0, []

    def review(self, prompt):
        self.calls += 1; self.prompts.append(prompt)
        event = self.events.pop(0)
        if isinstance(event, Exception):
            raise event
        number, profile, findings = event
        result = deepcopy(self.template)
        result.update(round_number=number, profile=profile, draft_hash=draft_hash((self.root/'spec.md').read_bytes().decode()), feedback=deepcopy(findings))
        return result


class ContinuationTests(unittest.TestCase):
    setUp = runtime_fixtures.RuntimeTests.setUp
    setup_run = runtime_fixtures.RuntimeTests.setup_run
    snapshot = runtime_fixtures.RuntimeTests.snapshot
    approve = runtime_fixtures.RuntimeTests.approve

    def start(self, *, focused=False, serious=False, soft=False, budgets=None):
        self.setup_run(serious=serious)
        self.config = replace(self.config, review_budget_exhaustion_policy='soft' if soft else 'hard', review_profile_budgets=budgets or {'structural_integrity':2, 'determinism':1, 'operability':1})
        options = {}
        if focused:
            options = dict(scheduler_factory=lambda _: focused_phase_1_scheduler('structural_integrity',round_budget=1),
                           state_review_profile_budgets={'structural_integrity':1},run_mode='focused_phase_1',
                           completion_terminal_state='FOCUSED_PROFILE_STABLE',completion_ready_for_phase_2=False)
        result = LivePhase1Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor,**options).run()
        self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        self.service=acceptance_service(self.root)
        self.assertEqual(self.approve().outcome,'accepted')
        self.assertEqual(self.editor.calls,1)

    def authorize_current_base(self, *, prefix="current", finding_sources=None):
        base=(self.root/'spec.md').read_bytes()
        base_ref=self.p.save(f'{prefix}-base.md',base)
        inventory=build_inventory(base,path=base_ref['path'])
        inventory_ref=self.p.save(f'{prefix}-inventory.json',inventory)
        surface={**self.p.surface,'base_draft':base_ref,'inventory':inventory_ref,'finding_sources':finding_sources or [],
                 'allowed_sections':[s['section_id'] for s in inventory['sections']],
                 'allowed_unit_ids':[u['unit_id'] for u in inventory['units']]}
        surface_ref=self.p.save(f'{prefix}-surface.json',surface)
        self.config=replace(self.config,preservation_bridge=replace(self.config.preservation_bridge,allowed_change_surface=surface_ref,predecessor_report=None))

    def scripted(self, events):
        return ScriptedReviewer(self.root,self.p.feedback,events)

    def test_local_acceptance_then_continue_verifies_and_finishes_without_replay(self):
        self.start(); self.authorize_current_base()
        before=self.snapshot();plan=plan_resume_halted_run(self.root,self.config,continue_run=True)
        self.assertEqual(plan.next_round_number,2);self.assertEqual(before,self.snapshot())
        from whetstone.cli import main
        from contextlib import redirect_stdout
        import io, json, shlex
        command=read_status(root=self.root,config=self.config)['resume']['command']
        output=io.StringIO()
        with patch('whetstone.cli.load_config',return_value=self.config),redirect_stdout(output):
            self.assertEqual(main(shlex.split(command)[1:]+['--dry-run']),0)
        self.assertTrue(json.loads(output.getvalue())['continue'])
        self.assertEqual(before,self.snapshot())
        reviewer=self.scripted([(2,'structural_integrity',[]),(3,'determinism',[]),(4,'operability',[])])
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'PHASE_1_STABLE');self.assertTrue(result.ready_for_phase_2)
        self.assertEqual(result.round_number,4);self.assertEqual(reviewer.calls,3);self.assertEqual(self.editor.calls,1)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),4)
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'),4)
        guard_consumer(self.root,self.config)
        self.assertTrue(read_status(root=self.root,config=self.config)['ready_for_phase_2'])
        before=self.snapshot()
        again=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertFalse(again.resumed);self.assertEqual(before,self.snapshot())

    def test_focused_exhaustion_gets_fresh_review_only_closeout(self):
        self.start(focused=True,serious=True)
        # No new edit authorization is needed to observe the already accepted bytes.
        reviewer=self.scripted([(2,'structural_integrity',[])])
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'FOCUSED_PROFILE_STABLE');self.assertFalse(result.ready_for_phase_2)
        self.assertEqual(result.round_number,2);self.assertEqual(reviewer.calls,1);self.assertEqual(self.editor.calls,1)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),1)
        self.assertTrue((self.root/'rounds/round-2/preservation/review_complete.json').exists())
        context=continuation_context(self.root,self.config)
        self.assertTrue(context['scheduler'].phase_complete(accepted_draft=True))
        self.assertEqual(context['scheduler'].status()['profiles'][0]['rounds_used'],2)

    def test_closeout_serious_findings_prevent_stability(self):
        self.start(focused=True,serious=True)
        reviewer=self.scripted([(2,'structural_integrity',self.p.feedback['feedback'])])
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'TARGET_NOT_REACHED');self.assertFalse(result.ready_for_phase_2)
        self.assertEqual(self.editor.calls,1)
        self.assertTrue(continuation_context(self.root,self.config)['last_unresolved'])

    def test_new_edit_round_requires_current_base_approval_before_any_call(self):
        self.start(); before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'current base'):
            resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(before,self.snapshot());self.assertEqual(self.editor.calls,1)

    def test_pending_or_rejected_proposal_cannot_continue(self):
        self.setup_run()
        with self.assertRaises(BridgeHalt):self.runner.run_round(round_number=1,profile='structural_integrity',apply=True)
        before=self.snapshot()
        for continuation in (False,True):
            with self.assertRaises(BridgeContractError):resume_halted_run(self.root,self.config,continue_run=continuation,editor_client=self.editor)
        self.assertEqual(before,self.snapshot());self.assertEqual(self.editor.calls,1)

    def test_reviewer_timeout_resumes_same_input_and_round_then_pauses_for_acceptance(self):
        self.setup_run()
        reviewer=self.scripted([TimeoutError('scripted timeout'),(1,'structural_integrity',self.p.feedback['feedback'])])
        result=LivePhase1Runner(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor).run()
        self.assertEqual(result.terminal_state,'HALTED_CLIENT_TIMEOUT');self.assertEqual(self.editor.calls,0)
        old=(self.root/'rounds/round-1/preservation/reviewer-attempt-1/result.json').read_bytes()
        before=self.snapshot();plan=plan_resume_halted_run(self.root,self.config)
        self.assertEqual(plan.client_role,'reviewer');self.assertEqual(plan.next_attempt_number,2);self.assertEqual(before,self.snapshot())
        result=resume_halted_run(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor,continue_run=True)
        self.assertEqual(result.terminal_state,'PAUSED_DECISION');self.assertEqual(result.round_number,1)
        self.assertEqual(reviewer.prompts[0],reviewer.prompts[1]);self.assertEqual(self.editor.calls,1)
        self.assertEqual((self.root/'rounds/round-1/preservation/reviewer-attempt-1/result.json').read_bytes(),old)

    def test_closeout_timeout_resumes_without_repeating_the_editor(self):
        self.start(focused=True)
        reviewer=self.scripted([TimeoutError('closeout timeout'),(2,'structural_integrity',[])])
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'HALTED_CLIENT_TIMEOUT')
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'FOCUSED_PROFILE_STABLE');self.assertEqual(result.round_number,2)
        self.assertEqual(self.editor.calls,1);self.assertEqual(reviewer.calls,2)

    def test_completed_feedback_is_reused_after_canonical_write_failure(self):
        self.setup_run(noop=True)
        from whetstone.artifacts import ArtifactStore
        original=ArtifactStore.write_round_json
        def write(store, number, filename, packet, **kwargs):
            if filename=='reviewer_feedback.json':raise OSError('scripted canonical write failure')
            return original(store,number,filename,packet,**kwargs)
        with patch.object(ArtifactStore,'write_round_json',new=write):
            with self.assertRaises(OSError):self.runner.run_round(round_number=1,profile='structural_integrity',apply=True)
        self.assertEqual(self.reviewer.calls,1)
        result=resume_halted_run(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertIsNone(result.terminal_state);self.assertEqual(self.reviewer.calls,1);self.assertEqual(self.editor.calls,0)
        self.assertEqual(len(list(self.root.glob('rounds/round-1/preservation/reviewer-attempt-*'))),1)

    def test_changed_review_inputs_refuse_retry(self):
        self.setup_run()
        reviewer=self.scripted([TimeoutError('scripted timeout')])
        LivePhase1Runner(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor).run()
        (self.root/'rounds/round-1/preservation/reviewer-attempt-1/prompt.txt').write_text('replacement prompt')
        with self.assertRaisesRegex(BridgeContractError,'hash mismatch'):
            resume_halted_run(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(reviewer.calls,1);self.assertEqual(self.editor.calls,0)

    def test_changed_completion_mirror_blocks_status_and_continuation(self):
        self.start(focused=True)
        reviewer=self.scripted([(2,'structural_integrity',[])])
        resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        (self.root/'rounds/round-2/reviewer_feedback.json').write_text('{}')
        before=self.snapshot()
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)
        with self.assertRaises(BridgeContractError):resume_halted_run(self.root,self.config,continue_run=True)
        status=read_status(root=self.root,config=self.config)
        self.assertEqual(status['preservation_bridge']['pending_outcome'],'technical_failure')
        self.assertEqual(before,self.snapshot())

    def test_changed_budget_or_frozen_config_cannot_change_continuation(self):
        self.start(focused=True)
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'settings'):
            resume_halted_run(self.root,replace(self.config,review_budget_exhaustion_policy='soft'),continue_run=True)
        self.assertEqual(before,self.snapshot())
        path=self.root/'rounds/run_state.json';state=decode_json(path.read_bytes());state['review_profile_budgets']={'structural_integrity':99}
        from whetstone.preservation_proposals import json_bytes
        path.write_bytes(json_bytes(state))
        with self.assertRaisesRegex(BridgeContractError,'budget'):
            resume_halted_run(self.root,self.config,continue_run=True)

    def test_closeout_receipt_write_failure_recovers_without_repeating_review(self):
        self.start(focused=True)
        reviewer=self.scripted([(2,'structural_integrity',[])])
        from whetstone.preservation_proposals import ProposalStore
        original=ProposalStore._write
        def write(store, path, data):
            if path.endswith('/review_complete.json'):raise OSError('scripted completion failure')
            return original(store,path,data)
        with patch.object(ProposalStore,'_write',new=write):
            with self.assertRaises(OSError):
                resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'FOCUSED_PROFILE_STABLE');self.assertEqual(reviewer.calls,1)
        self.assertEqual(self.editor.calls,1)
        self.assertEqual(continuation_context(self.root,self.config)['scheduler'].status()['profiles'][0]['rounds_used'],2)

    def test_exhausted_closeout_does_not_repeat_review(self):
        self.start(focused=True,serious=True)
        reviewer=self.scripted([(2,'structural_integrity',self.p.feedback['feedback'])])
        resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        before=self.snapshot()
        self.assertFalse(plan_resume_halted_run(self.root,self.config,continue_run=True).resumable)
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'TARGET_NOT_REACHED');self.assertFalse(result.resumed)
        self.assertEqual(before,self.snapshot());self.assertEqual(reviewer.calls,1)

    def test_soft_budget_still_gets_verification_closeout(self):
        self.start(focused=True,soft=True)
        reviewer=self.scripted([(2,'structural_integrity',[])])
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'FOCUSED_PROFILE_STABLE');self.assertEqual(reviewer.calls,1)

    def test_corrupt_scheduler_cannot_preserve_ready_claim(self):
        self.setup_run(noop=True)
        self.config=replace(self.config,review_profile_budgets={'structural_integrity':1,'determinism':1,'operability':1})
        reviewer=self.scripted([(1,'structural_integrity',[]),(2,'determinism',[]),(3,'operability',[])])
        result=LivePhase1Runner(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor).run()
        self.assertTrue(result.ready_for_phase_2)
        path=self.root/'rounds/run_state.json';state=decode_json(path.read_bytes());state['review_round_budget']=99
        from whetstone.preservation_proposals import json_bytes
        path.write_bytes(json_bytes(state))
        before=self.snapshot();status=read_status(root=self.root,config=self.config)
        self.assertFalse(status['ready_for_phase_2']);self.assertFalse(status['resumable'])
        self.assertNotEqual(status['next_action'],'none');self.assertEqual(before,self.snapshot())

    def test_changed_timeout_cannot_retry(self):
        self.setup_run()
        reviewer=self.scripted([TimeoutError('scripted timeout')])
        LivePhase1Runner(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor,timeout_seconds=5).run()
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'timeout changed'):
            resume_halted_run(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor,timeout_seconds=6)
        self.assertEqual(before,self.snapshot());self.assertEqual(reviewer.calls,1)

    def test_deterministic_reviewer_failure_is_not_retryable(self):
        self.setup_run()
        reviewer=self.scripted([ValueError('invalid scripted artifact')])
        result=LivePhase1Runner(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor).run()
        self.assertEqual(result.terminal_state,'HALTED_ARTIFACT_INVALID')
        before=self.snapshot()
        with self.assertRaises(BridgeContractError):
            resume_halted_run(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(before,self.snapshot());self.assertEqual(reviewer.calls,1);self.assertEqual(self.editor.calls,0)

    def test_unscheduled_review_only_profile_is_refused_without_writes(self):
        self.start(focused=True)
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'scheduler'):
            LiveRoundRunner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run_review_only_round(
                round_number=2,profile='determinism',phase='phase_1')
        self.assertEqual(before,self.snapshot());self.assertEqual(self.reviewer.calls,1)

    def test_interrupted_multi_profile_closeout_keeps_prior_serious_findings(self):
        self.start(serious=True,budgets={'structural_integrity':1,'determinism':1,'operability':1})
        from whetstone.preservation_proposals import json_bytes
        base=(self.root/'spec.md').read_text()
        feedback={**self.p.feedback,'round_number':2,'profile':'determinism','draft_hash':draft_hash(base)}
        feedback_ref=self.p.save('second-feedback.json',feedback)
        self.authorize_current_base(finding_sources=[{'artifact':feedback_ref,'feedback_ids':['fb-1']}])
        summary=decode_json(self.editor.response)
        revised=self.p.raw.decode() if getattr(self,'cycle_revision',False) else base.replace('30 seconds or longer', 'a minimum of 30 seconds')
        summary.update(round_number=2,draft_before_hash=draft_hash(base),draft_after_hash=draft_hash(revised),draft_after_content=revised)
        self.editor.response=json_bytes(summary)
        reviewer=self.scripted([(2,'determinism',self.p.feedback['feedback']),(3,'operability',[]),
                                (4,'structural_integrity',self.p.feedback['feedback']),TimeoutError('second closeout'),
                                (5,'determinism',[])])
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'PAUSED_DECISION');self.assertEqual(result.round_number,2)
        from whetstone.preservation_review import adopt_effect
        effect=adopt_effect(self.service,proposal_ref=readback(self.root,self.config)['latest_proposal'],
            surface_ref=self.config.preservation_bridge.allowed_change_surface,output='second-effect.json',kind='attest_equivalence',
            base_lines=[9],output_lines=[9],disposition='reworded_equivalent',change_types=['clarify'],finding_ids=['fb-1'],
            effect='Same retry requirement.',rationale='Explicit scripted second clarification.',operator='fixture-operator',approve=True)
        request=self.service.prepare_request(proposal_ref=readback(self.root,self.config)['latest_proposal'],
                                            evidence_refs=[effect],output='second-request.json')
        self.assertEqual(self.service.accept(request).outcome,'accepted')
        self.authorize_current_base(prefix='third')
        if getattr(self,'cycle_revision',False):
            before=self.snapshot()
            with self.assertRaisesRegex(BridgeContractError,'oscillation'):
                resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
            self.assertEqual(before,self.snapshot());self.assertEqual(reviewer.calls,1)
            return
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'HALTED_CLIENT_TIMEOUT');self.assertEqual(result.round_number,5)
        receipt=(self.root/'rounds/round-4/preservation/review_complete.json').read_bytes()
        result=resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'TARGET_NOT_REACHED');self.assertEqual(result.round_number,5)
        self.assertEqual(reviewer.calls,5);self.assertEqual(self.editor.calls,2)
        self.assertEqual((self.root/'rounds/round-4/preservation/review_complete.json').read_bytes(),receipt)
        context=continuation_context(self.root,self.config)
        self.assertTrue(context['review_issues']);self.assertEqual(context['closeout_profiles'],[])
        self.assertEqual([p['rounds_used'] for p in context['scheduler'].status()['profiles']],[2,2,1])

    def test_local_acceptance_cannot_bypass_hard_oscillation_guard(self):
        self.cycle_revision=True
        self.test_interrupted_multi_profile_closeout_keeps_prior_serious_findings()


if __name__=='__main__':unittest.main()
