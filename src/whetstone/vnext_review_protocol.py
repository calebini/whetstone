"""Exact seed-review inputs and raw feedback/advice decoding for proposal runs."""
from copy import deepcopy
from dataclasses import dataclass

from whetstone.clients import canonicalize_reviewer_input
from whetstone.prompts import render_reviewer_prompt
from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import VNextSchemaRegistry,canonical_json_bytes,decode_json,require,sha256_bytes
from whetstone.vnext_unit_preflight import input_projection


class ReviewShapeError(ValueError):pass


@dataclass(frozen=True)
class ReviewPreflight:
    input_hash: str
    arguments: dict
    prompt: str


def prepare_seed_review(run,*,round_number,profile):
    run.validate_authority(run.store.read)
    reader,values=run._admission(run.store.read)._base(run.store.read)
    require(type(round_number) is int and round_number>0,'invalid Reviewer round')
    require(profile in {p['name'] for p in values['review']['profiles']},'Reviewer profile is outside pinned configuration')
    context=[]
    for binding in values['authority']['bindings']:
        if binding['role'] in {'mutable_target','excluded'}:continue
        raw=reader.raw({'path':binding['path'],'hash':binding['content_hash']})
        context.append({'binding':deepcopy(binding),'content':raw.decode('utf-8')})
    arguments={key:values[key] for key in ('job','authority','invariants','seed','seed_map','scope','review','base_pointer_ref')}
    arguments.update(round_number=round_number,profile=profile,context=context,suite_digest=reader.suite.digest)
    if run._record.get('launch_package') is not None:
        arguments['launch_package']=deepcopy(run._record['launch_package'])
    digest=sha256_bytes(canonical_json_bytes(input_projection(arguments)))
    prompt=render_reviewer_prompt(profile=profile,draft=values['seed'].decode('utf-8'),
        draft_path=values['job']['seed_draft']['path'],reference_context_paths=[],scope_contract_path=None,
        section_ids=[s['canonical_section_id'] for s in values['seed_map']['sections']],round_number=round_number,
        draft_hash_value=values['job']['seed_draft']['hash'])
    packet={key:arguments[key] for key in ('job','authority','invariants','scope','review','context','round_number','profile')}
    packet['seed_section_map']=values['seed_map']
    prompt+='\nReturn a vnext-review-response-v1 object with feedback and one classification advice item per source feedback_id.\n'
    prompt+='Classification advice cannot authorize edits, grants, authority changes or scope changes. Do not emit candidate or verification artifacts.\n'
    prompt+='All bound context is embedded below. Use its declared roles; excluded documents are unavailable.\n'
    prompt+='Feedback must retain the exact round, profile, draft hash and configured Reviewer identity.\n'
    prompt+=canonical_json_bytes(packet).decode('utf-8')
    return ReviewPreflight(digest,arguments,prompt)


def decode_seed_review(raw,preflight,*,feedback_path):
    values = preflight.arguments
    return _decode_review(raw, preflight, feedback_path=feedback_path,
                          base=values['seed'], section_map=values['seed_map'])


def _decode_review(raw, preflight, *, feedback_path, base, section_map):
    schemas=VNextSchemaRegistry();schemas.load('vnext_review_response_v1')
    try:
        packet=decode_json(raw);schemas.validate(packet,'vnext_review_response_v1')
    except ValueError as exc:raise ReviewShapeError(str(exc)) from exc
    values=preflight.arguments;feedback=deepcopy(packet['feedback'])
    require(feedback['round_number']==values['round_number'] and feedback['profile']==values['profile']
            and feedback['draft_hash']==sha256_bytes(base), 'Reviewer response has contradictory request bindings')
    require(feedback['reviewer']==values['review']['reviewer'],'Reviewer response differs from pinned role')
    feedback=canonicalize_reviewer_input(feedback)
    schemas.validate(feedback,'reviewer_feedback')
    reference={'path':feedback_path,'hash':sha256_bytes(canonical_json_bytes(feedback))}
    job=values['job']
    advice={'schema_version':'vnext-finding-advice-v1','job_id':job['job_id'],'base_draft_hash':sha256_bytes(base),
        'feedback':reference,'authority_map_hash':job['authority_map_hash'],'scope_contract_hash':job['scope_contract_hash'],
        'protected_invariants_hash':job['protected_invariants_hash'],'findings':deepcopy(packet['classifications'])}
    schemas.validate(advice,'vnext_finding_advice_v1')
    findings,evidence=classify_feedback(feedback=feedback,feedback_ref=reference,advice=advice,
        job=job,authority=values['authority'],invariants=values['invariants'],base=base,
        section_map=section_map,scope=values['scope'])
    return {'feedback':feedback,'advice':advice,'findings':findings,'evidence':evidence}
