# M2 vertical Phase 1 integration

Implemented and validated from `1d39057` under the user's next-slice authorization.
This is internal standard V Phase 1 integration. The user subsequently authorized
a local checkpoint. No public mode, external provider, source apply-back or push
is included. The
pre-existing `notes/future-improvements.md` edit is excluded.

## Authority and scope

The [scheduler](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#round-scheduling-algorithm)
owns independent same-draft profile reviews, deterministic consolidation,
profile accounting, conservative post-mutation invalidation and reporting.
Its D7 and vertical timeout-continuation rules retain prior completed reviews
and bound attempts to one logical request. The existing D8 single-host fence
owns publication and recovery. No new product/authority decision is needed.

A separately pinned vertical algorithm and additive merge/closeout schemas admit
this route on immutable standard vertical configuration v1, with fresh runtime
rounds. Focused selection, staged rounds and absent pins cannot enable it. Frozen
suite definitions and public qualification maps remain unchanged.

Each eligible profile receives its own exact-base prompt/context snapshot,
resolved focus anchors, before/after no-op snapshots, canonical feedback/advice,
raw-response journal and telemetry. Profiles run serially under the existing
single-writer fence; this slice introduces no concurrent clients or writers.

A cycle with feedback allocates a distinct `profile: vertical` consolidated
round. The merge commit binds every source receipt, source feedback and advice,
configuration and base pointer. It preserves issue IDs/fingerprints, rewrites
colliding feedback IDs in stable source order and keeps original IDs/profiles in
provenance included in Editor and Verifier context. Deterministic classification
continues to enforce authority, scope and operator decisions. Only consolidated
rounds enter the ordinary V candidate/verification/promotion path.

A promoted consolidated correction invalidates every clean-profile observation,
even on equal-byte promotion. Profile review counts survive. Further cycles use
only profiles with remaining pinned capacity; an exhausted unverified profile
prevents stability. Profile counters exclude synthetic rounds; total round budget
includes the sum of profile budgets plus their maximum. No implicit extension or
optional extra verification-only closeout cycle is enabled by this pin.

All-clean current-base reviews still face global blocking-debt checks. Stable
Phase 1 publishes its ordinary stable terminal; failed global acceptance or
exhaustion produces `TARGET_NOT_REACHED` with current profile verification debt.
Closeout v3 binds the configuration, review receipts, merge commits and technical
report. Its fixed path and repeated source barriers protect publication/reentry;
operator reconciliation projects committed reports/state without clients. Terminal
state and technical reports identify the last completed round, including synthetic
rounds; terminal scheduler status does not advertise a next review round.

## Boundaries retained

This slice establishes Phase 1 prerequisites only. Existing Phase 2 configuration
schemas remain horizontal-only; this work does not reinterpret vertical as
horizontal, publish a Phase 2 configuration, or enter Phase 2. Cross-route Phase 2
handoff needs its own versioned configuration/closeout consumer coverage before
M2/M5 acceptance. The first Phase 2 round must account for a final synthetic
no-op round, not only the largest independent review number.

Budget-extension events and their reconciliation with immutable configuration
remain the next M2 bundle. No generic resume, version maintenance or source-write
authority is added. M3–M5, full 18.8 acceptance, and 18.9 remain open.

## Verification

Development and verification records are retained under
`rounds/vnext-18-8-m2-002/`. The initial two-method smoke passed. The expanded
development cohort is excluded from acceptance: it crossed a schema edit, which
correctly triggered installed-schema drift rejection, and an overly broad fault
hook interrupted earlier source replay rather than the pending response. The
hook was narrowed to the exact request/attempt before the frozen campaign.

The first frozen campaign passes all 13 new methods (11 runtime and two pure
merge tests). It covers independent clean reviews; consolidation and original
provenance through promotion; explicit timeout continuation plus retained-output
recovery; three merge/proposal publication interruption points; exhaustion and
state-write acknowledgement loss; source/provenance tampering; no-op consolidation
with global out-of-focus debt; shape retry accounting and configuration drift;
source barriers, closeout acknowledgement and ownership loss; two promotions,
including an equal-byte second promotion; and unequal profile budgets.

Final review tightens terminal round reporting and removes an unnecessary change
to old staged-root admission. Runtime vertical scheduling still requires a fresh
root through its existing sequence guard. The [closing audit](audits/VNEXT_18_8_M2_VERTICAL.json) distinguishes earlier
evidence from the rechecks of these final changes.

No live provider, physical process-kill/power-loss, performance, complete legacy/
bridge suite, or full-repository qualification is claimed. Clients are local
scripted fixtures and the new faults are injected on macOS/APFS. Existing legacy
and bridge executors and public entry points are unchanged.


## Final verification and next step

The audit records **137 distinct passing methods**: 13 new and 124 existing,
across 148 credited executions. **86 distinct methods passed on final sources**;
51 are credited only at the earlier frozen snapshot. Both snapshots contain 616
hashed source/contract/test files. The eight-file delta is limited to terminal
round reporting, the additive closeout field, restoration of prior staged-root
admission, and matching test assertions.

| Cohort | Credited methods | Snapshot | Result |
| --- | ---: | --- | --- |
| Contracts, preflight, package, native adapter, semantic context and follow-up preflight | 74 | Final | Passed, 54.432s |
| Horizontal/focused review, Phase 1 status/closeout/operator and Phase 2 prerequisites | 49 | Earlier frozen | 49 individual passes; one diagnostic-message assertion failed in the 50-method cohort, 662.477s |
| New vertical journeys, faults and merge rules | 13 | Earlier frozen | Passed, 507.198s |
| Complete Phase 2 prerequisite regression module | 8 | Final | Passed, 142.614s |
| Vertical clean/no-op closeout, exhaustion/state recovery and final ownership | 4 | Final | Passed, 138.200s |

Seven prerequisite tests and four vertical tests overlap earlier passes and are
counted once. The old unsupported-mode assertion expected “standard horizontal”;
the route now correctly refuses a missing vertical contract pin. The assertion
was updated to that guard, and all eight prerequisite tests pass on final sources.
The earlier 74-method core run is superseded by its final-source rerun. No failed
or interrupted method receives passing credit.

Compilation and whitespace checks pass, including new untracked files. Final
source hashes and audit references were verified. At that verification snapshot,
HEAD was `1d39057`, the index was empty, and the unrelated notes edit retained its
original hash. Normative
specs, frozen suites, public activation maps and legacy/bridge executors are
unchanged. All original 18.8/18.9 checkboxes remain open.

**This bounded internal vertical Phase 1 bundle is complete; its local checkpoint
is authorized. M2 is not complete.** Next: reconcile and implement explicit Phase 1 budget-extension
events and the specifically supported continuation gates. Preserve the immutable
baseline configuration; a changed configuration cannot masquerade as continuation.
Vertical-to-Phase-2 handoff remains a separate known integration boundary within
M2/cross-route acceptance. No new product decision blocked this bundle. M4's
previously documented source-write authority dependency remains outside this work.
Push, public activation and external apply-back remain deferred.


## Local checkpoint authorization — 2026-09-27

The user authorized this bundle’s local commit with “let’s commit.” All 616 final
source hashes and 15 audit references were reverified before staging. Runtime,
contract and test sources remain identical to the final recorded snapshot; no
test rerun was needed. The audit retains its historical pre-commit status. The
unrelated notes edit is excluded. M2 remains incomplete.
