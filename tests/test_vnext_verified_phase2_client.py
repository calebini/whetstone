"""Scripted first Phase 2 invocation, exact result replay and bounded failures."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_phase2_client import JOURNAL_PATH
from whetstone.vnext_verified_phase2_review import REQUEST_PATH
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.identity import oscillation_fingerprint
import test_vnext_verified_review as runtime
import test_vnext_verified_phase2_review as requests
from test_vnext_verified_phase1_status import clean_response


class Client:
    def __init__(self, transport, template, callback=None):
        self.transport_binding=deepcopy(transport)
        self.identity=deepcopy(transport['reviewer'])
        self.template=deepcopy(template)
        self.callback=callback
        self.calls=0
        self.prompts=[]

    def review(self, prompt):
        self.calls+=1
        self.prompts.append(prompt)
        inputs=json.loads(prompt.splitlines()[-1])
        feedback=deepcopy(self.template)
        feedback.update(round_number=inputs['round_number'],profile=inputs['step']['profile'],
            reviewer=deepcopy(self.identity),draft_hash=inputs['entry']['current_verified_draft']['hash'])
        for row in feedback['feedback']:
            row['oscillation_key']=dict(section_id=inputs['base_map']['sections'][0]['canonical_section_id'],
                concern_type='precision_gap',direction='clarify',scope='local')
        return self.callback(self,feedback) if self.callback else canonical_json_bytes(feedback)


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class VerifiedPhase2ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture=runtime.VerifiedReviewTests.fixture
    start=runtime.VerifiedReviewTests.start
    files=runtime.VerifiedReviewTests.files
    reopen=runtime.VerifiedReviewTests.reopen
    review=runtime.VerifiedReviewTests.review
    promote=runtime.VerifiedReviewTests.promote
    config=requests.VerifiedPhase2ReviewTests.config

    def ready(self, *, promoted=False, bind=True):
        f, prior=self.start(phase2_client_contract=True)
        if promoted:
            self.review(f,prior)
            self.promote(f)
        prior.callback=clean_response
        f.run.review_next(client=prior)
        f.run.finish_phase1()
        f.run.reconcile_phase1_state()
        config=self.config(f)
        f.run.bind_phase2_entry(config)
        f.run.enter_phase2()
        transport=deepcopy(prior.transport_binding)
        from whetstone.vnext_contracts import CONTRACT_ROOT
        transport['output_schema_hash']=sha256_bytes((CONTRACT_ROOT/'schemas/phase2_reviewer_feedback_input.schema.json').read_bytes())
        if bind: f.run.bind_phase2_review(transport)
        return f,Client(transport,prior.feedback),config

    def test_valid_feedback_is_canonical_and_completed_replay_preserves_authority(self):
        for promoted in (False,True):
            with self.subTest(promoted=promoted):
                f,client,_=self.ready(promoted=promoted)
                before=self.files(f)
                def fenced_response(owner,feedback):
                    from whetstone.vnext_local_storage import LocalAuthorityStore, StorageBusy
                    f.store._check_owner(f.store._token)
                    peer=LocalAuthorityStore(f.root,job_id=json.loads(f.store.read_descriptor())['job_id'])
                    try:
                        with self.assertRaises(StorageBusy):peer.acquire(lambda read:None)
                    finally:peer.close()
                    return canonical_json_bytes(feedback)
                client.callback=fenced_response
                with patch.object(f.store,'locked',side_effect=AssertionError('status took lock')):
                    self.assertEqual(f.run.phase2_review_status().status,'prepared')
                self.assertEqual(self.files(f),before)
                with patch('whetstone.live_phase2.LivePhase2Runner',side_effect=AssertionError('legacy executor')):
                    result=f.run.run_phase2_review(client=client)
                self.assertEqual(result.status,'complete')
                self.assertEqual(result.round_number,3 if promoted else 2)
                self.assertEqual(result.receipt['accepted_passes'],1)
                key=result.review['feedback']['feedback'][0]['oscillation_key']
                self.assertEqual(key['fingerprint'],oscillation_fingerprint(key['section_id'],'precision_gap','clarify','local'))
                raw=json.loads(f.store.read(JOURNAL_PATH+'/attempts/1/response.json'))
                self.assertNotIn('fingerprint',raw['feedback'][0]['oscillation_key'])
                after=self.files(f)
                self.assertTrue(all(after[p]==v for p,v in before.items()))
                self.assertTrue(all(p.startswith(JOURNAL_PATH+'/') for p in set(after)-set(before)))
                result.review['feedback']['feedback'].clear()
                self.reopen(f)
                self.assertEqual(f.run.phase2_review_status().status,'complete')
                self.assertEqual(f.run.run_phase2_review().status,'complete')
                self.assertEqual(self.files(f),after)
                self.assertEqual(client.calls,1)
                publish=f.store.publish
                def fail(token,path,value):
                    if path==JOURNAL_PATH+'/result.json':raise OSError('result flush')
                    return publish(token,path,value)
                with patch.object(f.store,'publish',side_effect=fail):
                    with self.assertRaisesRegex(OSError,'result flush'):f.run.run_phase2_review()
                self.assertEqual(f.run.run_phase2_review().status,'complete')
                self.assertEqual(client.calls,1)

    def test_shape_and_process_failure_retry_once_and_exhaustion_survives_reopen(self):
        for variant in ('shape','process','exhausted'):
            with self.subTest(variant=variant):
                f,client,_=self.ready()
                def response(owner,feedback):
                    if owner.calls==2 and variant!='exhausted':return canonical_json_bytes(feedback)
                    if variant=='process':
                        feedback['feedback'][0]['issue_type']='context_unread'
                        feedback['feedback'][0]['claim']='Review could not be performed: required context files were not read.'
                        return canonical_json_bytes(feedback)
                    return b'not json'
                client.callback=response
                result=f.run.run_phase2_review(client=client)
                self.assertEqual(client.calls,2)
                self.assertIn('Previous shape errors:',client.prompts[1])
                marker=json.loads(f.store.read(JOURNAL_PATH+'/attempts/2/invocation.json'))
                self.assertEqual(marker['reason'],'shape_retry')
                self.reopen(f)
                if variant=='exhausted':
                    self.assertEqual(result.status,'attempts_exhausted')
                    self.assertFalse((f.root/JOURNAL_PATH/'reviewer_feedback.json').exists())
                    self.assertEqual(f.run.run_phase2_review(client=client,continuation=True).status,'attempts_exhausted')
                else:
                    self.assertEqual(result.status,'complete')
                    self.assertEqual(result.receipt['attempt'],2)
                    self.assertEqual(f.run.run_phase2_review().receipt['accepted_passes'],1)
                self.assertEqual(client.calls,2)

    def test_binding_and_section_contradictions_are_not_shape_retries(self):
        for variant in ('draft','section','duplicate'):
            with self.subTest(variant=variant):
                f,client,_=self.ready()
                def response(owner,feedback):
                    if variant=='draft':feedback['draft_hash']='0'*64
                    elif variant=='section':feedback['feedback'][0]['oscillation_key']['section_id']='not-a-section'
                    else:feedback['feedback'].append(deepcopy(feedback['feedback'][0]))
                    return canonical_json_bytes(feedback)
                client.callback=response
                self.assertEqual(f.run.run_phase2_review(client=client).status,'invalid_review')
                self.assertEqual(client.calls,1)
                self.assertEqual(f.run.run_phase2_review(client=client,continuation=True).status,'invalid_review')
                self.assertEqual(client.calls,1)
                self.assertFalse((f.root/JOURNAL_PATH/'reviewer_feedback.json').exists())

    def test_timeout_and_uncertain_invocation_require_explicit_remaining_slot(self):
        for variant in ('timeout','marker'):
            with self.subTest(variant=variant):
                f,client,_=self.ready()
                if variant=='timeout':
                    def timeout(owner,feedback):raise TimeoutError('bounded timeout')
                    client.callback=timeout
                    self.assertEqual(f.run.run_phase2_review(client=client).status,'timeout')
                    client.callback=None
                    path=f.root/JOURNAL_PATH/'attempts/1/outcome.json'
                    original=path.read_bytes()
                    for key,value in (('request_id','req_'+'0'*64),('attempt',2)):
                        altered=json.loads(original);altered[key]=value
                        path.write_bytes(canonical_json_bytes(altered))
                        before=self.files(f)
                        with self.assertRaisesRegex(ValueError,'outcome binding differs'):f.run.phase2_review_status()
                        with self.assertRaisesRegex(ValueError,'outcome binding differs'):
                            f.run.run_phase2_review(client=client,continuation=True)
                        self.assertEqual(self.files(f),before)
                        self.assertEqual(client.calls,1)
                        path.write_bytes(original)
                else:
                    publish=f.store.publish
                    def stop(token,path,value):
                        result=publish(token,path,value)
                        if path==JOURNAL_PATH+'/attempts/1/invocation.json':raise OSError('marker ack')
                        return result
                    with patch.object(f.store,'publish',side_effect=stop):
                        with self.assertRaisesRegex(OSError,'marker ack'):f.run.run_phase2_review(client=client)
                    self.assertEqual(client.calls,0)
                self.reopen(f)
                calls=client.calls
                self.assertEqual(f.run.run_phase2_review(client=client).status,'continuation_required')
                self.assertEqual(client.calls,calls)
                result=f.run.run_phase2_review(client=client,continuation=True)
                self.assertEqual(result.status,'complete')
                self.assertEqual(result.receipt['attempt'],2)
                self.assertEqual(client.calls,calls+1)

    def test_response_and_result_publication_prefixes_recover_without_client(self):
        for suffix in ('attempts/1/response.json','attempts/1/outcome.json','reviewer_feedback.json','result.json'):
            with self.subTest(suffix=suffix):
                f,client,_=self.ready()
                publish=f.store.publish
                def stop(token,path,value):
                    result=publish(token,path,value)
                    if path==JOURNAL_PATH+'/'+suffix:raise OSError('publication ack')
                    return result
                with patch.object(f.store,'publish',side_effect=stop):
                    with self.assertRaisesRegex(OSError,'publication ack'):f.run.run_phase2_review(client=client)
                self.assertEqual(client.calls,1)
                self.reopen(f)
                status=f.run.phase2_review_status()
                self.assertEqual(status.status,'complete' if suffix=='result.json' else 'valid_response')
                result=f.run.run_phase2_review(continuation=suffix!='result.json')
                self.assertEqual(result.status,'complete')
                self.assertEqual(result.receipt['attempt'],1)
                self.assertEqual(client.calls,1)

    def test_source_barriers_drift_and_separate_mirror_recovery_precede_execution(self):
        f,client,config=self.ready()
        sync=f.store.synchronize_existing
        def fail(token,path,**options):
            if path==REQUEST_PATH:raise OSError('request source barrier')
            return sync(token,path,**options)
        with patch.object(f.store,'synchronize_existing',side_effect=fail):
            with self.assertRaisesRegex(OSError,'request source barrier'):f.run.run_phase2_review(client=client)
        self.assertEqual(client.calls,0)
        (f.root/'spec.md').unlink()
        self.assertEqual(f.run.run_phase2_review(client=client).outcome,'materialization_recovered')
        self.assertEqual(client.calls,0)
        rubric=f.root/config['rubric']['artifact']['path'];original=rubric.read_bytes()
        def drift(owner,feedback):
            rubric.write_bytes(b'drift')
            return canonical_json_bytes(feedback)
        client.callback=drift
        with self.assertRaises(ValueError):f.run.run_phase2_review(client=client)
        self.assertFalse((f.root/JOURNAL_PATH/'result.json').exists())
        rubric.write_bytes(original)
        self.reopen(f)
        self.assertEqual(f.run.run_phase2_review(continuation=True).status,'complete')
        self.assertEqual(client.calls,1)

    def test_missing_request_pins_changed_transport_and_corrupt_receipt_dependencies_refuse(self):
        f,prior=self.start(phase2_review_contract=True)
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'client contracts'):f.run.phase2_review_status()
        self.assertEqual(self.files(f),before)
        f,client,_=self.ready(bind=False)
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'committed Reviewer request'):f.run.run_phase2_review(client=client)
        self.assertEqual(self.files(f),before)
        f.run.bind_phase2_review(client.transport_binding)
        original=deepcopy(client.transport_binding)
        client.transport_binding['timeout_seconds']+=1
        with self.assertRaisesRegex(ValueError,'transport differs'):f.run.run_phase2_review(client=client)
        self.assertEqual(client.calls,0)
        client.transport_binding=original
        result=f.run.run_phase2_review(client=client)
        for key in ('response','outcome','feedback'):
            path=f.root/result.receipt[key]['path'];raw=path.read_bytes();path.unlink()
            before=self.files(f)
            with self.subTest(key=key):
                with self.assertRaises((ValueError,FileNotFoundError)):f.run.run_phase2_review()
                self.assertEqual(self.files(f),before)
            path.write_bytes(raw)
        (f.root/JOURNAL_PATH/'attempts/3').mkdir()
        with self.assertRaisesRegex(ValueError,'unknown Phase 2 Reviewer attempt'):f.run.run_phase2_review(client=client)
        self.assertEqual(client.calls,1)
