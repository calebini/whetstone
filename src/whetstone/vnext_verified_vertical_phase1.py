"""Pinned vertical V scheduling and deterministic consolidation over original journals."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import re

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_verified_history import _snapshot

ALGORITHM = 'algorithms/vnext_verified_vertical_phase1_v1.md'
MERGER = dict(name='whetstone-vertical-merge', version='1.0', model='orchestrator')


def enabled(review):
    return review['review_mode'] == 'vertical'


def pins(suite):
    entries = {r['path']: r['sha256'] for family in ('algorithms', 'schemas') for r in suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/vnext_vertical_merge_v1.schema.json',
                 'schemas/vnext_verified_phase1_closeout_v3.schema.json',
                 'schemas/technical_failure_report.schema.json', 'schemas/editor_summary.schema.json'):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'vertical Phase 1 contract is absent or changed', path)


def ref(path, value):
    return dict(path=path, hash=sha256_bytes(canonical_json_bytes(value)))


def merge_packets(packets, number):
    """Pure stable source ordering, exact issue identities and collision provenance."""
    ids = [r['feedback_id'] for p in packets for r in p['feedback']['feedback']]
    rewrite = len(ids) != len(set(ids))
    occurrences, used, rows, hints, provenance = Counter(), set(), [], [], []
    for packet in packets:
        feedback, advice = packet['feedback'], packet['advice']
        by_id = {r['feedback_id']: r for r in advice['findings']}
        for row in feedback['feedback']:
            original = row['feedback_id']
            slug = re.sub('[^a-z0-9]+', '-', feedback['profile'].lower()).strip('-')
            stem = slug + ':' + original if rewrite else original
            occurrences[stem] += 1
            identifier = stem if occurrences[stem] == 1 else stem + ':' + str(occurrences[stem])
            # Include literal suffix-shaped source IDs in the same collision space.
            while identifier in used:
                occurrences[stem] += 1
                identifier = stem + ':' + str(occurrences[stem])
            used.add(identifier)
            rows.append({**deepcopy(row), 'feedback_id': identifier})
            hints.append({**deepcopy(by_id[original]), 'feedback_id': identifier})
            provenance.append(dict(feedback_id=identifier, source_profile=feedback['profile'],
                original_feedback_id=original, source_round=feedback['round_number']))
    feedback = dict(round_number=number, profile='vertical', reviewer=deepcopy(MERGER),
                    draft_hash=packets[0]['feedback']['draft_hash'], feedback=rows)
    advice = {**deepcopy(packets[0]['advice']),
              'feedback': ref(f'rounds/round-{number}/reviewer_feedback.json', feedback), 'findings': hints}
    return feedback, advice, provenance


def merge(proof, cycle, number):
    feedback, advice, provenance = merge_packets([f.review for f in cycle], number)
    prefix = f'rounds/round-{number}'
    packet = dict(schema_version='vnext-vertical-merge-v1', job_id=proof.seed_values['job']['job_id'],
        round_number=number, base_pointer=deepcopy(cycle[0].header['base_pointer']),
        review_configuration=deepcopy(proof.owner.run._record['review_configuration']),
        sources=[dict(round_number=f.request.number, profile=f.request.profile,
            receipt=ref(f.request.directory+'/result.json', f.receipt),
            feedback=deepcopy(f.receipt['feedback']), advice=deepcopy(f.receipt['advice'])) for f in cycle],
        feedback=ref(prefix+'/reviewer_feedback.json', feedback),
        advice=ref(prefix+'/finding_advice.json', advice), provenance=provenance)
    proof.reader.suite.registry.validate(packet, 'vnext_vertical_merge_v1')
    values = proof.values(packet['base_pointer'])
    from whetstone.vnext_classification import classify_feedback
    findings, evidence = classify_feedback(feedback=feedback, feedback_ref=packet['feedback'], advice=advice,
        job=values['job'], authority=values['authority'], invariants=values['invariants'],
        base=values['base'], section_map=values['base_map'], scope=values['scope'], review=values['review'])
    from whetstone.vnext_phase1_policy import requires_work
    actionable = requires_work(values['review'], dict(feedback=feedback, findings=findings, evidence=evidence))
    assets = {packet['feedback']['path']: canonical_json_bytes(feedback),
              packet['advice']['path']: canonical_json_bytes(advice), prefix+'/draft_before.md': values['base'],
              prefix+'/profile_used.yaml': canonical_json_bytes(dict(profile='vertical', round_kind='consolidated_editor'))}
    if not actionable:
        digest = feedback['draft_hash']
        summary = dict(round_number=number, draft_before_hash=digest, draft_after_hash=digest,
            accepted_feedback_ids=[], modified_feedback_ids=[], declined_feedback=[], created_conflict_ids=[],
            resolved_issue_ids=[], unresolved_issue_ids=[r['issue_id'] for r in feedback['feedback']])
        proof.reader.suite.registry.validate(summary, 'editor_summary')
        assets.update({prefix+'/draft_after.md': values['base'], prefix+'/editor_summary.json': canonical_json_bytes(summary)})
    assets[prefix+'/vertical_merge.json'] = canonical_json_bytes(packet)  # commit last
    present = False
    for path, raw in assets.items():
        try: stored = proof.store.read(path)
        except FileNotFoundError: stored = None
        require(stored is None or stored == raw, 'vertical merge conflicts with source replay', path)
        if path.endswith('/vertical_merge.json'): present = stored is not None
    if present:
        require(all(proof.store.read(p) == raw for p, raw in assets.items()), 'committed vertical merge lacks a source')
    return packet, assets, actionable, present


@dataclass(frozen=True)
class VerticalSequence:
    frames: tuple
    gate: str
    profile: str | None
    number: int
    merges: tuple


def sequence(proof, *, through_round=None):
    from whetstone.vnext_verified_review import _contract
    from whetstone.vnext_verified_review_requests import _read_review_prefix
    profiles = _contract(proof)
    from whetstone.vnext_verified_phase1_budget import Timeline
    timeline = Timeline(proof, profiles, through_round=through_round)
    profiles = timeline.profiles
    frames = _read_review_prefix(proof, through_round=through_round, require_complete=through_round is not None)
    counts = {r['name']: 0 for r in profiles}
    clean = dict.fromkeys(counts, False)
    base, cursor, number, merges = _snapshot(proof.pointers[0]), 0, 1, []

    def done(gate, profile=None):
        timeline.finish()
        require(cursor == len(frames), 'vertical journal continues beyond its eligible boundary')
        require(through_round is None, 'selected round is not a completed vertical consolidation')
        require(base == proof.latest, 'vertical reviews do not explain the current promotion')
        return VerticalSequence(frames, gate, profile, number, tuple(merges))

    while True:
        timeline.advance(number, counts, clean, base, frames[:cursor], merges)
        eligible = [p for p in profiles if counts[p['name']] < p['budget']]
        if not eligible: return done('review_complete' if all(clean.values()) else 'budget_exhausted')
        cycle = []
        for profile in eligible:
            name = profile['name']
            if cursor == len(frames): return done('review', name)
            frame = frames[cursor]
            require(frame.request.number == number and frame.request.profile == name
                    and frame.header['base_pointer'] == base, 'vertical review differs from eligible round/profile/base')
            cursor += 1
            if frame.receipt is None: return done('pending', name)
            cycle.append(frame)
            counts[name] += 1
            from whetstone.vnext_phase1_policy import blocking_rows
            clean[name] = not blocking_rows(proof.seed_values['review'], frame.review)
            number += 1
        if any(f.review['feedback']['feedback'] for f in cycle):
            packet, assets, actionable, present = merge(proof, cycle, number)
            merges.append((packet, assets, actionable, present))
            if through_round == number:
                timeline.finish()
                require(present and actionable, 'vertical proposal lacks its committed actionable merge')
                require(cursor == len(frames), 'vertical bounded replay includes later reviews')
                return VerticalSequence(frames, 'finding_admission', 'vertical', number, tuple(merges))
            if not present: return done('finding_admission' if actionable else 'merge_required', 'vertical')
            if actionable:
                old = proof.reader.json(base, 'current_verified_pointer_v1')
                ordinal = old['promotion_ordinal'] + 1
                if ordinal >= len(proof.pointers): return done('finding_admission', 'vertical')
                pointer = proof.pointers[ordinal]
                require(pointer['previous_verified_pointer_path'] == base['path']
                        and pointer['previous_verified_pointer_hash'] == base['hash'], 'vertical promotion predecessor changed')
                creation = proof.reader.json(dict(path=pointer['source_candidate_creation_event_path'],
                    hash=pointer['source_candidate_creation_event_hash']), 'candidate_creation_event_v1')
                require(creation['round_number'] == number, 'vertical promotion belongs to another consolidated round')
                base = _snapshot(pointer)
                clean = dict.fromkeys(clean, False)
            number += 1
        if all(clean.values()): return done('review_complete')


def synchronize(store, proof, state):
    from whetstone.vnext_verified_review_requests import _ReviewInputs, _VerifiedReviewRequest
    for frame in state.frames:
        if frame.receipt is None: break
        request = _VerifiedReviewRequest(_ReviewInputs(store, proof, frame.header['base_pointer']),
                                        frame.request.number, frame.request.profile)
        request.synchronize(store._token, frame.header, frame.outcomes)
        request.finish(store._token, frame.review)
    for packet, assets, _, present in state.merges:
        if present:
            proof.guard(store.read)
            for path, raw in assets.items(): store.publish(store._token, path, raw)


def context(reader, number, *, review, job, base_pointer):
    """Read bound source packets; history separately proves the eligible cycle."""
    pins(reader.suite)
    path = f'rounds/round-{number}/vertical_merge.json'
    raw = reader._read_path(path)
    packet = reader.json(dict(path=path, hash=sha256_bytes(raw)), 'vnext_vertical_merge_v1')
    require(packet['job_id'] == job['job_id'] and packet['round_number'] == number
            and packet['base_pointer'] == base_pointer
            and packet['review_configuration']['hash'] == job['review_configuration_hash'],
            'vertical Editor context bindings changed')
    sources = []
    for source in packet['sources']:
        receipt = reader.json(source['receipt'], 'vnext_review_result_v1')
        require(all(receipt[k] == source[k] for k in ('feedback', 'advice')), 'vertical source receipt changed')
        sources.append(dict(feedback=reader.json(source['feedback'], 'reviewer_feedback'),
                            advice=reader.json(source['advice'], 'vnext_finding_advice_v1')))
    return dict(merge=packet, sources=sources)


def validate_context(value, *, suite, job, review, feedback, advice, base_pointer):
    pins(suite)
    from whetstone.vnext_phase1_policy import enabled as shared_policy
    require(job['editing_mode'] == 'verified_promotion' and enabled(review)
            and (shared_policy(review) or review['workflow'] == 'standard'), 'vertical Editor requires standard V configuration')
    packet, sources = value['merge'], value['sources']
    suite.registry.validate(packet, 'vnext_vertical_merge_v1')
    require(packet['job_id'] == job['job_id'] and packet['base_pointer'] == base_pointer
            and packet['review_configuration']['hash'] == job['review_configuration_hash'],
            'vertical preflight bindings changed')
    require(len(sources) == len(packet['sources']) and bool(sources), 'vertical source coverage changed')
    names = [p['name'] for p in review['profiles']]
    previous = -1
    for source, refs in zip(sources, packet['sources']):
        row = source['feedback']
        require(row['profile'] in names and names.index(row['profile']) > previous,
                'vertical sources are not in configured profile order')
        previous = names.index(row['profile'])
        require(row['round_number'] == refs['round_number'] and row['profile'] == refs['profile']
                and row['draft_hash'] == feedback['draft_hash'] and row['reviewer'] == review['reviewer'],
                'vertical source identity changed')
        for key in ('feedback', 'advice'):
            require(ref(refs[key]['path'], source[key]) == refs[key], 'vertical source hash changed')
    merged, hints, provenance = merge_packets(sources, packet['round_number'])
    require(feedback == merged and advice == hints and packet['provenance'] == provenance
            and packet['feedback'] == ref(f"rounds/round-{packet['round_number']}/reviewer_feedback.json", feedback)
            and packet['advice'] == ref(f"rounds/round-{packet['round_number']}/finding_advice.json", advice),
            'vertical merge or provenance differs from original sources')


def validate_round(proof, number, record):
    state = sequence(proof, through_round=number)
    packet = state.merges[-1][0]
    require(record['base_pointer'] == packet['base_pointer']
            and record['feedback'] == packet['feedback'] and record['advice'] == packet['advice'],
            'vertical round differs from committed consolidation')


def publish_merge(store, proof, state):
    synchronize(store, proof, state)
    packet, assets, _, _ = state.merges[-1]
    proof.guard(store.read)
    for path, raw in assets.items(): store.publish(store._token, path, raw)
    proof.guard(store.read)
    store._check()
    return packet


def completed_round(state):
    return max([f.request.number for f in state.frames if f.receipt is not None]
               + [m[0]['round_number'] for m in state.merges if m[3]])


def failure(proof, frames, progress, *, existing=None, generated_at=None):
    from whetstone.vnext_verified_focused_phase1 import failure as focused_failure
    from whetstone.vnext_contracts import decode_json
    stamp = decode_json(existing)['generated_at'] if existing is not None else generated_at
    report = focused_failure(proof, frames, progress, generated_at=stamp)
    current = {f.request.profile: f for f in frames if f.receipt is not None and f.header['base_pointer'] == proof.latest}
    from whetstone.vnext_phase1_policy import enabled as shared_policy, blocking_rows
    rows = [r for f in current.values() for r in (blocking_rows(proof.seed_values['review'], f.review)
            if shared_policy(proof.seed_values['review']) else f.review['feedback']['feedback'])]
    for key, severity in [('unresolved_blockers', 'blocker'), ('unresolved_major_issues', 'major')]:
        report[key] = [{k: deepcopy(r[k]) for k in ('issue_id','issue_fingerprint','normalized_severity','affected_sections','claim')}
                       for r in rows if r['normalized_severity'] == severity]
    report.update(round_number=completed_round(sequence(proof)),
        terminal_state='TARGET_NOT_REACHED', exit_reason=(
        'vnext_vertical_global_acceptance_not_established' if all(p.clean for p in progress)
        else 'vnext_vertical_review_budget_exhausted'))
    report['profile_status']['total_round_budget'] += max(p.round_budget for p in progress)
    proof.reader.suite.registry.validate(report, 'technical_failure_report')
    require(existing is None or existing == canonical_json_bytes(report), 'vertical failure report conflicts with replay')
    return report
