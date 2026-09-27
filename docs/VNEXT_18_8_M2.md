# 18.8-M2 scheduler integration

Started from `bd6c7da` on 2026-09-27. The user authorized M2 implementation.
The user subsequently authorized a local checkpoint of the focused bundle.
No push, public activation, external client call, apply-back or normative
specification edit is included. The unrelated notes edit is preserved unchanged.
The first bounded focused integration bundle is implemented and validated below;
M2 as a whole remains incomplete.

## Route and authority matrix

| Route | Authority | Current integration / delivery boundary |
| --- | --- | --- |
| Horizontal V | Scheduler round scheduling and D7; existing immutable Reviewer, candidate, promotion and closeout owners | Preserve existing behavior and test it alongside the focused extension |
| Focused Phase 1 | Scheduler “Focused Phase 1 Profile Runs” and D7 | First bundle: immutable selected profile within the configured list, same V admission/promotion and client journals, focused terminal and explicit Phase 2 refusal |
| Vertical Phase 1 | Scheduler round scheduling and vertical continuation | Remaining bundle: independently bound reviews on one base, deterministic source-preserving merge, consolidated V Editor transaction, all-profile invalidation, closeout and interrupted-cycle replay |
| Phase 1 budget extension | Scheduler “Budget-Extension Resume” and D7 immutable configuration rule | Remaining bundle: reconcile append-only extension-event authority with descriptor-bound budgets before implementation; no ordinary configuration replacement or implicit budget increase |
| Technical continuation | D7 bounded retry and explicitly supported gates | Existing Reviewer/proposal/verification owners retain frozen inputs and request-wide attempt accounting; focused route reuses them. Vertical partial cycles and extended scheduling still require their own integration evidence |
| Phase 2 continuation | Existing separately implemented phase/gate owners | M2 does not create generic Phase 2 resume |

Normative authority is [scheduler/state/resume](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md).
The original M2 acceptance remains in the [implementation plan](../IMPLEMENTATION_PLAN.md#188-m2--scheduler-and-supported-continuation).

## Focused bundle design

Add a separately pinned review-configuration v2 for an explicit focused Phase 1
selection. Keep the complete configured profile list and budgets immutable; select
exactly one existing profile. This changes the job identity and requires a fresh
root; never retrofit a focused selection onto existing history. The old v1
configuration retains its existing standard behavior.

Only the selected profile can create Reviewer claims or admitted correction work.
Promotion invalidates its cleanliness; Editor or Verifier success cannot establish
focused stability. Complete focused review publishes `FOCUSED_PROFILE_STABLE`;
exhausted unverified focused work publishes `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`.
Neither establishes global accepted-draft status, full Phase 1 stability, nor
Phase 2 entry. Current-base, source, journal and D8 ownership checks remain required.

M2 remains incomplete until vertical scheduling, extension/continuation and the
cross-route acceptance campaign have their own implementation and evidence.

## Implemented and validated focused boundary

The internal `VerifiedRun` path now consumes review-configuration v2 through a
versioned reader. The descriptor hash freezes the selected profile together with
the complete profile list, budgets and roles. The new focused algorithm and
schemas must be pinned; old suites do not gain the route. Staged rounds and
unselected direct Reviewer requests refuse. Changing the selection is a new job,
not a same-root continuation.

Ordinary `review_next`, `admit_reviewed_round`, proposal/registration/verification
and promotion owners handle focused work. The selected profile's completed
review count survives promotion, while its cleanliness becomes unverified.
Status exposes `focused_profile_clean` separately and keeps `all_profiles_clean`
false. An out-of-focus major remains global debt without falsifying a clean
focused review. `accepted` stays false, even for a single-profile configuration.

Round publication retains canonical feedback/advice, before/after snapshots,
profile metadata, prompt references and a no-op summary when no mutation is
admitted. Existing durable client journals retain raw responses and attempts.
Focused reviews conservatively invalidate on every promotion and pin the full
reviewed section set in their profile metadata; no semantic skip optimization is
introduced. Promoted mutation snapshots remain owned by the existing verified
materialization service.

Closeout v2 binds the review configuration, selected profile and optional
technical failure report. Its fixed path prevents a changed report from silently
becoming another committed closeout. Publication and recovery repeat source
durability barriers. Recovery projects the focused terminal and
`ready_for_phase_2: false` into run state, and materializes a residual technical
report from committed evidence. It invokes no client. The existing Phase 2
prerequisite owner explicitly rejects focused-only completion.

This is an internal API integration, not public CLI activation or full M2
acceptance. Vertical scheduling, extensions and their continuation/status
campaigns remain open. Existing standard v1 behavior is a regression requirement.

## Development evidence

Local scripted-client logs are under `rounds/vnext-18-8-m2-001/`. The initial
clean smoke journey passed. The first expanded cohort exposed report timestamps
with unsupported subsecond precision and a test using the wrong binding method
name. Both were corrected. The next cohort caught use of the draft/state materializer
for a report path; the corrected owner uses immutable report publication, refuses
an unowned conflicting report and repeats its durability barrier on recovery.
Code review also added explicit version-type and Phase 1 profile-membership guards.
Earlier failed and superseded runs receive no delivery credit.

No physical process-kill/power-loss, live-provider, performance or full-repository
qualification is claimed. The documented focused fault checks simulate source
drift, immutable evidence tampering, publication interruption, acknowledgement
loss and final ownership loss on local macOS/APFS fixtures.

## Verification and handoff

The [focused audit](audits/VNEXT_18_8_M2_FOCUSED.json) indexes 111 distinct passing
methods (12 new, 99 existing) across 118 executions and two frozen 611-file
snapshots. This is selected regression evidence, not full-repository qualification.

| Cohort | Methods | Snapshot | Result |
| --- | ---: | --- | --- |
| Horizontal review, Phase 1 status/closeout/operator and Phase 2 prerequisites | 38 | Corrected | Passed, 525.317s |
| Contracts, unit preflight, proposal package and native Editor adapter | 61 | Delivery | Passed, 29.629s |
| Focused journeys/faults and configuration dispatch | 12 | Delivery | Passed, 130.273s |
| Phase 1 operator recovery regression | 7 | Delivery | Passed, 61.023s |

The seven operator methods overlap the broader runtime cohort and are counted
once. Eighty distinct methods passed on delivered sources; 31 additional methods
remain evidence at the earlier corrected snapshot. The five-file delta consists
of configuration dispatch/profile validation, focused report publication, the
focused tests, a review-owner docstring and removal of a redundant preflight check
on the standard Reviewer finish path. No cohort crossed a source edit. All 611
final source hashes and indexed logs were verified; compilation and
`git diff --check` passed. At that verification snapshot HEAD was `bd6c7da`
and the index was empty. Normative
specs/frozen suites/public entry points are unchanged, public qualification maps
remain empty, all eight original 18.8/18.9 checklist items remain open, and the
unrelated note retains its original hash.

The focused configuration, guarded correction/promotion, selected-profile
re-review, scoped completion/exhaustion and report/state recovery boundary is
complete at this internal API scope. No new product/authority decision was needed
for this bundle. Focused Reviewer timeout, shape retry and retained-response
continuation are tested; this does not qualify every focused Editor/Verifier fault
combination or a new generic resume interface.

**Next bounded bundle:** vertical Phase 1 integration. Preserve independent
profile reviews on the same verified draft, deterministic finding provenance and
ID collision handling, one consolidated V correction, and all-profile re-review
after promotion. Finish that bundle's status, exhaustion and recovery cases
together. Budget-extension events and specifically supported continuation remain
the following bundle; reconcile their event authority with the immutable baseline
configuration before writing. M3 version maintenance, M4 source-write authority
and M5 integrated acceptance remain separate. This evidence record adds no commit, release or external-write authorization.


## Local checkpoint authorization — 2026-09-27

The user authorized this focused bundle’s local commit with “let’s commit.”
Before staging, all 611 delivery source hashes and 15 audit references were
reverified, along with the baseline HEAD and unchanged unrelated note. Staging
then exposed one extra blank line at the end of the new focused test file; it
was removed without changing test code. This whitespace-only change is the sole
source delta from the delivery manifest; tests were not rerun for it. The audit
retains its historical pre-commit status. The checkpoint excludes the unrelated
notes edit; M2 remains incomplete. Push, activation and external writes remain
deferred.
