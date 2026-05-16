# Scope Intake And Decisions Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: scope_intake_and_decisions_spec
target_spec_role: leaf_spec
-->

## Scope Contract

A scope contract is an operator-approved first-contact artifact that defines what Whetstone is allowed to pressure during a run.

The canonical artifact path is configured by `scope_contract.path` and defaults to:

```text
rounds/intake/scope_contract.json
```

The scope contract MUST be treated as authoritative when present and approved. Reviewer prompts MUST instruct reviewers to mark concerns outside the contract as `in_scope = false` and to recommend a scope-promotion decision rather than silently expanding the current run. Editor prompts MUST instruct editors to decline out-of-scope or deferred feedback using the existing decline taxonomy.

`workflow: mvp` requires an approved scope contract before live review begins. If the scope contract is missing, invalid, or not approved, preflight validation MUST halt with `CONFIG_INVALID`. This is intentional: an MVP run has no meaningful boundary unless the operator defines the first useful build and its deferrals.

For other workflows, a scope contract is optional unless explicitly required by future configuration. If an approved scope contract exists, the Orchestrator SHOULD inject it into Reviewer and Editor context files and prompt snapshots.

`scope_contract.json` MUST include:

```yaml
schema_version: scope-contract-v1
status: draft | approved | superseded
readiness_target: exploratory | mvp | standard | governance | custom
core_outcome: string
primary_actor_or_consumer: string | null
core_flows:
  - id: string
    description: string
    priority: must | should | could
scope_surfaces:
  - id: string
    name: string
    status: in_scope | deferred | out_of_scope
    required_depth: mention | define | required_fields | full_schema | exhaustive | custom
    rationale: string
deferral_rules:
  - id: string
    trigger: string
    action: defer | allow_if_core | allow | block
    decline_reason: out_of_scope | deferred_to_later_round | architectural_conflict | ambiguous
    rationale: string
acceptance_floor:
  minimum_buildable_result: string
  must_answer: [string]
  may_defer: [string]
review_pressure_limits:
  max_depth_default: mention | define | required_fields | full_schema | exhaustive | custom
  expansion_policy: conservative | balanced | expansive
operator_decisions:
  - question: string
    answer: string
    rationale: string
approval:
  approved: boolean
  approved_by: string | null
  approved_at: timestamp | null
```

`whetstone intake --template mvp --output scope-notes.md` MUST produce a human-editable scope notes template. `whetstone intake --from-notes scope-notes.md` MUST produce a schema-valid scope contract. Unless `--approve` is supplied, generated contracts MUST remain `status = draft` and MUST NOT satisfy the MVP preflight requirement.

## SPEC DECOMPOSITION WORKFLOW

Spec decomposition splits an overloaded source spec into a governed spec family while preserving normative content, source provenance, and authority boundaries.

Decomposition MUST NOT assume the source spec is already an HLD. The source spec may be an architecture spec, workflow spec, protocol spec, artifact/schema spec, rubric spec, implementation spec, or any other document that has accumulated multiple separable authority surfaces.

Decomposition trigger thresholds are advisory calibration seeds, not empirical guarantees or convergence requirements. Default thresholds SHOULD be conservative under-triggering starting points: high enough that ordinary medium-sized specs are not decomposed unexpectedly, but low enough to flag documents whose size, section count, cross-reference density, or authority-surface count makes lossless ownership review difficult. If an implementation ships numeric defaults such as section-count, line-count, or cross-reference-density thresholds, the defaults MUST be documented as seed values expected to be refined from observed Whetstone runs, and operator overrides SHOULD be persisted with the resulting decomposition plan or run artifacts.

Definitions:

- `source_spec`: the original spec being considered for decomposition.
- `target_spec`: any spec produced by an approved decomposition.
- `coordinating_spec`: an optional target spec that owns orientation, cross-spec relationships, shared terminology, and authority routing for a decomposed family.
- `leaf_spec`: a target spec that owns detailed requirements for one bounded subsystem, workflow, artifact family, protocol, rubric, or other authority surface.
- `peer_spec`: a target spec in a peer-family split where no coordinating target spec is produced.
- `decomposition_manifest`: the authoritative artifact recording source-to-target provenance, hashes, authority topology, and coverage status.
- `extractable_unit`: the smallest source unit the decomposition plan may assign to a target spec.

Extractable units:

- A leaf section is an extractable unit.
- A non-leaf section is a container by default and MUST NOT be assigned directly.
- A non-leaf section MAY produce a synthetic `intro` extractable unit for direct body content before its first child heading.
- Extractable-unit `section_id` values MUST be stable across source spec title/version changes; the decomposition planner MUST NOT include the document H1 title in generated child section IDs.
- An `intro` unit exists only when the direct body content is meaningful. Meaningful direct body content contains at least one normative token, a code block, a table, a list, or more than a trivial implementation-defined token threshold.
- Meaningless connective prose such as "This section defines the following" SHOULD remain container scaffolding and SHOULD NOT create an extractable unit.
- Meaningful direct body content after a non-leaf section's child sections is invalid for decomposition planning. The planner MUST reject it rather than create an `outro` unit in the MVP implementation.

Authority topology MUST be one of:

- `coordinated_family`: one coordinating spec plus one or more leaf specs.
- `peer_family`: two or more peer specs with no coordinating spec; authority routing is owned by the decomposition manifest or an existing external index.
- `parent_child`: one parent spec remains authoritative for shared flow/intent while child specs own bounded details.
- `appendix_extraction`: one or more detailed appendices, schemas, rubrics, or artifact contracts are extracted while the source spec remains primary for the surrounding behavior.
- `no_split`: the plan determines the source spec should remain a single authority.

Decomposition phases:

1. `plan`
   - Inventory headings, section IDs, extractable units, source line ranges, normative statements, artifacts, schemas, roles, states, and cross-references.
   - Propose target specs, authority topology, extractable-unit assignments, and known duplicated/shared concepts.
   - MUST NOT mutate the source spec or write target specs.

2. `approve`
   - Operator reviews and approves a specific decomposition plan.
   - Approval MUST bind the source spec hash, plan hash, target paths, authority topology, and extraction mode.
   - Approval MUST re-read the current source spec and reject approval if its current hash differs from the plan's `source_spec_hash`.
   - Approval MUST persist `operator_approval.approved = true`, `approved_by`, `approved_at`, and `approved_plan_hash`.
   - Approval MUST set `planning_mode = approved_split`.
   - `approved_plan_hash` MUST be computed from the approval-bound plan content excluding `operator_approval` metadata, with `planning_mode` normalized to `approved_split`.
   - Re-running approval for the same unchanged plan SHOULD be idempotent.
   - Extraction MUST NOT run without an approved plan.

3. `extract`
   - Create target specs by copy-first extraction from the source spec.
   - Extraction MAY add minimal provenance headers, target titles, and backreference placeholders.
   - Extraction MUST NOT paraphrase, summarize, reorder normative content, or silently remove requirements.
   - Extraction MUST preserve readable heading hierarchy under each generated target title.
   - If an extracted `intro` unit is included, extraction MUST include the source parent heading as structural context before the intro body.
   - If a standalone child section is extracted without its parent section, extraction MUST normalize copied heading levels so the first copied heading is a top-level target section below the generated target title.
   - Extraction MUST require an approved plan whose `operator_approval.approved_plan_hash` still matches the current plan content.
   - Extraction MUST re-read the source spec and reject extraction if its current hash differs from the approved plan's `source_spec_hash`.
   - Extraction MUST write `decomposition_manifest.json`.

4. `audit`
   - Verify every extractable unit and its normative statements are assigned to at least one target spec, intentionally duplicated, or explicitly retired with rationale.
   - Verify target specs preserve source hashes/ranges in provenance metadata.
   - Verify authority surfaces are not duplicated without an explicit shared-authority or supersession rule.
   - Audit MUST write `coverage_matrix.md`.
   - Audit MUST write `unmapped_requirements.md` when extractable units or normative units are unmapped.
   - Audit MUST write `duplicated_authority_report.md` when the same extractable unit appears in more than one target spec without an explicit duplication authority model.
   - Audit MUST update `decomposition_manifest.json.coverage_status`.
   - Audit MUST fail when target files are missing, target hashes drift, provenance headers are missing, source hash drifts, normative units are unmapped, or extractable units are duplicated.

5. `promote`
   - Mark the decomposed spec family as authoritative only after the audit succeeds and the operator accepts the decomposition manifest.
   - Before promotion, the source spec remains authoritative.
   - Promotion MUST require `coverage_status = complete`.
   - Promotion MUST require an `audit` object with no issues, a matching source hash, and passing target existence, target hash, and provenance checks.
   - Promotion MUST persist `promoted = true`, `promoted_at`, `promoted_by`, and `promotion_manifest_hash`.
   - Promotion MUST NOT mutate the source spec or extracted target specs.

Decomposition plan inputs:

- `source_spec_path`
- `source_spec_hash`
- optional operator-supplied decomposition map
- optional target spec path map
- optional authority topology preference
- optional extraction mode
- optional explicit retired-extractable-unit list

Decomposition plan outputs MUST include:

```yaml
schema_version: string
source_spec_path: string
source_spec_hash: string
planning_mode: inventory_only | proposed_split | approved_split
authority_topology: coordinated_family | peer_family | parent_child | appendix_extraction | no_split
extraction_mode: copy_first
target_specs:
  - target_spec_id: string
    target_spec_path: string
    target_spec_role: coordinating_spec | leaf_spec | peer_spec | appendix_spec
    owned_authority_surfaces: [string]
    source_units:
      - section_id: string
        scope: section | intro
        unit_id: string
    source_section_ids: [string] # derived compatibility field listing sections represented by source_units
    source_line_ranges:
      - unit_id: string
        section_id: string
        scope: section | intro
        start_line: integer
        end_line: integer
    normative_statement_count: integer
extractable_units:
  - unit_id: string
    section_id: string
    scope: section | intro
    start_line: integer
    end_line: integer
    normative_statement_count: integer
coverage:
  source_section_count: integer
  extractable_unit_count: integer
  assigned_extractable_unit_count: integer
  unassigned_extractable_unit_ids: [string]
  retired_extractable_unit_ids: [string]
  duplicated_extractable_unit_ids: [string]
  assigned_source_section_count: integer
  unassigned_source_section_ids: [string] # compatibility alias for unassigned_extractable_unit_ids
  retired_source_section_ids: [string] # compatibility alias for retired_extractable_unit_ids
  duplicated_source_section_ids: [string] # compatibility alias for duplicated_extractable_unit_ids
operator_approval:
  approved: boolean
  approved_by: string | null
  approved_at: string | null
  approved_plan_hash: string | null
```

Decomposition map inputs SHOULD use structured `source_units`:

```yaml
target_specs:
  - target_spec_id: string
    target_spec_path: string
    target_spec_role: coordinating_spec | leaf_spec | peer_spec | appendix_spec
    owned_authority_surfaces: [string]
    source_units:
      - section_id: string
        scope: section | intro
```

For backward compatibility, a map MAY supply `source_section_ids`, but each listed section MUST be a leaf section. If a map assigns a non-leaf container section through `source_section_ids`, the planner MUST reject the map with a helpful error. Assigning only a parent intro MUST use structured `source_units` with `scope: intro`.

`decomposition_manifest.json` MUST include:

```yaml
schema_version: string
source_spec_path: string
source_spec_hash: string
approved_plan_hash: string
authority_topology: string
extraction_mode: copy_first
target_specs:
  - target_spec_id: string
    target_spec_path: string
    target_spec_hash: string
    target_spec_role: string
    source_units:
      - unit_id: string
        section_id: string
        scope: section | intro
    source_section_ids: [string]
    source_line_ranges:
      - unit_id: string
        section_id: string
        scope: section | intro
        start_line: integer
        end_line: integer
    provenance_header_present: boolean
coverage_status: complete | incomplete
unmapped_requirements_path: string | null
duplicated_authority_report_path: string | null
audit: object | null
promoted: boolean
promoted_at: string | null
promoted_by: string | null
promotion_manifest_hash: string | null
```

Lossless extraction rules:

- The source spec hash MUST match the approved plan hash guard before extraction.
- Target paths MUST be inside the configured project or run root and MUST NOT overwrite existing files unless `overwrite_targets = true` is explicitly approved.
- Target paths MUST be resolved against an explicit extraction root or the plan directory and MUST NOT escape that root.
- Every copied section MUST preserve its original prose except for heading-level normalization and provenance headers.
- Any summarization, paraphrase, deduplication, terminology normalization, or authority rewrite MUST be deferred to later Whetstone review of the extracted target specs.
- Extraction MUST preserve code blocks, tables, enum values, examples, MUST/SHOULD/MAY language, artifact paths, schema snippets, and rationale notes.
- If a non-leaf section contains meaningful direct intro content, that content MUST be assigned through its synthetic `intro` unit or explicitly retired.
- If a non-leaf section contains meaningful direct trailing content after child sections, planning MUST fail until the source is restructured.
- Extractable units MUST form an exact partition across target specs unless duplication is explicitly introduced by a future non-MVP authority model.

Coverage invariants:

- Every extractable unit MUST have one of: assigned, duplicated, retired, or unassigned.
- Every normative statement inside an extractable unit MUST have one of: assigned, duplicated, retired, or unmapped.
- Decomposition audit MUST fail when any normative statement remains unmapped.
- Retired normative content MUST include an operator-approved rationale.
- Duplicated authority MUST include a precedence, shared-authority, or future-reconciliation rule.

Failure handling:

- Planning failure MUST NOT mutate the source spec or target specs.
- Extraction MUST halt if the source hash no longer matches the approved plan.
- Extraction MUST halt if target paths are invalid or would overwrite unapproved files.
- Audit MUST fail if coverage is incomplete, target hashes are missing, provenance headers are missing, or duplicated authority lacks a rule.
- Promotion MUST fail unless the audit is complete and operator approval is present.

The decomposition workflow is separate from normal review convergence. A decomposed target spec MAY later enter Whetstone review as a normal source spec. Decomposition artifacts are provenance artifacts; they do not by themselves imply that any target spec has converged.

---

## EXPANDING CONTRACT SURFACE

`EXPANDING_CONTRACT_SURFACE` is a non-terminal diagnostic condition. It means repeated serious findings in one profile indicate that the system is no longer merely patching isolated defects; it is discovering or creating an immature contract family whose schemas, enums, validation rules, failure semantics, mapping tables, ordering rules, artifact semantics, or invocation surfaces need a holistic synthesis pass.

When enabled, the Orchestrator SHOULD evaluate expanding-contract-surface evidence after each successful Phase 1 reviewer/editor round. The detector SHOULD consider:

- number of rounds already spent on the current profile
- count of recent rounds with in-scope blocker or major findings
- clustering of serious findings around contract-bearing concepts such as schemas, validation, failure mapping, ordering, artifacts, checkpoints, replay behavior, or interfaces
- affected sections and feedback IDs across the recent window
- whether new serious findings continue to appear after previous Editor fixes

Detection MUST NOT by itself mark a profile clean, halt the run, or waive accepted-draft requirements.

If detected, the Orchestrator MUST persist:

```yaml
/rounds/contract_surface_report.json:
  detected: true
  type: EXPANDING_CONTRACT_SURFACE
  terminal_effect: none
  action_taken: injected_into_next_round_context | report_only
  next_round_number: integer | null
  requires_operator_action: false
  synthesis_pass_executed: false
  lifecycle_status: synthesis_pass_recommended | resolved_by_later_rounds | still_open | operator_review_recommended
  resolution_round_number: integer | null
  round_number: integer
  profile: string
  draft_hash: sha256
  profile_rounds_observed: integer
  recent_window: integer
  serious_recent_rounds: integer
  contract_families: [string]
  affected_sections: [string]
  suspected_feedback_ids: [string]
  round_evidence: [object]
  recommendation: synthesis_pass_recommended
  synthesis_scope:
    sections: [string]
    contract_families: [string]
    instruction: string
```

`terminal_effect` MUST be `none` for this version. `EXPANDING_CONTRACT_SURFACE` is advisory only: it does not halt execution, skip a profile, mark a profile clean, waive accepted-draft requirements, or imply that a synthesis pass has already occurred.

When `action_taken = injected_into_next_round_context`, the Orchestrator MUST expose the report to the next matching Editor round as a context file and set `next_round_number` to the first round where the report is expected to be available. This action is prompt context injection, not an automatic synthesis pass. `synthesis_pass_executed` MUST remain `false` unless a future explicit synthesis-pass workflow is implemented and actually run.

`contract_surface_report.md` SHOULD summarize the same information for operators, including terminal effect, action taken, next round, operator-action requirement, whether synthesis was executed, lifecycle status, and resolution round.

The Orchestrator SHOULD update `lifecycle_status` as later rounds complete:

- `synthesis_pass_recommended`: initial detected state when the report is injected into future Editor context.
- `resolved_by_later_rounds`: a later round for the same profile produced clean Reviewer feedback after the report was generated.
- `still_open`: later profile rounds have occurred, but no later clean Reviewer pass has resolved the surface.
- `operator_review_recommended`: the run reached terminal state while the surface remained unresolved or ambiguous.

When a matching `contract_surface_report.json` exists for the active profile, Editor prompts MAY include timeout-aware bounded synthesis guidance. A resumed Editor prompt after timeout SHOULD tell the Editor to read the contract surface report, prefer bounded synthesis over the report's listed sections and contract families, preserve global coherence, and still return `draft_after_content` as the complete revised draft text.

The initial action is `recommend_synthesis`, which currently means "recommend and prepare bounded synthesis by injecting the report into the next applicable Editor context." Future versions MAY add automatic synthesis-pass scheduling, but automatic synthesis MUST remain explicit in configuration and MUST NOT silently replace normal profile review.

---

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
decision_status_counts: object
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
terminal_state: HALTED_ARTIFACT_INVALID | HALTED_CLIENT_TIMEOUT
generated_at: string
round_number: integer
phase: phase_1 | phase_2
profile: string
client_role: reviewer | editor
client:
  name: string
  version: string
  model: string
failure_type: artifact_validation | client_timeout | client_error
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
