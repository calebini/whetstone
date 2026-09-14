"""Unactivated two-stage promotion selection, fenced commit and recovery."""
from copy import deepcopy
from dataclasses import dataclass

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_validation import validate_promotion
from whetstone.vnext_verified_history import _snapshot
from whetstone.vnext_verified_materialization import VerifiedMaterialization
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal


ALGORITHM = 'algorithms/vnext_verified_promotion_v1.md'


def _ref(path, value): return {'path': path, 'hash': sha256_bytes(canonical_json_bytes(value))}
def _directory(creation): return creation['candidate_path'].rsplit('/', 1)[0]
def _intent_path(creation, ordinal): return _directory(creation) + f'/promotion_intents/promotion-intent-{ordinal}.json'
def _event_path(creation): return _directory(creation) + '/disposition_events/event-4.json'


@dataclass(frozen=True)
class PromotionView:
    outcome: str
    current_pointer: dict
    candidate_id: str | None = None
    pending_paths: tuple = ()
    committed_pointer: dict | None = None


@dataclass(frozen=True)
class _Selection:
    creation: dict
    semantic: object
    intent: dict | None
    event: dict | None
    snapshot: dict | None


class VerifiedPromotion:
    def __init__(self, store, *, history):
        self.materialization = VerifiedMaterialization(store, history=history)
        self.store, self.history = store, history

    def _proof(self, read):
        proof = self.materialization._proof(read)
        entries = {entry['path']: entry for entry in proof.reader.suite.manifest['algorithms']}
        require(ALGORITHM in entries, 'verified promotion algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
                'installed verified promotion algorithm differs from pinned suite')
        return proof

    def _optional(self, proof, path, schema):
        raw = self.materialization._optional(path)
        if raw is None: return None
        return proof.reader.json({'path': path, 'hash': sha256_bytes(raw)}, schema)

    def _pending(self, proof):
        return self.materialization._pending(self.materialization._targets(proof))

    def _eligible(self, proof, creation, view, promoted):
        decision = view.decision
        if (creation['candidate_id'] in promoted or view.prepared or decision is None
                or not decision['decision_final'] or not decision['promotion_permitted']
                or decision['candidate_disposition'] != 'CANDIDATE_VERIFIED'
                or decision['deterministic_result'] != 'pass' or decision['semantic_result'] != 'pass'
                or decision['outstanding_decision_ids'] or decision['rejection_codes']):
            return False
        arguments = proof.router.load_inputs.for_proposal(self.store.read, creation['round_number'], creation['proposal_id'])
        return arguments['base_pointer_ref'] == proof.latest

    def _package(self, proof, selected, stamp):
        creation, view = selected.creation, selected.semantic
        current = proof.pointers[-1]
        if selected.intent is not None: stamp = selected.intent['prepared_at']
        ordinal = current['promotion_ordinal'] + 1
        creation_ref = _ref(f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json", creation)
        decision_ref = {'path': view.pointer['current_decision_path'], 'hash': view.pointer['current_decision_hash']}
        intent = dict(schema_version='promotion-intent-v1', intent_id='', job_id=creation['job_id'],
            transaction_id=creation['transaction_id'], candidate_id=creation['candidate_id'],
            candidate_creation_ordinal=creation['candidate_creation_ordinal'],
            candidate_creation_event_path=creation_ref['path'], candidate_creation_event_hash=creation_ref['hash'],
            candidate_section_identity_map_path=creation['candidate_section_identity_map_path'],
            candidate_section_identity_map_hash=creation['candidate_section_identity_map_hash'],
            base_draft_hash=current['verified_draft_hash'], candidate_hash=creation['candidate_hash'],
            candidate_verification_path=decision_ref['path'], candidate_verification_hash=decision_ref['hash'],
            expected_current_verified_hash=current['verified_draft_hash'],
            expected_current_verified_pointer_hash=proof.latest['hash'],
            expected_current_promotion_ordinal=current['promotion_ordinal'], next_promotion_ordinal=ordinal,
            status='prepared', prepared_at=stamp)
        intent['intent_id'] = ids.intent_id(intent)
        intent_ref = _ref(_intent_path(creation, ordinal), intent)
        event = dict(schema_version='candidate-disposition-event-v1', event_id='', job_id=creation['job_id'],
            candidate_id=creation['candidate_id'], candidate_creation_ordinal=creation['candidate_creation_ordinal'],
            event_ordinal=4, event_kind='promotion_committed', previous_event_hash=view.effective_event_ref['hash'],
            previous_disposition='CANDIDATE_VERIFIED', new_disposition='CANDIDATE_PROMOTED',
            source_artifact_path=intent_ref['path'], source_artifact_hash=intent_ref['hash'], recorded_at=stamp)
        event['event_id'] = ids.disposition_id(event)
        event_ref = _ref(_event_path(creation), event)
        pointer = {**current, 'promotion_ordinal': ordinal,
            'verified_draft_path': creation['candidate_path'], 'verified_draft_hash': creation['candidate_hash'],
            'verified_section_identity_map_path': creation['candidate_section_identity_map_path'],
            'verified_section_identity_map_hash': creation['candidate_section_identity_map_hash'],
            'source_transaction_id': creation['transaction_id'], 'source_candidate_id': creation['candidate_id'],
            'source_candidate_creation_ordinal': creation['candidate_creation_ordinal'],
            'source_candidate_creation_event_path': creation_ref['path'], 'source_candidate_creation_event_hash': creation_ref['hash'],
            'candidate_verification_path': decision_ref['path'], 'candidate_verification_hash': decision_ref['hash'],
            'promotion_intent_path': intent_ref['path'], 'promotion_intent_hash': intent_ref['hash'],
            'promotion_disposition_event_path': event_ref['path'], 'promotion_disposition_event_hash': event_ref['hash'],
            'previous_verified_draft_hash': current['verified_draft_hash'],
            'previous_verified_pointer_path': proof.latest['path'], 'previous_verified_pointer_hash': proof.latest['hash'],
            'promoted_at': stamp}
        for value, schema in ((intent, 'promotion_intent_v1'), (event, 'candidate_disposition_event_v1'),
                              (pointer, 'current_verified_pointer_v1')):
            proof.reader.suite.registry.validate(value, schema)
        validate_promotion(pointer, intent, intent_ref, current, proof.latest, creation, creation_ref,
                           view.decision, decision_ref, event, event_ref, proof.seed_values['job'])
        require(view.effective_event['event_ordinal'] == 3, 'promotion requires the final semantic event predecessor')
        return intent, event, pointer

    def _select(self, proof):
        proof.inspect_registry()
        require(not proof.view.orphans, 'registration recovery is required before promotion')
        registry = proof.router.registry()
        journal = VerifiedSemanticDecisionJournal(registry, admission=proof.router)
        current = proof.pointers[-1]
        ordinal = current['promotion_ordinal'] + 1
        snapshot = self._optional(proof, f'rounds/verified_history/current-verified-{ordinal}.json', 'current_verified_pointer_v1')
        promoted = {item['source_candidate_id'] for item in proof.pointers[1:]}
        claims, rows = [], []
        for creation in proof.view.creations:
            view = journal._state(creation)[0]
            intent = self._optional(proof, _intent_path(creation, ordinal), 'promotion_intent_v1')
            event = self._optional(proof, _event_path(creation), 'candidate_disposition_event_v1')
            eligible = self._eligible(proof, creation, view, promoted)
            selected = _Selection(creation, view, intent, event, snapshot)
            rows.append((selected, eligible))
            if intent is not None:
                require(eligible, 'prepared promotion claimant is no longer eligible')
                expected = self._package(proof, selected, intent['prepared_at'])
                require(intent == expected[0], 'prepared promotion intent differs from locked inputs')
                require(event is None or event == expected[1], 'prepared promotion event differs from its intent')
                claims.append((selected, expected))
            elif event is not None and creation['candidate_id'] not in promoted:
                source = proof.reader.json({'path': event['source_artifact_path'], 'hash': event['source_artifact_hash']},
                                           'promotion_intent_v1')
                require(source['next_promotion_ordinal'] <= current['promotion_ordinal'],
                        'promotion event lacks its exact next-ordinal intent')
        require(len(claims) <= 1, 'multiple candidates claim the next promotion ordinal')
        if claims:
            selected, expected = claims[0]
            require(snapshot is None or (selected.event is not None and snapshot == expected[2]),
                    'next promotion snapshot is not a matching intent/event prefix')
            result = selected
        else:
            require(snapshot is None, 'next promotion snapshot has no claimant')
            result = rows[-1][0] if rows and rows[-1][1] else None
        proof.guard(self.store.read)
        return result

    def inspect(self):
        proof = self._proof(self.store.read)
        pending = self._pending(proof)
        if pending:
            proof.guard(self.store.read)
            return PromotionView('materialization_required', deepcopy(proof.pointers[-1]), pending_paths=tuple(pending))
        selected = self._select(proof)
        return PromotionView('claimant_prepared' if selected and selected.intent else 'ready' if selected else 'not_eligible',
                             deepcopy(proof.pointers[-1]), selected.creation['candidate_id'] if selected else None)

    def _synchronize(self, token, proof, selected):
        creation, view = selected.creation, selected.semantic
        directory = _directory(creation)
        paths = {
            f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json": canonical_json_bytes(creation),
            directory + '/candidate_verification_pointer-attempt-2.json': canonical_json_bytes(view.pointer),
            directory + '/candidate_verification_current.json': canonical_json_bytes(view.pointer),
            proof.latest['path']: proof.head_raw, 'rounds/current_verified.json': proof.head_raw,
        }
        for path, raw in paths.items(): self.store.synchronize_existing(token, path, expected=raw)

    def promote(self, *, prepared_at):
        captured = {}
        def validate(read): captured['proof'] = self._proof(read)
        committed = None
        with self.store.locked(validate) as token:
            proof = captured['proof']
            pending = self._pending(proof)
            if not pending:
                selected = self._select(proof)
                if selected is None:
                    return PromotionView('not_eligible', deepcopy(proof.pointers[-1]))
                intent, event, pointer = self._package(proof, selected, prepared_at)
                self._synchronize(token, proof, selected)
                self.store.publish(token, _intent_path(selected.creation, pointer['promotion_ordinal']), intent)
                self.store.publish(token, _event_path(selected.creation), event)
                snapshot = _snapshot(pointer)
                self.store.publish(token, snapshot['path'], pointer)
                def transition(old, new):
                    require(old == proof.head_raw and new == canonical_json_bytes(pointer), 'promotion pointer transition changed')
                    fresh = self._proof(self.store.read)
                    require(not self._pending(fresh), 'committed mirrors changed during promotion preparation')
                    claimant = self._select(fresh)
                    require(claimant is not None and claimant.creation == selected.creation
                            and self._package(fresh, claimant, prepared_at) == (intent, event, pointer),
                            'promotion claimant or gate evidence changed before commit')
                self.store.replace_pointer(token, 'rounds/current_verified.json', expected=proof.head_raw,
                                           snapshot=snapshot, validate_transition=transition)
                committed = pointer
        repaired = self.materialization.repair()
        return PromotionView('promoted' if committed is not None else 'materialization_recovered', repaired.pointer,
            committed['source_candidate_id'] if committed else None, repaired.pending_paths, deepcopy(committed))
