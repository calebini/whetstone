# M4 verified strop/readback and source-write decision

Status: **complete at the documented internal boundary on 2026-09-29; local checkpoint authorized**. Policy ratified the same day. Baseline:
`a1d46a6`. The user requested completion of M4 after the M3 checkpoint and its
documentation follow-up, then approved the policy below with “yes, i approve your proposal”.
Existing M3 documentation changes and the unrelated notes edit are preserved.

## Ratified decision (2026-09-29)

Approve a bounded internal vNext apply-back policy: **an explicitly approved,
converged verified result may replace its descriptor-bound local source only
while that source remains unchanged; uncertain writes require readback and
reconciliation before any further write.**

This approval authorizes implementing and testing the complete internal M4
bundle below using disposable fixture sources. It does not authorize applying
Whetstone results to real specifications, editing the authoritative spec family,
activating public modes, committing or pushing. The scheduler remains the
normative policy owner; this document is the concrete amendment proposal and
records the implementation ratification, as the M3 handoff does for its
approved internal consumer. Coordinated normative publication remains separate.

## Authority and implementation at preflight

- The candidate leaf's [Safe Terminal Semantics](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#safe-terminal-semantics)
  supplies the mandatory verified-pointer, map, seed/candidate, final verification,
  promotion-intent/event, scheduler/convergence, source-hash and decision guards.
  It explicitly forbids upgrading unverified material through manual recovery.
- Its [Ratification Delta Map](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#ratification-delta-map)
  states: “Detailed vNext policy remains unratified until that scheduler amendment
  is completed.” The scheduler is designated owner of full eligibility and the
  external source-write lifecycle. The implementation plan repeats this dependency.
- [D8](specs/VNEXT_LOCAL_STORAGE_SPEC.md#ratified-operating-model) protects one
  physical run root with one authority writer. Its lock does not grant exclusive
  ownership of an arbitrary external source or prevent a text editor writing it.
- The [Quickstart](OPERATOR_QUICKSTART.md#apply-back) requires review and explicit
  approval for existing strop. `apply_back.py` calls `reject_legacy_writer` before
  any vNext consumption. Its legacy/bridge write path must remain unchanged;
  its direct source write is not the proposed vNext commit/recovery protocol.
- `VerifiedRun.phase2_closeout()` reconstructs convergence evidence and checks
  its state/declaration mirrors. Even a converged internal closeout currently
  records `apply_back_permitted=false`. A future separately pinned M4 assessment
  must consume that evidence; it cannot rewrite an old immutable closeout to
  claim that it had source-write authority.
- `job-descriptor-v2.source_spec` already binds a path and expected hash (or
  nulls); current generic V fixtures use nulls. Positive M4 fixtures need a
  genuine source binding established before job identity and initialization,
  not an in-place descriptor edit or a caller-selected replacement target.

## Approved policy — one bounded ratification

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
   write outcome separate. Only disposable fixture sources may be written during
   implementation. Public activation and real apply-back remain deferred.

## Implementation and acceptance after ratification

One M4 delivery bundle owns the consumer contract, read-only assessment,
approved intent/write/receipt lifecycle, recovery, focused tests and operator
handoff. Existing validated V history, convergence and D8 owners are reused;
there is no new scheduler, distributed lock service or generic metadata repair.

Required evidence before marking M4 complete:

- A converged promoted result and a converged unchanged seed both pass review,
  explicit fixture apply and fresh-owner readback with exact byte/hash lineage;
  versioned M3 history is retained. Repeated apply and approved no-op do not rewrite.
- Missing pins/source/approval, stale pointer/map/decision/intent, unpromoted or
  rejected selection, unresolved decisions, incomplete closeout and source drift
  refuse before source mutation. Tampered mirrors cannot select replacement bytes.
- Read-only calls change neither source nor run. Cross-root, symlink, multilink,
  parent/device changes and busy/lost D8 ownership refuse within the declared
  single-source environment. No concurrency guarantee beyond that environment is
  inferred from these tests.
- Faults before intent, during preparation, before replacement, at uncertain
  replacement acknowledgement, at file/directory flush, and during receipt/state
  publication preserve evidence and classify the outcome accurately. Process
  termination immediately before/after replacement reopens into recovery-only
  behavior, with before/after/third-byte and missing-source cases covered.
- Recovery retains original approval identity and candidate finality, makes no
  client calls, never restamps or promotes, and cannot overwrite later external
  edits. Status distinguishes completed historical write from present source
  drift and unresolved outcome. Legacy/bridge consumer regressions still pass.

No source-write implementation or M4 completion is credited by the authority
preflight. Its bounded current-boundary verification is indexed separately in
[the M4 preflight audit](audits/VNEXT_18_8_M4_PREFLIGHT.json). M5-I1 and M5-P1 remain
open in the delivery plan; this policy decision does not close those items.

## Preflight verification result

All **15 selected existing methods passed** in 142.211 seconds on one
unchanged 649-file source snapshot. They cover legacy review/approval/source
hash guards, vNext legacy-writer refusal, bridge pending-evidence refusal,
read-only bridge review, exact-byte repeated apply-back and declaration/manifest
tampering. All writes used disposable test sources. These checks establish
current behavior only; they do not validate the proposed M4 writer or recovery.

## Implemented internal consumer

The new `vnext_apply_back_v1` algorithm and four apply-back schemas must be
explicitly pinned by a consuming suite. The implementation adds methods to the
internal `VerifiedRun` API; no public CLI selector or shipping suite is changed.

| Internal operation | Behavior |
| --- | --- |
| `review_apply_back()` | Reproduces current eligibility and source binding, returning an exact assessment and diff or explicit blockers. No fence acquisition, artifact publication, source change or automatic repair. |
| `apply_back(assessment=..., approve=True, exclusive_source_access=True)` | Revalidates the reviewed packet and convergence under D8, publishes the immutable preimage/intent, prepares verified bytes, replaces the bound source once, then records the result. An existing incomplete intent returns its recovery state. |
| `apply_back_status()` | Revalidates the retained intent, historical verified pointer, prepared source identity and receipt; independently reports whether the source currently matches the result. |
| `recover_apply_back(exclusive_source_access=True)` | Reacquires D8 and performs only readback, durability barriers and receipt recovery. It cannot prepare or replace a source. |
| `apply_back(..., retry=True)` | An explicit attempt using the same approved assessment after `apply_required`; revalidates all current eligibility and original physical source identity. It cannot refresh approval or overwrite changed bytes. |

The first invocation's source assessment is supplied back unchanged as the
approval subject. The immutable intent retains that same assessment for restart;
caller flags are not permission to substitute a target, pointer or hash. Source
hashes use exact bytes, including line endings. The source-write receipt is a
separate record from immutable convergence closeout; old closeout reports remain
unchanged and are not retrospectively granted source-write permission.

| Readback outcome | Supported operator action |
| --- | --- |
| `not_started` | Review the bound result; no source write is evidenced by this consumer. Prepared preimage artifacts alone are not an intent. |
| `apply_required` | Original source bytes and identity remain. Recovery does not write. An explicitly approved retry must still pass current eligibility; this outcome does not prove an earlier uncertain syscall never ran. |
| `receipt_recovery_required` | Expected result bytes are on the recorded inode. Reacquire exclusive access and run recovery to repeat durability barriers and publish the receipt. |
| `completed` | Receipt and current source agree; repeated apply/recovery return the result without rewriting. An approved no-op reports no source replacement. |
| `source_drift` | A completed historical receipt exists but the current source differs. Inspect external changes; do not replay the old write. |
| `operator_attention_required` | Missing source, third bytes, unexpected identity or unsupported metadata prevents safe reconciliation. Preserve evidence; no automatic overwrite or rollback. |

The source adapter retains parent and source identities, rejects symlinks and
multiple links, and checks that the source shares the run's qualified local
APFS filesystem. It preserves ordinary permission bits, owner/group and the
exact Apple provenance attribute. Extended ACLs, file flags, special permission
bits and other extended attributes refuse before replacement. Content-change
timestamps are intentionally not retained. No new external lock service or
cross-run writer coordination is introduced; exclusive source access remains
an explicit operating precondition.

A failed staging write may leave a non-authoritative same-directory temporary.
Those bytes are preserved. If no preparation record committed, an explicit retry
may prepare another temporary. Once preparation is recorded, its exact inode and
bytes must match; recovery cannot silently substitute another temporary.

The adapter holds the same D8 process gate/mutex while checking ownership and
performing mutation syscalls. A lost replacement or receipt acknowledgement
releases ownership and reports reconciliation required. Source replacement and
run receipt publication are deliberately separate commits; there is no claimed
cross-directory atomic transaction or physical power-loss qualification.

Implementation verification is indexed separately in
[the M4 implementation audit](audits/VNEXT_18_8_M4_IMPLEMENTATION.json).
The historical 15-test preflight above remains evidence of prior behavior.

## Acceptance evidence and limits

**98 distinct methods passed in 106 executions:** 18 new methods and 80
regressions, plus eight repeated primitive methods after the test refinement.

| Final-runtime cohort | Methods | Seconds |
| --- | ---: | ---: |
| Source adapter + seeded owner/fault/process acceptance | 17 | 289.972 |
| Legacy/bridge, D8, contracts and closeout regressions | 80 | 224.996 |
| Refined source-adapter rerun | 8 | 0.453 |
| M3 versioned promotion → convergence → M4 apply/readback | 1 | 381.738 |

Compilation, source-manifest comparison and `git diff --check` also passed.

Acceptance uses scripted clients and disposable sources on local APFS. The
implementation audit binds each command and log to a 658-file source manifest.
Runtime and contracts are identical across the two recorded snapshots; the only
test change makes the directory-flush fault target the actual parent-directory
fd. All eight source-adapter methods were rerun after that refinement.

The new tests cover exact seeded apply/reopen/repeat, approved no-op, stale or
ineligible selection, source and lineage tampering, publication acknowledgement
loss, source readback, and actual child-process termination on both sides of
replacement. Separate primitive cases cover D8 ownership, paths/links/identity,
metadata and file/directory barriers. The versioned journey checks genuine M3
promotion through convergence and apply while retaining version history and the
old closeout's authority fields. Regression checks retain legacy/bridge behavior.
This is bounded internal acceptance, not exhaustive release qualification.

Development failures (an unsupported schema keyword and approval-ID preimage
shape) were corrected before acceptance. Earlier development passes and the
historical authority preflight are not added to acceptance totals. No physical
power-loss, live-provider, arbitrary external-writer or real-specification test
is claimed.

The next delivery milestone remains M5: integrate the complete M1–M4 workflow
matrix and reconcile the original A–D requirements. M5-I1 still owes its combined
two-promotion interruption/continuation/convergence verdict. M5-P1 still owes
measured replay analysis; the versioned M4 test's whole-test elapsed time is
additional evidence of cost, not an isolated replay benchmark. Normative family
consistency and 18.9 qualification/public activation remain separate. No commit
or push was authorized by the M4 policy approval itself. The user subsequently
authorized the local implementation checkpoint; push remains deferred.
