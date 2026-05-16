# WHETSTONE - AI SPEC CONVERGENCE ORCHESTRATOR (0.64 - STRICT CANDIDATE)

## Purpose

Automate iterative technical review between AI clients (e.g., Claude Code, Codex) to drive a spec from v0.1 -> converged (mid/final, permissive/strict), with controlled multi-perspective review per round, deterministic convergence behavior, explicit failure handling, and fully specified primitives.

Reading guide: This spec defines the core convergence subsystems: round scheduling, severity normalization, identity for issues/conflicts/oscillation, rubric gap tracking, convergence declaration, and artifact validation. It also defines operator workflows such as scope intake, decision capture, apply-back, and spec decomposition. The state machine and halting conditions sections describe how the runtime subsystems compose into deterministic execution.

Version `0.64` clarifies decomposition trigger-threshold rationale so configurable defaults are treated as calibration seeds rather than unexplained constants.

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
- scope_contract.json (required for `workflow: mvp`, optional for other workflows unless configured)
- reference context files (optional; e.g., HLDs, architecture notes, authority maps)
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
  - operator_decision_checkpoint.json
  - rubric_gaps.json (Phase 2 only)
  - profile_used.yaml (JSON-compatible metadata despite `.yaml` suffix)
  - prompt_snapshot.json
  - prompt_snapshots/
    - {client_role}-{artifact_name}-attempt-{attempt_number}.json
  - context/
    - draft_before.md
    - scope_contract.json (when an approved scope contract is available)
    - rubric.md (when rubric text is provided to the client)
    - convergence_declaration.md (Phase 2 convergence-check rounds only)
    - reviewer_feedback.json (Editor prompts only)
  - client_telemetry/
    - {client_role}-{artifact_name}-attempt-{attempt_number}.json
- /rounds/oscillation_report.json (if detected)
- /rounds/conflict_report.json (if escalated)
- /rounds/technical_failure_report.json (if Phase 1 fails)
- /rounds/convergence_failure_report.json (if Phase 2 fails)
- /rounds/config_validation_error.json (if preflight configuration validation fails)
- /rounds/artifact_validation_error.json (if client artifact validation retries are exhausted)
- /rounds/decision_register.json (at terminal state)
- /rounds/decision_register.md (human-readable decision register, at terminal state)
- /rounds/decision_summary.json (at terminal state)
- /rounds/decision_summary.md (human-readable decision summary, at terminal state)
- /rounds/decision_intervention_request.json (if decision intervention is required)
- /rounds/operator_decision_checkpoint_summary.json (at terminal state)
- /rounds/operator_decision_checkpoint_summary.md (human-readable checkpoint summary, at terminal state)
- /rounds/intake/scope_contract.json (approved scope contract, when present)
- /rounds/contract_surface_report.json (if expanding contract surface is detected)
- /rounds/contract_surface_report.md (human-readable synthesis recommendation, if detected)
- /rounds/rubric_manifest.json (required before Phase 2 review begins)
- /decomposition/decomposition_plan.json (if spec decomposition planning is run)
- /decomposition/decomposition_plan.md (human-readable decomposition plan)
- /decomposition/decomposition_manifest.json (if extraction is run)
- /decomposition/coverage_matrix.md (if extraction or audit is run)
- /decomposition/unmapped_requirements.md (if required source content is not assigned)
- /decomposition/duplicated_authority_report.md (if duplicated authority is detected)

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
  max_rounds: 12             # legacy/safety metadata; profile_budgets drive scheduling
  mode: horizontal            # horizontal | vertical
  profile_set: stateful_system # stateful_system | balanced_mvp | utility_mvp | governance
  budget_exhaustion_policy: hard  # hard | soft
  profile_budgets:
    structural_integrity: 10
    determinism: 10
    operability: 10

convergence:
  enabled: true
  target_phase: final        # mid | final
  target_mode: strict        # permissive | strict
  rubric_profile: governance-v6
  rubric_source: builtin      # builtin | custom
  rubric_label: ""            # REQUIRED when rubric_source = custom
  rubric_path: ./convergence_rubric.md
  max_rounds: 8              # legacy/safety metadata; profile_budgets drive scheduling
  profile_budgets:
    convergence_strict_check: 10
    adversarial: 10

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

timeouts:
  reviewer_seconds: 360
  editor_seconds: 900

contract_surface_policy:
  enabled: true
  action: recommend_synthesis   # recommend_synthesis | report_only
  min_profile_rounds: 4
  recent_window: 4
  min_recent_serious_rounds: 3
  min_contract_families: 2

scope_contract:
  path: ./rounds/intake/scope_contract.json

reference_context:
  files:
    architecture_hld:
      path: ./docs/hld-architecture.md
      role: architecture_authority
      required: true
```

Before entering `TECHNICAL_REVIEW`, the Orchestrator MUST validate configuration.

Client `version` and `model` fields MUST be non-empty strings after trimming whitespace. If any required client field is empty, the Orchestrator MUST halt before the first review round and produce `/rounds/config_validation_error.json` identifying the invalid fields. This preflight failure does not consume a Phase 1 or Phase 2 round.

`reference_context.files` is an optional map keyed by stable context label. Each entry MUST include:

- `path`: filesystem path to the reference document
- `role`: short role label, such as `architecture_authority`, `domain_requirements`, `source_policy`, or `implementation_context`
- `required`: boolean

If a required reference context file is missing, the Orchestrator MUST halt before the first review round with `CONFIG_INVALID`. Optional missing reference context files are ignored for context injection but remain visible in config snapshots.

Reference context files are not mutable draft artifacts. The Orchestrator MUST NOT edit them. When present, they are supplied as read-only file-backed context to Reviewer and Editor prompts. Reviewers and Editors MUST treat them as authority according to their configured `role` and MUST NOT inspect unlisted files to recover missing architecture or domain context.

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

### Scope Contract

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

## HALTING CONDITIONS (ORDERED PRECEDENCE)

1. Clean convergence achieved
2. Blocker-level conflict escalation triggered
3. Oscillation stop triggered
4. Artifact validation failure exhausted
5. Decision intervention required
6. profile budgets or max_rounds reached

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

soft Phase 1 profile-budget sweep completed with residuals:
- terminal_state: PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS
- required artifacts:
  - technical_failure_report.json
  - latest draft_after.md
  - spec.history.md
  - profile_status with per-profile residual_status values

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

client invocation timeout:
- terminal_state: HALTED_CLIENT_TIMEOUT
- required artifacts:
  - artifact_validation_error.json with failure_type = client_timeout
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

For versioned specs, the Orchestrator MUST stamp accepted mutating rounds with a new visible version label before computing and persisting the final `draft_after_hash`. A spec is versioned when its root heading, `Status:` line, or `Version:` field contains a supported numeric version label. If no supported numeric version anchor exists, the Orchestrator MAY skip version stamping and MUST continue to use hashes and round artifacts as rollback authority.

Version stamping rules:

- Phase 1 accepted mutating revision: increment the fractional stabilization version by one hundredth.
- Phase 1 non-mutating round: do not change the version label.
- Phase 1 rejected or unresolved round: do not change the version label.
- Phase 2 entry: promote to the smallest whole major version that is greater than or equal to the current numeric version, with a minimum of `1.0`.
- Unversioned Phase 2 entry: if no supported numeric version anchor exists, promotion MUST be a no-op (`promoted = false`) and MUST NOT block Phase 2 when the Phase 1 stable hash guard otherwise passes.
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

4. `audit`
   - Verify every extractable unit and its normative statements are assigned to at least one target spec, intentionally duplicated, or explicitly retired with rationale.
   - Verify target specs preserve source hashes/ranges in provenance metadata.
   - Verify authority surfaces are not duplicated without an explicit shared-authority or supersession rule.

5. `promote`
   - Mark the decomposed spec family as authoritative only after the audit succeeds and the operator accepts the decomposition manifest.
   - Before promotion, the source spec remains authoritative.

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
promoted: boolean
promoted_at: string | null
```

Lossless extraction rules:

- The source spec hash MUST match the approved plan hash guard before extraction.
- Target paths MUST be inside the configured project or run root and MUST NOT overwrite existing files unless `overwrite_targets = true` is explicitly approved.
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

## ROUND STRATEGY (ADAPTIVE)

The following strategy is the default `stateful_system` profile-set strategy. Other profile sets replace the profile sequence and default budgets while preserving the same scheduler semantics.

```yaml
round_strategy:
  phase_1:
    - profile: structural_integrity
      skip_if_clean: true
      repeat_if_blockers: true
      round_budget: 10
    - profile: determinism
      skip_if_clean: true
      repeat_if_blockers: true
      round_budget: 10
    - profile: operability
      skip_if_clean: false
      repeat_if_blockers: true
      round_budget: 10

  phase_2:
    - profile: convergence_strict_check
      repeat_if_blockers: true
      round_budget: 10
    - profile: adversarial
      repeat_if_blockers: true
      round_budget: 10
    - profile: convergence_strict_check
      repeat_if_blockers: true
      round_budget: 10
```

## ROUND SCHEDULING ALGORITHM

Phase 1 supports two review modes:

- `horizontal` (default): execute one profile review, run the Editor, then repeat or advance according to that profile's result.
- `vertical`: execute each configured Phase 1 profile as an independent Reviewer pass over the same `draft_before.md`, merge the resulting feedback, run one consolidated Editor revision, then repeat the full profile stack against the revised draft until every profile verifies clean on the same draft or profile budgets are exhausted.

In `vertical` mode, each profile review remains independent: it MUST have its own prompt, profile focus, `reviewer_feedback.json`, `profile_used.yaml`, prompt snapshot, context files, telemetry, and validation. Only the Editor step is consolidated.

The vertical merge artifact MUST preserve each finding's source profile. If feedback IDs are not globally unique across profile reviews, the Orchestrator MUST rewrite feedback IDs in the consolidated Editor packet using a deterministic profile-qualified form. Issue IDs and issue fingerprints remain those of the original reviewer findings.

Each round's `profile_used.yaml` MUST include:
- `profile`: the review profile or synthetic profile label
- `round_kind`: one of `review_editor`, `review_only`, `consolidated_editor`, or `fixture`

`vertical` mode MUST NOT mark a profile clean from Editor resolution claims. After any consolidated Editor mutation, all Phase 1 profiles must be reviewed again against the revised draft before Phase 1 can become stable.

For terminal reporting, a vertical profile's clean status applies only to the draft hash reviewed by that profile. If a later consolidated Editor mutation changes the draft, `technical_failure_report.json` MUST treat previously clean vertical profiles as unverified for the current draft until they review the changed draft again.

If vertical mode exhausts profile review budgets immediately after an accepted consolidated Editor mutation and there are no unresolved blocker or major issues, the Orchestrator MAY run one verification-only closeout cycle. The closeout cycle MUST:
- run each required Phase 1 profile once against the current draft
- invoke only Reviewer clients
- MUST NOT invoke the Editor
- MUST NOT mutate `spec.md`
- be persisted as normal review-only `round-N/` artifacts
- mark Phase 1 stable only if every closeout profile review is clean for the current draft hash

Stale profile residual status from a prior draft, including `exhausted_with_residuals`, MUST NOT by itself prevent the closeout cycle. The closeout cycle is the bounded mechanism that either clears stale profile debt by producing clean review-only passes for the current draft or confirms that blocker/major debt remains.

If the closeout cycle finds any blocker or major issue, the Orchestrator MUST NOT run another automatic Editor revision. It MUST halt using the applicable Phase 1 budget-exhaustion terminal state and report the remaining verification debt.

In `vertical` mode, `review_round_budget` MUST include the configured profile review budgets plus the maximum number of possible consolidated Editor rounds. Profile budget maps still count only independent profile review passes.

Phase 1 `horizontal` mode executes configured profiles in order.

For each Phase 1 profile in `horizontal` mode:
- run the profile unless `skip_if_clean = true` and the current draft already has a valid clean result for that profile
- the profile result is clean only when the Reviewer review of `draft_before.md` for that round returns zero in-scope blocker issues and zero in-scope major issues
- editor resolution claims in `editor_summary.json` determine which findings remain unresolved after the edit, but they MUST NOT by themselves mark the reviewed profile clean
- if the profile returns in-scope blocker or major issues and `repeat_if_blockers = true`, schedule the same profile again after editor revision until a later Reviewer pass verifies the current draft clean or the profile's `round_budget` is exhausted
- if the Reviewer pass is clean but the Editor mutates the draft in the same round, that clean result applies only to the pre-edit draft and MUST NOT mark the post-edit draft clean; the same profile requires a later clean verification pass unless a computable skip rule applies
- if the editor mutates any section whose canonical section ID matches the profile's resolved focus anchors, previous clean status for that profile is invalidated
- if the editor mutates only sections outside the profile's resolved focus anchors, previous clean status for that profile remains valid

If horizontal mode exhausts profile review budgets immediately after an accepted Editor mutation and there are no unresolved blocker or major issues, the Orchestrator MAY run one verification-only closeout pass over the profiles still marked unverified. The closeout pass MUST:
- invoke only Reviewer clients
- MUST NOT invoke the Editor
- MUST NOT mutate `spec.md`
- be persisted as normal review-only `round-N/` artifacts
- mark Phase 1 stable only if every closeout profile review is clean for the current draft hash

If the horizontal closeout pass finds any blocker or major issue, the Orchestrator MUST NOT run another automatic Editor revision. It MUST halt using the applicable Phase 1 budget-exhaustion terminal state and report the remaining verification debt.

If a Phase 1 Editor returns an unchanged draft while one or more in-scope blocker or major Reviewer findings remain unresolved, the Orchestrator MUST NOT classify that event as oscillation solely because the draft hash repeats. It MUST produce a Phase 1 technical failure report with `terminal_state: TARGET_NOT_REACHED`, `current_draft_status: not_accepted`, and an exit reason indicating unchanged Editor output with unresolved serious findings. This represents Reviewer/Editor disagreement or no-op editing debt, not semantic draft churn.

Phase 1 completes only when:
- all non-skipped Phase 1 profiles have valid clean status, and
- the current draft is accepted.

Phase 2 executes configured profiles in order.

After each Phase 2 reviewer/editor cycle, the Orchestrator MUST evaluate halt conditions in the ordered precedence defined by this spec.

Phase 2 completion is checked after each validated Phase 2 review cycle and any resulting declaration revision, not only after the full configured Phase 2 profile sequence has been exhausted.

As in Phase 1, Phase 2 profile cleanliness is based on Reviewer findings against `draft_before.md`, not on Editor resolution claims in the same round. A Phase 2 profile with any in-scope blocker or major finding is not clean even if the Editor resolves every finding in `draft_after.md`; a later Reviewer pass must verify the resulting draft. A clean Reviewer pass followed by an Editor mutation also requires later verification of the mutated draft.

For `target_phase = final` and `target_mode = strict`, the Orchestrator MUST NOT declare clean convergence until every distinct Phase 2 profile name in the configured sequence has produced at least one clean result in Phase 2 for the current draft lineage.

If Phase 2 reaches the end of its configured profile sequence with:
- zero unresolved in-scope blockers,
- zero unresolved in-scope major issues,
- zero unresolved rubric gaps,
- at least one required Phase 2 profile not yet verified clean on the current draft hash, and
- no Phase 2 profile budget exhausted with residual findings,

the Orchestrator MAY run a bounded reviewer-only Phase 2 closeout pass over the unverified distinct profile names. The closeout pass MUST:
- invoke only Reviewer clients
- MUST NOT invoke the Editor
- MUST NOT mutate `spec.md`
- be persisted as normal `review_only` `round-N/` artifacts
- include `convergence_declaration.md` as file-backed context when the closeout profile is a convergence-acceptance profile
- accept the convergence declaration and enter `CONVERGED` only if every closeout profile returns zero in-scope blocker and major findings and the target matrix remains satisfied

If any closeout profile finds an in-scope blocker or major issue, the Orchestrator MUST halt with `TARGET_NOT_REACHED` and produce `convergence_failure_report.json` identifying the remaining verification debt. The closeout pass MUST NOT be used to override exhausted profile budgets with residual findings.

`distinct Phase 2 profile` means unique by profile name, not sequence slot. In the default Phase 2 sequence, the two `convergence_strict_check` entries count as one distinct profile for this requirement, though both sequence positions may still run as scheduled.

If a Phase 2 profile is not run because of an explicit future skip condition, the skip condition MUST be persisted in `profile_used.yaml` and MUST count as a clean result only if the skip rule is computable from current artifacts.

If Phase 2 reaches the end of its configured profile sequence without clean convergence, the Orchestrator MUST halt with `TARGET_NOT_REACHED` and produce `convergence_failure_report.json` unless a future explicit schedule-loop rule is configured.

If Phase 2 exhausts its configured profile-level round budgets before clean convergence, the Orchestrator MUST halt with `TARGET_NOT_REACHED` and produce `convergence_failure_report.json`.

Phase 2 completes only when clean convergence is achieved.

Clean convergence is achieved when:
- the current draft satisfies the configured target matrix,
- `convergence_declaration.md` exists,
- the declaration is accepted under the convergence declaration criteria, and
- every required distinct Phase 2 profile has produced a clean Reviewer result for the current unmodified draft lineage,
- no halt condition with higher or equal precedence has already fired.

Candidate convergence declarations are Orchestrator-owned and MAY exist before final acceptance with `reviewer_final_status: not_run` and `declaration_status: rejected`.

After each Phase 2 round, if an existing candidate `convergence_declaration.md` has `final_draft_hash` that differs from the current `draft_after_hash`, the Orchestrator MUST regenerate the candidate declaration for the current draft before oscillation, conflict, or terminal-state evaluation for that round.

If the only remaining blocker or major findings are declaration hash-binding mismatches that are repaired by this Orchestrator-owned regeneration, those findings MUST be removed from the active unresolved issue set for scheduler, conflict, oscillation, target-matrix, and failure-report evaluation. The Editor MUST NOT be asked to repair `convergence_declaration.md` by mutating `spec.md`.

`rounds/run_state.json` MUST expose both configured and effective profile budgets. `configured_review_profile_budgets` and `configured_convergence_profile_budgets` preserve the explicit config overrides supplied by the operator. `review_profile_budgets` and `convergence_profile_budgets` MUST contain the resolved effective budgets used by the scheduler, including defaults for omitted profiles.

`rounds/run_state.json` MUST also include `effective_run_config`, a compact persisted run-identity block used by resume. It MUST include:

```yaml
effective_run_config:
  review_mode: horizontal | vertical
  review_profile_budgets: map<string, integer>
  review_budget_exhaustion_policy: hard | soft
  convergence_profile_budgets: map<string, integer>
  decision_points:
    enabled: boolean
    mode: end_of_cycle | intervention
    intervention_thresholds:
      severities: [blocker | major | minor | nit]
      trigger_on_requirement_strength_change: boolean
      trigger_on_authority_boundary_change: boolean
      trigger_on_scope_change: boolean
      trigger_on_new_enum_or_error_code: boolean
  timeouts:
    reviewer_seconds: integer | null
    editor_seconds: integer | null
  contract_surface_policy:
    enabled: boolean
    action: recommend_synthesis | report_only
    min_profile_rounds: integer
    recent_window: integer
    min_recent_serious_rounds: integer
    min_contract_families: integer
  scope_contract:
    path: string
  reference_context:
    files:
      <label>:
        path: string
        role: string
        required: boolean
```

The budget maps in `effective_run_config` MUST be the resolved effective maps used by the scheduler, not merely the operator-supplied override maps.

`review_budget_exhaustion_policy` controls only Phase 1 profile-budget exhaustion and Phase 1 profile-level oscillation handling:

- `hard`: the Orchestrator preserves the default strict behavior. A profile that exhausts its budget with unresolved or unverified blocker/major status prevents further Phase 1 advancement and ultimately halts with `TARGET_NOT_REACHED`, unless a higher-precedence halt fires first.
- `soft`: the Orchestrator MAY advance from an exhausted or oscillating Phase 1 profile to the next configured Phase 1 profile, but it MUST mark the prior profile with a residual status and MUST NOT mark the profile clean.

Soft budget mode is a diagnostic sweep mode, not convergence. If all Phase 1 profiles have been visited but one or more required profiles has residual status, the Orchestrator MUST halt with `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`, produce `technical_failure_report.json`, set `ready_for_phase_2 = false`, and require external input before any Phase 2 run.

A clean Reviewer pass for a profile MUST take precedence over budget exhaustion for that same profile. If the latest consumed budget round for a profile has zero in-scope blockers and zero in-scope majors, the profile MUST be marked clean even when that round equals the profile's configured budget. Budget exhaustion MUST NOT create a residual profile status after a clean latest pass.

If a clean Reviewer pass is followed only by Orchestrator-owned metadata mutation such as version stamping, that metadata mutation MUST NOT by itself invalidate the clean profile. If the Editor accepts or modifies feedback and changes the draft, the clean Reviewer pass applies only to the pre-edit draft and the profile still requires later clean verification.

Allowed Phase 1 residual statuses are:

- `exhausted_with_residuals`: the profile consumed its configured budget without valid clean Reviewer verification for the current draft.
- `halted_oscillation`: an oscillation stop condition was detected for the profile, but soft budget mode advanced the sweep to preserve cross-profile diagnostic coverage.

When soft mode converts a Phase 1 oscillation into a residual profile status, the Orchestrator MUST still persist `oscillation_report.json`. The top-level `run_state.json` terminal state remains the authority for whether the overall run halted immediately or continued the sweep.

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

## DEFINITION: CLEAN PROFILE

A profile is considered clean if:
- zero blocker issues within profile focus
- zero major issues within profile focus

Non-focus issues do not affect profile cleanliness.

A clean profile does not imply an accepted draft.

---

## ROUND BUDGET HANDLING

Round budgets are controlled at the profile-step level.

Each configured profile step MUST define `round_budget`, an integer greater than or equal to 1. The budget counts Reviewer passes for that profile step. Editor retries caused by invalid artifacts do not consume profile budget unless a validated Reviewer pass is accepted for the round.

`review.max_rounds` and `convergence.max_rounds` MAY be retained as legacy/safety metadata for operator display and backward compatibility, but they MUST NOT be the primary scheduler stop condition when profile-level budgets are configured.

Unused profile budget is not carried over to later profiles or phases.

Phase 2 may halt before consuming its full budget if clean convergence is achieved.

When `review_budget_exhaustion_policy = hard`, Phase 1 profile-budget exhaustion is a hard stop if any required Phase 1 profile lacks valid clean status or the current draft is not accepted. It does not proceed automatically to Phase 2.

When `review_budget_exhaustion_policy = soft`, Phase 1 profile-budget exhaustion advances to the next configured Phase 1 profile after recording residual status for the exhausted profile. After the final configured Phase 1 profile is exhausted or verified, the Orchestrator MUST evaluate Phase 1 stability. If stability is not achieved, it MUST halt with `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS` rather than `TARGET_NOT_REACHED`.

Soft budget mode MUST NOT weaken accepted-draft requirements, clean-profile requirements, convergence readiness, or Phase 2 entry. It only changes whether Phase 1 stops immediately on the first exhausted/oscillating profile or completes the remaining profile sweep for diagnostic value.

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

If a live Reviewer returns valid feedback with `feedback = []` and no explicit external `draft_after.md` fixture is being evaluated, the Orchestrator SHOULD NOT invoke the Editor. It MUST instead persist a deterministic no-op `editor_summary.json` with empty accepted/modified/declined/resolved/unresolved arrays, `draft_before_hash = draft_after_hash`, and, for applied rounds, `draft_after_content` equal to the unchanged draft. This no-op summary is Orchestrator-owned and has the same acceptance semantics as an Editor-confirmed no-op.

The Orchestrator MUST reject destructive Editor-generated draft replacements before writing `draft_after.md` or mutating `spec.md`. At minimum, when `draft_before.md` is non-empty, the Orchestrator MUST reject:
- empty or whitespace-only `draft_after_content`
- known Editor blocked/error placeholder text in `draft_after_content`
- near-empty replacements that are destructively smaller than a large non-empty draft
- forbidden text-corruption characters in `draft_after_content`

Forbidden text-corruption characters are Unicode category `Cc` control characters except LF, CR, and TAB, plus `U+FFFD` replacement characters. Such rejection is an artifact validation failure, not an accepted draft mutation. The invalid attempt MUST be persisted and the previous valid draft MUST remain authoritative.

Apply-back preflight MUST run the same text hygiene validation against the final draft before writing to the source spec. A final draft that violates text hygiene MUST NOT be applied, even if the run predates the validation guard or was manually edited after convergence.

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
    decision_status: editor_applied_decision | operator_review_recommended | operator_required_decision | record_only_hardening | deferred_scope_decision
    requires_human_decision: boolean
    orchestrator_action: record_only | present_at_end | pause_for_input
```

Decision points capture consequential choices made or proposed during revision. They are separate from issue identity and from conflict escalation. A decision point does not imply the Editor made an invalid change; it means the change carries product, policy, scope, authority, or operational consequences that should be visible outside the model turn.

`decision_status` disambiguates what kind of decision point was captured:

- `editor_applied_decision`: the Editor already encoded the choice in the draft and no special operator review was requested.
- `operator_review_recommended`: the Editor already encoded the choice in the draft, but the choice should be visible to the operator before apply-back, Phase 2, or implementation.
- `operator_required_decision`: the Orchestrator paused in intervention mode and external input is required before continuing.
- `record_only_hardening`: the change is routine precision hardening captured for audit, not a live owner decision.
- `deferred_scope_decision`: the decision concerns behavior that should remain deferred unless an operator explicitly pulls it into scope.

In `end_of_cycle` mode, `operator_review_recommended` is advisory and MUST NOT halt the run by itself. In `intervention` mode, `operator_required_decision` maps to `orchestrator_action = pause_for_input` and MAY halt through the existing `PAUSED_DECISION` path.

If an Editor change promotes a scope-contract `could`, `deferred`, or `out_of_scope` surface into normative `MUST` behavior, the Orchestrator SHOULD classify the resulting decision point as `deferred_scope_decision`. In `end_of_cycle` mode this is surfaced for operator review and MUST NOT halt the run by itself. In `intervention` mode it MAY pause only through the existing `PAUSED_DECISION` path.

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
- The Orchestrator MUST aggregate per-round decision points into `/rounds/decision_register.json` and `/rounds/decision_register.md` at terminal state.
- Terminal decision register and summary artifacts MUST be produced even when no decision points were captured, with `decision_points = []` and `unresolved_human_decision_count = 0`.
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

`operator_decision_checkpoint.json` is a per-round, nonblocking artifact derived from decision points and unresolved blocker/major Reviewer findings. It frames likely owner-level policy, scope, authority, validation, failure-handling, or reporting choices as operator-readable multiple-choice checkpoint cards.

This artifact is advisory in version `0.57`. It MUST NOT pause execution, alter scheduler state, mark a profile clean, resolve feedback, mutate the draft, or satisfy convergence by itself. Its runtime effect is explicitly `none`.

`operator_decision_checkpoint.json` MUST contain:

```yaml
generated_at: string
round_number: integer
profile: string
draft_hash: string
mode: artifact_only
runtime_effect: none
default_action: continue_without_operator_input
checkpoint_count: integer
checkpoints:
  - checkpoint_id: string
    round_number: integer
    profile: string
    source_type: decision_point | unresolved_issue
    source_ids: [string]
    severity: blocker | major | minor | nit | null
    trigger_reason: operator_policy_choice | deferable_scope_boundary | authority_boundary | validation_policy | failure_or_reporting_policy
    affected_sections: [string]
    question: string
    options:
      - option_id: string
        label: string
        description: string
        recommended: boolean
    recommended_option_id: string | null
    evidence_lines: [string]
    risk_if_skipped: string
    status: candidate
    runtime_effect: none
```

The Orchestrator SHOULD write `operator_decision_checkpoint.json` for every live round, even when `checkpoints = []`, so downstream operators can distinguish "no checkpoint candidates" from "artifact not produced."

Checkpoint candidates derived from unresolved Reviewer findings SHOULD be limited to in-scope blocker/major issues whose text indicates an operator-level choice, including scope boundaries, authority precedence, validation policy, failure/reporting behavior, fallback behavior, or product policy. Routine local precision gaps SHOULD remain Editor-fixable and SHOULD NOT create checkpoint cards.

Checkpoint candidates derived from `decision_points.json` SHOULD include decision points with `decision_status` in:

- `operator_review_recommended`
- `operator_required_decision`
- `deferred_scope_decision`

The `default_action = continue_without_operator_input` means the current runtime continues exactly as it would have without the checkpoint artifact. Future interactive or auto-guided modes MAY consume the same checkpoint shape and persist separate response artifacts, but version `0.57` MUST NOT imply such response handling exists.

At terminal state, the Orchestrator MUST aggregate per-round checkpoint artifacts into:

- `/rounds/operator_decision_checkpoint_summary.json`
- `/rounds/operator_decision_checkpoint_summary.md`

The checkpoint summary is a deterministic operator review aid. It MUST NOT pause execution, alter scheduler state, resolve feedback, mutate the draft, or satisfy convergence.

`operator_decision_checkpoint_summary.json` MUST contain:

```yaml
generated_at: string
terminal_state: string
source_glob: rounds/round-*/operator_decision_checkpoint.json
summary_method: mechanical_checkpoint_v1
checkpoint_count: integer
rounds_with_checkpoints: [integer]
trigger_reason_counts: object
source_type_counts: object
clusters:
  by_trigger_reason: [checkpoint_cluster]
  by_section: [checkpoint_cluster]
  by_source_type: [checkpoint_cluster]
recommended_operator_review: [checkpoint_summary_card]
```

Checkpoint summary clusters MUST be mechanical:

- `by_trigger_reason` groups by `trigger_reason`.
- `by_section` groups by the first affected section on each checkpoint card.
- `by_source_type` groups by `decision_point` vs `unresolved_issue`.
- `recommended_operator_review` MUST contain at most five checkpoint cards sorted by deterministic priority: authority boundary, deferred scope boundary, failure/reporting policy, validation policy, then general operator policy choice; ties sort by severity, round number, then checkpoint ID.

The human-readable Markdown summary MUST expose the same counts, recommended review cards, and clusters without adding semantic interpretation beyond persisted checkpoint fields.

`decision_register.json` MUST contain:

```yaml
generated_at: string
mode: end_of_cycle | intervention
terminal_state: string
decision_points: [decision_point]
decision_status_counts: object
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

## ARTIFACT VALIDATION POLICY

The Orchestrator MUST validate every client-produced artifact before using it for scheduling, mutation, acceptance, convergence, oscillation detection, or conflict escalation.

Validation order:
1. parse the client response as a single JSON object
2. validate contextual fields such as `round_number`, `profile`, `draft_hash`, `draft_before_hash`, and `draft_after_hash`
3. reject reviewer self-reported process/context-loading failure artifacts before semantic scheduling
4. validate the object against the phase-appropriate artifact schema
5. apply Orchestrator-owned canonicalization steps such as Phase 2 `oscillation_key` fingerprint and opposition-key computation
6. validate the canonicalized artifact against the persisted artifact schema

Reviewer feedback that declares the review could not be performed because context files were not read, context was unavailable, or another client-process prerequisite failed MUST be treated as an invalid reviewer artifact, not semantic feedback. The Orchestrator MUST retry it under the artifact validation policy. If the retry also returns process/context-loading failure feedback, the run MUST halt with `HALTED_ARTIFACT_INVALID`. Such process failure artifacts MUST NOT dirty profile cleanliness, create issue/conflict/oscillation identity, consume a successful review result, or be sent to the Editor as feedback to apply or decline.

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

If a client invocation times out before returning an artifact, the Orchestrator MUST NOT retry the same prompt automatically. It MUST halt with `HALTED_CLIENT_TIMEOUT`, produce `/rounds/artifact_validation_error.json`, set `failure_type = client_timeout`, and produce the phase-appropriate companion failure report. Timeout halts are distinct from artifact validation failures because no candidate artifact was available to validate.

When `HALTED_ARTIFACT_INVALID` occurs, `last_valid_draft_path` MUST point to the most recent draft snapshot the Orchestrator can safely treat as validated. If reviewer artifact validation fails before any validated review exists for the round, this MUST be the current round `draft_before.md`. If editor artifact validation fails after a validated reviewer artifact, this MAY be the current round `draft_after.md` only when that file is an Orchestrator-owned snapshot and not an unvalidated client artifact.

When `HALTED_CLIENT_TIMEOUT` occurs, `last_valid_draft_path` follows the same rule as artifact validation failures. A timed-out Reviewer points to `draft_before.md`. A timed-out Editor after validated reviewer feedback MAY point to the Orchestrator-owned `draft_after.md` snapshot for the round.

For Phase 2 reviewer feedback, an invalid or missing reviewer-proposed `oscillation_key`, an invalid enum value, or a `section_id` that does not resolve to exactly one canonical section ID is an artifact validation failure under this policy.

---

## RESUME POLICY

The Orchestrator MAY resume only explicitly resumable terminal states. In this version, the supported resume paths are:

1. Phase 1 Editor timeout recovery.
2. Phase 1 budget-extension continuation after explicit operator request.

### Editor Timeout Resume

The supported Editor-timeout resume path is:

- `terminal_state = HALTED_CLIENT_TIMEOUT`
- `failure_type = client_timeout`
- `phase = phase_1`
- `client_role = editor`
- the halted round already has validated `reviewer_feedback.json`

Resume MUST be hash-guarded. Before invoking the Editor, the Orchestrator MUST verify that the current `spec.md` hash equals the halted artifact's `last_valid_draft_hash`. If the hash differs, resume MUST refuse unless a future explicit override is defined.

Resume MUST NOT rerun prior rounds. For the supported Editor-timeout path, resume MUST:
- read `rounds/run_state.json`
- read `rounds/artifact_validation_error.json`
- read the halted round's `draft_before.md` and `reviewer_feedback.json`
- validate the persisted Reviewer feedback against the halted round context
- reconstruct Phase 1 scheduler state from completed prior rounds
- verify the scheduler's next profile matches the halted profile
- invoke only the Editor for the halted round
- start resumed attempt numbering after the last recorded attempt number
- preserve prior invalid attempt artifacts, timeout telemetry, and prompt snapshots
- clear the top-level timeout terminal report only after the resumed round completes successfully
- update `run_state.json`, `spec.md`, `draft_after.md`, `editor_summary.json`, `unresolved_issues.json`, `decision_points.json`, and `spec.history.md`

Resume does not imply hidden client session reuse. It uses persisted file artifacts as the replay source of truth.

Resume MUST inherit persisted effective run configuration from the halted run's `run_state.json` when present. At minimum, resume MUST inherit `review_profile_budgets`, `convergence_profile_budgets`, `decision_points`, and `timeouts` from `effective_run_config`. For compatibility with older runs, resume MAY fall back to top-level `run_state.json` `review_profile_budgets`, `convergence_profile_budgets`, and `timeouts` when `effective_run_config` is absent. Explicit CLI overrides supplied to the resume command take precedence over inherited run-state values.

By default, resume recovers only the halted round and then stops. If invoked with `--continue`, the Orchestrator MAY continue Phase 1 after the recovered round succeeds. `resume --continue` MUST:
- use the reconstructed scheduler state from completed prior rounds plus the recovered round result
- start subsequent rounds at the next round number
- preserve all prior round artifacts and timeout diagnostics
- continue applying the normal Phase 1 scheduling algorithm, profile budgets, validation rules, timeout rules, oscillation checks, and halting conditions
- halt normally on `PHASE_1_STABLE`, `TARGET_NOT_REACHED`, `HALTED_CLIENT_TIMEOUT`, `HALTED_ARTIFACT_INVALID`, `HALTED_CONFLICT`, or `HALTED_OSCILLATION`
- update `run_state.json` and `spec.history.md` after each continued round

`resume --continue` MUST NOT retroactively alter prior rounds, rerun the halted round's Reviewer, or restart the profile sequence.

`resume --dry-run` MUST validate resume eligibility without invoking any client. It MUST perform the same terminal-state, failure-type, role, phase, hash, scheduler, and persisted Reviewer-feedback checks as live resume. It MUST report at minimum:
- whether the run is resumable
- halted `round_number`
- halted `profile`
- `phase`
- `client_role`
- `failure_type`
- current and expected draft hashes
- next Editor attempt number
- whether `--continue` was requested
- next continued round number when computable

Read-only run status MUST expose whether a run is resumable and, when eligible, the exact `resume` and `resume --continue` commands an operator can run. Status guidance MUST be advisory; live resume remains responsible for enforcing the hash guard and artifact validation before invoking the Editor.

If a resumed Editor call times out again, the Orchestrator MUST halt again with `HALTED_CLIENT_TIMEOUT` and preserve both the original and resumed attempt artifacts.

### Budget-Extension Resume

The Orchestrator MAY resume a Phase 1 run after budget exhaustion only when the operator explicitly requests a review-budget extension.

Supported budget-extension terminal states are:
- `TARGET_NOT_REACHED`
- `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`

In this version, budget-extension resume is supported for Phase 1 `review.mode: horizontal` and `review.mode: vertical`.

Budget-extension resume MUST be hash-guarded. Before appending rounds, the Orchestrator MUST verify that the current `spec.md` hash equals `run_state.json.current_draft_hash`. If the hash differs, budget-extension resume MUST refuse unless a future explicit override is defined.

Budget-extension resume MUST NOT overwrite, delete, renumber, or rerun prior rounds. It MUST:
- read `rounds/run_state.json`
- inherit persisted `effective_run_config` before applying CLI overrides
- validate the run is a Phase 1 budget-exhausted terminal state
- reconstruct Phase 1 scheduler state from completed prior round artifacts
- increase the effective Phase 1 profile budgets by the operator-requested extension amount
- start at `current_round + 1`
- append new `round-N/` artifacts after the existing highest round number
- continue applying normal Phase 1 scheduling, validation, timeout, decision, oscillation, and halting rules
- update `run_state.json`, `spec.md`, and `spec.history.md` after each appended round

For `review.mode: vertical`, budget-extension resume MUST replay the prior vertical event stream to reconstruct:
- per-profile `rounds_used`
- per-profile clean/exhausted/residual status
- `last_accepted_draft_hash`
- `seen_draft_hashes`
- latest unresolved issues from the most recent synthetic `profile: vertical` editor round

After reconstruction, vertical budget-extension resume MUST increase each effective Phase 1 profile review budget by the operator-requested extension amount, then append additional vertical cycles. Each appended vertical cycle MUST:
- run each non-exhausted profile review pass against the same draft at the start of that cycle
- merge profile feedback into a synthetic `profile: vertical` reviewer artifact when any profile reports feedback
- run one consolidated Editor revision for the merged feedback
- stop with `PHASE_1_STABLE` only when all required profiles are clean on the current draft and the current draft is accepted

If reconstructed `rounds_used` for any profile is greater than the configured effective budget, including because a prior verification-only closeout consumed profile review rounds, the new budget for that profile MUST be `rounds_used + added_rounds_per_profile`, not the lower configured value plus the extension. Budget extension MUST always create additional available review capacity for every Phase 1 profile.

Budget-extension resume MUST record an auditable event in `run_state.json.budget_extensions[]` before invoking any live client for the appended continuation. Each event MUST include:
- stable `event_id`
- `generated_at`
- `phase`
- `previous_terminal_state`
- `previous_current_round`
- `previous_review_profile_budgets`
- `new_review_profile_budgets`
- `added_rounds_per_profile`
- `reason`

The default reason for an operator-requested budget extension is `operator_requested_resume_budget_extension`.

Budget-extension events MUST be preserved across subsequent `run_state.json` rewrites during the resumed continuation.

Budget-extension resume is a continuation of the same run, not a new run. Prior terminal reports remain historical artifacts unless a later run-state field supersedes their operational interpretation. Operators SHOULD treat `run_state.json` as the current status source of truth and preserved terminal reports as historical checkpoints.

Read-only status MUST prefer superseding `run_state.json` terminal state over stale historical terminal reports. If `run_state.json.terminal_state = PHASE_1_STABLE` and `ready_for_phase_2 = true`, status MUST report `current_draft_status = phase_1_stable` even if a prior `technical_failure_report.json` remains in `/rounds/`.

---

## FOCUSED PHASE 1 PROFILE RUNS

The Orchestrator MAY provide a focused Phase 1 profile run mode for targeted verification after an earlier run leaves one profile uncertain or an operator applies a bounded manual/synthesis fix.

A focused Phase 1 profile run:
- executes exactly one configured Phase 1 review profile, such as `structural_integrity`, `determinism`, or `operability`
- uses the same guarded Reviewer, Editor, artifact validation, context-file, prompt snapshot, telemetry, decision-point, text-hygiene, and contract-surface rules as `live-phase1`
- MUST write ordinary round artifacts under `/rounds/round-N/`
- MUST write `/rounds/run_state.json`
- MUST write decision register and decision summary artifacts when decision capture is enabled
- MUST preserve `spec.md`, `spec.history.md`, and per-round rollback snapshots like a normal Phase 1 run

Focused profile mode is not Phase 1 convergence. A clean focused profile run proves only that the selected profile is clean for the focused run's current draft. It MUST NOT set `ready_for_phase_2 = true` and MUST NOT claim `PHASE_1_STABLE` unless it actually executes the full configured Phase 1 profile sequence.

When a focused profile run's selected profile reaches reviewer-verified clean status, the terminal state MUST be `FOCUSED_PROFILE_STABLE`. When the selected profile exhausts its focused budget without reviewer-verified clean status, the Orchestrator MUST produce `technical_failure_report.json` with profile status limited to the focused profile and terminal state `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS` or a future focused-profile residual state.

The focused run root SHOULD be isolated from the source run root unless the operator explicitly requests in-place continuation. This preserves comparison between the original run artifacts and the targeted recheck.

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
- profile_status
- last_reviewer_findings: object | null
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

`profile_status` MUST explain verification state at halt time. It MUST include:
- `profiles`: ordered profile-step records with `profile`, `rounds_used`, `round_budget`, `clean`, `exhausted`, `residual_status`, and `active`
- `unverified_profiles`: profile names whose latest relevant Reviewer pass has not verified the current draft clean
- `exhausted_profiles`: profile names whose profile-step budget was consumed without a clean verification result
- `profiles_remaining`: profile names with unconsumed profile-step budget
- `total_round_budget`: sum of profile-step `round_budget` values for the phase

`residual_status` MUST be null when the profile has no residual condition. In Phase 1 soft budget mode, it MUST be `exhausted_with_residuals` or `halted_oscillation` when the Orchestrator advances past a non-clean profile for diagnostic sweep coverage.

`last_reviewer_findings` MUST summarize the last accepted Reviewer batch when available. It MUST include `round_number`, `profile`, `blocker_count`, `major_count`, and `feedback_ids` for in-scope blocker/major feedback. This field exists so a failure report can distinguish unresolved Editor issues from missing Reviewer verification.

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
- current_draft_status:
  - not_accepted
  - accepted_unverified_profiles
  - phase_1_stable
- ready_for_phase_2
- last_draft_hash
- profile_status
- last_reviewer_findings: object | null
- exit_reason
- recommendation:
  - continue_phase_1
  - narrow_scope
  - manual_review_required

ACTION:

Orchestrator MUST halt and require external input.

The system does not proceed automatically to Phase 2.

In Phase 1, empty `unresolved_blockers` and `unresolved_major_issues` do not imply Phase 1 stability. They mean the latest Editor summary did not leave blocker/major issues unresolved. Phase 1 stability still requires valid clean Reviewer status for every required Phase 1 profile and an accepted current draft. If profile-budget exhaustion occurs before that verification, `technical_failure_report.json` MUST make the missing verification visible through `profile_status` and `last_reviewer_findings`.

`last_accepted_draft_hash` records the latest draft hash that satisfied accepted-draft criteria. It MUST NOT be interpreted by itself as Phase 1 stability. `current_draft_status` MUST provide the operator-facing interpretation:

- `not_accepted`: `last_accepted_draft_hash` is null or does not match `last_draft_hash`.
- `accepted_unverified_profiles`: `last_accepted_draft_hash` matches `last_draft_hash`, but one or more required Phase 1 profiles remains unverified, exhausted with residual status, or unvisited.
- `phase_1_stable`: `last_accepted_draft_hash` matches `last_draft_hash` and every required Phase 1 profile has a clean Reviewer verification for the current draft.

`ready_for_phase_2` MUST be true only when `current_draft_status = phase_1_stable`.

If `terminal_state = PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`, the report means Phase 1 soft budget mode completed the configured profile sweep but did not produce a Phase 1 stable draft. The report MUST be interpreted as a manual-review checkpoint, not a successful stabilization result.

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
ANY STATE -> HALTED_CLIENT_TIMEOUT (on client invocation timeout)
ANY STATE -> PAUSED_DECISION (on decision intervention required)
TECHNICAL_REVIEW -> PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS (when soft Phase 1 profile sweep completes with residual blocker/major or oscillation status)
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
- scope contract path/hash/status when present
- reference context labels/roles/paths/hashes when present
- draft_hash
- semantic_change_hash when a draft mutation is requested
- context_files manifest when file-backed context is used

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
- scope contract path/hash/status when present
- reference context labels/roles/paths/hashes when present
- context_files manifest when file-backed context is used
- validation errors that caused the attempt, or an empty list for the first attempt

Live client prompts MAY use file-backed context for large authoritative inputs. File-backed context MUST be written under `rounds/round-N/context/`, and prompt text MUST reference those files by path instead of duplicating the full content. This mechanism is intended for bulky round inputs such as the draft, rubric, convergence declaration, reviewer feedback, scope contract, and reference context files.

When an approved scope contract is present, it MUST be supplied as file-backed context to Reviewer and Editor prompts. Prompt snapshots MUST include the scope contract context-file hash and a top-level `scope_contract_hash` or equivalent scope-contract summary.

When reference context files are configured and available, the Orchestrator MUST copy each available file into `rounds/round-N/context/`, label it as `reference:<label>` in the context manifest, and include its configured role in prompt text and prompt snapshots. A reference context file's copied round context content and SHA-256 hash are the replay authority for that attempt.

When file-backed context is used:
- the Orchestrator MUST persist each context file before the client attempt begins
- the prompt MUST list only the context files the client is allowed to read
- the prompt MUST explicitly allow the client to read the listed context files
- each prompt snapshot MUST include a `context_files` manifest with `label`, `path`, and exact SHA256 of the context file content
- context file paths SHOULD be workspace-relative when possible
- context files referenced by an attempt snapshot MUST NOT be mutated after that snapshot is persisted
- retry attempts MAY reuse the same context files when the authoritative inputs have not changed
- deterministic replay uses the prompt text plus the referenced context file contents and hashes

Clients MUST treat file-backed context as equivalent to inline prompt context. They MAY use read-only client-native file access or read-only shell commands solely to read the listed context file paths. They MUST NOT inspect unrelated repository files, use web search, or call tools for anything except reading listed context files.

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

Not implemented in 0.37.

---

## DESIGN PRINCIPLE

Every primitive MUST be computable.

No implied behavior.
No undefined aggregation.
No hidden state transitions.

Goal:
Deterministic convergence with no ambiguity in execution.
