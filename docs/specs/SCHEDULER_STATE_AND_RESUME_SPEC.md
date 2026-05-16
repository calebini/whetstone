# Scheduler State And Resume Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: scheduler_state_and_resume_spec
target_spec_role: leaf_spec
-->

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
