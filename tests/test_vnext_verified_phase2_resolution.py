"""Verified churn resolution, exact receipts and recovery without new work."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_signals as signals
import test_vnext_verified_phase2_client as clients
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_phase2_resolution import ROOT, STATE_FIELD, resolved_findings, residual_rows
from whetstone.vnext_phase2_signals import SignalTracker
from vnext_fixtures import STAMP


class ResolutionRulesTests(unittest.TestCase):
    feedback = signals.SignalRulesTests.feedback

    def test_reset_is_key_specific_and_does_not_clear_readdition_or_flip_flop(self):
        feedback = self.feedback(); key = feedback['feedback'][0]['oscillation_key']['opposition_key']
        tracker = SignalTracker(1,b'# A\nhello\n')
        tracker.record(1,feedback);tracker.record(2,feedback)
        self.assertFalse(tracker.record(3,feedback,resolved_opposition_keys=[key])['feedback_detections'])
        self.assertFalse(tracker.record(4,feedback)['feedback_detections'])
        self.assertEqual(tracker.record(5,feedback)['recommendations'],['escalate_conflict'])
        tracker = SignalTracker(1,b'# A\nhello\n')
        tracker.record(1,feedback);tracker.record(2,feedback)
        self.assertEqual(tracker.record(3,feedback,resolved_opposition_keys=['f'*64])['recommendations'],['escalate_conflict'])
        tracker = SignalTracker(1,b'# A\nhello\n')
        tracker.record(1,self.feedback('constrain'))
        self.assertEqual(tracker.record(2,self.feedback('relax'),resolved_opposition_keys=[key])['recommendations'],['freeze_prior_decision'])
        tracker = SignalTracker(1,b'# A\nhello\n')
        tracker.record(1,self.feedback('add'));tracker.record(2,{'feedback':[]})
        self.assertEqual(tracker.record(3,self.feedback('add'),resolved_opposition_keys=[key])['recommendations'],['continue_once'])

    def test_partial_rejected_duplicate_and_unrelated_findings_never_resolve(self):
        rows = self.feedback()['feedback']; identifier = rows[0]['issue_id']
        semantic = dict(verdict='pass',finding_results=[dict(finding_id=identifier,disposition='resolved')])
        self.assertEqual(resolved_findings(semantic,rows,{identifier}),{identifier})
        variants=[]
        for disposition in ('partially_resolved','not_resolved','made_worse'):
            bad=deepcopy(semantic);bad['finding_results'][0]['disposition']=disposition;variants.append(bad)
        bad=deepcopy(semantic);bad['verdict']='reject';variants.append(bad)
        bad=deepcopy(semantic);bad['finding_results']*=2;variants.append(bad)
        bad=deepcopy(semantic);bad['finding_results'][0]['finding_id']='derived';variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad),self.assertRaises(ValueError):resolved_findings(bad,rows,{identifier})
        with self.assertRaises(ValueError):resolved_findings(semantic,rows,{'unrelated'})
        with self.assertRaises(ValueError):resolved_findings(semantic,[],{identifier})

    def test_residuals_require_verified_coverage_and_recurrence_reopens(self):
        rows=self.feedback()['feedback']; identifier=rows[0]['issue_id']
        def frame(items,receipt=None):return dict(consumed=True,review=dict(feedback=dict(feedback=items)),resolution=receipt)
        receipt=dict(committed=True,resolved_issue_ids=[identifier])
        first=frame(rows)
        self.assertEqual(residual_rows([first,frame([])],set()),rows)
        self.assertEqual(residual_rows([first],{'unrelated'}),rows)
        first['resolution']=receipt
        self.assertEqual(residual_rows([first,frame([])],set()),[])
        self.assertEqual(residual_rows([first,frame(rows)],set()),rows)
        first['resolution']=dict(receipt,committed=False)
        self.assertEqual(residual_rows([first],set()),rows)


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class ResolutionRuntimeTests(unittest.TestCase):
    setUpClass=signals.SignalRuntimeTests.setUpClass
    fixture=signals.SignalRuntimeTests.fixture
    ready=signals.SignalRuntimeTests.ready
    config=signals.SignalRuntimeTests.config
    files=signals.SignalRuntimeTests.files
    reopen=signals.SignalRuntimeTests.reopen
    review=signals.SignalRuntimeTests.review
    promote=signals.SignalRuntimeTests.promote
    next_client=signals.SignalRuntimeTests.next_client
    advance=signals.SignalRuntimeTests.advance
    advice=signals.SignalRuntimeTests.advice
    candidate=signals.SignalRuntimeTests.candidate
    response=signals.SignalRuntimeTests.response

    def start(self,**kwargs):
        return clients.VerifiedPhase2ClientTests.start(self,phase2_resolution_contract=True,**kwargs)

    def corrected(self, *, promote=True, reject=False):
        f,reviewer,_=self.ready()
        base_response=self.response('clarify','major')
        def mixed(client,packet):
            packet=json.loads(base_response(client,packet))
            row=deepcopy(packet['feedback'][0]);row['feedback_id']='fb_retained'
            row.update(claim='Clarify the separate descriptive example.',baseline_severity='minor',normalized_severity='minor')
            row['oscillation_key']['concern_type']='clarity_gap'
            packet['feedback'].append(row)
            return canonical_json_bytes(packet)
        reviewer.callback=mixed
        result=f.run.run_phase2_review(client=reviewer);f.run.consume_phase2_result()
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        advice=self.advice(bound,result);advice['findings'][1]['classification']='deferable'
        f.run.bind_phase2_advice(advice);ref=f.run.admit_phase2_round()
        number=json.loads(f.store.read(ref['path']))['round_number']
        creation,verifier=self.candidate(f,number)
        if reject:
            response=json.loads(verifier.valid);response['verdict']='reject'
            response['finding_results'][0]['disposition']='partially_resolved'
            verifier.responses=[canonical_json_bytes(response)]
        final=f.run.verify(client=verifier,decided_at=STAMP)
        if promote:f.run.promote(prepared_at=STAMP)
        return f,reviewer,verifier,result,creation,final

    def test_receipt_gates_next_review_preserves_residuals_and_resets_once(self):
        f,first,verifier,result,creation,_=self.corrected(promote=False)
        self.assertEqual(f.run.phase2_resolution_status().outcome,'promotion_required')
        self.assertFalse((f.root/ROOT).exists())
        f.run.promote(prepared_at=STAMP)
        head=f.store.read('rounds/current_verified.json')
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'resolution_publication_required')
        self.assertEqual(f.run.bind_phase2_next_review(first.transport_binding)['gate'],'resolution_publication_required')
        files=self.files(f)
        with patch.object(f.store,'locked',side_effect=AssertionError('status writes')):
            status=f.run.phase2_resolution_status()
        self.assertEqual(self.files(f),files)
        record=status['records'][0];packet=record['packet']
        self.assertEqual(packet['reset_opposition_keys'],[result.review['feedback']['feedback'][0]['oscillation_key']['opposition_key']])
        self.assertEqual(packet['feedback'],result.receipt['feedback'])
        published=f.run.publish_phase2_resolutions()
        self.assertFalse(published['publication_required']);self.assertFalse(published['state_current'])
        summary=json.loads(f.store.read(packet['summary']['path']))
        self.assertEqual(summary['accepted_or_modified_feedback_ids'],[result.review['feedback']['feedback'][0]['feedback_id']])
        retained=json.loads(f.store.read(packet['unresolved_issues']['path']))['unresolved_issues']
        self.assertEqual([r['issue_id'] for r in retained],[result.review['feedback']['feedback'][1]['issue_id']])
        f.run.reconcile_phase2_resolution_state();self.reopen(f)
        status=f.run.phase2_sequence_status()
        self.assertEqual(status['gate'],'review');self.assertEqual(status['clean_profiles'],[])
        self.assertEqual(status['profiles'][0]['rounds_used'],1)
        saved={p:f.store.read(p) for p in (packet['summary']['path'],packet['unresolved_issues']['path'],record['reference']['path'])}
        for ordinal in (2,3):
            client=self.next_client(first,clean=False);client.callback=self.response('clarify','minor')
            bound,result,_=self.advance(f,client)
            advice=self.advice(bound,result)
            for row in advice['findings']:row['classification']='deferable'
            f.run.continue_phase2_pass(ordinal,action='advice',advice=advice)
            self.assertEqual(f.run.phase2_signal_status()['recommendations'],[])
        f.run.prepare_phase2_declaration()
        final=self.next_client(first,clean=False);final.callback=self.response('clarify','minor')
        self.advance(f,final)
        self.assertEqual(f.run.phase2_signal_status()['recommendations'],['escalate_conflict'])
        for path,raw in saved.items():self.assertEqual(f.store.read(path),raw)
        self.assertEqual(f.store.read('rounds/current_verified.json'),head)
        self.assertEqual((first.calls,f.editor.calls,verifier.calls),(1,1,1))

    def test_publication_prefixes_state_uncertainty_and_tampering_fail_closed(self):
        f,first,verifier,_,_,_=self.corrected()
        status=f.run.phase2_resolution_status();packet=status['records'][0]['packet']
        from whetstone.vnext_verified_materialization import STATE_PATH
        source=packet['semantic_verification']['path'];raw=f.store.read(source)
        sync=f.store.synchronize_existing
        def drift(token,path,**kwargs):
            value=sync(token,path,**kwargs)
            if path==source:(f.root/source).write_bytes(raw+b' ')
            return value
        with patch.object(f.store,'synchronize_existing',side_effect=drift):
            with self.assertRaises(ValueError):f.run.publish_phase2_resolutions()
        self.assertFalse((f.root/ROOT).exists());(f.root/source).write_bytes(raw)
        for suffix in ('/summary.json','/unresolved_issues.json','/commit.json'):
            publish=f.store.publish
            def lose(token,path,value):
                out=publish(token,path,value)
                if path.startswith(ROOT+'/') and path.endswith(suffix):raise OSError('lost publication ack')
                return out
            with patch.object(f.store,'publish',side_effect=lose):
                with self.assertRaises(OSError):f.run.publish_phase2_resolutions()
            self.reopen(f)
        self.assertFalse(f.run.publish_phase2_resolutions()['publication_required'])
        materialize=f.store.materialize
        def lost_state(token,path,value,**kwargs):
            out=materialize(token,path,value,**kwargs)
            if path==STATE_PATH:raise OSError('lost final state ack')
            return out
        with patch.object(f.store,'materialize',side_effect=lost_state):
            with self.assertRaises(OSError):f.run.reconcile_phase2_resolution_state()
        self.reopen(f);self.assertTrue(f.run.reconcile_phase2_resolution_state()['state_current'])
        for path in (source,packet['summary']['path'],packet['unresolved_issues']['path']):
            raw=f.store.read(path);(f.root/path).write_bytes(raw+b' ')
            with self.assertRaises(ValueError):f.run.phase2_resolution_status()
            (f.root/path).write_bytes(raw)
        path=packet['summary']['path'];raw=f.store.read(path);(f.root/path).unlink()
        with self.assertRaisesRegex(ValueError,'lacks dependencies'):f.run.phase2_resolution_status()
        (f.root/path).write_bytes(raw)
        rogue=f.root/ROOT/'pass-99';rogue.mkdir()
        with self.assertRaisesRegex(ValueError,'unknown Phase 2 resolution'):f.run.phase2_resolution_status()
        rogue.rmdir()
        # Receipt bytes, not a spoofed convenience field, decide the next gate.
        self.assertFalse((f.root/'rounds/phase2/review_requests/pass-2').exists())
        self.assertEqual((first.calls,f.editor.calls,verifier.calls),(1,1,1))

    def test_rejected_partial_candidate_has_no_resolution_receipt(self):
        f,first,verifier,_,_,final=self.corrected(reject=True)
        self.assertEqual(final.value.decision['candidate_disposition'],'CANDIDATE_REJECTED')
        self.assertEqual(f.run.phase2_resolution_status()['records'],[])
        self.assertEqual(f.run.publish_phase2_resolutions()['records'],[])
        self.assertFalse((f.root/ROOT).exists())
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'correction_required')
        self.assertEqual((first.calls,f.editor.calls,verifier.calls),(1,1,1))

    def test_second_receipt_extends_history_without_rewriting_first(self):
        f,first,verifier,result,_,_=self.corrected()
        first_record=f.run.publish_phase2_resolutions()['records'][0]
        f.run.reconcile_phase2_resolution_state()
        retained={p:f.store.read(p) for p in (first_record['reference']['path'],
            first_record['packet']['summary']['path'],first_record['packet']['unresolved_issues']['path'])}
        second=self.next_client(first,clean=False);second.callback=self.response('clarify','major')
        bound,result,_=self.advance(f,second)
        f.run.continue_phase2_pass(2,action='advice',advice=self.advice(bound,result))
        f.run.continue_phase2_pass(2,action='admit')
        from whetstone.vnext_contracts import sha256_bytes
        def correction(packet):
            content='Queue always waits before beginning work.\n'
            packet['payloads'][0]['content']=content
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        f.editor.callback=correction
        _,second_verifier=self.candidate(f,bound.request['round_number'])
        f.run.verify(client=second_verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'resolution_publication_required')
        records=f.run.publish_phase2_resolutions()['records'];self.assertEqual(len(records),2)
        self.assertEqual(records[1]['packet']['previous_resolutions'],[first_record['reference']])
        self.assertEqual(records[1]['packet']['base_pointer'],first_record['packet']['promoted_pointer'])
        self.assertEqual(len(records[1]['packet']['source_consumptions']),2)
        residual=json.loads(f.store.read(records[1]['packet']['unresolved_issues']['path']))['unresolved_issues']
        self.assertEqual(len(residual),1)
        self.assertEqual(residual[0]['claim'],'Clarify the separate descriptive example.')
        f.run.reconcile_phase2_resolution_state();self.reopen(f)
        historical=f.run._history().load_inputs(f.store.read,bound.request['round_number'])
        self.assertEqual(historical['base_pointer_ref'],bound.request['base_pointer'])
        status=f.run.phase2_sequence_status()
        self.assertEqual(status['gate'],'review');self.assertEqual(status['profiles'][0]['rounds_used'],2)
        self.assertEqual(status['clean_profiles'],[])
        for path,raw in retained.items():self.assertEqual(f.store.read(path),raw)
        self.assertEqual((first.calls,second.calls,f.editor.calls,verifier.calls,second_verifier.calls),(1,1,2,1,1))
