from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_decisions import decision_request
from whetstone.vnext_mutation_admission import inspect_admission, prepare_admission, exercise_proposal
from vnext_fixtures import ACTOR, STAMP
from vnext_mutation_fixtures import MutationFixture


class ToyPatchEditor:
    def __init__(self,hook=None,effect='clarification',payload=b'Wait 30 seconds or longer.\n'):
        self.calls=0;self.hook=hook;self.effect=effect;self.payload=payload
    def propose(self,prompt):
        self.calls+=1;p=json.loads(prompt.splitlines()[-1]);plan=p['mutation_plan']
        assert p['admitted_findings'][0]['source_findings'][0]['recommended_change']
        assert p['admitted_findings'][0]['feedback_refs']
        finding=next(f['finding_id'] for f in plan['finding_dispositions'] if f['admitted_to_editing'])
        target=p['target_sections'][0]
        patch={'schema_version':'patch-set-v1','job_id':plan['job_id'],'transaction_id':plan['transaction_id'],
            'proposal_id':None,'base_draft_hash':p['base_draft_hash'],'mutation_plan_hash':p['mutation_plan_hash'],
            'editor':ACTOR,'operations':[{'operation_id':'correct','operation_type':'replace_section_body',
                'target_stable_section_id':target['stable_section_id'],'expected_target_hash':target['section_hash'],
                'payload':{'path':'body.md','hash':sha256_bytes(self.payload)},'addressed_finding_ids':[finding],
                'reason':'Apply exactly the admitted correction.','normative_change':self.effect,
                'preserve_target_identity':True,'depends_on_operation_ids':[]}],
            'declined_findings':[],'editor_claims':{'addressed_finding_ids':[finding],
                                                 'normative_change_summary':'Exactly the requested interval wording.'}}
        if self.hook:self.hook()
        return canonical_json_bytes({'schema_version':'vnext-proposal-response-v1','patch':patch,
                                     'payloads':[{'path':'body.md','content':self.payload.decode()}]})


class MutationAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.suite=validate_contract_suite()
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.f=MutationFixture(Path(self.tmp.name),self.suite)
    def inputs(self):return dict(descriptor_ref=self.f.job_ref,review_ref=self.f.original.review_ref,
                                 feedback_ref=self.f.feedback_ref,advice_ref=self.f.advice_ref)
    def run_proposal(self,client,**kwargs):
        return exercise_proposal(self.f.root,round_number=1,client=client,constraints=self.f.constraints,**self.inputs(),**kwargs)
    def snapshot(self):return {p.relative_to(self.f.root):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}

    def test_complete_bound_correction_reaches_immutable_proposal_without_candidate_authority(self):
        before=self.snapshot();admission,plan,proof,_=prepare_admission(self.f.root,constraints=self.f.constraints,**self.inputs())
        self.assertEqual(before,self.snapshot())
        editor=ToyPatchEditor();proposal,ref=self.run_proposal(editor)
        self.assertEqual(editor.calls,1)
        self.assertEqual((self.f.root/ref['path']).read_bytes(),canonical_json_bytes(proposal.patch))
        self.assertEqual(proof['mutation_plan_hash'],sha256_bytes(canonical_json_bytes(plan)))
        self.assertEqual(before[Path('rounds/current_verified.json')],(self.f.root/'rounds/current_verified.json').read_bytes())
        self.assertFalse((self.f.root/'rounds/candidate_index').exists())
        self.assertFalse(list(self.f.root.rglob('candidate_unverified.md')))
        with self.assertRaisesRegex(ValueError,'fresh round'):self.run_proposal(editor)
        self.assertEqual(editor.calls,1)

    def test_missing_advice_or_unresolved_choice_stops_before_editor_and_writes(self):
        self.f.feedback['feedback'][0]['recommended_change']='Choose whether to weaken the minimum.';self.f.rebind()
        before=self.snapshot();editor=ToyPatchEditor()
        with self.assertRaisesRegex(ValueError,'unresolved'):self.run_proposal(editor)
        self.assertEqual(editor.calls,0);self.assertEqual(before,self.snapshot())
        self.f.feedback['feedback'][0]['recommended_change']='Clarify the interval.';self.f.rebind()
        with self.assertRaisesRegex(ValueError,'unresolved'):
            exercise_proposal(self.f.root,round_number=1,client=editor,constraints=self.f.constraints,
                **{**self.inputs(),'advice_ref':None})
        self.assertEqual(editor.calls,0)

    def test_changed_input_during_editor_retains_raw_attempt_but_no_canonical_proposal(self):
        def change():(self.f.root/'inputs/seed.md').write_bytes(self.f.base+b'Changed during call.\n')
        before=(self.f.root/'rounds/current_verified.json').read_bytes();editor=ToyPatchEditor(change)
        with self.assertRaises(ValueError):self.run_proposal(editor)
        self.assertEqual(editor.calls,1)
        self.assertTrue((self.f.root/'rounds/round-1/proposals/attempts/proposal-attempt-1.json').exists())
        self.assertFalse(list(self.f.root.rglob('proposed_patch.json')))
        self.assertEqual(before,(self.f.root/'rounds/current_verified.json').read_bytes())

    def test_pointer_or_seed_map_tamper_prevents_editor_invocation(self):
        for path in ['rounds/current_verified.json','inputs/seed_sections.json']:
            original=(self.f.root/path).read_bytes();(self.f.root/path).write_bytes(original+b' ')
            editor=ToyPatchEditor()
            with self.subTest(path=path),self.assertRaises(ValueError):self.run_proposal(editor)
            self.assertEqual(editor.calls,0);(self.f.root/path).write_bytes(original)

    def test_provider_failure_retains_evidence_and_cannot_restart_the_same_round(self):
        def fail():raise TimeoutError('fixture provider timeout')
        editor=ToyPatchEditor(fail)
        before=(self.f.root/'rounds/current_verified.json').read_bytes()
        with self.assertRaisesRegex(TimeoutError,'fixture provider timeout'):self.run_proposal(editor)
        failure=self.f.root/'rounds/round-1/proposals/attempts/failure-1.txt'
        self.assertEqual(failure.read_text(),'TimeoutError: fixture provider timeout')
        self.assertFalse(list(self.f.root.rglob('proposed_patch.json')))
        with self.assertRaisesRegex(ValueError,'fresh round'):self.run_proposal(editor)
        self.assertEqual(editor.calls,1)
        self.assertEqual(before,(self.f.root/'rounds/current_verified.json').read_bytes())

    def authorize_weakening(self):
        self.f.feedback['feedback'][0]['recommended_change']='Weaken the minimum interval from 30 to 10 seconds.'
        self.f.hint['requested_effects']=['weaken'];self.f.rebind()
        a=inspect_admission(self.f.root,**self.inputs());finding=a.findings[0]
        request=decision_request(job=a.job,base_hash=sha256_bytes(a.base),finding=finding,
            targets=finding['target_section_ids'],feedback_refs=[self.f.feedback_ref],
            options=[{'option_id':'ten_seconds','description':'Authorize the exact requested 30 to 10 second reduction.',
                      'authorized_effects':['weaken'],'authorized_deletion_unit_ids':[]}])
        response={'schema_version':'operator-decision-response-v1','job_id':a.job['job_id'],'response_id':'',
            'decision_id':request['decision_id'],'decision_request_hash':sha256_bytes(canonical_json_bytes(request)),
            'base_draft_hash':sha256_bytes(a.base),'authority_map_hash':a.job['authority_map_hash'],
            'scope_contract_hash':a.job['scope_contract_hash'],'selected_option_id':'ten_seconds',
            'authorized_effects':['weaken'],'authorized_deletion_unit_ids':[],
            'rationale':'Explicit fictional approval for this fixture.','decided_by':'fixture operator','decided_at':STAMP}
        response['response_id']=ids.response_id(response)
        return [{'finding_id':finding['finding_id'],'request':self.f.save('inputs/decision.json',request),
                 'response':self.f.save('inputs/response.json',response)}],response

    def test_exact_operator_response_yields_derived_task_and_stale_response_never_calls_editor(self):
        refs,response=self.authorize_weakening()
        editor=ToyPatchEditor(effect='weaken',payload=b'Wait at least 10 seconds.\n')
        self.run_proposal(editor,decision_refs=refs)
        proof=json.loads((self.f.root/'rounds/round-1/mutation_admission.json').read_bytes())
        self.assertEqual(len(proof['derived_tasks']),1)
        self.assertEqual(proof['derived_tasks'][0]['original_finding_id'],refs[0]['finding_id'])
        self.assertEqual(proof['findings'][0]['classification'],'operator_decision_required')
        response['base_draft_hash']='f'*64;response['response_id']=ids.response_id(response)
        refs[0]['response']=self.f.save('inputs/stale-response.json',response)
        with self.assertRaisesRegex(ValueError,'stale'):
            exercise_proposal(self.f.root,round_number=2,client=editor,constraints=self.f.constraints,**self.inputs(),decision_refs=refs)
        self.assertEqual(editor.calls,1)

    def test_operator_response_cannot_override_immutable_job_policy(self):
        self.f.hint['compatibility_change']='introduce'
        self.f.feedback['feedback'][0]['recommended_change']='Introduce compatibility aliases.';self.f.rebind()
        editor=ToyPatchEditor()
        with self.assertRaisesRegex(ValueError,'new job'):self.run_proposal(editor)
        self.assertEqual(editor.calls,0)

    def test_mixed_unauthorized_effect_cannot_publish_a_patch_or_change_seed(self):
        self.f.base=b'# Queue\n\n## Timing\nWait at least 30 seconds.\n\n## Reports\nThe queue MUST report failures.\n'
        self.f.feedback['feedback'][0]['affected_sections']=['timing','reports'];self.f.rebind()
        self.f.constraints.update(max_operations=2,max_changed_sections=2,
            allowed_operation_types=['replace_section_body','delete_section_subtree'])
        class MixedEditor(ToyPatchEditor):
            def propose(self,prompt):
                packet=json.loads(super().propose(prompt));context=json.loads(prompt.splitlines()[-1])
                timing=next(s for s in context['target_sections'] if s['content'].startswith('## Timing'))
                reports=next(s for s in context['target_sections'] if s['content'].startswith('## Reports'))
                correction=packet['patch']['operations'][0]
                correction.update(target_stable_section_id=timing['stable_section_id'],expected_target_hash=timing['section_hash'])
                deletion={**deepcopy(correction),'operation_id':'remove_reports','operation_type':'delete_section_subtree',
                    'target_stable_section_id':reports['stable_section_id'],'expected_target_hash':reports['section_hash'],
                    'payload':{'path':None,'hash':None},'normative_change':'remove','depends_on_operation_ids':['correct']}
                packet['patch']['operations'].append(deletion)
                return canonical_json_bytes(packet)
        editor=MixedEditor()
        before=(self.f.root/'rounds/current_verified.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'unit authorization'):self.run_proposal(editor)
        self.assertEqual(editor.calls,1)
        self.assertTrue((self.f.root/'rounds/round-1/proposals/attempts/proposal-attempt-1.json').exists())
        self.assertFalse(list(self.f.root.rglob('proposed_patch.json')))
        self.assertEqual(before,(self.f.root/'rounds/current_verified.json').read_bytes())

if __name__=='__main__':unittest.main()
