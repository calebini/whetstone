"""Selected child identity and receipt bytes survive command/fence boundaries."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock,patch

import test_vnext_local_storage as storage
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_command_state import candidate_state,proposal_state
from whetstone.vnext_verified_commands import phase1,resume,SelectionChanged
from whetstone.vnext_verified_phase2_commands import execute_phase2
from whetstone.vnext_verified_run import VerifiedRun
from whetstone.vnext_verified_work import VerifiedWorkView
from whetstone.vnext_proposal_requests import ProposalRequestResult


class ChildSelectionTests(unittest.TestCase):
    def select(self, *, marker=True, prepared=False, wrong_parent=False):
        creation=dict(candidate_id='parent',candidate_path='candidates/parent/candidate.md',round_number=2,job_id='job')
        proof=Mock();proof.view.creations=[creation];proof.pointers=[]
        reference=dict(path='transactions/child/admission.json',hash='a'*64)
        packet=dict(job_id='job',candidate_id='other' if wrong_parent else 'parent',transaction_input=reference)
        run=Mock();run.store.read.side_effect=None if marker else FileNotFoundError()
        run.store.read.return_value=canonical_json_bytes(packet)
        proof.reader.json.return_value=packet
        view=SimpleNamespace(prepared=prepared,decision=dict(decision_final=True))
        with patch('whetstone.vnext_verified_semantics.VerifiedSemanticDecisionJournal') as journal, \
             patch('whetstone.vnext_verified_command_state.proposal_state',return_value=dict(gate='proposal')) as proposal:
            journal.return_value._state.return_value=(view,None,None,dict(decision_ordinal=2))
            journal.return_value.paths.return_value=('directory','pending-decision.json')
            result=candidate_state(run,proof)
            return result,proposal.call_args,reference

    def test_only_committed_selection_routes_final_parent_to_child(self):
        state,call,ref=self.select()
        self.assertEqual(state['gate'],'proposal');self.assertEqual(call.kwargs['selected_ref'],ref)
        self.assertEqual(state['source_candidate']['candidate_id'],'parent')
        state,call,_=self.select(marker=False)
        self.assertEqual(state['gate'],'candidate_final');self.assertIsNone(call)

    def test_verification_publication_precedes_child_and_wrong_parent_refuses(self):
        state,call,_=self.select(prepared=True)
        self.assertEqual(state['recovery'],'verification');self.assertIsNone(call)
        with self.assertRaisesRegex(ValueError,'latest candidate'):self.select(wrong_parent=True)

    def test_selected_router_validates_exact_child_and_current_base_before_inspection(self):
        proof=Mock();proof.latest=dict(path='head',hash='b'*64)
        reference=dict(path='child',hash='a'*64);run=Mock();router=Mock()
        source=dict(candidate_id='parent',candidate_creation_ordinal=1)
        from whetstone.vnext_verified_history import _ref
        parent=_ref('rounds/candidate_index/creation-1.json',source)
        router.selected_record.return_value=dict(source_creation=parent)
        router.load_inputs.return_value=dict(base_pointer_ref=proof.latest)
        def inspect(store,*,load_inputs,validate_authority):
            load_inputs(store.read)
            return SimpleNamespace(status='complete',request_id='child-request',attempts=1)
        with patch('whetstone.vnext_verified_history._VerifiedTransactions',return_value=router) as constructor, \
             patch('whetstone.vnext_proposal_requests.inspect_proposal_request',side_effect=inspect):
            state=proposal_state(run,proof,2,selected_ref=reference,source_candidate=source)
            self.assertEqual(state['gate'],'registration');self.assertEqual(state['selected_ref'],reference)
            constructor.assert_called_once_with(proof.store,original=proof.admission,selected_ref=reference)
            router.validate_selected.assert_called_once_with(run.store.read)
            router.load_inputs.return_value=dict(base_pointer_ref={'path':'old','hash':'c'*64})
            with self.assertRaisesRegex(ValueError,'exact current base'):
                proposal_state(run,proof,2,selected_ref=reference,source_candidate=source)
            router.selected_record.return_value=dict(source_creation={'path':'other','hash':'c'*64})
            with self.assertRaisesRegex(ValueError,'another parent'):
                proposal_state(run,proof,2,selected_ref=reference,source_candidate=source)


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class SelectedExecutionGuardTests(unittest.TestCase):
    setUp=storage.LocalStorageTests.setUp
    open_store=storage.LocalStorageTests.open_store

    def scenario(self, phase, *, race=False):
        ref=dict(path='child/input.json',hash='a'*64)
        state=dict(gate='proposal',phase=phase,recovery=None,continuation=None,round_number=2,
                   request_status='not_started',selected_ref=ref)
        run=Mock(spec=VerifiedRun);run.store=self.store;run.state=deepcopy(state);events=[]
        def request(**kwargs):
            if race:run.state['selected_ref']['hash']='b'*64
            with self.store.locked(lambda read:None):
                self.assertEqual(kwargs['selected_ref'],ref);events.append('request')
                run.state=dict(state,gate='registration',request_status='complete')
            return VerifiedWorkView('proposal_complete', {}, value=ProposalRequestResult(
                'child-request', 'complete', 2, proposal={'payload': b'internal payload'},
                reference={'path': 'proposal.json', 'hash': 'c'*64}))
        def register(**kwargs):
            with self.store.locked(lambda read:None):
                self.assertEqual(kwargs['selected_ref'],ref);events.append('register')
                run.state=dict(state,gate='candidate_final')
        run.request.side_effect=request;run.register.side_effect=register
        return run,state,events

    def invoke(self,run,phase):
        with patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda r:deepcopy(r.state)), \
             patch('whetstone.vnext_verified_phase2_commands.inspect_command',side_effect=lambda r:deepcopy(r.state)), \
             patch('whetstone.vnext_verified_phase2_commands.optional',return_value=b'entry'), \
             patch('whetstone.vnext_verified_commands._client'),patch('whetstone.vnext_verified_phase2_commands._client'):
            return (phase1 if phase=='phase_1' else execute_phase2)(run,SimpleNamespace(),{}, {})

    def test_both_phases_forward_exact_child_through_request_and_registration(self):
        for phase in ('phase_1','phase_2'):
            with self.subTest(phase=phase):
                run,_,events=self.scenario(phase)
                self.assertEqual(self.invoke(run,phase)['gate'],'candidate_final')
                self.assertEqual(events,['request','register'])

    def test_child_replacement_inside_fence_refuses_in_both_phases(self):
        for phase in ('phase_1','phase_2'):
            with self.subTest(phase=phase):
                run,_,events=self.scenario(phase,race=True)
                with self.assertRaises(SelectionChanged):self.invoke(run,phase)
                self.assertEqual(events,[])

    def test_phase1_resume_keeps_child_reference_and_stops_before_registration(self):
        run,state,events=self.scenario('phase_1')
        state.update(continuation='editor',request_status='timeout');run.state=deepcopy(state)
        with patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda r:deepcopy(r.state)), \
             patch('whetstone.vnext_verified_commands._client'):
            result=resume(run,SimpleNamespace(dry_run=False,vnext_round=2),{}, {},state)
        self.assertEqual(result['value']['status'],'complete')
        self.assertEqual(result['value']['reference']['path'],'proposal.json')
        self.assertNotIn('proposal',result['value'])
        canonical_json_bytes(result)
        self.assertEqual(events,['request']);self.assertTrue(run.request.call_args.kwargs['continuation'])
        state.update(phase='phase_2',continuation='unsupported_phase2_continuation')
        with self.assertRaisesRegex(ValueError,'outside this release'):
            resume(run,SimpleNamespace(dry_run=False,vnext_round=2),{}, {},state)


if __name__=='__main__':unittest.main()
