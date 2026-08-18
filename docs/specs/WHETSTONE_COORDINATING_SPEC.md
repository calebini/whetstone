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

Version `0.69` specifies the lightweight `audit-change` workflow for reviewer-only cross-spec change audits.

Version `0.70` begins bounded ratification of the candidate-safe editing design by registering its normative owner and activation gate. This routing amendment does not activate candidate editing or change current runtime behavior by itself.

---

## Spec Family Map

This coordinating spec is the front door for the Whetstone spec family. It orients readers to the functional areas and routes them to the leaf specs that own normative detail. When a leaf spec and this overview disagree, the leaf spec is authoritative for its owned surface unless the decomposition manifest says otherwise.

### Rubrics, Profiles, And Feedback

See [Rubrics Profiles And Feedback Spec](RUBRICS_PROFILES_AND_FEEDBACK_SPEC.md).

Owns rubric profiles, workflow presets, review profiles, profile sets, severity normalization, baseline review invariants, and Phase 2 feedback classification. Use this leaf when changing how Whetstone judges quality, assigns review pressure, classifies issues, or constrains reviewer feedback shape.

### Scope Intake, Decisions, And Decomposition

See [Scope Intake And Decisions Spec](SCOPE_INTAKE_AND_DECISIONS_SPEC.md).

Owns scope contracts, first-contact intake, lightweight change audits, decision summaries, decision intervention/checkpoint artifacts, expanding contract surface detection, and the spec decomposition workflow. The decomposition material lives here under `SPEC DECOMPOSITION WORKFLOW`.

### Scheduler, State, Resume, And Budgets

See [Scheduler State And Resume Spec](SCHEDULER_STATE_AND_RESUME_SPEC.md).

Owns halting precedence, halt artifacts, accepted-draft semantics, version lifecycle, round scheduling, profile budgets, focused profile runs, Phase 1 failure handling, resume behavior, and the state machine. For the pending bounded ratification amendment, it is the designated normative owner for full strop/apply-back eligibility and the external source-write lifecycle; the candidate-editing leaf will supply the additional verified-candidate eligibility guard, and the Operator Quickstart will remain the operational procedure. This designation does not ratify detailed vNext strop/apply-back policy by itself. Until that scheduler amendment is completed, current operative apply-back behavior remains governed by the scheduler leaf's existing lineage and hash guards together with the Operator Quickstart procedure. Use the scheduler leaf for changes that affect when Whetstone advances, stops, resumes, declares Phase 1 stable, or may apply a run result back to its source.

### Artifacts, Validation, Hashing, And Telemetry

See [Artifacts Validation And Telemetry Spec](ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md).

Owns minimum artifact schemas, artifact validation policy, client telemetry, content normalization, hashing, and control-character hygiene. Use this leaf when changing persisted artifact contracts, validation retry behavior, or deterministic identity inputs.

### Candidate Editing, Verification, And Promotion

See [Candidate Editing And Promotion Spec](CANDIDATE_EDITING_AND_PROMOTION_SPEC.md).

Owns the vNext trust boundary around Editor proposals, stable section-addressed patching, candidate assembly and disposition, deterministic preservation validation, independent semantic verification, current-verified-draft lineage, serialized promotion, candidate-safe retry and resume, and the verified-candidate apply-back eligibility guard.

Editor output is untrusted client output. It is a change proposal, never draft authority or promotion proof. Only an Orchestrator-validated candidate that completes the leaf's atomic current-verified-pointer protocol may become the current verified draft.

This leaf is registered for ratification but remains non-operative. Registration in the family map does not supersede the current scheduler, artifact, scope/decision, Phase 2, or apply-back contracts and is not evidence that candidate-safe editing is implemented.

### Candidate-Safety Activation Gate

For a particular new job, candidate-safe automatic promotion becomes operative only when all of the following are true:

- the scheduler, artifact-validation, scope/decision, Phase 2, and apply-back authority surfaces named by the candidate-editing leaf's ratification delta map have been amended consistently;
- the coordinating and amended leaf specs advertise the same supported candidate contract-suite version;
- the version-pinned public contracts and cross-implementation conformance fixtures exist;
- every P0 release-acceptance scenario in the candidate-editing leaf passes; and
- `verified_promotion` is explicitly selected for a new job whose immutable descriptor binds that supported contract suite.

Until every condition holds, `verified_promotion` MUST be unavailable, a configuration value or artifact that claims otherwise is invalid, current runtime behavior remains governed by the existing operative spec family, and reviewer-only operation remains the safe default for valuable or unfamiliar specifications.

### Identity, Oscillation, And Conflicts

See [Identity Oscillation And Conflicts Spec](IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md).

Owns issue identity, conflict identity, oscillation detection, conflict modeling, Editor decline taxonomy, and conflict escalation. Use this leaf for recurring-feedback behavior, fingerprint semantics, opposition keys, and escalation rules.

### Phase 2, Convergence, And Declaration

See [Phase2 Convergence And Declaration Spec](PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md).

Owns Phase 2 failure handling, target matrix precedence, convergence declaration content, declaration acceptance, and reproducibility requirements. Use this leaf for changes to final convergence, strictness interpretation, declaration evidence, or convergence failure reports.

---

## CORE ROLES

- Editor:
  Produces proposed specification changes. All Editor output is untrusted client output. In current operative workflows, the Orchestrator may accept Editor draft output only under the existing scheduler and artifact contracts. After candidate-safe editing is activated, the Editor produces section-addressed patch proposals and MUST NOT write `spec.md`, decide candidate disposition, perform semantic verification, or create promotion artifacts.

- Reviewer:
  Produces structured, classified findings under a defined review profile. Reviewer findings are review evidence, not mutation commands.

- Deterministic Validator (candidate-safe mode, after activation):
  Orchestrator-owned code that validates patch contracts, assembles candidates, and checks identities, hashes, assertions, and preservation units. It has no authority to waive a deterministic failure.

- Semantic Verifier (candidate-safe mode, after activation):
  Independently evaluates the assembled candidate against the admitted findings, preservation obligations, and authority constraints. Its output is untrusted client evidence until validated, and it has no mutation or promotion authority.

- Orchestrator:
  Owns state, round scheduling, normalization, oscillation detection, conflict escalation, artifacts, and stopping conditions. After candidate-safe editing is activated, it is also the sole authority for proposal admission and validation, candidate assembly and disposition, and atomic current-verified-pointer promotion.

---

## PRIMARY INPUTS

- spec.md
- scope_contract.json (required for `workflow: mvp`, optional for other workflows unless configured)
- reference context files (optional; e.g., HLDs, architecture notes, authority maps)
- convergence_rubric.md
- orchestrator_config.yaml

Candidate-safe vNext reserves these additional authoritative inputs, but they are non-operative until the activation gate passes:

- `job_descriptor.json` (immutable, including editing mode and contract-suite bindings)
- `authority_map.json`
- `protected_invariants.json`
- hash-bound scope contracts, operator decisions, and source-spec expectations referenced by the job descriptor

---

## PRIMARY OUTPUTS

- spec.md (current operative workflows: accepted round draft; activated candidate-safe mode: byte-identical convenience mirror of the target selected by `/rounds/current_verified.json`, never independent authority or direct Editor output)
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
  - context_pressure_report.json (advisory actual prompt-context payload summary)
  - context_pressure_report.md (human-readable actual prompt-context payload summary)
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
- /rounds/context_pressure_report.json (advisory context payload observability)
- /rounds/context_pressure_report.md (human-readable context payload summary)
- /change_audit/audit_manifest.json (if `audit-change` is run)
- /change_audit/audit_brief.md (self-contained review brief for `audit-change`)
- /change_audit/change_audit_feedback.json (canonical reviewer feedback for `audit-change`)
- /change_audit/change_audit_report.json (machine-readable audit verdict)
- /change_audit/change_audit_report.md (human-readable audit verdict)
- /rounds/contract_surface_report.json (if expanding contract surface is detected)
- /rounds/contract_surface_report.md (human-readable synthesis recommendation, if detected)
- /rounds/rubric_manifest.json (required before Phase 2 review begins)
- /decomposition/decomposition_plan.json (if spec decomposition planning is run)
- /decomposition/decomposition_plan.md (human-readable decomposition plan)
- /decomposition/decomposition_manifest.json (if extraction is run)
- /decomposition/coverage_matrix.md (if extraction or audit is run)
- /decomposition/unmapped_requirements.md (if required source content is not assigned)
- /decomposition/duplicated_authority_report.md (if duplicated authority is detected)

After the relevant vNext surfaces are ratified and implemented, `proposal_only` and `verified_promotion` jobs produce the common non-promoting artifact family defined by the candidate-editing leaf, including:

- `/rounds/candidate_index/creation-{candidate_creation_ordinal}.json`
- `/rounds/round-N/mutation_plan.json`
- `/rounds/round-N/proposals/attempts/proposal-attempt-M.json`
- `/rounds/round-N/proposals/{proposal_id}/proposed_patch.json` and content-addressed payloads
- `/rounds/round-N/candidates/{candidate_id}/candidate_unverified.md`
- candidate section-identity maps, preservation reports, semantic-verification attempts, candidate-verification decisions and pointers, and non-promotion disposition events beneath the registered candidate directory

Every vNext job initializes `/rounds/current_verified.json` and its byte-identical ordinal-0 `/rounds/verified_history/current-verified-0.json` seed snapshot. A `proposal_only` job MUST NOT advance either artifact and MUST NOT create a promotion intent or a `promotion_committed` disposition event.

Only a `verified_promotion` job performing an authorized promotion attempt may additionally create a candidate-scoped promotion intent, a `promotion_committed` disposition event, a next-ordinal verified-history snapshot, atomically advance `/rounds/current_verified.json`, or materialize the promoted candidate as `draft_after.md`.

These paths describe the ratified target contract; their presence alone does not activate candidate-safe editing or grant promotion authority.

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

Candidate-safe vNext reserves these top-level configuration fields:

```yaml
editing_mode: reviewer_only       # reviewer_only | proposal_only | verified_promotion
contract_suite_version: ""        # non-empty supported version for every vNext job
```

These fields are non-operative until the relevant family surfaces are ratified and the implementation advertises support for them; the current runtime is not required to accept them. Configuration presence, artifact presence, or a caller claim MUST NOT activate `proposal_only` or `verified_promotion`. Once a vNext mode is supported, every new vNext job MUST copy the resolved values into its immutable `job_descriptor.json`; changing either value requires a new descriptor and job identity. `verified_promotion` MUST fail preflight unless the selected non-empty contract-suite version is supported and has passed the complete candidate-safety activation gate.

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

Model output never advances specification authority by assertion. After candidate-safe editing is activated, Editor output is an untrusted proposal, and only a fully validated candidate committed through atomic replacement of the current verified pointer may advance the authoritative run-local draft.

Promotion fails closed: a missing, invalid, stale, or mismatched gate preserves the prior current verified pointer. Partial ratification, configuration presence, or candidate artifact creation does not change current runtime behavior.

Goal:
Deterministic convergence with no ambiguity in execution.
