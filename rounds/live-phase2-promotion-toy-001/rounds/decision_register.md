# Decision Register

- mode: `end_of_cycle`
- terminal_state: `PHASE_1_STABLE`
- unresolved_human_decision_count: `1`

## dec_ecafc11b4d5c95c9

- type: `scope_change`
- triggers: `scope_change`
- round: `2`
- profile: `determinism`
- action: `present_at_end`
- requires_human_decision: `true`
- affected_sections: Adapter Contract

Should `Adapter Contract` adopt this change (scope change): **Determinism rule:** For a given `request_id`, the adapter always returns the status currently recorded for that key. Status transitions (`PENDING → APPROVED` or `PENDING → REJECTED`) are externally driven and recorded atomically; once a terminal status (`APPROVED` or `REJECTED`) is set, it cannot change.

Evidence:
- **Determinism rule:** For a given `request_id`, the adapter always returns the status currently recorded for that key. Status transitions (`PENDING → APPROVED` or `PENDING → REJECTED`) are externally driven and recorded atomically; once a terminal status (`APPROVED` or `REJECTED`) is set, it cannot change.

Risk if wrong: The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.
