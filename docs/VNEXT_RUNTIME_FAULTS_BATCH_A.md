# 18.7 Batch A: runtime promotion faults

Date: 2026-09-16. Base checkpoint: `2afae07`.

This bounded batch adds two test methods containing three fault cases in
[test_vnext_verified_runtime_faults.py](../tests/test_vnext_verified_runtime_faults.py).
Runtime, contracts, earlier tests and shipping controls are unchanged. It follows
Batch A of the [fault coverage inventory](VNEXT_18_7_FAULT_COVERAGE.md).

**All three fault cases pass (two test methods, 312.819 seconds, no skips).** No runtime fix was required. 18.7 remains incomplete.

## Cases and assertions

Each case constructs two production Reviewer rounds and canonical round inputs,
registers and independently verifies two candidates, and normally promotes the
first. The second candidate is eligible for ordinal 2. All clients are scripted;
there are no operator follow-ups in this batch because the fault concerns the
promotion owner and its committed history.

| Case | Injection boundary | Required recovery |
| --- | --- | --- |
| Killed before commit | A child opens the stored runtime, prepares the second intent/event/snapshot, pauses immediately before the actual `os.replace`, then receives `SIGKILL`. | Head remains ordinal 1. A fresh owner reuses the exact prepared claimant and timestamp, commits ordinal 2 once, then materializes it. |
| Killed after commit | The same runtime path pauses immediately after the actual `os.replace`, before post-rename barriers or normal lock release, then receives `SIGKILL`. | Readback observes ordinal 2. Recovery repeats durability/repairs mirrors without replacing the pointer and ends before another Reviewer call. |
| Uncertain rename acknowledgement | The real second `os.replace` succeeds, then its wrapper raises `OSError`. The actual adapter classifies and propagates `StorageWriteError`. | Classification is `outcome_requires_reconciliation`; token and descriptor are invalidated before the enclosing lock context unwinds. Stale-token publication refuses. Fresh runtime readback repairs committed mirrors without rollback or recommit. |

Both child-process cases use `open_verified_run` with only root/suite locators;
round selectors are resolved from the stored runtime. While the child holds the
lock, the separate parent process attempts Editor work, registration and promotion.
All three must raise `StorageBusy` without changing any file or calling a client.
Read-only reopening and inspection before and after death must preserve every byte.

Across recovery, immutable inputs, canonical rounds, previous client evidence,
intent/event/snapshots and the original prepared timestamp must remain exact.
The final `spec.md`, round-2 `draft_after.md`, and state projection must agree with
committed authority. Each case retains exactly two Reviewer, two Editor and two
Verifier calls. No third review claim or promotion ordinal may appear. Repeating
promotion is ineligible and changes no bytes; subsequent read-only reopening sees
review round 3 ready to start.

The uncertain-write assertion runs inside the pointer-call exception handler,
before normal `locked()` cleanup. This prevents ordinary release from masquerading
as successful uncertainty poisoning. The syscall wrapper raises an ordinary I/O
error; the test does not fabricate a `StorageWriteError` result.

## Evidence and remaining work

The [validation record](audits/VNEXT_RUNTIME_FAULTS_BATCH_A.json) records the exact
command, test identities, three fault boundaries, log/source hashes and macOS/ARM
environment. The final test file and every recorded runtime/contract source hash
still match the launch manifest. The focused command was:

```sh
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_runtime_faults -v
```

Raw evidence is retained in ignored `rounds/vnext-runtime-faults-001/`. Both test
methods passed on their first run. Compilation and whitespace checks also passed.
No runtime/shared producer changed, so existing component/compatibility results
were not rerun. This is a targeted integration check, not a full regression or
release qualification campaign.

Process death after rename differs from interleaving after normal promotion-lock
release and before materialization reacquires it. The latter remains a Batch C
gap, as do process death partway through mirror repair and finer operator/dependency
publication boundaries. Batch B remains next: killed Reviewer before/after durable
raw output and representative registration/verification recovery through the
canonical runtime owner. Existing component prefix matrices remain separately
scoped evidence.

D8 design/audit closure stands. 18.7 and consuming-suite qualification remain
incomplete. No 18.8–18.9 work, live provider calls, mode activation, push or external
specification apply-back is included. Legacy/bridge runtime bytes are unchanged;
no new legacy/bridge regression run is claimed.
