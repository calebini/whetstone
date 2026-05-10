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
    round_budget: int | None = None
    max_repeats: int | None = None

    @property
    def effective_round_budget(self) -> int:
        if self.round_budget is not None:
            return max(1, self.round_budget)
        if self.max_repeats is not None:
            return max(1, self.max_repeats + 1)
        return 1


@dataclass
class ProfileState:
    clean: bool = False
    rounds_used: int = 0
    residual_status: str | None = None


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
            if not state.clean and state.rounds_used >= step.effective_round_budget:
                self.index += 1
                continue
            return step.profile
        return None

    def active_profile(self) -> str | None:
        if self.index >= len(self.steps):
            return None
        return self.steps[self.index].profile

    def record_result(self, profile: str, *, blocker_count: int, major_count: int) -> None:
        if self.index >= len(self.steps):
            raise IndexError("scheduler has no active step")
        step = self.steps[self.index]
        if step.profile != profile:
            raise ValueError(f"expected profile {step.profile!r}, got {profile!r}")
        state = self.states[self.index]
        state.rounds_used += 1
        state.clean = blocker_count == 0 and major_count == 0
        if state.clean:
            state.residual_status = None
        has_blocking_findings = blocker_count > 0 or major_count > 0
        if has_blocking_findings and state.rounds_used >= step.effective_round_budget:
            state.residual_status = "exhausted_with_residuals"
        if has_blocking_findings and step.repeat_if_blockers and state.rounds_used < step.effective_round_budget:
            return
        self.index += 1

    def force_advance_current(self, *, residual_status: str) -> None:
        if self.index >= len(self.steps):
            raise IndexError("scheduler has no active step")
        state = self.states[self.index]
        if not state.clean:
            state.residual_status = residual_status
        self.index += 1

    def invalidate_for_mutated_sections(self, mutated_sections: Iterable[str]) -> None:
        mutated = set(mutated_sections)
        for index, step in enumerate(self.steps):
            if step.focus and _focus_matches_mutation(step.focus, mutated):
                self.states[index].clean = False

    def phase_complete(self, *, accepted_draft: bool) -> bool:
        return accepted_draft and all(state.clean for state in self.states)

    def sweep_complete(self) -> bool:
        return self.index >= len(self.steps)

    def total_round_budget(self) -> int:
        return sum(step.effective_round_budget for step in self.steps)

    def status(self) -> dict[str, object]:
        active_index = self.index if self.index < len(self.steps) else None
        profiles: list[dict[str, object]] = []
        for index, (step, state) in enumerate(zip(self.steps, self.states)):
            exhausted = not state.clean and state.rounds_used >= step.effective_round_budget
            profiles.append(
                {
                    "profile": step.profile,
                    "clean": state.clean,
                    "rounds_used": state.rounds_used,
                    "round_budget": step.effective_round_budget,
                    "exhausted": exhausted,
                    "residual_status": state.residual_status,
                    "active": index == active_index,
                }
            )
        unverified = [item["profile"] for item in profiles if not item["clean"]]
        exhausted = [item["profile"] for item in profiles if item["exhausted"]]
        remaining = [
            item["profile"]
            for item in profiles
            if not item["clean"] and not item["exhausted"] and item["rounds_used"] < item["round_budget"]
        ]
        return {
            "profiles": profiles,
            "unverified_profiles": unverified,
            "exhausted_profiles": exhausted,
            "profiles_remaining": remaining,
            "total_round_budget": self.total_round_budget(),
        }


def default_phase_1_scheduler(profile_budgets: dict[str, int] | None = None) -> PhaseScheduler:
    budgets = resolved_phase_1_profile_budgets(profile_budgets)
    return PhaseScheduler(
        [
            ProfileStep(
                "structural_integrity",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["structural_integrity"],
                skip_if_clean=True,
                repeat_if_blockers=True,
                round_budget=budgets["structural_integrity"],
            ),
            ProfileStep(
                "determinism",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["determinism"],
                skip_if_clean=True,
                repeat_if_blockers=True,
                round_budget=budgets["determinism"],
            ),
            ProfileStep(
                "operability",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["operability"],
                skip_if_clean=False,
                repeat_if_blockers=True,
                round_budget=budgets["operability"],
            ),
        ]
    )


def focused_phase_1_scheduler(profile: str, *, round_budget: int) -> PhaseScheduler:
    """Build a Phase 1 scheduler constrained to one review profile."""

    return PhaseScheduler(
        [
            ProfileStep(
                profile,
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS.get(profile, frozenset()),
                skip_if_clean=False,
                repeat_if_blockers=True,
                round_budget=max(1, int(round_budget)),
            )
        ]
    )


def default_phase_2_scheduler(profile_budgets: dict[str, int] | None = None) -> PhaseScheduler:
    budgets = resolved_phase_2_profile_budgets(profile_budgets)
    return PhaseScheduler(
        [
            ProfileStep(
                "convergence_strict_check",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["convergence_strict_check"],
                repeat_if_blockers=True,
                round_budget=budgets["convergence_strict_check"],
            ),
            ProfileStep(
                "adversarial",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["adversarial"],
                repeat_if_blockers=True,
                round_budget=budgets["adversarial"],
            ),
            ProfileStep(
                "convergence_strict_check",
                focus=DEFAULT_PROFILE_FOCUS_ANCHORS["convergence_strict_check"],
                repeat_if_blockers=True,
                round_budget=budgets["convergence_strict_check"],
            ),
        ]
    )


def resolved_phase_1_profile_budgets(profile_budgets: dict[str, int] | None = None) -> dict[str, int]:
    budgets = profile_budgets or {}
    return {
        "structural_integrity": max(1, int(budgets.get("structural_integrity", 10))),
        "determinism": max(1, int(budgets.get("determinism", 10))),
        "operability": max(1, int(budgets.get("operability", 10))),
    }


def resolved_phase_2_profile_budgets(profile_budgets: dict[str, int] | None = None) -> dict[str, int]:
    budgets = profile_budgets or {}
    return {
        "convergence_strict_check": max(1, int(budgets.get("convergence_strict_check", 10))),
        "adversarial": max(1, int(budgets.get("adversarial", 10))),
    }


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
