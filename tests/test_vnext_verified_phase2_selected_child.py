"""A Phase 2 interpretation child uses its own request and verification."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_protocol import RULES
from whetstone.vnext_verified_history import _VerifiedAnswerSource
from whetstone.vnext_verified_run import open_verified_run
from test_vnext_semantic_answers import input_for
from test_vnext_proposal_requests import Client as Editor
from test_vnext_semantic_requests import Client as Verifier
import test_vnext_verified_semantic_commands as semantic
import test_vnext_verified_reviewer_handoff as handoff
from test_vnext_verified_selected_execution import accepting_verifier,promote_and_stop


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class Phase2SelectedChildTests(unittest.TestCase):
    setUpClass=semantic.SemanticCommandTests.setUpClass
    setUp=semantic.SemanticCommandTests.setUp
    patch=semantic.SemanticCommandTests.patch
    qualify=semantic.SemanticCommandTests.qualify
    save_config=semantic.SemanticCommandTests.save_config
    clean=staticmethod(semantic.SemanticCommandTests.clean)
    invoke=semantic.SemanticCommandTests.invoke
    files=semantic.SemanticCommandTests.files
    call=semantic.SemanticCommandTests.call
    ready=handoff.ReviewerHandoffTests.ready
    stage_phase2=handoff.ReviewerHandoffTests.stage_phase2

    def test_phase2_interpretation_child_reaches_independent_promotion(self):
        self.ready()
        self.patch('whetstone.live_phase2.LivePhase2Runner',side_effect=AssertionError('legacy executor'))
        parent_editor=Editor();parents=[]
        self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=parent_editor)
        def question(**kwargs):
            with open_verified_run(self.root) as run:
                history=run._history();creation=history.inspect().creations[-1]
                context=load_registered_semantic_context(run.store,admission=history,candidate_id=creation['candidate_id'])
            client=Verifier(context);packet=context.packet
            target=next(r for r in packet['authority_map']['bindings'] if r['role']=='mutable_target')
            authority=next(r for r in packet['dependency_context'] if r['binding']['role']=='normative_authority')
            def alternative(identifier,text,interpretation):
                return dict(authority_binding_id=identifier,interpretation=interpretation,
                    evidence=dict(byte_start=0,byte_end=len(text.encode()),content_hash=sha256_bytes(text.encode()),text=text))
            response=json.loads(client.valid)
            response.update(authority_compliance='uncertain',operator_decision_required=True,
                verdict='operator_decision_required',authority_choice=dict(question='Which interpretation should a new transaction address?',
                    authority_scope=target['authority_scopes'][0],alternatives=[
                        alternative(target['binding_id'],packet['seed'],'Waiting is scoped to queue startup.'),
                        alternative(authority['binding']['binding_id'],authority['content'],'Waiting is scoped to each work start.')]),
                uncertainty_resolutions=[dict(field_path='authority_compliance',policy_rule_id=RULES['authority_choice'],
                    disposition='operator_decision_required',decision_id=None)])
            client.responses=[canonical_json_bytes(response)];parents.append(client);return client
        self.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient',side_effect=question)
        code,result=self.call('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(result['gate'],'candidate_final',result)
        parent=result['candidate'];self.assertFalse(result['decision']['promotion_permitted'])
        head=(self.root/'rounds/current_verified.json').read_bytes()
        entry=(self.root/'rounds/phase2/entry.json').read_bytes()
        with open_verified_run(self.root) as run:
            source=_VerifiedAnswerSource(run.store,admission=run._history(),candidate_id=parent['candidate_id'],require_current=True)
            answer=input_for(source)
        path=self.config_path.parent/'phase2-answer.json';path.write_bytes(canonical_json_bytes(answer))
        code,result=self.call('vnext-semantic-answer','--candidate',parent['candidate_id'],'--input',str(path))
        self.assertEqual(code,0,result);receipt=result['value']['reference']
        code,result=self.call('vnext-semantic-followup','--candidate',parent['candidate_id'],
            '--answer-receipt',receipt['path'],'--answer-hash',receipt['hash'])
        self.assertEqual(code,0,result);ref=result['value']
        before=self.files();parent_files={p:raw for p,raw in before.items() if '/candidates/' in p}
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('status took fence')):
            code,state=self.call('status','--format','json')
        self.assertEqual(code,0,state)
        self.assertEqual(state['recovery'],'correction_failure_projection',state)
        self.assertEqual(self.files(),before)
        # Child selection retires the active parent failure. Repair its stale
        # state projection first, without spending the child's Editor allowance.
        code,result=self.call('resume');self.assertEqual(code,0,result)
        self.assertEqual(parent_editor.calls,1);self.assertEqual(sum(c.calls for c in parents),1)
        self.assertEqual(self.phase2_reviewer.calls,1)
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('status took fence')):
            code,state=self.call('status','--format','json')
        self.assertEqual(code,0,state);self.assertEqual(state['gate'],'proposal',state)
        self.assertEqual(state['selected_ref'],ref);self.assertIsNone(state['continuation'])
        code,result=self.call('resume','--continue');self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),head)
        editor=Editor();self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=editor)
        verifiers=accepting_verifier(self)
        promote_and_stop(self,'live-phase2')
        with open_verified_run(self.root) as run:
            view=run._history().inspect();child=view.creations[-1]
            self.assertEqual(len(view.creations),2)
            self.assertNotEqual(child['candidate_id'],parent['candidate_id'])
            self.assertNotEqual(child['transaction_id'],parent['transaction_id'])
            self.assertEqual(run.inspect().current_pointer['source_candidate_id'],child['candidate_id'])
        self.assertEqual((parent_editor.calls,editor.calls,sum(c.calls for c in parents),sum(c.calls for c in verifiers)),(1,1,1,1))
        self.assertEqual(self.phase2_reviewer.calls,1)
        self.assertEqual((self.root/'rounds/phase2/entry.json').read_bytes(),entry)
        for path,raw in parent_files.items():self.assertEqual((self.root/path).read_bytes(),raw,path)


if __name__=='__main__':unittest.main()
