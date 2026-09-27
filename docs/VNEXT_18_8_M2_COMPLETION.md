# M2 completion campaign

Started on 2026-09-28 from `a09a6c5` after the user authorized completing M2 as
one delivery outcome. **M2 is implemented and validated at its documented internal
API scope; the user subsequently authorized its local checkpoint.** Push, public
activation, live provider calls, external apply-back and normative specification
edits remain outside this checkpoint's authorization.
The unrelated `notes/future-improvements.md` change is preserved.

Before checkpointing, all indexed cohort evidence and all 635 final source hashes
were revalidated, along with the unchanged unrelated notes. The audit retains
the historical uncommitted status and authority at the time of validation; the
subsequent user instruction authorizes this local commit only.

## Authority and implementation

The scheduler's **Budget-Extension Resume** section authorizes explicit
same-run extension events. D7 requires the descriptor-bound review configuration
to remain immutable. The implementation keeps the baseline configuration and
job identity unchanged and records grants separately; it does not replace the
configuration or permit general overrides. No new product decision is needed.

The separately pinned `vnext_verified_phase1_budget_v1` consumer adds:

- A fenced `extend_phase1_budget(added_rounds_per_profile=...)` operation requiring
  an explicit positive grant, a committed exhausted closeout, current state and
  exact current-draft hashes. It invokes no client. Stable completion, unresolved
  work, stale evidence and Phase 2 binding do not authorize additional capacity.
- Immutable chained grant records, deterministic scheduler event IDs, and an
  auditable `run_state.json.budget_extensions` projection before appended clients.
  Each effective budget is `max(previous_budget, completed_reviews) + grant`.
- Scheduler replay that applies a grant only at its original exhausted boundary.
  Reviewer claim v3 binds the exact grant references consumed by that round.
  Historical claims and synthetic round numbers remain unchanged.
- Recovery of a visible grant before any completed appended round, with no
  duplicate grant or reset of the original client request's attempt allowance.
  Changed grant parameters require resolving the existing operation first.
- Closeout v4 binding the full grant chain, original review receipts, vertical
  merges and final completed round. Historical reports remain immutable. Only
  an already owned compatibility failure-report mirror may be replaced.
- Derived round-state checkpoints under the same fence as appended reviews.
  An incomplete state projection has a client-free recovery action; it cannot
  authorize another appended review. Phase 1 state recovery cannot overwrite
  work after the first Phase 2 Reviewer request is bound.

Horizontal and vertical scheduling retain their original profile order and
cleanliness rules. Focused selection remains limited to its selected profile;
extensions do not turn focused completion into full Phase 1 acceptance.

The separately pinned `vnext_verified_phase2_routes_v1` consumer adds configuration
v3 with the original descriptor-bound horizontal/vertical review mode. It reuses
the existing Phase 2 target policy, sequential profile scheduler, entry commit,
declaration and convergence owners. It consumes complete Phase 1 closeout v1,
v3 or v4, counting a final synthetic vertical round before allocating the first
Phase 2 round. Focused-only completion still refuses entry. Entry continues to
refuse required version maintenance; that remains M3.

Frozen suite definitions and public qualification maps are unchanged. Legacy,
bridge and existing suites do not acquire these routes through their old pins.

## Internal operator sequence

These are `VerifiedRun` APIs for a consuming suite, not newly enabled public CLI
commands. Client calls still require their own payload authorization outside
scripted fixtures.

1. Inspect `phase1_status()` and `operator_status()`. Finish an eligible exhausted
   boundary with `finish_phase1()` and `reconcile_phase1_state()`.
2. Explicitly call `extend_phase1_budget(added_rounds_per_profile=N)`. If grant
   publication or its final state write is uncertain, repeat that same operation
   with the same grant amount and reason; the original event is retained.
3. Continue the existing review/admission/verification/promotion owners. A fresh
   Reviewer request uses `review_next(client=...)`. An incomplete existing request
   requires `review_next(continuation=True, ...)`; complete retained output needs
   no client. Editor/Verifier continuation keeps its existing request-wide limits
   and exact bindings. No generic Phase 2 resume or automatic repair is added.
4. If a completed review's state projection was interrupted, use
   `reconcile_phase1_state()` before another appended review. Source barriers
   repeat; the completed client request is not rerun.
5. Publish and reconcile the new Phase 1 closeout. A standard stable run may bind
   an explicit Phase 2 configuration v3 and enter Phase 2 using the existing
   unchanged-draft entry owner. Configuration publication alone is not entry.

## Verification record

Development and acceptance logs are retained under
`rounds/vnext-18-8-m2-completion-001/`. The delivery source manifest records the
exact Python, contract and normative-source bytes plus the unrelated note hash.
The [completion audit](audits/VNEXT_18_8_M2_COMPLETION.json) indexes **162 distinct
passing methods across 166 executions**: 11 new methods and 151 existing methods.
Twenty-six distinct methods ran on final sources; the remainder retain their
explicit baseline-snapshot scope. This is selected integration/regression evidence,
not a full repository run or release qualification.

The new Phase 2 joined journeys use standard/stateful-system configuration,
the builtin standard-v1 rubric and final/strict target, with no required version
change. They establish the new handoff and clean Phase 2 completion; they do not
claim the full target-by-route-by-fault cross-product.

| Cohort | Methods | Source snapshot | Result |
| --- | ---: | --- | --- |
| Contracts, local storage, Reviewer journals and Editor/Verifier work | 86 | Baseline | Passed |
| Horizontal, focused, vertical and Phase 2 entry regression | 45 | Baseline | Passed |
| New budget/continuation journeys and faults | 9 | Baseline | Passed |
| Existing bridge budgets and Phase 2 maintenance | 20 | Final | Passed |
| Grant barriers, acknowledgement recovery, three selections and repeated grants/promotions | 4 | Final | Passed |
| Horizontal/vertical Phase 2 convergence and final synthetic no-op handoff | 2 | Final | Passed |

The final delta affects only the new budget owner and its test module: repeat the
history/source/mirror checks after durability barriers and before grant commit,
and test configuration drift during that interval. The four final budget methods
cover that change. The core cohort began before the baseline manifest was captured;
only an unimported new-test fault hook changed in between, and its runtime/selected
checks match the indexed baseline. No cohort is represented as testing source
bytes it did not execute.

All 635 final source hashes match the manifest. Compilation and `git diff --check`
passed. HEAD remains `a09a6c5`; the index is unchanged. Normative specs, frozen
suites and public activation files are unchanged. The unrelated note retains
`d00f59d7e61335a980652d696011fb151f2006a4bcb7cc434bf14cab0279f502`.

M2 acceptance is reconciled as follows:

| Required outcome | Delivered evidence |
| --- | --- |
| Focused scheduling remains bounded | Existing focused checks plus a grant/re-review journey; focused stability remains unaccepted globally and cannot establish Phase 2 prerequisites |
| Vertical scheduling retains provenance and accounting | Existing merge/two-promotion regressions plus two grants, two promotions, unchanged historical reports and later clean reviews |
| Explicit extensions append work without configuration replacement | Horizontal, focused and vertical journeys preserve configuration bytes, prior artifacts, request attempts and event identity; invalid/stale/unpublished inputs refuse |
| Supported continuation and recovery | Timeout, exhausted shape allowance, retained response, grant/state interruption, post-review state failure, source drift and lost ownership checks; core Editor/Verifier continuation regressions pass |
| Cross-route Phase 2 handoff | Extended horizontal and vertical roots enter through a distinct entry commit and reach Phase 2 convergence; a final synthetic no-op is counted; the legacy executor is forbidden in the joined journeys |
| Compatibility | Prior V routes and the bridge budget/maintenance cohorts pass; no public mode or frozen suite is activated |

The original 18.8 acceptance checkboxes remain open for the remaining milestones.
M2 completion does not credit M3 version maintenance or M4 source-write authority.

Development failures are not acceptance evidence: initial schemas used two JSON
Schema constructs unsupported by the repository validator; a Reviewer grant
reference initially inherited the narrower verified-pointer path pattern; and
two scripted fault/no-op fixtures needed correction. One retained-response hook
initially interrupted replay of an earlier request instead of the appended
request. Intermediate runs that crossed edits or failed receive no completion
credit. A test-module import also collected existing vertical tests unintentionally;
the final new-test cohort selects the intended classes explicitly.
The superseded `routes-2` development run was stopped after it crossed source
edits; `routes-acceptance` owns the final cross-route result.

This campaign uses scripted local clients and macOS/APFS fixtures. Its new
interruption tests simulate publication failure, acknowledgement loss and lost
ownership. It does not claim a new physical process-kill/power-loss campaign,
live-model reliability, full repository qualification or release readiness.

## Remaining boundaries

M3 must carry required version maintenance through verified candidates. M4 still
requires the normative source-write decision before dependent implementation.
M5 must demonstrate the complete integrated workflow across M1–M4. The separate
18.9 compatibility, process/fault qualification, authorized live soak and public
activation requirements remain open. No extension event bypasses these gates.
