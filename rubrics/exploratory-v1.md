# Whetstone Exploratory-v1 Rubric

Derived from: Convergence Rubric v6
Profile version: exploratory-v1
Intended use: Exploratory-v1 is for early-stage specification shaping, risk discovery, and concept clarification before a system is ready for production-grade convergence review. It helps reviewers identify missing concepts, contradictions, unclear authority boundaries, untestable assumptions, and goals that are too vague to guide the next round of specification work.
Strictness level: low
Target fit: `target_phase=mid`, `target_mode=permissive`

## Derivation Note

This profile preserves v6's concerns for determinism, authority boundaries, artifact integrity, explicit acceptance evidence, state legality, failure handling, coupling awareness, and bias-resistant review. It intentionally relaxes governance-grade declaration requirements, exhaustive scoring, final convergence gates, Tier 5 scale/evolution checks, complete schemas, complete state machines, full traceability, and final acceptance criteria unless their absence blocks further specification.

## 1. Purpose

The Exploratory-v1 rubric determines whether an early-stage specification is clear enough to continue shaping without concealing major implementation risks.

It is not a final convergence rubric. It is a directional review tool for finding the highest-value gaps while the spec is still allowed to be incomplete.

A review under this profile should answer:

- What is the system trying to accomplish?
- Which concepts are missing, overloaded, or contradictory?
- Which authority boundaries or sources of truth are unclear?
- Which assumptions cannot yet be tested or validated?
- Which gaps would block meaningful next-stage specification?

## 2. Applicability

Use this profile when the spec is in early exploration and the expected output is feedback, risk discovery, or a next-specification plan.

In Whetstone runtime terms, "early" is a workflow intent rather than a target phase. Exploratory runs therefore resolve to `target_phase: mid` and `target_mode: permissive`.

This profile applies well to:

- concept notes
- early technical proposals
- first-pass product or system specs
- architecture sketches
- protocol or workflow drafts
- pre-MVP shaping documents

This profile does not require:

- a complete Convergence Declaration
- full schemas
- complete state machines
- exhaustive lifecycle coverage
- complete API contracts
- final acceptance criteria
- Tier 5 scale and evolution review

However, partial artifacts that appear in the spec are reviewable. If the spec includes schemas, APIs, config, pseudocode, states, lifecycle rules, or failure handling, reviewers MUST flag contradictions, undefined identifiers, and authority ambiguity that would mislead further specification.

## 3. Blocking Criteria

A finding is blocking when it prevents useful continuation of specification work or makes the intended system impossible to reason about.

Block the exploratory review if any of the following are true:

- The primary goal or intended outcome is missing.
- The spec contains two or more incompatible goals and gives no precedence rule.
- The core user, actor, system, or job flow cannot be identified.
- A named authority boundary or source of truth is contradicted elsewhere in the spec.
- The spec assigns the same decision to multiple authorities without a precedence rule.
- A central term is used in conflicting ways that would change implementation behavior.
- The spec depends on an external artifact, registry, schema, API, or policy that is referenced but not identifiable.
- A required input or output is named, but its owner, producer, or consumer is impossible to determine.
- The spec includes state-changing behavior but does not identify what state changes.
- The spec includes irreversible, destructive, financial, security, privacy, or user-visible failure cases without any stated failure behavior.
- The spec makes an assumption essential to the design, but there is no observable way to confirm or reject it.
- The document claims readiness for implementation, MVP build, production use, or final convergence while core goals, authority, or state legality remain undefined.

Blocking issues SHOULD be few and concrete. A reviewer SHOULD identify the smallest missing decision that would unblock the next useful specification pass.

## 4. Major Issue Criteria

A finding is major when it creates significant ambiguity, likely implementation divergence, or hidden risk, but does not prevent further specification work.

Flag a major issue when any of the following are true:

- A core concept is named but not defined enough to distinguish it from adjacent concepts.
- Terminology and data shape appear coupled, but the relationship is unclear.
- A data contract is sketched, but required fields, key identifiers, or nullability are inconsistent across examples.
- An enum, status, type, or category is referenced but not defined enough to support later validation.
- A state, lifecycle stage, or transition is implied but not named.
- A state transition is named but its trigger, actor, or legality condition is unclear.
- Decision rules exist but do not say who or what applies them.
- Failure handling is mentioned only as "best effort," "if needed," "eventually," "system decides," or equivalent unresolved discretion.
- Time semantics affect behavior, but ordering, freshness, timeout, or replay expectations are unclear.
- Idempotency, replay, retries, or duplicate handling are relevant but not acknowledged.
- A partial schema, API, config, or pseudocode block contains undefined identifiers, fields without types, inconsistent keys, or missing error paths.
- Acceptance criteria are present but cannot be observed, tested, or falsified.
- The spec mixes current scope with future scope in a way that obscures what the next implementation or specification pass should address.
- A declared or obvious coupling from v6 is relevant but underdeveloped on both sides.

Baseline couplings to consider, when relevant:

- Terminology <-> Data Contracts
- State Model <-> Lifecycle
- Decision Rules <-> Failure Handling
- Time Semantics <-> Ordering
- Idempotency <-> Replay

For Exploratory-v1, a coupling gap is major when both sides are below "defined enough to continue" and the gap could cause divergent design choices.

## 5. Minor Issue Criteria

A finding is minor when it would improve clarity, reviewability, or later convergence but does not materially block exploration.

Flag a minor issue when any of the following are true:

- A term should be renamed or narrowed for consistency, but current usage is understandable.
- A future requirement is useful but should be separated from current exploratory scope.
- A non-core example is incomplete but does not affect the main flow.
- Acceptance criteria are directional but should become more observable in a later profile.
- A schema, API, config, or pseudocode fragment would benefit from stricter typing later.
- A failure case is low impact and can be deferred with an explicit note.
- A coupling is probably relevant but not yet central to the exploratory decision being made.
- Review phase, scoring, or declaration metadata is incomplete but not needed for the current exploratory purpose.

Minor issues SHOULD NOT be used to force premature closure.

## 6. Non-Goals / Intentionally Relaxed Checks

Exploratory-v1 intentionally does not require:

- a complete Convergence Declaration
- project-specific declared couplings
- independent scoring verification
- numeric scoring for every v6 tier
- phase advancement proof
- final convergence conditions
- all Tier 1 dimensions at `3`
- all Tier 2 dimensions at `>= 2`
- Tier 3 critical dimension declaration
- Tier 4 resilience completeness
- Tier 5 entry mode, trigger analysis, or immutability checks
- exhaustive traceability across files, manifests, or versions
- complete schemas for every data structure
- complete state machines
- complete lifecycle rules
- complete operational runbooks
- full edge-case coverage
- final acceptance test suites

The reviewer MAY mention these areas as future work, but MUST NOT block the exploratory profile solely because they are incomplete.

## 7. Reviewer Instructions

Review only what the document actually says. Do not give credit for implied design intent unless the implication is directly supported by observable text.

Use severity as follows:

- Blocking: prevents useful next specification work.
- Major: likely to cause divergent implementation or hidden risk.
- Minor: improves clarity or later convergence but can wait.

When reviewing, prioritize:

1. goals and intended outcomes
2. core actors, users, systems, and jobs
3. authority boundaries and sources of truth
4. terminology consistency
5. state-changing behavior and state legality
6. decision rules and failure handling
7. testable assumptions and acceptance evidence
8. relevant v6 baseline couplings

Apply prose lint directionally. Terms such as "system decides," "best effort," "if needed," "eventually," "should," and unqualified "may" are not automatic blockers in Exploratory-v1. They become major or blocking only when they hide a decision needed for the next specification pass.

Apply structural lint to included technical artifacts. If schemas, APIs, config, or pseudocode appear, flag:

- enums referenced but not defined
- fields without types when type affects behavior
- nullable versus required mismatch
- missing error responses when errors affect the core flow
- undefined identifiers
- inconsistent key definitions

The reviewer SHOULD produce concrete findings with:

- the ambiguous or missing item
- why it matters
- what decision or evidence would resolve it
- whether it must be fixed now or can wait

## 8. Convergence Interpretation

Exploratory-v1 does not certify final convergence.

A spec passes Exploratory-v1 when:

- the primary goal is identifiable
- core actors or systems are identifiable
- no unresolved contradiction blocks further specification
- authority boundaries are at least identifiable where they affect core behavior
- state-changing behavior is understandable at the concept level
- critical assumptions are named or made testable enough for the next pass
- blocking failure-handling gaps are surfaced
- the reviewer can state a plausible next step toward MVP, standard, or governance review

A passing Exploratory-v1 result means the spec is fit for continued shaping. It does not mean the spec is ready to build.

A conditional pass means the spec can continue only after listed blocking questions are answered.

A failing Exploratory-v1 result means the spec lacks enough goal, authority, concept, or state clarity to support useful next-stage specification.
