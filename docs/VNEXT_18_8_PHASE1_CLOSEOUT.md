# 18.8 bounded horizontal acceptance and terminal closeout

Date: 2026-09-20. Starting checkpoint: `be4297e`.

`VerifiedRun.phase1_closeout()` now evaluates accepted-draft evidence and the
eligible Phase 1 terminal without writing. `finish_phase1()` publishes the exact
terminal and its bound evidence under the existing D8 fence. Both require a
separately pinned, unactivated consuming contract.

This implements the next bounded step after the
[profile-status slice](VNEXT_18_8_PHASE1_STATUS.md). All four 18.8 plan tasks remain
incomplete: these are internal horizontal-path APIs, not the complete scheduler,
operator-status/run-state, Phase 2 or apply-back integrations.

## Acceptance and terminal behavior

The [consumer](../src/whetstone/vnext_verified_phase1_closeout.py) follows the
candidate/D7 authority rules and the scheduler's separate definitions of global
acceptance and profile cleanliness. It replays actual canonical Reviewer receipts
against proven committed lineage. For each configured profile, only the latest
completed review on the exact current pointer contributes acceptance evidence.

| Evidence | Result |
| --- | --- |
| Missing current-pointer reviews | Acceptance is not established; missing profiles remain explicit. Old-pointer reviews and verification alone cannot discharge this debt. |
| A major/blocker anywhere in those reviews | Acceptance is not established, including findings outside profile focus. Exact round/feedback identities remain visible. |
| All profiles reviewed, no global major/blocker | Global acceptance is established for this bounded evidence; eligible terminal evaluation still requires the existing sequence gate. |
| Review, finding admission or technical recovery pending | No terminal report is fabricated. Existing recovery/work gates retain precedence. |
| Review complete, global acceptance and all profiles clean | `PHASE_1_STABLE` terminal report. |
| Hard budget exhaustion without stability, or profile-clean completion with global debt | `TARGET_NOT_REACHED` with the explicit budget or global-acceptance reason. |

Promotion does not establish acceptance. It changes the exact pointer and requires
fresh review evidence under the remaining original budgets. Candidate verification
or a candidate-local promotion event cannot substitute for a committed promotion.
The report projects latest registration separately from current authority, uses
the pointer-bound promotion event for a promoted candidate, and retains historical
rejections. Unresolved current decisions cannot be bypassed by closeout.

`accepted = false` means not established by this evidence, not a candidate
rejection. Neither acceptance nor the terminal report enables Phase 2 execution,
convergence, version stamping or source apply-back.

## Publication and recovery

The [new algorithm](../contracts/algorithms/vnext_verified_phase1_closeout_v1.md)
and [evidence schema](../contracts/schemas/vnext_verified_phase1_closeout_v1.schema.json)
leave existing frozen contracts unchanged. They must be explicitly included in a
test/consuming suite; the shipping qualification maps remain empty.

Publication uses two immutable, content-addressed artifacts:

1. The existing `terminal-report-v2` envelope under `rounds/terminal_reports/`.
2. A closeout evidence record under `rounds/phase1_closeouts/`, binding the job,
   exact current pointer snapshot, ordered original review receipts/bases,
   acceptance findings, missing/unclean profiles and report hash.

The evidence record is the closeout publication commit. It is not a new draft
authority pointer. Reentry derives the same bytes and paths without timestamps,
client calls or new review/candidate/decision/promotion ordinals. Earlier reports
are preserved; cached state and directory ordering never choose the current
terminal.

Before publishing, finishing repeats current-pointer/mirror barriers through the
work owner and the Reviewer journals' receipt/source barriers. A report-only
prefix is recovered by exact replay. Matching visible final evidence still
requires successful barrier replay after a lost acknowledgement. `materialized`
describes matching visible files, not certainty about a previous write's durability.
Missing report content after the evidence commit, conflicting bytes or damaged
source evidence refuse without reconstructing committed content.

If mirrors need repair, `finish_phase1()` performs the existing separate
materialization-only recovery and ends. A second explicit call can close the phase.
Inspection never writes; no legacy terminal/readiness/accepted-hash fields are
materialized by this slice.

## Validation and limits

**All 36 methods passed on their first runs with no skips or fixes:** six new
closeout methods in 73.820 seconds and 30 existing regressions in 228.507 seconds.
The recorded runtime/contract/test/spec snapshot matches both invocations.

The [validation record](audits/VNEXT_18_8_PHASE1_CLOSEOUT.json) binds commands,
method identities, logs and the source snapshot. New tests cover complete seed
review, missing-profile refusal, global debt despite profile cleanliness,
post-promotion review/budget outcomes, exact committed-event reporting, publication
prefixes, visible final-write acknowledgement loss, source-barrier failure,
corrupt committed targets, contract refusal and separate mirror recovery.
Existing profile-status, V review and scheduler tests are the regression cohort.

The tests use fictional clients and process-local suites on macOS/APFS. Injected
publication exceptions establish the stated caller/replay boundaries; they do not
add physical power-loss, syscall-permutation, distributed-writer or live-provider
qualification. This is not a full product regression. Raw evidence remains under
ignored `rounds/vnext-18-8-closeout-001/`.

## Handoff

Next bounded integration: connect this evidence-derived terminal selection to the
operator status/run-state projection, including stale historical reports and
recovery-only reentry. Keep Phase 2 capability distinct from a Phase 1 result and
bind any derived state to current verified lineage.

Still remaining in 18.8: the other focused/vertical/retry/resume/budget-extension
paths, version/history/declaration consumers, Phase 2 and convergence, strop/readback
eligibility, and complete terminal handling across those paths. Rejected-parent
follow-up compositions have earlier semantic/promotion evidence; exhaustive new
terminal projections over those compositions are not claimed by this cohort.

18.9 release qualification, shipping-suite publication, live soak and activation
remain deferred. Legacy/bridge runtime bytes and shipping maps are unchanged.
No external providers, public modes, push or external specification apply-back
are included.
