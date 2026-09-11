"""Explicit grants across exhausted guarded schedules and interrupted reviews."""
import unittest
from copy import deepcopy
from unittest.mock import patch

import test_preservation_continuation as horizontal
import test_preservation_vertical_recovery as vertical
from whetstone.preservation_contracts import BridgeContractError, decode_json
from whetstone.preservation_proposals import json_bytes, ProposalStore
from whetstone.preservation_acceptance import AcceptanceService
from whetstone.preservation_runtime import state_packet
from whetstone.resume import resume_budget_exhausted_run, plan_budget_extension_resume, resume_halted_run


def prepare_revision(case, number, *, finding_number=None):
    from whetstone.hashing import draft_hash
    base = (case.root/'spec.md').read_text()
    feedback = deepcopy(case.p.feedback)
    feedback.update(round_number=finding_number or number,draft_hash=draft_hash(base))
    ref = case.p.save('extension-finding.json',feedback)
    case.authorize_current_base(prefix='extension',finding_sources=[{'artifact':ref,'feedback_ids':['fb-1']}])
    revised = base.replace('30 seconds or longer','a minimum of 30 seconds')
    summary = decode_json(case.editor.response)
    summary.update(round_number=number,draft_before_hash=draft_hash(base),draft_after_hash=draft_hash(revised),
        draft_after_content=revised,resolved_issue_ids=[feedback['feedback'][0]['issue_id']])
    case.editor.response = json_bytes(summary)
    return feedback['feedback']


def accept_revision(case):
    from whetstone.preservation_runtime import readback
    from whetstone.preservation_review import adopt_effect
    proposal = readback(case.root,case.config)['latest_proposal']
    effect = adopt_effect(case.service,proposal_ref=proposal,surface_ref=case.config.preservation_bridge.allowed_change_surface,
        output='extension-effect.json',kind='attest_equivalence',base_lines=[9],output_lines=[9],disposition='reworded_equivalent',
        change_types=['clarify'],finding_ids=['fb-1'],effect='Same retry requirement.',rationale='Explicit fixture approval.',
        operator='fixture-operator',approve=True)
    request = case.service.prepare_request(proposal_ref=proposal,evidence_refs=[effect],output='extension-request.json')
    case.assertEqual(case.service.accept(request).outcome,'accepted')


class BudgetTests(unittest.TestCase):
    setUp = horizontal.ContinuationTests.setUp
    setup_run = horizontal.ContinuationTests.setup_run
    snapshot = horizontal.ContinuationTests.snapshot
    approve = horizontal.ContinuationTests.approve
    start = horizontal.ContinuationTests.start
    authorize_current_base = horizontal.ContinuationTests.authorize_current_base

    def exhausted(self):
        self.start(focused=True,serious=True)
        self.reviewer = horizontal.ScriptedReviewer(self.root,self.p.feedback,[(2,'structural_integrity',self.p.feedback['feedback'])])
        result = resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'TARGET_NOT_REACHED')
        self.authorize_current_base()

    def extend(self, amount=1):
        return resume_budget_exhausted_run(self.root,self.config,extend_review_budget=amount,
            reviewer_client=self.reviewer,editor_client=self.editor)

    def test_horizontal_grant_counts_closeout_and_preserves_original_recipe(self):
        self.exhausted()
        before = self.snapshot()
        plan = plan_budget_extension_resume(self.root,self.config,extend_review_budget=1)
        self.assertEqual(plan.next_round_number,3);self.assertEqual(before,self.snapshot())
        from whetstone.status import read_status
        self.assertIn('--extend-review-budget',read_status(root=self.root,config=self.config)['resume']['command'])
        self.assertEqual(before,self.snapshot())
        findings = prepare_revision(self,3)
        self.reviewer.events = [(3,'structural_integrity',findings)]
        result = self.extend()
        self.assertEqual(result.terminal_state,'PAUSED_DECISION')
        accept_revision(self)
        self.reviewer.events = [(4,'structural_integrity',[])]
        result = resume_halted_run(self.root,self.config,continue_run=True,reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'FOCUSED_PROFILE_STABLE')
        event = state_packet(self.root)['budget_extensions'][0]
        self.assertEqual(event['previous_review_profile_budgets'],{'structural_integrity':1})
        self.assertEqual(event['new_review_profile_budgets'],{'structural_integrity':3})
        self.assertEqual(self.editor.calls,2)
        before = self.snapshot()
        with self.assertRaises(BridgeContractError):self.extend()
        self.assertEqual(before,self.snapshot())

    def test_timeout_reuses_grant_and_exact_next_attempt(self):
        self.exhausted();self.reviewer.events = [TimeoutError('extension review'),(3,'structural_integrity',[])]
        self.assertEqual(self.extend().terminal_state,'HALTED_CLIENT_TIMEOUT')
        grant = (self.root/'rounds/preservation/budget-extensions/grant-1.json').read_bytes()
        before = self.snapshot()
        with self.assertRaises(BridgeContractError):self.extend(2)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.extend().terminal_state,'HALTED_ARTIFACT_INVALID')
        self.assertEqual(self.reviewer.prompts[-1],self.reviewer.prompts[-2])
        self.assertEqual(len(state_packet(self.root)['budget_extensions']),1)
        self.assertEqual(grant,(self.root/'rounds/preservation/budget-extensions/grant-1.json').read_bytes())

    def test_grant_commit_before_state_write_recovers_without_duplicate_grant(self):
        self.exhausted();self.reviewer.events = [(3,'structural_integrity',[])]
        original = AcceptanceService._replace
        def fail(store,path,data):
            if path == 'rounds/run_state.json' and decode_json(data).get('budget_extensions'):
                raise OSError('grant state mirror')
            return original(store,path,data)
        with patch.object(AcceptanceService,'_replace',new=fail):
            with self.assertRaises(OSError):self.extend()
        self.assertEqual(self.reviewer.calls,1)
        before = self.snapshot();plan_budget_extension_resume(self.root,self.config,extend_review_budget=1)
        from whetstone.status import read_status
        self.assertIn('--extend-review-budget 1',read_status(root=self.root,config=self.config)['resume']['command'])
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.extend().terminal_state,'HALTED_ARTIFACT_INVALID')
        self.assertEqual(len(state_packet(self.root)['budget_extensions']),1)

    def test_invalid_amount_hash_and_mutable_budget_refuse_without_writes(self):
        self.exhausted()
        before = self.snapshot()
        with self.assertRaises(BridgeContractError):self.extend(0)
        self.assertEqual(before,self.snapshot())
        path = self.root/'spec.md';original = path.read_bytes();path.write_bytes(original+b'changed\n')
        changed = self.snapshot()
        with self.assertRaises(BridgeContractError):self.extend()
        self.assertEqual(changed,self.snapshot());path.write_bytes(original)
        path = self.root/'rounds/run_state.json';state = state_packet(self.root)
        state['review_profile_budgets']['structural_integrity'] = 99
        path.write_bytes(json_bytes(state));changed = self.snapshot()
        with self.assertRaises(BridgeContractError):self.extend()
        self.assertEqual(changed,self.snapshot())

    def test_second_grant_uses_counts_from_prior_extension_and_closeout(self):
        self.exhausted();findings = prepare_revision(self,3)
        self.reviewer.events = [(3,'structural_integrity',findings)]
        self.assertEqual(self.extend().terminal_state,'PAUSED_DECISION');accept_revision(self)
        self.reviewer.events = [(4,'structural_integrity',findings)]
        self.assertEqual(resume_halted_run(self.root,self.config,continue_run=True,
            reviewer_client=self.reviewer,editor_client=self.editor).terminal_state,'TARGET_NOT_REACHED')
        self.authorize_current_base(prefix='second-grant')
        self.reviewer.events = [TimeoutError('second grant review')]
        self.assertEqual(self.extend().terminal_state,'HALTED_CLIENT_TIMEOUT')
        events = state_packet(self.root)['budget_extensions']
        self.assertEqual(len(events),2)
        self.assertEqual(events[-1]['previous_current_round'],4)
        self.assertEqual(events[-1]['previous_review_profile_budgets'],{'structural_integrity':3})
        self.assertEqual(events[-1]['new_review_profile_budgets'],{'structural_integrity':5})
        self.assertNotEqual(events[0]['event_id'],events[1]['event_id'])


class VerticalBudgetTests(unittest.TestCase):
    setUp = vertical.RecoveryTests.setUp
    setup_run = vertical.RecoveryTests.setup_run
    snapshot = vertical.RecoveryTests.snapshot
    approve = vertical.RecoveryTests.approve
    start = vertical.RecoveryTests.start
    resume = vertical.RecoveryTests.resume
    authorize_current_base = vertical.RecoveryTests.authorize_current_base

    def test_extension_after_closeout_runs_full_new_sweep_and_corrective_acceptance(self):
        self.start()
        self.reviewer.events = [(5,'structural_integrity',self.p.feedback['feedback']),
            (6,'determinism',[]),(7,'operability',[])]
        self.assertEqual(self.resume().terminal_state,'TARGET_NOT_REACHED')
        findings = prepare_revision(self,11,finding_number=8)
        self.reviewer.events = [(8,'structural_integrity',findings),(9,'determinism',[]),(10,'operability',[])]
        result = resume_budget_exhausted_run(self.root,self.config,extend_review_budget=1,
            reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'PAUSED_DECISION');self.assertEqual(result.round_number,11)
        accept_revision(self)
        self.reviewer.events = [(12,'structural_integrity',[]),(13,'determinism',[]),(14,'operability',[])]
        self.assertEqual(self.resume().terminal_state,'PHASE_1_STABLE')
        self.assertEqual(state_packet(self.root)['review_profile_budgets'],
            {'structural_integrity':3,'determinism':3,'operability':3})
        self.assertEqual(self.editor.calls,2)
        self.assertEqual(len(list(self.root.rglob('acceptance.json'))),2)
        from whetstone.preservation_vertical import context
        self.assertEqual(context(self.root,self.config)['terminal'],'PHASE_1_STABLE')
