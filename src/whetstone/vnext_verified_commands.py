"""Bounded command adapters over existing verified owners, with no public activation."""
from pathlib import Path

from whetstone import vnext_admission as common
from whetstone.vnext_contracts import canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_proposal_cli import _client
from whetstone.vnext_verified_command_state import (
    ENTRY_PATH, ENTRY_REQUEST, REVIEW_REQUEST, inspect_command, optional, public,
)


class SelectionChanged(ValueError):
    """The selected boundary changed before its actual writer fence."""


def guarded(run, expected, operation, *, validate_inputs=None):
    def validate(read):
        if validate_inputs is not None: validate_inputs()
        current = inspect_command(run)
        if current == expected: return
        # Promotion owns a second fence for its committed pointer's mirrors.
        # Only that exact selected candidate/ordinal may cross the boundary.
        if expected['gate'] == 'promotion' and current['recovery'] == 'materialization':
            old = expected['work']['current_pointer']
            head = current['work']['current_pointer']
            if (head['source_candidate_id'] == expected['promotion']['candidate_id'] and
                    head['promotion_ordinal'] == old['promotion_ordinal'] + 1): return
        raise SelectionChanged('selected boundary changed; inspect the current result before another invocation')
    with run.store.guard_invocation(validate):
        return operation()


def phase2_client(run, args, config, review):
    from whetstone.vnext_native_phase2_reviewer import NativePhase2ReviewerClient
    return NativePhase2ReviewerClient(review=review,
        command=config.get('clients', {}).get('reviewer', {}).get('command'), cwd=run.store.root,
        timeout_seconds=getattr(args, 'reviewer_timeout_seconds', None) or
            getattr(args, 'timeout_seconds', None) or config.get('timeouts', {}).get('reviewer_seconds', 360))


def configuration(run, config):
    reference = config.get('vnext_phase2_configuration')
    require(isinstance(reference, dict) and set(reference) == {'path', 'hash'},
            'Phase 2 requires an exact root-relative vnext_phase2_configuration Ref')
    raw = confined_file(run.store.root, reference['path']).read_bytes()
    require(sha256_bytes(raw) == reference['hash'], 'Phase 2 configuration hash differs')
    packet = decode_json(raw)
    require(raw == canonical_json_bytes(packet), 'Phase 2 configuration must be canonical')
    require(packet['review_mode'] != 'vertical' or
            (packet['target_phase'], packet['target_mode']) == ('final', 'strict'),
            'vertical Phase 2 supports final/strict only')
    return packet


def enter(run, args, config, review):
    packet = configuration(run, config)
    def selected_inputs():
        require(configuration(run, config) == packet, 'Phase 2 configuration changed before entry operation')
        if optional(run, ENTRY_REQUEST) is not None:
            request = decode_json(run.store.read(ENTRY_REQUEST))
            require(run.store.read(request['configuration']['path']) == canonical_json_bytes(packet),
                    'Phase 2 configuration differs from committed binding')
    def entry_operation(state, operation):
        return guarded(run, state, operation, validate_inputs=selected_inputs)
    if optional(run, ENTRY_REQUEST) is None:
        entry_operation(inspect_command(run), lambda: run.bind_phase2_entry(packet))
    else:
        # Preparation binds the supplied bytes even on reentry; it grants no entry.
        proof = run._operator()._proof(run.store.read)
        request = decode_json(run.store.read(ENTRY_REQUEST))
        require(proof.reader.raw(request['configuration']) == canonical_json_bytes(packet),
                'Phase 2 configuration differs from committed binding')
    while True:
        state = inspect_command(run)
        require(not state['recovery'] and not state['continuation'],
                'entry requires explicit bounded recovery before new work')
        if optional(run, ENTRY_PATH) is not None: return run.phase2_state()
        if state['gate'] == 'entry_required':
            from whetstone.vnext_version_operations import project
            pointer = decode_json(run.store.read('rounds/current_verified.json'))
            base = run.store.read(pointer['verified_draft_path'])
            projected, _ = project(base, base, phase='phase_2', transition='phase2_entry')
            if projected != base:
                entry_operation(state, lambda: run.prepare_phase2_version(created_at=common.stamp()))
                continue
            return entry_operation(state, run.enter_phase2)
        if state['gate'] == 'verification':
            result = entry_operation(state, lambda: run.verify(
                client=_client('verifier', review, config, args, run.store.root), decided_at=common.stamp()))
            if getattr(result, 'outcome', '') == 'continuation_required': return result
        elif state['gate'] == 'promotion':
            entry_operation(state, lambda: run.promote(prepared_at=common.stamp()))
        else: return state


def repair(run, state, args):
    row = state['recovery']
    if row in {'resolution_publication', 'closeout_publication'}:
        # One selected outcome includes its reports and derived state. Bind each
        # owner under its own fence; the second fence may only project the exact
        # result just published, never select a successor or spend an allowance.
        family = row.removesuffix('_publication')
        publish, project, field = ((run.publish_phase2_resolutions, run.reconcile_phase2_resolution_state, 'report')
            if family == 'resolution' else (run.finish_phase2, run.reconcile_phase2_state, 'closeout'))
        published = public(guarded(run, state, publish))
        current = inspect_command(run)
        require(current['recovery'] == family+'_projection' and current[field] == published
                and current['sequence']['current_pointer'] == state['sequence']['current_pointer'],
                'published outcome changed before projection; inspect before resuming')
        return guarded(run, current, project)
    if row in {'registration', 'verification'}:
        number = getattr(args, 'vnext_round', None)
        require(number is not None, 'publication recovery requires --vnext-round')
        if state.get('round_number') is not None:
            require(number == state['round_number'], 'publication recovery round differs')
        else:
            proof = run._operator()._proof(run.store.read)
            proof.inspect_registry()
            # Reconciliation may only finish producer bytes for the explicit round.
            import re
            require(len(proof.view.orphans) == 1, 'registration recovery requires one claimant')
            match = re.fullmatch(r'rounds/round-([1-9][0-9]*)/candidates/cand_[0-9a-f]{64}', proof.view.orphans[0])
            require(match is not None and int(match[1]) == number, 'orphan belongs to another round')
    operations = {
        'materialization': run.recover_registration,
        'registration': run.recover_registration,
        'verification': lambda: run.verify(decided_at=common.stamp(), continuation=True),
        'promotion': lambda: run.promote(prepared_at=common.stamp()),
        'phase1_publication': run.finish_phase1,
        'phase1_projection': run.reconcile_phase1_state,
        'entry': run.enter_phase2,
        'failure_publication': run.publish_phase2_failure,
        'failure_projection': run.reconcile_phase2_failure_state,
        'correction_failure_publication': run.publish_phase2_correction_failure,
        'correction_failure_projection': run.reconcile_phase2_correction_failure_state,
        'resolution_publication': run.publish_phase2_resolutions,
        'resolution_projection': run.reconcile_phase2_resolution_state,
        'signal_publication': run.publish_phase2_signals,
        'signal_projection': run.reconcile_phase2_signal_state,
        'closeout_projection': run.reconcile_phase2_state,
        'findings_publication': run.reconcile_phase2_findings,
        'advice': (run.bind_phase2_advice if state.get('pass_number') == 1 else
                   lambda: run.continue_phase2_pass(state['pass_number'], action='advice')),
    }
    require(row in operations, 'no supported publication recovery selected')
    return guarded(run, state, operations[row])


def phase1(run, args, config, review):
    seen = set()
    while True:
        state = inspect_command(run)
        key = canonical_json_bytes(state)
        require(key not in seen, 'owner made no progress; invocation stopped without repeating work')
        seen.add(key)
        require(state['phase'] == 'phase_1', 'Phase 1 cannot execute Phase 2 work')
        if state['continuation']: return state
        if state['recovery']:
            # An ordinary invocation may project its own successful boundary.
            # Interrupted preexisting work is handled by execute's entry guard.
            repair(run, state, args)
            continue
        gate = state['gate']
        if gate in {'review', 'merge_required'}:
            result = guarded(run, state, lambda: run.review_next(
                client=_client('reviewer', review, config, args, run.store.root) if gate == 'review' else None))
            if getattr(result, 'status', '') in {'timeout', 'client_error', 'invalid_review', 'attempts_exhausted'}:
                # Existing closeout owner publishes the technical outcome, not a retry.
                run.finish_phase1(); run.reconcile_phase1_state()
                return inspect_command(run)
        elif gate == 'finding_admission':
            from whetstone.vnext_verified_phase1_decisions import Phase1Decisions
            owner = Phase1Decisions(run)
            context = owner.context()
            selector = getattr(args, 'vnext_decisions', None)
            if selector:
                decisions = owner.selected(common.local_ref(run.store.root, selector))
            else:
                if any(row['classification'] not in {'editor_fixable', 'deferable'} for row in context['findings']):
                    return dict(state, operator=context)
                decisions = ()
            guarded(run, state, lambda: run.admit_reviewed_round(decision_refs=decisions))
        elif gate == 'proposal':
            if state['request_status'] != 'not_started': return state
            result = guarded(run, state, lambda: run.request(round_number=state['round_number'],
                client=_client('editor', review, config, args, run.store.root)))
            if result.value.status != 'complete': return inspect_command(run)
        elif gate == 'registration':
            guarded(run, state, lambda: run.register(round_number=state['round_number'], created_at=common.stamp()))
        elif gate == 'verification':
            result = guarded(run, state, lambda: run.verify(
                client=_client('verifier', review, config, args, run.store.root), decided_at=common.stamp()))
            if result.outcome == 'continuation_required': return inspect_command(run)
        elif gate == 'promotion':
            guarded(run, state, lambda: run.promote(prepared_at=common.stamp()))
        else: return state


def resume(run, args, config, review, state):
    if getattr(args, 'continue_run', False):
        require(state['phase'] == 'phase_1', '--continue is only a Phase 1 operation')
    grant = getattr(args, 'extend_review_budget', None)
    if grant is not None:
        require(state['phase'] == 'phase_1' and state['gate'] == 'phase1_stopped',
                'additional budget requires a retained exhausted Phase 1 context')
        if args.dry_run: return dict(state, proposed_budget_grant=grant)
        return guarded(run, state, lambda: run.extend_phase1_budget(added_rounds_per_profile=grant))
    require(state['recovery'] or state['continuation'], 'no supported recovery or continuation is selected')
    require(state['continuation'] != 'unsupported_phase2_continuation',
            'Phase 2 Editor/Verifier continuation is outside this release contract')
    if state['continuation'] in {'editor', 'verifier'} or state['recovery'] in {'registration', 'verification'}:
        require(getattr(args, 'vnext_round', None) is not None, 'this recovery requires --vnext-round')
    if args.dry_run: return state
    if state['recovery']: return repair(run, state, args)
    role = state['continuation']
    if role in {'editor', 'verifier'}:
        require(args.vnext_round == state['round_number'], 'continuation round differs from active request')
    if role == 'reviewer':
        operation = lambda: run.review_next(client=_client('reviewer', review, config, args, run.store.root), continuation=True)
    elif role == 'editor':
        operation = lambda: run.request(round_number=state['round_number'],
            client=_client('editor', review, config, args, run.store.root), continuation=True)
    elif role == 'verifier':
        operation = lambda: run.verify(client=_client('verifier', review, config, args, run.store.root),
                                       decided_at=common.stamp(), continuation=True)
    else:
        require(role == 'phase2_reviewer', 'unsupported continuation')
        client = phase2_client(run, args, config, review)
        operation = (lambda: run.run_phase2_review(client=client, continuation=True)) if state['pass_number'] == 1 else (
            lambda: run.continue_phase2_pass(state['pass_number'], action='execute', client=client, continuation=True))
    result = guarded(run, state, operation)
    if getattr(args, 'continue_run', False):
        after = inspect_command(run)
        if not after['continuation'] and not after['recovery']: return phase1(run, args, config, review)
    return result


def execute(run, args, config, review):
    command = args.command
    if command in {'strop', 'apply-back'}:
        from whetstone.vnext_verified_source_cli import execute_source
        return execute_source(run, args)
    state = inspect_command(run)
    number = getattr(args, 'vnext_round', None)
    require(number is None or number == state.get('round_number') or state['recovery'] == 'registration',
            'explicit round differs from current command boundary')
    if command == 'status': return state
    if command == 'resume': return resume(run, args, config, review, state)
    if command.startswith('vnext-semantic-'):
        if command == 'vnext-semantic-answers': return run.answers(candidate_id=args.candidate)
        if command == 'vnext-semantic-answer':
            from whetstone.vnext_verified_cli import read_input
            packet = read_input(args.input)
            require(packet.get('candidate_id') == args.candidate, 'answer differs from selected candidate')
            return run.submit_answer(packet=packet, dry_run=args.dry_run)
        return run.select_followup(candidate_id=args.candidate,
                                   answer_reference=dict(path=args.answer_receipt, hash=args.answer_hash))
    if command in {'vnext-decisions', 'vnext-decide'}:
        from whetstone.vnext_verified_cli import read_input
        if getattr(args, 'repair_request', None): return run.admit_phase2_repair(read_input(args.repair_request), dry_run=args.dry_run)
        if getattr(args, 'gap_acceptance', None): return run.accept_phase2_gaps(read_input(args.gap_acceptance), dry_run=args.dry_run)
        advice = getattr(args, 'advice', None)
        if advice is not None:
            require(command == 'vnext-decisions' and state['phase'] == 'phase_2',
                    'finding advice is available only from Phase 2 vnext-decisions')
            packet = read_input(advice)
            ordinal = state.get('sequence', {}).get('pass_number')
            require(type(ordinal) is int and ordinal > 0,
                    'finding advice requires an exact active Phase 2 pass')
            if ordinal == 1:
                return run.prepare_phase2_advice(packet) if args.dry_run else run.bind_phase2_advice(packet)
            return (run.prepare_phase2_continuation_advice(ordinal, packet) if args.dry_run else
                    run.continue_phase2_pass(ordinal, action='advice', advice=packet))
        from whetstone.vnext_verified_phase1_decisions import Phase1Decisions
        from whetstone.vnext_verified_phase2_operator import Phase2Operator
        owner = Phase2Operator(run) if state['phase'] == 'phase_2' else Phase1Decisions(run)
        locator = getattr(args, 'options', None) if command == 'vnext-decisions' else args.selections
        if locator is None: return owner.context()
        return owner.publish(read_input(locator), responses=command == 'vnext-decide', dry_run=args.dry_run)
    if getattr(args, 'dry_run', False): return state
    if state['continuation'] or (state['recovery'] and state['recovery'] not in {'phase1_projection', 'phase1_publication'}):
        return dict(state, next_action='resume')
    if command in {'live-phase1', 'live-focused-phase1'}: return phase1(run, args, config, review)
    if command == 'promote-phase2': return enter(run, args, config, review)
    if command == 'live-phase2':
        from whetstone.vnext_verified_phase2_commands import execute_phase2
        return execute_phase2(run, args, config, review)
    raise ValueError('unsupported verified command')
