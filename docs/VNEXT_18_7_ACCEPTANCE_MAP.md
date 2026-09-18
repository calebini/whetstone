# 18.7 acceptance map and bounded closeout

Date: 2026-09-18. Inspected checkpoint: `0d2e7f4`.

Subsequent G1 result: the [joint selection checkpoint](VNEXT_CONCURRENT_SELECTION.md) now passes the two lock-winner orders plus 18 promotion/Batch A regressions without runtime changes. G1 below is closed at its declared scope. The two Batch A methods are credited toward G2, leaving 97 existing methods (eight runtime, 89 component). Current-source passing evidence totals 84 distinct methods after overlap accounting. The original evidence map below remains the historical consolidation; its G1 gap/next-action and 99-method cohort statements are superseded by this checkpoint. 18.7 remains incomplete.

**The publication/operator boundary inventory is reconciled. One concrete joint
acceptance scenario remains unproved, followed by a fixed current-source evidence
refresh.** This pass found no additional runtime defect. It changes documentation
only and executes no runtime tests. 18.7 remains incomplete.

The [machine-readable map](audits/VNEXT_18_7_ACCEPTANCE_MAP.json) binds requirements,
exact test identities, retained logs and source comparisons. It supersedes the
open-ended “remaining Batch C boundaries” next steps in earlier handoffs, while
preserving their historical results and failures.

## Authority and acceptance boundary

The [18.7 plan](../IMPLEMENTATION_PLAN.md#187-atomic-promotion-locking-and-recovery),
[D8 qualification requirements](specs/VNEXT_LOCAL_STORAGE_SPEC.md#required-qualification),
and candidate leaf's [promotion protocol](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#promotion-and-current-verified-authority)
and [P0 scenarios](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#p0-release-acceptance)
control this map. D8 design ratification and its authorized correction audit are
closed. The retained passing report, empty feedback, five raw artifact digests
and input snapshots were rechecked; no new transmission is necessary.

The three 18.7 implementation bullets have code and passing bounded evidence:
shared fencing and publication, two-stage lineage/claimant reconciliation, and
explicit failure/recovery with nonrepairing status. Their completion boxes stay
open because the joint selection proof and consuming qualification below are
unfinished. Public activation also depends on later slices; it is not required
to test the isolated 18.7 implementation.

Coverage is layered: component tests enumerate persisted protocol prefixes;
canonical-runtime tests prove representative composition with real Reviewer
history and promoted bases; process tests prove exclusion and death/reacquisition;
primitive faults prove uncertainty and durability-barrier handling. The specs
require all protocol prefixes and process exclusion, but do not explicitly require
every syscall failure crossed with every runtime journey. This reconciliation
therefore retains those distinct levels rather than prescribing that Cartesian
product. It does not weaken the requirement to cover every persisted prefix.

## Requirement map

“Retained” means a passing result exists on its recorded source, not necessarily
a fresh pass at this checkpoint. The JSON identifies exact methods and their
source status. Links below point to executable tests, not just descriptions.

| ID / obligation | Implementation and inspected evidence | Status and limit |
| --- | --- | --- |
| D8-01: fresh root, descriptor, root/device and permanent-lock identity | `vnext_local_storage`; [storage tests](../tests/test_vnext_local_storage.py) cover interrupted/reused roots, copied root, missing/replaced/symlink/multiple-link lock, changed root/filesystem/device and independent process CWD. | Implemented; retained proof. Filesystem/device changes include injected identity checks, not another qualified filesystem. |
| D8-02: one exclusion domain; paused owner, death, registration/promotion exclusion | [Storage](../tests/test_vnext_local_storage.py), [registry](../tests/test_vnext_candidate_registry.py) and [runtime Batch A](../tests/test_vnext_verified_runtime_faults.py): stopped holder stays exclusive, death releases, two registrars yield one contiguous chain, held promoter excludes request/register/promote. | Implemented; actual processes. Batch A needs current-source refresh. |
| D8-03: stale/copied/forked ownership; client inheritance; release serialization | Storage checks reject foreign/released tokens and copy/pickle attempts; fork child cannot publish or unlock parent; live exec child retains no authority descriptor; release cannot race publication. | Implemented; retained proof. Advisory exclusion protects cooperating writers. |
| D8-04: immutable replay and uncertain durability | Storage checks exact replay/conflict, prepublication failure, actual link acknowledgement loss, directory failure and post-rename full-flush failure. Registry and runtime mirror/operator tests repeat failed barriers under fresh ownership. | Implemented; injected primitive failures. No physical power-loss claim. |
| D8-05: conditional pointer replacement and complete reads | Storage compares exact expected pointer and snapshot, rechecks after transition callback, handles cancellation; repeated concurrent reads see complete old/new bytes. | Implemented; reader observation uses a thread. Other exclusion/death tests use separate processes. |
| R-01: contiguous creation order and orphan recovery | [Registry](../tests/test_vnext_candidate_registry.py) interrupts seven after-publication prefixes; early incomplete packages refuse, complete packages reconcile once. [Runtime recovery](../tests/test_vnext_verified_runtime_recovery.py) revalidates original Reviewer evidence; [publication prefixes](../tests/test_vnext_verified_runtime_publication_prefixes.py) preserves incomplete registration above promotion 1. | Implemented. Missing artifacts are not synthesized. Creation-marker typed uncertainty remains component-level proof. |
| V-01: verification decision/event/snapshot/pointer commit | [Semantic decisions](../tests/test_vnext_semantic_decisions.py) interrupts three successive preparation publications, then recovers one exact final decision; runtime covers prepared-event recovery and actual candidate-pointer acknowledgement loss with failed/successful replay barriers. | Implemented. Three component interruptions are one journey. Candidate verification never implies global promotion. |
| P-01: current lineage before next-ordinal scan; map and ancestor integrity | [Pointer history](../tests/test_vnext_pointer_history.py) rejects missing/altered bound dependencies, own-snapshot mismatch, ordinal gaps and rehashed wrong bases; [materialization](../tests/test_vnext_verified_materialization.py) proves repair precedes malformed future work. | Implemented. Committed immutable dependencies cannot be repaired from mirrors. |
| P-02: latest selection, sole reservation, competing/nonprefix refusal | [Promotion](../tests/test_vnext_verified_promotion.py) refuses fallback from latest rejection, preserves an older reserved claimant over newer verified/rejected registration and rejects multiple intents/nonprefix packages. `_select` selects the final creation row when there is no claimant. | **Partial joint acceptance proof: G1 below.** Positive latest-of-two selection and process exclusion are not jointly demonstrated. |
| P-03: intent/event/snapshot ordering and exact preparation reuse | Promotion has six before/after preparation cases, stale same-draft/different-pointer refusal, final evidence/ownership revalidation. Runtime intent-only recovery preserves candidate and timestamp. | Implemented; component matrix and runtime representative both have passing evidence. |
| P-04: one committed next ordinal; uncertainty without rollback | Production writer drives two promotions; component and runtime deaths straddle commit; typed runtime rename uncertainty invalidates ownership before cleanup and requires fresh readback. | Implemented. Older Batch A runtime pass remains historical pending refresh. |
| M-01: committed mirrors, separate repair, current head after handoff | Materialization has six before/after mirror cases. Runtime kills partial-mirror writers and advances authority between release/reacquisition. Final-state uncertainty tests require barriers even when all mirrors already match. | Implemented; current 76-test correction evidence includes the mirror/handoff regressions. No repeated ordinal, history repair or next-work invocation during repair. |
| O-01: nonrepairing status and explicit operator/round evidence | [Operator](../tests/test_vnext_verified_operator.py) covers eight response/receipt/admission/selection prefixes and dry-run nonrepair; [runtime boundaries](../tests/test_vnext_verified_runtime_boundaries.py) covers receipt/selection link uncertainty and failed replay; [round decisions](../tests/test_vnext_verified_runtime_decision_refs.py) covers nonempty references. | Implemented for stated paths. Nonempty round-decision test is seed-base/single-decision; no automatic demand for every base/count permutation. |

## Evidence that can be carried forward

This pass verified **15 records and 35 distinct retained log digests**, including
failed/intermediate logs, and compared declared unittest counts where available.
A matching digest establishes faithful evidence; it does not turn a failure into
a pass or make an older source current.

**81 distinct methods have passing evidence on the current runtime source:**
76 from the final-state/operator correction and affected regressions, two from
nonempty round decisions, and three from publication prefixes. The source
manifests still match. Two regression logs from the correction used its initial
manifest; only the separate boundary-test harness subsequently changed. The
publication checkpoint preserves its initial assertion failure plus corrected
one-method rerun. The current 81 includes no failed method execution as a pass
and is not a clean full-suite run.

The older Batch A/B/C manifests differ in three runtime files changed by the
matching-mirror durability correction: `vnext_verified_materialization.py`,
`vnext_verified_promotion.py` and `vnext_verified_work.py`. The correction already
reran the two handoff/partial-mirror methods and the mirror-uncertainty method.
The following **ten runtime methods** still need a current-source refresh:

| Existing module | Methods | Why retained evidence needs refresh |
| --- | ---: | --- |
| `test_vnext_verified_runtime_followup` | 4 | Original operator-child/two-promotion and recovery journeys predate the correction. |
| `test_vnext_verified_runtime_faults` | 2 | Batch A actual commit deaths/cross-role exclusion and typed rename uncertainty. |
| `test_vnext_verified_runtime_recovery` | 3 | Batch B Reviewer deaths, orphan recovery and prepared verification. |
| `test_vnext_verified_runtime_verifier_faults` | 1 | Before/after durable-raw Verifier deaths. |

A second, fixed **89-method component cohort** covers storage (32), registration
(21), shared semantic decisions (7), pointer history (9), verified history (10)
and V semantics (10). All have retained passing evidence. Their older broad or
stage records are not a coordinated qualification of today's consuming graph.
Refreshing those existing modules gives the D8/18.7 acceptance map one explicit
current-checkpoint result without rerunning the whole product suite.

The initial 1,153-test reconciliation remains historical: its full run had two
fixture-import failures, followed by separately passing corrected modules.
Legacy/bridge regression evidence exists there; a current release-wide pass
remains an 18.9 gate. No such pass is inferred from the 81 or proposed 99.

## Remaining gates and exact next slice

**G1 — next bounded implementation/test slice: the P0 concurrent-selection
scenario.** Add one parameterized process test, forcing each of two callers to
win acquisition first in separate fresh fixtures. Start with two genuinely
registered, final verified candidates on the same current base and no prepared
intent. Use the existing component history/registration/Verifier fixture to
construct that P0 state; normal runtime scheduling correctly gates new work
behind pending promotion and should not be weakened to manufacture it.

Each run must show: highest creation ordinal selected; lock contender gets busy
with no artifact/client change; intent/event/snapshot bind that candidate;
exactly one next global promotion; fresh second-caller reentry cannot fall back
to the older candidate or allocate another ordinal. Existing reserved-claimant
and nonprefix tests retain their separate scope. This uses two processes of the
same implementation and does not claim cross-implementation determinism.
Validate the new test and the existing promotion/Batch A modules. Change runtime
only if the fixture exposes a defect. This slice does not authorize more modes.

**G2 — finite evidence closeout after G1.** Freeze the source manifest and run the
ten runtime methods plus 89 component methods listed in the JSON. Credit any
identical-source Batch A rerun from G1; do not run it twice. Carry forward the 81
current methods unless G1 changes their dependencies, in which case rerun the
affected coverage. Preserve failures and exact source versions; do not add
counts from overlapping runs. With G1 and this cohort passing, reassess the three
18.7 checkboxes against this map and record the bounded implementation result.

**G3 — earlier-slice dependencies.** Assembly and independent semantic acceptance,
plus their P/semantic/follow-up consuming qualifications, remain separately open
in 18.5–18.6. This storage map does not certify all preservation or semantic-policy
P0 scenarios. Resolve their exact acceptance maps before calling 18.5–18.7 complete.

**G4 — later release gates, excluded here.** D8 requires a new descriptor-bound
consuming suite pinning its normative document, storage envelopes and vectors.
Only frozen `vnext-contracts-1` is in the shipping registry; all three proposal/
semantic/follow-up qualification maps remain empty. Scheduler, Phase 2 and
apply-back consumers belong to 18.8. Complete P0/cross-implementation mapping,
full compatibility regression, separately authorized live soak and advertised
activation belong to 18.9. No new suite, mode, provider call, push or source-spec
apply-back is performed or authorized by this reconciliation.

Batch C's **boundary inventory reconciliation is complete** at the representative
scope above; its current-source qualification remains open under G2. There is no
next generic Batch C fault batch. Keep 18.7 incomplete until its concrete proof,
validation and dependency gates have been resolved.
