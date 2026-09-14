"""Fictional pointer-graph evidence, not runtime promotion qualification."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_pointer_history import read_committed_pointer_history
from whetstone.vnext_sections import seed_section_map
from whetstone.vnext_validation import ArtifactReader
from vnext_fixtures import Bundle


class PointerHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = validate_contract_suite()

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = Bundle(self.root, self.suite)
        # The older graph fixture only claims map hashes. This reader also
        # checks actual parser output, so construct exact maps for these bytes.
        bundle = self.bundle
        seed = (self.root / bundle.seed['path']).read_bytes()
        bundle.base_map = seed_section_map(seed, bundle.job, bundle.binding['binding_id'])
        bundle.base_map_ref = self.save(bundle.base_map_ref['path'], bundle.base_map)
        bundle.seed_pointer['verified_section_identity_map_hash'] = bundle.base_map_ref['hash']
        candidate = (self.root / bundle.candidate_ref['path']).read_bytes()
        bundle.candidate_map = seed_section_map(candidate, bundle.job, bundle.binding['binding_id'])
        bundle.candidate_map['sections'][0]['stable_section_id'] = bundle.base_map['sections'][0]['stable_section_id']
        self.reader = ArtifactReader(self.root, self.suite)
        self.nodes = []
        self.promote(self.bundle.seed_pointer)

    def save(self, path, value):
        return self.bundle.save(path, value)

    def pointer(self, packet):
        self.save(f"rounds/verified_history/current-verified-{packet['promotion_ordinal']}.json", packet)
        return self.save('rounds/current_verified.json', packet)

    def promote(self, previous):
        """Build a claimed graph node; assembly/semantic replay is separate."""
        bundle = self.bundle
        number = previous['promotion_ordinal'] + 1
        creation = deepcopy(bundle.creation)
        identifier = 'can_' + sha256_bytes(str(number).encode())
        directory = f'rounds/round-{number}/candidates/{identifier}'
        candidate_ref = self.save(directory + '/candidate_unverified.md',
                                  (self.root / bundle.candidate_ref['path']).read_bytes())
        mapping_ref = self.save(directory + '/section_identity_map_candidate.json', bundle.candidate_map)
        initial = {**bundle.initial, 'candidate_id': identifier, 'candidate_creation_ordinal': number,
                   'source_artifact_path': candidate_ref['path'], 'source_artifact_hash': candidate_ref['hash']}
        initial['event_id'] = ids.disposition_id(initial)
        initial_ref = self.save(directory + '/disposition_events/event-1.json', initial)
        creation.update(candidate_id=identifier, candidate_creation_ordinal=number, round_number=number,
                        candidate_path=candidate_ref['path'], candidate_hash=candidate_ref['hash'],
                        candidate_section_identity_map_path=mapping_ref['path'],
                        candidate_section_identity_map_hash=mapping_ref['hash'],
                        initial_disposition_event_path=initial_ref['path'], initial_disposition_event_hash=initial_ref['hash'],
                        previous_creation_event_hash=self.nodes[-1]['creation_ref']['hash'] if self.nodes else None)
        creation['creation_event_id'] = ids.creation_id(creation)
        creation_ref = self.save(f'rounds/candidate_index/creation-{number}.json', creation)
        decision = {**bundle.decision, 'candidate_id': identifier, 'candidate_creation_ordinal': number,
                    'base_draft_hash': previous['verified_draft_hash'],
                    'candidate_section_identity_map_path': mapping_ref['path'],
                    'candidate_section_identity_map_hash': mapping_ref['hash']}
        decision_ref = self.save(directory + '/candidate_verification-attempt-1.json', decision)
        verified = {**bundle.verification_event, 'candidate_id': identifier, 'candidate_creation_ordinal': number,
                    'previous_event_hash': initial_ref['hash'],
                    'source_artifact_path': decision_ref['path'], 'source_artifact_hash': decision_ref['hash']}
        verified['event_id'] = ids.disposition_id(verified)
        verified_ref = self.save(directory + '/disposition_events/event-2.json', verified)
        verification = {**bundle.verification_pointer, 'candidate_id': identifier, 'candidate_creation_ordinal': number,
                        'candidate_section_identity_map_path': mapping_ref['path'],
                        'candidate_section_identity_map_hash': mapping_ref['hash'],
                        'current_decision_path': decision_ref['path'], 'current_decision_hash': decision_ref['hash'],
                        'current_disposition_event_path': verified_ref['path'], 'current_disposition_event_hash': verified_ref['hash']}
        self.save(directory + '/candidate_verification_current.json', verification)
        self.save(directory + '/candidate_verification_pointer-attempt-1.json', verification)
        previous_ref = self.save(f"rounds/verified_history/current-verified-{number - 1}.json", previous)
        intent = {**bundle.intent, 'candidate_id': identifier, 'candidate_creation_ordinal': number,
                  'candidate_creation_event_path': creation_ref['path'], 'candidate_creation_event_hash': creation_ref['hash'],
                  'candidate_section_identity_map_path': mapping_ref['path'], 'candidate_section_identity_map_hash': mapping_ref['hash'],
                  'candidate_verification_path': decision_ref['path'], 'candidate_verification_hash': decision_ref['hash'],
                  'base_draft_hash': previous['verified_draft_hash'], 'expected_current_verified_hash': previous['verified_draft_hash'],
                  'expected_current_verified_pointer_hash': previous_ref['hash'],
                  'expected_current_promotion_ordinal': number - 1, 'next_promotion_ordinal': number}
        intent['intent_id'] = ids.intent_id(intent)
        intent_ref = self.save(directory + f'/promotion_intents/promotion-intent-{number}.json', intent)
        promoted = {**bundle.promotion_event, 'candidate_id': identifier, 'candidate_creation_ordinal': number,
                    'previous_event_hash': verified_ref['hash'], 'source_artifact_path': intent_ref['path'],
                    'source_artifact_hash': intent_ref['hash']}
        promoted['event_id'] = ids.disposition_id(promoted)
        promoted_ref = self.save(directory + '/disposition_events/event-3.json', promoted)
        pointer = {**bundle.pointer, 'promotion_ordinal': number,
                   'verified_draft_path': candidate_ref['path'], 'verified_draft_hash': candidate_ref['hash'],
                   'verified_section_identity_map_path': mapping_ref['path'], 'verified_section_identity_map_hash': mapping_ref['hash'],
                   'source_candidate_id': identifier, 'source_candidate_creation_ordinal': number,
                   'source_candidate_creation_event_path': creation_ref['path'], 'source_candidate_creation_event_hash': creation_ref['hash'],
                   'candidate_verification_path': decision_ref['path'], 'candidate_verification_hash': decision_ref['hash'],
                   'promotion_intent_path': intent_ref['path'], 'promotion_intent_hash': intent_ref['hash'],
                   'promotion_disposition_event_path': promoted_ref['path'], 'promotion_disposition_event_hash': promoted_ref['hash'],
                   'previous_verified_draft_hash': previous['verified_draft_hash'],
                   'previous_verified_pointer_path': previous_ref['path'], 'previous_verified_pointer_hash': previous_ref['hash']}
        self.pointer(pointer)
        node = dict(pointer=pointer, directory=directory, creation_ref=creation_ref, decision=decision,
                    decision_ref=decision_ref, intent=intent, intent_ref=intent_ref, promoted=promoted)
        self.nodes.append(node)
        return pointer

    def read(self, reader=None):
        return read_committed_pointer_history(reader or self.reader, job=self.bundle.job,
                                             seed_map_ref=self.bundle.base_map_ref)

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_complete_history_uses_callback_and_never_selects_unbound_future_artifacts(self):
        head = self.promote(self.nodes[-1]['pointer'])
        # These files are deliberately invalid. Stage 1 follows only bindings;
        # next-ordinal reconciliation owns future prepared artifacts.
        self.save('rounds/verified_history/current-verified-3.json', b'not JSON')
        self.save(self.nodes[-1]['directory'] + '/promotion_intents/promotion-intent-3.json', b'not JSON')
        stale = self.nodes[-1]['directory'] + '/promotion_intents/promotion-intent-1.json'
        self.save(stale, b'not JSON')
        before = self.files()
        reads = []
        def read(path):
            reads.append(path)
            return before[path]
        result = self.read(ArtifactReader(None, self.suite, read=read))
        self.assertEqual([p['promotion_ordinal'] for p in result], [0, 1, 2])
        self.assertEqual(result[-1], head)
        self.assertNotIn('rounds/verified_history/current-verified-3.json', reads)
        self.assertNotIn(stale, reads)
        self.assertEqual(self.files(), before)

    def test_seed_history_requires_exact_seed_map_and_no_candidate_lineage(self):
        self.pointer(self.bundle.seed_pointer)
        self.assertEqual(self.read(), (self.bundle.seed_pointer,))
        bad = {**self.bundle.seed_pointer, 'source_candidate_id': self.nodes[0]['pointer']['source_candidate_id']}
        self.pointer(bad)
        with self.assertRaisesRegex(ValueError, 'seed pointer has'): self.read()

    def test_missing_or_changed_bound_ancestor_artifacts_refuse_without_repairs(self):
        self.promote(self.nodes[-1]['pointer'])
        node = self.nodes[0]
        paths = ['rounds/verified_history/current-verified-0.json',
                 'rounds/verified_history/current-verified-1.json',
                 node['pointer']['verified_draft_path'], node['pointer']['verified_section_identity_map_path'],
                 node['creation_ref']['path'], node['decision_ref']['path'], node['intent_ref']['path'],
                 node['directory'] + '/disposition_events/event-3.json',
                 node['directory'] + '/candidate_verification_current.json',
                 node['directory'] + '/candidate_verification_pointer-attempt-1.json']
        for relative in paths:
            path = self.root / relative
            original = path.read_bytes()
            for missing in (False, True):
                with self.subTest(path=relative, missing=missing):
                    if missing: path.unlink()
                    else: path.write_bytes(original + b' ')
                    before = self.files()
                    with self.assertRaises((ValueError, FileNotFoundError)): self.read()
                    self.assertEqual(self.files(), before)
                    path.write_bytes(original)

    def test_predecessor_alias_gap_and_self_reference_refuse(self):
        good = self.nodes[-1]['pointer']
        self.save('inputs/seed-pointer-alias.json', self.bundle.seed_pointer)
        for changes in ({'previous_verified_pointer_path': 'inputs/seed-pointer-alias.json'},
                        {'promotion_ordinal': 2},
                        {'previous_verified_pointer_path': 'rounds/verified_history/current-verified-1.json'}):
            with self.subTest(changes=changes):
                self.pointer({**good, **changes})
                with self.assertRaisesRegex(ValueError, 'predecessor|ordinal'): self.read()

    def test_current_pointer_requires_own_identical_snapshot(self):
        self.save('rounds/current_verified.json', {**self.nodes[-1]['pointer'], 'promoted_at': '2030-01-01T00:00:00Z'})
        with self.assertRaisesRegex(ValueError, 'same-ordinal'): self.read()

    def test_rehashed_intent_cannot_change_expected_base(self):
        node = self.nodes[0]
        intent = {**node['intent'], 'expected_current_verified_hash': 'f' * 64}
        intent['intent_id'] = ids.intent_id(intent)
        intent_ref = self.save(node['intent_ref']['path'], intent)
        event = {**node['promoted'], 'source_artifact_hash': intent_ref['hash']}
        event['event_id'] = ids.disposition_id(event)
        event_ref = self.save(node['pointer']['promotion_disposition_event_path'], event)
        self.pointer({**node['pointer'], 'promotion_intent_hash': intent_ref['hash'],
                      'promotion_disposition_event_hash': event_ref['hash']})
        with self.assertRaisesRegex(ValueError, 'conflicting artifact binding'): self.read()

    def test_rehashed_promotion_event_cannot_skip_its_verified_predecessor(self):
        node = self.nodes[0]
        event = {**node['promoted'], 'previous_event_hash': 'f' * 64}
        event['event_id'] = ids.disposition_id(event)
        ref = self.save(node['pointer']['promotion_disposition_event_path'], event)
        self.pointer({**node['pointer'], 'promotion_disposition_event_hash': ref['hash']})
        with self.assertRaisesRegex(ValueError, 'does not extend'): self.read()

    def test_current_pointer_change_during_traversal_refuses(self):
        files = self.files()
        current_reads = 0
        def read(path):
            nonlocal current_reads
            if path == 'rounds/current_verified.json':
                current_reads += 1
                if current_reads == 4: return canonical_json_bytes(self.bundle.seed_pointer)
            return files[path]
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.read(ArtifactReader(None, self.suite, read=read))

    def test_fully_rehashed_history_cannot_reopen_a_final_decision(self):
        node = self.nodes[0]
        directory = node['directory']
        decision = {**node['decision'], 'decision_ordinal': 2,
                    'previous_decision_hash': node['decision_ref']['hash']}
        decision_ref = self.save(directory + '/candidate_verification-attempt-2.json', decision)
        pointer_path = directory + '/candidate_verification_current.json'
        verification = self.reader.json({'path': pointer_path,
                                         'hash': sha256_bytes((self.root / pointer_path).read_bytes())})
        event = self.reader.json({'path': verification['current_disposition_event_path'],
                                  'hash': verification['current_disposition_event_hash']})
        event.update(event_ordinal=3, previous_event_hash=verification['current_disposition_event_hash'],
                     previous_disposition='CANDIDATE_VERIFIED', source_artifact_path=decision_ref['path'],
                     source_artifact_hash=decision_ref['hash'])
        event['event_id'] = ids.disposition_id(event)
        event_ref = self.save(directory + '/disposition_events/event-3.json', event)
        verification.update(current_decision_ordinal=2, current_decision_path=decision_ref['path'],
                            current_decision_hash=decision_ref['hash'],
                            current_disposition_event_path=event_ref['path'], current_disposition_event_hash=event_ref['hash'])
        self.save(directory + '/candidate_verification_pointer-attempt-2.json', verification)
        self.save(directory + '/candidate_verification_current.json', verification)
        intent = {**node['intent'], 'candidate_verification_path': decision_ref['path'],
                  'candidate_verification_hash': decision_ref['hash']}
        intent['intent_id'] = ids.intent_id(intent)
        intent_ref = self.save(node['intent_ref']['path'], intent)
        promotion = {**node['promoted'], 'event_ordinal': 4, 'previous_event_hash': event_ref['hash'],
                     'source_artifact_hash': intent_ref['hash']}
        promotion['event_id'] = ids.disposition_id(promotion)
        promotion_ref = self.save(directory + '/disposition_events/event-4.json', promotion)
        self.pointer({**node['pointer'], 'candidate_verification_path': decision_ref['path'],
                      'candidate_verification_hash': decision_ref['hash'], 'promotion_intent_hash': intent_ref['hash'],
                      'promotion_disposition_event_path': promotion_ref['path'], 'promotion_disposition_event_hash': promotion_ref['hash']})
        with self.assertRaisesRegex(ValueError, 'reopens a final decision'): self.read()


if __name__ == '__main__':
    unittest.main()
