"""Exact completed-request handoff into the isolated candidate registry.

No client is accepted or invoked. Domain callbacks still own supported-suite,
current-authority and immutable round admission. This is not public activation.
"""
from copy import deepcopy

from whetstone.vnext_candidate_registry import CandidateRegistry, RegistrationView
from whetstone.vnext_contracts import VNextSchemaRegistry,canonical_json_bytes,decode_json,require,sha256_bytes
from whetstone.vnext_proposal_requests import _Journal


def _path(round_number):return f'rounds/round-{round_number}/proposal_handoff.json'
def _ref(path,raw):return {'path':path,'hash':sha256_bytes(raw)}


def proposal_inputs(load_inputs,read,round_number,proposal_id):
    """Explicit immutable proposal selection supplied by the admission owner."""
    resolver=getattr(load_inputs,'for_proposal',None)
    return resolver(read,round_number,proposal_id) if resolver is not None else load_inputs(read,round_number)


def _handoff_path(handoff):
    return handoff['plan']['path'].rsplit('/',1)[0]+'/proposal_handoff.json'


def _prepare(store,round_number,load_inputs,proposal_id=None):
    require(type(round_number) is int and round_number>=1,'invalid proposal handoff round')
    factory=getattr(load_inputs,'request_journal',None)
    journal=factory(store,round_number,proposal_id) if factory is not None else _Journal(
        store,lambda read:proposal_inputs(load_inputs,read,round_number,proposal_id)
                     if proposal_id is not None else load_inputs(read,round_number))
    require(journal.arguments['feedback']['round_number']==round_number,'request Reviewer evidence belongs to another round')
    header,outcomes,proposal,receipt=journal.inspect()
    require(receipt is not None and proposal is not None,'proposal handoff requires a completed durable request')
    prefix=f"rounds/round-{round_number}/proposals/{proposal.patch['proposal_id']}"
    plan_path=f'rounds/round-{round_number}/mutation_plan.json'
    if journal.preflight.plan['schema_version']=='mutation-plan-v3':
        plan_path=f"rounds/round-{round_number}/transactions/{journal.preflight.plan['transaction_id']}/mutation_plan.json"
    artifacts={plan_path:canonical_json_bytes(journal.preflight.plan)}
    artifacts.update({prefix+'/'+path:raw for path,raw in sorted(proposal.payloads.items())})
    artifacts[prefix+'/proposed_patch.json']=canonical_json_bytes(proposal.patch)
    handoff={'schema_version':'vnext-proposal-handoff-v1','job_id':journal.arguments['job']['job_id'],
        'round_number':round_number,'request_id':journal.request_id,'transaction_id':journal.preflight.plan['transaction_id'],
        'input_hash':journal.preflight.input_hash,'base_pointer':journal.arguments['base_pointer_ref'],
        'request':_ref(journal.directory+'/request.json',canonical_json_bytes(header)),
        'request_result':_ref(journal.directory+'/proposal_result.json',canonical_json_bytes(receipt)),
        'plan':_ref(plan_path,artifacts[plan_path]),'proposal':_ref(prefix+'/proposed_patch.json',artifacts[prefix+'/proposed_patch.json'])}
    VNextSchemaRegistry().validate(handoff,'vnext_proposal_handoff_v1')
    return journal,header,outcomes,proposal,handoff,artifacts


def _existing(store,round_number,*,path=None):
    try:raw=store.read(path or _path(round_number))
    except FileNotFoundError:
        store.read_descriptor();return None
    value=decode_json(raw)
    require(raw==canonical_json_bytes(value),'noncanonical proposal handoff receipt')
    VNextSchemaRegistry().validate(value,'vnext_proposal_handoff_v1')
    return value


def validate_proposal_handoff(store,*,round_number,load_inputs,validate_authority):
    """Read-only exact replay; never finishes a partially copied handoff."""
    validate_authority(store.read)
    journal,_,_,_,expected,artifacts=_prepare(store,round_number,load_inputs)
    require(_existing(store,round_number,path=_handoff_path(expected))==expected,'missing or conflicting proposal handoff receipt')
    for path,raw in artifacts.items():require(store.read(path)==raw,'round proposal differs from completed request',path)
    return deepcopy(expected)


def handoff_proposal_request(store,*,round_number,load_inputs,validate_authority,expected_proposal_id=None):
    """Publish exact round copies and commit their handoff receipt last."""
    with store.locked(validate_authority) as token:
        journal,header,outcomes,proposal,handoff,artifacts=_prepare(store,round_number,load_inputs)
        require(expected_proposal_id is None or expected_proposal_id==proposal.patch['proposal_id'],
                'registration selected a different proposal than the completed request')
        existing=_existing(store,round_number,path=_handoff_path(handoff))
        require(existing is None or existing==handoff,'round already binds a different completed request')
        # Do not call a client to establish or reconstruct source authority.
        journal.synchronize(token,header,outcomes);journal.finish(token,proposal)
        for path,raw in artifacts.items():store.publish(token,path,raw)
        for path,raw in artifacts.items():require(store.read(path)==raw,'handoff artifact changed before receipt publication')
        journal.recheck()
        store.publish(token,_handoff_path(handoff),handoff)
        return validate_proposal_handoff(store,round_number=round_number,load_inputs=load_inputs,validate_authority=validate_authority)


def registry_for_proposal_requests(store,*,load_inputs,validate_authority):
    """Registry input loader derived from exact completed request admission.

    This current-base implementation is suitable for the bounded proposal-only
    path. Historical promoted-base loading must qualify before promotion uses
    it; it never silently substitutes the current draft for an older base.
    """
    def assessment_inputs(read,round_number,proposal_id):
        journal,_,_,proposal,expected,artifacts=_prepare(store,round_number,load_inputs,proposal_id)
        require(proposal.patch['proposal_id']==proposal_id,'registration selected a different proposal than the handoff')
        require(_existing(store,round_number,path=_handoff_path(expected))==expected,'registration lacks its exact completed-request handoff')
        for path,raw in artifacts.items():require(read(path)==raw,'registered round input changed after handoff',path)
        values=journal.arguments
        return {**({'plan_reference':expected['plan']} if journal.preflight.plan['schema_version']=='mutation-plan-v3' else {}),
            **{key:values[key] for key in ('authority','invariants','seed','seed_map','base','base_map','review')},
            'base_inventory':journal.preflight.inventory,'bindings':journal.preflight.bindings,'rules':journal.preflight.rules}
    class RequestCandidateRegistry(CandidateRegistry):
        def inspect(self):
            limit=getattr(load_inputs,'history_limit',None)
            if limit is None:return super().inspect()
            # Evidence-only prefix: the outer admission validates the full
            # applicable registry. Never expose this view as a writer.
            self.validate_authority(self.store.read)
            return RegistrationView(tuple(self._chain(limit)),())

        def reconcile(self):
            require(getattr(load_inputs,'history_limit',None) is None,'historical registry is read-only')
            return super().reconcile()

        def register(self,*,round_number,proposal_id,created_at):
            require(getattr(load_inputs,'history_limit',None) is None,'historical registry is read-only')
            # Every registration entry point repeats the handoff barriers; a
            # visible receipt alone cannot prove a prior durable acknowledgement.
            handoff_proposal_request(store,round_number=round_number,load_inputs=load_inputs,
                                     validate_authority=validate_authority,expected_proposal_id=proposal_id)
            return super().register(round_number=round_number,proposal_id=proposal_id,created_at=created_at)
    job=decode_json(store.read_descriptor())
    return RequestCandidateRegistry(store,job=job,validate_authority=validate_authority,load_inputs=assessment_inputs)


def register_completed_proposal_request(store,*,round_number,load_inputs,validate_authority,created_at):
    validate_authority(store.read)
    _,_,_,proposal,_,_=_prepare(store,round_number,load_inputs)
    registry=registry_for_proposal_requests(store,load_inputs=load_inputs,validate_authority=validate_authority)
    return registry.register(round_number=round_number,proposal_id=proposal.patch['proposal_id'],created_at=created_at)
