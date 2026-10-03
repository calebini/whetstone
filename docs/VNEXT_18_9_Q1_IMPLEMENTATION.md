# 18.9 Q1 implementation handoff

Started 2026-10-02 from `78dfa8b27b896e3d90e990774aebfd80b7e40486`, following
operator approval of the bounded amendment/interface package. **Q1 is incomplete.**
The operator authorized this partial implementation checkpoint on 2026-10-02.
Production qualification remains empty; no live provider calls, real external
apply-back operations or pushes have occurred during this implementation.

## Applied and implemented so far

The approved amendment patch was applied to the six specification owners and the
Operator Quickstart. The proposal and implementation plan now distinguish that
ratification from implementation and release qualification.

A separate config-selected V dispatcher now opens `VerifiedRun`. Fresh bootstrap
shares the package copier with P but uses a V seed validator; it initializes only a
nonexistent root, retains immutable inputs and materializes the seed through D8.
Reopening resolves retained mode even without config selectors. New work requires
matching V config; public qualification remains an independent exact-digest gate.

`vnext-verified-consumer-1` is staged and registered **offline only**. It pins the
installed schema/algorithm closure and existing vectors plus four Q1 schema
vectors. `vnext-contracts-1` remains unchanged. This consuming manifest
is not release-qualified and does not establish coverage of every pinned feature.

Command adapters have been written over existing owners for Phase 1, distinct
Phase 2 entry and execution, operator/semantic inputs, bounded recovery and source
operations. The new Phase 2 native transport retains the complete review/rubric
response shape and leaves attempts to the existing journal. A command-selection
guard rechecks selected boundaries inside actual D8 owner fences, including the
selected promotion's projection fence. Guard integration across the full command
surface remains part of Q1 acceptance. These are implementation drafts; the
evidence below establishes only tested paths.

## Adopted direct Reviewer handoff decision

On 2026-10-02 the operator selected direct Reviewer-to-Orchestrator guidance,
with human involvement for product or authority decisions. This supersedes the
proposed routine `--advice FILE` handoff. Guidance accompanies each Phase 2 review
that has findings, including later rounds; Phase 2 entry itself requires no advice.

The new [Reviewer advice supplement](../contracts/algorithms/vnext_phase2_reviewer_advice_v1.md)
pins `vnext_phase2_rubric_response_v2`: `review`, `rubric_findings`, and advisory
`classifications`. Whetstone computes all job, draft, feedback and authority
bindings, validates exact finding coverage, and applies the existing conservative
classifier. After result consumption, the command consumer binds that evidence
through the existing D8 advice owner before correction admission. No extra model
request or routine human-authored file is needed. Sensitive product, policy,
scope, protected-invariant and authority findings still stop for explicit decisions.

Old suites retain their v1 response and explicit advice contracts. The optional
`--advice` operand cannot replace new-suite Reviewer guidance: it must exactly
match the retained response's derived packet. Interrupted attachment publication
is recovery-only and cannot start an Editor or another review.

## Acceptance inventory

| Q1 acceptance case | Current evidence / remaining work |
| --- | --- |
| 1. Fresh config-selected admission | Focused CLI tests exercise injected exact qualification, dry-run, fresh initialization and V reopening. Production gate remains empty. |
| 2. Unknown/unqualified/conflicting selectors | Public refusal, suite conflict, existing destination and no-client/no-write assertions covered; expand the selector/Phase 2 Ref matrix. |
| 3. Retained mode | Removed config selectors still select V status; new work without mode refuses. Broaden edited-selector negative cases. |
| 4. Genuine verification/promotion/entry/convergence | Clean unversioned horizontal command journey passes through distinct entry and two real scripted review owners to convergence. A first-pass automatic Reviewer-to-Editor-to-Verifier correction now passes through one durable promotion, declaration preparation, follow-up reviews and convergence, including report recovery. Versioned `promote-phase2` now passes a system-only candidate through independent verification, promotion and distinct entry, including entry recovery. Versioned convergence, vertical/focused and the remaining target combinations still need command-level evidence. Core M1–M5 tests are prior owner evidence, not substitute command qualification. |
| 5. Status/recovery | Storage selection-guard tests pass. Focused Phase 1 stale-selection race, timeout, read-only dry-run, refusal of implicit retry and explicit continuation cases pass. The direct Reviewer campaign also passes a later-pass interrupted advice attachment, read-only dry-run and repair-only resume without another client. The post-promotion journey also passes historical entry-projection repair, resolution and converged-closeout publication/projection repair, lost final-state acknowledgement and terminal reentry. The Reviewer-resume campaign adds first/later timeout continuation, failure publication/projection repair before retry, lost continuation-state acknowledgement, retained valid-response reuse, exhausted refusal and Phase 2 rejection of `--continue`. The original ratified 12-row table plus the advice-attachment row remain unqualified as a complete set: prepared registration/decision/promotion, other report/terminal families, remaining interruption points and Phase 1 repair-only `--continue` need complete command evidence and any resulting fixes. |
| 6. Separate source approval | Adapter tests cover envelope/null/noncanonical/duplicate-key/hash rejection, explicit operands and recovery bypass of fresh eligibility using a recording owner. Real disposable-fixture command apply/retry, uncertain write, pointer advancement and historical drift journeys remain to run. No real external source was written. |
| 7. Compatibility and disabled production | The package regression and storage/native/proposal CLI batch pass. The final direct-handoff run also passes the legacy CLI suite and old explicit-advice owner tests. Broader legacy/bridge/R/P route qualification remains Q1 work; release-wide qualification remains Q3. |

## Verification

- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_vnext_proposal_package.py -q`: 13 passed, 20.474s.
- `PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_command_guards test_vnext_native_phase2_reviewer test_vnext_proposal_cli -q`: 56 passed, 105.750s. Imported fixture test classes also exercise the existing storage and native Editor regressions.
- The first isolated clean Phase 2 command journey passed in 146.179s. This is useful correctness evidence, not a replay performance qualification.
- `PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_cli test_vnext_verified_source_cli -v`: 10 passed, 191.877s, including the clean Phase 2 journey, Phase 1 race/timeout and source operand tests.
- Subsequent focused `test_bound_configuration_is_not_entry_and_changed_selector_refuses`: passed, 18.336s; config publication cannot authorize resume/entry, and a changed Phase 2 Ref refuses without writes.
- Final public-refusal/reopen tests plus `test_cli`: 41 passed, 8.959s. This also exercises the existing legacy CLI suite, including disposable-fixture apply-back.
- `compileall`, `git diff --check`, reverse applicability of the approved amendment patch, and offline validation of both suites passed. All production qualification maps are empty.
- No test worker remains running. The unrelated notes file still has SHA-256 `d00f59d7e61335a980652d696011fb151f2006a4bcb7cc434bf14cab0279f502`.

The earlier 10-test campaign preceded the final selector/phase-label tightening;
subsequent focused checks cover those boundary changes. Those earlier runs used
the prior response envelope and establish no correction/promotion, versioned,
full recovery-table or real V source-write command journey. They are not final Q1
qualification. The direct Reviewer handoff verification is recorded separately below.

## Direct Reviewer handoff verification

Evidence is retained under `rounds/vnext-18-9-q1-reviewer-handoff-001/`.
The first three-case command campaign passed the product-decision stop and
later-pass interrupted-attachment recovery. Its correction case exposed a
read-only command-selection bug: status constructed a live admission helper
requiring a borrowed fence. Selection now uses the proven read-only transaction
router and checks its exact current base. The correction test explicitly checks
that proposal status takes no writer fence and changes no files.

The next correction run stopped before promotion. Inspection found the staged
consumer selecting `semantic-policy-v1`, whereas the delivered semantic owner
requires `semantic-policy-v2`; the consumer dispatch is corrected.
A focused check now guards this pairing and the frozen older suite's v1 dispatch.
A redundant diagnostic run was deliberately stopped by expiring its supervision
lease; this was not a performance timeout or successful test. Failed/aborted logs
remain evidence and are not counted as passes.

The final combined run passed **52 tests in 912.317s** (912.914s supervised wall
clock, 60% duty limit). It covers the v2 response/authority classifier, exact native
provider projection, v1 response compatibility, older explicit-advice owner
including interruption/tamper checks, the legacy CLI suite, clean Phase 2 entry
and convergence, and one automatic source correction through Editor, independent
Verifier and durable promotion. The correction case asserts exactly one Editor
call, one Verifier call and promotion ordinal 1, then deliberately stops at that
boundary; it does not claim post-correction convergence. The two earlier passing
operator-stop/later-advice-recovery cases used the pre-correction staged policy
selector; they exercise no semantic invocation and are retained as scoped evidence,
not a final full-matrix qualification run.

`compileall`, `git diff --check`, both offline suite validations and a fresh CLI
help check passed. The frozen suite digest is unchanged. The V/P/semantic/follow-up
production qualification maps are empty. The verification workers have all
exited. No live provider, real external apply or push occurred.

Final verification results and the exact runtime input hashes are recorded in
`verification.json` in that directory. Tests use scripted clients, disposable
local D8 roots, one supervised worker, a 60% duty limit and finite deadlines.
This remains bounded implementation evidence, not suite-wide qualification or
permission to activate V, invoke live providers or apply to external sources.

## Post-promotion continuation verification

Started from checkpoint `de09ab5` on 2026-10-02. This bounded slice covers one
unversioned horizontal final/strict correction through promotion, resolution
publication, declaration preparation, follow-up review and convergence. It uses
the ratified scheduler recovery row and existing owners; no new product policy,
scheduler, contract pin or public mode is introduced.

The command selector now exposes pending findings and closeout publication and
prepares a scheduled strict review's declaration package before binding its
request. Later review execution reselects the committed request under its actual
D8 fence. Resolution and closeout recovery publish and project only the selected
outcome, with fresh selection at each fence; a changed outcome cannot be projected.

Committed entry inspection/recovery now uses its proven original ancestor after
a correction advances the pointer, preserving the actual current-head/read
guards. Uncommitted entry still requires the current head. Versioned historical
entry replay now matches the older historical branch: immutable entry evidence
proves the past; its mutable state projection does not. Live projection validity
remains with the entry owner.

The complete command journey passed **1 test in 5,259.147s** (5,259.655s supervised
wall time, 60% duty limit). It asserts exactly three Phase 2 Reviewer calls, one
Editor call, one Verifier call and promotion ordinal 1 through these boundaries:

- Interrupted resolution publication, followed by removal and recovery of the
  derived historical entry reference, without replacing the entry or advancing work.
- Read-only status/dry-run, refusal of implicit live-command repair, and explicit
  resolution publication plus state recovery that stops before another review.
- Post-correction declaration preparation and follow-up reviews, then interrupted
  closeout publication with the same read-only/refusal checks.
- Lost acknowledgement after the final state write, independent `CONVERGED`
  status, unchanged completed-run reentry and refusal of an unnecessary resume.

The focused regression batch passed **18 tests in 723.389s**: four publication
selection/fence tests, three invocation-guard tests, eight existing entry
interruption/tamper/barrier tests, the supported versioned-entry owner test, clean
Phase 2 command convergence and disabled public-admission refusal. Together with
the composed journey, **19 tests passed on the final runtime/test source hashes**.
Targeted compilation, whitespace checks and both suite validations passed; all
production qualification maps remain empty. All workers from this slice exited.
The full fault/reentry journey took **87.7 minutes** at the stated duty limit.
That is a practical qualification cost, not an isolated promotion benchmark or
production-throughput claim. Replay profiling/optimization remains Q3 work.

Evidence is retained under `rounds/vnext-18-9-q1-post-promotion-001/`, including
exact input hashes, failed and completed logs, and four stable disposable-fixture
snapshots for diagnosis/replay profiling. `verification.json` records the exact
commands, outcomes, source hashes, preserved-file hashes and scope limits. Two
earlier attempts expired their
supervision leases and count as neither passes nor assertion failures. Three
actual failures exposed the entry-base, mutable historical projection and missing
declaration-preparation defects described above. The successful run used one
worker, a 300-second lease and a finite 6,000-second ceiling. No live provider,
real external source write, public activation, commit or push occurred.

## Versioned entry command verification

Started from checkpoint `7bb66f6` on 2026-10-02. This slice exercises the
config-selected `promote-phase2` dispatcher for one supported numeric heading
and matching status anchor (`0.17` to `1.0`), horizontal final/strict inputs.
Authority is the candidate leaf's **Scheduler-authorized system metadata**, the
scheduler's declared `promote-phase2` route and finite recovery table, and the
pinned `vnext_version_entry_v1` / `vnext_verified_commands_v1` algorithms.
No policy or specification amendment is required.

The adapter now revalidates the selected configuration bytes and any committed
configuration binding inside every entry-operation D8 fence, including version
preparation, verification, promotion and entry. Initial request/configuration
binding also uses the command-selection guard. Existing owners continue to
validate prerequisites, exact pointers, request, rubric and source barriers.

Evidence is retained under `rounds/vnext-18-9-q1-version-entry-001/`.
The composed command test passed **1 test in 359.132s** (359.546s supervised
wall time, 60% duty limit). It injects stops before entry publication and after its
commit but before projection. It checks promotion is not entry, ordinary commands
cannot implicitly recover, explicit resume stops after projection, and reentry
does not repeat a stamp, client or promotion. Exact totals are one independent
Verifier invocation, zero Editor or Phase 2 Reviewer invocations, and promotion
ordinal 1. A separate race test changes the
selected configuration at the actual initial-binding and version-preparation
fences and proves refusal without authority writes. Its focused regression batch
passed **50 tests in 552.460s** (552.940s supervised wall time, 60% duty limit):
that race test, three invocation-guard tests, four publication-command tests,
clean unversioned Phase 2 convergence, bound-configuration refusal, disabled
public admission and 39 legacy CLI tests. **51 distinct tests passed** across
the two successful runs. All clients are scripted; production qualification
remains disabled. Both workers exited and the bounded-worker lock is available.

The initial journey attempt failed in test setup because `promote-phase2` has no
`--dry-run` operand. The test now uses supported read-only `status` and
`resume --dry-run`; no CLI capability was added. That failed attempt is retained
and not counted as a pass. The journey's executed method and runtime remained
unchanged while it ran; the separate race method was added during that run and
then executed in the regression batch. Exact commands, logs and final source
hashes are recorded in `verification.json`. Targeted compilation and whitespace
checks passed; both suite digests are unchanged and all four production
qualification maps remain empty. No live providers, external source apply-back,
specification changes, commit or push occurred in this slice.

This scope does not qualify versioned Phase 2 convergence, all numeric anchor
forms, the full recovery table or the remaining route/target matrix. Q1 remains
incomplete.

## First-review command fencing

Started from `16e3fbd` on 2026-10-03. This slice addresses declaration
preparation, first Reviewer request binding and first invocation through the Q1
command adapter. The scheduler's declared `live-phase2` route and finite resume
table, plus `vnext_verified_commands_v1`, supply the authority. No new recovery
row or specification amendment is introduced.

Read-only first-review selection now reproduces the declaration package through
the existing owner and records visible request-input/prompt dependencies. The
adapter guards declaration preparation and request binding separately, reselects
after each, and invokes the first Reviewer through the same guarded
`pending_review` branch used by later reviews. Peer completion or changed
preparation bytes cannot silently advance the stale invocation.

Partial declaration/request publication remains preparation on `live-phase2`.
Without a started client request or another retained recovery condition,
`resume` refuses. A committed, unstarted request may be invoked once by ordinary
`live-phase2`; it does not consume a technical retry allowance merely because
its publication acknowledgement was lost. Existing owner barriers, immutable
inputs and attempt budgets continue to apply.

The two new command journeys passed **2 tests in 552.412s** at a 60% duty limit;
evidence is retained under `rounds/vnext-18-9-q1-first-review-001/`.
The publication journey injects lost acknowledgements after a declaration asset,
request inputs and the request commit. Read-only status acquires no writer fence;
plain/dry-run resume refuses those unstarted preparations without writes or
clients. Ordinary reentry invokes the Reviewer once and stops at its product
decision, retaining the exact request, entry and current pointer. The peer-race
journey advances declaration preparation, request binding and review completion
immediately before each selected invocation acquires its actual fence. All
three stale commands refuse before further writes or calls; subsequent result
consumption does not repeat the peer's one Reviewer invocation.

The fixed regression batch passed **12 tests in 907.568s** (908.038s supervised
wall time): three invocation-guard tests, four publication-command tests, two
request/client source-barrier tests, versioned entry with recovery, clean Phase 2
convergence and disabled public admission. Together, **14 distinct tests passed**
on the final runtime/test sources. Both runs used one worker at a time, a 60%
duty limit, 300-second supervision leases and finite deadlines. The two new
journeys took 552.912s supervised wall time; the combined test cost was about
24.3 minutes at that duty limit. This is qualification cost, not a single-review
latency or production-throughput measurement. Replay optimization remains Q3.

Exact commands, results, logs and source hashes are retained in
`verification.json` in the evidence directory. Targeted compilation and
whitespace checks passed; both suite digests are unchanged and all four
production qualification maps remain empty. Both workers exited, and the
bounded-worker lock is available. The unrelated notes and pre-existing audit
report retain their original hashes. No live providers, external source writes,
specification amendments, commits or pushes occurred in this slice.

Broader client-timeout/result-publication continuation,
remaining report composition, route/target and source-operation qualification
remain outside these cases. Q1 remains incomplete and production gates remain
empty.

## Reviewer continuation and failure recovery

The previous first-review slice was checkpointed at `7a4eb17`. This slice stays
within Q1's existing finite continuation table in
`SCHEDULER_STATE_AND_RESUME_SPEC.md` and `vnext_verified_commands_v1`; it introduces
no new recovery permission or retry allowance.

Explicit resume of a retained Reviewer failure publication now completes that
failure's reports and state projection, then stops. Publication and projection
use separate real owner fences, with an exact-outcome check between them.
Continuation remains a separate invocation after the repair is current.

First/later Phase 2 Reviewer continuation now projects its own retained failure
outcome, including clearing an earlier active failure after a valid response.
Selection carries the journal's request, pass, attempt count, last outcome,
receipt and consumption status. The adapter checks those against the returned
result and current pointer before projection, and rechecks selection inside the
projection fence. A peer completing or consuming another outcome ends the stale
invocation. Resume stops before result consumption, advice, correction or another
review; ordinary `live-phase2` cannot implicitly retry, and Phase 2 still rejects
`--continue`. Complete retained valid output can finish its receipt without
another client call.

The three new config-to-command journeys passed **3 tests in 1006.234s**
(1006.805s supervised wall time) at a 60% duty limit:

- First-pass timeout, interrupted failure publication, repair-only resume,
  successful explicit retry and lost acknowledgement after the final failure
  state write. Reentry does not repeat the Reviewer; the request, historical
  failure records and current pointer remain unchanged.
- Clean first pass followed by a second-pass timeout, projection-only repair
  and another timeout on the last retained attempt. Status exposes exhaustion;
  resume/live reentry cannot spend another allowance or consume the result.
- Valid retained response with interrupted result-receipt publication. Resume
  finishes the receipt with no client call and stops before consumption.

All three check read-only status/dry-run, refusal of implicit live-command retry
and Phase 2 refusal of `--continue`. Fixtures forbid live providers and legacy
full-draft execution. Evidence is retained under
`rounds/vnext-18-9-q1-reviewer-resume-001/`.

The fixed regression batch passed **14 tests in 505.605s** (506.038s supervised
wall time): three invocation guards, five publication-command tests, four
Reviewer-continuation guards, clean Phase 2 convergence and disabled public
admission. The new guard tests exercise exact-result projection, result
replacement, peer consumption at the projection fence and peer advancement to
another role. Together **17 distinct tests passed**, including eight new methods.
Both campaigns used one worker at a time, 60% duty, a 300-second heartbeat lease
and finite deadlines. Combined supervised test time was about 25.2 minutes;
this is qualification cost, not production latency.

Source scope is explicit: the journey worker loaded the implementation before
two result-selection lookups were hardened to refuse a peer's different-role
selection without a `KeyError`. The final regression exercises both matching
and changed selections on the hardened sources. The three journey tests were
not repeated after that narrow defensive change. `input-snapshot.json`,
`regression-input-snapshot.json` and `guard-hardening.json` record this distinction;
`verification.json` records exact commands, results, logs and source hashes.

Targeted compilation, whitespace checks and offline suite validation passed.
Both suite digests are unchanged, all four production qualification maps remain
empty, both workers exited and the bounded-worker lock is available. The unrelated
notes and pre-existing audit retain their original hashes. This new slice is
uncommitted; no push, live provider call, external source write or specification
amendment occurred. There is no new product/authority blocker for this slice.
Other report families, remaining interruption points and the broader route/target
and source-operation matrix remain open. Q1 is incomplete.

## Resume the implementation

The direct Reviewer handoff decision is resolved. Its implementation and
verification are recorded above; the broader Q1 command qualification remains
open. Continue the **same Q1 package**, without creating another delivery
milestone or marking any acceptance row complete early. Finish the remaining
adapter/recovery paths and their seven-case evidence, reconcile
the supported-command matrix with actual results, then perform the bounded review.
In particular, finish the other report/terminal publication and projection
compositions, later declaration-preparation interruption coverage, semantic follow-up
selection, remaining execution/recovery configuration and request-selection
boundaries under the fence. Versioned convergence, vertical/focused/target command routes and
the disposable V source-apply/retry/recovery journeys remain open. Do not infer
that a written adapter has passed those cases.

Versioned `promote-phase2`, first-review preparation/invocation and the bounded
first/later Reviewer continuation cases now have command evidence above; do not
repeat them as unimplemented owners or infer qualification of every interruption
point. The next bounded command work is the remaining correction-failure and
signal report publication/projection compositions: select one retained outcome,
complete its reports/state under fresh fences and stop without a client or
successor operation. Preserve the finite resume table; do not infer a generic
Phase 2 continuation. Keep this within the same Q1 package and its offline
qualification gate, then continue the remaining terminal, route/target and
source-operation acceptance inventory.

Keep Q2's seven P0 gaps, Q3 replay/full qualification and Q4 live soak/activation
separate. Preserve `notes/future-improvements.md` and the pre-existing untracked
`docs/audits/VNEXT_18_9_Q1_BOUNDED_AUDIT_002.md`. Audit reports remain uncommitted.
