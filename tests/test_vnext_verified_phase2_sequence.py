"""Later Phase 2 passes, profile budgets and further genuine V corrections."""
from copy import deepcopy
import json
import sys
import subprocess
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_journey as journey
import test_vnext_verified_phase2_client as clients
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_phase2_review import INPUT_PATH
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class Phase2SequenceTests(unittest.TestCase):
    setUpClass=journey.Phase2JourneyTests.setUpClass
    fixture=journey.Phase2JourneyTests.fixture
    files=journey.Phase2JourneyTests.files
    reopen=journey.Phase2JourneyTests.reopen
    ready=journey.Phase2JourneyTests.ready
    reviewed=journey.Phase2JourneyTests.reviewed
    review=journey.Phase2JourneyTests.review
    promote=journey.Phase2JourneyTests.promote
    admitted=journey.Phase2JourneyTests.admitted
    candidate=journey.Phase2JourneyTests.candidate

    def start(self, **kwargs):
        kwargs['phase2_sequence_contract']=True
        return clients.VerifiedPhase2ClientTests.start(self,**kwargs)

    def config(self,f):
        config=journey.Phase2JourneyTests.config(self,f)
        config['profiles'][0]['budget']=3
        return config

    def next_client(self, original, *, clean=True):
        def response(client, packet):
            inputs=json.loads(client.prompts[-1].splitlines()[-1])
            packet['draft_hash']=sha256_bytes(inputs['draft'].encode())
            if clean:
                packet['feedback']=[]
            return canonical_json_bytes(packet)
        return clients.Client(original.transport_binding,original.template,callback=response)

    def advance(self,f,client):
        bound=f.run.bind_phase2_next_review(client.transport_binding)
        ordinal=int(bound.request_ref['path'].split('/pass-')[1].split('/')[0])
        result=f.run.continue_phase2_pass(ordinal,action='execute',client=client)
        self.assertEqual(result.status,'complete')
        consumed=f.run.continue_phase2_pass(ordinal,action='consume')
        return bound,result,consumed

    def test_clean_sequence_has_distinct_repeated_steps_and_no_convergence(self):
        f,reviewer,_=self.ready()
        reviewer.callback=lambda client,packet: canonical_json_bytes({**packet,'feedback':[]})
        f.run.run_phase2_review(client=reviewer);f.run.consume_phase2_result()
        status=f.run.phase2_sequence_status()
        self.assertEqual((status['gate'],status['accepted_passes']),('review',1))
        client=self.next_client(reviewer)
        for index in (2,3):
            bound,result,consumed=self.advance(f,client)
            self.assertEqual(bound.request['step']['index'],index)
            self.assertEqual(consumed['accepted_passes'],index)
            self.assertEqual(bound.request['step']['rounds_used'],0)
            self.reopen(f)
        status=f.run.phase2_sequence_status()
        self.assertEqual(status['gate'],'closeout_required')
        self.assertFalse(status['phase_complete'])
        self.assertEqual([r['rounds_used'] for r in status['profiles']],[1,1,1])
        self.assertEqual(status['clean_profiles'],['adversarial','convergence_strict_check'])
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))
        before=self.files(f)
        self.assertEqual(f.run.bind_phase2_next_review(client.transport_binding)['gate'],'closeout_required')
        self.assertEqual(self.files(f),before)

    def test_promoted_correction_repeats_step_on_new_base_then_advances(self):
        f,reviewer,_,_,_,number=self.admitted()
        _,verifier=self.candidate(f,number)
        f.run.verify(client=verifier,decided_at=STAMP)
        f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        status=f.run.phase2_sequence_status()
        self.assertEqual((status['gate'],status['accepted_passes']),('review',1))
        client=self.next_client(reviewer)
        bound,result,consumed=self.advance(f,client)
        self.assertEqual(bound.request['step'],dict(index=1,profile='convergence_strict_check',round_budget=3,rounds_used=1,pass_number=2))
        self.assertEqual(bound.request['base_pointer']['path'],'rounds/verified_history/current-verified-1.json')
        self.assertEqual(result.review['feedback']['draft_hash'],json.loads(f.store.read('rounds/current_verified.json'))['verified_draft_hash'])
        for step in (2,3):
            bound,_,_=self.advance(f,client)
            self.assertEqual(bound.request['step']['index'],step)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'closeout_required')
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls,verifier.calls),(1,3,1,1))

    def advice(self, bound, result):
        inputs=bound.inputs;job=inputs['job']
        mutable=next(r for r in inputs['authority']['bindings'] if r['role']=='mutable_target')
        return dict(schema_version='vnext-finding-advice-v1',job_id=job['job_id'],
            base_draft_hash=result.review['feedback']['draft_hash'],feedback=deepcopy(result.receipt['feedback']),
            authority_map_hash=job['authority_map_hash'],scope_contract_hash=job['scope_contract_hash'],
            protected_invariants_hash=job['protected_invariants_hash'],findings=[dict(feedback_id=r['feedback_id'],
                classification='editor_fixable',authority_scope_ids=mutable['authority_scopes'],
                source_authority_binding_ids=[mutable['binding_id']],scope_surface_ids=[],
                compatibility_change='none',requested_effects=['clarification']) for r in result.review['feedback']['feedback']])

    def test_later_correction_promotes_and_replays_original_bases(self):
        f,reviewer,_,_,_,first_number=self.admitted()
        _,verifier=self.candidate(f,first_number)
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        client=self.next_client(reviewer,clean=False)
        bound,result,consumed=self.advance(f,client)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'operator_or_advice_required')
        f.run.continue_phase2_pass(2,action='advice',advice=self.advice(bound,result))
        ref=f.run.continue_phase2_pass(2,action='admit')
        number=bound.request['round_number']
        self.assertEqual(json.loads(f.store.read(ref['path']))['base_pointer'],bound.request['base_pointer'])
        def change(packet):
            content='Queue always waits before beginning work.\n'
            packet['payloads'][0]['content']=content
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        f.editor.callback=change
        _,second_verifier=self.candidate(f,number)
        f.run.verify(client=second_verifier,decided_at=STAMP)
        promoted=f.run.promote(prepared_at=STAMP)
        self.assertEqual(promoted.current_pointer['promotion_ordinal'],2)
        self.reopen(f)
        before=self.files(f)
        script = """import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path=sys.argv[1:]; manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(run.phase2_sequence_status()))
"""
        child=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path)],
                             capture_output=True,timeout=180)
        self.assertEqual(child.returncode,0,child.stderr.decode())
        self.assertEqual(json.loads(child.stdout)['accepted_passes'],2)
        self.assertEqual(self.files(f),before)
        historical=f.run._history().load_inputs(f.store.read,number)
        self.assertEqual(historical['base_pointer_ref'],bound.request['base_pointer'])
        self.assertEqual(historical['phase2']['request'],bound.request)
        clean=self.next_client(reviewer)
        third,_,_=self.advance(f,clean)
        self.assertEqual(third.request['step']['rounds_used'],2)
        status=f.run.phase2_sequence_status()
        self.assertEqual((status['gate'],status['accepted_passes']),('review',3))
        self.assertEqual(status['profiles'][0]['rounds_used'],3)
        self.assertEqual((reviewer.calls,client.calls,clean.calls,f.editor.calls,verifier.calls,second_verifier.calls),(1,1,1,2,1,1))
        with self.assertRaisesRegex(ValueError,'historical Phase 2 pass'):
            f.run.continue_phase2_pass(2,action='execute',client=client)

    def clean_start(self):
        f,reviewer,_=self.ready()
        reviewer.callback=lambda client,packet: canonical_json_bytes({**packet,'feedback':[]})
        f.run.run_phase2_review(client=reviewer);f.run.consume_phase2_result()
        return f,reviewer,self.next_client(reviewer)

    def test_lost_request_response_and_consumption_acknowledgements(self):
        f,reviewer,client=self.clean_start()
        def lose(original,suffix):
            def publish(token,path,value):
                result=original(token,path,value)
                if path.endswith(suffix): raise OSError('lost acknowledgement')
                return result
            return publish
        for suffix in ('/inputs.json','/prompt.txt','/request.json'):
            with patch.object(f.store,'publish',side_effect=lose(f.store.publish,suffix)):
                with self.assertRaises(OSError): f.run.bind_phase2_next_review(client.transport_binding)
            self.reopen(f)
        bound=f.run.bind_phase2_next_review(client.transport_binding)
        self.assertTrue(bound.committed)
        with patch.object(f.store,'publish',side_effect=lose(f.store.publish,'/response.json')):
            with self.assertRaises(OSError): f.run.continue_phase2_pass(2,action='execute',client=client)
        self.reopen(f)
        self.assertEqual(f.run.continue_phase2_pass(2,action='execute').status,'continuation_required')
        self.assertEqual(f.run.continue_phase2_pass(2,action='execute',continuation=True).status,'complete')
        with patch.object(f.store,'publish',side_effect=lose(f.store.publish,'/consumption.json')):
            with self.assertRaises(OSError): f.run.continue_phase2_pass(2,action='consume')
        self.reopen(f)
        # Recovery only: an explicit pass selector cannot silently create pass 3.
        consumed=f.run.continue_phase2_pass(2,action='consume')
        self.assertEqual(consumed['accepted_passes'],2)
        self.assertFalse((f.root/'rounds/phase2/review_requests/pass-3/request.json').exists())
        self.assertEqual((reviewer.calls,client.calls),(1,1))

    def test_budget_exhaustion_after_last_correction_does_not_grant_another_review(self):
        config=self.config
        def small(f):
            result=config(f);result['profiles'][0]['budget']=1;return result
        with patch.object(self,'config',side_effect=small):
            f,reviewer,_,_,_,number=self.admitted()
        _,verifier=self.candidate(f,number)
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        before=self.files(f)
        status=f.run.bind_phase2_next_review(reviewer.transport_binding)
        self.assertEqual(status['gate'],'budget_exhausted')
        self.assertEqual(status['profiles'][0]['rounds_used'],1)
        self.assertEqual(self.files(f),before)
        self.assertEqual(reviewer.calls,1)

    def test_stale_sources_gaps_and_unresolved_choices_refuse_before_dispatch(self):
        f,reviewer,client=self.clean_start()
        bound=f.run.bind_phase2_next_review(client.transport_binding)
        before=self.files(f)
        paths=[bound.request['previous_consumption']['path'],bound.request['configuration']['path'],
               bound.request['entry']['path'],bound.inputs['configuration']['rubric']['artifact']['path']]
        for path in paths:
            original=(f.root/path).read_bytes();(f.root/path).write_bytes(original+b' ')
            with self.assertRaises(ValueError): f.run.continue_phase2_pass(2,action='execute',client=client)
            (f.root/path).write_bytes(original)
        self.assertEqual(client.calls,0)
        self.assertEqual(self.files(f),before)
        # A successor directory may not bypass a pending predecessor.
        rogue=f.root/'rounds/phase2/review_requests/pass-4';rogue.mkdir()
        with self.assertRaisesRegex(ValueError,'contiguous'): f.run.phase2_sequence_status()
        rogue.rmdir()
        client=self.next_client(reviewer,clean=False)
        result=f.run.continue_phase2_pass(2,action='execute',client=client)
        f.run.continue_phase2_pass(2,action='consume')
        advice=self.advice(bound,result);advice['findings'][0]['requested_effects']=['weaken']
        f.run.continue_phase2_pass(2,action='advice',advice=advice)
        self.assertEqual(f.run.bind_phase2_next_review(client.transport_binding)['gate'],'operator_or_advice_required')
        with self.assertRaisesRegex(ValueError,'blocked by sequence'):f.run.continue_phase2_pass(2,action='admit')
        self.assertEqual((client.calls,f.editor.calls),(1,0))

    def test_later_transport_retry_and_source_drift_do_not_duplicate_credit(self):
        f,reviewer,client=self.clean_start()
        bound=f.run.bind_phase2_next_review(client.transport_binding)
        valid=client.callback
        client.callback=lambda c,p: b'{broken' if c.calls==1 else valid(c,p)
        result=f.run.continue_phase2_pass(2,action='execute',client=client)
        self.assertEqual((result.status,client.calls),('complete',2))
        self.assertEqual(f.run.continue_phase2_pass(2,action='consume')['accepted_passes'],2)
        self.assertEqual(f.run.continue_phase2_pass(2,action='consume')['accepted_passes'],2)
        self.assertEqual(client.calls,2)
        bound=f.run.bind_phase2_next_review(client.transport_binding)
        path=bound.request['previous_consumption']['path'];original=(f.root/path).read_bytes()
        def drift(c,p):
            (f.root/path).write_bytes(original+b' ')
            return valid(c,p)
        client.callback=drift
        with self.assertRaisesRegex(ValueError,'predecessor/source changed'):
            f.run.continue_phase2_pass(3,action='execute',client=client)
        self.assertFalse((f.root/'rounds/phase2/review_requests/pass-3/execution/result.json').exists())
        (f.root/path).write_bytes(original)
        self.reopen(f)
        self.assertEqual(f.run.continue_phase2_pass(3,action='execute').status,'continuation_required')
        self.assertEqual(f.run.phase2_sequence_status()['accepted_passes'],2)

    def test_unpinned_continuation_refuses_and_entry_state_cannot_grant_permission(self):
        with patch.object(self,'start',side_effect=lambda **kw: journey.Phase2JourneyTests.start(self,**kw)):
            f,reviewer,_=self.ready()
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'continuation contract'):
            f.run.bind_phase2_next_review(reviewer.transport_binding)
        self.assertEqual(self.files(f),before)
        g,reviewer,client=self.clean_start()
        from whetstone.vnext_verified_materialization import STATE_PATH
        state=json.loads(g.store.read(STATE_PATH));state.pop('vnext_phase2_entry')
        (g.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        with self.assertRaisesRegex(ValueError,'entry state recovery'):
            g.run.bind_phase2_next_review(client.transport_binding)
        self.assertEqual(client.calls,0)

    def test_later_advice_round_recovery_and_rejected_candidate_preserve_authority(self):
        f,reviewer,_=self.clean_start()
        client=self.next_client(reviewer,clean=False)
        bound,result,_=self.advance(f,client)
        before=f.store.read('rounds/current_verified.json')
        advice=self.advice(bound,result)
        def lose(original,suffix):
            def publish(token,path,value):
                response=original(token,path,value)
                if path.endswith(suffix): raise OSError('lost acknowledgement')
                return response
            return publish
        for suffix in ('/finding_advice.json','/advice_binding.json'):
            with patch.object(f.store,'publish',side_effect=lose(f.store.publish,suffix)):
                with self.assertRaises(OSError): f.run.continue_phase2_pass(2,action='advice',advice=advice)
            self.reopen(f)
        f.run.continue_phase2_pass(2,action='advice')
        with patch.object(f.store,'publish',side_effect=lose(f.store.publish,'/proposal_input.json')):
            with self.assertRaises(OSError): f.run.continue_phase2_pass(2,action='admit')
        self.reopen(f)
        f.run.continue_phase2_pass(2,action='admit')
        _,verifier=self.candidate(f,bound.request['round_number'])
        response=json.loads(verifier.valid)
        response.update(verdict='reject',unrelated_semantic_change='detected')
        verifier.responses=[canonical_json_bytes(response)]
        decision=f.run.verify(client=verifier,decided_at=STAMP).value.decision
        self.assertEqual(decision['candidate_disposition'],'CANDIDATE_REJECTED')
        self.reopen(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome,'not_eligible')
        self.assertEqual(f.run.bind_phase2_next_review(client.transport_binding)['gate'],'correction_required')
        self.assertEqual(f.store.read('rounds/current_verified.json'),before)
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls,verifier.calls),(1,1,1,1))
