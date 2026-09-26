# Bounded Phase 2 final-review termination milestone

Started 2026-09-26 from clean checkpoint `804a6f0`. The authorized milestone covers
the consumed final scheduled v3 review in the current standard, horizontal,
unchanged-version V path. Reuse `phase2_closeout()`, `finish_phase2()` and
`reconcile_phase2_state()`; do not add another independently operated journal.

## Acceptance matrix fixed before implementation

Authority: [scheduler ordering and Phase 2 completion](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md)
and [Phase 2 failure handling](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md#phase-2-failure-handling).
The line references below identify the source passages examined when the matrix
was fixed; these authoritative specifications are unchanged by this milestone.

| Case | Authority and expected behavior | Verification |
| --- | --- | --- |
| Clean final review at its budget limit | Scheduler lines 18–24, 358–400 and 458: normal acceptance wins; existing CONVERGED path and separate state recovery remain intact | Clean end-to-end journey |
| Serious final findings, final ordered step has spent its budget | Scheduler lines 389–406; Phase 2 failure handling lines 24–78: TARGET_NOT_REACHED plus complete convergence failure report, unresolved findings preserved | Failure publication, status and recovery journey |
| Serious final findings with unused final-step budget | Approved reporting decision: unsupported repair is blocked work, not exhaustion | No terminal or writes; budget unchanged |
| Authority/rubric/oscillation signals alongside exhaustion | Scheduler maintenance and D7 preconditions precede budget selection; unsupported resolution cannot be bypassed | Refuse budget terminal; preserve all blocking reasons |
| Incomplete final request/result/consumption or missing reconciliation | D7 validates evidence before terminal selection | Preserve existing prerequisite gate; no invented timeout, decision or failure terminal |
| Altered sources, pointer or committed dependencies | D8 and D7: invalid evidence is a failed precondition | Refusal before terminal/state writes |
| Publication interrupted before/after report or commit writes | Existing immutable closeout publication under D8 | Exact-prefix recovery, same evidence, no clients or duplicate review credit |
| Mirror/state writes interrupted, including lost final acknowledgement | D8 recovery-only reentry | Repeat barriers, complete projection, preserve legacy state and stop |
| Forged or conflicting mutable mirrors/state | Committed evidence owns status; unowned report bytes are preserved | Cache cannot grant acceptance; conflicting mirror refuses |
| Fresh-process reopen and older suite | Bound suite and immutable inputs remain authoritative | Fresh-process readback/recovery; opt-in failure extension does not upgrade older suites |

This table defines the completion claim for this milestone. It does not cover
earlier client-failure terminals, conflict/oscillation report publication, operator
decision resolution, rubric-gap resolution, final-review corrections, new review
selection, other scheduler modes, version maintenance, external apply-back or
18.9 activation. Such paths remain explicit gates. The milestone must not be
described as complete general Phase 2 termination or complete 18.8.

## Implementation and evidence

The bounded milestone is implemented and validated; the user subsequently authorized a local checkpoint. The new pinned termination algorithm and failure
closeout schema extend the existing three closeout APIs. Existing suite pins and
receipts remain unchanged; the extension also requires finding reconciliation.

Before first publication, eligible exhaustion inspection returns
`failure_report_publication_required`, the proposed terminal and remaining budget
zero, without a fabricated timestamp or commit reference. `finish_phase2()` runs
under the existing D8 fence and publishes the immutable convergence failure report,
terminal-report-v2 and one closeout commit, in that order. The request-hash directory
is shared with the success path so the same evidence cannot commit both outcomes.

The failure report uses the existing convergence-failure schema. It records the
current verified draft, exact reviewed declaration/rubric, unresolved serious
findings, ordered profile budgets and latest current-lineage verification, plus the
original Phase 1 accepted draft hash. This distinguishes later verified promotion
from Phase 1 acceptance. Its final Reviewer status is rejected. The declaration
supplied to the Reviewer remains immutable historical input; its original candidate
status/counts are not rewritten or presented as repaired. The failure commit binds
that declaration and the post-review reconciliation/issues. Recommendations are
reported only; no client, Editor, candidate, extra review or automatic resume follows.

`generated_at` is the publication invocation's UTC timestamp. Recovery retains that
single metadata field from an already-written validated report and reproduces all
other fields from sources. Exact commit bindings prevent substitution after commit.
No new timestamp allocation artifact or separately operated journal is introduced.

`reconcile_phase2_state()` repeats source/report/commit barriers, create-only
publishes `rounds/convergence_failure_report.json`, then recovers the existing
`vnext_phase2_closeout` run-state reference. It preserves legacy fields and any
original declaration. The materialization whitelist stays frozen. Conflicting
unowned failure-report bytes refuse; a namespaced cache cannot confer authority.
Failure has `accepted: false` and `phase_complete: false`; `halt_complete: true`
requires both matching report mirror and state. A lost final acknowledgement repeats
the barriers and ends after recovery. The clean CONVERGED path remains unchanged.

All competing reconciliation reasons remain visible. A complete final review
establishes that its client invocation/result completed validly; an earlier recovered
technical attempt is not reinterpreted as a current timeout. Pending requests or
unconsumed results remain prerequisites. Authority/rubric/oscillation signals cannot
be converted into budget exhaustion; this milestone does not manufacture their
operator decisions, repairs or higher-priority terminal artifacts.

The acceptance matrix is covered by **72 distinct passing test methods across 73
successful executions**, mapped to exact commands, logs and source hashes in
[the evidence record](audits/VNEXT_18_8_PHASE2_TERMINATION.json):

- Eight new terminal/recovery journeys, 19 existing closeout/finding/blocked-report
  regressions and 44 contract/declaration/evaluation checks passed before the final
  report-summary correction (71 distinct methods).
- The final specification cross-check found that the last Reviewer summary must
  list only in-scope major/blocker feedback IDs. The new module's filter was
  corrected. A new mixed-feedback journey and the existing full failure
  publication/recovery journey passed on the delivered bytes, including fresh
  subprocess readback. All findings remain preserved in reconciliation; summary
  filtering does not resolve them. The other 70 methods were not rerun after this
  isolated filter/test change.
- Earlier fixture failures are retained separately and excluded from the passing
  count: a stale draft hash after promotion, missing admission advice, a display
  anchor instead of the canonical source anchor, and duplicated oscillation
  identities in the first mixed-feedback fixture. Runtime rejection was retained;
  the fixture inputs were corrected.

Raw evidence is under `rounds/vnext-18-8-phase2-termination-001/`. All 544 source
snapshot hashes match the delivered manifest. Frozen suite 1 is unchanged, all
public qualification maps remain empty, `git diff --check` passes, and the index
is empty at baseline `804a6f0`.

Verification used scripted clients on macOS/APFS, injected source/write/barrier
failures and fresh-process reopening. It does not claim a full repository or new
legacy/bridge campaign, live-provider qualification, physical power-loss testing,
or process termination during a write. The inherited bound-rubric package remains
limited to the existing path; general rubric maintenance is unqualified.

## Remaining work and next boundary

General Phase 2 halt/failure handling is still open. The next proposed bounded
milestone is the earlier client-failure terminal/report lifecycle and explicit
technical continuation, preserving historical terminal evidence. Its supported
publication and recovery boundaries must be reconciled with the specs before
coding; any missing product or authority rule returns as one concrete decision.
This handoff does not authorize that implementation.

Actual declaration repair, further review selection, conflict/oscillation terminal
publication and operator/rubric resolution remain separate blocked or unimplemented
paths. All four 18.8 tasks and 18.9 qualification remain incomplete. No unresolved
product decision blocks the delivered final-review milestone.

The user subsequently authorized a local commit after revalidation of all 544
source hashes and recorded evidence. The evidence JSON retains its pre-commit
validation snapshot and records this later authorization separately. No push, live
transmission, public activation or external specification write is authorized.
