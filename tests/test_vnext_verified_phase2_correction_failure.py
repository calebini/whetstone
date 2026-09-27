"""Phase 2 correction terminal evidence without granting new work."""
import json
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_sequence as sequence_tests
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_phase2_correction_failure import ROOT, STATE_FIELD
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class CorrectionFailureTests(unittest.TestCase):
    def start(self, **kwargs):
        import test_vnext_verified_phase2_client as clients
        return clients.VerifiedPhase2ClientTests.start(self, phase2_correction_failure_contract=True, **kwargs)

    def publish(self, f, terminal):
        status=f.run.publish_phase2_correction_failure()
        self.assertEqual(status['terminal_state'],terminal)
        self.assertTrue(status['committed']);self.assertFalse(status['resume_permitted'])
        recovered=f.run.reconcile_phase2_correction_failure_state()
        self.assertTrue(recovered['state_current']);self.assertTrue(recovered['mirrors_current'])
        return status

    def test_editor_timeout_success_and_promotion_preserve_history(self):
        f,reviewer,_,_,_,number=self.admitted()
        def timeout(packet):raise TimeoutError('Editor timeout')
        f.editor.callback=timeout
        before=f.store.read('rounds/current_verified.json')
        self.assertEqual(f.run.request(round_number=number,client=f.editor).value.status,'timeout')
        pending=f.run.phase2_correction_failure_status()
        self.assertEqual(pending['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        self.assertFalse(pending['committed']);self.assertTrue(pending['publication_required'])
        status=self.publish(f,'HALTED_CLIENT_TIMEOUT')
        packet=json.loads(f.store.read(status['active']['path']))
        report=json.loads(f.store.read(packet['failure']['path']))
        self.assertEqual(report['profile_status']['profiles'][0]['rounds_used'],1)
        self.assertEqual(report['reviewer_final_status'],'not_run')
        self.assertTrue(report['unresolved_major_issues'])
        self.assertEqual(f.store.read('rounds/current_verified.json'),before)
        f.editor.callback=None
        self.assertEqual(f.run.request(round_number=number,client=f.editor,continuation=True).value.status,'complete')
        self.assertIsNone(f.run.phase2_correction_failure_status()['active'])
        f.run.reconcile_phase2_correction_failure_state()
        _,verifier=self.candidate(f,number)
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        recovered=f.run.reconcile_phase2_correction_failure_state()
        self.assertEqual(recovered['history'],status['history']);self.assertIsNone(recovered['active'])
        self.assertEqual(json.loads(f.store.read(status['history'][0]['path'])),packet)
        self.assertEqual(f.editor.calls,2)

    def test_verifier_timeout_then_rejection_keeps_both_dispositions(self):
        f,_,_,_,_,number=self.admitted()
        creation,verifier=self.candidate(f,number)
        before=f.store.read('rounds/current_verified.json')
        verifier.responses=[TimeoutError('Verifier timeout')]
        self.assertEqual(f.run.verify(client=verifier,decided_at=STAMP).value.status,'timeout')
        first=self.publish(f,'HALTED_CLIENT_TIMEOUT')
        packet=json.loads(f.store.read(first['active']['path']))
        old=f.store.read(packet['terminal']['path'])
        self.assertEqual(json.loads(old)['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(json.loads(f.store.read(packet['error']['path']))['client_role'],'verifier')
        response=json.loads(verifier.valid);response.update(verdict='reject',unrelated_semantic_change='detected')
        verifier.responses=[canonical_json_bytes(response)]
        final=f.run.verify(client=verifier,decided_at=STAMP,continuation=True).value.decision
        self.assertTrue(final['decision_final'])
        second=self.publish(f,'TARGET_NOT_REACHED')
        self.assertEqual(len(second['history']),2)
        self.assertEqual(f.store.read(packet['terminal']['path']),old)
        latest=json.loads(f.store.read(json.loads(f.store.read(second['active']['path']))['terminal']['path']))
        self.assertEqual(latest['latest_candidate']['disposition'],'CANDIDATE_REJECTED')
        self.assertEqual(latest['rejected_candidate_ids'],[creation['candidate_id']])
        with self.assertRaises(ValueError):f.run.verify(client=verifier,decided_at=STAMP,continuation=True)
        self.assertEqual(f.store.read('rounds/current_verified.json'),before)
        self.assertEqual(verifier.calls,2)

    def test_invalid_editor_shape_transport_and_deterministic_rejection(self):
        for kind in ('invalid','shape','transport','deterministic','assembly'):
            with self.subTest(kind=kind):
                f,_,_,_,_,number=self.admitted()
                before=f.store.read('rounds/current_verified.json')
                def response(packet):
                    if kind=='transport':raise RuntimeError('provider error')
                    if kind=='shape':return b'bad json'
                    if kind=='invalid':packet['patch']['base_draft_hash']='f'*64
                    else:
                        content='Queue sometimes waits.\n' if kind=='deterministic' else 'Queue always waits.'
                        packet['payloads'][0]['content']=content
                        packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
                    return canonical_json_bytes(packet)
                f.editor.callback=response
                f.run.request(round_number=number,client=f.editor)
                if kind=='deterministic':
                    f.run.register(round_number=number,created_at=STAMP)
                    self.assertEqual(f.run.verify(decided_at=STAMP).value.decision['deterministic_result'],'fail')
                elif kind=='assembly':
                    with self.assertRaises(ValueError):f.run.register(round_number=number,created_at=STAMP)
                status=self.publish(f,'HALTED_ARTIFACT_INVALID')
                packet=json.loads(f.store.read(status['active']['path']))
                terminal=json.loads(f.store.read(packet['terminal']['path']))
                self.assertEqual(terminal['latest_candidate']['disposition'],'CANDIDATE_REJECTED' if kind=='deterministic' else None)
                self.assertEqual(f.store.read('rounds/current_verified.json'),before)
                self.assertEqual(f.editor.calls,2 if kind=='shape' else 1)

    def test_unstarted_and_retained_output_are_not_failures(self):
        f,_,_,_,_,number=self.admitted()
        before=self.files(f)
        self.assertFalse(f.run.phase2_correction_failure_status()['publication_required'])
        self.assertEqual(self.files(f),before)
        publish=f.store.publish
        def lost(token,path,value):
            result=publish(token,path,value)
            if path.endswith('/response.json'):raise OSError('response acknowledgement')
            return result
        with patch.object(f.store,'publish',side_effect=lost):
            with self.assertRaises(OSError):f.run.request(round_number=number,client=f.editor)
        self.reopen(f)
        self.assertFalse(f.run.publish_phase2_correction_failure()['publication_required'])
        self.assertEqual(f.run.phase2_correction_failure_status()['history'],[])
        self.assertEqual(f.run.request(round_number=number,continuation=True).value.status,'complete')
        self.assertEqual(f.editor.calls,1)

    def test_publication_projection_and_uncertain_state_recovery(self):
        from whetstone.vnext_verified_materialization import STATE_PATH
        f,_,_,_,_,number=self.admitted()
        def timeout(packet):raise TimeoutError('bounded failure')
        f.editor.callback=timeout
        f.run.request(round_number=number,client=f.editor)
        for suffix,after in (('/failure.json',False),('/terminal.json',True),('/commit.json',True)):
            publish=f.store.publish
            def fail(token,path,value):
                selected=path.startswith(ROOT+'/') and path.endswith(suffix)
                if selected and not after:raise OSError('publication fault')
                result=publish(token,path,value)
                if selected:raise OSError('publication fault')
                return result
            with patch.object(f.store,'publish',side_effect=fail):
                with self.assertRaisesRegex(OSError,'publication fault'):f.run.publish_phase2_correction_failure()
            self.reopen(f)
        self.assertTrue(f.run.phase2_correction_failure_status()['committed'])
        materialize=f.store.materialize
        def lost(token,path,value,**kwargs):
            result=materialize(token,path,value,**kwargs)
            if path==STATE_PATH:raise OSError('state acknowledgement')
            return result
        with patch.object(f.store,'materialize',side_effect=lost):
            with self.assertRaisesRegex(OSError,'state acknowledgement'):f.run.reconcile_phase2_correction_failure_state()
        self.reopen(f)
        synchronized=[];original=f.store.synchronize_existing
        def sync(token,path,**kwargs):
            synchronized.append(path);return original(token,path,**kwargs)
        with patch.object(f.store,'synchronize_existing',side_effect=sync):
            self.assertTrue(f.run.reconcile_phase2_correction_failure_state()['state_current'])
        self.assertIn(STATE_PATH,synchronized);self.assertEqual(f.editor.calls,1)
        (f.root/'rounds/convergence_failure_report.json').write_bytes(b'unowned')
        with self.assertRaisesRegex(ValueError,'unowned'):f.run.reconcile_phase2_correction_failure_state()

    def test_source_barriers_and_committed_report_tampering_refuse(self):
        f,_,_,_,ref,number=self.admitted()
        def timeout(packet):raise TimeoutError('bounded failure')
        f.editor.callback=timeout;f.run.request(round_number=number,client=f.editor)
        original=f.store.synchronize_existing
        from whetstone.vnext_verified_phase2_entry import ENTRY_PATH
        entry=json.loads(f.store.read(ENTRY_PATH))
        configuration=json.loads(f.store.read(entry['configuration']['path']))
        for source in (ref['path'],f.run._record['review_configuration']['path'],
                       entry['configuration']['path'],configuration['rubric']['artifact']['path']):
            raw=f.store.read(source)
            def drift(token,path,**kwargs):
                result=original(token,path,**kwargs)
                if path==source:(f.root/path).write_bytes(raw+b' ')
                return result
            with patch.object(f.store,'synchronize_existing',side_effect=drift):
                with self.assertRaises(ValueError):f.run.publish_phase2_correction_failure()
            self.assertFalse((f.root/ROOT).exists());(f.root/source).write_bytes(raw)
        publish=f.store.publish;raw=f.store.read(ref['path'])
        def drift_before_commit(token,path,value):
            result=publish(token,path,value)
            if path.startswith(ROOT+'/') and path.endswith('/failure.json'):
                (f.root/ref['path']).write_bytes(raw+b' ')
            return result
        with patch.object(f.store,'publish',side_effect=drift_before_commit):
            with self.assertRaises(ValueError):f.run.publish_phase2_correction_failure()
        self.assertEqual(list((f.root/ROOT).rglob('commit.json')),[])
        (f.root/ref['path']).write_bytes(raw)
        status=self.publish(f,'HALTED_CLIENT_TIMEOUT')
        packet=json.loads(f.store.read(status['active']['path']))
        for path in (ref['path'],packet['failure']['path'],packet['terminal']['path']):
            raw=f.store.read(path);(f.root/path).write_bytes(raw+b' ')
            with self.assertRaises(ValueError):f.run.phase2_correction_failure_status()
            (f.root/path).write_bytes(raw)
        request_path=packet['client_request']['path']
        invocation_path=request_path.rsplit('/',1)[0]+'/attempts/1/invocation.json'
        request_raw=f.store.read(request_path);invocation_raw=f.store.read(invocation_path)
        header=json.loads(request_raw);invocation=json.loads(invocation_raw)
        header['transport']['command']='different-editor'
        invocation['transport']['command']='different-editor'
        (f.root/request_path).write_bytes(canonical_json_bytes(header))
        (f.root/invocation_path).write_bytes(canonical_json_bytes(invocation))
        with self.assertRaisesRegex(ValueError,'exact evidence replay'):f.run.phase2_correction_failure_status()
        (f.root/request_path).write_bytes(request_raw);(f.root/invocation_path).write_bytes(invocation_raw)
        invocation=json.loads(invocation_raw);invocation['transport']['timeout_seconds']+=1
        (f.root/invocation_path).write_bytes(canonical_json_bytes(invocation))
        with self.assertRaises(ValueError):f.run.phase2_correction_failure_status()
        (f.root/invocation_path).write_bytes(invocation_raw)
        self.assertEqual(f.editor.calls,1)

    def test_verifier_invalid_shape_transport_and_prepared_decision(self):
        for kind in ('shape','invalid','transport','prepared'):
            with self.subTest(kind=kind):
                f,_,_,_,_,number=self.admitted();_,verifier=self.candidate(f,number)
                if kind=='shape':verifier.responses=[b'bad json',b'bad json']
                elif kind=='transport':verifier.responses=[RuntimeError('transport rejected')]
                elif kind=='invalid':
                    response=json.loads(verifier.valid);response['context_hash']='f'*64
                    verifier.responses=[canonical_json_bytes(response)]
                else:
                    response=json.loads(verifier.valid);response.update(verdict='reject',unrelated_semantic_change='detected')
                    verifier.responses=[canonical_json_bytes(response)]
                if kind=='prepared':
                    publish=f.store.publish
                    def lost(token,path,value):
                        result=publish(token,path,value)
                        if path.endswith('/candidate_verification-attempt-2.json'):raise OSError('decision ack')
                        return result
                    with patch.object(f.store,'publish',side_effect=lost):
                        with self.assertRaises(OSError):f.run.verify(client=verifier,decided_at=STAMP)
                    self.reopen(f)
                    status=f.run.phase2_correction_failure_status()
                    self.assertEqual(status['gate'],'verification_commit_recovery_required')
                    self.assertFalse(status['publication_required']);self.assertIsNone(status['terminal_state'])
                    f.run.verify(decided_at=STAMP,continuation=True)
                    self.publish(f,'TARGET_NOT_REACHED')
                else:
                    f.run.verify(client=verifier,decided_at=STAMP)
                    status=self.publish(f,'HALTED_ARTIFACT_INVALID')
                    packet=json.loads(f.store.read(status['active']['path']))
                    report=json.loads(f.store.read(packet['terminal']['path']))
                    self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
                self.assertEqual(verifier.calls,2 if kind=='shape' else 1)

    def test_operator_choice_is_final_rejection_and_not_resume(self):
        import test_vnext_unit_preflight as unit
        from whetstone.vnext_identity import binding_id
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        from test_vnext_semantic_repeated_followup import unresolved_interpretation
        original=unit.UnitPreflightTests.setUp
        def authority(test):
            original(test);fixture=test.c.f
            ref=fixture.save('inputs/waiting-authority.md',b'Queue waiting applies to each work start.\n')
            target=next(r for r in fixture.authority['bindings'] if r['role']=='mutable_target')
            binding=dict(path=ref['path'],content_hash=ref['hash'],role='normative_authority',
                authority_scopes=target['authority_scopes'],effective_horizon='current',mutable=False,may_introduce_requirements=True)
            binding['binding_id']=binding_id(binding);fixture.authority['bindings'].append(binding)
            fixture.authority['precedence']=[dict(authority_scope=scope,
                ordered_binding_ids=[binding['binding_id'],target['binding_id']],conflict_policy='pause') for scope in target['authority_scopes']]
            fixture.rebind()
        with patch.object(unit.UnitPreflightTests,'setUp',side_effect=authority,autospec=True):
            f,_,_,_,_,number=self.admitted()
        creation,verifier=self.candidate(f,number)
        context=load_registered_semantic_context(f.store,admission=f.run._history(),candidate_id=creation['candidate_id'])
        verifier.responses=[unresolved_interpretation(verifier,context)]
        decision=f.run.verify(client=verifier,decided_at=STAMP).value.decision
        self.assertEqual(decision['semantic_result'],'operator_decision_required')
        status=self.publish(f,'PAUSED_DECISION')
        packet=json.loads(f.store.read(status['active']['path']))
        report=json.loads(f.store.read(packet['terminal']['path']))
        self.assertEqual(report['outstanding_decision_ids'],decision['outstanding_decision_ids'])
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_REJECTED')
        self.assertIsNone(packet['error']);self.assertFalse(report['resume']['permitted'])
        with self.assertRaises(ValueError):f.run.verify(client=verifier,decided_at=STAMP,continuation=True)
        self.assertEqual(verifier.calls,1)

    def test_second_editor_failure_and_fresh_process_state_recovery(self):
        import subprocess
        f,_,_,_,_,number=self.admitted()
        def timeout(packet):raise TimeoutError('bounded failure')
        f.editor.callback=timeout;f.run.request(round_number=number,client=f.editor)
        first=self.publish(f,'HALTED_CLIENT_TIMEOUT')
        f.run.request(round_number=number,client=f.editor,continuation=True)
        status=f.run.publish_phase2_correction_failure();self.assertEqual(len(status['history']),2)
        original=f.store.replace_pointer
        source=f.run._record['review_configuration']['path'];source_raw=f.store.read(source)
        old_error=f.store.read('rounds/artifact_validation_error.json')
        def drift(token,path,**kwargs):
            (f.root/source).write_bytes(source_raw+b' ')
            try:return original(token,path,**kwargs)
            finally:(f.root/source).write_bytes(source_raw)
        with patch.object(f.store,'replace_pointer',side_effect=drift):
            with self.assertRaises(ValueError):f.run.reconcile_phase2_correction_failure_state()
        self.assertEqual(f.store.read('rounds/artifact_validation_error.json'),old_error)
        def lost(token,path,**kwargs):
            result=original(token,path,**kwargs)
            if path=='rounds/convergence_failure_report.json':raise OSError('mirror acknowledgement')
            return result
        with patch.object(f.store,'replace_pointer',side_effect=lost):
            with self.assertRaises(OSError):f.run.reconcile_phase2_correction_failure_state()
        script="""import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path=sys.argv[1:];manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(run.reconcile_phase2_correction_failure_state()))
"""
        child=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path)],capture_output=True,timeout=180)
        self.assertEqual(child.returncode,0,child.stderr.decode());self.assertTrue(json.loads(child.stdout)['state_current'])
        self.assertEqual(json.loads(f.store.read('rounds/artifact_validation_error.json'))['attempts'][-1]['attempt_number'],2)
        self.assertEqual(f.run.request(round_number=number,client=f.editor,continuation=True).value.status,'attempts_exhausted')
        self.assertEqual(f.editor.calls,2);self.assertEqual(first['history'],status['history'][:1])

    def test_later_failure_and_reviewer_reports_share_owned_projections(self):
        f,reviewer,_,_,_,number=self.admitted()
        _,verifier=self.candidate(f,number);f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        client=self.next_client(reviewer,clean=False)
        bound=f.run.bind_phase2_next_review(client.transport_binding)
        def timeout_review(c,p):raise TimeoutError('Reviewer timeout')
        original=client.callback;client.callback=timeout_review
        f.run.continue_phase2_pass(2,action='execute',client=client);f.run.reconcile_phase2_failure_state()
        reviewer_history=f.run.phase2_failure_status()['history']
        client.callback=original
        result=f.run.continue_phase2_pass(2,action='execute',client=client,continuation=True)
        f.run.reconcile_phase2_failure_state();f.run.continue_phase2_pass(2,action='consume')
        f.run.continue_phase2_pass(2,action='advice',advice=self.advice(bound,result))
        ref=f.run.continue_phase2_pass(2,action='admit');number=json.loads(f.store.read(ref['path']))['round_number']
        def timeout_editor(p):raise TimeoutError('later Editor timeout')
        f.editor.callback=timeout_editor;f.run.request(round_number=number,client=f.editor)
        status=self.publish(f,'HALTED_CLIENT_TIMEOUT')
        packet=json.loads(f.store.read(status['active']['path']))
        self.assertEqual(packet['current_verified_pointer'],bound.request['base_pointer'])
        self.assertEqual(json.loads(f.store.read(packet['terminal']['path']))['latest_candidate']['disposition'],'CANDIDATE_PROMOTED')
        expected=f.store.read('rounds/convergence_failure_report.json')
        f.run.reconcile_phase2_failure_state()
        self.assertEqual(f.store.read('rounds/convergence_failure_report.json'),expected)
        self.assertEqual(f.run.phase2_failure_status()['history'],reviewer_history)
        self.assertTrue(f.run.phase2_correction_failure_status()['mirrors_current'])

    def test_correction_history_through_later_reviewer_and_final_closeout(self):
        import test_vnext_verified_phase2_termination as termination
        for exhausted in (True,False):
            with self.subTest(exhausted=exhausted):
                original_config=self.config
                def config(f):
                    value=original_config(f);value['profiles'][-1]['budget']=1
                    return value
                with patch.object(self,'config',side_effect=config):
                    f,reviewer,_,_,_,number=self.admitted()
                def timeout(packet):raise TimeoutError('Editor timeout')
                f.editor.callback=timeout;f.run.request(round_number=number,client=f.editor)
                old=self.publish(f,'HALTED_CLIENT_TIMEOUT')
                f.editor.callback=None;f.run.request(round_number=number,client=f.editor,continuation=True)
                _,verifier=self.candidate(f,number);f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
                f.run.reconcile_phase2_correction_failure_state()
                client=self.next_client(reviewer)
                bound=f.run.bind_phase2_next_review(client.transport_binding)
                if not exhausted:
                    original=client.callback
                    def reviewer_timeout(c,p):raise TimeoutError('later Reviewer timeout')
                    client.callback=reviewer_timeout
                    f.run.continue_phase2_pass(2,action='execute',client=client);f.run.reconcile_phase2_failure_state()
                    new=f.store.read('rounds/convergence_failure_report.json')
                    f.run.reconcile_phase2_correction_failure_state()
                    self.assertEqual(f.store.read('rounds/convergence_failure_report.json'),new)
                    client.callback=original
                    f.run.continue_phase2_pass(2,action='execute',client=client,continuation=True)
                    f.run.reconcile_phase2_failure_state()
                else:
                    # Exhaustion must also replace a correction-only mirror, with no Reviewer failure history.
                    f.run.continue_phase2_pass(2,action='execute',client=client)
                f.run.continue_phase2_pass(2,action='consume')
                self.advance(f,client)
                f.run.prepare_phase2_declaration()
                if exhausted:
                    def final_serious(c,p):
                        inputs=json.loads(c.prompts[-1].splitlines()[-1])
                        p['draft_hash']=sha256_bytes(inputs['draft'].encode())
                        return termination.FinalTerminationTests.serious(c,p)
                    client.callback=final_serious
                self.advance(f,client)
                f.run.reconcile_phase2_findings();finished=f.run.finish_phase2()
                self.assertEqual(finished['packet']['terminal_state'],'TARGET_NOT_REACHED' if exhausted else 'CONVERGED')
                f.run.reconcile_phase2_state()
                mirror=f.store.read('rounds/convergence_failure_report.json')
                status=f.run.reconcile_phase2_correction_failure_state();f.run.reconcile_phase2_failure_state()
                self.assertEqual(status['history'],old['history']);self.assertIsNone(status['active'])
                self.assertEqual(f.store.read('rounds/convergence_failure_report.json'),mirror)

    def test_interrupted_invocation_and_available_shape_retry_do_not_invent_outcomes(self):
        for stage in ('editor','verifier'):
            with self.subTest(stage=stage):
                f,_,_,_,_,number=self.admitted()
                if stage=='editor':
                    client=f.editor
                    invoke=lambda **kwargs:f.run.request(round_number=number,**kwargs)
                else:
                    _,client=self.candidate(f,number)
                    invoke=lambda **kwargs:f.run.verify(decided_at=STAMP,**kwargs)
                publish=f.store.publish
                def lost(token,path,value):
                    result=publish(token,path,value)
                    if path.endswith('/invocation.json'):raise OSError('invocation acknowledgement')
                    return result
                with patch.object(f.store,'publish',side_effect=lost):
                    with self.assertRaises(OSError):invoke(client=client)
                self.reopen(f)
                status=self.publish(f,'HALTED_ARTIFACT_INVALID')
                packet=json.loads(f.store.read(status['active']['path']))
                error=json.loads(f.store.read(packet['error']['path']))
                self.assertEqual(error['failure_type'],'client_error');self.assertEqual(client.calls,0)
                invoke(client=client,continuation=True)
                self.assertEqual(client.calls,1)
                # A successful Verifier is now waiting for promotion; no fresh work is granted.
                if stage=='verifier':f.run.promote(prepared_at=STAMP)
                self.assertIsNone(f.run.reconcile_phase2_correction_failure_state()['active'])
        f,_,_,_,_,number=self.admitted()
        f.editor.callback=lambda packet:b'bad json'
        publish=f.store.publish
        def lost_shape(token,path,value):
            result=publish(token,path,value)
            if path.endswith('/outcome.json'):raise OSError('shape acknowledgement')
            return result
        with patch.object(f.store,'publish',side_effect=lost_shape):
            with self.assertRaises(OSError):f.run.request(round_number=number,client=f.editor)
        status=f.run.publish_phase2_correction_failure()
        self.assertEqual(status['history'],[]);self.assertFalse(status['publication_required'])
        f.editor.callback=None
        self.assertEqual(f.run.request(round_number=number,client=f.editor,continuation=True).value.status,'complete')
        self.assertEqual(f.editor.calls,2)


for name,value in sequence_tests.Phase2SequenceTests.__dict__.items():
    if not name.startswith('test_') and not name.startswith('__') and name not in CorrectionFailureTests.__dict__:
        setattr(CorrectionFailureTests,name,value)
