"""Round scheduling primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


DEFAULT_PROFILE_FOCUS_ANCHORS: dict[str, frozenset[str]] = {
    "structural_integrity": frozenset(
        {
            "core-roles",
            "halting-conditions-ordered-precedence",
            "halt-artifact-matrix",
            "review-profiles",
            "round-strategy-adaptive",
            "round-scheduling-algorithm",
            "artifact-validation-policy",
            "artifact-schemas-minimum-required-fields",
            "conflict-model",
            "editor-decline-taxonomy",
            "conflict-escalation",
            "state-machine-full-transitions",
        }
    ),
    "determinism": frozenset(
        {
            "issue-and-conflict-identity",
            "phase-gated-feedback-classification",
            "content-normalization-and-hashing",
            "oscillation-detection-full-definition",
            "reproducibility",
        }
    ),
    "operability": frozenset(
        {
            "primary-outputs",
            "configuration",
            "halt-artifact-matrix",
            "artifact-validation-policy",
            "phase-2-failure-handling",
            "phase-1-failure-handling",
            "reproducibility",
        }
    ),
    "adversarial": frozenset(
        {
            "baseline-review-invariants",
            "phase-gated-feedback-classification",
            "oscillation-detection-full-definition",
            "conflict-model",
            "target-matrix-precedence",
        }
    ),
    "convergence_strict_check": frozenset(
        {
            "accepted-draft-definition",
            "round-scheduling-algorithm",
            "phase-2-failure-handling",
            "target-matrix-precedence",
            "convergence-declaration",
        }
    ),
}


@dataclass(frozen=True)
class ProfileStep:
    profile: str
    focus: frozenset[str] = field(default_factory=frozenset)
    skip_if_clean: bool = False
    repeat_if_blockers: bool = False
    max_repeats: int = 1


@dataclass
class ProfileState:
    clean: bool = False
    repeats_used: int = 0


class PhaseScheduler:
    """Deterministic scheduler for configured profile sequences."""

    def __init__(self, steps: Iterable[ProfileStep]) -> None:
        self.steps = list(steps)
        self.states = [ProfileState() for _ in self.steps]
        self.index = 0

    def next_profile(self) -> str | None:
        while self.index < len(self.steps):
            step = self.steps[self.index]
            state = self.states[self.index]
            if step.skip_if_clean and state.clean:
                self.index += 1
                continue
            return step.profile
        return None

    def record_result(self, profile: str, *, blocker_count: int, major_count: int) -> None:
        if self.index >= len(self.steps):
            raise IndexError("scheduler has no active step")
        step = self.steps[self.index]
        if step.profile != profile:
            raise ValueError(f"expected profile {step.profile!r}, got {profile!r}")
        state = self.states[self.index]
        state.clean = blocker_count == 0 and major_count == 0
        has_blocking_findings = blocker_count > 0 or major_count > 0
        if has_blocking_findings and step.repeat_if_blockers and state.repeats_used < step.max_repeats:
            state.repeats_used += 1
            return
        self.index += 1

    def invalidate_for_mutated_sections(self, mutated_sections: Iterable[str]) -> None:
        mutated = set(mutated_sections)
        for index, step in enumerate(self.steps):
            if step.focus and _focus_matches_mutation(step.focus, mutated):
                self.states[index].clean = False

    def phase_complete(self, *, accepted_draft: bool) -> bool:
        return accepted_draft and all(state.clean for state in self.states)


def default_phase_1_scheduler() -> PhaseScheduler:
    return PhaseScheduler(
        [
            ProfileStep(
                "structural_integrity",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["structural_integrity"],
                skip_if_clean=True,
                repeat_if_blockers=True,
                max_repeats=2,
            ),
            ProfileStep(
                "determinism",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["determinism"],
                skip_if_clean=True,
                repeat_if_blockers=True,
                max_repeats=2,
            ),
            ProfileStep(
                "operability",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["operability"],
                skip_if_clean=False,
                repeat_if_blockers=True,
                max_repeats=1,
            ),
        ]
    )


def default_phase_2_scheduler() -> PhaseScheduler:
    return PhaseScheduler(
        [
            ProfileStep(
                "convergence_strict_check",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["convergence_strict_check"],
                repeat_if_blockers=True,
                max_repeats=2,
            ),
            ProfileStep(
                "adversarial",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["adversarial"],
                repeat_if_blockers=True,
                max_repeats=2,
            ),
            ProfileStep(
                "convergence_strict_check",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["convergence_strict_check"],
                repeat_if_blockers=True,
                max_repeats=2,
            ),
        ]
    )


def resolve_focus_anchors(canonical_section_ids: Iterable[str], focus_anchors: Iterable[str]) -> frozenset[str]:
    """Resolve configured focus-anchor suffixes to concrete canonical section ids."""

    section_ids = list(canonical_section_ids)
    resolved: set[str] = set()
    for anchor in focus_anchors:
        matches = [section_id for section_id in section_ids if section_id == anchor or section_id.endswith(f"-{anchor}")]
        if len(matches) != 1:
            raise ValueError(f"focus anchor {anchor!r} resolved to {len(matches)} sections")
        resolved.add(matches[0])
    return frozenset(resolved)


def _focus_matches_mutation(focus: frozenset[str], mutated: set[str]) -> bool:
    for anchor in focus:
        for section_id in mutated:
            if section_id == anchor or section_id.endswith(f"-{anchor}"):
                return True
    return False
