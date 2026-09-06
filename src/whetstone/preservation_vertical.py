"""First-cycle vertical preservation bindings; later-cycle replay remains gated."""
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
    require(all(p['round_number'] == i for i, p in enumerate(sources, 1)) and admission['round_number'] == len(sources)+1,
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
    require(number == len(profiles)+1 and len(refs) == len(profiles) and len(feedback_refs) == len(profiles)+1,
            'unsupported vertical cycle or incomplete source topology')
    packets = []
    for index, (profile, ref) in enumerate(zip(profiles, refs), 1):
        read_ref(root, ref)
        require(ref['path'] == f'rounds/round-{index}/preservation/review_complete.json', 'vertical source receipt path mismatch')
        packet, config, feedback, _, _ = verify_review_receipt(root, index)
        require(packet['kind'] == 'vertical_source' and packet['profile'] == profile and packet['accepted'] is None,
                'vertical source identity differs')
        original = deepcopy(config['resolved_config'])
        current = deepcopy(resolved)
        original['preservation_bridge'].pop('predecessor_report', None)
        current['preservation_bridge'].pop('predecessor_report', None)
        require(original == current and config['scope_contract_packet'] == frozen['scope_contract_packet'],
                'vertical source configuration changed')
        require(decode_json(read_ref(root, feedback_refs[index])) == feedback, 'retained vertical source differs')
        packets.append(feedback)
    merged = decode_json(read_ref(root, feedback_refs[0]))
    require(merged == merge_feedback(packets, number, packets[0]['draft_hash']), 'vertical merged feedback differs from source receipts')
    return packets


def source_bindings(root, config, number):
    from whetstone.preservation_runtime import acceptance_service
    from whetstone.preservation_continuation import verify_review_receipt
    profiles = profile_names_for_phase(config.review_profile_set, 'phase_1')
    require(number == len(profiles)+1, 'vertical continuation beyond the first cycle is not yet qualified')
    service = acceptance_service(root)
    receipts, feedback = [], []
    for index in range(1, number):
        verify_review_receipt(root, index)
        receipt_ref = service.reference(f'rounds/round-{index}/preservation/review_complete.json')
        receipt = decode_json(read_ref(Path(root), receipt_ref))
        result = decode_json(read_ref(Path(root), receipt['result']))
        receipts.append(receipt_ref); feedback.append(result['feedback'])
    return receipts, feedback


def guard_source(root, config, *, round_number, profile, phase, overwrite, resume):
    from whetstone import preservation_runtime as rt
    root = Path(root)
    require(phase == 'phase_1' and not overwrite, 'vertical source reviews require Phase 1 without overwrite')
    require(not resume, 'vertical Reviewer recovery is not yet qualified')
    require(not rt.acceptance_service(root)._chain(), 'vertical continuation beyond the first cycle is not yet qualified')
    profiles = profile_names_for_phase(config.review_profile_set, 'phase_1')
    require(1 <= round_number <= len(profiles) and profile == profiles[round_number-1], 'vertical source review is out of order')
    rt.guard_operation(root, config, phase=phase, round_number=round_number)
    from whetstone.preservation_continuation import verify_review_receipt
    for previous in range(1, round_number):
        packet, frozen, _, _, _ = verify_review_receipt(root, previous)
        require(packet['kind'] == 'vertical_source' and packet['profile'] == profiles[previous-1], 'vertical source topology changed')
        require(frozen['resolved_config'] == rt._jsonable(asdict(config)), 'vertical source configuration changed')
    require(not (root/f'rounds/round-{round_number}').exists(), 'vertical source round already exists')


def verify_seed_review(root, packet, frozen):
    require(packet['kind'] == 'vertical_source' and packet['accepted'] is None, 'source review must observe the admitted seed')
    config = frozen['resolved_config']
    require(config['review_mode'] == 'vertical', 'source review mode differs')
    profiles = profile_names_for_phase(config['review_profile_set'], 'phase_1')
    number = packet['round_number']
    require(1 <= number <= len(profiles) and packet['profile'] == profiles[number-1], 'source review profile/round differs')
    surface = validate_surface_bindings(Path(root), config['preservation_bridge']['allowed_change_surface'])
    require(read_ref(Path(root), packet['base']) == surface.base and frozen['scope_contract_packet'] == decode_json(read_ref(Path(root), surface.surface['scope_contract'])),
            'source review differs from admitted seed/scope')


def prepare_consolidated(runner, number, feedback, base):
    """Validate the complete review topology before any consolidated round writes."""
    from whetstone import preservation_runtime as rt
    rt.guard_operation(runner.root, runner.config, phase='phase_1', round_number=number)
    source_bindings(runner.root, runner.config, number)
    from whetstone.preservation_continuation import verify_review_receipt
    packets = [verify_review_receipt(runner.root, i)[2] for i in range(1, number)]
    require(feedback == merge_feedback(packets, number, draft_hash(base)), 'consolidated feedback differs from source reviews')
    directory = runner.store.begin_round(number)
    runner.store.write_round_text(number, 'draft_before.md', base)
    runner.store.write_round_json(number, 'profile_used.yaml', {'profile':'vertical','round_kind':'consolidated_editor'})
    runner.store.write_round_json(number, 'reviewer_feedback.json', feedback)
    return directory


def completed_cycle_plan(root, config):
    """Only an accepted all-empty initial sweep can complete in this checkpoint."""
    from whetstone import preservation_runtime as rt
    from whetstone.resume import ResumePlan
    root = Path(root)
    rt.guard_consumer(root, config)
    chain = rt.acceptance_service(root)._chain()
    require(len(chain) == 1 and chain[0][1]['accepted_noop'], 'vertical scheduler continuation is not yet qualified')
    _, marker, issues = chain[0]
    service = rt.acceptance_service(root)
    _, proposal, admission = service._proposal_directory(marker['proposal'])
    normal = proposal['normal_round_evidence']
    frozen = decode_json(read_ref(root, normal['effective_config']))
    packets = verify_sources(root, frozen, admission['round_number'], normal['reviewer_feedback'])
    require(all(not p['feedback'] for p in packets) and not issues, 'vertical verification continuation is not yet qualified')
    require(rt._jsonable(asdict(config)) == frozen['resolved_config'], 'vertical completion configuration changed')
    state = rt.state_packet(root)
    require(state.get('terminal_state') == 'PHASE_1_STABLE' and state.get('current_round') == admission['round_number']
            and state.get('current_draft_hash') == marker['materialized_draft_hash'], 'vertical completion state is incomplete')
    seed = frozen['runtime']['state_before']
    for key in ('review_profile_budgets','review_round_budget','run_mode','effective_run_config'):
        require(state.get(key) == seed.get(key), 'vertical scheduler completion mirror changed')
    return ResumePlan(False, 'PHASE_1_STABLE', 'accepted_round_continuation', 'phase_1', 'orchestrator',
                      admission['round_number'], '', marker['materialized_draft_hash'], marker['materialized_draft_hash'],
                      0, True, None, 'The accepted initial vertical sweep is complete')
