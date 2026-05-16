"""Controlled vocabulary and profile taxonomy for Whetstone."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


VOCABULARY_SCHEMA_VERSION = "controlled-vocabulary-v1"
VOCABULARY_VERSION = "2026-05-17"

SEVERITY_ORDER = ("nit", "minor", "major", "blocker")
SEVERITY_VALUES = frozenset(SEVERITY_ORDER)
SEVERITY_RANK = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}

SEVERITY_ALIASES: dict[str, str | None] = {
    "critical": "blocker",
    "severe": "blocker",
    "high": "major",
    "medium": "minor",
    "moderate": "minor",
    "low": "nit",
    "none": None,
    "null": None,
    "na": None,
    "n/a": None,
    "not applicable": None,
    "not_applicable": None,
    "not-applicable": None,
    "no impact": None,
    "no_impact": None,
    "no-impact": None,
    "not impacted": None,
    "no authority impact": None,
    "no determinism impact": None,
    "no rubric impact": None,
    "not applicable to authority": None,
    "not applicable to determinism": None,
    "not applicable to rubric": None,
}

REVIEW_INVARIANTS: dict[str, str] = {
    "authority_boundary": "ownership, precedence, and mutation authority are explicit where behavior can diverge",
    "deterministic_behavior": "required behavior has deterministic inputs, ordering, decisions, and outputs",
    "state_legality": "stateful behavior defines legal states, transitions, terminal states, and invalid-transition handling",
    "artifact_integrity": "required artifacts have producer, consumer, identity, validation, mutation, and persistence semantics",
    "failure_handling": "required failure paths define reject, retry, halt, continue, preserve, report, or escalate behavior",
    "replay_idempotency": "replay, retry, deduplication, and idempotency behavior are explicit where required",
    "scope_control": "review pressure stays inside the configured workflow, rubric, profile, and approved scope contract",
    "acceptance_testability": "completion criteria are observable enough to test implementation readiness",
    "rubric_alignment": "the draft satisfies the active rubric profile and target phase/mode without hidden gaps",
    "version_lineage": "source, draft, dependency, and apply-back identity are hashable and auditable",
}

CONCERN_TYPES: dict[str, str] = {
    "clarity_gap": "section is ambiguous, undefined, or unclear",
    "completeness_gap": "section is missing required content, rule, definition, or edge case",
    "consistency_violation": "section contradicts another section or prior decision",
    "determinism_violation": "section permits non-deterministic behavior",
    "authority_violation": "section violates a defined role, boundary, or authority rule",
    "scope_violation": "section addresses something out of scope or omits something in scope",
    "redundancy": "section duplicates content elsewhere",
    "precision_gap": "section is correct but under-specified",
}

DIRECTIONS: dict[str, str] = {
    "add": "add missing content or behavior",
    "remove": "remove content or behavior",
    "modify": "change content when no more specific direction applies",
    "clarify": "clarify ambiguous content without materially changing scope or strictness",
    "constrain": "make behavior stricter, narrower, or more bounded",
    "relax": "make behavior looser, broader, or less restrictive",
}

SCOPES: dict[str, str] = {
    "local": "specific rule, sentence, definition, field, or invariant",
    "structural": "section organization, responsibility boundary, lifecycle shape, or cross-section architecture",
}

OPPOSING_DIRECTIONS: dict[str, str] = {
    "add": "remove",
    "remove": "add",
    "constrain": "relax",
    "relax": "constrain",
}


@dataclass(frozen=True)
class ReviewProfileDefinition:
    name: str
    focus: tuple[str, ...]
    prompt_guidance: str


@dataclass(frozen=True)
class ProfileSetDefinition:
    name: str
    phase_1_profiles: tuple[str, ...]
    phase_2_profiles: tuple[str, ...]
    phase_1_default_budgets: dict[str, int]
    phase_2_default_budgets: dict[str, int]


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


def controlled_vocabulary_packet() -> dict[str, Any]:
    """Return a deterministic packet for Whetstone's active controlled vocabulary."""

    return {
        "schema_version": VOCABULARY_SCHEMA_VERSION,
        "vocabulary_version": VOCABULARY_VERSION,
        "severity_order": list(SEVERITY_ORDER),
        "severity_aliases": {key: SEVERITY_ALIASES[key] for key in sorted(SEVERITY_ALIASES)},
        "review_invariants": _term_map(REVIEW_INVARIANTS),
        "oscillation": {
            "concern_types": _term_map(CONCERN_TYPES),
            "directions": _term_map(DIRECTIONS),
            "scopes": _term_map(SCOPES),
            "opposition_pairs": [["add", "remove"], ["constrain", "relax"]],
        },
        "review_profiles": {
            name: {
                "focus": list(definition.focus),
                "prompt_guidance": definition.prompt_guidance,
                "focus_anchors": sorted(DEFAULT_PROFILE_FOCUS_ANCHORS.get(name, frozenset())),
            }
            for name, definition in sorted(REVIEW_PROFILE_DEFINITIONS.items())
        },
        "profile_sets": {
            name: {
                "phase_1_profiles": list(definition.phase_1_profiles),
                "phase_2_profiles": list(definition.phase_2_profiles),
                "phase_1_default_budgets": dict(sorted(definition.phase_1_default_budgets.items())),
                "phase_2_default_budgets": dict(sorted(definition.phase_2_default_budgets.items())),
            }
            for name, definition in sorted(PROFILE_SETS.items())
        },
        "convergence_acceptance_profiles": sorted(CONVERGENCE_ACCEPTANCE_PROFILES),
    }


def controlled_vocabulary_hash() -> str:
    payload = json.dumps(controlled_vocabulary_packet(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_controlled_vocabulary(path: Path | str) -> Path:
    """Persist the active controlled vocabulary packet."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(controlled_vocabulary_packet(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def validate_oscillation_terms(*, concern_type: str, direction: str, scope: str) -> None:
    """Validate reviewer-proposed oscillation terms against the controlled vocabulary."""

    if concern_type not in CONCERN_TYPES:
        raise ValueError(f"unknown concern_type {concern_type!r}")
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction {direction!r}")
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}")


def _term_map(source: dict[str, str]) -> dict[str, dict[str, str]]:
    return {key: {"description": source[key]} for key in sorted(source)}
