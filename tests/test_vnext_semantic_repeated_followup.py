import json
import sys
import unittest

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_answers import SemanticAnswerSource,submit_semantic_answer
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from whetstone.vnext_semantic_followup_admission import SemanticFollowupAdmission,admit_semantic_followup
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from vnext_fixtures import STAMP
import test_vnext_semantic_followup_admission as fixtures


def unresolved_interpretation(client,context):
    packet=context.packet
    target=next(row for row in packet['authority_map']['bindings'] if row['role']=='mutable_target')
    authority=packet['dependency_context'][0]
    def alternative(identifier,text,interpretation):
        raw=text.encode()
        return dict(authority_binding_id=identifier,interpretation=interpretation,
                    evidence=dict(byte_start=0,byte_end=len(raw),content_hash=sha256_bytes(raw),text=text))
    response=json.loads(client.valid)
    response.update(authority_compliance='uncertain',operator_decision_required=True,verdict='operator_decision_required',
        authority_choice=dict(question='Which waiting interpretation should the next transaction preserve?',
            authority_scope=target['authority_scopes'][0],alternatives=[
                alternative(target['binding_id'],packet['seed'],'Waiting is scoped to queue startup.'),
                alternative(authority['binding']['binding_id'],authority['content'],'Waiting is scoped to every work start.')]),
        uncertainty_resolutions=[dict(field_path='authority_compliance',
            policy_rule_id=fixtures.answers.requests.RULES['authority_choice'],
            disposition='operator_decision_required',decision_id=None)])
    return canonical_json_bytes(response)


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class RepeatedSemanticFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.SemanticFollowupAdmissionTests.setUpClass()

    def test_rejected_v3_child_can_receive_a_distinct_answer_and_produce_a_third_candidate(self):
        owner=fixtures.SemanticFollowupAdmissionTests();owner.setUp();self.addCleanup(owner.doCleanups)
        original_files=fixtures.answers.files(owner.subject)
        seed=owner.store.read('rounds/current_verified.json')
        source_id=owner.subject.identifier;answer=owner.answer
        creations=[owner.subject.creation];contexts=[owner.subject.context];plans=[];clients=[]
        source_questions=[owner.question_id]
        for index in (1,2):
            reference=admit_semantic_followup(owner.store,original=owner.original,
                candidate_id=source_id,answer_reference=answer['reference'])
            selected=SemanticFollowupAdmission(owner.store,original=owner.original,selected_ref=reference)
            plan=prepare_unit_preflight(**selected.load_inputs(owner.store.read,1)).plan;plans.append(plan)
            self.assertEqual(plan['semantic_origin']['source_candidate_id'],source_id)
            print(f'follow-up {index} explicitly admitted from candidate {index}',flush=True)
            editor=fixtures.proposals.Client();clients.append(editor)
            self.assertEqual(selected.request(client=editor).status,'complete')
            creation=selected.register(created_at=STAMP);creations.append(creation)
            self.assertEqual(creation['candidate_creation_ordinal'],index+1)
            context=load_registered_semantic_context(owner.store,admission=selected,candidate_id=creation['candidate_id'])
            contexts.append(context)
            verifier=fixtures.answers.requests.Client(context);clients.append(verifier)
            if index==1:verifier.responses=[unresolved_interpretation(verifier,context)]
            result,view=selected.verify(candidate_id=creation['candidate_id'],client=verifier,decided_at=STAMP)
            self.assertEqual(result.status,'complete')
            self.assertEqual(view.decision['candidate_disposition'],
                             'CANDIDATE_REJECTED' if index==1 else 'CANDIDATE_VERIFIED')
            self.assertFalse(view.decision['promotion_permitted'])
            print(f'candidate {index+1} independently decided',flush=True)
            if index==1:
                source_id=creation['candidate_id']
                source=SemanticAnswerSource(owner.store,admission=selected,candidate_id=source_id)
                source_questions.append(source.request['decision_id'])
                answer=submit_semantic_answer(owner.store,admission=selected,packet=fixtures.answers.input_for(source))
                before_third=fixtures.answers.files(owner.subject)
        self.assertEqual(plans[0]['semantic_origin']['editing_plan_hash'],plans[1]['semantic_origin']['editing_plan_hash'])
        for field in ('candidate_id','transaction_id','proposal_id'):
            self.assertEqual(len({row[field] for row in creations}),3,field)
        self.assertEqual({row['round_number'] for row in creations},{1})
        journal=SemanticDecisionJournal(selected.registry(),admission=selected)
        for creation,question,context in zip(creations[:2],source_questions,contexts[:2]):
            view=journal.inspect(creation['candidate_id'])
            self.assertTrue(view.decision['decision_final'])
            self.assertEqual(view.decision['candidate_disposition'],'CANDIDATE_REJECTED')
            self.assertEqual(view.decision['outstanding_decision_ids'],[question])
            self.assertEqual(load_registered_semantic_context(owner.store,admission=selected,
                candidate_id=creation['candidate_id']).raw,context.raw)
        after=fixtures.answers.files(owner.subject)
        for retained in (original_files,before_third):
            self.assertTrue(all(after.get(path)==raw for path,raw in retained.items()))
        self.assertEqual(owner.store.read('rounds/current_verified.json'),seed)
        self.assertEqual([client.calls for client in clients],[1,1,1,1])
        self.assertEqual(selected.request(client=object()).status,'complete')


if __name__=='__main__':unittest.main()
