# Whetstone Implementation Plan

This plan is the traceable build checklist for Whetstone `0.17`.

## Build Strategy

Build deterministic behavior first, then introduce live clients behind narrow gates.

Fixture mode remains the regression harness. Live Codex/Claude behavior must not weaken fixture determinism, schema validation, artifact integrity, or halt-state reproducibility.

## Current State

Completed:

- [x] Bare repository scaffold
- [x] `0.17` spec persisted as `spec.md`
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
- [ ] Status/resume support available or explicit non-resumable limitation documented

Acceptance:

- [ ] Full multi-round run reaches `CONVERGED` or a correct terminal state
- [ ] Halt artifacts match terminal state
- [ ] Cross-round memory explains any oscillation/conflict halt
- [ ] Fixture-mode tests still pass afterward

## Remaining Build Checklist

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

- [ ] Generate `convergence_declaration.md`
- [ ] Validate declaration content against current draft hash, rubric hash, target matrix, and unresolved issue set
- [ ] Distinguish `CONVERGENCE_REVISION` from `DECLARATION_REVISION`
- [ ] Re-review declaration with `convergence_strict_check`
- [ ] Reject conditional declarations as terminal status

Acceptance:

- [ ] `CONVERGED` requires accepted declaration
- [ ] Declaration-only changes route through `DECLARATION_REVISION`
- [ ] Spec changes route through `CONVERGENCE_REVISION`
- [ ] `conditional` is never emitted as terminal declaration status

### 6a. Rubric Gap Evaluation

Tasks:

- [x] Define `rubric_content_hash` normalization
- [x] Define `rubric_gaps.json` schema
- [ ] Emit `rubric_gaps.json` during Phase 2 rounds
- [ ] Derive `unresolved_rubric_gaps` from unresolved blocking rubric gaps
- [ ] Feed derived rubric gaps into target-matrix evaluation
- [ ] Include rubric gaps in convergence failure reports

Acceptance:

- [ ] `final/strict` convergence cannot pass with unresolved blocking rubric gaps
- [ ] Permissive targets can accept documented rubric gaps when policy allows
- [ ] Rubric gap ordering is deterministic

### 7. Role Assignment And Client Factory

Tasks:

- [ ] Read `clients.reviewer` from config
- [ ] Read `clients.editor` from config
- [ ] Instantiate Codex reviewer adapter
- [ ] Instantiate Codex editor adapter if configured
- [ ] Instantiate Claude Code editor adapter
- [ ] Keep fixture clients available
- [ ] Surface unsupported client names as configuration errors

Acceptance:

- [ ] Reviewer and editor can be assigned independently
- [ ] Codex can be reviewer while Claude Code is editor
- [ ] Fixture clients can be used for either role in tests
- [ ] Config model preserves concrete command/version/model values

### 8. Live Round Engine

Tasks:

- [ ] Render reviewer prompt
- [ ] Persist reviewer prompt snapshot
- [ ] Invoke reviewer client
- [ ] Validate reviewer artifact
- [ ] Render editor prompt
- [ ] Persist editor prompt snapshot
- [ ] Invoke editor client
- [ ] Validate editor artifact
- [ ] Capture or apply draft mutation
- [ ] Emit full round packet

Acceptance:

- [ ] One live round can complete with fixture reviewer + live editor
- [ ] One live round can complete with live reviewer + fixture editor
- [ ] One live round can complete with live reviewer + live editor
- [ ] Invalid client output cannot mutate `spec.md`

### 9. Live CLI Surface

Tasks:

- [ ] Add `run`
- [ ] Add `live-round`
- [ ] Add `status`
- [ ] Add `resume`
- [ ] Keep `fixture-script`
- [ ] Keep `codex-review`

Acceptance:

- [ ] `status` reports latest terminal state or latest round packet
- [ ] `resume` refuses unsafe resume when required artifacts are missing
- [ ] `run` uses configured roles
- [ ] CLI errors are actionable

### 10. Golden Fixtures

Tasks:

- [x] Clean convergence fixture
- [ ] Blocker conflict escalation fixture
- [ ] Oscillation cycle fixture
- [ ] Mechanical churn freeze fixture
- [ ] Feedback flip-flop fixture
- [ ] Feedback churn manual-review fixture
- [ ] Re-addition stop fixture
- [ ] Phase 1 max rounds fixture
- [ ] Phase 2 declaration failure fixture
- [ ] Phase 2 convergence failure fixture
- [ ] Permissive target with documented Phase 2 major issue fixture
- [ ] Malformed reviewer output rejection fixture
- [ ] Malformed editor output rejection fixture

Acceptance:

- [ ] Every terminal state has at least one fixture
- [ ] Every fixture validates emitted artifacts
- [ ] Fixtures remain stable across test runs

## Identity-System Notes

Whetstone uses three identity surfaces:

- `feedback_id`: per-round feedback item identity
- `issue_id` / `issue_fingerprint`: stricter issue identity, potentially prose-sensitive
- `oscillation_fingerprint` / `oscillation_opposition_key`: looser Phase 2 concern identity

Implementation rules:

- [ ] Conflict escalation uses conflict fingerprints and may underfire when issue prose changes
- [ ] Phase 2 oscillation detection uses oscillation keys and should fire earlier for recurring churn
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

- [ ] Assign reviewer and editor roles from config
- [ ] Run Codex as reviewer
- [ ] Run Claude Code or another configured client as editor
- [ ] Persist complete prompt snapshots
- [ ] Complete at least one live round without accepting malformed artifacts
- [ ] Preserve fixture-mode regression behavior
