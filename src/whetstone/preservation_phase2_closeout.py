"""Bounded Reviewer-only Phase 2 closeout, with its own recovery admission.

This operation cannot invoke an Editor or resume an ordinary Phase 2 round.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from whetstone.hashing import draft_hash
from whetstone.preservation_contracts import decode_json, read_ref, read_artifact, require
from whetstone.preservation_proposals import json_bytes

PREFIX = 'rounds/preservation/phase2-closeout'


def schedule(root, refs, config, *, require_exhausted=True):
    """Replay admitted Phase 2 rounds; flags in run_state are not evidence."""
    from whetstone.scheduler import default_phase_2_scheduler
    from whetstone.live_phase1 import _reviewer_count
    root = Path(root)
    scheduler = default_phase_2_scheduler(config['convergence_profile_budgets'],profile_set=config['review_profile_set'])
    clean, entry, number, base = set(), None, None, None
    rubric_identity = None
    for ref in refs:
        marker = read_artifact(root,ref,'preservation_bridge_acceptance')
        proposal = read_artifact(root,marker['proposal'],'preservation_bridge_proposal')
        admission = read_artifact(root,proposal['admission'],'preservation_bridge_proposal_admission')
        if admission['phase'] != 'phase_2':
            require(entry is None,'Phase 1 acceptance follows Phase 2 entry')
            continue
        frozen = decode_json(read_ref(root,proposal['normal_round_evidence']['effective_config']))
        manifest = frozen.get('rubric_manifest_packet')
        require(isinstance(manifest,dict), 'Phase 2 round lacks frozen rubric identity')
        identity = {key:value for key,value in manifest.items() if key != 'generated_at'}
        require(rubric_identity is None or rubric_identity == identity, 'Phase 2 rubric identity changed between rounds')
        rubric_identity = identity
        expected = deepcopy(config); actual = deepcopy(frozen['resolved_config'])
        expected.pop('preservation_bridge');actual.pop('preservation_bridge')
        require(expected == actual,'closeout cannot change frozen Phase 2 settings')
        if admission['origin'] == 'phase2_entry':
            require(entry is None,'duplicate Phase 2 entry')
            entry = ref
            number = frozen['runtime']['state_before']['current_round']
        else:
            require(entry is not None and admission['round_number'] == number+1
                    and admission['profile'] == scheduler.next_profile(), 'Phase 2 evidence differs from its scheduler')
            require(read_ref(root,admission['base_draft']) == base,'Phase 2 closeout lineage differs')
            feedback = decode_json(read_ref(root,proposal['normal_round_evidence']['reviewer_feedback'][0]))
            blockers, majors = (_reviewer_count(feedback,s) for s in ('blocker','major'))
            changed = not marker['accepted_noop']
            scheduler.record_result(admission['profile'],blocker_count=blockers,major_count=majors+int(changed and not (blockers or majors)))
            if changed:
                clean.clear()
            elif not (blockers or majors):
                clean.add(admission['profile'])
            number += 1
        base = read_ref(root,marker['materialized_draft'])
    require(entry is not None, 'Phase 2 verification requires an accepted entry')
    require(not require_exhausted or scheduler.next_profile() is None,'Phase 2 closeout requires exhausted ordinary scheduling')
    return scheduler, clean, number, base


def admission(root, packet=None):
    root = Path(root)
    if packet is None:
        packet = decode_json((root/PREFIX/'admission.json').read_bytes())
    require(isinstance(packet,dict) and set(packet) == {'version','config','state_before','acceptances','profiles','clean_profiles',
            'start_round','base_hash','scope','failure_report','automatic','residuals','rubric_hash','rubric_manifest'},
            'invalid Phase 2 closeout admission')
    require(packet['version'] == 'bridge-phase2-closeout-v1','unsupported Phase 2 closeout admission')
    require(not any(i.get('normalized_severity') in {'blocker','major'} for i in packet['residuals']),
            'Phase 2 closeout cannot bypass unresolved substantive issues')
    scheduler, clean, number, base = schedule(root,packet['acceptances'],packet['config'])
    profiles = [s.profile for s in scheduler.steps if s.profile not in clean]
    require(packet['profiles'] == list(dict.fromkeys(profiles)) and packet['clean_profiles'] == sorted(clean)
            and packet['start_round'] == number+1 and packet['base_hash'] == draft_hash(base.decode()),
            'Phase 2 closeout selection differs from completed evidence')
    state = packet['state_before']
    require(state['phase'] == 'phase_2' and state['current_round'] == number and state['current_draft_hash'] == packet['base_hash'],
            'Phase 2 closeout boundary differs')
    read_ref(root,packet['scope'])
    read_ref(root,packet['rubric_manifest'])
    require(type(packet['automatic']) is bool,'invalid closeout admission mode')
    if not packet['automatic']:
        report = decode_json(read_ref(root,packet['failure_report']))
        require(state['terminal_state'] == report['terminal_state'] == 'TARGET_NOT_REACHED'
                and report['round_number'] == number and report['draft_hash'] == packet['base_hash']
                and not any(report[k] for k in ('unresolved_blockers','unresolved_major_issues','unresolved_rubric_gaps')),
                'Phase 2 closeout requires a matching budget-stop report without substantive debt')
    else:
        require(state['terminal_state'] is None and not scheduler.status()['exhausted_profiles'],
                'automatic closeout is not authorized by the exhausted scheduler')
    return packet, scheduler, base


def verify_review(root, packet, frozen):
    admitted, _, base = admission(root)
    ref = frozen['runtime'].get('phase2_closeout')
    require(ref is not None and ref['path'] == f'{PREFIX}/admission.json', 'review is missing its closeout admission')
    read_ref(Path(root),ref)
    index = packet['round_number']-admitted['start_round']
    require(packet['phase'] == 'phase_2' and packet['kind'] == 'review_only'
            and 0 <= index < len(admitted['profiles']) and packet['profile'] == admitted['profiles'][index],
            'review is outside the bounded Phase 2 closeout')
    require(packet['accepted'] == admitted['acceptances'][-1] and read_ref(Path(root),packet['base']) == base
            and frozen['resolved_config'] == admitted['config'], 'Phase 2 closeout review binding changed')
    require(frozen['scope_contract_packet'] == decode_json(read_ref(Path(root),admitted['scope'])), 'closeout scope changed')


def inspect(root, config):
    """Validate a bounded retry without exposing generic Phase 2 resume."""
    from whetstone import preservation_runtime as rt
    from whetstone.preservation_continuation import verify_review_receipt, pending_review
    root = Path(root)
    packet, scheduler, base = admission(root)
    require(rt._jsonable(asdict(config)) == packet['config'],'Phase 2 closeout settings changed')
    require(config.scope_contract.path.read_bytes() == read_ref(root,packet['scope']), 'Phase 2 closeout scope changed')
    from whetstone.rubrics import read_rubric_text
    rubric = read_rubric_text(config)
    require(packet['rubric_hash'] == (draft_hash(rubric) if rubric is not None else None),'Phase 2 closeout rubric changed')
    service = rt.acceptance_service(root);chain = service._chain()
    require([r for r,_,_ in chain] == packet['acceptances'],'Phase 2 closeout accepted lineage changed')
    require(chain[-1][2] == packet['residuals'],'Phase 2 closeout residuals changed')
    service._verify_mirrors(chain);service.verify_runtime_completion(chain)
    require((root/'spec.md').read_bytes() == base,'Phase 2 closeout current authority changed')
    completed, serious = packet['start_round']-1, False
    for index, profile in enumerate(packet['profiles']):
        number = packet['start_round']+index
        if not (root/f'rounds/round-{number}/preservation/review_complete.json').exists():
            break
        require(not serious,'Phase 2 closeout continued after a serious finding')
        review, frozen, _, _, issues = verify_review_receipt(root,number)
        verify_review(root,review,frozen)
        serious = any(i.get('normalized_severity') in {'blocker','major'} for i in issues)
        completed = number
    later = [int(p.name.removeprefix('round-')) for p in (root/'rounds').glob('round-*') if p.name.removeprefix('round-').isdigit()]
    require(not later or max(later) <= completed+(not serious), 'unexpected work beyond bounded Phase 2 closeout')
    state = rt.state_packet(root)
    require(state.get('phase') == 'phase_2' and state.get('current_round') in ({completed} if serious else {completed,completed+1})
            and state.get('current_draft_hash') == packet['base_hash'], 'Phase 2 closeout state differs')
    before = packet['state_before']
    require(state.get('phase_2_rounds_completed') == state['current_round']-before['phase_1_rounds_completed'],
            'Phase 2 closeout round accounting changed')
    if state.get('terminal_state') == 'CONVERGED':
        require(not serious and completed == packet['start_round']+len(packet['profiles'])-1,
                'Phase 2 convergence is not proven by the bounded reviews')
    for key in ('review_profile_budgets','convergence_profile_budgets','review_round_budget','convergence_round_budget',
                'budget_extensions','effective_run_config','phase_1_rounds_completed','run_mode'):
        require(state.get(key) == before.get(key), 'Phase 2 closeout scheduler settings changed')
    pending = pending_review(root,accepted_round=packet['start_round']-1)
    if pending:
        require(not serious and pending['round_number'] == completed+1,'closeout retry is outside the admitted boundary')
        from whetstone.preservation_continuation import validate_review_retry
        validate_review_retry(root,config,pending,closeout=True)
    return packet, scheduler, completed, pending


def begin_review(root, config, *, round_number, profile, overwrite, resume):
    require(not overwrite,'guarded closeout evidence cannot be overwritten')
    packet, _, completed, pending = inspect(root,config)
    index = round_number-packet['start_round']
    require(round_number == completed+1 and 0 <= index < len(packet['profiles']) and profile == packet['profiles'][index],
            'Phase 2 closeout review is out of order')
    require(bool(pending) == bool(resume),'Phase 2 closeout retry must preserve its existing attempt')
    if not resume:
        require(not (Path(root)/f'rounds/round-{round_number}').exists(),'Phase 2 closeout round already exists')


def review_round(runner, number, profile):
    from whetstone.live import LiveRoundRunner, LiveRoundResult
    from whetstone.preservation_continuation import verify_review_receipt, pending_review
    path = Path(runner.root)/f'rounds/round-{number}'
    if (path/'preservation/review_complete.json').exists():
        packet, _, feedback, _, _ = verify_review_receipt(runner.root,number)
        hashed = draft_hash(read_ref(Path(runner.root),packet['base']).decode())
        return LiveRoundResult(number,path,hashed,hashed,not feedback['feedback'],len(feedback['feedback']),False)
    pending = pending_review(runner.root,accepted_round=number-1)
    return LiveRoundRunner(runner.root,runner.config,reviewer_client=runner.reviewer_client,
        editor_client=runner.editor_client,timeout_seconds=runner.timeout_seconds).run_review_only_round(
            round_number=number,profile=profile,phase='phase_2',reuse_existing_round=bool(pending),
            start_reviewer_attempt_number=pending['input']['attempt']+1 if pending else 1)


def prepare(root, config, *, automatic=None):
    from whetstone import preservation_runtime as rt
    from whetstone.live_phase2 import _read_phase2_closeout_handoff
    from whetstone.rubrics import read_rubric_text
    root = Path(root)
    service = rt.acceptance_service(root)
    rt.guard_consumer(root,config)
    state = rt.state_packet(root) if automatic else _read_phase2_closeout_handoff(config.rounds_dir)
    chain = service._chain()
    resolved = rt._jsonable(asdict(config))
    scheduler, clean, number, base = schedule(root,[r for r,_,_ in chain],resolved)
    require(not any(i.get('normalized_severity') in {'blocker','major'} for i in chain[-1][2]),
            'Phase 2 closeout cannot bypass unresolved substantive issues')
    profiles = list(dict.fromkeys(s.profile for s in scheduler.steps if s.profile not in clean))
    require(state['current_round'] == number and (root/'spec.md').read_bytes() == base,'closeout boundary changed')
    report = None
    if not automatic:
        report = service.reference('rounds/convergence_failure_report.json')
    rubric = read_rubric_text(config)
    packet = {'version':'bridge-phase2-closeout-v1','config':resolved,'state_before':state,
        'acceptances':[r for r,_,_ in chain],'profiles':profiles,'clean_profiles':sorted(clean),
        'start_round':number+1,'base_hash':draft_hash(base.decode()),
        'scope':service.reference(str(config.scope_contract.path.relative_to(root))),
        'failure_report':report,'automatic':bool(automatic),'residuals':chain[-1][2],
        'rubric_hash':draft_hash(rubric) if rubric is not None else None,
        'rubric_manifest':service.reference('rounds/rubric_manifest.json')}
    admission(root,packet)
    return packet


def plan(root, config):
    root = Path(root)
    if (root/PREFIX/'admission.json').exists():
        packet, _, completed, _ = inspect(root,config)
        return not (root/PREFIX/'completed.json').exists(), completed+1, packet
    packet = prepare(root,config)
    return True, packet['start_round'], packet



def verify_completion(root, packet, declaration_path):
    """Validate the immutable terminal receipt for recovery and final consumers."""
    from whetstone import preservation_runtime as rt
    root = Path(root)
    service = rt.acceptance_service(root)
    finish = root/PREFIX/'completed.json'
    require(finish.is_file(), 'Phase 2 closeout completion requires recovery')
    result = decode_json(finish.read_bytes())
    require(isinstance(result,dict) and set(result) == {'admission','terminal_state','state','files'}
            and result['terminal_state'] in {'CONVERGED','TARGET_NOT_REACHED'}
            and result['terminal_state'] == result['state'].get('terminal_state'), 'invalid closeout completion')
    require(result['admission'] == service.reference(f'{PREFIX}/admission.json')
            and result['state'] == rt.state_packet(root), 'completed Phase 2 closeout state changed')
    required = str(Path(declaration_path).relative_to(root)) if result['terminal_state']=='CONVERGED' else 'rounds/convergence_failure_report.json'
    require(required in [r['path'] for r in result['files']], 'closeout completion is missing its terminal output')
    for ref in result['files']:
        read_ref(root,ref)
    return result


def run(runner, *, overwrite=False, automatic=None):
    from whetstone import preservation_runtime as rt
    from whetstone.live_phase2 import LivePhase2Result
    from whetstone.rubrics import RubricManifest
    root, config = Path(runner.root), runner.config
    require(not overwrite,'guarded closeout evidence cannot be overwritten')
    service = rt.acceptance_service(root)
    if not (root/PREFIX/'admission.json').exists():
        packet = prepare(root,config,automatic=automatic)
        if packet['failure_report']:
            packet['failure_report'] = service._write(f'{PREFIX}/failure_report.json',read_ref(root,packet['failure_report']))
        service._write(f'{PREFIX}/admission.json',json_bytes(packet))
    packet, scheduler, completed, _ = inspect(root,config)
    finish = root/PREFIX/'completed.json'
    if finish.exists():
        result = verify_completion(root, packet, config.declaration_path)
        return LivePhase2Result(result['terminal_state'],completed,packet['base_hash'],packet['base_hash'],
            config.declaration_path if config.declaration_path.exists() else None,
            config.rounds_dir/'convergence_failure_report.json' if result['terminal_state']=='TARGET_NOT_REACHED' else None)
    runner.phase_1_rounds_completed = packet['state_before']['phase_1_rounds_completed']
    runner.rubric_manifest = RubricManifest(root/packet['rubric_manifest']['path'],decode_json(read_ref(root,packet['rubric_manifest'])))
    runner._preservation_closeout_completed = completed
    result = runner._execute_phase2_closeout(profiles=packet['profiles'],start_round=packet['start_round'],
        clean_profiles=set(packet['clean_profiles']),current_hash=packet['base_hash'],last_accepted_draft_hash=packet['base_hash'],
        declaration_path=config.declaration_path if config.declaration_path.exists() else None,
        scheduler_status=scheduler.status(),overwrite=False)
    if result.terminal_state in {'CONVERGED','TARGET_NOT_REACHED'}:
        files = [service.reference(str(p.relative_to(root))) for p in (result.declaration_path,result.report_path) if p and p.exists()]
        service._write(f'{PREFIX}/completed.json',json_bytes({'admission':service.reference(f'{PREFIX}/admission.json'),
            'terminal_state':result.terminal_state,'state':rt.state_packet(root),'files':files}))
    return result
