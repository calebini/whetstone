"""Explicit gap acceptance retains source debt, draft binding and review authority."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_targets as targets
import test_vnext_verified_phase2_signals as signals
from whetstone.vnext_contracts import canonical_json_bytes
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class GapAcceptanceTests(unittest.TestCase):
    setUpClass = targets.TargetRuntimeTests.setUpClass
    fixture = targets.TargetRuntimeTests.fixture
    files = targets.TargetRuntimeTests.files
    reopen = targets.TargetRuntimeTests.reopen
    review = targets.TargetRuntimeTests.review
    promote = targets.TargetRuntimeTests.promote
    candidate = targets.TargetRuntimeTests.candidate
    advice = targets.TargetRuntimeTests.advice
    advance = targets.TargetRuntimeTests.advance
    config = targets.TargetRuntimeTests.config
    ready = targets.TargetRuntimeTests.ready
    target = ('final','permissive')

    def start(self, **kwargs):
        return targets.TargetRuntimeTests.start(self, phase2_gap_acceptance_contract=True, **kwargs)

    def response(self, *, gaps=True, severity='minor', direction='clarify'):
        base = signals.SignalRuntimeTests.response(self,direction,severity,empty=not gaps)
        def callback(client,packet):
            review = json.loads(base(client,packet));annotations = []
            if gaps:
                row = review['feedback'][0];row['rubric_impact'] = 'minor'
                requirement = json.loads(client.prompts[-1].splitlines()[-1])['rubric_catalogue'][0]
                annotations = [dict(feedback_id=row['feedback_id'],rubric_anchor=requirement['rubric_anchor'],
                                    requirement_hash=requirement['requirement_hash'])]
            return canonical_json_bytes(dict(review=review,rubric_findings=annotations))
        return callback

    def gap_ready(self, **kwargs):
        f,client,_ = self.ready();client.callback=self.response(**kwargs)
        review = f.run.run_phase2_review(client=client)
        self.assertEqual(review.status,'complete');f.run.consume_phase2_result()
        return f,client,review

    def packet(self,f):
        context = f.run.phase2_gap_acceptance_context()
        return dict(context['bindings'],gaps=sorted([row['selection'] for row in context['gaps']],key=lambda row:row['gap_id']),
                    decided_by='operator',rationale='Accept this documented gap for this exact draft.',decided_at=STAMP)

    def test_acceptance_requires_new_declaration_review_and_preserves_source_finding(self):
        f,client,_=self.gap_ready();packet=self.packet(f)
        before=self.files(f)
        with patch.object(f.store,'locked',side_effect=AssertionError('preview acquired writer fence')):
            preview=f.run.accept_phase2_gaps(packet,dry_run=True)
        self.assertFalse(preview['committed']);self.assertEqual(self.files(f),before)
        pointer=f.store.read('rounds/current_verified.json')
        accepted=f.run.accept_phase2_gaps(packet)
        self.assertTrue(accepted['committed']);self.assertEqual(f.run.phase2_sequence_status()['gate'],'review')
        self.assertFalse(f.run.phase2_closeout()['phase_complete'])
        self.reopen(f);client.callback=self.response(gaps=False);self.advance(f,client)
        package=f.run.prepare_phase2_declaration()
        self.assertEqual(package['declaration']['schema_version'],'vnext-phase2-declaration-v3')
        self.assertEqual(package['declaration']['gap_acceptances'],[accepted['reference']])
        gaps=json.loads(f.store.read(package['declaration']['rubric_gaps']['path']))['rubric_gaps']
        self.assertEqual(gaps[0]['status'],'accepted');self.assertFalse(gaps[0]['blocking_convergence'])
        client.callback=self.response();bound,_,_=self.advance(f,client)
        self.assertIn(accepted['reference'],bound.inputs['sources'])
        findings=f.run.reconcile_phase2_findings()
        issues=json.loads(f.store.read(findings['packet']['unresolved_issues']['path']))['unresolved_issues']
        self.assertEqual(len(issues),1);self.assertEqual(issues[0]['normalized_severity'],'minor')
        result=f.run.finish_phase2();self.assertEqual(result['packet']['terminal_state'],'CONVERGED')
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual(f.store.read('rounds/current_verified.json'),pointer)
        self.assertEqual((client.calls,f.editor.calls),(3,0))
        self.reopen(f);before=self.files(f)
        self.assertTrue(f.run.phase2_closeout()['phase_complete']);self.assertEqual(self.files(f),before)

    def test_wrong_bindings_duplicate_selection_and_implicit_acceptance_refuse_without_writes(self):
        f,client,_=self.gap_ready();original=self.packet(f);before=self.files(f)
        variants=[]
        for key in ('configuration','base_pointer','verified_draft','rubric','source_request','source_consumption'):
            packet=deepcopy(original);packet[key]['hash']='0'*64;variants.append(packet)
        for key in ('requirement_hash','gap_hash'):
            packet=deepcopy(original);packet['gaps'][0][key]='0'*64;variants.append(packet)
        for key,value in [('gaps',[]),('gaps',original['gaps']*2),('decided_by',' '),('rationale',' '),('target',dict(phase='final',mode='strict'))]:
            packet=deepcopy(original);packet[key]=value;variants.append(packet)
        for packet in variants:
            with self.subTest(packet=packet),self.assertRaises(ValueError):f.run.accept_phase2_gaps(packet)
        self.assertEqual(self.files(f),before);self.assertEqual((client.calls,f.editor.calls),(1,0))

    def test_publication_lost_ack_and_final_ownership_loss_recover_exact_decision(self):
        from whetstone.vnext_local_storage import OwnershipLost
        for mode in ('ack','owner'):
            with self.subTest(mode=mode):
                f,client,_=self.gap_ready();packet=self.packet(f);publish=f.store.publish
                def lose(token,path,value):
                    result=publish(token,path,value)
                    if '/gap_acceptances/' in path:
                        if mode=='ack':raise OSError('lost acceptance acknowledgement')
                        f.store._invalidate()
                    return result
                with patch.object(f.store,'publish',side_effect=lose):
                    with self.assertRaises(OSError if mode=='ack' else OwnershipLost):f.run.accept_phase2_gaps(packet)
                self.reopen(f);before=self.files(f)
                self.assertTrue(f.run.accept_phase2_gaps(packet)['committed'])
                self.assertEqual(self.files(f),before);self.assertEqual((client.calls,f.editor.calls),(1,0))

    def test_acceptance_does_not_waive_major_source_debt_or_authorize_replacement(self):
        f,client,result=self.gap_ready(severity='major');packet=self.packet(f)
        accepted=f.run.accept_phase2_gaps(packet)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'operator_or_advice_required')
        before=self.files(f);other=deepcopy(packet);other['rationale']='Replace old decision'
        with self.assertRaises(ValueError):f.run.accept_phase2_gaps(other)
        with self.assertRaises(ValueError):f.run.finish_phase2()
        self.assertEqual(self.files(f),before);self.assertEqual(f.editor.calls,0)
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        f.run.bind_phase2_advice(self.advice(bound,result));ref=f.run.admit_phase2_round()
        number=json.loads(f.store.read(ref['path']))['round_number']
        def timeout(value):raise TimeoutError('bounded source-correction timeout')
        f.editor.callback=timeout
        self.assertEqual(f.run.request(round_number=number,client=f.editor).value.status,'timeout')
        published=f.run.publish_phase2_correction_failure()
        record=json.loads(f.store.read(published['active']['path']))
        manifest=json.loads(f.store.read(record['rubric_manifest']['path']))
        self.assertEqual(manifest['schema_version'],'vnext-bound-rubric-v2')
        self.assertEqual(manifest['gap_acceptances'],[accepted['reference']])
        report=json.loads(f.store.read(record['failure']['path']))
        self.assertEqual(report['unresolved_rubric_gaps'],[]);self.assertTrue(report['unresolved_major_issues'])
        path=f.root/accepted['reference']['path'];raw=path.read_bytes()
        other=deepcopy(packet);other['decided_by']='Changed operator'
        path.write_bytes(canonical_json_bytes(other))
        with self.assertRaises(ValueError):f.run.phase2_correction_failure_status()
        path.write_bytes(raw);f.run.reconcile_phase2_correction_failure_state()

    def test_acceptance_refuses_after_advice_and_on_strict_or_unpinned_suites(self):
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        f,client,result=self.gap_ready();packet=self.packet(f)
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        f.run.bind_phase2_advice(self.advice(bound,result));before=self.files(f)
        with self.assertRaises(ValueError):f.run.accept_phase2_gaps(packet)
        self.assertEqual(self.files(f),before)
        self.target=('final','strict');f,client,_=self.gap_ready();before=self.files(f)
        with self.assertRaises(ValueError):f.run.phase2_gap_acceptance_context()
        self.assertEqual(self.files(f),before)

        with patch.object(self,'start',side_effect=lambda **kw:targets.TargetRuntimeTests.start(self,**kw)):
            f,client,_=self.ready()
        before=self.files(f)
        with self.assertRaises(ValueError):f.run.phase2_gap_acceptance_context()
        self.assertEqual(self.files(f),before)

    def test_new_promotion_invalidates_acceptance_and_requires_explicit_current_draft_renewal(self):
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        from whetstone.vnext_phase2_rubric import retained
        from whetstone.vnext_verified_phase2_gap_acceptance import GapAcceptance
        from whetstone.vnext_verified_phase2_sequence import sequence
        f,client,_=self.ready();original=self.response()
        def mixed(owner,packet):
            value=json.loads(original(owner,packet));extra=deepcopy(value['review']['feedback'][0])
            extra.update(feedback_id='fb-source',baseline_severity='major',normalized_severity='major',rubric_impact=None,
                         claim='The waiting transition needs a precise source explanation.')
            value['review']['feedback'].append(extra);return canonical_json_bytes(value)
        client.callback=mixed;result=f.run.run_phase2_review(client=client);self.assertEqual(result.status,'complete')
        f.run.consume_phase2_result();old=self.packet(f);accepted=f.run.accept_phase2_gaps(old)
        old_raw=f.store.read(accepted['reference']['path'])
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        advice=self.advice(bound,result);advice['findings'][0]['classification']='deferable'
        advice['findings'][0]['requested_effects']=[]
        f.run.bind_phase2_advice(advice);ref=f.run.admit_phase2_round()
        number=json.loads(f.store.read(ref['path']))['round_number'];_,verifier=self.candidate(f,number)
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        f.run.publish_phase2_resolutions();self.reopen(f)
        owner=GapAcceptance(f.run);proof=owner._proof(owner.store.read);state=sequence(proof)
        gaps=retained(state['frames'],proof.latest)
        self.assertEqual(gaps[0]['status'],'unresolved');self.assertTrue(gaps[0]['blocking_convergence'])
        before=self.files(f)
        with self.assertRaises(ValueError):f.run.accept_phase2_gaps(old)
        self.assertEqual(self.files(f),before)
        renewed=self.packet(f);self.assertNotEqual(renewed['base_pointer'],old['base_pointer'])
        self.assertIsNotNone(renewed['source_resolution'])
        f.run.accept_phase2_gaps(renewed);package=f.run.prepare_phase2_declaration()
        self.assertEqual(len(package['declaration']['gap_acceptances']),2)
        self.assertEqual(json.loads(f.store.read(package['declaration']['rubric_gaps']['path']))['rubric_gaps'][0]['status'],'accepted')
        self.assertEqual(f.store.read(accepted['reference']['path']),old_raw)
        self.assertEqual((client.calls,f.editor.calls,verifier.calls),(1,1,1))

    def test_source_drift_and_consumer_tampering_fail_without_new_authority(self):
        f,client,_=self.gap_ready();packet=self.packet(f);source=packet['rubric']['path'];raw=f.store.read(source)
        synchronize=f.store.synchronize_existing;changed=False
        def drift(token,path,**kwargs):
            nonlocal changed
            result=synchronize(token,path,**kwargs)
            if path==source and not changed:
                changed=True;(f.root/source).write_bytes(raw+b'\n')
            return result
        with patch.object(f.store,'synchronize_existing',side_effect=drift):
            with self.assertRaises(ValueError):f.run.accept_phase2_gaps(packet)
        (f.root/source).write_bytes(raw)
        accepted=f.run.accept_phase2_gaps(packet);client.callback=self.response(gaps=False)
        f.run.bind_phase2_next_review(client.transport_binding)
        decision_path=f.root/accepted['reference']['path'];original=decision_path.read_bytes()
        changed_packet=deepcopy(packet);changed_packet['rationale']='Changed after request publication'
        decision_path.write_bytes(canonical_json_bytes(changed_packet))
        with self.assertRaises(ValueError):f.run.phase2_sequence_status()
        decision_path.write_bytes(original)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'pending_review')
        self.assertEqual((client.calls,f.editor.calls),(1,0))

    def test_freeze_cannot_be_released_by_gap_acceptance(self):
        f,client,_=self.gap_ready(direction='constrain');f.run.accept_phase2_gaps(self.packet(f))
        client.callback=self.response(direction='relax');self.advance(f,client)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'oscillation_freeze_required')
        before=self.files(f)
        with self.assertRaises(ValueError):f.run.phase2_gap_acceptance_context()
        self.assertEqual(self.files(f),before);self.assertEqual(f.editor.calls,0)

    def test_failure_report_preserves_acceptance_and_prepared_successor_seals_decision(self):
        f,client,_=self.gap_ready();packet=self.packet(f);accepted=f.run.accept_phase2_gaps(packet)
        bound=f.run.bind_phase2_next_review(client.transport_binding)
        before=self.files(f)
        # Exact acknowledgement recovery grants no ability to change the decision.
        self.assertTrue(f.run.accept_phase2_gaps(packet)['committed'])
        self.assertEqual(self.files(f),before)
        def timeout(owner,request):raise TimeoutError('bounded timeout after accepted gap')
        client.callback=timeout
        self.assertEqual(f.run.continue_phase2_pass(2,action='execute',client=client).status,'timeout')
        f.run.reconcile_phase2_failure_state()
        report=json.loads(f.store.read('rounds/convergence_failure_report.json'))
        self.assertEqual(report['unresolved_rubric_gaps'],[])
        self.assertEqual(json.loads(f.store.read(accepted['reference']['path'])),packet)
        self.assertIn(accepted['reference'],bound.inputs['sources'])
        self.assertEqual((client.calls,f.editor.calls),(2,0))

    def test_acceptance_after_last_review_does_not_grant_extra_budget_or_convergence(self):
        original=self.config
        def one_pass(f):
            value=original(f)
            for profile in value['profiles']:profile['budget']=1
            return value
        with patch.object(self,'config',side_effect=one_pass):f,client,_=self.gap_ready()
        f.run.accept_phase2_gaps(self.packet(f));client.callback=self.response(gaps=False);self.advance(f,client)
        f.run.prepare_phase2_declaration();base=self.response()
        def new_gap(owner,packet):
            value=json.loads(base(owner,packet));value['review']['feedback'][0]['claim']='A different documented rubric gap remains.'
            return canonical_json_bytes(value)
        client.callback=new_gap;self.advance(f,client)
        final_packet=self.packet(f);final_acceptance=f.run.accept_phase2_gaps(final_packet)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'declaration_closeout_required')
        f.run.reconcile_phase2_findings();result=f.run.finish_phase2()
        self.assertEqual(result['packet']['terminal_state'],'TARGET_NOT_REACHED')
        self.assertIn('declaration_gap_acceptance_changed',result['packet']['blockers'])
        self.assertTrue(f.run.reconcile_phase2_state()['halt_complete'])
        self.assertEqual((client.calls,f.editor.calls),(3,0))
        self.assertFalse((f.root/'rounds/phase2/review_requests/pass-4').exists())
        path=f.root/final_acceptance['reference']['path'];raw=path.read_bytes()
        other=deepcopy(final_packet);other['rationale']='Changed after terminal publication'
        path.write_bytes(canonical_json_bytes(other))
        with self.assertRaises(ValueError):f.run.phase2_closeout()
        path.write_bytes(raw);self.assertTrue(f.run.phase2_closeout()['halt_complete'])
