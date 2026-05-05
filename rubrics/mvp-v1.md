# Whetstone MVP v1 Rubric

Aligned with: Convergence Rubric v6
Profile version: mvp-v1
Intended use: This profile evaluates whether a specification is ready for a first useful implementation of an MVP. It prioritizes the minimum information an engineer needs to build the core job flow without guessing: scope, interfaces, data contracts, state transitions, acceptance criteria, artifact integrity, authority boundaries, deterministic behavior, and obvious failure handling.
Strictness level: medium
Target fit: `target_phase: mid` / `target_mode: strict`

## Derivation Note

This is an intentionally relaxed Whetstone profile aligned with Convergence Rubric v6. It is not a full governance-v6 substitute and was not mechanically generated from the v6 text.

This profile preserves v6 concerns that protect deterministic implementation, authority boundaries, artifact integrity, explicit acceptance criteria, legal state transitions, structural linting, baseline coupling checks, and failure handling. It intentionally relaxes governance-grade declaration ceremony, exhaustive coupling declarations, independent scoring proof, full final convergence gating, Tier 5 scale/evolution review, long-term operational polish, and edge cases outside the MVP scope.

## 1. Purpose

The mvp-v1 rubric determines whether a specification is buildable enough for the first useful implementation.

A passing MVP specification defines the core user or job flow, the required interfaces and data contracts, the legal state changes, the artifacts produced or consumed, the acceptance criteria, and the obvious failure behavior needed to implement the MVP without inventing product or system behavior.

This rubric is stricter than exploratory shaping and less strict than production or governance convergence. It separates issues that block building from issues that can be deferred until after the MVP.

## 2. Applicability

Use mvp-v1 when the target output is an implementation-ready MVP spec for a service, workflow, adapter, tool, protocol, data pipeline, artifact-producing process, or user-facing feature.

The recommended target is `target_phase: mid` and `target_mode: strict`.

A formal Convergence Declaration is not required. The spec should still identify enough review context to determine:

- the MVP goal
- the in-scope first useful flow
- the primary users, callers, systems, or jobs
- authoritative source material or ownership for required behavior
- required inputs, outputs, states, artifacts, and acceptance criteria

If the MVP scope cannot be determined from the spec or supplied context, that is a blocking issue.

## 3. Blocking Criteria

A finding MUST be classified as blocking when it prevents a reasonable engineer from building the MVP core behavior without guessing.

Block when any of the following are true:

- The MVP goal or first useful flow is missing, contradictory, or too broad to identify what must be built first.
- The spec does not identify the authoritative source of truth for required MVP behavior, required data, state mutation, artifact production, or final decisions.
- A required MVP interface, API, config surface, command, artifact, schema, or pseudocode block omits fields, field types, identifiers, enum values, requiredness, nullability, validation rules, or error responses needed to implement it.
- Two or more sections define conflicting names, types, enum values, identifiers, requiredness, nullability, state meanings, artifact identities, or ownership rules for the same MVP concept.
- A core user/job flow has undefined trigger conditions, required inputs, outputs, completion condition, or handoff between components.
- A lifecycle-bearing MVP component lacks required states, legal transitions, terminal states, invalid-transition behavior, or ownership of state mutation.
- A required decision rule depends on unbounded discretion, including phrases such as `system decides`, `best effort`, `if needed`, or `eventually`, when no deterministic fallback rule is provided.
- Authority boundaries are ambiguous where more than one actor, service, model, client, artifact, or process can decide the same outcome, mutate the same state, or override another actor.
- Required artifacts lack producer, consumer, identity or path, validation rule, mutation rule, or persistence semantics needed to preserve artifact integrity.
- Acceptance criteria are absent for the MVP core flow or are not observable enough to test whether the MVP is complete.
- Failure handling is missing for an obvious MVP failure path where implementation must know whether to reject, retry, halt, continue, preserve state, emit an artifact, or report an error.
- Time, ordering, idempotency, replay, or deduplication is required by the MVP flow but undefined or contradictory.
- A baseline coupling failure would cause divergent MVP implementation across terminology/data contracts, state/lifecycle, decision/failure handling, time/ordering, or idempotency/replay.

## 4. Major Issue Criteria

A finding SHOULD be classified as major when it creates meaningful MVP implementation risk but does not fully block a first useful build.

Classify as major when any of the following are true:

- The MVP scope is mostly clear, but boundary cases between MVP and post-MVP work are incomplete.
- A core behavior is defined, but examples, validation evidence, or acceptance tests are incomplete enough to risk rework.
- A data contract is usable, but secondary fields, optional fields, examples, or validation details are incomplete.
- A state model exists, but non-core transitions, recovery paths, or secondary terminal states are underspecified.
- Failure handling exists for the main path, but malformed input, duplicate input, timeout, retry, partial write, or validation-failure behavior is incomplete.
- Coupled sections are directionally consistent but use different terminology, ordering assumptions, lifecycle framing, or identifiers that could cause implementation drift.
- Prose uses weak normative terms such as `should` or unqualified `may` in MVP-relevant requirements, but surrounding text still makes the likely implementation path clear.
- Acceptance criteria exist but are not tied to specific inputs, outputs, states, artifacts, or observable behavior.
- Replay, idempotency, ordering, or deduplication is defined for the normal path but not for retries, restarts, or duplicate requests.
- Operational behavior such as logging, metrics, operator intervention, or terminal reporting is incomplete but not required to build the MVP core flow.
- A post-MVP dependency or edge case is mentioned but lacks a clear deferral boundary.

## 5. Minor Issue Criteria

A finding MAY be classified as minor when it does not affect MVP buildability, deterministic core behavior, state legality, artifact integrity, or acceptance testing.

Classify as minor when any of the following are true:

- Wording is inconsistent but the required MVP concept is still uniquely identifiable.
- A section would benefit from clearer examples, labels, ordering, or formatting, but required behavior is explicit.
- Non-normative prose contains weak terms such as `should` or `may` without changing implementation obligations.
- Declaration metadata, traceability, or coupling documentation is incomplete but the MVP source of truth remains clear.
- A non-core operational detail is missing and can be deferred without changing MVP interfaces, states, artifacts, failure behavior, or acceptance outcomes.
- Documentation organization makes review harder but does not create implementation ambiguity.

## 6. Non-Goals / Intentionally Relaxed Checks

mvp-v1 does not require governance-v6 final convergence.

The following checks are intentionally relaxed:

- A formal Convergence Declaration is not required if MVP scope, authority, and target behavior are otherwise clear.
- Independent scoring or peer-verification evidence is recommended but not required.
- Project-specific couplings do not need to be exhaustively declared before review.
- Full Tier 1, Tier 2, Tier 3, and Tier 4 convergence proof is not required.
- Tier 5 Entry Mode does not need to be declared unless scale, external input, or distributed execution changes MVP correctness.
- Exhaustive edge-case coverage is not required outside the first useful flow.
- Long-term operability, governance, migration, audit, scale, and evolution concerns can be deferred when they do not affect MVP correctness.
- Full schemas for post-MVP surfaces are not required.
- Cosmetic drift, prose polish, and non-authoritative examples should not block MVP readiness.

## 7. Reviewer Instructions

Review in this order:

1. Identify the MVP goal, first useful flow, authoritative source material, required artifacts, and target users or callers.
2. Apply an MVP scope filter. Treat only the first useful implementation path and its required contracts, states, artifacts, decisions, and obvious failures as blocking scope.
3. Apply prose lint to requirement-bearing MVP text. Flag `system decides`, `best effort`, `if needed`, `eventually`, weak `should`, and unqualified `may` when they control implementation behavior.
4. Apply structural lint to MVP schemas, APIs, config, artifacts, and pseudocode. Check for undefined enums, missing field types, required/nullable mismatch, missing errors, undefined identifiers, and inconsistent keys.
5. Evaluate baseline couplings where they affect MVP behavior:
   - Terminology <-> Data Contracts
   - State Model <-> Lifecycle
   - Decision Rules <-> Failure Handling
   - Time Semantics <-> Ordering
   - Idempotency <-> Replay
6. Evaluate declared or obvious project-specific couplings only when they affect MVP implementation.
7. Classify each finding as blocker, major, or minor using observable evidence from the spec.
8. Prefer one root-cause finding when a single ambiguity creates multiple downstream issues.
9. For each blocker or major, name the affected section, the missing or conflicting requirement, and the minimum correction needed.

When using numeric scoring, use the v6 scale:

- `0` = missing
- `1` = acknowledged but undefined
- `2` = defined but not validated
- `3` = explicit and validated

Under mvp-v1, scores guide severity. A `0` or `1` in MVP scope clarity, core flow, required interfaces, data contracts, state legality, authority boundaries, artifact integrity, obvious failure handling, or acceptance criteria usually indicates a blocker. A `2` in those areas usually indicates a major unless the missing validation prevents implementation.

## 8. Convergence Interpretation

A specification converges under mvp-v1 when all of the following are true:

- No unresolved blocker findings remain.
- The MVP goal and first useful flow are clear enough to build.
- Required MVP interfaces, data contracts, artifacts, state transitions, decision rules, obvious failure paths, and acceptance criteria are defined.
- Baseline couplings are internally consistent for MVP-scope behavior.
- Any remaining major findings are either outside the first useful implementation path or have an explicit deferral boundary that does not change MVP interfaces, states, artifacts, failure behavior, or acceptance outcomes.
- Remaining minor findings do not affect MVP buildability or deterministic core behavior.

mvp-v1 convergence means the spec is ready to start the first useful implementation. It does not mean the spec is production-complete, governance-ready, exhaustively traceable, or fully validated for long-term scale and evolution.
