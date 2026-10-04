"""Phase 2 command loop delegates every transition to its existing owner."""
from whetstone import vnext_admission as common
from whetstone.vnext_contracts import canonical_json_bytes, require
from whetstone.vnext_proposal_cli import _client
from whetstone.vnext_verified_command_state import ENTRY_PATH, inspect_command, optional
from whetstone.vnext_verified_commands import enter, guarded, phase2_client, repair, admit_selection, transaction_selection, report_failed_request


def execute_phase2(run, args, config, review):
    if optional(run, ENTRY_PATH) is None:
        result = enter(run, args, config, review)
        if optional(run, ENTRY_PATH) is None: return result
    seen = set()
    while True:
        state = inspect_command(run)
        key = canonical_json_bytes(state)
        require(key not in seen, 'Phase 2 owner made no progress; stopped without repeating work')
        seen.add(key)
        if state['continuation']: return state
        if state['recovery']:
            repair(run, state, args)
            continue
        gate = state['gate']
        ordinal = state.get('sequence', {}).get('pass_number')
        if gate == 'first_review_binding':
            if state.get('declaration', {}).get('committed') is False:
                guarded(run, state, run.prepare_phase2_declaration)
                continue
            client = phase2_client(run, args, config, review)
            guarded(run, state, lambda: run.bind_phase2_review(client.transport_binding))
            # Reselect the committed first request before any client invocation,
            # just as for later requests. Declaration preparation is separately selected.
        elif gate == 'review':
            client = phase2_client(run, args, config, review)
            guarded(run, state, lambda: run.bind_phase2_next_review(client.transport_binding))
            # Reselect the committed request; pending_review guards its actual
            # invocation under D8, including when another command raced binding.
        elif gate == 'pending_review':
            if state['request_status'] != 'not_started': return state
            client = phase2_client(run, args, config, review)
            operation = (lambda: run.run_phase2_review(client=client)) if ordinal == 1 else (
                lambda: run.continue_phase2_pass(ordinal, action='execute', client=client))
            result = guarded(run, state, operation)
            if getattr(result, 'status', '') != 'complete': return inspect_command(run)
        elif gate == 'result_consumption_required':
            guarded(run, state, run.consume_phase2_result if ordinal == 1 else
                    lambda: run.continue_phase2_pass(ordinal, action='consume'))
        elif gate == 'advice_handoff_required':
            guarded(run, state, run.bind_phase2_advice if ordinal == 1 else
                    lambda: run.continue_phase2_pass(ordinal, action='advice'))
        elif gate in {'operator_or_advice_required', 'correction_required'}:
            selector = getattr(args, 'vnext_decisions', None)
            if selector:
                admit_selection(run, state, selector, phase2=True)
            else:
                if gate == 'operator_or_advice_required':
                    return dict(state, operator=run.phase2_operator_context())
                guarded(run, state, run.admit_phase2_round if ordinal == 1 else
                        lambda: run.continue_phase2_pass(ordinal, action='admit'))
        elif gate == 'proposal':
            if state['request_status'] != 'not_started': return state
            result = guarded(run, state, lambda: run.request(round_number=state['round_number'],
                client=_client('editor', review, config, args, run.store.root), **transaction_selection(state)))
            if result.value.status != 'complete':
                return report_failed_request(run, args, result, phase2=True, request_state=state)
        elif gate == 'registration':
            guarded(run, state, lambda: run.register(round_number=state['round_number'], created_at=common.stamp(),
                                                   **transaction_selection(state)))
        elif gate == 'verification':
            result = guarded(run, state, lambda: run.verify(
                client=_client('verifier', review, config, args, run.store.root), decided_at=common.stamp()))
            if result.outcome not in {'candidate_final', 'promotion_required'}: return inspect_command(run)
        elif gate == 'promotion':
            guarded(run, state, lambda: run.promote(prepared_at=common.stamp()))
        elif gate == 'declaration_maintenance_required':
            guarded(run, state, run.prepare_phase2_declaration)
        elif gate in {'declaration_closeout_required', 'closeout_required'}:
            # Ready publication is selected explicitly by inspect_command.
            # Remaining declaration blockers belong to their existing owners.
            return state
        else:
            # Unhandled gates retain their owner and require explicit action.
            return state
