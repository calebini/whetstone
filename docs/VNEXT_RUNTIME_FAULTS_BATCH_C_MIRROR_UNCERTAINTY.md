# 18.7 Batch C: runtime mirror uncertainty

This bounded continuation adds [one runtime recovery test](../tests/test_vnext_verified_runtime_mirror_uncertainty.py)
with two sequential injected barrier failures. It uses production canonical
Reviewer rounds and promotion publishers through `open_verified_run`. A second
verified candidate differs from the first promoted draft; unrelated operator
state must survive its promotion and repair.

**The test passes with both injected failures (110.233 seconds, no skips).**
Its first run passed; no runtime fix was required. Runtime and contract bytes
remain unchanged from `54a5c3c`. No broad regression was repeated
for this test-only change.

## Exact failure boundaries

1. Promotion 2 commits normally. During its separate materialization operation,
   the real adapter replaces `spec.md` and synchronizes the directory. The
   injected `OSError` occurs at the subsequent `_full_flush` call, before that
   flush runs. The adapter itself must classify the result as
   `outcome_requires_reconciliation`, naming `spec.md` and its exact draft hash.
2. A fresh runtime sees the new spec bytes with the source-round draft and state
   still pending. Its repair synchronizes the committed snapshot and pointer,
   then synchronizes the matching spec. An injected `OSError` at the second
   `_full_flush` call for that existing spec must propagate the same uncertainty
   classification and stop before either pending mirror write.

These are primitive-level injected failures, not a fabricated `StorageWriteError`
after a successfully acknowledged publication. They exercise the real adapter's
classification and owner invalidation. They are not process deaths, actual
device failures, or physical power-loss qualification.

Both errors must clear the token and release the lock before the surrounding
`locked()` context exits. An attempted publication with the old token must fail
with `OwnershipLost`, both immediately and after reopening. No stale-owner
artifact may appear.

Read-only reopen/status must preserve all bytes and report only the remaining
source-round draft and run state. After the second failure, another fresh runtime
synchronizes the snapshot, pointer and matching spec, writes precisely those two
remaining mirrors, and returns `materialization_recovered` without invoking the
available Reviewer. Authority publication and pointer replacement are forbidden
during this successful repair.

The committed ordinal-2 pointer, original timestamp, candidate evidence and
prior history remain exact. The unrelated operator state survives. Reentry is
ineligible for another promotion; read-only status selects round 3 without
claiming it. No third promotion or additional client call occurs: Reviewer,
Editor and Verifier totals remain two each.

## Evidence and remaining scope

The [validation record](audits/VNEXT_RUNTIME_FAULTS_BATCH_C_MIRROR_UNCERTAINTY.json)
binds the test result, launch manifest and log digest. Raw evidence is retained
under ignored `rounds/vnext-runtime-mirror-uncertainty-001/`.

```sh
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_runtime_mirror_uncertainty -v
```

The [materialization contract](../contracts/algorithms/vnext_verified_materialization_v1.md)
requires exact existing-byte synchronization before pending writes and recovery
against fresh committed authority. The [D8 storage contract](specs/VNEXT_LOCAL_STORAGE_SPEC.md)
requires uncertainty classification, ownership invalidation and readback after
post-publication barrier failure. No contract change is included.

This checkpoint covers a visible uncertain spec mirror while two targets remain
pending, and a repeated synchronization failure at that same spec. It does not
establish every destination/barrier combination or runtime recovery after an
uncertain final run-state write leaves all visible mirrors matching. Existing
component tests remain separately scoped evidence for their own boundaries.

Next: reconcile the remaining registration/verification prefixes,
decision-reference synchronization and operator receipt/selection-marker
boundaries against the existing component and runtime evidence. Add only the
runtime cases justified by that mapping. Complete consuming-suite qualification
and the 18.5–18.7 acceptance map remain open; Batch C and 18.7 are incomplete.

D8 design/audit closure stands. This local test uses no external providers.
Legacy/bridge behavior, frozen suite 1 and shipping qualification maps remain
unchanged. No 18.8–18.9 work, mode activation, external specification apply-back
or push is included.
