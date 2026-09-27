"""Explicit repair admission is distinct from technical retry and interpretation."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_operator as operator
import test_vnext_verified_phase2_client as clients
import test_vnext_verified_history as history
import test_vnext_verified_phase2_signals as signals
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','D8 targets local macOS/APFS')
class Phase2RepairTests(unittest.TestCase):
    setUpClass = operator.Phase2OperatorTests.setUpClass
    fixture = operator.Phase2OperatorTests.fixture
    ready = operator.Phase2OperatorTests.ready
    config = operator.Phase2OperatorTests.config
    files = operator.Phase2OperatorTests.files
    reopen = operator.Phase2OperatorTests.reopen
    review = operator.Phase2OperatorTests.review
    promote = operator.Phase2OperatorTests.promote
    next_client = operator.Phase2OperatorTests.next_client
    advance = operator.Phase2OperatorTests.advance
    advice = operator.Phase2OperatorTests.advice
    candidate = operator.Phase2OperatorTests.candidate
    response = operator.Phase2OperatorTests.response
    corrected = operator.Phase2OperatorTests.corrected
    first = signals.SignalRuntimeTests.first
    second = signals.SignalRuntimeTests.second

    def start(self, **kwargs):
        return clients.VerifiedPhase2ClientTests.start(self, phase2_repair_contract=True, **kwargs)

    def rejected(self):
        f, reviewer, verifier, _, parent, _ = self.corrected(promote=False,reject=True)
        context=f.run.phase2_repair_context(candidate_id=parent['candidate_id'])
        request=dict(schema_version='vnext-phase2-repair-request-v1',
            **{k:context[k] for k in ('job_id','round_number','base_pointer','source_creation','source_verification')},
            operation_ids=[r['operation_id'] for r in context['operations']],
            finding_ids=[r['finding_id'] for r in context['findings'] if r['disposition']!='resolved'],
            limits={**context['limits'],'max_operations':1},decided_by='fixture operator',decided_at=STAMP,
            rationale='Repair the unresolved whole finding in the selected failed operation.')
        return f,reviewer,verifier,parent,request

    def test_repair_child_promotes_and_preserves_parent_report(self):
        f,reviewer,verifier,parent,packet=self.rejected()
        parent_report=f.run.publish_phase2_correction_failure()
        f.run.reconcile_phase2_correction_failure_state()
        saved=self.files(f)
        preview=f.run.admit_phase2_repair(packet,dry_run=True)
        self.assertEqual(saved,self.files(f))
        result=f.run.admit_phase2_repair(packet)
        self.assertEqual(result,preview)
        self.assertEqual(f.run.admit_phase2_repair(packet),result)
        self.reopen(f)
        editor=history.verified.fixtures.Client()
        selected=result['reference'];number=packet['round_number']
        self.assertEqual(f.run.request(round_number=number,client=editor,selected_ref=selected).value.status,'complete')
        child=f.run.register(round_number=number,created_at=STAMP,selected_ref=selected).value
        self.assertNotEqual(child['transaction_id'],parent['transaction_id'])
        context=load_registered_semantic_context(f.store,admission=f.run._history(),candidate_id=child['candidate_id'])
        self.assertIn('repair',context.packet)
        child_verifier=history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=child_verifier,decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome,'promoted')
        f.run.publish_phase2_resolutions();f.run.reconcile_phase2_resolution_state()
        self.advance(f,self.next_client(reviewer))
        status=f.run.phase2_correction_failure_status()
        self.assertIsNone(status['terminal_state']);self.assertIn(parent_report['active'],status['history'])
        for ref in parent_report['history']:
            self.assertEqual(f.store.read(ref['path']),saved[ref['path']])
        self.assertEqual((reviewer.calls,f.editor.calls,verifier.calls,editor.calls,child_verifier.calls),(1,1,1,1,1))

    def test_invalid_repair_selection_and_budgets_refuse_without_writes(self):
        f,_,_,parent,packet=self.rejected()
        before=self.files(f)
        cases=[]
        bad=deepcopy(packet);bad['base_pointer']['hash']='0'*64;cases.append(bad)
        bad=deepcopy(packet);bad['operation_ids']=['op_'+'0'*64];cases.append(bad)
        bad=deepcopy(packet);bad['finding_ids']=['unrelated'];cases.append(bad)
        bad=deepcopy(packet);bad['limits']['max_operations']=100000;cases.append(bad)
        bad=deepcopy(packet);bad['decided_by']=' ';cases.append(bad)
        for bad in cases:
            with self.assertRaises(ValueError):f.run.admit_phase2_repair(bad)
            self.assertEqual(self.files(f),before)

    def test_admission_and_selection_lost_ack_recover_without_clients(self):
        f,reviewer,verifier,parent,packet=self.rejected()
        preview=f.run.admit_phase2_repair(packet,dry_run=True)
        for suffix in ('/admission.json','/followup_transaction.json'):
            publish=f.store.publish
            def lost(token,path,value):
                result=publish(token,path,value)
                if path.endswith(suffix):raise OSError('lost repair acknowledgement')
                return result
            with patch.object(f.store,'publish',side_effect=lost):
                with self.assertRaises(OSError):f.run.admit_phase2_repair(packet)
            self.reopen(f)
        self.assertEqual(f.run.admit_phase2_repair(packet),preview)
        self.assertEqual(f.run.phase2_repair_context(candidate_id=parent['candidate_id'])['selected_transaction'],preview['reference'])
        self.assertEqual((reviewer.calls,f.editor.calls,verifier.calls),(1,1,1))

    def test_source_barrier_and_final_write_ownership_loss(self):
        from whetstone.vnext_local_storage import OwnershipLost
        f,reviewer,verifier,parent,packet=self.rejected()
        path=packet['source_verification']['path'];raw=f.store.read(path)
        sync=f.store.synchronize_existing
        def drift(token,name,**kwargs):
            result=sync(token,name,**kwargs)
            if name==path:(f.root/path).write_bytes(raw+b' ')
            return result
        with patch.object(f.store,'synchronize_existing',side_effect=drift):
            with self.assertRaises(ValueError):f.run.admit_phase2_repair(packet)
        (f.root/path).write_bytes(raw)
        marker=parent['candidate_path'].rsplit('/',1)[0]+'/followup_transaction.json'
        self.assertFalse((f.root/marker).exists())
        publish=f.store.publish
        def lose(token,name,value):
            result=publish(token,name,value)
            if name==marker:f.store._invalidate()
            return result
        with patch.object(f.store,'publish',side_effect=lose):
            with self.assertRaises(OwnershipLost):f.run.admit_phase2_repair(packet)
        self.reopen(f)
        self.assertEqual(f.run.admit_phase2_repair(packet)['record']['request'],packet)
        self.assertEqual((reviewer.calls,f.editor.calls,verifier.calls),(1,1,1))

    def test_unpinned_repair_refuses_before_work(self):
        with patch.object(self,'start',side_effect=lambda **kwargs: clients.VerifiedPhase2ClientTests.start(
                self,phase2_operator_contract=True,**kwargs)):
            f,_,_=self.ready()
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'repair contract'):
            f.run.phase2_repair_context(candidate_id='can_'+'0'*64)
        self.assertEqual(self.files(f),before)

    def test_approved_freeze_preserves_evidence_and_allows_only_report_recovery(self):
        from whetstone.vnext_verified_materialization import STATE_PATH
        f,first,second,bound,_=self.second('minor')
        head=f.store.read('rounds/current_verified.json');draft=f.store.read('spec.md')
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'oscillation_freeze_required')
        f.run.publish_phase2_signals()
        materialize=f.store.materialize
        def lost(token,path,value,**options):
            result=materialize(token,path,value,**options)
            if path==STATE_PATH:raise OSError('lost freeze state acknowledgement')
            return result
        with patch.object(f.store,'materialize',side_effect=lost):
            with self.assertRaises(OSError):f.run.reconcile_phase2_signal_state()
        self.reopen(f)
        status=f.run.reconcile_phase2_signal_state()
        self.assertFalse(status['resume_permitted']);self.assertIsNone(status['terminal_state'])
        self.assertTrue(status['state_current']);self.assertTrue(status['mirrors_current'])
        before=self.files(f)
        with self.assertRaises(ValueError):f.run.phase2_repair_context(candidate_id='can_'+'0'*64)
        with self.assertRaises(ValueError):f.run.phase2_operator_context()
        with self.assertRaises(ValueError):f.run.continue_phase2_pass(2,action='admit')
        with self.assertRaises(ValueError):f.run.request(round_number=bound.request['round_number'],client=f.editor)
        with self.assertRaises(ValueError):f.run.prepare_phase2_declaration()
        with self.assertRaises(ValueError):f.run.finish_phase2()
        self.assertEqual(f.run.bind_phase2_next_review(second.transport_binding)['gate'],'oscillation_freeze_required')
        self.assertFalse(f.run.phase2_closeout()['phase_complete'])
        self.assertEqual(self.files(f),before)
        self.assertEqual(f.store.read('rounds/current_verified.json'),head)
        self.assertEqual(f.store.read('spec.md'),draft)
        self.assertEqual((first.calls,second.calls,f.editor.calls),(1,1,0))
