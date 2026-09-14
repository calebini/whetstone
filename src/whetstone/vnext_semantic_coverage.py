"""Pure semantic evidence coverage for inventory-v2 candidates.

This unactivated consumer neither invokes a verifier nor grants a disposition.
The storage caller must validate committed base lineage and registration before
using it. Replaying an assessment proves local bindings, not storage authority.
"""
from copy import deepcopy

from whetstone.vnext_candidate_validation import validate_assessment_readback
from whetstone.vnext_contracts import (
    VNextSchemaRegistry, canonical_json_bytes, content_identifier, require, sha256_bytes,
)


def _hash(value):
    return sha256_bytes(canonical_json_bytes(value))


def prepare_semantic_obligations(*, report, inventory, **assessment_inputs):
    """Reproduce deterministic evidence before deriving exact review subjects.

    Every semantic-required unit row and every explicit correspondence group
    has a separate obligation. Group coverage never substitutes for unit
    coverage. Source diagnostics are also retained for independent assessment.
    """
    validate_assessment_readback(report, inventory, **assessment_inputs)
    require(report['result'] == 'pass' and report['metrics_complete'] and inventory is not None,
            'semantic coverage requires a complete deterministic pass')
    base_inventory = assessment_inputs['base_inventory']
    base = assessment_inputs['base']
    candidate = assessment_inputs['candidate_bytes']
    old = {unit['unit_id']: unit for unit in base_inventory['units']}
    new = {unit['unit_id']: unit for unit in inventory['units']}
    bindings = {
        key: report[key] for key in (
            'job_id', 'transaction_id', 'candidate_id', 'base_draft_hash', 'candidate_hash',
            'candidate_section_identity_map_path', 'candidate_section_identity_map_hash',
            'patch_set_hash', 'base_inventory_hash', 'candidate_inventory_hash',
        )
    }
    bindings.update(preservation_report_hash=_hash(report),
                    mutation_plan_hash=_hash(assessment_inputs['plan']),
                    job_descriptor_hash=_hash(assessment_inputs['job']))

    def endpoint(key, side):
        unit = (old if side == 'base' else new)[key]
        raw = base if side == 'base' else candidate
        content = raw[unit['byte_start']:unit['byte_end']]
        require(sha256_bytes(content) == unit['content_hash'], 'semantic endpoint content changed')
        return {'side': side, 'unit': deepcopy(unit), 'text': content.decode('utf-8')}

    obligations = []

    def append(kind, rows, before, after, diagnostics=()):
        subject = {
            'kind': kind,
            'report_rows': sorted(deepcopy(rows), key=canonical_json_bytes),
            'base_units': [endpoint(key, 'base') for key in sorted(set(before))],
            'candidate_units': [endpoint(key, 'candidate') for key in sorted(set(after))],
            'baseline_diagnostics': deepcopy(list(diagnostics)),
        }
        identifier = content_identifier('sem', 'whetstone-semantic-obligation-v1', [bindings, subject])
        obligations.append({'obligation_id': identifier, **subject})

    groups = {}
    for row in report['unit_changes']:
        key = row['unit_id']
        if row['semantic_required']:
            append('unit', [row], [key] if key in old else [], row['candidate_unit_ids'])
        group = row['correspondence_group_id']
        if group is not None:
            groups.setdefault(group, []).append(row)
    for rows in groups.values():
        append('correspondence_group', rows,
               [row['unit_id'] for row in rows if row['unit_id'] in old],
               [key for row in rows for key in row['candidate_unit_ids']])
    if report['baseline_diagnostics']:
        append('baseline_diagnostics', [], [], [], report['baseline_diagnostics'])
    packet = {'schema_version': 'vnext-semantic-obligations-v1', 'bindings': bindings,
              'obligations': sorted(obligations, key=lambda row: row['obligation_id'])}
    VNextSchemaRegistry().validate(packet, 'vnext_semantic_obligations_v1')
    return packet


def validate_semantic_coverage(response, *, obligations):
    """Require exactly one substantive assessment of each frozen subject.

    `obligations` must come from prepare_semantic_obligations (or exact replay
    of it), never from client output. Return a detached response retaining fail
    and uncertain results. The separate policy consumer decides their effect;
    even complete passing coverage is not an overall verification verdict.
    """
    schemas = VNextSchemaRegistry()
    schemas.validate(obligations, 'vnext_semantic_obligations_v1')
    schemas.validate(response, 'vnext_semantic_coverage_v1')
    require(response['obligations_hash'] == _hash(obligations), 'semantic obligations binding changed')
    expected = {}
    for item in obligations['obligations']:
        subject = {key: value for key, value in item.items() if key != 'obligation_id'}
        identifier = content_identifier('sem', 'whetstone-semantic-obligation-v1',
                                        [obligations['bindings'], subject])
        require(item['obligation_id'] == identifier and identifier not in expected,
                'semantic obligation identity changed or duplicated')
        expected[identifier] = _hash(item)
    seen = set()
    for row in response['results']:
        identifier = row['obligation_id']
        require(identifier in expected and identifier not in seen,
                'unknown or duplicate semantic coverage obligation')
        require(row['obligation_hash'] == expected[identifier], 'semantic coverage endpoints changed')
        require(bool(row['evidence'].strip()), 'semantic coverage requires substantive evidence')
        seen.add(identifier)
    require(seen == set(expected), 'semantic coverage omitted required obligations')
    return deepcopy(response)
