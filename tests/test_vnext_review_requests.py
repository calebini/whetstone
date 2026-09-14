from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_proposal_admission import initialize_proposal_storage
from whetstone.vnext_proposal_run import open_proposal_run
from whetstone.vnext_review_requests import inspect_seed_review
from whetstone.vnext_native_reviewer import NativeProposalReviewerClient
import test_vnext_proposal_admission as fixtures
from test_vnext_proposal_requests import Client as Editor
from vnext_fixtures import STAMP


class Reviewer:
    def __init__(self,fixture,callback=None):
        self.fixture=fixture;self.callback=callback;self.calls=0;self.identity=deepcopy(fixture.original.review['reviewer']);self.timeout=5
    @property
    def transport_binding(self):return {'reviewer':self.identity,'command':'fictional-reviewer','cwd':'/fictional',
        'timeout_seconds':self.timeout,'output_schema_hash':'a'*64}
    def review(self,prompt):
        self.calls+=1;packet=json.loads(prompt.splitlines()[-1]);feedback=deepcopy(self.fixture.feedback)
        feedback.update(round_number=packet['round_number'],profile=packet['profile'],draft_hash=packet['job']['seed_draft']['hash'],reviewer=self.identity)
        response={'schema_version':'vnext-review-response-v1','feedback':feedback,'classifications':[deepcopy(self.fixture.hint)]}
        return self.callback(response) if self.callback else canonical_json_bytes(response)


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class SeedReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ProposalAdmissionTests.setUpClass()
    def setUp(self):
        self.f=fixtures.ProposalAdmissionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root.with_name('live-seed-review');self.initialize()
        self.client=Reviewer(self.f.f)
    def initialize(self):
        f=self.f.f;omitted={f.feedback_ref['path'],f.advice_ref['path'],self.f.record_ref['path']}
        artifacts={p.relative_to(f.root).as_posix():p.read_bytes() for p in f.root.rglob('*')
            if p.is_file() and p.relative_to(f.root).as_posix() not in omitted}
        store,_=initialize_proposal_storage(self.root,artifacts=artifacts,suite_path=self.f.path,descriptor_ref=f.job_ref,
            review_ref=f.original.review_ref,seed_map_ref=f.map_ref,round_refs={});store.close()
        self.run=open_proposal_run(self.root,suite_path=self.f.path);self.addCleanup(self.run.close)
    def step(self,client=None,continuation=False):return self.run.review_next(client=client or self.client,continuation=continuation)
    def files(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def directory(self,result):return self.root/'rounds/client_requests'/result.request_id
    def record(self,result):return {'schema_version':'vnext-proposal-round-input-v1','job_id':self.f.f.job['job_id'],
        'round_number':result.round_number,'base_pointer':self.f.f.pointer_ref,'feedback':result.receipt['feedback'],
        'advice':result.receipt['advice'],'decision_refs':[],'constraints':self.f.f.constraints}

    def test_live_feedback_and_advice_feed_admitted_editor_and_candidate(self):
        result=self.step();self.assertEqual(result.status,'complete');self.assertEqual(self.client.calls,1)
        self.assertEqual(result.review['findings'][0]['classification'],'editor_fixable')
        waiting=self.step();self.assertEqual(waiting.status,'finding_admission');self.assertEqual(self.client.calls,1)
        self.run.admit_round(self.record(result));editor=Editor()
        report,_=self.run.run_round(round_number=1,client=editor,decided_at=STAMP)
        self.assertEqual(report['resume']['reason'],'vnext_gate_unavailable');self.assertEqual(editor.calls,1)
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(self.step().status,'finding_admission');self.assertEqual(self.client.calls,1)

    def test_shape_retry_is_one_slot_and_inspection_does_not_repair(self):
        def reply(packet):return b'{}' if self.client.calls==1 else canonical_json_bytes(packet)
        self.client.callback=reply;result=self.step()
        self.assertEqual((result.status,result.attempts,self.client.calls),('complete',2,2))
        before=self.files();self.assertEqual(inspect_seed_review(self.run).status,'finding_admission');self.assertEqual(self.files(),before)

    def test_timeout_requires_explicit_continuation_and_freezes_transport(self):
        def timeout(packet):raise TimeoutError('fictional review deadline')
        self.client.callback=timeout;result=self.step();self.assertEqual(result.status,'timeout')
        restarted=Reviewer(self.f.f);restarted.timeout=10
        self.assertEqual(self.step(restarted).status,'continuation_required');self.assertEqual(restarted.calls,0)
        self.assertEqual(self.step(restarted,True).status,'complete');self.assertEqual(restarted.calls,1)

    def test_prepared_first_invocation_cannot_contradict_claimed_timeout(self):
        original=self.run.store.publish
        def stop(token,path,value):
            result=original(token,path,value)
            if path=='rounds/review_index/request-1.json':raise OSError('fictional claim interruption')
            return result
        with patch.object(self.run.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.step()
        self.assertEqual(self.run.review_status().status,'prepared')
        self.assertEqual(self.client.calls,0);before=self.files();changed=Reviewer(self.f.f);changed.timeout=10
        with self.assertRaisesRegex(ValueError,'first Reviewer invocation must use its claimed transport'):
            self.step(changed,True)
        self.assertEqual(changed.calls,0);self.assertEqual(self.files(),before)
        self.assertEqual(self.step(continuation=True).status,'complete');self.assertEqual(self.client.calls,1)

    def test_exhaustion_and_binding_failure_never_get_an_extra_review(self):
        self.client.callback=lambda packet:b'{}';self.assertEqual(self.step().status,'attempts_exhausted')
        restarted=Reviewer(self.f.f)
        self.assertEqual(self.step(restarted,True).status,'attempts_exhausted');self.assertEqual(restarted.calls,0)

    def test_contradictory_round_binding_is_not_a_shape_retry(self):
        def invalid(packet):packet['feedback']['round_number']=4;return canonical_json_bytes(packet)
        self.client.callback=invalid;result=self.step()
        self.assertEqual((result.status,self.client.calls),('invalid_review',1))
        again=Reviewer(self.f.f);self.assertEqual(self.step(again,True).status,'invalid_review');self.assertEqual(again.calls,0)

    def test_sensitive_advice_is_only_advisory_and_blocks_editor(self):
        def unsafe(packet):packet['classifications'][0]['requested_effects']=['weaken'];return canonical_json_bytes(packet)
        self.client.callback=unsafe;result=self.step()
        self.assertEqual(result.review['findings'][0]['classification'],'operator_decision_required')
        with self.assertRaisesRegex(ValueError,'unresolved operator decisions'):self.run.admit_round(self.record(result))
        self.assertFalse((self.root/'rounds/round-1/proposal_input.json').exists())

    def test_retained_response_can_finish_after_interruption_without_another_call(self):
        original=self.run.store.publish
        def stop(token,path,value):
            outcome=original(token,path,value)
            if path.endswith('/response.json'):raise OSError('fictional response interruption')
            return outcome
        with patch.object(self.run.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.step()
        self.assertEqual(inspect_seed_review(self.run).status,'valid_response')
        resumed=Reviewer(self.f.f);self.assertEqual(self.step(resumed,True).status,'complete');self.assertEqual(resumed.calls,0)

    def test_missing_bound_predecessor_and_claim_do_not_reset_attempts(self):
        self.client.callback=lambda packet:b'{}';result=self.step()
        previous=self.directory(result)/'attempts/1/outcome.json';raw=previous.read_bytes();previous.unlink()
        with self.assertRaises(ValueError):self.step(Reviewer(self.f.f),True)
        previous.write_bytes(raw);(self.root/'rounds/review_index/request-1.json').unlink()
        with self.assertRaisesRegex(ValueError,'no durable request claim'):self.step(Reviewer(self.f.f))

    def test_clean_review_finishes_without_candidate_or_extra_round(self):
        def clean(packet):packet['feedback']['feedback']=[];packet['classifications']=[];return canonical_json_bytes(packet)
        self.client.callback=clean;self.assertEqual(self.step().status,'complete')
        self.assertEqual(self.step().status,'phase_1_stable');self.assertEqual(self.client.calls,1)
        self.assertFalse((self.root/'rounds/candidate_index').exists())

    def test_extra_round_claim_cannot_advance_past_findings(self):
        self.step();source=self.root/'rounds/review_index/request-1.json'
        (source.parent/'request-2.json').write_bytes(source.read_bytes())
        with self.assertRaisesRegex(ValueError,'finding/budget boundary'):self.step()
        self.assertEqual(self.client.calls,1)

    def test_rehashed_advice_cannot_replace_committed_reviewer_provenance(self):
        result=self.step();record=self.record(result)
        advice=deepcopy(result.review['advice']);advice['findings'][0]['requested_effects']=['strengthen']
        path=self.root/'inputs/altered-advice.json';path.write_bytes(canonical_json_bytes(advice))
        record['advice']={'path':'inputs/altered-advice.json','hash':sha256_bytes(path.read_bytes())}
        with self.assertRaisesRegex(ValueError,'differs from the committed Reviewer'):self.run.admit_round(record)

    def test_alternate_feedback_path_cannot_bypass_live_reviewer_proof(self):
        result=self.step();record=self.record(result)
        path=self.root/'inputs/copied-feedback.json';path.write_bytes(canonical_json_bytes(result.review['feedback']))
        record['feedback']={'path':'inputs/copied-feedback.json','hash':sha256_bytes(path.read_bytes())}
        with self.assertRaisesRegex(ValueError,'differs from the committed Reviewer'):self.run.admit_round(record)
        self.assertFalse((self.root/'rounds/round-1/proposal_input.json').exists())

    def configure_profiles(self,mode,budget=2):
        self.run.close();f=self.f.f
        f.original.review.update(review_mode=mode,profiles=[
            {'name':'structural_integrity','budget':budget},{'name':'determinism','budget':budget}])
        f.original.review_ref=f.save(f.original.review_ref['path'],f.original.review)
        f.job['review_configuration_hash']=f.original.review_ref['hash'];f.rebind()
        self.root=self.root.with_name('profiles-'+mode);self.initialize();self.client=Reviewer(f)

    def test_horizontal_and_vertical_profile_order_and_clean_completion(self):
        for mode,expected in [('horizontal',['structural_integrity','structural_integrity','determinism']),
                              ('vertical',['structural_integrity','determinism','structural_integrity'])]:
            with self.subTest(mode=mode):
                self.configure_profiles(mode);seen=[]
                def response(packet):
                    seen.append(packet['feedback']['profile'])
                    if len(seen)==1:packet['classifications'][0]['classification']='deferable'
                    else:packet['feedback']['feedback']=[];packet['classifications']=[]
                    return canonical_json_bytes(packet)
                self.client.callback=response
                for number in range(1,4):
                    result=self.step();self.assertEqual((result.status,result.round_number),('complete',number))
                self.assertEqual(seen,expected);self.assertEqual(self.step().status,'phase_1_stable')
                self.assertEqual(self.client.calls,3)

    def test_profile_budget_exhaustion_and_shape_repair_have_separate_counts(self):
        self.configure_profiles('vertical',budget=1)
        def response(packet):
            packet['classifications'][0]['classification']='deferable'
            return b'{}' if self.client.calls==1 else canonical_json_bytes(packet)
        self.client.callback=response;result=self.step()
        self.assertEqual((result.round_number,result.attempts),(1,2))
        self.assertEqual(self.step().status,'budget_exhausted');self.assertEqual(self.client.calls,2)
        self.assertFalse((self.root/'rounds/review_index/request-2.json').exists())

    def test_selected_status_is_read_only_and_retains_timeout_cause_after_exhaustion(self):
        before=self.files();status=self.run.status(round_number=1)
        self.assertEqual(status['request_status'],'not_started');self.assertFalse(status['resume']['permitted'])
        self.assertEqual(self.files(),before)
        def timeout(packet):raise TimeoutError('fictional review deadline')
        self.client.callback=timeout;self.step()
        self.run.close();self.run=open_proposal_run(self.root,suite_path=self.f.path);self.addCleanup(self.run.close)
        before=self.files();status=self.run.status(round_number=1)
        self.assertTrue(status['resume']['permitted']);self.assertEqual(status['resume']['next_gate'],'review')
        self.assertIn('fictional review deadline',status['resume']['reason']);self.assertEqual(self.files(),before)
        self.step(continuation=True);status=self.run.status(round_number=1)
        self.assertEqual(status['request_status'],'attempts_exhausted')
        self.assertEqual(status['resume']['next_gate'],'materialization')
        self.assertIn('timeout',status['terminal_report']['resume']['reason']);self.assertEqual(self.client.calls,2)
        self.run.review_phase(client=self.client,continuation=True)
        status=self.run.status(round_number=1)
        self.assertFalse(status['resume']['permitted']);self.assertIn('timeout',status['resume']['reason'])
        self.assertEqual(self.client.calls,2)
        future=self.run.status(round_number=2)
        self.assertEqual(future['request_status'],'not_admitted');self.assertFalse(future['resume']['permitted'])

    def test_selected_status_stops_at_findings_without_claiming_candidate_or_resume(self):
        self.step();before=self.files();status=self.run.status(round_number=1)
        self.assertEqual(status['processing_gate'],'finding_admission');self.assertFalse(status['resume']['permitted'])
        self.assertIsNone(status['terminal_report']);self.assertEqual(before,self.files())

    def test_lost_result_acknowledgement_is_replayed_before_next_claim(self):
        self.configure_profiles('vertical');original=self.run.store.publish;stopped=False
        def clean(packet):packet['feedback']['feedback']=[];packet['classifications']=[];return canonical_json_bytes(packet)
        self.client.callback=clean
        def stop(token,path,value):
            nonlocal stopped
            outcome=original(token,path,value)
            if path.endswith('/result.json') and not stopped:stopped=True;raise OSError('fictional lost result acknowledgement')
            return outcome
        with patch.object(self.run.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.step()
        self.assertEqual(self.client.calls,1);writes=[]
        def record(token,path,value):writes.append(path);return original(token,path,value)
        with patch.object(self.run.store,'publish',side_effect=record):self.assertEqual(self.step().round_number,2)
        old_result=next(i for i,path in enumerate(writes) if path.endswith('/result.json'))
        self.assertLess(old_result,writes.index('rounds/review_index/request-2.json'));self.assertEqual(self.client.calls,2)

    def test_mid_call_authority_drift_retains_raw_and_refuses_result(self):
        def drift(packet):
            target=self.root/self.f.f.original.review_ref['path'];target.write_bytes(target.read_bytes()+b' ')
            return canonical_json_bytes(packet)
        self.client.callback=drift
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.step()
        self.assertEqual(self.client.calls,1);self.assertEqual(len(list(self.root.rglob('response.json'))),1)
        self.assertEqual(list(self.root.rglob('result.json')),[])

    def test_native_reviewer_uses_raw_transport_and_the_new_response_schema(self):
        self.run.close();f=self.f.f
        f.original.review['reviewer']={'name':'codex','version':'scripted-1','model':'scripted-model'}
        f.original.review_ref=f.save(f.original.review_ref['path'],f.original.review)
        f.job['review_configuration_hash']=f.original.review_ref['hash'];f.rebind()
        self.root=self.root.with_name('native-review');self.initialize()
        command=self.root.parent/'scripted-reviewer';counter=command.with_name('review-count')
        template=canonical_json_bytes({'feedback':f.feedback,'hint':f.hint}).decode()
        command.write_text(f'''#!{sys.executable}
import json,sys
from pathlib import Path
prompt=sys.stdin.read();packet=json.loads(prompt.splitlines()[-1]);template=json.loads({template!r})
feedback=template['feedback'];feedback.update(round_number=packet['round_number'],profile=packet['profile'],reviewer=packet['review']['reviewer'])
response={{'schema_version':'vnext-review-response-v1','feedback':feedback,'classifications':[template['hint']]}}
count=Path({str(counter)!r});n=int(count.read_text())+1 if count.exists() else 1;count.write_text(str(n))
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_bytes(b'{{}}' if n==1 else json.dumps(response).encode())
print('tokens used\\n23')
''');command.chmod(0o700)
        client=NativeProposalReviewerClient(review=f.original.review,command=str(command),cwd=self.root,timeout_seconds=5)
        result=self.step(client);self.assertEqual((result.status,result.attempts),('complete',2));self.assertEqual(counter.read_text(),'2')
        self.assertEqual(self.step(client).status,'finding_admission');self.assertEqual(counter.read_text(),'2')
        self.assertEqual(json.loads((self.directory(result)/'attempts/2/telemetry.json').read_bytes())['usage']['total_tokens'],23)
        self.run.admit_round(self.record(result));report,_=self.run.run_round(round_number=1,client=Editor(),decided_at=STAMP)
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
