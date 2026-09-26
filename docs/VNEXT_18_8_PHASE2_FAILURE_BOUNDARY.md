# Phase 2 Reviewer failure boundary: authority check

Inspected at checkpoint `e84995a726f23641bd3cfdf7fe1aa9e5e82d972f`.
This is an implementation-boundary investigation, not a runtime change or a claim
that general Phase 2 failure handling is complete. The working tree was clean at
entry. No authoritative specification is changed.

## Decision

The specs establish authority for a bounded Phase 2 Reviewer failure-reporting
lifecycle and the existing, explicitly selected component continuation. No new
product decision is required for that scope. Generic Phase 2 resume, additional
attempts, changed frozen inputs, new scheduling or repair policies are excluded.
Public capability activation remains deferred.

The next milestone should connect the existing Reviewer attempt journal to failure
publication, recovery, current status and supersession after a permitted
continuation. Report publication alone would leave stale terminal state or prevent
a second failure from being reported; those transitions belong in the same bounded
milestone.

## Authoritative boundaries

| Requirement | Authority | Consequence |
| --- | --- | --- |
| Timeout stops immediately; invalid output exhausting its allowed handling stops as artifact-invalid | [Scheduler halt artifact matrix](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#halt-artifact-matrix), lines 107–128; [artifact validation policy](specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#artifact-validation-policy), lines 1007–1042 | Publish `artifact_validation_error.json`, the Phase 2 `convergence_failure_report.json`, and the applicable vNext terminal evidence; preserve the exact cause. |
| One automatic shape retry per logical request across restarts; no automatic timeout, transport or persistence retry | [D7 retry and continuation](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#retry-decisions-and-continuation), lines 550–558 | Preserve the existing two-slot journal and closed invalid/exhausted outcomes. A timeout is not budget exhaustion or malformed feedback. |
| Continuation requires an implemented, published role/phase/gate with exact frozen-input/current-base/attempt checks | Same D7 section, lines 556–558; [slice availability](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#reporting-and-slice-availability), lines 562–568 | Qualify only the internal Reviewer/Phase 2/review gate. Do not extend the generic CLI `resume` command. |
| Generic legacy resume supports only the enumerated Phase 1 paths | [Resume policy](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#resume-policy), lines 625–635 | The narrower vNext component contract is not general Phase 2 resume permission. |
| Failed validation attempts do not consume accepted review cycles | Artifact leaf, lines 1011–1018; D7 valid-Reviewer transition | Do not increment profile budgets, mark clean, advance the schedule or admit a candidate from failure evidence. |
| Phase 2 failure requires external input and an evidence-derived report | [Phase 2 failure handling](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md#phase-2-failure-handling), lines 24–78 | Preserve current verified draft, accepted ancestry, residual findings, profile verification and last valid review context. Before valid final verification, status is `not_run`, not a fabricated rejection. A declaration may be absent. |
| Historical terminal reports cannot override valid later current state | Scheduler lines 28–30; D7 reporting, lines 562–564 | Retain immutable failure snapshots, derive current status from validated current evidence and recover state separately. A cached state field grants no continuation authority. |
| Uncertain writes require revalidation under the same D8 owner | [Local storage kernel](../contracts/algorithms/vnext_local_storage_kernel_v1.md), publication/replacement and uncertainty rules | No new journal, fallback write path, model call or duplicate ordinal to repair uncertainty. If storage or authority is unreadable, report that failure rather than inventing a durable terminal packet. |

D7 expressly permits a qualified narrow continuation while expressly withholding
generic Phase 2 resume. These statements are compatible. The existing pinned
[Phase 2 client algorithm](../contracts/algorithms/vnext_verified_phase2_client_v1.md)
already defines its two-slot component boundary; the next milestone must preserve
it and use a separate opt-in contract for the added reporting lifecycle.

## Actual implementation

- `vnext_verified_phase2_client.py`: validates exact first request and dependencies,
  records timeout/transport/shape/invalid outcomes, enforces two total slots,
  requires explicit continuation, and finishes valid retained output without a
  client. Its API returns component outcomes; it does not publish phase failure
  reports or terminal state.
- `vnext_review_requests.py`: the shared driver stops on timeout/transport failure,
  retries shape failure once and preserves immutable attempt evidence. It must
  remain compatible with its other consumers.
- `vnext_verified_phase2_sequence.py`: later passes use the same journal/owner;
  an incomplete result remains `pending_review`. Execution requires an explicit
  selected pass and current base. Failed attempts do not become consumed passes.
- `vnext_verified_phase2_closeout.py` and `vnext_verified_phase2_termination.py`:
  current terminal publication requires a consumed final declaration review.
  Earlier failed requests cannot enter this path. The failure report mirror is
  currently create-only, adequate for the terminal-only exhausted-budget path but
  insufficient for repeated earlier failures followed by allowed continuation.
- `vnext_local_storage.py`: materialization has a fixed destination whitelist.
  Conditional canonical-JSON snapshot replacement is already available with
  exact-old-byte and domain-transition validation. The lifecycle implementation
  must explicitly prove ownership and predecessor bindings for any replaceable
  report projection; it cannot overwrite unowned reports or bypass the whitelist
  through an unvalidated replacement call.

The inherited clean-closeout terminal builder hardcodes `resume.permitted: false`
and requires appropriate promoted-candidate evidence. A failure owner must derive
technical eligibility from the selected incomplete request, not reuse that boolean
or infer eligibility from a cached failure report. A retained valid response needs
completion, not another Reviewer call. An invocation marker without a response
proves interruption, not necessarily a client timeout.

## Fixed acceptance boundary for the next milestone

1. Select the current incomplete committed Phase 2 Reviewer request (first or later
   supported request, including a final-review invocation that never yielded a valid
   result). Verify current lineage, entry/configuration/rubric, request and attempt
   evidence. Do not require a successful consumption or invent declaration inputs.
2. Report timeout, exhausted shape/process failures, closed invalid-review and
   transport failures with their existing exact classification. Preserve prior
   successful feedback, residual debt and budgets. Bind safe current draft and
   available declaration/rubric evidence; do not publish unvalidated response bytes
   as feedback. Distinguish interruption and failed persistence from known timeout.
3. Publish immutable per-request/per-outcome reports and commit evidence under D8;
   recover report projections and current state separately. Preserve history across
   a second failure. Refuse conflicting unowned report bytes and corrupt sources.
4. Offer only existing component continuation when its gate and slot are eligible.
   Keep frozen inputs/transport, no timeout override or third attempt; reuse retained
   valid output. Recovery after uncertain state writes ends before fresh work.
5. On successful completion, make the earlier terminal historical without deleting
   it; successful-pass consumption still occurs exactly once through its existing
   owner. Cover a subsequent failure and eventual clean/failure closeout so stale
   root reports cannot block or falsely determine current status.
6. Test first and later requests, seed and promoted bases, timeout then success,
   timeout then exhausted failure, invalid output, retained valid response,
   tampering, report/commit/projection/state interruptions and fresh-process
   reopening. Preserve existing success/blocked/failure closeout and legacy/bridge
   behavior. No public activation, provider call, external apply-back or push.

This is a finite boundary for one milestone, not an estimate of total remaining
feature work. Other client roles, candidate rejection terminals, conflict and
oscillation publication, decision/rubric resolution, declaration repair, broader
scheduler modes, version maintenance and strop/readback remain separate coverage.
All four 18.8 tasks and 18.9 qualification remain open.

## Verification

Two existing component tests passed on the checkpoint source in 56.378 seconds:
shape/process retry and exhaustion across reopening, plus timeout/uncertain-marker
explicit remaining-slot continuation. All 541 selected source/contract/test file
hashes matched the inspection snapshot afterward. This validates the existing
component boundary only, not the proposed phase-level reporting lifecycle. Evidence
is retained under `rounds/vnext-18-8-phase2-failure-boundary-001/`
(`evidence.json`, `source-manifest.json`, `client-boundary-recheck.log`). The passing
log SHA-256 is `413106977e33e24bbe7b04aa137d2d42488dec356ce21f69b98a29bb3b1045b2`. The first collection command used
an incorrect test-class name; its collection-error log is retained and does not
count as a runtime test. No runtime implementation or test source is changed.
