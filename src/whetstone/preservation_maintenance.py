"""Narrow maintenance authority over the immediately preceding accepted bytes."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from whetstone.hashing import draft_hash
from whetstone.preservation_contracts import SurfaceContext, decode_json, read_artifact, read_ref, require, validate_surface_bindings
from whetstone.preservation_inventory import validate_inventory


def operation_directory(admission):
    parent = ('rounds/preservation/phase2-entry' if admission['origin'] == 'phase2_entry' else
              f"rounds/round-{admission['round_number']}/preservation")
    return f"{parent}/attempt-{admission['attempt_number']}"


def proposal_context(root, admission, frozen):
    """Resolve provenance; full predecessor acceptance is checked by the service.

    The derived comparison surface grants no changes. It is not a new approval.
    """
    root = Path(root)
    approved = validate_surface_bindings(root, admission['allowed_change_surface'])
    parent = frozen.get('runtime', {}).get('maintenance_parent')
    if parent is None:
        require(admission['origin'] != 'phase2_entry', 'Phase 2 entry requires accepted maintenance lineage')
        for key in ('base_draft','inventory','scope_contract','finding_sources'):
            require(admission[key] == approved.surface[key], 'proposal admission/surface mismatch')
        return approved
    require(admission['origin'] in {'orchestrator_noop','phase2_entry'}, 'only maintenance may inherit authorization')
    require(frozen.get('scope_contract_packet') == decode_json(read_ref(root,approved.surface['scope_contract'])), 'maintenance frozen scope changed')
    marker = read_artifact(root,parent,'preservation_bridge_acceptance')
    parent_admission = read_artifact(root,marker['admission'],'preservation_bridge_acceptance_admission')
    require(admission['allowed_change_surface'] == parent_admission['allowed_change_surface'], 'maintenance must inherit the accepted authorization')
    for key in ('scope_contract','finding_sources'):
        require(admission[key] == parent_admission[key] == approved.surface[key], 'maintenance provenance changed')
    require(admission['base_draft'] == marker['materialized_draft'], 'maintenance base must be the accepted output Ref')
    base = read_ref(root,admission['base_draft'])
    inventory = read_artifact(root,admission['inventory'],'bridge_inventory')
    require(inventory['base_draft'] == admission['base_draft'], 'maintenance inventory/base differs')
    validate_inventory(inventory,base)
    surface = {**approved.surface,'base_draft':admission['base_draft'],'inventory':admission['inventory'],
               'allowed_sections':[],'allowed_unit_ids':[], 'frozen_sections':[s['section_id'] for s in inventory['sections']]}
    return SurfaceContext(surface,inventory,base,approved.findings)


def verify_parent(service, original, chain):
    directory = operation_directory(original)
    proposal = decode_json((service.root/directory/'proposal.json').read_bytes())
    frozen = decode_json(read_ref(service.root,proposal['normal_round_evidence']['effective_config']))
    parent = frozen.get('runtime',{}).get('maintenance_parent')
    if parent is not None:
        require(chain and parent == chain[-1][0], 'maintenance must follow its exact accepted parent')
    if original['origin'] == 'phase2_entry':
        require(parent is not None and not any(service._proposal_directory(m['proposal'])[2]['phase'] == 'phase_2' for _,m,_ in chain),
                'Phase 2 entry must occur once after Phase 1')
        verify_handoff(service, frozen, chain)


def verify_handoff(service, frozen, chain):
    """Prove full-profile cleanliness from frozen review/acceptance evidence."""
    from whetstone.scheduler import profile_names_for_phase
    from whetstone.preservation_continuation import verify_review_receipt
    state = frozen['runtime']['state_before']
    require(chain and state.get('phase') == 'phase_1' and state.get('terminal_state') == 'PHASE_1_STABLE'
            and state.get('ready_for_phase_2') is True and state.get('run_mode') != 'focused_phase_1',
            'Phase 2 maintenance requires a full stable Phase 1 handoff')
    require((state.get('preservation_bridge') or {}).get('accepted') == chain[-1][0], 'Phase 1 handoff accepted pointer differs')
    base = read_ref(service.root,chain[-1][1]['materialized_draft'])
    expected_hash = draft_hash(base.decode())
    require(state.get('current_draft_hash') == state.get('last_accepted_draft_hash') == expected_hash,
            'Phase 1 handoff hash differs from accepted authority')
    require(not any(i['normalized_severity'] in {'major','blocker'} for i in chain[-1][2]), 'serious accepted residuals block Phase 2')
    config = frozen['resolved_config']
    profiles = profile_names_for_phase(config['review_profile_set'],'phase_1')
    verified = {}
    completed = set()
    for _, marker, _ in chain:
        _, proposal, admission = service._proposal_directory(marker['proposal'])
        require(admission['phase'] == 'phase_1', 'handoff chain already entered Phase 2')
        prior = decode_json(read_ref(service.root,proposal['normal_round_evidence']['effective_config']))
        for key in ('review_mode','review_profile_set','review_profile_budgets','review_budget_exhaustion_policy'):
            require(prior['resolved_config'][key] == config[key], 'Phase 1 handoff settings changed')
        completed.add(admission['round_number'])
        if admission['profile'] != 'vertical':
            feedback = read_artifact(service.root,proposal['normal_round_evidence']['reviewer_feedback'][0],'reviewer_feedback')
            verified[admission['profile']] = (admission['round_number'],feedback)
    frozen_refs = frozen['runtime'].get('handoff_reviews',[])
    for ref in frozen_refs:
        receipt = decode_json(read_ref(service.root,ref))
        result = decode_json(read_ref(service.root,receipt['result']))
        packet = decode_json(read_ref(service.root,result['input']))
        number = packet['round_number']
        require(ref['path'] == f'rounds/round-{number}/preservation/review_complete.json', 'handoff receipt path differs')
        packet, _, feedback, _, issues = verify_review_receipt(service.root,number)
        require(packet['phase'] == 'phase_1' and number <= state['current_round'], 'handoff review lies outside Phase 1')
        if packet['kind']=='vertical_source':
            require(number < service._proposal_directory(chain[-1][1]['proposal'])[2]['round_number'], 'vertical handoff requires accepted consolidation after source reviews')
        completed.add(number)
        if packet['profile'] not in verified or number > verified[packet['profile']][0]:
            verified[packet['profile']] = (number,feedback)
    require(sorted(completed) == list(range(1,state['current_round']+1)), 'Phase 1 handoff evidence is incomplete')
    for profile in profiles:
        require(profile in verified, 'Phase 1 profile has no completed verification')
        feedback = verified[profile][1]
        require(feedback['draft_hash'] == expected_hash and not any(f['normalized_severity'] in {'major','blocker'} and f['in_scope'] for f in feedback['feedback']),
                'Phase 1 profile has not verified the accepted bytes clean')


def enter_phase2(root, config):
    """Commit/repair one maintenance operation, without clients or a review round."""
    from whetstone import preservation_runtime as rt
    from whetstone.preservation_proposals import json_bytes
    from whetstone.versioning import VersionPromotionResult, _find_version_target
    root = Path(root)
    service = rt.acceptance_service(root)
    require(config.preservation_bridge is not None, 'guarded Phase 2 cannot downgrade')
    from whetstone.config import parse_preservation_bridge
    parse_preservation_bridge(asdict(config.preservation_bridge))
    surface=validate_surface_bindings(root,config.preservation_bridge.allowed_change_surface)
    require(config.scope_contract.path.read_bytes()==read_ref(root,surface.surface['scope_contract']), 'maintenance scope differs from approved scope')
    require(config.spec_path.resolve()==root.resolve()/'spec.md' and config.rounds_dir.resolve()==root.resolve()/'rounds'
            and config.history_path.resolve()==root.resolve()/'spec.history.md', 'maintenance requires canonical guarded paths')
    # A repeated entry only repairs its own local acceptance. Generic Phase 2
    # execution/retry is intentionally a separate operation.
    paths = sorted(root.glob('rounds/preservation/phase2-entry/attempt-*/noop_request.json'),
                   key=lambda p:int(p.parent.name.rsplit('-',1)[1]))
    if not paths:
        proposals=sorted(root.glob('rounds/preservation/phase2-entry/attempt-*/proposal.json'), key=lambda p:int(p.parent.name.rsplit('-',1)[1]))
        if proposals:
            path=proposals[-1];proposal_ref=service.reference(str(path.relative_to(root)))
            _,proposal,_=service._proposal_directory(proposal_ref)
            frozen=decode_json(read_ref(root,proposal['normal_round_evidence']['effective_config']))
            require(frozen['resolved_config']==rt._jsonable(asdict(config)), 'maintenance recovery settings changed')
            report=read_artifact(root,service.reference(str(path.with_name('report.json').relative_to(root))),'current_runtime_preservation_bridge_report')
            require(report['outcome']=='eligible', 'maintenance proposal requires inspection')
            service.prepare_request(proposal_ref=proposal_ref,evidence_refs=[],output=str(path.with_name('noop_request.json').relative_to(root)))
            paths=[path.with_name('noop_request.json')]
    if paths:
        request_ref=service.reference(str(paths[-1].relative_to(root)))
        request=read_artifact(root,request_ref,'preservation_bridge_acceptance_request')
        _, proposal, _ = service._proposal_directory(request['proposal'])
        frozen=decode_json(read_ref(root,proposal['normal_round_evidence']['effective_config']))
        require(frozen['resolved_config'] == rt._jsonable(asdict(config)), 'maintenance recovery settings changed')
        result=service.accept(request_ref)
    else:
        rt.guard_consumer(root,config)
        chain=service._chain();state=rt.state_packet(root)
        frozen=rt.config_snapshot(config,phase='phase_2',profile=None,state=state)
        frozen['runtime']['handoff_reviews']=[service.reference(str(p.relative_to(root))) for p in sorted(root.glob('rounds/round-*/preservation/review_complete.json'))]
        verify_handoff(service,frozen,chain)
        ticket=service.admit(surface_ref=config.preservation_bridge.allowed_change_surface,effective_config=frozen,
                             reviewer_feedback_refs=[],round_number=None,profile=None,phase='phase_2',origin='phase2_entry',
                             client_attempt_number=None,maintenance_parent=chain[-1][0])
        report_ref=service.capture_maintenance(ticket)
        report=read_artifact(root,report_ref,'current_runtime_preservation_bridge_report')
        require(report['outcome']=='eligible', 'Phase 2 maintenance proposal failed; inspect its report')
        request_ref=service.prepare_request(proposal_ref=report['proposal'],evidence_refs=[],output=f'{ticket.directory}/noop_request.json')
        result=service.accept(request_ref)
        proposal=read_artifact(root,report['proposal'],'preservation_bridge_proposal')
    require(result.outcome=='accepted','Phase 2 maintenance acceptance failed')
    admission=read_artifact(root,proposal['admission'],'preservation_bridge_proposal_admission')
    before=read_ref(root,admission['base_draft']);after=read_ref(root,proposal['materialized_draft'])
    old,new=_find_version_target(before.decode()),_find_version_target(after.decode())
    return VersionPromotionResult(before!=after,old.version if old else '',new.version if new else '',draft_hash(before.decode()),draft_hash(after.decode()))


def guard_phase2_review(root, config, number):
    from dataclasses import asdict
    from whetstone import preservation_runtime as rt
    rt.guard_consumer(root,config)
    service=rt.acceptance_service(root);chain=service._chain()
    entries=[m for _,m,_ in chain if service._proposal_directory(m['proposal'])[2]['origin']=='phase2_entry']
    require(len(entries)==1,'Phase 2 review requires accepted entry maintenance')
    _,proposal,_=service._proposal_directory(entries[0]['proposal'])
    frozen=decode_json(read_ref(Path(root),proposal['normal_round_evidence']['effective_config']))
    expected=deepcopy(frozen['resolved_config']);actual=rt._jsonable(asdict(config))
    expected.pop('preservation_bridge');actual.pop('preservation_bridge')
    require(expected==actual,'Phase 2 settings differ from the admitted entry')
    require(config.scope_contract.path.read_bytes()==read_ref(Path(root),read_artifact(Path(root),proposal['admission'],'preservation_bridge_proposal_admission')['scope_contract']), 'Phase 2 scope changed')
    require(number>service.operation_order(service._proposal_directory(chain[-1][1]['proposal'])[2]),'Phase 2 round already accepted')


def phase2_start_state(root, config):
    from whetstone import preservation_runtime as rt
    service=rt.acceptance_service(root);chain=service._chain()
    entries=[m for _,m,_ in chain if service._proposal_directory(m['proposal'])[2]['origin']=='phase2_entry']
    if entries:
        require(chain[-1][1]==entries[0], 'generic Phase 2 continuation is unsupported')
        _,proposal,_=service._proposal_directory(entries[0]['proposal'])
        frozen=decode_json(read_ref(Path(root),proposal['normal_round_evidence']['effective_config']))
        bound=frozen['runtime']['state_before']['current_round']
        require(not any(int(p.name.removeprefix('round-'))>bound for p in (Path(root)/'rounds').glob('round-*') if p.name.removeprefix('round-').isdigit()),
                'generic Phase 2 technical resume is unsupported')
        return frozen['runtime']['state_before']
    rt.guard_consumer(root,config)
    state=rt.state_packet(root)
    frozen=rt.config_snapshot(config,phase='phase_2',profile=None,state=state)
    frozen['runtime']['handoff_reviews']=[service.reference(str(p.relative_to(service.root))) for p in sorted(service.root.glob('rounds/round-*/preservation/review_complete.json'))]
    verify_handoff(service,frozen,chain)
    return state
