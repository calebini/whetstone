# M5 acceptance closeout

Status on 2026-10-01: **M5 is complete at the approved internal acceptance
boundary.** M5-I1 has a whole passing interruption/recovery verdict. M5-P1's
measurement and reconciliation obligation is complete, with slow replay retained
as a release limitation. Public activation and broader release qualification
remain deferred.

The replay optimization is checkpointed at `2eb4223`. The closeout campaign
preserves that exact runtime, test and contract snapshot (660 files), the
authoritative specifications and the unrelated notes edit. This document and
the [closeout audit](audits/VNEXT_18_8_M5_CLOSEOUT.json) supersede the earlier
partial status in the [M5 campaign record](VNEXT_18_8_M5.md). Interrupted runs
remain preserved with their original outcomes.

## Acceptance evidence

| Evidence | Exact credit |
| --- | --- |
| Remaining operator/terminal matrix | All 22 selected methods passed on `2eb4223` sources. Ten individual passes preceded the first supervisor deadline; subsequent cohorts completed four, five and three. No passing method was repeated. This is not one uninterrupted suite pass. |
| Joined versioned interruption journey | One whole method passed in 1602.056 seconds: `0.17 → 1.0 → 1.1`, Reviewer timeout, uncertain failure-state acknowledgement, reopen, explicit continuation, declaration/convergence and uncertain fixture apply/readback. Exact history, retained failure evidence and client counts are asserted; recovery performs no second source replacement. |
| Four-promotion history | One whole method passed in 1208.656 seconds: four verified promotions `0.17 → 0.21`, profiles at one/four promotions, reopen and clean review. Every version transition appears exactly once; the committed head/history remain unchanged after final review, with exactly five Reviewer and four Editor calls. |
| Previous journal regression | 17 distinct methods passed on bytes identical to this campaign's 660-file manifest. See the [journal audit](audits/VNEXT_18_8_M5_JOURNAL.json). |
| Earlier M5 evidence | 33 distinct methods at their recorded snapshots: the extended horizontal/vertical journey, 30 compatibility/recovery methods, the four-target method and one individual operator method. These include the other two of the original 24 selected matrix methods. They are carried evidence, not fresh current-source executions. |

The current campaign credits **24 distinct passing methods**, plus the 17
same-source prior checks; the 33 earlier methods retain their separate source
scope. No integration failure required a runtime correction during this campaign.
Legacy/bridge runtime files remain unchanged since M4. The changed shared
storage/contracts/replay/version-entry files retain the corrected replay
regression's exact bytes; the subsequent private journal change has the 17
same-source checks and this affected-consumer campaign. This is proportionate
compatibility verification, not a new full-repository suite pass.

## Original A–D requirements

| Requirement | Internal implementation and evidence | Remaining boundary |
| --- | --- | --- |
| A — Scheduler integration | M2 owners; extended horizontal/vertical promotion, budget extension, Phase 2 and fixture apply journey; completed focused/budget/operator matrix and joined explicit continuation. | Public mode dispatch/CLI qualification and unsupported cross-products receive no credit. Focused stability cannot supply full Phase 1 acceptance. |
| B — Verified lifecycle consumers | M3 versioned candidates and distinct entry; joined exact history, declaration and convergence; guarded replay regression and longer-history acceptance. | M3's ratified metadata policy still needs coordinated normative publication; replay performance is a retained limitation. |
| C — Strop/readback | M4's approved exact-source/current-pointer policy; extended and joined fixture apply, lost receipt and readback without rewriting; carried legacy/bridge checks. | M4's internal policy still needs normative publication. Exclusive external source access remains required; no public strop or real-source permission is granted. |
| D — Terminal/operator evidence | Completed choice, repair, freeze, target, gap, review-only, blocked/conflict/oscillation, failure and continuation matrix; joined uncertain state/reopen retains evidence and exact gates. | Every public/process terminal and the complete P0 matrix remain unqualified. Freeze and unchanged valid declaration disagreement retain their approved blocked behavior. |

M5's internal acceptance and broader 18.8 completion are distinct. The original
A–D checkboxes remain open where their full supported-route, normative and
release requirements exceed this approved internal matrix. The existing
[supported matrix](VNEXT_18_8_M5.md#supported-internal-matrix),
[ratification reconciliation](VNEXT_18_8_M5.md#ratification-delta-reconciliation)
and [operator handoff](VNEXT_18_8_M5.md#internal-operator-handoff) identify those
boundaries; they do not introduce new implementation milestones.

## Replay cost

**M5-P1 is closed as measurement/reconciliation, with replay cost explicitly
unresolved.** The earlier controlled
baseline/handoff/handoff/baseline comparison recorded identical results, no
writes and unchanged proof-guard counts, with mean profiled one-promotion
reductions of 10.9% for history and 14.4% for Phase 2 state. The unsuccessful
candidate-material cache experiment remains withdrawn.

The completed samples on `2eb4223` are:

| History size | Profiled history sample | Profiled Phase 1 state sample |
| --- | --- | --- |
| One promotion | 5.342s | 9.431s |
| Four promotions | 43.682s | 77.428s |

The four promotion stages took 48.317s, 124.470s, 245.432s and 425.798s.
These samples show roughly eightfold replay cost for four times the promotion
count in this fixture. The history profile reconstructs candidate material 34
times at four promotions versus four times at one; this is evidence of remaining
repeated prerequisite work, not a general complexity bound. There is no complete
pre-optimization four-promotion sample for a controlled before/after claim.

All current acceptance work uses one worker at 50% duty with a 300-second
actively refreshed lease. Profiling adds overhead. Whole-test durations include
fixture setup and many operations; they are not production operation latencies.
No SLA or performance waiver is ratified. Slow replay must remain visible in the
release decision despite the completed correctness and measurement obligations.

The final reopened clean-review stage passed in 227.220 seconds. Both whole
journey verdicts and all required samples are indexed with hashes; no earlier
interrupted run is relabeled as complete. All supervisors have exited, and final
process inspection found no task-owned test or profiling worker.

## Handoff

After this internal acceptance, the next stage is 18.9 qualification: reconcile
the executable P0 map and family dependencies, then process/CLI and full
regression evidence. Coordinated specification publication, live soak and public
activation require their own authorization and gates. No push, public activation,
live provider call, normative edit or real external apply-back is included here.

The replay checkpoint is committed. The user authorized the separate closeout
documentation and evidence checkpoint on 2026-10-01;
`notes/future-improvements.md` stays outside the feature checkpoint.
