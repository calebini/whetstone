"""Pure Phase 2 profile context check; provenance remains the storage owner's duty."""
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes


def validate_phase2_context(context, *, job, review, feedback, base_pointer_ref, suite):
    path = 'algorithms/vnext_verified_phase2_round_v1.md'
    pins = {row['path']: row for row in suite.manifest['algorithms']}
    require(path in pins and pins[path]['sha256'] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
            'Phase 2 proposal context is outside supported suite')
    require(job['editing_mode'] == 'verified_promotion' and set(context) == {'configuration', 'request'},
            'invalid Phase 2 proposal context')
    config, request = context['configuration'], context['request']
    suite.registry.validate(config, 'vnext_phase2_configuration_v1')
    later = request.get('schema_version') == 'vnext-phase2-review-request-v2'
    if later:
        from whetstone.vnext_verified_phase2_sequence import ALGORITHM
        require(ALGORITHM in pins and pins[ALGORITHM]['sha256'] == sha256_bytes(confined_file(CONTRACT_ROOT,ALGORITHM).read_bytes()),
                'Phase 2 continuation preflight is outside supported suite')
    suite.registry.validate(request, 'vnext_phase2_review_request_v2' if later else 'vnext_phase2_review_request_v1')
    require(config['job_id'] == job['job_id'] == request['job_id']
            and config['review_configuration']['hash'] == job['review_configuration_hash']
            and request['configuration']['hash'] == sha256_bytes(canonical_json_bytes(config))
            and all(config[key] == review[key] for key in ('workflow','review_mode','profile_set','reviewer','editor','verifier')),
            'Phase 2 proposal changes immutable configuration')
    index = request['step']['index']-1 if later else 0
    require(0 <= index < len(config['profiles']), 'Phase 2 step is outside configuration')
    used = request['step']['rounds_used'] if later else 0
    require(used < config['profiles'][index]['budget'], 'Phase 2 request exceeds profile budget')
    require(request['base_pointer'] == base_pointer_ref and request['round_number'] == feedback['round_number']
            and request['step'] == dict(index=index+1, profile=config['profiles'][index]['name'],
                round_budget=config['profiles'][index]['budget'], rounds_used=used, pass_number=used+1)
            and feedback['profile'] == request['step']['profile'], 'Phase 2 proposal feedback differs from bound request')
    return config['profiles']
