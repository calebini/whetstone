"""Fenced explicit repair admission and bounded historical reconstruction."""
from copy import copy, deepcopy

from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_phase2_repair import pins, prepare, SCHEMA, REQUEST_SCHEMA
from whetstone.vnext_semantic_followup_admission import _input_path, _selection_path, _ref
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_verified_phase2_sequence import _Continuation, _Evidence, sequence
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal


def source(router, event):
    """The source creation precedes every repair consumer; no future authority."""
    historical = type(router)(router.store, original=router.original,
                             history_limit=event['candidate_creation_ordinal'])
    registry=historical.registry()
    require(registry.inspect().latest==event,'repair source is not the registered history prefix')
    journal = VerifiedSemanticDecisionJournal(registry, admission=historical)
    state,completed = journal._state_with_request(event)
    view=state[0]
    require(not view.prepared and view.decision is not None and view.decision['decision_final'],
            'repair source decision requires recovery or verification')
    require(completed is not None,'repair requires a committed semantic result')
    request,_,_,result=completed
    decision_ref = dict(path=view.pointer['current_decision_path'], hash=view.pointer['current_decision_hash'])
    return dict(context=request.context.packet, decision=view.decision, decision_ref=decision_ref,
                semantic=result.verification)


def derive(router, read, record):
    reader, _ = router._base(read); pins(reader.suite)
    values = router.original.load_inputs(read, record['round_number'])
    require(record['job_id'] == values['job']['job_id'] and record['base_pointer'] == values['base_pointer_ref'],
            'repair admission has stale job or base bindings')
    event = router._source(read, record)
    evidence = source(router, event)
    require(record['source_context_hash'] == sha256_bytes(canonical_json_bytes(evidence['context']))
            and record['source_verification'] == evidence['decision_ref'], 'repair source evidence changed')
    evidence['request'] = record['request']
    arguments = dict(values, phase2_repair=canonical_json_bytes(evidence))
    preflight = prepare_unit_preflight(**arguments)
    require(preflight.plan['transaction_id'] == record['transaction_id']
            and sha256_bytes(canonical_json_bytes(preflight.plan)) == record['mutation_plan_hash'],
            'repair plan does not reproduce from exact sources')
    return arguments, preflight, event


class Phase2Repair(_Continuation):
    def __init__(self, run):
        tracked=copy(run);tracked.store=_Evidence(run.store)
        super().__init__(tracked)

    def _proof(self, read):
        proof = super()._proof(self.store.read); pins(proof.reader.suite); return proof

    def _context(self, proof, candidate_id):
        state = sequence(proof)
        require(state['gate'] == 'correction_required', 'Phase 2 repair is blocked by the current sequence gate')
        frame = state['frames'][-1]
        require(proof.view.creations and proof.view.creations[-1]['candidate_id'] == candidate_id,
                'repair requires the latest candidate')
        event = proof.view.creations[-1]
        require(event['round_number'] == frame['owner'].number
                and frame['bound'].request['base_pointer'] == proof.latest, 'repair source review is stale')
        evidence = source(proof.router,event)
        decision=evidence['decision']
        require(decision['candidate_disposition']=='CANDIDATE_REJECTED' and decision['semantic_result']=='reject'
                and not decision['outstanding_decision_ids'], 'repair requires semantic rejection without an outstanding choice')
        return frame,event,evidence

    def context(self, *, candidate_id):
        proof = self._proof(self.store.read); work = self._observe(proof)
        if work.outcome != 'work_available': return work
        frame,event,evidence = self._context(proof,candidate_id)
        selected=None
        marker=self._optional(_selection_path(event))
        if marker is not None:
            choice=proof.reader.json(dict(path=_selection_path(event),hash=sha256_bytes(marker)),
                                     'vnext_semantic_followup_selection_v1')
            selected=choice['transaction_input']
            router=type(proof.router)(proof.store,original=proof.admission,selected_ref=selected)
            record=router.selected_record(self.store.read)
            require(record['source_creation']==evidence['context']['creation_ref'], 'repair selection belongs to another source')
            router._transaction(self.store.read,record['round_number'],record['transaction_id'])
        result = dict(job_id=event['job_id'],round_number=event['round_number'],base_pointer=deepcopy(proof.latest),
            source_creation=evidence['context']['creation_ref'],source_verification=evidence['decision_ref'],
            operations=evidence['context']['editor_proposal']['patch']['operations'],
            findings=evidence['semantic']['finding_results'],limits={k:evidence['context']['mutation_plan'][k]
                for k in ('max_operations','max_changed_sections','max_changed_normative_units')},
            selected_transaction=selected,gate='repair_selected' if selected else 'explicit_repair_admission_required',
            phase_complete=False,resume_permitted=False)
        proof.guard(self.store.read); self.store.check(self.store.reads)
        return result

    def admit(self, packet, *, dry_run=False):
        frozen=deepcopy(packet)
        require(type(dry_run) is bool,'repair dry_run must be an explicit boolean')
        def operation(store,proof):
            proof.reader.suite.registry.validate(frozen,REQUEST_SCHEMA)
            event=proof.reader.json(frozen['source_creation'],'candidate_creation_event_v1')
            frame,event,evidence=self._context(proof,event['candidate_id'])
            evidence['request']=frozen
            values=proof.admission.load_inputs(self.store.read,event['round_number'])
            preflight=prepare(values,canonical_json_bytes(evidence))
            record=dict(schema_version='vnext-phase2-repair-input-v1',job_id=event['job_id'],round_number=event['round_number'],
                transaction_id=preflight.plan['transaction_id'],base_pointer=deepcopy(proof.latest),
                source_creation=evidence['context']['creation_ref'],source_verification=evidence['decision_ref'],
                source_context_hash=sha256_bytes(canonical_json_bytes(evidence['context'])),request=frozen,
                mutation_plan_hash=sha256_bytes(canonical_json_bytes(preflight.plan)))
            proof.reader.suite.registry.validate(record,SCHEMA)
            ref=_ref(_input_path(event['round_number'],record['transaction_id']),record)
            marker=dict(schema_version='vnext-semantic-followup-selection-v1',job_id=event['job_id'],
                        candidate_id=event['candidate_id'],transaction_input=ref)
            old=self._optional(_selection_path(event))
            require(old is None or old==canonical_json_bytes(marker),'source already selected a different child')
            require(not any(c['transaction_id']==record['transaction_id'] for c in proof.view.creations),
                    'repair transaction identity is already registered')
            result=dict(reference=ref,record=record,plan=preflight.plan)
            if dry_run:return result
            snapshot={p:r for p,r in self.store.reads.items() if p not in {ref['path'],_selection_path(event)}}
            self.store.synchronize(store._token,snapshot,self.run._record['descriptor']['path'])
            require(derive(proof.router,self.store.read,record)[1].plan==preflight.plan,'repair sources changed at barrier')
            self.store.check(snapshot)
            store.publish(store._token,ref['path'],record)
            store.publish(store._token,_selection_path(event),marker)
            proof.router._transaction(self.store.read,event['round_number'],record['transaction_id'])
            self.store.check(snapshot);store.read_descriptor()
            return result
        if not dry_run:return self._execute(operation)
        proof=self._proof(self.store.read);work=self._observe(proof)
        if work.outcome!='work_available':return work
        return operation(None,proof)
