"""A config-selected interpretation answer selects a child without executing it."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_identity import binding_id
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_protocol import RULES
from whetstone.vnext_verified_history import _VerifiedAnswerSource
from whetstone.vnext_verified_operator import VerifiedOperator
from whetstone.vnext_verified_run import open_verified_run
import test_vnext_unit_preflight as unit
import test_vnext_verified_cli as cli
import test_vnext_verified_operator_commands as operators
from test_vnext_proposal_requests import Client as Editor
from test_vnext_semantic_requests import Client as Verifier
from test_vnext_semantic_answers import input_for


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class SemanticCommandTests(unittest.TestCase):
    setUpClass=cli.VerifiedCLITests.setUpClass
    patch=cli.VerifiedCLITests.patch
    qualify=cli.VerifiedCLITests.qualify
    save_config=cli.VerifiedCLITests.save_config
    clean=staticmethod(cli.VerifiedCLITests.clean)
    invoke=cli.VerifiedCLITests.invoke
    files=cli.VerifiedCLITests.files
    call=operators.OperatorCommandTests.call

    def setUp(self):
        setup=unit.UnitPreflightTests.setUp
        def with_authority(test):
            setup(test);f=test.c.f
            ref=f.save('inputs/waiting-authority.md',b'Queue waiting applies to each work start.\n')
            target=next(r for r in f.authority['bindings'] if r['role']=='mutable_target')
            authority=dict(path=ref['path'],content_hash=ref['hash'],role='normative_authority',
                authority_scopes=target['authority_scopes'],effective_horizon='current',mutable=False,
                may_introduce_requirements=True)
            authority['binding_id']=binding_id(authority);f.authority['bindings'].append(authority)
            f.authority['precedence']=[dict(authority_scope=scope,
                ordered_binding_ids=[authority['binding_id'],target['binding_id']],conflict_policy='pause')
                for scope in target['authority_scopes']]
            f.rebind()
        with patch.object(unit.UnitPreflightTests,'setUp',with_authority):cli.VerifiedCLITests.setUp(self)

    def test_answer_and_exact_followup_select_child_without_reopening_parent(self):
        self.qualify();code,result=self.call('vnext-admit');self.assertEqual(code,0,result)
        head=(self.root/'rounds/current_verified.json').read_bytes()
        self.reviewer.callback=canonical_json_bytes
        editor=Editor();verifiers=[]
        self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=editor)
        def verifier(**kwargs):
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
            client.responses=[canonical_json_bytes(response)];verifiers.append(client);return client
        self.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient',side_effect=verifier)
        code,result=self.call('live-phase1');self.assertEqual(code,2,result)
        self.assertEqual(result['gate'],'candidate_final',result)
        parent=result['candidate']['candidate_id'];self.assertTrue(result['decision']['decision_final'])
        self.assertFalse(result['decision']['promotion_permitted'])
        with open_verified_run(self.root) as run:
            source=_VerifiedAnswerSource(run.store,admission=run._history(),candidate_id=parent,require_current=True)
            packet=input_for(source)
        path=self.config_path.parent/'semantic-answer.json';raw=canonical_json_bytes(packet);path.write_bytes(raw)
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('inspection took fence')):
            code,answers=self.call('vnext-semantic-answers','--candidate',parent);self.assertEqual(code,0,answers)
            code,preview=self.call('vnext-semantic-answer','--candidate',parent,'--input',str(path),'--dry-run')
        self.assertEqual(code,0,preview);self.assertEqual(self.files(),before)
        submit=VerifiedOperator.submit_answer
        def changed(owner,**kwargs):
            path.write_bytes(raw+b' ');return submit(owner,**kwargs)
        with patch.object(VerifiedOperator,'submit_answer',changed):
            code,result=self.call('vnext-semantic-answer','--candidate',parent,'--input',str(path))
        self.assertEqual(code,2,result);self.assertIn('selected operator input changed',result['reason'])
        self.assertEqual(self.files(),before);path.write_bytes(raw)
        code,answer=self.call('vnext-semantic-answer','--candidate',parent,'--input',str(path))
        self.assertEqual(code,0,answer);self.assertEqual(answer['value'],preview['value'])
        self.assertEqual(answer['value']['response']['authorized_effects'],[])
        ref=answer['value']['reference'];before=self.files()
        code,result=self.call('vnext-semantic-followup','--candidate',parent,
            '--answer-receipt',ref['path'],'--answer-hash','f'*64)
        self.assertEqual(code,2,result);self.assertEqual(self.files(),before)
        code,selected=self.call('vnext-semantic-followup','--candidate',parent,
            '--answer-receipt',ref['path'],'--answer-hash',ref['hash'])
        self.assertEqual(code,0,selected);self.assertEqual(selected['outcome'],'followup_selected')
        after=self.files()
        code,again=self.call('vnext-semantic-followup','--candidate',parent,
            '--answer-receipt',ref['path'],'--answer-hash',ref['hash'])
        self.assertEqual(code,0,again);self.assertEqual(again['value'],selected['value'])
        self.assertEqual(self.files(),after)
        for name,raw in before.items():self.assertEqual((self.root/name).read_bytes(),raw,name)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),head)
        self.assertEqual((self.reviewer.calls,editor.calls,sum(v.calls for v in verifiers)),(1,1,1))
        with open_verified_run(self.root) as run:
            self.assertEqual(len(run._history().inspect().creations),1)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())


if __name__=='__main__':unittest.main()
