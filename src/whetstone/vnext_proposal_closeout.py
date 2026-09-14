"""Bounded proposal-only decisions and terminal projections, without clients.

This first decision consumer records deterministic failure or semantic not-run.
It never invents semantic evidence or advances a final decision. Later semantic
continuation must qualify its append policy before adding another ordinal.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import PurePosixPath

from whetstone import vnext_identity as ids
from whetstone.vnext_candidate_registry import CandidateAssemblyFailure
from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_validation import validate_decision, validate_verification_pointer, validate_terminal


def _ref(path,packet):return {'path':path,'hash':sha256_bytes(canonical_json_bytes(packet))}


@dataclass(frozen=True)
class ProposalDecisionView:
    creation: dict
    decision: dict | None
    pointer: dict | None
    effective_event: dict
    effective_event_ref: dict
    prepared: bool


class ProposalDecisionJournal:
    MODE = 'proposal_only'

    def __init__(self,registry):
        require(registry.job['editing_mode']==self.MODE,'bounded closeout requires '+self.MODE+' mode')
        self.registry=registry;self.store=registry.store;self.schemas=registry.schemas

    def terminal(self, **options):
        return proposal_terminal_report(self.registry, decision_journal=self, **options)

    def _optional(self,path,schema):
        try:return self.registry._json(path,schema)[0]
        except FileNotFoundError:
            self.store.read_descriptor()
            return None

    def _paths(self,creation):
        directory=str(PurePosixPath(creation['candidate_path']).parent)
        return directory, directory+'/candidate_verification-attempt-1.json', directory+'/disposition_events/event-2.json', \
            directory+'/candidate_verification_pointer-attempt-1.json', directory+'/candidate_verification_current.json'

    def _decision(self,creation,report,stamp):
        failed=report['result']=='fail'
        value={'schema_version':'candidate-verification-v1',
            **{key:report[key] for key in ('job_id','transaction_id','candidate_id','base_draft_hash','candidate_hash',
                'candidate_section_identity_map_path','candidate_section_identity_map_hash','patch_set_hash')},
            'candidate_creation_ordinal':creation['candidate_creation_ordinal'],'decision_ordinal':1,
            'previous_decision_hash':None,'preservation_report_hash':sha256_bytes(canonical_json_bytes(report)),
            'semantic_verification_hash':None,'deterministic_result':report['result'],'semantic_result':'not_run',
            'outstanding_decision_ids':[],'candidate_disposition':'CANDIDATE_REJECTED' if failed else 'CANDIDATE_UNVERIFIED',
            'promotion_permitted':False,'decision_final':failed,
            'rejection_codes':sorted({f['code'] for f in report['failures']}) or ['vnext_preservation_failed'] if failed else [],
            'decided_at':stamp}
        self.schemas.validate(value,'candidate_verification_v1')
        validate_decision(value,report,None,self.registry.job)
        return value

    def _targets(self,creation,initial,decision):
        _,decision_path,event_path,_,_=self._paths(creation)
        decision_ref=_ref(decision_path,decision)
        event={'schema_version':'candidate-disposition-event-v1','event_id':'',
            'job_id':creation['job_id'],'candidate_id':creation['candidate_id'],
            'candidate_creation_ordinal':creation['candidate_creation_ordinal'],'event_ordinal':2,
            'event_kind':'verification_decision','previous_event_hash':creation['initial_disposition_event_hash'],
            'previous_disposition':initial['new_disposition'],'new_disposition':decision['candidate_disposition'],
            'source_artifact_path':decision_ref['path'],'source_artifact_hash':decision_ref['hash'],
            'recorded_at':decision['decided_at']}
        event['event_id']=ids.disposition_id(event)
        self.schemas.validate(event,'candidate_disposition_event_v1')
        event_ref=_ref(event_path,event)
        pointer={'schema_version':'candidate-verification-pointer-v1',
            **{key:decision[key] for key in ('job_id','transaction_id','candidate_id','candidate_creation_ordinal',
                'candidate_section_identity_map_path','candidate_section_identity_map_hash','candidate_disposition','decision_final')},
            'current_decision_ordinal':1,'current_decision_path':decision_path,'current_decision_hash':decision_ref['hash'],
            'current_disposition_event_path':event_path,'current_disposition_event_hash':event_ref['hash'],
            'updated_at':decision['decided_at']}
        self.schemas.validate(pointer,'candidate_verification_pointer_v1')
        validate_verification_pointer(pointer,decision,decision_ref,event,event_ref,creation)
        return event,pointer

    def _state(self,creation):
        directory,decision_path,event_path,snapshot_path,pointer_path=self._paths(creation)
        # Canonical next paths are the only recovery claimants in this release.
        allowed={PurePosixPath(p).name for p in (decision_path,snapshot_path,pointer_path)}
        for name,kind in self.registry._listing(directory):
            if name.startswith('candidate_verification'):
                require(name in allowed and kind=='file','unsupported or duplicate candidate decision claim')
        for name,kind in self.registry._listing(directory+'/disposition_events'):
            if name.startswith('.vnext-tmp-'):continue
            require(name in {'event-1.json','event-2.json'} and kind=='file','unsupported or duplicate disposition event claim')
        initial=self.registry._json(creation['initial_disposition_event_path'],'candidate_disposition_event_v1')[0]
        report=self.registry._json(directory+'/preservation_report.json','preservation_report_v2')[0]
        decision=self._optional(decision_path,'candidate_verification_v1')
        event=self._optional(event_path,'candidate_disposition_event_v1')
        snapshot=self._optional(snapshot_path,'candidate_verification_pointer_v1')
        pointer=self._optional(pointer_path,'candidate_verification_pointer_v1')
        if decision is None:
            require(event is None and snapshot is None and pointer is None,'verification targets have no decision source')
        else:
            require(decision==self._decision(creation,report,decision['decided_at']),
                    'prepared or committed decision differs from deterministic evidence')
            expected_event,expected_pointer=self._targets(creation,initial,decision)
            require(event is None or event==expected_event,'verification event conflicts with its exact decision')
            require(snapshot is None or (event is not None and snapshot==expected_pointer),
                    'verification snapshot has missing or conflicting targets')
            require(pointer is None or (snapshot is not None and pointer==expected_pointer),
                    'verification pointer has missing, stale or conflicting targets')
        effective=event if pointer is not None else initial
        effective_ref=_ref(event_path,effective) if pointer is not None else {
            'path':creation['initial_disposition_event_path'],'hash':creation['initial_disposition_event_hash']}
        view=ProposalDecisionView(deepcopy(creation),deepcopy(decision) if pointer else None,
            deepcopy(pointer),deepcopy(effective),effective_ref,decision is not None and pointer is None)
        return view,report,initial,decision

    def inspect(self,candidate_id):
        registered=self.registry.inspect()
        creation=next((e for e in registered.events if e['candidate_id']==candidate_id),None)
        require(creation is not None,'decision candidate is not registered')
        return self._state(creation)[0]

    def commit(self,candidate_id,*,decided_at):
        with self.store.locked(self.registry.validate_authority) as token:
            registered=self.registry._reconcile(token,self.registry._chain())
            creation=next((e for e in registered if e['candidate_id']==candidate_id),None)
            require(creation is not None,'decision candidate is not registered')
            view,report,initial,prepared=self._state(creation)
            decision=prepared if prepared is not None else self._decision(creation,report,decided_at)
            event,pointer=self._targets(creation,initial,decision)
            _,decision_path,event_path,snapshot_path,pointer_path=self._paths(creation)
            # Every replay repeats source barriers before acknowledging an
            # uncertain prior pointer publication. No new decision is allocated.
            self.store.publish(token,decision_path,decision)
            self.store.publish(token,event_path,event)
            self.store.publish(token,snapshot_path,pointer)
            snapshot=_ref(snapshot_path,pointer)
            expected=canonical_json_bytes(view.pointer) if view.pointer is not None else None
            def transition(old,new):
                require(old==expected and new==canonical_json_bytes(pointer),'verification pointer transition changed')
                self.registry.validate_authority(self.store.read)
                current=next((e for e in self.registry._chain() if e['candidate_id']==candidate_id),None)
                require(current==creation,'candidate registration changed during verification commit')
                checked=self._state(creation)[0]
                require(checked.pointer==view.pointer,'verification predecessor changed during commit')
            self.store.replace_pointer(token,pointer_path,expected=expected,snapshot=snapshot,validate_transition=transition)
            return self._state(creation)[0]


def proposal_terminal_report(registry,*,terminal_state=None,reason=None,next_gate=None,resume_permitted=False,
                             decision_journal=None,outstanding_decision_ids=()):
    """Derive latest from creation authority and commit-bound dispositions.

    Explicit outcomes are used for failures before a decision commit. They do
    not change disposition or excuse invalid evidence. Prepared targets are
    diagnosed through a retained verification_commit next gate.
    """
    journal=decision_journal if decision_journal is not None else ProposalDecisionJournal(registry)
    registered=registry.inspect()
    require(not registered.orphans,'unresolved candidate orphan requires registration recovery')
    views=[journal._state(e)[0] for e in registered.events]
    pointer=registry._json('rounds/current_verified.json','current_verified_pointer_v1')[0]
    require(pointer['promotion_ordinal']==0,'proposal-only terminal requires committed seed authority')
    latest=views[-1] if views else None
    fields=registry.schemas.load('terminal_report_v2')['properties']['latest_candidate']['properties']
    projection={key:None for key in fields};creation_ref=None;decision_ref=None
    if latest:
        creation=latest.creation;creation_ref=_ref(f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json",creation)
        decision_ref={'path':latest.pointer['current_decision_path'],'hash':latest.pointer['current_decision_hash']} if latest.pointer else None
        projection.update(candidate_id=creation['candidate_id'],candidate_creation_ordinal=creation['candidate_creation_ordinal'],
            candidate_creation_event_path=creation_ref['path'],candidate_creation_event_hash=creation_ref['hash'],
            path=creation['candidate_path'],hash=creation['candidate_hash'],disposition=latest.effective_event['new_disposition'],
            disposition_event_path=latest.effective_event_ref['path'],disposition_event_hash=latest.effective_event_ref['hash'],
            verification_decision_path=decision_ref['path'] if decision_ref else None,
            verification_decision_hash=decision_ref['hash'] if decision_ref else None,
            verification_decision_final=latest.decision['decision_final'] if latest.decision else None)
    if terminal_state is None:
        require(latest is not None,'empty candidate chain has no proposal endpoint')
        if latest.prepared or latest.decision is None:
            terminal_state='HALTED_ARTIFACT_INVALID';reason='vnext_verification_commit_incomplete'
            next_gate='verification_commit';resume_permitted=True
        elif latest.decision['decision_final']:
            terminal_state='HALTED_ARTIFACT_INVALID';reason='vnext_preservation_failed'
        else:
            terminal_state='TARGET_NOT_REACHED';reason='vnext_gate_unavailable'
    require(isinstance(reason,str) and bool(reason),'terminal outcome requires a reason')
    report={'schema_version':'terminal-report-v2','terminal_state':terminal_state,
        'current_verified_draft_path':pointer['verified_draft_path'],'current_verified_draft_hash':pointer['verified_draft_hash'],
        'latest_candidate':projection,'rejected_candidate_ids':[v.creation['candidate_id'] for v in views
            if v.effective_event['new_disposition']=='CANDIDATE_REJECTED'],
        'outstanding_decision_ids':list(outstanding_decision_ids),'apply_back_permitted':False,
        'resume':{'permitted':resume_permitted,'next_gate':next_gate if resume_permitted else None,'reason':reason}}
    registry.schemas.validate(report,'terminal_report_v2')
    validate_terminal(report,pointer,latest.creation if latest else None,creation_ref,
        latest.effective_event if latest else None,latest.effective_event_ref if latest else None,
        latest.decision if latest else None,decision_ref)
    return report


def finish_proposal_round(store,*,admission,round_number,decided_at):
    """Register, commit the bounded decision and retain a terminal projection.

    No Editor or Semantic Verifier can be invoked by this API. Storage errors
    propagate; callers can inspect the last committed disposition and explicitly
    recover without inventing the intended decision as an effective result.
    """
    registry=registry_for_proposal_requests(store,load_inputs=admission.load_inputs,
                                            validate_authority=admission.validate_authority)
    journal=decision_journal_for(admission,registry)
    from whetstone.vnext_proposal_requests import _Journal
    request=_Journal(store,lambda read:admission.load_inputs(read,round_number))
    _,_,proposal,receipt=request.inspect()
    require(receipt is not None and proposal is not None,'closeout requires a completed proposal request')
    failure=None
    try:
        creation=registry.register(round_number=round_number,proposal_id=proposal.patch['proposal_id'],created_at=decided_at)
    except CandidateAssemblyFailure as exc:
        failure=exc
    else:journal.commit(creation['candidate_id'],decided_at=decided_at)
    with store.locked(admission.validate_authority) as token:
        report=journal.terminal(**({'terminal_state':'HALTED_ARTIFACT_INVALID',
            'reason':'vnext_assembly_invalid','next_gate':'assembly'} if failure is not None else {}))
        # Content-addressed projections are retained history, never a selector
        # of current disposition. Fresh status always derives from commit data.
        path='rounds/terminal_reports/terminal-'+sha256_bytes(canonical_json_bytes(report))+'.json'
        store.publish(token,path,report)
        return report,_ref(path,report)


def run_proposal_round(store,*,admission,round_number,client,decided_at,continuation=False):
    """Run the admitted request through its bounded D7 proposal-only endpoint."""
    require(type(continuation) is bool,'continuation must be explicit boolean')
    from whetstone.vnext_proposal_requests import run_proposal_request,inspect_proposal_request,finish_proposal_request
    load=lambda read:admission.load_inputs(read,round_number)
    if client is None:
        result=inspect_proposal_request(store,load_inputs=load,validate_authority=admission.validate_authority)
        require(result.status in {'complete','invalid_proposal','attempts_exhausted'}
                or (continuation is True and result.status=='valid_response'),
                'an Editor client is required unless exact retained output can complete this gate')
        if result.status=='valid_response':
            result=finish_proposal_request(store,load_inputs=load,
                validate_authority=admission.validate_authority,continuation=continuation)
    else:
        result=run_proposal_request(store,load_inputs=load,
            validate_authority=admission.validate_authority,client=client,continuation=continuation)
    registry=registry_for_proposal_requests(store,load_inputs=admission.load_inputs,
                                            validate_authority=admission.validate_authority)
    journal=decision_journal_for(admission,registry)
    if result.status=='complete':
        if continuation:
            failure_path=f"rounds/round-{round_number}/proposals/{result.proposal.patch['proposal_id']}/assembly_failure.json"
            require(journal._optional(failure_path,'vnext_candidate_assembly_failure_v1') is None,
                    'deterministic assembly failure is not a technical continuation')
            creation=next((e for e in registry.inspect().events if e['proposal_id']==result.proposal.patch['proposal_id']),None)
            if creation is not None:
                view=journal.inspect(creation['candidate_id'])
                if view.decision is not None:
                    report=journal.terminal()
                    path='rounds/terminal_reports/terminal-'+sha256_bytes(canonical_json_bytes(report))+'.json'
                    try:materialized=store.read(path)
                    except FileNotFoundError:materialized=None
                    # A committed decision with a missing terminal projection
                    # has only materialization work left, never another gate.
                    require(materialized is None,'candidate has no implemented incomplete gate for technical continuation')
        return finish_proposal_round(store,admission=admission,round_number=round_number,decided_at=decided_at)
    last=result.last_outcome or {}
    classification=last.get('classification','interrupted')
    # Eligibility must not erase the actual last machine cause (notably a
    # timeout in slot two). Complete output can be reused without another slot.
    eligible=result.status not in {'attempts_exhausted','invalid_proposal'} and (
        result.attempts<2 or classification=='valid_proposal')
    state='HALTED_CLIENT_TIMEOUT' if classification=='timeout' else 'HALTED_ARTIFACT_INVALID'
    reason='vnext_proposal_'+classification
    if last.get('error'):reason+=': '+last['error']
    with store.locked(admission.validate_authority) as token:
        report=journal.terminal(terminal_state=state,reason=reason,
            next_gate='proposal',resume_permitted=eligible)
        path='rounds/terminal_reports/terminal-'+sha256_bytes(canonical_json_bytes(report))+'.json'
        store.publish(token,path,report)
        return report,_ref(path,report)


def decision_journal_for(admission,registry):
    factory=getattr(admission,'decision_journal',ProposalDecisionJournal)
    return factory(registry)
