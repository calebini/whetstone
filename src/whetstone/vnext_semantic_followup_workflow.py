"""Normal semantic workflow views over explicitly committed follow-ups."""
from copy import deepcopy

from whetstone.vnext_contracts import canonical_json_bytes,confined_file,CONTRACT_ROOT,require,sha256_bytes
from whetstone.vnext_proposal_run import ProposalRun
from whetstone.vnext_proposal_status import inspect_proposal_run
from whetstone.vnext_semantic_followup_admission import SemanticFollowupAdmission,admit_semantic_followup,_input_path,_selection_path
from whetstone.vnext_semantic_workflow import SemanticProposalRun,_WorkflowDecisions


ALGORITHM='algorithms/vnext_semantic_followup_workflow_v1.md'


class _CommandView:
    def __init__(self,run,number,reference,*,writable=False):
        self.run=run;self.number=number;self.reference=deepcopy(reference)
        self.writable=writable
        self.admission=SemanticFollowupAdmission(run.store,original=run.original,selected_ref=reference)
        self.load_inputs=self.admission.load_inputs

    def __getattr__(self,name):return getattr(self.run,name)

    def validate_authority(self,read):
        self.run.validate_authority(read)
        require(self.run.committed_selection(read,self.number)==self.reference,
                'active follow-up selection changed before command work')
        if self.writable and self.reference is not None:
            self.admission.validate_selected(read)

    def decision_journal(self,registry):return _WorkflowDecisions(registry,admission=self)
    def status(self,*,round_number):
        require(round_number==self.number,'command view belongs to another Reviewer round')
        return inspect_proposal_run(self,round_number=round_number)
    def candidate_status(self,round_number,journal,creation):
        return SemanticProposalRun.candidate_status(self,round_number,journal,creation)
    def admit_round(self,record):return ProposalRun.admit_round(self,record)
    def run_round(self,**options):
        view=self if self.writable else _CommandView(self.run,self.number,self.reference,writable=True)
        return ProposalRun.run_round(view,**options)
    def semantic_status(self,*,round_number):
        from whetstone.vnext_semantic_run import inspect_semantic_round
        return inspect_semantic_round(self,round_number=round_number)
    def verify_round(self,**options):
        from whetstone.vnext_semantic_run import run_semantic_round
        view=self if self.writable else _CommandView(self.run,self.number,self.reference,writable=True)
        return run_semantic_round(view,**options)


class _WorkflowInputs:
    def __init__(self,run):self.run=run
    def __call__(self,read,number):return self.run.command_view(number).load_inputs(read,number)
    def for_proposal(self,read,number,identifier):
        return self.run.router.load_inputs.for_proposal(read,number,identifier)


class SemanticFollowupRun(SemanticProposalRun):
    def __init__(self,store,*,suite_path):
        super().__init__(store,suite_path=suite_path)
        self.original=SemanticProposalRun(store,suite_path=suite_path)
        self.router=SemanticFollowupAdmission(store,original=self.original)
        reader,_=self._base(store.read)
        algorithms={row['path']:row for row in reader.suite.manifest['algorithms']}
        require(ALGORITHM in algorithms,'follow-up workflow algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT,ALGORITHM).read_bytes())==algorithms[ALGORITHM]['sha256'],
                'installed follow-up workflow differs from pinned suite')
        self._command_views={}
        self.load_inputs=_WorkflowInputs(self)

    def committed_selection(self,read,number):
        require(type(number) is int and number>0,'invalid follow-up workflow round')
        registered=self.router.registry().inspect()
        events=[event for event in registered.events if event['round_number']==number]
        if not events:return None
        latest=events[-1]
        path=_selection_path(latest)
        try:read(path)
        except FileNotFoundError:selection=None
        else:selection=self.router._json(read,path,'vnext_semantic_followup_selection_v1')
        if selection is not None:
            reference=selection['transaction_input']
            record=self.router._json(read,reference['path'],'vnext_semantic_followup_input_v1',reference['hash'])
            require(record['source_creation']=={'path':f"rounds/candidate_index/creation-{latest['candidate_creation_ordinal']}.json",
                    'hash':sha256_bytes(canonical_json_bytes(latest))},'active selection belongs to another source candidate')
        else:
            from whetstone.vnext_unit_preflight import prepare_unit_preflight
            original=prepare_unit_preflight(**self.original.load_inputs(read,number))
            if latest['transaction_id']==original.plan['transaction_id']:return None
            path=_input_path(number,latest['transaction_id'])
            record=self.router._json(read,path,'vnext_semantic_followup_input_v1')
            reference={'path':path,'hash':sha256_bytes(canonical_json_bytes(record))}
        selected=SemanticFollowupAdmission(self.store,original=self.original,selected_ref=reference)
        selected.selected_record(read)
        selected.load_inputs(read,number)
        return deepcopy(reference)

    def command_view(self,number):
        if number not in self._command_views:
            self._command_views[number]=_CommandView(self,number,self.committed_selection(self.store.read,number))
        return self._command_views[number]

    def status(self,*,round_number):return self.command_view(round_number).status(round_number=round_number)
    def run_round(self,*,round_number,**options):
        return self.command_view(round_number).run_round(round_number=round_number,**options)
    def semantic_status(self,*,round_number):
        return self.command_view(round_number).semantic_status(round_number=round_number)
    def verify_round(self,*,round_number,**options):
        return self.command_view(round_number).verify_round(round_number=round_number,**options)

    def admit_followup(self,*,candidate_id,answer_reference):
        reference=admit_semantic_followup(self.store,original=self.original,candidate_id=candidate_id,
                                          answer_reference=answer_reference)
        record=self.router._json(self.store.read,reference['path'],'vnext_semantic_followup_input_v1',reference['hash'])
        self._command_views.pop(record['round_number'],None)
        return reference
