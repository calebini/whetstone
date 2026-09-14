# Seed review phase execution and closeout (under development)

This private 18.5 consumer executes the configured seed Reviewer sequence through its first finding boundary or terminal outcome. It consumes the existing [request journal](vnext_seed_review_requests_v1.md), [stored-run admission](vnext_proposal_run_v1.md), D7 terminal contract and proposed D8 publication kernel. It does not register a shipping suite or activate a mode.

## Execution boundary

`ProposalRun.review_phase` derives the next round/profile from validated request claims and receipts. It runs the bounded request operation until a classified finding needs admission, all required profiles are clean, a configured budget is exhausted, or a client request fails. Request shape repair and technical continuation retain their original two-slot limits. No new request ID or allowance is created to escape a failure.

The entry inspects stored status before any execution. Interrupted work requires explicit continuation. Invalid or exhausted client work cannot receive another call. A final outcome whose terminal projection is missing exposes only `materialization`; explicit recovery publishes that report and ends the invocation. Repeated completed invocations reproduce and repeat durability barriers for the same report. A completed endpoint is not technically resumable.

The consumer returns at `finding_admission` without fabricating a terminal decision, operator request, option, response, mutation plan or candidate. Editor-fixable findings may proceed through the existing explicit round-input admission. Sensitive findings still require their concrete hash-bound operator requests and answers. Public operator interaction remains an integration obligation; an absent request is not reported as `PAUSED_DECISION`.

## Terminal outcomes and authority

Derive the outcome from the independently replayed seed review sequence, not a caller-supplied status or a previously written terminal file:

- Every configured profile clean and no admitted changes pending: `PHASE_1_STABLE`, reason `vnext_seed_review_complete`.
- An uncleared profile exhausts its pinned budget: `TARGET_NOT_REACHED`, reason `vnext_review_budget_exhausted`. Deferred but still serious in-scope findings remain unresolved review debt.
- Timeout: `HALTED_CLIENT_TIMEOUT`, retaining the exact last machine cause, including after slot exhaustion.
- Invalid shape/bindings, transport failure or interrupted response: `HALTED_ARTIFACT_INVALID`, retaining the exact last machine cause. Only eligible unfinished requests expose `review` continuation.

No terminal is produced for fresh work, an uninvoked prepared request, complete raw output awaiting its result receipt, or findings awaiting admission. Those states retain their specific next gate. Missing valid-output materialization is repaired under the request consumer's explicit continuation rules without another call.

The terminal reuses `terminal-report-v2`. Revalidate the current committed seed pointer and require no registered candidates or registration orphans before seed-only closeout. Candidate processing cannot be hidden by clean review evidence. All latest-candidate fields are null, rejection and outstanding-decision lists are empty, and source apply-back is false. Phase 1 completion implies no Phase 2 invocation, convergence declaration, version mutation, synthetic no-op patch or promotion.

## Publication and read-only projection

Under D8 ownership, repeat each completed request's prompt/attempt/result dependency barriers; synchronize any unfinished request's exact attempt evidence without inventing a response. Recompute the terminal and publish it to `rounds/terminal_reports/terminal-{sha256(canonical report)}.json`. Revalidate the resulting readback. A conflicting file is invalid and must not be overwritten. This report is a derived materialization; it is not a new authority pointer or a substitute for its source review evidence.

Read-only status independently replays current review evidence and derives that exact path. It never enumerates terminal filenames to choose current state. A prior timeout report remains retained history after successful continuation, but cannot override the later clean result. Removing or damaging required review evidence prevents a historical success report from establishing completion.

A final missing report exposes D7's `materialization` gate; a fully materialized terminal exposes `complete`. A recoverable transient request stays at `review`, with its exact timeout/interruption cause and bounded eligibility, whether or not its historical failure projection was written. Status takes no writer lock, invokes no client and performs no repair.

The earlier provisional `phase_1_closeout` label is removed from the unregistered status schema; this consumer uses the already specified D7 gate vocabulary. Public package/configuration/CLI routing, concrete operator interaction, D8 audit/reconciliation and shipping qualification remain open. Existing legacy, bridge and Reviewer-only paths are unchanged.
