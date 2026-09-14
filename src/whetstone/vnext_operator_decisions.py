"""Explicit operator choices for a retained, not-yet-admitted seed review.

Requests and answers are immutable evidence. Only a separately selected receipt
can supply decisions to round admission; directory order never selects consent.
"""
from copy import deepcopy
import re

from whetstone.vnext_contracts import VNextSchemaRegistry,canonical_json_bytes,decode_json,require,sha256_bytes
from whetstone.vnext_discovery import discovery_rules
from whetstone.vnext_identity import response_id
from whetstone.vnext_inventory import seed_inventory
from whetstone.vnext_proposal_closeout import proposal_terminal_report
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_proposal_run import round_input_path
from whetstone.vnext_review_requests import _sequence
from whetstone.vnext_unit_authorization import bind_unit_response,unit_decision_request

BLOCKING=frozenset({'operator_decision_required','authority_conflict','scope_change'})


def _ref(path,value):return {'path':path,'hash':sha256_bytes(canonical_json_bytes(value))}
def _directory(number):return f'rounds/round-{number}/operator_decisions'
def _request_path(number,identifier):return _directory(number)+'/'+identifier+'/request.json'
def _response_path(number,request,identifier):return _directory(number)+'/'+request+'/responses/'+identifier+'.json'
def _selection_ref(number,value):
    digest=sha256_bytes(canonical_json_bytes(value))
    return {'path':_directory(number)+'/selections/selection-'+digest+'.json','hash':digest}


def _context(run,number):
    reader,values=run._admission(run.store.read)._base(run.store.read)
    step=run.review_status()
    require(step.status=='finding_admission' and step.round_number==number and step.receipt is not None,
            'operator work requires the active completed finding review')
    result=_ref('rounds/client_requests/'+step.request_id+'/result.json',step.receipt)
    reader.json(result,'vnext_review_result_v1')
    inventory=seed_inventory(values['seed'],values['seed_map'],values['job'],rules=discovery_rules(values['invariants']))
    return reader,values,step,inventory,result


def _unadmitted(run,number):
    require(number not in run._staged,'operator action cannot alter a staged proposal admission')
    try:run.store.read(round_input_path(number))
    except FileNotFoundError:pass
    else:require(False,'operator action cannot alter an admitted round; new work needs a separate transaction')
    registry=registry_for_proposal_requests(run.store,load_inputs=run.load_inputs,validate_authority=run.validate_authority)
    registered=registry.inspect()
    require(not registered.events and not registered.orphans,'operator action cannot bypass candidate processing')


def _binding(packet,values,result,number):
    require(packet['job_id']==values['job']['job_id'] and packet['round_number']==number
            and packet['review_result']==result,'operator input has stale job, round or Reviewer bindings')


def _request_arguments(values,step,inventory,key):
    finding=next((f for f in step.review['findings'] if f['finding_id']==key),None)
    require(finding is not None,'operator request references an unknown finding')
    evidence=step.review['evidence'][key]
    return dict(job=values['job'],base_hash=sha256_bytes(values['base']),finding=finding,
        targets=finding['target_section_ids'],feedback_refs=evidence['feedback_refs'],inventory=inventory,
        section_map=values['base_map'])


def _read_request(reader,values,step,inventory,reference,number):
    packet=reader.json(reference,'vnext_mutation_decision_request_v2')
    arguments=_request_arguments(values,step,inventory,packet['finding_id'])
    require(packet==unit_decision_request(options=packet['options'],**arguments),
            'retained operator request does not reproduce from current evidence')
    require(reference==_ref(_request_path(number,packet['decision_id']),packet),
            'operator request must use its canonical retained location')
    return packet,arguments


def _validate_receipt(run,packet,context):
    reader,values,step,inventory,result=context;number=step.round_number
    reader.suite.registry.validate(packet,'vnext_operator_selection_v1');_binding(packet,values,result,number)
    require(packet['base_pointer']==values['base_pointer_ref'],'operator selection has a stale verified base')
    keys=[d['finding_id'] for d in packet['decision_refs']]
    require(bool(keys) and keys==sorted(set(keys)),'operator selection requires sorted unique finding decisions')
    for entry in packet['decision_refs']:
        request,arguments=_read_request(reader,values,step,inventory,entry['request'],number)
        require(entry['finding_id']==request['finding_id'],'selected decision belongs to another finding')
        response=reader.json(entry['response'],'operator_decision_response_v1')
        bind_unit_response(response,request,suite=reader.suite,**arguments)
        require(entry['response']==_ref(_response_path(number,request['decision_id'],response['response_id']),response),
                'operator response must use its canonical retained location')
    return deepcopy(packet['decision_refs'])


def selected_operator_decisions(run,*,round_number,reference):
    context=_context(run,round_number);reader=context[0]
    packet=reader.json(reference,'vnext_operator_selection_v1')
    require(reference==_selection_ref(round_number,packet),'operator selection must use its canonical retained location')
    return _validate_receipt(run,packet,context)


def decision_context(run,*,round_number):
    """Read-only exact evidence for an agent/operator to construct choices."""
    _,values,step,inventory,result=_context(run,round_number)
    return {'job_id':values['job']['job_id'],'round_number':round_number,'review_result':result,
        'base_pointer':values['base_pointer_ref'],'inventory':inventory,'section_map':values['base_map'],
        'findings':deepcopy(step.review['findings']),'evidence':deepcopy(step.review['evidence'])}


def _synchronize_review(run,token,expected):
    completed,pending,gate,profile,previous=_sequence(run)
    require(pending is None and gate=='finding_admission','operator source review is no longer complete')
    for request,header,outcomes,review,receipt in completed:
        request.synchronize(token,header,outcomes);request.finish(token,review)
    context=_context(run,expected['round_number']);_binding(expected,context[1],context[4],expected['round_number'])
    return context


def prepare_operator_requests(run,packet,*,dry_run=False):
    """Publish explicitly supplied options, never choose one or call a client."""
    frozen=deepcopy(packet);VNextSchemaRegistry().validate(frozen,'vnext_operator_options_v1')
    number=frozen['round_number'];_unadmitted(run,number)
    def prepare():
        reader,values,step,inventory,result=_context(run,number);_binding(frozen,values,result,number)
        choices=frozen['choices'];keys=[c['finding_id'] for c in choices]
        require(len(keys)==len(set(keys)),'duplicate finding options')
        requests=[]
        for choice in choices:
            require(all(o['description'].strip() for o in choice['options']),'operator option requires a concrete description')
            request=unit_decision_request(options=choice['options'],
                **_request_arguments(values,step,inventory,choice['finding_id']))
            requests.append((_ref(_request_path(number,request['decision_id']),request),request))
        return sorted(requests,key=lambda pair:pair[0]['path'])
    requests=prepare()
    if dry_run:return [{'request':ref,'content':value} for ref,value in requests]
    with run.store.locked(run.validate_authority) as token:
        _unadmitted(run,number);_synchronize_review(run,token,frozen)
        require(prepare()==requests,'operator options changed before publication')
        for reference,value in requests:run.store.publish(token,reference['path'],value)
        for reference,value in requests:
            require(run.store.read(reference['path'])==canonical_json_bytes(value),'operator request readback differs')
        _publish_pause(run,token,number)
    return [{'request':ref,'content':value} for ref,value in requests]


def submit_operator_responses(run,packet,*,dry_run=False):
    """Build responses from explicit selections; commit their selection last.

    Actor, rationale and timestamp are explicit caller inputs. No approval or
    effect field is inferred from Reviewer advice, existing answers or defaults.
    """
    frozen=deepcopy(packet);VNextSchemaRegistry().validate(frozen,'vnext_operator_response_input_v1')
    number=frozen['round_number'];_unadmitted(run,number)
    def prepare():
        reader,values,step,inventory,result=_context(run,number);_binding(frozen,values,result,number)
        records=[];responses=[]
        for choice in frozen['selections']:
            request,arguments=_read_request(reader,values,step,inventory,choice['request'],number)
            option=next((o for o in request['options'] if o['option_id']==choice['selected_option_id']),None)
            require(option is not None,'operator selected an unknown option')
            response={'schema_version':'operator-decision-response-v1','job_id':values['job']['job_id'],
                'response_id':'','decision_id':request['decision_id'],'decision_request_hash':choice['request']['hash'],
                'base_draft_hash':request['base_draft_hash'],'authority_map_hash':request['authority_map_hash'],
                'scope_contract_hash':request['scope_contract_hash'],'selected_option_id':choice['selected_option_id'],
                'authorized_effects':deepcopy(option['authorized_effects']),
                'authorized_deletion_unit_ids':deepcopy(option['authorized_deletion_unit_ids']),
                **{k:choice[k] for k in ('rationale','decided_by','decided_at')}}
            response['response_id']=response_id(response)
            bind_unit_response(response,request,suite=reader.suite,**arguments)
            reference=_ref(_response_path(number,request['decision_id'],response['response_id']),response)
            # Equal response identity does not permit rewriting an earlier timestamp.
            try:existing=run.store.read(reference['path'])
            except FileNotFoundError:existing=None
            require(existing is None or existing==canonical_json_bytes(response),'operator response identity already has different bytes')
            records.append({'finding_id':request['finding_id'],'request':choice['request'],'response':reference})
            responses.append((reference,response))
        keys=[d['finding_id'] for d in records];require(len(keys)==len(set(keys)),'multiple selections for one finding')
        receipt={'schema_version':'vnext-operator-selection-v1','job_id':values['job']['job_id'],
            'round_number':number,'review_result':result,'base_pointer':values['base_pointer_ref'],
            'decision_refs':sorted(records,key=lambda d:d['finding_id'])}
        reader.suite.registry.validate(receipt,'vnext_operator_selection_v1')
        return receipt,responses
    receipt,responses=prepare();reference=_selection_ref(number,receipt)
    result={'selection':reference,'content':receipt,'responses':[{'response':r,'content':v} for r,v in responses]}
    if dry_run:return result
    with run.store.locked(run.validate_authority) as token:
        _unadmitted(run,number);_synchronize_review(run,token,frozen)
        require(prepare()==(receipt,responses),'operator selection changed before publication')
        for entry in receipt['decision_refs']:
            raw=run.store.read(entry['request']['path'])
            require(sha256_bytes(raw)==entry['request']['hash'],'operator request changed before response publication')
            run.store.publish(token,entry['request']['path'],raw)
        for ref,value in responses:run.store.publish(token,ref['path'],value)
        _validate_receipt(run,receipt,_context(run,number))
        run.store.publish(token,reference['path'],receipt)
        require(selected_operator_decisions(run,round_number=number,reference=reference)==receipt['decision_refs'],
                'operator selection readback differs')
    return result


def _entries(run,path):
    try:return [(name,kind) for name,kind in run.store.list_directory(path) if not name.startswith('.vnext-tmp-')]
    except FileNotFoundError:run.store.read_descriptor();return []


def inspect_operator_work(run,*,round_number):
    """List evidence without selecting an answer, writing or taking ownership."""
    context=_context(run,round_number);reader,values,step,inventory,result=context
    requests=[];selections=[];number=round_number
    for name,kind in _entries(run,_directory(number)):
        require(kind=='directory','invalid operator evidence directory')
        if name=='selections':
            for leaf,leaf_kind in _entries(run,_directory(number)+'/selections'):
                require(leaf_kind=='file' and re.fullmatch(r'selection-[0-9a-f]{64}\.json',leaf),'invalid operator selection entry')
                path=_directory(number)+'/selections/'+leaf;raw=run.store.read(path)
                reference={'path':path,'hash':sha256_bytes(raw)};packet=reader.json(reference,'vnext_operator_selection_v1')
                require(reference==_selection_ref(number,packet),'operator selection identity differs')
                _validate_receipt(run,packet,context);selections.append(reference)
            continue
        require(re.fullmatch(r'decision_[0-9a-f]{64}',name),'invalid operator request directory')
        for leaf,leaf_kind in _entries(run,_directory(number)+'/'+name):
            require((leaf,leaf_kind) in {('request.json','file'),('responses','directory')},'invalid operator request artifact')
        path=_request_path(number,name);raw=run.store.read(path);reference={'path':path,'hash':sha256_bytes(raw)}
        request,arguments=_read_request(reader,values,step,inventory,reference,number);answers=[]
        for leaf,leaf_kind in _entries(run,_directory(number)+'/'+name+'/responses'):
            require(leaf_kind=='file' and re.fullmatch(r'resp_[0-9a-f]{64}\.json',leaf),'invalid operator response entry')
            path=_directory(number)+'/'+name+'/responses/'+leaf;raw=run.store.read(path)
            ref={'path':path,'hash':sha256_bytes(raw)};response=reader.json(ref,'operator_decision_response_v1')
            bind_unit_response(response,request,suite=reader.suite,**arguments)
            require(ref==_ref(_response_path(number,name,response['response_id']),response),'operator response identity differs')
            answers.append(ref)
        requests.append({'finding_id':request['finding_id'],'request':reference,'responses':sorted(answers,key=lambda r:r['path'])})
    blocking=[f['finding_id'] for f in step.review['findings'] if f['classification'] in BLOCKING]
    return {'review_result':result,'blocking_finding_ids':sorted(blocking),
        'requires_new_job':sorted(k for k,e in step.review['evidence'].items() if e['requires_new_job']),
        'requests':sorted(requests,key=lambda r:r['request']['path']),'selections':sorted(selections,key=lambda r:r['path'])}


def operator_pause(run,*,round_number):
    work=inspect_operator_work(run,round_number=round_number)
    if not any(r['finding_id'] in work['blocking_finding_ids'] for r in work['requests']):return work,None,None
    registry=registry_for_proposal_requests(run.store,load_inputs=run.load_inputs,validate_authority=run.validate_authority)
    registered=registry.inspect()
    require(not registered.events and not registered.orphans,'operator pause cannot bypass candidate processing')
    report=proposal_terminal_report(registry,terminal_state='PAUSED_DECISION',reason='vnext_operator_decision_required')
    reference=_ref('unused',report);reference['path']='rounds/terminal_reports/terminal-'+reference['hash']+'.json'
    try:raw=run.store.read(reference['path'])
    except FileNotFoundError:raw=None
    require(raw is None or raw==canonical_json_bytes(report),'operator terminal conflicts with current evidence')
    return work,report,{'reference':reference,'materialized':raw is not None}


def _publish_pause(run,token,number):
    work,report,materialization=operator_pause(run,round_number=number)
    if report is not None:run.store.publish(token,materialization['reference']['path'],report)


def finish_operator_pause(run,*,round_number):
    with run.store.locked(run.validate_authority) as token:
        _unadmitted(run,round_number)
        _,values,step,inventory,result=_context(run,round_number)
        _synchronize_review(run,token,{'job_id':values['job']['job_id'],'round_number':round_number,'review_result':result})
        work=inspect_operator_work(run,round_number=round_number)
        for request in work['requests']:
            reference=request['request'];run.store.publish(token,reference['path'],run.store.read(reference['path']))
        _publish_pause(run,token,round_number)
