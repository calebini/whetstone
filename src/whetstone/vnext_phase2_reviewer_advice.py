"""Suite-pinned Reviewer guidance, bound by the orchestrator to exact feedback."""
from copy import deepcopy

from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_phase2_reviewer_advice_v1.md'
RESPONSE_SCHEMA = 'vnext_phase2_rubric_response_v2'


def supported(suite):
    return any(row['path'] == ALGORITHM for row in suite.manifest['algorithms'])


def pins(suite):
    entries = {r['path']:r['sha256'] for group in ('algorithms', 'schemas') for r in suite.manifest[group]}
    for path in (ALGORITHM, 'schemas/'+RESPONSE_SCHEMA+'.schema.json',
                 'schemas/vnext_finding_advice_v1.schema.json'):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'Reviewer advice contract is absent or changed', path)


def bind(suite, inputs, feedback, feedback_path, classifications):
    """The model supplies hints only; all run and authority references are computed."""
    pins(suite)
    job = inputs['job']
    advice = dict(schema_version='vnext-finding-advice-v1', job_id=job['job_id'],
        base_draft_hash=sha256_bytes(inputs['draft'].encode('utf-8')),
        feedback=dict(path=feedback_path, hash=sha256_bytes(canonical_json_bytes(feedback))),
        authority_map_hash=job['authority_map_hash'], scope_contract_hash=job['scope_contract_hash'],
        protected_invariants_hash=job['protected_invariants_hash'], findings=deepcopy(classifications))
    # Validate exact coverage and authority citations before accepting the review.
    # Policy and destructive effects remain operator work, even if mislabelled.
    classify_feedback(feedback=feedback, feedback_ref=advice['feedback'], advice=advice,
        job=job, authority=inputs['authority'], invariants=inputs['invariants'],
        base=inputs['draft'].encode('utf-8'), section_map=inputs['base_map'], scope=inputs['scope'])
    return advice
