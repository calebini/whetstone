# Phase 2 evidence-backed churn resolution

Implemented and validated from `68a8f6f`, authorized on 2026-09-27. The user
subsequently authorized a local checkpoint after source and evidence revalidation.
This completes the bounded churn-resolution slice, not general Phase 2 or 18.8.
No release qualification is claimed.
The pre-existing `notes/future-improvements.md` edit is unrelated and preserved.
No push, external transmission, public activation or specification change.

## Acceptance and authority

The [oscillation rule](specs/IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md)
requires a churn reset when round R accepted/modified feedback names the tracked
concern and the corresponding issue is absent from the unresolved snapshot before
the next review. The [candidate contract](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md)
requires verification-derived resolution, rather than Editor claims. The
[scheduler](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md) retains D7 preconditions,
budgets and later-review cleanliness requirements. D8 owns publication/recovery.

This slice joins those existing authorities. A separately pinned contract admits
only standard horizontal, unversioned verified Phase 2. A verified but unpromoted
candidate produces no resolution record; an unrelated promotion, silence, partial
resolution or model claim cannot clear an issue.

For each proven correction, an immutable receipt binds its original
configuration, entry, request, consumed feedback/advice, complete consumed review
prefix, previous resolution receipts, exact base/promotion, registered candidate,
final passing decision and semantic verification. It includes a derived
compatibility summary and unresolved snapshot. Observed issues outside the
verified whole-finding coverage remain unresolved; a later occurrence reopens
an issue. A missing receipt gates the next review, while higher-priority signal
and budget gates remain intact.

The V summary exposes `accepted_or_modified_feedback_ids`, the union needed by
the reset predicate. It deliberately does not invent whether a correction used
the Reviewer's exact wording: the candidate protocol does not encode that
legacy distinction. Its separately versioned schema leaves legacy/bridge Editor
summaries unchanged. No root `unresolved_issues.json` mirror is claimed by this
owner, and it does not change other report owners' residual-finding policies.

Only exact committed receipts reset churn, at the next review. They do not
rewrite triggering diagnostics, erase conflict history, reset other oscillation
trackers, grant review budget, mark a profile clean, resolve freeze requests or
establish convergence.

## Internal operations

- `phase2_resolution_status()` reproduces and validates evidence without writes.
- `publish_phase2_resolutions()` publishes missing receipt assets and commits
  under the D8 fence, then stops.
- `reconcile_phase2_resolution_state()` recovers only the namespaced convenience
  projection `vnext_phase2_resolutions`, then stops without clients or scheduling.

Artifacts live at `rounds/phase2/resolutions/pass-N/`. The immutable commit is
authority; the mutable state projection cannot grant or revoke a reset. Reentry
rechecks source and output durability even after an acknowledgement was lost.
Missing committed assets, changed sources, tampered receipts and unknown claims
are rejected. Original suites without the new pin retain their prior behavior.

## Remaining boundaries

Freeze resolution, declaration repair, operator followups/new repair admission,
rubric handling, broader scheduler modes, version maintenance, strop/readback,
and release qualification remain open. All four 18.8 checklist items and 18.9
remain open. No product decision is introduced by this bounded verified-evidence
projection; it grants no new mutation or operator authority.

## Verification and handoff

The [evidence record](audits/VNEXT_18_8_PHASE2_RESOLUTION.json) credits **59 distinct
passing methods across 62 executions**: seven new methods and 52 existing checks.
The new coverage comprises three pure-rule methods and four runtime journeys:

- Exact whole-finding coverage, rejection of partial/unrelated/duplicate claims,
  residual retention and recurrence, key-specific reset, and unchanged other
  oscillation histories.
- A genuine verified correction, pre-promotion refusal, missing-receipt gate,
  read-only status, deferred issue retention, later review and renewed escalation.
- Every receipt publication prefix, source drift during barriers, lost final-state
  acknowledgement, reopen recovery, tampering, missing assets and unknown claims.
- Rejected partial candidate with no receipt or next-review permission.
- Two genuine corrections/promotions with linked receipts, retained deferred
  evidence, original-base replay and immutable earlier receipt bytes.

The existing checks cover oscillation, conflicts, evaluation, contract replay,
older-suite two-promotion continuation and nonblocking conflict history through
promotion/clean closeout. The frozen first suite hash is unchanged and all three
public proposal qualification maps remain empty. The evidence validates 562
source hashes; no authoritative specification files changed.

Early runs exposed an overly narrow feedback-ID schema constraint, corrected to
the existing non-empty-string rule. Already-admitted old fixtures then correctly
refused the changed schema. A later test incorrectly expected a record list before
promotion; the actual D7 `promotion_required` result was correct. That assertion
was corrected and rerun. Four individually passing methods from that cohort are
credited on unchanged runtime/contracts and unchanged methods/helpers; the failed
method is credited only from its corrected passing rerun. The two-promotion test
was appended and passed separately. Raw failed/superseded logs are retained and
are not represented as passing cohorts.

Validation used injected clients and local macOS/APFS storage faults. It does not
qualify physical power loss, process death during a write, live providers,
performance or the full repository. No further runtime change is pending for this
bounded slice. The local checkpoint is authorized; the remaining feature
boundaries above remain open. The audit JSON retains the historical pre-checkpoint
validation status and scope.
