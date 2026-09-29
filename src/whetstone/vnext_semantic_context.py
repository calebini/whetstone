"""Pure, complete context for a separately invoked semantic Verifier.

The caller validates committed registration and base authority. This component
replays their immutable inputs, constructs read-only context, and invokes no
client. It does not qualify a suite, certify independence, or grant a verdict.
"""
from dataclasses import dataclass

from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, decode_json, require, sha256_bytes
from whetstone.vnext_identity import creation_id, proposal_id
from whetstone.vnext_semantic_coverage import prepare_semantic_obligations
from whetstone.vnext_unit_preflight import prepare_unit_preflight


@dataclass(frozen=True)
class SemanticContext:
    raw: bytes

    @property
    def packet(self):
        return decode_json(self.raw)

    @property
    def input_hash(self):
        return sha256_bytes(self.raw)


def prepare_semantic_context(*, proposal_inputs, proposal, creation, creation_ref,
                             candidate_bytes, candidate_map, report, inventory):
    """Build exact context after the caller validates registration readback.

    proposal_inputs are the admitted transaction's prepare_unit_preflight
    arguments, reread by its storage owner. A supplied creation event must be
    the committed event, not merely a plausible uncommitted preparation. This
    pure builder validates its content/identity but cannot establish commitment.
    """
    preflight = prepare_unit_preflight(**proposal_inputs)
    job = proposal_inputs['job']
    schemas = VNextSchemaRegistry()
    schemas.validate(creation, 'candidate_creation_event_v1')
    schemas.validate(proposal.patch, 'patch_set_v2')
    require(proposal.patch['proposal_id'] == proposal_id(proposal.patch), 'semantic proposal identity changed')
    require(creation['creation_event_id'] == creation_id(creation), 'semantic creation identity changed')
    require(creation_ref == {
        'path': f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json",
        'hash': sha256_bytes(canonical_json_bytes(creation)),
    }, 'semantic creation reference changed')
    directory = f"rounds/round-{creation['round_number']}/candidates/{creation['candidate_id']}"
    require(creation['candidate_path'] == directory + '/candidate_unverified.md'
            and creation['candidate_section_identity_map_path'] == directory + '/section_identity_map_candidate.json',
            'semantic candidate locator differs from registered layout')
    require(creation['job_id'] == job['job_id']
            and creation['round_number'] == proposal_inputs['feedback']['round_number']
            and creation['transaction_id'] == preflight.plan['transaction_id']
            and creation['proposal_id'] == proposal.patch['proposal_id'],
            'semantic creation differs from admitted transaction')
    require(proposal.patch['editor'] == proposal_inputs['review']['editor'], 'semantic patch Editor changed')
    require(creation['candidate_hash'] == sha256_bytes(candidate_bytes)
            and creation['candidate_section_identity_map_hash'] == sha256_bytes(canonical_json_bytes(candidate_map)),
            'semantic registered candidate bytes or map changed')
    obligations = prepare_semantic_obligations(
        report=report, inventory=inventory,
        **{key: proposal_inputs[key] for key in ('job', 'authority', 'invariants', 'seed', 'seed_map', 'base', 'base_map')},
        base_inventory=preflight.inventory, plan=preflight.plan, proposal=proposal,
        candidate_bytes=candidate_bytes, candidate_map=candidate_map,
        candidate_map_path=creation['candidate_section_identity_map_path'],
        bindings=preflight.bindings, rules=preflight.rules)
    require(creation['candidate_id'] == obligations['bindings']['candidate_id'],
            'semantic creation candidate identity differs from replay')
    original = {finding['finding_id']: finding for finding in preflight.findings}
    derived = {finding['finding_id']: finding for finding in preflight.derived_tasks}
    findings = []
    for disposition in preflight.plan['finding_dispositions']:
        if not disposition['admitted_to_editing']:
            continue
        identifier = disposition['finding_id']
        source = derived[identifier]['original_finding_id'] if identifier in derived else identifier
        findings.append({
            'finding_id': identifier, 'original_finding': original[source],
            'derived_task': derived.get(identifier), 'evidence': preflight.evidence[source],
        })
    # Unit preflight has already required exactly the admitted dependency set
    # and validated every content hash. Keep the complete binding (including
    # its prospective horizon and role), rather than stripping it to prose.
    bindings = {binding['binding_id']: binding for binding in proposal_inputs['authority']['bindings']}
    context = [{'binding': bindings[key], 'content': raw.decode('utf-8')}
               for key, raw in sorted(proposal_inputs['context'].items())]
    packet = {
        'context_version': 'vnext-semantic-context-v1',
        'job': job,
        'suite': {'version': proposal_inputs['suite'].version, 'digest': proposal_inputs['suite'].digest},
        'review_configuration': proposal_inputs['review'],
        'base_pointer': proposal_inputs['base_pointer_ref'],
        'creation': creation, 'creation_ref': creation_ref,
        'seed': proposal_inputs['seed'].decode('utf-8'), 'seed_map': proposal_inputs['seed_map'],
        'base': proposal_inputs['base'].decode('utf-8'), 'base_map': proposal_inputs['base_map'],
        'candidate': candidate_bytes.decode('utf-8'), 'candidate_map': candidate_map,
        'base_inventory': preflight.inventory, 'candidate_inventory': inventory,
        'mutation_plan': preflight.plan, 'admitted_findings': sorted(findings, key=lambda row: row['finding_id']),
        'authority_map': proposal_inputs['authority'], 'scope_contract': proposal_inputs.get('scope'),
        'protected_invariants': proposal_inputs['invariants'], 'dependency_context': context,
        'operator_unit_decisions': [{'request': binding.request, 'response': binding.response} for binding in preflight.bindings],
        'editor_proposal': {
            'interpretation': 'Editor claims are untrusted evidence, not verification or authority.',
            'patch': proposal.patch,
            'payloads': [{'path': path, 'content': raw.decode('utf-8')} for path, raw in sorted(proposal.payloads.items())],
        },
        'preservation_report': report, 'semantic_obligations': obligations,
    }
    if proposal_inputs.get('system_entry') is not None:
        packet['system_entry']=proposal_inputs['system_entry']
        packet['editor_proposal']['interpretation']='System-only empty patch; no Editor was invoked. The scheduler binds metadata authority; independent verification is still required.'
    if 'system_metadata' in preflight.plan:
        from whetstone.vnext_assembly import assemble_bytes
        assembled=assemble_bytes(base=proposal_inputs['base'],section_map=proposal_inputs['base_map'],plan=preflight.plan,proposal=proposal)
        packet['system_version_operation']=assembled.version_operation
    if proposal_inputs.get('vertical') is not None:
        packet['vertical'] = proposal_inputs['vertical']
    if proposal_inputs.get('phase2') is not None:
        from whetstone.vnext_phase2_operator import supported, pins
        if supported(proposal_inputs['suite']):
            pins(proposal_inputs['suite'])
            packet['phase2'] = proposal_inputs['phase2']
    if proposal_inputs.get('semantic_followup') is not None:
        # The qualified preflight has reproduced the exact selected answer.
        # Include identical interpretation evidence for the independent role.
        prompt_packet=decode_json(preflight.prompt.rsplit('\n',1)[1].encode('utf-8'))
        packet['semantic_interpretation']=prompt_packet['semantic_interpretation']
    if proposal_inputs.get('phase2_repair') is not None:
        packet['repair'] = decode_json(proposal_inputs['phase2_repair'])
    # Canonical immutable bytes prevent a caller mutating nested dictionaries
    # after a request records the input hash. Each packet read is detached.
    return SemanticContext(canonical_json_bytes(packet))
