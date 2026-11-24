"""Versioned review obligations, independent of candidate promotion mechanics."""
from copy import deepcopy

from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes

POLICY = 'scope-aware-phase1-v1'
ALGORITHM = 'algorithms/vnext_phase1_completion_policy_v1.md'
DECISIONS = frozenset({'operator_decision_required', 'scope_change', 'authority_conflict'})


def enabled(review):
    return review.get('schema_version') == 'review-configuration-v3' and review.get('completion_policy') == POLICY


def pins(suite):
    entries = {r['path']: r['sha256'] for family in ('algorithms', 'schemas') for r in suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/review_configuration_v3.schema.json',
                 'schemas/vnext_verified_phase1_closeout_v5.schema.json'):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'shared Phase 1 completion contract is absent or changed', path)


def validate_selection(review):
    """Capability admission only; the obligation evaluator below has no preset branches."""
    from whetstone.scheduler import profile_names_for_phase
    require(review['workflow'] in {'standard', 'mvp'}, 'unsupported shared Phase 1 workflow')
    require(review['profile_set'] in {'stateful_system', 'balanced_mvp', 'utility_mvp'},
            'unsupported shared Phase 1 profile set')
    require(review['review_mode'] in {'horizontal', 'vertical'}, 'unsupported shared Phase 1 route')
    names = [p['name'] for p in review['profiles']]
    require(bool(names) and len(names) == len(set(names)) and all(p['budget'] > 0 for p in review['profiles']),
            'Phase 1 profiles must be unique, nonempty and positively budgeted')
    allowed = profile_names_for_phase(review['profile_set'], 'phase_1')
    require(all(name in allowed for name in names), 'profile is outside selected Phase 1 set')


def classify_obligations(feedback, advice, findings, evidence, scope, invariants):
    """Refine canonical classifications; never let advisory deferral override authority."""
    hints = {r['feedback_id']: r for r in (advice or {}).get('findings', [])}
    surfaces = {s['id']: s for s in (scope or {}).get('scope_surfaces', [])}
    approved = bool(scope and scope['status'] == 'approved' and scope['approval']['approved'])
    protected = {a['assertion_id'] for a in invariants['assertions'] if a['severity'] == 'blocking'}
    priority = {'editor_fixable': 0, 'deferable': 1, 'operator_decision_required': 2,
                'scope_change': 3, 'authority_conflict': 4}
    for finding in findings:
        detail = evidence[finding['finding_id']]
        items = detail['source_items']
        proposed = [hints.get(item['feedback_id']) for item in items]
        reasons = set(detail['reasons'])
        invariant_conflict = any(item['invariant_violated'] in protected for item in items)
        if invariant_conflict:
            finding['classification'] = 'authority_conflict'
            detail['requires_new_job'] = True
            reasons.add('blocking_invariant_conflicts_with_completion')
        for hint in proposed:
            if hint and hint['classification'] in DECISIONS:
                finding['classification'] = max((finding['classification'], hint['classification']), key=priority.get)
                reasons.add('explicit_decision_prevents_deferral')
            if hint and set(hint['requested_effects']) & {'scope_change', 'authority_change'}:
                finding['classification'] = max((finding['classification'], 'operator_decision_required'), key=priority.get)
                reasons.add('scope_or_authority_effect_prevents_deferral')
        # The legacy classifier retains evidence even where deferred-surface advice
        # overwrote an earlier conflict. Such evidence cannot justify completion.
        authority_conflicts = reasons & {'non_normative_requirement_source', 'source_outside_declared_authority_scope',
            'blocking_invariant_conflicts_with_deferral', 'immutable_section_invariant', 'compatibility_policy_forbidden'}
        scope_conflicts = reasons & {'unknown_target_anchor', 'authority_scope_outside_target', 'unresolved_scope_surface', 'out_of_scope_surface'}
        if authority_conflicts: finding['classification'] = 'authority_conflict'
        elif scope_conflicts:
            finding['classification'] = max((finding['classification'], 'scope_change'), key=priority.get)
        conflicts = reasons - {'deferred_scope_surface'}
        valid = (approved and not conflicts and not detail['requires_new_job']
                 and finding['classification'] == 'deferable'
                 and all(h and h['classification'] == 'deferable' and h['scope_surface_ids']
                         and all(s in surfaces and surfaces[s]['status'] == 'deferred' for s in h['scope_surface_ids'])
                         for h in proposed))
        if valid:
            reasons.add('approved_scope_deferral')
        elif finding['classification'] == 'deferable' and (
                any(i['normalized_severity'] in {'major', 'blocker'} for i in items) or conflicts):
            finding['classification'] = 'operator_decision_required'
            reasons.add('unjustified_deferral_requires_decision')
        detail['reasons'] = sorted(reasons)


def dispositions(review_result):
    """Return source feedback rows and their canonical completion disposition."""
    records = {source: f for f in review_result['findings'] for source in f['source_feedback_ids']}
    for row in review_result['feedback']['feedback']:
        finding = records[row['feedback_id']]
        detail = review_result['evidence'][finding['finding_id']]
        deferred = (finding['classification'] == 'deferable'
                    and 'approved_scope_deferral' in detail['reasons'])
        blocking = finding['classification'] in DECISIONS or (
            row['normalized_severity'] in {'major', 'blocker'} and not deferred)
        yield row, deferred, blocking


def blocking_rows(review, result, *, global_acceptance=False):
    if enabled(review):
        return [row for row, _, blocking in dispositions(result) if blocking]
    return [row for row in result['feedback']['feedback']
            if row['normalized_severity'] in {'major', 'blocker'} and (global_acceptance or row['in_scope'])]


def requires_work(review, result):
    """Optional-only reviews need no edit; blocking rounds may also admit minor fixes."""
    if enabled(review): return bool(blocking_rows(review, result))
    return any(row['classification'] != 'deferable' for row in result['findings'])


def deferred_rows(frames):
    result = []
    for frame in frames:
        hints = {h['feedback_id']: h for h in frame.review['advice']['findings']}
        for row, deferred, _ in dispositions(frame.review):
            if deferred:
                result.append(dict(round_number=frame.request.number, profile=frame.request.profile,
                    feedback_id=row['feedback_id'], severity=row['normalized_severity'],
                    scope_surface_ids=deepcopy(hints[row['feedback_id']]['scope_surface_ids'])))
    return result


def closeout_schema(review):
    return 'vnext_verified_phase1_closeout_v5' if enabled(review) else 'vnext_verified_phase1_closeout_v4'


GUIDANCE = '''\nShared Phase 1 completion policy:
The approved scope contract governs this review, regardless of workflow or lens.
A major/blocker outside your lens's focus still counts when it is a job obligation.
Use deferable advice only for explicitly deferred scope surfaces that have no
conflicting in-scope dependency, authority decision or protected invariant.
Cite every applicable scope_surface_id. Mixed in-scope/deferred surfaces cannot
justify deferral. A bare in_scope=false flag cannot discharge an obligation.
If deferred work is necessary for an in-scope core flow, report scope_change or
operator_decision_required advice and explain the dependency. Never silently
expand scope or waive a protected requirement. Keep approved deferred work visible.
'''
