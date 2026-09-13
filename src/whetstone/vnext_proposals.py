"""Non-promoting, section-addressed proposal preparation.

Inputs must be an admitted immutable plan. This module never invokes a client,
registers a candidate, changes the verified pointer or proves semantic meaning.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import (
    canonical_json_bytes, confined_file, decode_json, require, sha256_bytes,
)
from whetstone.vnext_sections import section_spans
from whetstone.vnext_storage import publish
from whetstone.vnext_validation import validate_patch

INSERT_OPERATIONS = {'insert_section_before', 'insert_section_after', 'append_child_section'}


@dataclass(frozen=True)
class PreparedProposal:
    patch: dict
    payloads: dict[str, bytes]

    @property
    def digest(self):
        return sha256_bytes(canonical_json_bytes(self.patch))


def _targets(raw, mapping):
    require(mapping['draft_hash'] == sha256_bytes(raw), 'section map has a stale draft')
    active = sorted((s for s in mapping['sections'] if s['status'] == 'active'),
                    key=lambda s: s['preorder_ordinal'])
    spans = section_spans(raw)
    require(len(active) == len(spans), 'section map does not cover base headings')
    require(len({s['stable_section_id'] for s in mapping['sections']}) == len(mapping['sections']),
            'section identity collision')
    result = {}
    for index, (item, span) in enumerate(zip(active, spans)):
        require(item['preorder_ordinal'] == index + 1
                and item['heading_level'] == span.level
                and item['heading_text'] == span.heading
                and item['canonical_section_id'] == span.canonical_id
                and item['section_hash'] == sha256_bytes(raw[span.start:span.end])
                and item['direct_body_hash'] == sha256_bytes(raw[span.heading_end:span.direct_end])
                and item['parent_stable_section_id'] == (
                    active[span.parent]['stable_section_id'] if span.parent is not None else None),
                'section map disagrees with exact base bytes')
        result[item['stable_section_id']] = (item, span)
    return result


def _payload_shape(raw, operation, target):
    # Decode strictly even when no headings occur; malformed bytes never become payload authority.
    raw.decode('utf-8')
    spans = section_spans(raw)
    kind = operation['operation_type']
    if kind == 'replace_section_body':
        require(all(span.level > target.level for span in spans),
                'body payload contains a heading at or above target level')
        return
    expected = target.level + (kind == 'append_child_section')
    require(bool(spans) and spans[0].start == 0 and spans[0].level == expected,
            'section payload must start with one root at the required level')
    require(sum(span.parent is None for span in spans) == 1,
            'section payload must contain exactly one root')
    require(all(span.level > expected for span in spans[1:]), 'payload escapes its root')
    # markdown-atx-v1 permits skipped descendant levels; only the payload root
    # and an append-child root have an exact level requirement.


def _effect_authorization(op, plan, responses):
    effect = op['normative_change']
    if effect not in {'remove', 'weaken', 'authority_change', 'scope_change'}:
        return
    dispositions = {f['finding_id']: f for f in plan['finding_dispositions']}
    by_id = {r['response_id']: r for r in responses}
    for finding in op['addressed_finding_ids']:
        response = by_id.get(dispositions[finding]['decision_response_id'])
        require(response is not None and effect in response['authorized_effects'],
                'operator response does not authorize the claimed effect')


class _PayloadReader:
    """Use already read immutable bytes for the offline cross-artifact validator."""
    def __init__(self, directory, payloads):
        self.directory = directory
        self.payloads = payloads

    def raw(self, reference):
        prefix = self.directory + '/'
        require(reference['path'].startswith(prefix), 'payload outside proposal')
        raw = self.payloads[reference['path'][len(prefix):]]
        require(sha256_bytes(raw) == reference['hash'], 'payload digest mismatch')
        return raw


def prepare_patch(raw_response, *, payload_root, plan, base, section_map, editor,
                  suite, responses=(), units=None):
    """Validate a raw client envelope and derive canonical Orchestrator metadata.

    Runtime admission/decision authorization precedes this pure preparation API.
    Slice 18.4 rejects overlapping base mutations: the frozen plan has no field
    that can explicitly authorize overlap. Dependencies alone do not grant it.
    """
    client = decode_json(raw_response)
    suite.registry.validate(client, 'patch_set_client_v1')
    suite.registry.validate(plan, 'mutation_plan_v1')
    suite.registry.validate(section_map, 'section_identity_map_v1')
    require(section_map['job_id'] == plan['job_id'], 'section map belongs to another job')
    require(sha256_bytes(base) == plan['base_draft_hash'], 'proposal base is stale')
    targets = _targets(base, section_map)
    patch = deepcopy(client)
    patch['editor'] = deepcopy(editor)
    for key, value in [('job_id', plan['job_id']), ('transaction_id', plan['transaction_id']),
                       ('base_draft_hash', plan['base_draft_hash']),
                       ('mutation_plan_hash', sha256_bytes(canonical_json_bytes(plan)))]:
        require(patch[key] == value, 'client changed frozen proposal binding', key)
    admitted = {f['finding_id'] for f in plan['finding_dispositions'] if f['admitted_to_editing']}
    dispositions = {f['finding_id']: f for f in plan['finding_dispositions']}
    for decline in patch['declined_findings']:
        require(decline['finding_id'] in dispositions, 'decline cites an unknown finding')
        require(set(decline['source_feedback_ids']) == set(
            dispositions[decline['finding_id']]['source_feedback_ids']),
            'decline source feedback differs from admitted evidence')
    require(all(f['classification'] == 'editor_fixable' for f in plan['finding_dispositions']
                if f['admitted_to_editing']), 'plan admits a non-editor-fixable finding')
    require(not (admitted & {f['finding_id'] for f in patch['declined_findings']}),
            'admitted finding declined; reconcile through a new plan')
    operations = ids.topological(patch['operations'], 'operation_id', 'depends_on_operation_ids')
    renamed = {}
    payloads = {}
    prepared = []
    mutated = []
    anchors = {}
    for original in operations:
        op = deepcopy(original)
        target_id = op['target_stable_section_id']
        require(target_id in targets, 'operation targets an unknown or retired section')
        item, span = targets[target_id]
        require(op['expected_target_hash'] == item['section_hash'], 'stale target preimage')
        require(bool(op['addressed_finding_ids']) and set(op['addressed_finding_ids']) <= admitted,
                'operation cites unadmitted work')
        require(any(target_id in sl['target_section_ids']
                    and set(op['addressed_finding_ids']) <= set(sl['admitted_finding_ids'])
                    for sl in plan['slices']), 'operation attribution is outside its section slice')
        kind = op['operation_type']
        require(kind in plan['allowed_operation_types'], 'operation type outside plan')
        if kind in {'replace_section_subtree', 'delete_section_subtree'}:
            require(span.parent is not None, 'document root cannot be replaced or deleted')
        if kind == 'replace_section_body':
            interval = (span.heading_end, span.direct_end)
        elif kind in {'replace_section_subtree', 'delete_section_subtree'}:
            interval = (span.start, span.end)
        else:
            position = span.start if kind == 'insert_section_before' else span.end
            interval = (position, position)
        # Repeated insertions need explicit ordering. All other overlapping base
        # mutations require a future plan contract with explicit overlap policy.
        for earlier, old_interval in mutated:
            a, b = interval
            c, d = old_interval
            overlap = (a < d and c < b) or (a == b and c < a < d) or (c == d and a < c < b)
            require(not overlap, 'overlapping base mutation is not authorized by this plan contract')
            require(not (target_id == earlier['target_stable_section_id']
                         and not (kind in INSERT_OPERATIONS and earlier['operation_type'] in INSERT_OPERATIONS)),
                    'duplicate mutation target')
        if kind in INSERT_OPERATIONS:
            # Adjacent subtree end/start addresses can name the same physical
            # insertion point. Ordering must not depend on an address alias.
            anchor = interval[0]
            if anchor in anchors:
                require(anchors[anchor] in op['depends_on_operation_ids'],
                        'multiple insertions at an anchor require explicit dependency')
            anchors[anchor] = original['operation_id']
        if kind == 'delete_section_subtree':
            require(op['payload'] == {'path': None, 'hash': None}, 'delete requires a null payload')
            require(op['normative_change'] == 'remove', 'deletion must declare removal')
            require(units is not None, 'deletion requires an exact base unit catalog')
            removed={key for key,unit in units.items() if span.start<=unit['byte_start']<span.end and unit['protected']}
            require(bool(removed) and removed<=set(plan['authorized_deletion_unit_ids']),
                    'deletion lacks exact unit authorization for its subtree')
            # A plan-wide union is insufficient: an operation cannot borrow
            # deletion units from an operator decision for unrelated work.
            response_ids = {dispositions[f]['decision_response_id'] for f in op['addressed_finding_ids']}
            attributed_units = {unit for response in responses
                                if response['response_id'] in response_ids and 'remove' in response['authorized_effects']
                                for unit in response['authorized_deletion_unit_ids']}
            require(removed <= attributed_units,
                    'deletion units are not authorized by the addressed operator tasks')
        else:
            reference = op['payload']
            require(reference['path'] is not None and reference['hash'] is not None,
                    'non-delete operation requires a payload')
            raw = confined_file(Path(payload_root), reference['path']).read_bytes()
            require(sha256_bytes(raw) == reference['hash'], 'client payload hash mismatch')
            _payload_shape(raw, op, span)
            path = 'payloads/' + reference['hash'] + '.md'
            require(path not in payloads or payloads[path] == raw, 'payload hash collision')
            payloads[path] = raw
            op['payload'] = {'path': path, 'hash': reference['hash']}
        _effect_authorization(op, plan, responses)
        op['depends_on_operation_ids'] = sorted(renamed[label] for label in op['depends_on_operation_ids'])
        op['operation_id'] = ids.operation_id(plan['transaction_id'], op)
        require(op['operation_id'] not in renamed.values(), 'operation identity collision')
        renamed[original['operation_id']] = op['operation_id']
        prepared.append(op)
        mutated.append((op, interval))
    patch['operations'] = ids.topological(prepared, 'operation_id', 'depends_on_operation_ids')
    patch['proposal_id'] = ids.proposal_id(patch)
    suite.registry.validate(patch, 'patch_set_v1')
    directory = 'proposals/' + patch['proposal_id']
    validate_patch(patch, plan, {key: item for key, (item, _) in targets.items()},
                   _PayloadReader(directory, payloads), proposal_directory=directory)
    return PreparedProposal(patch, payloads)


def persist_proposal(root, round_number, attempt_number, raw_response, *, payload_root,
                     plan, base, section_map, editor, suite, responses=(), units=None):
    """Retain a raw attempt, then publish validated immutable proposal bytes.

    The caller owns offline transaction exclusion. Runtime exposure requires the
    later D8 adapter and the complete admission gate; this is not a CLI endpoint.
    """
    require(type(round_number) is int and round_number > 0
            and type(attempt_number) is int and attempt_number > 0, 'invalid attempt ordinal')
    directory = f'rounds/round-{round_number}/proposals'
    publish(Path(root), directory + f'/attempts/proposal-attempt-{attempt_number}.json', raw_response)
    proposal = prepare_patch(raw_response, payload_root=payload_root, plan=plan, base=base,
                             section_map=section_map, editor=editor, suite=suite, responses=responses, units=units)
    canonical_directory = directory + '/' + proposal.patch['proposal_id']
    for path, raw in sorted(proposal.payloads.items()):
        publish(Path(root), canonical_directory + '/' + path, raw)
    reference = publish(Path(root), canonical_directory + '/proposed_patch.json', proposal.patch)
    return proposal, reference
