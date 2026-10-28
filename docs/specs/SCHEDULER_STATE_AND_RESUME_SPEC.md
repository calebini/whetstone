# Scheduler State And Resume Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: scheduler_state_and_resume_spec
target_spec_role: leaf_spec
-->

## Verified-Promotion Release

Public support: **explicit config opt-in `verified_promotion`**, qualified on
2026-10-28 for **`vnext-verified-consumer-1`**, exact manifest digest
`7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58`.
This leaf's V requirements are operative only for that advertised suite and the
[qualified scope and evidence](../VNEXT_VERIFIED_PROMOTION_RELEASE.md).
D8 requires a canonical physical run root on local macOS/APFS. The standard
workflow, stateful-system profiles, fixed rubric, command/recovery matrix and
immutable input gates remain mandatory. Other modes/suites gain no qualification
by implication; legacy/bridge defaults and separate provider/source-write consent
remain unchanged. See the [operator procedure](../OPERATOR_QUICKSTART.md#operating-a-qualified-v-release).

## HALTING CONDITIONS (ORDERED PRECEDENCE)

Preflight validation runs before runtime halt precedence. If preflight configuration validation fails, the Orchestrator MUST halt with `CONFIG_INVALID` before invoking any Reviewer or Editor and MUST NOT evaluate runtime halt conditions.

Runtime halt precedence:

1. Client invocation timeout
2. Clean convergence achieved
3. Blocker-level conflict escalation triggered
4. Oscillation stop triggered
5. Artifact validation failure exhausted
6. Decision intervention required
7. Profile-level round budget exhausted

The first condition satisfied halts execution.

For an explicitly guarded run, the [preservation bridge lifecycle](#preservation-bridge-lifecycle) is an acceptance precondition, not another lower-priority vote in halt precedence. A rejected/paused/incomplete proposal cannot satisfy clean convergence, profile-clean or accepted-draft conditions. Evaluate its failure before any proposed bytes become authority.

Only active conditions from the current evaluation cycle participate in halt precedence. Historical terminal reports from earlier halted, resumed, or superseded states are audit artifacts and MUST NOT preempt the current `run_state.json` interpretation after a valid continuation has advanced the run. When a resumed or continued run writes a later `run_state.json`, that run state is the authority for current terminal evaluation; preserved older terminal reports remain historical evidence only.

---

## HALT ARTIFACT MATRIX

clean convergence achieved:
- terminal_state: CONVERGED
- required artifacts:
  - spec.md
  - spec.history.md
  - convergence_declaration.md

Phase 1 stable boundary:
- terminal_state: PHASE_1_STABLE
- required artifacts:
  - spec.md
  - spec.history.md
  - rounds/run_state.json
  - latest draft_after.md
  - one current-draft reviewer_feedback.json per required Phase 1 profile
  - one profile_used.yaml per required Phase 1 profile identifying the reviewed draft hash, profile name, round path, and round kind
- must set:
  - ready_for_phase_2: true

focused profile stable:
- terminal_state: FOCUSED_PROFILE_STABLE
- required artifacts:
  - spec.md
  - spec.history.md
  - rounds/run_state.json
  - latest draft_after.md
  - latest reviewer_feedback.json proving the focused profile is clean on the current draft hash
- must set:
  - ready_for_phase_2: false

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

profile-level round budget exhausted:
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

For V, accepted/profile-clean/stable/converged quality states remain distinct
from verified lineage. Each quality consumer MUST resolve the current committed
verified pointer and its required current review/declaration evidence. A candidate
or legacy accepted-draft hash does not establish verification or permit promotion;
verification alone does not establish cleanliness or convergence.

A draft is considered accepted if:
- zero blockers globally
- zero major issues globally

For an explicitly guarded run, acceptance additionally requires a valid bridge acceptance marker for the exact materialized bytes, or the explicitly recorded unchanged initial seed before any editing. Issue-resolution claims alone do not satisfy that gate.

This is used for:
- last_accepted_draft_hash
- convergence readiness baseline

Accepted draft and clean profile are intentionally different scopes.

Accepted draft is stricter than some convergence targets and is required before Phase 2 regardless of target policy.

---

## SPEC VERSION LIFECYCLE

For V specifically, Editor-selected version/status changes are rejected under
the pinned system-metadata algorithm; the legacy restoration rule below MUST NOT
silently repair or authorize them. Legitimate V maintenance uses the separately
attributed system spans before verification, as defined by the candidate leaf.

For an explicitly pinned V consumer, all mutating version/status transitions
below MUST be assembled before candidate hashing and pass the candidate leaf's
scheduler-authorized system-metadata protocol. No legacy stamp helper may mutate
already verified bytes. Phase 2 entry is a distinct fenced commit after its
complete Phase 1, configuration, request, rubric and source prerequisites; a
metadata promotion or configuration publication alone is not entry. Unversioned
entry has no metadata candidate when no supported numeric change is required.
Older modes retain their existing version lifecycle.

Spec version labels express maturity:
- `0.x` versions are Phase 1 stabilization drafts.
- whole-number major versions (`1.0`, `2.0`, etc.) indicate the spec has passed Phase 1 acceptance and entered Phase 2 convergence.
- post-entry Phase 2 decimal versions (`1.1`, `1.2`, etc.) indicate accepted mutating convergence revisions after Phase 2 entry.

For legacy and preservation-bridge consumers, version stamping is Orchestrator-owned. The Editor MUST NOT choose, increment, decrement, or otherwise modify the visible spec version label unless the Orchestrator explicitly supplies that exact version label as part of the editable draft. If an Editor-produced draft changes the visible version anchor before an accepted mutating round is stamped, the Orchestrator MUST restore the pre-round version anchor before applying the Orchestrator-owned stamp. This normalization SHOULD be recorded in the round Editor artifact so operators can see that the Editor attempted a version change, but it MUST NOT double-increment the visible version label.

The restoration rule above is legacy-only. Under `preservation-bridge-v1`, preserve the raw proposal and reject an Editor-authored version edit as `untrusted_version_edit`; do not disguise it as a trusted restoration/stamp. Apply the versioned Orchestrator transformation to separate materialized bytes before preservation/acceptance, then install those bytes unchanged. Bridge no-ops do not increment the version, and repeated resume cannot restamp an already committed acceptance.

For versioned specs, the Orchestrator MUST stamp accepted mutating rounds with a new visible version label before computing and persisting the final `draft_after_hash`. A spec is versioned when its root heading, `Status:` line, or `Version:` field contains a supported numeric version label. Supported numeric version labels contain one, two, or three numeric components (`N`, `N.N`, or `N.N.N`). The Orchestrator MUST parse the complete version label and MUST NOT partially match a longer dotted label. If no supported numeric version anchor exists, the Orchestrator MAY skip version stamping and MUST continue to use hashes and round artifacts as rollback authority.

Version stamping rules:

- Phase 1 accepted mutating revision with a two-component stabilization label: increment the second component while preserving its visible width and carrying two-digit overflow into the major component.
- Phase 1 accepted mutating revision with a three-component label: increment the third component and preserve the existing version scheme.
- Phase 1 accepted mutating revision of a `Status: Accepted ...` document MUST demote the run-root draft status to `Status: Draft ...`; Phase 1 stabilization does not by itself produce a newly accepted source artifact.
- Phase 1 non-mutating round: do not change the version label.
- Phase 1 rejected or unresolved round: do not change the version label.
- Phase 2 entry: promote to the smallest whole major version that is greater than or equal to the current numeric version, with a minimum of `1.0`.
- Unversioned Phase 2 entry: if no supported numeric version anchor exists, promotion MUST be a no-op (`promoted = false`) and MUST NOT block Phase 2 when the Phase 1 stable hash guard otherwise passes.
- Phase 2 accepted mutating revision after entry with a two-component label: increment the first decimal place under the current major version.
- Phase 2 accepted mutating revision after entry with a three-component label: increment the third component and preserve the existing version scheme.
- Phase 2 non-mutating round: do not change the version label.
- Phase 2 rejected or unresolved round: do not change the version label.
- Clean convergence declaration generation alone does not change the version label unless the same accepted round also mutates `spec.md`.

Examples:
- Phase 1 accepted mutation: `0.17` stamps to `0.18`
- Phase 1 accepted mutation: `0.99` stamps to `1.00`, but this does not by itself authorize Phase 2 entry
- Phase 1 accepted mutation: `0.1.1` stamps to `0.1.2`
- `0.17` promotes to `1.0`
- `0.1.1` promotes to `1.0`
- `1.7` promotes to `2.0`
- `2.0` remains `2.0`
- Phase 2 accepted mutation: `1.0` stamps to `1.1`
- Phase 2 accepted mutation: `1.9` stamps to `1.10`
- Phase 2 accepted mutation: `1.0.3` stamps to `1.0.4`

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

All draft, spec, snapshot, run-state, and artifact hashes used by this leaf MUST use the canonical text, canonical JSON, and SHA-256 hash semantics defined by the artifact/content normalization spec. Resume guards, version stamping, accepted-draft tracking, budget-extension events, and `spec.history.md` entries MUST compute hashes after the relevant content is persisted in canonical form. Version stamping MUST occur before the stamped draft's persisted `draft_after_hash` or Phase 2 promoted `draft_before_hash` is computed.

When more than one supported numeric version anchor exists, version-anchor precedence is:

1. explicit `Version:` field in frontmatter or document metadata
2. visible `Version:` line in the document body before the first non-title section
3. root heading numeric version label
4. `Status:` line numeric version label

If multiple supported anchors are present, they MUST either agree before stamping or the Orchestrator MUST halt with `HALTED_ARTIFACT_INVALID` before mutating `spec.md`. Stamping MUST update the highest-precedence anchor. Lower-precedence synchronized anchors MAY also be updated only when they exactly matched the prior authoritative version; conflicting lower-precedence anchors are invalid rather than silently overwritten.

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

The Orchestrator MAY provide a pre-mutation diagnostic sweep command for first-contact or expensive-scope runs. A diagnostic sweep is not a Phase 1 stabilization run. It MUST:
- execute exactly one Reviewer-only pass for each configured Phase 1 profile in the selected profile set
- review the same current `spec.md` hash for every profile
- invoke only Reviewer clients
- MUST NOT invoke the Editor
- MUST NOT mutate `spec.md`
- persist normal `round-N/` review-only artifacts for each profile
- write `/rounds/profile_sweep_report.json` and `/rounds/profile_sweep_report.md`

The diagnostic sweep report MUST cluster blocker and major findings by profile, issue type, affected section, and feedback identifier. It SHOULD recommend one of:
- `start_phase_1`: the sweep found no blocker or major feedback
- `run_bounded_synthesis`: serious findings cluster across multiple profiles, sections, or contract families and should be handled as a synthesis pass before normal Phase 1
- `run_vertical_phase_1`: serious findings exist but are small enough for normal vertical review/edit cycles
- `manual_scope_review`: findings suggest the scope contract or job design is too broad, contradictory, or missing a run-boundary authority rule

A diagnostic sweep MUST NOT mark any Phase 1 profile clean, set `ready_for_phase_2`, satisfy accepted-draft requirements, produce a convergence declaration, or count as a Phase 1 closeout cycle. It exists to reveal the shape of the problem before the first mutating Editor pass.

In-scope implementation authority conflicts, such as identifier ownership, row identity, response authority, or source-of-truth precedence inside the approved scope, SHOULD normally recommend `run_bounded_synthesis` rather than `manual_scope_review`. `manual_scope_review` is reserved for cases where the operator likely needs to change the scope contract, reference authority set, or job design before mutation.

Canonical section IDs and profile focus anchors used by scheduling are imported from the artifact/content normalization spec and the rubric/profile spec. Each Reviewer pass MUST persist the resolved focus anchor set for its profile in `profile_used.yaml`. Clean-profile reuse and invalidation MUST compare semantic change section IDs against that persisted anchor set, not against freshly inferred prose labels.

If an edit renames or moves a section, invalidation uses the semantic change record: the old canonical section ID is treated as changed, and the new canonical section ID is treated as changed. If either ID matches a persisted focus anchor for a previously clean profile, that profile's clean status is invalidated for the new draft.

The Orchestrator is the producer of semantic change records used for clean-profile invalidation. A mutating round MUST persist the canonical changed section IDs in the round artifacts before clean-status reuse is evaluated. If the semantic change record is missing, schema-invalid, or cannot map an edit to canonical section IDs, the Orchestrator MUST use the conservative fallback: invalidate every previously clean Phase 1 profile for the new draft. If the record cannot be produced because the draft artifact itself is unreadable or invalid, the round MUST halt under artifact validation policy instead.

In `vertical` mode, each profile review remains independent: it MUST have its own prompt, profile focus, `reviewer_feedback.json`, `profile_used.yaml`, prompt snapshot, context files, telemetry, and validation. Only the Editor step is consolidated.

The vertical merge artifact MUST preserve each finding's source profile. If feedback IDs are not globally unique across profile reviews, the Orchestrator MUST rewrite feedback IDs in the consolidated Editor packet using:

```text
feedback_id = profile_slug + ":" + original_feedback_id
```

`profile_slug` is the lowercase profile name with every contiguous run of non-ASCII alphanumeric characters replaced by `-` and leading/trailing `-` removed. The consolidated packet MUST preserve `source_profile` and `original_feedback_id` for audit. If two rewritten IDs still collide, append `":" + N` using the one-based occurrence count in stable source ordering. Stable source ordering is phase profile order, then round number, then original feedback order inside the source `reviewer_feedback.json`. Issue IDs and issue fingerprints remain those of the original reviewer findings.

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
- if the Reviewer returns no in-scope feedback requiring draft mutation, the Orchestrator MUST skip the Editor and persist an Orchestrator-owned no-op `editor_summary.json` with `draft_before_hash = draft_after_hash`
- if the Reviewer returns only minor or nit feedback, the Orchestrator MAY invoke the Editor only when the selected target policy says minor/nit cleanup is in scope for the current profile; otherwise it MUST carry the findings as nonblocking residual feedback and advance or close out according to profile cleanliness
- if the Reviewer returns any in-scope blocker or major feedback selected for resolution, the Orchestrator MUST invoke the Editor unless another higher-precedence halt condition applies
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

Resume continuation MUST apply the same horizontal closeout eligibility check when the reconstructed scheduler has no remaining review-editor profile to run. The fact that exhaustion is reached inside `resume` rather than inside the original live Phase 1 loop MUST NOT suppress an otherwise eligible closeout pass.

If the horizontal closeout pass finds any blocker or major issue, the Orchestrator MUST NOT run another automatic Editor revision. It MUST halt using the applicable Phase 1 budget-exhaustion terminal state and report the remaining verification debt.

If a Phase 1 Editor returns an unchanged draft while one or more in-scope blocker or major Reviewer findings remain unresolved, the Orchestrator MUST NOT classify that event as oscillation solely because the draft hash repeats. It MUST produce a Phase 1 technical failure report with `terminal_state: TARGET_NOT_REACHED`, `current_draft_status: not_accepted`, and an exit reason indicating unchanged Editor output with unresolved serious findings. This represents Reviewer/Editor disagreement or no-op editing debt, not semantic draft churn.

Phase 1 completes only when:
- all non-skipped Phase 1 profiles have valid clean status, and
- the current draft is accepted.

Phase 2 executes configured profiles in order.

After each Phase 2 reviewer/editor cycle, the Orchestrator MUST first perform Orchestrator-owned declaration maintenance for the current draft lineage, then evaluate halt conditions in the ordered precedence defined by this spec. Declaration maintenance includes regenerating a stale candidate `convergence_declaration.md` for the current draft hash and removing active declaration hash-binding findings that are fully repaired by that regeneration.

Client invocation timeout and artifact validation failure are evaluated before declaration maintenance when the client call or artifact needed for the current cycle did not complete validly. Decision intervention is evaluated after artifact validation and before invoking an Editor or declaration revision that would require an operator-owned choice. Once a valid Phase 2 cycle exists and no intervention blocks maintenance, declaration maintenance MUST happen before oscillation, conflict, target-matrix, clean-convergence, or budget-exhaustion evaluation.

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

`rounds/run_state.json` and `whetstone status` output MUST include `run_artifact_pointers` with operator-facing pointers to the active scope contract and any discovered job descriptor. Each pointer MUST include the artifact path, whether it currently exists, and a content hash when the file exists. The job descriptor pointer MAY be absent/missing when no first-contact job descriptor was used.

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

Unknown or obsolete round-limit keys in older configuration files MAY be ignored for backward compatibility; they MUST NOT affect scheduling, status reporting, manifests, or prompt snapshots.

Unused profile budget is not carried over to later profiles or phases.

Phase 2 may halt before consuming its full budget if clean convergence is achieved.

When `review_budget_exhaustion_policy = hard`, Phase 1 profile-budget exhaustion is a hard stop if any required Phase 1 profile lacks valid clean status or the current draft is not accepted. It does not proceed automatically to Phase 2.

When `review_budget_exhaustion_policy = soft`, Phase 1 profile-budget exhaustion advances to the next configured Phase 1 profile after recording residual status for the exhausted profile. After the final configured Phase 1 profile is exhausted or verified, the Orchestrator MUST evaluate Phase 1 stability. If stability is not achieved, it MUST halt with `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS` rather than `TARGET_NOT_REACHED`.

Soft budget mode MUST NOT weaken accepted-draft requirements, clean-profile requirements, convergence readiness, or Phase 2 entry. It only changes whether Phase 1 stops immediately on the first exhausted/oscillating profile or completes the remaining profile sweep for diagnostic value.

---

## vNext Candidate Processing (D7)

This section is the scheduler contract for prospective vNext jobs. It does not activate a runtime mode. The [coordinating admission rules](WHETSTONE_COORDINATING_SPEC.md#vnext-admission-and-capability-negotiation-d7) own selection and availability; the candidate leaf owns immutable evidence and commit points. Existing legacy and preservation-bridge runs retain their own lifecycle. For vNext, this section supersedes whole-draft Editor acceptance, automatic metadata mutation and generic Editor-retry scheduling wherever those would advance unverified bytes.

### State, Authority And Evaluation Order

`processing_gate` is an internal next-work label, separate from the existing run terminal state and the four candidate dispositions. Its values are `admission`, `seed_initialization`, `review`, `finding_admission`, `proposal`, `assembly`, `deterministic_validation`, `semantic_verification`, `verification_commit`, `promotion`, `materialization`, and `complete`. A gate is derived from validated evidence; a run-state field cannot authorize skipping it. `complete` means the current bounded invocation has no further permitted work, not convergence. Operator waiting and technical interruption are terminal outcomes with a retained next gate, not extra candidate dispositions.

Before clients or authority writes, resolve protocol/mode and capability, validate descriptor/suite/input bindings, and validate the existing root's ownership and lineage when continuing. A fresh admission commits the seed initialization before reviewing. For an existing root, validate the current pointer and history first; if only permitted materializations are missing/stale, repair those and end the invocation. Otherwise validate registration and decision evidence before selecting work. Status and dry-run perform the same reads but never repair. Corrupt authority evidence is a failed precondition, not a condition that clean convergence can outrank.

Every Reviewer pass reads the exact current verified draft. Only a committed promotion may change that base. Final verification alone does not clear findings or profile debt, consume a clean round, stamp a version or enter Phase 2. Promotion invalidates review evidence for the changed draft under the existing profile rules; it does not itself establish acceptance, stability or convergence. Metadata changes cannot use the legacy stamping exception to bypass the candidate protocol.

After these preconditions, existing ordered halt precedence applies to active runtime conditions. An unresolved operator decision prevents clean completion; a failed candidate gate cannot satisfy clean convergence. Timeouts, conflict and oscillation retain their existing precedence. A table row below describes the outcome absent another higher-precedence active halt; retain all applicable reasons even when one determines the terminal state.

### Processing Transition Table

`R` = reviewer_only, `P` = proposal_only, `V` = verified_promotion. All rows require the selected capability to be implemented. No row licenses a future gate in an earlier slice.

| Gate / trigger | Modes | Next work or terminal outcome | Candidate and authority effect |
|---|---|---|---|
| Admission succeeds on a fresh isolated root | R/P/V | `seed_initialization` | Freeze exact descriptor and inputs; no clients yet. |
| Seed/map/history/pointer initialization validates and commits | R/P/V | `review` | Ordinal-0 seed is authoritative; no candidate, verification or promotion event is invented. |
| Valid Reviewer result | R/P/V | `finding_admission`; consume one successful profile review under existing budgets | Findings are evidence only; authority unchanged. |
| Review/classification finds a concrete unresolved operator-owned choice | R/P/V | `PAUSED_DECISION`; retain `finding_admission` | Persist the hash-bound request; no automatic choice or Editor invocation. |
| No operator gate, R has editor-fixable findings | R | Continue permitted reviewer-only sweep/closeout within its budget; at its end `TARGET_NOT_REACHED`, or `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS` under the existing soft-sweep rule | Never invoke Editor/Verifier, assemble a candidate, or claim those findings resolved. |
| No admitted changes remain and required review evidence is clean | R/P/V | Existing focused/Phase 1 completion rules; `complete` for that invocation | No synthetic patch/candidate/no-op promotion. Phase 2 requires its separately implemented gate. |
| Valid mutation plan admits work and resolves required decisions | P/V | `proposal` | Freeze base, plan, slices and context before Editor invocation. |
| Valid normalized patch and exact payloads | P/V | `assembly` | Proposal is retained as evidence; no authority effect. |
| Assembly succeeds and exact candidate/map registration commits | P/V | `deterministic_validation` | Initial effective disposition is `CANDIDATE_UNVERIFIED`. Prepared orphan files are not latest. |
| Deterministic validation fails for a registered candidate | P/V | `verification_commit`, then `HALTED_ARTIFACT_INVALID` with `vnext_preservation_failed` | Commit final `CANDIDATE_REJECTED`; do not invoke Semantic Verifier. |
| Deterministic validation passes; semantic service unavailable in this release | P only | Retain non-final decision with semantic `not_run`; `TARGET_NOT_REACHED`, reason `vnext_gate_unavailable` | Candidate remains unverified, inspectable and unpromotable. This is the bounded proposal-only endpoint before 18.6. |
| Deterministic validation passes and semantic service is available | P/V | `semantic_verification` | Candidate remains unverified. P may verify for inspection; it cannot promote. |
| Valid semantic `reject`, including policy-mapped unsafe uncertainty | P/V | `verification_commit`, then `TARGET_NOT_REACHED`, reason `vnext_semantic_rejected` | Final rejected candidate; authority and outstanding finding debt unchanged. |
| Valid semantic `operator_decision_required` with a concrete bound request | P/V | `verification_commit`, then `PAUSED_DECISION`, reason `vnext_operator_decision_required` | Final rejected candidate, not a candidate waiting for retroactive approval. Operator response requires a new transaction and fresh verification. |
| Both layers pass and all decision gates are clear | P/V | `verification_commit` | Commit final `CANDIDATE_VERIFIED`; promotion permission is true only in V. |
| Final verified decision, P | P | `TARGET_NOT_REACHED`, reason `vnext_proposal_only_complete`; `complete` | Stop the bounded proposal journey for inspection. Existing draft remains authoritative; no automatic repeat of the same findings. |
| Final verified decision, V and full promotion capability | V | `promotion` | Recheck locked current base and the candidate leaf's claimant selection; prepared intent is not authority. |
| Atomic current-pointer replacement commits | V | `materialization` | Candidate becomes promoted only through the pointer-bound event. |
| Permitted materializations complete during uninterrupted execution | V | `review` under remaining budgets, or existing terminal evaluation | Subsequent review uses the promoted bytes. |
| Resume finds committed pointer with missing/stale permitted materializations | R/P/V as applicable | `materialization`, then end invocation | Repair only mirrors/run state. No new client, decision, registration or promotion ordinal in that invocation. |
| Valid final rejected or verified-P candidate encountered on technical resume | P/V as applicable | Refuse candidate-verification continuation | Final decisions are immutable. A separately admitted new transaction is distinct from technical resume. V may proceed to promotion from its valid final verified decision. |
| Invalid proposal/assembly before registration | P/V | Shape repair only as bounded below, otherwise `HALTED_ARTIFACT_INVALID` | No fabricated rejection event for a candidate that never registered; retain proposal and diagnostic evidence. |
| Invalid, missing, interrupted or timed-out semantic output | P/V | Bounded technical handling below | Candidate remains unverified. Persist a non-final decision only when all its required inputs, including the deterministic report, exist and validate. Never fabricate a semantic verdict. |
| Write interruption during registration, verification commit or promotion | P/V | Halt; supported explicit recovery only | Determine effective disposition solely through the owning commit pointer/event rules. Prepared artifacts have no authority. |

A promotion base mismatch, broken hash/map/ordinal chain, ambiguous claimant or partial committed pointer is `HALTED_ARTIFACT_INVALID`. Never fall back to an older candidate, replay the Editor to reconstruct bytes, overwrite evidence, or silently refresh the base. Failure before registration leaves the prior registered candidate latest; failure after registration preserves the new candidate's last effective disposition. If a required rejection/verification commit itself fails, report the write failure and the last committed disposition, not the intended next disposition.

### Retry, Decisions And Continuation

Client artifact-shape validation retains the artifact leaf's hard maximum of one automatic validation retry per logical client request, across restarts. Retry only the failed shape with identical role, base, plan (if any), slice, context and algorithm bindings plus precise validation errors. A retry is a new immutable attempt; starting another process does not reset the allowance. Reviewer process/context-loading failures follow that same rule. This vNext rule is separate from the preservation bridge's stricter guarded-Editor retry policy.

Patch semantics, preservation failure and valid semantic rejection receive **zero automatic repair proposals** in this initial vNext policy. The candidate leaf's narrower-repair mechanisms are available only as explicit new admissions once implemented; they are not technical retries. Each such admission has its own immutable plan/transaction, declared bounds and attempt lineage, against the still-current verified base. An unchanged rejected plan cannot be resubmitted as an allegedly new automatic retry. No budget extension or manual recovery flag may bypass finality or safety gates.

Client timeout halts `HALTED_CLIENT_TIMEOUT` with zero automatic retry. Other transport, provider, authentication, unknown-exit and local persistence failures halt `HALTED_ARTIFACT_INVALID` with their exact cause and zero automatic retry; do not reinterpret them as shape errors. An explicit technical continuation is available only for a published role/phase/gate and after exact frozen-input, current-base, attempt-budget and evidence checks. It resumes the first incomplete gate and reuses complete valid output. An incomplete candidate is never the input draft. Changing a timeout does not change candidate authorization; changing mode or descriptor-bound inputs requires a new job. No generic Phase 2 resume support is implied.

Before an operator response permits new work, validate the request/response bindings under the candidate and scope leaves. A decision made before proposal admission may produce a newly admitted plan. A valid verifier decision request finally rejects its candidate; a response may authorize a new transaction but cannot reopen that candidate. Changes to descriptor-bound scope, authority, invariants or review configuration require a new job identity/root; changes only to a same-job, same-base transaction authorization require a new transaction. Declined/unresolved decisions cannot become editor-fixable by timeout, budget pressure or operator silence. Read-only further inspection is permitted; automatic continuation past a pending blocking choice is not.

### Reporting And Slice Availability

Use the coordinating spec's `vnext` capability block in status and preflight diagnostics. After initialization, terminal-report-v2 binds the verified seed/current pointer and uses null latest-candidate fields when no registration exists. `resume.permitted` means the exact next gate is implemented, technically eligible and permitted in the immutable mode; `next_gate` is null otherwise, with an explicit refusal reason. An operator action or new admission is not advertised as technical resume. Before initialization, use configuration/technical diagnostics without manufacturing a current verified pointer or terminal-report-v2 lineage. A damaged initialized root must report unreadable evidence rather than manufacture a valid terminal report from cached paths.

18.3 qualifies admission, seed-only initialization (including the seed-map subset), reviewer-only work and read-only capability reporting. R remains pinned to ordinal 0 and performs no version stamping, candidate creation, semantic verification, automatic Phase 2 handoff or source apply-back. Reviewer budgets/classification still apply. Mutating commands and generic legacy resume reject R when they request unavailable work. Seed initialization runs only under exclusive fresh-root ownership and the candidate leaf's immutable publication requirements; a partial initialization is diagnosed and preserved, never overwritten by a second admission. Seed-materialization recovery and every other continuation are advertised only after their dedicated checks exist.

P remains unavailable until 18.5 qualifies proposal/assembly/registration and D8's required storage protocol. P may stop with an unverified candidate until 18.6 qualifies semantic verification; no silent fallback is allowed when a caller explicitly requests a later gate. V is available only for the advertised suite that passed the full coordinating activation gate. Offline suite recognition is not runtime capability. Later implementations must publish their exact supported role/phase/gate combinations before status may recommend them.

#### Verified command execution and recovery

The V command adapter MUST consume the existing verified scheduler owners, not
reimplement their selection/finality rules or invoke the legacy full-draft Phase
2 executor. Standard horizontal/vertical Phase 1 and explicitly selected focused
work retain their pinned profiles, cleanliness criteria and ordinary budgets.
Focused stability cannot satisfy full Phase 1 or Phase 2 entry prerequisites.
Phase 2 supports only the declared standard workflow, stateful-system profile set,
exact standard-v1 rubric and published target combinations; unsupported configured
routes refuse rather than borrowing a legacy implementation.

`live-phase1` and `live-phase2` may advance the selected ordinary gates within
existing bounds and MUST stop at blocking decisions, technical failures,
exhaustion, freeze or other unsupported actions. An admitted correction passes
request, registration, deterministic and independent semantic verification before
promotion; candidate presence or a clean review cannot stand in for these gates.
`promote-phase2` performs only the shared entry preparation/required system
candidate/verification/promotion and distinct entry commit, not Phase 2 reviews.
`live-phase2` uses the same entry owner when entry is required, then the existing
review/resolve/declaration/convergence sequence. Reentry cannot stamp or enter twice.

`status` and `resume --dry-run` are read-only and client-free. They expose current
verified authority, latest candidate and effective disposition, retained
rejected/orphan/failure evidence, decisions and the exact next/recovery gate.
`resume` performs only the currently supported, explicitly invoked recovery or
technical continuation. Recovery-only reentry MUST end after the committed
materialization/report/receipt repair; it cannot start another round or consume
a client allowance. Technical continuation retains the original request inputs
and attempt budget. `--continue` is available only for the declared Phase 1
continuation; no generic Phase 2 loop or freeze resume is introduced.
`--extend-review-budget N` is an explicit existing Phase 1 grant, not a descriptor
rewrite or permission to retry a final candidate. Any source-write uncertainty
routes to separately acknowledged strop recovery, never an implicit source write.

Disabling future automatic jobs means stopping the external launcher or changing
the configuration used to prepare future jobs. It MUST NOT rewrite an active
job descriptor, remove a retained D8 lock, change historical artifacts or imply
permission to continue an already paused job.

##### Exact V recovery and continuation routes

This table is the complete initial V `resume` surface. It does not change the
earlier R/P interfaces. Every row requires valid retained inputs, the pinned
consumer and fresh evidence validation under D8. Status reports the exact row,
request/transaction/pass references and proposed invocation; it cannot authorize
another row. Recheck the selected row inside the same fence as its mutation;
if another invocation completed it, return its result rather than falling through
to new work. `--dry-run` on any row performs reads only, with no client or repair.

Selection comes from the unique active committed request/transaction and current
verified lineage, not an arbitrary newest filename. An explicit `--vnext-round N`
must match that selection and is required where shown. Missing, ambiguous, stale
or conflicting evidence refuses before a client. Candidate selection follows
the candidate leaf's ordering/finality rules and its sole prepared-claimant
exception; no operator selector can choose an older candidate for new work.

| Retained condition / gate | Explicit invocation and evidence selector | Owner / client permission | End of this invocation |
| --- | --- | --- | --- |
| Current committed pointer has missing/stale permitted materializations | `resume`; select that pointer and its committed source | Verified materialization owner through its recovery branch; no client and no next promotion | Repair those projections and stop. |
| Interrupted registration or verification-decision publication, with all producer output complete | `resume --vnext-round N`; bind the retained transaction, candidate/creation evidence and exact pending decision | `recover_registration` or the existing verification commit owner; reuse complete bytes, no Editor/Verifier | Finish only that publication and its required projections; stop before verification, promotion or another request. |
| One valid prepared next-ordinal promotion claimant | `resume`; bind its exact intent, verified decision, ordinal and expected base | `promote` prepared-claimant recovery; no client and no fresh claimant selection | Complete that reserved promotion/materialization and stop, even if a later candidate exists. |
| Phase 1 terminal/report/state publication incomplete | `resume`; bind exact current closeout or retained failure/review evidence | Existing Phase 1 publication/reconciliation owner; no client | Publish/repair that outcome and stop before another review. |
| Phase 2 entry already committed but projection incomplete, or pending failure/correction-failure/resolution/signal/findings/blocked/closeout publication | `resume`; bind exact entry or active pass/outcome references | Existing entry and Phase 2 publication/reconciliation owners; no client | Complete that outcome's reports/state and stop. Mere configuration publication cannot authorize entry; uncommitted entry remains with `promote-phase2`. |
| Phase 1 Reviewer request interrupted and journal permits continuation | `resume`; select unique active Phase 1 review request/profile/cycle | `review_next(continuation=True)`; only that Reviewer request may use its remaining attempt/shape allowance | Retain result and required recovery/failure projections, then stop before finding admission or another role. |
| Phase 1 Editor proposal request interrupted and journal permits continuation | `resume --vnext-round N`; exact selected immutable plan/transaction/request | `request(..., continuation=True)`; only that Editor request's existing remaining allowance | Retain the proposal/failure and stop before registration, verification or promotion. |
| Phase 1 semantic request interrupted, candidate non-final and journal permits continuation | `resume --vnext-round N`; exact latest eligible candidate, base and semantic request | `verify(..., continuation=True)`; only that Verifier request's existing remaining allowance | Complete its verification decision/projections and stop before promotion. |
| Phase 2 advice attachment retained without its binding | `resume`; select the exact consumed pass and request | First/later advice owner reconstructs only the exact Reviewer-derived attachment and binding; no clients | Stop after attachment repair, before correction admission, Editor, Verifier or next review. |
| Phase 2 Reviewer request interrupted, failure projections current and journal permits continuation | `resume`; select exact unique active pass ordinal and committed request | First pass: `run_phase2_review(continuation=True)`; later pass: `continue_phase2_pass(pass_number, action="execute", continuation=True)`; only that Reviewer request's remaining allowance | Retain the review/failure outcome and required projections; stop before consumption, advice, correction or the next pass. |
| Phase 1 additional-budget admission | `resume --extend-review-budget N`; bind the retained budget-exhausted context | `extend_phase1_budget`; explicit grant only, no client | Record grant and stop; a separate `live-phase1` invocation executes ordinary work. |
| External source-write uncertainty | `strop --recover --exclusive-source-access` (or `apply-back` alias); bind retained historical intent | Source readback/receipt owner only; no model and no source replacement | Return the reconciled historical result or explicit operator-attention state. |
| Any other condition | Refuse `resume` | No client or authority write | Includes exhausted/closed requests, final candidate rejection, corrupt/ambiguous authority, generic Phase 2 Editor/Verifier continuation, freeze and unchanged valid declaration disagreement. Supported report repair does not waive these refusals. |

Pending publication/projection recovery takes precedence over client continuation.
If such repair is needed, even `resume --continue` repairs and stops; the operator
must invoke continuation separately after inspecting the new status. Repair must
never silently spend the allowance whose failure it is reporting.

For V, `--continue` is an optional Phase 1 loop request after successful technical
continuation of the selected logical request. It resumes ordinary Phase 1 gates
within existing budgets and stops at a decision, failure, exhaustion or Phase 1
terminal. It is invalid on Phase 2, on source recovery, and when combined with
`--extend-review-budget`. Plain `resume` always ends at the boundary in the table.
Existing automatic shape-retry limits remain within a logical request; this
table grants no new retry slot. Complete retained valid output is reused without
calling a client. A live-command rerun, including `live-phase2` or
`promote-phase2`, cannot implicitly retry an interrupted request; it reports the
explicit continuation above or an unsupported/refused gate. An ordinary live
invocation after successful continuation may consume the retained result.

## Preservation Bridge Lifecycle

This is the pending two-stage `preservation-bridge-v1` contract, operative only under the [separate activation gate](WHETSTONE_COORDINATING_SPEC.md#preservation-bridge-activation). It introduces no vNext candidate states or promotion locking. Normal, supplied, resumed, horizontal/focused, vertical and Phase 2 acceptance use one service. Enforce exclusive single-writer access when admitting attempts and committing acceptance; reject simultaneous mutating invocation on one root. The bridge does not support competing candidates or advertise vNext fencing.

### Admission And Transition Table

Validate opt-in capability and pinned inputs before clients run. Proposal admission freezes exact current base/inventory, approved scope/surface/findings and transform policy before Editor invocation, without requiring exact-output attestations. Preliminary assessment then runs all decidable checks over retained materialized bytes. Acceptance admission freezes an explicit local request binding the existing proposal and adopted evidence; it never calls an Editor. Initial invalid admission yields `CONFIG_INVALID` without fabricated attempt evidence; post-admission binding failure rejects.

The following are internal processing states/outcomes. Pending evidence uses existing `PAUSED_DECISION`; no new global terminal-state enum is introduced.

| From | Condition | Required action |
|---|---|---|
| Unadmitted | Supported config and valid proposal bindings | Persist proposal admission before Editor/fixture/maintenance processing |
| Unadmitted | Missing, stale, incompatible or invalid bindings | `CONFIG_INVALID`; no Editor or authority change |
| Proposal admitted | Valid client/fixture output, or maintenance no-op | Persist raw bytes, materialize, retain normal-round evidence and immutable proposal |
| Proposal assessment | Resolvable correspondence or exact-effect attestations missing; no independent hard failure | `awaiting_operator_evidence`; `PAUSED_DECISION`; retain report and review request |
| Proposal assessment | All applicable checks pass without effect evidence, e.g. maintenance | Prepare empty-evidence no-op/maintenance acceptance request; still no authority until final acceptance |
| Proposal assessment | Known deterministic binding, hygiene, transform, permission, surface or preservation failure | `rejected`; `HALTED_ARTIFACT_INVALID`; zero automatic retries |
| Waiting/rejected proposal | Explicit new valid acceptance request; base remains current | Allocate new immutable acceptance admission, preserving previous reports |
| Acceptance assessment | Missing/conflicting mappings or evidence, stale base, or any deterministic failure | `rejected`; `HALTED_ARTIFACT_INVALID`; zero automatic retries |
| Acceptance assessment | Preservation passes but ordinary round gates do not | No marker/write; ordinary residual/stop handling on prior authoritative draft |
| Acceptance assessment | Preservation and ordinary gates pass | Persist final report, recheck base, atomically commit acceptance marker |
| Committed acceptance | Materialized bytes equal base | Accepted no-op; complete round once without version increment |
| Committed acceptance | Changed materialized bytes | Install checked bytes and advance lineage/history once |
| Committed acceptance | Interrupted mirror/history/scheduler updates | Revalidate and repair only from marker; no client, restamp or duplicate accounting |
| Any uncommitted stage | Typed transient failure | Preserve available evidence; technical handling below |

`awaiting_operator_evidence` means known output exists for explicit review, not that it is safe. Missing equivalence, addition, strengthening, deletion, weakening, supersession or a resolvable correspondence mapping may remain pending during proposal assessment if independent checks have no known failure. Uncomputable checks remain outstanding, never assumed passing. Invalid identities/references, conflicting supplied mappings, a known surface overrun, unsupported transforms and corruption are hard failures. Permission violations do not become harmless because the operator might later approve a different surface. New acceptance authorization may address an authorizable failure, but its fresh report must rerun all checks; it never rewrites the earlier rejection.

Pending reports map to `PAUSED_DECISION` with the immutable proposal/report references, exact affected units/effects, outstanding obligations and `next_action = review_proposal` or `submit_acceptance_request`. This safety pause applies even under ordinary `end_of_cycle`. Do not emit an artifact-validation failure or spend a model retry merely because proposal-stage evidence is absent. A submitted acceptance request with inadequate evidence, however, rejects deterministically. Pending evidence and rejection both leave draft authority and unresolved-issue state unchanged.

Deterministic terminal reports use `failure_type = preservation_violation`, the report Ref, failed categories/units, prior accepted marker/hash, raw/materialized Refs, `automatic_retries = 0` and the supported next action. Report all independent failures even if pending obligations also exist. Terminal draft pointers refer to prior accepted bytes or the initial seed, never pending/rejected materialization. A passing preliminary assessment does not complete a round.

### Technical Continuation And New Authorization

Transient failures are limited to a recorded client timeout; an explicitly parsed provider `rate_limit` or `service_unavailable` response; transport `ECONNRESET`, `ETIMEDOUT` or `ENETUNREACH`; or local `EINTR`, `EAGAIN`, `ENOSPC` or `EDQUOT` while persisting evidence. Unknown nonzero exits, malformed JSON, wrong schemas, permissions/authentication failures and all deterministic bridge checks are not transient by assumption. Persist the exact machine cause. Client timeouts retain `HALTED_CLIENT_TIMEOUT` and no automatic retry. Other transient client failures may consume at most the one remaining validation retry, under identical frozen input hashes. Local persistence failures have no automatic client retry; halt `HALTED_ARTIFACT_INVALID` with `failure_type = preservation_persistence_failure`, retaining every artifact that could be written.

For Phase 1, `resume --dry-run` MUST report a guarded technical attempt resumable only if it satisfies the existing role/scheduler/hash gates AND all frozen proposal-admission inputs still validate. Pending operator evidence is not a technical failure and is not resumed through this path. This adds typed transient bridge failures to the supported Phase 1 Editor artifact-recovery path; it does not make deterministic rejection resumable. Resume may change an explicit timeout/budget under existing precedence but MUST retain mode, capability, base, scope, surface, findings and transform policy. If recovering a local acceptance persistence interruption, also retain the exact request/evidence bindings and never invoke an Editor. A new client execution gets a new immutable attempt with predecessor reference. If complete valid outputs already exist after a persistence interruption, revalidate/reuse them instead of invoking the client again. Complete immutable admissions/reports are never overwritten; an incomplete acceptance may complete only with its frozen inputs. An already committed acceptance permits only idempotent reconciliation. Stale hashes reject, never silently refresh.

Generic Phase 2 timeout/technical resume remains unsupported in this bridge release. Report `resumable = false` and recommend explicit new admission from the last accepted draft; do not promise a new Phase 2 resume API. Reviewer technical recovery follows existing supported phases and must not fabricate or mutate a frozen Editor handoff.

Changed authorization is not technical resume. An explicit `preservation-bridge-acceptance-request-v1` selects the retained proposal, acceptance scope/surface/findings and operator evidence. The local acceptance operation validates and freezes a new acceptance admission in the same root when the exact proposal base remains authoritative, bridge/transform versions agree, and no committed repair is pending. The original round/phase/profile and normal-round evidence remain bound; a narrower acceptance surface cannot erase original serious findings or supply a new claim of their resolution. Scope changes and added finding attribution require independently valid same-base artifacts and approval. Acceptance itself makes no model call and consumes no additional model-review budget.

Preserve every prior admission, proposal, report and request. Different authorization allocates a new acceptance attempt; identical committed proposal replay returns its recorded result rather than accepting again. Pending or rejected proposals may be referenced by a later explicit request, but remain non-authoritative until the new acceptance passes. This is neither an automatic retry nor retrospective editing of the old outcome. A prior rejection report explains provenance; it does not prohibit a newly authorized effect or waive any current check.

If the authoritative base has changed, refuse acceptance of the old proposal. New content, transformation inputs or normal-round evidence require new proposal admission against current authority, not silent rebasing or substitution into an existing proposal. A new proposal in the same root must occupy a legal scheduler round/attempt under ordinary phase/budget rules; the acceptance operation cannot invent review results or bypass those rules. Fresh roots remain available for incompatible capabilities or a separately scoped job; they are not required merely to approve retained bytes. Cross-root imports remain new seed/proposal work under explicit provenance and the artifact leaf's reference rules, not transfer of an existing acceptance chain. No `--overwrite` may erase admitted bridge history.

### Acceptance And Downstream Consumers

One acceptance service MUST validate the request and immutable references, reproduce materialization/inventories, validate complete correspondence and evidence, check allowed surface and limits, and evaluate all normal round acceptance conditions. Persist the final report, recheck current base and previous accepted marker under single-writer exclusion, and atomically create the acceptance marker before any authoritative write. The marker chains to the prior accepted marker or explicit original seed. Publication consumes byte-identical materialized output, without normalization or restamping.

For round-bound proposals, successful local acceptance completes the original pending round exactly once, persists its canonical accepted summary from the frozen normal-round evidence with Orchestrator-owned final hashes, updates its issue/history/scheduler artifacts using existing rules, and stops without invoking a further Reviewer/Editor. Preserve any superseded top-level pause/failure report as historical evidence and refresh status from the committed result. Do not mark profiles clean from an Editor resolution claim. Status MUST distinguish accepted output needing ordinary review from Phase 1 stable or converged output. A crash while finishing the round is repair of a committed round, not an additional round or budget charge. Pending acceptance prevents scheduling the next mutating round. Phase 2 entry instead completes its maintenance operation once without inventing a numbered round or consuming a review budget. Ordinary in-process no-op/maintenance acceptance may return to its existing scheduler; the explicit local acceptance command stops after completing/repairing its selected operation.

No rejected, pending, incomplete, preliminary or merely `eligible` report may advance accepted hashes, clear residuals, become the next-round base, enter Phase 2, satisfy a declaration or reach strop. This holds under `apply=true, accepted=false`, soft budgets, budget extension, manual recovery and source-mismatch/non-converged overrides. Successful preservation never replaces Reviewer verification or the external source-hash guard.

For guarded roots, Phase 2 handoff/declaration and dry/live strop MUST validate the acceptance marker -> final acceptance report/admission -> request/evidence/proposal -> proposal admission/base/materialization chain, exact current bytes, normalized accepted hash and ordinary eligibility. A preliminary report or operator approval alone is insufficient. A mismatch refuses; dry strop never repairs or mutates. Source mismatch permission can relax only the external comparison. Legacy roots retain existing behavior and explicit `legacy_unguarded` labeling; earlier unpublished bridge formats cannot masquerade as qualified evidence.

## RESUME POLICY

The Orchestrator MAY resume only explicitly resumable terminal states. In this version, the supported resume paths are:

1. Phase 1 Reviewer timeout recovery.
2. Phase 1 Editor timeout recovery.
3. Phase 1 Editor artifact-validation recovery after validated Reviewer feedback.
4. Phase 1 budget-extension continuation after explicit operator request.

### Client Timeout Resume

The supported Phase 1 client-timeout resume paths are:

- `terminal_state = HALTED_CLIENT_TIMEOUT`
- `failure_type = client_timeout`
- `phase = phase_1`
- `client_role = reviewer | editor`
- for `client_role = reviewer`, the halted round has persisted `draft_before.md` but no validated `reviewer_feedback.json` is required
- for `client_role = editor`, the halted round already has validated `reviewer_feedback.json`

Resume MUST be hash-guarded. Before invoking the resumed client, the Orchestrator MUST verify that the current `spec.md` hash equals the halted artifact's `last_valid_draft_hash`. If the hash differs, resume MUST refuse unless a future explicit override is defined.

Resume MUST NOT rerun prior rounds. For a supported Reviewer-timeout path, resume MUST:
- read `rounds/run_state.json`
- read `rounds/artifact_validation_error.json`
- read the halted round's `draft_before.md`
- reconstruct Phase 1 scheduler state from completed prior rounds
- verify the scheduler's next profile matches the halted profile
- invoke the Reviewer for the halted round using the halted draft/context
- if Reviewer output validates, complete the normal round flow, including invoking the Editor when Reviewer feedback requires it
- start resumed Reviewer attempt numbering after the last recorded Reviewer attempt number
- preserve prior invalid Reviewer attempt artifacts, timeout telemetry, and prompt snapshots
- clear the top-level timeout terminal report only after the resumed round completes successfully
- update `run_state.json`, and when the round completes, update the normal round artifacts (`reviewer_feedback.json`, `editor_summary.json`, `draft_after.md`, `unresolved_issues.json`, `decision_points.json`, `spec.md`, and `spec.history.md` as applicable)

For a supported Editor-timeout path, resume MUST:
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

### Editor Artifact-Validation Resume

The supported Phase 1 Editor artifact-validation resume path is:

- `terminal_state = HALTED_ARTIFACT_INVALID`
- `failure_type = artifact_validation | client_error`
- `phase = phase_1`
- `client_role = editor`
- the halted round already has validated `reviewer_feedback.json`
- the current `spec.md` hash equals the halted artifact's `last_valid_draft_hash`

This path exists because the Reviewer handoff can be valid while the Editor response fails structured artifact validation after retry. In that case, rerunning the Reviewer would waste tokens and could change the already-validated feedback surface. Resume MUST reuse the persisted Reviewer feedback and retry only the Editor for the halted round.

For a supported Editor artifact-validation path, resume MUST follow the same scheduler reconstruction, Reviewer feedback validation, attempt-numbering, hash guard, artifact preservation, and successful-cleanup rules as the Editor-timeout path. It MUST NOT resume Reviewer artifact-validation failures, Phase 2 artifact-validation failures, hash mismatches, or arbitrary malformed run roots.

Resume does not imply hidden client session reuse. It uses persisted file artifacts as the replay source of truth.

When `review.mode = vertical`, client-timeout resume MUST reconstruct the vertical event stream rather than the horizontal profile scheduler. The reconstructed state MUST include completed profile review rounds in the current vertical cycle, the latest synthetic `profile: vertical` editor round, the per-profile clean/exhausted/verified-draft state, and any unedited feedback already collected in the interrupted cycle. If a Reviewer timeout occurs after one or more profile reviews in the same vertical cycle, `resume --continue` MUST carry those prior profile findings forward into the next synthetic `profile: vertical` consolidated Editor artifact rather than rerunning or dropping them.

For Reviewer-timeout resume idempotency, the halted round number is reused until a valid `reviewer_feedback.json` and the corresponding normal round completion artifacts are persisted for that round. Prompt snapshots, telemetry files, raw timeout diagnostics, invalid Reviewer responses, or partial attempt artifacts do not complete the resumed round. A repeated resume command after a partial resumed attempt MUST preserve those artifacts, reuse the halted round number, and choose the next attempt number as one plus the highest persisted attempt number for that halted Reviewer artifact. If the halted round later contains a valid Reviewer artifact and normal round completion artifacts, a repeated resume command MUST refuse unless the run remains resumable for a later terminal state.

For Editor-timeout and Editor artifact-validation resume idempotency, the halted round number is reused until a valid `editor_summary.json` and corresponding validated `draft_after.md` are persisted for that round. Prompt snapshots, telemetry files, raw timeout diagnostics, invalid Editor responses, or partial attempt artifacts do not complete the resumed round. A repeated resume command after a partial resumed attempt MUST preserve those artifacts, reuse the halted round number, and choose the next attempt number as one plus the highest persisted attempt number for that halted Editor artifact. If the halted round later contains a valid Editor artifact, a repeated resume command MUST refuse unless the run remains resumable for a later terminal state.

Attempt numbers are derived from persisted attempt artifacts in the halted `round-N/` directory. Authoritative attempt artifacts are filenames matching:

```text
<client_role>-<artifact_name>-attempt-<attempt_number>.json
```

where `client_role` is `reviewer` or `editor`, `artifact_name` is the expected client artifact, and `attempt_number` is a positive base-10 integer without leading zeros. The next attempt number is:

```text
max(valid attempt_number values for the same round, client_role, and artifact_name) + 1
```

If no valid attempt artifact exists, the next attempt number is `1`. Malformed attempt filenames are preserved as diagnostics but ignored for attempt-number calculation. Duplicate valid attempt numbers for the same round/client/artifact are artifact-invalid unless one file is the canonical validated artifact and the other is explicitly named as raw diagnostic output.

Resume MUST inherit persisted effective run configuration from the halted run's `run_state.json` when present. At minimum, resume MUST inherit `review_profile_budgets`, `convergence_profile_budgets`, `decision_points`, and `timeouts` from `effective_run_config`. For compatibility with older runs, resume MAY fall back to top-level `run_state.json` `review_profile_budgets`, `convergence_profile_budgets`, and `timeouts` when `effective_run_config` is absent. Explicit CLI overrides supplied to the resume command take precedence over inherited run-state values.

By default, resume recovers only the halted round and then stops. If invoked with `--continue`, the Orchestrator MAY continue Phase 1 after the recovered round succeeds. `resume --continue` MUST:
- use the reconstructed scheduler state from completed prior rounds plus the recovered round result
- start subsequent rounds at the next round number
- preserve all prior round artifacts and timeout diagnostics
- continue applying the normal Phase 1 scheduling algorithm, profile budgets, validation rules, timeout rules, oscillation checks, and halting conditions
- halt normally on `PHASE_1_STABLE`, `TARGET_NOT_REACHED`, `HALTED_CLIENT_TIMEOUT`, `HALTED_ARTIFACT_INVALID`, `HALTED_CONFLICT`, or `HALTED_OSCILLATION`
- update `run_state.json` and `spec.history.md` after each continued round

`resume --continue` MUST NOT retroactively alter prior rounds or restart the profile sequence. It MUST rerun the halted round's Reviewer only for an explicitly supported Reviewer-timeout resume where no valid `reviewer_feedback.json` was persisted.

`resume --dry-run` MUST validate resume eligibility without invoking any client. It MUST perform the same terminal-state, failure-type, role, phase, hash, scheduler, and role-specific artifact checks as live resume. It MUST report at minimum:
- whether the run is resumable
- halted `round_number`
- halted `profile`
- `phase`
- `client_role`
- `failure_type`
- current and expected draft hashes
- next resumed client attempt number
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

For `review.mode: horizontal`, budget-extension resume MUST reconstruct per-profile `rounds_used` from prior round artifacts. For each profile, the resumed effective budget MUST be:

```text
max(previous_effective_budget, reconstructed_rounds_used) + added_rounds_per_profile
```

This rule ensures a budget extension always creates additional capacity even when a previous closeout or verification pass consumed rounds beyond the explicit configured value.

For `review.mode: vertical`, budget-extension resume MUST replay the prior vertical event stream to reconstruct:
- per-profile `rounds_used`
- per-profile clean/exhausted/residual status
- `last_accepted_draft_hash`
- `seen_draft_hashes`
- latest unresolved issues from the most recent synthetic `profile: vertical` editor round

After reconstruction, vertical budget-extension resume MUST increase each effective Phase 1 profile review budget by the operator-requested extension amount, then recompute profile eligibility from reconstructed `rounds_used` and the new effective budgets. A profile is eligible in resumed vertical cycles when `rounds_used < new_effective_budget`, regardless of whether it previously ended in exhausted or residual status. A profile is ineligible only when it has no remaining review capacity under the new effective budget or a separate terminal guard blocks continuation.

Each appended vertical cycle MUST:
- run each eligible profile review pass against the same draft at the start of that cycle
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

`event_id` MUST be deterministic:

```text
event_id = "bxe_" + first_16_hex_chars(SHA256(canonical_json({
  "phase": phase,
  "previous_terminal_state": previous_terminal_state,
  "previous_current_round": previous_current_round,
  "previous_current_draft_hash": current_draft_hash,
  "previous_review_profile_budgets": previous_review_profile_budgets,
  "new_review_profile_budgets": new_review_profile_budgets,
  "added_rounds_per_profile": added_rounds_per_profile,
  "reason": reason,
  "extension_ordinal": extension_ordinal
})))
```

`extension_ordinal` is one plus the number of prior budget-extension events already persisted for the run. `generated_at` MUST NOT participate in `event_id`.

If a budget-extension event with the same `event_id` already exists and no appended client round has been persisted after that event, a repeated resume command MUST reuse the existing event and continue without appending a duplicate event. If appended rounds already exist after the event, the repeated resume command MUST reconstruct from the latest persisted round and continue normally or refuse if the run is no longer resumable.

An appended client round is considered persisted only when its `round-N/` directory contains a schema-valid `profile_used.yaml` and the required validated reviewer/editor artifacts for that round kind. Prompt snapshots, telemetry files, raw invalid responses, or partial attempt diagnostics without a valid round artifact set are partial attempt artifacts, not completed appended rounds. A repeated resume command after such a partial attempt MUST preserve the partial artifacts, reuse the existing budget-extension event, reuse the same next round number, and continue with the next deterministic attempt number for the interrupted client role.

Budget-extension events MUST be preserved across subsequent `run_state.json` rewrites during the resumed continuation.

Budget-extension resume is a continuation of the same run, not a new run. Prior terminal reports remain historical artifacts unless a later run-state field supersedes their operational interpretation. Operators SHOULD treat `run_state.json` as the current status source of truth and preserved terminal reports as historical checkpoints.

Read-only status MUST treat a terminal report as active only when the report's `terminal_state`, `round_number`, and `draft_hash` or `last_draft_hash` match the current `run_state.json` terminal state, current round, and current draft hash. If any of those fields conflict after a valid continuation advances the run, status MUST classify the report as historical or stale rather than present it as the active terminal report, and SHOULD emit an operator-visible stale-terminal-report warning.

Read-only status MUST prefer superseding `run_state.json` terminal state over stale historical terminal reports. If `run_state.json.terminal_state = PHASE_1_STABLE` and `ready_for_phase_2 = true`, status MUST report `current_draft_status = phase_1_stable` even if a prior `technical_failure_report.json` remains in `/rounds/`.

Read-only status MUST compare the current run-root `spec.md` hash with `run_state.json.current_draft_hash` when both are available. If they differ, status MUST emit an operator-visible warning that `run_state.json` remains the authoritative lineage hash until the root draft is reconciled. The warning MUST include both hashes. This warning is informational for diagnosis, but resume, Phase 2 promotion, and apply-back hash guards MUST continue to enforce their own existing lineage checks.

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

State names describe conceptual Orchestrator phases. Persisted `terminal_state` values describe externally observable run outcomes. `TECHNICAL_STABLE` is the conceptual state reached when Phase 1 is complete; `PHASE_1_STABLE` is the persisted terminal/run-state value for a Phase 1-only run that stops at that boundary with `ready_for_phase_2 = true`.

INITIALIZED -> TECHNICAL_REVIEW

INITIALIZED -> CONFIG_INVALID (on preflight configuration validation failure)

TECHNICAL_REVIEW -> TECHNICAL_REVISION
TECHNICAL_REVISION -> TECHNICAL_REVIEW

TECHNICAL_REVIEW -> TECHNICAL_STABLE / PHASE_1_STABLE (if accepted draft and all non-skipped Phase 1 profiles have valid clean status; persist `terminal_state = PHASE_1_STABLE` when the run stops before entering Phase 2)

TECHNICAL_STABLE -> CONVERGENCE_REVIEW (after Phase 2 entry version promotion)

CONVERGENCE_REVIEW -> CONVERGENCE_REVISION (if any in-scope unresolved feedback item targets `spec.md` or another non-declaration source artifact)
CONVERGENCE_REVIEW -> DECLARATION_REVISION (if all in-scope unresolved feedback items target only `convergence_declaration.md`, `rubric_gaps.json`, `unresolved_issues.json`, or other declaration-evaluation artifacts)

CONVERGENCE_REVISION -> CONVERGENCE_REVIEW
DECLARATION_REVISION -> CONVERGENCE_REVIEW

CONVERGENCE_REVIEW -> CONVERGED (if clean convergence is achieved: declaration accepted, target matrix satisfied, zero blocking issues or gaps, and every required distinct Phase 2 profile clean on the current unmodified draft lineage)

ANY STATE -> HALTED_CONFLICT (on blocker-level conflict escalation)
ANY STATE -> HALTED_OSCILLATION (on oscillation stop)
ANY STATE -> HALTED_ARTIFACT_INVALID (on exhausted artifact validation retry)
ANY STATE -> HALTED_CLIENT_TIMEOUT (on client invocation timeout)
ANY STATE -> PAUSED_DECISION (on decision intervention required)
TECHNICAL_REVIEW -> PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS (when soft Phase 1 profile sweep completes with residual blocker/major or oscillation status)
ANY STATE -> TARGET_NOT_REACHED (on profile-level budget exhaustion before the required clean/stable condition is verified)

If both `CONVERGENCE_REVISION` and `DECLARATION_REVISION` guards are true for the same review, `CONVERGENCE_REVISION` takes precedence because source-spec changes may invalidate declaration artifacts.

---

## Verified-Promotion Source Write And Readback

The following six requirements publish the operator-ratified internal M4 policy
of 2026-09-29 for a new explicitly pinned consumer. Source-write capability is
separate from choosing V mode and remains subject to full release qualification.

1. **Eligibility.** Limit the new consumer to explicitly pinned
   `verified_promotion` runs with a complete, current `CONVERGED` closeout and
   no unresolved blocking decisions, pending candidate work, orphan recovery or
   materialization repair. Reconstruct current verified pointer, map, inventory,
   seed or promoted candidate, final verification, intent/event and convergence
   evidence. A legitimate converged seed is eligible without inventing a
   candidate. Rejected historical candidates remain visible but do not by
   themselves block a later valid converged result. Reviewer-only, proposal-only,
   focused-only and non-converged outcomes do not gain write permission.
2. **Exact source and approval.** Require both descriptor source fields and an
   explicit approval bound to the reviewed source path, exact source SHA-256,
   current verified pointer, candidate bytes and convergence evidence. The source
   hash means SHA-256 of the exact original bytes under this new contract; do not
   reinterpret old consumers. Require an absolute descriptor source path for this
   first consumer; relative paths cannot acquire a target from the invocation's
   working directory. Require the source to match that original binding, including
   byte-level line-ending changes. No source-mismatch or non-converged override,
   rebasing, target substitution or automatic approval refresh. A null binding
   remains inspection-only. Source drift requires a separately authorized new run.
3. **Single-source operating boundary.** One host, one existing regular source
   file outside the run root, on the same qualified local APFS filesystem.
   Require the operator to ensure exclusive source access throughout review,
   write and unresolved recovery: no concurrent editor, sync agent or second run
   targeting it. Refuse detected path/device/parent identity drift, symlinks and
   multiply linked targets. Hold the run's D8 fence through revalidation and
   publication; it does not itself fence external writers. Distributed writers,
   cross-run source coordination, bundles and filesystem relocation remain
   unsupported. This restriction is explicit, not a claim that a hash check
   prevents an arbitrary process from racing the replacement.
4. **Review and commit.** Read-only assessment returns the exact selected bytes,
   diff, evidence references and blockers without repairing or publishing anything.
   A write consumes the exact approved assessment and revalidates it under D8.
   Durably retain source preimage, approved request and write intent before
   touching the source. Prepare exact verified bytes in a same-directory temporary,
   preserve the admitted source file's permission bits, recheck source bytes and
   physical identity, and atomically replace the one source path. Repeat the
   qualified file/directory durability barriers before publishing a completion
   receipt. Metadata that the adapter cannot preserve must cause refusal before
   replacement; it must not silently discard source metadata. The source
   replacement is the external commit point; the run receipt records its outcome.
   There is no atomic transaction spanning the source and the run receipt.
5. **Uncertainty and recovery.** Failure after replacement is attempted means
   `outcome_requires_reconciliation`; release ownership and preserve evidence.
   Do not roll back, rewrite, choose a new candidate or claim noncommit from a
   missing receipt. Reacquire ownership and read the exact approved source:
   desired bytes allow durability-barrier replay and receipt recovery without
   rewriting; original bytes mean the desired update is not currently visible
   and recovery performs no source write; any third value, missing file or
   contradictory identity requires operator attention without overwrite. Observing
   original bytes after an uncertain attempt does not prove replacement never
   happened. A further attempt requires an explicit apply invocation and complete
   current revalidation. Completed evidence may be reported historically after
   source drift, but never implies that the source still contains those bytes.
   If the run pointer advances, recovery may reconcile the old recorded outcome
   but cannot apply its old approval to new bytes. If before and desired bytes
   are identical, record an approved no-op with no replacement. Reentry after a
   completed write returns its bound result without a second write.
6. **Compatibility and delivery.** Implement the internal reader, approved
   write, recovery and operator result together behind new consumer pins. Do not
   route vNext through the legacy executor, change shipped suites, rewrite old
   closeouts, grant new model work or alter legacy/bridge overrides. Reports keep
   lineage validity, convergence, source-match eligibility, approval and actual
   write outcome separate. Qualification used only disposable fixture sources.
   Public support is limited to the advertised qualified suite; a real source
   write still requires separate exact approval and exclusive source access.

### Source assessment, write and historical recovery

These are distinct subcases of `strop` / `apply-back`. Do not run fresh-write
eligibility as a shared precondition for read-only diagnostics or historical
recovery. Ordinary config/suite and lineage validation still applies; historical
recovery does not excuse corrupt authority.

| Operation | Eligibility and evidence | Result / permitted effect |
| --- | --- | --- |
| Default read-only review/status | Inspect the V root and descriptor source binding; current convergence is evaluated, not required to produce diagnostics | Return an eligible assessment plus diff, or blockers with `assessment: null`. A retained intent also returns its historical readback status; no repair, new approval or source write. |
| New `--apply --approve` | Exact canonical assessment file/hash, current complete convergence, current verified pointer and unchanged descriptor-bound source; explicit exclusive access | Revalidate under D8 and perform only the approved M4 write/no-op. A different retained intent refuses; the same intent returns its retained result/recovery state without another write. |
| `--apply --approve --retry-apply` | Retained intent reports `apply_required`; same exact assessment/hash plus all current new-write eligibility and exclusive-access checks | Explicit further attempt, never automatic recovery or approval refresh. Stale pointer, convergence, source bytes or physical identity refuse a new write. |
| `--recover --exclusive-source-access` | Valid retained intent and its historical approved pointer/draft/convergence, with exact source identity/readback checks | Reconcile durability and receipt without replacing the source. Current-pointer advancement or loss of current new-write eligibility alone must not block historical reconciliation. Original bytes return `apply_required`; third/missing bytes or identity conflict require attention; completed evidence after drift stays historical. |

`--recover` cannot be combined with `--apply`, `--approve`, `--retry-apply`,
`--approval` or `--approval-hash`; it uses the retained intent rather than a fresh
approval file. No retained intent means `not_started`, with no source write or
receipt fabricated. New writes always require the exact descriptor source;
legacy mismatch/non-converged overrides remain invalid. Exclusivity is the
operator's assertion of actual exclusive source access throughout review, write
and unresolved recovery, not a lock acquired over other editors or runs.

Read-only stdout is the **review-result envelope**, not the approval subject.
It exposes `eligible`, `apply_back_permitted` (false during review), `blockers`
and `assessment`. Eligible review also includes `diff`; existing-intent review
includes `recovery`. For an ineligible review `assessment` is null; a source-less
descriptor yields blockers rather than a write target. The adapter preserves
these existing owner-result distinctions without adding fields to the frozen
`vnext-apply-back-review-v1` assessment schema. Referenced verified bytes and
evidence remain inspectable through their exact retained paths/hashes.

The approval subject is only the non-null `assessment` object. Save its D6
canonical JSON bytes as a separate file outside the run root. `--approval-hash`
is lowercase SHA-256 of those exact file bytes, not the envelope, diff, a pretty
JSON rendering or a newline-terminated variant. The adapter rejects a wrong
digest, noncanonical bytes, duplicate keys, an envelope submitted as assessment,
or a null assessment before the write owner runs. It validates the unchanged
assessment schema and then passes the packet to the existing M4 owner, which
revalidates current approval under D8.

For example, after the operator saves read-only stdout to `review.json` outside
the root, this local extraction creates `approval.json` without overwriting a
file and prints the value for `--approval-hash` (both paths must be outside the
run root):

```python
from pathlib import Path
from whetstone.vnext_contracts import canonical_json_bytes, decode_json, sha256_bytes

review = decode_json(Path("review.json").read_bytes())
if review.get("eligible") is not True or review.get("assessment") is None:
    raise ValueError("review has no approvable assessment")
raw = canonical_json_bytes(review["assessment"])
with Path("approval.json").open("xb") as output:
    output.write(raw)
print(sha256_bytes(raw))
```

Saving/extracting the packet grants no write permission. The operator must still
review the diff and evidence and explicitly invoke `--apply --approve` with the
assessment file/hash and exclusive-access acknowledgement. Read-only strop itself
does not write either file or publish/repair a run artifact.
