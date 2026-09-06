"""Runtime bridge adapters; marker evidence is authority, run state is readback."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from whetstone.config import OrchestratorConfig, root_declares_bridge
from whetstone.hashing import draft_hash
from whetstone.preservation_acceptance import AcceptanceService
from whetstone.preservation_contracts import BridgeContractError, decode_json, read_artifact, read_ref, require, validate_proposal_bindings, validate_surface_bindings
from whetstone.preservation_inventory import sha256_bytes
from whetstone.preservation_proposals import ProposalStore, json_bytes


class BridgeHalt(ValueError):
    def __init__(self, terminal_state: str, report_ref: dict[str, str]):
        self.terminal_state = terminal_state
        self.report_ref = report_ref
        super().__init__(f"preservation operation stopped: {terminal_state}")


def active(root: Path, config: OrchestratorConfig | None = None) -> bool:
    return bool(config and config.preservation_bridge is not None) or root_declares_bridge(Path(root))


def _jsonable(value):
    if isinstance(value, Path):return str(value)
    if isinstance(value, dict):return {k: _jsonable(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)):return [_jsonable(v) for v in value]
    return value


def verify_frozen_round_state(current, before, *, materialized_hash=None):
    """Only terminal/readback/telemetry fields may change while an operation is held."""
    mutable = {'terminal_state', 'ready_for_phase_2', 'resumable', 'preservation_bridge', 'updated_at', 'telemetry_totals'}
    actual = {key: value for key, value in current.items() if key not in mutable}
    expected = {key: value for key, value in before.items() if key not in mutable}
    if materialized_hash is not None and actual.get('current_draft_hash') == materialized_hash:
        actual['current_draft_hash'] = expected.get('current_draft_hash')
    require(actual == expected, 'frozen scheduler binding changed; inspect the conflicting round state')


def config_snapshot(config, *, phase, profile, state):
    from whetstone.run_state import effective_run_config
    from whetstone.scope import read_scope_contract
    scope = read_scope_contract(config.scope_contract.path)
    return {"scope_contract_packet": scope.packet if scope else None, "phase": phase, "profile": profile, "workflow": config.workflow,
            "effective_run_config": effective_run_config(config), "resolved_config": _jsonable(asdict(config)),
            "runtime": {"version": "bridge-runtime-v1", "state_before": deepcopy(state)}}


def initialize(root: Path, config: OrchestratorConfig, *, overwrite=False):
    require(config.preservation_bridge is not None, "CONFIG_INVALID: guarded root cannot downgrade to legacy")
    require(not overwrite, "CONFIG_INVALID: guarded evidence cannot be overwritten")
    require(config.review_mode in {"horizontal", "vertical"}, "CONFIG_INVALID: unsupported bridge review mode")
    from whetstone.config import parse_preservation_bridge
    parse_preservation_bridge(asdict(config.preservation_bridge))
    root = Path(root).resolve();store = ProposalStore(root)
    require(config.spec_path.resolve() == root/'spec.md' and config.rounds_dir.resolve() == root/'rounds'
            and config.history_path.resolve() == root/'spec.history.md', "CONFIG_INVALID: bridge currently requires canonical run paths")
    path = root/'rounds/preservation/runtime.json'
    with store._lock():
        if path.exists():
            packet = decode_json(path.read_bytes())
            require(packet == {"mode":"enforce", "capability_version":"preservation-bridge-v1"}, "invalid runtime capability marker")
            return
        state = root/'rounds/run_state.json'
        require(not state.exists(), "CONFIG_INVALID: legacy runs cannot acquire retrospective bridge coverage")
        require(not list(root.glob('rounds/round-*/preservation/attempt-*/admission.json')), "CONFIG_INVALID: initialize guarded runtime before proposal admission")
        surface = validate_surface_bindings(root, config.preservation_bridge.allowed_change_surface)
        require(config.scope_contract.path.is_file() and config.scope_contract.path.read_bytes() == read_ref(root, surface.surface['scope_contract']),
                'CONFIG_INVALID: runtime scope must match the admitted approved scope')
        store._write('rounds/preservation/runtime.json',json_bytes({"mode":"enforce", "capability_version":"preservation-bridge-v1"}))


def readback(root: Path, config: OrchestratorConfig | None = None, *, include_reviews=True):
    root = Path(root)
    guarded = active(root, config)
    result = {"mode": "enforce" if guarded else "legacy_unguarded", "capability_version": "preservation-bridge-v1" if guarded else None,
              "latest_proposal":None, "latest_attempt_report":None, "pending_acceptance_admission":None,
              "accepted":None, "pending_outcome":None, "next_action":"none"}
    if not guarded:return result
    service = acceptance_service(root)
    service._boundary()
    chain = service._chain()
    if chain:
        service._verify_mirrors(chain, allow_last_pending=True)
        result['accepted'] = chain[-1][0]
    attempts=[]
    import re
    directories=[]
    for directory in root.glob('rounds/round-*/preservation/attempt-*'):
        match=re.fullmatch(r'rounds/round-([1-9][0-9]*)/preservation/attempt-([1-9][0-9]*)',str(directory.relative_to(root)))
        if match: directories.append((int(match[1]),int(match[2]),directory))
    if directories and not (max(directories)[2]/'admission.json').is_file():
        result.update(pending_outcome='technical_failure', next_action='inspect_and_repair')
        return result
    for path in root.glob('rounds/round-*/preservation/attempt-*/admission.json'):
        ref=service.reference(str(path.relative_to(root)));admission=read_artifact(root,ref,'preservation_bridge_proposal_admission')
        attempts.append((admission['round_number'],admission['attempt_number'],path.parent,ref))
    if attempts:
        _,_,directory,admission_ref=max(attempts)
        proposal_path=directory/'proposal.json'
        if proposal_path.exists():
            result['latest_proposal']=service.reference(str(proposal_path.relative_to(root)))
            validate_proposal_bindings(root,result['latest_proposal'])
        reports=[]
        if (directory/'report.json').exists():reports.append((0,directory/'report.json'))
        for path in directory.glob('acceptance-attempt-*/report.json'):
            reports.append((int(path.parent.name.rsplit('-',1)[1]),path))
        if reports:
            _,path=max(reports);ref=service.reference(str(path.relative_to(root)))
            report=read_artifact(root,ref,'current_runtime_preservation_bridge_report')
            result.update(latest_attempt_report=ref,pending_outcome=report['outcome'],next_action=report['next_action'])
        else:result.update(pending_outcome='technical_failure',next_action='inspect_and_repair')
        accepted_here=chain and chain[-1][1]['proposal']==result['latest_proposal']
        if accepted_here:
            try:
                service._verify_mirrors(chain)
                service.verify_runtime_completion(chain)
            except BridgeContractError:
                result.update(pending_outcome='technical_failure', next_action='inspect_and_repair')
            else:
                result.update(pending_outcome=None, next_action='ordinary_review')
        elif (directory/'proposal.json').exists():
            admissions=sorted(directory.glob('acceptance-attempt-*/admission.json'),key=lambda p:int(p.parent.name.rsplit('-',1)[1]))
            if admissions:result['pending_acceptance_admission']=service.reference(str(admissions[-1].relative_to(root)))
    if include_reviews:
        from whetstone.preservation_continuation import pending_review
        accepted_round = 0
        if chain:
            _, _, original = service._proposal_directory(chain[-1][1]['proposal'])
            accepted_round = original['round_number']
        pending = pending_review(root, accepted_round=accepted_round, proposal_round=max((a[0] for a in attempts), default=0))
        if pending:
            result.update(pending_outcome='technical_failure', next_action=pending['next_action'])
            path = pending['directory']/'result.json'
            if path.exists():
                result['latest_attempt_report'] = service.reference(str(path.relative_to(root)))
    return result


def guard_consumer(root: Path, config: OrchestratorConfig | None = None):
    if not active(root,config):return
    status=readback(root,config)
    require(status['accepted'] is not None and status['pending_outcome'] is None, 'preservation: pending/rejected/incomplete evidence cannot be consumed')
    service=acceptance_service(root)
    chain=service._chain()
    service._verify_mirrors(chain)
    service.verify_runtime_completion(chain)


def acceptance_service(root: Path):
    if active(root):return RuntimeAcceptanceService(root)
    return AcceptanceService(root)


def guard_operation(root, config, *, phase, round_number, technical_resume=False):
    """Refuse a new Editor until all earlier authority and scheduler repair is complete."""
    require(phase == 'phase_1', 'CONFIG_INVALID: guarded Phase 2 and maintenance are not yet qualified')
    surface = validate_surface_bindings(Path(root), config.preservation_bridge.allowed_change_surface)
    require((Path(root)/'spec.md').read_bytes() == surface.base, 'new round requires authorization for the current base')
    require(config.scope_contract.path.is_file() and config.scope_contract.path.read_bytes() == read_ref(Path(root), surface.surface['scope_contract']),
            'CONFIG_INVALID: runtime scope must match the admitted approved scope')
    status = readback(root, config)
    if technical_resume:
        require(status['pending_outcome'] == 'technical_failure' and status['next_action'] == 'technical_resume',
                'technical continuation requires a retained typed timeout')
    if status['accepted']:
        service = acceptance_service(root)
        service.verify_runtime_completion(service._chain())
        _, _, previous = service._proposal_directory(read_artifact(root, status['accepted'], 'preservation_bridge_acceptance')['proposal'])
        require(round_number > previous['round_number'], 'round already accepted; use local acceptance replay')
    if status['pending_outcome']:
        require(technical_resume and status['next_action'] == 'technical_resume',
                'pending/rejected proposal requires its local preservation operation')
        report = read_artifact(root, status['latest_attempt_report'], 'current_runtime_preservation_bridge_report')
        admission = read_artifact(root, report['admission'], 'preservation_bridge_proposal_admission')
        require(admission['phase'] == 'phase_1' and admission['round_number'] == round_number,
                'technical continuation must retain phase and round')
        require(config.preservation_bridge.allowed_change_surface == admission['allowed_change_surface'],
                'technical continuation cannot refresh authorization')
        require(config.preservation_bridge.predecessor_report == status['latest_attempt_report'],
                'technical continuation must link its immediate predecessor report')
        execution = decode_json((Path(root)/report['admission']['path']).with_name('execution_started').read_bytes())
        require(execution['admission'] == report['admission'], 'retry execution admission mismatch')
        frozen = decode_json(read_ref(Path(root), execution['effective_config']))
        verify_frozen_round_state(state_packet(root), frozen['runtime']['state_before'])
        for mirror in execution['snapshots']:
            require(read_ref(Path(root), mirror['source']) == read_ref(Path(root), mirror['snapshot']), 'retry input snapshot changed')
        if execution.get('supplied_input') is not None:
            read_ref(Path(root), execution['supplied_input'])
        require(len(execution['reviewer_feedback']) == 1 or frozen['resolved_config']['review_mode'] == 'vertical', 'unsupported retry Reviewer topology')
        feedback = decode_json((Path(root)/f"rounds/round-{round_number}/reviewer_feedback.json").read_bytes())
        require(feedback == decode_json(read_ref(Path(root), execution['reviewer_feedback'][0])), 'retry Reviewer evidence changed')
        require(frozen['resolved_config'] == _jsonable(asdict(config)) | {'preservation_bridge': frozen['resolved_config']['preservation_bridge']},
                'technical continuation cannot change effective settings')
        require((Path(root)/'spec.md').read_bytes() == read_ref(root, admission['base_draft']), 'technical continuation base changed')


class RuntimeAcceptanceService(AcceptanceService):
    def _boundary(self):
        path = self.root/'rounds/preservation/runtime.json'
        require(path.is_file(), 'missing guarded runtime identity')
        require(decode_json(path.read_bytes()) == {'mode':'enforce','capability_version':'preservation-bridge-v1'},
                'invalid guarded runtime identity')

    runtime = True

    def _check_round(self, original, chain):
        require(original['phase'] == 'phase_1' and original['origin'] != 'phase2_entry',
                'CONFIG_INVALID: guarded Phase 2 and maintenance are not yet qualified')
        previous_rounds=[]
        for _, marker, _ in chain:
            _, _, before=self._proposal_directory(marker['proposal'])
            if before['round_number'] is not None:previous_rounds.append(before['round_number'])
        require(original['round_number'] > max(previous_rounds,default=0), 'runtime round already committed or out of order')

    def _ordinary(self, proposal, admission, previous_issues):
        normal=proposal['normal_round_evidence']
        config=decode_json(read_ref(self.root,normal['effective_config']))
        runtime=config.get('runtime')
        require(isinstance(runtime,dict) and runtime.get('version')=='bridge-runtime-v1','missing frozen runtime context')
        state=runtime['state_before']
        require(state.get('phase',admission['phase'])==admission['phase'], 'frozen scheduler phase mismatch')
        require(state.get('current_round',admission['round_number'])==admission['round_number'], 'frozen scheduler round mismatch')
        require(state.get('active_profile',admission['profile'])==admission['profile'], 'frozen scheduler profile mismatch')
        require(config['resolved_config']['review_mode'] in {'horizontal','vertical'}, 'unsupported frozen review mode')
        from whetstone.preservation_continuation import verify_review_receipt
        previous_issues = list(previous_issues)
        for path in self.root.glob('rounds/round-*/preservation/review_complete.json'):
            number = int(path.parent.parent.name.removeprefix('round-'))
            if number < admission['round_number']:
                packet, _, _, _, review_issues = verify_review_receipt(self.root, number)
                if packet['kind'] in {'review_only','vertical_closeout'} and packet['accepted'] == (state.get('preservation_bridge') or {}).get('accepted'):
                    previous_issues.extend(review_issues)
        eligible, issues = super()._ordinary(proposal,admission,previous_issues)
        decisions = self._decisions(proposal, admission)
        eligible = eligible and not any(p['orchestrator_action'] == 'pause_for_input' for p in decisions['decision_points'])
        return eligible, issues

    def _decisions(self, proposal, admission):
        from whetstone.config import DecisionPointConfig
        from whetstone.decisions import detect_decision_points
        normal = proposal['normal_round_evidence']
        frozen = decode_json(read_ref(self.root, normal['effective_config']))
        feedback = read_artifact(self.root, normal['reviewer_feedback'][0], 'reviewer_feedback')
        summary = read_artifact(self.root, normal['editor_summary'], 'editor_summary')
        return detect_decision_points(
            draft_before=read_ref(self.root, admission['base_draft']).decode(),
            draft_after=read_ref(self.root, proposal['materialized_draft']).decode(),
            round_number=admission['round_number'], profile=admission['profile'],
            reviewer_feedback=feedback, editor_summary=summary,
            config=DecisionPointConfig(**frozen['resolved_config']['decision_points']),
            scope_contract=frozen['scope_contract_packet'])

    def _mirrors(self, chain, *, initial=None):
        import json
        mirrors = super()._mirrors(chain, initial=initial)
        for _, marker, _ in chain:
            _, proposal, original = self._proposal_directory(marker['proposal'])
            prefix = f"rounds/round-{original['round_number']}"
            normal = proposal['normal_round_evidence']
            frozen = decode_json(read_ref(self.root, normal['effective_config']))
            require(len(normal['reviewer_feedback']) == 1 or frozen['resolved_config']['review_mode'] == 'vertical',
                    'horizontal proposal must retain one Reviewer artifact')
            feedback = read_artifact(self.root, normal['reviewer_feedback'][0], 'reviewer_feedback')
            mirrors[f'{prefix}/reviewer_feedback.json'] = (json.dumps(feedback, indent=2, sort_keys=True)+'\n').encode()
            mirrors[f'{prefix}/decision_points.json'] = json_bytes(self._decisions(proposal, original))
        return mirrors


    def _runtime_state(self, chain):
        ref, marker, issues=chain[-1]
        _,proposal,original=self._proposal_directory(marker['proposal'])
        config=decode_json(read_ref(self.root,proposal['normal_round_evidence']['effective_config']))
        state=deepcopy(config['runtime']['state_before'])
        number=original['round_number']
        hashes=list(state.get('seen_draft_hashes',[]))
        if not hashes or hashes[-1]!=marker['materialized_draft_hash']:hashes.append(marker['materialized_draft_hash'])
        state.update(current_round=number,current_absolute_round=number,phase=original['phase'],active_profile=original['profile'],
                     current_draft_hash=marker['materialized_draft_hash'],last_accepted_draft_hash=marker['materialized_draft_hash'],
                     seen_draft_hashes=hashes,terminal_state=None,ready_for_phase_2=False,resumable=True,
                     preservation_bridge={'mode':'enforce','capability_version':'preservation-bridge-v1',
                         'latest_proposal':marker['proposal'],'latest_attempt_report':marker['report'],
                         'pending_acceptance_admission':None,'accepted':ref,'pending_outcome':None,'next_action':'ordinary_review'})
        if original['phase']=='phase_1':state['phase_1_rounds_completed']=number
        else:state['phase_2_rounds_completed']=number-int(state.get('phase_1_rounds_completed',0))
        state['effective_run_config']=config['effective_run_config']
        return state

    def _accept(self, request_ref, *, dry_run):
        self._boundary()
        request = read_artifact(self.root, request_ref, 'preservation_bridge_acceptance_request')
        chain = self._chain()
        replay = any(marker['proposal'] == request['proposal'] for _, marker, _ in chain)
        if not replay:
            if chain:
                self.verify_runtime_completion(chain)
            status = readback(self.root)
            require(status['latest_proposal'] == request['proposal'], 'a later proposal attempt supersedes this operation')
            _, proposal, original = self._proposal_directory(request['proposal'])
            frozen = decode_json(read_ref(self.root, proposal['normal_round_evidence']['effective_config']))
            before = frozen['runtime']['state_before']
            current = state_packet(self.root)
            verify_frozen_round_state(current, before)
            require(current.get('current_draft_hash') == draft_hash(read_ref(self.root, original['base_draft']).decode()),
                    'frozen scheduler draft hash changed')
        result = super()._accept(request_ref, dry_run=dry_run)
        if not dry_run and result.outcome == 'rejected':
            state = state_packet(self.root)
            state.update(terminal_state='HALTED_ARTIFACT_INVALID', ready_for_phase_2=False, resumable=False,
                         preservation_bridge=readback(self.root))
            self._replace('rounds/run_state.json', json_bytes(state))
        return result

    def _completion(self, chain):
        ref, marker, issues = chain[-1]
        _, proposal, original = self._proposal_directory(marker['proposal'])
        feedback = read_artifact(self.root, proposal['normal_round_evidence']['reviewer_feedback'][0], 'reviewer_feedback')
        # Scheduler cleanliness uses Reviewer findings, never Editor resolution claims.
        counts = {severity: sum(i['normalized_severity'] == severity and i['in_scope'] for i in feedback['feedback'])
                  for severity in ('blocker', 'major')}
        return {'acceptance': ref, 'round_number': original['round_number'], 'profile': original['profile'],
                'reviewer_counts': counts, 'unresolved_issues': issues,
                'spec_mutated': not marker['accepted_noop']}

    def _completion_path(self, marker):
        return f"{Path(marker['admission']['path']).parent}/runtime_completed.json"

    def verify_runtime_completion(self, chain):
        from whetstone.preservation_continuation import verify_review_receipt
        for path in self.root.glob('rounds/round-*/preservation/review_complete.json'):
            number = int(path.parent.parent.name.removeprefix('round-'))
            packet, _, _, _, _ = verify_review_receipt(self.root, number)
            prior = [(ref, marker) for ref, marker, _ in chain
                     if self._proposal_directory(marker['proposal'])[2]['round_number'] < number]
            if packet['kind'] == 'vertical_source' and packet['accepted'] is None:
                require(not prior, 'seed source cannot observe later authority')
                continue
            require(prior and prior[-1][0] == packet['accepted'], 'review-only parent is not the preceding acceptance')
            require(all(self._proposal_directory(marker['proposal'])[2]['round_number'] != number for _, marker, _ in chain),
                    'review-only round has competing acceptance')
            parents = [(ref, marker) for ref, marker, _ in chain if ref == packet['accepted']]
            require(len(parents) == 1, 'review-only acceptance is missing from the chain')
            require(read_ref(self.root, packet['base']) == read_ref(self.root, parents[0][1]['materialized_draft']),
                    'review-only base differs from its acceptance')
        for index in range(1, len(chain)+1):
            path = self._path(self._completion_path(chain[index-1][1]))
            require(path.is_file() and path.read_bytes() == json_bytes(self._completion(chain[:index])),
                    'scheduler completion repair is pending or conflicting')
        if chain:
            current = state_packet(self.root)
            require((current.get('preservation_bridge') or {}).get('accepted') == chain[-1][0],
                    'scheduler acceptance pointer is stale')
            require(current.get('last_accepted_draft_hash') == chain[-1][1]['materialized_draft_hash'],
                    'scheduler accepted hash differs')

    def _repair(self, chain):
        if not chain:
            return super()._repair(chain)
        expected = self._runtime_state(chain)
        current = state_packet(self.root)
        accepted = (current.get('preservation_bridge') or {}).get('accepted')
        previous = chain[-2][0] if len(chain) > 1 else None
        require(accepted in (previous, chain[-1][0]), 'conflicting scheduler acceptance pointer')
        if accepted != chain[-1][0]:
            _, proposal, original = self._proposal_directory(chain[-1][1]['proposal'])
            frozen = decode_json(read_ref(self.root, proposal['normal_round_evidence']['effective_config']))
            before = frozen['runtime']['state_before']
            verify_frozen_round_state(current, before, materialized_hash=chain[-1][1]['materialized_draft_hash'])
            require(current.get('current_draft_hash') in (draft_hash(read_ref(self.root, original['base_draft']).decode()),
                                                         chain[-1][1]['materialized_draft_hash']),
                    'scheduler repair has an unrelated draft hash')
        completion_path = self._completion_path(chain[-1][1])
        completion = json_bytes(self._completion(chain))
        path = self._path(completion_path)
        require(not path.exists() or path.read_bytes() == completion, 'conflicting scheduler completion')
        super()._repair(chain)
        if accepted != chain[-1][0]:
            self._replace('rounds/run_state.json', json_bytes(expected))
        self._write(completion_path, completion)
        self.verify_runtime_completion(chain)


def state_packet(root: Path):
    path=Path(root)/'rounds/run_state.json'
    return decode_json(path.read_bytes()) if path.exists() else {}


def preserve_state_fields(root: Path, config: OrchestratorConfig, packet: dict):
    if not active(root,config):
        packet['preservation_bridge']=readback(root,config)
        return packet
    previous=state_packet(root)
    existing=previous.get('preservation_bridge')
    packet['preservation_bridge']=existing or readback(root,config)
    return packet


def run_proposal(runner, *, round_number, profile, phase, prompt, feedback, editor=None, supplied=None, apply=True, client_attempt_number=1):
    root=runner.root.resolve();config=runner.config
    require(config.preservation_bridge is not None,'CONFIG_INVALID: missing bridge configuration')
    store=ProposalStore(root)
    # Ordinary reviewer storage is preserved, while admission freezes an exact
    # immutable copy before the Editor call can produce any new output.
    feedback_ref=store._write(f'rounds/round-{round_number}/preservation/reviewer-{sha256_bytes(json_bytes(feedback))}.json',json_bytes(feedback))
    before_state=state_packet(root)
    before_state.update(current_round=round_number, phase=phase, active_profile=profile,
                        current_draft_hash=draft_hash((root/'spec.md').read_bytes().decode()))
    before_state.setdefault('last_accepted_draft_hash', None)
    acceptance_service(root)._replace('rounds/run_state.json', json_bytes(before_state))
    frozen=config_snapshot(config,phase=phase,profile=profile,state=before_state)
    frozen['editor_prompt'] = prompt
    frozen['editor_timeout_seconds'] = runner._timeout_for_role('editor')
    surface = validate_surface_bindings(root, config.preservation_bridge.allowed_change_surface)
    require(frozen['scope_contract_packet'] == decode_json(read_ref(root, surface.surface['scope_contract'])),
            'frozen runtime scope differs from the admitted approved scope')
    if config.preservation_bridge.predecessor_report:
        previous = read_artifact(root, config.preservation_bridge.predecessor_report, 'current_runtime_preservation_bridge_report')
        execution = decode_json((root/previous['admission']['path']).with_name('execution_started').read_bytes())
        earlier = decode_json(read_ref(root, execution['effective_config']))
        require(frozen['editor_timeout_seconds'] == earlier['editor_timeout_seconds'], 'technical retry cannot change the resolved timeout')
    feedback_refs = [feedback_ref]
    if config.review_mode == 'vertical':
        from whetstone.preservation_vertical import source_bindings
        receipts, source_refs = source_bindings(root, config, round_number)
        frozen['vertical_review_sources'] = receipts
        feedback_refs.extend(source_refs)
    origin='supplied_revision' if supplied is not None else ('editor' if feedback.get('feedback') else 'orchestrator_noop')
    ticket=store.admit(surface_ref=config.preservation_bridge.allowed_change_surface,effective_config=frozen,
                       reviewer_feedback_refs=feedback_refs,round_number=round_number,profile=profile,phase=phase,origin=origin,
                       client_attempt_number=client_attempt_number if origin=='editor' else None,predecessor_report=config.preservation_bridge.predecessor_report)
    if origin=='orchestrator_noop':
        from whetstone.live import _no_op_editor_summary
        base=read_ref(root,decode_json(ticket.admission_json)['base_draft'])
        summary=_no_op_editor_summary(round_number=round_number,draft_hash_value=draft_hash(base.decode()),draft_after_content=base.decode())
        report_ref=store.capture_revision(ticket,base,summary)
    else:
        require(editor is not None,'missing Editor adapter')
        def invoke(inputs):
            require(hasattr(editor,'revise_raw'), 'guarded Editor adapter must expose exact revise_raw response bytes')
            try:
                return editor.revise_raw(prompt + '\n\nPreservation bridge: do not alter the orchestrator-owned version/status anchors. '
                                         + 'Only the approved change surface may be edited. Its root-relative immutable Ref is '
                                         + json_bytes(config.preservation_bridge.allowed_change_surface).decode().strip() + '.\n')
            finally:
                runner._write_client_telemetry(round_number=round_number, phase=phase, profile=profile,
                    client_role='editor', client_config=config.editor, artifact_name='preservation',
                    attempt_number=decode_json(ticket.admission_json)['attempt_number'], call=editor.revise_raw)
        if supplied is None:
            report_ref=store.run_editor(ticket,invoke)
        else:
            raw=supplied if isinstance(supplied,bytes) else supplied.encode('utf-8')
            report_ref=store.run_supplied(ticket, raw, invoke)
    report=read_artifact(root,report_ref,'current_runtime_preservation_bridge_report')
    service=acceptance_service(root)
    if report['validation_result']=='pass' and apply:
        request=service.prepare_request(proposal_ref=report['proposal'],evidence_refs=[],output=f'{ticket.directory}/noop_request.json')
        result=service.accept(request)
        if result.acceptance is not None:
            from whetstone.live import LiveRoundResult
            original=decode_json(ticket.admission_json);base=read_ref(root,original['base_draft'])
            return LiveRoundResult(round_number,root/f'rounds/round-{round_number}',draft_hash(base.decode()),
                                   report['materialized_draft_hash'],True,len(feedback['feedback']),base!=read_ref(root,report['materialized_draft']))
        report=result.report;report_ref=result.report_ref
    terminal=('PAUSED_DECISION' if report['outcome'] in {'awaiting_operator_evidence','eligible'} else
              'HALTED_CLIENT_TIMEOUT' if any(f['category']=='client_timeout' for f in report['failures']) else 'HALTED_ARTIFACT_INVALID')
    current=before_state;chain=service._chain()
    pointers={'mode':'enforce','capability_version':'preservation-bridge-v1','latest_proposal':report['proposal'],
              'latest_attempt_report':report_ref,'pending_acceptance_admission':None,'accepted':chain[-1][0] if chain else None,
              'pending_outcome':report['outcome'],'next_action':report['next_action']}
    current.update(current_round=round_number,phase=phase,active_profile=profile,current_draft_hash=draft_hash((root/'spec.md').read_bytes().decode()),
                   terminal_state=terminal,ready_for_phase_2=False,resumable=terminal=='HALTED_CLIENT_TIMEOUT',preservation_bridge=pointers)
    service._replace('rounds/run_state.json',json_bytes(current))
    # Pending evidence is an operator pause, never a validation retry trigger.
    if terminal!='PAUSED_DECISION':
        service._replace('rounds/artifact_validation_error.json',json_bytes({'terminal_state':terminal,'round_number':round_number,
            'phase':phase,'profile':profile,'client_role':'editor','failure_type':'client_timeout' if terminal=='HALTED_CLIENT_TIMEOUT' else 'preservation_violation',
            'last_valid_draft_hash':current['current_draft_hash'],'last_valid_draft_path':'./spec.md','report':report_ref,'automatic_retries':0}))
    raise BridgeHalt(terminal,report_ref)


def resume_context(root: Path, config: OrchestratorConfig):
    """Read-only validation of the narrow, typed Phase 1 Editor retry."""
    from dataclasses import replace
    require(config.preservation_bridge is not None, 'CONFIG_INVALID: guarded root cannot downgrade')
    status = readback(root, config)
    require(status['next_action'] == 'technical_resume',
            'preservation requires its local acceptance/repair operation, not an Editor retry')
    report = read_artifact(root, status['latest_attempt_report'], 'current_runtime_preservation_bridge_report')
    require(report['outcome'] == 'technical_failure' and
            [f['category'] for f in report['failures']] == ['client_timeout'], 'only typed Editor timeouts can resume')
    admission = read_artifact(root, report['admission'], 'preservation_bridge_proposal_admission')
    require(admission['origin'] in {'editor', 'supplied_revision'}, 'unsupported retry origin')
    directory = (Path(root)/report['admission']['path']).parent
    execution = decode_json((directory/'execution_started').read_bytes())
    require(execution['admission'] == report['admission'], 'retry execution admission mismatch')
    frozen = decode_json(read_ref(Path(root), execution['effective_config']))
    verify_frozen_round_state(state_packet(root), frozen['runtime']['state_before'])
    if execution.get('supplied_input') is not None:
        read_ref(Path(root), execution['supplied_input'])
    for ref in execution['reviewer_feedback']:
        read_ref(Path(root), ref)
    for mirror in execution['snapshots']:
        require(read_ref(Path(root), mirror['source']) == read_ref(Path(root), mirror['snapshot']), 'retry input snapshot changed')
    # Mutable canonical Reviewer storage cannot supply replacement resolution evidence.
    require(len(execution['reviewer_feedback']) == 1 or frozen['resolved_config']['review_mode'] == 'vertical', 'unsupported retry Reviewer topology')
    feedback = decode_json((Path(root)/f"rounds/round-{admission['round_number']}/reviewer_feedback.json").read_bytes())
    require(feedback == decode_json(read_ref(Path(root), execution['reviewer_feedback'][0])), 'retry Reviewer evidence changed')
    retry_config = replace(config, preservation_bridge=replace(config.preservation_bridge,
                            predecessor_report=status['latest_attempt_report']))
    guard_operation(root, retry_config, phase=admission['phase'], round_number=admission['round_number'], technical_resume=True)
    return retry_config, admission, directory


def resume_operation(root, config, *, continue_run=False, reviewer_client=None, editor_client=None, timeout_seconds=None):
    """Recover one frozen operation, then explicitly continue Phase 1 if requested."""
    from whetstone.live import LiveRoundRunner, create_editor_client
    from whetstone.resume import ResumeResult
    # Local acceptance remains separate; only --continue requests more rounds.
    from whetstone.preservation_continuation import resume_review, pending_review, continue_phase1
    review = pending_review(Path(root))
    # Proposal attempts take precedence over their already completed Reviewer stage.
    if review and list((Path(root)/f"rounds/round-{review['round_number']}/preservation").glob('attempt-*/admission.json')):
        review = None
    if review:
        return resume_review(root, config, review, continue_run=continue_run, reviewer_client=reviewer_client,
                             editor_client=editor_client, timeout_seconds=timeout_seconds)
    status = readback(Path(root), config)
    if status['pending_outcome'] is None and (status['accepted'] is not None or config.review_mode == 'vertical'):
        require(continue_run, 'accepted operation is complete; use --continue for ordinary review')
        return continue_phase1(root, config, reviewer_client=reviewer_client, editor_client=editor_client, timeout_seconds=timeout_seconds)
    retry_config, admission, directory = resume_context(root, config)
    runner = LiveRoundRunner(root, retry_config, reviewer_client=reviewer_client,
                             editor_client=editor_client, timeout_seconds=timeout_seconds)
    number, profile = admission['round_number'], admission['profile']
    try:
        execution = decode_json((directory/'execution_started').read_bytes())
        frozen = decode_json(read_ref(Path(root), execution['effective_config']))
        feedback = decode_json(read_ref(Path(root), execution['reviewer_feedback'][0]))
        editor = editor_client or create_editor_client(retry_config.editor, cwd=Path(root),
                                                      timeout_seconds=runner._timeout_for_role('editor'))
        supplied = read_ref(Path(root), execution['supplied_input']) if admission['origin'] == 'supplied_revision' else None
        run_proposal(runner, round_number=number, profile=profile, phase='phase_1',
                     prompt=frozen['editor_prompt'], feedback=feedback, editor=editor, supplied=supplied, apply=True,
                     client_attempt_number=(admission['client_attempt_number'] or 0)+1)
    except BridgeHalt as exc:
        state = state_packet(root)
        return ResumeResult(True, exc.terminal_state, number, 'phase_1', profile,
                            state['current_draft_hash'], state.get('last_accepted_draft_hash'), False)
    if continue_run:
        return continue_phase1(root, config, reviewer_client=reviewer_client, editor_client=editor_client, timeout_seconds=timeout_seconds)
    state = state_packet(root)
    return ResumeResult(True, state.get('terminal_state'), number, 'phase_1', profile,
                        state['current_draft_hash'], state.get('last_accepted_draft_hash'), False)


def guard_admission(root, *, round_number, phase, predecessor_report):
    service = acceptance_service(root)
    service._boundary()
    require(phase == 'phase_1', 'CONFIG_INVALID: guarded Phase 2 admission is not yet qualified')
    chain = service._chain()
    if chain:
        service._verify_mirrors(chain)
        service.verify_runtime_completion(chain)
        _, _, previous = service._proposal_directory(chain[-1][1]['proposal'])
        require(round_number > previous['round_number'], 'runtime round already committed')
    status = readback(root, include_reviews=False)
    if status['pending_outcome']:
        require(status['next_action'] == 'technical_resume' and predecessor_report == status['latest_attempt_report'],
                'pending operation must be completed before a new admission')
        report = read_artifact(root, predecessor_report, 'current_runtime_preservation_bridge_report')
        admission = read_artifact(root, report['admission'], 'preservation_bridge_proposal_admission')
        require(admission['round_number'] == round_number, 'technical retry must retain its original round')
