# WHETSTONE - AI SPEC CONVERGENCE ORCHESTRATOR (0.22 - STRICT CANDIDATE)

## Purpose

Automate iterative technical review between AI clients (e.g., Claude Code, Codex) to drive a spec from v0.1 -> converged (mid/final, permissive/strict), with controlled multi-perspective review per round, deterministic convergence behavior, explicit failure handling, and fully specified primitives.

Reading guide: This spec defines six interacting subsystems: round scheduling, severity normalization, identity for issues/conflicts/oscillation, rubric gap tracking, convergence declaration, and artifact validation. The state machine and halting conditions sections describe how these subsystems compose into deterministic execution.

Version `0.22` separates editor resolution from reviewer-verified clean status so round advancement and convergence require a clean review of the current draft, not only an editor claim that findings were handled.

---

## CORE ROLES

- Editor:
  Owns spec mutation, applies/declines feedback, preserves architectural integrity, resolves conflicts within defined authority.

- Reviewer:
  Produces structured, classified feedback under a defined review profile.

- Orchestrator:
  Owns state, round scheduling, normalization, oscillation detection, conflict escalation, artifacts, and stopping conditions.

---

## PRIMARY INPUTS

- spec.md
- convergence_rubric.md
- orchestrator_config.yaml

---

## PRIMARY OUTPUTS

- spec.md (mutated per round)
- spec.history.md (append-only)
- convergence_declaration.md (created/updated in Phase 2)
- /rounds/round-N/
  - reviewer_feedback.json
  - reviewer_working_notes.md (human-readable; not schema-bound)
  - editor_summary.json
  - draft_before.md
  - draft_after.md
  - unresolved_issues.json
  - decision_points.json
  - rubric_gaps.json (Phase 2 only)
  - profile_used.yaml
  - prompt_snapshot.json
  - prompt_snapshots/
    - {client_role}-{artifact_name}-attempt-{attempt_number}.json
  - client_telemetry/
    - {client_role}-{artifact_name}-attempt-{attempt_number}.json
- /rounds/oscillation_report.json (if detected)
- /rounds/conflict_report.json (if escalated)
- /rounds/technical_failure_report.json (if Phase 1 fails)
- /rounds/convergence_failure_report.json (if Phase 2 fails)
- /rounds/config_validation_error.json (if preflight configuration validation fails)
- /rounds/artifact_validation_error.json (if client artifact validation retries are exhausted)
- /rounds/decision_register.json (if any decision point is captured)
- /rounds/decision_register.md (human-readable decision register, if any decision point is captured)
- /rounds/decision_summary.json (if decision summary generation is enabled and any decision point is captured)
- /rounds/decision_summary.md (human-readable decision summary, if generated)
- /rounds/decision_intervention_request.json (if decision intervention is required)
- /rounds/rubric_manifest.json (required before Phase 2 review begins)

---

## CONFIGURATION

```yaml
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
declaration_path: ./convergence_declaration.md

workflow: standard             # exploratory | mvp | standard | governance | custom

clients:
  editor:
    name: claude-code
    command: claude
    version: ""   # MUST be a concrete version string
    model: ""     # MUST be a concrete model identifier
  reviewer:
    name: codex
    command: codex
    version: ""   # MUST be a concrete version string
    model: ""     # MUST be a concrete model identifier

review:
  max_rounds: 12

convergence:
  enabled: true
  target_phase: final        # mid | final
  target_mode: strict        # permissive | strict
  rubric_profile: governance-v6
  rubric_source: builtin      # builtin | custom
  rubric_label: ""            # REQUIRED when rubric_source = custom
  rubric_path: ./convergence_rubric.md
  max_rounds: 8

decision_points:
  enabled: true
  mode: end_of_cycle          # end_of_cycle | intervention
  summary:
    enabled: true
    include_interpretive_summary: false
  intervention_thresholds:
    severities: [blocker, major]
    trigger_on_requirement_strength_change: true
    trigger_on_authority_boundary_change: true
    trigger_on_scope_change: true
    trigger_on_new_enum_or_error_code: true
```

Before entering `TECHNICAL_REVIEW`, the Orchestrator MUST validate configuration.

Client `version` and `model` fields MUST be non-empty strings after trimming whitespace. If any required client field is empty, the Orchestrator MUST halt before the first review round and produce `/rounds/config_validation_error.json` identifying the invalid fields. This preflight failure does not consume a Phase 1 or Phase 2 round.

---

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
warnings: [string]
```

Phase 2 MUST NOT start unless rubric identity is explicit and manifest validation passes.

For built-in rubrics:

- `rubric_profile` MUST be one of the built-in canonical profile names.
- `rubric_content_hash` MUST match the packaged rubric content used for prompt construction.
- If `rubric_path` points to a copied materialized rubric, the copied content hash MUST match the built-in profile hash.

For custom rubrics:

- `rubric_label` MUST be non-empty.
- The run start summary and manifest MUST mark the rubric as custom.
- The CLI SHOULD warn that custom rubric identity is hash-based and may not be comparable to built-in profile results.

Phase 2 prompt snapshots, convergence declarations, convergence failure reports, decision summaries, and apply-back reports MUST include the manifest path or the full rubric identity tuple:

```text
(workflow, rubric_profile, rubric_source, rubric_label, rubric_content_hash, target_phase, target_mode)
```

This tuple is audit metadata. It MUST NOT replace `rubric_content_hash` as the deterministic replay primitive.

---

## HALTING CONDITIONS (ORDERED PRECEDENCE)

1. Clean convergence achieved
2. Blocker-level conflict escalation triggered
3. Oscillation stop triggered
4. Artifact validation failure exhausted
5. Decision intervention required
6. max_rounds reached

The first condition satisfied halts execution.

---

## HALT ARTIFACT MATRIX

clean convergence achieved:
- terminal_state: CONVERGED
- required artifacts:
  - spec.md
  - spec.history.md
  - convergence_declaration.md

blocker-level conflict escalation:
- terminal_state: HALTED_CONFLICT
- required artifacts:
  - conflict_report.json
  - latest draft_after.md
  - spec.history.md
- if in Phase 2, also produce:
  - convergence_failure_report.json

oscillation stop:
- terminal_state: HALTED_OSCILLATION
- required artifacts:
  - oscillation_report.json
  - latest draft_after.md
  - spec.history.md
- if in Phase 2, also produce:
  - convergence_failure_report.json

max_rounds reached:
- terminal_state: TARGET_NOT_REACHED
- required artifacts:
  - latest draft_after.md
  - spec.history.md
- if in Phase 1, also produce:
  - technical_failure_report.json
- if in Phase 2, also produce:
  - convergence_failure_report.json

preflight configuration invalid:
- terminal_state: CONFIG_INVALID
- required artifacts:
  - config_validation_error.json

artifact validation failure exhausted:
- terminal_state: HALTED_ARTIFACT_INVALID
- required artifacts:
  - artifact_validation_error.json
  - latest validated draft_after.md, or current round draft_before.md when no validated draft_after.md exists
  - spec.history.md
- if in Phase 1, also produce:
  - technical_failure_report.json
- if in Phase 2, also produce:
  - convergence_failure_report.json

decision intervention required:
- terminal_state: PAUSED_DECISION
- required artifacts:
  - decision_intervention_request.json
  - decision_register.json
  - decision_register.md
  - latest draft_after.md
  - spec.history.md

---

## ACCEPTED DRAFT DEFINITION

A draft is considered accepted if:
- zero blockers globally
- zero major issues globally

This is used for:
- last_accepted_draft_hash
- convergence readiness baseline

Accepted draft and clean profile are intentionally different scopes.

Accepted draft is stricter than some convergence targets and is required before Phase 2 regardless of target policy.

---

## SPEC VERSION LIFECYCLE

Spec version labels express maturity:
- `0.x` versions are Phase 1 stabilization drafts.
- whole-number major versions (`1.0`, `2.0`, etc.) indicate the spec has passed Phase 1 acceptance and entered Phase 2 convergence.
- post-entry Phase 2 decimal versions (`1.1`, `1.2`, etc.) indicate accepted mutating convergence revisions after Phase 2 entry.

Version stamping is Orchestrator-owned. The Editor MUST NOT choose, increment, decrement, or otherwise modify the visible spec version label unless the Orchestrator explicitly supplies that exact version label as part of the editable draft.

For versioned specs, the Orchestrator MUST stamp accepted mutating rounds with a new visible version label before computing and persisting the final `draft_after_hash`. A spec is versioned when its root heading contains a numeric version label. If no numeric root-heading version exists, the Orchestrator MAY skip version stamping and MUST continue to use hashes and round artifacts as rollback authority.

Version stamping rules:

- Phase 1 accepted mutating revision: increment the fractional stabilization version by one hundredth.
- Phase 1 non-mutating round: do not change the version label.
- Phase 1 rejected or unresolved round: do not change the version label.
- Phase 2 entry: promote to the smallest whole major version that is greater than or equal to the current numeric version, with a minimum of `1.0`.
- Phase 2 accepted mutating revision after entry: increment the first decimal place under the current major version.
- Phase 2 non-mutating round: do not change the version label.
- Phase 2 rejected or unresolved round: do not change the version label.
- Clean convergence declaration generation alone does not change the version label unless the same accepted round also mutates `spec.md`.

Examples:
- Phase 1 accepted mutation: `0.17` stamps to `0.18`
- Phase 1 accepted mutation: `0.99` stamps to `1.00`, but this does not by itself authorize Phase 2 entry
- `0.17` promotes to `1.0`
- `1.7` promotes to `2.0`
- `2.0` remains `2.0`
- Phase 2 accepted mutation: `1.0` stamps to `1.1`
- Phase 2 accepted mutation: `1.9` stamps to `1.10`

Phase 2 entry promotion MUST happen only after the accepted-draft gate is satisfied and all required Phase 1 clean-profile conditions are met. Invoking a Phase 2 command directly does not by itself authorize version promotion.

Each version stamp is an Orchestrator-owned mutation. It MUST be persisted to `spec.md`, recorded in `spec.history.md`, and reflected in the affected round snapshot:

- Phase 1 and post-entry Phase 2 accepted mutating revisions: reflected in that round's `draft_after.md`.
- Phase 2 entry promotion: reflected in the Phase 2 `draft_before.md` snapshot for the first convergence review.

`spec.history.md` MUST record:

- round number or transition name
- phase
- previous version label
- stamped version label
- draft hash before stamping
- draft hash after stamping

Rollback authority remains the round artifacts and hashes. Version labels are human navigation aids and MUST NOT replace hash validation for replay, audit, or rollback correctness.

---

## REVIEW PROFILES

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
```

Profile focus labels are review concerns, not section identifiers.

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

## ROUND STRATEGY (ADAPTIVE)

```yaml
round_strategy:
  phase_1:
    - profile: structural_integrity
      skip_if_clean: true
      repeat_if_blockers: true
      max_repeats: 2
    - profile: determinism
      skip_if_clean: true
      repeat_if_blockers: true
      max_repeats: 2
    - profile: operability
      skip_if_clean: false
      repeat_if_blockers: true
      max_repeats: 1

  phase_2:
    - profile: convergence_strict_check
      repeat_if_blockers: true
      max_repeats: 2
    - profile: adversarial
      repeat_if_blockers: true
      max_repeats: 2
    - profile: convergence_strict_check
      repeat_if_blockers: true
      max_repeats: 2
```

## ROUND SCHEDULING ALGORITHM

Phase 1 executes configured profiles in order.

For each Phase 1 profile:
- run the profile unless `skip_if_clean = true` and the current draft already has a valid clean result for that profile
- the profile result is clean only when the Reviewer review of `draft_before.md` for that round returns zero in-scope blocker issues and zero in-scope major issues
- editor resolution claims in `editor_summary.json` determine which findings remain unresolved after the edit, but they MUST NOT by themselves mark the reviewed profile clean
- if the profile returns in-scope blocker or major issues and `repeat_if_blockers = true`, schedule the same profile again after editor revision until a later Reviewer pass verifies the current draft clean or `max_repeats` is reached
- if the Reviewer pass is clean but the Editor mutates the draft in the same round, that clean result applies only to the pre-edit draft and MUST NOT mark the post-edit draft clean; the same profile requires a later clean verification pass unless a computable skip rule applies
- if the editor mutates any section whose canonical section ID matches the profile's resolved focus anchors, previous clean status for that profile is invalidated
- if the editor mutates only sections outside the profile's resolved focus anchors, previous clean status for that profile remains valid

Phase 1 completes only when:
- all non-skipped Phase 1 profiles have valid clean status, and
- the current draft is accepted.

Phase 2 executes configured profiles in order.

After each Phase 2 reviewer/editor cycle, the Orchestrator MUST evaluate halt conditions in the ordered precedence defined by this spec.

Phase 2 completion is checked after each validated Phase 2 review cycle and any resulting declaration revision, not only after the full configured Phase 2 profile sequence has been exhausted.

As in Phase 1, Phase 2 profile cleanliness is based on Reviewer findings against `draft_before.md`, not on Editor resolution claims in the same round. A Phase 2 profile with any in-scope blocker or major finding is not clean even if the Editor resolves every finding in `draft_after.md`; a later Reviewer pass must verify the resulting draft. A clean Reviewer pass followed by an Editor mutation also requires later verification of the mutated draft.

For `target_phase = final` and `target_mode = strict`, the Orchestrator MUST NOT declare clean convergence until every distinct Phase 2 profile name in the configured sequence has produced at least one clean result in Phase 2 for the current draft lineage.

`distinct Phase 2 profile` means unique by profile name, not sequence slot. In the default Phase 2 sequence, the two `convergence_strict_check` entries count as one distinct profile for this requirement, though both sequence positions may still run as scheduled.

If a Phase 2 profile is not run because of an explicit future skip condition, the skip condition MUST be persisted in `profile_used.yaml` and MUST count as a clean result only if the skip rule is computable from current artifacts.

If Phase 2 reaches the end of its configured profile sequence without clean convergence and Phase 2 round budget remains, the Orchestrator MUST start the Phase 2 profile sequence again from its first configured profile.

If Phase 2 reaches `convergence.max_rounds` before clean convergence, the Orchestrator MUST halt with `TARGET_NOT_REACHED` and produce `convergence_failure_report.json`.

Phase 2 completes only when clean convergence is achieved.

Clean convergence is achieved when:
- the current draft satisfies the configured target matrix,
- `convergence_declaration.md` exists,
- the declaration is accepted under the convergence declaration criteria, and
- every required distinct Phase 2 profile has produced a clean Reviewer result for the current unmodified draft lineage,
- no halt condition with higher or equal precedence has already fired.

---

## DEFINITION: CLEAN PROFILE

A profile is considered clean if:
- zero blocker issues within profile focus
- zero major issues within profile focus

Non-focus issues do not affect profile cleanliness.

A clean profile does not imply an accepted draft.

---

## ROUND BUDGET HANDLING

Unused Phase 1 rounds are not carried over.
Each phase has an independent max_rounds budget.

Phase 2 may halt before consuming its full budget if clean convergence is achieved.

Phase 1 max_rounds failure is a hard stop and does not proceed automatically to Phase 2.

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

## ISSUE AND CONFLICT IDENTITY

Every reviewer feedback item MUST include a stable `feedback_id`.

Every persisted issue MUST include:
- `issue_id`
- `issue_fingerprint`

Every conflict MUST include:
- `conflict_id`
- `conflict_fingerprint`

Fingerprints are computed by the Orchestrator from normalized semantic fields, not from round number, reviewer-provided identifiers, timestamps, or client-specific formatting.

Issue fingerprint:

```text
issue_fingerprint = SHA256(
  normalized(issue_type) + "\n" +
  normalized(affected_sections) + "\n" +
  normalized(invariant_violated) + "\n" +
  normalized(claim)
)
```

Conflict fingerprint:

```text
conflict_fingerprint = SHA256(
  normalized(conflict_type) + "\n" +
  normalized(sorted_participating_issue_fingerprints) + "\n" +
  normalized(conflict_claim)
)
```

`issue_id` and `conflict_id` are deterministic aliases:

```text
issue_id = "iss_" + first_16_hex_chars(issue_fingerprint)
conflict_id = "con_" + first_16_hex_chars(conflict_fingerprint)
```

The same issue or conflict across rounds is determined by matching fingerprint.

Reviewer-generated input MUST provide the semantic fields needed to compute issue identity: `issue_type`, `affected_sections`, `invariant_violated`, and `claim`. Reviewer-generated `issue_id`, `issue_fingerprint`, and `normalized_severity` are treated as input placeholders. The Orchestrator MUST recompute and inject canonical values before persisted artifact validation.

Normalization for fingerprint fields:
- trim leading/trailing whitespace
- collapse internal whitespace to a single space
- lowercase enum-like values
- sort arrays only when their order is semantically irrelevant
- preserve `affected_sections` order when the order is part of the claim
- sort `participating_issue_fingerprints` lexicographically before conflict fingerprint hashing

Canonical array serialization for fingerprint inputs:
- normalize each array element using the string normalization rules above
- preserve or sort element order according to the field-specific ordering rule
- join normalized elements with a single LF character
- use the resulting string as the `normalized(array_field)` hash input

Empty arrays serialize to the empty string.

Each feedback item represents exactly one issue. If a reviewer finds multiple issues in one passage, it MUST emit multiple feedback items and may reuse the same `affected_sections` values.

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

## ARTIFACT SCHEMAS (MINIMUM REQUIRED FIELDS)

`reviewer_feedback.json` MUST contain:

```yaml
round_number: integer
profile: string
reviewer:
  name: string
  version: string
  model: string
draft_hash: string
feedback:
  - feedback_id: string
    issue_id: string            # persisted canonical value; reviewer input may provide a placeholder
    issue_fingerprint: string   # persisted canonical value; reviewer input may provide a placeholder
    issue_type: string
    affected_sections: [string]
    baseline_severity: blocker | major | minor | nit | null
    authority_impact: blocker | major | minor | nit | null
    determinism_impact: blocker | major | minor | nit | null
    rubric_impact: blocker | major | minor | nit | null
    normalized_severity: blocker | major | minor | nit  # persisted canonical value recomputed by Orchestrator
    invariant_violated: string | null
    claim: string
    evidence: string
    recommended_change: string
    in_scope: boolean
    severity_rationale: string | null
    oscillation_key: null | object
```

`in_scope = true` means the feedback concerns the current draft, configured target, active review profile, baseline review invariants, or required artifacts. `in_scope = false` means the reviewer detected an issue outside those boundaries. Out-of-scope feedback MAY be persisted for auditability, but it MUST NOT block profile cleanliness, draft acceptance, convergence, or halt decisions unless the Editor or Orchestrator converts it into an in-scope issue with an explicit rationale.

`severity_rationale` MUST be non-null when `baseline_severity = null`; otherwise it MAY be null.

`oscillation_key` MAY be null in Phase 1.

Phase 2 reviewer input MUST use the phase-specific reviewer input schema. In Phase 2 reviewer input, `oscillation_key` MUST contain exactly the reviewer-proposed classification fields:
- `section_id`
- `concern_type`
- `direction`
- `scope`

Phase 2 reviewer input MUST NOT include `fingerprint` or `opposition_key`.

Persisted Phase 2 `reviewer_feedback.json` MUST use the canonical persisted schema. In persisted Phase 2 artifacts, `oscillation_key` MUST contain the reviewer-proposed fields plus the Orchestrator-computed `fingerprint` and `opposition_key`.

`editor_summary.json` MUST contain:

```yaml
round_number: integer
draft_before_hash: string
draft_after_hash: string   # persisted artifact; may be null in editor-generated live input before Orchestrator canonicalization
accepted_feedback_ids: [string]
modified_feedback_ids: [string]
declined_feedback:
  - feedback_id: string
    decline_reason: string
    rationale: string
    target_profile: string | null
    target_round_or_phase: string | null
created_conflict_ids: [string]
resolved_issue_ids: [string]
unresolved_issue_ids: [string]
draft_after_content: string | null   # required in editor-generated applied revision input; optional in persisted summary
```

`accepted_feedback_ids` are feedback items accepted as written.

`modified_feedback_ids` are feedback items accepted in substance but implemented with materially different wording, structure, or placement than the reviewer recommended.

When an applied live round expects the Editor to generate a revised draft, the Editor response MUST include `draft_after_content` containing the complete revised draft text. The Editor response MAY set `draft_after_hash` to null or an implementation-specific placeholder in this generated-revision input. The Orchestrator MUST treat `draft_after_content` as the input authority for the revised draft, compute `draft_after_hash` from that content, inject the computed hash before persisted artifact validation, write the content to `draft_after.md`, and only then mutate `spec.md`.

Persisted `editor_summary.json` MUST contain the Orchestrator-computed `draft_after_hash`. The Editor is not authoritative for derived hashes in editor-generated applied revisions.

When `draft_after.md` is supplied by an external fixture or explicit Orchestrator input, `draft_after_content` MAY be null or omitted.

When a `declined_feedback` item has `decline_reason = deferred_to_later_round`, `target_profile` and `target_round_or_phase` MUST be non-null strings. For every other decline reason, they MAY be null.

`decision_points.json` MUST contain:

```yaml
round_number: integer
draft_hash: string
decision_points:
  - decision_id: string
    round_number: integer
    profile: string
    source_feedback_ids: [string]
    affected_sections: [string]
    decision_type: tighten_requirement | relax_requirement | choose_policy | define_default | resolve_conflict | add_operational_requirement | scope_change
    question: string
    options_considered:
      - option_id: string
        label: string
        description: string
    editor_selected_option_id: string | null
    editor_rationale: string
    risk_if_wrong: string
    requires_human_decision: boolean
    orchestrator_action: record_only | present_at_end | pause_for_input
```

Decision points capture consequential choices made or proposed during revision. They are separate from issue identity and from conflict escalation. A decision point does not imply the Editor made an invalid change; it means the change carries product, policy, scope, authority, or operational consequences that should be visible outside the model turn.

The Editor MUST create a decision point when accepting or modifying feedback causes any of:
- changes normative strength among `MUST`, `SHOULD`, `MAY`, `MUST NOT`, or equivalent language
- adds, removes, narrows, or broadens an authority boundary
- chooses one policy among multiple viable policies
- defines a default behavior where the source spec did not define one
- adds, removes, or changes an enum, status value, reason code, error code, terminal state, or externally visible artifact field
- changes scope by moving behavior into or out of the component, role, phase, adapter, or Orchestrator
- resolves a conflict by preferring one architectural direction over another
- introduces an operational requirement such as logging, retrieval, receipt emission, retry behavior, timeout behavior, or observability behavior

The Orchestrator MUST validate every decision point for schema shape and source feedback references. The Orchestrator MAY also compute additional decision points from draft diffs when deterministic triggers are detectable, such as normative keyword strength changes or new enum-like lists.

Decision point identifiers are deterministic aliases:

```text
decision_fingerprint = SHA256(
  normalized(decision_type) + "\n" +
  normalized(affected_sections) + "\n" +
  normalized(question)
)

decision_id = "dec_" + first_16_hex_chars(decision_fingerprint)
```

`decision_points.mode = end_of_cycle`:
- The Orchestrator MUST persist per-round `decision_points.json`.
- The Orchestrator MUST aggregate all captured decision points into `/rounds/decision_register.json` and `/rounds/decision_register.md` at terminal state.
- Decision points with `requires_human_decision = true` MUST NOT block Phase 1 stability, Phase 2 progression, or convergence solely by existing.
- Terminal output MUST disclose whether unresolved human decision points exist.

`decision_points.mode = intervention`:
- If a decision point has `orchestrator_action = pause_for_input`, the Orchestrator MUST produce `/rounds/decision_intervention_request.json`, set terminal_state to `PAUSED_DECISION`, and halt before scheduling the next review round.
- A decision point MUST use `orchestrator_action = pause_for_input` when `requires_human_decision = true` and any configured intervention threshold is met.
- The system MUST NOT auto-apply the selected option after `PAUSED_DECISION`; external input is required.

Decision point thresholds MUST be computable from persisted artifacts or deterministic draft analysis. The default threshold set is:
- source feedback normalized severity is `blocker` or `major`
- draft diff changes normative keyword strength
- draft diff adds or removes authority-boundary language
- draft diff adds or removes public enum/status/error-code values
- draft diff changes role, phase, adapter, or Orchestrator scope

Decision point records MUST NOT replace reviewer feedback, editor summaries, conflict reports, or convergence declarations. They are an operator-facing release valve for consequential choices that would otherwise be hidden inside `accepted_feedback_ids` or `modified_feedback_ids`.

`decision_register.json` MUST contain:

```yaml
generated_at: string
mode: end_of_cycle | intervention
terminal_state: string
decision_points: [decision_point]
unresolved_human_decision_count: integer
```

## DECISION SUMMARY

Decision summary artifacts are operator-facing review aids derived from `decision_register.json`.

The Orchestrator MUST NOT use decision summary artifacts as authority for convergence, halt selection, conflict escalation, oscillation detection, draft mutation, or replay. The decision register remains the authoritative decision-point artifact.

When `decision_points.summary.enabled = true` and at least one decision point is captured, the Orchestrator MUST produce:

- `/rounds/decision_summary.json`
- `/rounds/decision_summary.md`

The mechanical portion of the decision summary MUST be deterministic and MUST be derivable solely from persisted decision-point artifacts and run metadata.

The mechanical summary MUST include these grouping surfaces:

```yaml
generated_at: string
source_register_path: string
terminal_state: string
decision_point_count: integer
unresolved_human_decision_count: integer
section_clusters:
  - cluster_id: string
    section_family: string
    affected_sections: [string]
    decision_ids: [string]
    round_numbers: [integer]
    profiles: [string]
    trigger_counts: object
    decision_type_counts: object
    representative_questions: [string]
round_profile_clusters:
  - cluster_id: string
    round_number: integer
    profile: string
    decision_ids: [string]
    trigger_counts: object
    decision_type_counts: object
trigger_clusters:
  - cluster_id: string
    trigger_type: string
    decision_ids: [string]
    affected_sections: [string]
    round_numbers: [integer]
interpretive_summary: object | null
```

`section_clusters` MUST group decision points by document topology, not by semantic guesswork:

- For numbered Markdown sections, `section_family` MUST be the first numeric section component from the first affected section, e.g. `13` for `13.2 Duplicate Identity`.
- For unnumbered sections, `section_family` MUST be the normalized top-level affected section text.
- If a decision point has multiple affected sections, the first affected section in persisted order is the primary grouping anchor; all affected sections MUST still be listed in the cluster.
- Cluster ordering MUST be deterministic: numeric section families in numeric order, then nonnumeric section families lexicographically.

`round_profile_clusters` MUST group decision points by `(round_number, profile)` and MUST sort by `round_number` ascending, then `profile` lexicographically.

`trigger_clusters` MUST group decision points by each value in `trigger_types` and MUST sort by `trigger_type` lexicographically.

Within every cluster:

- `decision_ids` MUST be sorted lexicographically.
- `affected_sections` MUST be de-duplicated and sorted by first observed source order.
- `round_numbers` MUST be de-duplicated and sorted ascending.
- `profiles` MUST be de-duplicated and sorted lexicographically.
- `trigger_counts` and `decision_type_counts` MUST use deterministic key ordering.
- `representative_questions` MUST contain at most three questions, selected by the cluster's decision order after sorting by `(round_number, decision_id)`.

The human-readable `decision_summary.md` MUST clearly separate:

- mechanical counts and clusters
- optional interpretive summary, if present

Mechanical summary text MUST NOT claim semantic theme authority beyond section family, round/profile, trigger type, and directly quoted or paraphrased decision-point fields.

If `decision_points.summary.include_interpretive_summary = false`, then `interpretive_summary = null`.

If `decision_points.summary.include_interpretive_summary = true`, the interpretive summary MAY be produced by an AI client, but it MUST obey these constraints:

- It MUST consume the mechanical summary as input, not raw draft-only context.
- It MUST preserve and cite decision IDs for every interpreted theme.
- It MUST NOT invent decision points, affected sections, approvals, rejections, or source claims.
- It MUST be labeled non-authoritative in both JSON and Markdown.
- It MUST include the client name, version, model, prompt snapshot path, and timestamp used to produce it.
- Failure to produce an interpretive summary MUST NOT invalidate the mechanical summary.

Decision summary generation MUST be read-only with respect to `spec.md`, `spec.history.md`, `convergence_declaration.md`, and all per-round artifacts.

`decision_intervention_request.json` MUST contain:

```yaml
terminal_state: PAUSED_DECISION
generated_at: string
round_number: integer
profile: string
draft_hash: string
decision_points: [decision_point]
recommendation: choose_option | modify_draft_manually | lower_threshold | continue_record_only
```

`unresolved_issues.json` MUST contain:

```yaml
round_number: integer
draft_hash: string
unresolved_issues:
  - issue_id: string
    issue_fingerprint: string
    normalized_severity: blocker | major | minor | nit
    affected_sections: [string]
    claim: string
    in_scope: boolean
    blocking_acceptance: boolean
```

`in_scope` in `unresolved_issues.json` is copied from the source feedback item or set by the Orchestrator when it converts a non-feedback condition into an unresolved issue.

`blocking_acceptance = true` only when the unresolved issue's `normalized_severity` is `blocker` or `major` and `in_scope = true`. `blocking_acceptance = false` for minor, nit, accepted rubric gaps under permissive target policy, and out-of-scope feedback. `blocking_acceptance` is the machine-readable indicator used to explain why an issue prevents accepted-draft status; it does not replace the accepted-draft definition.

`rubric_gaps.json` MUST be produced in Phase 2 and MUST contain:

```yaml
round_number: integer
draft_hash: string
rubric_content_hash: string
rubric_gaps:
  - gap_id: string
    gap_fingerprint: string
    rubric_anchor: string
    affected_sections: [string]
    normalized_severity: blocker | major | minor | nit
    claim: string
    evidence: string
    recommendation: string
    status: unresolved | accepted | resolved
    blocking_convergence: boolean
```

Each rubric gap represents exactly one target-rubric requirement that is missing, contradicted, unverifiable, or explicitly accepted under a permissive target.

`blocking_convergence` MUST be computed from target policy and gap status:
- If `status = resolved`, then `blocking_convergence = false`.
- If `status = accepted`, then `blocking_convergence = false` only when the target matrix permits accepted rubric gaps for the current target.
- If `status = accepted` and the target matrix does not permit accepted rubric gaps for the current target, then `blocking_convergence = true`.
- If `status = unresolved`, then `blocking_convergence = true`.

For `final/strict`, every rubric gap with `status = unresolved` or `status = accepted` is blocking because final/strict forbids unresolved rubric gaps and does not permit accepted gaps.

For `final/permissive`, rubric gaps with `status = accepted` are not blocking and rubric gaps with `status = unresolved` are blocking.

For `mid` targets, rubric gaps are evaluated only when the target rubric explicitly applies to the mid target. If the rubric requirement applies, `status = unresolved` is blocking and `status = accepted` is blocking only when the target matrix forbids accepted gaps for that mid target.

Rubric gap fingerprint:

```text
gap_fingerprint = SHA256(
  normalized(rubric_anchor) + "\n" +
  normalized(affected_sections) + "\n" +
  normalized(claim)
)
```

`gap_id` is a deterministic alias:

```text
gap_id = "gap_" + first_16_hex_chars(gap_fingerprint)
```

`unresolved_rubric_gaps` in convergence evaluation and failure reports is the ordered subset of `rubric_gaps` where:
- `status = unresolved`, and
- `blocking_convergence = true`.

Rubric gap ordering MUST be deterministic:
1. source order of `rubric_anchor` in `convergence_rubric.md`
2. source order of the first affected section in `spec.md`
3. `gap_id` lexicographically

Terminal report schemas MUST include all fields listed in their failure-handling sections plus `terminal_state`, `generated_at`, `round_number`, and `draft_hash`.

`conflict_report.json` MUST contain:

```yaml
terminal_state: HALTED_CONFLICT | null
generated_at: string
round_number: integer
draft_hash: string
conflicts:
  - conflict_id: string
    conflict_fingerprint: string
    conflict_type: architectural_conflict | prior_decision_conflict | profile_conflict | rubric_conflict | ambiguous_feedback | out_of_scope_feedback
    conflict_claim: string
    participating_issue_ids: [string]
    participating_issue_fingerprints: [string]
    conflict_severity: blocker | major | minor | nit
    first_seen_round: integer
    last_seen_round: integer
    consecutive_count: integer
    total_count: integer
    escalated: boolean
    blocker_level: boolean
    manual_review_required: boolean
    recommendation: freeze_prior_decision | continue_once | manual_review_required | stop_iteration
```

When conflict escalation does not halt execution, `terminal_state` MUST be null. When blocker-level conflict escalation halts execution, `terminal_state` MUST be `HALTED_CONFLICT`.

`config_validation_error.json` MUST contain:

```yaml
terminal_state: CONFIG_INVALID
generated_at: string
invalid_fields:
  - path: string
    reason: string
```

`artifact_validation_error.json` MUST contain:

```yaml
terminal_state: HALTED_ARTIFACT_INVALID
generated_at: string
round_number: integer
phase: phase_1 | phase_2
profile: string
client_role: reviewer | editor
client:
  name: string
  version: string
  model: string
attempts:
  - attempt_number: integer
    artifact_name: string
    validation_errors: [string]
    raw_response_path: string | null
retry_exhausted: boolean
last_valid_draft_hash: string
last_valid_draft_path: string
recommendation: retry_with_simpler_schema | switch_client | manual_review_required
```

---

## ARTIFACT VALIDATION POLICY

The Orchestrator MUST validate every client-produced artifact before using it for scheduling, mutation, acceptance, convergence, oscillation detection, or conflict escalation.

Validation order:
1. parse the client response as a single JSON object
2. validate the object against the phase-appropriate artifact schema
3. validate contextual fields such as `round_number`, `profile`, `draft_hash`, `draft_before_hash`, and `draft_after_hash`
4. apply Orchestrator-owned canonicalization steps such as Phase 2 `oscillation_key` fingerprint and opposition-key computation
5. validate the canonicalized artifact against the persisted artifact schema

If validation fails, the Orchestrator MUST NOT persist the invalid artifact under its canonical artifact filename. It MAY persist the raw response and validation errors under diagnostic filenames in the current round directory.

Validation retry policy:
- each client artifact gets at most 1 validation retry
- the retry MUST use the same round number, same draft hash, same profile, same phase, same client role, and same source prompt context
- the retry prompt MAY include the validation errors and the required schema constraints
- the original prompt attempt and retry prompt attempt MUST each be persisted under `prompt_snapshots/`
- retry prompt snapshots MUST include the validation errors that caused the retry
- validation attempts do not advance the profile schedule and do not count as accepted review cycles
- the round budget is consumed only after a reviewer artifact validates successfully

If the retry validates, the Orchestrator continues with the validated artifact.

If the retry fails, the Orchestrator MUST halt with `HALTED_ARTIFACT_INVALID` and produce `/rounds/artifact_validation_error.json`.

When `HALTED_ARTIFACT_INVALID` occurs, `last_valid_draft_path` MUST point to the most recent draft snapshot the Orchestrator can safely treat as validated. If reviewer artifact validation fails before any validated review exists for the round, this MUST be the current round `draft_before.md`. If editor artifact validation fails after a validated reviewer artifact, this MAY be the current round `draft_after.md` only when that file is an Orchestrator-owned snapshot and not an unvalidated client artifact.

For Phase 2 reviewer feedback, an invalid or missing reviewer-proposed `oscillation_key`, an invalid enum value, or a `section_id` that does not resolve to exactly one canonical section ID is an artifact validation failure under this policy.

---

## CLIENT TELEMETRY

The Orchestrator MUST persist per-attempt client telemetry for every live client invocation, including successful attempts, invalid artifact attempts, timeout attempts, and nonzero-exit attempts whenever process metadata is available.

Telemetry artifacts MUST be written under:

```text
/rounds/round-N/client_telemetry/{client_role}-{artifact_name}-attempt-{attempt_number}.json
```

Client telemetry is audit and observability data. It MUST NOT be used for convergence, acceptance, severity normalization, artifact validation, conflict escalation, oscillation detection, draft hashing, or replay authority.

`client_telemetry` artifacts MUST contain:

```yaml
generated_at: string
round_number: integer
phase: phase_1 | phase_2
profile: string
client_role: reviewer | editor
artifact_name: string
attempt_number: integer
client:
  name: string
  command: string
  configured_version: string
  observed_version: string | null
  model: string
started_at: string
finished_at: string | null
duration_ms: integer | null
duration_api_ms: integer | null
exit_code: integer | null
timed_out: boolean
session_id: string | null
stop_reason: string | null
terminal_reason: string | null
total_cost_usd: number | null
usage:
  input_tokens: integer | null
  output_tokens: integer | null
  cache_creation_input_tokens: integer | null
  cache_read_input_tokens: integer | null
  total_tokens: integer | null
  provider_raw: object | null
model_usage: object | null
raw_envelope_path: string | null
stderr_path: string | null
telemetry_source: claude_json_envelope | codex_stdout | codex_json_envelope | process_metadata | unavailable
```

`usage.total_tokens` MUST be computed by the Orchestrator when token components are available:

```text
total_tokens =
  input_tokens +
  output_tokens +
  cache_creation_input_tokens +
  cache_read_input_tokens
```

Null token components MUST be treated as zero for this computed total only. If every token component is null, `usage.total_tokens` MUST be null.

When a client exposes a raw JSON envelope with usage metadata, such as Claude Code `--output-format json`, the Orchestrator MUST persist the raw envelope or a lossless redacted copy and set `raw_envelope_path`.

When a client exposes usage only in stdout/stderr text, such as a human-readable `tokens used` line, the Orchestrator MAY parse the available fields and MUST preserve the raw stdout/stderr text or a redacted copy if it is needed to explain the parsed usage.

When no usage data is available, telemetry MUST still be emitted with timing, exit, and configured-client metadata when available, and `telemetry_source = unavailable` or `process_metadata`.

Telemetry persistence MUST be best-effort but non-silent:

- Failure to persist telemetry MUST NOT by itself invalidate a schema-valid reviewer/editor artifact.
- Telemetry persistence failure MUST be recorded as a validation warning or run warning in the round packet.
- Missing telemetry for a live invocation MUST be detectable by artifact validation or status tooling.

Prompt text MUST NOT be duplicated into telemetry artifacts unless the prompt snapshot path is referenced. The attempt-level `prompt_snapshots/` artifact remains the authoritative prompt audit artifact.

---

## CONTENT NORMALIZATION AND HASHING

Draft hash normalization:
- normalize line endings to LF
- remove trailing spaces and tabs from each line
- preserve all non-whitespace content
- preserve all markdown heading text and order
- preserve frontmatter if present
- ensure exactly one trailing newline

`draft_hash` is SHA256 of the normalized full draft.

If a round requires Orchestrator-owned version stamping, stamping MUST occur before writing the canonical `draft_after.md`, before mutating `spec.md`, and before computing the persisted `draft_after_hash`.

Rubric hash normalization:
- use the same normalization rules as `draft_hash`
- compute the hash from the full normalized `convergence_rubric.md`

`rubric_content_hash` is SHA256 of the normalized full rubric.

Semantic change hash normalization:
- compute section-level diff between normalized `draft_before.md` and normalized `draft_after.md`
- strip whitespace-only differences
- preserve all section headers
- preserve all ordered list order
- preserve unordered list order by default
- normalize unordered list order only when a list is explicitly marked order-insensitive

Semantic change polarity is:
- `add` when normalized content exists only in `draft_after.md`
- `remove` when normalized content exists only in `draft_before.md`
- `modify` when both sides exist and differ

`semantic_change_hash` is SHA256 of normalized section id, polarity, before content hash, and after content hash.

`mechanical_change_key` is a polarity-neutral key used only for draft-level mechanical churn:

```text
mechanical_change_key = SHA256(
  normalized(section_id) + "\n" +
  sorted(before_content_hash_or_absent, after_content_hash_or_absent)
)
```

`mechanical_change_key` deliberately excludes polarity so an exact add/remove reversal can be compared mechanically. Polarity remains a separate field on the semantic change record.

---

## OSCILLATION DETECTION (FULL DEFINITION)

Oscillation detection has two layers:

1. Draft-level mechanical detection
2. Feedback-level Phase 2 detection

Draft-level detection is deterministic but limited. It detects exact cycles and exact mechanical churn in normalized drafts. It MUST NOT claim that two differently worded feedback items are the same concern.

Feedback-level detection is Phase 2 only. It uses Orchestrator-canonicalized `oscillation_key` fields derived from reviewer-proposed classification.

Each round computes:

1. draft_hash:
   SHA256 of full normalized draft_after.md

2. semantic_change_hash:
   SHA256 of normalized section-level diff between draft_before and draft_after

3. mechanical_change_keys:
   one polarity-neutral key per changed section, derived from normalized section id and unordered before/after content hashes

Explicit order-insensitive marker:

```text
[ORDER_INSENSITIVE_LIST]
- item B
- item A
[/ORDER_INSENSITIVE_LIST]
```

Only lists inside this marker may be sorted during normalization.

`[ORDER_INSENSITIVE_LIST]` and `[/ORDER_INSENSITIVE_LIST]` are source-control markers, not standard Markdown. Rendered Markdown viewers will display them literally.

Oscillation rules:

- Cycle:
  draft_hash repeats -> cycle detected

- Mechanical draft churn:
  same `mechanical_change_key` appears with opposing exact add/remove polarity across rounds

- Feedback flip-flop (Phase 2 only):
  same `oscillation_opposition_key` appears across rounds with opposing directions:
  - `add` after `remove`
  - `remove` after `add`
  - `constrain` after `relax`
  - `relax` after `constrain`

- Feedback churn (Phase 2 only):
  same `oscillation_opposition_key` appears cumulatively 3 times in Phase 2 with `modify` or `clarify` and without intervening resolution

Intervening resolution for feedback churn is computable from artifacts.

For an `oscillation_opposition_key`, an intervening resolution occurs between Phase 2 round R and the next Phase 2 review when:
- `editor_summary.json` for round R includes a `feedback_id` in `accepted_feedback_ids` or `modified_feedback_ids` whose matching item in round R `reviewer_feedback.json` has the tracked `oscillation_opposition_key`, and
- the corresponding issue is absent from `unresolved_issues.json` at the start of the next Phase 2 review.

The Orchestrator MUST reset the feedback churn counter for that `oscillation_opposition_key` to zero when intervening resolution occurs.

A round in which the opposition key does not appear is not, by itself, an intervening resolution.

- Feedback re-addition (Phase 2 only):
  same oscillation concern is added, removed, and then re-added by fingerprint history

Outputs:

/rounds/oscillation_report.json

Fields:
- detected: true|false
- type: cycle | mechanical_churn | feedback_flip_flop | feedback_churn | feedback_re_addition
- affected_sections
- suspected_feedback_ids
- oscillation_fingerprints
- oscillation_opposition_keys
- recommendation:
  - freeze_prior_decision
  - escalate_conflict
  - continue_once
  - stop_iteration

Recommendation selection is deterministic:
- cycle => stop_iteration
- mechanical_churn involving exact draft add/remove reversal => freeze_prior_decision
- feedback_flip_flop involving any blocker or major issue => escalate_conflict
- feedback_flip_flop involving only minor or nit issues => freeze_prior_decision
- first feedback_re_addition => continue_once
- repeated feedback_re_addition of the same oscillation fingerprint => stop_iteration
- feedback_churn involving `modify` or `clarify` for 3 cumulative Phase 2 appearances of the same opposition key without intervening resolution => escalate_conflict

Issues with `normalized_severity = nit`, including all-null severity-component cases, are treated as nit for oscillation recommendation.

If Phase 2 feedback lacks a valid reviewer-proposed `oscillation_key`, or if the proposed `section_id` is not in the canonical section index, the reviewer artifact is invalid and MUST be rejected before oscillation detection runs.

`escalate_conflict` from feedback churn produces `conflict_report.json` tagged for manual review. It halts only if the resulting conflict is blocker-level under the conflict escalation rules.

If recommendation = stop_iteration, terminal_state = HALTED_OSCILLATION.

---

## CONFLICT MODEL

Conflict types:

- architectural_conflict
- prior_decision_conflict
- profile_conflict
- rubric_conflict
- ambiguous_feedback
- out_of_scope_feedback

Conflict severity:

```text
conflict_severity = max(normalized_severity of participating issues)
```

A blocker-level conflict is any conflict where `conflict_severity = blocker`.

Conflict creation authority:
- the Orchestrator is the authority that creates and persists conflicts
- the Editor may request conflict creation by listing conflict IDs in `created_conflict_ids`
- every Editor-requested conflict MUST be derivable from declined feedback, mutually incompatible accepted feedback, an oscillation recommendation of `escalate_conflict`, or a prior decision contradiction documented in current artifacts
- the Orchestrator MUST validate each requested conflict against the conflict identity rules before tracking it
- invalid or under-specified Editor-requested conflicts MUST be ignored for escalation and recorded as a validation warning unless they also make `editor_summary.json` schema-invalid

The Orchestrator MUST persist tracked conflict state across rounds in `conflict_report.json` when escalation is reached, and MAY persist non-escalated conflict tracking state in implementation-specific round metadata. Non-escalated tracking state is not a halt artifact.

The Editor's conflict-resolution authority is limited to recommending resolution through accepted, modified, or declined feedback decisions. The Orchestrator owns conflict threshold counting, escalation, terminal-state selection, and halt artifact production.

---

## EDITOR DECLINE TAXONOMY

Editor may decline feedback only with one of:

- architectural_conflict
- contradicts_source_authority
- out_of_scope
- factually_incorrect
- already_satisfied
- ambiguous
- superseded_by_better_fix
- deferred_to_later_round
- nit_declined

deferred_to_later_round requires:
- target_profile
- target_round_or_phase
- rationale

When persisted in `editor_summary.json`, declined feedback with `decline_reason = deferred_to_later_round` MUST set `target_profile` and `target_round_or_phase` to non-null strings. Null values are invalid for this decline reason.

Declined feedback MUST be persisted in editor_summary.json.

Decline taxonomy is separate from conflict type.
Some declined feedback may create a conflict; some may not.

---

## CONFLICT ESCALATION

Threshold:
- same conflict persists for 2 consecutive rounds OR
- same conflict appears 3 times non-consecutively

Escalation produces:
/rounds/conflict_report.json

Blocker-level conflicts trigger halt.

Same conflict is determined by `conflict_fingerprint`.

---

## PHASE 2 FAILURE HANDLING

Produces:

/rounds/convergence_failure_report.json

Includes:
- final_draft_path
- final_declaration_path: string | null
- target_phase
- target_mode
- workflow
- rubric_profile
- rubric_source
- rubric_label: string | null
- rubric_manifest_path
- unresolved_blockers
- unresolved_major_issues
- unresolved_rubric_gaps
- reviewer_final_status
- last_accepted_draft_hash
- last_draft_hash
- exit_reason
- recommendation:
  - return_to_phase_1
  - continue_convergence
  - lower_target
  - manual_review_required

ACTION:

Orchestrator MUST halt and require external input.

The system does not auto-apply recommendation.

`reviewer_final_status` is a string enum:
- `accepted`
- `rejected`
- `not_run`

`reviewer_final_status = accepted` means declaration verification passed under the convergence declaration criteria.

`reviewer_final_status = rejected` means declaration verification ran and failed at least one convergence declaration acceptance criterion.

`reviewer_final_status = not_run` means Phase 2 halted before a final declaration verification review could run.

---

## PHASE 1 FAILURE HANDLING

Produces:

/rounds/technical_failure_report.json

Includes:
- final_draft_path
- unresolved_blockers
- unresolved_major_issues
- unresolved_conflicts
- unresolved_oscillation
- last_accepted_draft_hash
- last_draft_hash
- exit_reason
- recommendation:
  - continue_phase_1
  - narrow_scope
  - manual_review_required

ACTION:

Orchestrator MUST halt and require external input.

The system does not proceed automatically to Phase 2.

---

## TARGET MATRIX PRECEDENCE

At convergence evaluation:

target matrix overrides issue policy.

mid/permissive:
- blockers forbidden
- major issues allowed if documented

mid/strict:
- blockers forbidden
- major issues forbidden
- minor allowed if documented

final/permissive:
- blockers forbidden
- major forbidden
- rubric gaps allowed if accepted

final/strict:
- no blockers
- no major issues
- no unresolved rubric gaps
- declaration required and accepted

The target matrix controls convergence evaluation only. It does not weaken the accepted draft requirement for entering Phase 2.

For permissive targets, this creates an intentional asymmetry: major issues cannot survive from Phase 1 into Phase 2, but documented major issues may be introduced or discovered during Phase 2 and still be allowed when the target matrix permits them.

---

## STATE MACHINE (FULL TRANSITIONS)

INITIALIZED -> TECHNICAL_REVIEW

INITIALIZED -> CONFIG_INVALID (on preflight configuration validation failure)

TECHNICAL_REVIEW -> TECHNICAL_REVISION
TECHNICAL_REVISION -> TECHNICAL_REVIEW

TECHNICAL_REVIEW -> TECHNICAL_STABLE (if accepted draft and all non-skipped Phase 1 profiles have valid clean status)

TECHNICAL_STABLE -> CONVERGENCE_REVIEW (after Phase 2 entry version promotion)

CONVERGENCE_REVIEW -> CONVERGENCE_REVISION (if any in-scope unresolved feedback item targets `spec.md` or another non-declaration source artifact)
CONVERGENCE_REVIEW -> DECLARATION_REVISION (if all in-scope unresolved feedback items target only `convergence_declaration.md`, `rubric_gaps.json`, `unresolved_issues.json`, or other declaration-evaluation artifacts)

CONVERGENCE_REVISION -> CONVERGENCE_REVIEW
DECLARATION_REVISION -> CONVERGENCE_REVIEW

CONVERGENCE_REVIEW -> CONVERGED (if declaration accepted)

ANY STATE -> HALTED_CONFLICT (on blocker-level conflict escalation)
ANY STATE -> HALTED_OSCILLATION (on oscillation stop)
ANY STATE -> HALTED_ARTIFACT_INVALID (on exhausted artifact validation retry)
ANY STATE -> PAUSED_DECISION (on decision intervention required)
ANY STATE -> TARGET_NOT_REACHED (on max_rounds)

If both `CONVERGENCE_REVISION` and `DECLARATION_REVISION` guards are true for the same review, `CONVERGENCE_REVISION` takes precedence because source-spec changes may invalidate declaration artifacts.

---

## CONVERGENCE DECLARATION

`convergence_declaration.md` MUST exist before `CONVERGED`.

The convergence declaration is a separate Orchestrator-owned artifact. Editors MUST NOT satisfy declaration requirements by adding declaration text, acceptance statements, or declaration metadata to `spec.md` unless that text is explicitly part of the source spec domain itself.

Minimum declaration content:
- target_phase
- target_mode
- workflow
- rubric_profile
- rubric_source
- rubric_label: string | null
- rubric_manifest_path
- final_draft_hash
- rubric_content_hash
- unresolved_blockers count
- unresolved_major_issues count
- unresolved_rubric_gaps count
- reviewer_final_status
- declaration_status: accepted | rejected

The declaration is verified by a Phase 2 `convergence_strict_check` review whose review scope includes `convergence_declaration.md`, the current draft, the current rubric hash, the target matrix, `unresolved_issues.json`, and `rubric_gaps.json`.

Declaration-scoped issues are issues whose `affected_sections` explicitly contains `convergence_declaration.md`.

Target-matrix issues are issues whose `rubric_impact` is non-null or whose `affected_sections` contains `target-matrix-precedence`, `rubric_gaps.json`, or `unresolved_issues.json`.

The declaration is accepted only when all of the following are true:
- `convergence_declaration.md` exists
- `final_draft_hash` equals the current `draft_hash`
- `rubric_content_hash` equals the current `rubric_content_hash`
- declaration rubric identity equals the current `rubric_manifest.json`
- declaration counts equal the counts derived from `unresolved_issues.json` and `rubric_gaps.json`
- target matrix requirements are satisfied
- `convergence_strict_check` returns zero in-scope blocker declaration-scoped issues
- `convergence_strict_check` returns zero in-scope major declaration-scoped issues
- `convergence_strict_check` returns zero in-scope blocker target-matrix issues
- `convergence_strict_check` returns zero in-scope major target-matrix issues
- final/strict targets have zero unresolved blocking rubric gaps

If all declaration acceptance criteria pass, `declaration_status = accepted` and `reviewer_final_status = accepted`.

If any declaration acceptance criterion fails after the verification review runs, `declaration_status = rejected` and `reviewer_final_status = rejected`.

If Phase 2 halts before declaration verification runs, `declaration_status = rejected` when a declaration exists and `reviewer_final_status = not_run`.

`conditional` is not a terminal declaration status. Conditional convergence concerns MUST be represented as rejected declaration status plus documented unresolved issues, rubric gaps, or recommendations in the relevant failure report.

---

## REPRODUCIBILITY

prompt_snapshot.json MUST include:
- prompt text
- profile
- client
- version
- model
- timestamp
- config snapshot
- workflow
- rubric profile
- rubric source
- rubric content hash
- rubric manifest path in Phase 2
- draft_hash
- semantic_change_hash when a draft mutation is requested

`prompt_snapshot.json` is the round-level convenience snapshot. It MAY be updated as the round advances from reviewer prompt to editor prompt.

`prompt_snapshots/{client_role}-{artifact_name}-attempt-{attempt_number}.json` is the attempt-level audit trail. It MUST be append-only within a round, MUST NOT overwrite prior attempts, and MUST include:
- prompt text sent for that attempt
- profile
- phase
- client role
- client name, version, and model
- artifact name
- attempt number
- timestamp
- config snapshot
- workflow
- rubric profile
- rubric source
- rubric manifest path in Phase 2
- validation errors that caused the attempt, or an empty list for the first attempt

`client_telemetry/{client_role}-{artifact_name}-attempt-{attempt_number}.json` is the attempt-level client runtime telemetry artifact. It MUST be keyed to the same `client_role`, `artifact_name`, and `attempt_number` as the corresponding prompt snapshot when both exist. It MAY reference raw client envelopes or stderr/stdout captures but MUST NOT replace prompt snapshots or canonical reviewer/editor artifacts.

Phase 2 reviewer prompt snapshots MUST include the full oscillation classification table shown to the reviewer.

reviewer_working_notes.md is part of the audit trail and MUST be persisted, but it is not required for deterministic replay.

---

## MULTI-REVIEWER (NON-NORMATIVE FUTURE NOTE)

Combination strategies:

- union:
  include all issues
  severity = max severity

- intersection:
  include issues shared by quorum_threshold reviewers
  severity = min severity among included reviewers

- weighted:
  weighted average mapped to severity tier

- authority-priority:
  authority reviewers override others

Future config MUST include:
- quorum_threshold

If implemented later, weighted mode MUST define numeric severity mapping, reviewer weights, and rounding behavior before use.

Not implemented in 0.22.

---

## DESIGN PRINCIPLE

Every primitive MUST be computable.

No implied behavior.
No undefined aggregation.
No hidden state transitions.

Goal:
Deterministic convergence with no ambiguity in execution.
