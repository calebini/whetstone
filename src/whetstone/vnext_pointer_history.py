"""Read-only structural validation of committed verified-pointer history.

This joins exact stored evidence; it does not reproduce candidate assembly or
Verifier judgments. A runtime consumer must additionally validate bootstrap,
registration and semantic evidence under its qualified suite. No writer,
recovery, next-ordinal selection or runtime capability is provided here.
"""
from whetstone import vnext_identity as ids
from whetstone.hashing import normalize_draft
from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_sections import seed_section_map
from whetstone.vnext_section_lineage import validate_lineage_map
from whetstone.vnext_validation import (
    validate_disposition_chain, validate_pointer_snapshot, validate_promotion,
    validate_seed_pointer, validate_verification_pointer,
)


CURRENT_PATH = 'rounds/current_verified.json'


def _reference(packet, prefix):
    reference = {'path': packet[prefix + '_path'], 'hash': packet[prefix + '_hash']}
    require(all(isinstance(value, str) and value for value in reference.values()),
            'committed pointer has an incomplete reference', prefix)
    return reference


def _snapshot(ordinal):
    return f'rounds/verified_history/current-verified-{ordinal}.json'


def _json_at(reader, path, schema):
    raw = reader._read_path(path)
    reference = {'path': path, 'hash': sha256_bytes(raw)}
    return reader.json(reference, schema), reference


def _draft_map(reader, pointer, job):
    raw = reader.raw(_reference(pointer, 'verified_draft'))
    mapping = reader.json(_reference(pointer, 'verified_section_identity_map'))
    require(mapping.get('schema_version') in {'section-identity-map-v1', 'section-identity-map-v2'},
            'unsupported committed section map')
    require(mapping['job_id'] == job['job_id']
            and mapping['draft_hash'] == pointer['verified_draft_hash']
            and mapping['parser_contract_version'] == job['parser_contract_version'],
            'committed section map differs from pointer or job')
    validate_lineage_map(mapping, raw)
    return raw, mapping


def _promotion(reader, pointer, previous, previous_ref, job):
    creation_ref = _reference(pointer, 'source_candidate_creation_event')
    creation = reader.json(creation_ref, 'candidate_creation_event_v1')
    ordinal = creation['candidate_creation_ordinal']
    require(creation_ref['path'] == f'rounds/candidate_index/creation-{ordinal}.json'
            and creation['creation_event_id'] == ids.creation_id(creation),
            'committed creation identity or path differs')
    directory = f"rounds/round-{creation['round_number']}/candidates/{creation['candidate_id']}"
    require(creation['candidate_path'] == directory + '/candidate_unverified.md'
            and creation['candidate_section_identity_map_path'] == directory + '/section_identity_map_candidate.json',
            'committed candidate has a noncanonical locator')
    decision_ref = _reference(pointer, 'candidate_verification')
    decision = reader.json(decision_ref, 'candidate_verification_v1')
    require(decision_ref['path'] == directory + f"/candidate_verification-attempt-{decision['decision_ordinal']}.json",
            'committed verification has a noncanonical locator')
    require(decision['deterministic_result'] == decision['semantic_result'] == 'pass'
            and not decision['outstanding_decision_ids'] and not decision['rejection_codes'],
            'committed verification has unresolved gates')
    intent_ref = _reference(pointer, 'promotion_intent')
    require(intent_ref['path'] == directory + f"/promotion_intents/promotion-intent-{pointer['promotion_ordinal']}.json",
            'committed intent has a noncanonical locator')
    intent = reader.json(intent_ref, 'promotion_intent_v1')
    event_ref = _reference(pointer, 'promotion_disposition_event')
    event = reader.json(event_ref, 'candidate_disposition_event_v1')
    require(event_ref['path'] == directory + f"/disposition_events/event-{event['event_ordinal']}.json"
            and event['event_id'] == ids.disposition_id(event),
            'committed promotion event identity or path differs')

    verification, verification_ref = _json_at(reader, directory + '/candidate_verification_current.json',
                                             'candidate_verification_pointer_v1')
    verification_snapshot = directory + f"/candidate_verification_pointer-attempt-{decision['decision_ordinal']}.json"
    require(reader._read_path(verification_snapshot) == reader.raw(verification_ref),
            'committed verification pointer differs from its snapshot')
    verification_event_ref = _reference(verification, 'current_disposition_event')
    verification_event = reader.json(verification_event_ref, 'candidate_disposition_event_v1')
    require(verification_event_ref['path'] == directory + f"/disposition_events/event-{verification_event['event_ordinal']}.json",
            'committed verification event has a noncanonical locator')
    validate_verification_pointer(verification, decision, decision_ref,
                                  verification_event, verification_event_ref, creation)
    require(event['job_id'] == job['job_id'] == creation['job_id']
            and event['candidate_creation_ordinal'] == ordinal
            and event['previous_event_hash'] == verification_event_ref['hash']
            and event['event_ordinal'] == verification_event['event_ordinal'] + 1,
            'committed promotion event does not extend the verified disposition')

    # Follow exact predecessor hashes. Directory contents never select state.
    references = [event_ref]
    next_event = event
    while next_event['event_ordinal'] > 1:
        number = next_event['event_ordinal'] - 1
        reference = {'path': directory + f'/disposition_events/event-{number}.json',
                     'hash': next_event['previous_event_hash']}
        next_event = reader.json(reference, 'candidate_disposition_event_v1')
        require(next_event['event_ordinal'] == number, 'committed disposition ordinal gap')
        references.append(reference)
    require(creation['initial_disposition_event_path'] == directory + '/disposition_events/event-1.json'
            and next_event['event_kind'] == 'candidate_created'
            and next_event['new_disposition'] == 'CANDIDATE_UNVERIFIED'
            and next_event['source_artifact_path'] == creation['candidate_path']
            and next_event['source_artifact_hash'] == creation['candidate_hash'],
            'committed disposition chain lacks its registered initial event')
    dispositions = validate_disposition_chain(reader, list(reversed(references)), creation)
    final = False
    for disposition in dispositions:
        if disposition['event_kind'] == 'verification_decision':
            require(not final, 'committed verification history reopens a final decision')
            source = reader.json(_reference(disposition, 'source_artifact'), 'candidate_verification_v1')
            final = source['decision_final']
    validate_promotion(pointer, intent, intent_ref, previous, previous_ref,
                       creation, creation_ref, decision, decision_ref, event, event_ref, job)


def read_committed_pointer_history(reader, *, job, seed_map_ref):
    """Read seed-to-current pointer bindings without enumerating other intents.

    The caller supplies a freshly validated job and seed-map reference. Only
    current_verified.json selects the head; a prepared history snapshot cannot
    advance this reader. Returned packets are observations, not cached grants.
    """
    raw = reader._read_path(CURRENT_PATH)
    current_ref = {'path': CURRENT_PATH, 'hash': sha256_bytes(raw)}
    current = validate_pointer_snapshot(reader, current_ref)
    descending = [current]
    pointer = current
    seen_candidates = set()
    while True:
        require(pointer['job_id'] == job['job_id'], 'committed pointer belongs to another job')
        draft, mapping = _draft_map(reader, pointer, job)
        if pointer['promotion_ordinal'] == 0:
            validate_seed_pointer(pointer, job, seed_map_ref)
            require(normalize_draft(draft.decode('utf-8')).encode('utf-8') == draft,
                    'committed seed is not normalized')
            authority = reader.json({'path': job['authority_map_path'], 'hash': job['authority_map_hash']},
                                    'authority_map_v1')
            mutable = [row for row in authority['bindings'] if row['role'] == 'mutable_target']
            require(len(mutable) == 1 and mutable[0]['content_hash'] == job['seed_draft']['hash'],
                    'committed seed lacks its exact mutable authority binding')
            require(mapping == seed_section_map(draft, job, mutable[0]['binding_id']),
                    'committed seed map does not reproduce')
            break
        candidate = pointer['source_candidate_id']
        require(candidate not in seen_candidates, 'candidate is promoted more than once')
        seen_candidates.add(candidate)
        previous_ref = _reference(pointer, 'previous_verified_pointer')
        expected = pointer['promotion_ordinal'] - 1
        require(previous_ref['path'] == _snapshot(expected), 'committed predecessor has a noncanonical ordinal path')
        previous = reader.json(previous_ref, 'current_verified_pointer_v1')
        require(previous['promotion_ordinal'] == expected, 'committed pointer ordinal gap or cycle')
        _promotion(reader, pointer, previous, previous_ref, job)
        descending.append(previous)
        pointer = previous
    require(reader.raw(current_ref) == canonical_json_bytes(current), 'current pointer changed during history read')
    return tuple(reversed(descending))
