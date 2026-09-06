# Whetstone Implementation Plan

This is Whetstone's traceable implementation plan. The original `0.21` gates and completion records below are historical; they are not a current capability inventory. Current behavior is governed by the [coordinating spec](docs/specs/WHETSTONE_COORDINATING_SPEC.md) and its leaf specs.

Active initiative: [18. Safer Editor Pipeline](#18-safer-editor-pipeline), grounded in candidate-editing design `0.4` and coordinating spec `0.72`. This is the delivery owner for the preservation bridge and later candidate pipeline; the future-improvements list is not a parallel implementation checklist.

## Build Strategy

Build deterministic behavior first, then introduce live clients behind narrow gates.

Fixture mode remains the regression harness. Live Codex/Claude behavior must not weaken fixture determinism, schema validation, artifact integrity, or halt-state reproducibility.

## Historical Build Baseline

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

Limitations at that historical baseline (subsequently superseded by resume and apply-back work):

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
- [x] Report terminal effect, context-injection action, next round, operator-action requirement, and synthesis execution status
- [x] Include matching contract surface report in Editor context files
- [x] Add timeout-aware bounded synthesis guidance to Editor prompts
- [x] Update `spec.md` to `0.33`
- [x] Update `spec.md` to `0.36` with explicit advisory/reporting semantics
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

### Gate 4.8: First-Contact Scope Contracts

Goal: give Whetstone an operator-approved scope brake before review pressure starts, especially for MVP runs.

Tasks:

- [x] Add `scope_contract.json` schema
- [x] Add config support for `scope_contract.path`
- [x] Add manual approved scope contract loading and validation
- [x] Inject approved scope contracts into Reviewer and Editor prompts as file-backed context
- [x] Include scope contract summary/hash in prompt snapshots
- [x] Require approved scope contracts for `workflow: mvp` live preflight
- [x] Add `whetstone intake --template mvp`
- [x] Add `whetstone intake --from-notes`
- [x] Add regression coverage for intake, schema validation, prompt injection, and MVP preflight
- [x] Update `spec.md` to `0.35`

Acceptance:

- [x] MVP live runs halt with `CONFIG_INVALID` when no approved scope contract exists
- [x] Approved scope contracts are visible in round context files and prompt snapshots
- [x] Operators can generate scope notes templates and canonical scope contracts from notes
- [x] Focused CLI/config/contracts/prompt/live tests pass

## Remaining Build Checklist

This checklist now tracks work remaining after Gates 1 through 4.8. Earlier live-client and live-round checklist items have been reconciled with the implemented gates above.

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
- [x] Add `strop` as the preferred operator alias for apply-back
- [x] Persist the original source hash before apply-back
- [x] Reject final drafts with forbidden control/replacement characters before source mutation
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
- [x] Final-draft text hygiene failures refuse apply-back
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
- [x] Persist effective profile-budget maps and effective total round budget in rubric manifests
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

### 18. Safer Editor Pipeline

Status: specification amendment and bounded consistency audit complete; the 18.1 contract/inventory and proposal-capture increments are implemented. The guarded runtime transaction and complete qualification remain open. Runtime baseline is `1054bb0`; the two-stage bridge amendment at `da074f4` updates owning specifications only. Slice 18.1 implementation inspection identified undefined predecessor/successor pairing before code changes. The revised contracts define explicit correspondence, proposal admission, post-output operator evidence, and immutable same-root acceptance admission. The audit below supports proceeding with implementation; it is neither runtime qualification nor convergence. No unchecked item is a runtime/release claim. Record test names and commit/artifact evidence when each implementation check lands.

#### Authority And Runtime Map

| Authority | Delivery responsibility |
|---|---|
| [Candidate Editing And Promotion](docs/specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md) | Bridge, preservation dispositions, vNext modes, identities, patch protocol, verification, registration, promotion, recovery, P0 qualification |
| [Artifacts Validation And Telemetry](docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md) | Bridge report, full-draft attempts, validation, hashing, persisted evidence and client contracts |
| [Coordinating](docs/specs/WHETSTONE_COORDINATING_SPEC.md) | Non-operative registration, family authority, activation and supported contract-suite gates |
| [Scheduler State And Resume](docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md) | Draft acceptance, state transitions, retries, budgets, resume, and designated apply-back policy owner |
| [Scope Intake And Decisions](docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md) | Finding admission, authority/scope decisions, operator response bindings |
| [Phase 2](docs/specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md) | Profile verification, declaration bindings and convergence consumption |
| [Operator Quickstart](docs/OPERATOR_QUICKSTART.md) | Supported commands, guarded-run setup, inspection, resume and strop procedure |

The current acceptance choke points are `LiveRoundRunner.run_round` and `resume_editor_round` in [live.py](src/whetstone/live.py). Both validate Editor JSON, compute acceptance, normalize/stamp versions, persist round output, and write `spec.md`. `_validate_editor_summary` and `_reject_destructive_draft_after` check corruption, placeholders and size/line collapse; they do not implement a preservation inventory or allowed-surface gate. Crucially, proposed bytes can be written when `apply` is true without `accepted` being true. Bridge rejection must therefore stop the write path itself, not only change an acceptance boolean.

[sections.py](src/whetstone/sections.py) provides canonical heading-path IDs but no preservation-unit identity and currently recognizes heading-like lines inside fences. [decomposition.py](src/whetstone/decomposition.py) has a separate source-range inventory; reuse compatible mechanics only after parser conformance checks, not its extraction ownership model by assumption. [hashing.py](src/whetstone/hashing.py) distinguishes normalized draft hashing from raw byte hashing. Existing `ArtifactStore` writers overwrite named artifacts and are not immutable-attempt or atomic-promotion primitives.

The schema registry in [contracts.py](src/whetstone/contracts.py) implements the JSON Schema subset used locally, including the bridge's array bounds and uniqueness constraints. The ten bridge artifact schemas and shared definitions now exist under `contracts/schemas/`; candidate public schemas remain pending. Existing job-descriptor discovery in `run_state.py` is a status pointer, not immutable vNext descriptor admission. Existing scope/checkpoint artifacts are not automatically valid hash-bound mutation authorizations.

#### Decisions Required Before Implementation

The D1-D5 rows and recorded-decision sections below preserve historical policy and proposed wire details. For implementation, the current owning leaves and D1-D5 Readiness section supersede pre-output effect evidence, flat correspondence arrays, missing-evidence rejection during proposal preparation, and mandatory fresh-root re-admission. The policies of exact authorization, immutable evidence and no unsafe acceptance remain in force. D6-D8 remain unresolved vNext work.

D1-D5 now have owning-spec resolutions and a completed bounded audit recorded under D1-D5 Readiness. The table and recorded decisions retain their historical status; they do not reopen those specification prerequisites. D6-D8 remain specification work items: resolve each in its owning leaf and link the resolution here. Independent fixture preparation and implementation mapping may proceed while a decision is open; the affected slice cannot ship. If implementation exposes a new unspecified decision, resolve it in the affected owning leaf before completing that part of the slice.

| ID | Recorded gap or decision | Owner and blocked delivery at recording |
|---|---|---|
| D1 | Activation policy decided by the operator on 2026-09-05: explicit opt-in run configuration, versioned bridge capability, and hard enforcement of a versioned allowed-change-surface contract bound to the exact base and approved scope/findings before Editor invocation. No default-wide activation or unfinished vNext modes. See the recorded decision and recommended configuration below. Owning-spec amendments, public schemas and implementation remain pending. | Policy resolved; coordinating, scheduler, scope, artifacts still gate 18.1 admission and release |
| D2 | Inventory policy decided by the operator on 2026-09-05: link an operator-approved allowed/frozen change-surface manifest to a deterministic inventory of every section/protected unit bound to the exact base. Preserve unauthorized content by default; use versioned structural identities, total original-unit dispositions and separate additions. Moves/renames require explicit source/destination authorization; preservation does not restrict Reviewer visibility. See the recorded decision below. | Policy resolved; candidate, scope, artifacts still gate 18.1 identity/parser/manifest contracts |
| D3 | Policy decided by the operator on 2026-09-05: no autonomous acceptance of weakening; an explicit hash-bound operator decision must identify the exact protected units, permitted change type and rationale. Persist a distinct successful weakening disposition. Equivalence/supersession requires admissible evidence or a later independent verifier; absent evidence, reject. See the recorded decision below. | Policy resolved; candidate, scope, artifacts still gate 18.1 representation and evidence contracts |
| D4 | Identity/ordering policy decided by the operator on 2026-09-05: immutably retain and hash the exact raw Editor proposal, deterministically materialize a separate output using only defined Whetstone-owned transformations, hash its exact bytes separately, and compare the final materialized output before acceptance. Reports bind both identities and the trusted transformation; Editor-authored version edits get no exemption. See the recorded decision below. | Policy resolved; artifacts, candidate, scheduler still gate 18.1 wire contracts and acceptance/replay ordering |
| D5 | Lifecycle policy decided by the operator on 2026-09-05: freeze base and authorization per attempt; retry/resume only transient technical failures under unchanged bindings; reject deterministic preservation violations without automatic retry; pause only for a legitimate explicit scope-expansion or weakening decision. Changed authorization creates a new validated attempt, never rewrites a failed report. Valid unchanged output may complete as an accepted no-op. See the recorded decision below. | Policy resolved; scheduler, scope, artifacts still gate 18.1 state/report/attempt-binding contracts |
| D6 | vNext `job_id` is deterministic from canonical inputs, but its exact preimage and all identifier grammars/collision rules are not closed. The public contract suite is a list, not a pinned manifest format with schema/algorithm/fixture digests and support matching. Close these before emitting interoperable identities. | Candidate, artifacts, coordinating; 18.2-18.4 |
| D7 | Candidate disposition protocols are detailed, but the scheduler lacks a complete candidate-processing transition table covering modes, failed gates, interruption and operator decisions. Define transitions and unavailable/mismatched-mode reporting, including legacy/new-config precedence. | Scheduler, candidate, coordinating; 18.3 and 18.8 |
| D8 | Promotion requires storage-backed, recoverable, fenced exclusion with registration, but concrete acquisition, fencing, loss, reclamation and supported-filesystem semantics are not published. Select and contract-test the storage protocol before registration/promotion concurrency is exposed. | Candidate, artifacts; 18.5 registration and 18.7 promotion |

Dependency order: 18.1 -> 18.2 -> 18.3 -> 18.4 -> 18.5 -> 18.6 -> 18.7 -> 18.8 -> 18.9. D1-D5 are prerequisites inside the first deliverable, not a separate shipped paperwork milestone. D6-D8 may be resolved alongside earlier work but remain gates on their consumers. Public contract fragments and fixtures land with each consuming slice; 18.2 extends the minimal bridge contracts into the complete vNext suite.

#### D1 Recorded Activation Decision

The operator selected explicit opt-in hard enforcement for the current-runtime bridge. This resolves the activation policy, not the remaining inventory, evidence, hashing, or recovery contracts in D2-D5. The following is the recommended exact configuration shape for the owning-spec amendments; it is not a command/config surface supported by today's runtime:

```yaml
preservation_bridge:
  mode: enforce
  capability_version: preservation-bridge-v1
  allowed_change_surface:
    path: ./rounds/intake/bounded_change_surface.json
    sha256: "<SHA-256 of the exact allowed-change-surface artifact bytes>"
```

The proposed `preservation-bridge-v1` capability identifies the implemented bridge contract/algorithm version. The surface artifact retains the spec's `schema_version: bounded-change-surface-v1`; capability version and artifact schema version serve different purposes and both must be supported. The path is run-root-relative, resolved and validated before use. The expected SHA-256 pins the supplied contract, rather than trusting whatever bytes later occupy that path. This is separate from vNext `editing_mode` and `contract_suite_version`.

The admission contract must require and validate the surface artifact's bindings to the exact base draft, the configured approved scope contract, and the exact persisted Reviewer finding artifacts and admitted finding IDs. The Orchestrator verifies those bindings and confirms that admitted findings and allowed mutations remain within the approved scope; an Editor's claimed resolutions or a checkpoint recommendation cannot authorize the surface. Deletion/weakening/supersession evidence remains governed by D3 and the candidate leaf. The recorded D4 decision separates raw and materialized byte identities; its owning-spec amendment must define their fields without relaxing the exact-base requirement.

Validate configuration, capability support, contract schema and supplied artifact hash at run admission. Validate the complete current base/scope/finding bindings again immediately before each Editor invocation, after that round's Reviewer artifacts exist, then persist the immutable contract snapshot bound to that attempt. Missing, stale, unsupported or mismatched inputs must fail admission before the Editor runs; do not silently remove the bridge, fall back to unguarded editing, or expand permissions to continue. A contract pinned to an older draft or finding set cannot be reused for a later round merely because the run remains opted in. D5 permits an explicit new validated attempt with changed authorization; technical resume never silently rebinds it.

Omitting the entire `preservation_bridge` block leaves the run under explicitly identified legacy/unguarded semantics. Once the block is present, all shown fields are required; partial configuration is an error, not an implicit opt-out. The first supported mode is `enforce`; there is no report-only mode that can satisfy guarded acceptance. Persist the resolved mode, capability and bound surface identity in effective run configuration, prompt/attempt context, and status/terminal readback. Resuming an opted-in run must inherit enforcement and reject a capability downgrade or missing bindings; a legacy run must never acquire a claim of preservation coverage from the mere presence of an artifact.

Bridge activation remains confined to explicitly opted-in current-runtime full-draft workflows after bridge qualification. It does not select `proposal_only` or `verified_promotion`, grant candidate authority, or change defaults for other runs. Conflicting bridge/vNext configuration must fail rather than choose a more permissive path. This decision creates no standalone CLI flag; a future alias would need the same configuration and binding checks.

No further operator choice is required for D1's activation policy. The field spelling above is the recommended implementation contract, pending its owning-spec amendment; exact inventory/evidence/hash/lifecycle schemas remain the separately tracked D2-D5 work. Recording D1 does not mark 18.1 implemented or ratified.

#### D2 Recorded Change Surface And Inventory Decision

The bridge uses two linked artifacts with different authorities. The operator-approved change-surface manifest declares allowed and frozen surfaces, permitted change types, and applicable limits. The Orchestrator-generated preservation inventory binds to the exact base-draft hash and enumerates every section and protected unit. The manifest is the approval surface; the inventory is deterministic evidence of what exists and cannot grant edit authority by itself. Reconcile the manifest with the existing proposed `bounded-change-surface-v1` contract rather than adding a competing authorization registry.

Generate the inventory before obtaining/validating approval of a surface that references its units. Bind the approved manifest to that exact inventory/base and the D1 approved scope/findings; record both artifact identities in attempt context and reports. Preserve the D5 immutable attempt bindings. Changing the base, inventory/parser version, allowed/frozen surface or relevant approval is new admission, never an invisible refresh of a technical retry.

Anything not explicitly authorized for change is preserved by default. Frozen surfaces cannot be changed under the active manifest; a finding or Editor recommendation cannot remove that protection. Validate manifest references and conflicting allowed/frozen declarations before invocation, and never interpret a missing entry as unconstrained permission.

Unit identity uses canonical heading path, unit type, and a defined position/ordinal within its parent under a versioned parser. Bind the identity namespace to the exact base inventory so the same ordinal in another draft is not automatically the same unit. Do not derive correspondence from fuzzy similarity, model guesses, or absent vNext patch/transaction IDs. The parser must exclude heading-like text inside fences and account for document preamble, direct parent body and nested/overlapping units; nested content cannot disappear between inventories or be implicitly omitted because its parent is authorized. Exact serialization, structural position rules and overlap/change counting belong in the public parser/inventory contract with conformance fixtures.

Every original unit requires an explicit preservation disposition. Enumerate additions separately; an addition cannot cancel a missing original unit or conceal a removed table row/field. Moves and renames require explicit authorization of both source and destination, plus the allowed change type and applicable evidence. Without that authorization, treat the result as removal plus unrelated addition and reject the attempted move/rename; broad delete/add permission cannot be used to launder it. If structural correspondence is ambiguous, reject rather than assume identity continuity. D3 still controls any semantic equivalence/supersession evidence and any weakening approval.

Review scope controls what the Reviewer can inspect and report; the edit-preservation manifest must not hide frozen units or silence otherwise in-scope findings about them. A finding on a frozen surface may justify a new operator-approved surface under D5, but never modifies the current authorization automatically. Keep review visibility, edit authority and scope-expansion approval distinct in prompts and artifacts.

No user-level D2 policy question remains. The owning-spec amendment must now close the linked manifest/inventory fields, parser/identity version and deterministic correspondence/counting rules without weakening these decisions. This records the first bridge's structural model; it does not activate vNext stable-section mapping or candidate promotion.

#### D3 Recorded Weakening And Evidence Decision

The first bridge must never authorize weakening autonomously or accept an Editor assertion as authorization. Acceptance requires a persisted, explicit operator decision bound to the exact protected unit or units, the permitted `weaken` change type and the rationale. The decision must identify the authorized change, not grant a general exemption to preservation. Existing conjunction rules still apply: `weaken` must be allowed, `weakening_allowed` must be true, affected units/sections must be within the admitted surface, and required scope/finding bindings and other validation checks must pass.

Recommended successful disposition token: `operator_authorized_weakened`. Add it consistently to the candidate leaf's preservation disposition definitions and the bridge report schema during the owning-spec amendment. It means an actual reduction in normative force was explicitly approved; it must not be reported as `preserved`, `reworded_equivalent`, `strengthened`, or an ordinary modification. A successful unit disposition is not a pass for the whole draft if any other unit or gate fails. This token is proposed here, not an already-supported runtime enum.

The evidence contract must bind the operator decision to the base, relevant scope/allowed-surface contract and exact proposed effect, retain the operator identity and rationale, and expose the decision artifact path/hash in the attempt report. Under D4, evidence must identify the exact materialized bytes being considered for acceptance and retain their binding to the raw proposal and trusted transformation. Approval of raw text alone cannot authorize an unbound materialized result. Stale decisions, different units/effects, and mismatched hashes fail. Neither an earlier general approval nor an Editor-generated decision record is an operator decision.

Equivalence and supersession are evidence claims, not permission to weaken. They require explicit admissible evidence bound to the compared units/drafts that establishes unchanged meaning or equal-or-stronger successor coverage. A later independent semantic verifier may supply validated evidence when that capability exists; the first bridge must not assume it exists. Editor assertions, a clean Reviewer pass, size ratios and generic similarity do not suffice. An operator's authorization to weaken cannot be relabeled as equivalence or supersession. Without sufficient admissible evidence, reject under the existing ambiguous/unauthenticated-supersession categories.

The public evidence schema and versioned admissibility rules still need bounded specification work: producer/authority, exact input bindings, unit/effect coverage, and the checks that establish the claimed preservation. This is implementation-contract work, not an unresolved choice about whether weakening needs operator approval. Evidence that the first bridge cannot validate remains insufficient; do not add a permissive fallback to get a pass.

If approval arrives after an attempt was rejected, preserve that failure and its frozen contract. Under D5, changed authorization creates a new validated attempt; no approval may retroactively overwrite a failed report or make the rejected artifact current. The decision authorizes only the named weakening and never bypasses remaining preservation or downstream acceptance checks.

No further operator policy choice is needed for D3. The small representation choice is the enum spelling; use `operator_authorized_weakened` in the proposed amendments unless the shared contract vocabulary requires an equivalent name. Scope the first implementation to the evidence it can validate, and keep unsupported claims rejected.

#### D4 Recorded Proposal And Materialization Decision

Retain two distinct artifact identities for every materialized full-draft attempt. First persist the exact raw Editor-proposed draft bytes immutably and compute their SHA-256 before any Whetstone normalization, stamping or other transformation. Then deterministically materialize a separate proposed draft using only explicitly defined Whetstone-owned transformations and compute SHA-256 over those exact final bytes. Raw proposal identity is not the hash of a normalized string or a reconstructed accepted Editor summary; preserve the original client response separately under the existing raw-response policy.

The preservation comparison evaluates the exact base against the final materialized draft. All report, evidence and authorization checks must pass before those bytes can enter accepted history, become authoritative `draft_after.md`, replace `spec.md`, update accepted hashes or advance downstream authority. Do not validate the raw draft and then mutate it after validation. Proposed materialization is isolated attempt evidence and does not create or register a vNext candidate; the current-runtime bridge retains its narrower lifecycle.

Recommended report extensions for the owning-spec amendment are distinct `raw_proposal_path`/`raw_proposal_sha256` and `materialized_draft_path`/`materialized_draft_sha256` bindings, plus an ordered trusted-transformation record. Each transformation records its supported identifier/version, exact parameters, input byte hash and output byte hash. An empty transformation sequence binds identical raw and materialized hashes while preserving their separate artifact roles. Replaying the recorded sequence must reproduce the recorded materialized bytes; unknown transforms, altered parameters, unrecorded writes or mismatched hashes fail validation. These are proposed field names, not existing bridge-report fields.

A version-only change is trusted only when the Orchestrator actually performs the specifically defined and approved version transformation. Provenance, not the shape of a diff or an Editor claim, establishes this exception. An Editor-authored version change remains client-proposed content subject to ordinary allowed-surface/preservation checks; the Orchestrator must not launder it into a trusted stamp by copying its value or tagging it as its own. The transformation contract must identify its exact permitted version anchor/effect and cannot exempt adjacent normative text, arbitrary formatting or broad rewriting.

Reports must bind both artifact identities and the exact transformation between them for passing and failing comparisons. Preserve both artifacts once materialization exists; a failure before materialization must retain the available raw evidence and identify the failed stage rather than fabricate final bytes or a preservation pass. D5 owns that incomplete-attempt terminal/retry representation. Successful acceptance consumes the already-validated materialized bytes without further edits; resume replays/revalidates the bound transformations rather than restamping against an installed default or advancing the version twice.

Current normalized `draft_hash` may remain as an explicitly labeled compatibility identity where existing lineage requires it, but it cannot substitute for either exact-byte SHA-256. The wire contract must relate that normalized identity to the accepted materialized artifact. Report/schema amendments must also distinguish the raw rewrite-attempt artifact from the final materialized artifact, rather than ambiguously reusing the existing `proposed_draft_hash` field for both.

No user-level D4 choice remains. Exact field names, attempt filenames, text-decoding boundary, transformation version/parameters and compatibility wiring need specification/conformance detail, following this settled two-identity and validate-final-output policy. Do not silently generalize the approved version-stamp example into permission for other transformations.

#### D5 Recorded Failure And Continuation Decision

Freeze the exact base draft and authorization for each attempt. An attempt binds its immutable base, allowed surface, approved scope, admitted findings, relevant operator evidence, bridge version and D4 transformation inputs. Technical continuation must validate and retain those same bindings; no timeout, retry, resume flag or recovery path may silently substitute a new base, broaden the surface or refresh approval.

| Outcome | Required handling | Authority effect |
|---|---|---|
| Transient technical failure | Retry or resume only under unchanged frozen bindings and the supported technical retry budget; preserve every failed attempt immutably. Record a new attempt for a repeated execution without overwriting the interrupted/failed evidence. | Prior accepted draft remains authoritative. |
| Deterministic preservation violation | Reject with the exact failed checks and units; no automatic retry. An Editor cannot be asked repeatedly until one output evades the same guard. | Proposed bytes remain non-authoritative evidence. |
| Legitimate authorization decision | Pause only when explicit scope expansion or weakening authorization could legitimately make the exact proposed change valid. Persist the question, proposed effect and bound evidence for the operator. | No acceptance while approval is absent; approval alone does not advance authority. |

The decision path is not a blanket escape from a failed check. Corrupted or missing evidence, unresolvable identity, unsupported transformations, unauthenticated supersession and other deterministic defects remain rejection cases. If independent failures would remain after the suggested authorization, do not present that authorization as sufficient to pass. A mixed outcome must identify those failures; its reporting cannot imply that a single approval repairs the draft.

Changed authorization requires an explicit new validated attempt with a new immutable authorization snapshot and traceable predecessor/decision reference. Keep the prior base authoritative, revalidate its identity, and rerun every applicable materialization/preservation/acceptance check. Reuse of proposed bytes as evidence does not make those bytes a new accepted base. If the base itself has changed, the original attempt cannot be technically resumed; admission must bind any new attempt to the explicitly selected valid base rather than silently rebase.

This decision refines the earlier round-frozen/new-round-or-run restriction in the candidate leaf and D1/D3 planning text. The owning-spec amendment must support immutable authorization per attempt, with exact report and context references; the single `round-N/context/bounded_change_surface.json` path cannot be overwritten to impersonate a prior attempt's contract. Choose versioned attempt paths/bindings in that amendment. Technical retries share the same authorization; changed authorization is a new admission, not technical resume. Whether the existing CLI expresses that new admission inside a round or by a new round remains lifecycle wiring, not permission to overwrite evidence.

No failed or paused materialized draft may enter accepted history, replace `draft_after.md` or `spec.md` as authority, advance stability, reach Phase 2, or pass recovery/strop controls as accepted output. A soft budget, manual-recovery flag or later clean Reviewer cannot waive this boundary. A completed valid no-change result may be accepted as a no-op after applicable admission, binding, preservation and artifact checks; it does not need an invented mutation or a version increment. Profile-clean/convergence policy remains independently evaluated.

The scheduler/artifact amendments must map these outcomes to existing terminal/decision semantics, define the exact transient-error classification and retry budget inheritance, and report supported next actions without claiming unsupported resume paths. An interrupted/unwritable report retains whatever evidence exists, records the technical failure, and cannot be treated as a completed comparison or accepted round. Repeated continuation must not overwrite completed attempts or duplicate acceptance/history commits. These are remaining contract details under the settled three-way policy, not new operator decisions.

#### D1-D5 Readiness

The user-approved two-stage revision is now specified across the owning leaves. Its intended journey is bounded proposal generation -> exact-effect review -> immutable acceptance request/admission -> complete revalidation -> acceptance commit. Missing evidence during proposal assessment is expected pending work; no preliminary artifact becomes authority. Acceptance calls no Editor. Changed authorization can stay in the same root while the exact base remains current.

| Decision | Current owning amendment / trace |
|---|---|
| D1 | [Preservation Bridge Activation](docs/specs/WHETSTONE_COORDINATING_SPEC.md#preservation-bridge-activation): opt-in enforcement, complete qualification, proposal configuration separate from acceptance requests; no vNext activation |
| D2 | [Explicit Correspondence Rules](docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#explicit-correspondence-rules): direct predecessor/successor entries, all-line inventory, one-to-many reflow, complete supersession groups, total coverage and no implied array pairing |
| D3 | [Operator Evidence](docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#operator-evidence-contract): exact proposal-bound attestations collected after output exists; grouped affirmative adoption; no model self-certification |
| D4 | [Attempt Storage And Materialization](docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#attempt-storage-and-materialization): separate exact raw/materialized identities and fixed prospective transforms; final acceptance consumes identical bytes |
| D5 | [Bridge Lifecycle](docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#preservation-bridge-lifecycle): pending proposal evidence versus hard failure, no-client acceptance, new same-root admission for changed authorization, frozen technical continuation, single commit and downstream guards |

The completed audit covered the acyclic reference graph, proposal/acceptance attempt numbering, complete correspondence and evidence-kind rules, stale-base refusal, normal-round evidence retention, maintenance-only authorization inheritance, and exactly-once round completion after local acceptance. Executable fixtures must now verify those behaviors. Earlier `bridge-operator-evidence-v1`, single-admission and report-v1 draft shapes are superseded, not supported legacy bridge inputs. The qualified capability remains reserved as `preservation-bridge-v1`; publish its complete revised schema set together.

- [x] Bounded `audit-change` consistency review of the two-stage amendment at `da074f401889beaeb098dc8c7504847b4a16afe5`: `pass`, zero blocker/major/minor/nit findings, one Codex invocation using `gpt-5.5` and CLI `0.142.0`. The reviewed packet contained exact excerpts from the six owning specs plus this plan and the Quickstart. Source and snapshot hashes were verified; the source documents remained unchanged.

Audit evidence: local run `rounds/two-stage-preservation-bridge-audit-001/`, including `source_manifest.json`, `verification.json`, and `change_audit/{audit_manifest.json,change_audit_feedback.json,change_audit_report.json}`. The audit brief hash is `5d9f5a6bc7db3776f749b7e8b7b1c8b07cd1f6ec45e40e3bec26de1827a75ae9`. Run artifacts are ignored local evidence; this record preserves the reviewed commit, scope, client and outcome for the implementation handoff. The pass applies to that bounded source packet, not later edits or unreviewed source sections.

Next: implement acceptance admission, effect adoption, marker commit and replay/repair on the completed proposal-capture increment recorded below. No full Phase 1 sharpening run is a prerequisite. Reopen a focused contract review only if implementation exposes a concrete unresolved decision or requires a normative change. Schema publication does not provide runtime enforcement. D6-D8 remain later-vNext gates; the integrated 18.1 implementation/qualification checks remain open.

#### 18.1 Current-Runtime Preservation Bridge

First deliverable: one integrated, opt-in two-stage guarded full-draft path with explicit correspondence, operator effect review, deterministic acceptance, rejection, readback and replay. Specification dependency: the revised D1-D5 contracts and their bounded audit are complete. Stage implementation in the following order; capability advertisement remains gated on the complete bridge qualification:

1. Publish the closed schemas and cross-artifact validators alongside inventory/correspondence conformance vectors and deterministic journey fixtures. Establish both authorized success and unsafe rejection cases before wiring authoritative writes.
2. Implement immutable proposal admission/storage, frozen normal-round evidence, materialization and preliminary assessment, including pending obligations and hard failures.
3. Implement the shared acceptance service, marker commit and replay/repair, then the local effect-review/request preparation, explicit acceptance operation and read-only dry-run. Prove the pending-to-accepted journey and stale-base refusal with scripted inputs and zero acceptance-stage model calls.
4. Route normal, supplied, resumed, focused/vertical and maintenance paths through that service; integrate scheduler/readback and Phase 2/declaration/strop consumers. Complete the positive, negative and fault-injection qualification below before enabling opt-in enforcement.

Foundation increment evidence (2026-09-06; committed as `a3f268f`):

- [x] Publish ten closed bridge artifact schemas plus shared definitions, including origin-specific admission nullability, exact Ref/hash shapes and duplicate-free arrays.
- [x] Implement the exact-byte `bridge-lines-v1` inventory, fence/section ownership, deterministic identities and conservative matching; publish three independent inventory vectors and an exhaustive small-sequence matching oracle.
- [x] Implement read-only reference, surface, proposal/evidence-binding, correspondence, supersession, relocation and cap checks. The composed untransformed-proposal check leaves all files unchanged and creates no acceptance marker.
- [x] Reject unavailable `preservation_bridge` configuration with `CONFIG_INVALID`; preserve exact toy-spec checkout bytes with local Git attributes.

Validation: `tests/test_preservation_inventory.py`, `tests/test_preservation_contracts.py` and `ConfigTests.test_unqualified_bridge_configuration_is_never_silently_ignored`; 30 focused preservation tests and 329 tests in the full suite pass. See [contract foundation guide](contracts/PRESERVATION_BRIDGE.md) for exact APIs and limits. These are foundation checks, not completed transaction/operator-journey qualification. The next increment below adds transformed proposals and preliminary reports; maintenance inheritance, acceptance report/marker validation, runtime integration and replay remain pending. The broader checks below stay open until their integrated behavior has evidence.


Proposal-capture increment evidence (2026-09-06; working changes based on `a3f268f`):

- [x] Freeze approved base/surface/scope/findings, exact Reviewer evidence and resolved config before a single-use Editor callback; recheck current base and input bytes before completing a proposal.
- [x] Persist immutable numbered attempts, exact raw responses/extracted or supplied drafts, separate prospective materialization/inventory, proposal records and preliminary reports. Retain incomplete identities and refuse duplicate execution or overwrites; persistence failures retain available evidence and a terminal sidecar when possible.
- [x] Reproduce the pinned version/status transform from immutable inputs; reject Editor-owned anchor edits; reverse verified stamp effects only for internal correspondence/counting. Pure Phase 2 entry stamping is tested; accepted-chain admission remains pending.
- [x] Demonstrate clarification pending, hidden frozen schema/table/enum loss rejected, unchanged preservation eligible, and no authoritative draft/summary/history/marker writes. Exercise duplicate ambiguity/multiplicity, additions, relocation, caps, corrupt input, stale inputs, timeout and persistence failures.

Validation: `tests/test_preservation_proposals.py` adds 30 deterministic tests; 60 focused preservation tests and 359 tests in the full suite pass. No nested model calls. These developer components complete step 2 above; ordinary acceptance/residual gates, acceptance attempts, marker commit, technical replay and runtime path integration remain open. A preliminary pass never authorizes installation. The broader integrated qualification checks remain unchecked.

Implementation checks:

- [ ] Publish the revised bridge contracts: surface/inventory, proposal admission/record, evidence-v2 with explicit correspondence, acceptance request/admission, report-v2, acceptance-v2 marker and terminal-failure contract. Validate base/scope/surface/findings before proposal generation; collect and bind exact-effect evidence after output exists. Reject superseded draft shapes and unknown fields. Verify the artifact graph is acyclic.
- [ ] Build the versioned structural section/unit inventory and deterministic comparison using heading path, unit type and defined parent position/ordinal. Cover preamble, parent bodies, normative statements, schemas/fields, tables/rows, enums, flags, artifacts, states, scenarios and references, including nesting/overlap. Exclude fenced pseudo-headings, preserve unauthorized units by default, require total base-unit disposition and separately enumerate additions. Unresolved correspondence is pending during proposal assessment when no hard failure exists, and blocks final acceptance; explicit adopted mappings must resolve it without fuzzy inference.
- [ ] Persist raw proposal bytes and materialize separate proposed output through the defined Orchestrator transformations. Bind both exact-byte hashes and the ordered transformation evidence; run preservation on the final materialized bytes before any authoritative writes or accepted history. Keep normalized lineage hashes separately labeled. Freeze effective config before execution and retain origin-specific Reviewer feedback/Editor summary references; acceptance cannot substitute later defaults, new resolution claims or different normal-round evidence. Changed transformation inputs require a new proposal, never post-approval restamping.
- [ ] Enforce allowed sections/units/types and numeric caps, including source/destination ownership for moves, operator-authorized deletion/weakening, and evidenced supersession. Keep size ratios advisory; preserve current corruption and placeholder checks. Do not mistake clarity, shortening, or reviewer silence for semantic equivalence.
- [ ] Integrate the same acceptance service into normal and supported resumed Editor paths, supplied revisions, vertical consolidated editing and focused/horizontal paths. Reject before authoritative `draft_after.md`, canonical accepted summary/hash, `spec.md`, accepted history/version advancement, stability, Phase 2 or strop can consume failed output. Test the `apply=true, accepted=false` path explicitly.
- [ ] Persist immutable proposal and acceptance attempts with distinct counters and reports, including pending assessments. Retain `full_draft_rewrite_attempt-M.md`, materialized output and frozen normal-round evidence; approval never rewrites a proposal report. New content or transformation inputs allocate proposal attempt `M`; changed acceptance authorization/evidence allocates acceptance attempt `K`. Bind each new request to the immediately preceding assessment report when one exists, and retain incomplete attempts without silently reusing their identity. Retain raw invalid input under existing attempt policy. Report/attempt persistence or hash-validation failure cannot result in acceptance. Existing generic overwrite helpers cannot silently overwrite attempt evidence.
- [ ] Commit only through the final acceptance marker after preservation and ordinary round gates pass, under exclusive single-writer admission/commit access and atomic create-if-absent persistence. Recheck the current base and previous marker at commit. Repeated acceptance, including no-ops, reuses the existing marker; later authority must never be replaced by historical replay. Finish checked mirror/history/scheduler repair before another admission may commit, with no duplicate version, issue or budget accounting.
- [ ] Bind reporting to the exact attempt and prior authoritative draft: extend run-state/status, validation/terminal reporting and readback with report path/hash, failed categories/units, accepted versus proposed hashes, and the precise supported next action. A passing report alone never means profile-clean or apply-back eligible.
- [ ] Implement proposal `awaiting_operator_evidence` as `PAUSED_DECISION`, with no model retry for missing effect evidence. Known hard failures reject. Add the explicit local request-file acceptance operation and read-only dry-run; freeze new same-root acceptance admissions for changed authorization, call no Editor, retain prior reports, refuse stale base and complete the original round once. The local acceptance command completes or repairs its selected operation and stops without invoking the next Reviewer/Editor or charging another model-review budget. Pending acceptance blocks the next mutating round. Technical continuation retains frozen bindings and existing phase limits; generic Phase 2 technical resume remains unsupported.
- [ ] Implement unchanged-output and Phase 2 entry maintenance acceptance with empty evidence where the owning contracts permit it. Preserve origin-specific normal-round eligibility; initial seed no-ops require normal admission, only maintenance origins may inherit older authorization through a validated acceptance chain, and no-op handling cannot clear serious residuals. Phase 2 entry uses its dedicated attempt path and null round/profile/client fields, without a fabricated Editor summary or numbered round.
- [ ] Apply the complete marker/report/admission/request/evidence/proposal chain guard at Phase 2 handoff, declaration, and dry/live strop for runs declaring bridge support. Dry-run consumers never repair or mutate. Preserve the existing external-source hash check. Historical runs without bridge evidence remain explicitly legacy, not retrospectively verified or silently broken by a new required field.

Likely surfaces: `live.py`, `config.py`, `cli.py`, `prompts.py`, `sections.py`, `hashing.py`, `artifacts.py`, `versioning.py`, `run_state.py`, `status.py`, `reports.py`, `termination.py`, `resume.py`, `live_phase1.py`, `live_phase2.py`, `apply_back.py`, `contracts.py`, the new minimal schemas, and the D1-D5 owning specs/Quickstart. A focused inventory/comparison module is justified; a parallel orchestration framework is not.

Acceptance evidence:

Seed corpus: [Preservation bridge toy specs](examples/fixtures/preservation_bridge/README.md) supplies seven fictional bases, fixed proposal variants, expected outcomes and lifecycle exercises. Use these as inputs for executable fixtures; creating the corpus does not complete any qualification check.

- [ ] Unit/conformance fixtures cover fenced pseudo-headings, duplicate/renamed headings, direct intro content, nested lists, table/enum/field loss, normative weakening, allowed/disallowed changes, ambiguous identity, stale authorization, and boundary counts. Legitimate unchanged/allowed additions and demonstrably preserved changes pass, preventing a reject-everything implementation.
- [ ] Manifest/inventory fixtures cover frozen and unspecified surfaces, mismatched base/inventory approval, deterministic parent/ordinal identity, nested coverage, and explicit move/rename source/destination authorization. Reviewer fixtures prove an in-scope frozen-surface finding remains visible and cannot expand the active edit surface without operator approval.
- [ ] Weakening fixtures prove that Editor claims and configuration permission alone fail; an exact valid operator decision yields `operator_authorized_weakened` only for the approved units/effect. Stale or mismatched decisions fail, unrelated loss still fails, and missing equivalence/supersession evidence cannot be replaced with a weakening approval.
- [ ] Materialization fixtures cover a genuine Orchestrator version stamp, no-transform identity, Editor-authored version edits, tampered raw/materialized bytes or transform parameters, materialization failure, and repeated resume. Final-output preservation must detect any unapproved materialized change, retain exact raw evidence, and prevent post-check mutation or double stamping.
- [ ] Lifecycle fixtures distinguish transient technical retry, deterministic rejection with zero automatic retries, a pending operator-evidence pause, changed authorization producing a separate fully validated same-root acceptance attempt, stale-base refusal, and a valid accepted no-op. Prove that paused/rejected output cannot advance via soft budgets, Phase 2, recovery or strop, and that technical resume never refreshes authorization.
- [ ] Reproduce the motivating destructive bounded-synthesis incident class: a schema-valid full-draft response resolves targeted issues while collapsing unrelated contracts. Use a minimized checked-in fixture with expected lost-unit evidence; padding above size thresholds must not evade rejection. Historical ignored run artifacts may help derive the fixture but cannot be required for tests or committed wholesale.
- [ ] Integration tests exercise initial/retry/resumed acceptance and vertical consolidated output with scripted clients. Failed proposals leave authoritative files/hashes and downstream eligibility unchanged; passing and failing attempts both persist; storage failures cannot advance authority. A legitimate subsequent retry succeeds without erasing evidence.
- [ ] CLI-shaped fixture tests cover proposal admission -> pending assessment -> grouped evidence/request -> same-root acceptance -> status -> supported technical recovery -> Phase 2/strop guards, including existing no-op and version-stamping behavior. Acceptance dry-run leaves authority, attempts and history unchanged; the explicit acceptance command stops after its selected operation with no further model call or review-budget charge. Document the actual supported command and generated request/evidence workflow in the Quickstart when implemented. No real model is needed for this acceptance proof.
- [ ] Positive operator-journey fixtures cover one-to-one clarification, attested addition, one-to-many reflow, complete many-to-one supersession, authorized deletion/weakening and an added exception affecting verbatim base units. Record displayed effects, adopted mappings, interaction count and model calls; acceptance must require no further Editor invocation or manual hash/JSON construction.
- [ ] Negative/recovery fixtures cover swapped mappings, conflicting evidence, incomplete supersession groups, uncovered output, pending work plus hard failures, altered normal-round evidence, stale-base approval, duplicate accepted no-ops and interruption before/after commit. Same-root acceptance cannot clear unrelated residuals or bypass Phase 2/strop lineage. Include predecessor-report continuity, concurrent local admission/commit exclusion, historical acceptance replay after authority advances, and interrupted mirror/history/scheduler repair with no duplicate accounting.
- [ ] Maintenance fixtures cover initial-seed no-op admission, unchanged output from each supported origin, prior-acceptance authorization inheritance only for maintenance, and Phase 2 entry with empty feedback/null summary and no numbered round or review-budget charge. A trusted heading stamp preserves correspondence for descendants while adjacent unauthorized content changes still fail. These fixtures must not create a generic Phase 2 technical-resume path.

Rollout: only explicitly admitted guarded runs after all bridge conformance and positive operator-journey qualification passes; keep existing full-draft client protocol compatible. Clearly label unguarded/legacy runs. Non-goals: patch proposals, candidate pointers/registration, new semantic-verifier calls, report-only bypass, default-wide scheduler changes, automatic synthesis, context trimming or pressure-based editing.

#### 18.2 Public vNext Contracts And Conformance Foundation

Dependencies: 18.1; resolve D6. This extends, rather than postpones, the bridge's already-shipped minimal contracts.

- [ ] Publish the descriptor-bound contract-suite manifest and every schema listed in the candidate leaf's Public Contract Suite: authorities/ratification/invariants, section identities, decisions, mutation plan, patches, candidate creation/verification/disposition, preservation/semantic reports, promotion/current pointer and terminal report.
- [ ] Define each schema's field ownership, nullability, unknown-field policy, canonical bytes, exact identity preimages, identifier grammar/collisions, versions and supported migrations. Separate model-input envelopes from Orchestrator-derived persisted fields.
- [ ] Supply executable cross-artifact validators and positive/negative conformance vectors. Audit the in-repo schema validator's keyword support and add only the semantics the published contracts actually need; never silently ignore a required constraint.

Likely surfaces: `contracts/schemas/`, proposed versioned conformance fixtures under `tests/fixtures/`, `contracts.py`, `hashing.py`, `tests/test_contracts.py`, and candidate/artifact/coordinating specs. Acceptance: identical canonical bytes/IDs for published vectors, rejection of unknown suites, missing fields, altered bindings and collisions; schema-valid but inconsistent artifact graphs fail. Rollout: offline contract validation only. Non-goals: live proposal generation, automatic promotion or historical artifact migration.

#### 18.3 Job Admission And Mode Gates

Dependencies: 18.2; resolve D7, including the processing transition table before scheduler wiring.

- [ ] Admit immutable `job-descriptor-v2` with seed, authority, scope, invariants, algorithms and review configuration. Validate mode/suite support before clients or writes; changed inputs create a new identity.
- [ ] Implement ratified CLI/config capability negotiation for `reviewer_only`, `proposal_only`, and `verified_promotion`, with unsupported modes rejected. Publish exact operator-facing unavailable/mismatch reasons. Reviewer-only is the vNext default; whole-document replacement is unavailable in all vNext modes.
- [ ] Persist only the mode's permitted initialization artifacts, including the ordinal-0 seed pointer/history once their contract is implemented. Expose proposed versus available capability in status; refuse promotion until all later gates pass.

Likely surfaces: `cli.py`, `config.py`, `run_state.py`, `status.py`, `prompts.py`, new descriptor admission helpers, corresponding tests, coordinating/candidate/scheduler specs and Quickstart. Acceptance: zero Editor/Verifier calls in reviewer-only, unsupported suite/mode fails before invocation, stale descriptor/ref hashes fail, legacy keys cannot activate a new mode. Rollout: new isolated vNext roots only; proposal mode remains unavailable until 18.5. Non-goals: upgrading an in-flight legacy run or treating file presence as capability support.

#### 18.4 Admitted Mutations And Section-Addressed Proposals

Dependencies: 18.3; D2/D3 bridge lessons must be reconciled with the vNext identity/evidence contracts.

- [ ] Classify findings against authority/scope/invariants, bind operator responses, and admit only editor-fixable derived tasks. Build section-sliced mutation plans whose union is the admitted finding set and whose dependency ordering/overlap is validated.
- [ ] Implement stable section identities separately from existing canonical review anchors, immutable payload storage, client patch proposals and canonical Orchestrator-owned patch metadata. Enforce declared operations, assertions, predecessor hashes and mutation budgets.
- [ ] Reject unsupported operations, duplicate/overlapping targets, identity collisions, stale decisions and whole-draft responses. Keep proposal attempts inspectable without making them candidate or draft authority.

Likely surfaces: `scope.py`, `decisions.py`, `identity.py`, `sections.py`, `clients.py`, `protocols.py`, `prompts.py`, dedicated proposal/plan modules, public contracts and focused tests. Acceptance: a bounded admitted correction yields one validated patch set with traceable source findings; a mixed proposal containing an unauthorized deletion is rejected. Rollout: fixture-driven, non-promoting artifacts; public proposal workflow still gated until assembly/registration. Non-goals: prose-to-patch inference, automatic operator decisions, expanding scope to satisfy a Reviewer.

#### 18.5 Candidate Assembly, Validation And Registration

Dependencies: 18.4; resolve D8's registration exclusion/storage protocol before enabling concurrent registration.

- [ ] Assemble deterministically from the immutable base and canonical patch/payload hashes, deriving and binding the candidate section identity map. Check parser, structure, assertions, invariants, inventories and allowed surface with reusable bridge primitives where their contracts match.
- [ ] Implement candidate identity, immutable candidate directories, initial unverified disposition and run-wide creation-event registration. Select latest through the unique contiguous committed chain; preserve and diagnose incomplete orphans without timestamp/directory heuristics.
- [ ] Exercise proposal-only from admitted request through inspectable registered candidate and deterministic report while seed authority remains unchanged. Passing deterministic validation must not label a candidate verified.

Likely surfaces: dedicated assembler/candidate-store/registration modules, `artifacts.py`, contracts, section/inventory helpers, `status.py`, and candidate/artifact specs. Acceptance: repeat assembly yields identical bytes/maps/IDs; altered payloads/maps, duplicate registrations, crashes and competing registrations obey the contract. Rollout: opt-in `proposal_only` after its supported subflow qualifies; no promotion intents or pointer advancement. Non-goals: semantic approval, recovering orphan content by guessing, or replacing the legacy scheduler wholesale.

#### 18.6 Independent Semantic Verification And Disposition

Dependencies: 18.5.

- [ ] Add the independent verifier protocol with bounded but sufficient base/candidate context, admitted findings, preservation obligations and authority constraints. Validate all returned evidence and exact input bindings; Editor self-certification is insufficient.
- [ ] Implement immutable verification attempts, per-finding coverage, candidate decisions, disposition events and atomic candidate-local verification-pointer commit. Distinguish validation pass, candidate verified/rejected, and interrupted unverified state.
- [ ] Keep retries on the correct immutable base and plan; any proposed reduced patch is a new validated proposal, not an in-place edit of a registered candidate.

Likely surfaces: `clients.py`, `protocols.py`, `prompts.py`, candidate verification modules, `artifacts.py`, `status.py`, decision/report contracts and tests. Acceptance: useful fix plus unrelated regression fails; missing findings, stale hashes, invalid output, timeout and torn decision/event writes cannot verify a candidate. A successful proposal-only verification still leaves the current verified seed untouched. Rollout: proposal-only soak with scripted verification first. Non-goals: verifier quorum, auto-ratification, bypassing deterministic failures or promotion.

#### 18.7 Atomic Promotion, Locking And Recovery

Dependencies: 18.6 and ratified D8.

- [ ] Implement the fenced run-wide lock mutually excluding registration and promotion, then promotion intents, prepared disposition events, ordinal-indexed pointer snapshots and the atomic current-verified replacement commit point.
- [ ] Implement current committed lineage validation, sole next-ordinal claimant selection and post-commit materialization recovery in the specified order. Materialize `spec.md`, `draft_after.md`, history and state only from the committed authority.
- [ ] Make lock loss, competing preparation, stale base, missing map, interrupted pointer replacement and failed materialization explicit recoverable/rejecting cases under the storage contract. Read-only status must not repair anything.

Likely surfaces: isolated lock/promotion/recovery modules, `artifacts.py`, `run_state.py`, `status.py`, `resume.py`, storage/conformance fixtures, candidate/artifact specs. Acceptance: fault injection at every prepare/commit/materialization boundary and concurrent processes prove at most one valid next ordinal, no stale-holder writes, and repeatable recovery. Rollout: offline/fixture promotion capability first; public automatic mode remains gated. Non-goals: unsupported distributed storage semantics or manual edits to current pointers.

#### 18.8 Scheduler, Phase 2 And Apply-Back Integration

Dependencies: 18.7; complete the D7 transition table and candidate leaf's Ratification Delta Map across all owning leaves.

- [ ] Integrate the candidate transaction into normal, focused, vertical, retry, budget-extension and supported resume paths without changing profile budgets or cleanliness policy. Keep run terminal state orthogonal to candidate disposition.
- [ ] Make accepted-draft selection, version lifecycle, review history, declaration regeneration, Phase 2 verification and convergence resolve only the current verified lineage. Candidate existence, a clean Reviewer, or a verified-but-unpromoted candidate cannot advance these consumers.
- [ ] Bind strop/readback to the current verified pointer, candidate/map/decision/intent evidence, decision gates and external source hash. Ensure legacy manual-recovery flags cannot label unverified material verified or bypass vNext eligibility.
- [ ] Report prior authority, latest candidate, orphan/rejected evidence, outstanding decisions, next gate and supported resume action on every relevant terminal path. Preserve earlier attempt reports and committed history.

Likely surfaces: `live.py`, `runner.py`, `engine.py`, `live_phase1.py`, `live_phase2.py`, `scheduler.py`, `resume.py`, `evaluation.py`, `declaration.py`, `versioning.py`, `apply_back.py`, `termination.py`, `reports.py`, `status.py`, `run_state.py` and their tests; all ratification-delta leaves and Quickstart. Acceptance: CLI-shaped fixture campaigns exercise both phase boundaries, closeout, budgets, interruptions and strop; no candidate failure advances draft authority or convergence. Rollout: new-root end-to-end qualification, preserving existing legacy behavior through explicit mode dispatch. Non-goals: retroactive verification, in-place legacy conversion, changing convergence criteria to hide incomplete verification.

#### 18.9 Compatibility, Qualification And Controlled Activation

Dependencies: 18.1-18.8, all D1-D8 closed, all family amendments consistent.

- [ ] Map every candidate-spec P0 scenario to an executable fixture/test and evidence record, including destructive recurrence, valid simplification, forbidden compatibility, stale decisions, parser edges, partial regression, cross-implementation determinism, interrupted registration/verification/promotion, and external-source drift.
- [ ] Run the full regression suite plus process/CLI and fault-injection conformance; demonstrate that legacy runs, reviewer-only audits/sweeps, bridge runs and proposal-only jobs retain their declared behavior. Publish exact tested schema/algorithm/client versions and known limits.
- [ ] Perform a separately authorized isolated live soak only after deterministic gates pass; inspect both successful and rejected proposals and preservation evidence. No source apply-back is implied by qualification.
- [ ] Advertise `verified_promotion` only for the supported suite that passed the complete activation gate. Document new-root seed import, unsupported-version refusal, immutable input rules, operator recovery, and how to disable future automatic jobs without rewriting active descriptors or historical artifacts.

Likely surfaces: conformance fixtures/tests, release metadata, coordinating and all amended leaves, Quickstart and examples. Acceptance: every P0 row has reproducible evidence; no advertised mode exceeds qualified support; legacy accepted hashes are never presented as candidate verification proof. Rollout: explicit opt-in promotion, then observation before considering wider defaults. Non-goals: automatic legacy migration, project-wide spec tracking, semantic quorum, UI work or unrelated scheduler optimization.

#### Verification And Next Action

Use the existing `unittest` architecture: pure unit fixtures, injected Reviewer/Editor/Verifier clients, scripted multi-profile scheduler campaigns, fake configured executables for CLI/subprocess boundaries, and filesystem fault injection. The nearest existing tests are `test_live.py`, `test_resume.py`, `test_live_phase1.py`, `test_live_phase2.py`, `test_contracts.py`, `test_sections.py`, `test_artifacts.py`, `test_status.py`, `test_reports.py`, `test_cli.py`, `test_apply_back.py`, `test_runner.py` and `test_engine.py`. Add focused bridge/candidate tests where responsibility warrants them; do not rely on live model consistency for deterministic acceptance.

Next action: continue 18.1 with shared acceptance admission/effect adoption, ordinary-round gates, marker commit and replay/repair, then the local request-file acceptance operation and read-only dry-run. Extend the completed proposal-capture tests into pending-to-accepted, stale-base, no-op/Phase 2 maintenance and commit-recovery journeys, then wire the shared service through the runtime paths. The bounded audit is complete; do not add a full Phase 1 run as an implementation prerequisite. If a fixture reveals an unresolved contract decision, pause the affected part, amend its owning leaf and use a focused review of that delta while independent work continues. Any additional nested live-client audit or usability trial requires its own payload authorization. Production bridge activation remains gated on complete 18.1 qualification; D6-D8 and later vNext work retain their own prerequisites. Feature completion means all slice checks have executable evidence, not that files with proposed names exist.

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
- [ ] Editor mutation safety: editor output can be valid while still producing undesirable draft changes; delivery tracked in [18. Safer Editor Pipeline](#18-safer-editor-pipeline)
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
