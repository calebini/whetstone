from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from test_preservation_contracts import Packet, CORPUS, ISSUE
from whetstone.contracts import validate_artifact
from whetstone.hashing import draft_hash
from whetstone.preservation_contracts import BridgeContractError, decode_json, read_ref, validate_proposal_bindings, validate_reference_graph
from whetstone.preservation_inventory import build_inventory, match_inventory_units
from whetstone.preservation_materialization import MaterializationError, comparison_inventory, materialize_proposal, verify_materialization
from whetstone.preservation_proposals import ProposalStore, json_bytes


class MaterializationTests(unittest.TestCase):
    def materialize(self, base, raw, **kwargs):
        return materialize_proposal(base, raw, phase=kwargs.pop('phase', 'phase_1'),
                                    origin=kwargs.pop('origin', 'editor'), ordinary_eligible=kwargs.pop('eligible', True), **kwargs)

    def test_byte_spans_status_demotion_and_only_selected_values_change(self):
        base = '# Café 0.17\r\nStatus: Accepted\r\n\r\n## Rules\nA MUST hold.\r'.encode()
        raw = base.replace(b'A MUST hold.', b'A MUST always hold.')
        result = self.materialize(base, raw)
        self.assertEqual(result.content, raw.replace(b'0.17', b'0.18').replace(b'Accepted', b'Draft'))
        self.assertEqual([c['kind'] for c in result.transformations[0]['parameters']['changes']], ['version', 'status'])
        verify_materialization(base, raw, result.content, result.transformations, phase='phase_1', origin='editor', ordinary_eligible=True)
        for change in result.transformations[0]['parameters']['changes']:
            self.assertEqual(base[change['base_byte_start']:change['base_byte_end']], change['before'].encode())
            self.assertEqual(raw[change['input_byte_start']:change['input_byte_end']], change['before'].encode())

    def test_noop_ineligible_and_missing_anchors_have_no_transform(self):
        for base, raw, eligible in [(b'# Spec 0.17\nA\n', b'# Spec 0.17\nA\n', True),
                                     (b'# Spec 0.17\nA\n', b'# Spec 0.17\nB\n', False),
                                     (b'# Spec\nA\n', b'# Spec\nB\n', True)]:
            self.assertEqual(self.materialize(base, raw, eligible=eligible).transformations, [])

    def test_phase2_entry_and_editor_same_bytes_have_different_authority(self):
        base=(CORPUS/'06_parser_and_versions/base.md').read_bytes()
        final=(CORPUS/'06_parser_and_versions/phase2_materialized.md').read_bytes()
        result=self.materialize(base,base,phase='phase_2',origin='phase2_entry')
        self.assertEqual(result.content,final)
        with self.assertRaisesRegex(MaterializationError,'selected version anchor'):
            self.materialize(base,final,phase='phase_2')
        before=build_inventory(base,path='base.md');actual=build_inventory(final,path='out.md')
        matched=match_inventory_units(before,comparison_inventory(base,actual))
        self.assertEqual(len(matched.pairs),len(before['units']))
        self.assertTrue(set(dict(matched.pairs).values()) <= {u['unit_id'] for u in actual['units']})

    def test_adjacent_editor_change_is_not_exempt_and_tampered_transform_rejects(self):
        base=b'# Spec 0.17\n## Rules\nA MUST hold.\n'
        raw=b'# Changed Spec 0.17\n## Rules\nA MAY hold.\n'
        result=self.materialize(base,raw)
        view=comparison_inventory(raw,build_inventory(result.content,path='out.md'))
        self.assertTrue(match_inventory_units(build_inventory(base,path='base.md'),view).unmatched_base)
        bad=deepcopy(result.transformations);bad[0]['parameters']['changes'][0]['after']='9.9'
        with self.assertRaisesRegex(MaterializationError,'pinned algorithm'):
            verify_materialization(base,raw,result.content,bad,phase='phase_1',origin='editor',ordinary_eligible=True)

    def test_fences_are_not_anchors_and_ambiguity_rejects(self):
        base=b'```\n# Fake 9.9\n```\n# Real 0.17\nBody\n'
        self.assertIn(b'# Fake 9.9', self.materialize(base,base+b'Extra\n').content)
        for base in (b'# Spec 1.0 and 2.0\n', b'# Spec 0.17\nStatus: Accepted\nStatus: Accepted\n'):
            with self.assertRaisesRegex(MaterializationError,'ambiguous'):
                self.materialize(base,base+b'Extra\n')

    def test_maintenance_cannot_change_content_and_version_changes_always_reject(self):
        base=b'# Spec 0.17\nA\n'
        for origin in ('orchestrator_noop','phase2_entry'):
            with self.assertRaisesRegex(MaterializationError,'maintenance raw'):
                self.materialize(base,base+b'B\n',origin=origin,phase='phase_2')
        with self.assertRaisesRegex(MaterializationError,'selected version anchor'):
            self.materialize(base,base.replace(b'0.17',b'0.18'),eligible=False)
        with self.assertRaisesRegex(MaterializationError,'status anchor'):
            self.materialize(base+b'Status: Draft\n',base+b'Status: Accepted\n')


class ProposalStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.store=ProposalStore(self.root)

    def packet(self, *args, bounded=False, **kwargs):
        p=Packet(self.root,*args,**kwargs)
        (self.root/'spec.md').write_bytes(p.raw)
        if bounded:
            unit=next(u for u in p.inventory['units'] if u['kind']=='body' and u['normative']
                      and u['section_id'].endswith('["Delivery",1]]'))
            p.surface.update(allowed_sections=[unit['section_id']],allowed_unit_ids=[unit['unit_id']],
                             frozen_sections=[s['section_id'] for s in p.inventory['sections']
                                              if s['section_id'] not in ('[]',unit['section_id']) and s['parent_section_id'] != '[]'])
            p.surface_ref=p.save('surface.json',p.surface)
        return p

    def admit(self,p,**kwargs):
        return self.store.admit(surface_ref=p.surface_ref,effective_config={'phase':'phase_1','profile':'consistency','budget':3},
                                reviewer_feedback_refs=[p.feedback_ref],round_number=1,profile='consistency',**kwargs)

    def response(self,p,raw=None,**changes):
        summary=decode_json(read_ref(self.root,p.proposal['raw_response']))
        summary.update(draft_after_content=(p.after if raw is None else raw).decode(),**changes)
        return json.dumps(summary,ensure_ascii=True,indent=3).encode()+b' \n'

    def assert_coverage(self,p,report):
        out=decode_json(read_ref(self.root,report['materialized_inventory']))
        self.assertEqual([e['base_unit_id'] for e in report['unit_dispositions']],[u['unit_id'] for u in p.inventory['units']])
        ids=[uid for e in report['unit_dispositions'] for uid in e['successor_unit_ids']]+report['added_unit_ids']+report['unmapped_output_unit_ids']
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),{u['unit_id'] for u in out['units']})
        self.assertEqual((self.root/'spec.md').read_bytes(),p.raw)
        self.assertFalse(list((self.root/'rounds').rglob('acceptance.json')))
        self.assertFalse((self.root/'rounds/round-1/draft_after.md').exists())
        self.assertFalse((self.root/'rounds/round-1/editor_summary.json').exists())

    def test_clarification_freezes_inputs_before_client_then_pending_with_exact_bytes(self):
        p=self.packet(bounded=True);ticket=self.admit(p);response=self.response(p);calls=[]
        def editor(inputs):
            calls.append(inputs)
            self.assertTrue((self.root/ticket.directory/'admission.json').is_file())
            self.assertEqual(decode_json(inputs.effective_config_json)['budget'],3)
            self.assertEqual(inputs.base,p.raw)
            self.assertEqual(inputs.reviewer_feedback_json[0],read_ref(self.root,p.feedback_ref))
            return response
        report_ref=self.store.run_editor(ticket,editor);report=self.store.report(ticket)
        self.assertEqual(len(calls),1)
        self.assertEqual(report['validation_result'],'pending')
        self.assertEqual(report['outcome'],'awaiting_operator_evidence')
        self.assertTrue(report['pending_obligations']);self.assertEqual(report['failures'],[])
        self.assertEqual(read_ref(self.root,report['raw_response']),response)
        self.assertEqual(read_ref(self.root,report['raw_proposal']),p.after)
        self.assertNotEqual(report['raw_proposal']['path'],report['materialized_draft']['path'])
        validate_reference_graph(self.root,report_ref,'current_runtime_preservation_bridge_report')
        validate_proposal_bindings(self.root,report['proposal']);self.assert_coverage(p,report)

    def test_hidden_frozen_losses_reject_even_with_independent_pending_clarification(self):
        for variant in ('missing_field','missing_state','missing_enum'):
            with self.subTest(variant=variant),TemporaryDirectory() as tmp:
                self.root=Path(tmp);self.store=ProposalStore(self.root)
                p=self.packet(1,variant,bounded=True);ticket=self.admit(p)
                self.store.capture_response(ticket,self.response(p));report=self.store.report(ticket)
                self.assertEqual(report['validation_result'],'fail')
                self.assertEqual(report['outcome'],'rejected')
                self.assertIn('allowed_surface_overrun',{f['category'] for f in report['failures']})
                self.assertTrue(report['pending_obligations']);self.assert_coverage(p,report)

    def test_noop_preservation_passes_without_advancing_authority(self):
        p=self.packet();ticket=self.admit(p)
        self.store.capture_response(ticket,self.response(p,p.raw));report=self.store.report(ticket)
        self.assertEqual(report['validation_result'],'pass');self.assertEqual(report['transformations'],[])
        self.assertEqual(report['pending_obligations'],[]);self.assert_coverage(p,report)

    def test_supplied_and_orchestrator_noop_origins_have_no_raw_response(self):
        p=self.packet()
        for origin,raw in [('supplied_revision',p.after),('orchestrator_noop',p.raw)]:
            ticket=self.admit(p,origin=origin,client_attempt_number=None)
            summary=decode_json(self.response(p,raw))
            self.store.capture_revision(ticket,raw,summary);report=self.store.report(ticket)
            self.assertIsNone(report['raw_response']);self.assertEqual(read_ref(self.root,report['raw_proposal']),raw)
            self.assert_coverage(p,report)

    def test_versioned_proposal_reproduces_transform_from_retained_evidence(self):
        p=self.packet(5,'raw_adjacent_edit');ticket=self.admit(p)
        self.store.capture_response(ticket,self.response(p));report=self.store.report(ticket)
        self.assertEqual(report['stage'],'complete');self.assertTrue(report['transformations'])
        self.assertIn(b'0.18',read_ref(self.root,report['materialized_draft']))
        proposal,_=validate_proposal_bindings(self.root,report['proposal'])
        wrong_config=deepcopy(proposal)
        wrong_config['normal_round_evidence']['effective_config']=p.save('wrong-config.json',{'phase':'phase_2','profile':'consistency'})
        with self.assertRaisesRegex(BridgeContractError,'effective config phase/profile'):
            validate_proposal_bindings(self.root,p.save('wrong-config-proposal.json',wrong_config))
        proposal['transformations'][0]['parameters']['changes'][0]['after']='9.9'
        with self.assertRaisesRegex(MaterializationError,'pinned algorithm'):
            validate_proposal_bindings(self.root,p.save('tampered-proposal.json',proposal))
        self.assert_coverage(p,report)

    def test_serious_unresolved_finding_withheld_stamp_and_unknown_resolution_rejects(self):
        p=self.packet(5,'raw_adjacent_edit');p.feedback['feedback'][0]['normalized_severity']='major'
        p.feedback_ref=p.save('feedback.json',p.feedback)
        p.surface['finding_sources'][0]['artifact']=p.feedback_ref;p.surface_ref=p.save('surface.json',p.surface)
        ticket=self.admit(p);self.store.capture_response(ticket,self.response(p,resolved_issue_ids=[],unresolved_issue_ids=[ISSUE]))
        self.assertEqual(self.store.report(ticket)['transformations'],[])
        ticket=self.admit(p);self.store.capture_response(ticket,self.response(p,resolved_issue_ids=['iss_'+'b'*16]))
        self.assertEqual(self.store.report(ticket)['validation_result'],'fail')

    def test_invalid_response_is_retained_without_fabricated_proposal(self):
        p=self.packet()
        for response in (b'{bad',b'{"draft_after_content":"\\ud800"}',b'{"a":1,"a":2}',b'\xff'):
            ticket=self.admit(p);self.store.capture_response(ticket,response);report=self.store.report(ticket)
            self.assertEqual(report['validation_result'],'fail');self.assertIsNone(report['proposal'])
            self.assertEqual(report['failures'][0]['category'],'invalid_artifact')
            self.assertIsNone(report['raw_proposal']);self.assertEqual(read_ref(self.root,report['raw_response']),response)
            self.assertEqual((self.root/'spec.md').read_bytes(),p.raw)

    def test_untrusted_version_edit_retains_raw_but_no_materialized_output(self):
        p=self.packet(5,'editor_version_change');ticket=self.admit(p)
        self.store.capture_response(ticket,self.response(p));report=self.store.report(ticket)
        self.assertEqual(report['failures'][0]['category'],'untrusted_version_edit')
        self.assertEqual(read_ref(self.root,report['raw_proposal']),p.after)
        self.assertIsNone(report['proposal']);self.assertIsNone(report['materialized_draft'])
        self.assertTrue((self.root/ticket.directory/'editor_summary.json').is_file())
        ticket=self.admit(p)
        self.store.capture_response(ticket,self.response(p,p.after+'\ufffd\n'.encode()))
        self.assertEqual({f['category'] for f in self.store.report(ticket)['failures']}, {'untrusted_version_edit','invalid_artifact'})

    def test_stale_current_base_refuses_before_client_and_admission_rejects_mutable_base_ref(self):
        p=self.packet();ticket=self.admit(p);(self.root/'spec.md').write_bytes(p.raw+b'changed\n')
        calls=[];self.store.run_editor(ticket,lambda inputs:calls.append(inputs))
        self.assertEqual(calls,[]);self.assertEqual(self.store.report(ticket)['validation_result'],'fail')
        (self.root/'spec.md').write_bytes(p.raw)
        with self.assertRaisesRegex(BridgeContractError,'immutable snapshot'):
            self.admit(p,current_draft='seed.md')

    def test_frozen_config_and_approved_surface_mutation_stop_client(self):
        p=self.packet()
        for target in ('effective_config.json','surface.json'):
            ticket=self.admit(p)
            path=self.root/(f'{ticket.directory}/{target}' if target=='effective_config.json' else target)
            original=path.read_bytes();path.write_bytes(original+b' ')
            calls=[];self.store.run_editor(ticket,lambda inputs:calls.append(inputs))
            self.assertEqual(calls,[]);self.assertEqual(self.store.report(ticket)['validation_result'],'fail')
            path.write_bytes(original)

    def test_attempts_never_reused_and_report_never_overwritten(self):
        p=self.packet();ticket=self.admit(p)
        self.store.capture_response(ticket,self.response(p))
        before={str(f.relative_to(self.root)):f.read_bytes() for f in self.root.rglob('*') if f.is_file()}
        with self.assertRaisesRegex(BridgeContractError,'already started'):
            self.store.capture_response(ticket,b'new response')
        self.assertEqual(before,{str(f.relative_to(self.root)):f.read_bytes() for f in self.root.rglob('*') if f.is_file()})
        (self.root/'rounds/round-1/preservation/attempt-9').mkdir()
        next_ticket=self.admit(p);self.assertTrue(next_ticket.directory.endswith('attempt-10'))
        self.assertEqual((self.root/ticket.directory/'report.json').read_bytes(),before[f'{ticket.directory}/report.json'])

    def test_timeout_has_one_call_and_no_automatic_retry(self):
        p=self.packet();ticket=self.admit(p);calls=[]
        def client(inputs):
            calls.append(1);raise TimeoutError('fixture timeout')
        self.store.run_editor(ticket,client);report=self.store.report(ticket)
        self.assertEqual(len(calls),1);self.assertEqual(report['validation_result'],'not_completed')
        self.assertEqual(report['failures'][0]['category'],'client_timeout');self.assertIsNone(report['proposal'])

    def test_persistence_failure_keeps_available_evidence_and_terminal_sidecar(self):
        p=self.packet();ticket=self.admit(p);write=self.store._write
        def fail(path,raw):
            if '/materialized_draft_attempt-' in path: raise OSError('fixture disk failure')
            return write(path,raw)
        with patch.object(self.store,'_write',side_effect=fail),self.assertRaisesRegex(OSError,'fixture disk'):
            self.store.capture_response(ticket,self.response(p))
        terminal=decode_json((self.root/ticket.directory/'terminal_failure.json').read_bytes())
        validate_artifact(terminal,'preservation_bridge_terminal_failure')
        self.assertEqual(terminal['category'],'persistence_failure');self.assertIsNone(terminal['acceptance'])
        self.assertTrue((self.root/'rounds/round-1/full_draft_rewrite_attempt-1.md').exists())
        self.assertFalse((self.root/ticket.directory/'proposal.json').exists())
        self.assertEqual((self.root/'spec.md').read_bytes(),p.raw)

    def test_report_persistence_failure_cannot_be_mistaken_for_completion(self):
        p=self.packet();ticket=self.admit(p);write=self.store._write
        def fail(path,raw):
            if path.endswith('/report.json'): raise OSError('report disk failure')
            return write(path,raw)
        with patch.object(self.store,'_write',side_effect=fail),self.assertRaises(OSError):
            self.store.capture_response(ticket,self.response(p))
        self.assertTrue((self.root/ticket.directory/'proposal.json').exists())
        self.assertFalse((self.root/ticket.directory/'report.json').exists())
        self.assertTrue((self.root/ticket.directory/'terminal_failure.json').exists())

    def test_hygiene_failure_does_not_hide_other_frozen_losses(self):
        p=self.packet(1,'missing_field',bounded=True);ticket=self.admit(p)
        self.store.capture_response(ticket,self.response(p,p.after+'\ufffd\n'.encode()));report=self.store.report(ticket)
        self.assertEqual(report['validation_result'],'fail')
        self.assertTrue({'invalid_artifact','allowed_surface_overrun'} <= {f['category'] for f in report['failures']})
        self.assertTrue(report['pending_obligations']);self.assert_coverage(p,report)

    def test_failure_after_report_link_keeps_report_and_binds_terminal_sidecar(self):
        p=self.packet();ticket=self.admit(p);write=self.store._write
        def fail(path,raw):
            ref=write(path,raw)
            if path.endswith('/report.json'): raise OSError('after durable report link')
            return ref
        with patch.object(self.store,'_write',side_effect=fail),self.assertRaises(OSError):
            self.store.capture_response(ticket,self.response(p))
        report_path=self.root/ticket.directory/'report.json';before=report_path.read_bytes()
        terminal=decode_json((self.root/ticket.directory/'terminal_failure.json').read_bytes())
        self.assertEqual(read_ref(self.root,terminal['report']),before)
        self.assertEqual(decode_json(before)['validation_result'],'pending')
        self.assertEqual((self.root/'spec.md').read_bytes(),p.raw)

    def test_unclassified_client_failure_is_terminal_without_retry(self):
        p=self.packet();ticket=self.admit(p);calls=[]
        def client(inputs):
            calls.append(1);raise RuntimeError('adapter broke')
        self.store.run_editor(ticket,client);report=self.store.report(ticket)
        self.assertEqual(calls,[1]);self.assertEqual(report['outcome'],'technical_failure')
        self.assertEqual(report['next_action'],'inspect_and_repair')
        self.assertNotEqual(report['failures'][0]['category'],'transient_client_failure')

    def test_failed_input_snapshot_consumes_attempt_without_invoking_client(self):
        p=self.packet();write=self.store._write
        def fail(path,raw):
            if path.endswith('/effective_config.json'): raise OSError('snapshot unavailable')
            return write(path,raw)
        with patch.object(self.store,'_write',side_effect=fail),self.assertRaises(OSError):
            self.admit(p)
        directory=self.root/'rounds/round-1/preservation/attempt-1'
        self.assertTrue((directory/'admission.json').is_file())
        self.assertTrue((directory/'terminal_failure.json').is_file())
        self.assertTrue(self.admit(p).directory.endswith('attempt-2'))

    def test_callback_input_mutation_retains_response_but_refuses_completed_proposal(self):
        p=self.packet();ticket=self.admit(p);response=self.response(p)
        def client(inputs):
            (self.root/'surface.json').write_bytes(b'changed authorization')
            return response
        self.store.run_editor(ticket,client);report=self.store.report(ticket)
        self.assertEqual(report['validation_result'],'fail');self.assertIsNone(report['proposal'])
        self.assertEqual(read_ref(self.root,report['raw_response']),response)
        self.assertEqual((self.root/'spec.md').read_bytes(),p.raw)

    def test_duplicate_choice_is_pending_but_frozen_multiplicity_loss_is_hard(self):
        p=self.packet(2,'one_duplicate_removed')
        ticket=self.admit(p);self.store.capture_response(ticket,self.response(p))
        self.assertEqual(self.store.report(ticket)['validation_result'],'pending')
        p.surface.update(allowed_sections=[],allowed_unit_ids=[],frozen_sections=['[]'])
        p.surface_ref=p.save('new-frozen-surface.json',p.surface)
        ticket=self.admit(p);self.store.capture_response(ticket,self.response(p));report=self.store.report(ticket)
        self.assertEqual(report['validation_result'],'fail')
        self.assertTrue(any('multiplicity' in f['reason'] for f in report['failures']))
        self.assertTrue(report['pending_obligations']);self.assert_coverage(p,report)

    def test_known_addition_requires_permission_and_effect_evidence(self):
        p=self.packet();raw=p.raw+b'Additional note.\n'
        ticket=self.admit(p);self.store.capture_response(ticket,self.response(p,raw));report=self.store.report(ticket)
        self.assertEqual(report['validation_result'],'fail');self.assertTrue(report['added_unit_ids'])
        self.assertFalse(report['unmapped_output_unit_ids']);self.assert_coverage(p,report)
        p.surface['allowed_change_types'].append('add');p.surface_ref=p.save('addition-surface.json',p.surface)
        ticket=self.admit(p);self.store.capture_response(ticket,self.response(p,raw));report=self.store.report(ticket)
        self.assertEqual(report['validation_result'],'pending')
        self.assertEqual(report['pending_obligations'][0]['kind'],'addition')

    def test_relocation_and_caps_are_checked_before_semantic_evidence(self):
        p=self.packet(4,'moved');ticket=self.admit(p)
        self.store.capture_response(ticket,self.response(p));report=self.store.report(ticket)
        self.assertEqual(report['validation_result'],'fail')
        self.assertTrue(any('relocated' in f['reason'] for f in report['failures']))
        p.surface['max_changed_sections']=1;p.surface_ref=p.save('capped-surface.json',p.surface)
        ticket=self.admit(p);self.store.capture_response(ticket,self.response(p));report=self.store.report(ticket)
        self.assertTrue(any('max_changed_sections=1' in f['reason'] for f in report['failures']))
        self.assert_coverage(p,report)

    def test_duplicate_normative_loss_exceeds_zero_cap_even_without_a_chosen_identity(self):
        p=self.packet(2,'one_duplicate_removed',max_changed_normative_units=0);ticket=self.admit(p)
        self.store.capture_response(ticket,self.response(p));report=self.store.report(ticket)
        self.assertEqual(report['validation_result'],'fail')
        self.assertTrue(any('max_changed_normative_units=0' in f['reason'] for f in report['failures']))

    def test_atomic_writer_refuses_symlink_and_conflicting_overwrite(self):
        self.store._write('evidence/raw.bin',b'exact')
        self.store._write('evidence/raw.bin',b'exact')
        with self.assertRaisesRegex(BridgeContractError,'different bytes'):
            self.store._write('evidence/raw.bin',b'other')
        (self.root/'alias').symlink_to(self.root/'evidence')
        with self.assertRaisesRegex(BridgeContractError,'symlink'):
            self.store._write('alias/escape.bin',b'bad')
        self.assertEqual((self.root/'evidence/raw.bin').read_bytes(),b'exact')


if __name__=='__main__':unittest.main()
