"""Target-specific declaration entry and completion before the full sweep."""
import json
import sys
import subprocess
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_client as clients
import test_vnext_verified_phase2_rubric as rubric
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class TargetRuntimeTests(unittest.TestCase):
    setUpClass=rubric.RubricRuntimeTests.setUpClass
    fixture=rubric.RubricRuntimeTests.fixture
    files=rubric.RubricRuntimeTests.files
    reopen=rubric.RubricRuntimeTests.reopen
    review=rubric.RubricRuntimeTests.review
    promote=rubric.RubricRuntimeTests.promote
    candidate=rubric.RubricRuntimeTests.candidate
    advice=rubric.RubricRuntimeTests.advice
    advance=rubric.RubricRuntimeTests.advance
    response=rubric.RubricRuntimeTests.response
    target=('final','strict')

    def start(self,**kwargs):
        return rubric.RubricRuntimeTests.start(self,phase2_targets_contract=True,**kwargs)

    def config(self,f):
        config=rubric.RubricRuntimeTests.config(self,f)
        config.update(schema_version='vnext-phase2-configuration-v2',target_phase=self.target[0],target_mode=self.target[1])
        return config

    def ready(self):
        f,client,config=clients.VerifiedPhase2ClientTests.ready(self,bind=False)
        client.transport_binding['output_schema_hash']=sha256_bytes((CONTRACT_ROOT/'schemas/vnext_phase2_rubric_response_v1.schema.json').read_bytes())
        f.run.prepare_phase2_declaration()
        bound=f.run.bind_phase2_review(client.transport_binding)
        self.assertEqual(bound.request['schema_version'],'vnext-phase2-review-request-v6')
        return f,client,config

    def test_clean_targets_complete_with_current_declaration_and_required_profiles(self):
        for target in [('mid','permissive'),('mid','strict'),('final','permissive'),('final','strict')]:
            with self.subTest(target=target):
                self.target=target
                f,client,_=self.ready();client.callback=self.response(gaps=False)
                self.assertEqual(f.run.run_phase2_review(client=client).status,'complete')
                f.run.consume_phase2_result()
                if target==('final','strict'):
                    self.assertEqual(f.run.phase2_sequence_status()['gate'],'review')
                    self.advance(f,client)
                self.assertEqual(f.run.phase2_sequence_status()['gate'],'declaration_closeout_required')
                f.run.reconcile_phase2_findings()
                finished=f.run.finish_phase2()
                self.assertEqual(finished['packet']['terminal_state'],'CONVERGED')
                self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
                self.assertEqual(client.calls,2 if target==('final','strict') else 1)
                self.assertEqual(f.editor.calls,0)
                self.assertFalse((f.root/'rounds/phase2/review_requests/pass-3').exists())
                if target==('final','strict'):
                    before=self.files(f)
                    script="""import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path=sys.argv[1:];manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={key:job[key] for key in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(run.phase2_closeout()))
"""
                    child=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path)],
                                         capture_output=True,timeout=180)
                    self.assertEqual(child.returncode,0,child.stderr.decode())
                    self.assertTrue(json.loads(child.stdout)['phase_complete'])
                    self.assertEqual(self.files(f),before)

    def test_mid_permissive_documents_major_and_rereviews_changed_declaration_counts(self):
        self.target=('mid','permissive')
        f,client,_=self.ready()
        import test_vnext_verified_phase2_signals as signals
        base=signals.SignalRuntimeTests.response(self,'clarify','major')
        client.callback=lambda owner,packet:canonical_json_bytes(dict(review=json.loads(base(owner,packet)),rubric_findings=[]))
        f.run.run_phase2_review(client=client);f.run.consume_phase2_result()
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'review')
        self.assertFalse(f.run.phase2_closeout()['phase_complete'])
        package=f.run.prepare_phase2_declaration()
        self.assertEqual(package['declaration']['counts']['major_issues'],1)
        self.advance(f,client)
        f.run.reconcile_phase2_findings()
        self.assertEqual(f.run.finish_phase2()['packet']['terminal_state'],'CONVERGED')
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual((client.calls,f.editor.calls),(2,0))

    def test_out_of_scope_adversarial_finding_is_retained_without_an_edit_gate(self):
        f,client,_=self.ready();client.callback=self.response(gaps=False)
        self.assertEqual(f.run.run_phase2_review(client=client).status,'complete')
        f.run.consume_phase2_result()
        import test_vnext_verified_phase2_signals as signals
        base=signals.SignalRuntimeTests.response(self,'clarify','major')
        def response(owner,packet):
            review=json.loads(base(owner,packet));review['feedback'][0]['in_scope']=False
            return canonical_json_bytes(dict(review=review,rubric_findings=[]))
        client.callback=response;self.advance(f,client)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'declaration_closeout_required')
        evidence=f.run.reconcile_phase2_findings()
        issues=json.loads(f.store.read(evidence['packet']['unresolved_issues']['path']))['unresolved_issues']
        self.assertEqual(len(issues),1)
        self.assertFalse(issues[0]['in_scope']);self.assertFalse(issues[0]['blocking_acceptance'])
        self.assertEqual(f.run.finish_phase2()['packet']['terminal_state'],'CONVERGED')
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual((client.calls,f.editor.calls),(2,0))

    def test_mid_target_rubric_claim_is_bounded_invalid_output(self):
        self.target=('mid','strict');f,client,_=self.ready()
        import test_vnext_verified_phase2_signals as signals
        from whetstone.vnext_phase2_rubric import catalogue
        base=signals.SignalRuntimeTests.response(self,'clarify','minor')
        def response(owner,packet):
            review=json.loads(base(owner,packet));review['feedback'][0]['rubric_impact']='major'
            inputs=json.loads(owner.prompts[-1].splitlines()[-1])
            self.assertEqual(inputs['rubric_catalogue'],[])
            requirement=catalogue(inputs['rubric'].encode())[0]
            return canonical_json_bytes(dict(review=review,rubric_findings=[dict(
                feedback_id=review['feedback'][0]['feedback_id'],rubric_anchor=requirement['rubric_anchor'],
                requirement_hash=requirement['requirement_hash'])]))
        client.callback=response;pointer=f.store.read('rounds/current_verified.json')
        self.assertEqual(f.run.run_phase2_review(client=client).status,'attempts_exhausted')
        self.assertEqual(f.store.read('rounds/current_verified.json'),pointer)
        self.assertEqual((client.calls,f.editor.calls),(2,0))

    def test_initial_declaration_lost_ack_and_final_ownership_loss_recover(self):
        from whetstone.vnext_local_storage import OwnershipLost
        f,client,_=clients.VerifiedPhase2ClientTests.ready(self,bind=False)
        publish=f.store.publish
        def lose(token,path,value):
            result=publish(token,path,value)
            if path.endswith('/declaration/commit.json'):f.store._invalidate()
            return result
        with patch.object(f.store,'publish',side_effect=lose):
            with self.assertRaises(OwnershipLost):f.run.prepare_phase2_declaration()
        self.reopen(f)
        result=f.run.prepare_phase2_declaration()
        before=self.files(f)
        self.assertEqual(f.run.prepare_phase2_declaration(),result)
        self.assertEqual(self.files(f),before)
        self.assertEqual((client.calls,f.editor.calls),(0,0))

    def test_last_pass_promotion_maintains_current_declaration_then_halts_and_recovers(self):
        original=self.config
        def config(f):
            packet=original(f);packet['profiles'][0]['budget']=1;return packet
        with patch.object(self,'config',side_effect=config):f,client,_=self.ready()
        client.callback=self.response()
        result=f.run.run_phase2_review(client=client);f.run.consume_phase2_result()
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        f.run.bind_phase2_advice(self.advice(bound,result));ref=f.run.admit_phase2_round()
        number=json.loads(f.store.read(ref['path']))['round_number']
        _,verifier=self.candidate(f,number)
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        f.run.publish_phase2_resolutions()
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'budget_exhausted')
        self.assertEqual(f.run.phase2_closeout()['gate'],'declaration_maintenance_required')
        package=f.run.prepare_phase2_declaration()
        pointer=f.store.read('rounds/current_verified.json')
        result=f.run.finish_phase2()
        self.assertEqual(result['packet']['schema_version'],'vnext-phase2-failure-closeout-v2')
        self.assertEqual(result['packet']['terminal_state'],'TARGET_NOT_REACHED')
        self.assertEqual(result['packet']['declaration_binding'],package['reference'])
        report=json.loads(f.store.read(result['packet']['failure_report']['path']))
        self.assertEqual(report['reviewer_final_status'],'not_run')
        self.assertEqual(report['unresolved_rubric_gaps'],[])
        self.assertFalse(result['phase_complete'])
        from whetstone.vnext_verified_materialization import STATE_PATH
        materialize=f.store.materialize
        def lost(token,path,raw,**kwargs):
            result=materialize(token,path,raw,**kwargs)
            if path==STATE_PATH:raise OSError('lost final state acknowledgement')
            return result
        with patch.object(f.store,'materialize',side_effect=lost):
            with self.assertRaises(OSError):f.run.reconcile_phase2_state()
        self.reopen(f)
        self.assertTrue(f.run.reconcile_phase2_state()['halt_complete'])
        self.assertEqual(f.store.read('rounds/current_verified.json'),pointer)
        self.assertEqual((client.calls,f.editor.calls,verifier.calls),(1,1,1))

    def test_nonpermissive_major_stays_source_work_not_convergence(self):
        import test_vnext_verified_phase2_signals as signals
        for target in [('mid','strict'),('final','permissive'),('final','strict')]:
            with self.subTest(target=target):
                self.target=target;f,client,_=self.ready()
                callback=signals.SignalRuntimeTests.response(self,'clarify','major')
                client.callback=lambda owner,packet:canonical_json_bytes(dict(review=json.loads(callback(owner,packet)),rubric_findings=[]))
                f.run.run_phase2_review(client=client);f.run.consume_phase2_result()
                self.assertEqual(f.run.phase2_sequence_status()['gate'],'operator_or_advice_required')
                before=self.files(f)
                with self.assertRaises(ValueError):f.run.finish_phase2()
                self.assertEqual(self.files(f),before)
                self.assertEqual(f.editor.calls,0)

    def test_target_path_preserves_approved_freeze_and_recovery_only_boundary(self):
        import test_vnext_verified_phase2_signals as signals
        f,client,_=self.ready()
        def response(direction):
            callback=signals.SignalRuntimeTests.response(self,direction,'minor')
            return lambda owner,packet:canonical_json_bytes(dict(review=json.loads(callback(owner,packet)),rubric_findings=[]))
        client.callback=response('constrain')
        f.run.run_phase2_review(client=client);f.run.consume_phase2_result()
        client.callback=response('relax');self.advance(f,client)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'oscillation_freeze_required')
        f.run.publish_phase2_signals();recovered=f.run.reconcile_phase2_signal_state()
        self.assertFalse(recovered['resume_permitted']);self.assertIsNone(recovered['terminal_state'])
        before=self.files(f)
        self.assertEqual(f.run.bind_phase2_next_review(client.transport_binding)['gate'],'oscillation_freeze_required')
        with self.assertRaises(ValueError):f.run.prepare_phase2_declaration()
        with self.assertRaises(ValueError):f.run.phase2_operator_context()
        self.assertEqual(self.files(f),before)
        self.assertEqual((client.calls,f.editor.calls),(2,0))
