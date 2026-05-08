# Whetstone Implementation Plan

This plan is the traceable build checklist for Whetstone `0.21`.

## Build Strategy

Build deterministic behavior first, then introduce live clients behind narrow gates.

Fixture mode remains the regression harness. Live Codex/Claude behavior must not weaken fixture determinism, schema validation, artifact integrity, or halt-state reproducibility.

## Current State

Completed:

- [x] Bare repository scaffold
- [x] `0.21` spec persisted as `spec.md`
- [x] Contract schemas for primary artifacts
- [x] Dependency-free schema validator
- [x] Draft normalization and draft hashing
- [x] Section-level semantic change hashing
- [x] Polarity-neutral mechanical change key primitive
- [x] Rubric content hashing primitive
- [x] Issue and conflict identity helpers
- [x] Phase 2 oscillation identity helpers
- [x] Canonical Markdown section indexer
- [x] Phase 2 oscillation key canonicalizer
- [x] Severity normalization
- [x] Accepted-draft and target-matrix evaluation
- [x] Guarded artifact store
- [x] Fixture one-round runner
- [x] Multi-round fixture engine
- [x] Scheduler primitives
- [x] Terminal report writing
- [x] Convergence declaration rendering
- [x] Prompt rendering
- [x] Phase 2 reviewer prompt classification table
- [x] Process client boundary
- [x] Codex reviewer adapter
- [x] Claude Code reviewer adapter
- [x] Codex editor adapter
- [x] Claude Code editor adapter
- [x] Live-client reviewer input canonicalization for severity aliases
- [x] Codex-compatible editor structured-output schema
- [x] `codex-review` CLI probe
- [x] `reviewer-smoke` CLI probe
- [x] `editor-smoke` CLI probe
- [x] Config-driven live client factory
- [x] Guarded `live-round` CLI command
- [x] Live single-round packet writer
- [x] `codex-review --phase phase_2` schema selection
- [x] Phase 2 reviewer output canonicalized before persistence
- [x] Live Codex reviewer smoke test against `spec.md`
- [x] Live Claude Code reviewer smoke test against a tiny Phase 2 draft
- [x] Minimal non-resumable live Phase 1 runner
- [x] Minimal non-resumable live Phase 2 runner
- [x] Decision point register and intervention pause support
- [x] Artifact validation retry/halt audit trail
- [x] Phase 2 version promotion
- [x] Accepted-round version stamping
- [x] Separate Orchestrator-owned convergence declaration artifact
- [x] Spec-defined decision-summary artifact contract
- [x] Spec-defined client telemetry artifact contract
- [x] Live Codex Phase 2 smoke against a toy spec
- [x] Live Codex Phase 2 smoke against Foreman HAG Adapter spec copy
- [x] Clean-convergence fixture script

Verification baseline:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q src tests
```

Acceptance:

- [x] Full test suite passes
- [x] Compile check passes
- [x] No stale legacy role terminology remains

Current limitation:

- Live Phase 1 and Phase 2 runners are intentionally non-resumable.
- Live spec sharpening currently operates on an isolated run root. Applying accepted changes back to a source repository remains a planned workflow.

## Live Test Gates

### Gate 1: Codex Reviewer Smoke Test

Goal: prove Codex can emit schema-valid `reviewer_feedback.json`.

Tasks:

- [x] Add Codex reviewer adapter using `codex exec`
- [x] Add `codex-review` CLI command
- [x] Validate Codex output against `reviewer_feedback.schema.json`
- [x] Run one live Codex reviewer smoke test against `spec.md`
- [x] Persist output under `rounds/`

Acceptance:

- [x] Command exits successfully
- [x] Output validates against `reviewer_feedback.schema.json`
- [x] No spec mutation occurs
- [x] Fixture-mode tests still pass afterward

### Gate 2: Editor Client Smoke Test

Goal: prove an editor client can emit schema-valid `editor_summary.json`.

Tasks:

- [x] Add Claude Code adapter
- [x] Add optional Codex editor adapter command path if useful
- [x] Add `editor-review` or `editor-smoke` CLI command
- [x] Validate editor output against `editor_summary.schema.json`
- [x] Use tiny fixture reviewer feedback, not a full live round

Acceptance:

- [x] Editor output validates
- [x] No spec mutation occurs
- [x] Decline taxonomy validation works
- [x] Fixture-mode tests still pass afterward

### Gate 2a: Claude Reviewer Plumbing Smoke Test

Goal: prove Claude Code can be used as a reviewer client without weakening local validation.

Tasks:

- [x] Add Claude Code reviewer adapter
- [x] Add shared `reviewer-smoke` CLI command
- [x] Unwrap Claude Code `structured_output` responses
- [x] Unwrap Claude Code JSON emitted inside the CLI `result` field
- [x] Canonicalize reviewer severity aliases before schema validation
- [x] Run one live Claude Code Phase 2 reviewer smoke against a tiny draft
- [x] Persist output under `rounds/live-claude-reviewer-smoke/`

Acceptance:

- [x] Command exits successfully
- [x] Output validates against persisted `phase2_reviewer_feedback`
- [x] Output includes Orchestrator-computed `oscillation_key.fingerprint`
- [x] Output includes Orchestrator-computed `oscillation_key.opposition_key`
- [x] No spec mutation occurs
- [x] Fixture-mode tests still pass afterward

### Gate 3: Live Single-Round Test

Goal: prove reviewer -> editor -> round packet works once.

Tasks:

- [x] Add config-driven client factory
- [x] Assign reviewer/editor roles from `clients.reviewer` and `clients.editor`
- [x] Add `live-round` CLI command
- [x] Persist complete prompt snapshots before client invocation
- [x] Call live reviewer client
- [x] Validate reviewer artifact
- [x] Call live editor client
- [x] Validate editor artifact
- [x] Apply or capture `draft_after.md` only after validation
- [x] Emit full `rounds/round-N/` packet

Acceptance:

- [x] Role assignment works from config
- [x] One live round emits all required artifacts
- [x] Malformed reviewer output is rejected before editor invocation
- [x] Malformed editor output is rejected before spec mutation
- [x] Fixture-mode tests still pass afterward
- [x] Real Codex reviewer -> Claude editor tiny-spec E2E round completes without mutation

### Gate 3.5: Minimal Live Phase 1 Runner

Goal: make Phase 1 real without requiring full Phase 2 cross-round memory.

This is an intentional intermediate gate between the single-round live engine and the full live multi-round orchestrator. It exercises the Phase 1 stabilization loop while deferring Phase 2 feedback-level oscillation memory, conflict escalation history, declaration workflow, and resumable long-running orchestration.

Scope:

- Phase 1 only
- non-resumable for the first implementation, but every round must persist enough state to explain progress and support later resume work
- basic draft-hash cycle detection only
- no Phase 2 feedback-level oscillation detection
- no conflict escalation tracker beyond existing artifact/report primitives

Tasks:

- [x] Add `rounds/run_state.json` for live Phase 1 runs
- [x] Track current round, phase, active profile, current draft hash, last accepted draft hash, seen draft hashes, and terminal state
- [x] Add `live-phase1` or equivalent CLI command
- [x] Use the existing Phase 1 scheduler profile order
- [x] Repeat blocker profiles according to scheduler repeat limits
- [x] Apply validated `draft_after.md` to `spec.md` only after the round packet validates
- [x] Append compact per-round entries to `spec.history.md`
- [x] Stop successfully when all Phase 1 profiles are clean and the draft is accepted
- [x] Stop with `TARGET_NOT_REACHED` and `technical_failure_report.json` when Phase 1 max rounds is reached
- [x] Stop with `HALTED_ARTIFACT_INVALID` when live artifact validation retry is exhausted
- [x] Stop with `HALTED_OSCILLATION` on repeated draft hash cycle
- [x] Explicitly document the first runner as non-resumable

Acceptance:

- [x] Multi-round Phase 1 run can advance across `structural_integrity`, `determinism`, and `operability`
- [x] Blocker profile repeats before advancing
- [x] Accepted Phase 1 draft stops the run as ready for Phase 2
- [x] Max-round failure emits `technical_failure_report.json`
- [x] Draft-hash cycle emits `oscillation_report.json`
- [x] `run_state.json` updates after every completed round
- [x] Invalid reviewer/editor artifacts cannot advance the loop or mutate `spec.md`
- [x] Fixture-mode tests still pass afterward
- [x] Real Claude reviewer -> Codex editor toy-spec `live-phase1` smoke reaches `PHASE_1_STABLE`

### Gate 3.6: Decision Point Register

Goal: add a release valve for consequential editor choices before relying on live Phase 1 output for source-spec promotion.

This gate captures decisions deterministically from round artifacts and draft diffs. It is fixture/local-first and does not require live Claude availability.

Scope:

- Phase 1 decision capture
- deterministic diff-triggered decision points
- end-of-cycle register aggregation
- intervention-mode pause semantics
- no model-authored decision classification required for the first implementation

Tasks:

- [x] Add `decision_points.json`, `decision_register.json`, and `decision_intervention_request.json` schemas
- [x] Add `PAUSED_DECISION` to terminal-state validation
- [x] Add decision-point config defaults and YAML loading
- [x] Detect normative keyword strength changes
- [x] Detect new enum/status/error-code-like values
- [x] Detect authority-boundary and scope-change language
- [x] Persist per-round `decision_points.json`
- [x] Aggregate terminal `decision_register.json` and `decision_register.md`
- [x] Pause with `PAUSED_DECISION` in intervention mode when thresholds match
- [x] Add a Foreman-artifact decision-only regression using the known HAG diff shape

Acceptance:

- [x] Known HAG-style diff captures decision points for stricter display context, first-write-wins policy, and new adapter error codes
- [x] End-of-cycle mode reaches normal terminal state and emits a register
- [x] Intervention mode halts before the next round with `decision_intervention_request.json`
- [x] Decision point artifacts validate against schemas
- [x] Fixture/local tests pass without live client calls

### Gate 3.7: Artifact Failure Audit Hardening

Goal: close the artifact-failure gaps found by the Codex 5.5 reviewer smoke before broader live runs rely on those failure artifacts.

Tasks:

- [x] Add `technical_failure_report.json` to the primary output inventory
- [x] Record `last_valid_draft_path` alongside `last_valid_draft_hash` in artifact-validation halts
- [x] Persist per-attempt prompt snapshots under `prompt_snapshots/`
- [x] Include validation errors in retry prompt snapshots
- [x] Route artifact-validation companion reports to the same last-valid draft path used by the halt artifact

Acceptance:

- [x] Reviewer validation exhaustion points to current round `draft_before.md`
- [x] Editor validation exhaustion points to current round `draft_after.md` when the snapshot is Orchestrator-owned
- [x] Retry prompt snapshots do not overwrite first-attempt prompt snapshots
- [x] Artifact-validation schema and live-run tests cover the new fields

### Gate 3.8: Phase 2 Version Promotion

Goal: make Phase 2 entry visibly distinguishable by promoting the spec from fractional stabilization versions to a whole major convergence version.

Tasks:

- [x] Add a version parser/promotion helper for root spec headings
- [x] Promote `0.x` accepted Phase 1 drafts to `1.0` before the first Phase 2 review
- [x] Preserve already-whole major versions without repeated promotion
- [x] Persist the promotion to `spec.md`, `spec.history.md`, and the first Phase 2 `draft_before.md`
- [x] Reject direct Phase 2 promotion when the Phase 1 accepted-draft gate has not been satisfied

Acceptance:

- [x] `0.17` promotes to `1.0` at `TECHNICAL_STABLE -> CONVERGENCE_REVIEW`
- [x] `1.7` promotes to `2.0`
- [x] `2.0` remains `2.0`
- [x] Tests cover promotion timing, history entry, and no-promotion failure cases

### Gate 4: Live Multi-Round Test

Goal: run full live multi-round orchestration after cross-round memory is implemented.

Gate 4 builds on Gate 3.5. It should cover both Phase 1 and Phase 2 behavior, including cross-round conflict/oscillation memory and convergence/declaration handling.

Prerequisites:

- [x] Gate 3.5 minimal live Phase 1 runner complete
- [x] Gate 3.6 decision point register complete
- [x] Gate 3.7 artifact failure audit hardening complete
- [x] Gate 3.8 Phase 2 version promotion complete
- [x] Cross-round oscillation detector complete
- [x] Conflict escalation tracker complete
- [x] Halt precedence automation complete
- [x] Artifact validation retry/halt policy complete
- [x] Status/resume support available or explicit non-resumable limitation documented

Acceptance:

- [x] Full multi-round run reaches `CONVERGED` or a correct terminal state
- [x] Halt artifacts match terminal state
- [x] Cross-round memory explains any oscillation/conflict halt
- [x] Fixture-mode tests still pass afterward

### Gate 4.1: Non-Resumable Live Phase 2 Runner

Goal: make Phase 2 executable from a valid Phase 1 handoff without waiting for resumable orchestration.

Tasks:

- [x] Require `PHASE_1_STABLE` and `ready_for_phase_2=true` before live Phase 2 starts
- [x] Promote accepted Phase 1 fractional versions to the Phase 2 whole version before the first Phase 2 round
- [x] Run the configured Phase 2 profile sequence with live reviewer/editor clients
- [x] Persist per-round `rubric_gaps.json`
- [x] Generate a candidate convergence declaration before final acceptance
- [x] Require a later `convergence_strict_check` pass before emitting accepted declaration
- [x] Carry Phase 2 draft and feedback oscillation memory through the live loop
- [x] Emit Phase 2 convergence failure reports for max-round and halt outcomes
- [x] Expose `live-phase2` CLI command

Acceptance:

- [x] Clean live Phase 2 fixture run promotes `0.x` to `1.0` and reaches `CONVERGED`
- [x] Missing Phase 1 handoff is rejected
- [x] Phase 2 max rounds persists `convergence_failure_report.json`
- [x] Phase 2 artifact validation failure halts without advancing
- [x] Full unit suite passes

### Gate 4.2: Orchestrator-Owned Version Stamping

Goal: make accepted mutating rounds easier to inspect and roll back by assigning human-readable version labels while keeping hashes authoritative.

Tasks:

- [x] Add round-stamping helpers for Phase 1 and post-entry Phase 2 versions
- [x] Keep Phase 2 entry promotion separate from accepted-round stamping
- [x] Stamp only accepted mutating applied live rounds
- [x] Compute `draft_after_hash` after version stamping
- [x] Persist stamped content to `draft_after.md` and `spec.md`
- [x] Record version stamp before/after versions and hashes in `spec.history.md`
- [x] Skip stamping safely for unversioned root headings

Acceptance:

- [x] Phase 1 accepted mutating round stamps `0.17 -> 0.18`
- [x] Phase 2 accepted mutating round stamps `1.0 -> 1.1`
- [x] Persisted `editor_summary.json` hash matches stamped draft content
- [x] Full unit suite passes

### Gate 4.3: File-Backed Live Prompt Context

Goal: reduce live prompt size and timeout pressure by persisting large authoritative inputs as round-local context files and referencing them by path plus hash.

Tasks:

- [x] Persist Reviewer context under `rounds/round-N/context/` before the attempt begins
- [x] Persist Editor context under `rounds/round-N/context/` after Reviewer feedback is validated
- [x] Render Reviewer prompts with draft/rubric/declaration paths instead of embedded bulky content
- [x] Render Editor prompts with draft and reviewer-feedback paths instead of embedded bulky content
- [x] Include `context_files` manifests in round-level and attempt-level prompt snapshots
- [x] Use exact SHA256 content hashes for context file manifests
- [x] Keep resume Editor attempts on the same file-backed prompt contract
- [x] Update live CLI fixtures and prompt tests for file-backed context
- [x] Document the file-backed context primitive in `spec.md`

Acceptance:

- [x] Focused live/prompt/CLI/resume tests pass with file-backed context
- [x] Prompt snapshots identify every context file by label, path, and SHA256
- [x] Editor and Reviewer prompts instruct clients to read only listed context files
- [x] Full unit suite passes

### Gate 4.4: File-Backed Context Hardening

Goal: make file-backed live runs safe under real clients by allowing listed-file reads while preventing failed file access from wiping run drafts.

Tasks:

- [x] Update Reviewer and Editor prompts to explicitly allow read-only access to listed context files
- [x] Keep file access constrained to listed context paths only
- [x] Reject empty Editor-generated `draft_after_content` when the prior draft is non-empty
- [x] Reject known Editor blocked/error placeholder text as a draft replacement
- [x] Reject near-empty replacements for large non-empty drafts
- [x] Preserve the prior valid draft when destructive draft validation fails
- [x] Persist invalid destructive attempts as artifact validation failures
- [x] Write terminal decision register and summary artifacts even when no decision points were captured
- [x] Expose resolved effective profile budgets in `run_state.json`
- [x] Preserve explicitly configured profile budget overrides separately from resolved defaults
- [x] Update `spec.md` to define the hardened contract

Acceptance:

- [x] A client cannot replace a non-empty draft with empty content through `editor_summary.json`
- [x] A blocked/error placeholder response cannot become `spec.md`
- [x] `run_state.json` reports default profile budgets rather than `{}` when no overrides are configured
- [x] Focused live/prompt/status/resume tests pass

### Gate 4.5: Resume Effective Run Config Inheritance

Goal: keep resumed runs faithful to the effective scheduling, decision, and timeout settings that were active when the run halted.

Tasks:

- [x] Persist `effective_run_config` in `rounds/run_state.json`
- [x] Include effective profile budgets, decision-point configuration, and timeouts in `effective_run_config`
- [x] Read persisted `effective_run_config` from `rounds/run_state.json` during `resume`
- [x] Fall back to older top-level run-state budget/timeout fields when `effective_run_config` is absent
- [x] Apply inherited run-state config before resume execution
- [x] Preserve explicit resume CLI timeout overrides as highest precedence
- [x] Add regression coverage for effective run config inheritance
- [x] Update `spec.md` with the resume config inheritance rule

Acceptance:

- [x] Plain `resume` no longer falls back to default `editor_seconds` when the halted run used a different timeout
- [x] Plain `resume` reconstructs Phase 1 with the halted run's persisted effective profile budgets
- [x] Plain `resume --continue` uses the halted run's persisted decision-point mode and thresholds
- [x] Focused resume/CLI/status tests pass

### Gate 4.6: Expanding Contract Surface Detection

Goal: detect when a profile is repeatedly discovering or creating a contract family instead of merely closing isolated findings, and give the Editor a bounded synthesis path.

Tasks:

- [x] Add `EXPANDING_CONTRACT_SURFACE` detector for repeated serious contract-bearing findings
- [x] Persist `rounds/contract_surface_report.json`
- [x] Persist human-readable `rounds/contract_surface_report.md`
- [x] Keep detection non-terminal and advisory
- [x] Include synthesis scope with affected sections and contract families
- [x] Include matching contract surface report in Editor context files
- [x] Add timeout-aware bounded synthesis guidance to Editor prompts
- [x] Update `spec.md` to `0.33`
- [x] Add regression coverage for detection and prompt guidance

Acceptance:

- [x] Repeated serious schema/failure/mapping findings produce a contract surface report
- [x] Editor prompts reference the report and still require complete `draft_after_content`
- [x] Focused live/prompt tests pass

### Gate 4.7: Soft Phase 1 Profile Budget Sweep

Goal: let operators run a full Phase 1 diagnostic sweep across all configured review profiles without pretending residual blockers, majors, or oscillation are convergence.

Tasks:

- [x] Add `review.budget_exhaustion_policy` with `hard | soft`
- [x] Persist `review_budget_exhaustion_policy` in `effective_run_config`
- [x] Let soft mode advance from an exhausted Phase 1 profile with residual status
- [x] Let soft mode convert Phase 1 oscillation into profile residual status while preserving `oscillation_report.json`
- [x] Add `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`
- [x] Keep Phase 2 blocked unless Phase 1 reaches `PHASE_1_STABLE`
- [x] Add `residual_status` to profile status schemas and reports
- [x] Update `spec.md` to `0.34`
- [x] Add regression coverage for exhausted-profile and oscillation residual sweeps

Acceptance:

- [x] Hard mode preserves existing strict budget halt behavior
- [x] Soft mode completes all Phase 1 profiles and halts with residual sweep state when stability is not reached
- [x] Residual profile status identifies exhausted and oscillating profiles
- [x] Phase 2 remains unavailable after a residual sweep
- [x] Focused scheduler/live/config/schema tests pass

## Remaining Build Checklist

This checklist now tracks work remaining after Gates 1 through 4.7. Earlier live-client and live-round checklist items have been reconciled with the implemented gates above.

### 1. Schema Completion

Tasks:

- [ ] Add `prompt_snapshot.json` schema
- [ ] Convert `profile_used.yaml` to `profile_used.json` or add explicit YAML contract
- [x] Add `rubric_gaps.json` schema
- [x] Add `config_validation_error.json` schema
- [x] Add `artifact_validation_error.json` schema
- [x] Add `oscillation_key` schema
- [x] Add reviewer-input `oscillation_key` schema
- [x] Require `oscillation_key` in Phase 2 reviewer feedback
- [ ] Add structured convergence declaration schema or frontmatter contract
- [ ] Refine terminal report schemas after live report artifacts exist

Acceptance:

- [x] Phase 1 reviewer feedback may set `oscillation_key = null`
- [x] Phase 2 reviewer feedback without valid `oscillation_key` is rejected
- [x] Persisted Phase 2 feedback includes Orchestrator-computed `fingerprint` and `opposition_key`
- [x] Rubric gap artifacts have a machine-readable schema
- [ ] Prompt snapshot artifacts validate before round packet is accepted
- [x] Existing fixture artifacts are updated and valid

### 2. Phase 2 Prompt Discipline

Tasks:

- [x] Add canonical concern type table to Phase 2 reviewer prompt
- [x] Add canonical section ID list to Phase 2 reviewer prompt
- [x] Add direction enum and symmetric opposition pairs to Phase 2 reviewer prompt
- [x] Add scope enum to Phase 2 reviewer prompt
- [x] Add examples of valid `oscillation_key` classifications
- [x] Instruct reviewer to never invent categories
- [x] Instruct reviewer to choose `section_id` only from the canonical list
- [x] Instruct reviewer not to author deterministic identity fields
- [x] Instruct reviewer that `modify` is only for no-more-specific-direction cases

Acceptance:

- [x] Phase 2 prompt snapshot includes the full classification table
- [x] Tests assert prompt contains concern types, directions, scope values, and examples
- [x] Phase 1 prompts do not require structured oscillation classification
- [x] Tests assert section ID list is exposed in Phase 2 prompts

### 2a. Oscillation Key Canonicalization

Tasks:

- [x] Add Markdown section indexer using heading-path slug IDs
- [x] Add duplicate heading suffix behavior
- [x] Validate Phase 2 `section_id` against the canonical section index
- [x] Compute `oscillation_fingerprint` in the Orchestrator/client boundary
- [x] Compute `oscillation_opposition_key` in the Orchestrator/client boundary
- [x] Persist canonicalized `oscillation_key`
- [x] Reject unknown Phase 2 section IDs

Acceptance:

- [x] Reviewer does not need to compute hashes
- [x] Unknown `section_id` rejects before downstream oscillation detection
- [x] Bad or missing reviewer-authored hash cannot poison oscillation memory

### 3. Cross-Round Oscillation Memory

Tasks:

- [x] Track draft hashes for cycle detection
- [x] Track polarity-neutral `mechanical_change_key` for draft-level mechanical churn
- [x] Track exact semantic change polarity separately from `mechanical_change_key`
- [x] Track Phase 2 `oscillation_fingerprint`
- [x] Track Phase 2 `oscillation_opposition_key`
- [x] Detect feedback flip-flop using opposing directions
- [x] Detect feedback churn after 3 cumulative Phase 2 appearances without intervening resolution
- [x] Detect feedback re-addition
- [x] Attribute suspected feedback IDs where computable

Acceptance:

- [x] Phase 1 cycle can produce `HALTED_OSCILLATION`
- [x] Phase 1 mechanical churn uses matching `mechanical_change_key` plus opposing polarity
- [x] Phase 1 mechanical churn recommends `freeze_prior_decision` and does not halt by itself
- [x] Phase 2 feedback flip-flop produces deterministic recommendation
- [x] Phase 2 feedback churn creates a manual-review conflict report
- [x] Churn escalation halts only if resulting conflict is blocker-level
- [x] Oscillation history starts fresh at Phase 2 boundary

### 4. Conflict Escalation Tracker

Tasks:

- [x] Track `conflict_fingerprint` history across rounds
- [x] Detect same conflict for 2 consecutive rounds
- [x] Detect same conflict 3 times non-consecutively
- [x] Compute conflict severity from participating issues
- [x] Emit `conflict_report.json`
- [x] Halt only on blocker-level conflicts

Acceptance:

- [x] Consecutive conflict threshold is tested
- [x] Non-consecutive conflict threshold is tested
- [x] Non-blocker conflict escalation emits report without halt unless terminal rules require halt
- [x] Blocker-level conflict produces `HALTED_CONFLICT`

### 5. Halt Precedence Automation

Tasks:

- [x] Apply clean convergence first
- [x] Apply blocker-level conflict halt second
- [x] Apply oscillation stop third
- [x] Apply exhausted artifact validation failure fourth
- [x] Apply decision intervention fifth
- [x] Apply max-rounds sixth
- [x] Emit required halt artifact matrix

Acceptance:

- [x] Conflicting halt conditions resolve by ordered precedence
- [x] Phase 1 max rounds emits `technical_failure_report.json`
- [x] Phase 2 max rounds emits `convergence_failure_report.json`
- [x] Exhausted artifact validation emits `artifact_validation_error.json`
- [x] Phase 2 conflict/oscillation halt also emits convergence failure report

### 5a. Artifact Validation Policy

Tasks:

- [x] Validate client output before canonical artifact persistence
- [x] Preserve invalid raw output under diagnostic filenames
- [x] Retry each invalid client artifact at most once
- [x] Keep retry attempts in the same round/profile/phase context
- [x] Persist attempt-level prompt snapshots, including validation errors on retry attempts
- [x] Record the last valid draft path used for failure reports
- [x] Emit `HALTED_ARTIFACT_INVALID` after retry exhaustion
- [x] Ensure invalid reviewer/editor artifacts cannot advance scheduling or mutate `spec.md`

Acceptance:

- [x] Reviewer validation failure retries once, then emits `artifact_validation_error.json`
- [x] Editor validation failure retries once, then emits `artifact_validation_error.json`
- [x] Phase 2 invalid `oscillation_key` follows the same validation policy
- [x] Retry exhaustion produces the correct Phase 1 or Phase 2 companion failure report

### 6. Phase 2 Declaration Workflow

Tasks:

- [x] Generate `convergence_declaration.md`
- [x] Validate declaration content against current draft hash, rubric hash, target matrix, and unresolved issue set
- [x] Distinguish `CONVERGENCE_REVISION` from `DECLARATION_REVISION`
- [x] Re-review declaration with `convergence_strict_check`
- [x] Reject conditional declarations as terminal status

Acceptance:

- [x] `CONVERGED` requires accepted declaration
- [x] Declaration-only changes route through `DECLARATION_REVISION`
- [x] Spec changes route through `CONVERGENCE_REVISION`
- [x] `conditional` is never emitted as terminal declaration status

### 6a. Rubric Gap Evaluation

Tasks:

- [x] Define `rubric_content_hash` normalization
- [x] Define `rubric_gaps.json` schema
- [x] Emit `rubric_gaps.json` during Phase 2 rounds
- [x] Derive `unresolved_rubric_gaps` from unresolved blocking rubric gaps
- [x] Feed derived rubric gaps into target-matrix evaluation
- [x] Include rubric gaps in convergence failure reports

Acceptance:

- [x] `final/strict` convergence cannot pass with unresolved blocking rubric gaps
- [x] Permissive targets can accept documented rubric gaps when policy allows
- [ ] Rubric gap ordering is deterministic

### 7. Role Assignment And Client Factory

Tasks:

- [x] Read `clients.reviewer` from config
- [x] Read `clients.editor` from config
- [x] Instantiate Codex reviewer adapter
- [x] Instantiate Codex editor adapter if configured
- [x] Instantiate Claude Code reviewer adapter
- [x] Instantiate Claude Code editor adapter
- [x] Keep fixture clients available through direct test injection and fixture-mode runners
- [x] Surface unsupported client names as configuration errors

Acceptance:

- [x] Reviewer and editor can be assigned independently
- [x] Codex can be reviewer while Claude Code is editor
- [x] Fixture clients can be used for either role in tests
- [x] Config model preserves concrete command/version/model values

### 8. Live Round Engine

Tasks:

- [x] Render reviewer prompt
- [x] Persist reviewer prompt snapshot
- [x] Invoke reviewer client
- [x] Validate reviewer artifact
- [x] Render editor prompt
- [x] Persist editor prompt snapshot
- [x] Invoke editor client
- [x] Validate editor artifact
- [x] Capture or apply draft mutation
- [x] Emit full round packet

Acceptance:

- [x] Injected fixture reviewer/editor clients can complete a guarded round in tests
- [x] One live round can complete with live reviewer + live editor
- [x] Real Codex reviewer -> Claude editor tiny-spec E2E round completes
- [x] Real Claude reviewer -> Codex editor tiny-spec E2E round completes
- [x] Invalid client output cannot mutate `spec.md`

### 9. Live CLI Surface

Tasks:

- [ ] Add `run`
- [x] Add `live-round`
- [x] Add `live-phase1`
- [x] Add `live-phase2`
- [x] Add `status`
- [ ] Add `resume`
- [x] Keep `fixture-script`
- [x] Keep `codex-review`

Acceptance:

- [x] `status` reports latest terminal state or latest round packet
- [ ] `resume` refuses unsafe resume when required artifacts are missing
- [ ] `run` uses configured roles and sequences Phase 1 -> Phase 2
- [ ] CLI errors are actionable

### 10. Golden Fixtures

Tasks:

- [x] Clean convergence fixture
- [x] Blocker conflict escalation fixture
- [x] Oscillation cycle fixture
- [x] Mechanical churn freeze fixture
- [x] Feedback flip-flop fixture
- [x] Feedback churn manual-review fixture
- [x] Re-addition stop fixture
- [x] Phase 1 max rounds fixture
- [x] Phase 2 declaration failure fixture
- [x] Phase 2 convergence failure fixture
- [x] Permissive target with documented Phase 2 major issue fixture
- [x] Malformed reviewer output rejection fixture
- [x] Malformed editor output rejection fixture
- [ ] Add curated golden fixture files for each terminal state beyond unit-level fixture scripts

Acceptance:

- [x] Every implemented terminal state has at least one unit or fixture-script regression
- [x] Every fixture regression validates emitted artifacts
- [x] Fixtures remain stable across test runs
- [ ] Curated golden fixture directories can be inspected without reading unit-test setup code

### 11. Apply-Back Workflow

Goal: safely promote an isolated Whetstone run result back to the source spec repository after human review.

Tasks:

- [x] Add an apply-back command or module that accepts a source spec path and completed run root
- [x] Persist the original source hash before apply-back
- [x] Compute a human-readable diff from source spec to final Whetstone draft
- [x] Produce an apply-back review artifact before mutating the source file
- [x] Require explicit approval or an explicit non-interactive flag before writing to the source file
- [x] Exclude Whetstone-only artifacts such as `convergence_declaration.md` from source-spec mutation unless requested
- [x] Preserve source repo formatting and path ownership
- [x] Persist an apply-back report with before/after hashes, selected final draft, and approval mode

Acceptance:

- [x] Dry-run apply-back produces a diff and report without mutating the source file
- [x] Approved apply-back updates only the requested source spec
- [x] Hash mismatch refuses apply-back unless an explicit override is provided
- [x] Declaration artifacts do not leak into source specs by default
- [x] Foreman HAG Adapter isolated-run result can be reviewed as an apply-back candidate

### 12. Status, Resume, And Recovery

Goal: make long live runs operable after interruption without treating partial artifacts as accepted packets.

Tasks:

- [x] Add `status` command
- [x] Add isolated run-root support for `status`
- [x] Add human-readable `status --format text`
- [ ] Add `resume` command
- [ ] Define complete-round packet detection
- [x] Detect and report partial round directories
- [ ] Refuse unsafe resume when required artifacts are missing or invalid
- [ ] Resume from the latest valid run state
- [ ] Preserve non-resumable runners as simpler smoke-test paths or replace them with the resumable runner

Acceptance:

- [x] `status` summarizes terminal state, phase, round, active profile, latest accepted hash, and next action
- [ ] `resume` can continue after a completed round boundary
- [ ] `resume` refuses after a partial client-attempt artifact without explicit recovery action
- [ ] Recovery behavior is covered by fixture tests

### 12a. Decision Summary

Goal: make large decision registers reviewable without asking operators to read every raw decision point.

Tasks:

- [x] Add `decision_summary.json` schema
- [x] Add deterministic section-family clustering from `decision_register.json`
- [x] Add deterministic round/profile clustering
- [x] Add deterministic trigger-type clustering
- [x] Add `decision-summary` CLI command
- [x] Emit `decision_summary.md` with mechanical clusters and representative questions
- [x] Auto-emit decision summaries when decision registers are written
- [x] Add mechanical hotspot fields for largest and human-decision-heavy clusters
- [x] Keep interpretive summary disabled by default
- [ ] Label any future AI interpretation as non-authoritative and cite decision IDs

Acceptance:

- [x] Existing Approval Persistence run decision register collapses into deterministic section, round/profile, and trigger clusters
- [x] Mechanical summary is stable across repeated runs against the same register
- [x] Summary generation does not mutate spec, history, declaration, or round artifacts
- [x] Human-readable summary makes the Approval Persistence register reviewable at cluster level

### 12b. Client Telemetry

Goal: capture per-attempt runtime, token, cost, and client-envelope metadata for live reviewer/editor invocations.

Tasks:

- [x] Add `client_telemetry.json` schema
- [x] Add a telemetry result object to process client execution
- [x] Persist `client_telemetry/{client_role}-{artifact_name}-attempt-{attempt_number}.json` for every live invocation attempt
- [x] Preserve Claude Code JSON envelopes or lossless redacted copies before unwrapping `structured_output` / `result`
- [x] Extract Claude usage fields: input, output, cache creation/read tokens, cost, duration, API duration, turns, session, stop/terminal reason
- [x] Extract Codex usage when available from stdout text
- [ ] Extract Codex usage from structured envelope if a future CLI envelope exposes it
- [x] Preserve raw stdout/stderr references when needed to explain parsed telemetry
- [x] Keep telemetry failures non-fatal
- [x] Surface telemetry persistence failures as run warnings
- [x] Add status/report aggregation for per-round total duration, tokens, and cost

Acceptance:

- [x] Claude editor/reviewer attempts emit telemetry with `usage`, `total_cost_usd`, `duration_ms`, and `session_id` when the CLI envelope provides them
- [x] Codex reviewer attempts emit telemetry with parsed token totals when available
- [x] Successful attempts and invalid attempts both produce telemetry
- [x] Missing usage data still produces process metadata telemetry
- [x] Telemetry artifacts do not duplicate prompt text
- [x] Telemetry is not used for convergence, validation, mutation, or replay authority

### 12c. Canonical Rubrics And Workflows

Goal: make the convergence quality bar explicit and auditable by separating canonical rubric identity from operational workflow behavior.

Tasks:

- [x] Add packaged built-in rubric profiles: `governance-v6`, `standard-v1`, `mvp-v1`, and `exploratory-v1`
- [x] Add config fields for `workflow`, `convergence.rubric_profile`, `convergence.rubric_source`, and `convergence.rubric_label`
- [x] Resolve workflow defaults without hiding the final `rubric_profile`, target, or round budget
- [x] Persist `/rounds/rubric_manifest.json` before Phase 2 begins
- [x] Block Phase 2 entry when rubric identity is invalid, unlabeled for custom runs, or built-in hash-mismatched
- [ ] Block Phase 2 entry when rubric identity is implicit rather than default-resolved
- [x] Include rubric manifest identity in Phase 2 prompt snapshots, declarations, failure reports, and apply-back reports
- [ ] Include rubric manifest identity in decision summaries after Gate 12a is implemented
- [x] Add CLI flags for `--workflow` and `--rubric`
- [x] Print custom-rubric warnings in CLI run output
- [x] Treat any future `--mvp` shortcut as a workflow alias, not as a rubric-definition shortcut
- [x] Add tests proving a soft/custom rubric cannot be used silently during a final/strict run

Acceptance:

- [x] Phase 2 refuses to start without a valid built-in rubric profile or custom rubric label/path/hash
- [x] Built-in rubric hashes are stable and checked before prompt construction
- [ ] Custom rubric runs are visibly labeled in the manifest and run-start output
- [x] The Approval Persistence soft-rubric scenario would have produced an explicit manifest warning
- [x] `--workflow mvp --rubric mvp-v1` and `--workflow governance --rubric governance-v6` produce distinct manifests
- [x] Reproducibility artifacts include the full rubric identity tuple for implemented Phase 2 prompt snapshots, declarations, failure reports, and apply-back reports

### 13. Cleanup And Operator Summaries

Goal: reduce artifact noise while preserving auditability.

Tasks:

- [ ] Add `--cleanup` or archive mode for completed runs
- [ ] Preserve essential artifacts: final spec, spec history, terminal report, decision register, declaration, and apply-back report when present
- [ ] Archive or summarize per-round raw artifacts instead of deleting them silently
- [ ] Generate an operator-facing run summary
- [ ] Generate a decision-point TL;DR suitable for approval review

Acceptance:

- [ ] Cleanup mode never destroys the only copy of a rollback target
- [ ] Cleanup output states exactly what was retained, archived, or removed
- [ ] Operator summary can be read without opening every round directory

### 14. Two-Stage Review Pipeline

Goal: separate content critique from strict Whetstone classification so clients can be assigned to the stage that matches their strengths.

Source spec:

- [x] Draft `docs/TWO_STAGE_REVIEW_PIPELINE_SPEC.md`

Tasks:

- [ ] Review and sharpen the two-stage subsystem spec
- [ ] Add `critic_findings.json` schema
- [ ] Add `canonicalizer_summary.json` schema
- [ ] Add `review_pipeline.mode = direct | critic_then_canonicalizer` config parsing
- [ ] Add Critic and Canonicalizer client factories
- [ ] Persist Critic and Canonicalizer prompt snapshots and telemetry
- [ ] Implement Canonicalizer retry without rerunning a successful Critic by default
- [ ] Preserve lineage from Critic finding to canonical feedback item
- [ ] Keep `reviewer_feedback.json` as the only artifact consumed by existing convergence logic
- [ ] Add live smoke with Claude Code as Critic and Codex `gpt-5.5` as Canonicalizer

Acceptance:

- [ ] Direct reviewer mode remains backward compatible
- [ ] Two-stage mode can complete one fixture round
- [ ] Invalid Critic output halts before Canonicalizer invocation
- [ ] Invalid Canonicalizer output can retry without rerunning Critic
- [ ] Persisted `reviewer_feedback.json` is schema-valid and Orchestrator-canonicalized
- [ ] Operator can trace Critic finding -> canonical feedback item -> editor handling

### 15. Explanatory Failure Reports and Profile Budgets

Goal: make `TARGET_NOT_REACHED` reports explain whether the draft still has unresolved issues or merely lacks reviewer-verified clean profile status, and move run budget control from phase-wide ceilings to profile-level constraints.

Tasks:

- [x] Add profile-level `round_budget` scheduling primitive
- [x] Parse `review.profile_budgets` and `convergence.profile_budgets`
- [x] Make live Phase 1 consume profile-step budgets instead of universal phase max rounds
- [x] Make live Phase 2 consume profile-step budgets instead of universal phase max rounds
- [x] Add `profile_status` and `last_reviewer_findings` to failure reports
- [x] Update technical and convergence failure schemas
- [x] Update `spec.md` to define the new scheduling and report contract
- [x] Add soft profile-budget sweep option with residual status reporting
- [ ] Add operator-facing status/help copy for profile budgets

Acceptance:

- [x] A run can halt with no unresolved Editor issues while still reporting unverified/exhausted profiles
- [x] Failure reports distinguish Editor resolution from Reviewer verification
- [x] Profile budgets are visible in `run_state.json`
- [x] Default profile budgets preserve the prior default scheduler shape
- [x] Soft budget mode can complete a Phase 1 diagnostic sweep without allowing Phase 2
- [ ] Live replay against a medium Foreman spec shows less artificial convergence behavior

### 16. Client Timeout Semantics And Role-Specific Timeouts

Goal: make client invocation timeouts an explicit terminal condition and allow Reviewer and Editor calls to use different timeout windows.

Tasks:

- [x] Add `HALTED_CLIENT_TIMEOUT` terminal state
- [x] Add `failure_type = client_timeout` to the artifact failure diagnostic
- [x] Make timeout companion reports use `HALTED_CLIENT_TIMEOUT`
- [x] Parse `timeouts.reviewer_seconds` and `timeouts.editor_seconds`
- [x] Use role-specific timeouts when constructing live Reviewer and Editor clients
- [x] Add CLI overrides for reviewer/editor timeout seconds
- [x] Persist timeout configuration in live `run_state.json`
- [x] Update `spec.md` to define timeout semantics

Acceptance:

- [x] Timeout halts no longer report as generic `HALTED_ARTIFACT_INVALID`
- [x] Timeout attempts are not retried automatically
- [x] Schema validation failures still report as `HALTED_ARTIFACT_INVALID`
- [x] Reviewer and Editor calls can have different configured timeout windows

### 17. Narrow Resume From Editor Timeout

Goal: recover expensive live runs that halt after validated Reviewer feedback but before the Editor returns a valid artifact.

Tasks:

- [x] Add `whetstone resume`
- [x] Support `HALTED_CLIENT_TIMEOUT` with `phase_1` and `client_role = editor`
- [x] Hash-guard resume against the halted draft hash
- [x] Reuse persisted `draft_before.md` and `reviewer_feedback.json`
- [x] Validate persisted Reviewer feedback before invoking the Editor
- [x] Reconstruct Phase 1 scheduler state from prior completed rounds
- [x] Resume Editor attempts at the next attempt number
- [x] Preserve original timeout artifacts and per-attempt diagnostics
- [x] Clear top-level timeout reports only after successful resume
- [x] Update `run_state.json` and `spec.history.md` after resume
- [x] Add `resume --continue` for continuing Phase 1 after the recovered round
- [x] Continue from reconstructed scheduler state rather than restarting the profile sequence
- [x] Persist continued-round history entries and state updates
- [x] Add `resume --dry-run` planning with the same eligibility checks as live resume
- [x] Make `status` expose exact resume and resume-continue commands for eligible timeout halts
- [x] Add CLI-shaped timeout/resume-continue smoke coverage using fake clients

Acceptance:

- [x] Resume does not rerun prior rounds
- [x] Resume does not rerun the halted round's Reviewer
- [x] Resume refuses when current `spec.md` hash differs from the halted hash
- [x] Successful resume writes `editor_summary.json`, `draft_after.md`, `unresolved_issues.json`, and decision artifacts
- [x] Successful resume leaves the prior `editor_invalid_attempt_1.json` diagnostic in place
- [x] `resume --continue` can complete the remaining Phase 1 profiles after recovering the failed round
- [x] `resume --dry-run` validates the resume plan without invoking an Editor
- [x] `status --format text` gives an operator copyable resume commands when a run is eligible
- [x] A CLI smoke covers timeout -> dry-run -> resume-continue -> `PHASE_1_STABLE`

## Identity-System Notes

Whetstone uses three identity surfaces:

- `feedback_id`: per-round feedback item identity
- `issue_id` / `issue_fingerprint`: stricter issue identity, potentially prose-sensitive
- `oscillation_fingerprint` / `oscillation_opposition_key`: looser Phase 2 concern identity

Implementation rules:

- [x] Conflict escalation uses conflict fingerprints and may underfire when issue prose changes
- [x] Phase 2 oscillation detection uses oscillation keys and should fire earlier for recurring churn
- [ ] Operator-facing reports explain which identity system triggered the result

## Risk Register

Known live-build risk areas:

- [ ] CLI output discipline: clients may emit malformed JSON or schema-near misses
- [x] Phase 2 hash poisoning: mitigated by Orchestrator-computed oscillation identity fields
- [x] Section anchor drift: mitigated by canonical section IDs and Phase 2 section validation
- [ ] Editor mutation safety: editor output can be valid while still producing undesirable draft changes
- [ ] Prompt snapshot completeness: replay depends on prompt, config, client, model, and rubric hashes
- [ ] Resume safety: partial artifacts must not be treated as accepted round packets
- [ ] Live client version capture: configured and observed client versions may diverge
- [ ] Artifact migration: schema changes may strand older round packets unless versioned explicitly

## Success Criteria

First successful deterministic build:

- [x] Validate core artifact contracts
- [x] Run deterministic fixture-mode rounds
- [x] Reproduce stable hashes
- [x] Halt with correct terminal state in fixture mode
- [x] Emit required reports in fixture mode
- [x] Reject malformed reviewer/editor output before mutation

First successful live build:

- [x] Assign reviewer and editor roles from config
- [x] Run Codex as reviewer
- [x] Run Claude Code or another configured client as editor
- [x] Persist complete prompt snapshots
- [x] Complete at least one live round without accepting malformed artifacts
- [x] Preserve fixture-mode regression behavior
