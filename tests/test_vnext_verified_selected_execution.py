"""Explicit selections reach ordinary work without reopening their parent."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_run import VerifiedRun,open_verified_run
from test_vnext_proposal_requests import Client as Editor
from test_vnext_semantic_requests import Client as Verifier
import test_vnext_verified_semantic_commands as semantic
import test_vnext_verified_operator_commands as operator


class Promoted(Exception):pass


def promote_and_stop(test, command, *args):
    promote=VerifiedRun.promote
    def stop(run,**options):
        result=promote(run,**options)
        test.assertEqual(result.outcome,'promoted')
        raise Promoted()
    with patch.object(VerifiedRun,'promote',stop),test.assertRaises(Promoted):test.call(command,*args)


def accepting_verifier(test):
    clients=[]
    def create(**kwargs):
        with open_verified_run(test.root) as run:
            history=run._history();creation=history.inspect().creations[-1]
            context=load_registered_semantic_context(run.store,admission=history,candidate_id=creation['candidate_id'])
        client=Verifier(context);clients.append(client);return client
    test.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient',side_effect=create)
    return clients


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class SelectedChildExecutionTests(unittest.TestCase):
    setUpClass=semantic.SemanticCommandTests.setUpClass
    setUp=semantic.SemanticCommandTests.setUp
    patch=semantic.SemanticCommandTests.patch
    qualify=semantic.SemanticCommandTests.qualify
    save_config=semantic.SemanticCommandTests.save_config
    clean=staticmethod(semantic.SemanticCommandTests.clean)
    invoke=semantic.SemanticCommandTests.invoke
    files=semantic.SemanticCommandTests.files
    call=semantic.SemanticCommandTests.call
    selected=semantic.SemanticCommandTests.test_answer_and_exact_followup_select_child_without_reopening_parent

    def test_selected_child_timeout_resume_register_verify_and_promote(self):
        self.selected()
        before=self.files();parent_files={p:raw for p,raw in before.items() if '/candidates/' in p}
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('status took fence')):
            code,state=self.call('status','--format','json')
        self.assertEqual(code,0,state);self.assertEqual(state['gate'],'proposal',state)
        self.assertEqual(state['request_status'],'not_started');self.assertIsNone(state['continuation'])
        ref=state['selected_ref'];parent=state['source_candidate'];number=state['round_number']
        self.assertEqual(self.files(),before)
        child_input=json.loads((self.root/ref['path']).read_bytes())
        self.assertNotEqual(child_input['transaction_id'],parent['transaction_id'])
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('fresh child resume took fence')):
            code,result=self.call('resume','--vnext-round',str(number));self.assertEqual(code,2,result)
        def timeout(packet):raise TimeoutError('fixture child Editor timeout')
        editor=Editor(timeout)
        self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=editor)
        code,result=self.call('live-phase1');self.assertEqual(code,2,result)
        self.assertEqual(result['continuation'],'editor',result);self.assertEqual(result['selected_ref'],ref)
        self.assertEqual(editor.calls,1)
        before=self.files()
        code,result=self.call('live-phase1');self.assertEqual(code,2,result)
        self.assertEqual(editor.calls,1);self.assertEqual(self.files(),before)
        code,result=self.call('resume','--vnext-round',str(number),'--dry-run');self.assertEqual(code,0,result)
        self.assertEqual(result['selected_ref'],ref);self.assertEqual(self.files(),before)
        editor.callback=None
        code,result=self.call('resume','--vnext-round',str(number));self.assertEqual(code,0,result)
        self.assertEqual(result['value']['status'],'complete');self.assertEqual(editor.calls,2)
        self.assertIsNotNone(result['value']['reference']);self.assertNotIn('proposal',result['value'])
        with open_verified_run(self.root) as run:self.assertEqual(len(run._history().inspect().creations),1)
        verifiers=accepting_verifier(self)
        promote_and_stop(self,'live-phase1')
        with open_verified_run(self.root) as run:
            view=run._history().inspect();child=view.creations[-1]
            self.assertEqual(len(view.creations),2)
            self.assertEqual(child['transaction_id'],child_input['transaction_id'])
            self.assertNotEqual(child['candidate_id'],parent['candidate_id'])
            self.assertEqual(run.inspect().current_pointer['source_candidate_id'],child['candidate_id'])
        self.assertEqual(editor.calls,2);self.assertEqual(sum(c.calls for c in verifiers),1)
        for path,raw in parent_files.items():self.assertEqual((self.root/path).read_bytes(),raw,path)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class SelectedOperatorExecutionTests(unittest.TestCase):
    setUpClass=operator.OperatorCommandTests.setUpClass
    setUp=operator.OperatorCommandTests.setUp
    patch=operator.OperatorCommandTests.patch
    qualify=operator.OperatorCommandTests.qualify
    save_config=operator.OperatorCommandTests.save_config
    clean=staticmethod(operator.OperatorCommandTests.clean)
    invoke=operator.OperatorCommandTests.invoke
    files=operator.OperatorCommandTests.files
    stage_phase2=operator.OperatorCommandTests.stage_phase2
    ready=operator.OperatorCommandTests.ready
    call=operator.OperatorCommandTests.call
    choices=operator.OperatorCommandTests.choices

    def execute_selection(self,command):
        code,context=self.call('vnext-decisions');self.assertEqual(code,0,context)
        self.assertEqual(len(context['selections']),1)
        selector=context['selections'][0]['path']
        raw=(self.root/selector).read_bytes();before=self.files()
        # Replace the selected receipt immediately before the real admission
        # fence. No admitted record or client invocation may follow it.
        target=VerifiedRun.admit_phase2_operator_round if command=='live-phase2' else VerifiedRun.admit_reviewed_round
        name='admit_phase2_operator_round' if command=='live-phase2' else 'admit_reviewed_round'
        def changed(run,*args,**kwargs):
            (self.root/selector).write_bytes(raw+b' ')
            return target(run,*args,**kwargs)
        with patch.object(VerifiedRun,name,changed):
            code,result=self.call(command,'--vnext-decisions',selector)
        self.assertEqual(code,2,result);self.assertIn('selected operator receipt changed',result['reason'])
        (self.root/selector).write_bytes(raw);self.assertEqual(self.files(),before)
        editor=Editor();self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=editor)
        verifiers=accepting_verifier(self)
        promote_and_stop(self,command,'--vnext-decisions',selector)
        with open_verified_run(self.root) as run:self.assertEqual(run.inspect().current_pointer['promotion_ordinal'],1)
        self.assertEqual(editor.calls,1);self.assertEqual(sum(c.calls for c in verifiers),1)
        self.assertEqual((self.root/selector).read_bytes(),raw)

    def test_phase1_selected_operator_receipt_reaches_promotion(self):
        operator.OperatorCommandTests.test_phase1_options_and_responses_bind_exact_input_without_admitting_work(self)
        self.execute_selection('live-phase1');self.assertEqual(self.reviewer.calls,1)

    def test_phase2_selected_operator_receipt_reaches_promotion(self):
        operator.OperatorCommandTests.test_phase2_options_and_responses_preserve_bound_review_and_entry(self)
        self.execute_selection('live-phase2');self.assertEqual(self.phase2_reviewer.calls,1)


if __name__=='__main__':unittest.main()
