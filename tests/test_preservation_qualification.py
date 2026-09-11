"""Joined operator and consumer qualification, using fictional specs and scripted clients."""
import unittest
from unittest.mock import patch

import test_preservation_acceptance as acceptance_fixtures
import test_preservation_maintenance as maintenance_fixtures
import test_preservation_runtime as runtime_fixtures
from test_preservation_contracts import Packet
from whetstone.apply_back import apply_back
from whetstone.hashing import draft_hash
from whetstone.live_phase2 import LivePhase2Runner
from whetstone.preservation_acceptance import AcceptanceService
from whetstone.preservation_contracts import BridgeContractError, decode_json, read_ref
from whetstone.preservation_proposals import ProposalStore, json_bytes
from whetstone.preservation_review import adopt_effect, review_proposal
from whetstone.preservation_runtime import state_packet
from whetstone.scheduler import profile_names_for_phase


class OperatorJourneyTests(unittest.TestCase):
    setUp = acceptance_fixtures.AcceptanceTests.setUp
    snapshot = acceptance_fixtures.AcceptanceTests.snapshot

    def journey(self, case, variant, groups, **permissions):
        p = Packet(self.root, case, variant, **permissions)
        if 'delete' in p.surface['allowed_change_types']:
            p.surface['authorized_deletion_unit_ids'] = [u['unit_id'] for u in p.inventory['units']]
        if 'supersede' in p.surface['allowed_change_types']:
            p.surface['authorized_supersession_unit_ids'] = [u['unit_id'] for u in p.inventory['units']]
        surface = p.save('journey-surface.json', p.surface)
        (self.root/'spec.md').write_bytes(p.raw)
        store = ProposalStore(self.root)
        ticket = store.admit(surface_ref=surface, effective_config={'phase':'phase_1','profile':'consistency'},
            reviewer_feedback_refs=[p.feedback_ref], round_number=1, profile='consistency')
        def editor(inputs):
            self.calls += 1
            return read_ref(self.root, p.proposal['raw_response'])
        store.run_editor(ticket, editor)
        preliminary = store.report(ticket)
        self.assertEqual(preliminary['outcome'], 'awaiting_operator_evidence')
        proposal = preliminary['proposal']
        before = self.snapshot()
        display = review_proposal(self.service, proposal)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(''.join(row['text'] for row in display['base']).encode(), p.raw)
        self.assertEqual(''.join(row['text'] for row in display['output']).encode(), p.after)
        effects = []
        evidence = []
        for index, (old, new, disposition, kind, types, effect) in enumerate(groups):
            # Operator-facing line selections only: the helper fills all hashes and unit IDs.
            ref = adopt_effect(self.service, proposal_ref=proposal, surface_ref=surface,
                output=f'effect-{index}.json', base_lines=old, output_lines=new,
                disposition=disposition, kind=kind, change_types=types, finding_ids=['fb-1'],
                effect=effect, rationale='Scripted operator explicitly reviews this exact toy effect.',
                operator='qualification-fixture', approve=True)
            evidence.append(ref)
            record = decode_json(read_ref(self.root, ref))
            self.assertEqual(record['effect'], effect)
            self.assertEqual([e['base_unit_id'] for e in record['correspondence']],
                [display['base'][n-1]['unit_id'] for n in old])
            successors = [display['output'][n-1]['unit_id'] for n in new]
            for entry in record['correspondence']:
                self.assertEqual(entry['successor_unit_ids'], successors)
            if kind == 'attest_addition':self.assertEqual(record['added_unit_ids'], successors)
            effects.append(record)
        request = self.service.prepare_request(proposal_ref=proposal, surface_ref=surface,
            evidence_refs=evidence, output='request.json')
        before = self.snapshot()
        self.assertEqual(self.service.accept(request, dry_run=True).outcome, 'eligible')
        self.assertEqual(before, self.snapshot())
        result = self.service.accept(request)
        self.assertEqual(result.outcome, 'accepted')
        self.assertEqual((self.root/'spec.md').read_bytes(), p.after)
        self.assertEqual(self.calls, 1)
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'), 1)
        before = self.snapshot()
        self.assertTrue(AcceptanceService(self.root).accept(request).replayed)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.calls, 1)
        # Retain an explicit, machine-readable observation for artifact harnesses.
        self.observation = {'variant':variant, 'display':display, 'adopted_effects':effects,
            'operator_interactions':4+len(groups), 'editor_calls':self.calls,
            'acceptance_editor_calls':0, 'acceptance':result.acceptance}

    def test_clarification(self):
        self.journey(0, 'clarified', [([9],[9],'reworded_equivalent','attest_equivalence',['clarify'],
            'Clarify the minimum retry delay without changing it.')])

    def test_reflow(self):
        self.journey(2, 'reflowed', [([7],[7,8],'reworded_equivalent','attest_equivalence',['reword'],
            'Both retry obligations survive in two lines.')], max_changed_normative_units=1)

    def test_supersession(self):
        self.journey(6, 'consolidated', [([5,6],[5],'superseded','attest_supersession',['supersede'],
            'The single successor preserves both access checks.')], allowed_change_types=['supersede'],
            max_changed_normative_units=2)

    def test_deletion_with_explicit_duplicate_selection(self):
        self.journey(2, 'one_duplicate_removed', [
            ([5],[5],'preserved','attest_equivalence',[], 'Retain the first duplicate.'),
            ([6],[],'authorized_deleted','authorize_deletion',['delete'], 'Delete only the second duplicate.')],
            allowed_change_types=['delete'], deletion_allowed=True)

    def test_addition(self):
        self.journey(3, 'harmless_addition', [([], [11], None, 'attest_addition',['add'],
            'Add observability without reducing existing storage or retention obligations.')], allowed_change_types=['add'])

    def test_weakening(self):
        self.journey(3, 'weakened_retention', [([6],[6],'operator_authorized_weakened','authorize_weakening',['weaken'],
            'Explicitly relax mandatory retention to a recommendation.')], allowed_change_types=['weaken'], weakening_allowed=True)

    def test_added_exception_discloses_weakening_of_verbatim_requirement(self):
        self.journey(3, 'maintenance_exception', [
            ([5],[5],'operator_authorized_weakened','authorize_weakening',['weaken'],
                'The exception permits acknowledgment before storage during maintenance despite unchanged base wording.'),
            ([],[11],None,'attest_addition',['add'],
                'Add the maintenance exception with its separately approved weakening of the storage requirement.')],
            allowed_change_types=['add','weaken'], weakening_allowed=True)


class ConsumerJourneyTests(unittest.TestCase):
    setUp = runtime_fixtures.RuntimeTests.setUp
    snapshot = runtime_fixtures.RuntimeTests.snapshot
    setup_run = runtime_fixtures.RuntimeTests.setup_run
    stable = maintenance_fixtures.MaintenanceTests.stable

    def converge(self, **kwargs):
        self.stable(**kwargs)
        start = self.handoff['current_round']+1
        self.reviewer.events = [(start+i,p,[]) for i,p in enumerate(profile_names_for_phase(self.config.review_profile_set,'phase_2'))]
        self.phase2 = LivePhase2Runner(self.root,self.config,reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(self.phase2.run().terminal_state, 'CONVERGED')

    def test_crlf_verified_convergence_to_dry_live_and_repeated_apply_back(self):
        self.converge(versioned=True, crlf=True)
        source = self.root/'source.md';source.write_bytes(self.base)
        expected = self.base.replace(b'0.17',b'1.0')
        self.assertEqual((self.root/'spec.md').read_bytes(), expected)
        calls = (self.reviewer.calls,self.editor.calls)
        before = self.snapshot()
        dry = apply_back(source_path=source,run_root=self.root,expected_source_hash=draft_hash(self.base.decode()))
        self.assertEqual(before,self.snapshot())
        self.assertFalse(dry.applied)
        applied = apply_back(source_path=source,run_root=self.root,apply=True,approve=True,
            expected_source_hash=draft_hash(self.base.decode()))
        self.assertTrue(applied.applied)
        self.assertEqual(source.read_bytes(),expected)
        self.assertEqual(applied.source_after_hash,applied.final_draft_hash)
        source.write_bytes(expected.replace(b'\r\n', b'\n'))
        restored = apply_back(source_path=source,run_root=self.root,apply=True,approve=True)
        self.assertTrue(restored.applied)
        self.assertEqual(source.read_bytes(),expected)
        repeat = apply_back(source_path=source,run_root=self.root,apply=True,approve=True,
            expected_source_hash=applied.source_after_hash)
        self.assertFalse(repeat.changed);self.assertFalse(repeat.applied)
        self.assertEqual((self.reviewer.calls,self.editor.calls),calls)

    def test_false_convergence_cannot_apply_unverified_accepted_phase1(self):
        runtime_fixtures.RuntimeTests.pending(self)
        runtime_fixtures.RuntimeTests.approve(self)
        state = state_packet(self.root);state['terminal_state']='CONVERGED'
        (self.root/'rounds/run_state.json').write_bytes(json_bytes(state))
        source = self.root/'source.md';source.write_bytes(self.p.raw)
        before = self.snapshot()
        with self.assertRaises(BridgeContractError):
            apply_back(source_path=source,run_root=self.root,apply=True,approve=True)
        self.assertEqual(before,self.snapshot())


    def test_declaration_and_manifest_tampering_blocks_dry_live_consumers_and_status(self):
        from whetstone.status import read_status
        self.converge()
        source = self.root/'source.md';source.write_bytes(self.base)
        for path in (self.config.declaration_path, self.root/'rounds/rubric_manifest.json'):
            original = path.read_bytes()
            changed = original.replace(b'accepted',b'rejected') if path.suffix == '.md' else original.replace(b'standard-v1',b'exploratory-v1')
            self.assertNotEqual(original,changed)
            path.write_bytes(changed)
            before = self.snapshot()
            for apply in (False,True):
                with self.subTest(path=path,apply=apply), self.assertRaises(BridgeContractError):
                    apply_back(source_path=source,run_root=self.root,apply=apply,approve=True,allow_non_converged=True)
            status = read_status(root=self.root,config=self.config)
            self.assertFalse(status['apply_back']['available'])
            self.assertEqual(status['next_action'],'inspect_and_repair')
            self.assertEqual(before,self.snapshot())
            path.write_bytes(original)
        self.assertTrue(read_status(root=self.root,config=self.config)['apply_back']['available'])

    def test_source_change_during_review_is_not_overwritten(self):
        # Explicit accepted-output manual recovery still checks the external source.
        runtime_fixtures.RuntimeTests.pending(self)
        runtime_fixtures.RuntimeTests.approve(self)
        source = self.root/'source.md';source.write_bytes(self.p.raw)
        import whetstone.apply_back as module
        original = module._unified_diff
        def concurrent_edit(**kwargs):
            source.write_bytes(b'External edit during review.\n')
            return original(**kwargs)
        with patch.object(module,'_unified_diff',side_effect=concurrent_edit):
            with self.assertRaisesRegex(ValueError,'source changed'):
                apply_back(source_path=source,run_root=self.root,apply=True,approve=True,allow_non_converged=True)
        self.assertEqual(source.read_bytes(),b'External edit during review.\n')
        self.assertFalse((self.root/'rounds/apply_back_review.json').exists())

    def test_accepted_phase1_cannot_publish_accepted_phase2_declaration(self):
        runtime_fixtures.RuntimeTests.pending(self)
        runtime_fixtures.RuntimeTests.approve(self)
        runner = LivePhase2Runner(self.root,self.config)
        before = self.snapshot()
        with self.assertRaises(BridgeContractError):
            runner._write_declaration(draft_hash_value=state_packet(self.root)['current_draft_hash'],
                reviewer_final_status='accepted',declaration_status='accepted',blocker_count=0,major_count=0,rubric_gap_count=0)
        self.assertEqual(before,self.snapshot())


class GrantJourneyTests(unittest.TestCase):
    import test_preservation_budget as fixtures
    setUp = fixtures.BudgetTests.setUp
    setup_run = fixtures.BudgetTests.setup_run
    snapshot = fixtures.BudgetTests.snapshot
    approve = fixtures.BudgetTests.approve
    start = fixtures.BudgetTests.start
    authorize_current_base = fixtures.BudgetTests.authorize_current_base
    extend = fixtures.BudgetTests.extend

    def test_full_horizontal_grant_editor_retry_then_verified_handoff(self):
        from test_preservation_budget import prepare_revision, accept_revision
        from test_preservation_continuation import ScriptedReviewer
        from whetstone.resume import resume_halted_run
        from whetstone.preservation_maintenance import enter_phase2
        profiles = ['structural_integrity','determinism','operability']
        self.start(serious=True,budgets={p:1 for p in profiles})
        self.authorize_current_base()
        self.reviewer = ScriptedReviewer(self.root,self.p.feedback,
            [(2,profiles[1],[]),(3,profiles[2],[]),(4,profiles[0],self.p.feedback['feedback'])])
        result = resume_halted_run(self.root,self.config,continue_run=True,
            reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'TARGET_NOT_REACHED')
        findings = prepare_revision(self,5)
        response = self.editor.response
        self.editor.response = TimeoutError('appended Editor timeout')
        self.reviewer.events = [(5,profiles[0],findings)]
        self.assertEqual(self.extend().terminal_state,'HALTED_CLIENT_TIMEOUT')
        calls = self.reviewer.calls
        self.editor.response = response
        self.assertEqual(self.extend().terminal_state,'PAUSED_DECISION')
        self.assertEqual(self.reviewer.calls,calls)
        accept_revision(self)
        self.authorize_current_base(prefix='post-grant')
        self.reviewer.events = [(6,profiles[1],[]),(7,profiles[2],[]),(8,profiles[0],[])]
        result = resume_halted_run(self.root,self.config,continue_run=True,
            reviewer_client=self.reviewer,editor_client=self.editor)
        self.assertEqual(result.terminal_state,'PHASE_1_STABLE')
        self.assertEqual(self.reviewer.events,[])
        self.assertEqual(state_packet(self.root)['current_round'],8)
        self.assertEqual(len(state_packet(self.root)['budget_extensions']),1)
        calls = (self.reviewer.calls,self.editor.calls)
        enter_phase2(self.root,self.config)
        self.assertEqual((self.reviewer.calls,self.editor.calls),calls)
        self.assertEqual(state_packet(self.root)['phase_2_rounds_completed'],0)


class OriginJourneyTests(unittest.TestCase):
    def test_editor_and_supplied_unchanged_outputs_use_normal_admission(self):
        from whetstone.preservation_runtime import acceptance_service, guard_consumer
        for supplied in (False, True):
            with self.subTest(supplied=supplied):
                case = runtime_fixtures.RuntimeTests()
                case.setUp()
                try:
                    case.setup_run()
                    summary = decode_json(case.editor.response)
                    summary.update(draft_after_content=case.p.raw.decode(),draft_after_hash=draft_hash(case.p.raw.decode()))
                    case.editor.response = json_bytes(summary)
                    result = case.runner.run_round(round_number=1,profile='structural_integrity',
                        draft_after=case.p.raw if supplied else None,apply=True)
                    self.assertTrue(result.accepted)
                    service = acceptance_service(case.root)
                    chain = service._chain()
                    self.assertEqual(len(chain),1)
                    _, proposal, admission = service._proposal_directory(chain[0][1]['proposal'])
                    self.assertEqual(admission['origin'],'supplied_revision' if supplied else 'editor')
                    self.assertTrue(chain[0][1]['accepted_noop'])
                    self.assertEqual((case.root/'spec.md').read_bytes(),case.p.raw)
                    self.assertEqual(case.editor.calls,1)
                    guard_consumer(case.root,case.config)
                finally:
                    case.doCleanups()


class DestructiveRewriteTests(unittest.TestCase):
    def test_padding_does_not_hide_frozen_schema_loss_or_erase_pending_effect(self):
        import test_preservation_proposals as fixtures
        from whetstone.preservation_inventory import build_inventory
        case = fixtures.ProposalStoreTests()
        case.setUp()
        try:
            p = case.packet(1,'missing_field',bounded=True)
            padding = b'\\n<!-- Preserved fixture padding: '+b'x'*65536+b' -->\\n'
            p.raw += padding;p.after += padding
            self.assertGreater(len(p.after)/len(p.raw),0.999)
            p.base_ref = p.save('seed.md',p.raw)
            p.inventory = build_inventory(p.raw,path='seed.md')
            p.inventory_ref = p.save('inventory.json',p.inventory)
            p.feedback['draft_hash'] = draft_hash(p.raw.decode())
            p.feedback_ref = p.save('feedback.json',p.feedback)
            allowed = next(u for u in p.inventory['units'] if u['kind']=='body' and u['normative'] and u['section_id'].endswith('["Delivery",1]]'))
            p.surface.update(base_draft=p.base_ref,inventory=p.inventory_ref,allowed_unit_ids=[allowed['unit_id']],
                finding_sources=[{'artifact':p.feedback_ref,'feedback_ids':['fb-1']}])
            p.surface_ref = p.save('surface.json',p.surface)
            (case.root/'spec.md').write_bytes(p.raw)
            ticket = case.admit(p)
            response = case.response(p,draft_before_hash=draft_hash(p.raw.decode()),draft_after_hash=draft_hash(p.after.decode()))
            case.store.capture_response(ticket,response)
            report = case.store.report(ticket)
            self.assertEqual(report['outcome'],'rejected')
            self.assertIn('allowed_surface_overrun',{f['category'] for f in report['failures']})
            lost = next(u['unit_id'] for u in p.inventory['units']
                if p.raw[u['byte_start']:u['byte_end']].startswith(b'idempotency_key: string'))
            self.assertIn(lost,{uid for f in report['failures'] for uid in f['affected_unit_ids']})
            self.assertEqual(next(d for d in report['unit_dispositions'] if d['base_unit_id']==lost)['successor_unit_ids'],[])
            self.assertTrue(report['pending_obligations'])
            case.assert_coverage(p,report)
        finally:
            case.doCleanups()


class CloseoutConsumerTests(unittest.TestCase):
    import test_preservation_phase2_closeout as fixtures
    setUp = fixtures.CloseoutTests.setUp
    setup_run = fixtures.CloseoutTests.setup_run
    snapshot = fixtures.CloseoutTests.snapshot
    stable = fixtures.CloseoutTests.stable
    authorize_current_base = fixtures.CloseoutTests.authorize_current_base
    budget_stop = fixtures.CloseoutTests.budget_stop
    closeout = fixtures.CloseoutTests.closeout

    def test_incomplete_closeout_cannot_claim_convergence_then_retry_can_apply(self):
        self.budget_stop()
        self.reviewer.events.insert(1,TimeoutError('closeout consumer qualification'))
        self.assertEqual(self.closeout().terminal_state,'HALTED_CLIENT_TIMEOUT')
        source = self.root/'source.md';source.write_bytes(self.base)
        state_path = self.root/'rounds/run_state.json'
        original = state_path.read_bytes()
        state = decode_json(original);state['terminal_state']='CONVERGED'
        state_path.write_bytes(json_bytes(state))
        before = self.snapshot()
        for apply in (False,True):
            with self.assertRaises(BridgeContractError):
                apply_back(source_path=source,run_root=self.root,apply=apply,approve=True,allow_non_converged=True)
        self.assertEqual(before,self.snapshot())
        state_path.write_bytes(original)
        self.assertEqual(self.closeout().terminal_state,'CONVERGED')
        calls = (self.reviewer.calls,self.editor.calls)
        result = apply_back(source_path=source,run_root=self.root,apply=True,approve=True)
        self.assertTrue(result.applied)
        self.assertEqual(source.read_bytes(),(self.root/'spec.md').read_bytes())
        self.assertEqual((self.reviewer.calls,self.editor.calls),calls)


class CLIRuntimeJourneyTests(unittest.TestCase):
    setUp = runtime_fixtures.RuntimeTests.setUp
    setup_run = runtime_fixtures.RuntimeTests.setup_run
    snapshot = runtime_fixtures.RuntimeTests.snapshot

    def test_pending_effect_accept_status_resume_and_handoff_through_cli(self):
        import io
        import json
        from contextlib import redirect_stdout
        from whetstone.cli import main
        from whetstone.resume import resume_halted_run
        from whetstone.preservation_runtime import readback
        from whetstone.preservation_maintenance import enter_phase2
        from test_preservation_continuation import ContinuationTests, ScriptedReviewer
        runtime_fixtures.RuntimeTests.pending(self)
        proposal = readback(self.root,self.config)['latest_proposal']['path']
        base = ['--root',str(self.root)]
        def cli(command, *args):
            output = io.StringIO()
            with patch('whetstone.cli.load_config',return_value=self.config), redirect_stdout(output):
                code = main([command,*base,*args])
            packet = json.loads(output.getvalue())
            self.assertEqual(code,0,packet)
            return packet
        display = cli('preservation-review','--proposal',proposal)
        self.assertIn('retry',display['base'][8]['text'])
        cli('preservation-attest','--proposal',proposal,'--output','cli-effect.json',
            '--kind','attest_equivalence','--base-lines','9','--output-lines','9',
            '--disposition','reworded_equivalent','--change-type','clarify','--finding','fb-1',
            '--effect','The retry delay remains at least thirty seconds.','--rationale','Explicit toy effect review.',
            '--operator','qualification-fixture','--approve')
        cli('preservation-request','--proposal',proposal,'--evidence','cli-effect.json','--output','cli-request.json')
        calls = (self.reviewer.calls,self.editor.calls)
        before = self.snapshot()
        self.assertEqual(cli('preservation-accept','--request','cli-request.json','--dry-run')['outcome'],'eligible')
        self.assertEqual(before,self.snapshot())
        self.assertEqual(cli('preservation-accept','--request','cli-request.json')['outcome'],'accepted')
        self.assertEqual((self.reviewer.calls,self.editor.calls),calls)
        self.assertEqual(state_packet(self.root)['current_round'],1)
        ContinuationTests.authorize_current_base(self)
        before = self.snapshot()
        status = cli('status','--format','json')
        self.assertTrue(status['resume']['eligible'])
        self.assertTrue(cli('resume','--continue','--dry-run')['continue'])
        self.assertEqual(before,self.snapshot())
        self.reviewer = ScriptedReviewer(self.root,self.p.feedback,
            [(2,'structural_integrity',[]),(3,'determinism',[]),(4,'operability',[])])
        def scripted_resume(root,config,**kwargs):
            return resume_halted_run(root,config,reviewer_client=self.reviewer,editor_client=self.editor,**kwargs)
        with patch('whetstone.cli.resume_halted_run',side_effect=scripted_resume):
            self.assertEqual(cli('resume','--continue')['terminal_state'],'PHASE_1_STABLE')
        self.assertEqual(self.editor.calls,calls[1])
        self.assertTrue(cli('status','--format','json')['ready_for_phase_2'])
        enter_phase2(self.root,self.config)
        source = self.root/'source.md';source.write_bytes(self.p.raw)
        before = self.snapshot()
        self.assertFalse(apply_back(source_path=source,run_root=self.root).applied)
        self.assertEqual(before,self.snapshot())
