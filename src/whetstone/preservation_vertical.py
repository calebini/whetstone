"""Vertical preservation bindings, schedule reconstruction and recovery."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from whetstone.hashing import draft_hash
from whetstone.preservation_contracts import decode_json, read_ref, require, validate_surface_bindings
from whetstone.scheduler import profile_names_for_phase


def merge_feedback(packets, number, base_hash):
    from whetstone.live_phase1 import _vertical_merged_feedback_id
    counts, findings = {}, []
    for packet in packets:
        for finding in packet['feedback']:
            fid = _vertical_merged_feedback_id(packet['profile'], finding['feedback_id'], counts)
            findings.append({**finding, 'feedback_id': fid})
    return {'round_number': number, 'profile': 'vertical', 'draft_hash': base_hash,
            'reviewer': {'name': 'whetstone-vertical-merge', 'version': '1.0', 'model': 'orchestrator'}, 'feedback': findings}


def ordinary_feedback(admission, feedback):
    """Check and use the deterministic merge once, without double-counting sources."""
    if admission['profile'] != 'vertical' or len(feedback) == 1:
        return feedback
    merged, *sources = feedback
    require(bool(sources) and [p['round_number'] for p in sources] == list(range(admission['round_number']-len(sources), admission['round_number'])),
            'vertical source round topology differs')
    require(all(p['draft_hash'] == merged['draft_hash'] for p in sources), 'vertical source base differs')
    require(merged == merge_feedback(sources, admission['round_number'], merged['draft_hash']), 'vertical merged feedback differs from sources')
    return [merged]


def verify_sources(root, frozen, number, feedback_refs):
    """Bind every original review to its receipt, settings, base and merge."""
    from whetstone.preservation_continuation import verify_review_receipt
    root = Path(root)
    refs = frozen.get('vertical_review_sources')
    require(isinstance(refs, list), 'missing vertical source-review topology')
    resolved = frozen['resolved_config']
    require(frozen.get('phase') == 'phase_1' and frozen.get('profile') == 'vertical' and resolved['review_mode'] == 'vertical',
            'invalid consolidated operation identity')
    profiles = profile_names_for_phase(resolved['review_profile_set'], 'phase_1')
    require(refs and len(refs) <= len(profiles) and len(feedback_refs) == len(refs)+1, 'incomplete vertical source topology')
    start = number-len(refs)
    counts = {p:0 for p in profiles}
    for earlier in range(1,start):
        if (root/f'rounds/round-{earlier}/preservation/review_complete.json').exists():
            earlier_packet, _, _, _, _ = verify_review_receipt(root, earlier)
            require(earlier_packet['kind'] == 'vertical_source', 'consolidation cannot follow closeout')
            counts[earlier_packet['profile']] += 1
    from whetstone.scheduler import resolved_phase_1_profile_budgets
    budgets = resolved_phase_1_profile_budgets(resolved['review_profile_budgets'],profile_set=resolved['review_profile_set'])
    profiles = [p for p in profiles if counts[p] < budgets[p]]
    require(len(refs) == len(profiles), 'vertical source sweep omitted a profile')
    packets = []
    for index, (profile, ref) in enumerate(zip(profiles, refs), 1):
        source_number = start+index-1
        read_ref(root, ref)
        require(ref['path'] == f'rounds/round-{source_number}/preservation/review_complete.json', 'vertical source receipt path mismatch')
        packet, config, feedback, _, _ = verify_review_receipt(root, source_number)
        require(packet['kind'] == 'vertical_source' and packet['profile'] == profile,
                'vertical source identity differs')
        if start == 1:
            require(packet['accepted'] is None, 'initial vertical source has an accepted parent')
        else:
            from whetstone.preservation_contracts import read_artifact
            marker = read_artifact(root,packet['accepted'],'preservation_bridge_acceptance')
            proposal = read_artifact(root,marker['proposal'],'preservation_bridge_proposal')
            admission = read_artifact(root,proposal['admission'],'preservation_bridge_proposal_admission')
            require(admission['round_number'] == start-1, 'vertical cycle source parent is not the preceding consolidation')
        original = deepcopy(config['resolved_config'])
        current = deepcopy(resolved)
        original['preservation_bridge'].pop('predecessor_report', None)
        current['preservation_bridge'].pop('predecessor_report', None)
        require(original == current and config['scope_contract_packet'] == frozen['scope_contract_packet'],
                'vertical source configuration changed')
        require(decode_json(read_ref(root, feedback_refs[index])) == feedback, 'retained vertical source differs')
        if packets:
            require(packet['accepted'] == parent, 'vertical source lineage changed within cycle')
        parent = packet['accepted']
        packets.append(feedback)
    merged = decode_json(read_ref(root, feedback_refs[0]))
    require(merged == merge_feedback(packets, number, packets[0]['draft_hash']), 'vertical merged feedback differs from source receipts')
    return packets


def source_bindings(root, config, number):
    from whetstone.preservation_runtime import acceptance_service
    from whetstone.preservation_continuation import verify_review_receipt
    service = acceptance_service(root)
    chain = service._chain()
    prior_numbers = [service._proposal_directory(marker['proposal'])[2]['round_number'] for _,marker,_ in chain]
    start = max((n for n in prior_numbers if n < number), default=0)+1
    receipts, feedback = [], []
    for index in range(start, number):
        packet, _, _, _, _ = verify_review_receipt(root, index)
        require(packet['kind'] == 'vertical_source', 'consolidation requires source reviews')
        receipt_ref = service.reference(f'rounds/round-{index}/preservation/review_complete.json')
        receipt = decode_json(read_ref(Path(root), receipt_ref))
        result = decode_json(read_ref(Path(root), receipt['result']))
        receipts.append(receipt_ref); feedback.append(result['feedback'])
    return receipts, feedback


def guard_source(root, config, *, round_number, profile, phase, overwrite, resume):
    from whetstone import preservation_runtime as rt
    root = Path(root)
    require(phase == 'phase_1' and not overwrite, 'vertical source reviews require Phase 1 without overwrite')
    from whetstone.preservation_continuation import pending_review, validate_review_retry
    if resume:
        packet, _, _ = validate_review_retry(root,config,pending_review(root))
        require(packet['round_number'] == round_number and packet['profile'] == profile, 'vertical review retry identity differs')
        return packet['kind']
    ctx = context(root,config,allow_inflight=True)
    require(ctx['next_round'] == round_number and ctx['next_profile'] == profile and
            ctx['next_kind'] in {'vertical_source','vertical_closeout'}, 'vertical source review is out of order')
    if ctx['next_kind'] == 'vertical_source':
        rt.guard_operation(root,config,phase=phase,round_number=round_number)
    require(not (root/f'rounds/round-{round_number}').exists(), 'vertical source round already exists')
    return ctx['next_kind']


def verify_seed_review(root, packet, frozen):
    require(packet['kind'] in {'vertical_source','vertical_closeout'}, 'invalid vertical review kind')
    config = frozen['resolved_config']
    require(config['review_mode'] == 'vertical' and packet['profile'] in profile_names_for_phase(config['review_profile_set'],'phase_1'),
            'vertical review mode/profile differs')
    surface = validate_surface_bindings(Path(root),config['preservation_bridge']['allowed_change_surface'])
    require(frozen['scope_contract_packet'] == decode_json(read_ref(Path(root),surface.surface['scope_contract'])), 'vertical review scope differs')
    if packet['accepted'] is None:
        require(packet['kind'] == 'vertical_source', 'closeout requires accepted authority')
        base = surface.base
    else:
        from whetstone.preservation_contracts import read_artifact
        marker = read_artifact(Path(root),packet['accepted'],'preservation_bridge_acceptance')
        base = read_ref(Path(root),marker['materialized_draft'])
    require(read_ref(Path(root),packet['base']) == base, 'vertical review differs from accepted base')
    if packet['kind'] == 'vertical_source':
        require(surface.base == base, 'vertical source review lacks current-base authorization')


def prepare_consolidated(runner, number, feedback, base):
    """Validate the complete review topology before any consolidated round writes."""
    from whetstone import preservation_runtime as rt
    rt.guard_operation(runner.root, runner.config, phase='phase_1', round_number=number)
    _, source_refs = source_bindings(runner.root, runner.config, number)
    from whetstone.preservation_continuation import verify_review_receipt
    packets = [decode_json(read_ref(runner.root, ref)) for ref in source_refs]
    require(feedback == merge_feedback(packets, number, draft_hash(base)), 'consolidated feedback differs from source reviews')
    directory = runner.store.begin_round(number)
    runner.store.write_round_text(number, 'draft_before.md', base)
    runner.store.write_round_json(number, 'profile_used.yaml', {'profile':'vertical','round_kind':'consolidated_editor'})
    runner.store.write_round_json(number, 'reviewer_feedback.json', feedback)
    return directory


def context(root, config, *, allow_inflight=False):
    """Reconstruct vertical scheduling from receipts and committed acceptances."""
    from whetstone import preservation_runtime as rt
    from whetstone.preservation_continuation import verify_review_receipt
    from whetstone.scheduler import resolved_phase_1_profile_budgets
    from whetstone.live_phase1 import _reviewer_count, _vertical_profile_status, _has_serious_issues
    root = Path(root)
    service = rt.acceptance_service(root)
    service._boundary()
    status = rt.readback(root, config)
    require(status['pending_outcome'] is None, 'pending vertical operation requires its preservation recovery')
    chain = service._chain()
    if chain:
        service._verify_mirrors(chain)
    service.verify_runtime_completion(chain)
    records = {}
    for ref, marker, issues in chain:
        _, proposal, admission = service._proposal_directory(marker['proposal'])
        frozen = decode_json(read_ref(root, proposal['normal_round_evidence']['effective_config']))
        number = admission['round_number']
        records[number] = {'kind':'consolidated_editor', 'profile':'vertical', 'frozen':frozen,
                           'base':read_ref(root, admission['base_draft']), 'after':read_ref(root, marker['materialized_draft']),
                           'accepted':ref, 'issues':issues, 'feedback':decode_json(read_ref(root, proposal['normal_round_evidence']['reviewer_feedback'][0]))}
    for path in root.glob('rounds/round-*/preservation/review_complete.json'):
        number = int(path.parent.parent.name.removeprefix('round-'))
        packet, frozen, feedback, _, issues = verify_review_receipt(root, number)
        require(number not in records, 'competing vertical round completions')
        records[number] = {'kind':packet['kind'],'profile':packet['profile'],'frozen':frozen,
                           'base':read_ref(root, packet['base']),'after':read_ref(root, packet['base']),
                           'accepted':packet['accepted'],'issues':issues,'feedback':feedback}
    require(sorted(records) == list(range(1, len(records)+1)), 'vertical completed rounds are not contiguous')
    original = records[1]['frozen'] if records else rt.config_snapshot(config, phase='phase_1', profile='', state=rt.state_packet(root))
    actual = rt._jsonable(asdict(config)); expected = deepcopy(original['resolved_config'])
    actual.pop('preservation_bridge'); expected.pop('preservation_bridge')
    require(actual == expected and config.review_mode == 'vertical', 'vertical continuation settings changed')
    from whetstone.config import parse_preservation_bridge
    require(config.preservation_bridge is not None, 'guarded vertical run cannot downgrade')
    parse_preservation_bridge(asdict(config.preservation_bridge))
    from whetstone.scope import read_scope_contract
    scope = read_scope_contract(config.scope_contract.path)
    require(scope is not None and scope.packet == original['scope_contract_packet'], 'vertical continuation scope changed')
    for record in records.values():
        settings = deepcopy(record['frozen']['resolved_config']); settings.pop('preservation_bridge')
        require(settings == expected and record['frozen']['scope_contract_packet'] == original['scope_contract_packet'],
                'vertical completed round changed settings or scope')
    budgets = resolved_phase_1_profile_budgets(config.review_profile_budgets, profile_set=config.review_profile_set)
    profiles = list(budgets)
    states = {p:{'profile':p,'clean':False,'rounds_used':0,'round_budget':budgets[p], 'exhausted':False,
                 'residual_status':None,'active':False,'verified_draft_hash':None} for p in profiles}
    base = records[1]['base'] if records else (root/'spec.md').read_bytes()
    seed = base
    number, accepted, issues = 0, None, []
    closeout_issues = []

    def consume(kind, profile):
        nonlocal number
        number += 1
        if number not in records:
            return None
        record = records[number]
        require(record['kind'] == kind and record['profile'] == profile and record['base'] == base,
                'vertical round differs from reconstructed schedule/base')
        if kind != 'consolidated_editor':
            require(record['accepted'] == accepted, 'vertical review accepted parent changed')
            state = states[profile]
            clean = not any(_reviewer_count(record['feedback'], severity) for severity in ('blocker','major'))
            state.update(rounds_used=state['rounds_used']+1, clean=clean, verified_draft_hash=draft_hash(base.decode()))
            state['exhausted'] = not clean and (kind == 'vertical_closeout' or state['rounds_used'] >= state['round_budget'])
            state['residual_status'] = 'exhausted_with_residuals' if state['exhausted'] else None
        return record

    def finish(next_kind=None, profile='', terminal=None):
        require(not terminal or number == len(records), 'completed vertical run has unexpected later evidence')
        state = rt.state_packet(root)
        completed = len(records)
        require(state.get('phase','phase_1') == 'phase_1' and state.get('current_round',0) in
                ({completed,completed+1} if allow_inflight else {completed}), 'unfinished or mismatched vertical round')
        require((root/'spec.md').read_bytes() == base, 'vertical current authority differs from completed evidence')
        require(state.get('current_draft_hash',draft_hash(base.decode())) == draft_hash(base.decode()), 'vertical current hash differs')
        before = original['runtime']['state_before']
        for key in ('review_profile_budgets','review_round_budget','run_mode'):
            if key in before:
                require(state.get(key) == before[key], 'vertical scheduler budget/mode mirror changed')
        return {'records':records,'completed':completed,'seed':seed,'next_kind':next_kind,'next_profile':profile,
                'next_round':completed+1 if next_kind else None,'terminal':terminal,'profile_state':states,
                'accepted':accepted,'current_hash':draft_hash(base.decode()),'issues':issues+closeout_issues}

    for cycle in range(max(budgets.values())):
        packets, source_numbers = [], []
        for profile in profiles:
            if states[profile]['rounds_used'] >= budgets[profile]:
                continue
            record = consume('vertical_source', profile)
            if record is None:
                return finish('vertical_source',profile)
            packets.append(record['feedback']); source_numbers.append(number)
        if not packets:
            break
        record = consume('consolidated_editor','vertical')
        if record is None:
            return finish('consolidated_editor','vertical')
        require(record['feedback'] == merge_feedback(packets, number, draft_hash(base.decode())), 'vertical cycle merge differs')
        receipt_paths = [ref['path'] for ref in record['frozen']['vertical_review_sources']]
        require(receipt_paths == [f'rounds/round-{n}/preservation/review_complete.json' for n in source_numbers], 'vertical cycle source selection differs')
        base, accepted, issues = record['after'], record['accepted'], record['issues']
        if not record['feedback']['feedback'] and not _vertical_profile_status(states,current_draft_hash=draft_hash(base.decode()))['unverified_profiles'] and not _has_serious_issues(issues):
            return finish(terminal='PHASE_1_STABLE')
    if accepted and _vertical_profile_status(states,current_draft_hash=draft_hash(base.decode()))['unverified_profiles'] and not _has_serious_issues(issues):
        for profile in profiles:
            record = consume('vertical_closeout',profile)
            if record is None:
                return finish('vertical_closeout',profile)
            closeout_issues.extend(record['issues'])
        stable = not _vertical_profile_status(states,current_draft_hash=draft_hash(base.decode()))['unverified_profiles'] and not _has_serious_issues(closeout_issues)
        return finish(terminal='PHASE_1_STABLE' if stable else 'TARGET_NOT_REACHED')
    return finish(terminal='TARGET_NOT_REACHED')


def plan(root, config, *, preflight=True):
    from whetstone import preservation_runtime as rt
    from whetstone.resume import ResumePlan
    ctx = context(root, config)
    if preflight and ctx['next_kind'] in {'vertical_source','consolidated_editor'}:
        rt.guard_operation(Path(root),config,phase='phase_1',round_number=ctx['next_round'])
    terminal = rt.state_packet(root).get('terminal_state')
    needed = bool(ctx['next_kind']) or terminal != ctx['terminal']
    return ResumePlan(needed, terminal or '', 'vertical_continuation', 'phase_1', 'orchestrator',ctx['completed'],
                      ctx['next_profile'],ctx['current_hash'],ctx['current_hash'],0,True,ctx['next_round'],
                      'Continue the verified vertical schedule without repeating completed operations')


def continue_run(root, config, **clients):
    from whetstone.live_phase1 import LivePhase1Runner
    from whetstone.resume import ResumeResult
    planned = plan(root, config)
    if not planned.resumable:
        return ResumeResult(False,planned.terminal_state,planned.round_number,'phase_1','',planned.current_draft_hash,
                            planned.current_draft_hash,planned.terminal_state == 'PHASE_1_STABLE')
    result = LivePhase1Runner(root,config,**clients).run(continuation=True)
    return ResumeResult(True,result.terminal_state,result.round_number,'phase_1','',result.current_draft_hash,
                        result.last_accepted_draft_hash,result.ready_for_phase_2)


def replay_result(root, number, profile, kind, records):
    from whetstone.live import LiveRoundResult
    record = records.get(number)
    if record is None:
        return None
    require(record['kind'] == kind and record['profile'] == profile, 'vertical replay operation mismatch')
    return LiveRoundResult(number,Path(root)/f'rounds/round-{number}',draft_hash(record['base'].decode()),
                           draft_hash(record['after'].decode()),kind == 'consolidated_editor',
                           len(record['feedback']['feedback']),record['base'] != record['after'])
