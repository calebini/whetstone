"""Bounded signal classification, fenced reporting and exact historical recovery."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_sequence as sequence_tests
import test_vnext_verified_phase2_client as clients
from whetstone.identity import oscillation_fingerprint, oscillation_opposition_key
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_phase2_signals import SignalTracker, gate_for, terminal
from whetstone.vnext_verified_phase2_signals import ROOT, STATE_FIELD
from vnext_fixtures import STAMP


class SignalRulesTests(unittest.TestCase):
    def feedback(self, direction='clarify', severity='minor'):
        return dict(feedback=[dict(feedback_id='fb_a',issue_id='iss_'+'a'*16,issue_fingerprint='a'*64,
            normalized_severity=severity,oscillation_key=dict(section_id='a',concern_type='precision_gap',
                direction=direction,scope='local',fingerprint=oscillation_fingerprint('a','precision_gap',direction,'local'),
                opposition_key=oscillation_opposition_key('a','precision_gap','local')))])

    def test_readdition_freeze_and_simultaneous_terminal_precedence(self):
        t=SignalTracker(1,b'# A\nhello\n')
        for number,feedback in enumerate([self.feedback('add'),{'feedback':[]},self.feedback('add'),{'feedback':[]},self.feedback('add')],1):
            result=t.record(number,feedback)
            if number==3:self.assertEqual(gate_for(result,'review'),'review');self.assertEqual(result['recommendations'],['continue_once'])
        self.assertEqual(result['terminal_state'],'HALTED_OSCILLATION')
        t=SignalTracker(1,b'# A\nhello\n');t.record(1,self.feedback('constrain'))
        self.assertEqual(gate_for(t.record(2,self.feedback('relax')),'review'),'oscillation_freeze_required')
        all_states=['TARGET_NOT_REACHED','PAUSED_DECISION','HALTED_ARTIFACT_INVALID','HALTED_OSCILLATION','HALTED_CONFLICT','CONVERGED','HALTED_CLIENT_TIMEOUT']
        for i,state in enumerate(all_states):self.assertEqual(terminal(all_states[:i+1]),state)

    def test_conflict_history_counts_absence_and_preserves_severity(self):
        t=SignalTracker(1,b'# A\nhello\n')
        for number in (1,2):self.assertFalse(t.record(number,self.feedback('clarify','major'))['conflicts'])
        first=t.record(3,self.feedback('clarify','major'))
        self.assertEqual(first['conflicts'][0]['conflict_severity'],'major');self.assertIsNone(first['terminal_state'])
        second=t.record(4,self.feedback('clarify','major'))
        self.assertIn('2 consecutive',second['escalation_reason'])
        absent=t.record(5,{'feedback':[]})['conflict_state']['conflicts'][0]
        self.assertEqual((absent['consecutive_present_rounds'],absent['total_present_rounds']),(0,2))
        third=t.record(6,self.feedback('clarify','major'))
        self.assertIn('3 times non-consecutively',third['escalation_reason'])
        t=SignalTracker(1,b'# A\nhello\n');t.record(1,self.feedback('constrain','blocker'))
        self.assertEqual(t.record(2,self.feedback('relax','major'))['terminal_state'],'HALTED_CONFLICT')

    def test_normalized_cycle_and_draft_feedback_reasons_survive_together(self):
        initial=b'# A\nhello\n';changed=b'# A\nhello again\n'
        t=SignalTracker(1,initial)
        t.record(1,self.feedback('constrain','major'),before=initial,after=changed)
        result=t.record(2,self.feedback('relax','blocker'),before=changed,after=initial+b'\n')
        self.assertEqual(set(result['conditions']),{'HALTED_CONFLICT','HALTED_OSCILLATION'})
        self.assertEqual(result['terminal_state'],'HALTED_CONFLICT')
        self.assertEqual(result['draft_detection']['oscillation_type'],'cycle')


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class SignalRuntimeTests(unittest.TestCase):
    setUpClass=sequence_tests.Phase2SequenceTests.setUpClass
    fixture=sequence_tests.Phase2SequenceTests.fixture
    ready=sequence_tests.Phase2SequenceTests.ready
    config=sequence_tests.Phase2SequenceTests.config
    files=sequence_tests.Phase2SequenceTests.files
    reopen=sequence_tests.Phase2SequenceTests.reopen
    review=sequence_tests.Phase2SequenceTests.review
    promote=sequence_tests.Phase2SequenceTests.promote
    next_client=sequence_tests.Phase2SequenceTests.next_client
    advance=sequence_tests.Phase2SequenceTests.advance
    advice=sequence_tests.Phase2SequenceTests.advice
    candidate=sequence_tests.Phase2SequenceTests.candidate

    def start(self,**kwargs):
        return clients.VerifiedPhase2ClientTests.start(self,phase2_signals_contract=True,**kwargs)

    def response(self,direction,severity='minor',empty=False):
        def callback(client,packet):
            inputs=json.loads(client.prompts[-1].splitlines()[-1])
            packet['draft_hash']=sha256_bytes(inputs['draft'].encode())
            if empty:packet['feedback']=[]
            else:
                row=packet['feedback'][0]
                row.update(baseline_severity=severity,normalized_severity=severity,authority_impact=None,
                    determinism_impact=None,rubric_impact=None,invariant_violated=None,
                    claim=f'Clarify the waiting description: {direction}, {severity}.',recommended_change='Clarify the wording.')
                row['oscillation_key']['direction']=direction
            return canonical_json_bytes(packet)
        return callback

    def first(self,direction='constrain'):
        f,client,_=self.ready();client.callback=self.response(direction)
        result=f.run.run_phase2_review(client=client);self.assertEqual(result.status,'complete')
        f.run.consume_phase2_result()
        from whetstone.vnext_verified_phase2_review import INPUT_PATH, REQUEST_PATH
        from types import SimpleNamespace
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        advice=self.advice(bound,result)
        for row in advice['findings']:row['classification']='deferable'
        f.run.bind_phase2_advice(advice)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'review')
        return f,client

    def second(self,severity='blocker'):
        f,first=self.first();second=self.next_client(first,clean=False);second.callback=self.response('relax',severity)
        bound,result,_=self.advance(f,second)
        return f,first,second,bound,result

    def test_freeze_is_distinct_and_blocker_conflict_reports_without_clients(self):
        for severity,gate,expected in [('minor','oscillation_freeze_required',None),('blocker','conflict_halt_required','HALTED_CONFLICT')]:
            with self.subTest(severity=severity):
                f,first,second,bound,result=self.second(severity)
                before=f.store.read('rounds/current_verified.json')
                self.assertEqual(f.run.phase2_sequence_status()['gate'],gate)
                files=self.files(f)
                with patch.object(f.store,'locked',side_effect=AssertionError('status writes')):
                    status=f.run.phase2_signal_status()
                self.assertEqual(self.files(f),files);self.assertEqual(status['terminal_state'],expected)
                self.assertTrue(status['publication_required'])
                published=f.run.publish_phase2_signals()
                recovered=f.run.reconcile_phase2_signal_state()
                self.assertEqual(recovered['terminal_state'],expected)
                self.assertTrue(recovered['state_current']);self.assertTrue(recovered['mirrors_current'])
                self.assertFalse(recovered['resume_permitted'])
                self.assertEqual(f.run.bind_phase2_next_review(second.transport_binding)['gate'],gate)
                with self.assertRaisesRegex(ValueError,'blocked by sequence'):f.run.continue_phase2_pass(2,action='admit')
                if expected:
                    self.assertEqual(json.loads(f.store.read('rounds/conflict_report.json'))['terminal_state'],expected)
                    packet=json.loads(f.store.read(published['active']['path']))
                    failure=json.loads(f.store.read(packet['failure']['path']))
                    self.assertEqual(failure['reviewer_final_status'],'not_run')
                    self.assertEqual([r['rounds_used'] for r in failure['profile_status']['profiles']],[1,1,0])
                self.assertEqual(f.store.read('rounds/current_verified.json'),before)
                self.assertEqual((first.calls,second.calls,f.editor.calls),(1,1,0))
                self.reopen(f);self.assertTrue(f.run.reconcile_phase2_signal_state()['state_current'])

    def test_report_prefixes_final_state_loss_and_source_tampering(self):
        f,first,second,bound,result=self.second()
        from whetstone.vnext_verified_materialization import STATE_PATH
        source=bound.request['configuration']['path'];raw=f.store.read(source)
        sync=f.store.synchronize_existing
        def drift(token,path,**kwargs):
            value=sync(token,path,**kwargs)
            if path==source:(f.root/source).write_bytes(raw+b' ')
            return value
        with patch.object(f.store,'synchronize_existing',side_effect=drift):
            with self.assertRaises(ValueError):f.run.publish_phase2_signals()
        self.assertFalse((f.root/ROOT).exists());(f.root/source).write_bytes(raw)
        for suffix in ('/evidence.json','/conflict.json','/commit.json'):
            publish=f.store.publish
            def lost(token,path,value):
                out=publish(token,path,value)
                if path.startswith(ROOT+'/') and path.endswith(suffix):raise OSError('acknowledgement lost')
                return out
            with patch.object(f.store,'publish',side_effect=lost):
                with self.assertRaises(OSError):f.run.publish_phase2_signals()
            self.reopen(f)
        status=f.run.publish_phase2_signals()
        materialize=f.store.materialize
        def lost_state(token,path,value,**kwargs):
            out=materialize(token,path,value,**kwargs)
            if path==STATE_PATH:raise OSError('state acknowledgement lost')
            return out
        with patch.object(f.store,'materialize',side_effect=lost_state):
            with self.assertRaises(OSError):f.run.reconcile_phase2_signal_state()
        self.reopen(f);self.assertTrue(f.run.reconcile_phase2_signal_state()['state_current'])
        packet=json.loads(f.store.read(status['active']['path']))
        for path in (source,packet['evidence']['path'],packet['failure']['path']):
            raw=f.store.read(path);(f.root/path).write_bytes(raw+b' ')
            with self.assertRaises(ValueError):f.run.phase2_signal_status()
            (f.root/path).write_bytes(raw)
        (f.root/'rounds/conflict_report.json').write_bytes(b'unowned')
        with self.assertRaisesRegex(ValueError,'unowned'):f.run.reconcile_phase2_signal_state()
        self.assertEqual((first.calls,second.calls,f.editor.calls),(1,1,0))

    def test_nonblocking_conflict_survives_promotion_and_clean_closeout(self):
        f,first,second,bound,result=self.second('major')
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'operator_or_advice_required')
        published=f.run.publish_phase2_signals();self.assertIsNone(published['terminal_state'])
        f.run.reconcile_phase2_signal_state()
        original={ref['path']:f.store.read(ref['path']) for ref in published['history']}
        f.run.continue_phase2_pass(2,action='advice',advice=self.advice(bound,result))
        f.run.continue_phase2_pass(2,action='admit')
        _,verifier=self.candidate(f,bound.request['round_number'])
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        f.run.publish_phase2_signals();f.run.reconcile_phase2_signal_state()
        for path,raw in original.items():self.assertEqual(f.store.read(path),raw)
        clean=self.next_client(first)
        self.advance(f,clean)
        f.run.prepare_phase2_declaration();self.advance(f,clean)
        f.run.reconcile_phase2_findings();f.run.finish_phase2();f.run.reconcile_phase2_state()
        self.assertTrue(f.run.phase2_closeout()['phase_complete'])
        f.run.publish_phase2_signals();f.run.reconcile_phase2_signal_state()
        self.assertIsNone(f.run.phase2_signal_status()['terminal_state'])
        for path,raw in original.items():self.assertEqual(f.store.read(path),raw)
        # Recovery through the older failure owner cannot replace later signal mirrors.
        mirror=f.store.read('rounds/conflict_report.json')
        f.run.reconcile_phase2_failure_state()
        self.assertEqual(f.store.read('rounds/conflict_report.json'),mirror)
        self.assertEqual((first.calls,second.calls,clean.calls,f.editor.calls,verifier.calls),(1,1,2,1,1))

    def test_final_conflict_precedes_budget_and_nonblocking_churn_can_converge(self):
        for severity,expected in [('minor','CONVERGED'),('blocker','HALTED_CONFLICT')]:
            with self.subTest(severity=severity):
                original_config=self.config
                def config(f):
                    value=original_config(f);value['profiles'][-1]['budget']=1;return value
                with patch.object(self,'config',side_effect=config):f,first=self.first('clarify')
                second=self.next_client(first,clean=False);second.callback=self.response('clarify')
                bound,result,_=self.advance(f,second)
                advice=self.advice(bound,result)
                for row in advice['findings']:row['classification']='deferable'
                f.run.continue_phase2_pass(2,action='advice',advice=advice)
                f.run.prepare_phase2_declaration()
                final=self.next_client(first,clean=False);final.callback=self.response('clarify',severity)
                self.advance(f,final)
                if expected=='HALTED_CONFLICT':
                    status=f.run.phase2_signal_status()
                    self.assertIsNone(status['terminal_state'])
                    self.assertIn('final_findings_reconciliation_uncommitted',status['blocked'])
                f.run.reconcile_phase2_findings()
                f.run.publish_phase2_signals();status=f.run.reconcile_phase2_signal_state()
                if expected=='CONVERGED':
                    self.assertIsNone(status['terminal_state'])
                    f.run.finish_phase2();f.run.reconcile_phase2_state()
                    self.assertTrue(f.run.phase2_closeout()['phase_complete'])
                else:
                    self.assertEqual(status['terminal_state'],expected)
                    self.assertEqual(f.run.phase2_closeout()['gate'],'signal_reporting_required')
                    packet=json.loads(f.store.read(status['active']['path']))
                    failure=json.loads(f.store.read(packet['failure']['path']))
                    self.assertEqual(failure['reviewer_final_status'],'rejected')
                    self.assertEqual(failure['profile_status']['profiles'][-1]['rounds_used'],1)
                    with self.assertRaises(ValueError):f.run.finish_phase2()
                self.assertEqual((first.calls,second.calls,final.calls,f.editor.calls),(1,1,1,0))

    def test_committed_draft_cycle_halts_at_verified_authority(self):
        f,first,_=self.ready()
        first.callback=self.response('clarify','major')
        result=f.run.run_phase2_review(client=first);f.run.consume_phase2_result()
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        f.run.bind_phase2_advice(self.advice(bound,result));ref=f.run.admit_phase2_round()
        number=json.loads(f.store.read(ref['path']))['round_number']
        _,verifier=self.candidate(f,number)
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        second=self.next_client(first,clean=False);second.callback=self.response('clarify','major')
        bound,result,_=self.advance(f,second)
        f.run.continue_phase2_pass(2,action='advice',advice=self.advice(bound,result))
        f.run.continue_phase2_pass(2,action='admit')
        def back(packet):
            content='Queue always waits.\n'
            packet['payloads'][0]['content']=content
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        f.editor.callback=back
        _,second_verifier=self.candidate(f,bound.request['round_number'])
        f.run.verify(client=second_verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'oscillation_halt_required')
        status=f.run.publish_phase2_signals();f.run.reconcile_phase2_signal_state()
        self.assertEqual(status['terminal_state'],'HALTED_OSCILLATION')
        self.assertEqual(json.loads(f.store.read('rounds/oscillation_report.json'))['terminal_state'],'HALTED_OSCILLATION')
        packet=json.loads(f.store.read(status['active']['path']))
        report=json.loads(f.store.read(packet['terminal']['path']))
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_PROMOTED')
        self.assertEqual(report['current_verified_draft_hash'],json.loads(f.store.read('rounds/current_verified.json'))['verified_draft_hash'])
        failure=json.loads(f.store.read(packet['failure']['path']))
        self.assertTrue(failure['unresolved_major_issues'])
        self.assertTrue(failure['profile_status']['unverified_profiles'])
        self.assertEqual((first.calls,second.calls,f.editor.calls,verifier.calls,second_verifier.calls),(1,1,2,1,1))
