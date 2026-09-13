"""Exact operator-response binding for non-promoting mutation preparation.

These helpers adopt an explicitly supplied operator response. They never infer
approval from Reviewer/Editor text, a timeout, an omitted response or a default.
"""
from copy import deepcopy

from whetstone import vnext_identity as ids
from whetstone.identity import issue_fingerprint, issue_id
from whetstone.vnext_contracts import (
    VNextSchemaRegistry, canonical_json_bytes, content_identifier, require, sha256_bytes,
)

EFFECTS = {'none', 'clarification', 'add', 'remove', 'strengthen', 'weaken',
           'authority_change', 'scope_change'}


def decision_request(*, job, base_hash, finding, targets, options, feedback_refs):
    """Build an exact request; option effects and unit IDs are explicit inputs.

    The Orchestrator supplies concrete options after classification. Creating a
    request is not approval of any option, nor authorization to alter a job input.
    """
    require(finding['classification'] != 'editor_fixable', 'decision requires an unresolved classified finding')
    require(bool(targets) and len(targets) == len(set(targets)), 'decision requires unique exact section targets')
    require(bool(options) and len({o['option_id'] for o in options}) == len(options), 'duplicate or absent decision options')
    for option in options:
        require(set(option['authorized_effects']) <= EFFECTS, 'unknown authorized effect')
        require(not option['authorized_deletion_unit_ids'] or 'remove' in option['authorized_effects'],
                'unit deletion requires an explicit removal effect')
    packet = {'schema_version': 'vnext-mutation-decision-request-v1',
              'job_id': job['job_id'], 'base_draft_hash': base_hash,
              'authority_map_hash': job['authority_map_hash'],
              'scope_contract_hash': job['scope_contract_hash'],
              'protected_invariants_hash': job['protected_invariants_hash'],
              'finding_id': finding['finding_id'],
              'source_feedback_ids': sorted(finding['source_feedback_ids']),
              'classification': finding['classification'],
              'target_section_ids': sorted(targets),
              'feedback_refs': sorted(deepcopy(feedback_refs), key=lambda r: (r['path'], r['hash'])),
              'options': sorted(deepcopy(options), key=lambda o: o['option_id'])}
    packet['decision_id'] = content_identifier('decision', 'whetstone-mutation-decision-v1', [packet])
    VNextSchemaRegistry().validate(packet, 'vnext_mutation_decision_request_v1')
    return packet


def validate_request(request, *, job, base_hash, finding, targets, feedback_refs):
    VNextSchemaRegistry().validate(request, 'vnext_mutation_decision_request_v1')
    expected = decision_request(job=job, base_hash=base_hash, finding=finding,
                                targets=targets, options=request['options'], feedback_refs=feedback_refs)
    require(request == expected, 'decision request identity, inputs or provenance changed')
    return sha256_bytes(canonical_json_bytes(request))


def bind_response(response, request, *, job, base_hash, finding, targets, feedback_refs, suite):
    """Validate an already canonical operator artifact against its exact request."""
    digest = validate_request(request, job=job, base_hash=base_hash, finding=finding,
                              targets=targets, feedback_refs=feedback_refs)
    suite.registry.validate(response, 'operator_decision_response_v1')
    expected = {'job_id': job['job_id'], 'decision_id': request['decision_id'],
                'decision_request_hash': digest, 'base_draft_hash': base_hash,
                'authority_map_hash': job['authority_map_hash'], 'scope_contract_hash': job['scope_contract_hash']}
    require(all(response[key] == value for key, value in expected.items()), 'operator response is stale or bound to another request')
    require(response['response_id'] == ids.response_id(response), 'operator response identity differs')
    option = next((o for o in request['options'] if o['option_id'] == response['selected_option_id']), None)
    require(option is not None, 'operator selected an unknown option')
    require(response['authorized_effects'] == option['authorized_effects']
            and response['authorized_deletion_unit_ids'] == option['authorized_deletion_unit_ids'],
            'operator effects or deletion units differ from the selected exact option')
    require(bool(response['decided_by'].strip()) and bool(response['rationale'].strip()),
            'operator response requires an actor and rationale')
    return deepcopy(response), sha256_bytes(canonical_json_bytes(response))


def derived_task(finding, response, request):
    """Retain the original classification and construct a distinct canonical issue.

    Call only after bind_response; plan admission must retain the response hash
    and exact request alongside this derived task. An empty-effect option is a
    deferral, not editor authorization.
    """
    require(bool(response['authorized_effects']), 'a deferred response cannot create editing work')
    require(response['decision_id'] == request['decision_id']
            and request['finding_id'] == finding['finding_id'], 'derived task provenance differs')
    claim = canonical_json_bytes({'original_finding_id': finding['finding_id'],
                                  'operator_response_id': response['response_id'],
                                  'decision_request_hash': response['decision_request_hash']}).decode()
    fingerprint = issue_fingerprint('operator_authorized_task', request['target_section_ids'], None, claim)
    return {'finding_id': issue_id(fingerprint), 'issue_fingerprint': fingerprint,
            'source_feedback_ids': sorted(finding['source_feedback_ids']),
            'classification': 'editor_fixable', 'admitted_to_editing': True,
            'decision_response_id': response['response_id'],
            'original_finding_id': finding['finding_id'],
            'decision_request_hash': response['decision_request_hash'],
            'target_section_ids': list(request['target_section_ids'])}
