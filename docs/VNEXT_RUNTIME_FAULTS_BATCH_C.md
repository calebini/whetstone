# 18.7 Batch C checkpoint: lock handoff and partial mirror repair

Date: 2026-09-17. Base checkpoint: `c9d3409`.

This bounded Batch C step adds two test methods with three process cases in
[test_vnext_verified_runtime_materialization.py](../tests/test_vnext_verified_runtime_materialization.py):
one normal lock handoff with an interleaving promotion, and two killed writers
during partial mirror repair. It does not close every remaining Batch C or 18.7
boundary. Runtime, contract and shipping-control bytes are unchanged.

**All three process cases pass (two test methods, 429.696 seconds, no skips).**
No runtime fix was required. This checkpoint leaves the remaining Batch C and
18.7 qualification work open.

## Boundaries and assertions

Each fixture executes two production Reviewer rounds, publishes their canonical
inputs, and registers/verifies two candidates. Ordinal 1 is already promoted;
the child opens the runtime using root/suite locators and promotes ordinal 2.
No caller-supplied round selectors or live provider clients are used. A fixture
operator note in run state must survive every repair.

| Case | Process boundary | Required outcome |
| --- | --- | --- |
| Normal handoff with advanced authority | Child commits ordinal 2, normally releases its promotion fence, checks its old token cannot publish, then pauses before materialization reacquires ownership. Parent repairs ordinal 2, executes round 3 and promotes ordinal 3. Child resumes. | The child freshly proves and synchronizes ordinal 3 and its mirrors; it reports its own committed pointer as 2 separately from current pointer 3. It creates/rewrites no artifact and cannot restore ordinal 2. |
| Death after spec mirror | Child has committed ordinal 2 and completed the `spec.md` replacement under the separate materialization fence, then is killed with `SIGKILL`. | Read-only status identifies only round-2 `draft_after.md` and run state as pending. Recovery synchronizes existing authority/spec and writes only those remaining mirrors. |
| Death after source-round mirror | Child has also completed round-2 `draft_after.md`, then is killed while holding the materialization fence. | Only run state remains pending. Recovery synchronizes authority and both matching draft mirrors, then writes only run state. |

The normal-handoff case checks a real change in authority, not merely a second
owner reading the same head. The third candidate has different draft bytes from
the second. Once ordinal 3 is complete, the resumed child's publication,
pointer-replacement and mirror-rewrite methods are forbidden; only existing-byte
synchronization is permitted. Its synchronization paths must bind ordinal 3 and
round 3. All files remain byte-identical while that child finishes.

In each killed-writer case, parent Reviewer and promotion attempts must raise
`StorageBusy` while the child holds the materialization lock. Read-only reopen
and status preserve all bytes both before and after death. Recovery receives a
Reviewer client but must return `materialization_recovered` before using it.
Authority publication and pointer replacement are forbidden during recovery;
matching mirrors repeat synchronization and only mismatched targets are written.

The final spec, source-round draft and run-state projection must match committed
authority. All prior immutable artifacts and unrelated run-state members remain
unchanged. Repeated promotion is ineligible, does not change files, and allocates
no third ordinal or review in either partial-repair case. Those cases retain two
calls per scripted role. The handoff case intentionally completes a third round
and promotion (three calls per role); the resumed child adds no further work or
fourth ordinal.

## Evidence and remaining work

The [validation record](audits/VNEXT_RUNTIME_FAULTS_BATCH_C.json) records the command,
test identities, source/log digests and the three distinct process boundaries.
All source hashes still match the launch manifest. Raw evidence is retained in
ignored `rounds/vnext-runtime-materialization-001/`.

```sh
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_runtime_materialization -v
```

Both methods passed on their first run. Compilation and whitespace checks also
passed. No runtime/shared producer changed, so earlier component/compatibility
runs were not repeated. This test-only step does not run a full regression or
establish release qualification. The existing lower-level six before/after mirror
exception cases remain separately scoped evidence; these new process cases cover the two partial
states after fully completed mirror publications, not physical power loss or all
storage-barrier failure placements.

Remaining 18.7 work includes actual Verifier process death, finer registration/
verification prefixes, runtime mirror uncertainty, explicit decision-reference
synchronization and operator receipt/selection-marker boundaries. Reconcile these
against existing component tests before adding further integration cases. Complete
consuming-suite qualification and the 18.5–18.7 acceptance map remain open.

D8 design/audit closure stands. No 18.8–18.9 implementation, mode activation,
external model call, push or external specification apply-back is included.
