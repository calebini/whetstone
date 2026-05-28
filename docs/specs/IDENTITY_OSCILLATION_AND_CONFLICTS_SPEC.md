# Identity Oscillation And Conflicts Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: identity_oscillation_and_conflicts_spec
target_spec_role: leaf_spec
-->

## ISSUE AND CONFLICT IDENTITY

Every reviewer feedback item MUST include a stable `feedback_id`.

Every persisted issue MUST include:
- `issue_id`
- `issue_fingerprint`

Every conflict MUST include:
- `conflict_id`
- `conflict_fingerprint`

Fingerprints are computed by the Orchestrator from normalized semantic fields, not from round number, reviewer-provided identifiers, timestamps, or client-specific formatting.

Issue fingerprint:

```text
issue_fingerprint = SHA256(
  normalized(issue_type) + "\n" +
  normalized(affected_sections) + "\n" +
  normalized(invariant_violated) + "\n" +
  normalized(claim)
)
```

Conflict fingerprint:

```text
conflict_fingerprint = SHA256(
  normalized(conflict_type) + "\n" +
  normalized(sorted_participating_issue_fingerprints) + "\n" +
  normalized(conflict_claim)
)
```

`issue_id` and `conflict_id` are deterministic aliases:

```text
issue_id = "iss_" + first_16_hex_chars(issue_fingerprint)
conflict_id = "con_" + first_16_hex_chars(conflict_fingerprint)
```

The same issue or conflict across rounds is determined by matching fingerprint.

Reviewer-generated input MUST provide the semantic fields needed to compute issue identity: `issue_type`, `affected_sections`, `invariant_violated`, and `claim`. Reviewer-generated `issue_id`, `issue_fingerprint`, and `normalized_severity` are treated as input placeholders. The Orchestrator MUST recompute and inject canonical values before persisted artifact validation.

Normalization for fingerprint fields MUST use the canonical scalar and array normalization rules from the artifact/content normalization spec.

Field-specific ordering rules:
- `affected_sections` MUST contain canonical section IDs and MUST be sorted lexicographically before issue fingerprint hashing.
- If the order of affected sections is part of the claim, that order MUST be stated in `claim`; the fingerprint still uses sorted `affected_sections`.
- `participating_issue_fingerprints` MUST be sorted lexicographically before conflict fingerprint hashing.
- Null semantic fields MUST serialize using the canonical null scalar representation before hashing.

Canonical array serialization for fingerprint inputs:
- normalize each array element using the string normalization rules above
- preserve or sort element order according to the field-specific ordering rule
- join normalized elements with a single LF character
- use the resulting string as the `normalized(array_field)` hash input

Empty arrays serialize to the empty string.

Each feedback item represents exactly one issue. If a reviewer finds multiple issues in one passage, it MUST emit multiple feedback items and may reuse the same `affected_sections` values.

---

## OSCILLATION DETECTION (FULL DEFINITION)

Oscillation detection has two layers:

1. Draft-level mechanical detection
2. Feedback-level Phase 2 detection

Draft-level detection is deterministic but limited. It detects exact cycles and exact mechanical churn in normalized drafts. It MUST NOT claim that two differently worded feedback items are the same concern.

Feedback-level detection is Phase 2 only. It uses Orchestrator-canonicalized `oscillation_key` fields derived from reviewer-proposed classification.

Each round computes:

1. draft_hash:
   SHA256 of full normalized draft_after.md

2. semantic_change_hash:
   SHA256 of normalized section-level diff between draft_before and draft_after

3. mechanical_change_keys:
   one polarity-neutral key per changed section, derived from normalized section id and unordered before/after content hashes

Explicit order-insensitive marker:

```text
[ORDER_INSENSITIVE_LIST]
- item B
- item A
[/ORDER_INSENSITIVE_LIST]
```

Only lists inside this marker may be sorted during normalization.

`[ORDER_INSENSITIVE_LIST]` and `[/ORDER_INSENSITIVE_LIST]` are source-control markers, not standard Markdown. Rendered Markdown viewers will display them literally.

Oscillation rules:

- Cycle:
  draft_hash repeats -> cycle detected

- Mechanical draft churn:
  same `mechanical_change_key` appears with opposing exact add/remove polarity across rounds

- Feedback flip-flop (Phase 2 only):
  same `oscillation_opposition_key` appears across rounds with opposing directions:
  - `add` after `remove`
  - `remove` after `add`
  - `constrain` after `relax`
  - `relax` after `constrain`

- Feedback churn (Phase 2 only):
  same `oscillation_opposition_key` appears cumulatively 3 times in Phase 2 with `modify` or `clarify` and without intervening resolution

Intervening resolution for feedback churn is computable from artifacts.

For an `oscillation_opposition_key`, an intervening resolution occurs between Phase 2 round R and the next Phase 2 review when:
- `editor_summary.json` for round R includes a `feedback_id` in `accepted_feedback_ids` or `modified_feedback_ids` whose matching item in round R `reviewer_feedback.json` has the tracked `oscillation_opposition_key`, and
- the corresponding issue is absent from `unresolved_issues.json` at the start of the next Phase 2 review.

The Orchestrator MUST reset the feedback churn counter for that `oscillation_opposition_key` to zero when intervening resolution occurs.

A round in which the opposition key does not appear is not, by itself, an intervening resolution.

- Feedback re-addition (Phase 2 only):
  same oscillation concern is added, removed, and then re-added by fingerprint history

Outputs:

/rounds/oscillation_report.json

Fields:
- detected: true|false
- type: cycle | mechanical_churn | feedback_flip_flop | feedback_churn | feedback_re_addition
- affected_sections
- suspected_feedback_ids
- oscillation_fingerprints
- oscillation_opposition_keys
- recommendation:
  - freeze_prior_decision
  - escalate_conflict
  - continue_once
  - stop_iteration

Recommendation selection is deterministic:
- cycle => stop_iteration
- mechanical_churn involving exact draft add/remove reversal => freeze_prior_decision
- feedback_flip_flop involving any blocker or major issue => escalate_conflict
- feedback_flip_flop involving only minor or nit issues => freeze_prior_decision
- first feedback_re_addition => continue_once
- repeated feedback_re_addition of the same oscillation fingerprint => stop_iteration
- feedback_churn involving `modify` or `clarify` for 3 cumulative Phase 2 appearances of the same opposition key without intervening resolution => escalate_conflict

Issues with `normalized_severity = nit`, including all-null severity-component cases, are treated as nit for oscillation recommendation.

If Phase 2 feedback lacks a valid reviewer-proposed `oscillation_key`, or if the proposed `section_id` is not in the canonical section index, the reviewer artifact is invalid and MUST be rejected before oscillation detection runs.

`escalate_conflict` from feedback churn produces `conflict_report.json` tagged for manual review. It halts only if the resulting conflict is blocker-level under the conflict escalation rules.

If recommendation = stop_iteration, terminal_state = HALTED_OSCILLATION.

---

## CONFLICT MODEL

Conflict types:

- architectural_conflict
- prior_decision_conflict
- profile_conflict
- rubric_conflict
- ambiguous_feedback
- out_of_scope_feedback

Conflict severity:

```text
conflict_severity = max(normalized_severity of participating issues)
```

A blocker-level conflict is any conflict where `conflict_severity = blocker`.

Conflict creation authority:
- the Orchestrator is the authority that creates and persists conflicts
- the Editor may request conflict creation by listing conflict IDs in `created_conflict_ids`
- every Editor-requested conflict MUST be derivable from declined feedback, mutually incompatible accepted feedback, an oscillation recommendation of `escalate_conflict`, or a prior decision contradiction documented in current artifacts
- the Orchestrator MUST validate each requested conflict against the conflict identity rules before tracking it
- invalid or under-specified Editor-requested conflicts MUST be ignored for escalation and recorded as a validation warning unless they also make `editor_summary.json` schema-invalid

The Orchestrator MUST persist tracked conflict state across rounds in `/rounds/conflict_state.json` after every round that detects, updates, or clears a conflict. `conflict_report.json` remains the halt/escalation artifact and MUST be produced when escalation is reached.

`conflict_state.json` MUST contain:

```yaml
schema_version: conflict_state_v1
generated_at: string
round_number: integer
conflicts:
  - conflict_id: string
    conflict_fingerprint: string
    conflict_type: string
    conflict_severity: blocker | major | minor | nit
    state: present | absent | resolved
    first_seen_round: integer
    last_seen_round: integer
    consecutive_present_rounds: integer
    total_present_rounds: integer
    participating_issue_fingerprints: [string]
    latest_issue_ids: [string]
    latest_conflict_claim: string
```

A newly detected conflict counts as `present` in its creation round. If the same `conflict_fingerprint` is not detected in a later round, `consecutive_present_rounds` resets to zero while `total_present_rounds`, `first_seen_round`, and prior identity remain preserved. Resume MUST reconstruct conflict escalation state from `conflict_state.json` when present, or deterministically from prior round artifacts when the state artifact is absent.

The Editor's conflict-resolution authority is limited to recommending resolution through accepted, modified, or declined feedback decisions. The Orchestrator owns conflict threshold counting, escalation, terminal-state selection, and halt artifact production.

---

## EDITOR DECLINE TAXONOMY

Editor may decline feedback only with one of:

- architectural_conflict
- contradicts_source_authority
- out_of_scope
- factually_incorrect
- already_satisfied
- ambiguous
- superseded_by_better_fix
- deferred_to_later_round
- nit_declined

deferred_to_later_round requires:
- target_profile
- target_round_or_phase
- rationale

When persisted in `editor_summary.json`, declined feedback with `decline_reason = deferred_to_later_round` MUST set `target_profile` and `target_round_or_phase` to non-null strings. Null values are invalid for this decline reason.

Declined feedback MUST be persisted in editor_summary.json.

Decline taxonomy is separate from conflict type.
Some declined feedback may create a conflict; some may not.

---

## CONFLICT ESCALATION

Threshold:
- same conflict persists for 2 consecutive rounds OR
- same conflict appears 3 times non-consecutively

Escalation produces:
/rounds/conflict_report.json

Blocker-level conflicts trigger halt.

Same conflict is determined by `conflict_fingerprint`.

---
