"""System-only Phase 2 version candidates using ordinary V journals/finality.

The storage round is the last real prerequisite review's locator, not a new
review or a budget charge. Entry authority comes from the immutable request.
"""
from copy import copy, deepcopy

from whetstone.vnext_contracts import (CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes,
    confined_file, content_identifier, decode_json, require, sha256_bytes)
from whetstone.vnext_version_operations import ASSEMBLER, pins as operation_pins, plan_context

ALGORITHM='algorithms/vnext_version_entry_v1.md'
ADMISSION='rounds/phase2/version_admission.json'


def pins(suite):
    operation_pins(suite)
    entries={r['path']:r for group in ('algorithms','schemas') for r in suite.manifest[group]}
    for path in (ALGORITHM,'schemas/vnext_version_admission_v1.schema.json','schemas/vnext_phase2_entry_v2.schema.json',
                 'schemas/vnext_system_entry_request_v1.schema.json'):
        require(path in entries and sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes())==entries[path]['sha256'],
                'version entry contract absent or changed',path)


def prefix_at(proof, reference):
    from whetstone.vnext_verified_history import _snapshot, _ReplayAdmission, VerifiedHistoryView
    from types import SimpleNamespace
    proof.values(reference)
    ordinal=next(i for i,p in enumerate(proof.pointers) if _snapshot(p)==reference)
    result=copy(proof);result.pointers=proof.pointers[:ordinal+1];result.latest=deepcopy(reference)
    paths={_snapshot(p)['path'] for p in result.pointers}
    result.bases={k:v for k,v in proof.bases.items() if k in paths}
    result.admission=_ReplayAdmission(result)
    limit=result.pointers[-1]['source_candidate_creation_ordinal'] or 0
    if limit:
        result.router=result.transactions(limit)
        events=result.router.registry().inspect().events
    else:
        result.router=SimpleNamespace(registry=lambda:SimpleNamespace(schemas=proof.reader.suite.registry))
        events=()
    result.view=VerifiedHistoryView(tuple(result.pointers),tuple(events),())
    return result


def binding_at(proof):
    from whetstone.vnext_verified_phase2_binding import REQUEST_PATH, REQUEST_SCHEMA
    from whetstone.vnext_verified_phase2_round import _HistoricalAdvice
    raw=proof.store.read(REQUEST_PATH)
    request=proof.reader.json(dict(path=REQUEST_PATH,hash=sha256_bytes(raw)),REQUEST_SCHEMA)
    prefix=prefix_at(proof,request['current_verified_pointer'])
    owner=_HistoricalAdvice(proof.owner.run)
    # Call the unchanged binding implementation on its original prerequisite base.
    from whetstone.vnext_verified_phase2_entry import _Entry
    binding=_Entry._original_committed_binding(owner,prefix)
    return prefix,owner,binding


def inputs(proof):
    pins(proof.reader.suite)
    require(proof.seed_values['job']['assembler_version']==ASSEMBLER,'entry requires versioned assembler')
    prefix,owner,binding=binding_at(proof)
    closeout=owner.evaluate(prefix)
    rows=closeout.evidence['review_receipts']
    require(bool(rows),'entry version requires real Phase 1 review evidence')
    last=rows[-1]
    receipt=decode_json(prefix.reader.raw(last['receipt']))
    feedback=prefix.reader.json(receipt['feedback'],'reviewer_feedback')
    require(feedback['round_number']==last['round_number'],'entry review locator differs')
    values=prefix.values(prefix.latest)
    context={}
    for row in values['authority']['bindings']:
        if row['role']=='normative_authority':
            context[row['binding_id']]=prefix.reader.raw(dict(path=row['path'],hash=row['content_hash']))
    # Preserve real feedback as provenance only; it supplies no editing findings.
    values.update(feedback=feedback,feedback_ref=receipt['feedback'],advice=None,context=context,
        constraints=dict(allowed_operation_types=[],max_operations=0,max_changed_sections=0,
                         max_changed_normative_units=0,required_context_binding_ids=[]),
        system_entry=dict(request=binding.request,request_ref=binding.request_ref,
                          configuration=binding.configuration,closeout=closeout.evidence,
                          review_receipt=last['receipt']))
    return values,prefix,owner,binding


def preflight(arguments):
    from whetstone.vnext_unit_preflight import UnitProposalPreflight, input_projection
    from whetstone.vnext_identity import transaction_id
    from whetstone.vnext_inventory import seed_inventory, validate_seed_inventory
    from whetstone.vnext_discovery import discovery_rules
    from whetstone.vnext_assertions import validate_assertion_program
    from whetstone.vnext_unit_lineage import validate_inventory_facts
    from whetstone.vnext_validation import validate_plan
    pins(arguments['suite'])
    job=arguments['job'];entry=arguments['system_entry'];request=entry['request']
    require(job['assembler_version']==ASSEMBLER and job['editing_mode']=='verified_promotion', 'invalid system entry mode/assembler')
    require(request['job_id']==job['job_id'] and request['current_verified_pointer']==arguments['base_pointer_ref']
            and request['current_verified_draft']['hash']==sha256_bytes(arguments['base'])
            and entry['closeout']['accepted'] and not entry['closeout']['unclean_profiles']
            and not entry['closeout'].get('focused_profile'), 'invalid system entry prerequisites')
    require(entry['request_ref']['hash']==sha256_bytes(canonical_json_bytes(request)), 'entry request hash differs')
    rules=discovery_rules(arguments['invariants'])
    inventory=deepcopy(arguments.get('base_inventory'))
    if inventory is None:
        require(arguments['base']==arguments['seed'] and arguments['base_map']==arguments['seed_map'], 'entry lacks committed inventory')
        inventory=seed_inventory(arguments['base'],arguments['base_map'],job,rules=rules)
        validate_seed_inventory(inventory,arguments['base'],arguments['base_map'],job,rules=rules)
    validate_inventory_facts(inventory,arguments['base'],arguments['base_map'],rules=rules)
    validate_assertion_program(arguments['invariants'],arguments['seed'],arguments['seed_map'])
    context=plan_context(phase='phase_2',transition='phase2_entry',source=entry['request_ref'],base_pointer=arguments['base_pointer_ref'])
    plan=dict(schema_version='mutation-plan-v4',job_id=job['job_id'],transaction_id='',
        base_draft_hash=sha256_bytes(arguments['base']),authority_map_hash=job['authority_map_hash'],
        scope_contract_hash=job['scope_contract_hash'],protected_invariants_hash=job['protected_invariants_hash'],
        finding_dispositions=[],allowed_section_ids=[],allowed_operation_types=[],max_operations=0,
        max_changed_sections=0,max_changed_normative_units=0,authorized_deletion_unit_ids=[],
        required_context_binding_ids=sorted(arguments['context']),slices=[],
        base_inventory_hash=sha256_bytes(canonical_json_bytes(inventory)),
        base_section_identity_map_hash=sha256_bytes(canonical_json_bytes(arguments['base_map'])),system_metadata=context)
    plan['transaction_id']=transaction_id(plan,{})
    VNextSchemaRegistry().validate(plan,'mutation_plan_v4')
    validate_plan(plan,job,arguments['authority'],arguments['base_map'],[])
    digest=sha256_bytes(canonical_json_bytes(input_projection({k:v for k,v in arguments.items() if k!='suite'})))
    # This is stored system context, never an Editor prompt or invocation.
    prompt=canonical_json_bytes(dict(kind='system_phase2_entry',mutation_plan=plan,entry=entry)).decode()
    return UnitProposalPreflight(digest,plan,inventory,rules,(),[],{},[],prompt)


class SystemJournal:
    def __init__(self,store,load_inputs):
        from whetstone.vnext_identity import proposal_id
        from whetstone.vnext_proposals import PreparedProposal
        self.store,self.load_inputs=store,load_inputs
        self.arguments=load_inputs(store.read);self.preflight=preflight(self.arguments)
        plan=self.preflight.plan
        self.request_id=content_identifier('req','whetstone-system-entry-request-v1',[plan['job_id'],plan['transaction_id']])
        self.directory='rounds/system_requests/'+self.request_id
        self.schemas=VNextSchemaRegistry()
        packet=dict(schema_version='patch-set-v2',job_id=plan['job_id'],transaction_id=plan['transaction_id'],proposal_id=None,
            base_draft_hash=plan['base_draft_hash'],mutation_plan_hash=sha256_bytes(canonical_json_bytes(plan)),
            editor=self.arguments['review']['editor'],operations=[],declined_findings=[],
            editor_claims=dict(addressed_finding_ids=[],normative_change_summary='System-only metadata; no Editor invocation.'))
        packet['proposal_id']=proposal_id(packet);self.schemas.validate(packet,'patch_set_v2')
        self.proposal=PreparedProposal(packet,{})
        self.header=dict(schema_version='vnext-system-entry-request-v1',request_id=self.request_id,
                         entry_request=self.arguments['system_entry']['request_ref'],input_hash=self.preflight.input_hash,
                         mutation_plan_hash=packet['mutation_plan_hash'],base_pointer=self.arguments['base_pointer_ref'])
        self.schemas.validate(self.header,'vnext_system_entry_request_v1')

    def recheck(self):
        require(preflight(self.load_inputs(self.store.read))==self.preflight,'system entry inputs changed')

    def inspect(self):
        from whetstone.vnext_proposal_requests import _Journal
        receipt=_Journal.receipt(self,self.proposal)
        for name,value in (('request.json',self.header),('mutation_plan.json',self.preflight.plan),
                           ('base_inventory.json',self.preflight.inventory),
                           ('proposal_result.json',receipt),
                           ('proposals/'+self.proposal.patch['proposal_id']+'/proposed_patch.json',self.proposal.patch)):
            require(self.store.read(self.directory+'/'+name)==canonical_json_bytes(value),'system entry source changed',name)
        self.recheck()
        return self.header,[],self.proposal,receipt

    def synchronize(self,token,header,outcomes):
        require(header==self.header and not outcomes,'system entry cannot claim client attempts')
        self.recheck()
        for name,value in (('request.json',self.header),('mutation_plan.json',self.preflight.plan),
                           ('base_inventory.json',self.preflight.inventory)):
            self.publish(token,name,value)

    def publish(self,token,name,value): return self.store.publish(token,self.directory+'/'+name,value)

    def finish(self,token,proposal):
        from whetstone.vnext_proposal_requests import _Journal
        require(proposal==self.proposal,'system proposal changed')
        return _Journal.finish(self,token,proposal)

    def receipt(self,proposal):
        from whetstone.vnext_proposal_requests import _Journal
        return _Journal.receipt(self,proposal)


def selected_inputs(router,read,number,transaction):
    try:raw=read(ADMISSION)
    except FileNotFoundError:return None
    record=decode_json(raw)
    if record.get('transaction_id')!=transaction:return None
    values,_,_,_=inputs(router.original.proof)
    expected=admission_record(values)
    require(record==expected and raw==canonical_json_bytes(expected) and number==record['round_number'],
            'system entry admission differs from original prerequisites')
    return values


def admission_record(values):
    plan=preflight(values).plan
    record=dict(schema_version='vnext-version-admission-v1',job_id=plan['job_id'],transaction_id=plan['transaction_id'],
        round_number=values['feedback']['round_number'],entry_request=values['system_entry']['request_ref'],
        base_pointer=values['base_pointer_ref'],mutation_plan_hash=sha256_bytes(canonical_json_bytes(plan)))
    VNextSchemaRegistry().validate(record,'vnext_version_admission_v1')
    return record


def prepare(run, *, created_at):
    from whetstone.vnext_verified_phase2_entry import _Entry
    from whetstone.vnext_proposal_handoff import register_completed_proposal_request
    from whetstone.vnext_version_operations import project
    owner=_Entry(run)
    def perform(store,proof):
        values,prefix,historical,binding=inputs(proof)
        require(proof.latest==prefix.latest,'entry version already has a promoted successor')
        projected,_=project(values['base'],values['base'],phase='phase_2',transition='phase2_entry')
        require(projected!=values['base'],'entry needs no version candidate')
        record=admission_record(values)
        # Only this transaction may follow the original complete prerequisite
        # registry. Recovery of its visible registration cannot require that
        # same candidate to have been promoted already.
        prior=len(prefix.view.creations)
        require(all(c['transaction_id']==record['transaction_id'] for c in proof.view.creations[prior:]),
                'unrelated candidate blocks system entry')
        # Live admission still requires the original current Phase 1 state.
        require(owner._status(prefix,owner.evaluate(prefix)).state_current,
                'entry version requires current Phase 1 state')
        owner._synchronize_entry_sources(store,prefix,binding)
        def load(read):
            proof.guard(read);run._guard(read)
            return inputs(proof)[0]
        journal=SystemJournal(store,load)
        journal.synchronize(store._token,journal.header,[])
        journal.finish(store._token,journal.proposal)
        journal.recheck()
        store.publish(store._token,ADMISSION,record)
        class Loader:
            def __call__(self,read,number):
                require(number==record['round_number'],'wrong entry storage locator')
                return load(read)
            def for_proposal(self,read,number,identifier):
                if identifier==journal.proposal.patch['proposal_id']:return self(read,number)
                return proof.router.load_inputs.for_proposal(read,number,identifier)
            def request_journal(self,storage,number,identifier):
                if identifier is None or identifier==journal.proposal.patch['proposal_id']:return SystemJournal(storage,load)
                return proof.router.load_inputs.request_journal(proof.store,number,identifier)
        return register_completed_proposal_request(store,round_number=record['round_number'],load_inputs=Loader(),
                                                   validate_authority=lambda read:load(read),created_at=created_at)
    return owner._execute(perform)


def entry_view(owner,proof,binding):
    from whetstone.vnext_verified_phase2_entry import ENTRY_PATH, STATE_FIELD, Phase2EntryState
    from whetstone.vnext_verified_materialization import STATE_PATH
    from whetstone.vnext_verified_phase2_binding import _ref
    from whetstone.vnext_version_operations import project
    pins(proof.reader.suite)
    raw=proof.reader.raw(binding.request['current_verified_draft'])
    projected,version=project(raw,raw,phase='phase_2',transition='phase2_entry')
    changed=projected!=raw
    pointer=proof.pointers[-1]
    entry=dict(schema_version='vnext-phase2-entry-v1',phase='phase_2',job_id=binding.request['job_id'],
        entry_request=deepcopy(binding.request_ref),configuration=deepcopy(binding.configuration_ref),
        current_verified_pointer=deepcopy(proof.latest),
        current_verified_draft=dict(path=pointer['verified_draft_path'],hash=pointer['verified_draft_hash']),
        current_verified_map=dict(path=pointer['verified_section_identity_map_path'],hash=pointer['verified_section_identity_map_hash']),
        phase1_closeout=deepcopy(binding.request['phase1_closeout']),
        version=dict(before=version['before'],after=version['after'],changed=changed))
    if changed:
        values,_,_,_=inputs(proof);record=admission_record(values)
        require(owner.store.read(ADMISSION)==canonical_json_bytes(record),'entry lacks its system admission')
        require(pointer['previous_verified_pointer_path']==binding.request['current_verified_pointer']['path']
                and pointer['previous_verified_pointer_hash']==binding.request['current_verified_pointer']['hash']
                and pointer['source_transaction_id']==record['transaction_id']
                and pointer['verified_draft_hash']==sha256_bytes(projected),
                'Phase 2 entry requires its verified system version promotion')
        entry.update(schema_version='vnext-phase2-entry-v2',version_admission=_ref(ADMISSION,record))
    else:
        require(proof.latest==binding.request['current_verified_pointer'],'unchanged entry base advanced')
    schema=entry['schema_version'].replace('-','_')
    proof.reader.suite.registry.validate(entry,schema)
    reference=_ref(ENTRY_PATH,entry)
    existing=owner._optional(ENTRY_PATH)
    require(existing is None or existing==canonical_json_bytes(entry),'Phase 2 entry differs from version evidence')
    state=decode_json(owner.store.read(STATE_PATH))
    require(isinstance(state,dict),'entry state must be an object')
    require(existing is not None or STATE_FIELD not in state,'entry state references missing commit')
    current=existing is not None and state.get(STATE_FIELD)==reference
    pending=(() if existing else (ENTRY_PATH,))+(() if current else (STATE_PATH,))
    proof.guard(owner.store.read);owner.run._guard(owner.store.read)
    return Phase2EntryState('entered' if current else 'entry_state_recovery_required' if existing else 'entry_required',
                            entry,reference,existing is not None,current,pending)


def validate_pending_transition(proof):
    """Account for the single metadata successor before any Phase 2 review."""
    if proof.seed_values['job']['assembler_version']!=ASSEMBLER:return False
    try:raw=proof.store.read(ADMISSION)
    except FileNotFoundError:return False
    values,prefix,owner,binding=inputs(proof)
    require(raw==canonical_json_bytes(admission_record(values)),'entry admission changed')
    if proof.latest!=prefix.latest:entry_view(owner,proof,binding)
    from whetstone.vnext_verified_review import _sequence
    _sequence(prefix)
    return True
