"""Read-only horizontal scheduler progress on proven V authority.

This projection is not an accepted-draft decision, phase terminal, resume grant
or Phase 2 admission. Mutating owners still select work under their own fence.
"""
from copy import deepcopy

from whetstone.vnext_review_configuration import focused_profile
from dataclasses import dataclass

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_verified_review import VerifiedReview, _contract, _sequence
from whetstone.vnext_verified_work import VerifiedWork


ALGORITHM = 'algorithms/vnext_verified_phase1_status_v1.md'


@dataclass(frozen=True)
class ProfileProgress:
    profile: str
    round_budget: int
    rounds_used: int
    clean: bool
    exhausted: bool
    last_completed_round: int | None
    clean_base_pointer: dict | None
    clean_review_receipt: dict | None


@dataclass(frozen=True)
class VerifiedPhase1Status:
    current_pointer: dict
    work_outcome: str
    latest_candidate: dict | None
    promotion_candidate: dict | None
    pending_paths: tuple
    # None means withheld behind materialization, not an empty journal.
    orphan_directories: tuple | None
    profiles: tuple[ProfileProgress, ...] | None
    review_gate: str | None
    selected_profile: str | None
    review_round: int | None
    pending_review_attempts: int | None
    all_profiles_clean: bool | None
    focused_profile: str | None = None
    focused_profile_clean: bool | None = None


def _profiles(proof, profiles, frames):
    progress = []
    for profile in profiles:
        completed = [frame for frame in frames
                     if frame.request.profile == profile['name'] and frame.receipt is not None]
        latest = completed[-1] if completed else None
        clean = bool(latest is not None and latest.header['base_pointer'] == proof.latest
                     and not any(row['in_scope'] and row['normalized_severity'] in {'major', 'blocker'}
                                 for row in latest.review['feedback']['feedback']))
        receipt = (dict(path=latest.request.directory + '/result.json',
                        hash=sha256_bytes(canonical_json_bytes(latest.receipt))) if clean else None)
        progress.append(ProfileProgress(profile['name'], profile['budget'], len(completed), clean,
            not clean and len(completed) >= profile['budget'], latest.request.number if latest else None,
            deepcopy(proof.latest) if clean else None, receipt))
    return tuple(progress)


def inspect_verified_phase1(run):
    owner = VerifiedReview(run)
    proof = owner._proof(run.store.read)
    entries = {row['path']: row for row in proof.reader.suite.manifest['algorithms']}
    require(ALGORITHM in entries, 'verified Phase 1 status algorithm is outside supported suite')
    require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
            'installed verified Phase 1 status differs from pinned suite')
    # Inspect committed materialization before unrelated future Reviewer claims.
    # The subsequent _sequence replay supplies the same runtime sequence checks
    # as VerifiedReview._observe, without replaying that sequence twice.
    work = VerifiedWork._observe(owner, proof)
    profiles = gate = selected = number = attempts = clean = orphans = None
    if work.outcome != 'materialization_required':
        frames, gate, selected = _sequence(proof)
        profiles = _profiles(proof, _contract(proof), frames)
        orphans = tuple(proof.view.orphans)
        clean = all(row.clean for row in profiles)
        if gate == 'review': number = len(frames) + 1
        elif gate in {'pending', 'finding_admission'}: number = frames[-1].request.number
        if gate == 'pending': attempts = len(frames[-1].outcomes)
    proof.guard(run.store.read)
    run._guard(run.store.read)
    focused = focused_profile(proof.seed_values['review'])
    return VerifiedPhase1Status(deepcopy(work.current_pointer), work.outcome,
        deepcopy(work.latest_candidate), deepcopy(work.promotion_candidate), work.pending_paths,
        orphans, profiles, gate, selected, number, attempts,
        False if focused and clean is not None else clean, focused, clean if focused else None)
