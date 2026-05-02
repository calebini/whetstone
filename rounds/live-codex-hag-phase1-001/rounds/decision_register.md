# Decision Register

- mode: `end_of_cycle`
- terminal_state: `PHASE_1_STABLE`
- unresolved_human_decision_count: `46`

## dec_d61cf6458cd83d65

- type: `choose_policy`
- triggers: `choose_policy`
- round: `1`
- profile: `structural_integrity`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this change (choose policy): Required preserved fields (copied from the immutable request):

Evidence:
- Required preserved fields (copied from the immutable request):

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_0b2295f0c147b780

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `structural_integrity`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this change (scope change): Required response fields (supplied by adapter runtime and human input):

Evidence:
- Required response fields (supplied by adapter runtime and human input):

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_c8ded64e7b2865b7

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `1`
- profile: `structural_integrity`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this change (tighten requirement): `approver_id` (MUST be sourced from authenticated identity, not from the request)

Evidence:
- - `approver_id` (MUST be sourced from authenticated identity, not from the request)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_218754ad04aaab25

- type: `scope_change`
- triggers: `tighten_requirement`, `scope_change`
- round: `1`
- profile: `structural_integrity`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 22. Reason-Code Boundary

Should `22. Reason-Code Boundary` adopt this change (tighten requirement, scope change): Adapter operational errors MUST NOT be used as Foreman reason codes.

Evidence:
- Adapter operational errors MUST NOT be used as Foreman reason codes.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_a1345c0cd4623cf9

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `2`
- profile: `determinism`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this change (tighten requirement, choose policy, scope change): For expiration validity, Foreman uses Foreman-side response ingestion time as the authoritative clock. Foreman MUST persist the specific `response_received_at` timestamp used for expiration comparison as part of Arbiter decision material, and Foreman replay MUST use that persisted timestamp for the expiration check.

Evidence:
- For expiration validity, Foreman uses Foreman-side response ingestion time as the authoritative clock. Foreman MUST persist the specific `response_received_at` timestamp used for expiration comparison as part of Arbiter decision material, and Foreman replay MUST use that persisted timestamp for the expiration check.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_2649a7fecdcd21d8

- type: `scope_change`
- triggers: `scope_change`
- round: `2`
- profile: `determinism`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this change (scope change): Adapter-provided `submitted_at` is a captured claim and audit field; it does not by itself prove that a response was submitted before `expires_at`.

Evidence:
- Adapter-provided `submitted_at` is a captured claim and audit field; it does not by itself prove that a response was submitted before `expires_at`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_a0197f10d3f01366

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `2`
- profile: `determinism`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this change (choose policy, scope change): The Arbiter performs the canonical expiration check using Foreman-persisted `response_received_at` as the comparison timestamp.

Evidence:
- The Arbiter performs the canonical expiration check using Foreman-persisted `response_received_at` as the comparison timestamp.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_ce2ef37cfb2578aa

- type: `choose_policy`
- triggers: `add_operational_requirement`, `choose_policy`, `scope_change`
- round: `2`
- profile: `determinism`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this change (add operational requirement, choose policy, scope change): Foreman, Arbiter, and policy diagnostics use `FOREMAN_APPROVAL_STALE` for stale approval when that reason code is emitted.

Evidence:
- Foreman, Arbiter, and policy diagnostics use `FOREMAN_APPROVAL_STALE` for stale approval when that reason code is emitted.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_b39c972bf3bc80c8

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `2`
- profile: `determinism`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 17. Audit Contribution

Should `17. Audit Contribution` adopt this change (tighten requirement, choose policy, scope change): MUST be preserved without semantic mutation by the adapter (no key insertion/removal, value rewriting, type coercion, or normalization of strings).

Evidence:
- - MUST be preserved without semantic mutation by the adapter (no key insertion/removal, value rewriting, type coercion, or normalization of strings).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_fa7dbb764a17e774

- type: `scope_change`
- triggers: `tighten_requirement`, `scope_change`
- round: `2`
- profile: `determinism`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 17. Audit Contribution

Should `17. Audit Contribution` adopt this change (tighten requirement, scope change): MUST NOT be canonicalized by the adapter (canonicalization, if any, is Foreman-owned).

Evidence:
- - MUST NOT be canonicalized by the adapter (canonicalization, if any, is Foreman-owned).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_ac2d42756277ef56

- type: `scope_change`
- triggers: `tighten_requirement`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1 Operational Persistence and Recovery

Should `11.1 Operational Persistence and Recovery` adopt this change (tighten requirement, scope change): The adapter MUST behave deterministically across retries and restarts with respect to:

Evidence:
- The adapter MUST behave deterministically across retries and restarts with respect to:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_1b55eba73bf3cce3

- type: `choose_policy`
- triggers: `choose_policy`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1 Operational Persistence and Recovery

Should `11.1 Operational Persistence and Recovery` adopt this change (choose policy): preserved authority-bearing request fields

Evidence:
- - preserved authority-bearing request fields

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d219bb889ef9f9af

- type: `choose_policy`
- triggers: `choose_policy`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1 Operational Persistence and Recovery

Should `11.1 Operational Persistence and Recovery` adopt this change (choose policy): idempotency at the `approval_request_id` boundary

Evidence:
- - idempotency at the `approval_request_id` boundary

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_3677c6aadd40764b

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.1 Minimum Durable State (When Applicable)

Should `11.1.1 Minimum Durable State (When Applicable)` adopt this change (tighten requirement, choose policy, scope change): If the adapter can receive the same `approval_request_id` more than once over time (including after process restart) and is expected to perform preserved-field comparison or duplicate/conflict detection beyond the immediate in-memory lifecycle, it MUST durably persist, at minimum:

Evidence:
- If the adapter can receive the same `approval_request_id` more than once over time (including after process restart) and is expected to perform preserved-field comparison or duplicate/conflict detection beyond the immediate in-memory lifecycle, it MUST durably persist, at minimum:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_3edde5beda829c04

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.1 Minimum Durable State (When Applicable)

Should `11.1.1 Minimum Durable State (When Applicable)` adopt this change (choose policy, scope change): the received immutable approval request (all authority-bearing fields, plus `created_at` and `display_context` if the adapter chooses to retain them)

Evidence:
- - the received immutable approval request (all authority-bearing fields, plus `created_at` and `display_context` if the adapter chooses to retain them)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_787f5617ee5229a5

- type: `scope_change`
- triggers: `tighten_requirement`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.1 Minimum Durable State (When Applicable)

Should `11.1.1 Minimum Durable State (When Applicable)` adopt this change (tighten requirement, scope change): Durable persistence MUST survive normal process restart and crash recovery for the adapter to claim restart-safe idempotency and mutated-field rejection.

Evidence:
- Durable persistence MUST survive normal process restart and crash recovery for the adapter to claim restart-safe idempotency and mutated-field rejection.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_00cdb3fcb12860e5

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.2 Stateless Profile (Foreman-Owned Durability)

Should `11.1.2 Stateless Profile (Foreman-Owned Durability)` adopt this change (scope change): #### 11.1.2 Stateless Profile (Foreman-Owned Durability)

Evidence:
- #### 11.1.2 Stateless Profile (Foreman-Owned Durability)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d1271b8763e802ff

- type: `scope_change`
- triggers: `relax_requirement`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.2 Stateless Profile (Foreman-Owned Durability)

Should `11.1.2 Stateless Profile (Foreman-Owned Durability)` adopt this change (relax requirement, scope change): An adapter MAY be stateless with respect to durable storage if and only if:

Evidence:
- An adapter MAY be stateless with respect to durable storage if and only if:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_bbe9316c6cf6e5ba

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.2 Stateless Profile (Foreman-Owned Durability)

Should `11.1.2 Stateless Profile (Foreman-Owned Durability)` adopt this change (choose policy, scope change): Foreman provides the immutable approval request on each presentation/submission attempt, or provides an immutable request store reference that the adapter can dereference reliably at time of presentation, and

Evidence:
- - Foreman provides the immutable approval request on each presentation/submission attempt, or provides an immutable request store reference that the adapter can dereference reliably at time of presentation, and

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_1350b855f9d77201

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.2 Stateless Profile (Foreman-Owned Durability)

Should `11.1.2 Stateless Profile (Foreman-Owned Durability)` adopt this change (scope change): Foreman (or an upstream gateway owned by Foreman) provides the canonical idempotency and duplicate/conflict handling.

Evidence:
- - Foreman (or an upstream gateway owned by Foreman) provides the canonical idempotency and duplicate/conflict handling.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_85b6b5f606883d57

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.2 Stateless Profile (Foreman-Owned Durability)

Should `11.1.2 Stateless Profile (Foreman-Owned Durability)` adopt this change (tighten requirement, choose policy, scope change): the adapter MUST still treat authority-bearing fields in the received request as read-only within the current request envelope

Evidence:
- - the adapter MUST still treat authority-bearing fields in the received request as read-only within the current request envelope

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_49dfdab2630230a9

- type: `relax_requirement`
- triggers: `relax_requirement`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.2 Stateless Profile (Foreman-Owned Durability)

Should `11.1.2 Stateless Profile (Foreman-Owned Durability)` adopt this change (relax requirement): mutated-field rejection and duplicate/conflict detection MAY be limited to what is detectable within that envelope and that single submission attempt

Evidence:
- - mutated-field rejection and duplicate/conflict detection MAY be limited to what is detectable within that envelope and that single submission attempt

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d665be73e2cc5dbe

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.2 Stateless Profile (Foreman-Owned Durability)

Should `11.1.2 Stateless Profile (Foreman-Owned Durability)` adopt this change (choose policy, scope change): In all cases, Foreman remains responsible for authoritative replay, audit, and arbitration.

Evidence:
- In all cases, Foreman remains responsible for authoritative replay, audit, and arbitration.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_a46853765670b55d

- type: `scope_change`
- triggers: `tighten_requirement`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.3 Recovery Behavior

Should `11.1.3 Recovery Behavior` adopt this change (tighten requirement, scope change): If the adapter uses durable state (Section 11.1.1), then after restart it MUST:

Evidence:
- If the adapter uses durable state (Section 11.1.1), then after restart it MUST:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_42c8f37d139f4217

- type: `choose_policy`
- triggers: `choose_policy`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.3 Recovery Behavior

Should `11.1.3 Recovery Behavior` adopt this change (choose policy): reject submissions for an `approval_request_id` when the preserved authority-bearing fields differ from the originally received request for that `approval_request_id`

Evidence:
- - reject submissions for an `approval_request_id` when the preserved authority-bearing fields differ from the originally received request for that `approval_request_id`

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_f44409387e2e0725

- type: `scope_change`
- triggers: `tighten_requirement`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.3 Recovery Behavior

Should `11.1.3 Recovery Behavior` adopt this change (tighten requirement, scope change): treat duplicate submissions for an already-recorded (`approval_request_id`, `approver_id`) as idempotent or reject them, but MUST NOT reinterpret them as a Foreman transition

Evidence:
- - treat duplicate submissions for an already-recorded (`approval_request_id`, `approver_id`) as idempotent or reject them, but MUST NOT reinterpret them as a Foreman transition

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_bda7280f9a9ed5cf

- type: `scope_change`
- triggers: `relax_requirement`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11.1.3 Recovery Behavior

Should `11.1.3 Recovery Behavior` adopt this change (relax requirement, scope change): If durable state is unavailable or corrupted, the adapter MAY fail closed by emitting an adapter failure output (Section 16) rather than accepting a potentially non-deterministic submission.

Evidence:
- If durable state is unavailable or corrupted, the adapter MAY fail closed by emitting an adapter failure output (Section 16) rather than accepting a potentially non-deterministic submission.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d25d63bac0fe2838

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.1 Failure Lifecycle and Delivery Semantics

Should `16.1 Failure Lifecycle and Delivery Semantics` adopt this change (scope change): Failure output is the adapter's contract-level error reporting to Foreman when the adapter cannot:

Evidence:
- Failure output is the adapter's contract-level error reporting to Foreman when the adapter cannot:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_7492d81f6d2b8be5

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.1 Failure Lifecycle and Delivery Semantics

Should `16.1 Failure Lifecycle and Delivery Semantics` adopt this change (scope change): deliver a captured response to Foreman as required by the deployment.

Evidence:
- - deliver a captured response to Foreman as required by the deployment.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_8c25c6cd6fd04c88

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.1 Failure Lifecycle and Delivery Semantics

Should `16.1 Failure Lifecycle and Delivery Semantics` adopt this change (scope change): Unless otherwise negotiated by deployment integration, a failure output is returned to Foreman synchronously on the same channel used for request/response exchange.

Evidence:
- Unless otherwise negotiated by deployment integration, a failure output is returned to Foreman synchronously on the same channel used for request/response exchange.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_738aef311e60722b

- type: `scope_change`
- triggers: `relax_requirement`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.1 Failure Lifecycle and Delivery Semantics

Should `16.1 Failure Lifecycle and Delivery Semantics` adopt this change (relax requirement, scope change): The adapter MAY additionally emit telemetry/logging, but telemetry is not a substitute for returning a contract failure output to Foreman when Foreman is the delivery target.

Evidence:
- The adapter MAY additionally emit telemetry/logging, but telemetry is not a substitute for returning a contract failure output to Foreman when Foreman is the delivery target.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_42e67a51c453fa23

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.2 Required Failure Fields

Should `16.2 Required Failure Fields` adopt this change (tighten requirement): A failure output MUST include:

Evidence:
- A failure output MUST include:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_596e83035bce6c02

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.2 Required Failure Fields

Should `16.2 Required Failure Fields` adopt this change (tighten requirement): `status` (MUST be `failed`)

Evidence:
- - `status` (MUST be `failed`)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_089c18f595e357b4

- type: `relax_requirement`
- triggers: `relax_requirement`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.2 Required Failure Fields

Should `16.2 Required Failure Fields` adopt this change (relax requirement): A failure output SHOULD include when available:

Evidence:
- A failure output SHOULD include when available:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_88b8db2532c28232

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.2 Required Failure Fields

Should `16.2 Required Failure Fields` adopt this change (scope change): `hag_receipt_id` (to correlate with adapter receipts, if receipts are emitted)

Evidence:
- - `hag_receipt_id` (to correlate with adapter receipts, if receipts are emitted)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_90cdbcf1e3c6a09d

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.2 Required Failure Fields

Should `16.2 Required Failure Fields` adopt this change (scope change): `retryable` (boolean; whether Foreman can retry the same operation)

Evidence:
- - `retryable` (boolean; whether Foreman can retry the same operation)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_9b5481cebc97b67b

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.2 Required Failure Fields

Should `16.2 Required Failure Fields` adopt this change (scope change): `details` (JSON object; adapter-local diagnostic data)

Evidence:
- - `details` (JSON object; adapter-local diagnostic data)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_40a2fcae732a8bfd

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.2 Required Failure Fields

Should `16.2 Required Failure Fields` adopt this change (tighten requirement, choose policy, scope change): If included, `details` MUST NOT contain Foreman reason codes, MUST NOT claim approval validity, and MUST NOT be interpreted as transition authority.

Evidence:
- If included, `details` MUST NOT contain Foreman reason codes, MUST NOT claim approval validity, and MUST NOT be interpreted as transition authority.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_e4224b4a0f94cc42

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.3 Retry Classification

Should `16.3 Retry Classification` adopt this change (scope change): If the adapter includes `retryable`:

Evidence:
- If the adapter includes `retryable`:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_a4892c0d949c0031

- type: `scope_change`
- triggers: `relax_requirement`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.3 Retry Classification

Should `16.3 Retry Classification` adopt this change (relax requirement, scope change): `retryable = true` indicates a transient adapter-side failure where Foreman may retry without changing the approval request.

Evidence:
- - `retryable = true` indicates a transient adapter-side failure where Foreman may retry without changing the approval request.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d4f4a06ffdc2cb01

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.3 Retry Classification

Should `16.3 Retry Classification` adopt this change (scope change): `retryable = false` indicates a terminal adapter-side failure for that adapter instance/configuration, where retry without remediation is unlikely to succeed.

Evidence:
- - `retryable = false` indicates a terminal adapter-side failure for that adapter instance/configuration, where retry without remediation is unlikely to succeed.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_4bf700aa5127b3e5

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.3 Retry Classification

Should `16.3 Retry Classification` adopt this change (choose policy, scope change): Retry classification is operational guidance only and does not grant authority to emit Foreman reason codes.

Evidence:
- Retry classification is operational guidance only and does not grant authority to emit Foreman reason codes.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_34330b87f26c0dab

- type: `scope_change`
- triggers: `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.4 `error_code` Namespace

Should `16.4 `error_code` Namespace` adopt this change (scope change): `error_code` is an adapter-local namespace and is not registry-bound.

Evidence:
- `error_code` is an adapter-local namespace and is not registry-bound.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_f81a2ff8497843ae

- type: `relax_requirement`
- triggers: `relax_requirement`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16.4 `error_code` Namespace

Should `16.4 `error_code` Namespace` adopt this change (relax requirement): This specification does not define an exhaustive enum. Implementations SHOULD use stable, documented string constants (for example, `HAG_ADAPTER_*`) to support consistent operations.

Evidence:
- This specification does not define an exhaustive enum. Implementations SHOULD use stable, documented string constants (for example, `HAG_ADAPTER_*`) to support consistent operations.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_412ad4e5a6aeea26

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (choose policy, scope change): AC 1.16 Adapter defines restart-safe behavior for preserved-field comparison and best-effort duplicate/conflict detection (Section 11.1).

Evidence:
- AC 1.16 Adapter defines restart-safe behavior for preserved-field comparison and best-effort duplicate/conflict detection (Section 11.1).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_6610c552b4445b5a

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `3`
- profile: `operability`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (choose policy, scope change): AC 1.17 Adapter failure outputs include required fields and retry classification guidance without leaking Foreman authority (Section 16).

Evidence:
- AC 1.17 Adapter failure outputs include required fields and retry classification guidance without leaking Foreman authority (Section 16).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.
