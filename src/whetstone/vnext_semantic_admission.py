"""Read-only registered-candidate admission for the unactivated Verifier.

This reader does not infer completion, permit a client call, choose a candidate,
or change a decision. Its caller supplies the exact candidate and separately
enforces current decision finality and durable request/continuation policy.
"""
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests, proposal_inputs
from whetstone.vnext_proposals import PreparedProposal
from whetstone.vnext_semantic_context import prepare_semantic_context
from whetstone.vnext_semantic_protocol import POLICY_VERSION


SEMANTIC_SCHEMAS = frozenset({
    'semantic_verification_client_v2', 'semantic_verification_client_v2.codex', 'semantic_verification_v2',
    'vnext_semantic_authority_request_v1', 'vnext_semantic_obligations_v1', 'vnext_semantic_coverage_v1',
})
SEMANTIC_ALGORITHMS = ('vnext_semantic_context_v1', 'vnext_semantic_coverage_v1', 'vnext_semantic_policy_v2')


def load_registered_semantic_context(store, *, admission, candidate_id):
    """Reproduce the exact context from committed, suite-bound local evidence.

    Current seed-only proposal admission remains the underlying base reader.
    Historical promoted-base loading needs the later promotion consumer; this
    reader never replaces a missing base with the current draft or reseeds it.
    """
    reader, values = admission._base(store.read)
    job = values['job']
    require(job['semantic_verifier_policy_version'] == POLICY_VERSION, 'unsupported semantic verifier policy version')
    pinned = {entry['path']: entry for entry in reader.suite.manifest['schemas']}
    require({'schemas/' + name + '.schema.json' for name in SEMANTIC_SCHEMAS} <= pinned.keys(),
            'semantic consumer schema is outside supported suite')
    algorithms = {entry['path']: entry for entry in reader.suite.manifest['algorithms']}
    for name in SEMANTIC_ALGORITHMS:
        path = 'algorithms/' + name + '.md'
        require(path in algorithms, 'semantic consumer algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == algorithms[path]['sha256'],
                'installed semantic algorithm differs from pinned suite', path)
    registry = registry_for_proposal_requests(store, load_inputs=admission.load_inputs,
                                              validate_authority=admission.validate_authority)
    view = registry.inspect()
    require(not view.orphans, 'semantic admission requires candidate registration recovery first')
    matches = [event for event in view.events if event['candidate_id'] == candidate_id]
    require(len(matches) == 1, 'semantic candidate lacks exact committed registration')
    creation = matches[0]
    creation_ref = {
        'path': f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json",
        'hash': sha256_bytes(canonical_json_bytes(creation)),
    }
    arguments = proposal_inputs(admission.load_inputs,store.read,creation['round_number'],creation['proposal_id'])
    prefix = f"rounds/round-{creation['round_number']}/proposals/{creation['proposal_id']}"
    patch, _ = registry._json(prefix + '/proposed_patch.json', 'patch_set_v2')
    payloads = {operation['payload']['path']: store.read(prefix + '/' + operation['payload']['path'])
                for operation in patch['operations'] if operation['payload']['path'] is not None}
    directory = creation['candidate_path'].rsplit('/', 1)[0]
    candidate_map, _ = registry._json(creation['candidate_section_identity_map_path'], 'section_identity_map_v2')
    report, _ = registry._json(directory + '/preservation_report.json', 'preservation_report_v2')
    require(report['result'] == 'pass', 'semantic admission requires deterministic pass')
    inventory, _ = registry._json(directory + '/preservation_inventory_candidate.json', 'vnext_preservation_inventory_v2')
    context = prepare_semantic_context(
        proposal_inputs=arguments, proposal=PreparedProposal(patch, payloads), creation=creation, creation_ref=creation_ref,
        candidate_bytes=store.read(creation['candidate_path']), candidate_map=candidate_map, report=report, inventory=inventory)
    admission.validate_authority(store.read)
    require(store.read(creation_ref['path']) == canonical_json_bytes(creation), 'semantic creation changed during admission')
    return context
