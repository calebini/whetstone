"""Exact V Reviewer inputs over one already proven original base."""
from copy import deepcopy

from whetstone.prompts import render_reviewer_prompt
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, content_identifier, require, sha256_bytes
from whetstone.vnext_review_protocol import ReviewPreflight, _decode_review
from whetstone.vnext_unit_preflight import input_projection


ALGORITHM = 'algorithms/vnext_verified_review_requests_v1.md'
SCHEMAS = frozenset({'vnext_review_request_v2', 'vnext_review_request_transport_v1',
    'vnext_review_invocation_v1', 'vnext_review_outcome_v1', 'vnext_review_result_v1',
    'vnext_review_response_v1', 'vnext_review_response_v1.codex', 'reviewer_feedback', 'vnext_finding_advice_v1'})


SCOPE_GUIDANCE = (
    'Classification identifier fields have distinct meanings:\n'
    '- feedback.affected_sections uses canonical_section_id values from base_section_map, not stable_section_id values.\n'
    '- authority_scope_ids uses declared authority_scopes from authority.bindings; these are not section IDs or scope surfaces.\n'
    '- source_authority_binding_ids uses binding_id values from authority.bindings. Cite only actual sources; a citation does not grant authority.\n'
    '- scope_surface_ids uses only id values from scope.scope_surfaces. If scope is null, every classification MUST use "scope_surface_ids": []. '
    'Do not copy canonical_section_id or stable_section_id values into this field.\n'
    'When a scope contract exists, identify its applicable declared surfaces without inventing IDs; unresolved scope requires scope_change advice, not invented authority. '
    'Absent scope does not remove authority, invariant, or operator-decision requirements.\n'
)


def validate_verified_review_contract(suite):
    entries = {entry['path']: entry for family in ('algorithms', 'schemas') for entry in suite.manifest[family]}
    paths = {ALGORITHM} | {'schemas/' + name + '.schema.json' for name in SCHEMAS}
    require(paths <= entries.keys(), 'verified Reviewer contracts are outside supported suite')
    for path in paths:
        require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == entries[path]['sha256'],
                'installed verified Reviewer contract differs from pinned suite', path)


def prepare_verified_review(inputs, *, round_number, profile):
    reader, values, pointer = inputs.values()
    require(values['job']['editing_mode'] == 'verified_promotion', 'verified Reviewer requires V mode')
    validate_verified_review_contract(reader.suite)
    if values['review']['review_mode'] == 'vertical':
        from whetstone.vnext_verified_vertical_phase1 import pins
        pins(reader.suite)
        require(values['review']['workflow'] == 'standard', 'vertical V review requires standard workflow')
    require(type(round_number) is int and round_number > 0, 'invalid verified Reviewer round')
    require(profile in {row['name'] for row in values['review']['profiles']}, 'Reviewer profile is outside pinned configuration')
    from whetstone.vnext_review_configuration import focused_profile
    focused = focused_profile(values['review'])
    require(focused is None or profile == focused, 'Reviewer profile differs from immutable focused selection')
    context = []
    for binding in values['authority']['bindings']:
        if binding['role'] in {'mutable_target', 'excluded'}: continue
        raw = reader.raw({'path': binding['path'], 'hash': binding['content_hash']})
        context.append({'binding': deepcopy(binding), 'content': raw.decode('utf-8')})
    arguments = {key: values[key] for key in ('job', 'authority', 'invariants', 'seed', 'seed_map', 'base',
                                              'base_map', 'base_pointer_ref', 'scope', 'review')}
    arguments.update(round_number=round_number, profile=profile, context=context, suite_digest=reader.suite.digest)
    if values.get('base_inventory') is not None: arguments['base_inventory'] = deepcopy(values['base_inventory'])
    if inputs.launch_package is not None: arguments['launch_package'] = deepcopy(inputs.launch_package)
    digest = sha256_bytes(canonical_json_bytes(input_projection(arguments)))
    prompt = render_reviewer_prompt(profile=profile, draft=values['base'].decode('utf-8'),
        draft_path=pointer['verified_draft_path'], reference_context_paths=[], scope_contract_path=None,
        section_ids=[row['canonical_section_id'] for row in values['base_map']['sections']],
        round_number=round_number, draft_hash_value=pointer['verified_draft_hash'])
    packet = {key: arguments[key] for key in ('job', 'authority', 'invariants', 'scope', 'review', 'context',
                                              'round_number', 'profile', 'base_pointer_ref')}
    packet.update(seed=values['seed'].decode('utf-8'), seed_section_map=values['seed_map'],
                  base=values['base'].decode('utf-8'), base_section_map=values['base_map'],
                  base_draft_hash=pointer['verified_draft_hash'])
    prompt += '\nReturn a vnext-review-response-v1 object with feedback and one classification advice item per source feedback_id.\n'
    prompt += 'Review the exact base draft and its section map. The original seed is retained context.\n'
    prompt += 'Classification advice cannot authorize edits, grants, authority or scope changes, candidates, or verification.\n'
    prompt += 'Bound context retains its declared roles; excluded documents are unavailable.\n'
    prompt += 'Feedback must retain the exact round, profile, base draft hash and configured Reviewer identity.\n'
    packet_text = canonical_json_bytes(packet).decode('utf-8')
    legacy_prompt = prompt + packet_text
    prompt += SCOPE_GUIDANCE + packet_text
    # Journal replay must reproduce the original prompt exactly. Recognize only
    # the previous deterministic rendering, never arbitrary retained instructions.
    request_id = content_identifier('req', 'whetstone-logical-client-request-v1',
        [values['job']['job_id'], 'reviewer', 'phase1', 'review', round_number, profile])
    try:
        original = inputs.store.read('rounds/client_requests/' + request_id + '/original_prompt.txt')
    except FileNotFoundError:
        original = None
    if original == legacy_prompt.encode('utf-8'):
        prompt = legacy_prompt
    inputs.guard()
    return ReviewPreflight(digest, arguments, prompt)


def decode_verified_review(raw, preflight, *, feedback_path):
    values = preflight.arguments
    return _decode_review(raw, preflight, feedback_path=feedback_path,
                          base=values['base'], section_map=values['base_map'])
