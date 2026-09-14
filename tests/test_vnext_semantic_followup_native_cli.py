from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone import vnext_proposal_cli as routing
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_identity import binding_id
from vnext_fixtures import STAMP
import test_vnext_semantic_cli as cli
import test_vnext_semantic_followup_workflow as workflow


def native_followup_suite(test,directory):
    original=workflow.consuming_suite
    def extended(*args,**options):
        options['additional_algorithms']+=('vnext_semantic_operator_cli_v1',)
        return original(*args,**options)
    with patch.object(workflow,'consuming_suite',extended):
        return workflow.workflow_suite(test,directory)


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class NativeSemanticFollowupCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cli.SemanticCLITests.setUpClass()

    def test_native_command_journey_preserves_rejection_and_verifies_explicit_followup(self):
        fixture_class=cli.cli_tests.package_tests.fixtures.fixtures.UnitPreflightTests
        setup=fixture_class.setUp
        def with_authority(test):
            setup(test);fixture=test.c.f
            reference=fixture.save('inputs/waiting-authority.md',b'Queue waiting applies to each work start.\n')
            target=next(row for row in fixture.authority['bindings'] if row['role']=='mutable_target')
            authority=dict(path=reference['path'],content_hash=reference['hash'],role='normative_authority',
                authority_scopes=target['authority_scopes'],effective_horizon='current',mutable=False,may_introduce_requirements=True)
            authority['binding_id']=binding_id(authority)
            fixture.authority['bindings'].append(authority)
            fixture.authority['precedence']=[dict(authority_scope=scope,
                ordered_binding_ids=[authority['binding_id'],target['binding_id']],conflict_policy='pause')
                for scope in target['authority_scopes']]
            fixture.rebind()
        with patch.object(fixture_class,'setUp',with_authority):
            subject=self.subject=cli.fixture(self,factory=native_followup_suite)
        with patch.dict(routing.QUALIFIED_SEMANTIC_FOLLOWUP_SUITES,{subject.suite.version:subject.suite.digest}), \
                cli.native_clients(subject):
            script=subject.root.parent/'semantic-cli-native-verifier'
            text=script.read_text();needle='    response = helper.response()\n'
            self.assertEqual(text.count(needle),1)
            text=text.replace(needle,needle+'''    if packet['context']['mutation_plan']['schema_version'] != 'mutation-plan-v3':
        from types import SimpleNamespace
        from test_vnext_semantic_repeated_followup import unresolved_interpretation
        response = json.loads(unresolved_interpretation(SimpleNamespace(valid=canonical_json_bytes(response)), helper.context))
''')
            script.write_text(text)
            code,first=subject.invoke('live-phase1',package=True)
            self.assertEqual(code,2,first)
            self.assertEqual(first['terminal_report']['latest_candidate']['disposition'],'CANDIDATE_REJECTED')
            source_id=self.source_id=first['terminal_report']['latest_candidate']['candidate_id']
            seed=(subject.root/'rounds/current_verified.json').read_bytes()
            original=subject.files()
            print('native original candidate finally rejected with an interpretation question',flush=True)
            candidate_args=('--candidate',source_id,'--vnext-round','1')
            code,inspected=subject.invoke('vnext-semantic-answers',*candidate_args)
            self.assertEqual(code,0,inspected)
            detail=inspected['semantic_answers']
            answer=dict(schema_version='vnext-semantic-answer-input-v1',job_id=detail['job_id'],
                candidate_id=source_id,request=detail['request'],candidate_verification=detail['candidate_verification'],
                action='select',selected_authority_binding_id=detail['question']['choice']['alternatives'][0]['authority_binding_id'],
                rationale='Retain the selected interpretation within the original editing scope.',
                decided_by='fictional-command-operator',decided_at=STAMP)
            answer_path=subject.root.parent/'semantic-command-answer.json'
            answer_path.write_bytes(canonical_json_bytes(answer))
            code,submitted=subject.invoke('vnext-semantic-answer',*candidate_args,'--input',str(answer_path))
            self.assertEqual(code,0,submitted)
            self.assertEqual(submitted['semantic_answer']['response']['authorized_effects'],[])
            reference=self.answer_reference=submitted['semantic_answer']['reference']
            code,admitted=subject.invoke('vnext-semantic-followup',*candidate_args,
                '--answer-receipt',reference['path'],'--answer-hash',reference['hash'])
            self.assertEqual(code,0,admitted)
            self.followup_reference=admitted['semantic_followup']
            self.assertEqual(admitted['proposal_status']['request_status'],'not_started')
            print('native follow-up explicitly admitted through operator commands',flush=True)
            code,final=subject.invoke('live-phase1','--vnext-round','1')
            self.assertEqual(code,2,final)
            self.assertEqual(final['terminal_report']['latest_candidate']['disposition'],'CANDIDATE_VERIFIED')
            self.final_packet=deepcopy(final)
            self.assertNotEqual(final['terminal_report']['latest_candidate']['candidate_id'],source_id)
            self.assertEqual((subject.root/'rounds/current_verified.json').read_bytes(),seed)
            after=subject.files()
            self.assertTrue(all(after.get(path)==raw for path,raw in original.items()))
            def counts():return {role:int((subject.root.parent/('semantic-cli-native-'+role+'.count')).read_text())
                                 for role in ('reviewer','editor','verifier')}
            self.assertEqual(counts(),{'reviewer':1,'editor':2,'verifier':2})
            before=subject.files()
            with patch.object(routing,'_client',side_effect=AssertionError('Completed reentry must not construct adapters')):
                self.assertEqual(subject.invoke('status','--vnext-round','1')[1],final)
                self.assertEqual(subject.invoke('live-phase1','--vnext-round','1')[1],final)
            self.assertEqual(subject.files(),before)
            self.role_calls=counts()
            self.assertEqual(self.role_calls,{'reviewer':1,'editor':2,'verifier':2})


if __name__=='__main__':unittest.main()
