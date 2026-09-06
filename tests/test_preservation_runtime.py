from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from test_preservation_contracts import Packet
from whetstone.config import OrchestratorConfig, PreservationBridgeConfig, ClientConfig, ScopeContractConfig
from whetstone.live import LiveRoundRunner
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.preservation_runtime import BridgeHalt, acceptance_service, readback, guard_consumer
from whetstone.preservation_proposals import json_bytes
from whetstone.preservation_contracts import decode_json, read_ref, BridgeContractError
from whetstone.preservation_review import adopt_effect
from whetstone.status import read_status
from whetstone.apply_back import apply_back


class Reviewer:
    def __init__(self, feedback): self.feedback = feedback; self.calls = 0
    def review(self, prompt): self.calls += 1; return deepcopy(self.feedback)


class Editor:
    def __init__(self, response): self.response = response; self.calls = 0
    def revise_raw(self, prompt):
        self.calls += 1
        if isinstance(self.response, Exception): raise self.response
        return self.response
    def revise(self, prompt): raise AssertionError('legacy Editor path invoked')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def setup_run(self, *, noop=False, variant='clarified', case=0, serious=False, profile='structural_integrity'):
        self.p = p = Packet(self.root, case, variant)
        (self.root/'spec.md').write_bytes(p.raw)
        p.feedback['profile'] = profile
        if noop: p.feedback['feedback'] = []
        if serious: p.feedback['feedback'][0]['normalized_severity'] = 'major';p.feedback['feedback'][0]['baseline_severity'] = 'major'
        p.feedback_ref = p.save('feedback.json', p.feedback)
        p.surface['finding_sources'] = [] if noop else [{'artifact': p.feedback_ref, 'feedback_ids':['fb-1']}]
        p.surface_ref = p.save('surface.json', p.surface)
        self.config = replace(OrchestratorConfig.default(self.root),
            scope_contract=ScopeContractConfig(self.root/'scope.json'),
            reviewer=ClientConfig('codex','unused','1','fixture'), editor=ClientConfig('codex','unused','1','fixture'),
            preservation_bridge=PreservationBridgeConfig('enforce','preservation-bridge-v1',p.surface_ref))
        self.reviewer = Reviewer(p.feedback)
        self.editor = Editor(read_ref(self.root, p.proposal['raw_response']))
        self.runner = LiveRoundRunner(self.root, self.config, reviewer_client=self.reviewer, editor_client=self.editor)
        self.service = None
        return self.runner

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def pending(self, **kwargs):
        self.setup_run(**kwargs)
        with self.assertRaises(BridgeHalt) as error:
            self.runner.run_round(round_number=1, profile=self.p.feedback['profile'], apply=True)
        self.service = acceptance_service(self.root)
        return error.exception

    def approve(self):
        status = readback(self.root,self.config)
        effect = adopt_effect(self.service, proposal_ref=status['latest_proposal'],surface_ref=self.p.surface_ref,
            output='effect.json',kind='attest_equivalence',base_lines=[9],output_lines=[9],disposition='reworded_equivalent',
            change_types=['clarify'],finding_ids=['fb-1'],effect='Same retry requirement.',rationale='Explicit fixture review.',
            operator='fixture-operator',approve=True)
        self.request = self.service.prepare_request(proposal_ref=status['latest_proposal'],evidence_refs=[effect],output='request.json')
        return self.service.accept(self.request)

    def test_live_pending_acceptance_repair_and_status(self):
        error = self.pending()
        self.assertEqual(error.terminal_state,'PAUSED_DECISION')
        self.assertEqual(self.editor.calls,1)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)
        self.assertFalse((self.root/'rounds/round-1/draft_after.md').exists())
        self.assertFalse((self.root/'rounds/round-1/editor_summary.json').exists())
        old_report = read_ref(self.root,error.report_ref)
        result = self.approve()
        self.assertEqual(result.outcome,'accepted',result.report)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.after)
        self.assertEqual(self.editor.calls,1)
        self.assertEqual(read_ref(self.root,error.report_ref),old_report)
        snapshot = self.snapshot()
        self.service.accept(self.request)
        self.assertEqual(snapshot,self.snapshot())
        status = read_status(root=self.root,config=self.config)
        self.assertIsNone(status['preservation_bridge']['pending_outcome'])
        self.assertFalse(status['ready_for_phase_2'])
        self.assertEqual(snapshot,self.snapshot())
        guard_consumer(self.root,self.config)

    def test_scheduler_stops_at_pending_even_with_soft_budgets(self):
        self.setup_run()
        config = replace(self.config, review_budget_exhaustion_policy='soft')
        result = LivePhase1Runner(self.root,config,reviewer_client=self.reviewer,editor_client=self.editor).run()
        self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        self.assertEqual(result.round_number,1)
        self.assertFalse(result.ready_for_phase_2)
        self.assertEqual(self.editor.calls,1)
        self.assertFalse((self.root/'rounds/round-2').exists())

    def test_noop_round_uses_no_editor_and_one_commit(self):
        self.setup_run(noop=True)
        result = self.runner.run_round(round_number=1,profile='structural_integrity',apply=True)
        self.assertTrue(result.accepted)
        self.assertFalse(result.spec_mutated)
        self.assertEqual(self.editor.calls,0)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),1)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)

    def test_malformed_editor_body_is_retained_and_never_retried(self):
        self.setup_run();self.editor.response=b'{bad JSON\r\n'
        with self.assertRaises(BridgeHalt) as exc:
            self.runner.run_round(round_number=1,profile='structural_integrity',apply=True)
        self.assertEqual(exc.exception.terminal_state,'HALTED_ARTIFACT_INVALID')
        self.assertEqual(self.editor.calls,1)
        self.assertEqual(next(self.root.glob('rounds/round-1/preservation/attempt-*/raw_response.json')).read_bytes(),self.editor.response)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)

    def test_pending_cannot_run_next_round_or_strop_with_overrides(self):
        self.pending();source=self.root/'source.md';source.write_bytes(self.p.raw)
        snapshot=self.snapshot()
        for apply in (False,True):
            with self.assertRaises(BridgeContractError):
                apply_back(source_path=source,run_root=self.root,apply=apply,approve=True,allow_non_converged=True,allow_source_hash_mismatch=True)
        with self.assertRaises(BridgeContractError):
            self.runner.run_round(round_number=2,profile='structural_integrity',apply=True)
        self.assertEqual(snapshot,self.snapshot())
        self.assertEqual(self.editor.calls,1)

    def test_supplied_revision_is_retained_before_summary_and_pending(self):
        self.setup_run()
        original=self.editor.revise_raw
        def summary(prompt):
            retained=next(self.root.glob('rounds/round-1/preservation/attempt-*/supplied_input.md'))
            self.assertEqual(retained.read_bytes(),self.p.after)
            return original(prompt)
        self.editor.revise_raw=summary
        with self.assertRaises(BridgeHalt):
            self.runner.run_round(round_number=1,profile='structural_integrity',draft_after=self.p.after,apply=True)
        self.assertEqual(self.editor.calls,1)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)
        self.assertFalse((self.root/'rounds/round-1/draft_after.md').exists())

    def test_unfinished_scheduler_repair_blocks_read_only_consumer(self):
        self.pending()
        original=self.service._replace
        def fail(path, content):
            if path=='rounds/run_state.json': raise OSError('simulated scheduler write failure')
            return original(path, content)
        with patch.object(self.service,'_replace',side_effect=fail):
            with self.assertRaises(OSError):self.approve()
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),1)
        snapshot=self.snapshot()
        with self.assertRaises(BridgeContractError): guard_consumer(self.root,self.config)
        self.assertEqual(snapshot,self.snapshot())
        self.service.accept(self.request)
        guard_consumer(self.root,self.config)
        self.assertEqual(self.editor.calls,1)
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'),1)

    def test_timeout_retry_keeps_round_and_reviewer_and_allocates_new_attempt(self):
        from whetstone.resume import resume_halted_run, plan_resume_halted_run
        self.setup_run();original=self.editor.response;self.editor.response=TimeoutError('fixture timeout')
        with self.assertRaises(BridgeHalt) as error:
            self.runner.run_round(round_number=1, profile='structural_integrity', apply=True)
        self.assertEqual(error.exception.terminal_state,'HALTED_CLIENT_TIMEOUT')
        old=read_ref(self.root,error.exception.report_ref)
        snapshot=self.snapshot()
        plan=plan_resume_halted_run(self.root,self.config)
        self.assertTrue(plan.resumable);self.assertEqual(plan.next_attempt_number,2)
        self.assertEqual(snapshot,self.snapshot())
        self.editor.response=original
        result=resume_halted_run(self.root,self.config,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        self.assertEqual(result.round_number,1)
        self.assertEqual(self.reviewer.calls,1);self.assertEqual(self.editor.calls,2)
        self.assertEqual(read_ref(self.root,error.exception.report_ref),old)
        admission=decode_json((self.root/'rounds/round-1/preservation/attempt-2/admission.json').read_bytes())
        self.assertEqual(admission['predecessor_report'],error.exception.report_ref)
        self.assertEqual(admission['client_attempt_number'],2)
        self.assertEqual(admission['allowed_change_surface'],self.p.surface_ref)
        self.service=acceptance_service(self.root);self.approve()
        state=decode_json((self.root/'rounds/run_state.json').read_bytes())
        self.assertEqual(state['phase_1_rounds_completed'],1)
        self.assertEqual(self.editor.calls,2)

    def test_retry_cannot_refresh_config_or_base(self):
        from whetstone.resume import resume_halted_run
        self.setup_run();self.editor.response=TimeoutError('fixture timeout')
        with self.assertRaises(BridgeHalt):
            self.runner.run_round(round_number=1,profile='structural_integrity',apply=True)
        snapshot=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'settings'):
            resume_halted_run(self.root,replace(self.config,review_budget_exhaustion_policy='soft'),editor_client=self.editor)
        self.assertEqual(snapshot,self.snapshot());self.assertEqual(self.editor.calls,1)
        (self.root/'spec.md').write_bytes(b'changed base')
        with self.assertRaises(BridgeContractError):
            resume_halted_run(self.root,self.config,editor_client=self.editor)
        self.assertEqual(self.editor.calls,1)

    def test_hard_loss_with_apply_true_preserves_authority_and_blocks_retry(self):
        from whetstone.resume import resume_halted_run
        self.setup_run(case=1,variant='missing_field')
        unit=next(u for u in self.p.inventory['units'] if u['kind']=='body' and u['normative'] and u['section_id'].endswith('["Delivery",1]]'))
        self.p.surface.update(allowed_sections=[unit['section_id']],allowed_unit_ids=[unit['unit_id']],
            frozen_sections=[sec['section_id'] for sec in self.p.inventory['sections'] if sec['section_id'] not in ('[]',unit['section_id']) and sec['parent_section_id']!='[]'])
        surface=self.p.save('surface.json',self.p.surface)
        self.config=replace(self.config,preservation_bridge=replace(self.config.preservation_bridge,allowed_change_surface=surface))
        self.runner.config=self.config
        with self.assertRaises(BridgeHalt) as exc:
            self.runner.run_round(round_number=1,profile='structural_integrity',apply=True)
        self.assertEqual(exc.exception.terminal_state,'HALTED_ARTIFACT_INVALID')
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)
        self.assertFalse((self.root/'rounds/round-1/draft_after.md').exists())
        snapshot=self.snapshot()
        with self.assertRaises(BridgeContractError):resume_halted_run(self.root,self.config,editor_client=self.editor)
        self.assertEqual(snapshot,self.snapshot());self.assertEqual(self.editor.calls,1)

    def test_changed_scheduler_prevents_commit(self):
        self.pending()
        state_path=self.root/'rounds/run_state.json';state=decode_json(state_path.read_bytes())
        state['review_round_budget']=999;state_path.write_bytes(json_bytes(state))
        with self.assertRaisesRegex(BridgeContractError,'scheduler binding'):
            self.approve()
        self.assertFalse(list(self.root.rglob('acceptance.json')))
        self.assertEqual((self.root/'spec.md').read_bytes(),self.p.raw)

    def test_pending_phase2_and_direct_promotion_refuse_without_writes(self):
        from whetstone.live_phase2 import LivePhase2Runner
        from whetstone.versioning import promote_spec_file_for_phase2
        self.pending();snapshot=self.snapshot()
        for closeout in (False,True):
            with self.assertRaises(BridgeContractError):
                LivePhase2Runner(self.root,self.config).run(closeout_existing=closeout)
        with self.assertRaises(BridgeContractError):
            promote_spec_file_for_phase2(spec_path=self.root/'spec.md',history_path=self.root/'spec.history.md',rounds_dir=self.root/'rounds')
        self.assertEqual(snapshot,self.snapshot())

    def test_accepted_dry_strop_is_read_only_and_external_hash_guard_remains(self):
        self.pending();self.approve();source=self.root/'source.md';source.write_bytes(self.p.raw)
        snapshot=self.snapshot()
        result=apply_back(source_path=source,run_root=self.root)
        self.assertFalse(result.applied);self.assertEqual(snapshot,self.snapshot())
        with self.assertRaisesRegex(ValueError,'source hash mismatch'):
            apply_back(source_path=source,run_root=self.root,apply=True,approve=True,allow_non_converged=True,expected_source_hash='0'*64)
        self.assertEqual(snapshot,self.snapshot())

    def test_serious_finding_remains_reviewer_evidence_after_explicit_acceptance(self):
        self.pending(serious=True);result=self.approve()
        self.assertEqual(result.outcome,'accepted',result.report)
        completion=decode_json(next(self.root.rglob('runtime_completed.json')).read_bytes())
        self.assertEqual(completion['reviewer_counts']['major'],1)
        self.assertFalse(decode_json((self.root/'rounds/run_state.json').read_bytes())['ready_for_phase_2'])

    def test_missing_admission_blocks_consumer_after_earlier_acceptance(self):
        self.pending();self.approve()
        (self.root/'rounds/round-2/preservation/attempt-1').mkdir(parents=True)
        snapshot=self.snapshot()
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)
        self.assertEqual(snapshot,self.snapshot())

    def test_vertical_and_overwrite_refuse_before_any_call(self):
        self.setup_run();snapshot=self.snapshot()
        for config, overwrite in ((replace(self.config,review_mode='vertical'),False),(self.config,True)):
            with self.assertRaises(BridgeContractError):
                LivePhase1Runner(self.root,config,reviewer_client=self.reviewer,editor_client=self.editor).run(overwrite=overwrite)
        self.assertEqual(snapshot,self.snapshot());self.assertEqual(self.reviewer.calls,0)

    def test_phase1_focused_pending_is_same_guarded_path(self):
        from whetstone.scheduler import focused_phase_1_scheduler
        self.setup_run()
        result=LivePhase1Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor,
            scheduler_factory=lambda _: focused_phase_1_scheduler('structural_integrity',round_budget=2),
            state_review_profile_budgets={'structural_integrity':2},run_mode='focused_phase_1').run()
        self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        self.service=acceptance_service(self.root);self.approve()
        state=decode_json((self.root/'rounds/run_state.json').read_bytes())
        self.assertEqual(state['run_mode'],'focused_phase_1');self.assertEqual(state['review_round_budget'],2)
        self.assertEqual(state['phase_1_rounds_completed'],1)

    def test_supplied_timeout_retains_input_and_retries_summary_once(self):
        from whetstone.resume import resume_halted_run
        self.setup_run();original=self.editor.response;self.editor.response=TimeoutError('summary timeout')
        with self.assertRaises(BridgeHalt):
            self.runner.run_round(round_number=1,profile='structural_integrity',draft_after=self.p.after,apply=True)
        self.editor.response=original
        result=resume_halted_run(self.root,self.config,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        self.assertEqual(self.editor.calls,2);self.assertEqual(self.reviewer.calls,1)
        self.assertEqual((self.root/'rounds/round-1/preservation/attempt-2/supplied_input.md').read_bytes(),self.p.after)

    def test_status_legacy_is_explicit_and_read_only(self):
        self.setup_run();config=replace(self.config,preservation_bridge=None)
        snapshot=self.snapshot();status=read_status(root=self.root,config=config)
        self.assertEqual(status['preservation_bridge']['mode'],'legacy_unguarded')
        self.assertEqual(snapshot,self.snapshot())

    def test_clean_noop_phase1_completes_three_profiles_through_markers(self):
        self.setup_run(noop=True)
        profiles=['structural_integrity','determinism','operability']
        def review(prompt):
            self.reviewer.calls+=1
            feedback=deepcopy(self.p.feedback)
            feedback.update(round_number=self.reviewer.calls,profile=profiles[self.reviewer.calls-1])
            return feedback
        self.reviewer.review=review
        result=LivePhase1Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run()
        self.assertEqual(result.terminal_state,'PHASE_1_STABLE')
        self.assertEqual(result.round_number,3)
        self.assertEqual(self.editor.calls,0)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),3)
        self.assertEqual(len(list(self.root.rglob('runtime_completed.json'))),3)
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'),3)
        guard_consumer(self.root,self.config)

    def test_frozen_timeout_config_or_feedback_corruption_refuses_retry(self):
        from whetstone.resume import resume_halted_run
        self.setup_run();self.editor.response=TimeoutError('fixture timeout')
        with self.assertRaises(BridgeHalt):
            self.runner.run_round(round_number=1,profile='structural_integrity',apply=True)
        path=self.root/'rounds/round-1/preservation/attempt-1/effective_config.json'
        value=decode_json(path.read_bytes());value['runtime']['state_before']['review_round_budget']=10000
        path.write_bytes(json_bytes(value))
        with self.assertRaisesRegex(BridgeContractError,'hash mismatch'):
            resume_halted_run(self.root,self.config,editor_client=self.editor)
        self.assertEqual(self.editor.calls,1)

    def test_changed_supplied_bytes_cannot_be_retried_as_the_original_input(self):
        from whetstone.resume import resume_halted_run
        self.setup_run();self.editor.response=TimeoutError('fixture summary timeout')
        with self.assertRaises(BridgeHalt):
            self.runner.run_round(round_number=1,profile='structural_integrity',draft_after=self.p.after,apply=True)
        (self.root/'rounds/round-1/preservation/attempt-1/supplied_input.md').write_bytes(b'replacement body')
        with self.assertRaisesRegex(BridgeContractError,'hash mismatch'):
            resume_halted_run(self.root,self.config,editor_client=self.editor)
        self.assertEqual(self.editor.calls,1)

    def test_runtime_scope_must_match_the_admitted_approved_scope(self):
        self.setup_run();self.config=replace(self.config,scope_contract=ScopeContractConfig(self.root/'missing-scope.json'))
        snapshot=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'runtime scope'):
            LivePhase1Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run()
        self.assertFalse((self.root/'rounds/preservation/runtime.json').exists())
        self.assertEqual(self.editor.calls,0);self.assertEqual(self.reviewer.calls,0)


if __name__=='__main__': unittest.main()
