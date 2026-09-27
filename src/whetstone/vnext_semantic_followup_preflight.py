"""Pure follow-up planning from an explicitly selected semantic answer.

Snapshot construction validates current stored evidence. It is not durable
transaction admission: the eventual owner must reread that evidence before
request work, rather than treating a cached snapshot as authority.
"""
from copy import deepcopy
from dataclasses import replace

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_identity import transaction_id
from whetstone.vnext_semantic_answers import ALGORITHM as ANSWER_ALGORITHM, ANSWER_SCHEMAS, SemanticAnswerSource, validate_answer_response
from whetstone.vnext_semantic_context import SemanticContext
from whetstone.vnext_validation import validate_plan


ALGORITHM = 'algorithms/vnext_semantic_followup_preflight_v1.md'
SCHEMAS = ANSWER_SCHEMAS | {'mutation_plan_v3'}


def validate_followup_contracts(suite):
    entries = {entry['path']:entry for family in ('schemas','algorithms') for entry in suite.manifest[family]}
    paths = {'schemas/'+name+'.schema.json' for name in SCHEMAS} | {ALGORITHM, ANSWER_ALGORITHM}
    require(paths <= entries.keys(), 'semantic follow-up contracts are outside supported suite')
    for path in paths:
        require(sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()) == entries[path]['sha256'],
                'installed semantic follow-up contract differs from pinned suite',path)


def read_followup_evidence(store, *, admission, candidate_id, reference):
    """Read a current exact answer into a pure planning snapshot; write nothing."""
    return _read_followup_evidence(store, admission=admission, candidate_id=candidate_id,
                                  reference=reference, source_type=SemanticAnswerSource)


def _read_followup_evidence(store, *, admission, candidate_id, reference, source_type):
    source = source_type(store,admission=admission,candidate_id=candidate_id,require_current=True)
    validate_followup_contracts(source.suite)
    require(isinstance(reference,dict) and set(reference)=={'path','hash'}
            and isinstance(reference['path'],str) and isinstance(reference['hash'],str),
            'semantic follow-up requires an exact answer receipt reference')
    responses,receipts = source.inspect()
    receipt = receipts.get(reference['path'])
    require(receipt is not None and source.receipt_ref(receipt)==reference,
            'semantic follow-up answer receipt is missing or stale')
    require(receipt['action']=='select','declined semantic answer cannot enable follow-up work')
    source.guard()
    return canonical_json_bytes({'schema_version':'vnext-semantic-followup-evidence-v1',
        'source_context':source.context.packet,'source_verification':source.view.decision,
        'source_verification_ref':source.decision_ref,'question':source.request,
        'response':responses[receipt['response']['path']], 'receipt':receipt,'receipt_ref':reference})


def _editing_plan(plan, responses):
    """Project a follow-up back to its unchanged, independently admitted scope."""
    result = deepcopy(plan)
    if result.get('schema_version')=='mutation-plan-v3':
        origin = result.pop('semantic_origin')
        result['schema_version']='mutation-plan-v2'
        result['transaction_id']=transaction_id(result,responses)
        require(sha256_bytes(canonical_json_bytes(result))==origin['editing_plan_hash'],
                'semantic source editing scope differs from its origin')
    return result


def prepare_followup_preflight(arguments, raw):
    """Reproduce a fresh plan without expanding independently admitted work.

Pure callers own registration authority. Runtime loaders must reproduce raw
from the selected receipt and original source evidence on every invocation.
"""
    from whetstone.vnext_unit_preflight import prepare_unit_preflight
    suite=arguments['suite'];validate_followup_contracts(suite)
    require(isinstance(raw,bytes),'semantic follow-up evidence requires exact canonical bytes')
    evidence=decode_json(raw)
    require(isinstance(evidence,dict) and set(evidence)=={
        'schema_version','source_context','source_verification','source_verification_ref',
        'question','response','receipt','receipt_ref'} and evidence['schema_version']=='vnext-semantic-followup-evidence-v1',
        'invalid semantic follow-up evidence envelope')
    require(raw==canonical_json_bytes(evidence),'noncanonical semantic follow-up evidence')
    baseline=prepare_unit_preflight(**arguments)
    context=SemanticContext(canonical_json_bytes(evidence['source_context']))
    source=context.packet
    if arguments.get('vertical') is not None:
        require(source.get('vertical') == arguments['vertical'], 'semantic follow-up vertical sources changed')
    if arguments.get('phase2') is not None:
        require(source.get('phase2') == arguments['phase2'],
                'semantic follow-up Phase 2 configuration or request changed')
    response=validate_answer_response(evidence['response'],request=evidence['question'],context=context,suite=suite)
    require(response['selected_option_id']!='decline','declined semantic answer cannot enable follow-up work')
    for key in ('job','seed_map','base_map','authority_map','scope_contract','protected_invariants','review_configuration','base_pointer'):
        name={'authority_map':'authority','scope_contract':'scope','protected_invariants':'invariants',
              'review_configuration':'review','base_pointer':'base_pointer_ref'}.get(key,key)
        require(source[key]==arguments.get(name),'semantic follow-up source binding changed: '+key)
    for key in ('seed','base'):
        require(source[key].encode('utf-8')==arguments[key],'semantic follow-up source bytes changed: '+key)
    responses={b.response['response_id']:b.response_hash for b in baseline.bindings if b.response['authorized_effects']}
    source_plan=source['mutation_plan']
    suite.registry.validate(source_plan,'mutation_plan_v3' if source_plan.get('schema_version')=='mutation-plan-v3' else 'mutation_plan_v2')
    validate_plan(source_plan,arguments['job'],arguments['authority'],arguments['base_map'],
                  [(b.response,b.response_hash) for b in baseline.bindings if b.response['authorized_effects']])
    require(_editing_plan(source_plan,responses)==baseline.plan,
            'semantic follow-up cannot change the independently admitted editing scope')
    question=evidence['question'];decision=evidence['source_verification'];receipt=evidence['receipt']
    suite.registry.validate(decision,'candidate_verification_v1')
    suite.registry.validate(receipt,'vnext_semantic_answer_receipt_v1')
    source_id=source['creation']['candidate_id']
    require(question['candidate_id']==source_id and question['transaction_id']==source_plan['transaction_id'],
            'semantic follow-up question belongs to another source transaction')
    require(decision['job_id']==arguments['job']['job_id'] and decision['candidate_id']==source_id
            and decision['decision_final'] and decision['candidate_disposition']=='CANDIDATE_REJECTED'
            and decision['semantic_result'] in {'operator_decision_required','reject'}
            and decision['outstanding_decision_ids']==[question['decision_id']],
            'semantic follow-up requires its exact final rejected source decision')
    directory=source['creation']['candidate_path'].rsplit('/',1)[0]
    response_path=directory+'/operator_answers/'+question['decision_id']+'/responses/'+response['response_id']+'.json'
    def ref(path,value):return {'path':path,'hash':sha256_bytes(canonical_json_bytes(value))}
    require(evidence['source_verification_ref']==ref(directory+'/candidate_verification-attempt-'+str(decision['decision_ordinal'])+'.json',decision),
            'semantic follow-up source verification reference changed')
    expected={'schema_version':'vnext-semantic-answer-receipt-v1','job_id':arguments['job']['job_id'],'candidate_id':source_id,
        'request':ref(directory+'/semantic_decisions/'+question['decision_id']+'/request.json',question),
        'candidate_verification':evidence['source_verification_ref'],'response':ref(response_path,response),
        'base_pointer':arguments['base_pointer_ref'],'action':'select',
        'resolution_scope':'interpretation_only_no_editing_or_authority_grant'}
    require(receipt==expected,'semantic follow-up receipt differs from its exact sources')
    receipt_path=directory+'/operator_answers/'+question['decision_id']+'/receipts/answer-'+sha256_bytes(canonical_json_bytes(receipt))+'.json'
    require(evidence['receipt_ref']==ref(receipt_path,receipt),'semantic follow-up receipt reference changed')
    plan=deepcopy(baseline.plan)
    plan.update(schema_version='mutation-plan-v3',semantic_origin={
        'source_candidate_id':source_id,'source_transaction_id':source_plan['transaction_id'],
        'editing_plan_hash':sha256_bytes(canonical_json_bytes(baseline.plan)),
        'answer_receipt':deepcopy(evidence['receipt_ref']),
        'source_verification':deepcopy(evidence['source_verification_ref'])})
    plan['transaction_id']=transaction_id(plan,responses)
    require(plan['transaction_id']!=source_plan['transaction_id'],'semantic follow-up must create a fresh transaction')
    suite.registry.validate(plan,'mutation_plan_v3')
    validate_plan(plan,arguments['job'],arguments['authority'],arguments['base_map'],
                  [(b.response,b.response_hash) for b in baseline.bindings if b.response['authorized_effects']])
    intro,packet_raw=baseline.prompt.rsplit('\n',1)
    packet=decode_json(packet_raw.encode('utf-8'))
    packet.update(mutation_plan=plan,mutation_plan_hash=sha256_bytes(canonical_json_bytes(plan)),
        semantic_interpretation={'source_candidate_id':source_id,'question':question,'response':response,
                                 'answer_receipt':evidence['receipt_ref']})
    prompt=intro+'\nThe source candidate remains finally rejected. Use the explicit interpretation only within '
    prompt+='the unchanged admitted editing scope; it grants no effects and changes no authority precedence.\n'
    prompt+=canonical_json_bytes(packet).decode('utf-8')
    digest=sha256_bytes(canonical_json_bytes({'version':'vnext-semantic-followup-preflight-v1',
        'editing_input_hash':baseline.input_hash,'followup_evidence_hash':sha256_bytes(raw)}))
    return replace(baseline,input_hash=digest,plan=plan,prompt=prompt)
