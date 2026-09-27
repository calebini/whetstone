"""Focused projections from immutable V review and promotion evidence."""
from copy import deepcopy
from datetime import datetime, timezone

from whetstone.vnext_contracts import canonical_json_bytes, decode_json, require
from whetstone.vnext_review_configuration import focused_profile

FAILURE_MIRROR = 'rounds/technical_failure_report.json'


def directory(proof, frames):
    return 'rounds/focused_phase1/' + proof.latest['hash'] + '-' + str(frames[-1].request.number)


def failure(proof, frames, progress, *, existing=None, generated_at=None):
    last = frames[-1]
    rows = last.review['feedback']['feedback'] if last.header['base_pointer'] == proof.latest else []
    def issues(severity):
        return [{key: deepcopy(row[key]) for key in ('issue_id', 'issue_fingerprint',
                 'normalized_severity', 'affected_sections', 'claim')}
                for row in rows if row['normalized_severity'] == severity]
    if existing is not None:
        retained = decode_json(existing)
        proof.reader.suite.registry.validate(retained, 'technical_failure_report')
        generated_at = retained['generated_at']
    stamp = generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    pointer = proof.pointers[-1]
    report = dict(terminal_state='PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS', generated_at=stamp,
        round_number=last.request.number, draft_hash=pointer['verified_draft_hash'],
        final_draft_path=pointer['verified_draft_path'], unresolved_blockers=issues('blocker'),
        unresolved_major_issues=issues('major'), unresolved_conflicts=[], unresolved_oscillation=None,
        last_accepted_draft_hash=None, current_draft_status='not_accepted', ready_for_phase_2=False,
        last_draft_hash=pointer['verified_draft_hash'], exit_reason='vnext_focused_profile_residuals',
        recommendation='manual_review_required', profile_status=dict(
            profiles=[dict(profile=p.profile, clean=p.clean, rounds_used=p.rounds_used,
                round_budget=p.round_budget, exhausted=p.exhausted,
                residual_status='exhausted_with_residuals' if p.exhausted else None, active=False) for p in progress],
            unverified_profiles=[p.profile for p in progress if not p.clean],
            exhausted_profiles=[p.profile for p in progress if p.exhausted], profiles_remaining=[],
            total_round_budget=sum(p.round_budget for p in progress)),
        last_reviewer_findings=dict(round_number=last.request.number, profile=last.request.profile,
            blocker_count=sum(r['normalized_severity'] == 'blocker' for r in last.review['feedback']['feedback']),
            major_count=sum(r['normalized_severity'] == 'major' for r in last.review['feedback']['feedback']),
            feedback_ids=[r['feedback_id'] for r in last.review['feedback']['feedback']]))
    proof.reader.suite.registry.validate(report, 'technical_failure_report')
    require(existing is None or existing == canonical_json_bytes(report), 'focused failure report conflicts with replay')
    return report


def round_assets(request, review=None):
    values = request.preflight.arguments
    from whetstone.vnext_verified_vertical_phase1 import enabled
    vertical = enabled(values['review'])
    if focused_profile(values['review']) is None and not vertical: return {}
    from whetstone.scheduler import REVIEW_PROFILE_DEFINITIONS
    prefix = f'rounds/round-{request.number}'
    raw = values['base']
    profile = REVIEW_PROFILE_DEFINITIONS[request.profile]
    # Full draft review plus conservative invalidation: pin all actual section IDs.
    metadata = dict(profile=request.profile, round_kind='review_only' if vertical else 'review_editor',
        focus=list(profile.focus), resolved_focus_anchors=[r['canonical_section_id'] for r in values['base_map']['sections']],
        focused=not vertical)
    assets = {prefix+'/draft_before.md': raw, prefix+'/profile_used.yaml': canonical_json_bytes(metadata),
        prefix+'/prompt_snapshot.json': canonical_json_bytes(dict(request_id=request.id,
            input_hash=request.preflight.input_hash, base_pointer=values['base_pointer_ref'],
            original_prompt_path=request.directory+'/original_prompt.txt'))}
    if vertical:
        assets[prefix+'/context_snapshot.json'] = canonical_json_bytes(values['context'])
    if review is not None and (vertical or not any(row['classification'] != 'deferable' for row in review['findings'])):
        digest = review['feedback']['draft_hash']
        summary = dict(round_number=request.number, draft_before_hash=digest, draft_after_hash=digest,
            accepted_feedback_ids=[], modified_feedback_ids=[], declined_feedback=[], created_conflict_ids=[],
            resolved_issue_ids=[], unresolved_issue_ids=[r['issue_id'] for r in review['feedback']['feedback']])
        request.schemas.validate(summary, 'editor_summary')
        assets.update({prefix+'/draft_after.md': raw, prefix+'/editor_summary.json': canonical_json_bytes(summary)})
    return assets
