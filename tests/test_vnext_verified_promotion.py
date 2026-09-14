import json
import select
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone.clients import canonicalize_reviewer_input
from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import OwnershipLost, Publication, StorageBusy, StorageWriteError
from whetstone.vnext_proposal_handoff import register_completed_proposal_request, registry_for_proposal_requests
from whetstone.vnext_proposal_requests import run_proposal_request
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_history import VerifiedHistoryAdmission
from whetstone.vnext_verified_materialization import VerifiedMaterialization
from whetstone.vnext_verified_promotion import VerifiedPromotion
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal
from vnext_fixtures import STAMP
import test_vnext_verified_history as history


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedPromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): history.VerifiedHistoryTests.setUpClass()

    files = history.VerifiedHistoryTests.files
    owner = history.VerifiedHistoryTests.owner
    ready = history.VerifiedHistoryTests.ready
    run_request = history.VerifiedHistoryTests.run_request
    prepared_tail = history.VerifiedHistoryTests.prepared_tail
    promoted = history.VerifiedHistoryTests.promoted
    followup_fixture = history.VerifiedHistoryTests.followup_fixture

    def fixture(self, *, contract=True, register_candidate=True):
        algorithms = ('vnext_verified_materialization_v1',)
        if contract: algorithms += ('vnext_verified_promotion_v1',)
        return history.VerifiedHistoryTests.fixture(self, extra_algorithms=algorithms, register_candidate=register_candidate)

    def service(self, f): return VerifiedPromotion(f.store, history=self.owner(f))

    def promote_fixture(self, f, final):
        # The shared historical journeys now use the production pointer owner;
        # their current-round/answer admission remains explicit fixture setup.
        service = self.service(f)
        if service.inspect().outcome == 'materialization_required':
            self.assertEqual(service.promote(prepared_at=STAMP).outcome, 'materialization_recovered')
        result = service.promote(prepared_at=STAMP)
        self.assertEqual(result.outcome, 'promoted')
        self.assertEqual(result.candidate_id, f.identifier)
        return result.current_pointer

    def verified(self):
        f = self.ready()
        self.run_request(f)
        f.final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        return f

    def materialize_seed(self, f):
        VerifiedMaterialization(f.store, history=self.owner(f)).repair()

    def stop_after_intent(self, f):
        publish = f.store.publish
        def stop(token, path, value):
            result = publish(token, path, value)
            if '/promotion_intents/' in path: raise OSError('prepared intent')
            return result
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'prepared intent'): self.service(f).promote(prepared_at=STAMP)

    def later_candidate(self, f, *, reject=False, prepare_only=False):
        owner = self.owner(f)
        current = owner.inspect().pointers[-1]
        source = json.loads(f.store.read(f.admission._refs['rounds'][1]['path']))
        feedback = json.loads(f.store.read(source['feedback']['path']))
        feedback.update(round_number=2, draft_hash=current['verified_draft_hash'])
        feedback['feedback'][0]['claim'] = 'The waiting behavior needs a second precise explanation.'
        feedback = canonicalize_reviewer_input(feedback)
        feedback_path = 'inputs/promotion-feedback-2.json'
        feedback_ref = {'path': feedback_path, 'hash': sha256_bytes(canonical_json_bytes(feedback))}
        advice = json.loads(f.store.read(source['advice']['path']))
        advice.update(base_draft_hash=current['verified_draft_hash'], feedback=feedback_ref)
        advice_path = 'inputs/promotion-advice-2.json'
        record = {**source, 'round_number': 2, 'feedback': feedback_ref,
            'advice': {'path': advice_path, 'hash': sha256_bytes(canonical_json_bytes(advice))},
            'base_pointer': {'path': f"rounds/verified_history/current-verified-{current['promotion_ordinal']}.json",
                             'hash': sha256_bytes(canonical_json_bytes(current))}}
        record_path = 'inputs/promotion-round-2.json'
        with f.store.locked(owner.validate_authority) as token:
            for path, value in ((feedback_path, feedback), (advice_path, advice), (record_path, record)):
                f.store.publish(token, path, value)
        owner = VerifiedHistoryAdmission(f.store, suite_path=owner.suite_path,
            descriptor_ref=owner._refs['descriptor'], review_ref=owner._refs['review'], seed_map_ref=owner._refs['seed_map'],
            round_refs={**owner._refs['rounds'], 2: {'path': record_path, 'hash': sha256_bytes(canonical_json_bytes(record))}})
        f.admission = history._CurrentRoundFixture(f.store, owner, 2)
        def change(packet):
            content = 'Queue sometimes waits.\n' if reject else 'Queue always waits before processing begins.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        f.editor = history.verified.fixtures.Client(change)
        if prepare_only: return f
        self.assertEqual(run_proposal_request(f.store, load_inputs=lambda read: f.admission.load_inputs(read, 2),
            validate_authority=f.admission.validate_authority, client=f.editor).status, 'complete')
        f.creation = register_completed_proposal_request(f.store, round_number=2,
            load_inputs=f.admission.load_inputs, validate_authority=f.admission.validate_authority, created_at=STAMP)
        f.identifier = f.creation['candidate_id']
        f.registry = registry_for_proposal_requests(f.store, load_inputs=f.admission.load_inputs,
                                                    validate_authority=f.admission.validate_authority)
        f.decisions = VerifiedSemanticDecisionJournal(f.registry, admission=f.admission)
        f.final = f.decisions.commit(f.identifier, decided_at=STAMP)
        if not reject:
            context = load_registered_semantic_context(f.store, admission=f.admission, candidate_id=f.identifier)
            f.client = history.verified.semantic.Client(context)
            self.assertEqual(self.run_request(f).status, 'complete')
            f.final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        return f

    def test_real_writer_recovers_seed_then_promotes_once_without_extra_clients(self):
        f = self.verified()
        service = self.service(f)
        before = self.files(f)
        self.assertEqual(service.inspect().outcome, 'materialization_required')
        self.assertEqual(self.files(f), before)
        first = service.promote(prepared_at=STAMP)
        self.assertEqual(first.outcome, 'materialization_recovered')
        self.assertEqual(first.current_pointer['promotion_ordinal'], 0)
        self.assertFalse(list(f.root.rglob('promotion-intent-*.json')))
        before = self.files(f)
        self.assertEqual(service.inspect().outcome, 'ready')
        self.assertEqual(self.files(f), before)
        promoted = service.promote(prepared_at=STAMP)
        self.assertEqual(promoted.outcome, 'promoted')
        self.assertEqual(promoted.current_pointer['promotion_ordinal'], 1)
        self.assertEqual(promoted.committed_pointer, promoted.current_pointer)
        self.assertEqual(promoted.candidate_id, f.identifier)
        self.assertEqual(f.store.read('spec.md'), f.store.read(f.creation['candidate_path']))
        self.assertEqual(f.store.read('rounds/round-1/draft_after.md'), f.store.read('spec.md'))
        before = self.files(f)
        self.assertEqual(service.promote(prepared_at='2031-01-01T00:00:00Z').outcome, 'not_eligible')
        self.assertEqual(self.files(f), before)
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def test_all_precommit_prefixes_reuse_claimant_and_timestamp(self):
        for suffix in ('promotion-intent-1.json', 'event-4.json', 'current-verified-1.json'):
            for after in (False, True):
                with self.subTest(suffix=suffix, after=after):
                    f = self.verified()
                    self.materialize_seed(f)
                    service = self.service(f)
                    seed = f.store.read('rounds/current_verified.json')
                    publish = f.store.publish
                    def interrupt(token, path, value):
                        if path.endswith(suffix) and not after: raise OSError('before preparation')
                        result = publish(token, path, value)
                        if path.endswith(suffix) and after: raise OSError('after preparation')
                        return result
                    with patch.object(f.store, 'publish', side_effect=interrupt):
                        with self.assertRaises(OSError): service.promote(prepared_at=STAMP)
                    self.assertEqual(f.store.read('rounds/current_verified.json'), seed)
                    had_intent = bool(list(f.root.rglob('promotion-intent-1.json')))
                    before = self.files(f)
                    self.assertIn(service.inspect().outcome, {'ready', 'claimant_prepared'})
                    self.assertEqual(self.files(f), before)
                    result = service.promote(prepared_at='2031-01-01T00:00:00Z')
                    self.assertEqual(result.current_pointer['promotion_ordinal'], 1)
                    self.assertEqual(result.current_pointer['promoted_at'], STAMP if had_intent else '2031-01-01T00:00:00Z')
                    self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def test_reserved_older_claimant_survives_a_later_rejected_registration(self):
        f = self.verified()
        first_id = f.identifier
        self.materialize_seed(f)
        self.stop_after_intent(f)
        self.later_candidate(f, reject=True)
        self.assertEqual(f.final.decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        service = self.service(f)
        self.assertEqual(service.inspect().candidate_id, first_id)
        result = service.promote(prepared_at='2031-01-01T00:00:00Z')
        self.assertEqual(result.candidate_id, first_id)
        self.assertEqual(result.current_pointer['promoted_at'], STAMP)
        self.assertNotEqual(result.candidate_id, f.identifier)

    def test_latest_rejection_does_not_fall_back_to_an_older_verified_candidate(self):
        f = self.verified()
        self.materialize_seed(f)
        self.later_candidate(f, reject=True)
        before = self.files(f)
        self.assertEqual(self.service(f).promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertEqual(self.files(f), before)
        self.assertFalse(list(f.root.rglob('promotion-intent-*.json')))

    def test_absent_unverified_and_nonfinal_candidates_cannot_prepare_promotion(self):
        for state in ('absent', 'unverified', 'nonfinal'):
            with self.subTest(state=state):
                f = self.ready() if state == 'nonfinal' else self.fixture(register_candidate=state != 'absent')
                self.materialize_seed(f)
                before = self.files(f)
                service = self.service(f)
                self.assertEqual(service.inspect().outcome, 'not_eligible')
                self.assertEqual(service.promote(prepared_at=STAMP).outcome, 'not_eligible')
                self.assertEqual(self.files(f), before)
                self.assertEqual(f.editor.calls, 0 if state == 'absent' else 1)
                if state == 'nonfinal': self.assertEqual(f.client.calls, 0)

    def test_reserved_older_claimant_survives_a_later_verified_registration(self):
        f = self.verified()
        first_id = f.identifier
        self.materialize_seed(f)
        self.stop_after_intent(f)
        self.later_candidate(f)
        self.assertEqual(f.final.decision['candidate_disposition'], 'CANDIDATE_VERIFIED')
        service = self.service(f)
        self.assertEqual(service.inspect().candidate_id, first_id)
        result = service.promote(prepared_at='2031-01-01T00:00:00Z')
        self.assertEqual(result.candidate_id, first_id)
        self.assertEqual(result.current_pointer['promoted_at'], STAMP)
        before = self.files(f)
        self.assertEqual(service.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertEqual(self.files(f), before)

    def test_unselected_later_round_during_repair_refuses_without_restoring_old_head(self):
        f = self.verified()
        first_id = f.identifier
        self.materialize_seed(f)
        service = self.service(f)
        repair = service.materialization.repair
        def advance_then_repair():
            self.assertIsNone(f.store._token)
            repair()
            self.later_candidate(f)
            second = self.service(f).promote(prepared_at='2031-01-01T00:00:00Z')
            self.assertEqual(second.current_pointer['promotion_ordinal'], 2)
            return repair()
        with patch.object(service.materialization, 'repair', side_effect=advance_then_repair):
            with self.assertRaisesRegex(ValueError, 'unselected historical Reviewer round'):
                service.promote(prepared_at=STAMP)
        # Explicit selectors cannot silently authorize a newly published round.
        # A fresh owner can prove it; neither path restores the older commit.
        result = self.service(f).materialization.repair()
        self.assertEqual(result.pointer['promotion_ordinal'], 2)
        self.assertNotEqual(result.pointer['source_candidate_id'], first_id)
        self.assertEqual(result.pointer['source_candidate_id'], f.identifier)
        self.assertEqual(f.store.read('spec.md'), f.store.read(f.creation['candidate_path']))

    def test_competing_valid_intents_refuse_without_choosing_a_winner(self):
        f = self.verified()
        self.materialize_seed(f)
        self.stop_after_intent(f)
        self.later_candidate(f)
        self.prepared_tail(f, f.final)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'multiple candidates claim'):
            self.service(f).promote(prepared_at=STAMP)
        self.assertEqual(self.files(f), before)

    def test_lost_pointer_acknowledgement_recovers_materialization_without_repromotion(self):
        f = self.verified()
        self.materialize_seed(f)
        service = self.service(f)
        write = f.store._tree.write
        def uncertain(path, raw, **options):
            result = write(path, raw, **options)
            if path == 'rounds/current_verified.json':
                raise StorageWriteError(Publication('outcome_requires_reconciliation', path, result.hash), OSError('lost commit ack'))
            return result
        with patch.object(f.store._tree, 'write', side_effect=uncertain):
            with self.assertRaises(StorageWriteError): service.promote(prepared_at=STAMP)
        self.assertIsNone(f.store._token)
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'], 1)
        with patch.object(f.store, 'replace_pointer', side_effect=AssertionError('second pointer replacement')):
            result = service.promote(prepared_at='2031-01-01T00:00:00Z')
        self.assertEqual(result.outcome, 'materialization_recovered')
        self.assertEqual(result.current_pointer['promotion_ordinal'], 1)
        self.assertIsNone(result.committed_pointer)

    def test_promotion_requires_its_own_pin_before_any_mirror_write(self):
        f = self.fixture(contract=False)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'promotion algorithm is outside supported suite'):
            self.service(f).promote(prepared_at=STAMP)
        self.assertEqual(self.files(f), before)

    def test_two_successive_promotions_use_the_production_pointer_owner(self):
        history.VerifiedHistoryTests.test_second_genuine_promotion_replays_both_original_bases(self)

    def test_same_round_followup_uses_the_production_pointer_owner(self):
        history.VerifiedHistoryTests.test_promoted_same_round_followup_replays_rejected_parent_and_exact_answer(self)

    def test_nonprefix_or_changed_preparation_never_overwrites_evidence(self):
        for damage in ('missing_intent', 'missing_event', 'orphan_snapshot', 'changed_snapshot'):
            with self.subTest(damage=damage):
                f = self.verified()
                self.materialize_seed(f)
                service = self.service(f)
                publish = f.store.publish
                def stop(token, path, value):
                    result = publish(token, path, value)
                    if path.endswith('current-verified-1.json'): raise OSError('prepared snapshot')
                    return result
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'prepared snapshot'): service.promote(prepared_at=STAMP)
                directory = f.root / f.creation['candidate_path'].rsplit('/', 1)[0]
                if damage in {'missing_intent', 'orphan_snapshot'}:
                    (directory / 'promotion_intents/promotion-intent-1.json').unlink()
                if damage in {'missing_event', 'orphan_snapshot'}:
                    (directory / 'disposition_events/event-4.json').unlink()
                if damage == 'changed_snapshot':
                    target = f.root / 'rounds/verified_history/current-verified-1.json'
                    packet = json.loads(target.read_bytes())
                    packet['promoted_at'] = '2031-01-01T00:00:00Z'
                    target.write_bytes(canonical_json_bytes(packet))
                before = self.files(f)
                with self.assertRaises((ValueError, FileNotFoundError)): service.promote(prepared_at=STAMP)
                self.assertEqual(self.files(f), before)

    def test_real_process_death_before_and_after_pointer_commit_recovers_once(self):
        script = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_history import VerifiedHistoryAdmission
from whetstone.vnext_verified_promotion import VerifiedPromotion
packet=json.loads(sys.argv[1]);root=Path(packet['root'])
manifest=json.loads(Path(packet['suite_path']).read_bytes())
job=json.loads((root/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={key:job[key] for key in ALGORITHM_VERSIONS}
selectors=packet['selectors'];selectors['round_refs']={int(key):value for key,value in selectors['round_refs'].items()}
with LocalAuthorityStore(root,job_id=job['job_id']) as store:
    owner=VerifiedHistoryAdmission(store,suite_path=packet['suite_path'],**selectors)
    original=store.replace_pointer
    def pause(*args,**kwargs):
        if packet['after']: result=original(*args,**kwargs)
        print('paused',flush=True)
        sys.stdin.readline()
        return result if packet['after'] else original(*args,**kwargs)
    store.replace_pointer=pause
    VerifiedPromotion(store,history=owner).promote(prepared_at=packet['stamp'])
'''
        for after in (False, True):
            with self.subTest(after=after):
                f = self.verified()
                self.materialize_seed(f)
                selectors = f.admission._refs
                packet = {'root': str(f.root), 'suite_path': str(f.admission.suite_path), 'after': after, 'stamp': STAMP,
                    'selectors': {'descriptor_ref': selectors['descriptor'], 'review_ref': selectors['review'],
                        'seed_map_ref': selectors['seed_map'], 'round_refs': selectors['rounds']}}
                child = subprocess.Popen([sys.executable, '-u', '-c', script, json.dumps(packet)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                def cleanup(process=child):
                    if process.poll() is None: process.kill()
                    process.communicate(timeout=5)
                self.addCleanup(cleanup)
                readable, _, _ = select.select([child.stdout], [], [], 60)
                self.assertTrue(readable, 'promotion child did not reach the commit boundary')
                line = child.stdout.readline()
                self.assertEqual(line, b'paused\n', child.stderr.read() if child.poll() is not None else line)
                service = self.service(f)
                before = self.files(f)
                self.assertEqual(service.inspect().outcome, 'materialization_required' if after else 'claimant_prepared')
                with self.assertRaises(StorageBusy): service.promote(prepared_at=STAMP)
                self.assertEqual(self.files(f), before)
                child.kill()
                child.communicate(timeout=10)
                result = service.promote(prepared_at='2031-01-01T00:00:00Z')
                self.assertEqual(result.outcome, 'materialization_recovered' if after else 'promoted')
                self.assertEqual(result.current_pointer['promotion_ordinal'], 1)
                self.assertEqual(result.current_pointer['promoted_at'], STAMP)
                self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def test_lost_ownership_and_changed_final_evidence_refuse_before_commit(self):
        for failure in ('ownership', 'semantic_evidence'):
            with self.subTest(failure=failure):
                f = self.verified()
                self.materialize_seed(f)
                service = self.service(f)
                seed = f.store.read('rounds/current_verified.json')
                publish = f.store.publish
                def stop(token, path, value):
                    result = publish(token, path, value)
                    if path.endswith('current-verified-1.json'):
                        if failure == 'ownership': f.store.release(token)
                        else:
                            request = next(path for path in f.root.glob('rounds/client_requests/*/request.json')
                                           if json.loads(path.read_bytes())['role'] == 'verifier')
                            response = request.parent / 'attempts/1/response.json'
                            response.write_bytes(response.read_bytes() + b' ')
                    return result
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaises((OwnershipLost, ValueError)): service.promote(prepared_at=STAMP)
                self.assertEqual(f.store.read('rounds/current_verified.json'), seed)
                self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def test_stale_tail_with_identical_base_bytes_cannot_authorize_another_intent(self):
        client_type = history.verified.fixtures.Client
        def unchanged(packet):
            content = 'Queue always waits.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        with patch.object(history.verified.fixtures, 'Client', side_effect=lambda callback=None: client_type(callback or unchanged)):
            f = self.verified()
        seed_raw = f.store.read('rounds/verified_history/current-verified-0.json')
        seed = json.loads(seed_raw)
        self.materialize_seed(f)
        promoted = self.service(f).promote(prepared_at=STAMP)
        self.assertEqual(promoted.current_pointer['verified_draft_hash'], seed['verified_draft_hash'])
        self.later_candidate(f)
        intent_path, intent, event_path, event = self.prepared_tail(f, f.final)
        intent.update(expected_current_promotion_ordinal=0, next_promotion_ordinal=1,
                      expected_current_verified_pointer_hash=sha256_bytes(seed_raw))
        intent['intent_id'] = ids.intent_id(intent)
        stale_path = intent_path.replace('promotion-intent-2.json', 'promotion-intent-1.json')
        (f.root / intent_path).unlink()
        (f.root / stale_path).write_bytes(canonical_json_bytes(intent))
        event.update(source_artifact_path=stale_path, source_artifact_hash=sha256_bytes(canonical_json_bytes(intent)))
        event['event_id'] = ids.disposition_id(event)
        (f.root / event_path).write_bytes(canonical_json_bytes(event))
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'exact admitted base pointer'):
            self.service(f).promote(prepared_at=STAMP)
        self.assertEqual(self.files(f), before)


if __name__ == '__main__': unittest.main()
