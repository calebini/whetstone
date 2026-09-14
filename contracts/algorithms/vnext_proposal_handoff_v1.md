# Completed proposal request to round handoff

Status: isolated 18.5 integration, unactivated. The consuming suite must pin this algorithm and `vnext-proposal-handoff-v1`; the frozen first suite is unchanged. D8 review, public admission/continuation routing and a shipping consuming suite remain release gates.

## Source and round binding

The handoff accepts no client and never invokes one. It reopens the durable Editor request through the same preflight, input, current-base, attempt-chain, raw-response and completed-result checks used by request replay. A valid raw response without a completed request receipt is insufficient: explicit request continuation must finalize it first. Timeout, exhausted or invalid requests cannot become handoffs.

The selected positive round number must equal the round in the request's immutable Reviewer evidence. The handoff derives the request ID and proposal identity; it does not trust a caller-provided result object or copied patch. When the registry supplies a proposal selector, it must match the completed request before publication begins. Complete descriptor/suite, current-authority and immutable round admission remain required domain callbacks; these checks do not qualify an arbitrary test suite.

The closed canonical receipt at `rounds/round-N/proposal_handoff.json` binds job, round, request and transaction IDs, preflight input hash, base-pointer reference, exact request-header/result references, and the round-local plan and proposal references. Existing receipts must equal the independently reconstructed record. The receipt has no candidate disposition or promotion authority.

## Publication and replay

Under D8 exclusion, repeat the completed request's immutable evidence barriers, including its canonical proposal/payloads and completed receipt. Then publish the exact plan at the round's `mutation_plan.json` and exact patch/payload bytes below `proposals/{proposal_id}`. Re-read the round artifacts and frozen request inputs before publishing the handoff receipt last. This receipt commits the handoff only; the candidate creation event remains the registration commit point.

A partial round copy with no receipt is ineligible for registration. Handoff recovery may replay byte-identical copies and finish the receipt from the already complete request, without consuming another invocation slot. Conflicting existing bytes remain untouched and cause failure. An uncertain source or handoff barrier halts and releases ownership; no candidate is created on that failure path. Later recovery revalidates and repeats the required barriers.

Every registration entry point returned by `registry_for_proposal_requests` repeats handoff publication/barriers before calling the candidate registry. This includes direct `register` calls, so a visible but previously unacknowledged handoff receipt cannot bypass synchronization. Handoff and registration reacquire the same exclusion separately, and registration rechecks authority and exact source/round bindings after reacquisition. A changed current base between them prevents registration; it is not silently refreshed.

The registry's assessment loader derives its authority, invariants, seed/base maps, complete base inventory, configured review, named-unit decisions and discovery rules from the validated request preflight. It requires the exact handoff and round copies each time registered candidate history is read. Rehashed or altered handoff, source receipt, plan, patch or payload evidence invalidates readback rather than becoming a new authorization.

Read-only handoff validation invokes the authority validator but takes no exclusive lock, repairs no copies or receipt, and makes no client call. Handoff alone leaves the candidate creation chain empty. Successful registration creates only the existing initial unverified disposition; exact replay reuses its ordinal and event. Neither path changes the verified pointer or emits `draft_after.md`.

## Qualification boundary

Tests cover every copy/receipt prefix for a single-payload proposal, explicit request finalization before handoff, wrong round/proposal selectors, conflicting bytes, rehashed receipts, read-only validation, source and handoff uncertainty, direct-entry durability checks, registered-source tampering and a full scripted native shape-repair/request/handoff/registration journey. Replay makes no additional Editor call.

This loader currently requires the request's base to remain current, matching the bounded proposal-only path where no promotion changes the seed. Historical promoted-base inspection and loading must qualify before a promotion consumer uses it; it never substitutes a newer draft for a historical base. The [seed admission consumer](vnext_proposal_admission_v1.md) now supplies supported-suite validation and validated input-package-to-fresh-root initialization. The [bounded closeout consumer](vnext_proposal_closeout_v1.md) adds final rejection/non-final decisions, terminal projections and pre-registration assembly-failure evidence. Public CLI/status/continuation routing, the shipping consuming suite and external D8 audit remain open. Qualification uses temporarily registered test suites and no live models.
