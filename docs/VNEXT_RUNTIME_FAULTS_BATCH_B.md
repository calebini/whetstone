# 18.7 Batch B: Reviewer slots and runtime recovery precedence

Date: 2026-09-17. Base checkpoint: `9a01f9c`.

This batch adds three test methods with four fault cases in
[test_vnext_verified_runtime_recovery.py](../tests/test_vnext_verified_runtime_recovery.py).
All cases start from one production promotion and a runtime root with no staged
round selectors. Round 2 is selected against committed ordinal 1. Clients are
scripted. One V-mode recovery change fixes the defect described below; contracts
and shipping controls remain unchanged.

**All four new fault cases pass (three test methods, 227.408 seconds, no skips).**
All 25 affected live-work/history regressions also pass: **28 distinct tests**
on the corrected source. 18.7 remains incomplete.

## Cases

| Case | Boundary | Required result |
| --- | --- | --- |
| Reviewer death before raw | Child opens the stored runtime, invokes the round-2 Reviewer once, then pauses before publishing its raw response and receives `SIGKILL`. | Used invocation slot remains. Read-only reopening and a call without explicit continuation cannot publish or invoke. Explicit continuation commits the interrupted first outcome, links a second invocation to it and completes without resetting the budget. |
| Reviewer death after raw | Same child pauses after raw response publication has completed its storage barriers, before outcome/receipt publication, then receives `SIGKILL`. | Readback reconstructs a valid response. Explicit continuation with no client supplied completes that same first attempt, retaining exact raw bytes and allocating no second attempt. |
| Registration orphan | Round-2 Editor has completed. An injected exception stops registration before `creation-2.json`, after the complete candidate and initial disposition evidence. | Request, registration, verification and Reviewer work all report registration recovery required. Explicit recovery commits only the original creation event; the candidate remains unverified and no later work starts. |
| Prepared verification | Round-2 Verifier has completed. An injected exception stops after the prepared final disposition event (`event-3.json`) and before the second candidate-pointer snapshot/commit. | The effective decision remains nonfinal/unverified until explicit continuation. Recovery without a client preserves the prepared final decision and timestamp, commits its candidate pointer, and stops before global promotion. |

The Reviewer subprocess receives only root/suite locators and fictional client
response templates, not round selectors. Its call count at the pause must be one.
A second process attempting Reviewer work must be excluded while it holds the
fence. Reopening/status are checked for byte preservation before and after death.
The two allowed attempts are distinguished from two logical review rounds; no
third attempt or round may be allocated by recovery. Canonical round-2 admission
uses committed ordinal 1 after recovery.

Registration recovery is also attempted with altered original round-1 Reviewer
raw evidence; verification recovery is attempted with altered round-2 evidence.
Both must refuse without further writes. The test restores the exact fixture bytes
before testing the valid recovery path; restoration is not a runtime repair.

Recovery retains root selectors, prior canonical rounds, client artifacts and
committed authority. Registration adds only its creation event. Verification adds
only its candidate-pointer snapshot and changes only that candidate's current
pointer. No recovery creates another candidate, review round or global promotion.
Reviewer death requires one child call plus zero additional calls when raw was
retained, or one explicitly authorized retry when it was not. Registration and
verification recovery add no client calls.

## Evidence and limits

The [validation record](audits/VNEXT_RUNTIME_FAULTS_BATCH_B.json) records the exact
commands, test identities, source/log digests, initial failures and correction
scope. All corrected-run source hashes still match. Raw evidence and both initial and
corrected manifests are retained in ignored `rounds/vnext-runtime-recovery-001/`.

```sh
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_runtime_recovery -v
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_work test_vnext_verified_history -v
```

Both corrected runs finish `OK` with no skips. Compilation and whitespace checks
also pass. Counts exclude the initial failed run; no full regression or fresh
legacy/bridge campaign is claimed. Existing legacy/bridge sources, contract pins,
frozen suite 1 and empty shipping qualification maps are unchanged.

The initial run exposed a registration recovery defect: with a prior semantic
candidate and a later registration orphan, `VerifiedWork` validated the earlier
decision through the unrestricted current registry. Semantic admission rejected
the orphan, preventing the explicit recovery that would reconcile it. The fix
replays each existing candidate through its bounded historical creation prefix,
then reconciles the orphan under the same ownership fence. Existing decisions
are still validated; the live semantic admission guard is unchanged. Historical
readers cannot publish or invoke clients. The regression preserves the original
claimant and rejects altered Reviewer evidence before recovery writes.

The initial run also exposed a separate test-hook error: the Reviewer hook matched
historical round-1 raw replay before the new client invocation. The corrected hook
requires the new scripted Reviewer call before pausing raw publication. The first
run's two hook failures and registration error are retained. The complete new
module passed after both corrections. All 15 existing live-work tests and
ten historical replay tests also passed on the corrected source.

This batch does not test actual Verifier process death, every registration or
verification publication prefix, the normal promotion-lock release/materialization
reacquisition handoff, partial mirror process death, or remaining operator and
decision-reference boundaries. Those gaps remain explicit in the
[fault inventory](VNEXT_18_7_FAULT_COVERAGE.md). No full regression, live-provider
qualification, 18.8–18.9 work, mode activation, push or external specification
apply-back is included. D8 design/audit closure stands; complete 18.7 fault and
consuming-suite qualification remain open.
