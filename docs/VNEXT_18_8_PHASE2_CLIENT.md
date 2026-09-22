# Bounded first Phase 2 invocation and result

Date: 2026-09-22. Clean starting checkpoint: `d5a51e5`.
This slice was validated unstaged and uncommitted. The user subsequently authorized
a local checkpoint; pushing remains deferred until feature completion.

`VerifiedRun.run_phase2_review(client=..., continuation=False)` consumes the exact
committed first request. `phase2_review_status()` inspects its journal without a
writer fence or repairs. Both require the new
[algorithm](../contracts/algorithms/vnext_verified_phase2_client_v1.md) and
[result schema](../contracts/schemas/vnext_phase2_review_result_v1.schema.json),
plus the canonical Phase 2 feedback and existing invocation/outcome pins.
These pins must already be in the root's suite before request publication;
there is no in-place suite migration or public-mode activation.

The injected client must expose the exact configured identity and immutable
transport binding, and return raw bytes from `review(prompt)`. There is no default
provider adapter or command launch. Tests use scripted clients only; no external
transmission is authorized or performed. Existing legacy full-draft executors and
shared transport/normalization code remain unchanged.

Under D8 ownership, the owner revalidates request, entry/state, current lineage,
Phase 1 prerequisites, configuration, rubric, vocabulary and exact source inputs.
It repeats source barriers before dispatch or recovery. Separate mirror recovery
ends the invocation before any client call. No implicit binding or entry occurs.

The dedicated `rounds/phase2/review_requests/first/execution/` journal retains an
original prompt, attempt prompts and invocation markers, raw bytes, deterministic
outcomes, canonical feedback and a final result receipt. A visible invocation
marker consumes its slot, including when acknowledgement was lost before the call.
There are at most two slots across restarts. One JSON/schema or process/context
failure permits a bounded shape retry. Contradictory request fields, unknown map
sections or repeated feedback IDs halt as invalid reviews without automatic retry.
Timeouts/transport failures stop; using a remaining slot requires explicit component
continuation. Persistence and source/ownership failures propagate unchanged.

Raw feedback passes contextual checks, the existing pure process-failure guard,
pinned input schema, deterministic issue/severity and oscillation canonicalization,
unique feedback IDs and the persisted Phase 2 schema. Invalid output never becomes
canonical feedback. The receipt binds the request, successful attempt, raw response,
outcome and canonical feedback. Its `accepted_passes: 1` records one validated pass
for the logical request, independent of how many attempts it required; it does not
mutate a scheduler counter or mark a profile clean.

Completed reentry repeats the complete source/result dependency barriers and stops
without a client. Interrupted started work requires explicit continuation. Retained
valid raw output completes without another call. A committed result with missing
or conflicting dependencies refuses reconstruction. No candidate/advice, second
request, profile advancement, draft/pointer/state change or convergence is produced.

## Validation

All **28 distinct methods pass**: seven focused methods on unchanged corrected
source (276.654 seconds) and 21 request/journal/oscillation regressions (154.863
seconds), with no skips. The [validation record](audits/VNEXT_18_8_PHASE2_CLIENT.json)
binds exact commands, method identities, source snapshots and log hashes. Raw
evidence is retained under ignored `rounds/vnext-18-8-phase2-client-001/`.

The regression cohort completed before the final no-response outcome binding fix.
Only the new client module and its focused test changed afterward; neither is
consumed by those regression modules. The shared transport loop, prior request
owner, canonicalization helpers and regression tests remain byte-identical. The
seven focused methods were rerun in full on the corrected snapshot. No full-product
regression or whole-repository unchanged-source claim spans both snapshots.

Focused cases cover seed and promoted entry bases, canonical feedback/oscillation
identity, competing storage-descriptor exclusion during the actual client call,
completed and interrupted publication replay, one shape/process retry, exhaustion,
explicit timeout/interrupted-slot continuation, source barriers/drift, separate
mirror recovery, missing pins/request, changed transport and missing/corrupt result
dependencies. Returned feedback is detached and prior authority/state bytes stay
unchanged. These are scripted clients and process-local publication/barrier hooks
on macOS/APFS, not live-provider, new multiprocess-death or physical power-loss
qualification. All shipping maps remain empty and frozen suite 1 is unchanged.

A final code review and retained reproduction found that no-response outcomes
needed an explicit request-ID/attempt binding check. The new owner now checks
both fields before replay, with refusal tests for altered timeout outcomes in
read-only status and mutating continuation. Shared legacy journals were not
changed. The initial passing cohort and the reproduction remain retained;
final qualification uses the corrected focused cohort.

## Handoff

Next: consume the bound validated Phase 2 result at the scheduler/finding boundary.
Define and qualify exact successful-pass accounting and V finding-advice/admission
before permitting candidate work or another profile pass. Feedback alone cannot
grant edit authority. Historical entry anchoring after a later Phase 2 promotion,
subsequent requests/profile budgets, version maintenance through V candidates,
convergence/declaration, remaining scheduler modes, strop/readback and complete
terminal reporting remain open. Provider-specific raw adapters and public execution
also remain unqualified. This component continuation is not generic Phase 2 resume.
All four 18.8 tasks remain incomplete; 18.9, external apply-back and push remain
excluded. The subsequent local commit authorization does not expand implementation
or validation scope. No new product or authority decision is assumed.
