"""Vertical continuation and interrupted-closeout journeys with scripted clients."""
from dataclasses import replace
import unittest
from unittest.mock import patch
import test_preservation_vertical as fixtures
import test_preservation_continuation as horizontal_fixtures
from whetstone.preservation_runtime import acceptance_service, guard_consumer
from whetstone.preservation_contracts import BridgeContractError, decode_json
from whetstone.preservation_proposals import json_bytes
from whetstone.preservation_vertical import context
from whetstone.resume import resume_halted_run, plan_resume_halted_run
from whetstone.status import read_status


class RecoveryTests(unittest.TestCase):
    setUp=fixtures.VerticalTests.setUp
    setup_run=fixtures.VerticalTests.setup_run
    snapshot=fixtures.VerticalTests.snapshot
    approve=fixtures.VerticalTests.approve
    authorize_current_base=horizontal_fixtures.ContinuationTests.authorize_current_base

    def start(self, *, budgets=None, crlf=False):
        self.setup_run(serious=True)
        if crlf:
            from whetstone.hashing import draft_hash
            from whetstone.preservation_inventory import build_inventory
            self.p.raw=self.p.raw.replace(b'\n',b'\r\n');self.p.after=self.p.after.replace(b'\n',b'\r\n')
            (self.root/'spec.md').write_bytes(self.p.raw)
            base_ref=self.p.save('crlf-seed.md',self.p.raw)
            inventory=build_inventory(self.p.raw,path=base_ref['path'])
            self.p.feedback['draft_hash']=draft_hash(self.p.raw.decode())
            self.p.feedback_ref=self.p.save('feedback.json',self.p.feedback)
            self.p.surface={**self.p.surface,'base_draft':base_ref,'inventory':self.p.save('crlf-inventory.json',inventory),
                'allowed_sections':[item['section_id'] for item in inventory['sections']],
                'allowed_unit_ids':[item['unit_id'] for item in inventory['units']],
                'finding_sources':[{'artifact':self.p.feedback_ref,'feedback_ids':['fb-1']}]}
            self.p.surface_ref=self.p.save('crlf-surface.json',self.p.surface)
            self.config=replace(self.config,preservation_bridge=replace(self.config.preservation_bridge,allowed_change_surface=self.p.surface_ref))
            self.runner.config=self.config
            summary=decode_json(self.editor.response)
            summary.update(draft_before_hash=draft_hash(self.p.raw.decode()),draft_after_hash=draft_hash(self.p.after.decode()),draft_after_content=self.p.after.decode())
            self.editor.response=json_bytes(summary)
        if budgets:
            self.config=replace(self.config,review_profile_budgets=budgets);self.runner.config=self.config
        result=self.runner.run();self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        self.service=acceptance_service(self.root);self.assertEqual(self.approve().outcome,'accepted')

    def resume(self):
        return resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=self.reviewer,editor_client=self.editor)

    def test_acceptance_then_clean_closeout_without_repeated_sources_or_editor(self):
        self.start()
        self.reviewer.events=[(5,'structural_integrity',[]),(6,'determinism',[]),(7,'operability',[])]
        before=self.snapshot();plan=plan_resume_halted_run(self.root,self.config,continue_run=True)
        self.assertEqual(plan.next_round_number,5);self.assertEqual(before,self.snapshot())
        result=self.resume();self.assertEqual(result.terminal_state,'PHASE_1_STABLE');self.assertTrue(result.ready_for_phase_2)
        self.assertEqual(result.round_number,7);self.assertEqual(self.reviewer.calls,6);self.assertEqual(self.editor.calls,1)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),1)
        self.assertEqual([v['rounds_used'] for v in context(self.root,self.config)['profile_state'].values()],[2,2,2])
        self.assertTrue(read_status(root=self.root,config=self.config)['ready_for_phase_2'])
        before=self.snapshot();self.assertFalse(self.resume().resumed);self.assertEqual(before,self.snapshot())

    def test_crlf_closeout_timeout_recovers_exact_accepted_bytes(self):
        from whetstone.hashing import draft_hash
        self.start(crlf=True)
        self.reviewer.events=[(5,'structural_integrity',[]),TimeoutError('closeout'),(6,'determinism',[]),(7,'operability',[])]
        self.assertEqual(self.resume().terminal_state,'HALTED_CLIENT_TIMEOUT')
        result=self.resume();self.assertEqual(result.terminal_state,'PHASE_1_STABLE')
        self.assertEqual(result.current_draft_hash,draft_hash(self.p.after.decode()))
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.after)
        self.assertEqual(self.reviewer.calls,7);self.assertEqual(self.editor.calls,1)
        self.assertEqual(context(self.root,self.config)['terminal'],'PHASE_1_STABLE')

    def test_closeout_timeout_retains_earlier_serious_findings_and_receipt(self):
        self.start()
        self.reviewer.events=[(5,'structural_integrity',self.p.feedback['feedback']),TimeoutError('closeout'),
                              (6,'determinism',[]),(7,'operability',[])]
        result=self.resume();self.assertEqual(result.terminal_state,'HALTED_CLIENT_TIMEOUT')
        receipt=(self.root/'rounds/round-5/preservation/review_complete.json').read_bytes()
        result=self.resume();self.assertEqual(result.terminal_state,'TARGET_NOT_REACHED');self.assertFalse(result.ready_for_phase_2)
        self.assertEqual(result.round_number,7);self.assertEqual(self.reviewer.calls,7);self.assertEqual(self.editor.calls,1)
        self.assertEqual(receipt,(self.root/'rounds/round-5/preservation/review_complete.json').read_bytes())
        self.assertTrue(context(self.root,self.config)['issues'])
        before=self.snapshot();self.assertFalse(self.resume().resumed);self.assertEqual(before,self.snapshot())

    def test_second_cycle_requires_current_base_approval_then_uses_only_remaining_budgets(self):
        self.start(budgets={'structural_integrity':2,'determinism':1,'operability':1})
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'current base'):self.resume()
        self.assertEqual(before,self.snapshot());self.assertEqual(self.reviewer.calls,3)
        self.authorize_current_base()
        # One remaining source, then a no-op consolidation. Exhausted profiles
        # still need closeout against the edited bytes.
        self.reviewer.events=[(5,'structural_integrity',[]),(7,'structural_integrity',[]),
                              (8,'determinism',[]),(9,'operability',[])]
        result=self.resume();self.assertEqual(result.terminal_state,'PHASE_1_STABLE');self.assertEqual(result.round_number,9)
        self.assertEqual(self.reviewer.calls,7);self.assertEqual(self.editor.calls,1)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),2)
        self.assertEqual([v['rounds_used'] for v in context(self.root,self.config)['profile_state'].values()],[3,2,2])

    def test_source_timeout_resume_finishes_cycle_without_repeating_completed_review(self):
        self.setup_run(clean=True)
        self.reviewer.events=[(1,'structural_integrity',[]),TimeoutError('source'),(2,'determinism',[]),(3,'operability',[])]
        result=self.runner.run();self.assertEqual(result.terminal_state,'HALTED_CLIENT_TIMEOUT')
        result=self.resume();self.assertEqual(result.terminal_state,'PHASE_1_STABLE');self.assertEqual(result.round_number,4)
        self.assertEqual(self.reviewer.calls,4);self.assertEqual(self.editor.calls,0)
        self.assertEqual(self.reviewer.prompts[1],self.reviewer.prompts[2])

    def test_closeout_receipt_write_failure_reuses_completed_feedback(self):
        self.start()
        self.reviewer.events=[(5,'structural_integrity',[]),(6,'determinism',[]),(7,'operability',[])]
        from whetstone.preservation_proposals import ProposalStore
        original=ProposalStore._write
        def write(store,path,data):
            if path.endswith('round-5/preservation/review_complete.json'):raise OSError('receipt failure')
            return original(store,path,data)
        with patch.object(ProposalStore,'_write',new=write):
            with self.assertRaises(OSError):self.resume()
        self.assertEqual(self.reviewer.calls,4)
        result=self.resume();self.assertEqual(result.terminal_state,'PHASE_1_STABLE')
        self.assertEqual(self.reviewer.calls,6);self.assertEqual(self.editor.calls,1)

    def test_changed_budget_or_completed_receipt_blocks_continuation(self):
        self.start()
        path=self.root/'rounds/run_state.json';state=decode_json(path.read_bytes());state['review_round_budget']=99
        path.write_bytes(json_bytes(state));before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'budget'):self.resume()
        self.assertEqual(before,self.snapshot())
        (self.root/'rounds/round-2/reviewer_feedback.json').write_text('{}')
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)
        self.assertFalse(read_status(root=self.root,config=self.config)['ready_for_phase_2'])

    def test_second_consolidated_edit_accepts_then_verifies_latest_authority(self):
        self.start(budgets={'structural_integrity':2,'determinism':2,'operability':2})
        from copy import deepcopy
        from whetstone.hashing import draft_hash
        from whetstone.preservation_runtime import readback
        from whetstone.preservation_review import adopt_effect
        base=(self.root/'spec.md').read_text()
        feedback=deepcopy(self.p.feedback)
        feedback.update(round_number=5,draft_hash=draft_hash(base))
        feedback_ref=self.p.save('second-feedback.json',feedback)
        self.authorize_current_base(finding_sources=[{'artifact':feedback_ref,'feedback_ids':['fb-1']}])
        summary=decode_json(self.editor.response)
        revised=base.replace('30 seconds or longer','a minimum of 30 seconds')
        summary.update(round_number=8,draft_before_hash=draft_hash(base),draft_after_hash=draft_hash(revised),draft_after_content=revised)
        self.editor.response=json_bytes(summary)
        self.reviewer.events=[(5,'structural_integrity',feedback['feedback']),(6,'determinism',[]),(7,'operability',[])]
        result=self.resume();self.assertEqual(result.terminal_state,'PAUSED_DECISION');self.assertEqual(result.round_number,8)
        proposal=readback(self.root,self.config)['latest_proposal']
        effect=adopt_effect(self.service,proposal_ref=proposal,surface_ref=self.config.preservation_bridge.allowed_change_surface,
            output='second-effect.json',kind='attest_equivalence',base_lines=[9],output_lines=[9],disposition='reworded_equivalent',
            change_types=['clarify'],finding_ids=['fb-1'],effect='Same retry requirement.',rationale='Explicit second fixture approval.',
            operator='fixture-operator',approve=True)
        request=self.service.prepare_request(proposal_ref=proposal,evidence_refs=[effect],output='second-request.json')
        self.assertEqual(self.service.accept(request).outcome,'accepted')
        self.reviewer.events=[(9,'structural_integrity',[]),(10,'determinism',[]),(11,'operability',[])]
        result=self.resume();self.assertEqual(result.terminal_state,'PHASE_1_STABLE');self.assertEqual(result.round_number,11)
        self.assertEqual(self.editor.calls,2);self.assertEqual(self.reviewer.calls,9)
        self.assertEqual((self.root/'spec.md').read_text(),revised)
        self.assertEqual([v['rounds_used'] for v in context(self.root,self.config)['profile_state'].values()],[3,3,3])

    def test_completed_source_receipt_survives_interruption_before_scheduler_updates(self):
        self.setup_run(clean=True)
        from whetstone.preservation_continuation import finish_review_only
        def finish(runner,number):
            finish_review_only(runner,number)
            if number == 2:raise OSError('after receipt commit')
        with patch('whetstone.preservation_continuation.finish_review_only',side_effect=finish):
            with self.assertRaises(OSError):self.runner.run()
        self.assertEqual(self.reviewer.calls,2)
        result=self.resume();self.assertEqual(result.terminal_state,'PHASE_1_STABLE')
        self.assertEqual(self.reviewer.calls,3);self.assertEqual(self.editor.calls,0)

    def test_changed_timeout_or_prompt_refuses_vertical_closeout_retry(self):
        self.start();self.reviewer.events=[TimeoutError('closeout')]
        self.assertEqual(self.resume().terminal_state,'HALTED_CLIENT_TIMEOUT')
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'timeout changed'):
            resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=self.reviewer,editor_client=self.editor,timeout_seconds=999)
        self.assertEqual(before,self.snapshot())
        (self.root/'rounds/round-5/preservation/reviewer-attempt-1/prompt.txt').write_text('changed')
        with self.assertRaises(BridgeContractError):self.resume()
        self.assertEqual(self.reviewer.calls,4);self.assertEqual(self.editor.calls,1)

if __name__=='__main__':unittest.main()
