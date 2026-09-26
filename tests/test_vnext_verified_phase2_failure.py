"""Reviewer failure publication, retained history and explicit continuation."""
import json
import sys
import subprocess
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_termination as terminal
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_phase2_failure import STATE_FIELD, MIRRORS
from whetstone.vnext_verified_materialization import STATE_PATH


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class ReviewerFailureTests(unittest.TestCase):
    def start(self,**kwargs):
        import test_vnext_verified_phase2_findings as findings
        return findings.FinalFindingsTests.start(self,phase2_failure_contract=True,**kwargs)

    def test_timeout_publication_recovery_and_success_preserve_history(self):
        f,reviewer,_=self.ready()
        def timeout(c,p):raise TimeoutError('bounded timeout')
        reviewer.callback=timeout
        draft=f.store.read('spec.md')
        result=f.run.run_phase2_review(client=reviewer)
        self.assertEqual(result.status,'timeout')
        status=f.run.phase2_failure_status()
        self.assertEqual(status['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        self.assertTrue(status['committed']);self.assertTrue(status['resume_permitted'])
        self.assertFalse(status['state_current'])
        calls=reviewer.calls
        recovered=f.run.run_phase2_review(client=reviewer,continuation=True)
        self.assertEqual(recovered['gate'],'reviewer_failure_state_recovery_required')
        f.run.reconcile_phase2_failure_state()
        self.assertEqual(reviewer.calls,calls)
        history=f.store.read(status['active']['path'])
        report=json.loads(f.store.read(MIRRORS['failure']))
        self.assertEqual(report['reviewer_final_status'],'not_run')
        self.assertIsNone(report['final_declaration_path'])
        self.assertEqual([p['rounds_used'] for p in report['profile_status']['profiles']],[0,0,0])
        reviewer.callback=lambda c,p:canonical_json_bytes({**p,'feedback':[]})
        result=f.run.run_phase2_review(client=reviewer,continuation=True)
        self.assertEqual(result.status,'complete')
        self.assertIsNone(f.run.phase2_failure_status()['terminal_state'])
        self.assertFalse(f.run.phase2_failure_status()['state_current'])
        f.run.reconcile_phase2_failure_state()
        self.assertEqual(f.store.read(status['active']['path']),history)
        self.assertEqual(f.store.read('spec.md'),draft)
        self.assertIsNone(json.loads(f.store.read(STATE_PATH))[STATE_FIELD]['active'])
        self.assertEqual(f.run.consume_phase2_result()['accepted_passes'],1)
        self.assertEqual(reviewer.calls,calls+1)

    def child_failure(self,f,*,recover=False):
        script="""import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path,recover=sys.argv[1:];manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(run.reconcile_phase2_failure_state() if recover=='yes' else run.phase2_failure_status()))
"""
        result=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path),'yes' if recover else 'no'],
                              capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr.decode());return json.loads(result.stdout)

    def timeout(self,client):
        def fail(c,p):raise TimeoutError('bounded timeout')
        client.callback=fail

    def test_second_failure_replaces_owned_projection_and_closes_attempts(self):
        f,client,_=self.ready();self.timeout(client)
        f.run.run_phase2_review(client=client);f.run.reconcile_phase2_failure_state()
        first=f.run.phase2_failure_status()['active'];raw=f.store.read(first['path'])
        result=f.run.run_phase2_review(client=client,continuation=True)
        self.assertEqual(result.status,'timeout')
        status=f.run.phase2_failure_status();self.assertEqual(len(status['history']),2)
        self.assertFalse(status['resume_permitted'])
        for destination in (MIRRORS['error'],MIRRORS['failure']):
            replace=f.store.replace_pointer
            def lost(token,path,**kwargs):
                result=replace(token,path,**kwargs)
                if path==destination:raise OSError('projection acknowledgement')
                return result
            with patch.object(f.store,'replace_pointer',side_effect=lost):
                with self.assertRaisesRegex(OSError,'projection acknowledgement'):f.run.reconcile_phase2_failure_state()
            self.reopen(f)
        f.run.reconcile_phase2_failure_state()
        report=json.loads(f.store.read(MIRRORS['error']))
        self.assertEqual(len(report['attempts']),2);self.assertTrue(report['retry_exhausted'])
        self.assertEqual(f.store.read(first['path']),raw)
        self.assertEqual(f.run.run_phase2_review(client=client,continuation=True).status,'attempts_exhausted')
        self.assertEqual(client.calls,2)

    def test_invalid_transport_and_shape_failures_keep_exact_causes(self):
        for kind in ('invalid','transport','shape'):
            with self.subTest(kind=kind):
                f,client,_=self.ready()
                def response(c,p):
                    if kind=='transport':raise RuntimeError('provider authentication failure')
                    if kind=='shape':return b'invalid json'
                    return canonical_json_bytes({**p,'draft_hash':'0'*64})
                client.callback=response
                f.run.run_phase2_review(client=client)
                status=f.run.phase2_failure_status()
                self.assertEqual(status['terminal_state'],'HALTED_ARTIFACT_INVALID')
                f.run.reconcile_phase2_failure_state()
                error=json.loads(f.store.read(MIRRORS['error']))
                self.assertEqual(error['failure_type'],'client_error' if kind=='transport' else 'artifact_validation')
                self.assertEqual(client.calls,2 if kind=='shape' else 1)
                self.assertEqual(status['resume_permitted'],kind=='transport')
                self.assertEqual(f.run.phase2_sequence_status()['profiles'][0]['rounds_used'],0)

    def test_later_and_final_failed_reviews_reach_both_closeout_outcomes(self):
        for serious in (False,True):
            with self.subTest(serious=serious):
                f,reviewer,client=self.clean_start()
                bound=f.run.bind_phase2_next_review(client.transport_binding)
                self.timeout(client)
                f.run.continue_phase2_pass(2,action='execute',client=client)
                f.run.reconcile_phase2_failure_state()
                client.callback=lambda c,p:canonical_json_bytes({**p,'feedback':[]})
                f.run.continue_phase2_pass(2,action='execute',client=client,continuation=True)
                f.run.reconcile_phase2_failure_state();f.run.continue_phase2_pass(2,action='consume')
                f.run.prepare_phase2_declaration();f.run.bind_phase2_next_review(client.transport_binding)
                self.timeout(client)
                f.run.continue_phase2_pass(3,action='execute',client=client)
                f.run.reconcile_phase2_failure_state()
                old=f.store.read(MIRRORS['failure'])
                self.assertIsNotNone(json.loads(old)['final_declaration_path'])
                client.callback=self.serious if serious else lambda c,p:canonical_json_bytes({**p,'feedback':[]})
                f.run.continue_phase2_pass(3,action='execute',client=client,continuation=True)
                f.run.reconcile_phase2_failure_state();f.run.continue_phase2_pass(3,action='consume')
                f.run.reconcile_phase2_findings();finished=f.run.finish_phase2()
                recovered=f.run.reconcile_phase2_state()
                self.assertEqual(finished['packet']['terminal_state'],'TARGET_NOT_REACHED' if serious else 'CONVERGED')
                self.assertTrue(recovered['halt_complete'] if serious else recovered['phase_complete'])
                self.assertIsNone(f.run.phase2_failure_status()['terminal_state'])
                f.run.reconcile_phase2_failure_state()
                if serious:self.assertNotEqual(f.store.read(MIRRORS['failure']),old)
                else:self.assertEqual(f.store.read(MIRRORS['failure']),old)
                self.assertEqual(len(f.run.phase2_failure_status()['history']),2)

    def test_failure_history_survives_verified_promotion(self):
        from vnext_fixtures import STAMP
        f,reviewer,client=self.clean_start()
        bound=f.run.bind_phase2_next_review(client.transport_binding);self.timeout(client)
        f.run.continue_phase2_pass(2,action='execute',client=client);f.run.reconcile_phase2_failure_state()
        ref=f.run.phase2_failure_status()['active'];before=f.store.read(ref['path'])
        client.callback=self.next_client(reviewer,clean=False).callback
        result=f.run.continue_phase2_pass(2,action='execute',client=client,continuation=True)
        f.run.reconcile_phase2_failure_state();f.run.continue_phase2_pass(2,action='consume')
        f.run.continue_phase2_pass(2,action='advice',advice=self.advice(bound,result))
        f.run.continue_phase2_pass(2,action='admit')
        _,verifier=self.candidate(f,bound.request['round_number'])
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        self.assertIsNone(f.run.phase2_failure_status()['terminal_state'])
        self.assertEqual(f.store.read(ref['path']),before)
        clean=self.next_client(reviewer);request=f.run.bind_phase2_next_review(clean.transport_binding)
        self.timeout(clean);f.run.continue_phase2_pass(3,action='execute',client=clean)
        f.run.reconcile_phase2_failure_state()
        failure=json.loads(f.store.read(MIRRORS['failure']))
        self.assertNotEqual(failure['last_draft_hash'],failure['last_accepted_draft_hash'])
        self.assertEqual(len(f.run.phase2_failure_status()['history']),2)

    def test_publication_and_uncertain_final_state_recover_without_clients(self):
        f,client,_=self.ready();self.timeout(client)
        with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,'/failure.json')):
            with self.assertRaises(OSError):f.run.run_phase2_review(client=client)
        self.reopen(f)
        for suffix in ('/error.json','/terminal.json','/rubric_manifest.json','/commit.json'):
            publish=f.store.publish
            def before_write(token,path,value):
                if path.endswith(suffix):raise OSError('before report publication')
                return publish(token,path,value)
            with patch.object(f.store,'publish',side_effect=before_write):
                with self.assertRaisesRegex(OSError,'before report publication'):f.run.publish_phase2_failure()
            with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,suffix)):
                with self.assertRaises(OSError):f.run.publish_phase2_failure()
            self.reopen(f)
        f.run.publish_phase2_failure()
        with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,MIRRORS['error'])):
            with self.assertRaises(OSError):f.run.reconcile_phase2_failure_state()
        materialize=f.store.materialize
        def lost(token,path,raw,**kwargs):
            result=materialize(token,path,raw,**kwargs)
            if path==STATE_PATH:raise OSError('final state acknowledgement')
            return result
        with patch.object(f.store,'materialize',side_effect=lost):
            with self.assertRaises(OSError):f.run.reconcile_phase2_failure_state()
        self.reopen(f)
        self.assertEqual(self.child_failure(f,recover=True)['gate'],'reviewer_failure_state_recovered')
        f.run.reconcile_phase2_failure_state()
        self.assertTrue(f.run.phase2_failure_status()['state_current']);self.assertEqual(client.calls,1)

    def test_retained_response_and_uncertain_invocation_are_distinct(self):
        for suffix in ('/response.json','/invocation.json'):
            with self.subTest(suffix=suffix):
                f,client,_=self.ready();client.callback=lambda c,p:canonical_json_bytes({**p,'feedback':[]})
                with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,suffix)):
                    with self.assertRaises(OSError):f.run.run_phase2_review(client=client)
                self.reopen(f);calls=client.calls
                if suffix=='/invocation.json':
                    f.run.publish_phase2_failure();f.run.reconcile_phase2_failure_state()
                    self.assertEqual(f.run.phase2_failure_status()['terminal_state'],'HALTED_ARTIFACT_INVALID')
                else:self.assertIsNone(f.run.phase2_failure_status()['terminal_state'])
                result=f.run.run_phase2_review(client=client,continuation=True)
                self.assertEqual(result.status,'complete')
                self.assertEqual(client.calls,calls+(suffix=='/invocation.json'))

    def test_tampering_cache_and_unowned_reports_cannot_grant_continuation(self):
        f,client,_=self.ready();self.timeout(client)
        f.run.run_phase2_review(client=client)
        status=f.run.phase2_failure_status();packet=json.loads(f.store.read(status['active']['path']))
        for ref in (packet['request'],packet['outcomes'][0],packet['failure'],packet['terminal'],status['active']):
            path=f.root/ref['path'];raw=path.read_bytes();path.write_bytes(raw+b' ')
            before=self.files(f)
            with self.assertRaises(ValueError):f.run.reconcile_phase2_failure_state()
            self.assertEqual(self.files(f),before);path.write_bytes(raw)
        path=f.root/packet['failure']['path'];raw=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(ValueError,'lacks its report'):f.run.phase2_failure_status()
        path.write_bytes(raw)
        sync=f.store.synchronize_existing
        def drift(token,name,**kwargs):
            result=sync(token,name,**kwargs)
            if name==packet['request']['path']:path.write_bytes(raw+b' ')
            return result
        with patch.object(f.store,'synchronize_existing',side_effect=drift):
            with self.assertRaises(ValueError):f.run.reconcile_phase2_failure_state()
        path.write_bytes(raw)
        state=json.loads(f.store.read(STATE_PATH));state[STATE_FIELD]={'active':None,'history':[]}
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        self.assertEqual(f.run.run_phase2_review(client=client,continuation=True)['gate'],'reviewer_failure_state_recovery_required')
        (f.root/MIRRORS['failure']).write_bytes(b'unowned')
        with self.assertRaisesRegex(ValueError,'unowned'):f.run.reconcile_phase2_failure_state()
        self.assertEqual(client.calls,1)

    def test_available_shape_retry_and_unstarted_request_are_not_failures(self):
        f,client,_=self.ready();before=self.files(f)
        self.assertIsNone(f.run.publish_phase2_failure()['terminal_state'])
        with self.assertRaisesRegex(ValueError,'explicit boolean'):
            f.run.run_phase2_review(client=client,continuation=1)
        self.assertEqual(self.files(f),before);self.assertEqual(client.calls,0)
        def response(c,p):
            return b'bad json' if c.calls==1 else canonical_json_bytes({**p,'feedback':[]})
        client.callback=response
        with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,'/outcome.json')):
            with self.assertRaises(OSError):f.run.run_phase2_review(client=client)
        self.reopen(f);before=self.files(f)
        status=f.run.phase2_failure_status()
        self.assertIsNone(status['terminal_state']);self.assertFalse(status['publication_required'])
        self.assertEqual(self.files(f),before)
        result=f.run.run_phase2_review(client=client,continuation=True)
        self.assertEqual(result.status,'complete');self.assertEqual(client.calls,2)
        self.assertEqual(f.run.consume_phase2_result()['accepted_passes'],1)


# Reuse helper methods without inheriting the old test cases.
for name,value in terminal.FinalTerminationTests.__dict__.items():
    if not name.startswith('test_') and not name.startswith('__') and name not in ReviewerFailureTests.__dict__:
        setattr(ReviewerFailureTests,name,value)
