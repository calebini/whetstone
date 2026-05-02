# Decision Register

- mode: `end_of_cycle`
- terminal_state: `DECISION_SCAN_COMPLETE`
- unresolved_human_decision_count: `42`

## dec_941b891a3b084d61

- type: `choose_policy`
- triggers: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 2. Alignment With Foreman Specs

Should `2. Alignment With Foreman Specs` adopt this change (choose policy): The High-Level Design (HLD) remains authoritative for:

Evidence:
- The High-Level Design (HLD) remains authoritative for:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_9cf50a5f725ac4a9

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this change (tighten requirement, choose policy): `trace_id` is OPTIONAL and MUST be treated as an opaque string. It is non-authoritative correlation context.

Evidence:
- - `trace_id` is OPTIONAL and MUST be treated as an opaque string. It is non-authoritative correlation context.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_e509873363b8b2a2

- type: `scope_change`
- triggers: `tighten_requirement`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this change (tighten requirement, scope change): If `trace_id` is present in the request, the adapter MUST echo the same `trace_id` value into any approval response (Section 7) without modification.

Evidence:
- - If `trace_id` is present in the request, the adapter MUST echo the same `trace_id` value into any approval response (Section 7) without modification.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_a773f6ac4a1c8348

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this change (tighten requirement, choose policy, scope change): The adapter MUST treat all authority-bearing fields in the received request as read-only after request receipt.

Evidence:
- The adapter MUST treat all authority-bearing fields in the received request as read-only after request receipt.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_122c50a480036fce

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this change (tighten requirement, choose policy, scope change): On submission, the adapter MUST reject the submission if any request-bound preserved field in the response differs from the received request. The request-bound preserved field set is:

Evidence:
- On submission, the adapter MUST reject the submission if any request-bound preserved field in the response differs from the received request. The request-bound preserved field set is:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_3fa72cf8fefd5186

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 6. Display Context

Should `6. Display Context` adopt this change (tighten requirement, choose policy): Nested fields within `display_context` MUST NOT use keys that match authority-bearing field names at any depth.

Evidence:
- - Nested fields within `display_context` MUST NOT use keys that match authority-bearing field names at any depth.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_63d3d281413778df

- type: `choose_policy`
- triggers: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this change (choose policy): Request-bound preserved fields:

Evidence:
- Request-bound preserved fields:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_0ba19025ce6413f6

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this change (tighten requirement, choose policy, scope change): These response fields MUST match the received immutable approval request, and the adapter MUST reject on mismatch:

Evidence:
- These response fields MUST match the received immutable approval request, and the adapter MUST reject on mismatch:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_9a5b3be53f2d30d6

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this change (tighten requirement): If the received request includes `trace_id`, the response MUST include the identical `trace_id` value.

Evidence:
- - If the received request includes `trace_id`, the response MUST include the identical `trace_id` value.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_88b24e3db1bd26db

- type: `relax_requirement`
- triggers: `relax_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this change (relax requirement): If the received request does not include `trace_id`, the response MAY omit `trace_id`.

Evidence:
- - If the received request does not include `trace_id`, the response MAY omit `trace_id`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d58faa06e77cbc76

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this change (choose policy, scope change): For expiration validity, Foreman uses Foreman-side arbitration time as the authoritative clock.

Evidence:
- For expiration validity, Foreman uses Foreman-side arbitration time as the authoritative clock.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_f29d758c98524678

- type: `scope_change`
- triggers: `tighten_requirement`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this change (tighten requirement, scope change): Foreman SHOULD record a Foreman-side response ingestion timestamp for every received adapter response as an audit/observability field named `foreman_ingested_at`, but it MUST NOT be used for expiration validity.

Evidence:
- Foreman SHOULD record a Foreman-side response ingestion timestamp for every received adapter response as an audit/observability field named `foreman_ingested_at`, but it MUST NOT be used for expiration validity.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_2649a7fecdcd21d8

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this change (scope change): Adapter-provided `submitted_at` is a captured claim and audit field; it does not by itself prove that a response was submitted before `expires_at`.

Evidence:
- Adapter-provided `submitted_at` is a captured claim and audit field; it does not by itself prove that a response was submitted before `expires_at`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_388da444dae804ff

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this change (scope change): If the adapter blocks submission after expiration, it does not need to send a special expired response to Foreman.

Evidence:
- If the adapter blocks submission after expiration, it does not need to send a special expired response to Foreman.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_eb0154632905e4e9

- type: `scope_change`
- triggers: `relax_requirement`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this change (relax requirement, scope change): However, when a submission attempt is blocked due to adapter-local expiration detection, the adapter SHOULD emit an adapter receipt (Section 12) with `response_status = "locally_rejected"` and `reason = "adapter_expiration_block"`.

Evidence:
- However, when a submission attempt is blocked due to adapter-local expiration detection, the adapter SHOULD emit an adapter receipt (Section 12) with `response_status = "locally_rejected"` and `reason = "adapter_expiration_block"`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_72cceb2d20b54af5

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this change (choose policy, scope change): Foreman can discover expiration from the immutable approval request's `expires_at` during candidate selection and arbitration.

Evidence:
- Foreman can discover expiration from the immutable approval request's `expires_at` during candidate selection and arbitration.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_f2cab6b440a8a291

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11. Idempotency and Multi-Approver Behavior

Should `11. Idempotency and Multi-Approver Behavior` adopt this change (tighten requirement): conflicting duplicate submissions from the same `approver_id` for the same `approval_request_id` MUST be rejected when detectable

Evidence:
- - conflicting duplicate submissions from the same `approver_id` for the same `approval_request_id` MUST be rejected when detectable

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d3401684f8bdb638

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11. Idempotency and Multi-Approver Behavior

Should `11. Idempotency and Multi-Approver Behavior` adopt this change (scope change): A conflict is detectable iff the adapter's local submission store contains a prior submission for the same (`approval_request_id`, `approver_id`) at the time the new submission is evaluated.

Evidence:
- - A conflict is detectable iff the adapter's local submission store contains a prior submission for the same (`approval_request_id`, `approver_id`) at the time the new submission is evaluated.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_520d1083a37f374e

- type: `choose_policy`
- triggers: `tighten_requirement`, `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11. Idempotency and Multi-Approver Behavior

Should `11. Idempotency and Multi-Approver Behavior` adopt this change (tighten requirement, choose policy, scope change): The Arbiter owns the resolution strategy. For Foreman MVP, the Arbiter MUST apply first-write-wins per (`approval_request_id`, `approver_id`) using arbitration time ordering; later responses for the same pair are ignored for normalization and transition decisions.

Evidence:
- The Arbiter owns the resolution strategy. For Foreman MVP, the Arbiter MUST apply first-write-wins per (`approval_request_id`, `approver_id`) using arbitration time ordering; later responses for the same pair are ignored for normalization and transition decisions.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_0eb8a3144ab711c2

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (scope change): Adapter receipts are observability artifacts.

Evidence:
- Adapter receipts are observability artifacts.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_b905dec2674a9f33

- type: `scope_change`
- triggers: `relax_requirement`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (relax requirement, scope change): Adapters SHOULD emit a receipt for every approval request presentation attempt and for every approval response submission outcome (including adapter-local rejection outcomes).

Evidence:
- Adapters SHOULD emit a receipt for every approval request presentation attempt and for every approval response submission outcome (including adapter-local rejection outcomes).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_2dc352ce39d60704

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (tighten requirement): Adapters MUST emit a receipt when `delivery_status = "delivery_failed"`.

Evidence:
- Adapters MUST emit a receipt when `delivery_status = "delivery_failed"`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d58a8432721cde1e

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (tighten requirement): `delivery_status` MUST be one of: `presented`, `delivery_failed`

Evidence:
- - `delivery_status` MUST be one of: `presented`, `delivery_failed`

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_17fcfc5a406179b0

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (tighten requirement): `response_status` MUST be one of: `submitted`, `locally_rejected`

Evidence:
- - `response_status` MUST be one of: `submitted`, `locally_rejected`

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_85793aa012968f17

- type: `tighten_requirement`
- triggers: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (tighten requirement): `reason` is OPTIONAL. If present, it MUST be an opaque string suitable for operator diagnostics.

Evidence:
- - `reason` is OPTIONAL. If present, it MUST be an opaque string suitable for operator diagnostics.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_45fd36674b073669

- type: `scope_change`
- triggers: `relax_requirement`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (relax requirement, scope change): When `response_status = "locally_rejected"` due to adapter-local expiration detection, adapters SHOULD set `reason = "adapter_expiration_block"`.

Evidence:
- - When `response_status = "locally_rejected"` due to adapter-local expiration detection, adapters SHOULD set `reason = "adapter_expiration_block"`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_71c0e2c144ee5c63

- type: `relax_requirement`
- triggers: `relax_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (relax requirement): Adapters SHOULD emit receipts to a well-known structured log sink configured by the deployment environment.

Evidence:
- - Adapters SHOULD emit receipts to a well-known structured log sink configured by the deployment environment.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_6bc497f1de87770e

- type: `scope_change`
- triggers: `relax_requirement`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this change (relax requirement, scope change): If an adapter exposes a programmatic receipt retrieval surface, it SHOULD support querying by `approval_request_id`.

Evidence:
- - If an adapter exposes a programmatic receipt retrieval surface, it SHOULD support querying by `approval_request_id`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_f76e2223d7b7d50b

- type: `add_operational_requirement`
- triggers: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this change (add operational requirement): `HAG_ADAPTER_REQUEST_RETRIEVAL_FAILED` (failed to retrieve or receive the approval request)

Evidence:
- - `HAG_ADAPTER_REQUEST_RETRIEVAL_FAILED` (failed to retrieve or receive the approval request)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_e7084af7c53b8923

- type: `add_operational_requirement`
- triggers: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this change (add operational requirement): `HAG_ADAPTER_PRESENTATION_FAILED` (failed to present the request to the human)

Evidence:
- - `HAG_ADAPTER_PRESENTATION_FAILED` (failed to present the request to the human)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_63cad918f9153edf

- type: `scope_change`
- triggers: `add_operational_requirement`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this change (add operational requirement, scope change): `HAG_ADAPTER_SUBMISSION_FAILED` (failed to submit a captured response to Foreman)

Evidence:
- - `HAG_ADAPTER_SUBMISSION_FAILED` (failed to submit a captured response to Foreman)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_897a228e645242b9

- type: `add_operational_requirement`
- triggers: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this change (add operational requirement): `HAG_ADAPTER_AUTH_FAILED` (authentication/authorization or identity-layer failure)

Evidence:
- - `HAG_ADAPTER_AUTH_FAILED` (authentication/authorization or identity-layer failure)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_99c958ca52639329

- type: `add_operational_requirement`
- triggers: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this change (add operational requirement): `HAG_ADAPTER_DELIVERY_FAILED` (generic delivery failure when a more specific code is unavailable)

Evidence:
- - `HAG_ADAPTER_DELIVERY_FAILED` (generic delivery failure when a more specific code is unavailable)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d0540ba9b9a25905

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 20. Execution Flow

Should `20. Execution Flow` adopt this change (choose policy, scope change): 6. Adapter validates request-bound preserved fields; rejects submission on mismatch.

Evidence:
- 6. Adapter validates request-bound preserved fields; rejects submission on mismatch.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_3c37f5d265e8007c

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 20. Execution Flow

Should `20. Execution Flow` adopt this change (scope change): 7. Adapter returns response to Foreman.

Evidence:
- 7. Adapter returns response to Foreman.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_cf5e9fc697e3f329

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (scope change): AC 1.13 Adapter error codes are never emitted as Foreman transition reason codes.

Evidence:
- AC 1.13 Adapter error codes are never emitted as Foreman transition reason codes.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_2290b94c91cad0e7

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (scope change): AC 1.15 Adapter does not decide whether migration, rebind, graph changes, or hash changes stale an approval.

Evidence:
- AC 1.15 Adapter does not decide whether migration, rebind, graph changes, or hash changes stale an approval.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d6b6a50866974aa5

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (choose policy, scope change): AC 1.16 Foreman does not place authority-bearing field names as top-level `display_context` keys (or adapter rejects such requests).

Evidence:
- AC 1.16 Foreman does not place authority-bearing field names as top-level `display_context` keys (or adapter rejects such requests).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_a111c394677d54ed

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (scope change): AC 1.17 Adapter receipts (if emitted) are not approval records and do not establish approval validity.

Evidence:
- AC 1.17 Adapter receipts (if emitted) are not approval records and do not establish approval validity.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_aba3eaa573863e2b

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (scope change): AC 1.18 MVP adapter output sets `signature` to null.

Evidence:
- AC 1.18 MVP adapter output sets `signature` to null.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_8be54d9c3e26e05d

- type: `choose_policy`
- triggers: `choose_policy`, `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (choose policy, scope change): AC 1.19 When signatures are enforced, signature verification authority is Arbiter-owned (adapter does not establish approval validity).

Evidence:
- AC 1.19 When signatures are enforced, signature verification authority is Arbiter-owned (adapter does not establish approval validity).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_4cf678f4216fa63e

- type: `scope_change`
- triggers: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this change (scope change): AC 1.20 Adapter failure output conforms to the specified failure shape and uses an adapter error-code namespace distinct from Foreman reason codes.

Evidence:
- AC 1.20 Adapter failure output conforms to the specified failure shape and uses an adapter error-code namespace distinct from Foreman reason codes.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.
