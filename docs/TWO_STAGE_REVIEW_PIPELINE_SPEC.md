# Whetstone Two-Stage Review Pipeline Spec 1.2

Status: exploratory subsystem spec

## Reading Guide

This spec defines an optional review pipeline that separates content critique from canonical artifact classification. It is intended to reduce pressure on a single reviewer model by letting one stage optimize for finding useful issues and another stage optimize for Whetstone's strict schemas, enums, anchors, and validation behavior.

## Purpose

The current direct reviewer role performs two different cognitive jobs:

- content review: understand the draft, identify issues, explain evidence, and recommend corrections
- structured classification: produce schema-valid Whetstone feedback with canonical severities, issue types, anchors, oscillation keys, rubric gaps, and artifact fields

The two-stage review pipeline splits those jobs into separate stages:

- Critic: produces high-quality findings in a lower-pressure review format.
- Canonicalizer: converts critic findings into Whetstone canonical reviewer feedback.

The goal is to preserve Whetstone's deterministic orchestration and artifact validation while allowing different models or clients to be assigned to the stage where they are strongest.

## Non-Goals

This subsystem does not replace the Editor role.

This subsystem does not make model-generated hashes authoritative. The Orchestrator still computes hashes, fingerprints, section indexes, normalized severities, and any other computable primitive.

This subsystem does not allow the Canonicalizer to silently invent new findings. New substantive critique belongs in the Critic stage.

This subsystem does not make telemetry, raw notes, or critic prose authoritative for convergence.

## Pipeline Modes

The Orchestrator MUST support the existing direct review path:

```yaml
review_pipeline:
  mode: direct
```

The optional two-stage path is:

```yaml
review_pipeline:
  mode: critic_then_canonicalizer
```

In `direct` mode, the configured reviewer client produces reviewer input that is canonicalized and persisted as `reviewer_feedback.json`.

In `critic_then_canonicalizer` mode, the configured Critic client first produces `critic_findings.json`; then the configured Canonicalizer client transforms those findings into reviewer input that is canonicalized and persisted as `reviewer_feedback.json`.

## Role Model

### Critic

The Critic reviews the draft and rubric context for substance.

The Critic SHOULD optimize for:

- finding blockers, major issues, and high-signal minor issues
- explaining why each finding matters
- citing observable evidence from the draft, declaration, rubric, or supplied artifacts
- recommending the minimum correction needed
- avoiding premature classification when uncertain

The Critic MAY produce looser prose than the persisted Whetstone reviewer schema, but it MUST still produce a machine-readable artifact.

### Canonicalizer

The Canonicalizer maps Critic findings into Whetstone reviewer input.

The Canonicalizer SHOULD optimize for:

- controlled enum selection
- section anchor selection
- severity component mapping
- Phase 2 oscillation key classification
- rubric gap mapping
- preserving traceability from critic finding to persisted feedback item

The Canonicalizer MUST NOT add a new substantive issue unless it marks the item as a canonicalization warning and the Orchestrator treats the artifact as invalid by default.

The Canonicalizer MAY split, merge, or drop Critic findings only under the explicit transformation rules in this spec.

### Orchestrator

The Orchestrator owns:

- state transitions
- prompt snapshots
- client telemetry
- artifact validation retry and halt behavior
- section index generation
- issue fingerprint computation
- severity normalization
- oscillation fingerprint and opposition-key computation
- artifact content hash computation (including `canonicalizer_summary.json.source_critic_findings_hash`)
- final persisted `reviewer_feedback.json`

The Orchestrator MUST treat Critic and Canonicalizer output as model-proposed input, not as authoritative persisted state until canonicalization and validation succeed.

## Configuration

Example:

```yaml
review_pipeline:
  mode: critic_then_canonicalizer
  critic:
    name: claude-code
    command: claude
    version: "1.0.47"
    model: "claude-sonnet-4-6"
  canonicalizer:
    name: codex
    command: codex
    version: "0.128.0"
    model: "gpt-5.5"
```

If `review_pipeline.mode = direct`, `clients.reviewer` remains the reviewer source of truth.

If `review_pipeline.mode = critic_then_canonicalizer`, the Orchestrator MUST require concrete `critic` and `canonicalizer` client configuration. Missing version or model fields MUST fail preflight with `CONFIG_INVALID`.

## Round Artifacts

In two-stage mode, each round MUST persist a round directory at:

```text
/rounds/round-N/
```

Within the directory, the Orchestrator MUST persist prompt snapshots and client telemetry for every Critic and Canonicalizer attempt.

The Orchestrator MUST persist stage artifacts only when the specific artifact validates and is accepted for persistence.

Artifact acceptance for persistence is per-artifact, not per-round. A round MAY persist some stage artifacts even if the round later halts with `HALTED_ARTIFACT_INVALID`.

In particular:

- if `critic_findings.json` validates, it SHOULD be accepted for persistence even if a later Canonicalizer attempt fails.
- if a Canonicalizer attempt emits a schema-valid `canonicalizer_summary.json`, it SHOULD be accepted for persistence for that Canonicalizer attempt even if the corresponding model-proposed reviewer feedback fails validation or canonicalization.

### Canonicalizer Summary Identity And Paths

`canonicalizer_summary.json` is an attempt-scoped audit artifact.

- For each Canonicalizer attempt `M` whose summary validates and is accepted for persistence, the Orchestrator MUST persist it at:

```text
/rounds/round-N/canonicalizer_summary-attempt-M.json
```

- The Orchestrator MUST NOT overwrite a previously persisted `canonicalizer_summary-attempt-*.json`.

- On a successful round completion, the Orchestrator MAY also persist a convenience copy at:

```text
/rounds/round-N/canonicalizer_summary.json
```

If the convenience copy is persisted, it MUST be byte-identical to the accepted `canonicalizer_summary-attempt-M.json` for the Canonicalizer attempt that produced the persisted `reviewer_feedback.json`.

- If the round halts with `HALTED_ARTIFACT_INVALID`, the Orchestrator MUST NOT create or update `/rounds/round-N/canonicalizer_summary.json` as a “latest” pointer. In halt paths, only the attempt-scoped summaries are authoritative.

On a successful round (both stages validate and the round completes), the round directory MUST contain:

```text
/rounds/round-N/
  critic_findings.json
  canonicalizer_summary-attempt-M.json
  reviewer_feedback.json
  prompt_snapshots/
    critic-critic_findings.json-attempt-M.json
    canonicalizer-reviewer_feedback.json-attempt-M.json
  client_telemetry/
    critic-critic_findings.json-attempt-M.json
    canonicalizer-reviewer_feedback.json-attempt-M.json
```

If the convenience copy is used, the directory ALSO contains:

```text
/rounds/round-N/
  canonicalizer_summary.json
```

If the round halts with `HALTED_ARTIFACT_INVALID`, the round directory MUST contain:

- `round_failure_report.json`
- all prompt snapshots and telemetry already written for attempts in the round
- all successfully validated-and-accepted-for-persistence stage artifacts written prior to the halt (for example, a valid `critic_findings.json` from an earlier stage, or one or more valid `canonicalizer_summary-attempt-M.json` files from failed Canonicalizer attempts)

The Orchestrator MUST NOT delete or overwrite previously persisted artifacts when halting.

`reviewer_feedback.json` remains the only reviewer artifact consumed by existing unresolved issue evaluation, conflict tracking, oscillation detection, Editor prompting, and convergence evaluation.

`critic_findings.json` and `canonicalizer_summary-*.json` are audit artifacts. They are not convergence-authoritative.

## round_failure_report.json

`round_failure_report.json` MUST be persisted if and only if the Orchestrator halts the round with `HALTED_ARTIFACT_INVALID`.

`round_failure_report.json` MUST contain at least:

```yaml
round_number: integer
failed_stage: critic | canonicalizer
failure_reason: string
attempt_count: integer
last_prompt_snapshot_path: string
last_client_telemetry_path: string
```

`attempt_count` MUST be the number of attempts performed for `failed_stage` in the halted round.

`last_prompt_snapshot_path` and `last_client_telemetry_path` MUST be workspace-relative paths pointing to the last persisted attempt snapshot and telemetry file for `failed_stage`.

Additional fields MAY be present, but are non-authoritative.

## critic_findings.json

`critic_findings.json` MUST contain:

```yaml
round_number: integer
phase: phase_1 | phase_2
profile: string
critic:
  name: string
  version: string
  model: string
draft_hash: string
findings:
  - critic_finding_id: string
    affected_sections: string[]
    claim: string
    evidence: string
    why_it_matters: string
    recommended_change: string
    provisional_severity: blocker | major | minor | nit | null
    confidence: high | medium | low
    in_scope: boolean
    notes: string | null
```

`critic_finding_id` MUST be generated by the Critic.

`critic_finding_id` MUST be unique within a single `critic_findings.json` artifact.

`critic_finding_id` MUST follow this format:

- `cf_` prefix
- 1-based ordinal in the `findings` array

Example: `cf_1`, `cf_2`, `cf_3`.

Each Critic finding SHOULD describe one root concern. If one root concern affects multiple places, it SHOULD remain one finding with multiple `affected_sections`.

The Critic MAY use section titles or descriptive anchors in Phase 1. In Phase 2, the Critic SHOULD choose from the canonical section ID list when the prompt provides one, but failure to do so does not by itself invalidate the Critic artifact.

## canonicalizer_summary.json

`canonicalizer_summary.json` MUST contain:

```yaml
round_number: integer
phase: phase_1 | phase_2
profile: string
canonicalizer:
  name: string
  version: string
  model: string
draft_hash: string
source_critic_findings_hash: string
transformations:
  - critic_finding_ids: string[]
    canonicalizer_feedback_item_ids: string[]
    action: mapped | split | merged | dropped | warned
    rationale: string
warnings:
  - warning_id: string
    critic_finding_ids: string[]
    warning_type: invented_issue | insufficient_evidence | anchor_unresolved | duplicate_finding | out_of_scope | schema_repair
    message: string
```

`source_critic_findings_hash` MUST be computed by the Orchestrator.

`source_critic_findings_hash` MUST be the SHA-256 hex digest (lowercase, 64 chars) of the UTF-8 bytes of the persisted `critic_findings.json` file content.

The Orchestrator MUST compute the hash over the exact bytes it persists for `critic_findings.json`.

`canonicalizer_feedback_item_ids` are Canonicalizer-scoped identifiers for feedback items produced during the Canonicalizer attempt.

`canonicalizer_feedback_item_ids` MUST be generated by the Canonicalizer and MUST be unique within a single Canonicalizer attempt.

The Orchestrator MUST NOT require `canonicalizer_summary.json` to contain any Orchestrator-assigned identifier class.

The summary MUST explain every split, merge, drop, or warning. One-to-one mappings MAY use a short rationale.

`warning_id` MUST be generated by the Canonicalizer.

`warning_id` MUST be unique within a single `canonicalizer_summary.json` artifact.

`warning_id` MUST follow this format:

- `w_` prefix
- 1-based ordinal in the `warnings` array

Example: `w_1`, `w_2`, `w_3`.

### Transformation Validation Invariants

To make `canonicalizer_summary.json` acceptance deterministic, the Orchestrator MUST validate the following invariants (in addition to JSON schema validity) before accepting a summary for persistence:

- Coverage: every in-scope `critic_finding_id` present in the persisted `critic_findings.json` MUST appear in exactly one `canonicalizer_summary.json.transformations[*].critic_finding_ids` entry.

- Exclusivity: a `critic_finding_id` MUST NOT appear in multiple transformation entries.

- Action/ID consistency:
  - if `action` is `mapped`, `split`, or `merged`, then `canonicalizer_feedback_item_ids` MUST be a non-empty array.
  - if `action` is `dropped` or `warned`, then `canonicalizer_feedback_item_ids` MUST be an empty array.

- Warning linkage: if `action` is `warned`, then at least one `warnings[*]` entry MUST exist whose `critic_finding_ids` contains all `critic_finding_ids` listed in that `warned` transformation row.

Out-of-scope Critic findings MAY either:

- appear in `transformations` with `action: dropped` and an `out_of_scope` warning, or
- appear in `transformations` with `action: dropped` without a warning.

If an out-of-scope finding appears in `warnings`, it MUST still satisfy Coverage and Exclusivity via a single `transformations` entry.

## Transformation Rules

The Canonicalizer MAY map one Critic finding to one feedback item.

The Canonicalizer MAY split one Critic finding into multiple feedback items when the Critic finding contains multiple separable root concerns. Each split item MUST reference the source `critic_finding_id`.

The Canonicalizer MAY merge multiple Critic findings when they describe the same root concern. The merged feedback item MUST reference all source `critic_finding_ids`.

The Canonicalizer MAY drop a Critic finding only when one of the following is true:

- the finding is out of scope for the current profile
- the finding is a duplicate of another mapped finding
- the finding lacks evidence sufficient to classify
- the finding is already satisfied by the draft text

Dropped findings MUST appear in `canonicalizer_summary.json`.

The Canonicalizer MUST NOT add a feedback item with no source `critic_finding_id`. If it does, the Orchestrator MUST reject the canonicalizer artifact unless an explicit future configuration allows Canonicalizer-discovered findings.

## Reviewer Feedback Lineage

In two-stage mode, each Canonicalizer-produced reviewer feedback item (the model-proposed reviewer input prior to Orchestrator persistence) MUST include source lineage:

```yaml
source_critic_finding_ids: string[]
```

If the persisted `reviewer_feedback.json` schema includes `source_critic_finding_ids`, the Orchestrator MUST persist it unchanged.

If the persisted `reviewer_feedback.json` schema does not include `source_critic_finding_ids`, the Orchestrator MUST persist the mapping in `canonicalizer_summary.json`.

Lineage is required so an operator can trace:

```text
critic finding -> canonical feedback item -> editor decision -> unresolved issue
```

## Phase Behavior

### Phase 1

Two-stage review is useful in Phase 1 when a client is strong at critique but unreliable at strict schema output.

Phase 1 Canonicalizer output MUST satisfy the same persisted `reviewer_feedback.json` requirements as direct Phase 1 review.

Phase 1 does not require feedback-level oscillation keys.

#### Phase 1 Anchor Resolution

Because the Phase 1 Critic MAY use free-form anchors, the Canonicalizer MUST apply a deterministic anchor resolution rule when producing `reviewer_feedback.json.affected_sections`.

If the Orchestrator provides a canonical section ID list (or section index) in the Canonicalizer prompt, then for each Critic `affected_sections` entry the Canonicalizer MUST:

- treat the entry as a canonical ID if and only if it exactly matches one of the provided canonical IDs
- otherwise, attempt an exact, case-sensitive match against the provided section titles; if matched, map to the corresponding canonical ID
- otherwise, attempt a whitespace-normalized exact match (trim leading/trailing whitespace; collapse internal runs of ASCII whitespace to a single space) against the provided section titles; if matched, map to the corresponding canonical ID
- otherwise, treat the anchor as unresolvable: the Canonicalizer MUST emit an `anchor_unresolved` warning referencing the originating `critic_finding_id` and MUST NOT invent a canonical affected section

For an unresolvable anchor, the Canonicalizer MUST omit the corresponding affected section entry from the produced reviewer feedback item. The reviewer feedback item MAY contain an empty `affected_sections` array if no anchors were resolvable.

### Phase 2

Two-stage review is stricter in Phase 2.

The Canonicalizer prompt MUST include:

- canonical section ID list
- concern type enum
- direction enum
- scope enum
- opposition pair rules
- target rubric identity
- declaration context when applicable

Phase 2 Canonicalizer output MUST satisfy the Phase 2 reviewer input schema before Orchestrator canonicalization.

Invalid Phase 2 oscillation classification is an artifact validation failure under the existing retry/halt policy.

## Prompt Snapshots And Telemetry

Critic and Canonicalizer prompt attempts MUST use the same attempt snapshot pattern as reviewer/editor attempts:

```text
prompt_snapshots/{stage}-{artifact_name}-attempt-{attempt_number}.json
```

Critic and Canonicalizer telemetry MUST use the same client telemetry schema when possible:

```text
client_telemetry/{stage}-{artifact_name}-attempt-{attempt_number}.json
```

Telemetry remains non-authoritative. Prompt snapshots remain the authoritative prompt audit artifact.

## Validation And Retry

Critic artifact validation failure MUST retry the Critic stage before invoking the Canonicalizer.

Canonicalizer artifact validation failure MUST retry the Canonicalizer stage without rerunning the Critic, unless the Orchestrator determines the failure is caused by irreparable Critic ambiguity.

Irreparable Critic ambiguity MUST be determined by the Orchestrator.

Irreparable Critic ambiguity MUST be treated as true if and only if at least one of the following is true:

- the Canonicalizer emits an `insufficient_evidence` warning for every in-scope `critic_finding_id` in `critic_findings.json`
- for every in-scope finding, the `evidence` field is empty after trimming ASCII whitespace (i.e., it contains zero non-whitespace characters)

If Critic output validates but is too ambiguous for canonicalization, the Canonicalizer MUST emit an `insufficient_evidence` warning.

In this ambiguity-triggered path, the Orchestrator MUST treat `canonicalizer_summary-attempt-M.json` as the authoritative persisted warning source for Critic retry prompt construction.

Therefore, if the Orchestrator will retry the Critic due to ambiguity, the Orchestrator MUST:

- require the corresponding `canonicalizer_summary.json` content for that Canonicalizer attempt to be schema-valid
- accept and persist that Canonicalizer attempt summary at `canonicalizer_summary-attempt-M.json` (even though the Canonicalizer attempt did not produce an acceptable persisted `reviewer_feedback.json`)

If the Canonicalizer attempt summary fails schema validation, the Orchestrator MUST treat the attempt as a Canonicalizer artifact validation failure and retry the Canonicalizer (not the Critic) under the existing retry policy.

Given a persisted, schema-valid `canonicalizer_summary-attempt-M.json` containing the ambiguity warnings, the Orchestrator MUST either:

- retry the Critic once with Canonicalizer warnings as feedback
- halt with `HALTED_ARTIFACT_INVALID`

The default behavior MUST be to retry the Critic once, then halt if ambiguity persists.

### Critic Retry Prompt Construction

When retrying the Critic due to ambiguity, the Orchestrator MUST construct the retry prompt deterministically.

The retry attempt MUST use the same base prompt template as the initial Critic attempt for the same round/phase/profile, with exactly one additional appended block titled `CANONICALIZER_WARNINGS`.

The `CANONICALIZER_WARNINGS` block MUST contain the JSON serialization of the full `canonicalizer_summary.json.warnings` array from the Canonicalizer attempt that triggered the Critic retry.

Warnings MUST be included in the array order as persisted in `canonicalizer_summary-attempt-M.json`.

If `canonicalizer_summary.json.warnings` is empty, the Orchestrator MUST still append `CANONICALIZER_WARNINGS` with an empty JSON array (`[]`).

No other Canonicalizer fields (including `transformations`) may be injected into the Critic retry prompt.

### Terminal Reporting For Persistent Ambiguity

If the Orchestrator performs the default ambiguity retry (Critic retry once) and ambiguity persists (i.e., the post-retry Canonicalizer again indicates irreparable Critic ambiguity), the Orchestrator MUST halt with `HALTED_ARTIFACT_INVALID` and persist `round_failure_report.json` with:

- `failed_stage: critic`
- `attempt_count` equal to the number of Critic attempts performed in the round (including the retry)
- `failure_reason` indicating persistent ambiguity (for example: `CRITIC_AMBIGUOUS_PERSISTENT`)
- `last_prompt_snapshot_path` and `last_client_telemetry_path` pointing to the last persisted Critic attempt snapshot/telemetry

Canonicalizer attempts performed only to detect ambiguity MUST NOT change `failed_stage` from `critic` in this terminal reporting path.

If retry exhaustion occurs, existing artifact validation failure behavior applies. The Orchestrator MUST persist `round_failure_report.json` and the report MUST identify which stage failed.

## Determinism Boundary

The split pipeline improves reliability but does not make the Critic or Canonicalizer deterministic.

Determinism is preserved by:

- controlled schemas
- Orchestrator-computed hashes and fingerprints
- Orchestrator severity normalization
- validation before canonical persistence
- explicit lineage
- retry/halt artifacts

The Canonicalizer is a probabilistic translator into a deterministic artifact boundary.

## Acceptance Criteria

A two-stage implementation is acceptable if all criteria below are observably true.

### Successful Round

Given `review_pipeline.mode = critic_then_canonicalizer` and valid client configuration, when both stage outputs validate on their first attempt:

- the round persists `critic_findings.json`, `canonicalizer_summary-attempt-1.json`, and `reviewer_feedback.json`
- `reviewer_feedback.json` is schema-valid for the phase
- `canonicalizer_summary-attempt-1.json.source_critic_findings_hash` equals the SHA-256 hex digest (lowercase) of the UTF-8 bytes of the persisted `critic_findings.json`
- every in-scope `critic_finding_id` present in the persisted `critic_findings.json` appears in exactly one `canonicalizer_summary-attempt-1.json.transformations[*].critic_finding_ids` entry

If the implementation uses the convenience copy `canonicalizer_summary.json`, it MUST be byte-identical to `canonicalizer_summary-attempt-1.json` in this case.

### Canonicalizer Retry Without Critic Rerun

If `critic_findings.json` validates and Canonicalizer attempt 1 fails artifact validation, then on Canonicalizer attempt 2:

- the Orchestrator MUST NOT re-run the Critic
- the Canonicalizer MUST receive the same persisted `critic_findings.json` content (same hash)
- the round persists multiple Canonicalizer attempt snapshots/telemetry under `prompt_snapshots/` and `client_telemetry/`

### Canonicalizer Summary Persistence Across Attempts

If a Canonicalizer attempt emits a schema-valid `canonicalizer_summary.json` but the corresponding reviewer feedback is rejected, and a later Canonicalizer attempt succeeds or also emits a valid summary:

- each accepted summary is persisted under its own attempt-scoped path `canonicalizer_summary-attempt-M.json`
- no previously persisted `canonicalizer_summary-attempt-*.json` is overwritten
- `canonicalizer_summary.json` (if used) points only to the successful attempt summary and is not used as a retry-time “latest” pointer

### Critic Retry Warning Source

If the Orchestrator retries the Critic due to irreparable ambiguity (as defined in this spec):

- the Orchestrator persists the schema-valid `canonicalizer_summary-attempt-M.json` for the Canonicalizer attempt that triggered the retry
- the Critic retry prompt includes `CANONICALIZER_WARNINGS` containing exactly the persisted `canonicalizer_summary.json.warnings` array content in the persisted array order

### Halt On Invalid Artifacts

If a stage exhausts retries without producing a valid artifact:

- the Orchestrator exits the round with `HALTED_ARTIFACT_INVALID`
- the round persists `round_failure_report.json`
- the failure report identifies the failing stage (`critic` or `canonicalizer`)

### Halt On Persistent Critic Ambiguity

If the Orchestrator performs the default Critic ambiguity retry and ambiguity persists:

- the Orchestrator exits the round with `HALTED_ARTIFACT_INVALID`
- the round persists `round_failure_report.json` with `failed_stage: critic`
- `attempt_count` equals the number of Critic attempts performed in the round

## Recommended Initial Client Assignment

The recommended initial live configuration is:

- Critic: Claude Code, especially in Phase 1, where rich critique is valuable
- Canonicalizer: Codex `gpt-5.5`, where strict structured output has been more reliable
- Editor: configured independently based on editing performance and availability

This recommendation is empirical and SHOULD remain configurable.

## Migration Plan

1. Keep `direct` mode as the default.
2. Add `critic_findings.json` schema.
3. Add `canonicalizer_summary.json` schema.
4. Add config parsing for `review_pipeline`.
5. Add fixture clients for Critic and Canonicalizer.
6. Implement two-stage live round path behind `review_pipeline.mode`.
7. Add tests proving Canonicalizer retry does not rerun a successful Critic by default.
8. Add live smoke using Claude Code as Critic and Codex `gpt-5.5` as Canonicalizer.
9. Decide whether `source_critic_finding_ids` should become part of persisted `reviewer_feedback.json`.
10. Consider making two-stage mode the default for Claude reviewer configurations only after repeated live evidence.

## Open Questions

- Should Canonicalizer-discovered issues ever be allowed, or should they always be routed back through a Critic retry?
- Should `critic_findings.json` be JSON-only, or should `critic_working_notes.md` also be persisted for richer reasoning?
- Should Phase 2 require the Critic to use canonical section IDs, or is that solely the Canonicalizer's job?
- Should a Canonicalizer merge/drop decision create a decision point when the source finding was blocker or major?
- Should two-stage mode be profile-selective, such as Phase 1 only or Phase 2 only?
- Should reviewer telemetry totals distinguish Critic and Canonicalizer from direct Reviewer in run summaries?
