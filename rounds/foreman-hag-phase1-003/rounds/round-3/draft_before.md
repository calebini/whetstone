# Foreman HAG Adapter Specification (Locked v0.6)

Status: Locked  
Locked: 2026-04-29  
Scope: Human Approval Gate adapter contract for Foreman MVP  
Primary Lens: Deterministic approval capture with zero authority leakage

---

## 1. Purpose

The Human Approval Gate (HAG) Adapter is a boundary component responsible for collecting human approval decisions and returning them to Foreman in a structured, replayable form.

It does not participate in adjudication.

It does not mutate intent state.

It does not interpret policy, evidence, graph semantics, registry semantics, or approval validity.

Core invariant:

```text
HAG adapters collect decisions.
The Arbiter validates approvals.
The Arbiter performs transitions.
```

---

## 2. Alignment With Foreman Specs

This specification refines the adapter-facing approval model without changing Foreman's authority boundary.

The High-Level Design (HLD) remains authoritative for:

- Arbiter ownership of validation
- state-transition authority
- approval binding semantics
- audit and replay invariants
- reason-code registry behavior

This specification owns the adapter-facing request and response contract.

The Policy Specification owns normalized policy approval records and `approval_valid` semantics.

The Intent Schema Specification owns runtime intent records, approval material references, and audit reference placement.

The Registry Specification owns registry snapshot component shapes and the Reason-Code Registry.

The Registry Diff + Migration Specification owns rebind, migration, and approval-staleness effects caused by registry or graph changes.

Cross-spec alignment points:

- `expires_at` is the adapter contract field for approval expiration.
- `intent_hash` is required in the adapter request because it is part of the HLD approval binding set.
- Adapter responses are captured human decisions, not policy approval records.
- Replay of approval validity requires the immutable approval request, adapter response, and Arbiter decision material.

---

## 3. Authority Model

Authority is strictly partitioned.

Foreman Arbiter:

- defines approval requirements
- constructs approval requests
- binds hashes
- validates approval responses
- determines approval validity
- emits Foreman reason codes
- determines and applies state transitions through the store

HAG Adapter:

- presents approval requests
- collects human decisions
- returns approval responses
- records adapter-local interaction metadata

Constraint:

```text
An approval response is a claim.
Only the Arbiter decides if that claim is valid.
```

---

## 4. Non-Goals

The adapter MUST NOT:

- evaluate policy
- validate evidence
- accept or reject evidence
- determine dependency satisfaction
- determine approval validity
- enforce registry constraints
- validate registry references
- compute hashes
- verify hashes
- perform live registry lookup
- apply state transitions
- infer intent semantics
- retry or reinterpret approvals as Foreman transitions
- emit Foreman transition reason codes

---

## 5. Approval Request

Canonical adapter input:

```json
{
  "approval_request_id": "approval_request:123",
  "intent_id": "intent:123",
  "requested_transition": "awaiting_approval->approved_for_release",
  "intent_hash": "sha256:...",
  "graph_root_hash": "sha256:...",
  "policy_hash": "sha256:...",
  "decision_evidence_hash": "sha256:...",
  "registry_snapshot_hash": "sha256:...",
  "approver_role": "release_manager",
  "expires_at": "2026-04-28T01:00:00Z",
  "created_at": "2026-04-28T00:00:00Z",
  "display_context": {}
}
```

Authority-bearing fields:

- `approval_request_id`
- `intent_id`
- `requested_transition`
- `intent_hash`
- `graph_root_hash`
- `policy_hash`
- `decision_evidence_hash`
- `registry_snapshot_hash`
- `approver_role`
- `expires_at`

Field rules:

- `expires_at` is the canonical approval expiration field for the adapter contract.
- `decision_evidence_hash` is the canonical approval evidence binding field.
- `intent_hash` is required because approval binds to the full HLD approval binding set.
- `intent_id` identifies the bound intent. It is authority-bearing as a routing identifier but is not part of the hash binding set.
- `registry_snapshot_hash` identifies the decision registry snapshot selected by Foreman. It is authority-bearing, but the adapter does not load or validate the snapshot.
- `created_at` is adapter-visible request metadata and is not part of approval validity.
- `display_context` is non-authoritative presentation metadata.

Adapter invariant:

The adapter MUST treat all authority-bearing fields in the received request as read-only after request receipt.

On submission, the adapter MUST reject the submission if any request-bound preserved field in the response differs from the received request. The request-bound preserved field set is:

- `approval_request_id`
- `approver_role`
- `requested_transition`

---

## 6. Display Context

`display_context` is non-authoritative and implementation-specific.

Constraints:

- MUST be a JSON object.
- Foreman MUST NOT construct `display_context` with top-level fields that have the same names as authority-bearing fields.
- The adapter MAY reject approval requests whose `display_context` violates the top-level authority-bearing field-name rule.
- Nested fields within `display_context` MUST NOT use keys that match authority-bearing field names at any depth.
- MUST NOT influence approval validation.
- MUST NOT influence policy evaluation.
- MUST NOT be consumed by the Arbiter for transition decisions.
- MAY be included in audit as opaque metadata when Foreman chooses to preserve it.

The adapter MAY use `display_context` to render human-readable summaries, links, labels, warnings, or supplemental context.

---

## 7. Approval Response

Canonical adapter output:

```json
{
  "approval_request_id": "approval_request:123",
  "decision": "approved",
  "approver_id": "user:456",
  "approver_role": "release_manager",
  "requested_transition": "awaiting_approval->approved_for_release",
  "submitted_at": "2026-04-28T00:12:00Z",
  "metadata": {},
  "signature": null
}
```

Allowed `decision` values:

- `approved`
- `rejected`
- `revision_required`

Decision semantics:

- `approved` expresses approver intent to approve the requested transition.
- `rejected` expresses approver intent to reject the requested transition.
- `revision_required` expresses approver intent to request revision before release.

Decision values do not directly map to Foreman state transitions.

Only the Arbiter determines the resulting state.

Required preserved fields:

- `approval_request_id`
- `approver_id`
- `approver_role`
- `requested_transition`

Request-bound preserved fields:

These response fields MUST match the received immutable approval request, and the adapter MUST reject on mismatch:

- `approval_request_id`
- `approver_role`
- `requested_transition`

The response MUST NOT include the full hash binding set. Foreman MUST retain the immutable approval request and validate the response against that request during arbitration.

If an adapter implementation includes request hash fields in an extended response envelope, the Arbiter MUST ignore those response-provided hashes for approval validation. The immutable Foreman-created approval request is the only source of bound hash values.

---

## 8. Replay Contract

Replayable approval data consists of:

- the immutable approval request created by Foreman
- the adapter response submitted by the approver
- the Arbiter decision that accepted, rejected, ignored, or normalized the response

The adapter response alone is not sufficient to replay approval validity because it does not carry all bound hashes.

Foreman replay MUST reconstruct approval validation from the request plus response pair.

Runtime intent records MAY reference approval request refs, adapter response refs, normalized approval record refs, and approval signature refs as defined by the Intent Schema Specification. Those references are operational and audit material; they do not grant approval validity without Arbiter evaluation.

---

## 9. Arbiter Validation Boundary

Arbiter validation includes:

- approval request match
- requested transition match
- approver authorization
- bound hash equality
- expiration validity
- signature validation, when signatures are enforced
- state-machine legality for any resulting transition
- reason-code registry validation for any emitted Foreman reason code

Adapter validation is optional, defensive, and non-authoritative.

The adapter MAY perform UX or input checks such as missing field detection, enum checks, immutable-field comparison, or stale-request warnings, but those checks do not establish approval validity.

For expiration validity, Foreman uses Foreman-side arbitration time as the authoritative clock. Foreman MAY record Foreman-side response ingestion time as an audit/observability timestamp, but it MUST NOT be used for expiration validity. Adapter-provided `submitted_at` is a captured claim and audit field; it does not by itself prove that a response was submitted before `expires_at`.

---

## 10. Expiration Handling

The adapter MAY:

- display `expires_at`
- warn on submission after expiration
- block submission after expiration as a UX choice

The adapter MUST NOT:

- mutate intent state based on expiration
- emit `FOREMAN_APPROVAL_STALE`
- decide whether an expired response is valid

Adapter-side expiration handling is UX only.

If the adapter blocks submission after expiration, it does not need to send a special expired response to Foreman. Foreman can discover expiration from the immutable approval request's `expires_at` during candidate selection and arbitration.

The Arbiter performs the canonical expiration check. Foreman, Arbiter, and policy diagnostics use `FOREMAN_APPROVAL_STALE` for stale approval when that reason code is emitted.

---

## 11. Idempotency and Multi-Approver Behavior

`approval_request_id` defines the adapter idempotency boundary.

Adapter rules:

- identical submissions MAY be treated as idempotent
- conflicting duplicate submissions from the same `approver_id` for the same `approval_request_id` MUST be rejected when detectable
- same request plus different approver MAY be allowed

Definitions:

- Two submissions are identical iff they share the same `approval_request_id`, `approver_id`, `decision`, `approver_role`, and `requested_transition`.
- A conflicting duplicate submission is a submission for the same `approval_request_id` and `approver_id` whose `decision` differs from a prior submission.
- A conflict is detectable iff the adapter's local submission store contains a prior submission for the same (`approval_request_id`, `approver_id`) at the time the new submission is evaluated.

The adapter performs best-effort duplicate detection. Canonical resolution is Arbiter-owned regardless of adapter behavior.

The Arbiter owns the resolution strategy. For Foreman MVP, the Arbiter MUST apply first-write-wins per (`approval_request_id`, `approver_id`) using arbitration time ordering; later responses for the same pair are ignored for normalization and transition decisions.

Retries MUST NOT reinterpret an approval response as a Foreman transition.

---

## 12. Adapter Receipt

Adapter receipts are optional observability artifacts.

Example:

```json
{
  "hag_receipt_id": "hag_receipt:123",
  "approval_request_id": "approval_request:123",
  "adapter_id": "hag_adapter:local_cli",
  "adapter_version": "1.0.0",
  "delivery_status": "presented",
  "response_status": "submitted",
  "presented_at": "2026-04-28T00:01:00Z",
  "submitted_at": "2026-04-28T00:12:00Z"
}
```

If receipts are emitted:

- `delivery_status` MUST be one of: `presented`, `delivery_failed`
- `response_status` MUST be one of: `submitted`, `locally_rejected`

Receipts:

- are not approval records
- are not Foreman transition audit events
- do not establish approval validity
- are adapter-local observability artifacts

Storage location is implementation-defined.

---

## 13. Signature Model

MVP:

```json
{
  "signature": null
}
```

Future:

- signature binds to the approval response payload
- signature proves authorship only
- signature verification is Arbiter-owned when signatures are enforced

Invariant:

```text
Signature != authority.
```

---

## 14. Hash Handling

The adapter MUST:

- preserve received authority-bearing hash fields in the immutable request context
- present hash-bound request material without modifying it
- reject submissions whose preserved authority-bearing fields differ from the received request

The adapter MUST NOT:

- recompute hashes
- normalize hash strings
- verify hash equality
- decide whether a hash mismatch makes an approval stale
- perform live registry lookup

Hash validation is Arbiter responsibility.

Registry snapshot shapes and reason-code registry contents are owned by the Registry Specification. The adapter receives `registry_snapshot_hash` as an opaque authority-bearing value and does not interpret the referenced snapshot.

---

## 15. Migration and Rebind Boundary

Registry migration, controlled rebind, and approval-staleness effects are owned by the Registry Diff + Migration Specification.

The adapter MUST NOT:

- decide whether a registry change stales an approval
- decide whether a graph change stales an approval
- classify registry diffs or migration modes
- initiate or approve rebind
- update approval binding hashes after rebind

The adapter may present a new Foreman-created approval request after migration or rebind, but it treats that request as a fresh immutable request.

---

## 16. Failure Handling

Adapter failure output:

```json
{
  "approval_request_id": "approval_request:123",
  "status": "failed",
  "error_code": "HAG_ADAPTER_DELIVERY_FAILED",
  "occurred_at": "2026-04-28T00:03:00Z"
}
```

Adapter error codes are operational diagnostics.

They exist outside the Foreman reason-code registry.

They MUST NOT appear as Foreman transition reason codes.

---

## 17. Audit Contribution

The adapter MUST return enough data for Foreman to create authoritative audit records:

- `approval_request_id`
- `approver_id`
- `approver_role`
- `decision`
- `requested_transition`
- `submitted_at`
- `metadata`, when present
- `signature`, when present

Metadata rules:

- MUST be a JSON object.
- MAY be empty.
- MUST be preserved verbatim by the adapter.
- MUST NOT be canonicalized by the adapter.

Foreman owns authoritative audit, canonicalization, replay, and transition persistence.

---

## 18. Policy Approval Record Boundary

Adapter responses are not policy approval records.

Foreman MAY normalize a received adapter response and its immutable request into an approval record for policy evaluation.

The HAG Adapter Specification does not own the policy approval record schema. Policy-facing approval records use the canonical Policy Specification shape, including:

- `approval_id`
- `approval_request_id`
- `status`
- `approver_role`
- `requested_transition`
- `intent_hash`
- `graph_root_hash`
- `policy_hash`
- `decision_evidence_hash`
- `registry_snapshot_hash`
- `expires_at`

The Policy Specification owns the canonical policy approval record shape.

Only a normalized approval record with `status = "approved"` can satisfy the policy `approval_valid` predicate.

Adapter decisions `rejected` and `revision_required` are captured human decisions. They do not satisfy `approval_valid`.

---

## 19. Security Requirements

The adapter MUST:

- receive an authenticated approver identity from the deployment auth layer
- include that identity as `approver_id`
- preserve `approver_role` as provided in the request
- treat authority-bearing fields as read-only
- reject conflicting duplicate submissions from the same `approver_id` for the same `approval_request_id` when detectable (as defined in Section 11)
- avoid placing authority-bearing data in mutable display-only surfaces

Authentication is handled by the deployment environment, such as SSO, mTLS, or local operator identity.

The adapter consumes authenticated identity; it does not establish trust by itself.

---

## 20. Execution Flow

Adapter scope:

1. Foreman creates immutable approval request.
2. Adapter retrieves or receives request.
3. Adapter presents request and display context.
4. Human selects decision.
5. Adapter captures response.
6. Adapter validates request-bound preserved fields; rejects submission on mismatch.
7. Adapter returns response to Foreman.

Foreman scope:

1. Conveyor schedules arbitration.
2. Arbiter loads request plus response.
3. Arbiter normalizes request plus response into the policy approval record shape when policy evaluation consumes approvals.
4. Arbiter validates approval.
5. Arbiter determines resulting transition.
6. Store commits transition and audit atomically.

Invariant:

```text
The adapter never advances state.
```

---

## 21. Adapter Registration

Example:

```json
{
  "adapter_id": "hag_adapter:local_cli",
  "adapter_version": "1.0.0",
  "adapter_type": "local_cli",
  "supported_decisions": [
    "approved",
    "rejected",
    "revision_required"
  ],
  "signature_mode": "none"
}
```

Registration is operational configuration only.

Registration does not grant transition authority.

---

## 22. Reason-Code Boundary

The adapter does not emit Foreman reason codes.

Adapter error codes and Foreman reason codes are separate namespaces.

Runtime Foreman reason codes are registry-bound and Arbiter-owned as defined by the Registry Specification.

Adapter diagnostics, UI warnings, transport failures, and adapter-local errors MUST NOT be used as Foreman transition reason codes unless the Arbiter maps them to registered Foreman runtime reason codes during arbitration.

```text
Adapter operational errors MUST NOT be used as Foreman transition reason codes.
```

---

## 23. Acceptance Criteria

AC 1.1 Adapter accepts a valid approval request.  
AC 1.2 Adapter presents request clearly.  
AC 1.3 Adapter returns a valid decision enum.  
AC 1.4 Adapter treats authority-bearing fields as read-only after request receipt.  
AC 1.5 Adapter rejects submissions with mutated preserved authority-bearing fields.  
AC 1.6 Adapter does not mutate intent state.  
AC 1.7 Adapter supports idempotent submission behavior.  
AC 1.8 Adapter does not evaluate policy or evidence.  
AC 1.9 Adapter contributes data needed for replayable approval audit.  
AC 1.10 Adapter does not interpret approval validity.  
AC 1.11 Adapter response is explicitly distinct from policy approval records.  
AC 1.12 Replay validation uses immutable approval request plus adapter response.  
AC 1.13 Adapter error codes are never emitted as Foreman transition reason codes.  
AC 1.14 Adapter does not perform live registry lookup or registry validation.  
AC 1.15 Adapter does not decide whether migration, rebind, graph changes, or hash changes stale an approval.  
AC 1.16 Foreman does not place authority-bearing field names as top-level `display_context` keys (or adapter rejects such requests).  
AC 1.17 Adapter receipts (if emitted) are not approval records and do not establish approval validity.  
AC 1.18 MVP adapter output sets `signature` to null.  
AC 1.19 When signatures are enforced, signature verification authority is Arbiter-owned (adapter does not establish approval validity).  
AC 1.20 Adapter failure output conforms to the specified failure shape and uses an adapter error-code namespace distinct from Foreman reason codes.

---

## 24. Core Principle

The HAG Adapter captures the human decision.

It does not decide what the decision means.
