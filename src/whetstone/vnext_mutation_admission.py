"""Read-only seed-transaction admission and an isolated proposal exercise.

Public proposal mode remains gated on 18.5 and D8. These APIs qualify the 18.4
non-promoting path with injected clients; they never register or promote.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from whetstone.vnext_review_configuration import read as read_review_configuration
from whetstone import vnext_identity as ids
from whetstone.preservation_inventory import build_inventory
from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import (VNextSchemaRegistry, canonical_json_bytes, confined_file,
    decode_json, require, sha256_bytes, validate_contract_suite)
from whetstone.vnext_plans import build_plan
from whetstone.vnext_proposal_protocol import proposal_prompt, capture_response
from whetstone.vnext_sections import section_spans, seed_section_map
from whetstone.vnext_storage import publish, writer
from whetstone.vnext_validation import validate_bootstrap, validate_seed_pointer, validate_pointer_snapshot


def _packet(reader,reference,schema):
    raw=reader.raw(reference);packet=decode_json(raw)
    require(raw==canonical_json_bytes(packet), 'noncanonical admission input')
    VNextSchemaRegistry().validate(packet,schema)
    return packet


def addressable_seed_units(base,mapping):
    """D6 identities for units inside real seed sections, never synthetic targets.

    Preamble bytes have no editing address in this slice. This catalog is not a
    complete candidate preservation inventory and cannot prove preservation.
    """
    spans=section_spans(base);sections=mapping['sections'];counts={};catalog={};base_hash=sha256_bytes(base)
    for unit in build_inventory(base,path='draft.md')['units']:
        owners=[i for i,span in enumerate(spans) if span.start<=unit['byte_start']<span.end]
        if not owners:continue
        owner=sections[max(owners)]['stable_section_id'];kind=unit['kind']
        key=(owner,kind);counts[key]=counts.get(key,0)+1
        identifier=ids.seed_unit_id(base_hash,owner,kind,counts[key])
        require(identifier not in catalog,'seed unit identity collision')
        catalog[identifier]={'owning_section_id':owner,'kind':kind,'byte_start':unit['byte_start'],
                            'byte_end':unit['byte_end'],'content_hash':unit['content_sha256'],
                            'protected':bool(base[unit['byte_start']:unit['byte_end']].strip())}
    return catalog


@dataclass
class MutationAdmission:
    reader: object
    job: dict
    authority: dict
    invariants: dict
    scope: dict | None
    review: dict
    base: bytes
    mapping: dict
    pointer_ref: dict
    findings: list
    evidence: dict
    feedback_ref: dict
    advice_ref: dict | None
    units: dict


def inspect_admission(root,*,descriptor_ref,review_ref,feedback_ref,advice_ref=None):
    suite=validate_contract_suite()
    reader,job,authority,invariants=validate_bootstrap(root,descriptor_ref,suite,review_configuration_ref=review_ref)
    require(job['editing_mode'] in {'proposal_only','verified_promotion'}, 'job mode prohibits a proposal')
    review=read_review_configuration(reader, review_ref)
    path='rounds/current_verified.json';raw=confined_file(reader.root,path).read_bytes()
    pointer_ref={'path':path,'hash':sha256_bytes(raw)}
    pointer=validate_pointer_snapshot(reader,pointer_ref)
    require(pointer['promotion_ordinal']==0,'18.4 isolated exercise requires verified seed authority')
    map_ref={'path':pointer['verified_section_identity_map_path'],'hash':pointer['verified_section_identity_map_hash']}
    seed_path=Path(job['seed_draft']['path'])
    if seed_path.is_absolute():seed_path=seed_path.relative_to(reader.root)
    validate_seed_pointer(pointer,{**job,'seed_draft':{'path':seed_path.as_posix(),'hash':job['seed_draft']['hash']}},map_ref)
    base=reader.raw({'path':pointer['verified_draft_path'],'hash':pointer['verified_draft_hash']})
    mapping=reader.json(map_ref,'section_identity_map_v1')
    mutable=next(b for b in authority['bindings'] if b['role']=='mutable_target')
    require(mapping==seed_section_map(base,job,mutable['binding_id']), 'seed map does not reproduce')
    scope=reader.json({'path':job['scope_contract_path'],'hash':job['scope_contract_hash']},'scope_contract') if job['scope_contract_hash'] else None
    feedback=_packet(reader,feedback_ref,'reviewer_feedback')
    require(feedback['reviewer']==review['reviewer'], 'feedback Reviewer identity differs from pinned role')
    require(feedback['profile'] in {p['name'] for p in review['profiles']}, 'feedback profile is outside pinned review configuration')
    advice=_packet(reader,advice_ref,'vnext_finding_advice_v1') if advice_ref is not None else None
    findings,evidence=classify_feedback(feedback=feedback,feedback_ref=feedback_ref,advice=advice,
        job=job,authority=authority,invariants=invariants,base=base,section_map=mapping,scope=scope,review=review)
    return MutationAdmission(reader,job,authority,invariants,scope,review,base,mapping,pointer_ref,
                             findings,evidence,deepcopy(feedback_ref),deepcopy(advice_ref),addressable_seed_units(base,mapping))


def prepare_admission(root,*,constraints,decision_refs=(),**inputs):
    admission=inspect_admission(root,**inputs)
    require(not any(e['requires_new_job'] for e in admission.evidence.values()),
            'immutable authority, scope or invariant policy requires a new job')
    decisions=[]
    for references in decision_refs:
        require(set(references)=={'finding_id','request','response'}, 'invalid decision references')
        finding_id=references['finding_id']
        require(finding_id in admission.evidence,'decision references an unknown finding')
        request=_packet(admission.reader,references['request'],'vnext_mutation_decision_request_v1')
        response=admission.reader.json(references['response'],'operator_decision_response_v1')
        require(set(response['authorized_deletion_unit_ids'])<=admission.units.keys(), 'decision names nonexistent or unaddressable seed units')
        decisions.append({'finding_id':finding_id,'request':request,'response':response,
                          'feedback_refs':admission.evidence[finding_id]['feedback_refs']})
    constraints=deepcopy(constraints)
    mutable=next(b for b in admission.authority['bindings'] if b['role']=='mutable_target')
    normative={b['binding_id'] for b in admission.authority['bindings']
               if b['role'] in {'mutable_target','normative_authority'}
               and set(b['authority_scopes']) & set(mutable['authority_scopes'])}
    assertion_sources={key for assertion in admission.invariants['assertions']
                       for key in assertion['source_authority_binding_ids']}
    constraints['required_context_binding_ids']=sorted(
        set(constraints['required_context_binding_ids'])|normative|assertion_sources)
    plan,provenance,responses=build_plan(job=admission.job,authority=admission.authority,section_map=admission.mapping,
        findings=admission.findings,constraints=constraints,suite=admission.reader.suite,decisions=decisions)
    # Publish every binding required to judge admission, including original
    # classified evidence. A transaction is never justified by just a task ID.
    proof={'schema_version':'vnext-mutation-admission-v1','job_id':admission.job['job_id'],'base_pointer':admission.pointer_ref,
           'feedback':admission.feedback_ref,'advice':admission.advice_ref,
           'findings':admission.findings,'evidence':admission.evidence,
           'derived_tasks':provenance,'decision_refs':deepcopy(list(decision_refs)),
           'mutation_plan_hash':sha256_bytes(canonical_json_bytes(plan))}
    VNextSchemaRegistry().validate(proof,'vnext_mutation_admission_v1')
    return admission,plan,proof,responses


def exercise_proposal(root,*,round_number,client,constraints,decision_refs=(),**inputs):
    """One injected-client exercise under local exclusion, without registration.

    A failed/interrupted attempt cannot be silently restarted. The caller must
    inspect its retained evidence. Native role adapters and bounded shape retry
    integration remain in the consuming runtime slice.
    """
    root=Path(root).resolve()
    require(type(round_number) is int and round_number>0,'invalid proposal round')
    frozen=deepcopy({'constraints':constraints,'decision_refs':list(decision_refs),**inputs})
    admission,plan,proof,responses=prepare_admission(root,**frozen)
    directory=f'rounds/round-{round_number}'
    require(not (root/directory).exists(),'proposal exercise requires a fresh round; inspect prior evidence')
    with writer(root):
        admission,plan,proof,responses=prepare_admission(root,**frozen)
        require(not (root/directory).exists(),'another proposal already claimed this round')
        context={}
        bindings={b['binding_id']:b for b in admission.authority['bindings']}
        for key in plan['required_context_binding_ids']:
            binding=bindings[key]
            if binding['role']!='mutable_target':
                context[key]=admission.reader.raw({'path':binding['path'],'hash':binding['content_hash']})
        derived={task['finding_id']:task for task in proof['derived_tasks']}
        by_response={response['response_id']:response for response,_ in responses}
        finding_details=[]
        for finding in plan['finding_dispositions']:
            if not finding['admitted_to_editing']:continue
            original=derived[finding['finding_id']]['original_finding_id'] if finding['finding_id'] in derived else finding['finding_id']
            finding_details.append({'finding_id':finding['finding_id'],'original_finding_id':original,
                'source_findings':admission.evidence[original]['source_items'],
                'feedback_refs':admission.evidence[original]['feedback_refs'],
                'operator_response':by_response.get(finding['decision_response_id'])})
        prompt=proposal_prompt(plan=plan,base=admission.base,section_map=admission.mapping,
            authority=admission.authority,invariants=admission.invariants,context=context,finding_details=finding_details,scope=admission.scope)
        publish(root,directory+'/mutation_plan.json',plan)
        publish(root,directory+'/mutation_admission.json',proof)
        publish(root,directory+'/proposals/attempts/prompt-1.txt',prompt.encode())
        try:
            raw=client.propose(prompt)
        except Exception as exc:
            publish(root,directory+'/proposals/attempts/failure-1.txt',
                    (type(exc).__name__+': '+str(exc)).encode('utf-8'))
            raise
        require(isinstance(raw,bytes),'proposal client must return exact response bytes')
        # Raw evidence is retained even if a concurrent input change prevents
        # canonical proposal publication. Revalidation makes no authority writes.
        publish(root,directory+'/proposals/attempts/proposal-attempt-1.json',raw)
        current,current_plan,current_proof,_=prepare_admission(root,**frozen)
        require(current_plan==plan and current_proof==proof,'proposal inputs changed during the client call')
        proposal,reference=capture_response(root,round_number,1,raw,plan=plan,base=current.base,
            section_map=current.mapping,editor=current.review['editor'],suite=current.reader.suite,
            responses=[response for response,_ in responses],units=current.units)
        result={'schema_version':'vnext-proposal-result-v1','proposal':reference,'mutation_plan_hash':proof['mutation_plan_hash'],
            'base_pointer':proof['base_pointer'],'candidate_registered':False,'verified':False,'promoted':False}
        VNextSchemaRegistry().validate(result,'vnext_proposal_result_v1')
        publish(root,directory+'/proposal_result.json',result)
        return proposal,reference
