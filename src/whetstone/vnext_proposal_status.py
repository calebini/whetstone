"""Read-only next-work inspection for a selected stored proposal round."""
from whetstone.vnext_candidate_registry import CandidateAssemblyFailure
from whetstone.vnext_contracts import canonical_json_bytes,require,sha256_bytes
from whetstone.vnext_proposal_closeout import decision_journal_for
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_proposal_requests import inspect_proposal_request
from whetstone.vnext_proposal_run import round_input_path


def _unadmitted_review_status(run,packet):
    """Project only a live seed sequence; externally staged rounds stay explicit."""
    try:run.store.list_directory('rounds/review_index');live=True
    except FileNotFoundError:
        run.store.read_descriptor()
        live=not run._staged and not any(name.startswith('round-') for name,kind in run.store.list_directory('rounds'))
    if not live:return
    review=run.review_status()
    if review.round_number!=packet['round_number']:
        packet['resume']['reason']='vnext_selected_round_not_active';return
    packet.update(request_id=review.request_id,request_status=review.status,request_attempts=review.attempts)
    if review.status=='finding_admission':
        packet['processing_gate']='finding_admission'
        packet['resume']['reason']='vnext_finding_admission_required'
        from whetstone.vnext_operator_decisions import operator_pause
        work,report,materialization=operator_pause(run,round_number=review.round_number)
        packet['operator_work']=work
        if report is not None:
            packet.update(terminal_report=report,terminal_materialization='present' if materialization['materialized'] else 'missing')
            packet['resume']=dict(report['resume'])
        return
    if review.status in {'phase_1_stable','budget_exhausted'}:
        packet['resume']['reason']='vnext_'+review.status
    eligible=review.status not in {'not_started','invalid_review','attempts_exhausted'} and (
        review.attempts<2 or review.status=='valid_response')
    cause=(review.last_outcome or {}).get('classification',review.status)
    reason='vnext_review_'+cause
    if (review.last_outcome or {}).get('error'):reason+=': '+review.last_outcome['error']
    packet['resume']={'permitted':eligible,'next_gate':'review' if eligible else None,'reason':reason}
    from whetstone.vnext_seed_review_closeout import inspect_seed_review_closeout
    closeout=inspect_seed_review_closeout(run,review)
    if closeout is not None:
        packet.update(terminal_report=closeout.report,
            terminal_materialization='present' if closeout.materialized else 'missing')
        if closeout.final:
            packet['processing_gate']='complete' if closeout.materialized else 'materialization'
            packet['resume']=dict(closeout.report['resume']) if closeout.materialized else {
                'permitted':True,'next_gate':'materialization','reason':'vnext_terminal_materialization_incomplete'}


def inspect_proposal_run(run,*,round_number):
    """Inspect hashes and commit bindings without locks, writes or clients.

    The selected round is explicit. This reader never guesses the active round
    from directory ordering, timestamps, terminal projections or candidate IDs.
    """
    store=run.store;run.validate_authority(store.read)
    number=round_number;path=round_input_path(number)
    packet={'schema_version':'vnext-proposal-status-v1','job_id':run._record['job_id'],'round_number':number,
        'processing_gate':'review','request_id':None,'request_status':'not_admitted','request_attempts':0,
        'terminal_report':None,'terminal_materialization':'not_applicable',
        'resume':{'permitted':False,'next_gate':None,'reason':'vnext_review_gate_unavailable'}}
    schemas=run._admission(store.read)._base(store.read)[0].suite.registry
    registry=registry_for_proposal_requests(store,load_inputs=run.load_inputs,validate_authority=run.validate_authority)
    registered=registry.inspect();journal=decision_journal_for(run,registry)
    for event in registered.events:journal._state(event)
    try:store.read(path)
    except FileNotFoundError:
        if number not in run._staged:
            require(not registered.orphans,'unresolved candidate orphan requires registration recovery')
            _unadmitted_review_status(run,packet)
            schemas.validate(packet,'vnext_proposal_status_v1');return packet
    request=inspect_proposal_request(store,load_inputs=lambda read:run.load_inputs(read,number),
                                    validate_authority=run.validate_authority)
    packet.update(request_id=request.request_id,request_status=request.status,request_attempts=request.attempts)
    def finish(gate,permitted,reason,report=None,materialization='not_applicable'):
        packet.update(processing_gate=gate,terminal_report=report,terminal_materialization=materialization,
            resume={'permitted':permitted,'next_gate':gate if permitted else None,'reason':reason})
        schemas.validate(packet,'vnext_proposal_status_v1');return packet
    if registered.orphans:
        # Recovery is available only for the complete sole canonical claimant,
        # and only when it belongs to this selected completed request.
        eligible=False
        if len(registered.orphans)==1 and request.status=='complete':
            try:
                previous=sha256_bytes(canonical_json_bytes(registered.events[-1])) if registered.events else None
                pending,_=registry._validate_preparation(registered.orphans[0],ordinal=len(registered.events)+1,previous=previous)
                eligible=pending['round_number']==number and pending['proposal_id']==request.proposal.patch['proposal_id']
            except (ValueError,OSError):pass
        run.validate_authority(store.read)
        return finish('assembly',eligible,'vnext_registration_recovery_required')
    if request.status!='complete':
        if request.status=='not_started':return finish('proposal',False,'vnext_proposal_not_started')
        classification=(request.last_outcome or {}).get('classification','interrupted')
        eligible=request.status not in {'invalid_proposal','attempts_exhausted'} and (
            request.attempts<2 or request.status=='valid_response')
        reason='vnext_proposal_'+classification
        if (request.last_outcome or {}).get('error'):reason+=': '+request.last_outcome['error']
        state='HALTED_CLIENT_TIMEOUT' if classification=='timeout' else 'HALTED_ARTIFACT_INVALID'
        report=journal.terminal(terminal_state=state,reason=reason,next_gate='proposal',resume_permitted=eligible)
        return finish('proposal',eligible,reason,report)
    proposal_id=request.proposal.patch['proposal_id']
    failure_path=f'rounds/round-{number}/proposals/{proposal_id}/assembly_failure.json'
    failure=journal._optional(failure_path,'vnext_candidate_assembly_failure_v1')
    if failure is not None:
        # A diagnostic file cannot manufacture a deterministic rejection.
        try:registry._material(number,proposal_id)
        except CandidateAssemblyFailure as exc:require(exc.evidence==failure,'assembly diagnostic does not reproduce')
        else:require(False,'assembly diagnostic contradicts reproducible candidate')
        report=journal.terminal(terminal_state='HALTED_ARTIFACT_INVALID',reason='vnext_assembly_invalid')
        return finish('assembly',False,'vnext_assembly_invalid',report)
    creation=next((e for e in registered.events if e['proposal_id']==proposal_id),None)
    if creation is None:
        report=journal.terminal(terminal_state='HALTED_ARTIFACT_INVALID',reason='vnext_registration_incomplete',
                                        next_gate='assembly',resume_permitted=True)
        return finish('assembly',True,'vnext_registration_incomplete',report)
    candidate_status=getattr(run,'candidate_status',None)
    if creation==registered.latest and candidate_status is not None:
        # The exact completed request and registered selection were already
        # validated above. Let the qualified consumer project this candidate.
        return candidate_status(number,journal,creation)
    view=journal.inspect(creation['candidate_id'])
    if view.decision is None:
        report=journal.terminal(terminal_state='HALTED_ARTIFACT_INVALID',
            reason='vnext_verification_commit_incomplete',next_gate='verification_commit',resume_permitted=True)
        return finish('verification_commit',True,'vnext_verification_commit_incomplete',report)
    report=journal.terminal()
    if creation!=registered.latest:return finish('complete',False,'vnext_historical_proposal_complete',report)
    raw=canonical_json_bytes(report);target='rounds/terminal_reports/terminal-'+sha256_bytes(raw)+'.json'
    try:materialized=store.read(target)
    except FileNotFoundError:materialized=None
    require(materialized is None or materialized==raw,'terminal materialization conflicts with committed evidence')
    if materialized is None:return finish('materialization',True,'vnext_terminal_materialization_incomplete',report,'missing')
    gate='complete' if view.decision['decision_final'] else 'semantic_verification'
    return finish(gate,False,report['resume']['reason'],report,'present')
