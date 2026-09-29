"""Unactivated D7 Editor request journal with bounded explicit continuation.

The caller owns suite/current-authority and immutable-input admission. Requests
are run-wide by job/transaction, never by a caller-selected attempt directory.
No candidate registration, verification or promotion occurs in this module.
"""
from copy import deepcopy
from dataclasses import dataclass
import json

from whetstone.vnext_assembly import ASSEMBLER_VERSION, NORMALIZATION_VERSION
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, content_identifier, decode_json, require, sha256_bytes
from whetstone.vnext_inventory import INVENTORY_VERSION
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_unit_protocol import ProposalShapeError, decode_unit_response


@dataclass(frozen=True)
class ProposalRequestResult:
    request_id: str
    status: str
    attempts: int
    proposal: object | None = None
    reference: dict | None = None
    last_outcome: dict | None = None


def logical_request_id(job_id,transaction_id):
    return content_identifier('req','whetstone-logical-client-request-v1',
                              [job_id,'editor','phase1','proposal',transaction_id])


def _identity(transport):return {key:value for key,value in transport.items() if key!='timeout_seconds'}


class _Journal:
    def __init__(self,store,load_inputs):
        self.store=store;self.load_inputs=load_inputs;self.schemas=VNextSchemaRegistry()
        self.arguments,self.preflight=self.load()
        job=self.arguments['job']
        self.schemas.validate(job,'job_descriptor_v2')
        require(canonical_json_bytes(job)==store.read_descriptor(),'proposal descriptor differs from storage binding')
        require(job['contract_suite_version']!='vnext-contracts-1','frozen suite has no durable proposal request capability')
        require(job['contract_suite_version']==self.arguments['suite'].version,'proposal suite selection differs')
        from whetstone.vnext_version_operations import ASSEMBLER, pins as version_pins
        assembler=ASSEMBLER_VERSION
        if job['assembler_version']==ASSEMBLER:
            version_pins(self.arguments['suite']); assembler=ASSEMBLER
        for key,value in [('assembler_version',assembler),('normalization_version',NORMALIZATION_VERSION),('inventory_version',INVENTORY_VERSION)]:
            require(job[key]==value,'proposal request algorithm differs: '+key)
        self.request_id=logical_request_id(job['job_id'],self.preflight.plan['transaction_id'])
        self.directory='rounds/client_requests/'+self.request_id

    def load(self):
        values=self.load_inputs(self.store.read)
        arguments={**deepcopy({k:v for k,v in values.items() if k!='suite'}),'suite':values['suite']}
        self.validate_base(arguments)
        return arguments,prepare_unit_preflight(**arguments)

    def validate_base(self, arguments):
        pointer=arguments['base_pointer_ref']
        raw=self.store.read(pointer['path'])
        require(sha256_bytes(raw)==pointer['hash'] and self.store.read('rounds/current_verified.json')==raw,
                'proposal request base pointer is no longer current')

    def recheck(self):
        arguments,preflight=self.load()
        require(preflight.input_hash==self.preflight.input_hash and preflight.prompt==self.preflight.prompt,
                'proposal request frozen inputs changed')
        return arguments,preflight

    def read(self,name):
        try:return self.store.read(self.directory+'/'+name)
        except FileNotFoundError:
            self.store.read_descriptor()
            return None

    def json(self,name,schema):
        raw=self.read(name)
        if raw is None:return None
        value=decode_json(raw);require(raw==canonical_json_bytes(value),'noncanonical request artifact',name)
        self.schemas.validate(value,schema);return value

    def publish(self,token,name,value):return self.store.publish(token,self.directory+'/'+name,value)

    def header(self,transport):
        p=self.preflight
        return {'schema_version':'vnext-proposal-request-v1','request_id':self.request_id,
            'job_id':self.arguments['job']['job_id'],'transaction_id':p.plan['transaction_id'],
            'role':'editor','phase':'phase1','gate':'proposal','input_hash':p.input_hash,
            'plan_hash':sha256_bytes(canonical_json_bytes(p.plan)),'inventory_hash':sha256_bytes(canonical_json_bytes(p.inventory)),
            'prompt_hash':sha256_bytes(p.prompt.encode()),'base_pointer':self.arguments['base_pointer_ref'],
            'transport':deepcopy(transport),'maximum_attempts':2,'maximum_shape_retries':1}

    def check_transport(self,transport):
        self.schemas.validate(transport,'vnext_proposal_request_transport_v1')
        require(transport['editor']==self.arguments['review']['editor'],'request transport differs from pinned Editor')

    def prompt(self,previous):
        if previous is None or previous['classification']!='shape_invalid':return self.preflight.prompt
        return ('Correct only the response JSON/schema shape under the unchanged frozen authorization.\n'
                'Previous shape validation errors:\n'+previous['error']+'\n\n'+self.preflight.prompt)

    def outcome(self,attempt,classification,*,raw=None,error=None,proposal=None):
        value={'schema_version':'vnext-proposal-request-outcome-v1','request_id':self.request_id,'attempt':attempt,
            'classification':classification,'response_hash':sha256_bytes(raw) if raw is not None else None,
            'proposal_hash':proposal.digest if proposal is not None else None,'error':error}
        self.schemas.validate(value,'vnext_proposal_request_outcome_v1');return value

    def decode(self,attempt,raw):
        try:
            proposal=decode_unit_response(raw,self.preflight,base=self.arguments['base'],
                section_map=self.arguments['base_map'],editor=self.arguments['review']['editor'])
        except ProposalShapeError as exc:
            return self.outcome(attempt,'shape_invalid',raw=raw,error=str(exc)),None
        except ValueError as exc:
            return self.outcome(attempt,'invalid_proposal',raw=raw,error=str(exc)),None
        return self.outcome(attempt,'valid_proposal',raw=raw,proposal=proposal),proposal

    def inspect(self):
        header=self.json('request.json','vnext_proposal_request_v1')
        if header is None:
            try:entries=self.store.list_directory(self.directory)
            except FileNotFoundError:
                self.store.read_descriptor();entries=()
            require(not any(not name.startswith('.vnext-tmp-') for name,_ in entries),'request artifacts have no request binding')
            return None,[],None,None
        self.check_transport(header['transport'])
        require(header==self.header(header['transport']),'request binding differs from frozen inputs')
        for name,raw in [('mutation_plan.json',canonical_json_bytes(self.preflight.plan)),
                         ('base_inventory.json',canonical_json_bytes(self.preflight.inventory)),
                         ('original_prompt.txt',self.preflight.prompt.encode())]:
            actual=self.read(name)
            require(actual is None or actual==raw,'request preflight evidence changed',name)
        try:entries=self.store.list_directory(self.directory+'/attempts')
        except FileNotFoundError:
            self.store.read_descriptor();entries=()
        require(all(name.startswith('.vnext-tmp-') or (name in {'1','2'} and kind=='directory') for name,kind in entries),
                'unknown request attempt or allowance extension')
        outcomes=[];proposal=None;previous=None
        for attempt in (1,2):
            prefix=f'attempts/{attempt}/'
            marker=self.json(prefix+'invocation.json','vnext_proposal_request_invocation_v1')
            raw=self.read(prefix+'response.json')
            stored=self.json(prefix+'outcome.json','vnext_proposal_request_outcome_v1')
            prompt=self.prompt(previous);actual_prompt=self.read(prefix+'prompt.txt')
            require(actual_prompt is None or actual_prompt==prompt.encode(),'request attempt prompt differs')
            if marker is None:
                require(raw is None and stored is None and self.read(prefix+'telemetry.json') is None,
                        'request response/outcome/telemetry lacks invocation evidence')
                if attempt==1:
                    require(all(self.read('attempts/2/'+name) is None for name in ('prompt.txt','invocation.json','response.json','outcome.json','telemetry.json')),
                            'request attempt chain has a gap')
                break
            require(actual_prompt is not None,'invocation lacks its immutable prompt')
            require(all(self.read(name) is not None for name in ('mutation_plan.json','base_inventory.json','original_prompt.txt')),
                    'invocation lacks immutable preflight evidence')
            self.check_transport(marker['transport'])
            require(_identity(marker['transport'])==_identity(header['transport']),'attempt transport identity changed')
            reason='initial' if previous is None else ('shape_retry' if previous['classification']=='shape_invalid' else 'technical_continuation')
            if previous is not None:
                require(previous['classification'] in {'shape_invalid','timeout','transport_failure','interrupted'},'attempt reopens a completed or invalid proposal')
                require(self.read('attempts/1/outcome.json') is not None,'second invocation lost its committed predecessor outcome')
            expected={'schema_version':'vnext-proposal-request-invocation-v1','request_id':self.request_id,'attempt':attempt,
                'input_hash':self.preflight.input_hash,'prompt_hash':sha256_bytes(prompt.encode()),'transport':marker['transport'],
                'reason':reason,'previous_outcome_hash':sha256_bytes(canonical_json_bytes(previous)) if previous else None}
            require(marker==expected,'request invocation lineage differs')
            if raw is not None:
                outcome,proposal=self.decode(attempt,raw)
                require(stored is None or stored==outcome,'request outcome contradicts exact response replay')
            elif stored is not None:
                require(stored['classification'] in {'timeout','transport_failure','interrupted'}
                    and stored==self.outcome(attempt,stored['classification'],error=stored['error']) and bool(stored['error']),
                    'request outcome lacks its response or failure evidence')
                outcome=stored
            else:outcome=self.outcome(attempt,'interrupted',error='Invocation has no durable response or completion record.')
            outcomes.append(outcome);previous=outcome
        receipt=self.json('proposal_result.json','vnext_proposal_result_v1')
        if receipt is not None:
            require(proposal is not None,'completed request has no valid response')
            require(receipt==self.receipt(proposal),'request receipt differs from valid response')
            prefix='proposals/'+proposal.patch['proposal_id']
            require(self.read(prefix+'/proposed_patch.json')==canonical_json_bytes(proposal.patch),'completed request patch changed')
            for path,raw in proposal.payloads.items():require(self.read(prefix+'/'+path)==raw,'completed request payload changed')
        return header,outcomes,proposal,receipt

    def receipt(self,proposal):
        return {'schema_version':'vnext-proposal-result-v1',
            'proposal':{'path':self.directory+'/proposals/'+proposal.patch['proposal_id']+'/proposed_patch.json','hash':proposal.digest},
            'mutation_plan_hash':sha256_bytes(canonical_json_bytes(self.preflight.plan)),
            'base_pointer':self.arguments['base_pointer_ref'],'candidate_registered':False,'verified':False,'promoted':False}

    def result(self,status,outcomes,proposal=None,reference=None):
        return ProposalRequestResult(self.request_id,status,len(outcomes),proposal,reference,
                                     deepcopy(outcomes[-1]) if outcomes else None)

    def synchronize(self,token,header,outcomes):
        """Replay complete evidence barriers; callers must inspect it first."""
        self.publish(token,'request.json',header)
        for name,value in [('mutation_plan.json',self.preflight.plan),('base_inventory.json',self.preflight.inventory),
                           ('original_prompt.txt',self.preflight.prompt.encode())]:self.publish(token,name,value)
        for outcome in outcomes:
            prefix=f"attempts/{outcome['attempt']}/"
            for name in ('prompt.txt','invocation.json','response.json'):
                raw=self.read(prefix+name)
                if raw is not None:self.publish(token,prefix+name,raw)
            self.publish(token,prefix+'outcome.json',outcome)

    def finish(self,token,proposal):
        prefix='proposals/'+proposal.patch['proposal_id']
        for path,raw in sorted(proposal.payloads.items()):self.publish(token,prefix+'/'+path,raw)
        self.publish(token,prefix+'/proposed_patch.json',proposal.patch)
        receipt=self.receipt(proposal);self.schemas.validate(receipt,'vnext_proposal_result_v1')
        self.publish(token,'proposal_result.json',receipt)
        return receipt


def inspect_proposal_request(store,*,load_inputs,validate_authority):
    """Derive request status without a client, exclusive lock, or repair."""
    validate_authority(store.read)
    journal=_Journal(store,load_inputs);header,outcomes,proposal,receipt=journal.inspect()
    if receipt is not None:status='complete'
    elif proposal is not None:status='valid_response'
    elif outcomes and outcomes[-1]['classification']=='invalid_proposal':status='invalid_proposal'
    elif len(outcomes)==2:status='attempts_exhausted'
    elif outcomes:status=outcomes[-1]['classification']
    else:status='prepared' if header is not None else 'not_started'
    return journal.result(status,outcomes,proposal,receipt['proposal'] if receipt else None)


def finish_proposal_request(store,*,load_inputs,validate_authority,continuation=False):
    """Materialize already validated output on explicit continuation, without a client."""
    require(continuation is True,'request materialization requires explicit continuation')
    with store.locked(validate_authority) as token:
        journal=_Journal(store,load_inputs)
        header,outcomes,proposal,_=journal.inspect()
        require(header is not None and proposal is not None,'request has no valid retained output to materialize')
        journal.synchronize(token,header,outcomes)
        receipt=journal.finish(token,proposal)
        return journal.result('complete',outcomes,proposal,receipt['proposal'])


def run_proposal_request(store,*,load_inputs,validate_authority,client,continuation=False):
    """Two total calls; at most one shape retry; technical retry requires opt-in.

    Re-entering without continuation can read a completed result, but cannot
    advance interrupted work. Timeout is the sole mutable transport setting on
    explicit continuation. Durable invocation markers consume the call budget.
    """
    require(type(continuation) is bool,'continuation must be explicit boolean')
    with store.locked(validate_authority) as token:
        journal=_Journal(store,load_inputs);transport=deepcopy(client.transport_binding)
        journal.check_transport(transport)
        require(client.identity==journal.arguments['review']['editor'],'client identity differs from pinned Editor')
        header,outcomes,proposal,receipt=journal.inspect()
        if header is not None:
            require(_identity(header['transport'])==_identity(transport),'request transport identity changed')
            if receipt is None and not continuation:
                if proposal is None and outcomes and outcomes[-1]['classification']=='invalid_proposal':
                    return journal.result('invalid_proposal',outcomes)
                if proposal is None and len(outcomes)==2:
                    return journal.result('attempts_exhausted',outcomes)
                return journal.result('continuation_required',outcomes)
        else:header=journal.header(transport)
        # Re-establish durability of complete retained evidence. Missing
        # derived outcomes can be reconstructed, but missing bound inputs cannot.
        journal.synchronize(token,header,outcomes)
        if proposal is not None:
            receipt=journal.finish(token,proposal)
            return journal.result('complete',outcomes,proposal,receipt['proposal'])
        if outcomes and outcomes[-1]['classification']=='invalid_proposal':
            return journal.result('invalid_proposal',outcomes)
        while len(outcomes)<2:
            previous=outcomes[-1] if outcomes else None;attempt=len(outcomes)+1
            prompt=journal.prompt(previous);journal.recheck()
            require(client.transport_binding==transport,'request transport changed before invocation')
            prefix=f'attempts/{attempt}/'
            journal.publish(token,prefix+'prompt.txt',prompt.encode())
            marker={'schema_version':'vnext-proposal-request-invocation-v1','request_id':journal.request_id,'attempt':attempt,
                'input_hash':journal.preflight.input_hash,'prompt_hash':sha256_bytes(prompt.encode()),'transport':transport,
                'reason':'initial' if previous is None else ('shape_retry' if previous['classification']=='shape_invalid' else 'technical_continuation'),
                'previous_outcome_hash':sha256_bytes(canonical_json_bytes(previous)) if previous else None}
            journal.schemas.validate(marker,'vnext_proposal_request_invocation_v1')
            journal.publish(token,prefix+'invocation.json',marker)
            failure=None;raw=None
            try:raw=client.propose(prompt)
            except Exception as exc:failure=exc
            telemetry=getattr(client,'last_telemetry',None)
            if telemetry is not None:journal.publish(token,prefix+'telemetry.json',json.dumps(telemetry,sort_keys=True).encode())
            if failure is not None:
                outcome=journal.outcome(attempt,'timeout' if isinstance(failure,TimeoutError) else 'transport_failure',
                                        error=type(failure).__name__+': '+str(failure))
                journal.publish(token,prefix+'outcome.json',outcome)
                outcomes.append(outcome)
                return journal.result(outcome['classification'],outcomes)
            require(isinstance(raw,bytes),'proposal transport must return exact bytes')
            journal.publish(token,prefix+'response.json',raw)
            journal.recheck();require(client.transport_binding==transport,'request transport changed during invocation')
            outcome,proposal=journal.decode(attempt,raw)
            journal.publish(token,prefix+'outcome.json',outcome);outcomes.append(outcome)
            if proposal is not None:
                receipt=journal.finish(token,proposal)
                return journal.result('complete',outcomes,proposal,receipt['proposal'])
            if outcome['classification']=='invalid_proposal':
                return journal.result('invalid_proposal',outcomes)
            # Only this freshly validated shape failure loops automatically.
        return journal.result('attempts_exhausted',outcomes)
