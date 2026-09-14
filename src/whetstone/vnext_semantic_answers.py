"""Exact operator interpretations after final semantic rejection.

Answers and receipts are immutable evidence. Neither grants editing effects,
chooses an active receipt for a new transaction, nor reopens its candidate.
"""
from copy import deepcopy
import re

from whetstone.vnext_contracts import CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_decisions import bind_selected_response
from whetstone.vnext_identity import response_id
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from whetstone.vnext_semantic_protocol import POLICY_VERSION, _authority_request


ALGORITHM = 'algorithms/vnext_semantic_answers_v1.md'
ANSWER_SCHEMAS = frozenset({'vnext_semantic_answer_input_v1', 'vnext_semantic_answer_receipt_v1'})


def _ref(path, packet):
    return {'path':path, 'hash':sha256_bytes(canonical_json_bytes(packet))}


def _question(request, context):
    require(context.packet['job']['semantic_verifier_policy_version'] == POLICY_VERSION, 'unsupported semantic answer policy')
    VNextSchemaRegistry().validate(request, 'vnext_semantic_authority_request_v1')
    require(request == _authority_request(request['choice'], context, request['verifier_response_hash']),
            'semantic answer question differs from its bound context')
    # The owning semantic request has been reproduced above. This projection
    # supplies only option membership to the existing response binder.
    keys = [row['authority_binding_id'] for row in request['choice']['alternatives']] + ['decline']
    return {'decision_id':request['decision_id'], 'options':[
        {'option_id':key, 'authorized_effects':[], 'authorized_deletion_unit_ids':[]} for key in keys]}


def validate_answer_response(response, *, request, context, suite):
    options = _question(request, context)
    return bind_selected_response(response, options, job=context.packet['job'],
        base_hash=sha256_bytes(context.packet['base'].encode('utf-8')),
        request_hash=sha256_bytes(canonical_json_bytes(request)), suite=suite)[0]


def prepare_answer(packet, *, request, context, request_ref, decision_ref, suite):
    suite.registry.validate(packet, 'vnext_semantic_answer_input_v1')
    require(packet['job_id'] == request['job_id'] and packet['candidate_id'] == request['candidate_id']
            and packet['request'] == request_ref and packet['candidate_verification'] == decision_ref,
            'semantic answer input has stale question or candidate decision bindings')
    require((packet['action'] == 'decline') == (packet['selected_authority_binding_id'] is None),
            'semantic answer action and authority selection disagree')
    response = {'schema_version':'operator-decision-response-v1', 'job_id':request['job_id'],
        'response_id':'', 'decision_id':request['decision_id'], 'decision_request_hash':request_ref['hash'],
        'base_draft_hash':sha256_bytes(context.packet['base'].encode('utf-8')),
        'authority_map_hash':context.packet['job']['authority_map_hash'],
        'scope_contract_hash':context.packet['job']['scope_contract_hash'],
        'selected_option_id':packet['selected_authority_binding_id'] if packet['action'] == 'select' else 'decline',
        'authorized_effects':[], 'authorized_deletion_unit_ids':[],
        **{key:packet[key] for key in ('rationale','decided_by','decided_at')}}
    response['response_id'] = response_id(response)
    return validate_answer_response(response, request=request, context=context, suite=suite)


class SemanticAnswerSource:
    DecisionJournal = SemanticDecisionJournal

    def __init__(self, store, *, admission, candidate_id, require_current=False):
        self.store = store
        self.admission = admission
        reader, _ = admission._base(store.read)
        self.suite = reader.suite
        algorithms = {entry['path']:entry for entry in self.suite.manifest['algorithms']}
        require(ALGORITHM in algorithms, 'semantic answer algorithm is outside supported suite')
        schemas = {entry['path']:entry for entry in self.suite.manifest['schemas']}
        paths = {'schemas/'+name+'.schema.json' for name in ANSWER_SCHEMAS}
        require(paths <= schemas.keys(), 'semantic answer schemas are outside supported suite')
        for path in paths | {ALGORITHM}:
            entry = algorithms[path] if path == ALGORITHM else schemas[path]
            require(sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()) == entry['sha256'],
                    'installed semantic answer contract differs from pinned suite')
        self.registry = registry_for_proposal_requests(store, load_inputs=admission.load_inputs,
                                                        validate_authority=admission.validate_authority)
        registered = self.registry.inspect()
        require(not registered.orphans, 'semantic answer requires completed registration')
        self.journal = self.DecisionJournal(self.registry, admission=admission)
        states = {event['candidate_id']:self.journal._state_with_request(event) for event in registered.events}
        require(candidate_id in states, 'semantic answer candidate is not registered')
        state, completed = states[candidate_id]
        self.view = state[0]
        self.current = registered.latest == self.view.creation
        require(not require_current or self.current, 'new semantic answer requires the current candidate')
        decision = self.view.decision
        require(decision is not None and not self.view.prepared and decision['decision_final']
                and decision['candidate_disposition'] == 'CANDIDATE_REJECTED'
                and decision['semantic_result'] in {'operator_decision_required','reject'},
                'semantic answer requires a committed final semantic rejection')
        require(completed is not None, 'semantic answer lacks its replayed final request')
        self.request_journal, self.header, self.outcomes, result = completed
        self.context = self.request_journal.context
        self.request = result.authority_request
        require(self.request is not None and decision['outstanding_decision_ids'] == [self.request['decision_id']],
                'candidate decision does not bind the exact semantic question')
        self.request_ref = result.verification['authority_decision_request']
        self.decision_ref = {'path':self.view.pointer['current_decision_path'], 'hash':self.view.pointer['current_decision_hash']}
        candidate = self.view.creation['candidate_path'].rsplit('/',1)[0]
        self.directory = candidate+'/operator_answers/'+self.request['decision_id']
        self.pointer_path = candidate+'/candidate_verification_current.json'

    def listing(self, path):
        return [(name,kind) for name,kind in self.registry._listing(path) if not name.startswith('.vnext-tmp-')]

    def response_ref(self, response):
        return _ref(self.directory+'/responses/'+response['response_id']+'.json', response)

    def receipt(self, response):
        value = {'schema_version':'vnext-semantic-answer-receipt-v1',
            'job_id':self.request['job_id'], 'candidate_id':self.request['candidate_id'],
            'request':deepcopy(self.request_ref), 'candidate_verification':deepcopy(self.decision_ref),
            'response':self.response_ref(response), 'base_pointer':deepcopy(self.context.packet['base_pointer']),
            'action':'decline' if response['selected_option_id'] == 'decline' else 'select',
            'resolution_scope':'interpretation_only_no_editing_or_authority_grant'}
        self.suite.registry.validate(value, 'vnext_semantic_answer_receipt_v1')
        return value

    def receipt_ref(self, receipt):
        return _ref(self.directory+'/receipts/answer-'+sha256_bytes(canonical_json_bytes(receipt))+'.json', receipt)

    def inspect(self):
        parent = self.directory.rsplit('/',1)[0]
        require(all(name == self.request['decision_id'] and kind == 'directory' for name,kind in self.listing(parent)),
                'semantic answer directory contains an unknown question')
        require(all(name in {'responses','receipts'} and kind == 'directory' for name,kind in self.listing(self.directory)),
                'unknown semantic answer artifact')
        responses = {}
        for name,kind in self.listing(self.directory+'/responses'):
            require(kind == 'file' and re.fullmatch(r'resp_[0-9a-f]{64}\.json',name), 'invalid semantic response filename')
            path = self.directory+'/responses/'+name
            response = self.registry._json(path,'operator_decision_response_v1')[0]
            validate_answer_response(response, request=self.request, context=self.context, suite=self.suite)
            reference = self.response_ref(response)
            require(reference['path'] == path, 'semantic response filename differs from its identity')
            responses[path] = response
        receipts = {}
        for name,kind in self.listing(self.directory+'/receipts'):
            require(kind == 'file' and re.fullmatch(r'answer-[0-9a-f]{64}\.json',name), 'invalid semantic answer receipt filename')
            path = self.directory+'/receipts/'+name
            value = self.registry._json(path,'vnext_semantic_answer_receipt_v1')[0]
            response = responses.get(value['response']['path'])
            require(response is not None and value == self.receipt(response), 'semantic answer receipt has missing or changed sources')
            require(self.receipt_ref(value)['path'] == path, 'semantic answer receipt filename differs from its content')
            receipts[path] = value
        return responses,receipts

    def synchronize(self, token):
        # Repeat upstream immutable barriers without changing either pointer.
        self.request_journal.synchronize(token,self.header,self.outcomes)
        _,_,result,_ = self.request_journal.inspect()
        self.request_journal.finish(token,result,self.outcomes)
        for ordinal in (1,2):
            for path in self.journal.paths(self.view.creation,ordinal)[1:4]:
                self.store.publish(token,path,self.store.read(path))
        self.guard()

    def guard(self):
        self.admission.validate_authority(self.store.read)
        require(self.store.read(self.pointer_path) == canonical_json_bytes(self.view.pointer), 'semantic answer candidate decision changed')
        for reference in (self.request_ref,self.decision_ref):
            require(sha256_bytes(self.store.read(reference['path'])) == reference['hash'], 'semantic answer source changed')


def inspect_semantic_answers(store, *, admission, candidate_id):
    return _inspect_semantic_answers(store, admission=admission, candidate_id=candidate_id,
                                     source_type=SemanticAnswerSource)


def _inspect_semantic_answers(store, *, admission, candidate_id, source_type):
    source = source_type(store,admission=admission,candidate_id=candidate_id)
    responses,receipts = source.inspect()
    rows = []
    for path,response in sorted(responses.items()):
        receipt = source.receipt(response)
        reference = source.receipt_ref(receipt)
        rows.append({'response':source.response_ref(response), 'action':receipt['action'],
            'selected_option_id':response['selected_option_id'],
            'receipt':reference if reference['path'] in receipts else None})
    return {'job_id':source.request['job_id'], 'candidate_id':candidate_id, 'submission_permitted':source.current,
        'request':deepcopy(source.request_ref), 'question':deepcopy(source.request),
        'candidate_verification':deepcopy(source.decision_ref), 'answers':rows}


def submit_semantic_answer(store, *, admission, packet, dry_run=False):
    return _submit_semantic_answer(store, admission=admission, packet=packet, dry_run=dry_run,
                                  source_type=SemanticAnswerSource)


def _submit_semantic_answer(store, *, admission, packet, dry_run, source_type):
    frozen = deepcopy(packet)
    VNextSchemaRegistry().validate(frozen,'vnext_semantic_answer_input_v1')
    require(type(dry_run) is bool, 'semantic answer dry_run must be a boolean')
    def prepare():
        source = source_type(store,admission=admission,candidate_id=frozen['candidate_id'],require_current=True)
        responses,_ = source.inspect()
        response = prepare_answer(frozen,request=source.request,context=source.context,request_ref=source.request_ref,
                                  decision_ref=source.decision_ref,suite=source.suite)
        reference = source.response_ref(response)
        require(reference['path'] not in responses or responses[reference['path']] == response,
                'semantic response identity already has different bytes')
        receipt = source.receipt(response)
        return source,response,receipt,source.receipt_ref(receipt)
    if dry_run:
        _,response,receipt,reference = prepare()
        return {'response':response,'receipt':receipt,'reference':reference}
    with store.locked(admission.validate_authority) as token:
        source,response,receipt,reference = prepare()
        source.synchronize(token)
        store.publish(token,source.response_ref(response)['path'],response)
        source.guard()
        store.publish(token,reference['path'],receipt)
        _,receipts = source.inspect()
        require(receipts.get(reference['path']) == receipt, 'semantic answer receipt did not read back')
        return {'response':response,'receipt':receipt,'reference':reference}


def read_semantic_answer(store, *, admission, candidate_id, reference):
    """Read an explicitly named receipt; never choose an ambient answer."""
    source = SemanticAnswerSource(store,admission=admission,candidate_id=candidate_id)
    responses,receipts = source.inspect()
    require(isinstance(reference,dict) and set(reference) == {'path','hash'}
            and isinstance(reference['path'],str) and isinstance(reference['hash'],str),
            'semantic answer requires an exact receipt reference')
    receipt = receipts.get(reference['path'])
    require(receipt is not None and source.receipt_ref(receipt) == reference, 'selected semantic answer receipt is missing or stale')
    return {'receipt':deepcopy(receipt),'response':deepcopy(responses[receipt['response']['path']]),'question':deepcopy(source.request)}
