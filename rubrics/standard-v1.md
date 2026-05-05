# Whetstone Standard Rubric

Derived from: Convergence Rubric v6
Profile version: standard-v1
Intended use: This profile is for production-ready technical specifications that need to be buildable, deterministic, internally consistent, and operable without requiring governance-grade final convergence evidence. It is intended to catch blockers and major ambiguities that would cause implementation failure, divergent behavior, invalid artifacts, or unclear handoff between systems, roles, states, and failure paths.
Strictness level: medium
Target fit: final/strict

## Derivation Note

Preserves v6 concerns for deterministic implementation, explicit data contracts, legal state transitions, failure handling, replay/idempotency, artifact integrity, structural linting, coupling checks, and conservative severity classification.

Relaxes v6 requirements for mandatory Convergence Declaration hard-blocking, exhaustive project-specific coupling declarations, independent scoring proof, Tier 5 mode ceremony, and full final convergence proof where the remaining gap does not affect production implementation correctness.

## 1. Purpose

The standard-v1 rubric evaluates whether a technical specification is ready for normal production implementation.

A passing specification must let an implementer build the intended system without guessing about required behavior, authoritative sources, data shapes, state legality, ordering, replay behavior, failure handling, or acceptance criteria.

This rubric is stricter than MVP readiness and exploratory review, but less strict than governance-v6. It focuses on correctness, determinism, consistency, and operability over audit ceremony.

## 2. Applicability

Use standard-v1 when the target output is a production-ready technical spec for a system, workflow, protocol, service, adapter, orchestrator, data pipeline, or artifact-producing process.

The recommended target is `target_phase: final` and `target_mode: strict`.

A lightweight convergence declaration SHOULD be present and SHOULD identify:

- authoritative input documents or artifacts
- rubric profile and target phase/mode
- known cross-section or cross-system couplings
- critical dimensions that must be deterministic for implementation

Missing declaration metadata is not automatically blocking under standard-v1. It becomes blocking only when the reviewer cannot determine the authoritative scope, target behavior, or source of truth from the spec itself.

## 3. Blocking Criteria

A finding MUST be classified as blocking when it prevents deterministic production implementation of target-scope behavior.

Block when any of the following are true:

- The spec lacks an authoritative source of truth for required behavior, required artifacts, required data, or ownership of a decision.
- Two or more sections define conflicting field names, types, enum values, nullability, requiredness, identifiers, artifact paths, or lifecycle meanings for the same target-scope concept.
- A required interface, schema, config surface, artifact, API, or pseudocode block omits fields, types, enum definitions, key definitions, validation rules, or error responses needed to implement it.
- A lifecycle-bearing component lacks required states, legal transitions, terminal states, invalid-transition behavior, or ownership of state mutation.
- A required decision rule depends on unbounded reviewer, operator, model, or system discretion, including phrases such as system decides, best effort, if needed, or eventually, when no deterministic fallback rule is provided.
- Time, ordering, idempotency, replay, or deduplication behavior is required by the system but undefined or internally contradictory.
- Failure handling is missing for a required path where the implementation must know whether to retry, halt, escalate, emit an artifact, preserve state, or continue.
- Required artifacts lack producer, consumer, path or identity, validation rule, mutation rule, or persistence semantics needed to preserve artifact integrity.
- Acceptance criteria are absent for a required workflow, deliverable, or externally visible behavior such that implementation completion cannot be tested.
- Authority boundaries are ambiguous where multiple roles, systems, clients, services, or artifacts can mutate the same state, decide the same outcome, or override each other.
- Baseline coupling failure would cause divergent implementation behavior across terminology/data contracts, state/lifecycle, decision/failure handling, time/ordering, or idempotency/replay.
- A claimed final/strict result depends on unresolved blocker-level ambiguity, contradictory source material, or unverifiable artifact identity.

## 4. Major Issue Criteria

A finding SHOULD be classified as major when it creates significant implementation risk but does not fully prevent a reasonable implementation path.

Classify as major when any of the following are true:

- A required behavior is defined, but validation evidence, examples, acceptance tests, or boundary cases are incomplete.
- A data contract is mostly defined, but secondary fields, optionality, examples, or validation details are incomplete enough to risk rework.
- A state model exists, but non-core transitions, recovery paths, or edge states are underspecified.
- Failure handling exists for the main path, but secondary errors, malformed input, timeout, retry, partial write, or artifact validation paths are incomplete.
- Coupled sections are directionally consistent but use different terminology, names, ordering assumptions, or lifecycle framing that could cause implementation drift.
- Project-specific couplings are not declared, but the reviewer can infer them and identify reviewable risk.
- Prose uses weak normative terms such as should or unqualified may in target-scope requirements, but surrounding text still makes the likely implementation clear.
- Acceptance criteria exist but are not computable, not tied to artifacts or behavior, or omit important negative cases.
- Replay, idempotency, ordering, or deduplication is defined for the normal path but not for retries, restarts, duplicate input, or partially completed work.
- Operational behavior is present but incomplete for observability, validation failure, operator intervention, or terminal reporting.
- Tier 5 scale or evolution concerns are relevant because the system accepts external input or is distributed, but the missing details affect robustness rather than core correctness.

## 5. Minor Issue Criteria

A finding MAY be classified as minor when it does not affect implementation correctness, deterministic behavior, artifact integrity, or acceptance testing.

Classify as minor when any of the following are true:

- Wording is inconsistent but the referenced concept is still uniquely identifiable.
- A section would benefit from clearer examples, labels, or ordering, but required behavior is already explicit.
- Non-normative prose contains weak terms such as should or may without changing implementation obligations.
- Traceability, declaration metadata, or coupling documentation is incomplete but the implementation-relevant source of truth is still clear.
- A non-core operational detail is missing and can be safely deferred without changing interfaces, states, artifacts, or failure behavior.
- Formatting, naming style, or document organization makes review harder but does not create ambiguity in required behavior.

## 6. Non-Goals / Intentionally Relaxed Checks

standard-v1 does not require full governance-v6 ceremony.

The following are intentionally relaxed:

- A missing formal Convergence Declaration is not an automatic hard block if scope, authority, target phase/mode, and critical behavior are otherwise clear.
- Independent scoring or peer-verification evidence is recommended but not required for every section.
- All project-specific couplings do not need to be exhaustively declared before review, but baseline couplings must still be evaluated where relevant.
- Final convergence proof does not require every Tier 1 dimension to be scored 3 if the remaining issue is minor and does not affect implementation correctness.
- Tier 5 Entry Mode does not need to be formally declared unless scale, distributed execution, or external input materially affects target-scope correctness.
- Cosmetic wording drift, non-authoritative examples, and documentation polish should not block convergence.
- Exhaustive edge-case enumeration is not required when the spec defines deterministic defaults, failure behavior, and acceptance criteria for the target scope.

## 7. Reviewer Instructions

Review in this order:

1. Identify the authoritative spec scope, target phase/mode, required artifacts, and target-scope workflows.
2. Apply prose lint to requirement-bearing text. Flag system decides, best effort, if needed, eventually, weak should, and unqualified may when they control implementation behavior.
3. Apply structural lint to schemas, APIs, config, artifacts, and pseudocode. Check for undefined enums, missing field types, required/nullable mismatch, missing errors, undefined identifiers, and inconsistent keys.
4. Evaluate baseline couplings:
   - Terminology <-> Data Contracts
   - State Model <-> Lifecycle
   - Decision Rules <-> Failure Handling
   - Time Semantics <-> Ordering
   - Idempotency <-> Replay
5. Evaluate any declared or clearly implied project-specific couplings that affect target-scope implementation.
6. Classify findings as blocker, major, or minor using observable evidence from the spec.
7. Prefer one root-cause finding when a single ambiguity causes multiple downstream issues.
8. Distinguish behavior-affecting drift from cosmetic or editorial drift.
9. For each blocker or major, identify the affected section, the missing or conflicting requirement, and the minimum correction needed to make the spec buildable.

When using numeric scoring, use the v6 scale:

- 0 = missing
- 1 = acknowledged but undefined
- 2 = defined but not validated
- 3 = explicit and validated

Under standard-v1, scores are guidance for severity. A 0 or 1 in target-scope determinism, enforceability, state legality, artifact integrity, or failure handling usually indicates a blocker. A 2 in a critical target-scope area usually indicates a major unless the missing validation would directly prevent implementation.

## 8. Convergence Interpretation

A specification converges under standard-v1 when all of the following are true:

- No unresolved blocker findings remain.
- No unresolved major findings remain for target-scope production behavior.
- Required data contracts, state transitions, decision rules, failure paths, artifacts, replay/idempotency behavior, and acceptance criteria are defined well enough for implementation without guessing.
- Baseline couplings are internally consistent for all target-scope behavior.
- Any remaining issues are minor, explicitly non-blocking, and do not change implementation behavior, artifact integrity, state legality, or acceptance outcomes.

standard-v1 convergence means the spec is ready for normal production implementation. It does not mean the spec has satisfied governance-v6 final convergence, exhaustive traceability, formal audit proof, or every optional scale/evolution check.
