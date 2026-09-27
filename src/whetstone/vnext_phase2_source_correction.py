"""Pinned eligibility for ordinary source correction during declaration review."""
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_verified_phase2_source_correction_v1.md'


def supported(suite):
    return any(row['path'] == ALGORITHM for row in suite.manifest['algorithms'])


def pins(suite):
    from whetstone.vnext_phase2_operator import pins as operator_pins
    operator_pins(suite)
    installed = {row['path']: row['sha256'] for family in ('algorithms', 'schemas')
                 for row in suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/vnext_phase2_review_request_v4.schema.json',
                 'schemas/vnext_phase2_consumption_v4.schema.json'):
        require(path in installed and installed[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'Phase 2 source-correction contract is absent or changed', path)


def source_findings(bound, review):
    """Do not infer a separable source task by dropping parts of a finding."""
    sections = {row['canonical_section_id'] for row in bound.inputs['base_map']['sections']}
    rows = review['feedback']['feedback']
    gap_sources = {row['source_issue_id'] for row in review.get('rubric_findings',[]) if row['gap']['blocking_convergence']}
    attributed_sources = {row['source_issue_id'] for row in review.get('rubric_findings',[])}
    from whetstone.vnext_phase2_targets import allowed_major
    config=bound.inputs.get('configuration')
    actionable = [row for row in rows if row['in_scope']
                  and (row['normalized_severity'] in {'major', 'blocker'} or row['issue_id'] in gap_sources)
                  and not (config and config['schema_version']=='vnext-phase2-configuration-v2' and allowed_major(row,config))]
    return bool(actionable) and all(row['affected_sections']
        and set(row['affected_sections']) <= sections
        and all(row[key] is None for key in ('authority_impact', 'determinism_impact', 'invariant_violated'))
        and (row['rubric_impact'] is None or row['issue_id'] in attributed_sources)
        for row in rows if row['in_scope'])
