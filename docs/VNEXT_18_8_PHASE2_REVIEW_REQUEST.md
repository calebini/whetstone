# First pinned Phase 2 Reviewer request

Date: 2026-09-21. Clean starting checkpoint: `6734ad6`.
This bounded slice was validated unstaged and uncommitted. On 2026-09-22 the user
authorized a local checkpoint; pushing remains deferred until feature completion.

`VerifiedRun.prepare_phase2_review(transport)` prepares a detached read-only view.
`VerifiedRun.bind_phase2_review(transport)` publishes the exact first request under
D8 ownership. Both require the separately pinned
[algorithm](../contracts/algorithms/vnext_verified_phase2_review_v1.md) and
[request schema](../contracts/schemas/vnext_phase2_review_request_v1.schema.json),
plus entry and response/vocabulary/transport dependencies.

The owner revalidates current lineage, complete Phase 1 prerequisites, immutable
configuration/request, committed entry and matching state. Configuration alone
cannot start review. Missing Phase 1 or entry state requires its separate recovery;
base mirror recovery ends the invocation before request publication.

The request selects step 1, pass 1, and the next round after the bound Phase 1
closeout. It preserves all ordered steps and independent budgets, including the
repeated strict-check step. Preparation and publication consume zero accepted
Reviewer passes. No result, budget advancement or convergence is inferred.

Inputs bind exact draft/map, original seed, authority/invariants/scope, permitted
reference context, rubric, final/strict target, all profile budgets, controlled
vocabulary, suite digest and response schema dependencies. The prompt embeds
content, uses Phase 2 oscillation instructions and explicitly omits declaration
review. Caller-supplied transport must retain the configured Reviewer identity
and the pinned ordinary Phase 2 feedback input schema hash. Recording a command
is not permission to execute it or transmit the input snapshot.

Publication writes `rounds/phase2/review_requests/first/inputs.json`, then
`prompt.txt`, then `request.json` as the commit. Source and dependency barriers
repeat on replay, including after visible final publication with a lost
acknowledgement. Exact uncommitted prefixes can finish; conflicting bytes or a
committed request with missing dependencies refuse without reconstruction.
Existing artifacts and derived run state are preserved.

## Validation

All **37 distinct methods pass**: six focused methods on final corrected source
(110.980 seconds), and 31 entry/binding/prompt/vocabulary regressions (210.692
seconds). No skips. The [validation record](audits/VNEXT_18_8_PHASE2_REVIEW_REQUEST.json)
binds exact commands, method identities, source snapshots and logs retained under
ignored `rounds/vnext-18-8-phase2-review-001/`.

The initial focused run failed because the consumer tried to synchronize the
immutable storage descriptor. The correction preserves descriptor validation and
leaves storage-control durability with initialization. A subsequent code review
and retained reproduction found returned source references aliasing the in-memory
run selectors; these references now use deep copies, with a same-open-run mutation
check added before reopen. Initial failures and intermediate evidence are retained.

The regression run started before the detached-reference fix. Only the new request
module and its focused test changed during that run; the existing regression
modules do not call these new APIs, and their entry/binding/prompt/vocabulary
runtime stayed byte-identical. This is not an all-source-unchanged regression
claim. The final six focused methods ran on the unchanged corrected snapshot.

Focused coverage includes exact phase/profile/budget/transport/prompt bindings,
detached return values, all before/after publication prefixes, final lost-ack
barrier replay, corrupt evidence and missing committed dependencies, source-barrier
failure and drift, separate entry/state/mirror recovery, and missing pins/vocabulary
drift. The new owner is exercised on a seed-base entry. Promoted-base request
qualification and historical entry consumption after later promotion remain open.
These are process-local scripted fixtures on macOS/APFS, not new process-death,
power-loss, live-provider or full-product qualification. Frozen suite 1, shipping
maps and existing legacy/bridge/storage/versioning runtime bytes are unchanged.

## Remaining boundary

The [invocation/result follow-up](VNEXT_18_8_PHASE2_CLIENT.md) now implements
a separately pinned journal consuming this immutable request, with Phase 2
response and oscillation validation, exact replay and explicit attempt limits. This slice neither calls a client nor consumes a response. It
does not yet translate Phase 2 feedback into V finding advice/candidate admission.
The ordinary feedback input schema is not the Phase 1 feedback/advice wrapper;
a future provider adapter must validate its schema and transport compatibility.

Historical entry anchoring after later promotion, subsequent passes/profile
advancement, version maintenance through V candidates, convergence/declaration,
remaining scheduler modes, strop/readback and terminal reporting remain open.
All four 18.8 tasks remain incomplete. Public activation, 18.9 qualification,
external transmission/apply-back and pushing remain excluded. The subsequent local
commit authorization does not expand the implementation or validation scope.
