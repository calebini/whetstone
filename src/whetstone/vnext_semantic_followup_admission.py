"""Immutable same-round follow-up admission and acyclic source replay.

The outer reader validates current authority and the full registry. Ancestor
proofs use strictly bounded read-only history; they cannot write or allocate.
"""
from copy import deepcopy
from dataclasses import replace
import re

from whetstone.vnext_contracts import CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_identity import creation_id, proposal_id
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests, register_completed_proposal_request
from whetstone.vnext_proposal_requests import finish_proposal_request,inspect_proposal_request,run_proposal_request
from whetstone.vnext_semantic_answers import SemanticAnswerSource
from whetstone.vnext_semantic_followup_preflight import read_followup_evidence, validate_followup_contracts
from whetstone.vnext_unit_preflight import prepare_unit_preflight


ALGORITHM='algorithms/vnext_semantic_followup_admission_v1.md'
SCHEMAS=frozenset({'vnext_semantic_followup_input_v1','vnext_semantic_followup_selection_v1'})


def _ref(path,value):return {'path':path,'hash':sha256_bytes(canonical_json_bytes(value))}


def _input_path(number,transaction):
    require(type(number) is int and number>0 and isinstance(transaction,str)
            and re.fullmatch(r'txn_[0-9a-f]{64}',transaction),'invalid follow-up transaction selector')
    return f'rounds/round-{number}/transactions/{transaction}/admission.json'


def _selection_path(creation):return creation['candidate_path'].rsplit('/',1)[0]+'/followup_transaction.json'


class _ReadOnlyStore:
    def __init__(self,store):self._source=store
    def read(self,path):return self._source.read(path)
    def read_descriptor(self):return self._source.read_descriptor()
    def list_directory(self,path):return self._source.list_directory(path)
    def locked(self,*args,**kwargs):raise ValueError('historical source evidence is read-only')
    def publish(self,*args,**kwargs):raise ValueError('historical source evidence is read-only')
    def replace_pointer(self,*args,**kwargs):raise ValueError('historical source evidence is read-only')


class _Inputs:
    def __init__(self,owner,history_limit=None):self.owner=owner;self.history_limit=history_limit
    def __call__(self,read,number):
        if self.owner.selected_ref is None:return self.owner.original.load_inputs(read,number)
        record=self.owner.selected_record(read)
        require(record['round_number']==number,'selected follow-up belongs to another Reviewer round')
        return self.owner._transaction(read,number,record['transaction_id'])
    def for_proposal(self,read,number,identifier):
        require(isinstance(identifier,str) and re.fullmatch(r'pro_[0-9a-f]{64}',identifier),'invalid historical proposal selector')
        packet=self.owner._json(read,f'rounds/round-{number}/proposals/{identifier}/proposed_patch.json','patch_set_v2')
        require(packet['proposal_id']==identifier and proposal_id(packet)==identifier,'historical proposal identity changed')
        return self.owner._transaction(read,number,packet['transaction_id'])


class SemanticFollowupAdmission:
    def __init__(self,store,*,original,selected_ref=None,history_limit=None):
        self.store=store;self.original=original;self.selected_ref=deepcopy(selected_ref)
        require(selected_ref is None or isinstance(selected_ref,dict) and set(selected_ref)=={'path','hash'}
                and isinstance(selected_ref['path'],str) and isinstance(selected_ref['hash'],str),
                'follow-up selection requires an exact admission reference')
        require(history_limit is None or type(history_limit) is int and history_limit>0,'invalid historical source boundary')
        self.load_inputs=_Inputs(self,history_limit)
        self._base(store.read)

    def _base(self,read):
        reader,values=self.original._base(read);validate_followup_contracts(reader.suite)
        entries={e['path']:e for family in ('algorithms','schemas') for e in reader.suite.manifest[family]}
        paths={ALGORITHM}|{'schemas/'+name+'.schema.json' for name in SCHEMAS}
        require(paths<=entries.keys(),'follow-up admission contracts are outside supported suite')
        for path in paths:
            require(sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes())==entries[path]['sha256'],
                    'installed follow-up admission contract differs from pinned suite',path)
        return reader,values

    def validate_authority(self,read):self._base(read)

    def _json(self,read,path,schema,digest=None):
        raw=read(path);value=decode_json(raw)
        require(raw==canonical_json_bytes(value),'noncanonical follow-up artifact',path)
        require(digest is None or sha256_bytes(raw)==digest,'follow-up source hash changed',path)
        # Entry points and transaction reconstruction validate the full suite
        # and current base. As in the other journals, an individual metadata
        # decode checks its own closed schema without re-running that entire
        # authority graph for every field reference.
        VNextSchemaRegistry().validate(value,schema)
        return value

    def selected_record(self,read):
        require(self.selected_ref is not None,'follow-up work requires an explicit admitted transaction')
        record=self._json(read,self.selected_ref['path'],'vnext_semantic_followup_input_v1',self.selected_ref['hash'])
        require(self.selected_ref==_ref(_input_path(record['round_number'],record['transaction_id']),record),
                'follow-up selection is outside its canonical transaction path')
        return record

    def registry(self):
        return registry_for_proposal_requests(self.store,load_inputs=self.load_inputs,validate_authority=self.validate_authority)

    def _source(self,read,record):
        event=self._json(read,record['source_creation']['path'],'candidate_creation_event_v1',record['source_creation']['hash'])
        require(event['creation_event_id']==creation_id(event)
                and record['source_creation']['path']==f"rounds/candidate_index/creation-{event['candidate_creation_ordinal']}.json"
                and event['job_id']==record['job_id'] and event['round_number']==record['round_number'],
                'follow-up source creation identity changed')
        limit=self.load_inputs.history_limit
        require(limit is None or event['candidate_creation_ordinal']<limit,'follow-up source must precede its historical consumer')
        return event

    def _derive(self,read,record):
        self._base(read)
        event=self._source(read,record)
        values=self._original_inputs(read,record,event)
        require(record['job_id']==values['job']['job_id'] and record['base_pointer']==values['base_pointer_ref'],
                'follow-up admission has stale job or base bindings')
        historical=type(self)(_ReadOnlyStore(self.store),original=self.original,
                                             history_limit=event['candidate_creation_ordinal'])
        evidence=self._read_evidence(historical, event['candidate_id'], record['answer_receipt'])
        arguments={**values,'semantic_followup':evidence}
        preflight=prepare_unit_preflight(**arguments)
        require(preflight.plan['transaction_id']==record['transaction_id']
                and preflight.plan['semantic_origin']['source_verification']==record['source_verification']
                and preflight.plan['semantic_origin']['editing_plan_hash']==record['editing_plan_hash']
                and sha256_bytes(canonical_json_bytes(preflight.plan))==record['mutation_plan_hash'],
                'follow-up transaction does not reproduce from its exact sources')
        return arguments,preflight,event

    def _original_inputs(self,read,record,event):
        return self.original.load_inputs(read,record['round_number'])

    def _read_evidence(self, historical, candidate_id, reference):
        return read_followup_evidence(historical.store, admission=historical,
                                      candidate_id=candidate_id, reference=reference)

    def _transaction(self,read,number,transaction):
        baseline=self.original.load_inputs(read,number)
        if prepare_unit_preflight(**baseline).plan['transaction_id']==transaction:return baseline
        path=_input_path(number,transaction)
        record=self._json(read,path,'vnext_semantic_followup_input_v1')
        require(record['round_number']==number and record['transaction_id']==transaction,'follow-up input selector changed')
        event=self._source(read,record)
        selection=self._json(read,_selection_path(event),'vnext_semantic_followup_selection_v1')
        expected={'schema_version':'vnext-semantic-followup-selection-v1','job_id':record['job_id'],
                  'candidate_id':event['candidate_id'],'transaction_input':_ref(path,record)}
        require(selection==expected,'follow-up input lacks its exact committed selection')
        return self._derive(read,record)[0]

    def validate_selected(self,read):
        require(self.load_inputs.history_limit is None,'historical source evidence cannot enable work')
        require(self.selected_ref is not None,'follow-up work requires an explicit admitted transaction')
        record=self.selected_record(read)
        self._transaction(read,record['round_number'],record['transaction_id'])
        source=self._source(read,record)
        registered=self.registry().inspect()
        latest=registered.latest
        require(latest is not None and (latest==source or latest['transaction_id']==record['transaction_id']),
                'selected follow-up is superseded by another candidate')
        require(len(registered.orphans)<=1,'follow-up cannot choose among registration orphans')
        if registered.orphans:
            pending=self._json(read,registered.orphans[0]+'/registration_preparation.json','candidate_registration_preparation_v1')['creation_event']
            require(pending['transaction_id']==record['transaction_id'] and pending['round_number']==record['round_number'],
                    'follow-up cannot recover another transaction orphan')

    def request(self,*,client,continuation=False):
        require(self.selected_ref is not None,'follow-up work requires an explicit admitted transaction')
        require(type(continuation) is bool,'follow-up continuation must be an explicit boolean')
        record=self.selected_record(self.store.read)
        load=lambda read:self.load_inputs(read,record['round_number'])
        status=inspect_proposal_request(self.store,load_inputs=load,validate_authority=self.validate_selected)
        if status.status in {'complete','invalid_proposal','attempts_exhausted'}:return status
        if status.status!='not_started' and not continuation:return replace(status,status='continuation_required')
        require(not continuation or status.status!='not_started','new follow-up request is not technical continuation')
        if status.status=='valid_response':
            return finish_proposal_request(self.store,load_inputs=load,
                validate_authority=self.validate_selected,continuation=continuation)
        return run_proposal_request(self.store,load_inputs=load,
                                   validate_authority=self.validate_selected,client=client,continuation=continuation)

    def register(self,*,created_at):
        require(self.selected_ref is not None,'follow-up work requires an explicit admitted transaction')
        record=self.selected_record(self.store.read)
        return register_completed_proposal_request(self.store,round_number=record['round_number'],load_inputs=self.load_inputs,
            validate_authority=self.validate_selected,created_at=created_at)

    def verify(self,*,candidate_id,client,decided_at,continuation=False):
        from whetstone.vnext_semantic_run import _SelectedAdmission
        from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
        from whetstone.vnext_semantic_requests import run_semantic_request
        self.validate_selected(self.store.read)
        record=self.selected_record(self.store.read)
        creation=self.registry().inspect().latest
        require(creation['candidate_id']==candidate_id and creation['transaction_id']==record['transaction_id'],
                'follow-up Verifier requires its exact latest registered candidate')
        selected=_SelectedAdmission(self,creation)
        registry=registry_for_proposal_requests(self.store,load_inputs=self.load_inputs,validate_authority=selected.validate_authority)
        journal=SemanticDecisionJournal(registry,admission=selected)
        initial=journal.commit(candidate_id,decided_at=decided_at)
        if initial.decision['deterministic_result']!='pass':return None,initial
        result=run_semantic_request(self.store,admission=selected,candidate_id=candidate_id,client=client,continuation=continuation)
        if result.status=='complete':journal.commit_semantic(candidate_id,decided_at=decided_at)
        return result,journal.inspect(candidate_id)


def admit_semantic_followup(store,*,original,candidate_id,answer_reference):
    """Commit one explicitly selected child transaction; never invoke clients."""
    router=SemanticFollowupAdmission(store,original=original)
    return _admit_semantic_followup(store, original=original, router=router, source_admission=router,
        source_type=SemanticAnswerSource, candidate_id=candidate_id, answer_reference=answer_reference)


def _admit_semantic_followup(store, *, original, router, source_admission, source_type, candidate_id, answer_reference):
    """Share immutable publication while admission owns mode and live selection."""
    with store.locked(router.validate_authority) as token:
        registered=router.registry().inspect()
        require(not registered.orphans,'follow-up admission requires registration recovery first')
        event=next((e for e in registered.events if e['candidate_id']==candidate_id),None)
        require(event is not None,'follow-up source is not registered')
        selection_path=_selection_path(event)
        try:store.read(selection_path)
        except FileNotFoundError:selection=None
        else:selection=router._json(store.read,selection_path,'vnext_semantic_followup_selection_v1')
        if selection is not None:
            reference=selection['transaction_input']
            record=router._json(store.read,reference['path'],'vnext_semantic_followup_input_v1',reference['hash'])
            require(record.get('answer_receipt')==answer_reference and record['source_creation']==_ref(
                f"rounds/candidate_index/creation-{event['candidate_creation_ordinal']}.json",event),
                'source candidate already selected a different follow-up')
            router._transaction(store.read,record['round_number'],record['transaction_id'])
            # The marker may be visible after its last acknowledgement was
            # lost. Re-establish the input/selection barriers before success.
            store.publish(token,reference['path'],record)
            store.publish(token,selection_path,selection)
            return deepcopy(reference)
        require(registered.latest==event,'new follow-up requires the current candidate')
        source=source_type(store,admission=source_admission,candidate_id=candidate_id,require_current=True)
        evidence=router._read_evidence(router,candidate_id,answer_reference)
        arguments=original.load_inputs(store.read,event['round_number'])
        preflight=prepare_unit_preflight(**{**arguments,'semantic_followup':evidence})
        record={'schema_version':'vnext-semantic-followup-input-v1','job_id':event['job_id'],'round_number':event['round_number'],
            'transaction_id':preflight.plan['transaction_id'],'base_pointer':arguments['base_pointer_ref'],
            'source_creation':source.context.packet['creation_ref'],'source_verification':source.decision_ref,
            'answer_receipt':deepcopy(answer_reference),'editing_plan_hash':preflight.plan['semantic_origin']['editing_plan_hash'],
            'mutation_plan_hash':sha256_bytes(canonical_json_bytes(preflight.plan))}
        router._base(store.read)[0].suite.registry.validate(record,'vnext_semantic_followup_input_v1')
        path=_input_path(event['round_number'],record['transaction_id']);reference=_ref(path,record)
        selection={'schema_version':'vnext-semantic-followup-selection-v1','job_id':event['job_id'],
                   'candidate_id':candidate_id,'transaction_input':reference}
        source.synchronize(token)
        packet=decode_json(evidence)
        store.publish(token,packet['receipt']['response']['path'],packet['response'])
        store.publish(token,packet['receipt_ref']['path'],packet['receipt'])
        router._derive(store.read,record)
        require(router.registry().inspect().latest==event,'follow-up source changed before admission')
        store.publish(token,path,record)
        store.publish(token,selection_path,selection)
        router._transaction(store.read,event['round_number'],record['transaction_id'])
        return reference
