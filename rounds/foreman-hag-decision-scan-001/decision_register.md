# Decision Register

- mode: `end_of_cycle`
- terminal_state: `DECISION_SCAN_COMPLETE`
- unresolved_human_decision_count: `64`

## dec_3326808724e1c171

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 2. Alignment With Foreman Specs

Should `2. Alignment With Foreman Specs` adopt this choose policy: The High-Level Design (HLD) remains authoritative for:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_3ec042de5a211fad

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this tighten requirement: `trace_id` is OPTIONAL and MUST be treated as an opaque string. It is non-authoritative correlation context.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_6ec0d8f1b846c9d1

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this choose policy: `trace_id` is OPTIONAL and MUST be treated as an opaque string. It is non-authoritative correlation context.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_c4f40adb3803962f

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this tighten requirement: If `trace_id` is present in the request, the adapter MUST echo the same `trace_id` value into any approval response (Section 7) without modification.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_cb7d9149cf49fdb6

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this scope change: If `trace_id` is present in the request, the adapter MUST echo the same `trace_id` value into any approval response (Section 7) without modification.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_7d26975c901857ee

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this tighten requirement: The adapter MUST treat all authority-bearing fields in the received request as read-only after request receipt.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_42de6e88fec87f64

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this choose policy: The adapter MUST treat all authority-bearing fields in the received request as read-only after request receipt.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_eba47e05756fa720

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this scope change: The adapter MUST treat all authority-bearing fields in the received request as read-only after request receipt.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_6e846e3830ea012e

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this tighten requirement: On submission, the adapter MUST reject the submission if any request-bound preserved field in the response differs from the received request. The request-bound preserved field set is:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_8bacca586c78dfb2

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this choose policy: On submission, the adapter MUST reject the submission if any request-bound preserved field in the response differs from the received request. The request-bound preserved field set is:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_6f9d07d774e5b88d

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 5. Approval Request

Should `5. Approval Request` adopt this scope change: On submission, the adapter MUST reject the submission if any request-bound preserved field in the response differs from the received request. The request-bound preserved field set is:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_0f2be6b1c497d3ab

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 6. Display Context

Should `6. Display Context` adopt this tighten requirement: Nested fields within `display_context` MUST NOT use keys that match authority-bearing field names at any depth.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_ccbdd8ef8c66ca94

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 6. Display Context

Should `6. Display Context` adopt this choose policy: Nested fields within `display_context` MUST NOT use keys that match authority-bearing field names at any depth.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_554aa4db06d427f7

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this choose policy: Request-bound preserved fields:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_de637c67e72c76c2

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this tighten requirement: These response fields MUST match the received immutable approval request, and the adapter MUST reject on mismatch:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_75762b9a43de2d89

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this choose policy: These response fields MUST match the received immutable approval request, and the adapter MUST reject on mismatch:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_66c49fbd22589a39

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this scope change: These response fields MUST match the received immutable approval request, and the adapter MUST reject on mismatch:

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d38aafb44320facf

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this tighten requirement: If the received request includes `trace_id`, the response MUST include the identical `trace_id` value.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_7bed687f8424b96d

- type: `relax_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 7. Approval Response

Should `7. Approval Response` adopt this relax requirement: If the received request does not include `trace_id`, the response MAY omit `trace_id`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_6590d39cb4d934cc

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this choose policy: For expiration validity, Foreman uses Foreman-side arbitration time as the authoritative clock.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_e4c8a6a95ea9351d

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this scope change: For expiration validity, Foreman uses Foreman-side arbitration time as the authoritative clock.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_01921fb7668ad65c

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this tighten requirement: Foreman SHOULD record a Foreman-side response ingestion timestamp for every received adapter response as an audit/observability field named `foreman_ingested_at`, but it MUST NOT be used for expiration validity.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_17f59886459a7fb3

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this scope change: Foreman SHOULD record a Foreman-side response ingestion timestamp for every received adapter response as an audit/observability field named `foreman_ingested_at`, but it MUST NOT be used for expiration validity.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_8d00f178e8d37c03

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 9. Arbiter Validation Boundary

Should `9. Arbiter Validation Boundary` adopt this scope change: Adapter-provided `submitted_at` is a captured claim and audit field; it does not by itself prove that a response was submitted before `expires_at`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_1bc97e8559111e40

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this scope change: If the adapter blocks submission after expiration, it does not need to send a special expired response to Foreman.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_55800a51850144f1

- type: `relax_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this relax requirement: However, when a submission attempt is blocked due to adapter-local expiration detection, the adapter SHOULD emit an adapter receipt (Section 12) with `response_status = "locally_rejected"` and `reason = "adapter_expiration_block"`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_de2aa3cfb3b5c20c

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this scope change: However, when a submission attempt is blocked due to adapter-local expiration detection, the adapter SHOULD emit an adapter receipt (Section 12) with `response_status = "locally_rejected"` and `reason = "adapter_expiration_block"`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_f875b08aea7840aa

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this choose policy: Foreman can discover expiration from the immutable approval request's `expires_at` during candidate selection and arbitration.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_9b4e17559978ac7d

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 10. Expiration Handling

Should `10. Expiration Handling` adopt this scope change: Foreman can discover expiration from the immutable approval request's `expires_at` during candidate selection and arbitration.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_a7f49dd351a7b6ae

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11. Idempotency and Multi-Approver Behavior

Should `11. Idempotency and Multi-Approver Behavior` adopt this tighten requirement: conflicting duplicate submissions from the same `approver_id` for the same `approval_request_id` MUST be rejected when detectable

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_796397927254c11e

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11. Idempotency and Multi-Approver Behavior

Should `11. Idempotency and Multi-Approver Behavior` adopt this scope change: A conflict is detectable iff the adapter's local submission store contains a prior submission for the same (`approval_request_id`, `approver_id`) at the time the new submission is evaluated.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_277d7dae064a3716

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11. Idempotency and Multi-Approver Behavior

Should `11. Idempotency and Multi-Approver Behavior` adopt this tighten requirement: The Arbiter owns the resolution strategy. For Foreman MVP, the Arbiter MUST apply first-write-wins per (`approval_request_id`, `approver_id`) using arbitration time ordering; later responses for the same pair are ignored for normalization and transition decisions.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d83e19890be551d2

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11. Idempotency and Multi-Approver Behavior

Should `11. Idempotency and Multi-Approver Behavior` adopt this choose policy: The Arbiter owns the resolution strategy. For Foreman MVP, the Arbiter MUST apply first-write-wins per (`approval_request_id`, `approver_id`) using arbitration time ordering; later responses for the same pair are ignored for normalization and transition decisions.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_1e9217ef9a0729ec

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 11. Idempotency and Multi-Approver Behavior

Should `11. Idempotency and Multi-Approver Behavior` adopt this scope change: The Arbiter owns the resolution strategy. For Foreman MVP, the Arbiter MUST apply first-write-wins per (`approval_request_id`, `approver_id`) using arbitration time ordering; later responses for the same pair are ignored for normalization and transition decisions.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_515d20e6584ffd41

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this scope change: Adapter receipts are observability artifacts.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_547666ec7ecd24ef

- type: `relax_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this relax requirement: Adapters SHOULD emit a receipt for every approval request presentation attempt and for every approval response submission outcome (including adapter-local rejection outcomes).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_76e4b35b6aec482c

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this scope change: Adapters SHOULD emit a receipt for every approval request presentation attempt and for every approval response submission outcome (including adapter-local rejection outcomes).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_0228082bcd3ade9e

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this tighten requirement: Adapters MUST emit a receipt when `delivery_status = "delivery_failed"`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_72bb40df05854cde

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this tighten requirement: `delivery_status` MUST be one of: `presented`, `delivery_failed`

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_304edb331da84872

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this tighten requirement: `response_status` MUST be one of: `submitted`, `locally_rejected`

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_5ac425e734abc79b

- type: `tighten_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this tighten requirement: `reason` is OPTIONAL. If present, it MUST be an opaque string suitable for operator diagnostics.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_b309c8f380917587

- type: `relax_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this relax requirement: When `response_status = "locally_rejected"` due to adapter-local expiration detection, adapters SHOULD set `reason = "adapter_expiration_block"`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_604b81990fafe921

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this scope change: When `response_status = "locally_rejected"` due to adapter-local expiration detection, adapters SHOULD set `reason = "adapter_expiration_block"`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d3240df1b0b7be2f

- type: `relax_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this relax requirement: Adapters SHOULD emit receipts to a well-known structured log sink configured by the deployment environment.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_0f66f75db702d8f1

- type: `relax_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this relax requirement: If an adapter exposes a programmatic receipt retrieval surface, it SHOULD support querying by `approval_request_id`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_9901303c9a05ddba

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 12. Adapter Receipt

Should `12. Adapter Receipt` adopt this scope change: If an adapter exposes a programmatic receipt retrieval surface, it SHOULD support querying by `approval_request_id`.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_9227a37230574a5c

- type: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this add operational requirement: `HAG_ADAPTER_REQUEST_RETRIEVAL_FAILED` (failed to retrieve or receive the approval request)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_087d0f11acba63fd

- type: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this add operational requirement: `HAG_ADAPTER_PRESENTATION_FAILED` (failed to present the request to the human)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_ae726f45143d6286

- type: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this add operational requirement: `HAG_ADAPTER_SUBMISSION_FAILED` (failed to submit a captured response to Foreman)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_baeaafc8027c266d

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this scope change: `HAG_ADAPTER_SUBMISSION_FAILED` (failed to submit a captured response to Foreman)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_12058cbda2d37d1c

- type: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this add operational requirement: `HAG_ADAPTER_AUTH_FAILED` (authentication/authorization or identity-layer failure)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_3ec9c5f3e3099c3c

- type: `add_operational_requirement`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 16. Failure Handling

Should `16. Failure Handling` adopt this add operational requirement: `HAG_ADAPTER_DELIVERY_FAILED` (generic delivery failure when a more specific code is unavailable)

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_01026ba8b6a0f829

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 20. Execution Flow

Should `20. Execution Flow` adopt this choose policy: 6. Adapter validates request-bound preserved fields; rejects submission on mismatch.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_60c41e34c7e6a2df

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 20. Execution Flow

Should `20. Execution Flow` adopt this scope change: 6. Adapter validates request-bound preserved fields; rejects submission on mismatch.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_048c9f5cbd070537

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 20. Execution Flow

Should `20. Execution Flow` adopt this scope change: 7. Adapter returns response to Foreman.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_ef687a72e4f25a05

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this scope change: AC 1.13 Adapter error codes are never emitted as Foreman transition reason codes.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_9ff2060e57f9b1d0

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this scope change: AC 1.15 Adapter does not decide whether migration, rebind, graph changes, or hash changes stale an approval.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_7fb5da35cb987d17

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this choose policy: AC 1.16 Foreman does not place authority-bearing field names as top-level `display_context` keys (or adapter rejects such requests).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d9c739496ba5e96e

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this scope change: AC 1.16 Foreman does not place authority-bearing field names as top-level `display_context` keys (or adapter rejects such requests).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_e520b52913ee28b9

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this scope change: AC 1.17 Adapter receipts (if emitted) are not approval records and do not establish approval validity.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_5ec6097d57df45af

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this scope change: AC 1.18 MVP adapter output sets `signature` to null.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_9569f2c7edcf44a4

- type: `choose_policy`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this choose policy: AC 1.19 When signatures are enforced, signature verification authority is Arbiter-owned (adapter does not establish approval validity).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_d4082431717b4661

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this scope change: AC 1.19 When signatures are enforced, signature verification authority is Arbiter-owned (adapter does not establish approval validity).

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.

## dec_a9d44722967678a9

- type: `scope_change`
- round: `1`
- profile: `decision_scan`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: 23. Acceptance Criteria

Should `23. Acceptance Criteria` adopt this scope change: AC 1.20 Adapter failure output conforms to the specified failure shape and uses an adapter error-code namespace distinct from Foreman reason codes.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.
