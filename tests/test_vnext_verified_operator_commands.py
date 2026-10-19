"""Config-selected explicit choices stop at request/response publication."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_phase2_operator import Phase2Operator
from vnext_fixtures import STAMP
import test_vnext_verified_reviewer_handoff as handoff


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class OperatorCommandTests(unittest.TestCase):
    setUpClass=handoff.ReviewerHandoffTests.setUpClass
    setUp=handoff.ReviewerHandoffTests.setUp
    patch=handoff.ReviewerHandoffTests.patch
    qualify=handoff.ReviewerHandoffTests.qualify
    save_config=handoff.ReviewerHandoffTests.save_config
    clean=staticmethod(handoff.ReviewerHandoffTests.clean)
    invoke=handoff.ReviewerHandoffTests.invoke
    files=handoff.ReviewerHandoffTests.files
    stage_phase2=handoff.ReviewerHandoffTests.stage_phase2
    ready=handoff.ReviewerHandoffTests.ready

    def call(self,command,*args):
        print('  command: '+command+' '+' '.join(args),file=sys.stderr,flush=True)
        code,result=self.invoke(command,*args)
        print('  result: '+str(code)+' '+str(result.get('gate',result.get('reason')) if isinstance(result,dict) else 'requests'),file=sys.stderr,flush=True)
        return code,result

    def choices(self):
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('context took fence')):
            code,context=self.call('vnext-decisions')
        self.assertEqual(code,0,context);self.assertEqual(self.files(),before)
        self.assertEqual(context['findings'][0]['classification'],'operator_decision_required')
        options=dict(schema_version='vnext-operator-options-v1',
            **{k:context[k] for k in ('job_id','round_number','review_result')},
            choices=[dict(finding_id=context['findings'][0]['finding_id'],options=[
                dict(option_id='clarify',description='Clarify existing behavior without weakening it.',
                     authorized_effects=['clarification'],authorized_deletion_unit_ids=[],authorized_unit_effects=[]),
                dict(option_id='defer',description='Retain the unresolved choice.',
                     authorized_effects=[],authorized_deletion_unit_ids=[],authorized_unit_effects=[])])])
        path=self.config_path.parent/'operator-options.json';raw=canonical_json_bytes(options);path.write_bytes(raw)
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('preview took fence')):
            code,preview=self.call('vnext-decisions','--options',str(path),'--dry-run')
        self.assertEqual(code,0,preview);self.assertEqual(self.files(),before)
        publish=Phase2Operator.publish
        def changed(owner,packet,**kwargs):
            path.write_bytes(raw+b' ')
            return publish(owner,packet,**kwargs)
        with patch.object(Phase2Operator,'publish',changed):
            code,result=self.call('vnext-decisions','--options',str(path))
        self.assertEqual(code,2,result);self.assertIn('selected operator input changed',result['reason'])
        self.assertEqual(self.files(),before);path.write_bytes(raw)
        code,requests=self.call('vnext-decisions','--options',str(path))
        self.assertEqual(code,0,requests);self.assertEqual(requests,preview)
        response=dict(schema_version='vnext-operator-response-input-v1',
            **{k:context[k] for k in ('job_id','round_number','review_result')},
            selections=[dict(request=requests[0]['request'],selected_option_id='clarify',
                rationale='Synthetic explicit operator choice.',decided_by='fixture operator',decided_at=STAMP)])
        selected=self.config_path.parent/'operator-selection.json';selected.write_bytes(canonical_json_bytes(response))
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('response preview took fence')):
            code,preview=self.call('vnext-decide','--selections',str(selected),'--dry-run')
        self.assertEqual(code,0,preview);self.assertEqual(self.files(),before)
        code,result=self.call('vnext-decide','--selections',str(selected))
        self.assertEqual(code,0,result);self.assertEqual(result,preview)
        after=self.files()
        code,again=self.call('vnext-decide','--selections',str(selected))
        self.assertEqual(code,0,again);self.assertEqual(again,result);self.assertEqual(self.files(),after)
        code,current=self.call('vnext-decisions');self.assertEqual(code,0,current)
        self.assertEqual(current['findings'],context['findings'])
        self.assertEqual(current['evidence'],context['evidence'])
        self.assertIn(result['selection'],current['selections']);self.assertFalse(current['admitted'])
        self.assertFalse(current['next_review_authorized']);self.assertFalse(current['resume']['permitted'])
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),self.head)
        self.assertFalse(list(self.root.rglob('candidate_unverified.md')))
        return result['selection']

    def test_consumed_phase1_selector_stops_at_later_choice_and_stale_reentry_refuses(self):
        from copy import deepcopy
        from whetstone.vnext_contracts import sha256_bytes
        from whetstone.vnext_verified_run import open_verified_run
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        from test_vnext_proposal_requests import Client as Editor
        from test_vnext_semantic_requests import Client as Verifier
        self.f.original.review['profiles'][0]['budget'] = 2
        self.f.original.review_ref = self.f.save('inputs/review.json', self.f.original.review)
        self.f.job['review_configuration_hash'] = self.f.original.review_ref['hash']
        self.f.rebind()
        self.fixture.package.update(job_descriptor=self.f.job_ref,
                                    review_configuration=self.f.original.review_ref)
        self.fixture.save_package()
        self.config['vnext_input_package']['hash'] = sha256_bytes(
            (self.fixture.source/'proposal_package.json').read_bytes())
        self.save_config()
        self.qualify()
        def review(prompt):
            self.reviewer.calls += 1
            inputs = json.loads(prompt.splitlines()[-1])
            feedback = deepcopy(self.f.feedback)
            feedback.update(round_number=inputs['round_number'], profile=inputs['profile'],
                            draft_hash=sha256_bytes(inputs['base'].encode()), reviewer=self.reviewer.identity)
            hint = deepcopy(self.f.hint)
            hint['classification'] = 'operator_decision_required'
            return canonical_json_bytes(dict(schema_version='vnext-review-response-v1',
                                             feedback=feedback, classifications=[hint]))
        with patch.object(self.reviewer, 'review', side_effect=review):
            code, result = self.call('live-phase1')
            self.assertEqual(code, 2, result)
            self.head = (self.root/'rounds/current_verified.json').read_bytes()
            selection = self.choices()
            editor = Editor(); verifiers = []
            self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient', return_value=editor)
            def verifier(**kwargs):
                with open_verified_run(self.root) as run:
                    history = run._history()
                    creation = history.inspect().creations[-1]
                    context = load_registered_semantic_context(run.store, admission=history,
                                                               candidate_id=creation['candidate_id'])
                client = Verifier(context); verifiers.append(client); return client
            self.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient', side_effect=verifier)
            code, result = self.call('live-phase1', '--vnext-decisions', selection['path'])
            self.assertEqual(code, 2, result)
            self.assertEqual(result.get('gate'), 'finding_admission', result)
            self.assertEqual(result['round_number'], 2)
            self.assertEqual(result['operator']['findings'][0]['classification'], 'operator_decision_required')
            self.assertEqual(result['status']['current_pointer']['promotion_ordinal'], 1)
            self.assertEqual((self.reviewer.calls, editor.calls, sum(c.calls for c in verifiers)), (2, 1, 1))
            before = self.files()
            code, stale = self.call('live-phase1', '--vnext-decisions', selection['path'])
            self.assertEqual(code, 2, stale)
            self.assertIn('noncanonical operator selection', stale['reason'])
            self.assertEqual(self.files(), before)
            self.assertEqual((self.reviewer.calls, editor.calls, sum(c.calls for c in verifiers)), (2, 1, 1))

    def test_phase1_options_and_responses_bind_exact_input_without_admitting_work(self):
        self.qualify()
        def sensitive(packet):
            packet['classifications'][0]['requested_effects']=['weaken']
            return canonical_json_bytes(packet)
        self.reviewer.callback=sensitive
        code,result=self.call('live-phase1');self.assertEqual(code,2,result)
        self.head=(self.root/'rounds/current_verified.json').read_bytes()
        self.choices();self.assertEqual(self.reviewer.calls,1)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())

    def test_phase2_options_and_responses_preserve_bound_review_and_entry(self):
        self.ready(effect='weaken')
        self.patch('whetstone.live_phase2.LivePhase2Runner',side_effect=AssertionError('legacy executor'))
        code,result=self.call('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(result['gate'],'operator_or_advice_required',result)
        self.head=(self.root/'rounds/current_verified.json').read_bytes()
        entry=(self.root/'rounds/phase2/entry.json').read_bytes()
        self.choices();self.assertEqual(self.phase2_reviewer.calls,1)
        self.assertEqual((self.root/'rounds/phase2/entry.json').read_bytes(),entry)


if __name__=='__main__':unittest.main()
