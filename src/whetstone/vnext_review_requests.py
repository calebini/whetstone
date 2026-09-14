"""Seed Reviewer sequence with durable claims, bounded retries and exact replay.

The sequence owns round/profile selection before a proposal is admitted. It
stops at finding admission or the pinned review budget/completion boundary.
It does not choose operator options or invoke an Editor.
"""
from copy import deepcopy
from dataclasses import dataclass
import json,re

from whetstone.vnext_contracts import VNextSchemaRegistry,canonical_json_bytes,content_identifier,decode_json,require,sha256_bytes
from whetstone.vnext_review_protocol import ReviewShapeError,prepare_seed_review,decode_seed_review


def _ref(path,value):return {'path':path,'hash':sha256_bytes(canonical_json_bytes(value))}
def _identity(transport):return {k:v for k,v in transport.items() if k!='timeout_seconds'}


@dataclass(frozen=True)
class ReviewStep:
    status: str
    round_number: int
    profile: str | None
    request_id: str | None=None
    attempts: int=0
    receipt: dict | None=None
    review: dict | None=None
    last_outcome: dict | None=None


class _Request:
    def prepare(self, run, *, round_number, profile):
        return prepare_seed_review(run, round_number=round_number, profile=profile)

    def decode_review(self, raw):
        return decode_seed_review(raw, self.preflight, feedback_path=self.feedback_path)

    def __init__(self,run,number,profile):
        self.run=run;self.store=run.store;self.schemas=VNextSchemaRegistry()
        self.preflight=self.prepare(run,round_number=number,profile=profile)
        self.number=number;self.profile=profile
        self.id=content_identifier('req','whetstone-logical-client-request-v1',
            [self.preflight.arguments['job']['job_id'],'reviewer','phase1','review',number,profile])
        self.directory='rounds/client_requests/'+self.id
        self.feedback_path=f'rounds/round-{number}/reviewer_feedback.json'
        self.advice_path=f'rounds/round-{number}/finding_advice.json'
        self.index_path=f'rounds/review_index/request-{number}.json'

    def recheck(self):
        current=self.prepare(self.run,round_number=self.number,profile=self.profile)
        require(current.input_hash==self.preflight.input_hash and current.prompt==self.preflight.prompt,'Reviewer frozen inputs changed')

    def read(self,name):
        try:return self.store.read(self.directory+'/'+name)
        except FileNotFoundError:
            self.store.read_descriptor();return None

    def packet(self,name,schema):
        raw=self.read(name)
        if raw is None:return None
        packet=decode_json(raw);require(raw==canonical_json_bytes(packet),'noncanonical Reviewer artifact')
        self.schemas.validate(packet,schema);return packet

    def header(self,transport,previous):
        self.schemas.validate(transport,'vnext_review_request_transport_v1')
        require(transport['reviewer']==self.preflight.arguments['review']['reviewer'],'Reviewer transport differs from pinned role')
        value={'schema_version':'vnext-review-request-v1','request_id':self.id,
            'job_id':self.preflight.arguments['job']['job_id'],'round_number':self.number,'profile':self.profile,
            'input_hash':self.preflight.input_hash,'previous_request_hash':previous,'transport':deepcopy(transport)}
        self.schemas.validate(value,'vnext_review_request_v1');return value

    def outcome(self,attempt,classification,raw=None,error=None,review=None):
        value={'schema_version':'vnext-review-outcome-v1','request_id':self.id,'attempt':attempt,
            'classification':classification,'response_hash':sha256_bytes(raw) if raw is not None else None,
            'error':error,'review_hash':sha256_bytes(canonical_json_bytes(review)) if review is not None else None}
        self.schemas.validate(value,'vnext_review_outcome_v1');return value

    def decode(self,attempt,raw):
        try:review=self.decode_review(raw)
        except ReviewShapeError as exc:return self.outcome(attempt,'shape_invalid',raw,error=str(exc)),None
        except ValueError as exc:return self.outcome(attempt,'invalid_review',raw,error=str(exc)),None
        return self.outcome(attempt,'valid_review',raw,review=review),review

    def prompt(self,previous):
        if previous and previous['classification']=='shape_invalid':
            return 'Correct only response JSON/schema shape under unchanged review inputs.\nPrevious shape errors:\n'+previous['error']+'\n'+self.preflight.prompt
        return self.preflight.prompt

    def receipt(self,review):
        return {'schema_version':'vnext-review-result-v1','request_id':self.id,'input_hash':self.preflight.input_hash,
            'feedback':_ref(self.feedback_path,review['feedback']),'advice':_ref(self.advice_path,review['advice']),
            'classification_hash':sha256_bytes(canonical_json_bytes({k:review[k] for k in ('findings','evidence')}))}

    def inspect(self,header):
        try:entries=self.store.list_directory(self.directory+'/attempts')
        except FileNotFoundError:self.store.read_descriptor();entries=()
        require(all(name.startswith('.vnext-tmp-') or (name in {'1','2'} and kind=='directory') for name,kind in entries),
                'unknown Reviewer attempt or budget extension')
        original=self.read('original_prompt.txt')
        require(original is None or original==self.preflight.prompt.encode(),'Reviewer prompt changed')
        outcomes=[];review=None;previous=None
        for attempt in (1,2):
            prefix=f'attempts/{attempt}/';marker=self.packet(prefix+'invocation.json','vnext_review_invocation_v1')
            raw=self.read(prefix+'response.json');stored=self.packet(prefix+'outcome.json','vnext_review_outcome_v1')
            if marker is None:
                require(raw is None and stored is None and self.read(prefix+'telemetry.json') is None,
                        'Reviewer response/outcome/telemetry lacks an invocation')
                if attempt==1:
                    require(not any(self.read('attempts/2/'+name) is not None for name in ('invocation.json','response.json','outcome.json','telemetry.json','prompt.txt')),
                            'Reviewer second attempt lacks its first invocation')
                break
            require(header is not None,'Reviewer invocation has no durable request claim')
            require(previous is None or previous['classification'] not in {'valid_review','invalid_review'},'closed Reviewer outcome cannot be retried')
            require(marker['request_id']==self.id and marker['attempt']==attempt and marker['input_hash']==self.preflight.input_hash,
                    'Reviewer invocation binding differs')
            require(_identity(marker['transport'])==_identity(header['transport']),'Reviewer invocation transport changed')
            require(attempt!=1 or marker['transport']==header['transport'],'initial Reviewer transport differs from its request claim')
            require(marker['previous_outcome_hash']==(sha256_bytes(canonical_json_bytes(previous)) if previous else None),
                    'Reviewer predecessor outcome differs')
            expected_reason='initial' if previous is None else ('shape_retry' if previous['classification']=='shape_invalid' else 'technical_continuation')
            require(marker['reason']==expected_reason,'Reviewer invocation reason differs')
            prompt=self.prompt(previous).encode()
            require(marker['prompt_hash']==sha256_bytes(prompt) and self.read(prefix+'prompt.txt')==prompt,'Reviewer invocation prompt differs')
            if attempt==2:require(self.read('attempts/1/outcome.json') is not None,'Reviewer committed predecessor outcome is missing')
            if raw is not None:expected,review=self.decode(attempt,raw)
            else:
                require(stored is None or (stored['classification'] in {'timeout','transport_failure','interrupted'}
                    and stored['response_hash'] is None and stored['review_hash'] is None and bool(stored['error'])),
                    'Reviewer no-response outcome is contradictory')
                expected=stored or self.outcome(attempt,'interrupted',error='Invocation has no durable response or failure outcome.')
            require(stored is None or stored==expected,'Reviewer outcome differs from exact response replay')
            outcomes.append(expected);previous=expected
        receipt=self.packet('result.json','vnext_review_result_v1')
        require(header is not None or (original is None and not outcomes and receipt is None),'Reviewer artifacts have no request claim')
        if receipt is not None:
            require(review is not None and receipt==self.receipt(review),'Reviewer result receipt differs from decoded evidence')
            for key in ('feedback','advice'):
                require(self.store.read(receipt[key]['path'])==canonical_json_bytes(review[key]),'canonical Reviewer evidence changed')
        return outcomes,review,receipt

    def synchronize(self,token,header,outcomes):
        self.store.publish(token,self.index_path,header)
        self.store.publish(token,self.directory+'/original_prompt.txt',self.preflight.prompt.encode())
        for outcome in outcomes:
            prefix=self.directory+f"/attempts/{outcome['attempt']}/"
            for name in ('prompt.txt','invocation.json','response.json'):
                raw=self.read(f"attempts/{outcome['attempt']}/"+name)
                if raw is not None:self.store.publish(token,prefix+name,raw)
            self.store.publish(token,prefix+'outcome.json',outcome)

    def finish(self,token,review):
        self.recheck()
        for path,value in ((self.feedback_path,review['feedback']),(self.advice_path,review['advice'])):
            self.store.publish(token,path,value)
        receipt=self.receipt(review);self.schemas.validate(receipt,'vnext_review_result_v1')
        self.store.publish(token,self.directory+'/result.json',receipt)
        return receipt


def _selection(profiles,mode,completed):
    counts={p['name']:0 for p in profiles};clean={name:False for name in counts}
    for request,header,outcomes,review,receipt in completed:
        if any(f['classification']!='deferable' for f in review['findings']):return 'finding_admission',request.profile
        counts[request.profile]+=1
        clean[request.profile]=not any(f['in_scope'] and f['normalized_severity'] in {'major','blocker'} for f in review['feedback']['feedback'])
    if all(clean.values()):return 'phase_1_stable',None
    if any(not clean[p['name']] and counts[p['name']]>=p['budget'] for p in profiles):return 'budget_exhausted',None
    names=[p['name'] for p in profiles]
    if mode=='vertical' and completed:
        start=(names.index(completed[-1][0].profile)+1)%len(names);names=names[start:]+names[:start]
    return 'review',next(name for name in names if not clean[name])


def _sequence(run):
    run.validate_authority(run.store.read)
    require(not run._staged,'live seed review cannot import preselected proposal rounds')
    _,values=run._admission(run.store.read)._base(run.store.read)
    try:entries=run.store.list_directory('rounds/review_index')
    except FileNotFoundError:run.store.read_descriptor();entries=()
    numbered={}
    for name,kind in entries:
        if name.startswith('.vnext-tmp-'):continue
        match=re.fullmatch(r'request-([1-9][0-9]*)\.json',name)
        require(match is not None and kind=='file','invalid Reviewer sequence claim')
        numbered[int(match[1])]=name
    require(sorted(numbered)==list(range(1,len(numbered)+1)),'Reviewer sequence has an ordinal gap')
    if not numbered:
        require(not any(name.startswith('round-') for name,kind in run.store.list_directory('rounds')),
                'live review requires a seed-only run without prior round processing')
    completed=[];previous=None;pending=None
    for number in sorted(numbered):
        gate,profile=_selection(values['review']['profiles'],values['review']['review_mode'],completed)
        require(gate=='review','Reviewer sequence continues beyond its finding/budget boundary')
        request=_Request(run,number,profile)
        raw=run.store.read(request.index_path);header=decode_json(raw)
        require(raw==canonical_json_bytes(header),'noncanonical Reviewer request claim')
        request.schemas.validate(header,'vnext_review_request_v1')
        require(header==request.header(header['transport'],previous),'Reviewer sequence claim differs from selected work')
        outcomes,review,receipt=request.inspect(header)
        if receipt is None:
            require(number==len(numbered),'Reviewer sequence skips an incomplete request')
            pending=(request,header,outcomes,review,receipt);break
        completed.append((request,header,outcomes,review,receipt));previous=sha256_bytes(raw)
    gate,profile=_selection(values['review']['profiles'],values['review']['review_mode'],completed)
    if gate=='review' and pending is None:
        for name,kind in run.store.list_directory('rounds'):
            if not re.fullmatch(r'round-[1-9][0-9]*',name):continue
            try:run.store.read('rounds/'+name+'/proposal_input.json')
            except FileNotFoundError:continue
            require(False,'proposal processing must finish before another Reviewer request')
    return completed,pending,gate,profile,previous


def _result(status,request,outcomes,review=None,receipt=None):
    return ReviewStep(status,request.number,request.profile,request.id,len(outcomes),deepcopy(receipt),deepcopy(review),
                      deepcopy(outcomes[-1]) if outcomes else None)


def inspect_seed_review(run):
    completed,pending,gate,profile,previous=_sequence(run)
    if pending:
        request,header,outcomes,review,receipt=pending
        status='valid_response' if review else ('invalid_review' if outcomes and outcomes[-1]['classification']=='invalid_review'
            else 'attempts_exhausted' if len(outcomes)==2 else outcomes[-1]['classification'] if outcomes else 'prepared')
        return _result(status,request,outcomes,review,receipt)
    if gate!='review':
        request,header,outcomes,review,receipt=completed[-1]
        return _result(gate,request,outcomes,review,receipt)
    return ReviewStep('not_started',len(completed)+1,profile)


def validate_review_binding(run,number,record):
    """Runtime-produced canonical feedback must retain its exact Reviewer proof."""
    expected=f'rounds/round-{number}/reviewer_feedback.json'
    try:claims=run.store.list_directory('rounds/review_index')
    except FileNotFoundError:run.store.read_descriptor();claims=()
    # Once a live sequence exists, alternate input paths cannot bypass it.
    if record['feedback']['path']!=expected and not claims:return
    completed,pending,gate,profile,previous=_sequence(run)
    match=next((entry for entry in completed if entry[0].number==number),None)
    require(match is not None,'round lacks its committed Reviewer result')
    receipt=match[4]
    require(record['feedback']==receipt['feedback'] and record['advice']==receipt['advice'],
            'proposal admission differs from the committed Reviewer feedback/advice')


def run_next_seed_review(run,*,client,continuation=False):
    require(type(continuation) is bool,'Reviewer continuation must be an explicit boolean')
    with run.store.locked(run.validate_authority) as token:
        completed,pending,gate,profile,previous=_sequence(run)
        for prior_request,prior_header,prior_outcomes,prior_review,prior_receipt in completed:
            prior_request.synchronize(token,prior_header,prior_outcomes)
            prior_request.finish(token,prior_review)
        if pending:request,header,outcomes,review,receipt=pending
        elif gate!='review':
            request,header,outcomes,review,receipt=completed[-1]
            require(not continuation,'no incomplete Reviewer gate remains')
            request.synchronize(token,header,outcomes);request.finish(token,review)
            return _result(gate,request,outcomes,review,receipt)
        else:
            require(not continuation,'no interrupted Reviewer request exists')
            request=_Request(run,len(completed)+1,profile);header=None
            outcomes,review,receipt=request.inspect(None)
        return _drive_request(request, token, header=header, outcomes=outcomes, review=review,
                              previous=previous, client=client, continuation=continuation, receipt=receipt)


def _drive_request(request, token, *, header, outcomes, review, previous, client, continuation, receipt=None):
    """Shared durable transport loop; callers own mode, base and work selection."""
    transport=deepcopy(client.transport_binding)
    expected=request.header(transport,previous)
    require(client.identity==request.preflight.arguments['review']['reviewer'],'Reviewer client differs from pinned identity')
    if header is not None:
        require(_identity(header['transport'])==_identity(transport),'Reviewer transport identity changed')
        if not continuation:return _result('continuation_required',request,outcomes,review,receipt)
        require(outcomes or header['transport']==transport,
                'first Reviewer invocation must use its claimed transport')
    else:header=expected
    request.synchronize(token,header,outcomes)
    if review is not None:
        receipt=request.finish(token,review);return _result('complete',request,outcomes,review,receipt)
    if outcomes and outcomes[-1]['classification']=='invalid_review':return _result('invalid_review',request,outcomes)
    while len(outcomes)<2:
        prior=outcomes[-1] if outcomes else None;attempt=len(outcomes)+1
        request.recheck();require(client.transport_binding==transport,'Reviewer transport changed before invocation')
        prompt=request.prompt(prior);prefix=request.directory+f'/attempts/{attempt}/'
        request.store.publish(token,prefix+'prompt.txt',prompt.encode())
        marker={'schema_version':'vnext-review-invocation-v1','request_id':request.id,'attempt':attempt,
            'input_hash':request.preflight.input_hash,'prompt_hash':sha256_bytes(prompt.encode()),'transport':transport,
            'previous_outcome_hash':sha256_bytes(canonical_json_bytes(prior)) if prior else None,
            'reason':'initial' if prior is None else 'shape_retry' if prior['classification']=='shape_invalid' else 'technical_continuation'}
        request.schemas.validate(marker,'vnext_review_invocation_v1');request.store.publish(token,prefix+'invocation.json',marker)
        failure=None;raw=None
        try:raw=client.review(prompt)
        except Exception as exc:failure=exc
        telemetry=getattr(client,'last_telemetry',None)
        if telemetry is not None:request.store.publish(token,prefix+'telemetry.json',json.dumps(telemetry,sort_keys=True).encode())
        if failure is not None:
            outcome=request.outcome(attempt,'timeout' if isinstance(failure,TimeoutError) else 'transport_failure',
                error=type(failure).__name__+': '+str(failure))
            request.store.publish(token,prefix+'outcome.json',outcome);outcomes.append(outcome)
            return _result(outcome['classification'],request,outcomes)
        require(isinstance(raw,bytes),'Reviewer transport must retain exact response bytes')
        request.store.publish(token,prefix+'response.json',raw);request.recheck()
        require(client.transport_binding==transport,'Reviewer transport changed during invocation')
        outcome,review=request.decode(attempt,raw);request.store.publish(token,prefix+'outcome.json',outcome);outcomes.append(outcome)
        if review is not None:
            receipt=request.finish(token,review);return _result('complete',request,outcomes,review,receipt)
        if outcome['classification']=='invalid_review':return _result('invalid_review',request,outcomes)
    return _result('attempts_exhausted',request,outcomes)
