# Rubrics Profiles And Feedback Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: rubrics_profiles_and_feedback_spec
target_spec_role: leaf_spec
-->

## CANONICAL RUBRICS AND WORKFLOWS

Whetstone separates the convergence quality bar from operational run behavior.

`rubric_profile` defines the standard being evaluated. It answers: "What quality bar is this draft being judged against?"

`workflow` defines the execution preset. It answers: "How should the Orchestrator schedule, halt, summarize, and require artifacts for this run?"

The terms MUST NOT be used interchangeably. A workflow MAY select a default rubric profile, but the persisted run identity MUST record both values independently.

### Canonical Rubric Profiles

Whetstone SHOULD ship canonical built-in rubric profiles that are always addressable by stable name and version:

- `governance-v6`: highest strictness; intended for final/strict governance-grade convergence.
- `standard-v1`: balanced technical convergence; intended for normal production-ready specs.
- `mvp-v1`: implementation-readiness convergence; prioritizes scope, buildability, acceptance criteria, and blocking ambiguity over exhaustive governance sharpness.
- `exploratory-v1`: early shaping convergence; intended for surfacing major gaps without forcing final-grade completeness.

Built-in rubric profiles MUST be immutable once released. If a built-in rubric changes materially, it MUST receive a new profile version.

Custom rubrics are allowed only when `rubric_source = custom`. Custom rubric runs MUST provide:

- `rubric_label`: non-empty human-readable label
- `rubric_path`: concrete path
- `rubric_content_hash`: Orchestrator-computed hash of the normalized rubric content

The Orchestrator MUST NOT infer that two custom rubrics are equivalent from label similarity. Hash identity is the replay authority.

### Workflow Presets

The initial canonical workflows are:

- `exploratory`: early review workflow; may default to `exploratory-v1`, `mid/permissive`, fewer rounds, and non-blocking decision summaries.
- `mvp`: MVP-readiness workflow; may default to `mvp-v1`, `mid/strict`, focused round budgets, and decision summaries optimized for approve/build decisions.
- `standard`: default production-spec workflow; may default to `standard-v1`, `final/strict`, full Phase 1 and Phase 2 gates.
- `governance`: highest-assurance workflow; MUST default to `governance-v6`, `final/strict`, declaration workflow, decision summary, telemetry when available, and full artifact validation.
- `custom`: explicitly configured workflow; MUST NOT silently inherit a built-in rubric unless configured.

`--workflow mvp` and any future `--mvp` shorthand are workflow selectors, not rubric definitions. The CLI MAY expose shorthand flags, but persisted configuration MUST normalize them to `workflow` plus explicit `rubric_profile`.

### Rubric Manifest

Before the first Phase 2 review, the Orchestrator MUST write `/rounds/rubric_manifest.json`.

`rubric_manifest.json` MUST include:

```yaml
workflow: string
rubric_profile: string
rubric_source: builtin | custom
rubric_label: string | null
rubric_path: string
rubric_content_hash: string
target_phase: mid | final
target_mode: permissive | strict
resolved_defaults:
  target_phase: mid | final
  target_mode: permissive | strict
  max_rounds: integer
  required_artifacts: [string]
configured_budgets:
  review_max_rounds: integer
  convergence_max_rounds: integer
  review_profile_budgets: object
  convergence_profile_budgets: object
  review_round_budget: integer
  convergence_round_budget: integer
  total_absolute_round_budget: integer
  effective_total_absolute_round_budget: integer
warnings: [string]
```

Phase 2 MUST NOT start unless rubric identity is explicit and manifest validation passes.

Rubric manifest budget fields MUST distinguish legacy global round fields from effective profile-level budgets. Operators MUST be able to see the actual scheduler budget used for profile-based review, even when legacy `review_max_rounds` or `convergence.max_rounds` remain present for compatibility.

For built-in rubrics:

- `rubric_profile` MUST be one of the built-in canonical profile names.
- `rubric_content_hash` MUST match the packaged rubric content used for prompt construction.
- If `rubric_path` points to a copied materialized rubric, the copied content hash MUST match the built-in profile hash.

For custom rubrics:

- `rubric_label` MUST be non-empty.
- The run start summary and manifest MUST mark the rubric as custom.
- The CLI SHOULD warn that custom rubric identity is hash-based and may not be comparable to built-in profile results.

Phase 2 prompt snapshots, convergence declarations, convergence failure reports, decision summaries, and strop/apply-back reports MUST include the manifest path or the full rubric identity tuple:

```text
(workflow, rubric_profile, rubric_source, rubric_label, rubric_content_hash, target_phase, target_mode)
```

This tuple is audit metadata. It MUST NOT replace `rubric_content_hash` as the deterministic replay primitive.

---

## REVIEW PROFILES

A review profile is a named review lens. It consists of:

- `name`: stable identifier used in artifacts and scheduling
- `focus`: controlled review concerns used in prompt construction and artifact metadata
- `prompt_guidance`: profile-specific instructions that tell the Reviewer what to emphasize and what not to over-expand
- optional `focus_anchors`: computable section anchors used to invalidate clean status when relevant sections mutate

Profiles are not rubrics. A rubric defines the quality bar. A profile defines the perspective used for one review pass.

```yaml
review_profiles:
  structural_integrity:
    focus: [authority_boundaries, state_machine_legality, cross_spec_consistency]

  determinism:
    focus: [hashing, replayability, idempotency]

  operability:
    focus: [failure_modes, observability, recovery]

  adversarial:
    focus: [ambiguity_attack, exploit_paths, assumption_breaking]

  convergence_strict_check:
    focus: [rubric_alignment, declaration_validity, strictness_gaps]

  buildability:
    focus: [core_flow, required_inputs_outputs, acceptance_criteria]

  consistency:
    focus: [terminology_consistency, command_option_consistency, artifact_reference_consistency]

  determinism_light:
    focus: [path_resolution, stable_ids, exit_codes, report_presence]

  operability_light:
    focus: [obvious_failure_modes, user_visible_errors, safe_non_destructive_behavior]

  mvp_readiness_check:
    focus: [mvp_scope, core_flow_buildability, deferred_hardening]

  scope_guard:
    focus: [scope_contract_alignment, over_expansion, deferred_surface_preservation]
```

Profile focus labels are review concerns, not section identifiers.

## REVIEW PROFILE SETS

A review profile set is a canonical bundle of Phase 1 profiles, Phase 2 profiles, and default per-profile round budgets. It answers: "Which lenses should Whetstone use for this kind of spec?"

`review.profile_set` MUST be one of:

- `stateful_system`: default high-assurance profile set for stateful, artifact-producing, replay-sensitive systems. This is the historical Whetstone behavior and is appropriate for Foreman-like specs.
- `balanced_mvp`: reduced-budget version of the stateful profile stack for MVPs that still have meaningful state, artifacts, lifecycle, or replay concerns.
- `utility_mvp`: lighter profile set for small CLIs/tools and utility workflows where buildability, consistency, visible determinism, and obvious failure behavior matter more than exhaustive replay/adversarial pressure.
- `governance`: highest-pressure profile set; adds adversarial Phase 1 review and uses strict Phase 2 review pressure.

Default profile-set schedules:

```yaml
profile_sets:
  stateful_system:
    phase_1:
      - structural_integrity
      - determinism
      - operability
    phase_2:
      - convergence_strict_check
      - adversarial
      - convergence_strict_check
    default_budgets:
      phase_1: {structural_integrity: 10, determinism: 10, operability: 10}
      phase_2: {convergence_strict_check: 10, adversarial: 10}

  balanced_mvp:
    phase_1:
      - structural_integrity
      - determinism
      - operability
    phase_2:
      - convergence_strict_check
      - adversarial
      - convergence_strict_check
    default_budgets:
      phase_1: {structural_integrity: 7, determinism: 7, operability: 6}
      phase_2: {convergence_strict_check: 6, adversarial: 4}

  utility_mvp:
    phase_1:
      - buildability
      - consistency
      - determinism_light
      - operability_light
    phase_2:
      - mvp_readiness_check
      - scope_guard
      - mvp_readiness_check
    default_budgets:
      phase_1: {buildability: 4, consistency: 4, determinism_light: 4, operability_light: 3}
      phase_2: {mvp_readiness_check: 4, scope_guard: 3}

  governance:
    phase_1:
      - structural_integrity
      - determinism
      - operability
      - adversarial
    phase_2:
      - convergence_strict_check
      - adversarial
      - convergence_strict_check
    default_budgets:
      phase_1: {structural_integrity: 10, determinism: 10, operability: 10, adversarial: 8}
      phase_2: {convergence_strict_check: 10, adversarial: 10}
```

Explicit `review.profile_budgets` and `convergence.profile_budgets` override only profiles present in the selected profile set. Unknown budget keys are ignored for scheduling and MAY be surfaced in operator diagnostics.

`mvp_readiness_check` is a Phase 2 convergence-acceptance profile for `utility_mvp` in the same way that `convergence_strict_check` is the convergence-acceptance profile for stricter profile sets.

For clean-status invalidation, each review profile MUST also have computable focus anchors. Focus anchors are canonical Markdown section IDs derived from the current draft using the section-index rule in this spec.

Default focus anchors:

```yaml
profile_focus_anchors:
  structural_integrity:
    - core-roles
    - halting-conditions-ordered-precedence
    - halt-artifact-matrix
    - review-profiles
    - round-strategy-adaptive
    - round-scheduling-algorithm
    - artifact-validation-policy
    - artifact-schemas-minimum-required-fields
    - conflict-model
    - editor-decline-taxonomy
    - conflict-escalation
    - state-machine-full-transitions

  determinism:
    - issue-and-conflict-identity
    - phase-gated-feedback-classification
    - content-normalization-and-hashing
    - oscillation-detection-full-definition
    - reproducibility

  operability:
    - primary-outputs
    - configuration
    - halt-artifact-matrix
    - artifact-validation-policy
    - phase-2-failure-handling
    - phase-1-failure-handling
    - reproducibility

  adversarial:
    - baseline-review-invariants
    - phase-gated-feedback-classification
    - oscillation-detection-full-definition
    - conflict-model
    - target-matrix-precedence

  convergence_strict_check:
    - accepted-draft-definition
    - round-scheduling-algorithm
    - phase-2-failure-handling
    - target-matrix-precedence
    - convergence-declaration
```

When the draft title includes a versioned root heading, the Orchestrator MUST resolve these anchors by suffix match against the canonical section index. If zero or multiple section IDs match a focus anchor suffix, configuration is invalid and the Orchestrator MUST halt with `CONFIG_INVALID`.

---

## SEVERITY NORMALIZATION FUNCTION

Severity ordering:

blocker > major > minor > nit

Each component maps to one of:
- blocker
- major
- minor
- nit
- null

null means not applicable and is excluded from max().

If all components are null, normalized_severity = nit.

normalized_severity = max(
  baseline_severity,
  authority_impact,
  determinism_impact,
  rubric_impact
)

Profiles may not elevate severity independently.
They only increase detection sensitivity.

Example:
- The adversarial profile may detect an ambiguity not noticed earlier.
- It may not call that ambiguity a blocker unless the ambiguity violates a baseline invariant, authority boundary, determinism requirement, or target rubric requirement.

`baseline_severity` SHOULD be non-null for every reported issue. If a reviewer cannot assign a baseline severity, it MUST set `baseline_severity = null` and provide `severity_rationale`.

---

## BASELINE REVIEW INVARIANTS

Every review MUST check:

- blocker issues
- authority boundary violations
- cross-spec inconsistencies
- undefined behavior
- replay/hash determinism violations

Profiles intensify scrutiny but do not replace or override baseline invariants.

---

## PHASE-GATED FEEDBACK CLASSIFICATION

Reviewer feedback classification is phase-gated.

Phase 1:
- oscillation classification fields are optional
- reviewers may focus on discovery and exploratory issue finding
- orchestrator MUST NOT use missing oscillation classifications as a validation failure
- oscillation detection is limited to draft-level cycle and exact mechanical churn signals
- only draft-hash cycle detection may produce `HALTED_OSCILLATION` in Phase 1
- Phase 1 mechanical churn MUST recommend `freeze_prior_decision` and MUST NOT halt by itself

Phase 2:
- every feedback item MUST include a reviewer-proposed `oscillation_key` input
- the reviewer prompt MUST satisfy the Phase 2 reviewer prompt requirements
- the reviewer MUST choose from fixed enums and MUST NOT invent categories
- orchestrator MUST reject Phase 2 feedback items with missing or invalid oscillation classification fields
- orchestrator MUST canonicalize valid reviewer-proposed keys before persistence

Rationale:
Phase 1 feedback is necessarily exploratory and varied. Phase 2 feedback occurs when the spec should be mostly stable, so recurring disagreements can be classified consistently enough for deterministic oscillation detection.

Oscillation history starts fresh at the Phase 2 boundary. The orchestrator MUST NOT retroactively classify Phase 1 feedback for feedback-level oscillation continuity.

Oscillation tracking is independent of issue identity. `issue_fingerprint` remains a stricter per-issue artifact identity that may include prose-sensitive fields; `oscillation_key` is the cross-round concern identity used for Phase 2 oscillation detection. A feedback item may fail to match a previous issue by `issue_fingerprint` and still participate in oscillation detection through the same `oscillation_opposition_key`.

Operators should expect these identity systems to disagree sometimes. Conflict escalation uses `conflict_fingerprint`, which incorporates issue identity and is therefore stricter and more prose-sensitive. Oscillation detection uses `oscillation_opposition_key`, which is classification-based and usually the more reliable Phase 2 signal for recurring churn. In true late-stage churn, oscillation detection may fire before conflict escalation because the reviewer can rephrase the same concern enough to produce different issue fingerprints.

Known limitation:
`scope` is part of the opposition key. If a reviewer drifts between `local` and `structural` for the same underlying concern across rounds, the orchestrator will treat those as separate oscillation concerns. This is intentional to avoid collapsing meaningfully different local and structural issues.

### Oscillation Key Canonicalization

Reviewer proposes; Orchestrator canonicalizes.

In Phase 2, the reviewer MUST provide only semantic classification fields:

```yaml
oscillation_key:
  section_id: string
  concern_type: string
  direction: string
  scope: string
```

The reviewer MUST NOT author `fingerprint` or `opposition_key`.

Before accepting Phase 2 feedback, the Orchestrator MUST:
- validate `section_id` against the current canonical section index
- validate `concern_type`, `direction`, and `scope` against the fixed enums
- compute `fingerprint`
- compute `opposition_key`
- persist the canonicalized `oscillation_key`

If `section_id` is not in the canonical section index, the reviewer artifact is invalid and MUST be retried or halted according to artifact validation policy.

The persisted canonical `oscillation_key` fields are:


```yaml
section_id: string
concern_type:
  - clarity_gap
  - completeness_gap
  - consistency_violation
  - determinism_violation
  - authority_violation
  - scope_violation
  - redundancy
  - precision_gap
direction:
  - add
  - remove
  - modify
  - clarify
  - constrain
  - relax
scope:
  - local
  - structural
fingerprint: string
opposition_key: string
```

`section_id` is the canonical primary anchor for the issue. It MUST be a single section ID, not a list. If a concern spans multiple sections, the reviewer MUST choose one primary anchor and MAY include the rest in `affected_sections`.

The Orchestrator MUST derive the canonical section index from the current `draft_before.md` Markdown heading paths using lowercase slug words joined by hyphens. If the same heading path repeats, append `#N` using the one-based occurrence count. The Phase 2 reviewer prompt MUST include the allowed section IDs, and reviewers MUST choose from that list.

When `oscillation_key` is present, `oscillation_key.section_id` is the primary anchor and `affected_sections` lists all touched sections, including secondary sections. The primary anchor SHOULD also appear in `affected_sections` for consistency.

`concern_type` definitions:
- `clarity_gap`: section is ambiguous, undefined, or unclear
- `completeness_gap`: section is missing required content, rule, definition, or edge case
- `consistency_violation`: section contradicts another section or prior decision
- `determinism_violation`: section permits non-deterministic behavior
- `authority_violation`: section violates a defined role, boundary, or authority rule
- `scope_violation`: section addresses something out of scope or omits something in scope
- `redundancy`: section duplicates content elsewhere
- `precision_gap`: section is directionally correct but under-specified, such as missing numeric, enum, schema, or threshold detail

`direction` definitions:
- `add`: add missing content or behavior
- `remove`: remove content or behavior
- `modify`: change content when no more specific direction applies
- `clarify`: clarify ambiguous content without materially changing scope or strictness
- `constrain`: make behavior stricter, narrower, or more bounded
- `relax`: make behavior looser, broader, or less restrictive

Direction opposition is symmetric:

```yaml
opposition_pairs:
  - [add, remove]
  - [constrain, relax]
```

`modify` and `clarify` do not have automatic opposites. Repeated `modify` or repeated `clarify` on the same key is a churn signal, not a flip-flop by default.

A sequence such as `add -> modify -> modify -> modify` for the same opposition key is classified as feedback churn, not feedback flip-flop, unless an opposing direction from the opposition pairs appears.

`clarity_gap` concerns will commonly use `direction = clarify`. Because `clarify` has no automatic opposite, clarity concerns generally produce churn signals rather than flip-flop signals.

`scope` definitions:
- `local`: issue targets a specific rule, sentence, definition, field, or invariant
- `structural`: issue targets section organization, responsibility boundary, lifecycle shape, or cross-section architecture

Oscillation fingerprint:

```text
oscillation_fingerprint = SHA256(
  section_id + "|" +
  concern_type + "|" +
  direction + "|" +
  scope
)
```

Oscillation opposition key:

```text
oscillation_opposition_key = SHA256(
  section_id + "|" +
  concern_type + "|" +
  scope
)
```

The fingerprint includes direction. Flip-flop detection groups by `oscillation_opposition_key` and compares direction across rounds.

### Phase 2 Reviewer Prompt Requirements

The Phase 2 reviewer prompt MUST include:
- the full `concern_type` enum with one-line definitions
- the full `direction` enum with one-line definitions
- the `scope` enum with one-line definitions
- the symmetric opposition pairs
- the canonical section ID list for the current draft
- instruction to choose the nearest enum value and never invent categories
- instruction to choose `section_id` from the canonical section ID list
- instruction that the reviewer MUST NOT author `fingerprint` or `opposition_key`
- instruction that `modify` SHOULD be used only when no more specific direction applies
- examples of valid `oscillation_key` classifications

These requirements are prompt-boundary discipline. Schema validation is the safety net, not the primary mechanism for obtaining stable classifications.

---
