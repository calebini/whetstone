"""Versioned vNext identity preimages; no artifact writes or mutation admission."""
from whetstone.vnext_contracts import canonical_json_bytes, content_identifier, require


def project(packet, *excluded):
    return {k: v for k, v in packet.items() if k not in excluded}


def binding_id(binding):
    return content_identifier('bind', 'whetstone-binding-id-v1', [project(binding, 'binding_id', 'path')])


def assertion_id(base_hash, assertion):
    return content_identifier('assert', 'whetstone-assertion-id-v1', [base_hash, project(assertion, 'assertion_id')])


def response_id(response):
    return content_identifier('resp', 'whetstone-response-id-v1', [project(response, 'response_id', 'decided_at')])


def slice_id(item):
    return content_identifier('slice', 'whetstone-slice-id-v1', [project(item, 'slice_id')])


def transaction_id(plan, response_hashes):
    # Response hashes are ordered by their response IDs, not by file location.
    return content_identifier('txn', 'whetstone-transaction-id-v1', [
        project(plan, 'transaction_id'), [[k, response_hashes[k]] for k in sorted(response_hashes)],
    ])


def operation_id(transaction, operation):
    return content_identifier('op', 'whetstone-operation-id-v1', [transaction, project(operation, 'operation_id')])


def proposal_id(patch):
    return content_identifier('pro', 'whetstone-proposal-id-v1', [{**patch, 'proposal_id': None}])


def candidate_id(transaction, base_hash, patch_hash, assembler, normalization):
    return content_identifier('can', 'whetstone-candidate-id-v1', [transaction, base_hash, patch_hash, assembler, normalization])


def seed_section_id(job, seed_hash, binding, ordinal):
    return content_identifier('sec', 'whetstone-seed-section-id-v1', [job, seed_hash, binding, ordinal])


def inserted_section_id(transaction, operation):
    return content_identifier('sec', 'whetstone-inserted-section-id-v1', [transaction, operation])


def seed_unit_id(seed_hash, section, kind, ordinal):
    return content_identifier('unit', 'whetstone-seed-unit-id-v1', [seed_hash, section, kind, ordinal])


def inserted_unit_id(transaction, operation, kind, ordinal):
    return content_identifier('unit', 'whetstone-inserted-unit-id-v1', [transaction, operation, kind, ordinal])


def creation_id(event):
    return content_identifier('creation', 'whetstone-creation-id-v1', [project(event, 'creation_event_id', 'created_at')])


def disposition_id(event):
    return content_identifier('event', 'whetstone-disposition-id-v1', [project(event, 'event_id', 'recorded_at')])


def intent_id(intent):
    return content_identifier('intent', 'whetstone-intent-id-v1', [project(intent, 'intent_id', 'prepared_at')])


def topological(items, key, dependencies):
    by_id = {item[key]: item for item in items}
    require(len(by_id) == len(items), 'duplicate graph identity')
    remaining = {identifier: set(item[dependencies]) for identifier, item in by_id.items()}
    require(all(deps <= by_id.keys() for deps in remaining.values()), 'unknown dependency')
    result = []
    while remaining:
        ready = sorted(identifier for identifier, deps in remaining.items() if not deps)
        require(bool(ready), 'dependency cycle')
        # Lexical priority is recomputed after each single ready node.
        selected = ready[0]; result.append(by_id[selected]); del remaining[selected]
        for deps in remaining.values(): deps.discard(selected)
    return result
