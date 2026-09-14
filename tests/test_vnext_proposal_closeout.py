from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_candidate_registry import CandidateAssemblyFailure
from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore,Publication,StorageBusy,StorageWriteError
from whetstone.vnext_proposal_closeout import ProposalDecisionJournal,finish_proposal_round,proposal_terminal_report,run_proposal_round
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests,register_completed_proposal_request
from whetstone.vnext_proposal_requests import run_proposal_request
from whetstone.clients import canonicalize_reviewer_input
import test_vnext_proposal_admission as fixtures
from test_vnext_proposal_requests import Client
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class ProposalCloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ProposalAdmissionTests.setUpClass()
    def setUp(self):
        self.f=fixtures.ProposalAdmissionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.store=self.f.store;self.admission=self.f.admission;self.client=Client()

    def request(self,client=None):
        client=client or self.client
        return run_proposal_request(self.store,load_inputs=lambda read:self.admission.load_inputs(read,1),
            validate_authority=self.admission.validate_authority,client=client)
    def registry(self):return registry_for_proposal_requests(self.store,load_inputs=self.admission.load_inputs,
                                                            validate_authority=self.admission.validate_authority)
    def register(self):
        self.request()
        return register_completed_proposal_request(self.store,round_number=1,load_inputs=self.admission.load_inputs,
            validate_authority=self.admission.validate_authority,created_at=STAMP)
    def finish(self):return finish_proposal_round(self.store,admission=self.admission,round_number=1,decided_at=STAMP)
    def run_round(self,client=None,continuation=False):return run_proposal_round(self.store,admission=self.admission,
        round_number=1,client=client or self.client,decided_at=STAMP,continuation=continuation)
    def raw(self,path):return self.store.read(path)
    def json(self,path):return json.loads(self.raw(path))
    def journal(self):return ProposalDecisionJournal(self.registry())

    def test_passing_determinism_commits_nonfinal_not_run_and_gate_unavailable(self):
        self.request();report,reference=self.finish()
        latest=report['latest_candidate'];decision=self.json(latest['verification_decision_path'])
        self.assertEqual(report['terminal_state'],'TARGET_NOT_REACHED')
        self.assertEqual(report['resume'],dict(permitted=False,next_gate=None,reason='vnext_gate_unavailable'))
        self.assertEqual((decision['deterministic_result'],decision['semantic_result'],decision['decision_final']),('pass','not_run',False))
        self.assertEqual(latest['disposition'],'CANDIDATE_UNVERIFIED');self.assertFalse(report['apply_back_permitted'])
        self.assertEqual(self.raw(reference['path']),canonical_json_bytes(report))
        again,_=self.finish();self.assertEqual(again,report);self.assertEqual(self.client.calls,1)
        self.assertEqual(len(list((self.store._tree.root).rglob('candidate_verification-attempt-*.json'))),1)

    def failing_client(self):
        def fail(packet):
            content='Queue sometimes waits.\n'
            packet['payloads'][0]['content']=content
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        return Client(fail)

    def test_deterministic_failure_commits_final_rejection_without_semantic_evidence(self):
        client=self.failing_client();self.request(client);report,_=self.finish()
        latest=report['latest_candidate'];decision=self.json(latest['verification_decision_path'])
        self.assertEqual((report['terminal_state'],report['resume']['reason']),('HALTED_ARTIFACT_INVALID','vnext_preservation_failed'))
        self.assertEqual((decision['semantic_result'],decision['candidate_disposition'],decision['decision_final']),('not_run','CANDIDATE_REJECTED',True))
        self.assertIsNone(decision['semantic_verification_hash']);self.assertTrue(decision['rejection_codes'])
        self.assertEqual(report['rejected_candidate_ids'],[latest['candidate_id']])
        self.assertFalse(report['resume']['permitted']);self.assertEqual(client.calls,1)
        again=self.journal().commit(latest['candidate_id'],decided_at='2030-01-01T00:00:00Z')
        self.assertEqual(again.decision,decision)
        self.assertFalse(list(self.store._tree.root.rglob('semantic_verification*')))

    def test_every_pre_pointer_prefix_is_prepared_and_recovery_reuses_exact_decision(self):
        creation=self.register();journal=self.journal();directory,decision_path,event_path,snapshot_path,pointer_path=journal._paths(creation)
        original=self.store.publish
        for stop_path in (decision_path,event_path,snapshot_path):
            def stop(token,path,value):
                result=original(token,path,value)
                if path==stop_path:raise OSError('scripted publication interruption')
                return result
            with patch.object(self.store,'publish',side_effect=stop):
                with self.assertRaisesRegex(OSError,'scripted'):journal.commit(creation['candidate_id'],decided_at=STAMP)
            before={p.relative_to(self.store._tree.root).as_posix():p.read_bytes() for p in self.store._tree.root.rglob('*') if p.is_file()}
            view=journal.inspect(creation['candidate_id'])
            self.assertTrue(view.prepared);self.assertIsNone(view.decision)
            self.assertEqual(view.effective_event['new_disposition'],'CANDIDATE_UNVERIFIED')
            report=proposal_terminal_report(self.registry())
            self.assertIsNone(report['latest_candidate']['verification_decision_path'])
            self.assertEqual(report['resume']['next_gate'],'verification_commit')
            after={p.relative_to(self.store._tree.root).as_posix():p.read_bytes() for p in self.store._tree.root.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
        committed=journal.commit(creation['candidate_id'],decided_at='2030-01-01T00:00:00Z')
        self.assertFalse(committed.prepared);self.assertEqual(committed.decision['decided_at'],STAMP)
        self.assertEqual(self.client.calls,1)

    def test_lost_pointer_acknowledgement_uses_actual_committed_disposition(self):
        self.client=self.failing_client();creation=self.register();journal=self.journal()
        pointer_path=journal._paths(creation)[-1];original=self.store._tree.write
        def lost(path,raw,**kwargs):
            result=original(path,raw,**kwargs)
            if path==pointer_path:raise StorageWriteError(Publication('outcome_requires_reconciliation',path,result.hash),'scripted lost acknowledgement')
            return result
        with patch.object(self.store._tree,'write',side_effect=lost):
            with self.assertRaises(StorageWriteError):journal.commit(creation['candidate_id'],decided_at=STAMP)
        view=journal.inspect(creation['candidate_id'])
        self.assertEqual(view.effective_event['new_disposition'],'CANDIDATE_REJECTED');self.assertIsNone(self.store._token)
        self.assertEqual(journal.commit(creation['candidate_id'],decided_at=STAMP).decision,view.decision)

    def test_failed_rejection_before_pointer_keeps_unverified_effective_state(self):
        self.client=self.failing_client();creation=self.register();journal=self.journal()
        with patch.object(self.store,'replace_pointer',side_effect=OSError('scripted pre-commit failure')):
            with self.assertRaises(OSError):journal.commit(creation['candidate_id'],decided_at=STAMP)
        report=proposal_terminal_report(self.registry())
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(report['rejected_candidate_ids'],[])
        journal.commit(creation['candidate_id'],decided_at=STAMP)
        self.assertEqual(proposal_terminal_report(self.registry())['latest_candidate']['disposition'],'CANDIDATE_REJECTED')

    def test_pointer_tampering_and_missing_targets_never_fall_back_to_initial_event(self):
        creation=self.register();journal=self.journal();journal.commit(creation['candidate_id'],decided_at=STAMP)
        _,decision_path,event_path,snapshot_path,pointer_path=journal._paths(creation)
        for path in (decision_path,event_path,snapshot_path):
            target=self.store._tree.root/path;raw=target.read_bytes();target.unlink()
            with self.subTest(path=path),self.assertRaises(ValueError):proposal_terminal_report(self.registry())
            target.write_bytes(raw)
        pointer=self.json(pointer_path);pointer['current_decision_hash']='f'*64
        (self.store._tree.root/pointer_path).write_bytes(canonical_json_bytes(pointer))
        with self.assertRaisesRegex(ValueError,'pointer'):journal.inspect(creation['candidate_id'])

    def test_rehashed_decision_cannot_claim_semantics_or_change_finality(self):
        creation=self.register();journal=self.journal();journal.commit(creation['candidate_id'],decided_at=STAMP)
        decision_path=journal._paths(creation)[1];raw=self.raw(decision_path)
        for changes in ({'semantic_result':'pass'},{'decision_final':True},{'promotion_permitted':True},
                        {'candidate_disposition':'CANDIDATE_REJECTED','decision_final':True,'rejection_codes':['invented']}):
            decision=json.loads(raw);decision.update(changes)
            (self.store._tree.root/decision_path).write_bytes(canonical_json_bytes(decision))
            with self.subTest(changes=changes),self.assertRaises(ValueError):journal.commit(creation['candidate_id'],decided_at=STAMP)
            (self.store._tree.root/decision_path).write_bytes(raw)

    def test_extra_decision_or_event_claim_is_invalid_and_not_selected(self):
        creation=self.register();journal=self.journal();journal.commit(creation['candidate_id'],decided_at=STAMP)
        directory=journal._paths(creation)[0]
        for name in ('candidate_verification-attempt-01.json','candidate_verification-attempt-2.json','disposition_events/event-3.json'):
            path=self.store._tree.root/directory/name;path.write_bytes(b'{}')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'claim'):journal.inspect(creation['candidate_id'])
            path.unlink()

    def test_event_without_decision_source_cannot_be_recovered(self):
        creation=self.register();journal=self.journal();view,report,initial,_=journal._state(creation)
        decision=journal._decision(creation,report,STAMP);event,_=journal._targets(creation,initial,decision)
        path=journal._paths(creation)[2];(self.store._tree.root/path).write_bytes(canonical_json_bytes(event))
        with self.assertRaisesRegex(ValueError,'no decision source'):journal.commit(creation['candidate_id'],decided_at=STAMP)

    def test_incomplete_request_cannot_enter_closeout(self):
        with self.assertRaisesRegex(ValueError,'completed proposal request'):self.finish()
        self.assertEqual(self.client.calls,0)

    def test_competing_owner_cannot_prepare_a_decision_or_allocate_an_ordinal(self):
        creation=self.register();journal=self.journal()
        other=LocalAuthorityStore(self.store._tree.root,job_id=creation['job_id']);self.addCleanup(other.close)
        with other.locked(self.admission.validate_authority):
            with self.assertRaises(StorageBusy):journal.commit(creation['candidate_id'],decided_at=STAMP)
        self.assertFalse((self.store._tree.root/journal._paths(creation)[1]).exists())
        journal.commit(creation['candidate_id'],decided_at=STAMP)
        self.assertEqual(journal.inspect(creation['candidate_id']).decision['decision_ordinal'],1)

    def test_replay_dependency_failure_is_not_acknowledged_as_success(self):
        creation=self.register();journal=self.journal();view=journal.commit(creation['candidate_id'],decided_at=STAMP)
        event_path=journal._paths(creation)[2];original=self.store._tree.write
        def fail(path,raw,**kwargs):
            if path==event_path:raise StorageWriteError(Publication('outcome_requires_reconciliation',path,sha256_bytes(raw)),'scripted barrier failure')
            return original(path,raw,**kwargs)
        with patch.object(self.store._tree,'write',side_effect=fail):
            with self.assertRaises(StorageWriteError):journal.commit(creation['candidate_id'],decided_at=STAMP)
        self.assertIsNone(self.store._token)
        self.assertEqual(journal.inspect(creation['candidate_id']).decision,view.decision)

    def test_real_assembly_boundary_failure_is_retained_before_candidate_creation(self):
        def invalid(packet):
            content='Queue always waits.'
            packet['payloads'][0]['content']=content
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        client=Client(invalid);request=self.request(client);self.assertEqual(request.status,'complete')
        report,_=self.finish();self.assertEqual(report['terminal_state'],'HALTED_ARTIFACT_INVALID')
        self.assertTrue(all(value is None for value in report['latest_candidate'].values()))
        path=f"rounds/round-1/proposals/{request.proposal.patch['proposal_id']}/assembly_failure.json"
        self.assertEqual(self.json(path)['stage'],'assembly');self.assertEqual(client.calls,1)
        self.assertEqual(self.registry().inspect().orphans,())

    def test_failure_evidence_write_error_propagates_without_rejection_or_terminal(self):
        def invalid(packet):
            content='Queue always waits.';packet['payloads'][0]['content']=content
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        self.request(Client(invalid));original=self.store.publish
        def fail(token,path,value):
            if path.endswith('/assembly_failure.json'):raise OSError('scripted diagnostic write failure')
            return original(token,path,value)
        with patch.object(self.store,'publish',side_effect=fail):
            with self.assertRaisesRegex(OSError,'diagnostic write'):self.finish()
        self.assertFalse((self.store._tree.root/'rounds/terminal_reports').exists())
        self.assertEqual(self.registry().inspect().events,())

    def test_round_entry_reaches_endpoint_and_does_not_advertise_an_unimplemented_gate(self):
        report,_=self.run_round();self.assertEqual(report['resume']['reason'],'vnext_gate_unavailable')
        self.assertIsNone(report['resume']['next_gate']);self.assertFalse(report['resume']['permitted'])
        self.assertEqual(self.run_round()[0],report);self.assertEqual(self.client.calls,1)
        with self.assertRaisesRegex(ValueError,'no implemented incomplete gate'):self.run_round(continuation=True)
        self.assertEqual(self.client.calls,1)

    def test_timeout_terminal_retains_exact_cause_and_explicit_continuation(self):
        def timeout(packet):raise TimeoutError('fictional deadline expired')
        failed=Client(timeout);report,_=self.run_round(failed)
        self.assertEqual(report['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        self.assertIn('TimeoutError: fictional deadline expired',report['resume']['reason'])
        self.assertEqual((report['resume']['permitted'],report['resume']['next_gate']),(True,'proposal'))
        self.assertTrue(all(v is None for v in report['latest_candidate'].values()))
        resumed=Client();self.run_round(resumed);self.assertEqual(resumed.calls,0)
        report,_=self.run_round(resumed,True)
        self.assertEqual(report['resume']['reason'],'vnext_gate_unavailable');self.assertEqual(resumed.calls,1)

    def test_timeout_in_final_slot_still_reports_timeout_but_no_resume(self):
        def respond(packet):
            if client.calls==1:return b'{}'
            raise TimeoutError('slot two deadline')
        client=Client(respond);report,_=self.run_round(client)
        self.assertEqual(report['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        self.assertFalse(report['resume']['permitted']);self.assertIsNone(report['resume']['next_gate'])
        self.assertEqual(client.calls,2)
        resumed=Client();again,_=self.run_round(resumed,True)
        self.assertEqual(again,report);self.assertEqual(resumed.calls,0)

    def test_shape_exhaustion_is_artifact_invalid_without_a_synthetic_candidate(self):
        client=Client(lambda packet:b'{}');report,_=self.run_round(client)
        self.assertEqual(report['terminal_state'],'HALTED_ARTIFACT_INVALID')
        self.assertIn('shape_invalid',report['resume']['reason'])
        self.assertFalse(report['resume']['permitted']);self.assertIsNone(report['latest_candidate']['candidate_id'])
        self.assertEqual(client.calls,2)

    def test_explicit_recovery_after_decision_interruption_does_not_reinvoke_editor(self):
        with patch.object(self.store,'replace_pointer',side_effect=OSError('scripted pre-commit failure')):
            with self.assertRaises(OSError):self.run_round()
        self.assertEqual(self.client.calls,1)
        resumed=Client();report,_=self.run_round(resumed,True)
        self.assertEqual(report['resume']['reason'],'vnext_gate_unavailable');self.assertEqual(resumed.calls,0)

    def test_lost_commit_acknowledgement_allows_only_missing_terminal_materialization(self):
        original=self.store._tree.write
        def lost(path,raw,**kwargs):
            result=original(path,raw,**kwargs)
            if path.endswith('/candidate_verification_current.json'):
                raise StorageWriteError(Publication('outcome_requires_reconciliation',path,result.hash),'scripted lost acknowledgement')
            return result
        with patch.object(self.store._tree,'write',side_effect=lost):
            with self.assertRaises(StorageWriteError):self.run_round()
        before=list(self.store._tree.root.rglob('candidate_verification-attempt-*.json'))
        resumed=Client();report,_=self.run_round(resumed,True)
        self.assertEqual(report['resume']['reason'],'vnext_gate_unavailable');self.assertEqual(resumed.calls,0)
        self.assertEqual(list(self.store._tree.root.rglob('candidate_verification-attempt-*.json')),before)
        with self.assertRaisesRegex(ValueError,'no implemented incomplete gate'):self.run_round(resumed,True)

    def add_round(self,number):
        f=self.f.f;feedback=deepcopy(f.feedback);feedback['round_number']=number
        feedback['feedback'][0]['claim']+=f' Additional fictional clarification {number}.'
        canonicalize_reviewer_input(feedback)
        feedback_ref=self.f.save_input(f'inputs/feedback-{number}.json',feedback)
        advice={**deepcopy(f.advice),'feedback':feedback_ref}
        advice_ref=self.f.save_input(f'inputs/advice-{number}.json',advice)
        record={**deepcopy(self.f.record),'round_number':number,'feedback':feedback_ref,'advice':advice_ref}
        reference=self.f.save_input(f'inputs/round-{number}.json',record)
        refs={**self.admission._refs['rounds'],number:reference}
        self.admission=self.f.make_admission(round_refs=refs)

    def test_terminal_selects_creation_ordinal_and_retains_earlier_rejections(self):
        first,_=self.run_round(self.failing_client());first_id=first['latest_candidate']['candidate_id']
        self.add_round(2)
        second,_=run_proposal_round(self.store,admission=self.admission,round_number=2,client=Client(),
            decided_at='2000-01-01T00:00:00Z')
        self.assertEqual(second['latest_candidate']['candidate_creation_ordinal'],2)
        self.assertNotEqual(second['latest_candidate']['candidate_id'],first_id)
        self.assertEqual(second['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(second['rejected_candidate_ids'],[first_id])

    def test_assembly_failure_keeps_prior_registered_candidate_latest(self):
        first,_=self.run_round();self.add_round(2)
        def invalid(packet):
            content='Queue always waits.';packet['payloads'][0]['content']=content
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        second,_=run_proposal_round(self.store,admission=self.admission,round_number=2,client=Client(invalid),decided_at=STAMP)
        self.assertEqual(second['latest_candidate'],first['latest_candidate'])
        self.assertEqual(second['resume']['reason'],'vnext_assembly_invalid')
        self.assertEqual(len(self.registry().inspect().events),1)

    def test_real_ambiguous_section_map_retains_failure_without_fabricated_candidate(self):
        f=self.f.f
        f.base=b'# Queue\n\n## Timing\nWait.\n### Detail\nSame.\n### Detail\nSame.\n## Reports\nReport.\n'
        f.rebind()
        self.f.record.update(job_id=f.job['job_id'],base_pointer=f.pointer_ref,feedback=f.feedback_ref,advice=f.advice_ref)
        self.f.record_ref=f.save(self.f.record_ref['path'],self.f.record)
        self.store,self.admission=self.f.staged(self.store._tree.root.with_name('ambiguous-store'))
        self.addCleanup(self.store.close)
        def ambiguous(packet):
            content='## Timing\nWait.\n### Detail\nChanged.\n### Detail\nChanged.\n'
            packet['payloads'][0]['content']=content;op=packet['patch']['operations'][0]
            op.update(operation_type='replace_section_subtree');op['payload']['hash']=sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        client=Client(ambiguous);result=self.request(client);self.assertEqual(result.status,'complete')
        report,ref=self.finish();self.assertEqual(report['resume']['reason'],'vnext_assembly_invalid')
        self.assertTrue(all(value is None for value in report['latest_candidate'].values()))
        self.assertEqual(self.registry().inspect().events,())
        path=f"rounds/round-1/proposals/{result.proposal.patch['proposal_id']}/assembly_failure.json"
        evidence=self.json(path);self.assertEqual(evidence['stage'],'section_map')
        self.assertIn('ambiguous descendant',evidence['message'])
        self.assertFalse(list(self.store._tree.root.rglob('candidate_verification*')))
        self.assertFalse(list(self.store._tree.root.rglob('candidate_unverified.md')))
        self.assertEqual(self.finish()[0],report);self.assertEqual(client.calls,1)
