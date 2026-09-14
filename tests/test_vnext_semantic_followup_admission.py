from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_local_storage import Publication,StorageWriteError
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_answers import SemanticAnswerSource,submit_semantic_answer
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from whetstone.vnext_semantic_followup_admission import SemanticFollowupAdmission,admit_semantic_followup
from whetstone.vnext_semantic_followup_admission import _ReadOnlyStore
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from vnext_consuming_suite_fixture import consuming_suite
from vnext_fixtures import STAMP
import test_vnext_semantic_answers as answers
import test_vnext_proposal_requests as proposals


def admission_suite(test,directory):
    return consuming_suite(test,directory,
        additional_schemas=answers.SEMANTIC_SCHEMAS|answers.REQUEST_SCHEMAS|answers.ANSWER_SCHEMAS|{
            'mutation_plan_v3','vnext_semantic_followup_input_v1','vnext_semantic_followup_selection_v1'},
        additional_algorithms=(*answers.SEMANTIC_ALGORITHMS,'vnext_semantic_requests_v1','vnext_semantic_decisions_v1',
            'vnext_semantic_answers_v1','vnext_semantic_followup_preflight_v1','vnext_semantic_followup_admission_v1'),
        algorithm_overrides={'semantic_verifier_policy_version':answers.POLICY_VERSION})


@unittest.skipUnless(sys.platform=='darwin','Proposed local storage targets macOS/APFS')
class SemanticFollowupAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):answers.requests.SemanticRequestTests.setUpClass()

    def setUp(self):
        with patch.object(answers,'answer_suite',admission_suite):self.subject=answers.subject_for(self)
        self.original=self.subject.admission;self.store=self.subject.store
        source=SemanticAnswerSource(self.store,admission=self.original,candidate_id=self.subject.identifier)
        self.question_id=source.request['decision_id']
        self.answer=submit_semantic_answer(self.store,admission=self.original,packet=answers.input_for(source))

    def admit(self):
        return admit_semantic_followup(self.store,original=self.original,candidate_id=self.subject.identifier,
                                       answer_reference=self.answer['reference'])

    def test_actual_same_round_child_registers_and_verifies_without_rewriting_rejected_parent(self):
        before=answers.files(self.subject)
        reference=self.followup_reference=self.admit()
        print('follow-up selection committed',flush=True)
        selected=SemanticFollowupAdmission(self.store,original=self.original,selected_ref=reference)
        inputs=selected.load_inputs(self.store.read,1);plan=prepare_unit_preflight(**inputs).plan
        self.assertEqual(plan['semantic_origin']['source_candidate_id'],self.subject.identifier)
        editor=self.child_editor=proposals.Client()
        request=selected.request(client=editor)
        self.assertEqual(request.status,'complete')
        print('follow-up Editor request complete',flush=True)
        creation=self.child_creation=selected.register(created_at=STAMP)
        self.assertEqual(creation['round_number'],1)
        self.assertEqual(creation['candidate_creation_ordinal'],2)
        self.assertNotEqual(creation['candidate_id'],self.subject.identifier)
        self.assertNotEqual(creation['transaction_id'],self.subject.creation['transaction_id'])
        print('second candidate registered',flush=True)
        context=load_registered_semantic_context(self.store,admission=selected,candidate_id=creation['candidate_id'])
        verifier=self.child_verifier=answers.requests.Client(context)
        result,view=selected.verify(candidate_id=creation['candidate_id'],client=verifier,decided_at=STAMP)
        self.assertEqual(result.status,'complete')
        self.assertEqual(view.decision['candidate_disposition'],'CANDIDATE_VERIFIED')
        self.assertFalse(view.decision['promotion_permitted'])
        print('second candidate independently verified',flush=True)
        journal=SemanticDecisionJournal(selected.registry(),admission=selected)
        parent=journal.inspect(self.subject.identifier)
        self.assertEqual(parent.decision['candidate_disposition'],'CANDIDATE_REJECTED')
        self.assertEqual(parent.decision['outstanding_decision_ids'],[self.question_id])
        self.assertEqual(selected.request(client=object()).reference,request.reference)
        self.assertEqual(selected.register(created_at='2031-01-01T00:00:00Z'),creation)
        again,final=selected.verify(candidate_id=creation['candidate_id'],client=object(),decided_at='2031-01-01T00:00:00Z')
        self.assertEqual(final.decision,view.decision)
        self.assertEqual(again.receipt,result.receipt)
        self.assertEqual(self.admit(),reference)
        after=answers.files(self.subject)
        self.assertTrue(all(after.get(path)==raw for path,raw in before.items()))
        self.assertEqual((self.subject.editor.calls,self.subject.client.calls,editor.calls,verifier.calls),(1,1,1,1))
        self.assertEqual(load_registered_semantic_context(self.store,admission=selected,candidate_id=self.subject.identifier).raw,
                         self.subject.context.raw)

    def test_prepared_input_and_lost_selection_acknowledgement_recover_without_clients(self):
        original=self.store.publish;captured={}
        def stop(token,path,value):
            result=original(token,path,value)
            if path.endswith('/admission.json'):
                captured.update(path=path,hash=sha256_bytes(canonical_json_bytes(value)))
                raise OSError('scripted prepared follow-up input')
            return result
        with patch.object(self.store,'publish',side_effect=stop):
            with self.assertRaisesRegex(OSError,'prepared follow-up'):self.admit()
        selected=SemanticFollowupAdmission(self.store,original=self.original,selected_ref=captured)
        editor=proposals.Client();before=answers.files(self.subject)
        with self.assertRaises(FileNotFoundError):selected.request(client=editor)
        self.assertEqual(answers.files(self.subject),before);self.assertEqual(editor.calls,0)
        selection_path=self.subject.creation['candidate_path'].rsplit('/',1)[0]+'/followup_transaction.json'
        write=self.store._tree.write
        def lost(path,raw,**options):
            result=write(path,raw,**options)
            if path==selection_path:
                raise StorageWriteError(Publication('outcome_requires_reconciliation',path,result.hash),'scripted selection acknowledgement loss')
            return result
        with patch.object(self.store._tree,'write',side_effect=lost):
            with self.assertRaises(StorageWriteError):self.admit()
        self.assertIsNone(self.store._token)
        published=[]
        def observe(token,path,value):
            result=original(token,path,value);published.append(path);return result
        with patch.object(self.store,'publish',side_effect=observe):
            self.assertEqual(self.admit(),captured)
        self.assertEqual(published[-2:],[captured['path'],selection_path])
        self.assertEqual(prepare_unit_preflight(**selected.load_inputs(self.store.read,1)).plan['schema_version'],'mutation-plan-v3')
        self.assertEqual((self.subject.editor.calls,self.subject.client.calls,editor.calls),(1,1,0))

    def test_missing_source_and_changed_selection_never_enable_request_or_expand_scope(self):
        reference=self.admit();selected=SemanticFollowupAdmission(self.store,original=self.original,selected_ref=reference)
        editor=proposals.Client();root=self.subject.fixture.root
        record=json.loads(self.store.read(reference['path']))
        selection_path=self.subject.creation['candidate_path'].rsplit('/',1)[0]+'/followup_transaction.json'
        paths=[record['source_creation']['path'],record['source_verification']['path'],
               record['answer_receipt']['path'],reference['path'],selection_path]
        for relative in paths:
            path=root/relative;raw=path.read_bytes();path.unlink();before=answers.files(self.subject)
            with self.subTest(path=relative),self.assertRaises((ValueError,FileNotFoundError)):
                selected.request(client=editor)
            self.assertEqual(answers.files(self.subject),before);path.write_bytes(raw)
        path=root/selection_path;raw=path.read_bytes();packet=json.loads(raw)
        packet['transaction_input']['hash']='f'*64;path.write_bytes(canonical_json_bytes(packet))
        before=answers.files(self.subject)
        with self.assertRaisesRegex(ValueError,'committed selection'):selected.request(client=editor)
        self.assertEqual(answers.files(self.subject),before);path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'different follow-up'):
            admit_semantic_followup(self.store,original=self.original,candidate_id=self.subject.identifier,
                                    answer_reference={**self.answer['reference'],'hash':'f'*64})
        self.assertEqual(editor.calls,0)

    def test_historical_prefix_cannot_write_consume_itself_or_alias_admission_paths(self):
        reference=self.admit()
        historical=SemanticFollowupAdmission(_ReadOnlyStore(self.store),original=self.original,
                                             selected_ref=reference,history_limit=1)
        before=answers.files(self.subject)
        self.assertEqual(len(historical.registry().inspect().events),1)
        with self.assertRaisesRegex(ValueError,'read-only'):historical.registry().reconcile()
        with self.assertRaisesRegex(ValueError,'read-only'):
            historical.registry().register(round_number=1,proposal_id=self.subject.creation['proposal_id'],created_at=STAMP)
        with self.assertRaisesRegex(ValueError,'read-only'):historical.store.locked(lambda read:None)
        record=json.loads(self.store.read(reference['path']))
        with self.assertRaisesRegex(ValueError,'precede'):
            historical._derive(historical.store.read,record)
        self.assertEqual(answers.files(self.subject),before)
        alias='inputs/followup-alias.json'
        self.subject.fixture.root.joinpath(alias).write_bytes(canonical_json_bytes(record))
        selected=SemanticFollowupAdmission(self.store,original=self.original,selected_ref={**reference,'path':alias})
        editor=proposals.Client();before=answers.files(self.subject)
        with self.assertRaisesRegex(ValueError,'canonical transaction path'):selected.request(client=editor)
        self.assertEqual(answers.files(self.subject),before);self.assertEqual(editor.calls,0)

    def test_captured_editor_response_and_completed_reentry_need_no_adapter(self):
        reference=self.admit();selected=SemanticFollowupAdmission(self.store,original=self.original,selected_ref=reference)
        original=self.store.publish;editor=proposals.Client()
        def stop(token,path,value):
            result=original(token,path,value)
            if '/attempts/1/response.json' in path:raise OSError('scripted captured follow-up response')
            return result
        with patch.object(self.store,'publish',side_effect=stop):
            with self.assertRaisesRegex(OSError,'captured follow-up'):selected.request(client=editor)
        before=answers.files(self.subject)
        self.assertEqual(selected.request(client=object()).status,'continuation_required')
        self.assertEqual(answers.files(self.subject),before)
        result=selected.request(client=object(),continuation=True)
        self.assertEqual(result.status,'complete')
        before=answers.files(self.subject)
        self.assertEqual(selected.request(client=object()),result)
        self.assertEqual(answers.files(self.subject),before);self.assertEqual(editor.calls,1)

    def test_deterministic_rejection_of_child_never_invokes_verifier(self):
        reference=self.admit();selected=SemanticFollowupAdmission(self.store,original=self.original,selected_ref=reference)
        def weaken(packet):
            text='Queue sometimes waits.\n';packet['payloads'][0]['content']=text
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(text.encode())
            return canonical_json_bytes(packet)
        editor=proposals.Client(weaken)
        self.assertEqual(selected.request(client=editor).status,'complete')
        creation=selected.register(created_at=STAMP)
        class NoVerifier:
            calls=0
            def verify(self,prompt):
                self.calls+=1
                raise AssertionError('Deterministic failure cannot reach Verifier')
        verifier=NoVerifier()
        result,view=selected.verify(candidate_id=creation['candidate_id'],client=verifier,decided_at=STAMP)
        self.assertIsNone(result)
        self.assertEqual((view.decision['deterministic_result'],view.decision['semantic_result']),('fail','not_run'))
        self.assertEqual(view.decision['candidate_disposition'],'CANDIDATE_REJECTED')
        self.assertEqual(verifier.calls,0)


if __name__=='__main__':unittest.main()
