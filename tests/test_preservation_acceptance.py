from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import fcntl
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from test_preservation_contracts import Packet, ISSUE, APPROVAL
from whetstone.cli import main
from whetstone.hashing import draft_hash
from whetstone.preservation_acceptance import AcceptanceService
from whetstone.preservation_contracts import BridgeContractError, decode_json, read_artifact, read_ref, validate_reference_graph
from whetstone.preservation_inventory import build_inventory, sha256_bytes
from whetstone.preservation_proposals import ProposalStore, json_bytes
from whetstone.preservation_review import adopt_effect, review_proposal


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.service=AcceptanceService(self.root);self.calls=0

    def snapshot(self):
        return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def proposal(self, *, case=0, variant='clarified', noop=False, serious=False, resolved=True, bounded=False, round_number=1):
        if round_number == 1:
            self.packet=Packet(self.root,case,variant)
            (self.root/'spec.md').write_bytes(self.packet.raw)
        p=self.packet
        base=(self.root/'spec.md').read_bytes()
        after=base if noop else p.after
        folder=f'inputs-{round_number}';(self.root/folder).mkdir(exist_ok=True)
        base_ref=p.save(f'{folder}/seed.md',base)
        inventory=build_inventory(base,path=base_ref['path']);inv_ref=p.save(f'{folder}/inventory.json',inventory)
        feedback=deepcopy(p.feedback);feedback.update(round_number=round_number,draft_hash=draft_hash(base.decode()))
        if serious:feedback['feedback'][0]['normalized_severity']='major'
        feedback_ref=p.save(f'{folder}/feedback.json',feedback)
        surface=deepcopy(p.surface);surface.update(base_draft=base_ref,inventory=inv_ref,
            finding_sources=[{'artifact':feedback_ref,'feedback_ids':['fb-1']}],
            allowed_unit_ids=[u['unit_id'] for u in inventory['units']],allowed_sections=[s['section_id'] for s in inventory['sections']])
        if bounded:
            unit=next(u for u in inventory['units'] if u['kind']=='body' and u['normative'] and u['section_id'].endswith('["Delivery",1]]'))
            surface.update(allowed_sections=[unit['section_id']],allowed_unit_ids=[unit['unit_id']],
                frozen_sections=[s['section_id'] for s in inventory['sections'] if s['section_id'] not in ('[]',unit['section_id']) and s['parent_section_id']!='[]'])
        surface_ref=p.save(f'{folder}/surface.json',surface)
        store=ProposalStore(self.root)
        ticket=store.admit(surface_ref=surface_ref,effective_config={'phase':'phase_1','profile':'consistency'},
                           reviewer_feedback_refs=[feedback_ref],round_number=round_number,profile='consistency')
        summary=decode_json(read_ref(self.root,p.proposal['raw_response']))
        summary.update(round_number=round_number,draft_before_hash=draft_hash(base.decode()),draft_after_content=after.decode(),
                       resolved_issue_ids=[ISSUE] if resolved else [],unresolved_issue_ids=[] if resolved else [ISSUE])
        def editor(inputs):self.calls+=1;return json_bytes(summary)
        store.run_editor(ticket,editor)
        report=store.report(ticket)
        self.assertIsNotNone(report['proposal'],report)
        return report['proposal'],surface_ref,report,ticket

    def evidence(self,proposal,surface, *, base_lines=[9], output_lines=[9], disposition='reworded_equivalent', kind='attest_equivalence', types=['clarify'], name='effect.json'):
        return adopt_effect(self.service,proposal_ref=proposal,surface_ref=surface,output=name,kind=kind,
            base_lines=base_lines,output_lines=output_lines,disposition=disposition,change_types=types,finding_ids=['fb-1'],
            effect='The selected fixture requirement keeps its meaning.',rationale='Explicit scripted fixture effect review.',operator='fixture-operator',approve=True)

    def request(self,proposal,surface,evidence=[],name='request.json'):
        return self.service.prepare_request(proposal_ref=proposal,surface_ref=surface,evidence_refs=evidence,output=name)

    def test_pending_clarification_to_accepted_without_model_and_idempotent_replay(self):
        proposal,surface,prior,ticket=self.proposal(bounded=True)
        prior_bytes=read_ref(self.root,self.service.reference(f'{ticket.directory}/report.json'))
        effect=self.evidence(proposal,surface);request=self.request(proposal,surface,[effect])
        snapshot=self.snapshot();preview=self.service.accept(request,dry_run=True)
        self.assertEqual(preview.outcome,'eligible');self.assertEqual(snapshot,self.snapshot())
        result=self.service.accept(request)
        self.assertEqual(result.outcome,'accepted');self.assertEqual(self.calls,1)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.after)
        validate_reference_graph(self.root,result.acceptance,'preservation_bridge_acceptance')
        self.assertEqual(read_ref(self.root,self.service.reference(f'{ticket.directory}/report.json')),prior_bytes)
        self.assertEqual(prior['outcome'],'awaiting_operator_evidence')
        snapshot=self.snapshot();replay=AcceptanceService(self.root).accept(request)
        self.assertTrue(replay.replayed);self.assertEqual(replay.acceptance,result.acceptance)
        self.assertEqual(snapshot,self.snapshot());self.assertEqual(self.calls,1)
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'),1)
        self.assertFalse((self.root/'rounds/run_state.json').exists())

    def test_missing_evidence_rejects_then_new_request_can_accept_same_proposal(self):
        proposal,surface,prior,ticket=self.proposal()
        first=self.request(proposal,surface);rejected=self.service.accept(first)
        self.assertEqual(rejected.outcome,'rejected');self.assertIsNone(rejected.acceptance)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.raw)
        old=read_ref(self.root,rejected.report_ref)
        second=self.request(proposal,surface,[self.evidence(proposal,surface)],'request-2.json')
        self.assertEqual(decode_json(read_ref(self.root,second))['predecessor_report'],rejected.report_ref)
        result=self.service.accept(second);self.assertEqual(result.outcome,'accepted')
        self.assertIn('acceptance-attempt-2',result.acceptance['path'])
        self.assertEqual(read_ref(self.root,rejected.report_ref),old);self.assertEqual(self.calls,1)

    def test_stale_base_is_refused_before_acceptance_admission(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        (self.root/'spec.md').write_bytes(b'different authority\n');before=self.snapshot()
        for dry in (True,False):
            with self.assertRaisesRegex(BridgeContractError,'stale'):self.service.accept(request,dry_run=dry)
        self.assertEqual(before,self.snapshot());self.assertFalse(list(self.root.rglob('acceptance-attempt-*')))

    def test_changed_request_binding_or_effect_hash_fails_preflight(self):
        proposal,surface,_,_=self.proposal();effect=self.evidence(proposal,surface)
        request=self.request(proposal,surface,[effect]);value=decode_json(read_ref(self.root,request));value['finding_sources']=[]
        bad=self.packet.save('wrong-request.json',value)
        with self.assertRaisesRegex(BridgeContractError,'request/surface'):self.service.accept(bad)
        evidence=decode_json(read_ref(self.root,effect));evidence['materialized_draft_sha256']='0'*64
        (self.root/effect['path']).write_bytes(json_bytes(evidence))
        with self.assertRaisesRegex(BridgeContractError,'hash mismatch'):self.service.accept(request)
        self.assertFalse(list(self.root.rglob('acceptance.json')))

    def test_noop_can_commit_once_but_cannot_clear_serious_finding(self):
        proposal,surface,_,_=self.proposal(noop=True,serious=True)
        result=self.service.accept(self.request(proposal,surface));self.assertEqual(result.outcome,'rejected')
        self.assertIn('ordinary acceptance',str(result.report['failures']))
        self.assertFalse(list(self.root.rglob('acceptance.json')))

    def test_noop_marker_and_history_replay(self):
        proposal,surface,_,_=self.proposal(noop=True)
        request=self.request(proposal,surface);result=self.service.accept(request)
        marker=decode_json(read_ref(self.root,result.acceptance));self.assertTrue(marker['accepted_noop'])
        before=self.snapshot();self.service.accept(request);self.assertEqual(before,self.snapshot())
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.raw)

    def test_ordinary_unresolved_major_blocks_even_complete_preservation(self):
        proposal,surface,_,_=self.proposal(serious=True,resolved=False)
        request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        result=self.service.accept(request);self.assertEqual(result.outcome,'rejected')
        self.assertIn('ordinary acceptance',str(result.report['failures']))
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.raw)

    def test_trusted_stamp_is_not_applied_twice_and_summary_hash_uses_final_bytes(self):
        proposal,surface,prior,ticket=self.proposal(case=5,variant='raw_adjacent_edit')
        inv=read_artifact(self.root,decode_json(read_ref(self.root,proposal))['materialized_inventory'],'bridge_inventory')
        changed=[i+1 for i,(a,b) in enumerate(zip(self.packet.raw.splitlines(),self.packet.after.splitlines())) if a!=b]
        surface_value=read_artifact(self.root,surface,'bounded_change_surface');surface_value.update(weakening_allowed=True,allowed_change_types=['weaken'])
        surface=self.packet.save('weakening-surface.json',surface_value)
        effect=self.evidence(proposal,surface,base_lines=changed,output_lines=changed,disposition='operator_authorized_weakened',kind='authorize_weakening',types=['weaken'])
        result=self.service.accept(self.request(proposal,surface,[effect]))
        self.assertEqual(result.outcome,'accepted',result.report)
        final=(self.root/'spec.md').read_bytes();self.assertIn(b'0.18',final)
        self.assertEqual(decode_json((self.root/'rounds/round-1/editor_summary.json').read_bytes())['draft_after_hash'],draft_hash(final.decode()))
        snapshot=self.snapshot();self.service.accept(self.service.reference('request.json'));self.assertEqual(snapshot,self.snapshot())

    def test_historical_replay_does_not_reinstall_an_older_proposal(self):
        proposal,surface,_,_=self.proposal();first=self.request(proposal,surface,[self.evidence(proposal,surface)])
        accepted=self.service.accept(first)
        proposal2,surface2,_,_=self.proposal(noop=True,round_number=2)
        request2=self.request(proposal2,surface2,name='request-2.json');second=self.service.accept(request2)
        marker=decode_json(read_ref(self.root,second.acceptance));self.assertEqual(marker['previous_acceptance'],accepted.acceptance)
        before=self.snapshot();result=self.service.accept(first)
        self.assertTrue(result.historical);self.assertEqual(before,self.snapshot())
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'),2)

    def test_report_tampering_or_marker_chain_tampering_refuses_replay(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        result=self.service.accept(request);marker=decode_json(read_ref(self.root,result.acceptance))
        path=self.root/marker['report']['path'];path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(BridgeContractError,'hash mismatch'):self.service.accept(request)

    def test_fault_before_marker_keeps_authority_then_resumes_same_k(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        write=self.service._write
        def fail(path,raw):
            if path.endswith('/acceptance.json'):raise OSError('marker unavailable')
            return write(path,raw)
        with patch.object(self.service,'_write',side_effect=fail),self.assertRaises(OSError):self.service.accept(request)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.raw)
        self.assertFalse((self.root/'rounds/round-1/draft_after.md').exists())
        reports={str(p):p.read_bytes() for p in self.root.rglob('acceptance-attempt-*/report.json')}
        result=AcceptanceService(self.root).accept(request);self.assertEqual(result.outcome,'accepted')
        self.assertEqual(len(list(self.root.rglob('acceptance-attempt-*'))),1)
        self.assertEqual(reports,{str(p):p.read_bytes() for p in self.root.rglob('acceptance-attempt-*/report.json')})
        self.assertEqual(self.calls,1)

    def test_fault_after_marker_repairs_without_second_marker_or_model(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        with patch.object(self.service,'_repair',side_effect=OSError('mirror unavailable')),self.assertRaises(OSError):self.service.accept(request)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.raw)
        marker_path=next(self.root.rglob('acceptance.json'));marker_before=marker_path.read_bytes()
        terminal=decode_json(next(self.root.rglob('terminal_failure.json')).read_bytes());self.assertIsNotNone(terminal['acceptance'])
        dry_before=self.snapshot();self.assertTrue(AcceptanceService(self.root).accept(request,dry_run=True).replayed)
        self.assertEqual(dry_before,self.snapshot())
        result=AcceptanceService(self.root).accept(request)
        self.assertTrue(result.replayed);self.assertEqual(marker_path.read_bytes(),marker_before)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.after);self.assertEqual(self.calls,1)

    def test_fault_after_spec_install_reconciles_history_once(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        replace=self.service._replace
        def fail(path,raw):
            if path=='spec.history.md':raise OSError('history unavailable')
            return replace(path,raw)
        with patch.object(self.service,'_replace',side_effect=fail),self.assertRaises(OSError):self.service.accept(request)
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.after)
        self.service.accept(request);self.service.accept(request)
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'),1)

    def test_missing_report_persistence_leaves_no_marker_and_can_resume(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        write=self.service._write
        def fail(path,raw):
            if 'acceptance-attempt-' in path and path.endswith('/report.json'):raise OSError('report unavailable')
            return write(path,raw)
        with patch.object(self.service,'_write',side_effect=fail),self.assertRaises(OSError):self.service.accept(request)
        self.assertFalse(list(self.root.rglob('acceptance.json')))
        self.assertEqual(self.service.accept(request).outcome,'accepted')
        self.assertEqual(len(list(self.root.rglob('acceptance-attempt-*'))),1)

    def test_stale_predecessor_cannot_erase_prior_rejection(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface)
        rejected=self.service.accept(request)
        value=decode_json(read_ref(self.root,request));value['operator_evidence']=[self.evidence(proposal,surface)]
        bad=self.packet.save('stale-request.json',value)
        with self.assertRaisesRegex(BridgeContractError,'immediately preceding'):self.service.accept(bad)
        self.assertEqual(self.service.accept(request).report_ref,rejected.report_ref)

    def test_exclusive_writer_refuses_a_competing_invocation(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        with (self.root/'.preservation.lock').open('rb') as stream:
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.service.accept(request)
        self.assertFalse(list(self.root.rglob('acceptance.json')))

    def test_live_scheduler_root_is_refused_without_mutation(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        (self.root/'rounds/run_state.json').write_text('{}');before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'runtime adapter'):self.service.accept(request)
        self.assertEqual(before,self.snapshot())

    def test_operator_adoption_requires_explicit_approval_and_known_lines(self):
        proposal,surface,_,_=self.proposal();before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'line selection'):
            self.evidence(proposal,surface,base_lines=[999])
        self.assertEqual(before,self.snapshot())
        with self.assertRaisesRegex(BridgeContractError,'explicit approval'):
            adopt_effect(self.service,proposal_ref=proposal,output='no-approval.json',kind='attest_equivalence',base_lines=[9],output_lines=[9],
                         disposition='reworded_equivalent',change_types=['clarify'],finding_ids=['fb-1'],effect='same',rationale='fixture',operator='fixture',approve=False)
        self.assertEqual(before,self.snapshot())

    def test_admission_exists_before_actual_assessment_and_dry_run_creates_no_lock(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        (self.root/'.preservation.lock').unlink();before=self.snapshot()
        self.service.accept(request,dry_run=True);self.assertEqual(before,self.snapshot())
        original=self.service._assess
        def assess(value,admission_ref,issues):
            self.assertTrue((self.root/admission_ref['path']).exists())
            return original(value,admission_ref,issues)
        with patch.object(self.service,'_assess',side_effect=assess):
            self.assertEqual(self.service.accept(request).outcome,'accepted')

    def test_known_canonical_collision_is_refused_by_dry_run_without_writes(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        (self.root/'rounds/round-1/editor_summary.json').write_text('conflicting artifact')
        before=self.snapshot()
        with self.assertRaisesRegex(BridgeContractError,'conflicting canonical'):
            self.service.accept(request,dry_run=True)
        self.assertEqual(before,self.snapshot())
        self.assertFalse(list(self.root.rglob('acceptance.json')))

    def test_frozen_loss_rejects_then_explicit_new_surface_and_deletion_can_accept(self):
        proposal,surface,prior,ticket=self.proposal(case=1,variant='missing_field',bounded=True)
        original=read_artifact(self.root,proposal,'preservation_bridge_proposal')
        from whetstone.preservation_inventory import match_inventory_units
        old=read_artifact(self.root,read_artifact(self.root,original['admission'],'preservation_bridge_proposal_admission')['inventory'],'bridge_inventory')
        out=read_artifact(self.root,original['materialized_inventory'],'bridge_inventory')
        match=match_inventory_units(old,out)
        changed=[i+1 for i,u in enumerate(old['units']) if u['unit_id'] in match.unmatched_base]
        rewritten=next(n for n in changed if old['units'][n-1]['section_id'].endswith('["Delivery",1]]'))
        lost=next(n for n in changed if n!=rewritten)
        destination=next(i+1 for i,u in enumerate(out['units']) if u['unit_id'] in match.unmatched_output)
        eq=self.evidence(proposal,surface,base_lines=[rewritten],output_lines=[destination])
        request=self.request(proposal,surface,[eq]);first=self.service.accept(request)
        self.assertEqual(first.outcome,'rejected')
        surface_value=read_artifact(self.root,surface,'bounded_change_surface')
        surface_value.update(allowed_sections=[v['section_id'] for v in old['sections']],allowed_unit_ids=[u['unit_id'] for u in old['units']],
            frozen_sections=[],deletion_allowed=True,authorized_deletion_unit_ids=[old['units'][lost-1]['unit_id']],allowed_change_types=['clarify','reword','delete'])
        expanded=self.packet.save('expanded-surface.json',surface_value)
        eq2=self.evidence(proposal,expanded,base_lines=[rewritten],output_lines=[destination],name='effect-2.json')
        delete=self.evidence(proposal,expanded,base_lines=[lost],output_lines=[],disposition='authorized_deleted',kind='authorize_deletion',types=['delete'],name='deletion.json')
        second_request=self.request(proposal,expanded,[eq2,delete],name='request-2.json')
        accepted=self.service.accept(second_request);self.assertEqual(accepted.outcome,'accepted',accepted.report)
        self.assertEqual(read_artifact(self.root,first.report_ref,'current_runtime_preservation_bridge_report')['outcome'],'rejected')
        self.assertEqual(prior['outcome'],'rejected');self.assertEqual(self.calls,1)

    def test_conflicting_operator_mappings_reject_with_no_marker(self):
        proposal,surface,_,_=self.proposal();effect=self.evidence(proposal,surface)
        conflict=self.evidence(proposal,surface,output_lines=[10],name='conflict.json')
        result=self.service.accept(self.request(proposal,surface,[effect,conflict]))
        self.assertEqual(result.outcome,'rejected');self.assertIn('conflicting',str(result.report['failures']))
        self.assertFalse(list(self.root.rglob('acceptance.json')))

    def test_marker_linked_before_persistence_error_is_repaired_as_committed(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        write=self.service._write
        def fail(path,raw):
            ref=write(path,raw)
            if path.endswith('/acceptance.json'):raise OSError('after marker link')
            return ref
        with patch.object(self.service,'_write',side_effect=fail),self.assertRaises(OSError):self.service.accept(request)
        self.assertTrue(list(self.root.rglob('acceptance.json')))
        self.assertTrue(AcceptanceService(self.root).accept(request).replayed)
        self.assertEqual((self.root/'spec.history.md').read_text().count('Preservation acceptance:'),1)

    def test_pending_repair_blocks_new_proposal_admission(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        with patch.object(self.service,'_repair',side_effect=OSError('pending repair')),self.assertRaises(OSError):self.service.accept(request)
        with self.assertRaisesRegex(BridgeContractError,'pending|differs'):
            self.proposal(noop=True,round_number=2)
        self.assertFalse((self.root/'rounds/round-2/preservation').exists())
        self.assertEqual(self.calls,1)

    def test_changed_authority_during_commit_is_not_overwritten(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        write=self.service._write
        def mutate(path,raw):
            ref=write(path,raw)
            if 'acceptance-attempt-' in path and path.endswith('/report.json'):
                (self.root/'spec.md').write_bytes(b'external update')
            return ref
        with patch.object(self.service,'_write',side_effect=mutate),self.assertRaisesRegex(BridgeContractError,'current base changed'):
            self.service.accept(request)
        self.assertFalse(list(self.root.rglob('acceptance.json')))
        self.assertEqual((self.root/'spec.md').read_bytes(),b'external update')

    def test_failure_sidecar_write_failure_propagates_without_acceptance(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        write=self.service._write
        def fail(path,raw):
            if path.endswith(('/acceptance.json','/terminal_failure.json')):raise OSError('disk full')
            return write(path,raw)
        with patch.object(self.service,'_write',side_effect=fail),self.assertRaisesRegex(OSError,'disk full'):self.service.accept(request)
        self.assertFalse(list(self.root.rglob('acceptance.json')))
        self.assertEqual((self.root/'spec.md').read_bytes(),self.packet.raw)

    def test_out_of_scope_serious_finding_still_obeys_global_ordinary_gate(self):
        from whetstone.preservation_round_evidence import validate_round_evidence
        p=Packet(self.root)
        summary=decode_json(read_ref(self.root,p.proposal['normal_round_evidence']['editor_summary']))
        feedback=deepcopy(p.feedback)
        extra=deepcopy(feedback['feedback'][0]);extra.update(feedback_id='fb-other',issue_id='iss_'+'b'*16,normalized_severity='major',in_scope=False)
        feedback['feedback'].append(extra)
        self.assertFalse(validate_round_evidence(p.raw,p.after,p.admission,[feedback],summary))

    def test_unresolved_minor_history_survives_noop_resolution_claim(self):
        proposal,surface,_,_=self.proposal(resolved=False)
        self.service.accept(self.request(proposal,surface,[self.evidence(proposal,surface)]))
        proposal2,surface2,_,_=self.proposal(noop=True,round_number=2)
        self.service.accept(self.request(proposal2,surface2,name='request-2.json'))
        remaining=decode_json((self.root/'rounds/round-2/unresolved_issues.json').read_bytes())
        self.assertEqual([i['issue_id'] for i in remaining['unresolved_issues']],[ISSUE])

    def test_external_edit_during_mirror_repair_is_not_overwritten(self):
        proposal,surface,_,_=self.proposal();request=self.request(proposal,surface,[self.evidence(proposal,surface)])
        write=self.service._write
        def mutate(path,raw):
            ref=write(path,raw)
            if path=='rounds/round-1/editor_summary.json':
                (self.root/'spec.md').write_bytes(b'external mirror edit')
            return ref
        with patch.object(self.service,'_write',side_effect=mutate),self.assertRaisesRegex(BridgeContractError,'authority/history differs'):
            self.service.accept(request)
        self.assertTrue(list(self.root.rglob('acceptance.json')))
        self.assertEqual((self.root/'spec.md').read_bytes(),b'external mirror edit')
        with self.assertRaisesRegex(BridgeContractError,'authority/history differs'):
            AcceptanceService(self.root).accept(request)

    def test_cli_review_request_dry_run_accept_and_replay(self):
        proposal,surface,_,_=self.proposal();base=['--root',str(self.root)]
        def cli(args):
            out=io.StringIO()
            with redirect_stdout(out):code=main(args)
            return code,json.loads(out.getvalue())
        code,review=cli(['preservation-review',*base,'--proposal',proposal['path']]);self.assertEqual(code,0)
        self.assertEqual(review['base'][8]['line'],9)
        code,effect=cli(['preservation-attest',*base,'--proposal',proposal['path'],'--output','cli-effect.json',
            '--kind','attest_equivalence','--base-lines','9','--output-lines','9','--disposition','reworded_equivalent',
            '--change-type','clarify','--finding','inputs-1/feedback.json::fb-1','--effect','same retry delay','--rationale','scripted fixture','--operator','fixture','--approve'])
        self.assertEqual(code,0,effect)
        code,request=cli(['preservation-request',*base,'--proposal',proposal['path'],'--evidence','cli-effect.json','--output','cli-request.json'])
        self.assertEqual(code,0,request);before=self.snapshot()
        code,preview=cli(['preservation-accept',*base,'--request','cli-request.json','--dry-run'])
        self.assertEqual(code,0,preview);self.assertEqual(before,self.snapshot())
        code,result=cli(['preservation-accept',*base,'--request','cli-request.json']);self.assertEqual(code,0,result)
        self.assertEqual(result['outcome'],'accepted');self.assertEqual(self.calls,1)


if __name__=='__main__':unittest.main()
