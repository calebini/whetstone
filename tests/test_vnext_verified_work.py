import json
import select
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_local_storage import OwnershipLost, StorageBusy
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_work import VerifiedWork
from vnext_fixtures import STAMP
import test_vnext_verified_history as history
import test_vnext_verified_promotion as promotion


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedWorkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): history.VerifiedHistoryTests.setUpClass()

    files = promotion.VerifiedPromotionTests.files
    owner = promotion.VerifiedPromotionTests.owner
    ready = promotion.VerifiedPromotionTests.ready
    run_request = promotion.VerifiedPromotionTests.run_request
    verified = promotion.VerifiedPromotionTests.verified
    materialize_seed = promotion.VerifiedPromotionTests.materialize_seed
    stop_after_intent = promotion.VerifiedPromotionTests.stop_after_intent
    service = promotion.VerifiedPromotionTests.service
    later_candidate = promotion.VerifiedPromotionTests.later_candidate
    followup_fixture = history.VerifiedHistoryTests.followup_fixture

    def fixture(self, *, register_candidate=True, work_contract=True):
        algorithms = ('vnext_verified_materialization_v1', 'vnext_verified_promotion_v1')
        if work_contract: algorithms += ('vnext_verified_work_v1',)
        return history.VerifiedHistoryTests.fixture(self, extra_algorithms=algorithms,
                                                    register_candidate=register_candidate)

    def work(self, f): return VerifiedWork(f.store, history=self.owner(f))

    def fresh_registered(self, editor_callback=None):
        f = self.fixture(register_candidate=False)
        if editor_callback is not None: f.editor = history.verified.fixtures.Client(editor_callback)
        work = self.work(f)
        self.assertEqual(work.request(round_number=1, client=f.editor).outcome, 'materialization_recovered')
        self.assertEqual(f.editor.calls, 0)
        result = work.request(round_number=1, client=f.editor)
        self.assertEqual(result.value.status, 'complete')
        f.creation = work.register(round_number=1, created_at=STAMP).value
        f.identifier = f.creation['candidate_id']
        return f

    def verifier(self, f):
        context = load_registered_semantic_context(f.store, admission=self.owner(f), candidate_id=f.identifier)
        return history.verified.semantic.Client(context)

    def test_live_owner_drives_seed_editor_registration_verifier_and_promotion(self):
        f = self.fresh_registered()
        work = self.work(f)
        before = self.files(f)
        self.assertEqual(work.request(round_number=1, client=f.editor).outcome, 'candidate_registered')
        self.assertEqual(self.files(f), before)
        verifier = self.verifier(f)
        result = work.verify(client=verifier, decided_at=STAMP)
        self.assertEqual(result.outcome, 'candidate_final')
        self.assertTrue(result.value.decision['promotion_permitted'])
        self.assertEqual(result.current_pointer['promotion_ordinal'], 0)
        before = self.files(f)
        self.assertEqual(work.inspect().outcome, 'promotion_required')
        self.assertEqual(work.verify(client=verifier, decided_at=STAMP).outcome, 'promotion_required')
        self.assertEqual(self.files(f), before)
        result = self.service(f).promote(prepared_at=STAMP)
        self.assertEqual(result.current_pointer['promotion_ordinal'], 1)
        self.assertEqual(f.store.read('spec.md'), f.store.read(f.creation['candidate_path']))
        self.assertEqual((f.editor.calls, verifier.calls), (1, 1))
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'exact current base pointer'):
            work.request(round_number=1, client=f.editor)
        self.assertEqual(self.files(f), before)

    def test_materialization_precedes_malformed_later_candidate_and_next_intent(self):
        f = self.fixture(register_candidate=False)
        (f.root / 'rounds/candidate_index').mkdir(parents=True, exist_ok=True)
        (f.root / 'rounds/candidate_index/creation-1.json').write_bytes(b'not json')
        future = f.root / 'rounds/verified_history/current-verified-1.json'
        future.write_bytes(b'not json')
        work = self.work(f)
        before = self.files(f)
        self.assertEqual(work.inspect().outcome, 'materialization_required')
        self.assertEqual(self.files(f), before)
        self.assertEqual(work.request(round_number=1, client=f.editor).outcome, 'materialization_recovered')
        self.assertEqual(f.editor.calls, 0)
        self.assertEqual(future.read_bytes(), b'not json')
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'], 0)

    def test_reserved_claimant_blocks_editor_and_verifier_after_later_registration(self):
        f = self.verified()
        self.materialize_seed(f)
        first = f.identifier
        self.stop_after_intent(f)
        self.later_candidate(f, reject=True)
        work = self.work(f)
        before = self.files(f)
        for result in (work.request(round_number=2, client=f.editor), work.verify(decided_at=STAMP)):
            self.assertEqual(result.outcome, 'promotion_required')
            self.assertEqual(result.promotion_candidate['candidate_id'], first)
            self.assertEqual(result.latest_candidate['candidate_id'], f.identifier)
        self.assertEqual(self.files(f), before)

    def test_own_contract_and_competing_fence_refuse_before_calls_or_writes(self):
        f = self.fixture(register_candidate=False, work_contract=False)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'verified work algorithm is outside supported suite'):
            self.work(f).request(round_number=1, client=f.editor)
        self.assertEqual(self.files(f), before)
        g = self.fixture(register_candidate=False)
        before = self.files(g)
        with g.store.locked(self.owner(g).validate_authority):
            with self.assertRaises(StorageBusy): self.work(g).request(round_number=1, client=g.editor)
        self.assertEqual(self.files(g), before)
        self.assertEqual((f.editor.calls, g.editor.calls), (0, 0))

    def test_borrowed_fence_does_not_survive_operation_or_ownership_loss(self):
        f = self.fixture(register_candidate=False)
        self.materialize_seed(f)
        captured = []
        def capture(store, proof):
            captured.append(store)
            return store.read('rounds/current_verified.json')
        self.work(f)._execute(capture)
        with self.assertRaises(OwnershipLost): captured[0].read('rounds/current_verified.json')
        before = self.files(f)
        original = f.editor.propose
        def lose_fence(prompt):
            result = original(prompt)
            f.store._invalidate()
            return result
        with patch.object(f.editor, 'propose', side_effect=lose_fence):
            with self.assertRaises(OwnershipLost): self.work(f).request(round_number=1, client=f.editor)
        self.assertEqual(f.store.read('rounds/current_verified.json'), before['rounds/current_verified.json'])
        self.assertFalse(list(f.root.rglob('response.json')))

    def test_live_owner_repeats_complete_journey_on_promoted_base(self):
        f = self.fresh_registered()
        first_id = f.identifier
        verifier = self.verifier(f)
        self.work(f).verify(client=verifier, decided_at=STAMP)
        first = self.service(f).promote(prepared_at=STAMP).current_pointer
        first_source = self.files(f)
        self.later_candidate(f, prepare_only=True)
        work = self.work(f)
        self.assertEqual(work.request(round_number=2, client=f.editor).value.status, 'complete')
        f.creation = work.register(round_number=2, created_at=STAMP).value
        f.identifier = f.creation['candidate_id']
        self.assertNotEqual(f.identifier, first_id)
        second_verifier = self.verifier(f)
        result = work.verify(client=second_verifier, decided_at=STAMP)
        self.assertEqual(result.outcome, 'candidate_final')
        self.assertEqual(result.value.decision['base_draft_hash'], first['verified_draft_hash'])
        second = self.service(f).promote(prepared_at=STAMP).current_pointer
        self.assertEqual(second['promotion_ordinal'], 2)
        self.assertEqual(second['previous_verified_draft_hash'], first['verified_draft_hash'])
        for path, raw in first_source.items():
            if path not in {'rounds/current_verified.json', 'spec.md', 'rounds/run_state.json'}:
                self.assertEqual(f.store.read(path), raw, path)
        self.assertEqual((f.editor.calls, verifier.calls, second_verifier.calls), (1, 1, 1))

    def test_registration_orphan_recovers_separately_without_another_editor(self):
        f = self.fixture(register_candidate=False)
        self.materialize_seed(f)
        work = self.work(f)
        self.assertEqual(work.request(round_number=1, client=f.editor).value.status, 'complete')
        publish = f.store.publish
        def stop(token, path, value):
            if path == 'rounds/candidate_index/creation-1.json': raise OSError('before registration commit')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'before registration commit'):
                work.register(round_number=1, created_at=STAMP)
        before = self.files(f)
        self.assertEqual(work.inspect().outcome, 'registration_recovery_required')
        self.assertEqual(work.request(round_number=1, client=f.editor).outcome, 'registration_recovery_required')
        self.assertEqual(work.verify(decided_at=STAMP).outcome, 'registration_recovery_required')
        self.assertEqual(self.files(f), before)
        result = work.recover_registration()
        self.assertEqual(result.outcome, 'registration_recovered')
        self.assertEqual(result.latest_candidate['candidate_creation_ordinal'], 1)
        self.assertFalse(result.value.orphans)
        self.assertFalse(list(f.root.rglob('candidate_verification_current.json')))
        self.assertEqual(f.editor.calls, 1)

    def test_prepared_verification_recovers_without_starting_verifier(self):
        for suffix in ('candidate_verification-attempt-1.json', 'candidate_verification_pointer-attempt-2.json'):
            with self.subTest(suffix=suffix):
                f = self.fresh_registered()
                verifier = self.verifier(f)
                work = self.work(f)
                publish = f.store.publish
                def stop(token, path, value):
                    result = publish(token, path, value)
                    if path.endswith(suffix): raise OSError('prepared decision')
                    return result
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'prepared decision'):
                        work.verify(client=verifier, decided_at=STAMP)
                calls = verifier.calls
                before = self.files(f)
                self.assertEqual(work.verify(client=verifier, decided_at=STAMP).outcome, 'continuation_required')
                self.assertEqual(self.files(f), before)
                result = work.verify(client=verifier, decided_at='2031-01-01T00:00:00Z', continuation=True)
                self.assertEqual(result.outcome, 'verification_recovered')
                self.assertEqual(result.value.decision['decided_at'], STAMP)
                self.assertEqual(verifier.calls, calls)
                self.assertEqual(result.current_pointer['promotion_ordinal'], 0)

    def test_verifier_timeout_requires_explicit_continuation_and_keeps_slot_budget(self):
        f = self.fresh_registered()
        verifier = self.verifier(f)
        verifier.responses = [TimeoutError('scripted timeout')]
        work = self.work(f)
        result = work.verify(client=verifier, decided_at=STAMP)
        self.assertEqual(result.outcome, 'semantic_result')
        self.assertEqual(result.value.status, 'timeout')
        before = self.files(f)
        self.assertEqual(work.verify(client=verifier, decided_at=STAMP).outcome, 'continuation_required')
        self.assertEqual(self.files(f), before)
        self.assertEqual(verifier.calls, 1)
        result = work.verify(client=verifier, decided_at=STAMP, continuation=True)
        self.assertEqual(result.outcome, 'candidate_final')
        self.assertTrue(result.value.decision['promotion_permitted'])
        self.assertEqual(verifier.calls, 2)

    def test_live_same_round_followup_uses_exact_selection_and_preserves_rejected_parent(self):
        f, parent_id, reference = self.followup_fixture()
        self.materialize_seed(f)
        before = self.files(f)
        parent_calls = f.editor.calls, f.client.calls
        f.editor = history.verified.fixtures.Client()
        work = self.work(f)
        self.assertEqual(work.request(round_number=1, client=f.editor).outcome, 'candidate_registered')
        self.assertEqual(f.editor.calls, 0)
        self.assertEqual(self.files(f), before)
        result = work.request(round_number=1, client=f.editor, selected_ref=reference)
        self.assertEqual(result.value.status, 'complete')
        f.creation = work.register(round_number=1, created_at=STAMP, selected_ref=reference).value
        f.identifier = f.creation['candidate_id']
        self.assertNotEqual(f.identifier, parent_id)
        current = self.files(f)
        with self.assertRaisesRegex(ValueError, 'superseded by a later candidate'):
            work.request(round_number=1, client=f.editor)
        self.assertEqual(self.files(f), current)
        verifier = self.verifier(f)
        result = work.verify(client=verifier, decided_at=STAMP)
        self.assertTrue(result.value.decision['promotion_permitted'])
        result = self.service(f).promote(prepared_at=STAMP)
        self.assertEqual(result.candidate_id, f.identifier)
        self.assertEqual(result.current_pointer['promotion_ordinal'], 1)
        for path, raw in before.items():
            if path not in {'rounds/current_verified.json', 'spec.md', 'rounds/run_state.json'}:
                self.assertEqual(f.store.read(path), raw, path)
        self.assertEqual(parent_calls, (1, 1))
        self.assertEqual((f.editor.calls, verifier.calls), (1, 1))

    def test_unfinished_latest_candidate_blocks_new_transaction_and_deterministic_reject_skips_verifier(self):
        f = self.fresh_registered()
        self.later_candidate(f, prepare_only=True)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'latest candidate must finish'):
            self.work(f).request(round_number=2, client=f.editor)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.editor.calls, 0)

        from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
        def weaken(packet):
            content = 'Queue sometimes waits.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        g = self.fresh_registered(weaken)
        result = self.work(g).verify(decided_at=STAMP)
        self.assertEqual(result.outcome, 'candidate_final')
        self.assertEqual(result.value.decision['deterministic_result'], 'fail')
        self.assertEqual(result.value.decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        self.assertFalse(result.value.decision['promotion_permitted'])
        before = self.files(g)
        with self.assertRaisesRegex(ValueError, 'final candidate cannot resume'):
            self.work(g).verify(decided_at=STAMP, continuation=True)
        self.assertEqual(self.files(g), before)
        requests = [json.loads(path.read_bytes()) for path in g.root.glob('rounds/client_requests/*/request.json')]
        self.assertEqual([packet['role'] for packet in requests], ['editor'])

    def test_real_process_holds_fence_through_editor_and_death_requires_continuation(self):
        f = self.fixture(register_candidate=False)
        self.materialize_seed(f)
        refs = f.admission._refs
        packet = dict(root=str(f.root), suite_path=str(f.admission.suite_path), selectors=dict(
            descriptor_ref=refs['descriptor'], review_ref=refs['review'], seed_map_ref=refs['seed_map'], round_refs=refs['rounds']))
        script = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_history import VerifiedHistoryAdmission
from whetstone.vnext_verified_work import VerifiedWork
from test_vnext_proposal_admission import Client
packet=json.loads(sys.argv[1]);root=Path(packet['root'])
manifest=json.loads(Path(packet['suite_path']).read_bytes())
job=json.loads((root/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={key:job[key] for key in ALGORITHM_VERSIONS}
selectors=packet['selectors'];selectors['round_refs']={int(key):value for key,value in selectors['round_refs'].items()}
with LocalAuthorityStore(root,job_id=job['job_id']) as store:
    owner=VerifiedHistoryAdmission(store,suite_path=packet['suite_path'],**selectors)
    client=Client();original=client.propose
    def pause(prompt):
        response=original(prompt)
        print('holding',flush=True)
        sys.stdin.readline()
        return response
    client.propose=pause
    VerifiedWork(store,history=owner).request(round_number=1,client=client)
'''
        child = subprocess.Popen([sys.executable, '-u', '-c', script, json.dumps(packet)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if child.poll() is None: child.kill()
            child.communicate(timeout=5)
        self.addCleanup(cleanup)
        readable, _, _ = select.select([child.stdout], [], [], 60)
        self.assertTrue(readable, 'live Editor child did not reach its invocation')
        line = child.stdout.readline()
        self.assertEqual(line, b'holding\n', child.stderr.read() if child.poll() is not None else line)
        before = self.files(f)
        work = self.work(f)
        self.assertEqual(work.inspect().outcome, 'work_available')
        with self.assertRaises(StorageBusy): work.request(round_number=1, client=f.editor)
        self.assertEqual(self.files(f), before)
        child.kill()
        child.communicate(timeout=10)
        self.assertEqual(work.request(round_number=1, client=f.editor).outcome, 'continuation_required')
        self.assertEqual(f.editor.calls, 0)
        result = work.request(round_number=1, client=f.editor, continuation=True)
        self.assertEqual(result.value.status, 'complete')
        self.assertEqual(result.value.attempts, 2)
        self.assertEqual(f.editor.calls, 1)
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'], 0)

    def test_retained_editor_and_verifier_output_recovers_without_a_client(self):
        for role in ('editor', 'verifier'):
            with self.subTest(role=role):
                f = self.fixture(register_candidate=False) if role == 'editor' else self.fresh_registered()
                self.materialize_seed(f)
                work = self.work(f)
                client = f.editor if role == 'editor' else self.verifier(f)
                def run(client=None, continuation=False):
                    if role == 'editor':
                        return work.request(round_number=1, client=client, continuation=continuation)
                    return work.verify(client=client, decided_at=STAMP, continuation=continuation)
                publish = f.store.publish
                def stop(token, path, value):
                    result = publish(token, path, value)
                    if path.endswith('/attempts/1/response.json'): raise OSError('retained raw output')
                    return result
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'retained raw output'): run(client)
                before = self.files(f)
                self.assertEqual(run().outcome, 'continuation_required')
                self.assertEqual(self.files(f), before)
                result = run(continuation=True)
                self.assertEqual(result.outcome, 'proposal_result' if role == 'editor' else 'candidate_final')
                self.assertEqual(client.calls, 1)
                if role == 'editor': self.assertEqual(result.value.status, 'complete')
                else: self.assertTrue(result.value.decision['promotion_permitted'])

    def test_changed_bound_authority_during_editor_cannot_commit_a_result(self):
        f = self.fixture(register_candidate=False)
        self.materialize_seed(f)
        job = json.loads(f.store.read_descriptor())
        authority = f.root / job['authority_map_path']
        head = f.store.read('rounds/current_verified.json')
        original = f.editor.propose
        def change_source(prompt):
            response = original(prompt)
            authority.write_bytes(authority.read_bytes() + b' ')
            return response
        with patch.object(f.editor, 'propose', side_effect=change_source):
            with self.assertRaises(ValueError): self.work(f).request(round_number=1, client=f.editor)
        self.assertEqual(f.editor.calls, 1)
        self.assertFalse(list(f.root.rglob('proposal_result.json')))
        self.assertFalse(list(f.root.rglob('creation-*.json')))
        self.assertEqual(f.store.read('rounds/current_verified.json'), head)

    def test_promoted_inventory_drift_during_editor_cannot_hide_in_proven_base(self):
        f = self.fresh_registered()
        self.work(f).verify(client=self.verifier(f), decided_at=STAMP)
        current = self.service(f).promote(prepared_at=STAMP).current_pointer
        inventory = f.root / current['verified_draft_path'].rsplit('/', 1)[0] / 'preservation_inventory_candidate.json'
        self.later_candidate(f, prepare_only=True)
        before = self.files(f)
        results_before = set(f.root.glob('rounds/client_requests/*/proposal_result.json'))
        original = f.editor.propose
        def change_source(prompt):
            response = original(prompt)
            inventory.write_bytes(inventory.read_bytes() + b' ')
            return response
        with patch.object(f.editor, 'propose', side_effect=change_source):
            with self.assertRaises(ValueError): self.work(f).request(round_number=2, client=f.editor)
        self.assertEqual(f.editor.calls, 1)
        self.assertEqual(set(f.root.glob('rounds/client_requests/*/proposal_result.json')), results_before)
        self.assertFalse((f.root / 'rounds/candidate_index/creation-2.json').exists())
        self.assertEqual(f.store.read('rounds/current_verified.json'), before['rounds/current_verified.json'])


if __name__ == '__main__': unittest.main()
