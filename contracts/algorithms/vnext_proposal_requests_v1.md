# Durable Editor request and continuation implementation

Status: isolated D7 implementation for 18.5, unactivated and outside the frozen first suite. The seed admission, completed-request handoff and bounded closeout consumers now connect the current seed authority through candidate registration and D7 terminal projections. Public configuration/CLI/status routing and later promoted-base admission remain consuming work. The D8 audit is still pending. The earlier fresh-directory exercise helper remains a fixture boundary; it must not be used by the eventual scheduler to allocate new retry allowances.

## Logical request and frozen inputs

The first supported journal role/phase/gate is Editor / Phase 1 / proposal. Its request identifier is `req_` plus the full lowercase SHA-256 digest of canonical JSON for:

```json
["whetstone-logical-client-request-v1",job_id,"editor","phase1","proposal",transaction_id]
```

The path is `rounds/client_requests/{request_id}`. Caller-selected directories, round numbers, process IDs, timeouts and attempts are not identity inputs. The same job/transaction cannot reset its allowance by changing those values. A same-ID request with different frozen input, plan, inventory, prompt or transport identity refuses. A different transaction still needs full new admission; this journal does not authorize a scheduler to manufacture a new plan in response to rejection.

A closed `vnext-proposal-request-v1` header binds the exact preflight input hash, plan and inventory hashes, original prompt hash, current base-pointer reference, configured transport and fixed budgets. Preflight still binds original Reviewer feedback/advice, exact role-tagged context, named-unit operator choices, rules and assertions, and the descriptor/suite inputs. The plan, base inventory and original prompt are persisted before the first invocation marker. The storage-bound descriptor must match exact canonical job bytes, and the implementation checks mode, suite selection and the implemented assembler/inventory/normalization versions. The outer validator must prove registered-suite support, D6 descriptor identity and complete committed authority; arbitrary suite names or fixture callbacks do not qualify admission.

The current pointer must remain byte-identical to the admitted immutable pointer reference. Inputs, prompt and transport are rechecked before each client call and after a returned response. No incomplete candidate is substituted as the base. Full authority/input loading remains required each time; a mutable Python object is not a substitute for admission evidence.

## Fixed invocation budget and explicit continuation

This initial implementation retains two total invocation slots per logical Editor request and at most one automatic shape repair. A durably published invocation marker consumes a slot even if the process then dies before the client call or no response survives. Uncertainty cannot restore a slot. There is no override, third attempt, new-process reset or extension through technical continuation.

Only a freshly observed response JSON/schema-shape error can immediately use the second slot automatically. The repair prompt includes exact validation errors and the unchanged original prompt. Contradictory bindings, invalid patch semantics, timeouts, transport/provider/authentication errors and local persistence failures never trigger an automatic repair. The transport's own `ValueError` remains a transport failure. If a technical interruption has already consumed one slot, an explicit continuation may use the remaining slot; a subsequent malformed response does not create a third slot just because no shape retry was previously used.

Re-entry into an incomplete request requires explicit continuation. A timeout, recorded transport failure or invocation with no durable completion can use the next slot only through that path and after all frozen-input/current-base/evidence checks pass. Changing `timeout_seconds` is permitted for explicit continuation and is recorded in the new invocation; Editor identity/model, executable, working directory and output-schema hash remain identical. A timeout change does not create a different logical request or change authorization. An invalid proposal cannot reopen through technical continuation, and exhaustion cannot be bypassed by changing transport settings.

An already complete request is independently validated and reused without another client call. A complete valid raw response whose derived outcome, canonical patch or result receipt was interrupted is also reused, under explicit continuation, rather than calling the client again. Shape repair after a restart consumes the same remaining slot and uses the same precise error. These are supported isolated journal behaviors; public status must not advertise a continuation until its entire role/phase/gate has qualified.

## Immutable attempt chain and outcome validation

Each attempt is stored below `attempts/1` or `attempts/2`, with exact prompt, `vnext-proposal-request-invocation-v1`, raw response when available, optional process telemetry, and `vnext-proposal-request-outcome-v1`. Markers are durably published before invoking the client. The second marker binds the exact first outcome hash and identifies either a shape repair or explicit technical continuation. Unknown attempts, gaps, missing invocation/preflight evidence and a missing predecessor already bound by a later marker halt instead of reconstructing committed dependencies.

Outcomes distinguish valid proposal, shape error, invalid proposal, timeout, transport failure and interrupted invocation. Returned raw bytes are replayed through the full response decoder; any stored outcome must equal that independently derived result. A missing derived outcome may be reconstructed only while it is not already a committed dependency of a later marker. An invocation with neither raw response nor recorded failure is conservatively interrupted and remains a consumed slot. A failure outcome cannot claim a raw response or proposal it does not have.

Complete retained evidence is republished byte-identically through the D8 storage barriers before writer continuation or successful completed-output reuse. Uncertain durability errors propagate and invalidate storage ownership; they never lead directly to another client call. Raw response and telemetry failures are local persistence failures, not malformed client responses.

The canonical proposal and payloads are stored under the request's `proposals/{proposal_id}` directory. The existing `vnext-proposal-result-v1` receipt binds the exact proposal, admitted plan and base pointer and explicitly claims no candidate registration, verification or promotion. The later round handoff must bind this validated request result to its admitted round and publish exact canonical bytes at the candidate registry's expected paths; file copying alone is not admission.

Read-only inspection derives status without a client, exclusive lock, new marker, outcome repair or publication. It distinguishes a valid retained response awaiting finalization from a complete receipt. An exhausted status retains the exact last outcome and cause so run-level halt precedence can still report a timeout or other failure; journal eligibility is separate from terminal-state evaluation.

## Evidence and limits

Tests use scripted clients and a real scripted native executable. They cover durable shape retry and telemetry, exact completed-result reuse, response-finalization recovery without another call, explicit timeout continuation, timeout-only changes, request identity/input drift, missing bound predecessors, contradictory outcomes, third-attempt refusal, conservative invocation accounting and read-only inspection. No live model is invoked.

The four new request/transport/invocation/outcome schemas and this algorithm remain unregistered. The isolated [completed-request handoff](vnext_proposal_handoff_v1.md) now connects this journal to round artifacts and the candidate registry. Full proposal admission and current/history loading, qualified runtime scheduling, failed-deterministic decision commit, canonical terminal reports, public continuation selectors, D8 audit and consuming-suite publication remain requirements before the 18.5 checkpoint. The journal neither grants semantic approval nor qualifies legacy/bridge continuation changes.
