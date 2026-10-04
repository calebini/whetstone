"""Read-only command selection from proven authority and retained request journals."""
from dataclasses import asdict, is_dataclass

from whetstone.vnext_contracts import canonical_json_bytes, decode_json, require, sha256_bytes
from whetstone.vnext_proposal_run import round_input_path
from whetstone.vnext_verified_phase2_binding import REQUEST_PATH as ENTRY_REQUEST
from whetstone.vnext_verified_phase2_entry import ENTRY_PATH
from whetstone.vnext_verified_phase2_review import REQUEST_PATH as REVIEW_REQUEST


def public(value):
    if is_dataclass(value): return public(asdict(value))
    if isinstance(value, dict): return {k: public(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [public(v) for v in value]
    return value


def optional(run, path):
    try: return run.store.read(path)
    except FileNotFoundError: return None


def selected(gate, *, phase='phase_1', recovery=None, continuation=None, **evidence):
    return dict(gate=gate, phase=phase, recovery=recovery, continuation=continuation, **public(evidence))


def pending_vertical_merge(proof):
    from whetstone.vnext_verified_vertical_phase1 import enabled, sequence
    if not enabled(proof.seed_values['review']): return None
    state = sequence(proof)
    if state.gate not in {'finding_admission', 'merge_required'}: return None
    packet, _, _, present = state.merges[-1]
    if present: return None
    from whetstone.vnext_verified_phase2_binding import _ref
    return selected('merge_required', round_number=state.number,
                    merge=_ref(f'rounds/round-{state.number}/vertical_merge.json', packet))


def candidate_state(run, proof):
    from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal, inspect_verified_semantic_request
    proof.inspect_registry()
    if not proof.view.creations: return None
    creation = proof.view.creations[-1]
    if creation['candidate_id'] in {p['source_candidate_id'] for p in proof.pointers[1:]}: return None
    journal = VerifiedSemanticDecisionJournal(proof.router.registry(), admission=proof.router)
    decision_state = journal._state(creation)
    view = decision_state[0]
    evidence = dict(candidate=creation, round_number=creation['round_number'], decision=view.decision)
    if view.prepared:
        pending = decision_state[3]
        from whetstone.vnext_verified_history import _ref
        reference = _ref(journal.paths(creation, pending['decision_ordinal'])[1], pending)
        return selected('verification_publication', recovery='verification', pending_decision=reference, **evidence)
    if view.decision is not None and view.decision['decision_final']:
        from whetstone.vnext_semantic_followup_admission import _selection_path
        path = _selection_path(creation)
        raw = optional(run, path)
        if raw is not None:
            reference = dict(path=path, hash=sha256_bytes(raw))
            marker = proof.reader.json(reference, 'vnext_semantic_followup_selection_v1')
            require(marker['job_id'] == creation['job_id'] and marker['candidate_id'] == creation['candidate_id'],
                    'child selection differs from the latest candidate')
            result = proposal_state(run, proof, creation['round_number'], selected_ref=marker['transaction_input'],
                                    source_candidate=creation)
            result.update(source_candidate=creation, source_decision=view.decision, selection=reference)
            return result
        return selected('candidate_final', **evidence)
    if view.decision is None: return selected('verification', **evidence)
    request = inspect_verified_semantic_request(run.store, admission=proof.router,
                                               candidate_id=creation['candidate_id'])
    # The journal's status is itself a bounded permission decision.
    status = request.status
    return selected('verification', continuation='verifier' if status not in
        {'not_started', 'invalid_semantic', 'attempts_exhausted'} else None,
        request_status=status, request_id=request.request_id, attempts=request.attempts, **evidence)


def proposal_state(run, proof, number, *, selected_ref=None, source_candidate=None):
    from whetstone.vnext_proposal_requests import inspect_proposal_request
    # Selection is read-only. Live _Admission requires a borrowed writer fence
    # and is used only by the subsequent request owner, never by status.
    if selected_ref is None:
        router = proof.transactions()
    else:
        from whetstone.vnext_verified_history import _VerifiedTransactions, _ref
        require(source_candidate is not None, 'child selection requires its exact source candidate')
        parent = _ref(f"rounds/candidate_index/creation-{source_candidate['candidate_creation_ordinal']}.json", source_candidate)
        router = _VerifiedTransactions(proof.store, original=proof.admission, selected_ref=selected_ref)
    def load(read):
        proof.guard(read)
        if selected_ref is not None:
            require(router.selected_record(read)['source_creation'] == parent,
                    'selected child admission belongs to another parent')
            router.validate_selected(read)
        inputs = router.load_inputs(read, number)
        require(inputs['base_pointer_ref'] == proof.latest,
                'proposal selection requires its exact current base pointer')
        proof.guard(read)
        return inputs
    result = inspect_proposal_request(run.store, load_inputs=load, validate_authority=proof.guard)
    return selected('registration' if result.status == 'complete' else 'proposal', round_number=number,
        request_status=result.status, request_id=result.request_id, attempts=result.attempts,
        continuation='editor' if result.status not in
        {'not_started', 'complete', 'invalid_proposal', 'attempts_exhausted'} else None,
        **(dict(selected_ref=selected_ref) if selected_ref is not None else {}))


def phase2_state(run):
    from whetstone.vnext_verified_phase2_sequence import _Continuation, sequence, _status
    entry = public(run.phase2_state())
    if not entry.get('state_current'):
        return selected('entry_projection', phase='phase_2', recovery='entry', entry=entry)
    if optional(run, REVIEW_REQUEST) is None:
        from whetstone.vnext_verified_phase2_review import _FirstReview, INPUT_PATH, PROMPT_PATH
        from whetstone.vnext_phase2_targets import supported, initial_owner
        owner = _FirstReview(run)
        proof = owner._proof(run.store.read)
        evidence = dict(entry=entry)
        if supported(proof.reader.suite):
            from whetstone.vnext_phase2_routes import first_round
            from whetstone.vnext_verified_phase2_closeout import _bundle
            binding = owner._committed_binding(proof)
            bound_entry = owner._entry_view(proof, binding)
            first = initial_owner(run, proof, binding, bound_entry, first_round(proof, bound_entry.entry))
            package = _bundle(first, [], [])
            evidence['declaration'] = {k: v for k, v in package.items() if k != 'assets'}
        # A partial dependency publication is still preparation, not a client
        # request or a new resume row. Bind visible bytes into the fence check.
        evidence['preparation'] = [dict(path=path, hash=sha256_bytes(raw))
            for path in (INPUT_PATH, PROMPT_PATH) if (raw := optional(run, path)) is not None]
        proof.guard(run.store.read)
        return selected('first_review_binding', phase='phase_2', **evidence)
    owner = _Continuation(run)
    proof = owner._proof(run.store.read)
    state = sequence(proof)
    status = _status(state)
    gate = status.pop('gate')
    evidence = dict(sequence=status)
    if state['frames']:
        frame = state['frames'][-1]
        evidence['review_evidence'] = dict(request=frame['bound'].request_ref,
            pass_number=frame['owner'].ordinal, request_id=frame['journal'].id,
            attempts=len(frame['outcomes']), last_outcome=frame['outcomes'][-1] if frame['outcomes'] else None,
            receipt=frame['receipt'], consumed=bool(frame.get('consumed')))
    # Report repairs always precede another client. These owners validate their
    # own historical sources, rather than interpreting mutable state as consent.
    mirror_repair = None
    for name, inspect in (('failure', run.phase2_failure_status),
                          ('correction_failure', run.phase2_correction_failure_status),
                          ('resolution', run.phase2_resolution_status),
                          ('signal', run.phase2_signal_status)):
        report = public(inspect())
        if report.get('publication_required') or report.get('pending_paths'):
            return selected(name+'_publication', phase='phase_2', recovery=name+'_publication', report=report, **evidence)
        if report.get('state_current') is False:
            return selected(name+'_projection', phase='phase_2', recovery=name+'_projection', report=report, **evidence)
        # Failure families share report mirrors. A mirror mismatch alone must
        # not steal a later family's own pending publication/state projection.
        if report.get('mirrors_current') is False and mirror_repair is None:
            mirror_repair = selected(name+'_projection', phase='phase_2', recovery=name+'_projection', report=report, **evidence)
    closeout = public(run.phase2_closeout())
    if closeout.get('committed'):
        if not closeout.get('state_current') or not closeout.get('mirror_current'):
            return selected('closeout_projection', phase='phase_2', recovery='closeout_projection', closeout=closeout, **evidence)
        if mirror_repair is not None: return mirror_repair
        return selected('phase2_complete' if closeout.get('phase_complete') else 'phase2_stopped',
                        phase='phase_2', closeout=closeout, **evidence)
    if closeout.get('gate') in {'closeout_publication_required', 'failure_report_publication_required'}:
        return selected('closeout_publication', phase='phase_2', recovery='closeout_publication',
                        closeout=closeout, **evidence)
    if mirror_repair is not None: return mirror_repair
    if gate in {'budget_exhausted', 'closeout_required'} and closeout.get('gate') == 'declaration_maintenance_required':
        from whetstone.vnext_verified_phase2_halt import maintenance_owner
        from whetstone.vnext_verified_phase2_closeout import _bundle
        package = _bundle(maintenance_owner(run, proof, state), state['frames'], state['clean'])
        return selected('declaration_maintenance_required', phase='phase_2', closeout=closeout,
                        declaration={k: v for k, v in package.items() if k != 'assets'}, **evidence)
    if gate == 'declaration_closeout_required':
        findings = public(run.phase2_final_findings())
        if not findings.get('committed'):
            return selected('findings_publication', phase='phase_2', recovery='findings_publication',
                            findings=findings, **evidence)
        evidence['findings'] = findings
        if findings['packet']['blocking_reasons']:
            # This owner explains retained disagreement without publishing or
            # granting repair/review permission. Keep the existing stopped gate.
            evidence['blocked_report'] = public(run.phase2_blocked_report())
    if gate == 'review':
        from whetstone.vnext_verified_phase2_closeout import _DeclarationPass, _bundle
        if isinstance(state['owner'], _DeclarationPass):
            package = _bundle(state['owner'], state['frames'], state['clean'])
            if not package['committed']:
                return selected('declaration_maintenance_required', phase='phase_2',
                    declaration={k: v for k, v in package.items() if k != 'assets'}, **evidence)
    if gate == 'pending_review':
        frame = state['frames'][-1]
        outcomes = frame['outcomes']
        status = ('valid_response' if frame['review'] is not None else
                  'attempts_exhausted' if len(outcomes) >= 2 else
                  outcomes[-1]['classification'] if outcomes else 'not_started')
        evidence.update(request=frame['bound'].request_ref, request_status=status,
                        pass_number=frame['owner'].ordinal, attempts=len(outcomes))
        return selected(gate, phase='phase_2', continuation='phase2_reviewer' if
            status not in {'not_started', 'invalid_review', 'attempts_exhausted'} else None, **evidence)
    if gate in {'operator_or_advice_required', 'correction_required'}:
        from whetstone.vnext_phase2_reviewer_advice import supported as advice_supported
        frame = state['frames'][-1]
        if advice_supported(proof.reader.suite):
            advice = frame['owner']._advice_view(frame['owner'].proof, None)[-1]
            if advice['status'] != 'bound':
                interrupted = optional(run, frame['owner'].advice_path) is not None
                return selected('advice_handoff_required', phase='phase_2',
                    recovery='advice' if interrupted else None, pass_number=frame['owner'].ordinal,
                    request=frame['bound'].request_ref, advice=advice, **evidence)
    if gate == 'correction_required':
        number = status['round_number']
        if optional(run, round_input_path(number)) is not None:
            result = candidate_state(run, proof) or proposal_state(run, proof, number)
            result['phase'] = 'phase_2'
            # Generic Phase 2 Editor/Verifier continuation is deliberately absent.
            if result['continuation']: result['continuation'] = 'unsupported_phase2_continuation'
            return result
    return selected(gate, phase='phase_2', closeout=closeout, **evidence)


def inspect_command(run):
    state = _inspect_command(run)
    from whetstone.vnext_verified_phase1_budget import DIRECTORY, recovery_record
    # Materialization recovery deliberately precedes current scheduler replay.
    # Optional grant metadata must not add that dependency back to this row.
    if (state['phase'] == 'phase_1' and state['recovery'] != 'materialization'
            and optional(run, DIRECTORY+'/extension-1.json') is not None):
        proof = run._operator()._proof(run.store.read)
        grant = recovery_record(proof)
        if grant is not None:
            reference, value = grant
            state['budget_reentry'] = dict(reference=reference, event=value['event'])
        proof.guard(run.store.read)
    return state


def _inspect_command(run):
    work = run.inspect()
    phase = 'phase_2' if optional(run, ENTRY_REQUEST) is not None else 'phase_1'
    if work.outcome == 'materialization_required':
        return selected(work.outcome, phase=phase, recovery='materialization', work=work)
    if work.outcome == 'registration_recovery_required':
        proof = run._operator()._proof(run.store.read)
        proof.inspect_registry()
        require(len(proof.view.orphans) == 1, 'registration recovery requires one claimant')
        previous = proof.view.creations[-1] if proof.view.creations else None
        creation, _ = proof.router.registry()._validate_preparation(proof.view.orphans[0],
            ordinal=len(proof.view.creations) + 1,
            previous=sha256_bytes(canonical_json_bytes(previous)) if previous else None)
        path = proof.view.orphans[0] + '/registration_preparation.json'
        proof.guard(run.store.read)
        return selected(work.outcome, phase=phase, recovery='registration', work=work,
            round_number=creation['round_number'], candidate=creation,
            preparation=dict(path=path, hash=sha256_bytes(run.store.read(path))))
    if work.outcome == 'promotion_required':
        from whetstone.vnext_verified_run import _RunPromotion
        promotion = _RunPromotion(run.store, history=run._history()).inspect()
        return selected('promotion', phase=phase, recovery='promotion' if promotion.outcome == 'claimant_prepared' else None,
                        work=work, promotion=promotion)
    if optional(run, ENTRY_PATH) is not None: return phase2_state(run)
    proof = run._operator()._proof(run.store.read)
    candidate = candidate_state(run, proof)
    if candidate:
        candidate['phase'] = phase
        if phase == 'phase_2' and candidate['continuation']:
            candidate['continuation'] = 'unsupported_phase2_continuation'
        return candidate
    if optional(run, ENTRY_REQUEST) is not None:
        return selected('entry_required', phase='phase_2')
    status = run.phase1_status()
    operator = run.operator_status()
    if operator.next_action in {'reconcile_phase1_state', 'finish_phase1'}:
        return selected(operator.next_action, recovery='phase1_projection' if
            operator.next_action == 'reconcile_phase1_state' else 'phase1_publication', operator=operator)
    if status.review_gate in {'finding_admission', 'merge_required'}:
        merge = pending_vertical_merge(proof)
        if merge is not None: return merge
    if status.review_gate == 'finding_admission' and optional(run, round_input_path(status.review_round)) is not None:
        return proposal_state(run, proof, status.review_round)
    review = run.review_status()
    if operator.terminal_report is not None and status.review_gate != 'pending':
        return selected('phase1_complete' if operator.accepted else 'phase1_stopped', operator=operator)
    return selected(status.review_gate, round_number=status.review_round, status=status, review=review,
        continuation='reviewer' if status.review_gate == 'pending' and review.status not in
        {'invalid_review', 'attempts_exhausted'} else None)
