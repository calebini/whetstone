# 18.7 Batch C: Verifier process interruption

This bounded continuation adds two actual killed-process cases in
[one parameterized test](../tests/test_vnext_verified_runtime_verifier_faults.py).
Each case uses `open_verified_run`, production canonical Reviewer rounds, and a
registered round-2 candidate above committed promotion 1. The child reconstructs
the registered semantic context from the stored root; no staged round selectors
or external provider calls are used.

**Both process cases pass (one test method, 206.997 seconds, no skips).**
The first run passed without a runtime fix. Runtime and contract bytes remain
unchanged from `de69207`. No broad regression was repeated
for this test-only change.

## Boundaries and required behavior

| Boundary | Required recovery |
| --- | --- |
| Kill after the Verifier returned, immediately before publishing its raw response | The durable first invocation marker consumes its slot. Ordinary reentry requires continuation and changes no files. Explicit continuation records the interrupted outcome and uses only slot 2, bound to that outcome's exact hash. Slot 1 receives no invented response. |
| Kill immediately after raw response publication and its durability barriers completed | Ordinary reentry requires continuation and changes no files. Explicit continuation with no client retains the exact response, completes its receipt and final candidate decision, and creates no second invocation. |

The child reports one scripted Verifier call before being killed with `SIGKILL`.
While it remains alive, competing verification and promotion raise `StorageBusy`.
Read-only reopening and inspection do not repair files. The initial deterministic
decision remains non-final/unverified and promotion is ineligible until explicit
semantic continuation succeeds.

Recovery finalizes candidate decision ordinal 2 at the continuation timestamp;
it does not promote that candidate. Global authority remains at promotion 1,
with no promotion-2 snapshot, third round claim or third candidate. Existing
immutable evidence, canonical Reviewer provenance and mirrors retain their exact
bytes; only the candidate-local current-decision pointer is replaced. A fresh
reopen then selects `promotion_required` without new Reviewer or Verifier calls.

Both cases retain two Reviewer and two Editor calls. Each has one baseline
Verifier call and one call in the killed child; only the missing-response case
adds one explicit retry. No third invocation slot is created.

The [durable semantic request contract](../contracts/algorithms/vnext_semantic_requests_v1.md)
controls consumed slots, retained raw evidence and retry bounds. The
[live-work contract](../contracts/algorithms/vnext_verified_work_v1.md) controls
the single retained fence, explicit continuation and separation from promotion.

## Scope and handoff

The [validation record](audits/VNEXT_RUNTIME_FAULTS_BATCH_C_VERIFIER.json) records
the exact command, source manifest, log digest and execution result. Raw evidence
is retained under ignored `rounds/vnext-runtime-verifier-001/`.

```sh
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_runtime_verifier_faults -v
```

This is test-only coverage of two response-publication boundaries. It does not
establish physical power-loss behavior, every Verifier/decision publication
prefix, killed registrars/operator writers, or a full regression pass.

Next: a bounded runtime mirror-uncertainty case, checking typed storage failure,
ownership poisoning and fresh-owner repair. Then reconcile decision-reference
synchronization, finer registration/verification prefixes and operator
receipt/selection-marker boundaries against the existing component evidence.
Complete consuming-suite qualification and the 18.5–18.7 acceptance map remain
open. Batch C and 18.7 remain incomplete.

D8 design/audit closure stands. Runtime, contracts, legacy/bridge behavior,
frozen suite 1 and shipping qualification maps are unchanged. No 18.8–18.9 work,
mode activation, external transmission, external specification apply-back or
push is included.
