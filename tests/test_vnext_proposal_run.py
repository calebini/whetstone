from copy import deepcopy
from pathlib import Path
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,decode_json
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_proposal_admission import initialize_proposal_storage
from whetstone.vnext_proposal_run import RUN_INPUT_PATH,open_proposal_run,round_input_path
from test_vnext_proposal_requests import Client
import test_vnext_proposal_admission as fixtures
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class StoredProposalRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ProposalAdmissionTests.setUpClass()
    def setUp(self):
        self.f=fixtures.ProposalAdmissionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root.with_name('stored-proposal-run')
        store,_=self.f.staged(self.root);store.close()
        self.run=self.open();self.addCleanup(self.run.close)
    def open(self):return open_proposal_run(self.root,suite_path=self.f.path)
    def invoke(self,client=None,continuation=False):return self.run.run_round(round_number=1,client=client or Client(),decided_at=STAMP,continuation=continuation)
    def files(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_reopened_root_derives_inputs_and_runs_without_caller_selectors(self):
        before=self.files();status=self.run.status(round_number=1)
        self.assertEqual((status['processing_gate'],status['request_status']),('proposal','not_started'))
        self.assertFalse(status['resume']['permitted']);self.assertEqual(before,self.files())
        client=Client();report,_=self.invoke(client);self.assertEqual(client.calls,1)
        self.assertTrue((self.root/round_input_path(1)).is_file())
        self.run.close();self.run=self.open();self.addCleanup(self.run.close)
        self.assertEqual(self.run.status(round_number=1)['terminal_report'],report)
        replay=Client();self.assertEqual(self.invoke(replay)[0],report);self.assertEqual(replay.calls,0)
        with self.assertRaisesRegex(ValueError,'not technically resumable'):self.invoke(replay,True)
        self.assertEqual(replay.calls,0)

    def test_status_and_reopen_are_read_only_while_an_owner_is_active(self):
        other=LocalAuthorityStore(self.root,job_id=self.f.f.job['job_id']);self.addCleanup(other.close)
        before=self.files()
        with other.locked(self.run.validate_authority):
            with self.open() as reader:self.assertEqual(reader.status(round_number=1)['request_status'],'not_started')
        self.assertEqual(before,self.files())

    def test_immutable_run_selector_changes_refuse_without_clients(self):
        path=self.root/RUN_INPUT_PATH;packet=decode_json(path.read_bytes())
        packet['review_configuration']['hash']='f'*64;path.write_bytes(canonical_json_bytes(packet))
        client=Client()
        with self.assertRaisesRegex(ValueError,'selectors changed'):self.invoke(client)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.open()
        self.assertEqual(client.calls,0)

    def test_duplicate_staged_selectors_cannot_choose_a_round(self):
        path=self.root/RUN_INPUT_PATH;packet=decode_json(path.read_bytes());packet['staged_rounds']*=2
        path.write_bytes(canonical_json_bytes(packet))
        with self.assertRaisesRegex(ValueError,'sorted and unique'):self.open()

    def test_round_admission_rejects_conflicting_staged_record_before_publication(self):
        packet=deepcopy(self.f.record);packet['constraints']['max_operations']+=1
        before=self.files()
        with self.assertRaisesRegex(ValueError,'contradicts its staged selector'):self.run.admit_round(packet)
        self.assertEqual(before,self.files())

    def test_unbound_input_record_is_not_treated_as_an_admitted_round(self):
        status=self.run.status(round_number=2)
        self.assertEqual(status['processing_gate'],'review');self.assertEqual(status['request_status'],'not_admitted')
        self.assertFalse(status['resume']['permitted']);self.assertIsNone(status['resume']['next_gate'])
        client=Client()
        with self.assertRaisesRegex(ValueError,'no admitted input record'):
            self.run.run_round(round_number=2,client=client,decided_at=STAMP)
        self.assertEqual(client.calls,0)

    def test_missing_terminal_materialization_is_resumable_without_another_client_call(self):
        original=self.run.store.publish
        def fail(token,path,value):
            if path.startswith('rounds/terminal_reports/'):raise OSError('scripted missing terminal write')
            return original(token,path,value)
        client=Client()
        with patch.object(self.run.store,'publish',side_effect=fail):
            with self.assertRaises(OSError):self.invoke(client)
        before=self.files();status=self.run.status(round_number=1)
        self.assertEqual(status['processing_gate'],'materialization');self.assertTrue(status['resume']['permitted'])
        self.assertEqual(status['terminal_materialization'],'missing');self.assertEqual(before,self.files())
        self.run.close();self.run=self.open();self.addCleanup(self.run.close)
        resumed=Client();self.invoke(resumed,True);self.assertEqual(resumed.calls,0)
        final=self.run.status(round_number=1)
        self.assertEqual(final['processing_gate'],'semantic_verification');self.assertFalse(final['resume']['permitted'])
        self.assertIsNone(final['resume']['next_gate']);self.assertEqual(final['terminal_materialization'],'present')

    def test_prepared_verification_is_resumable_without_claiming_a_decision(self):
        with patch.object(self.run.store,'replace_pointer',side_effect=OSError('scripted pointer stop')):
            with self.assertRaises(OSError):self.invoke()
        status=self.run.status(round_number=1)
        self.assertEqual(status['processing_gate'],'verification_commit');self.assertTrue(status['resume']['permitted'])
        self.assertIsNone(status['terminal_report']['latest_candidate']['verification_decision_path'])
        before=self.files();implicit=Client()
        with self.assertRaisesRegex(ValueError,'requires explicit continuation'):self.invoke(implicit)
        self.assertEqual(before,self.files());self.assertEqual(implicit.calls,0)
        resumed=Client();self.invoke(resumed,True);self.assertEqual(resumed.calls,0)

    def test_timeout_eligibility_survives_reopening_and_exhaustion_keeps_cause(self):
        def timeout(packet):raise TimeoutError('fictional timeout')
        first=Client(timeout);self.invoke(first)
        self.run.close();self.run=self.open();self.addCleanup(self.run.close)
        status=self.run.status(round_number=1)
        self.assertEqual(status['terminal_report']['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        self.assertEqual(status['resume']['next_gate'],'proposal')
        second=Client(timeout);self.invoke(second,True)
        status=self.run.status(round_number=1)
        self.assertFalse(status['resume']['permitted']);self.assertIn('fictional timeout',status['resume']['reason'])
        self.assertEqual((first.calls,second.calls),(1,1))

    def test_damaged_committed_pointer_is_not_hidden_by_unselected_future_round(self):
        report,_=self.invoke();decision_path=report['latest_candidate']['verification_decision_path']
        pointer=self.root/Path(decision_path).parent/'candidate_verification_current.json'
        packet=decode_json(pointer.read_bytes());packet['current_decision_hash']='f'*64
        pointer.write_bytes(canonical_json_bytes(packet))
        for number in (1,99):
            with self.subTest(number=number),self.assertRaises(ValueError):self.run.status(round_number=number)

    def test_seed_only_initialization_can_admit_feedback_later(self):
        f=self.f.f
        omitted={f.feedback_ref['path'],f.advice_ref['path'],self.f.record_ref['path']}
        artifacts={p.relative_to(f.root).as_posix():p.read_bytes() for p in f.root.rglob('*')
                   if p.is_file() and p.relative_to(f.root).as_posix() not in omitted}
        root=self.root.with_name('before-review')
        store,_=initialize_proposal_storage(root,artifacts=artifacts,suite_path=self.f.path,descriptor_ref=f.job_ref,
            review_ref=f.original.review_ref,seed_map_ref=f.map_ref,round_refs={})
        store.close()
        with open_proposal_run(root,suite_path=self.f.path) as run:
            self.assertEqual(run.status(round_number=1)['processing_gate'],'review')
            with run.store.locked(run.validate_authority) as token:
                for reference in (f.feedback_ref,f.advice_ref):
                    run.store.publish(token,reference['path'],(f.root/reference['path']).read_bytes())
            run.admit_round(self.f.record)
            report,_=run.run_round(round_number=1,client=Client(),decided_at=STAMP)
            self.assertEqual(report['resume']['reason'],'vnext_gate_unavailable')
        self.assertFalse((root/self.f.record_ref['path']).exists())

    def test_noncanonical_seed_and_invalid_review_policy_refuse_before_root_creation(self):
        f=self.f.f
        for name,update in [('seed',None),('profiles',[]),('workflow','unsupported'),('mvp','mvp')]:
            old_base=f.base;old_review=deepcopy(f.original.review)
            if name=='seed':f.base+=b'\n\n'
            elif name=='profiles':f.original.review['profiles']=update
            else:f.original.review['workflow']=update
            f.original.review_ref=f.save(f.original.review_ref['path'],f.original.review)
            f.job['review_configuration_hash']=f.original.review_ref['hash'];f.rebind()
            artifacts={p.relative_to(f.root).as_posix():p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
            destination=self.root.with_name('bad-'+name)
            with self.subTest(name=name),self.assertRaises(ValueError):
                initialize_proposal_storage(destination,artifacts=artifacts,suite_path=self.f.path,descriptor_ref=f.job_ref,
                    review_ref=f.original.review_ref,seed_map_ref=f.map_ref,round_refs={})
            self.assertFalse(destination.exists())
            f.base=old_base;f.original.review=old_review

    def test_fresh_process_reopens_and_replays_without_a_new_editor_call(self):
        self.invoke();self.run.close()
        from whetstone import vnext_registry
        version=self.f.suite.version;digest=self.f.suite.digest
        algorithms=deepcopy(vnext_registry.SUITE_ALGORITHM_VERSIONS[version])
        script=f'''
import json, sys
sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
from whetstone import vnext_registry
from whetstone.vnext_proposal_run import open_proposal_run
from test_vnext_proposal_requests import Client
vnext_registry.SUPPORTED_SUITES[{version!r}]={digest!r}
vnext_registry.SUITE_ALGORITHM_VERSIONS[{version!r}]={algorithms!r}
with open_proposal_run({str(self.root)!r},suite_path={str(self.f.path)!r}) as run:
    client=Client()
    report,_=run.run_round(round_number=1,client=client,decided_at={STAMP!r})
    print(json.dumps(dict(calls=client.calls,reason=report['resume']['reason'],status=run.status(round_number=1))))
'''
        completed=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=60)
        self.assertEqual(completed.returncode,0,completed.stderr)
        packet=json.loads(completed.stdout)
        self.assertEqual(packet['calls'],0);self.assertEqual(packet['reason'],'vnext_gate_unavailable')
        self.assertEqual(packet['status']['terminal_materialization'],'present')
