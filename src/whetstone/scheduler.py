"""Round scheduling primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal


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
    "buildability": frozenset(),
    "consistency": frozenset(),
    "determinism_light": frozenset(),
    "operability_light": frozenset(),
    "mvp_readiness_check": frozenset(),
    "scope_guard": frozenset(),
}


@dataclass(frozen=True)
class ReviewProfileDefinition:
    name: str
    focus: tuple[str, ...]
    prompt_guidance: str


REVIEW_PROFILE_DEFINITIONS: dict[str, ReviewProfileDefinition] = {
    "structural_integrity": ReviewProfileDefinition(
        name="structural_integrity",
        focus=("authority_boundaries", "state_machine_legality", "cross_spec_consistency"),
        prompt_guidance=(
            "Emphasize authority boundaries, legal state/lifecycle transitions, required artifact/schema structure, "
            "and cross-section consistency. This profile is appropriate for stateful systems where ambiguity can "
            "corrupt state, replay, or audit behavior."
        ),
    ),
    "determinism": ReviewProfileDefinition(
        name="determinism",
        focus=("hashing", "replayability", "idempotency"),
        prompt_guidance=(
            "Emphasize behavior that must produce the same outcome across implementers and repeated runs: hashes, "
            "ordering, replay, retries, idempotency, stable identifiers, deduplication, and deterministic failure states."
        ),
    ),
    "operability": ReviewProfileDefinition(
        name="operability",
        focus=("failure_modes", "observability", "recovery"),
        prompt_guidance=(
            "Emphasize operational failure modes, validation failures, terminal reporting, recovery behavior, "
            "observability, and operator handoff needed to run the system safely."
        ),
    ),
    "adversarial": ReviewProfileDefinition(
        name="adversarial",
        focus=("ambiguity_attack", "exploit_paths", "assumption_breaking"),
        prompt_guidance=(
            "Stress-test ambiguity, hidden assumptions, exploit paths, and cases where a permissive reading could "
            "produce unsafe, divergent, or out-of-scope behavior. Do not elevate severity unless the baseline "
            "invariants, authority model, determinism requirements, or active rubric justify it."
        ),
    ),
    "convergence_strict_check": ReviewProfileDefinition(
        name="convergence_strict_check",
        focus=("rubric_alignment", "declaration_validity", "strictness_gaps"),
        prompt_guidance=(
            "Evaluate target/rubric readiness, unresolved blocker or major issues, declaration validity, and whether "
            "the draft satisfies the configured convergence target. Do not expand scope merely to make the spec more complete."
        ),
    ),
    "buildability": ReviewProfileDefinition(
        name="buildability",
        focus=("core_flow", "required_inputs_outputs", "acceptance_criteria"),
        prompt_guidance=(
            "Review whether an engineer can build the first useful implementation without guessing. Prioritize core "
            "flows, required inputs and outputs, command/API behavior, ownership, and observable acceptance criteria. "
            "Avoid requesting post-MVP hardening unless it blocks the core flow."
        ),
    ),
    "consistency": ReviewProfileDefinition(
        name="consistency",
        focus=("terminology_consistency", "command_option_consistency", "artifact_reference_consistency"),
        prompt_guidance=(
            "Review internal consistency of terminology, option names, artifacts, section references, lifecycle terms, "
            "and source-of-truth statements. Prefer small alignment fixes over expanding the system contract."
        ),
    ),
    "determinism_light": ReviewProfileDefinition(
        name="determinism_light",
        focus=("path_resolution", "stable_ids", "exit_codes", "report_presence"),
        prompt_guidance=(
            "Review deterministic behavior only where it affects observable MVP outcomes: path resolution, exit codes, "
            "stable identifiers, ordering visible to users, and whether required reports or files are produced. Do not "
            "require exhaustive replay, idempotency, recovery, or audit contracts unless they are explicitly in scope."
        ),
    ),
    "operability_light": ReviewProfileDefinition(
        name="operability_light",
        focus=("obvious_failure_modes", "user_visible_errors", "safe_non_destructive_behavior"),
        prompt_guidance=(
            "Review obvious user-visible failures and safe behavior for the MVP. Prefer simple error/failure categories "
            "and clear user outcomes. Do not require full observability, recovery, runbooks, or exhaustive failure matrices."
        ),
    ),
    "mvp_readiness_check": ReviewProfileDefinition(
        name="mvp_readiness_check",
        focus=("mvp_scope", "core_flow_buildability", "deferred_hardening"),
        prompt_guidance=(
            "Evaluate whether the draft is ready for a first useful MVP implementation under the scope contract. "
            "Check blockers and major gaps in core flows, but treat nonessential hardening as deferrable when it does "
            "not change MVP interfaces, state legality, artifact integrity, or acceptance outcomes."
        ),
    ),
    "scope_guard": ReviewProfileDefinition(
        name="scope_guard",
        focus=("scope_contract_alignment", "over_expansion", "deferred_surface_preservation"),
        prompt_guidance=(
            "Review whether the draft stayed within the approved scope contract. Flag scope expansion, new persistent "
            "surfaces, exhaustive matrices, broad error vocabularies, or post-MVP hardening that became required without "
            "operator approval. Prefer scope-promotion decisions over silently widening the MVP."
        ),
    ),
}


@dataclass(frozen=True)
class ProfileSetDefinition:
    name: str
    phase_1_profiles: tuple[str, ...]
    phase_2_profiles: tuple[str, ...]
    phase_1_default_budgets: dict[str, int]
    phase_2_default_budgets: dict[str, int]


PROFILE_SETS: dict[str, ProfileSetDefinition] = {
    "stateful_system": ProfileSetDefinition(
        name="stateful_system",
        phase_1_profiles=("structural_integrity", "determinism", "operability"),
        phase_2_profiles=("convergence_strict_check", "adversarial", "convergence_strict_check"),
        phase_1_default_budgets={"structural_integrity": 10, "determinism": 10, "operability": 10},
        phase_2_default_budgets={"convergence_strict_check": 10, "adversarial": 10},
    ),
    "balanced_mvp": ProfileSetDefinition(
        name="balanced_mvp",
        phase_1_profiles=("structural_integrity", "determinism", "operability"),
        phase_2_profiles=("convergence_strict_check", "adversarial", "convergence_strict_check"),
        phase_1_default_budgets={"structural_integrity": 7, "determinism": 7, "operability": 6},
        phase_2_default_budgets={"convergence_strict_check": 6, "adversarial": 4},
    ),
    "utility_mvp": ProfileSetDefinition(
        name="utility_mvp",
        phase_1_profiles=("buildability", "consistency", "determinism_light", "operability_light"),
        phase_2_profiles=("mvp_readiness_check", "scope_guard", "mvp_readiness_check"),
        phase_1_default_budgets={"buildability": 4, "consistency": 4, "determinism_light": 4, "operability_light": 3},
        phase_2_default_budgets={"mvp_readiness_check": 4, "scope_guard": 3},
    ),
    "governance": ProfileSetDefinition(
        name="governance",
        phase_1_profiles=("structural_integrity", "determinism", "operability", "adversarial"),
        phase_2_profiles=("convergence_strict_check", "adversarial", "convergence_strict_check"),
        phase_1_default_budgets={"structural_integrity": 10, "determinism": 10, "operability": 10, "adversarial": 8},
        phase_2_default_budgets={"convergence_strict_check": 10, "adversarial": 10},
    ),
}

CONVERGENCE_ACCEPTANCE_PROFILES = frozenset({"convergence_strict_check", "mvp_readiness_check"})


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


def default_phase_1_scheduler(profile_budgets: dict[str, int] | None = None, profile_set: str = "stateful_system") -> PhaseScheduler:
    profile_set_definition = profile_set_definition_for(profile_set)
    budgets = resolved_phase_1_profile_budgets(profile_budgets, profile_set=profile_set)
    final_profile = profile_set_definition.phase_1_profiles[-1]
    return PhaseScheduler(
        ProfileStep(
            profile,
            focus=DEFAULT_PROFILE_FOCUS_ANCHORS.get(profile, frozenset()),
            skip_if_clean=profile != final_profile,
            repeat_if_blockers=True,
            round_budget=budgets[profile],
        )
        for profile in profile_set_definition.phase_1_profiles
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


def default_phase_2_scheduler(profile_budgets: dict[str, int] | None = None, profile_set: str = "stateful_system") -> PhaseScheduler:
    profile_set_definition = profile_set_definition_for(profile_set)
    budgets = resolved_phase_2_profile_budgets(profile_budgets, profile_set=profile_set)
    return PhaseScheduler(
        ProfileStep(
            profile,
            focus=DEFAULT_PROFILE_FOCUS_ANCHORS.get(profile, frozenset()),
            repeat_if_blockers=True,
            round_budget=budgets[profile],
        )
        for profile in profile_set_definition.phase_2_profiles
    )


def resolved_phase_1_profile_budgets(profile_budgets: dict[str, int] | None = None, profile_set: str = "stateful_system") -> dict[str, int]:
    defaults = profile_set_definition_for(profile_set).phase_1_default_budgets
    budgets = profile_budgets or {}
    return {profile: max(1, int(budgets.get(profile, default))) for profile, default in defaults.items()}


def resolved_phase_2_profile_budgets(profile_budgets: dict[str, int] | None = None, profile_set: str = "stateful_system") -> dict[str, int]:
    defaults = profile_set_definition_for(profile_set).phase_2_default_budgets
    budgets = profile_budgets or {}
    return {profile: max(1, int(budgets.get(profile, default))) for profile, default in defaults.items()}


def profile_set_definition_for(profile_set: str) -> ProfileSetDefinition:
    try:
        return PROFILE_SETS[profile_set]
    except KeyError as exc:
        raise ValueError(f"unknown review profile_set {profile_set!r}") from exc


def profile_names_for_phase(profile_set: str, phase: Literal["phase_1", "phase_2"]) -> tuple[str, ...]:
    definition = profile_set_definition_for(profile_set)
    if phase == "phase_1":
        return definition.phase_1_profiles
    return definition.phase_2_profiles


def profile_prompt_guidance(profile: str) -> str | None:
    definition = REVIEW_PROFILE_DEFINITIONS.get(profile)
    if definition is None:
        return None
    focus_text = ", ".join(definition.focus)
    return f"Profile focus: {focus_text}\nProfile guidance: {definition.prompt_guidance}"


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
