"""Guarded Phase 1 review records and reconstruction for the existing scheduler.

Review records prove observation of an accepted draft; they never promote bytes.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import re
import json

from whetstone.contracts import validate_artifact
from whetstone.hashing import draft_hash
from whetstone.preservation_contracts import decode_json, read_ref, require
from whetstone.preservation_proposals import json_bytes


def _runtime():
    from whetstone import preservation_runtime
    return preservation_runtime


def _attempts(root):
    result = []
    for path in Path(root).glob('rounds/round-*/preservation/reviewer-attempt-*'):
        match = re.fullmatch(r'rounds/round-([1-9][0-9]*)/preservation/reviewer-attempt-([1-9][0-9]*)', str(path.relative_to(root)))
        if match:
            result.append((int(match[1]), int(match[2]), path))
    return sorted(result)


def read_review(root, directory):
    """Validate an immutable review execution and every retained input."""
    root, directory = Path(root), Path(directory)
    rt = _runtime()
    service = rt.acceptance_service(root)
    input_ref = service.reference(str((directory/'input.json').relative_to(root)))
    packet = decode_json(read_ref(root, input_ref))
    require(isinstance(packet, dict) and set(packet) == {'version','round_number','phase','profile','kind','accepted','context',
            'supplied','attempt','predecessor','base','prompt','config'}, 'invalid review input shape')
    require(type(packet['round_number']) is int and packet['round_number'] > 0 and type(packet['attempt']) is int and packet['attempt'] > 0,
            'invalid review counters')
    require(packet['kind'] in {'review_editor','review_only','vertical_source','vertical_closeout'} and packet['phase'] in {'phase_1','phase_2'}, 'invalid review operation')
    require(packet['version'] == 'bridge-review-v1', 'unsupported review record')
    require(directory == Path(root)/f"rounds/round-{packet['round_number']}/preservation/reviewer-attempt-{packet['attempt']}", 'review identity/path mismatch')
    for key in ('base', 'config', 'prompt'):
        read_ref(root, packet[key])
    require(isinstance(packet['context'], list), 'invalid review context')
    if packet['accepted'] is not None:
        read_ref(root, packet['accepted'])
    for ref in packet['context']:
        read_ref(root, ref)
    if packet['supplied']:
        read_ref(root, packet['supplied'])
    frozen = decode_json(read_ref(root, packet['config']))
    require(isinstance(frozen, dict) and {'phase','profile','resolved_config','runtime','scope_contract_packet','reviewer_timeout_seconds'} <= set(frozen),
            'incomplete frozen review configuration')
    require(frozen['phase'] == packet['phase'] and frozen['profile'] == packet['profile'], 'review configuration binding mismatch')
    require(isinstance(frozen['runtime'], dict) and isinstance(frozen['runtime'].get('state_before'), dict)
            and isinstance(frozen['resolved_config'], dict) and isinstance(frozen['resolved_config'].get('decision_points'), dict),
            'invalid frozen review runtime')
    if packet['attempt'] == 1:
        require(packet['predecessor'] is None, 'initial review cannot have a predecessor')
    else:
        prior_dir = directory.parent/f"reviewer-attempt-{packet['attempt']-1}"
        require(packet['predecessor'] == service.reference(str((prior_dir/'result.json').relative_to(root))), 'review retry predecessor mismatch')
        prior, prior_config, prior_result = read_review(root, prior_dir)
        require(prior_result is not None and prior_result['outcome'] == 'client_timeout', 'only a typed timeout permits another review attempt')
        require(prior_config == frozen and all(prior[key] == packet[key] for key in
                ('round_number','phase','profile','kind','accepted','context','supplied')), 'review retry bindings changed')
        require(all(read_ref(root, prior[key]) == read_ref(root, packet[key]) for key in ('base','prompt')), 'review retry input changed')
    result = None
    if (directory/'result.json').exists():
        result = decode_json((directory/'result.json').read_bytes())
        require(isinstance(result, dict) and set(result) == {'input','outcome','feedback','error'}, 'invalid review result shape')
        require(result['input'] == input_ref, 'review result input hash mismatch')
        require(result['outcome'] in {'complete', 'client_timeout', 'invalid_artifact', 'client_error'}, 'unknown review outcome')
        if result['outcome'] == 'complete':
            require(result['error'] is None, 'complete review cannot contain an error')
            require(result['feedback'] == service.reference(str((directory/'feedback.json').relative_to(root))), 'review feedback path mismatch')
            feedback = decode_json(read_ref(root, result['feedback']))
            from whetstone.live import _validate_reviewer_feedback
            _validate_reviewer_feedback(feedback, round_number=packet['round_number'], profile=packet['profile'],
                                       draft_hash_value=draft_hash(read_ref(root, packet['base']).decode()), schema_name='phase2_reviewer_feedback' if packet['phase']=='phase_2' else 'reviewer_feedback')
        else:
            require(result['feedback'] is None and isinstance(result['error'], str), 'invalid failed review result')
    return packet, frozen, result


def pending_review(root, *, accepted_round=0, proposal_round=0):
    attempts = _attempts(root)
    if not attempts:
        return None
    number, _, directory = attempts[-1]
    if number <= accepted_round or number <= proposal_round:
        return None
    if (Path(root)/f'rounds/round-{number}/preservation/review_complete.json').exists():
        verify_review_receipt(root, number)
        return None
    if not (directory/'input.json').exists():
        return {'directory': directory, 'round_number': number, 'outcome': 'incomplete', 'next_action': 'inspect_and_repair'}
    packet, frozen, result = read_review(Path(root), directory)
    outcome = result['outcome'] if result else 'incomplete'
    return {'directory': directory, 'round_number': number, 'input': packet, 'frozen': frozen, 'result': result,
            'outcome': outcome, 'next_action': 'technical_resume' if packet['phase']=='phase_1' and outcome in {'client_timeout', 'complete'} else 'inspect_and_repair'}


def validate_review_retry(root, config, pending, *, closeout=False):
    require(pending and (pending['next_action'] == 'technical_resume' or
            (closeout and pending['outcome'] in {'complete','client_timeout'})), 'review execution is not resumable')
    rt = _runtime()
    packet, frozen, result = read_review(Path(root), pending['directory'])
    require(packet['phase'] == 'phase_1' or (closeout and packet['phase'] == 'phase_2' and packet['kind'] == 'review_only'),
            'generic Phase 2 resume is unsupported')
    if closeout:
        from whetstone.preservation_phase2_closeout import verify_review
        verify_review(root,packet,frozen)
    if packet['kind'] in {'vertical_source','vertical_closeout'}:
        from whetstone.preservation_vertical import verify_seed_review
        verify_seed_review(root,packet,frozen)
    require(rt._jsonable(asdict(config)) == frozen['resolved_config'], 'review retry cannot change frozen settings or authorization')
    require((Path(root)/'spec.md').read_bytes() == read_ref(root, packet['base']), 'review retry base changed')
    rt.verify_frozen_round_state(rt.state_packet(root), frozen['runtime']['state_before'])
    prefix = Path(root)/f"rounds/round-{packet['round_number']}"
    require((prefix/'draft_before.md').read_bytes() == read_ref(root, packet['base']), 'review base mirror changed')
    if result['outcome'] == 'complete':
        feedback = decode_json(read_ref(root, result['feedback']))
        if packet['kind'] in {'review_only','vertical_source','vertical_closeout'}:
            for name, expected in expected_review_files(root, packet, frozen, feedback).items():
                path = prefix/name
                require(not path.exists() or path.read_bytes() == expected, f'conflicting review recovery artifact: {name}')
        elif (prefix/'reviewer_feedback.json').exists():
            require(decode_json((prefix/'reviewer_feedback.json').read_bytes()) == feedback, 'review feedback mirror changed')

    service = rt.acceptance_service(root)
    chain = service._chain()
    require(packet['accepted'] == (chain[-1][0] if chain else None), 'review retry accepted lineage changed')
    if chain:
        service._verify_mirrors(chain)
        service.verify_runtime_completion(chain)
    return packet, frozen, result


def guarded_review(runner, **kwargs):
    """Freeze review inputs and invoke once; cache complete feedback for recovery."""
    rt = _runtime()
    root = runner.root.resolve()
    service = rt.acceptance_service(root)
    number, profile, phase = kwargs['round_number'], kwargs['profile'], kwargs['phase']
    kind = decode_json((root/f'rounds/round-{number}/profile_used.yaml').read_bytes())['round_kind']
    if phase == 'phase_1' and runner.config.review_mode == 'vertical':
        require(kind == 'review_only', 'unsupported vertical Reviewer operation')
        kind = runner._preservation_review_kind
    with service._lock():
        attempts = [item for item in _attempts(root) if item[0] == number]
        previous = None
        if attempts:
            directory = attempts[-1][2]
            pending = pending_review(root)
            require(pending and pending['directory'] == directory, 'review already completed or superseded')
            packet, frozen, result = validate_review_retry(root, runner.config, pending, closeout=phase == 'phase_2' and kind == 'review_only')
            require(packet['kind'] == kind and packet['profile'] == profile, 'review retry operation changed')
            require(frozen['reviewer_timeout_seconds'] == runner._timeout_for_role('reviewer'), 'review retry timeout changed')
            if result['outcome'] == 'complete':
                return decode_json(read_ref(root, result['feedback']))
            previous = service.reference(str((directory/'result.json').relative_to(root)))
            prompt = read_ref(root, packet['prompt']).decode()
            base = read_ref(root, packet['base'])
        else:
            prompt, base = kwargs['prompt'], runner.config.spec_path.read_bytes()
            state = rt.state_packet(root)
            state.update(current_round=number, phase=phase, active_profile=profile, current_draft_hash=draft_hash(base.decode()))
            state.setdefault('last_accepted_draft_hash', None)
            service._replace('rounds/run_state.json', json_bytes(state))
            frozen = rt.config_snapshot(runner.config, phase=phase, profile=profile, state=state)
            frozen['reviewer_timeout_seconds'] = runner._timeout_for_role('reviewer')
            if phase == 'phase_2' and kind == 'review_only':
                from whetstone.preservation_phase2_closeout import PREFIX
                frozen['runtime']['phase2_closeout'] = service.reference(f'{PREFIX}/admission.json')
        attempt = max((item[1] for item in attempts), default=0)+1
        relative = f'rounds/round-{number}/preservation/reviewer-attempt-{attempt}'
        service._mkdir(relative)
        if not attempts:
            chain = service._chain()
            context = []
            for item in kwargs['context_files']:
                path = Path(item.path)
                if not path.is_absolute():
                    path = root/path
                context.append(service.reference(str(path.resolve().relative_to(root))))
            supplied = getattr(runner, '_preservation_supplied', None)
            supplied_ref = service._write(f'{relative}/supplied.md', supplied if isinstance(supplied, bytes) else supplied.encode()) if supplied is not None else None
            packet = {'version': 'bridge-review-v1', 'round_number': number, 'phase': phase, 'profile': profile, 'kind': kind,
                      'accepted': chain[-1][0] if chain else None, 'context': context, 'supplied': supplied_ref}
        packet = {**packet, 'attempt': attempt, 'predecessor': previous,
                  'base': service._write(f'{relative}/base.md', base), 'prompt': service._write(f'{relative}/prompt.txt', prompt.encode()),
                  'config': service._write(f'{relative}/config.json', json_bytes(frozen))}
        input_ref = service._write(f'{relative}/input.json', json_bytes(packet))
        result = {'input': input_ref, 'outcome': 'complete', 'feedback': None, 'error': None}
        try:
            feedback = kwargs['call'](prompt)
            kwargs['validate'](feedback)
            # Revalidate exact inputs before accepting any Reviewer observations.
            read_review(root, root/relative)
            require(runner.config.spec_path.read_bytes() == base, 'authoritative bytes changed during review')
            result['feedback'] = service._write(f'{relative}/feedback.json', json_bytes(feedback))
        except TimeoutError as exc:
            result.update(outcome='client_timeout', error=str(exc))
        except ValueError as exc:
            result.update(outcome='invalid_artifact', error=str(exc))
        except Exception as exc:
            result.update(outcome='client_error', error=f'{type(exc).__name__}: {exc}')
        finally:
            runner._write_client_telemetry(round_number=number, phase=phase, profile=profile, client_role='reviewer',
                client_config=runner.config.reviewer, artifact_name='preservation-review', attempt_number=attempt, call=kwargs['call'])
        result_ref = service._write(f'{relative}/result.json', json_bytes(result))
        if result['outcome'] == 'complete':
            return feedback
        terminal = 'HALTED_CLIENT_TIMEOUT' if result['outcome'] == 'client_timeout' else 'HALTED_ARTIFACT_INVALID'
        state = rt.state_packet(root)
        state.update(terminal_state=terminal, ready_for_phase_2=False, resumable=phase == 'phase_1' and terminal == 'HALTED_CLIENT_TIMEOUT')
        service._replace('rounds/run_state.json', json_bytes(state))
        service._replace('rounds/artifact_validation_error.json', json_bytes({
            'terminal_state': terminal, 'round_number': number, 'phase': phase, 'profile': profile, 'client_role': 'reviewer',
            'failure_type': result['outcome'], 'last_valid_draft_hash': draft_hash(base.decode()),
            'last_valid_draft_path': './spec.md', 'review_result': result_ref, 'automatic_retries': 0}))
        raise rt.BridgeHalt(terminal, result_ref)


REVIEW_ARTIFACTS = ('draft_before.md', 'draft_after.md', 'reviewer_feedback.json', 'editor_summary.json',
                    'unresolved_issues.json', 'decision_points.json', 'profile_used.yaml', 'closeout_summary.json')


def finish_review_only(runner, number):
    rt = _runtime()
    service = rt.acceptance_service(runner.root)
    with service._lock():
        directory = [item[2] for item in _attempts(runner.root) if item[0] == number][-1]
        packet, _, result = read_review(runner.root, directory)
        require(packet['kind'] in {'review_only','vertical_source','vertical_closeout'} and result['outcome'] == 'complete', 'missing completed review')
        chain = service._chain()
        if packet['kind'] in {'vertical_source','vertical_closeout'}:
            require(packet['accepted'] == (chain[-1][0] if chain else None), 'vertical review lineage changed')
        else:
            require(chain and packet['accepted'] == chain[-1][0], 'review-only lineage changed')
        if chain:
            service._verify_mirrors(chain)
        service.verify_runtime_completion(chain)
        require(runner.config.spec_path.read_bytes() == read_ref(runner.root, packet['base']), 'review-only base changed')
        prefix = f'rounds/round-{number}'
        receipt = {'version': 'bridge-review-complete-v1', 'result': service.reference(str((directory/'result.json').relative_to(runner.root))),
                   'files': {name: service.reference(f'{prefix}/{name}') for name in REVIEW_ARTIFACTS}}
        verify_review_receipt(runner.root, number, receipt=receipt)
        service._write(f'{prefix}/preservation/review_complete.json', json_bytes(receipt))
        verify_review_receipt(runner.root, number)


def verify_review_receipt(root, number, *, receipt=None):
    root = Path(root)
    if receipt is None:
        receipt = decode_json((root/f'rounds/round-{number}/preservation/review_complete.json').read_bytes())
    require(isinstance(receipt, dict) and set(receipt) == {'version','result','files'} and isinstance(receipt['files'], dict), 'invalid review completion shape')
    require(receipt['version'] == 'bridge-review-complete-v1' and set(receipt['files']) == set(REVIEW_ARTIFACTS), 'invalid review completion')
    result = decode_json(read_ref(root, receipt['result']))
    require(isinstance(result, dict) and set(result) == {'input','outcome','feedback','error'}, 'invalid review result shape')
    packet, frozen, expected = read_review(root, root/Path(receipt['result']['path']).parent)
    require(result == expected and result['outcome'] == 'complete' and packet['kind'] in {'review_only','vertical_source','vertical_closeout'}, 'invalid completed review')
    require(packet['round_number'] == number, 'review completion round mismatch')
    if packet['phase'] == 'phase_2':
        from whetstone.preservation_phase2_closeout import verify_review
        verify_review(root,packet,frozen)
    if packet['kind'] in {'vertical_source','vertical_closeout'}:
        from whetstone.preservation_vertical import verify_seed_review
        verify_seed_review(root, packet, frozen)
    for name, ref in receipt['files'].items():
        read_ref(root, ref)
        require(ref['path'] == f'rounds/round-{number}/{name}', 'review completion mirror path mismatch')
    files = {name: read_ref(root, ref) for name, ref in receipt['files'].items()}
    require(files['draft_before.md'] == files['draft_after.md'] == read_ref(root, packet['base']), 'review-only output changed authority')
    feedback = decode_json(read_ref(root, result['feedback']))
    require(decode_json(files['reviewer_feedback.json']) == feedback, 'review feedback mirror changed')
    from whetstone.live import _no_op_editor_summary
    from whetstone.runner import _unresolved_issues
    summary = _no_op_editor_summary(round_number=number, draft_hash_value=draft_hash(files['draft_before.md'].decode()), draft_after_content=files['draft_before.md'].decode())
    require(decode_json(files['editor_summary.json']) == summary, 'review-only summary claims an edit')
    unresolved = decode_json(files['unresolved_issues.json'])
    validate_artifact(unresolved, 'unresolved_issues')
    require(unresolved['unresolved_issues'] == _unresolved_issues(feedback, summary), 'review-only residuals changed')
    require(decode_json(files['profile_used.yaml']) == {'profile': packet['profile'], 'round_kind': 'review_only'}, 'review profile changed')
    require(files == expected_review_files(root, packet, frozen, feedback), 'review completion differs from deterministic output')
    return packet, frozen, feedback, summary, unresolved['unresolved_issues']


def expected_review_files(root, packet, frozen, feedback):
    from whetstone.live import _no_op_editor_summary
    from whetstone.runner import _unresolved_issues
    from whetstone.decisions import detect_decision_points
    from whetstone.config import DecisionPointConfig
    base = read_ref(Path(root), packet['base'])
    number, profile = packet['round_number'], packet['profile']
    hashed = draft_hash(base.decode())
    summary = _no_op_editor_summary(round_number=number, draft_hash_value=hashed, draft_after_content=base.decode())
    decisions = detect_decision_points(draft_before=base.decode(), draft_after=base.decode(), round_number=number, profile=profile,
        reviewer_feedback=feedback, editor_summary=summary, config=DecisionPointConfig(**frozen['resolved_config']['decision_points']),
        scope_contract=frozen['scope_contract_packet'])
    packets = {
        'reviewer_feedback.json': feedback, 'editor_summary.json': summary,
        'unresolved_issues.json': {'round_number':number,'draft_hash':hashed,'unresolved_issues':_unresolved_issues(feedback, summary)},
        'decision_points.json': decisions, 'profile_used.yaml': {'profile':profile,'round_kind':'review_only'},
        'closeout_summary.json': {'round_number':number,'phase':packet['phase'],'profile':profile,'round_kind':'review_only',
            'editor_invoked':False,'draft_before_hash':hashed,'draft_after_hash':hashed,
            'note':'Reviewer-only closeout; editor_summary.json is a compatibility no-op and no Editor client was invoked.'}}
    return {'draft_before.md':base, 'draft_after.md':base,
            **{name:(json.dumps(value, indent=2, sort_keys=True)+'\n').encode() for name,value in packets.items()}}


def continuation_context(root, config, *, allow_inflight=False):
    """Reconstruct only completed, proven rounds; do not trust mutable profile flags."""
    rt = _runtime()
    root = Path(root)
    require(config.review_mode == 'horizontal', 'vertical scheduler continuation is not yet qualified')
    rt.guard_consumer(root, config)
    from whetstone.config import parse_preservation_bridge
    require(config.preservation_bridge is not None, 'guarded continuation cannot downgrade')
    parse_preservation_bridge(asdict(config.preservation_bridge))
    service = rt.acceptance_service(root)
    chain = service._chain()
    records = {}
    for ref, marker, issues in chain:
        _, proposal, original = service._proposal_directory(marker['proposal'])
        frozen = decode_json(read_ref(root, proposal['normal_round_evidence']['effective_config']))
        feedback = decode_json(read_ref(root, proposal['normal_round_evidence']['reviewer_feedback'][0]))
        summary = decode_json(read_ref(root, proposal['normal_round_evidence']['editor_summary']))
        number = original['round_number']
        records[number] = {'kind': 'review_editor', 'profile': original['profile'], 'frozen': frozen, 'feedback': feedback,
                           'summary': summary, 'issues': issues, 'mutated': not marker['accepted_noop'],
                           'base': read_ref(root, original['base_draft']), 'after': read_ref(root, marker['materialized_draft']), 'accepted': ref}
    for path in root.glob('rounds/round-*/preservation/review_complete.json'):
        number = int(path.parent.parent.name.removeprefix('round-'))
        packet, frozen, feedback, summary, issues = verify_review_receipt(root, number)
        require(number not in records, 'round has competing completion records')
        records[number] = {'kind': 'review_only', 'profile': packet['profile'], 'frozen': frozen, 'feedback': feedback,
                           'summary': summary, 'issues': issues, 'mutated': False, 'base': read_ref(root, packet['base']),
                           'after': read_ref(root, packet['base']), 'accepted': packet['accepted']}
    require(records and sorted(records) == list(range(1, max(records)+1)), 'completed rounds are not contiguous')
    first = records[1]['frozen']
    actual = rt._jsonable(asdict(config))
    expected = deepcopy(first['resolved_config'])
    actual.pop('preservation_bridge'); expected.pop('preservation_bridge')
    require(actual == expected, 'continuation cannot change frozen scheduler settings')
    from whetstone.scope import read_scope_contract
    scope = read_scope_contract(config.scope_contract.path)
    require(scope is not None and scope.packet == first['scope_contract_packet'], 'continuation scope differs from frozen approval')
    from whetstone.scheduler import PhaseScheduler, ProfileStep, default_phase_1_scheduler, focused_phase_1_scheduler
    seed_state = first['runtime']['state_before']
    mode = seed_state.get('run_mode', 'phase_1')
    budgets = seed_state.get('review_profile_budgets') or first['effective_run_config']['review_profile_budgets']
    if seed_state.get('scheduler_steps'):
        scheduler = PhaseScheduler(ProfileStep(**{**step, 'focus': frozenset(step['focus'])}) for step in seed_state['scheduler_steps'])
    elif mode == 'focused_phase_1':
        require(len(budgets) == 1, 'invalid focused scheduler')
        profile, budget = next(iter(budgets.items()))
        scheduler = focused_phase_1_scheduler(profile, round_budget=budget)
    else:
        scheduler = default_phase_1_scheduler(budgets, profile_set=config.review_profile_set)
    from whetstone.live_phase1 import _mutation_requires_verification, _reviewer_count, _last_reviewer_findings
    from whetstone.resume import _record_horizontal_closeout_result
    seen, prior, accepted = [], None, None
    review_issues, reviewed_profiles = [], []
    from whetstone.preservation_budget import grants, apply_grant, verify_record
    from whetstone.resume import _extend_phase1_scheduler_budgets
    extensions = {p['event']['previous_current_round']:p for p in grants(root)}
    require(all(n <= max(records) for n in extensions), 'budget grant is ahead of completed evidence')

    def extend(number):
        nonlocal budgets, reviewed_profiles
        if number not in extensions:
            return
        require(scheduler.next_profile() is None and not scheduler.phase_complete(accepted_draft=True),
                'budget grant does not follow an exhausted scheduler')
        budgets = apply_grant(extensions[number], budgets=budgets,
            counts={s.profile:v.rounds_used for s,v in zip(scheduler.steps,scheduler.states)},
            number=number,accepted=accepted,base_hash=draft_hash(prior.decode()))
        _extend_phase1_scheduler_budgets(scheduler,budgets)
        reviewed_profiles = []

    for number, record in sorted(records.items()):
        extend(number-1)
        verify_record(root,record['frozen'],number,list(extensions.values()))
        record_config = deepcopy(record['frozen']['resolved_config'])
        record_config.pop('preservation_bridge')
        require(record_config == expected and record['frozen']['scope_contract_packet'] == first['scope_contract_packet'],
                'completed round changed frozen scheduler settings or scope')
        if prior is not None:
            require(record['base'] == prior, 'round lineage base mismatch')
        else:
            seen.append(draft_hash(record['base'].decode()))
        blockers, majors = (_reviewer_count(record['feedback'], severity) for severity in ('blocker', 'major'))
        if record['kind'] == 'review_only':
            require(record['accepted'] == accepted, 'review observes a different accepted marker')
            require(scheduler.next_profile() is None and record['profile'] in scheduler.status()['unverified_profiles']
                    and record['profile'] not in reviewed_profiles, 'duplicate or unsolicited closeout profile')
            reviewed_profiles.append(record['profile'])
            _record_horizontal_closeout_result(scheduler, record['profile'], clean=blockers == majors == 0)
            review_issues.extend(record['issues'])
        else:
            require(scheduler.next_profile() == record['profile'], 'accepted round differs from frozen scheduler')
            verification = blockers == majors == 0 and _mutation_requires_verification(
                round_dir=root/f'rounds/round-{number}', editor_summary=record['summary'], spec_mutated=record['mutated'])
            scheduler.record_result(record['profile'], blocker_count=blockers, major_count=majors + int(verification))
            if record['mutated']:
                # Every clean observation is bound to the bytes it reviewed.
                for profile_state in scheduler.states:
                    profile_state.clean = False
            if draft_hash(record['after'].decode()) in seen and (blockers or majors):
                require(config.review_budget_exhaustion_policy == 'soft', 'accepted lineage contains an oscillation; automatic continuation is blocked')
                if scheduler.active_profile() == record['profile']:
                    scheduler.force_advance_current(residual_status='halted_oscillation')
            accepted = record['accepted']
            review_issues = []
        prior = record['after']; seen.append(draft_hash(prior.decode()))
        last_findings = _last_reviewer_findings(round_number=number, profile=record['profile'], reviewer_feedback=record['feedback'], blocker_count=blockers, major_count=majors)
    extend(max(records))
    state = rt.state_packet(root)
    allowed_rounds = {max(records), max(records)+1} if allow_inflight else {max(records)}
    require(state.get('phase') == 'phase_1' and state.get('current_round') in allowed_rounds, 'unfinished or mismatched scheduler round')
    require(state.get('current_draft_hash') == seen[-1], 'scheduler current hash differs')
    require((root/'spec.md').read_bytes() == prior, 'current authority differs from completed round')
    require(state.get('run_mode', mode) == mode, 'scheduler mode mirror changed')
    if state.get('review_round_budget') is not None:
        require(state['review_round_budget'] == sum(budgets.values()), 'scheduler budget total changed')
    if seed_state.get('scheduler_steps') is not None:
        require(state.get('scheduler_steps') == [{**asdict(s), 'focus':sorted(s.focus)} for s in scheduler.steps], 'scheduler recipe mirror changed')
    if state.get('review_profile_budgets') is not None:
        require(state['review_profile_budgets'] == budgets, 'scheduler budget mirror changed')
    from whetstone.live_phase1 import _has_serious_issues
    closeout_profiles = [profile for profile in scheduler.status()['unverified_profiles'] if profile not in reviewed_profiles]
    if not reviewed_profiles and _has_serious_issues(chain[-1][2]):
        closeout_profiles = []
    return {'closeout_profiles': closeout_profiles, 'reviewed_profiles': reviewed_profiles, 'review_issues': review_issues,
            'scheduler': scheduler, 'round_number': max(records), 'seen_hashes': seen,
            'last_accepted_draft_hash': chain[-1][1]['materialized_draft_hash'], 'last_unresolved': chain[-1][2] + review_issues,
            'last_reviewer_findings': last_findings, 'run_mode': mode, 'budgets': budgets,
            'terminal': 'FOCUSED_PROFILE_STABLE' if mode == 'focused_phase_1' else 'PHASE_1_STABLE',
            'ready': mode != 'focused_phase_1'}


def begin_review_only(root, config, *, round_number, profile, phase, overwrite, resume):
    rt = _runtime()
    if phase == 'phase_2':
        from whetstone.preservation_phase2_closeout import begin_review
        return begin_review(root,config,round_number=round_number,profile=profile,overwrite=overwrite,resume=resume)
    if config.review_mode == 'vertical':
        from whetstone.preservation_vertical import guard_source
        return guard_source(root, config, round_number=round_number, profile=profile, phase=phase, overwrite=overwrite, resume=resume)
    require(phase == 'phase_1' and config.review_mode == 'horizontal', 'unsupported guarded review-only phase/mode')
    require(not overwrite, 'guarded review evidence cannot be overwritten')
    if resume:
        validate_review_retry(Path(root), config, pending_review(Path(root)))
        return
    context = continuation_context(root, config, allow_inflight=True)
    require(round_number == context['round_number']+1 and context['scheduler'].next_profile() is None
            and profile in context['closeout_profiles'], 'review-only operation differs from frozen scheduler')
    require(not (Path(root)/f'rounds/round-{round_number}').exists(), 'review round already exists')


def continue_phase1(root, config, *, reviewer_client=None, editor_client=None, timeout_seconds=None):
    rt = _runtime()
    if config.review_mode == 'vertical':
        from whetstone.preservation_vertical import continue_run as continue_vertical
        return continue_vertical(root,config,reviewer_client=reviewer_client,editor_client=editor_client,timeout_seconds=timeout_seconds)
    context = continuation_context(root, config)
    terminal = rt.state_packet(root).get('terminal_state')
    complete = context['scheduler'].phase_complete(accepted_draft=True)
    exhausted = context['scheduler'].next_profile() is None and not context['closeout_profiles']
    if (complete and terminal == context['terminal']) or (exhausted and terminal in {'TARGET_NOT_REACHED','PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS'}):
        from whetstone.resume import ResumeResult
        return ResumeResult(False, terminal, context['round_number'], 'phase_1', '', context['seen_hashes'][-1],
                            context['last_accepted_draft_hash'], complete and context['ready'])
    # A new editing round needs current-base authorization; a verification-only
    # closeout observes the existing accepted bytes and creates no new authority.
    if context['scheduler'].next_profile() is not None:
        rt.guard_operation(Path(root), config, phase='phase_1', round_number=context['round_number']+1)
    from whetstone.live_phase1 import LivePhase1Runner
    from whetstone.resume import ResumeResult
    result = LivePhase1Runner(root, config, reviewer_client=reviewer_client, editor_client=editor_client,
                              timeout_seconds=timeout_seconds).run(continuation=True)
    return ResumeResult(True, result.terminal_state, result.round_number, 'phase_1', '',
                        result.current_draft_hash, result.last_accepted_draft_hash, result.ready_for_phase_2)


def resume_review(root, config, pending, *, continue_run, reviewer_client, editor_client, timeout_seconds):
    rt = _runtime()
    root = Path(root)
    packet, frozen, result = validate_review_retry(root, config, pending)
    from whetstone.live import LiveRoundRunner
    from whetstone.resume import ResumeResult
    runner = LiveRoundRunner(root, config, reviewer_client=reviewer_client, editor_client=editor_client, timeout_seconds=timeout_seconds)
    number, profile = packet['round_number'], packet['profile']
    require(runner._timeout_for_role('reviewer') == frozen['reviewer_timeout_seconds'], 'review retry timeout changed')
    try:
        if packet['kind'] in {'review_only','vertical_source','vertical_closeout'}:
            runner.run_review_only_round(round_number=number, profile=profile, phase='phase_1', reuse_existing_round=True,
                                         start_reviewer_attempt_number=packet['attempt']+1)
            state = rt.state_packet(root)
            state.update(terminal_state=None, ready_for_phase_2=False, resumable=True)
            rt.acceptance_service(root)._replace('rounds/run_state.json', json_bytes(state))
        else:
            supplied = read_ref(root, packet['supplied']) if packet['supplied'] else None
            runner.run_round(round_number=number, profile=profile, phase='phase_1', apply=True, draft_after=supplied,
                             reuse_existing_round=True, start_reviewer_attempt_number=packet['attempt']+1)
    except rt.BridgeHalt as exc:
        state = rt.state_packet(root)
        return ResumeResult(True, exc.terminal_state, number, 'phase_1', profile,
                            state['current_draft_hash'], state.get('last_accepted_draft_hash'), False)
    if continue_run:
        return continue_phase1(root, config, reviewer_client=reviewer_client, editor_client=editor_client, timeout_seconds=timeout_seconds)
    state = rt.state_packet(root)
    return ResumeResult(True, state.get('terminal_state'), number, 'phase_1', profile,
                        state['current_draft_hash'], state.get('last_accepted_draft_hash'), False)


def plan_continuation(root, config, *, continue_run):
    require(_runtime().state_packet(root).get('phase','phase_1') == 'phase_1', 'generic Phase 2 resume is unsupported')
    from whetstone.resume import ResumePlan
    rt = _runtime()
    root = Path(root)
    pending = pending_review(root)
    if pending and not list((root/f"rounds/round-{pending['round_number']}/preservation").glob('attempt-*/admission.json')):
        packet, _, result = validate_review_retry(root, config, pending)
        return ResumePlan(True, rt.state_packet(root).get('terminal_state') or '', result['outcome'], 'phase_1', 'reviewer',
                          packet['round_number'], packet['profile'], draft_hash((root/'spec.md').read_bytes().decode()),
                          draft_hash(read_ref(root, packet['base']).decode()), packet['attempt']+1, continue_run, None,
                          'Resume the frozen Reviewer operation; reuse already complete feedback')
    status = rt.readback(root, config)
    if config.review_mode == 'vertical' and status['pending_outcome'] is None:
        require(continue_run, 'completed review requires --continue for vertical scheduling')
        from whetstone.preservation_vertical import plan
        return plan(root,config)
    if status['pending_outcome'] is not None or status['accepted'] is None:
        return None
    require(continue_run, 'accepted operation is complete; use --continue for ordinary review')
    context = continuation_context(root, config)
    profile = context['scheduler'].next_profile()
    if profile is not None:
        rt.guard_operation(root, config, phase='phase_1', round_number=context['round_number']+1)
    else:
        profile = next(iter(context['closeout_profiles']), '')
    terminal = rt.state_packet(root).get('terminal_state')
    completed_terminals = {context['terminal']} if context['scheduler'].phase_complete(accepted_draft=True) else {'TARGET_NOT_REACHED','PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS'}
    needed = bool(profile) or terminal not in completed_terminals
    return ResumePlan(needed, rt.state_packet(root).get('terminal_state') or '', 'accepted_round_continuation', 'phase_1',
                      'orchestrator', context['round_number'], profile, context['seen_hashes'][-1], context['seen_hashes'][-1],
                      0, True, context['round_number']+1 if profile else None,
                      'Reconstruct the original scheduler from completed evidence and continue without replay')
