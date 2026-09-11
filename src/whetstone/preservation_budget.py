"""Explicit Phase 1 budget grants, bound to completed preservation evidence.

The configured recipe stays frozen. Grants form a separate, replayable overlay;
mutable run-state counters never authorize additional work.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from whetstone.preservation_contracts import decode_json, read_ref, require
from whetstone.preservation_proposals import json_bytes

PREFIX = 'rounds/preservation/budget-extensions'
REASON = 'operator_requested_resume_budget_extension'


def grants(root, *, check_mirror=True):
    from whetstone import preservation_runtime as rt
    from whetstone.resume import _budget_extension_event_id, BUDGET_EXTENSION_TERMINAL_STATES
    root = Path(root)
    paths = list((root/PREFIX).glob('grant-*.json'))
    packets = []
    for ordinal in range(1, len(paths)+1):
        path = root/PREFIX/f'grant-{ordinal}.json'
        require(path.is_file(), 'budget grant sequence is incomplete')
        packet = decode_json(path.read_bytes())
        require(isinstance(packet, dict) and set(packet) == {'version','event','state_before','accepted','reviews','config'},
                'invalid budget grant')
        require(packet['version'] == 'bridge-budget-grant-v1', 'unsupported budget grant')
        event, before = packet['event'], packet['state_before']
        require(isinstance(event, dict) and set(event) == {'event_id','generated_at','phase','previous_terminal_state',
                'previous_current_round','previous_review_profile_budgets','new_review_profile_budgets','added_rounds_per_profile','reason'},
                'invalid budget extension event')
        require(type(event['added_rounds_per_profile']) is int and event['added_rounds_per_profile'] > 0,
                'invalid budget extension amount')
        require(event['phase'] == before['phase'] == 'phase_1' and event['reason'] == REASON
                and event['previous_terminal_state'] == before['terminal_state'] in BUDGET_EXTENSION_TERMINAL_STATES
                and event['previous_current_round'] == before['current_round'], 'budget grant admission differs')
        require(before.get('budget_extensions', []) == [p['event'] for p in packets], 'budget grant predecessor differs')
        require(not packets or before['current_round'] > packets[-1]['event']['previous_current_round'],
                'budget grant requires completed appended work')
        require(event['event_id'] == _budget_extension_event_id(previous_state=before,
                original_budgets=event['previous_review_profile_budgets'], extended_budgets=event['new_review_profile_budgets'],
                extension_rounds=event['added_rounds_per_profile'], reason=REASON, extension_ordinal=ordinal),
                'budget grant identity differs')
        read_ref(root, packet['accepted'])
        for ref in packet['reviews']:
            read_ref(root, ref)
        packets.append(packet)
    if check_mirror:
        require(rt.state_packet(root).get('budget_extensions', []) == [p['event'] for p in packets],
                'budget extension mirror differs; replay the explicit extension to repair an uncommitted mirror')
    return packets


def apply_grant(packet, *, budgets, counts, number, accepted, base_hash):
    """Check a grant at its reconstructed boundary, not against mutable counts."""
    event = packet['event']
    require(event['previous_current_round'] == number and packet['accepted'] == accepted
            and packet['state_before']['current_draft_hash'] == base_hash, 'budget grant completed boundary differs')
    require(event['previous_review_profile_budgets'] == budgets, 'budget grant previous budgets differ')
    expected = {p:max(budgets[p], counts[p])+event['added_rounds_per_profile'] for p in budgets}
    require(event['new_review_profile_budgets'] == expected, 'budget grant accounting differs from completed evidence')
    return expected


def verify_record(root, frozen, number, packets):
    """Completed evidence pins the grants that existed when it was admitted."""
    expected = [p['event'] for p in packets if p['event']['previous_current_round'] < number]
    require(frozen['runtime']['state_before'].get('budget_extensions', []) == expected,
            'completed round budget grants changed')


def mirror(root, packet, packets):
    from whetstone import preservation_runtime as rt
    state = rt.state_packet(root)
    require(state == packet['state_before'], 'budget admission state changed before publication')
    state = deepcopy(state)
    budgets = packet['event']['new_review_profile_budgets']
    state['budget_extensions'] = [p['event'] for p in packets]
    state['review_profile_budgets'] = budgets
    total = sum(budgets.values()) + (max(budgets.values()) if state['review_mode'] == 'vertical' else 0)
    state['review_round_budget'] = total
    state['total_absolute_round_budget'] = total + state.get('convergence_round_budget', 0)
    state['effective_run_config']['review_profile_budgets'] = budgets
    if state.get('scheduler_steps'):
        for step in state['scheduler_steps']:
            step['round_budget'] = budgets[step['profile']]
    rt.acceptance_service(root)._replace('rounds/run_state.json', json_bytes(state))


def prepare(root, config, amount, *, write=False):
    from whetstone import preservation_runtime as rt
    from whetstone.resume import BUDGET_EXTENSION_TERMINAL_STATES, _budget_extension_event_id
    from whetstone.preservation_continuation import pending_review, validate_review_retry, continuation_context
    from whetstone.preservation_vertical import context as vertical_context
    root = Path(root)
    require(type(amount) is int and amount > 0, 'budget extension must add a positive number of rounds')
    packets = grants(root, check_mirror=False)
    state = rt.state_packet(root)
    if packets and state.get('budget_extensions', []) == [p['event'] for p in packets[:-1]]:
        packet = packets[-1]
        require(amount == packet['event']['added_rounds_per_profile'] and state == packet['state_before']
                and packet['config'] == rt._jsonable(asdict(config)), 'pending budget grant admission changed')
        rt.guard_operation(root, config, phase='phase_1', round_number=state['current_round']+1)
        if write:
            mirror(root, packet, packets)
        return packet
    grants(root)
    if packets:
        packet = packets[-1]
        boundary = packet['event']['previous_current_round']
        # A published grant with no completed appended round is the same request.
        completed = any((root/f'rounds/round-{boundary+1}/preservation').glob('attempt-*/acceptance-attempt-*/acceptance.json')) or (
            root/f'rounds/round-{boundary+1}/preservation/review_complete.json').exists()
        if not completed:
            require(amount == packet['event']['added_rounds_per_profile'] and packet['config'] == rt._jsonable(asdict(config)),
                    'pending budget extension settings changed')
            if list((root/f'rounds/round-{boundary+1}/preservation').glob('attempt-*/admission.json')):
                rt.resume_context(root,config)  # Only the existing typed Editor-timeout recovery is eligible.
                return packet
            pending = pending_review(root)
            if pending:
                validate_review_retry(root, config, pending)
            else:
                rt.guard_operation(root, config, phase='phase_1', round_number=boundary+1)
            return packet
        if state.get('terminal_state') not in BUDGET_EXTENSION_TERMINAL_STATES:
            require(amount == packet['event']['added_rounds_per_profile'], 'active budget extension amount changed')
            from whetstone.resume import plan_resume_halted_run
            require(plan_resume_halted_run(root,config,continue_run=True).resumable,
                    'budget extension is already complete')
            return packet
    require(state.get('phase') == 'phase_1' and state.get('terminal_state') in BUDGET_EXTENSION_TERMINAL_STATES,
            'budget extension requires a completed Phase 1 budget stop')
    ctx = vertical_context(root,config) if config.review_mode == 'vertical' else continuation_context(root,config)
    if config.review_mode == 'vertical':
        require(ctx['terminal'] == 'TARGET_NOT_REACHED', 'vertical budget stop has unfinished work')
        counts = {p:s['rounds_used'] for p,s in ctx['profile_state'].items()}
        budgets = {p:s['round_budget'] for p,s in ctx['profile_state'].items()}
    else:
        require(ctx['scheduler'].next_profile() is None and not ctx['scheduler'].phase_complete(accepted_draft=True),
                'horizontal budget stop has unfinished work or is already stable')
        require(not ctx['closeout_profiles'], 'horizontal budget stop has unfinished closeout verification')
        budgets = ctx['budgets']
        counts = {s.profile:v.rounds_used for s,v in zip(ctx['scheduler'].steps,ctx['scheduler'].states)}
    rt.guard_operation(root, config, phase='phase_1', round_number=state['current_round']+1)
    service = rt.acceptance_service(root)
    new = {p:max(budgets[p],counts[p])+amount for p in budgets}
    event = {'event_id':_budget_extension_event_id(previous_state=state, original_budgets=budgets,
        extended_budgets=new, extension_rounds=amount, reason=REASON, extension_ordinal=len(packets)+1),
        'generated_at':datetime.now(timezone.utc).isoformat(), 'phase':'phase_1',
        'previous_terminal_state':state['terminal_state'], 'previous_current_round':state['current_round'],
        'previous_review_profile_budgets':budgets, 'new_review_profile_budgets':new,
        'added_rounds_per_profile':amount, 'reason':REASON}
    packet = {'version':'bridge-budget-grant-v1','event':event,'state_before':state,
        'accepted':service._chain()[-1][0], 'config':rt._jsonable(asdict(config)),
        'reviews':[service.reference(str(p.relative_to(root))) for p in sorted(root.glob('rounds/round-*/preservation/review_complete.json'))]}
    if write:
        service._write(f'{PREFIX}/grant-{len(packets)+1}.json',json_bytes(packet))
        mirror(root,packet,packets+[packet])
    return packet


def plan(root, config, *, extend_review_budget):
    from whetstone.resume import ResumePlan, plan_resume_halted_run
    packet = prepare(root,config,extend_review_budget)
    state = packet['state_before']
    from whetstone.preservation_runtime import state_packet
    if state_packet(root)['current_round'] > state['current_round']:
        return plan_resume_halted_run(root,config,continue_run=True)
    return ResumePlan(True,state['terminal_state'],'budget_exhausted','phase_1','orchestrator',state['current_round'],
        '',state['current_draft_hash'],state['current_draft_hash'],1,True,state['current_round']+1,
        'Append rounds under the verified explicit budget grant')


def resume(root, config, *, extend_review_budget, **clients):
    from whetstone.resume import resume_halted_run
    prepare(root,config,extend_review_budget,write=True)
    return resume_halted_run(root,config,continue_run=True,**clients)
