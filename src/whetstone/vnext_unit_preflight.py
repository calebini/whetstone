"""Full inventory/assertion preflight for the isolated v2 proposal consumer.

The storage caller admits descriptor capabilities and committed base authority.
This component freezes their exact input values, classifies source feedback,
derives inventory-bound plans, and refuses invalid programs before Editor work.
It does not upgrade a job admitted under the frozen first suite.
"""
from copy import deepcopy
from dataclasses import dataclass
import re

from whetstone.vnext_review_configuration import validate as validate_review_configuration
from whetstone.vnext_assertions import validate_assertion_program
from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_discovery import discovery_rules
from whetstone.vnext_inventory import seed_inventory, validate_seed_inventory
from whetstone.vnext_proposal_protocol import _proposal_prompt_packet
from whetstone.vnext_sections import seed_section_map
from whetstone.vnext_unit_authorization import bind_unit_response
from whetstone.vnext_unit_lineage import validate_inventory_facts
from whetstone.vnext_unit_proposals import build_unit_plan

PAYLOAD_HASH_GUIDANCE = (
    'Compute each payload hash with a local read-only calculation from the same in-memory '
    'Unicode string used as payloads[].content. Encode that string as UTF-8, preserving '
    'punctuation and trailing newlines. Build the response JSON and hash from that one '
    'string; do not manually transcribe a separate Base64 copy or guess a digest. '
    'Before returning, parse the serialized JSON and recompute SHA-256 from every '
    'referenced payload content to confirm the declared hashes. Do not edit files.\n'
)


CORRESPONDENCE_GUIDANCE = (
    'Explicit correspondence is not required for every replacement. Whetstone inventories '
    'the returned payload and automatically matches unchanged units and a single changed '
    'same-kind unit between unchanged alignment anchors. For a local clarification that '
    'preserves paragraph/line structure and has this unambiguous mapping, use '
    'unit_correspondence=[]. A missing precomputed inventory of your not-yet-written '
    'payload is not by itself a reason to decline. Preserve layout when it fits the '
    'authorized correction; do not change meaning to force alignment. Split/merge or '
    'otherwise unresolved mappings still require exact selectors; never guess them. '
    'Automatic matching does not prove semantic preservation or waive validation.\n'
)


def input_projection(value):
    """Exact snapshots: bytes remain distinguishable from client JSON objects."""
    if isinstance(value,bytes):return ['bytes',sha256_bytes(value)]
    if isinstance(value,dict):return ['object',[[key,input_projection(v)] for key,v in sorted(value.items())]]
    if isinstance(value,(list,tuple)):return ['array',[input_projection(v) for v in value]]
    return ['scalar',value]


@dataclass(frozen=True)
class UnitProposalPreflight:
    input_hash: str
    plan: dict
    inventory: dict
    rules: list
    bindings: tuple
    findings: list
    evidence: dict
    derived_tasks: list
    prompt: str


def _prepare_unit_preflight(*,job,authority,invariants,seed,seed_map,base,base_map,review,
                           feedback,feedback_ref,advice,constraints,context,suite,
                           base_pointer_ref,scope=None,base_inventory=None,decisions=(),semantic_followup=None,phase2=None,phase2_repair=None,vertical=None):
    if semantic_followup is not None:
        if phase2 is not None:
            from whetstone.vnext_phase2_operator import pins
            pins(suite)
        arguments={key:value for key,value in locals().copy().items()
                   if (key != 'vertical' or vertical is not None) and key not in {'semantic_followup', 'pins'} and (key != 'phase2' or phase2 is not None)
                   and (key != 'phase2_repair' or phase2_repair is not None)}
        from whetstone.vnext_semantic_followup_preflight import prepare_followup_preflight
        return prepare_followup_preflight(arguments,semantic_followup)
    if phase2_repair is not None:
        arguments={key:value for key,value in locals().copy().items() if (key != 'vertical' or vertical is not None) and key not in {'semantic_followup','phase2_repair'}}
        from whetstone.vnext_phase2_repair import prepare
        return prepare(arguments,phase2_repair)
    # Omitting the new optional consumer retains the exact original preimage.
    raw_arguments={key:value for key,value in locals().copy().items() if (key != 'vertical' or vertical is not None) and key not in {'suite','semantic_followup','phase2_repair'} and (key != 'phase2' or phase2 is not None)}
    digest=sha256_bytes(canonical_json_bytes(input_projection({**raw_arguments,
        'suite_version':suite.version,'suite_digest':suite.digest})))
    rules=discovery_rules(invariants)
    registry=VNextSchemaRegistry();validate_review_configuration(review, registry)
    require(job['editing_mode'] in {'proposal_only','verified_promotion'},'job mode prohibits Editor work')
    require(sha256_bytes(canonical_json_bytes(review))==job['review_configuration_hash'], 'preflight role configuration changed')
    require(sha256_bytes(seed)==job['seed_draft']['hash'],'preflight seed bytes changed')
    require(sha256_bytes(canonical_json_bytes(invariants))==job['protected_invariants_hash'],'preflight invariant/rule binding changed')
    require(set(base_pointer_ref)=={'path','hash'},'preflight requires its admitted base pointer reference')
    require(isinstance(base_pointer_ref['path'],str) and bool(base_pointer_ref['path'])
            and isinstance(base_pointer_ref['hash'],str) and re.fullmatch(r'[0-9a-f]{64}',base_pointer_ref['hash']) is not None,
            'preflight base pointer reference is malformed')
    mutable=[b for b in authority['bindings'] if b['role']=='mutable_target']
    require(len(mutable)==1,'preflight requires one mutable target')
    require(seed_map==seed_section_map(seed,job,mutable[0]['binding_id']),'preflight seed map does not reproduce')
    validate_assertion_program(invariants,seed,seed_map)
    profiles = review['profiles']
    if phase2 is not None:
        from whetstone.vnext_verified_phase2_preflight import validate_phase2_context
        profiles = validate_phase2_context(phase2, job=job, review=review, feedback=feedback,
            base_map=base_map, base_pointer_ref=base_pointer_ref, suite=suite)
    reviewer = review['reviewer']
    if vertical is not None:
        require(phase2 is None, 'vertical Phase 1 cannot carry Phase 2 context')
        from whetstone.vnext_verified_vertical_phase1 import validate_context, MERGER
        validate_context(vertical, suite=suite, job=job, review=review, feedback=feedback, advice=advice, base_pointer=base_pointer_ref)
        profiles, reviewer = [{'name': 'vertical'}], MERGER
    require(feedback['reviewer']==reviewer and feedback['profile'] in {p['name'] for p in profiles},
            'preflight feedback differs from pinned Reviewer or profile')
    require(scope is None or (scope['status']=='approved' and scope['approval']['approved']), 'preflight scope must be approved')
    if base_inventory is None:
        require(base==seed and base_map==seed_map,'current candidate base requires its committed inventory')
        inventory=seed_inventory(base,base_map,job,rules=rules)
    else:
        inventory=deepcopy(base_inventory)
        validate_inventory_facts(inventory,base,base_map,rules=rules)
        require(inventory['seed_draft_hash']==job['seed_draft']['hash'],'inventory belongs to a different seed')
        if inventory['base_inventory_hash'] is None:validate_seed_inventory(inventory,base,base_map,job,rules=rules)
    findings,evidence=classify_feedback(feedback=feedback,feedback_ref=feedback_ref,advice=advice,job=job,
        authority=authority,invariants=invariants,base=base,section_map=base_map,scope=scope)
    require(not any(e['requires_new_job'] for e in evidence.values()),'immutable policy requires a new job')
    by_finding={f['finding_id']:f for f in findings};bindings=[]
    for decision in decisions:
        require(set(decision)=={'finding_id','request','response','feedback_refs'},'invalid unit decision bundle')
        key=decision['finding_id'];require(key in by_finding,'unit decision references unknown source finding')
        require(decision['feedback_refs']==evidence[key]['feedback_refs'],'unit decision source references changed')
        bindings.append(bind_unit_response(decision['response'],decision['request'],job=job,base_hash=sha256_bytes(base),
            finding=by_finding[key],targets=by_finding[key]['target_section_ids'],feedback_refs=evidence[key]['feedback_refs'],
            inventory=inventory,section_map=base_map,suite=suite))
    constraints=deepcopy(constraints)
    normative={b['binding_id'] for b in authority['bindings'] if b['role'] in {'mutable_target','normative_authority'}
               and set(b['authority_scopes'])&set(mutable[0]['authority_scopes'])}
    assertion_sources={key for a in invariants['assertions'] for key in a['source_authority_binding_ids']}
    constraints['required_context_binding_ids']=sorted(set(constraints['required_context_binding_ids'])|normative|assertion_sources)
    plan,derived,responses=build_unit_plan(inventory=inventory,job=job,authority=authority,section_map=base_map,
        findings=findings,constraints=constraints,suite=suite,decisions=decisions)
    derived_by_id={task['finding_id']:task for task in derived};by_response={r['response_id']:r for r,_ in responses}
    details=[]
    for finding in plan['finding_dispositions']:
        if not finding['admitted_to_editing']:continue
        identifier=finding['finding_id'];original=derived_by_id[identifier]['original_finding_id'] if identifier in derived_by_id else identifier
        details.append({'finding_id':identifier,'original_finding_id':original,'source_findings':evidence[original]['source_items'],
                        'feedback_refs':evidence[original]['feedback_refs'],'operator_response':by_response.get(finding['decision_response_id'])})
    packet=_proposal_prompt_packet(plan=plan,base=base,section_map=base_map,authority=authority,invariants=invariants,
                                   context=context,finding_details=details,scope=scope)
    packet.update(base_inventory=inventory,discovery_rules=rules,editor=deepcopy(review['editor']),
        operator_unit_decisions=[{'request':b.request,'response':b.response} for b in bindings])
    if phase2 is not None: packet['phase2'] = deepcopy(phase2)
    if vertical is not None: packet['vertical'] = deepcopy(vertical)
    prompt=(
        'Produce one JSON object with schema_version = vnext-proposal-response-v2, patch and payloads.\n'
        'The patch follows patch-set-client-v2. proposal_id is null, operation IDs are local labels, '
        'and dependencies name those labels. Copy all exact job, transaction, base and plan bindings.\n'
        'payloads is an array of {path, content}; content is exact Markdown and its patch hash is SHA-256 '
        'of the UTF-8 bytes. Return each referenced payload exactly once.\n'
        + PAYLOAD_HASH_GUIDANCE +
        'Every operation includes unit_correspondence, empty when unnecessary. For replacement split/merge '
        'or otherwise unresolved mapping, name exact base_unit_ids and payload_units selectors '
        '{kind, ordinal, content_hash}. Ordinal counts the complete raw payload inventory, including '
        'primary lines and overlapping lexical facets. Endpoints cannot be reused. '
        'A correspondence claim establishes no equivalence, deletion permission or verification.\n'
        + CORRESPONDENCE_GUIDANCE +
        'The full base inventory includes non-addressable preamble units. Edit only the admitted section '
        'targets and findings. Respect the operation and actual section/unit budgets, invariant assertions '
        'and exact named-unit grants. Do not infer approval from context, return a full replacement draft, '
        'edit files or claim verification. Decline admitted work explicitly if its exact authorized '
        'correction cannot be proposed. Context keeps its declared authority role and cannot expand scope.\n'
        +canonical_json_bytes(packet).decode('utf-8'))
    return UnitProposalPreflight(digest,deepcopy(plan),deepcopy(inventory),rules,tuple(bindings),findings,evidence,derived,prompt)


def prepare_unit_preflight(**arguments):
    if arguments.get('system_entry') is not None:
        from whetstone.vnext_version_entry import preflight
        return preflight(arguments)
    result = _prepare_unit_preflight(**arguments)
    from whetstone.vnext_version_operations import ASSEMBLER, anchors, pins, plan_context
    if arguments['job']['assembler_version'] != ASSEMBLER:
        return result
    pins(arguments['suite'])
    anchors(arguments['base'])
    from dataclasses import replace
    from whetstone.vnext_contracts import decode_json
    from whetstone.vnext_identity import transaction_id
    context = plan_context(phase='phase_2' if arguments.get('phase2') is not None else 'phase_1',
        transition='round',source=arguments['feedback_ref'],base_pointer=arguments['base_pointer_ref'])
    plan = deepcopy(result.plan)
    require('system_metadata' not in plan or plan['system_metadata']==context, 'system metadata authority changed')
    plan.update(schema_version='mutation-plan-v4',system_metadata=context)
    responses={b.response['response_id']:b.response_hash for b in result.bindings if b.response['authorized_effects']}
    plan['transaction_id']=transaction_id(plan,responses)
    VNextSchemaRegistry().validate(plan,'mutation_plan_v4')
    prefix, raw = result.prompt.rsplit('\n',1)
    packet = decode_json(raw.encode())
    packet.update(mutation_plan=plan,mutation_plan_hash=sha256_bytes(canonical_json_bytes(plan)))
    prompt=prefix+'\nVersion/status anchors are Orchestrator-owned. Preserve them exactly in Editor payloads.\n'+canonical_json_bytes(packet).decode()
    return replace(result,plan=plan,prompt=prompt,
        input_hash=sha256_bytes(canonical_json_bytes(['vnext-version-preflight-v1',result.input_hash,context])))
