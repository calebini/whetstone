# Whetstone Coordinating Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: whetstone_coordinating_spec
target_spec_role: coordinating_spec
-->

## Purpose

Automate iterative technical review between AI clients (e.g., Claude Code, Codex) to drive a spec from v0.1 -> converged (mid/final, permissive/strict), with controlled multi-perspective review per round, deterministic convergence behavior, explicit failure handling, and fully specified primitives.

Reading guide: This spec defines the core convergence subsystems: round scheduling, severity normalization, identity for issues/conflicts/oscillation, rubric gap tracking, convergence declaration, and artifact validation. It also defines operator workflows such as scope intake, decision capture, apply-back, and spec decomposition. The state machine and halting conditions sections describe how the runtime subsystems compose into deterministic execution.

Version `0.68` tightens decomposition extraction readability by restoring parent heading context for intro units and normalizing standalone child headings under generated target titles.

---

## Spec Family Map

This coordinating spec is the front door for the Whetstone spec family. It orients readers to the functional areas and routes them to the leaf specs that own normative detail. When a leaf spec and this overview disagree, the leaf spec is authoritative for its owned surface unless the decomposition manifest says otherwise.

### Rubrics, Profiles, And Feedback

See [Rubrics Profiles And Feedback Spec](RUBRICS_PROFILES_AND_FEEDBACK_SPEC.md).

Owns rubric profiles, workflow presets, review profiles, profile sets, severity normalization, baseline review invariants, and Phase 2 feedback classification. Use this leaf when changing how Whetstone judges quality, assigns review pressure, classifies issues, or constrains reviewer feedback shape.

### Scope Intake, Decisions, And Decomposition

See [Scope Intake And Decisions Spec](SCOPE_INTAKE_AND_DECISIONS_SPEC.md).

Owns scope contracts, first-contact intake, decision summaries, decision intervention/checkpoint artifacts, expanding contract surface detection, and the spec decomposition workflow. The decomposition material lives here under `SPEC DECOMPOSITION WORKFLOW`.

### Scheduler, State, Resume, And Budgets

See [Scheduler State And Resume Spec](SCHEDULER_STATE_AND_RESUME_SPEC.md).

Owns halting precedence, halt artifacts, accepted-draft semantics, version lifecycle, round scheduling, profile budgets, focused profile runs, Phase 1 failure handling, resume behavior, and the state machine. Use this leaf for changes that affect when Whetstone advances, stops, resumes, or declares Phase 1 stable.

### Artifacts, Validation, Hashing, And Telemetry

See [Artifacts Validation And Telemetry Spec](ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md).

Owns minimum artifact schemas, artifact validation policy, client telemetry, content normalization, hashing, and control-character hygiene. Use this leaf when changing persisted artifact contracts, validation retry behavior, or deterministic identity inputs.

### Identity, Oscillation, And Conflicts

See [Identity Oscillation And Conflicts Spec](IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md).

Owns issue identity, conflict identity, oscillation detection, conflict modeling, Editor decline taxonomy, and conflict escalation. Use this leaf for recurring-feedback behavior, fingerprint semantics, opposition keys, and escalation rules.

### Phase 2, Convergence, And Declaration

See [Phase2 Convergence And Declaration Spec](PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md).

Owns Phase 2 failure handling, target matrix precedence, convergence declaration content, declaration acceptance, and reproducibility requirements. Use this leaf for changes to final convergence, strictness interpretation, declaration evidence, or convergence failure reports.

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
