# Phase 2 correction failure reporting

Implemented and validated from `2c01979` (2026-09-27), uncommitted. The user
authorized this bounded implementation after the Reviewer failure milestone.
The six acceptance requirements below are covered at this scope; general Phase 2
and 18.8 completion are not claimed. No commit, push, public activation or external
transmission is included.

## Authority and bounded scope

The [D7 transition table and retry rules](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#processing-transition-table)
define Editor/Verifier technical halts, assembly failure without registration,
deterministic rejection, semantic rejection and concrete operator-choice rejection.
The [Phase 2 failure requirements](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md#phase-2-failure-handling)
require the companion report with current verified bytes, actual review budgets,
residual findings and truthful declaration verification status. No product-policy
choice is required to report these existing outcomes.

The existing shared Editor/Verifier journals retain their historical `phase1`
discriminator; the separately bound Phase 2 review, consumption and round establish
phase provenance. This is explicitly retained by the Phase 2 round contract.
No new attempt allocator, client executor or candidate decision owner is introduced.

The legacy artifact-error schema lists only Reviewer/Editor. A separately pinned
vNext correction diagnostic adds an explicit Verifier role and null client for
non-client assembly/deterministic failures. The legacy schema is unchanged.

## Fixed acceptance boundary

1. Reproduce first/later original Phase 2 correction provenance under D8, including
   current pointer, entry, immutable configuration/rubric, consumed review, advice,
   round, exact journal and effective committed candidate decision.
2. Publish immutable evidence for technical client halts, actual assembly failure,
   deterministic rejection, semantic rejection and concrete operator-choice rejection.
   Preserve the exact cause; no candidate before registration and no verdict from
   incomplete semantic output. A prepared decision retains its recovery gate.
3. Recover owned report projections and namespaced current status separately. Retain
   historical failures after existing explicit continuation, later decision and
   promotion; reject unowned root report bytes.
4. Coordinate Reviewer/correction report ownership in phase order; a committed final
   exhaustion report takes precedence. Recovery after uncertain final state writes
   repeats durability barriers and stops without clients.
5. Preserve existing attempt limits, finality, budget accounting and authority.
   This report owner advertises no technical resume. Existing component APIs keep
   their independent continuation gates; no Phase 2 followup admission is added.
6. Validate focused successes, failures, source drift, interrupted publication,
   projection/state acknowledgement loss, historical replay and compatibility.

## Outcomes preserved

| Existing evidence | Reported terminal | Candidate effect |
| --- | --- | --- |
| Editor or Verifier timeout | `HALTED_CLIENT_TIMEOUT` | No new candidate or semantic verdict. |
| Transport/interrupted invocation, invalid proposal/semantic result, exhausted shape handling | `HALTED_ARTIFACT_INVALID` | Preserve the last committed disposition. |
| Reproduced assembly failure | `HALTED_ARTIFACT_INVALID` | No fabricated registration or rejection. |
| Committed deterministic rejection | `HALTED_ARTIFACT_INVALID`, `vnext_preservation_failed` | Candidate remains finally rejected. |
| Committed semantic rejection | `TARGET_NOT_REACHED`, `vnext_semantic_rejected` | Candidate remains finally rejected. |
| Concrete committed operator-choice rejection | `PAUSED_DECISION`, `vnext_operator_decision_required` | Preserve bound outstanding decisions; candidate remains finally rejected. |
| Valid retained output or an available shape retry | No new failure report | Existing component owner retains its next gate. |
| Prepared candidate decision | Recovery gate, no intended final verdict | Only the committed disposition is effective. |

## Internal operator sequence

After existing `request`, `register` or `verify` work:

Status may identify a terminal cause before publication; `committed` and
`publication_required` distinguish that observation from durable report evidence.

- `phase2_correction_failure_status()` reads evidence without writing.
- `publish_phase2_correction_failure()` publishes/reconciles failure evidence only.
- `reconcile_phase2_correction_failure_state()` recovers root projections and
  `vnext_phase2_correction_failure`, then stops.

A successful existing continuation makes earlier failure historical. Reconcile
current status separately. Root diagnostics may remain as historical evidence when
a later outcome does not need a new artifact error; derive current status from
validated evidence, never the mere presence of an old root report. Final rejected candidates cannot resume verification.
No report grants a new transaction, repair, review, promotion or source apply-back.

## Validation and remaining work

The [evidence record](audits/VNEXT_18_8_PHASE2_CORRECTION_FAILURE.json) credits
69 distinct passing methods across 71 executions: 12 new integration methods and
57 existing compatibility/contract/evaluation/declaration methods. Eight new
methods passed on delivered runtime/contract bytes, covering both technical roles,
concrete operator rejection, original authority and source barriers, interrupted
invocations/publication, uncertain report/state acknowledgements, fresh-process
recovery, promotion, cross-role projection ownership and both final closeout outcomes.

Four other new methods retain their initial-source passing results; the 57
compatibility methods passed before final opt-in-only changes. These are scoped
cross-snapshot results, not a claim that all 69 methods reran on delivered bytes.
The evidence record names the source changes and individual methods. It excludes
exploratory failures, interrupted runs and duplicate smoke/diagnostic checks.
All 551 delivered manifest hashes match, `git diff --check` passes, the index is
empty, frozen suite 1 is unchanged, and all public qualification maps remain empty.
Raw logs and source manifests remain in the ignored local directory
`rounds/vnext-18-8-phase2-correction-failure-001/`. All four 18.8 tasks and 18.9 remain
incomplete.

These are explicit internal reporting APIs, not automatic scheduler dispatch or
a newly qualified continuation route. The bounded owner covers original correction
transactions in the standard horizontal, unversioned Phase 2 path. Existing
component APIs retain their own continuation gates. No genuine product or authority
decision blocks this reporting slice.

Remaining implementation includes conflict/oscillation/rubric handling, actual
declaration repair, operator followups and new repair admission, broader scheduler
modes, version maintenance, and strop/readback. Release qualification remains
separate. The next proposed boundary is to reconcile existing Phase 2 conflict and
oscillation evidence with the specified reporting and precedence rules. Establish
that boundary before coding; bring back one concrete decision if resolution policy
is unspecified. This handoff does not authorize that next implementation.

Validation uses local scripted clients, injected faults and fresh-process recovery
on macOS/APFS. It does not establish live-provider behavior, physical power-loss or
process-kill-during-write recovery, full-repository qualification, or performance
qualification. Historical replay remains computationally expensive. Corrupt source
authority and unsafe persistence errors propagate rather than fabricating a durable
failure report.
