"""Scripted first-cycle vertical preservation journeys; no live clients."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_preservation_runtime as runtime_fixtures
from test_preservation_continuation import ScriptedReviewer
from whetstone.live import LiveRoundRunner
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.preservation_contracts import BridgeContractError, decode_json, read_ref
from whetstone.preservation_proposals import json_bytes
from whetstone.preservation_runtime import acceptance_service, readback, guard_consumer, initialize
from whetstone.resume import resume_halted_run, plan_resume_halted_run
from whetstone.status import read_status


class VerticalTests(unittest.TestCase):
    setUp = runtime_fixtures.RuntimeTests.setUp
    snapshot = runtime_fixtures.RuntimeTests.snapshot
    approve = runtime_fixtures.RuntimeTests.approve

    def setup_run(self, *, clean=False, serious=False, variant='clarified', case=0, second_findings=None):
        runtime_fixtures.RuntimeTests.setup_run(self, noop=clean, serious=serious, variant=variant, case=case)
        self.config = replace(self.config, review_mode='vertical',
                              review_profile_budgets={'structural_integrity':1,'determinism':1,'operability':1})
        self.reviewer = ScriptedReviewer(self.root,self.p.feedback,[(1,'structural_integrity',self.p.feedback['feedback']),
                            (2,'determinism',second_findings or []),(3,'operability',[])])
        summary=decode_json(self.editor.response)
        summary.update(round_number=4, accepted_feedback_ids=['structural_integrity:fb-1'])
        self.editor.response=json_bytes(summary)
        self.runner=LivePhase1Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor)

    def pending(self, **kwargs):
        self.setup_run(**kwargs)
        result=self.runner.run()
        self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        self.service=acceptance_service(self.root)
        return result

    def test_sources_merge_pending_local_acceptance_and_no_false_clean_profile(self):
        result=self.pending(serious=True)
        self.assertEqual(result.round_number,4);self.assertEqual(self.reviewer.calls,3);self.assertEqual(self.editor.calls,1)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)
        self.assertFalse((self.root/'rounds/round-4/draft_after.md').exists())
        proposal=decode_json(read_ref(self.root,readback(self.root,self.config)['latest_proposal']))
        self.assertEqual(len(proposal['normal_round_evidence']['reviewer_feedback']),4)
        frozen=decode_json(read_ref(self.root,proposal['normal_round_evidence']['effective_config']))
        self.assertEqual(len(frozen['vertical_review_sources']),3)
        reports={str(p):p.read_bytes() for p in self.root.glob('rounds/round-*/preservation/review_complete.json')}
        self.assertEqual(self.approve().outcome,'accepted')
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.after)
        self.assertEqual(self.reviewer.calls,3);self.assertEqual(self.editor.calls,1)
        self.assertEqual(reports,{str(p):p.read_bytes() for p in self.root.glob('rounds/round-*/preservation/review_complete.json')})
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'),1)
        guard_consumer(self.root,self.config)
        self.assertFalse(read_status(root=self.root,config=self.config)['ready_for_phase_2'])
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'vertical scheduler continuation'):
            resume_halted_run(self.root,self.config,continue_run=True)
        self.assertEqual(before,self.snapshot())

    def test_empty_sweep_commits_seed_noop_before_stability(self):
        self.setup_run(clean=True)
        result=self.runner.run()
        self.assertEqual(result.terminal_state,'PHASE_1_STABLE');self.assertTrue(result.ready_for_phase_2)
        self.assertEqual(result.round_number,4);self.assertEqual(self.editor.calls,0);self.assertEqual(self.reviewer.calls,3)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),1)
        self.assertTrue(read_status(root=self.root,config=self.config)['ready_for_phase_2'])
        before=self.snapshot()
        self.assertFalse(plan_resume_halted_run(self.root,self.config,continue_run=True).resumable)
        self.assertFalse(resume_halted_run(self.root,self.config,continue_run=True).resumed)
        self.assertEqual(before,self.snapshot())

    def test_hidden_contract_loss_is_rejected_before_authority(self):
        self.setup_run(case=1,variant='missing_field')
        unit=next(u for u in self.p.inventory['units'] if u['kind']=='body' and u['normative'] and u['section_id'].endswith('["Delivery",1]]'))
        self.p.surface.update(allowed_sections=[unit['section_id']],allowed_unit_ids=[unit['unit_id']],
            frozen_sections=[sec['section_id'] for sec in self.p.inventory['sections'] if sec['section_id'] not in ('[]',unit['section_id']) and sec['parent_section_id']!='[]'])
        ref=self.p.save('surface.json',self.p.surface)
        self.config=replace(self.config,preservation_bridge=replace(self.config.preservation_bridge,allowed_change_surface=ref))
        self.runner.config=self.config
        result=self.runner.run()
        self.assertEqual(result.terminal_state,'HALTED_ARTIFACT_INVALID')
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)
        self.assertFalse(list(self.root.rglob('acceptance.json')))
        self.assertFalse((self.root/'rounds/round-4/draft_after.md').exists())
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)

    def test_editor_timeout_retry_keeps_sources_and_does_not_replay_reviewers(self):
        self.setup_run()
        response=self.editor.response;self.editor.response=TimeoutError('scripted Editor timeout')
        result=self.runner.run();self.assertEqual(result.terminal_state,'HALTED_CLIENT_TIMEOUT')
        self.assertEqual(plan_resume_halted_run(self.root,self.config).client_role,'editor')
        self.editor.response=response
        result=resume_halted_run(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'PAUSED_DECISION');self.assertEqual(result.round_number,4)
        self.assertEqual(self.reviewer.calls,3);self.assertEqual(self.editor.calls,2)
        self.service=acceptance_service(self.root)
        self.assertEqual(self.approve().outcome,'accepted')

    def test_changed_source_receipt_blocks_acceptance_and_repair(self):
        self.pending()
        (self.root/'rounds/round-2/reviewer_feedback.json').write_text('{}')
        before=self.snapshot()
        with self.assertRaises(BridgeContractError):self.approve()
        self.assertEqual(before,self.snapshot());self.assertEqual(self.editor.calls,1)

    def test_reviewer_timeout_stops_without_editor_or_unsupported_retry(self):
        self.setup_run()
        self.reviewer.events[1]=TimeoutError('scripted source timeout')
        result=self.runner.run()
        self.assertEqual(result.terminal_state,'HALTED_CLIENT_TIMEOUT');self.assertEqual(self.editor.calls,0)
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'vertical Reviewer recovery'):
            resume_halted_run(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(before,self.snapshot());self.assertEqual(self.reviewer.calls,2)

    def test_unscheduled_source_and_direct_editor_paths_are_refused(self):
        self.setup_run();initialize(self.root,self.config)
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'out of order'):
            LiveRoundRunner(self.root,self.config).run_review_only_round(round_number=1,profile='determinism')
        with self.assertRaisesRegex(ValueError,'consolidated'):
            LiveRoundRunner(self.root,self.config).run_round(round_number=1,profile='structural_integrity')
        self.assertEqual(before,self.snapshot());self.assertEqual(self.editor.calls,0)

    def test_corrupt_source_during_editor_call_cannot_commit(self):
        self.setup_run()
        original=self.editor.revise_raw
        def revise(prompt):
            result=original(prompt)
            (self.root/'rounds/round-1/reviewer_feedback.json').write_text('{}')
            return result
        self.editor.revise_raw=revise
        result=self.runner.run()
        self.assertEqual(result.terminal_state,'HALTED_ARTIFACT_INVALID')
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)
        self.assertFalse(list(self.root.rglob('acceptance.json')))

    def test_tampered_merge_is_refused_before_editor(self):
        self.setup_run()
        from whetstone.preservation_vertical import prepare_consolidated
        def prepare(runner, number, feedback, base):
            feedback=deepcopy(feedback);feedback['feedback']=[]
            return prepare_consolidated(runner,number,feedback,base)
        with patch('whetstone.preservation_vertical.prepare_consolidated',side_effect=prepare):
            with self.assertRaisesRegex(BridgeContractError,'differs from source'):
                self.runner.run()
        self.assertEqual(self.editor.calls,0);self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)
        self.assertFalse((self.root/'rounds/round-4').exists())

    def test_source_completion_fault_never_invokes_editor(self):
        self.setup_run()
        from whetstone.preservation_proposals import ProposalStore
        original=ProposalStore._write
        def write(store,path,data):
            if path.endswith('round-2/preservation/review_complete.json'):raise OSError('scripted source receipt failure')
            return original(store,path,data)
        with patch.object(ProposalStore,'_write',new=write):
            with self.assertRaises(OSError):self.runner.run()
        self.assertEqual(self.reviewer.calls,2);self.assertEqual(self.editor.calls,0)
        self.assertFalse(list(self.root.rglob('acceptance.json')))
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)

    def test_unrelated_serious_source_survives_merged_resolution_claims(self):
        self.setup_run()
        finding=deepcopy(self.p.feedback['feedback'][0])
        finding.update(issue_id='iss_'+'b'*16,issue_fingerprint='b'*64,normalized_severity='major',baseline_severity='major')
        self.reviewer.events[1]=(2,'determinism',[finding])
        result=self.runner.run();self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        self.service=acceptance_service(self.root)
        result=self.approve()
        self.assertEqual(result.outcome,'rejected');self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)
        self.assertEqual(self.editor.calls,1);self.assertFalse(list(self.root.rglob('acceptance.json')))

    def test_accepted_replay_repairs_without_repeating_sources_or_accounting(self):
        self.pending();self.assertEqual(self.approve().outcome,'accepted')
        before=self.snapshot();self.service.accept(self.request)
        self.assertEqual(before,self.snapshot());self.assertEqual(self.reviewer.calls,3);self.assertEqual(self.editor.calls,1)
        (self.root/'rounds/round-4/draft_after.md').unlink()
        self.service.accept(self.request)
        self.assertEqual(before,self.snapshot())

    def test_source_corruption_after_acceptance_blocks_consumers_and_readiness(self):
        self.pending();self.assertEqual(self.approve().outcome,'accepted')
        (self.root/'rounds/round-1/reviewer_feedback.json').write_text('{}')
        before=self.snapshot()
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)
        status=read_status(root=self.root,config=self.config)
        self.assertFalse(status['ready_for_phase_2']);self.assertEqual(status['next_action'],'inspect_and_repair')
        self.assertEqual(before,self.snapshot())

    def test_unchanged_minor_output_stops_after_one_consolidated_operation(self):
        self.setup_run()
        summary=decode_json(self.editor.response)
        summary.update(draft_after_content=self.p.raw.decode(),draft_after_hash=summary['draft_before_hash'])
        self.editor.response=json_bytes(summary)
        self.config=replace(self.config,review_profile_budgets={'structural_integrity':2,'determinism':2,'operability':2})
        self.runner.config=self.config
        result=self.runner.run()
        self.assertEqual(result.terminal_state,'TARGET_NOT_REACHED');self.assertEqual(result.round_number,4)
        self.assertEqual(self.reviewer.calls,3);self.assertEqual(self.editor.calls,1)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),1)

    def test_empty_vertical_sweep_preserves_crlf_bytes(self):
        self.setup_run(clean=True)
        from whetstone.preservation_inventory import build_inventory
        base=self.p.raw.replace(b'\n',b'\r\n')
        (self.root/'spec.md').write_bytes(base)
        base_ref=self.p.save('crlf-seed.md',base)
        inventory=build_inventory(base,path=base_ref['path'])
        inventory_ref=self.p.save('crlf-inventory.json',inventory)
        surface={**self.p.surface,'base_draft':base_ref,'inventory':inventory_ref,
                 'allowed_sections':[item['section_id'] for item in inventory['sections']],
                 'allowed_unit_ids':[item['unit_id'] for item in inventory['units']]}
        ref=self.p.save('crlf-surface.json',surface)
        self.config=replace(self.config,preservation_bridge=replace(self.config.preservation_bridge,allowed_change_surface=ref))
        self.runner.config=self.config
        result=self.runner.run()
        self.assertEqual(result.terminal_state,'PHASE_1_STABLE');self.assertEqual(self.editor.calls,0)
        self.assertEqual((self.root/'spec.md').read_bytes(),base)
        self.assertEqual((self.root/'rounds/round-4/draft_before.md').read_bytes(),base)
        self.assertEqual((self.root/'rounds/round-4/draft_after.md').read_bytes(),base)


if __name__=='__main__':unittest.main()
