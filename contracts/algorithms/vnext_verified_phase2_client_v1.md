# First verified Phase 2 invocation/result journal v1 (unactivated)

Consume only the exact committed first Reviewer request and its complete dependencies.
Require this separate algorithm and vnext_phase2_review_result_v1, phase2_reviewer_feedback,
vnext_review_invocation_v1 and vnext_review_outcome_v1 pins, alongside all first-request,
entry, Phase 1 and storage prerequisites. Pins must exist before immutable request
publication; this does not retrofit another suite into an existing root.

No implicit binding or entry. Reproduce the entire bound request, entry/state, current
pointer/draft/map, Phase 1 closeout, configuration, rubric, vocabulary and schema/input/
prompt hashes. Repeat their existing source barriers under the actual D8 fence. Existing
materialization/registration/promotion precedence applies; mirror recovery ends the call.
Descriptor durability remains storage-owned. Never mutate current authority or run state.

The caller supplies a raw-response client with exact configured identity and an unchanged
transport_binding matching the committed request, including timeout and output schema hash.
Its review(prompt) method returns bytes. There is no default provider adapter, command
execution, public mode, CLI or external-transmission grant. Testing uses scripted clients.
A separately authorized live consumer must qualify its actual raw transport adapter.

The logical request ID is content_identifier(req, whetstone-phase2-review-request-v1,
[request Ref]). Journal paths are rounds/phase2/review_requests/first/execution/.
Reuse the existing two-slot Reviewer transport loop: original prompt, attempt prompt and
invocation marker precede the call; exact response bytes precede deterministic outcome;
canonical reviewer_feedback.json precedes result.json. Markers/outcomes use existing
vNext Reviewer schemas and bind this logical ID and the request Ref hash as input_hash.
No Phase 1 review-index, advice, candidate, profile or promotion artifact is produced.

At most two invocations total across reentry. A JSON/schema shape failure or the existing
pure process/context-loading failure check permits one automatic shape retry with precise
errors and identical original context. A present contradictory round/profile/draft/Reviewer
binding, unknown canonical section, or duplicate feedback ID is invalid_review and gets no
automatic retry. Missing required fields are shape failures. Timeout/transport errors halt
without automatic retry; persistence/source/ownership errors propagate without relabeling.
Explicit continuation of an incomplete invocation may use its one remaining slot; a visible
marker with no response consumes its slot even if acknowledgement was lost before dispatch.
No generic Phase 2 resume, timeout change or budget extension is implemented.

Parse one JSON object; check present request-binding fields; reject process/context failure;
validate pinned Phase 2 input shape; use shared deterministic issue ID/severity and Phase 2
oscillation canonicalization over the exact current map IDs; require unique feedback IDs;
validate the canonical phase2_reviewer_feedback schema. Retain raw invalid responses only
as diagnostics. Never persist invalid feedback as canonical evidence. This consumer does
not classify V finding advice, compare multi-round oscillation history, or admit edits.

Inspect exact attempt slots 1 and 2, reject unknown slots, orphan responses/outcomes,
missing predecessors, changed prompt/transport/bindings, noncanonical journal JSON and
contradictory outcomes. Reproduce every outcome from retained raw bytes. A no-response
invocation derives interrupted evidence; only explicit mutating continuation persists it.
An already committed result must have all exact response/outcome/feedback dependencies;
never reconstruct missing dependencies of a claimed result. Uncommitted valid prefixes
may finish from retained raw output without another client.

The distinct result receipt binds request, attempt, raw response, deterministic outcome
and canonical feedback; accepted_passes is 1 for this logical request, regardless of
attempt count. It is evidence for a later scheduler consumer, not a counter mutation,
profile cleanliness, declaration, candidate verification or convergence verdict.
Completed reentry repeats source/prompt/invocation/raw/outcome/feedback/result barriers
and ends without clients. Incomplete started work requires explicit continuation; valid
retained raw completes without a client. Invalid/exhausted journals remain closed.
Read-only status acquires no mutation fence and repairs nothing. Returned views are detached.

Canonical publication/barrier and interrupted-call tests qualify this component only.
Historical entry anchoring after later promotions, later requests, budgets/profile advance,
V feedback admission, candidate routing, convergence/declaration and public activation
remain separate work. Preserve legacy, bridge and shared transport behavior unchanged.
