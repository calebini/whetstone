from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_operator_decisions import (decision_context,prepare_operator_requests,
    submit_operator_responses,selected_operator_decisions,finish_operator_pause)
from whetstone.vnext_proposal_run import open_proposal_run
import test_vnext_proposal_cli as cli_tests
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class OperatorDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cli_tests.ProposalCLITests.setUpClass()
    def setUp(self):
        self.c=cli_tests.ProposalCLITests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.c.reviewer.callback=self.sensitive
    def sensitive(self,packet):
        packet['classifications'][0]['requested_effects']=['weaken'];return canonical_json_bytes(packet)
    def start(self):
        code,packet=self.c.invoke('live-phase1',package=True)
        self.assertEqual(code,2,packet);self.assertEqual(self.c.editor.calls,0)
        self.run=open_proposal_run(self.c.root);self.addCleanup(self.run.close)
        self.context=decision_context(self.run,round_number=1)
        self.key=self.context['findings'][0]['finding_id']
        target=self.context['findings'][0]['target_section_ids'][0]
        self.unit=next(u for u in self.context['inventory']['units'] if u['normative'] and u['owning_section_id']==target)
        self.options={'schema_version':'vnext-operator-options-v1','job_id':self.context['job_id'],
            'round_number':1,'review_result':self.context['review_result'],'choices':[{'finding_id':self.key,'options':[
                {'option_id':'clarify','description':'Clarify the existing wait without weakening it.',
                 'authorized_effects':['clarification'],'authorized_deletion_unit_ids':[],'authorized_unit_effects':[]},
                {'option_id':'weaken','description':'Permit weakening only the named wait requirement.',
                 'authorized_effects':['weaken'],'authorized_deletion_unit_ids':[],
                 'authorized_unit_effects':[{'unit_id':self.unit['unit_id'],'effects':['weaken']}]},
                {'option_id':'defer','description':'Leave this choice unresolved; authorize no editing.',
                 'authorized_effects':[],'authorized_deletion_unit_ids':[],'authorized_unit_effects':[]}]}]}
        return packet
    def requests(self):
        self.request=prepare_operator_requests(self.run,self.options)[0]['request'];return self.request
    def response_input(self,option='clarify'):
        return {'schema_version':'vnext-operator-response-input-v1','job_id':self.context['job_id'],
            'round_number':1,'review_result':self.context['review_result'],'selections':[{
                'request':self.request,'selected_option_id':option,'rationale':'Fictional accountable operator choice.',
                'decided_by':'fixture operator','decided_at':STAMP}]}
    def write(self,name,packet):
        path=self.c.root.parent/name;path.write_text(json.dumps(packet));return str(path)

    def test_cli_evidence_preview_and_request_publication_do_not_approve(self):
        self.start();before=self.c.files()
        code,packet=self.c.invoke('vnext-decisions')
        self.assertEqual(code,0);self.assertEqual(packet['decision_context'],self.context);self.assertEqual(before,self.c.files())
        options=self.write('options.json',self.options)
        code,preview=self.c.invoke('vnext-decisions','--options',options,'--dry-run')
        self.assertEqual(code,0);self.assertEqual(before,self.c.files());self.assertIsNone(preview['terminal_state'])
        code,result=self.c.invoke('vnext-decisions','--options',options)
        self.assertEqual((code,result['terminal_state']),(0,'PAUSED_DECISION'))
        self.assertEqual(preview['operator_requests'],result['operator_requests'])
        self.assertFalse(result['proposal_status']['resume']['permitted'])
        self.assertEqual(result['vnext']['next_action'],'review_decisions')
        self.assertEqual((self.c.reviewer.calls,self.c.editor.calls),(1,0))

    def test_cli_explicit_receipt_admits_derived_work_and_preserves_original_classification(self):
        self.start();self.requests();selections=self.write('selections.json',self.response_input())
        before=self.c.files();code,preview=self.c.invoke('vnext-decide','--selections',selections,'--dry-run')
        self.assertEqual(code,0);self.assertEqual(before,self.c.files())
        code,result=self.c.invoke('vnext-decide','--selections',selections)
        self.assertEqual(code,0,result);self.assertEqual(preview['operator_selection'],result['operator_selection'])
        self.assertEqual(result['terminal_state'],'PAUSED_DECISION');self.assertEqual(self.c.editor.calls,0)
        self.assertEqual(self.c.invoke('live-phase1')[1]['terminal_state'],'PAUSED_DECISION');self.assertEqual(self.c.editor.calls,0)
        receipt=result['operator_selection']['selection']
        code,final=self.c.invoke('live-phase1','--vnext-decisions',receipt['path'])
        self.assertEqual(code,2,final);self.assertEqual(self.c.editor.calls,1)
        self.assertEqual(final['terminal_report']['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        plan=json.loads(self.c.editor.prompts[0].splitlines()[-1])['mutation_plan']
        original=next(f for f in plan['finding_dispositions'] if f['finding_id']==self.key)
        self.assertEqual(original['classification'],'operator_decision_required');self.assertFalse(original['admitted_to_editing'])
        derived=next(f for f in plan['finding_dispositions'] if f['admitted_to_editing'])
        self.assertNotEqual(derived['finding_id'],self.key);self.assertIsNotNone(derived['decision_response_id'])
        self.assertEqual(self.run.store.read('rounds/current_verified.json'),self.run.store.read('rounds/verified_history/current-verified-0.json'))
        before=self.c.files();self.assertEqual(self.c.invoke('vnext-decisions','--options',self.write('options.json',self.options))[0],2)
        self.assertEqual(before,self.c.files());self.assertEqual(self.c.editor.calls,1)

    def test_stale_binding_unknown_targets_and_cross_section_grants_fail_before_writes(self):
        self.start();before=self.c.files()
        variants=[]
        stale=deepcopy(self.options);stale['review_result']['hash']='f'*64;variants.append(stale)
        duplicate=deepcopy(self.options);duplicate['choices']*=2;variants.append(duplicate)
        unknown=deepcopy(self.options);unknown['choices'][0]['finding_id']='unknown';variants.append(unknown)
        outside=deepcopy(self.options);outside['choices'][0]['options'][1]['authorized_unit_effects'][0]['unit_id']=next(
            u['unit_id'] for u in self.context['inventory']['units'] if u['owning_section_id']!=self.unit['owning_section_id'])
        variants.append(outside)
        for packet in variants:
            with self.subTest(packet=packet),self.assertRaises(ValueError):prepare_operator_requests(self.run,packet)
            self.assertEqual(before,self.c.files())

    def test_invalid_response_inputs_never_publish_or_call_editor(self):
        self.start();self.requests();before=self.c.files()
        for name,value in [('selected_option_id','absent'),('decided_by',' '),('rationale',' ')]:
            packet=self.response_input();packet['selections'][0][name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):submit_operator_responses(self.run,packet)
            self.assertEqual(before,self.c.files())
        packet=self.response_input();packet['selections'][0]['request']['hash']='f'*64
        with self.assertRaises(ValueError):submit_operator_responses(self.run,packet)
        self.assertEqual(before,self.c.files());self.assertEqual(self.c.editor.calls,0)

    def test_declined_choice_is_retained_but_cannot_admit_or_technically_resume(self):
        self.start();self.requests();selection=submit_operator_responses(self.run,self.response_input('defer'))['selection']
        before=self.c.files();code,packet=self.c.invoke('live-phase1','--vnext-decisions',selection['path'])
        self.assertEqual(code,2);self.assertIn('deferred blocking choice',packet['vnext']['reason'])
        self.assertEqual(self.c.invoke('resume','--continue','--vnext-decisions',selection['path'])[0],2)
        self.assertEqual(before,self.c.files());self.assertEqual(self.c.editor.calls,0)
        self.assertEqual(self.c.invoke('status')[1]['terminal_state'],'PAUSED_DECISION')

    def test_multiple_retained_answers_do_not_select_latest_or_replace_admitted_choice(self):
        self.start();self.requests()
        first=submit_operator_responses(self.run,self.response_input('clarify'))['selection']
        second=submit_operator_responses(self.run,self.response_input('weaken'))['selection']
        status=self.run.status(round_number=1);self.assertEqual(len(status['operator_work']['selections']),2)
        self.c.invoke('live-phase1');self.assertEqual(self.c.editor.calls,0)
        self.c.invoke('live-phase1','--vnext-decisions',first['path']);self.assertEqual(self.c.editor.calls,1)
        before=self.c.files();code,packet=self.c.invoke('live-phase1','--vnext-decisions',second['path'])
        self.assertEqual((code,packet['vnext']['reason_code']),(2,'vnext_selection_conflict'))
        self.assertEqual(before,self.c.files());self.assertEqual(self.c.editor.calls,1)

    def test_response_publication_interruption_cannot_fabricate_selected_authorization(self):
        self.start();self.requests();packet=self.response_input();publish=self.run.store.publish
        def stop(token,path,value):
            result=publish(token,path,value)
            if '/operator_decisions/' in path and '/responses/' in path:raise OSError('fictional lost response acknowledgement')
            return result
        with patch.object(self.run.store,'publish',side_effect=stop),self.assertRaises(OSError):
            submit_operator_responses(self.run,packet)
        before=self.c.files();status=self.run.status(round_number=1);self.assertEqual(before,self.c.files())
        self.assertEqual(status['operator_work']['selections'],[])
        self.assertEqual(len(status['operator_work']['requests'][0]['responses']),1)
        self.c.invoke('live-phase1');self.assertEqual(self.c.editor.calls,0)
        result=submit_operator_responses(self.run,packet)
        self.assertEqual(selected_operator_decisions(self.run,round_number=1,reference=result['selection']),result['content']['decision_refs'])
        self.assertEqual(len(list((self.c.root/'rounds/round-1/operator_decisions').rglob('resp_*.json'))),1)

    def test_request_publication_interruption_and_pause_materialization_need_no_client(self):
        self.start();publish=self.run.store.publish
        def stop(token,path,value):
            result=publish(token,path,value)
            if '/operator_decisions/' in path and path.endswith('/request.json'):raise OSError('fictional request acknowledgement loss')
            return result
        with patch.object(self.run.store,'publish',side_effect=stop),self.assertRaises(OSError):
            prepare_operator_requests(self.run,self.options)
        before=self.c.files();status=self.run.status(round_number=1)
        self.assertEqual(status['terminal_report']['terminal_state'],'PAUSED_DECISION')
        self.assertEqual(status['terminal_materialization'],'missing');self.assertFalse(status['resume']['permitted'])
        self.assertEqual(before,self.c.files());finish_operator_pause(self.run,round_number=1)
        self.assertEqual(self.run.status(round_number=1)['terminal_materialization'],'present')
        self.assertEqual((self.c.reviewer.calls,self.c.editor.calls),(1,0))

    def test_explicit_request_replay_completes_a_directory_only_interruption(self):
        self.start();publish=self.run.store.publish
        def stop(token,path,value):
            if '/operator_decisions/' in path and path.endswith('/request.json'):
                (self.c.root/path).parent.mkdir(parents=True,exist_ok=True)
                raise OSError('fictional stop before immutable request file publication')
            return publish(token,path,value)
        with patch.object(self.run.store,'publish',side_effect=stop),self.assertRaises(OSError):
            prepare_operator_requests(self.run,self.options)
        before=self.c.files();self.assertEqual(self.c.invoke('status')[0],2);self.assertEqual(before,self.c.files())
        code,packet=self.c.invoke('vnext-decisions','--options',self.write('replay-options.json',self.options))
        self.assertEqual((code,packet['terminal_state']),(0,'PAUSED_DECISION'))
        self.assertEqual((self.c.reviewer.calls,self.c.editor.calls),(1,0))

    def test_operator_publication_refuses_candidate_orphans_before_writes(self):
        self.start();orphan=self.c.root/'rounds/round-9/candidates'/('can_'+'f'*64);orphan.mkdir(parents=True)
        before=self.c.files()
        with self.assertRaisesRegex(ValueError,'candidate processing'):prepare_operator_requests(self.run,self.options)
        self.assertEqual(before,self.c.files());self.assertEqual(self.c.editor.calls,0)

    def test_response_timestamp_cannot_rewrite_same_identity_and_tamper_refuses(self):
        self.start();self.requests();packet=self.response_input();result=submit_operator_responses(self.run,packet)
        changed=deepcopy(packet);changed['selections'][0]['decided_at']='2026-09-14T00:00:00Z';before=self.c.files()
        with self.assertRaisesRegex(ValueError,'different bytes'):submit_operator_responses(self.run,changed)
        self.assertEqual(before,self.c.files())
        response=result['content']['decision_refs'][0]['response'];path=self.c.root/response['path'];path.write_bytes(path.read_bytes()+b' ')
        before=self.c.files();code,packet=self.c.invoke('live-phase1','--vnext-decisions',result['selection']['path'])
        self.assertEqual((code,packet['terminal_state']),(2,'HALTED_ARTIFACT_INVALID'))
        self.assertEqual(before,self.c.files());self.assertEqual(self.c.editor.calls,0)

    def test_operator_choice_cannot_override_descriptor_bound_policy(self):
        def forbidden(packet):
            packet['classifications'][0]['compatibility_change']='introduce'
            return self.sensitive(packet)
        self.c.reviewer.callback=forbidden;self.start()
        self.assertTrue(self.context['evidence'][self.key]['requires_new_job']);self.requests()
        selection=submit_operator_responses(self.run,self.response_input())['selection'];before=self.c.files()
        code,packet=self.c.invoke('live-phase1','--vnext-decisions',selection['path'])
        self.assertEqual(code,2);self.assertIn('requires a new job',packet['vnext']['reason'])
        self.assertEqual(before,self.c.files());self.assertEqual(self.c.editor.calls,0)
        self.assertEqual(self.c.invoke('status')[1]['vnext']['next_action'],'new_isolated_root')

    def weakening_candidate(self,*,other_unit):
        f=self.c.f;f.base=b'Preamble MUST remain.\n# Queue\n## Timing\nQueue MUST wait.\nQueue MUST report.\n## Reports\nReport.\n';f.rebind()
        self.c.fixture.package['job_descriptor']=f.job_ref
        self.c.fixture.package['mutation_constraints']=f.save(self.c.fixture.constraint_ref['path'],
            {'schema_version':'vnext-mutation-constraints-v1','constraints':f.constraints})
        self.c.fixture.save_package();self.start();self.requests()
        selection=submit_operator_responses(self.run,self.response_input('weaken'))['selection']
        content='Queue MUST wait.\nQueue SHOULD report.\n' if other_unit else 'Queue SHOULD wait.\nQueue MUST report.\n'
        def respond(packet):
            packet['payloads'][0]['content']=content;packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
            packet['patch']['operations'][0]['normative_change']='weaken';return canonical_json_bytes(packet)
        self.c.editor.callback=respond
        code,packet=self.c.invoke('live-phase1','--vnext-decisions',selection['path'])
        self.assertEqual(code,2,packet);self.assertEqual((self.c.reviewer.calls,self.c.editor.calls),(1,1))
        self.assertEqual(self.run.store.read('rounds/current_verified.json'),self.run.store.read('rounds/verified_history/current-verified-0.json'))
        return packet

    def test_named_unit_weakening_flows_through_command_admission_and_deterministic_validation(self):
        packet=self.weakening_candidate(other_unit=False)
        self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')

    def test_named_unit_approval_does_not_authorize_weakening_a_neighbor(self):
        packet=self.weakening_candidate(other_unit=True)
        self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'],'CANDIDATE_REJECTED')
        self.assertEqual(packet['terminal_state'],'HALTED_ARTIFACT_INVALID')


if __name__=='__main__':unittest.main()
