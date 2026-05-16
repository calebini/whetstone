# Artifacts Validation And Telemetry Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: artifacts_validation_and_telemetry_spec
target_spec_role: leaf_spec
-->

## ARTIFACT SCHEMAS (MINIMUM REQUIRED FIELDS)

`reviewer_feedback.json` MUST contain:

```yaml
round_number: integer
profile: string
reviewer:
  name: string
  version: string
  model: string
draft_hash: string
feedback:
  - feedback_id: string
    issue_id: string            # persisted canonical value; reviewer input may provide a placeholder
    issue_fingerprint: string   # persisted canonical value; reviewer input may provide a placeholder
    issue_type: string
    affected_sections: [string]
    baseline_severity: blocker | major | minor | nit | null
    authority_impact: blocker | major | minor | nit | null
    determinism_impact: blocker | major | minor | nit | null
    rubric_impact: blocker | major | minor | nit | null
    normalized_severity: blocker | major | minor | nit  # persisted canonical value recomputed by Orchestrator
    invariant_violated: string | null
    claim: string
    evidence: string
    recommended_change: string
    in_scope: boolean
    severity_rationale: string | null
    oscillation_key: null | object
```

`in_scope = true` means the feedback concerns the current draft, configured target, active review profile, baseline review invariants, or required artifacts. `in_scope = false` means the reviewer detected an issue outside those boundaries. Out-of-scope feedback MAY be persisted for auditability, but it MUST NOT block profile cleanliness, draft acceptance, convergence, or halt decisions unless the Editor or Orchestrator converts it into an in-scope issue with an explicit rationale.

`severity_rationale` MUST be non-null when `baseline_severity = null`; otherwise it MAY be null.

`oscillation_key` MAY be null in Phase 1.

Phase 2 reviewer input MUST use the phase-specific reviewer input schema. In Phase 2 reviewer input, `oscillation_key` MUST contain exactly the reviewer-proposed classification fields:
- `section_id`
- `concern_type`
- `direction`
- `scope`

Phase 2 reviewer input MUST NOT include `fingerprint` or `opposition_key`.

Persisted Phase 2 `reviewer_feedback.json` MUST use the canonical persisted schema. In persisted Phase 2 artifacts, `oscillation_key` MUST contain the reviewer-proposed fields plus the Orchestrator-computed `fingerprint` and `opposition_key`.

`editor_summary.json` MUST contain:

```yaml
round_number: integer
draft_before_hash: string
draft_after_hash: string   # persisted artifact; may be null in editor-generated live input before Orchestrator canonicalization
accepted_feedback_ids: [string]
modified_feedback_ids: [string]
declined_feedback:
  - feedback_id: string
    decline_reason: string
    rationale: string
    target_profile: string | null
    target_round_or_phase: string | null
created_conflict_ids: [string]
resolved_issue_ids: [string]
unresolved_issue_ids: [string]
draft_after_content: string | null   # required in editor-generated applied revision input; optional in persisted summary
```

`accepted_feedback_ids` are feedback items accepted as written.

`modified_feedback_ids` are feedback items accepted in substance but implemented with materially different wording, structure, or placement than the reviewer recommended.

When an applied live round expects the Editor to generate a revised draft, the Editor response MUST include `draft_after_content` containing the complete revised draft text. The Editor response MAY set `draft_after_hash` to null or an implementation-specific placeholder in this generated-revision input. The Orchestrator MUST treat `draft_after_content` as the input authority for the revised draft, compute `draft_after_hash` from that content, inject the computed hash before persisted artifact validation, write the content to `draft_after.md`, and only then mutate `spec.md`.

Persisted `editor_summary.json` MUST contain the Orchestrator-computed `draft_after_hash`. The Editor is not authoritative for derived hashes in editor-generated applied revisions.

If a live Reviewer returns valid feedback with `feedback = []` and no explicit external `draft_after.md` fixture is being evaluated, the Orchestrator SHOULD NOT invoke the Editor. It MUST instead persist a deterministic no-op `editor_summary.json` with empty accepted/modified/declined/resolved/unresolved arrays, `draft_before_hash = draft_after_hash`, and, for applied rounds, `draft_after_content` equal to the unchanged draft. This no-op summary is Orchestrator-owned and has the same acceptance semantics as an Editor-confirmed no-op.

The Orchestrator MUST reject destructive Editor-generated draft replacements before writing `draft_after.md` or mutating `spec.md`. At minimum, when `draft_before.md` is non-empty, the Orchestrator MUST reject:
- empty or whitespace-only `draft_after_content`
- known Editor blocked/error placeholder text in `draft_after_content`
- near-empty replacements that are destructively smaller than a large non-empty draft
- forbidden text-corruption characters in `draft_after_content`

Forbidden text-corruption characters are Unicode category `Cc` control characters except LF, CR, and TAB, plus `U+FFFD` replacement characters. Such rejection is an artifact validation failure, not an accepted draft mutation. The invalid attempt MUST be persisted and the previous valid draft MUST remain authoritative.

Apply-back preflight MUST run the same text hygiene validation against the final draft before writing to the source spec. A final draft that violates text hygiene MUST NOT be applied, even if the run predates the validation guard or was manually edited after convergence.

When `draft_after.md` is supplied by an external fixture or explicit Orchestrator input, `draft_after_content` MAY be null or omitted.

When a `declined_feedback` item has `decline_reason = deferred_to_later_round`, `target_profile` and `target_round_or_phase` MUST be non-null strings. For every other decline reason, they MAY be null.

`decision_points.json` MUST contain:

```yaml
round_number: integer
draft_hash: string
decision_points:
  - decision_id: string
    round_number: integer
    profile: string
    source_feedback_ids: [string]
    affected_sections: [string]
    decision_type: tighten_requirement | relax_requirement | choose_policy | define_default | resolve_conflict | add_operational_requirement | scope_change
    question: string
    options_considered:
      - option_id: string
        label: string
        description: string
    editor_selected_option_id: string | null
    editor_rationale: string
    risk_if_wrong: string
    decision_status: editor_applied_decision | operator_review_recommended | operator_required_decision | record_only_hardening | deferred_scope_decision
    requires_human_decision: boolean
    orchestrator_action: record_only | present_at_end | pause_for_input
```

Decision points capture consequential choices made or proposed during revision. They are separate from issue identity and from conflict escalation. A decision point does not imply the Editor made an invalid change; it means the change carries product, policy, scope, authority, or operational consequences that should be visible outside the model turn.

`decision_status` disambiguates what kind of decision point was captured:

- `editor_applied_decision`: the Editor already encoded the choice in the draft and no special operator review was requested.
- `operator_review_recommended`: the Editor already encoded the choice in the draft, but the choice should be visible to the operator before apply-back, Phase 2, or implementation.
- `operator_required_decision`: the Orchestrator paused in intervention mode and external input is required before continuing.
- `record_only_hardening`: the change is routine precision hardening captured for audit, not a live owner decision.
- `deferred_scope_decision`: the decision concerns behavior that should remain deferred unless an operator explicitly pulls it into scope.

In `end_of_cycle` mode, `operator_review_recommended` is advisory and MUST NOT halt the run by itself. In `intervention` mode, `operator_required_decision` maps to `orchestrator_action = pause_for_input` and MAY halt through the existing `PAUSED_DECISION` path.

If an Editor change promotes a scope-contract `could`, `deferred`, or `out_of_scope` surface into normative `MUST` behavior, the Orchestrator SHOULD classify the resulting decision point as `deferred_scope_decision`. In `end_of_cycle` mode this is surfaced for operator review and MUST NOT halt the run by itself. In `intervention` mode it MAY pause only through the existing `PAUSED_DECISION` path.

The Editor MUST create a decision point when accepting or modifying feedback causes any of:
- changes normative strength among `MUST`, `SHOULD`, `MAY`, `MUST NOT`, or equivalent language
- adds, removes, narrows, or broadens an authority boundary
- chooses one policy among multiple viable policies
- defines a default behavior where the source spec did not define one
- adds, removes, or changes an enum, status value, reason code, error code, terminal state, or externally visible artifact field
- changes scope by moving behavior into or out of the component, role, phase, adapter, or Orchestrator
- resolves a conflict by preferring one architectural direction over another
- introduces an operational requirement such as logging, retrieval, receipt emission, retry behavior, timeout behavior, or observability behavior

The Orchestrator MUST validate every decision point for schema shape and source feedback references. The Orchestrator MAY also compute additional decision points from draft diffs when deterministic triggers are detectable, such as normative keyword strength changes or new enum-like lists.

Decision point identifiers are deterministic aliases:

```text
decision_fingerprint = SHA256(
  normalized(decision_type) + "\n" +
  normalized(affected_sections) + "\n" +
  normalized(question)
)

decision_id = "dec_" + first_16_hex_chars(decision_fingerprint)
```

`decision_points.mode = end_of_cycle`:
- The Orchestrator MUST persist per-round `decision_points.json`.
- The Orchestrator MUST aggregate per-round decision points into `/rounds/decision_register.json` and `/rounds/decision_register.md` at terminal state.
- Terminal decision register and summary artifacts MUST be produced even when no decision points were captured, with `decision_points = []` and `unresolved_human_decision_count = 0`.
- Decision points with `requires_human_decision = true` MUST NOT block Phase 1 stability, Phase 2 progression, or convergence solely by existing.
- Terminal output MUST disclose whether unresolved human decision points exist.

`decision_points.mode = intervention`:
- If a decision point has `orchestrator_action = pause_for_input`, the Orchestrator MUST produce `/rounds/decision_intervention_request.json`, set terminal_state to `PAUSED_DECISION`, and halt before scheduling the next review round.
- A decision point MUST use `orchestrator_action = pause_for_input` when `requires_human_decision = true` and any configured intervention threshold is met.
- The system MUST NOT auto-apply the selected option after `PAUSED_DECISION`; external input is required.

Decision point thresholds MUST be computable from persisted artifacts or deterministic draft analysis. The default threshold set is:
- source feedback normalized severity is `blocker` or `major`
- draft diff changes normative keyword strength
- draft diff adds or removes authority-boundary language
- draft diff adds or removes public enum/status/error-code values
- draft diff changes role, phase, adapter, or Orchestrator scope

Decision point records MUST NOT replace reviewer feedback, editor summaries, conflict reports, or convergence declarations. They are an operator-facing release valve for consequential choices that would otherwise be hidden inside `accepted_feedback_ids` or `modified_feedback_ids`.

`operator_decision_checkpoint.json` is a per-round, nonblocking artifact derived from decision points and unresolved blocker/major Reviewer findings. It frames likely owner-level policy, scope, authority, validation, failure-handling, or reporting choices as operator-readable multiple-choice checkpoint cards.

This artifact is advisory in version `0.57`. It MUST NOT pause execution, alter scheduler state, mark a profile clean, resolve feedback, mutate the draft, or satisfy convergence by itself. Its runtime effect is explicitly `none`.

`operator_decision_checkpoint.json` MUST contain:

```yaml
generated_at: string
round_number: integer
profile: string
draft_hash: string
mode: artifact_only
runtime_effect: none
default_action: continue_without_operator_input
checkpoint_count: integer
checkpoints:
  - checkpoint_id: string
    round_number: integer
    profile: string
    source_type: decision_point | unresolved_issue
    source_ids: [string]
    severity: blocker | major | minor | nit | null
    trigger_reason: operator_policy_choice | deferable_scope_boundary | authority_boundary | validation_policy | failure_or_reporting_policy
    affected_sections: [string]
    question: string
    options:
      - option_id: string
        label: string
        description: string
        recommended: boolean
    recommended_option_id: string | null
    evidence_lines: [string]
    risk_if_skipped: string
    status: candidate
    runtime_effect: none
```

The Orchestrator SHOULD write `operator_decision_checkpoint.json` for every live round, even when `checkpoints = []`, so downstream operators can distinguish "no checkpoint candidates" from "artifact not produced."

Checkpoint candidates derived from unresolved Reviewer findings SHOULD be limited to in-scope blocker/major issues whose text indicates an operator-level choice, including scope boundaries, authority precedence, validation policy, failure/reporting behavior, fallback behavior, or product policy. Routine local precision gaps SHOULD remain Editor-fixable and SHOULD NOT create checkpoint cards.

Checkpoint candidates derived from `decision_points.json` SHOULD include decision points with `decision_status` in:

- `operator_review_recommended`
- `operator_required_decision`
- `deferred_scope_decision`

The `default_action = continue_without_operator_input` means the current runtime continues exactly as it would have without the checkpoint artifact. Future interactive or auto-guided modes MAY consume the same checkpoint shape and persist separate response artifacts, but version `0.57` MUST NOT imply such response handling exists.

At terminal state, the Orchestrator MUST aggregate per-round checkpoint artifacts into:

- `/rounds/operator_decision_checkpoint_summary.json`
- `/rounds/operator_decision_checkpoint_summary.md`

The checkpoint summary is a deterministic operator review aid. It MUST NOT pause execution, alter scheduler state, resolve feedback, mutate the draft, or satisfy convergence.

`operator_decision_checkpoint_summary.json` MUST contain:

```yaml
generated_at: string
terminal_state: string
source_glob: rounds/round-*/operator_decision_checkpoint.json
summary_method: mechanical_checkpoint_v1
checkpoint_count: integer
rounds_with_checkpoints: [integer]
trigger_reason_counts: object
source_type_counts: object
clusters:
  by_trigger_reason: [checkpoint_cluster]
  by_section: [checkpoint_cluster]
  by_source_type: [checkpoint_cluster]
recommended_operator_review: [checkpoint_summary_card]
```

Checkpoint summary clusters MUST be mechanical:

- `by_trigger_reason` groups by `trigger_reason`.
- `by_section` groups by the first affected section on each checkpoint card.
- `by_source_type` groups by `decision_point` vs `unresolved_issue`.
- `recommended_operator_review` MUST contain at most five checkpoint cards sorted by deterministic priority: authority boundary, deferred scope boundary, failure/reporting policy, validation policy, then general operator policy choice; ties sort by severity, round number, then checkpoint ID.

The human-readable Markdown summary MUST expose the same counts, recommended review cards, and clusters without adding semantic interpretation beyond persisted checkpoint fields.

`decision_register.json` MUST contain:

```yaml
generated_at: string
mode: end_of_cycle | intervention
terminal_state: string
decision_points: [decision_point]
decision_status_counts: object
unresolved_human_decision_count: integer
```

## ARTIFACT VALIDATION POLICY

The Orchestrator MUST validate every client-produced artifact before using it for scheduling, mutation, acceptance, convergence, oscillation detection, or conflict escalation.

Validation order:
1. parse the client response as a single JSON object
2. validate contextual fields such as `round_number`, `profile`, `draft_hash`, `draft_before_hash`, and `draft_after_hash`
3. reject reviewer self-reported process/context-loading failure artifacts before semantic scheduling
4. validate the object against the phase-appropriate artifact schema
5. apply Orchestrator-owned canonicalization steps such as Phase 2 `oscillation_key` fingerprint and opposition-key computation
6. validate the canonicalized artifact against the persisted artifact schema

Reviewer feedback that declares the review could not be performed because context files were not read, context was unavailable, or another client-process prerequisite failed MUST be treated as an invalid reviewer artifact, not semantic feedback. The Orchestrator MUST retry it under the artifact validation policy. If the retry also returns process/context-loading failure feedback, the run MUST halt with `HALTED_ARTIFACT_INVALID`. Such process failure artifacts MUST NOT dirty profile cleanliness, create issue/conflict/oscillation identity, consume a successful review result, or be sent to the Editor as feedback to apply or decline.

If validation fails, the Orchestrator MUST NOT persist the invalid artifact under its canonical artifact filename. It MAY persist the raw response and validation errors under diagnostic filenames in the current round directory.

Validation retry policy:
- each client artifact gets at most 1 validation retry
- the retry MUST use the same round number, same draft hash, same profile, same phase, same client role, and same source prompt context
- the retry prompt MAY include the validation errors and the required schema constraints
- the original prompt attempt and retry prompt attempt MUST each be persisted under `prompt_snapshots/`
- retry prompt snapshots MUST include the validation errors that caused the retry
- validation attempts do not advance the profile schedule and do not count as accepted review cycles
- the round budget is consumed only after a reviewer artifact validates successfully

If the retry validates, the Orchestrator continues with the validated artifact.

If the retry fails, the Orchestrator MUST halt with `HALTED_ARTIFACT_INVALID` and produce `/rounds/artifact_validation_error.json`.

If a client invocation times out before returning an artifact, the Orchestrator MUST NOT retry the same prompt automatically. It MUST halt with `HALTED_CLIENT_TIMEOUT`, produce `/rounds/artifact_validation_error.json`, set `failure_type = client_timeout`, and produce the phase-appropriate companion failure report. Timeout halts are distinct from artifact validation failures because no candidate artifact was available to validate.

When `HALTED_ARTIFACT_INVALID` occurs, `last_valid_draft_path` MUST point to the most recent draft snapshot the Orchestrator can safely treat as validated. If reviewer artifact validation fails before any validated review exists for the round, this MUST be the current round `draft_before.md`. If editor artifact validation fails after a validated reviewer artifact, this MAY be the current round `draft_after.md` only when that file is an Orchestrator-owned snapshot and not an unvalidated client artifact.

When `HALTED_CLIENT_TIMEOUT` occurs, `last_valid_draft_path` follows the same rule as artifact validation failures. A timed-out Reviewer points to `draft_before.md`. A timed-out Editor after validated reviewer feedback MAY point to the Orchestrator-owned `draft_after.md` snapshot for the round.

For Phase 2 reviewer feedback, an invalid or missing reviewer-proposed `oscillation_key`, an invalid enum value, or a `section_id` that does not resolve to exactly one canonical section ID is an artifact validation failure under this policy.

---

## CLIENT TELEMETRY

The Orchestrator MUST persist per-attempt client telemetry for every live client invocation, including successful attempts, invalid artifact attempts, timeout attempts, and nonzero-exit attempts whenever process metadata is available.

Telemetry artifacts MUST be written under:

```text
/rounds/round-N/client_telemetry/{client_role}-{artifact_name}-attempt-{attempt_number}.json
```

Client telemetry is audit and observability data. It MUST NOT be used for convergence, acceptance, severity normalization, artifact validation, conflict escalation, oscillation detection, draft hashing, or replay authority.

`client_telemetry` artifacts MUST contain:

```yaml
generated_at: string
round_number: integer
phase: phase_1 | phase_2
profile: string
client_role: reviewer | editor
artifact_name: string
attempt_number: integer
client:
  name: string
  command: string
  configured_version: string
  observed_version: string | null
  model: string
started_at: string
finished_at: string | null
duration_ms: integer | null
duration_api_ms: integer | null
exit_code: integer | null
timed_out: boolean
session_id: string | null
stop_reason: string | null
terminal_reason: string | null
total_cost_usd: number | null
usage:
  input_tokens: integer | null
  output_tokens: integer | null
  cache_creation_input_tokens: integer | null
  cache_read_input_tokens: integer | null
  total_tokens: integer | null
  provider_raw: object | null
model_usage: object | null
raw_envelope_path: string | null
stderr_path: string | null
telemetry_source: claude_json_envelope | codex_stdout | codex_json_envelope | process_metadata | unavailable
```

`usage.total_tokens` MUST be computed by the Orchestrator when token components are available:

```text
total_tokens =
  input_tokens +
  output_tokens +
  cache_creation_input_tokens +
  cache_read_input_tokens
```

Null token components MUST be treated as zero for this computed total only. If every token component is null, `usage.total_tokens` MUST be null.

When a client exposes a raw JSON envelope with usage metadata, such as Claude Code `--output-format json`, the Orchestrator MUST persist the raw envelope or a lossless redacted copy and set `raw_envelope_path`.

When a client exposes usage only in stdout/stderr text, such as a human-readable `tokens used` line, the Orchestrator MAY parse the available fields and MUST preserve the raw stdout/stderr text or a redacted copy if it is needed to explain the parsed usage.

When no usage data is available, telemetry MUST still be emitted with timing, exit, and configured-client metadata when available, and `telemetry_source = unavailable` or `process_metadata`.

Telemetry persistence MUST be best-effort but non-silent:

- Failure to persist telemetry MUST NOT by itself invalidate a schema-valid reviewer/editor artifact.
- Telemetry persistence failure MUST be recorded as a validation warning or run warning in the round packet.
- Missing telemetry for a live invocation MUST be detectable by artifact validation or status tooling.

Prompt text MUST NOT be duplicated into telemetry artifacts unless the prompt snapshot path is referenced. The attempt-level `prompt_snapshots/` artifact remains the authoritative prompt audit artifact.

---

## CONTENT NORMALIZATION AND HASHING

Draft hash normalization:
- normalize line endings to LF
- remove trailing spaces and tabs from each line
- preserve all non-whitespace content
- preserve all markdown heading text and order
- preserve frontmatter if present
- ensure exactly one trailing newline

`draft_hash` is SHA256 of the normalized full draft.

If a round requires Orchestrator-owned version stamping, stamping MUST occur before writing the canonical `draft_after.md`, before mutating `spec.md`, and before computing the persisted `draft_after_hash`.

Rubric hash normalization:
- use the same normalization rules as `draft_hash`
- compute the hash from the full normalized `convergence_rubric.md`

`rubric_content_hash` is SHA256 of the normalized full rubric.

Semantic change hash normalization:
- compute section-level diff between normalized `draft_before.md` and normalized `draft_after.md`
- strip whitespace-only differences
- preserve all section headers
- preserve all ordered list order
- preserve unordered list order by default
- normalize unordered list order only when a list is explicitly marked order-insensitive

Semantic change polarity is:
- `add` when normalized content exists only in `draft_after.md`
- `remove` when normalized content exists only in `draft_before.md`
- `modify` when both sides exist and differ

`semantic_change_hash` is SHA256 of normalized section id, polarity, before content hash, and after content hash.

`mechanical_change_key` is a polarity-neutral key used only for draft-level mechanical churn:

```text
mechanical_change_key = SHA256(
  normalized(section_id) + "\n" +
  sorted(before_content_hash_or_absent, after_content_hash_or_absent)
)
```

`mechanical_change_key` deliberately excludes polarity so an exact add/remove reversal can be compared mechanically. Polarity remains a separate field on the semantic change record.

---
