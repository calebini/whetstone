"""Read-only proof of guarded convergence for declaration and apply-back consumers."""
from pathlib import Path

from whetstone.declaration import render_convergence_declaration
from whetstone.hashing import draft_hash
from whetstone.preservation_contracts import decode_json, read_ref, require


def verify_convergence(root, *, declaration_required=False):
    """Reconstruct verification on accepted bytes; terminal flags confer no authority."""
    from whetstone.preservation_runtime import acceptance_service, guard_consumer, state_packet
    from whetstone.preservation_phase2_closeout import PREFIX, admission, schedule
    from whetstone.preservation_continuation import verify_review_receipt
    from whetstone.live_phase2 import CONVERGENCE_ACCEPTANCE_PROFILES
    from whetstone.evaluation import target_matrix_satisfied

    root = Path(root)
    guard_consumer(root)
    service = acceptance_service(root)
    chain = service._chain()
    _, proposal, last = service._proposal_directory(chain[-1][1]['proposal'])
    require(last['phase'] == 'phase_2', 'convergence requires verified Phase 2 authority')
    frozen = decode_json(read_ref(root, proposal['normal_round_evidence']['effective_config']))
    config = frozen['resolved_config']
    refs = [ref for ref, _, _ in chain]
    scheduler, clean, number, base = schedule(root, refs, config, require_exhausted=False)
    manifest = frozen.get('rubric_manifest_packet')
    require(isinstance(manifest, dict), 'Phase 2 verification lacks its frozen rubric identity')
    issues = chain[-1][2]
    if (root/PREFIX/'admission.json').exists():
        packet, _, admitted_base = admission(root)
        require(packet['acceptances'] == refs and packet['residuals'] == issues and admitted_base == base,
                'convergence closeout lineage differs')
        admitted_manifest = decode_json(read_ref(root, packet['rubric_manifest']))
        require(_identity(admitted_manifest) == _identity(manifest), 'closeout rubric identity changed')
        for index, profile in enumerate(packet['profiles']):
            number = packet['start_round']+index
            path = root/f'rounds/round-{number}/preservation/review_complete.json'
            require(path.is_file(), 'convergence requires every bounded closeout review')
            review, _, _, _, issues = verify_review_receipt(root, number)
            require(review['profile'] == profile and review['accepted'] == refs[-1], 'closeout verification differs')
            require(not any(i.get('normalized_severity') in {'blocker','major'} for i in issues),
                    'serious closeout findings prevent convergence')
            clean.add(profile)
    else:
        require(last['profile'] in CONVERGENCE_ACCEPTANCE_PROFILES,
                'convergence requires a final acceptance profile')
    require({step.profile for step in scheduler.steps} <= clean,
            'convergence requires every Phase 2 profile clean on accepted bytes')
    state = state_packet(root)
    require(state.get('phase') == 'phase_2' and state.get('current_round') == number
            and state.get('current_draft_hash') == draft_hash(base.decode()), 'convergence state differs from verified rounds')
    target = config['convergence']
    require(target_matrix_satisfied(target_phase=target['target_phase'], target_mode=target['target_mode'],
            issues=issues, unresolved_rubric_gaps=[], declaration_accepted=True), 'convergence target remains unsatisfied')
    current_manifest = root/'rounds/rubric_manifest.json'
    require(current_manifest.is_file() and _identity(decode_json(current_manifest.read_bytes())) == _identity(manifest),
            'convergence rubric manifest changed')
    declaration = render_convergence_declaration(target_phase=target['target_phase'], target_mode=target['target_mode'],
        workflow=manifest['workflow'], rubric_profile=manifest['rubric_profile'], rubric_source=manifest['rubric_source'],
        rubric_label=manifest['rubric_label'], rubric_manifest_path='rounds/rubric_manifest.json',
        final_draft_hash=draft_hash(base.decode()), rubric_content_hash=manifest['rubric_content_hash'],
        unresolved_blockers_count=0, unresolved_major_issues_count=0, unresolved_rubric_gaps_count=0,
        reviewer_final_status='accepted', declaration_status='accepted')
    if declaration_required:
        if (root/PREFIX/'admission.json').exists():
            from whetstone.preservation_phase2_closeout import verify_completion
            verify_completion(root, packet, config['declaration_path'])
        path = Path(config['declaration_path'])
        require(path.is_file() and path.read_bytes() == declaration.encode(),
                'convergence declaration differs from accepted verification')
    return declaration


def _identity(packet):
    return {key:value for key,value in packet.items() if key != 'generated_at'}
