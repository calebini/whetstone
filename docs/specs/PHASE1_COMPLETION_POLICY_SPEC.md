# Shared Phase 1 completion policy

Consumer-3 is enabled for explicit Phase 1 selection in the shipping CLI. [Qualification evidence](../PHASE1_COMPLETION_QUALIFICATION.md).

## Ownership and selection

New verified jobs select `scope-aware-phase1-v1` in immutable
`review-configuration-v3`, pinned by `vnext-verified-consumer-3` with closeout v6. The held consumer-2 suite retains closeout v5. The same policy
applies to every selected Phase 1 profile, independently of workflow name.
The initial admission matrix is Standard or MVP with `stateful_system`,
`balanced_mvp`, or `utility_mvp`; MVP requires approved scope. Profile names must
belong to the selected set. Horizontal/vertical full sweeps and horizontal
focused reviews use the same finding policy. Focused completion never establishes
full Phase 1 acceptance. Other workflows and Phase 2 are not enabled by this suite.

Existing configuration versions and suites retain their original replay,
classification, prompt, scheduling, closeout and Phase 2 semantics. No in-place
migration of a job or frozen contract is permitted.

## Obligations and deferrals

An approved deferral must be supported by a bound approved scope contract and
nonempty declared surface IDs, all of which have status `deferred`. It also needs
consistent deferable advice and canonical classification. Unknown or mixed
surfaces, contradictory recommendations for the same issue, unresolved authority,
unknown anchors, requests to change authority/scope, or a cited blocking invariant
prevent deferral. Explicit operator/authority/scope decisions outrank deferral.
The reviewer must report a dependency needed for an in-scope core flow as a scope
or operator decision, not silently defer or expand it. Mechanical policy validates
these structured claims; it does not infer dependency truth from prose.

A major/blocker finding without a justified deferral blocks completion, including
one outside a particular lens's focus. A reviewer-selected `in_scope=false` or
`deferable` alone cannot waive that obligation. Unresolved operator decisions,
authority conflicts and scope changes block regardless of severity. Minor optional
observations do not block unless such a decision or protected obligation applies.
Explicitly cited blocking invariant violations cannot be waived at any severity.

The classification owner preserves this distinction through mutation admission
and replay. The shared completion evaluator uses canonical finding records and
scope evidence. Promotion continues checking candidate integrity, verification,
operator authority and current-base identity, without workflow/profile branches.

## Scheduling and completion

Scheduler work selection, cleanliness, status, failure projections and closeout
use the same blocking predicate. Optional-only reviews do not force an editing
round; a blocking round may still admit permitted minor fixes alongside its
required work. Every required profile must have a completed review of the
current accepted draft. Promotion invalidates prior-draft cleanliness. All
required reviews must be clean before full Phase 1 acceptance. Focused stability
covers only the selected profile. Budget exhaustion never substitutes for these
conditions. An unresolved decision must not be bypassed by a terminal report.

Both closeout versions retain existing receipts, current pointer, budgets and terminal
bindings, and records justified deferred findings with scope surface IDs and
scope hash. Deferred findings remain visible; they are not marked fixed.
Existing raw feedback remains immutable evidence. Technical failure summaries
list blocking residuals rather than approved deferred work.

## Phase 2 boundary

New-policy jobs explicitly report Phase 2 as unsupported and refuse binding or
entry. Existing-suite Phase 2 remains unchanged. Extending Phase 2 requires a
separate policy/contract qualification; Phase 1 completion does not authorize it.

## Qualification before release

Required evidence: pure policy boundary tests; schema/suite integrity and old
suite immutability; coherent Standard/MVP package admission and refusals; full and
focused completion; horizontal/vertical scheduling; approved deferral and
conflicting invariant/authority/dependency cases; real scripted Editor/Verifier
promotion with current-draft re-review; budget exhaustion/extension, interruption
and replay; retained old-suite behavior and explicit Phase 2 refusal. Test the
workflow/profile axes separately and together. Record actual coverage and limits.
Registration is not release qualification. Keep the new production qualification
entry disabled until the qualification evidence is reviewed; do not alter old
release qualification or runtime pins, publish, tag, or install as part of this work.
