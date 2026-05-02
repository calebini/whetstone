# WHETSTONE - AI SPEC CONVERGENCE ORCHESTRATOR (0.10 - STRICT CANDIDATE)

## Purpose

Automate iterative technical review between AI clients (e.g., Claude Code, Codex) to drive a spec from v0.1 -> converged (mid/final, permissive/strict), with controlled multi-perspective review per round, deterministic convergence behavior, explicit failure handling, and fully specified primitives.

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
  - rubric_gaps.json (Phase 2 only)
  - profile_used.yaml
  - prompt_snapshot.json
- /rounds/oscillation_report.json (if detected)
- /rounds/conflict_report.json (if escalated)
- /rounds/convergence_failure_report.json (if Phase 2 fails)
- /rounds/config_validation_error.json (if preflight configuration validation fails)

---

## CONFIGURATION

```yaml
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
declaration_path: ./convergence_declaration.md

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
  rubric_path: ./convergence_rubric.md
  max_rounds: 8
```

Before entering `TECHNICAL_REVIEW`, the Orchestrator MUST validate configuration.

Client `version` and `model` fields MUST be non-empty strings after trimming whitespace. If any required client field is empty, the Orchestrator MUST halt before the first review round and produce `/rounds/config_validation_error.json` identifying the invalid fields. This preflight failure does not consume a Phase 1 or Phase 2 round.

---

## HALTING CONDITIONS (ORDERED PRECEDENCE)

1. Clean convergence achieved
2. Blocker-level conflict escalation triggered
3. Oscillation stop triggered
4. max_rounds reached

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
      max_repeats: 1

  phase_2:
    - profile: convergence_strict_check
    - profile: adversarial
    - profile: convergence_strict_check
```

## ROUND SCHEDULING ALGORITHM

Phase 1 executes configured profiles in order.

For each Phase 1 profile:
- run the profile unless `skip_if_clean = true` and the current draft already has a valid clean result for that profile
- if the profile returns blocker issues and `repeat_if_blockers = true`, schedule the same profile again after editor revision until either blockers are cleared or `max_repeats` is reached
- if the editor mutates any section in the profile focus, previous clean status for that profile is invalidated
- if the editor mutates a section outside the profile focus, previous clean status for that profile remains valid

Phase 1 completes only when:
- all non-skipped Phase 1 profiles have valid clean status, and
- the current draft is accepted.

Phase 2 executes configured profiles in order.

After each Phase 2 reviewer/editor cycle, the Orchestrator MUST evaluate halt conditions in the ordered precedence defined by this spec.

Phase 2 completion is checked after each validated Phase 2 review cycle and any resulting declaration revision, not only after the full configured Phase 2 profile sequence has been exhausted.

For `target_phase = final` and `target_mode = strict`, the Orchestrator MUST NOT declare clean convergence until every distinct Phase 2 profile in the configured sequence has produced at least one clean result in Phase 2 for the current draft lineage.

If a Phase 2 profile is not run because of an explicit future skip condition, the skip condition MUST be persisted in `profile_used.yaml` and MUST count as a clean result only if the skip rule is computable from current artifacts.

If Phase 2 reaches the end of its configured profile sequence without clean convergence and Phase 2 round budget remains, the Orchestrator MUST start the Phase 2 profile sequence again from its first configured profile.

If Phase 2 reaches `convergence.max_rounds` before clean convergence, the Orchestrator MUST halt with `TARGET_NOT_REACHED` and produce `convergence_failure_report.json`.

Phase 2 completes only when clean convergence is achieved.

Clean convergence is achieved when:
- the current draft satisfies the configured target matrix,
- `convergence_declaration.md` exists,
- the declaration is accepted under the convergence declaration criteria, and
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

Every issue MUST include:
- `issue_id`
- `issue_fingerprint`

Every conflict MUST include:
- `conflict_id`
- `conflict_fingerprint`

Fingerprints are computed from normalized semantic fields, not from round number, reviewer phrasing, or timestamps.

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

Normalization for fingerprint fields:
- trim leading/trailing whitespace
- collapse internal whitespace to a single space
- lowercase enum-like values
- sort arrays only when their order is semantically irrelevant
- preserve `affected_sections` order when the order is part of the claim
- sort `participating_issue_fingerprints` lexicographically before conflict fingerprint hashing

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
    issue_id: string
    issue_fingerprint: string
    issue_type: string
    affected_sections: [string]
    baseline_severity: blocker | major | minor | nit | null
    authority_impact: blocker | major | minor | nit | null
    determinism_impact: blocker | major | minor | nit | null
    rubric_impact: blocker | major | minor | nit | null
    normalized_severity: blocker | major | minor | nit
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
draft_after_hash: string
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
```

`accepted_feedback_ids` are feedback items accepted as written.

`modified_feedback_ids` are feedback items accepted in substance but implemented with materially different wording, structure, or placement than the reviewer recommended.

When a `declined_feedback` item has `decline_reason = deferred_to_later_round`, `target_profile` and `target_round_or_phase` MUST be non-null strings. For every other decline reason, they MAY be null.

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

TECHNICAL_REVIEW -> TECHNICAL_STABLE (if accepted draft)

TECHNICAL_STABLE -> CONVERGENCE_REVIEW

CONVERGENCE_REVIEW -> CONVERGENCE_REVISION (if spec changes needed)
CONVERGENCE_REVIEW -> DECLARATION_REVISION (if declaration only)

CONVERGENCE_REVISION -> CONVERGENCE_REVIEW
DECLARATION_REVISION -> CONVERGENCE_REVIEW

CONVERGENCE_REVIEW -> CONVERGED (if declaration accepted)

ANY STATE -> HALTED_CONFLICT (on blocker-level conflict escalation)
ANY STATE -> HALTED_OSCILLATION (on oscillation stop)
ANY STATE -> TARGET_NOT_REACHED (on max_rounds)

---

## CONVERGENCE DECLARATION

`convergence_declaration.md` MUST exist before `CONVERGED`.

Minimum declaration content:
- target_phase
- target_mode
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
- rubric content hash
- draft_hash
- semantic_change_hash when a draft mutation is requested

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

Not implemented in 0.10.

---

## DESIGN PRINCIPLE

Every primitive MUST be computable.

No implied behavior.
No undefined aggregation.
No hidden state transitions.

Goal:
Deterministic convergence with no ambiguity in execution.
