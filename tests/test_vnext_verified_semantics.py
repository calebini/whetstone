"""Genuine V-mode candidate journals using scripted clients on local storage.

The fixture admits only its initial seed. Historical-base admission and public
qualification are separate required consumers, not supplied by this fixture.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import unittest
from unittest.mock import patch

from whetstone import vnext_identity as ids, vnext_registry
from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes, validate_contract_suite
from whetstone.vnext_local_storage import LocalAuthorityStore, initialize_storage
from whetstone.vnext_proposal_admission import ProposalAdmission
from whetstone.vnext_proposal_closeout import ProposalDecisionJournal
from whetstone.vnext_proposal_handoff import register_completed_proposal_request, registry_for_proposal_requests
from whetstone.vnext_proposal_requests import run_proposal_request
from whetstone.vnext_semantic_admission import SEMANTIC_ALGORITHMS, SEMANTIC_SCHEMAS, load_registered_semantic_context
from whetstone.vnext_semantic_protocol import POLICY_VERSION
from whetstone.vnext_semantic_requests import REQUEST_SCHEMAS, run_semantic_request
from whetstone.vnext_verified_semantics import (
    VerifiedSemanticDecisionJournal, VerifiedSemanticRequestJournal,
    finish_verified_semantic_request, inspect_verified_semantic_request, run_verified_semantic_request,
)
from vnext_consuming_suite_fixture import consuming_suite
from vnext_fixtures import STAMP
import test_vnext_proposal_admission as fixtures
import test_vnext_semantic_requests as semantic


class _SeedFixtureAdmission(ProposalAdmission):
    def _base(self, read):
        reader, values = self._seed_inputs(read, expected_mode='verified_promotion')
        require(read('rounds/current_verified.json') == reader.raw(values['base_pointer_ref']),
                'fixture cannot admit historical promoted bases')
        return reader, values


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixtures.ProposalAdmissionTests.setUpClass()

    def fixture(self, *, mode='verified_promotion', qualified=True, pin_intent=True, editor_callback=None,
                extra_algorithms=(), extra_schemas=(), register_candidate=True):
        owner = fixtures.fixtures.UnitPreflightTests()
        owner.setUp()
        self.addCleanup(owner.doCleanups)
        f = owner.c.f
        algorithms = (*SEMANTIC_ALGORITHMS, 'vnext_semantic_requests_v1', 'vnext_semantic_decisions_v1')
        if qualified: algorithms += ('vnext_verified_semantics_v1',)
        algorithms += tuple(extra_algorithms)
        suite, path, versions = consuming_suite(self, Path(owner.c.tmp.name) / 'consumer',
            additional_schemas=SEMANTIC_SCHEMAS | REQUEST_SCHEMAS | set(extra_schemas),
            additional_algorithms=algorithms, algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})
        if not pin_intent:
            manifest = json.loads(path.read_bytes())
            manifest['schemas'] = [entry for entry in manifest['schemas']
                                   if entry['path'] != 'schemas/promotion_intent_v1.schema.json']
            manifest['suite_digest'] = sha256_bytes(canonical_json_bytes(
                {key: value for key, value in manifest.items() if key != 'suite_digest'}))
            path.write_bytes(canonical_json_bytes(manifest))
            registry_patch = patch.dict(vnext_registry.SUPPORTED_SUITES,
                                        {manifest['suite_version']: manifest['suite_digest']})
            registry_patch.start()
            self.addCleanup(registry_patch.stop)
            suite = validate_contract_suite(path)
        f.suite = suite
        f.job.update(editing_mode=mode, contract_suite_version=suite.version, **versions)
        f.rebind()
        record = dict(schema_version='vnext-proposal-round-input-v1', job_id=f.job['job_id'], round_number=1,
                      base_pointer=f.pointer_ref, feedback=f.feedback_ref, advice=f.advice_ref,
                      decision_refs=[], constraints=f.constraints)
        reference = f.save('inputs/proposal-round-1.json', record)
        root = Path(owner.c.tmp.name) / 'verified-run'
        artifacts = {p.relative_to(f.root).as_posix(): p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        initialize_storage(root, job_id=f.job['job_id'], descriptor_ref=f.job_ref, artifacts=artifacts)
        store = LocalAuthorityStore(root, job_id=f.job['job_id'])
        self.addCleanup(store.close)
        admission_type = _SeedFixtureAdmission if mode == 'verified_promotion' else ProposalAdmission
        admission = admission_type(store, suite_path=path, descriptor_ref=f.job_ref,
            review_ref=f.original.review_ref, seed_map_ref=f.map_ref, round_refs={1: reference})
        editor = fixtures.Client(editor_callback)
        if not register_candidate:
            return SimpleNamespace(root=root, store=store, admission=admission, editor=editor)
        run_proposal_request(store, load_inputs=lambda read: admission.load_inputs(read, 1),
                             validate_authority=admission.validate_authority, client=editor)
        creation = register_completed_proposal_request(store, round_number=1, load_inputs=admission.load_inputs,
            validate_authority=admission.validate_authority, created_at=STAMP)
        registry = registry_for_proposal_requests(store, load_inputs=admission.load_inputs,
                                                  validate_authority=admission.validate_authority)
        return SimpleNamespace(root=root, store=store, admission=admission, registry=registry,
                               creation=creation, identifier=creation['candidate_id'], editor=editor)

    def ready(self):
        f = self.fixture()
        f.decisions = VerifiedSemanticDecisionJournal(f.registry, admission=f.admission)
        f.initial = f.decisions.commit(f.identifier, decided_at=STAMP)
        context = load_registered_semantic_context(f.store, admission=f.admission, candidate_id=f.identifier)
        f.client = semantic.Client(context)
        return f

    def run_request(self, f, **options):
        client = options.pop('client') if 'client' in options else f.client
        return run_verified_semantic_request(f.store, admission=f.admission, candidate_id=f.identifier,
                                             client=client, **options)

    def files(self, f):
        return {p.relative_to(f.root).as_posix(): p.read_bytes() for p in f.root.rglob('*') if p.is_file()}

    def prepared_tail(self, f, view):
        """Fixture publication of a protocol prefix; no global pointer commit."""
        previous_raw = f.store.read('rounds/current_verified.json')
        previous = json.loads(previous_raw)
        creation = f.creation
        directory = creation['candidate_path'].rsplit('/', 1)[0]
        intent = dict(schema_version='promotion-intent-v1', intent_id='',
            job_id=creation['job_id'], transaction_id=creation['transaction_id'], candidate_id=f.identifier,
            candidate_creation_ordinal=creation['candidate_creation_ordinal'],
            candidate_creation_event_path=f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json",
            candidate_creation_event_hash=sha256_bytes(canonical_json_bytes(creation)),
            candidate_section_identity_map_path=creation['candidate_section_identity_map_path'],
            candidate_section_identity_map_hash=creation['candidate_section_identity_map_hash'],
            base_draft_hash=view.decision['base_draft_hash'], candidate_hash=creation['candidate_hash'],
            candidate_verification_path=view.pointer['current_decision_path'],
            candidate_verification_hash=view.pointer['current_decision_hash'],
            expected_current_verified_hash=previous['verified_draft_hash'],
            expected_current_verified_pointer_hash=sha256_bytes(previous_raw),
            expected_current_promotion_ordinal=previous['promotion_ordinal'],
            next_promotion_ordinal=previous['promotion_ordinal'] + 1, status='prepared', prepared_at=STAMP)
        intent['intent_id'] = ids.intent_id(intent)
        intent_path = directory + f"/promotion_intents/promotion-intent-{intent['next_promotion_ordinal']}.json"
        event = dict(schema_version='candidate-disposition-event-v1', event_id='', job_id=creation['job_id'],
            candidate_id=f.identifier, candidate_creation_ordinal=creation['candidate_creation_ordinal'],
            event_ordinal=4, event_kind='promotion_committed', previous_event_hash=view.effective_event_ref['hash'],
            previous_disposition='CANDIDATE_VERIFIED', new_disposition='CANDIDATE_PROMOTED',
            source_artifact_path=intent_path, source_artifact_hash=sha256_bytes(canonical_json_bytes(intent)),
            recorded_at=STAMP)
        event['event_id'] = ids.disposition_id(event)
        event_path = directory + '/disposition_events/event-4.json'
        with f.store.locked(f.admission.validate_authority) as token:
            f.store.publish(token, intent_path, intent)
            f.store.publish(token, event_path, event)
        return intent_path, intent, event_path, event

    def test_actual_verified_decision_permits_later_promotion_without_advancing_authority(self):
        f = self.ready()
        seed = f.store.read('rounds/current_verified.json')
        original = self.files(f)
        with self.assertRaisesRegex(ValueError, 'requires proposal_only mode'):
            run_semantic_request(f.store, admission=f.admission, candidate_id=f.identifier, client=f.client)
        self.assertEqual(f.client.calls, 0)
        self.assertEqual(self.files(f), original)
        result = self.run_request(f)
        self.assertEqual(result.status, 'complete')
        self.assertFalse(f.decisions.inspect(f.identifier).decision['promotion_permitted'])
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        self.assertEqual(final.decision['candidate_disposition'], 'CANDIDATE_VERIFIED')
        self.assertTrue(final.decision['promotion_permitted'])
        self.assertEqual(f.store.read('rounds/current_verified.json'), seed)
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))
        before = self.files(f)
        self.assertEqual(self.run_request(f, client=object()).receipt, result.receipt)
        self.assertEqual(f.decisions.commit_semantic(f.identifier, decided_at='2030-01-01T00:00:00Z').decision, final.decision)
        self.assertEqual(self.files(f), before)
        with self.assertRaisesRegex(ValueError, 'promotion workflow owner'): f.decisions.terminal()
        with self.assertRaisesRegex(ValueError, 'requires proposal_only mode'): ProposalDecisionJournal(f.registry)

    def test_rejection_is_final_and_never_receives_promotion_permission(self):
        f = self.ready()
        response = json.loads(f.client.valid)
        response.update(verdict='reject', unrelated_semantic_change='detected')
        f.client.responses = [canonical_json_bytes(response)]
        seed = f.store.read('rounds/current_verified.json')
        self.assertEqual(self.run_request(f).status, 'complete')
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        self.assertEqual(final.decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        self.assertTrue(final.decision['decision_final'])
        self.assertFalse(final.decision['promotion_permitted'])
        self.assertEqual(f.decisions.commit(f.identifier, decided_at='2030-01-01T00:00:00Z').decision, final.decision)
        self.assertEqual(self.run_request(f, client=object()).status, 'complete')
        self.assertEqual(f.client.calls, 1)
        self.assertEqual(f.store.read('rounds/current_verified.json'), seed)

    def test_deterministic_rejection_stops_before_verifier_and_cannot_reopen(self):
        def weaken(packet):
            text = 'Queue sometimes waits.\n'
            packet['payloads'][0]['content'] = text
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(text.encode())
            return canonical_json_bytes(packet)
        f = self.fixture(editor_callback=weaken)
        decisions = VerifiedSemanticDecisionJournal(f.registry, admission=f.admission)
        rejected = decisions.commit(f.identifier, decided_at=STAMP)
        self.assertEqual(rejected.decision['deterministic_result'], 'fail')
        self.assertEqual(rejected.decision['semantic_result'], 'not_run')
        self.assertEqual(rejected.decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        self.assertTrue(rejected.decision['decision_final'])
        self.assertFalse(rejected.decision['promotion_permitted'])
        before = self.files(f)
        with self.assertRaises(ValueError): self.run_request(f, client=object())
        with self.assertRaises(ValueError): decisions.commit_semantic(f.identifier, decided_at=STAMP)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.editor.calls, 1)

    def test_retained_response_and_prepared_final_decision_recover_without_another_verifier(self):
        f = self.ready()
        seed = f.store.read('rounds/current_verified.json')
        publish = f.store.publish
        def stop_raw(token, path, value):
            result = publish(token, path, value)
            if path.endswith('/attempts/1/response.json'): raise OSError('retained V response')
            return result
        with patch.object(f.store, 'publish', side_effect=stop_raw), self.assertRaisesRegex(OSError, 'retained V'):
            self.run_request(f)
        self.assertEqual(inspect_verified_semantic_request(f.store, admission=f.admission,
                         candidate_id=f.identifier).status, 'valid_response')
        finish_verified_semantic_request(f.store, admission=f.admission, candidate_id=f.identifier)
        def stop_decision(token, path, value):
            result = publish(token, path, value)
            if path.endswith('/candidate_verification-attempt-2.json'): raise OSError('prepared V decision')
            return result
        with patch.object(f.store, 'publish', side_effect=stop_decision), self.assertRaisesRegex(OSError, 'prepared V'):
            f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        pending = f.decisions.inspect(f.identifier)
        self.assertTrue(pending.prepared)
        self.assertFalse(pending.decision['promotion_permitted'])
        final = f.decisions.commit_semantic(f.identifier, decided_at='2030-01-01T00:00:00Z')
        self.assertTrue(final.decision['promotion_permitted'])
        self.assertEqual(final.decision['decided_at'], STAMP)
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))
        self.assertEqual(f.store.read('rounds/current_verified.json'), seed)

    def test_missing_contract_and_proposal_mode_refuse_before_verifier(self):
        for mode, qualified, pin_intent, reason in (('verified_promotion', False, True, 'outside supported suite'),
                ('proposal_only', True, True, 'requires V mode'),
                ('verified_promotion', True, False, 'intent schema is outside supported suite')):
            with self.subTest(mode=mode, qualified=qualified, pin_intent=pin_intent):
                f = self.fixture(mode=mode, qualified=qualified, pin_intent=pin_intent)
                before = self.files(f)
                with self.assertRaisesRegex(ValueError, reason):
                    self.run_request(f, client=object())
                with self.assertRaisesRegex(ValueError, reason):
                    VerifiedSemanticDecisionJournal(f.registry, admission=f.admission)
                self.assertEqual(self.files(f), before)

    def test_final_decision_cannot_hide_missing_raw_verifier_evidence(self):
        f = self.ready()
        self.run_request(f)
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        journal = VerifiedSemanticRequestJournal(f.store, admission=f.admission, candidate_id=f.identifier)
        (f.root / journal.directory / 'attempts/1/response.json').unlink()
        before = self.files(f)
        with self.assertRaises(ValueError): f.decisions.inspect(f.identifier)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.client.calls, 1)
        self.assertTrue(final.decision['promotion_permitted'])

    def test_prepared_promotion_tail_is_readable_but_does_not_advance_authority_or_rewrite_decisions(self):
        f = self.ready()
        self.run_request(f)
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        seed = f.store.read('rounds/current_verified.json')
        self.prepared_tail(f, final)
        before = self.files(f)
        with patch.object(f.store, 'publish', side_effect=AssertionError('semantic reentry must not publish after tail')):
            observed = f.decisions.inspect(f.identifier)
            self.assertEqual(observed, final)
            self.assertEqual(f.decisions.commit(f.identifier, decided_at=STAMP), final)
            self.assertEqual(f.decisions.commit_semantic(f.identifier, decided_at=STAMP), final)
        self.assertEqual(observed.effective_event['new_disposition'], 'CANDIDATE_VERIFIED')
        self.assertEqual(f.store.read('rounds/current_verified.json'), seed)
        self.assertEqual(self.files(f), before)
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def test_rehashed_promotion_tail_conflicts_refuse_without_repair(self):
        f = self.ready()
        self.run_request(f)
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        intent_path, intent, event_path, event = self.prepared_tail(f, final)
        cases = [('intent', 'candidate_verification_hash', 'f' * 64),
                 ('intent', 'candidate_section_identity_map_hash', 'f' * 64),
                 ('intent', 'candidate_creation_event_hash', 'f' * 64),
                 ('intent', 'expected_current_verified_pointer_hash', 'f' * 64),
                 ('intent', 'next_promotion_ordinal', 2),
                 ('event', 'previous_event_hash', 'f' * 64),
                 ('event', 'event_ordinal', 5),
                 ('event', 'candidate_creation_ordinal', 2)]
        for kind, key, value in cases:
            with self.subTest(kind=kind, key=key):
                changed_intent, changed_event = dict(intent), dict(event)
                (changed_intent if kind == 'intent' else changed_event)[key] = value
                changed_intent['intent_id'] = ids.intent_id(changed_intent)
                changed_event['source_artifact_hash'] = sha256_bytes(canonical_json_bytes(changed_intent))
                changed_event['event_id'] = ids.disposition_id(changed_event)
                (f.root / intent_path).write_bytes(canonical_json_bytes(changed_intent))
                (f.root / event_path).write_bytes(canonical_json_bytes(changed_event))
                before = self.files(f)
                with self.assertRaises(ValueError): f.decisions.inspect(f.identifier)
                self.assertEqual(self.files(f), before)
        (f.root / intent_path).write_bytes(canonical_json_bytes(intent))
        (f.root / event_path).write_bytes(canonical_json_bytes(event))
        extra = f.root / event_path.replace('event-4.json', 'event-5.json')
        extra.write_bytes(canonical_json_bytes(event))
        with self.assertRaisesRegex(ValueError, 'unsupported or duplicate'): f.decisions.inspect(f.identifier)
        extra.unlink()
        (f.root / intent_path).unlink()
        before = self.files(f)
        with self.assertRaises(FileNotFoundError): f.decisions.inspect(f.identifier)
        self.assertEqual(self.files(f), before)

    def test_promotion_tail_cannot_substitute_for_final_semantic_evidence(self):
        f = self.ready()
        self.prepared_tail(f, f.initial)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'committed final semantic pass'):
            f.decisions.inspect(f.identifier)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.client.calls, 0)

    def test_promotion_tail_cannot_select_an_uncommitted_future_predecessor(self):
        f = self.ready()
        self.run_request(f)
        final = f.decisions.commit_semantic(f.identifier, decided_at=STAMP)
        intent_path, intent, event_path, event = self.prepared_tail(f, final)
        # Rehash the whole local tail around an unattached future snapshot.
        # Its bytes must not become a base merely because the file exists.
        future = json.loads(f.store.read('rounds/current_verified.json'))
        future['promotion_ordinal'] = 1
        raw = canonical_json_bytes(future)
        (f.root / 'rounds/verified_history/current-verified-1.json').write_bytes(raw)
        intent.update(expected_current_promotion_ordinal=1, next_promotion_ordinal=2,
                      expected_current_verified_pointer_hash=sha256_bytes(raw))
        intent['intent_id'] = ids.intent_id(intent)
        next_path = intent_path.replace('promotion-intent-1.json', 'promotion-intent-2.json')
        (f.root / next_path).write_bytes(canonical_json_bytes(intent))
        event.update(source_artifact_path=next_path, source_artifact_hash=sha256_bytes(canonical_json_bytes(intent)))
        event['event_id'] = ids.disposition_id(event)
        (f.root / event_path).write_bytes(canonical_json_bytes(event))
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'outside committed ancestry'):
            f.decisions.inspect(f.identifier)
        self.assertEqual(self.files(f), before)


if __name__ == '__main__': unittest.main()
