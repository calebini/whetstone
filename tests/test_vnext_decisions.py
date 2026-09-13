"""Exact operator choices stay bound to their request and original finding."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_decisions import bind_response, decision_request, derived_task
from vnext_fixtures import Bundle, ISSUE, STAMP


class MutationDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.suite=validate_contract_suite()

    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.b=Bundle(Path(self.tmp.name),self.suite)
        self.finding={'finding_id':ISSUE,'classification':'operator_decision_required','source_feedback_ids':['fb-1']}
        self.targets=list(self.b.plan['allowed_section_ids'])
        self.refs=[{'path':'reviewer_feedback.json','hash':'1'*64}]
        self.options=[{'option_id':'approve_exact_weakening','description':'Permit precisely the requested weakening.',
                       'authorized_effects':['weaken'],'authorized_deletion_unit_ids':[]},
                      {'option_id':'defer','description':'Keep this unresolved without editing.',
                       'authorized_effects':[],'authorized_deletion_unit_ids':[]}]
        self.kwargs=dict(job=self.b.job,base_hash=self.b.seed['hash'],finding=self.finding,targets=self.targets,feedback_refs=self.refs)
        self.request=decision_request(**self.kwargs,options=self.options)
        self.response={'schema_version':'operator-decision-response-v1','job_id':self.b.job['job_id'],'response_id':'',
            'decision_id':self.request['decision_id'],'decision_request_hash':sha256_bytes(canonical_json_bytes(self.request)),
            'base_draft_hash':self.b.seed['hash'],'authority_map_hash':self.b.job['authority_map_hash'],
            'scope_contract_hash':self.b.job['scope_contract_hash'],'selected_option_id':'approve_exact_weakening',
            'authorized_effects':['weaken'],'authorized_deletion_unit_ids':[],'rationale':'Explicit fictional test approval.',
            'decided_by':'fixture operator','decided_at':STAMP}
        self.response['response_id']=ids.response_id(self.response)

    def bind(self,response=None,request=None,**overrides):
        return bind_response(response or self.response,request or self.request,
                             **{**self.kwargs,**overrides},suite=self.suite)

    def test_exact_response_creates_distinct_task_without_relabeling_original(self):
        before=deepcopy(self.finding);response,digest=self.bind()
        task=derived_task(self.finding,response,self.request)
        self.assertEqual(self.finding,before)
        self.assertNotEqual(task['finding_id'],self.finding['finding_id'])
        self.assertEqual(task['original_finding_id'],self.finding['finding_id'])
        self.assertEqual(task['classification'],'editor_fixable')
        self.assertEqual(task['decision_response_id'],response['response_id'])
        self.assertEqual(task['source_feedback_ids'],['fb-1'])
        self.assertEqual(digest,sha256_bytes(canonical_json_bytes(response)))
        self.assertEqual(task,derived_task(self.finding,*[response,self.request]))

    def test_every_stale_binding_refuses_even_with_recomputed_response_id(self):
        for key,value in [('job_id','job_'+'f'*64),('base_draft_hash','f'*64),('authority_map_hash','f'*64),
                          ('scope_contract_hash','f'*64),('decision_request_hash','f'*64),('decision_id','decision_'+'f'*64)]:
            response=deepcopy(self.response);response[key]=value;response['response_id']=ids.response_id(response)
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind(response)

    def test_unknown_choice_or_additional_effect_cannot_be_smuggled(self):
        for key,value in [('selected_option_id','unpublished'),('authorized_effects',['weaken','remove']),
                          ('authorized_deletion_unit_ids',['unit_'+'f'*64])]:
            response=deepcopy(self.response);response[key]=value;response['response_id']=ids.response_id(response)
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind(response)

    def test_rehashed_request_still_requires_original_evidence_and_targets(self):
        for field,value in [('targets',['sec_'+'f'*64]),('feedback_refs',[{'path':'other.json','hash':'1'*64}])]:
            with self.subTest(field=field),self.assertRaises(ValueError):self.bind(**{field:value})
        changed=deepcopy(self.request);changed['options'][0]['authorized_effects'].append('remove')
        with self.assertRaises(ValueError):self.bind(request=changed)
        job=deepcopy(self.b.job);job['protected_invariants_hash']='f'*64
        with self.assertRaises(ValueError):self.bind(job=job)

    def test_defer_is_a_valid_response_but_never_an_editing_task(self):
        response=deepcopy(self.response);response.update(selected_option_id='defer',authorized_effects=[])
        response['response_id']=ids.response_id(response);self.bind(response)
        with self.assertRaisesRegex(ValueError,'deferred'):derived_task(self.finding,response,self.request)

    def test_deletion_option_requires_explicit_removal_and_exact_units(self):
        options=deepcopy(self.options);options[0]['authorized_deletion_unit_ids']=['unit_'+'f'*64]
        with self.assertRaisesRegex(ValueError,'removal'):decision_request(**self.kwargs,options=options)
        options[0]['authorized_effects']=['remove']
        request=decision_request(**self.kwargs,options=options)
        response=deepcopy(self.response);response.update(decision_id=request['decision_id'],
            decision_request_hash=sha256_bytes(canonical_json_bytes(request)),authorized_effects=['remove'],
            authorized_deletion_unit_ids=['unit_'+'f'*64])
        response['response_id']=ids.response_id(response);self.bind(response,request)
        response['authorized_deletion_unit_ids']=[];response['response_id']=ids.response_id(response)
        with self.assertRaises(ValueError):self.bind(response,request)

    def test_timestamp_is_evidence_but_not_response_or_derived_task_identity(self):
        later=deepcopy(self.response);later['decided_at']='2030-01-01T00:00:00Z'
        self.assertEqual(later['response_id'],ids.response_id(later));self.bind(later)
        self.assertNotEqual(self.bind()[1],self.bind(later)[1])
        self.assertEqual(derived_task(self.finding,self.response,self.request),derived_task(self.finding,later,self.request))

    def test_raw_missing_response_and_unknown_fields_cannot_imply_approval(self):
        with self.assertRaises(ValueError):bind_response({},self.request,**self.kwargs,suite=self.suite)
        response=deepcopy(self.response);response['approved_by_reviewer']=True
        with self.assertRaises(ValueError):self.bind(response)


if __name__=='__main__':unittest.main()
