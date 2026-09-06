"""Guarded maintenance and inherited-authority journeys; no live model clients."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_preservation_runtime as runtime_fixtures
from test_preservation_continuation import ScriptedReviewer
from whetstone.hashing import draft_hash
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.live_phase2 import LivePhase2Runner
from whetstone.preservation_contracts import BridgeContractError, decode_json, read_ref
from whetstone.preservation_inventory import build_inventory
from whetstone.preservation_maintenance import enter_phase2
from whetstone.preservation_proposals import json_bytes
from whetstone.preservation_runtime import acceptance_service, guard_consumer, state_packet
from whetstone.scheduler import profile_names_for_phase


class MaintenanceTests(unittest.TestCase):
    setUp=runtime_fixtures.RuntimeTests.setUp
    snapshot=runtime_fixtures.RuntimeTests.snapshot
    setup_run=runtime_fixtures.RuntimeTests.setup_run

    def stable(self, *, versioned=False, vertical=False, crlf=False):
        runtime_fixtures.RuntimeTests.setup_run(self,noop=True)
        base=self.p.raw
        if versioned:base=base.replace(b'# Parcel Queue',b'# Parcel Queue 0.17\nStatus: Accepted',1)
        if crlf:base=base.replace(b'\n',b'\r\n')
        self.base=base;(self.root/'spec.md').write_bytes(base)
        base_ref=self.p.save('maintenance-seed.md',base)
        inventory=build_inventory(base,path=base_ref['path'])
        surface={**self.p.surface,'base_draft':base_ref,'inventory':self.p.save('maintenance-inventory.json',inventory),
            'allowed_sections':[s['section_id'] for s in inventory['sections']],
            'allowed_unit_ids':[u['unit_id'] for u in inventory['units']]}
        self.surface_ref=self.p.save('maintenance-surface.json',surface)
        profiles=profile_names_for_phase(self.config.review_profile_set,'phase_1')
        phase2=profile_names_for_phase(self.config.review_profile_set,'phase_2')
        self.config=replace(self.config,review_mode='vertical' if vertical else 'horizontal',
            review_profile_budgets={p:1 for p in profiles},convergence_profile_budgets={p:1 for p in phase2},
            preservation_bridge=replace(self.config.preservation_bridge,allowed_change_surface=self.surface_ref))
        self.reviewer=ScriptedReviewer(self.root,self.p.feedback,[(i,p,[]) for i,p in enumerate(profiles,1)])
        result=LivePhase1Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run()
        self.assertEqual(result.terminal_state,'PHASE_1_STABLE')
        self.handoff=state_packet(self.root);self.service=acceptance_service(self.root)

    def test_unversioned_entry_has_null_round_and_empty_evidence_and_is_idempotent(self):
        self.stable()
        result=enter_phase2(self.root,self.config)
        self.assertFalse(result.promoted)
        chain=self.service._chain();_,proposal,admission=self.service._proposal_directory(chain[-1][1]['proposal'])
        self.assertEqual(admission['origin'],'phase2_entry')
        for key in ('round_number','profile','client_attempt_number'):self.assertIsNone(admission[key])
        self.assertEqual(proposal['normal_round_evidence']['reviewer_feedback'],[])
        self.assertIsNone(proposal['normal_round_evidence']['editor_summary'])
        self.assertEqual(state_packet(self.root)['current_round'],self.handoff['current_round'])
        self.assertEqual(state_packet(self.root)['phase_2_rounds_completed'],0)
        self.assertFalse((self.root/'rounds/round-None').exists())
        before=self.snapshot();enter_phase2(self.root,self.config);self.assertEqual(before,self.snapshot())
        self.assertEqual(self.editor.calls,0);self.assertEqual(self.reviewer.calls,3)
        guard_consumer(self.root,self.config)

    def test_versioned_vertical_entry_preserves_exact_bytes_and_does_not_charge_budget(self):
        self.stable(versioned=True,vertical=True,crlf=True)
        result=enter_phase2(self.root,self.config)
        self.assertTrue(result.promoted)
        expected=self.base.replace(b'0.17',b'1.0')
        self.assertEqual((self.root/'spec.md').read_bytes(),expected)
        after=state_packet(self.root)
        self.assertEqual(after['review_round_budget'],self.handoff['review_round_budget'])
        self.assertEqual(after['phase_1_rounds_completed'],4)
        self.assertEqual(after['phase_2_rounds_completed'],0)
        self.assertEqual(self.editor.calls,0)
        # Adjacent content cannot be laundered through the trusted heading stamp.
        materialized=self.root/'rounds/preservation/phase2-entry/attempt-1/materialized_draft.md'
        materialized.write_bytes(materialized.read_bytes().replace(b'MUST',b'MAY',1))
        before=self.snapshot()
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)
        self.assertEqual(before,self.snapshot())

    def test_clean_phase2_rounds_inherit_maintenance_authority_and_converge(self):
        self.stable(versioned=True)
        start=self.handoff['current_round']+1
        self.reviewer.events=[(start+i,p,[]) for i,p in enumerate(profile_names_for_phase(self.config.review_profile_set,'phase_2'))]
        result=LivePhase2Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run()
        self.assertEqual(result.terminal_state,'CONVERGED')
        self.assertEqual(self.editor.calls,0)
        chain=self.service._chain()
        self.assertEqual(len(chain),7)
        self.assertTrue(all(m['accepted_noop'] for _,m,_ in chain[-3:]))
        self.assertEqual(state_packet(self.root)['phase_2_rounds_completed'],3)
        guard_consumer(self.root,self.config)

    def test_false_stability_cannot_promote_unverified_accepted_output(self):
        runtime_fixtures.RuntimeTests.pending(self,serious=True)
        self.assertEqual(runtime_fixtures.RuntimeTests.approve(self).outcome,'accepted')
        state=state_packet(self.root);state.update(terminal_state='PHASE_1_STABLE',ready_for_phase_2=True)
        (self.root/'rounds/run_state.json').write_bytes(json_bytes(state))
        before=self.snapshot()
        with self.assertRaises(BridgeContractError):enter_phase2(self.root,self.config)
        self.assertEqual(before,self.snapshot())

    def test_entry_request_pause_supports_read_only_acceptance_and_local_completion(self):
        from whetstone.preservation_runtime import RuntimeAcceptanceService
        self.stable(versioned=True)
        with patch.object(RuntimeAcceptanceService,'accept',side_effect=OSError('before acceptance')):
            with self.assertRaises(OSError):enter_phase2(self.root,self.config)
        request=self.service.reference('rounds/preservation/phase2-entry/attempt-1/noop_request.json')
        self.assertEqual((self.root/'spec.md').read_bytes(),self.base)
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)
        before=self.snapshot();self.assertEqual(self.service.accept(request,dry_run=True).outcome,'eligible')
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.service.accept(request).outcome,'accepted')
        self.assertEqual(self.reviewer.calls,3);self.assertEqual(self.editor.calls,0)
        self.assertEqual(state_packet(self.root)['current_round'],3)
        self.assertFalse((self.root/'rounds/round-4').exists())

    def fault_entry(self, suffix):
        from whetstone.preservation_proposals import ProposalStore
        self.stable(versioned=True)
        original=ProposalStore._write
        def write(store,path,data):
            if 'phase2-entry' in path and path.endswith(suffix):raise OSError('entry persistence fault')
            return original(store,path,data)
        with patch.object(ProposalStore,'_write',new=write):
            with self.assertRaises(OSError):enter_phase2(self.root,self.config)
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)
        before_calls=(self.reviewer.calls,self.editor.calls)
        enter_phase2(self.root,self.config)
        self.assertEqual((self.reviewer.calls,self.editor.calls),before_calls)
        self.assertEqual(len(list(self.root.glob('rounds/preservation/phase2-entry/attempt-*'))),1)
        self.assertEqual(len(list(self.root.glob('rounds/preservation/phase2-entry/attempt-*/acceptance-attempt-*'))),1)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.base.replace(b'0.17',b'1.0'))
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation Phase 2 entry:'),1)
        before=self.snapshot();enter_phase2(self.root,self.config);self.assertEqual(before,self.snapshot())
        guard_consumer(self.root,self.config)

    def test_entry_recovers_before_acceptance_marker_without_double_stamp(self):
        self.fault_entry('/acceptance.json')

    def test_entry_repairs_committed_marker_without_double_accounting(self):
        self.fault_entry('/runtime_completed.json')

    def test_entry_reuses_complete_proposal_after_request_write_interruption(self):
        self.fault_entry('/noop_request.json')

    def test_inherited_authority_cannot_admit_editor_or_supplied_revision(self):
        from whetstone.preservation_runtime import config_snapshot
        self.stable(versioned=True);enter_phase2(self.root,self.config)
        chain=self.service._chain()
        frozen=config_snapshot(self.config,phase='phase_2',profile='consistency',state=state_packet(self.root))
        for origin in ('editor','supplied_revision'):
            with self.subTest(origin=origin):
                before=self.snapshot()
                with self.assertRaisesRegex(BridgeContractError,'maintenance'):
                    self.service.admit(surface_ref=self.surface_ref,effective_config=frozen,reviewer_feedback_refs=[],round_number=4,
                        profile='consistency',phase='phase_2',origin=origin,client_attempt_number=1 if origin=='editor' else None,
                        maintenance_parent=chain[-1][0])
                self.assertEqual(before,self.snapshot())

    def test_phase2_findings_require_current_base_edit_authorization(self):
        self.stable(versioned=True)
        from test_live_phase2 import ScriptedPhase2ReviewerClient
        reviewer=ScriptedPhase2ReviewerClient(self.root,['major'])
        with self.assertRaisesRegex(BridgeContractError,'current base'):
            LivePhase2Runner(self.root,self.config,reviewer_client=reviewer,editor_client=self.editor).run()
        self.assertEqual(self.editor.calls,0);self.assertEqual(reviewer.calls,1)
        self.assertFalse((self.root/'rounds/round-4/draft_after.md').exists())
        self.assertEqual((self.root/'spec.md').read_bytes(),self.base.replace(b'0.17',b'1.0'))

    def test_phase2_timeout_has_no_generic_retry_or_false_consumption(self):
        from whetstone.resume import resume_halted_run, plan_resume_halted_run
        self.stable();self.reviewer.events=[TimeoutError('phase2')]
        result=LivePhase2Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run()
        self.assertEqual(result.terminal_state,'HALTED_CLIENT_TIMEOUT')
        for call in (resume_halted_run,plan_resume_halted_run):
            before=self.snapshot()
            with self.assertRaisesRegex(BridgeContractError,'Phase 2'):
                call(self.root,self.config,continue_run=True)
            self.assertEqual(before,self.snapshot())
        with self.assertRaises(BridgeContractError):guard_consumer(self.root,self.config)
        self.assertEqual(self.reviewer.calls,4);self.assertEqual(self.editor.calls,0)

    def test_changed_scope_blocks_maintenance(self):
        self.stable(versioned=True)
        scope=self.config.scope_contract.path
        scope.write_bytes(scope.read_bytes()+b' ')
        before=self.snapshot()
        with self.assertRaises(BridgeContractError):enter_phase2(self.root,self.config)
        self.assertEqual(before,self.snapshot())

    def test_entry_inherits_older_authorization_after_accepted_edit_and_verification(self):
        import test_preservation_vertical_recovery as recovery
        case=recovery.RecoveryTests();case.root=self.root
        case.test_acceptance_then_clean_closeout_without_repeated_sources_or_editor()
        before=(case.reviewer.calls,case.editor.calls)
        result=enter_phase2(self.root,case.config)
        self.assertFalse(result.promoted)
        service=acceptance_service(self.root);chain=service._chain()
        _,proposal,admission=service._proposal_directory(chain[-1][1]['proposal'])
        self.assertNotEqual(admission['base_draft'],case.p.surface['base_draft'])
        self.assertNotEqual(admission['inventory'],case.p.surface['inventory'])
        self.assertEqual(admission['allowed_change_surface'],case.config.preservation_bridge.allowed_change_surface)
        self.assertEqual((case.reviewer.calls,case.editor.calls),before)
        self.assertEqual(state_packet(self.root)['current_round'],7)
        guard_consumer(self.root,case.config)

    def test_authorized_phase2_edit_pauses_then_local_acceptance_stamps_once(self):
        import test_preservation_continuation as continuation
        from test_live_phase2 import ScriptedPhase2ReviewerClient
        from whetstone.live import LiveRoundRunner
        from whetstone.preservation_runtime import BridgeHalt, readback
        from whetstone.preservation_review import adopt_effect
        self.stable(versioned=True);enter_phase2(self.root,self.config)
        base=(self.root/'spec.md').read_bytes().decode()
        profile=profile_names_for_phase(self.config.review_profile_set,'phase_2')[0]
        # The fixture explicitly authorizes this finding against the promoted base.
        feedback=ScriptedPhase2ReviewerClient(self.root,['major']).review(f'Review profile: {profile}\n- round_number: 4\n')
        finding=feedback['feedback'][0]
        ref=self.p.save('phase2-finding.json',feedback)
        continuation.ContinuationTests.authorize_current_base(self,finding_sources=[{'artifact':ref,'feedback_ids':[finding['feedback_id']]}])
        revised=base.replace('at least 30 seconds','30 seconds or longer')
        summary=decode_json(self.editor.response)
        summary.update(round_number=4,draft_before_hash=draft_hash(base),draft_after_hash=draft_hash(revised),draft_after_content=revised,
                       resolved_issue_ids=[finding['issue_id']])
        self.editor.response=json_bytes(summary)
        self.reviewer=ScriptedReviewer(self.root,feedback,[(4,profile,[finding])])
        with self.assertRaises(BridgeHalt) as held:
            LiveRoundRunner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor).run_round(round_number=4,profile=profile,phase='phase_2',apply=True)
        self.assertEqual(held.exception.terminal_state,'PAUSED_DECISION')
        self.assertEqual((self.root/'spec.md').read_bytes().decode(),base)
        status=readback(self.root,self.config)
        line=next(i for i,text in enumerate(base.splitlines(),1) if 'at least 30 seconds' in text)
        effect=adopt_effect(self.service,proposal_ref=status['latest_proposal'],surface_ref=self.config.preservation_bridge.allowed_change_surface,
            output='phase2-effect.json',kind='attest_equivalence',base_lines=[line],output_lines=[line],disposition='reworded_equivalent',
            change_types=['clarify'],finding_ids=[finding['feedback_id']],effect='Same retry requirement.',rationale='Explicit fixture review.',operator='fixture-operator',approve=True)
        request=self.service.prepare_request(proposal_ref=status['latest_proposal'],evidence_refs=[effect],output='phase2-request.json')
        self.assertEqual(self.service.accept(request).outcome,'accepted')
        self.assertEqual((self.root/'spec.md').read_text(),revised.replace('1.0','1.1',1))
        self.assertEqual(self.reviewer.calls,1);self.assertEqual(self.editor.calls,1)
        self.assertEqual(state_packet(self.root)['phase_2_rounds_completed'],1)
        before=self.snapshot();self.service.accept(request);self.assertEqual(before,self.snapshot())
        guard_consumer(self.root,self.config)
