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

Issue identifiers are Orchestrator-owned deterministic aliases:

```text
issue_fingerprint = SHA256(
  normalized(issue_type) + "\n" +
  normalized(sorted(affected_sections)) + "\n" +
  normalized(invariant_violated) + "\n" +
  normalized(claim)
)

issue_id = "iss_" + first_16_hex_chars(issue_fingerprint)
```

`affected_sections` MUST contain canonical section IDs and MUST be sorted lexicographically for issue identity. Null `invariant_violated` uses the canonical null scalar representation. Reviewer-provided `issue_id` and `issue_fingerprint` are placeholders until the Orchestrator recomputes them.

`severity_rationale` MUST be non-null when `baseline_severity = null`; otherwise it MAY be null.

`oscillation_key` MAY be null in Phase 1.

`change_audit_feedback.json` MUST use the same canonical persisted schema as `reviewer_feedback.json`. It is produced by the `audit-change` workflow and differs only in artifact path, prompt context, and hash authority: its `draft_hash` is the hash of `change_audit/audit_brief.md`.

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

When an applied live round expects the Editor to generate a revised draft, the Editor response MUST include `draft_after_content` containing the complete revised draft text. The Editor response MAY set `draft_after_hash` to null or an implementation-specific placeholder in this generated-revision input. The Orchestrator MUST treat that content as client input, not authority to replace a validated draft. Under legacy behavior it computes and injects `draft_after_hash` from that input before persisted validation, writes validated content to `draft_after.md`, and only then mutates `spec.md`. An explicitly guarded run MUST instead use the materialized bytes and acceptance ordering in the bridge contracts below; no raw proposal may be written as authority merely because its JSON validates.

Persisted `editor_summary.json` MUST contain the Orchestrator-computed `draft_after_hash`. The Editor is not authoritative for derived hashes in editor-generated applied revisions.

If a live Reviewer returns valid feedback with `feedback = []` and no explicit external `draft_after.md` fixture is being evaluated, the Orchestrator SHOULD NOT invoke the Editor. It MUST instead persist a deterministic no-op `editor_summary.json` with empty accepted/modified/declined/resolved/unresolved arrays, `draft_before_hash = draft_after_hash`, and, for applied rounds, `draft_after_content` equal to the unchanged draft. This no-op summary is Orchestrator-owned and has the same acceptance semantics as an Editor-confirmed no-op.

The Orchestrator MUST reject destructive Editor-generated draft replacements before writing `draft_after.md` or mutating `spec.md`. At minimum, when `draft_before.md` is non-empty, the Orchestrator MUST reject:
- empty or whitespace-only `draft_after_content`
- known Editor blocked/error placeholder text in `draft_after_content`
- near-empty replacements that are destructively smaller than a large non-empty draft
- forbidden text-corruption characters in `draft_after_content`

For runs explicitly admitted with supported `preservation_bridge.mode = enforce`, the Orchestrator MUST also run the current-runtime preservation bridge defined by [Candidate Editing And Promotion](CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#current-runtime-preservation-bridge). Compare materialized output against the exact pre-Editor base using the versioned bridge inventory, not only line counts, character ratios or legacy review section IDs. This is a specified capability pending implementation/qualification, not an assertion that current full-draft runs are guarded.

The bridge MUST classify base units with the preservation disposition vocabulary:

```text
preserved | moved | reworded_equivalent | strengthened | superseded | authorized_deleted | operator_authorized_weakened | unauthorized_deleted | ambiguous
```

The Orchestrator MUST reject automatic draft acceptance when bridge comparison finds an `unauthorized_deleted` or `ambiguous` protected unit, unauthorized weakening, disallowed change outside the bounded change surface, unauthenticated supersession, or replacement of concrete contracts with summaries, ellipses, placeholders, or "unchanged" references. Reviewer silence and a schema-valid `editor_summary.json` do not satisfy this preservation check.

When this bridge rejects a proposal, the proposed bytes MUST be persisted as a non-authoritative `full_draft_rewrite_attempt` for operator inspection, but MUST NOT be written as authoritative `draft_after.md`, copied to `spec.md`, used as `last_accepted_draft_hash`, marked profile-clean, advanced to Phase 2, or made apply-back eligible. This diagnostic artifact is not a vNext candidate and does not participate in candidate disposition, indexing, or promotion lineage. The terminal or validation report MUST reference the attempt's current-runtime preservation bridge report, including its failed categories and affected unit IDs.

Forbidden text-corruption characters are Unicode category `Cc` control characters except LF, CR, and TAB, plus `U+FFFD` replacement characters. Such rejection is an artifact validation failure, not an accepted draft mutation. The invalid attempt MUST be persisted and the previous valid draft MUST remain authoritative.

Apply-back preflight MUST run the same text hygiene validation against the final draft before writing to the source spec. A final draft that violates text hygiene MUST NOT be applied, even if the run predates the validation guard or was manually edited after convergence.

When `draft_after.md` is supplied by an external fixture or explicit Orchestrator input, `draft_after_content` MAY be null or omitted.

When a `declined_feedback` item has `decline_reason = deferred_to_later_round`, `target_profile` and `target_round_or_phase` MUST be non-null strings. For every other decline reason, they MAY be null.

### Current-Runtime Preservation Bridge Contracts

These are public specification contracts for the pending `preservation-bridge-v1` capability, not implemented schema files. They are independent of the vNext contract suite. The capability MUST NOT be advertised until equivalent closed schemas, validators and conformance fixtures ship. All declared fields are required unless explicitly optional; unknown fields fail, arrays are ordered and duplicate-free, integers exclude booleans, and hashes are 64 lowercase hexadecimal SHA-256 characters. `Ref` means exactly `{path: string, sha256: sha256}` over persisted bytes. Paths MUST be relative to the run root, resolve within it without symlink escape, and identify regular files. Missing files, changed bytes or unsupported schema/algorithm versions fail closed. Client output never owns these hashes.

#### Approved Change Surface

```yaml
schema_version: bounded-change-surface-v1
base_draft: Ref
inventory: Ref
scope_contract: Ref
finding_sources:
  - artifact: Ref
    feedback_ids: [string]
allowed_sections: [string]
allowed_unit_ids: [string]
frozen_sections: [string]
frozen_unit_ids: [string]
allowed_change_types: [add | clarify | strengthen | move | rename | reword | supersede | delete | weaken]
relocations:
  - source_unit_ids: [string]
    destination_section: string
    change_type: move | rename
deletion_allowed: boolean
weakening_allowed: boolean
authorized_deletion_unit_ids: [string]
authorized_supersession_unit_ids: [string]
max_changed_sections: integer | null
max_changed_normative_units: integer | null
approval:
  approved: true
  approved_by: string
  approved_at: RFC3339 UTC timestamp
```

The inventory's exact base MUST match `base_draft`; all existing IDs/sections MUST resolve there. New allowed destination sections use the parser's canonical path syntax and MUST NOT collide with existing IDs. Empty lists allow nothing; null limits mean no numeric cap, otherwise limits are non-negative. Deletion/supersession lists are subsets of allowed units; allowed/frozen conflicts, impossible relocations and orphan permission flags fail admission. Scope approval requires `status = approved`, `approval.approved = true` and a nonempty operator identity. Finding artifacts MUST be validated persisted Reviewer feedback for the exact base (their normalized hash is checked against the exact base), with every named ID present and in scope. Source identity is the pair of artifact SHA-256 and feedback ID, not bare ID alone.

Create the manifest's transitive inputs as immutable run-local files before operator approval, including an exact base snapshot rather than mutable `spec.md`, and a scope snapshot rather than a replaceable intake file. Inventory references the immutable base; manifest references that inventory and immutable scope/findings. Admission may make byte-identical context copies but MUST NOT rewrite internal paths or recompute approval over changed artifact bytes. Original referenced snapshots must remain available for later chain validation. The same rule applies to evidence. An imported `predecessor_report` is an opaque, hash-checked historical reference, not part of the new root's acceptance chain; retain the original root for inspecting its transitive references and do not rewrite them to resolve against new artifacts. Snapshot storage is authorized local Orchestrator work, never an Editor-write surface.

`finding_sources = []` permits an unchanged no-op but no client mutation. New Reviewer findings do not automatically join this list. A later finding or base change requires a newly approved surface. The operator approval asserts that the listed finding/action surfaces fit the pinned scope; Whetstone validates IDs, scope status and the approval rather than pretending to mechanically infer arbitrary prose intent. Scope and manifest both remain visible to review.

#### Inventory And Parser

`bridge-inventory-v1` has `schema_version`, `parser_version = bridge-lines-v1`, `base_draft: Ref`, `sections`, and `units`. The Orchestrator produces it; approval references it but cannot change parser output. Recompute it to validate it, rather than trust supplied IDs.

The parser consumes strict UTF-8 with no replacement decoding. Recognize physical lines using LF, CRLF or CR, retaining each exact byte slice and terminator. A final unterminated line is a line; a final terminator does not invent an additional empty line. Every byte belongs to exactly one line unit, including separators and a UTF-8 BOM when present. Non-UTF-8 input is invalid, not normalized away.

Only ATX headings of one through six `#` characters followed by space/tab or end of line, with at most three leading spaces, create sections. Fences begin with at least three identical backticks or tildes after at most three leading spaces and end with the same character at equal-or-greater length and only trailing whitespace. No heading is recognized inside a fence; an unclosed fence consumes the remaining lines. Setext and indented headings remain body content in this version, not guessed hierarchy. Heading parents are the nearest preceding shallower heading; missing levels are legal. Root/preamble is a section with path `[]`.

Canonical section paths are compact JSON arrays of `[heading_text, same_text_sibling_ordinal]` segments from the root. Strip heading markers, optional closing markers preceded by whitespace, and outer space/tab from the title; preserve case, Unicode and internal whitespace without slugging. Ordinals are one-based among equal titles under that exact parent. `section_id` is this serialized path string. Section records contain `section_id`, nullable `parent_section_id`, `heading_unit_id` (null only for root), and ordered `direct_unit_ids`; descendants are not duplicated into that list.

Every line unit contains `unit_id`, `section_id`, `kind`, `ordinal`, `byte_start`, `byte_end`, `content_sha256`, and `normative`. Spans are zero-based half-open byte ranges over the exact base, collectively partitioning all bytes. Kinds, in priority order, are `heading`, `fence_delimiter`, `fence_body`, `separator` (space/tab only without terminator), and `body`. Ordinal is one-based among the same kind directly owned by that section. A heading belongs to its new section, including its own heading unit. All other lines belong to the most recent section, so Markdown does not invent parent ownership for prose after a child's heading. Parent intro and child trailing text are never omitted.

Unit IDs are `u_` plus the full SHA-256 of UTF-8 canonical JSON `["bridge-lines-v1", base_sha256, section_id, kind, ordinal]`, using compact separators and unescaped Unicode. `content_sha256` hashes the exact line bytes. `normative` is true iff the decoded line contains a case-sensitive whole word `MUST`, `SHALL`, `SHOULD`, `MAY`, `REQUIRED`, `RECOMMENDED` or `OPTIONAL`, with word boundaries defined by ASCII letters/digits/underscore. Unmarked lines are still protected. An ID collision or non-partitioning span set is invalid. Materialized inventories use the same algorithm and their own exact draft hash; identities are not cross-draft semantic IDs.

Identical section direct-content sequences match positionally even when duplicates exist. Otherwise correspondence uses exact kind/content matches in that section and is accepted only if the maximum order-preserving matching is unique; multiple matchings are `ambiguous`. There is no similarity threshold. Remaining units require hash-bound operator correspondence evidence or receive removed/added/ambiguous treatment according to the candidate leaf. Container and semantic aggregates are not additional counted units, avoiding overlap/double counting; protection of a contract covers all its lines, including schema fields, table rows and prose enumerations. This conservative physical granularity means reflow alone may need an equivalence attestation; it is not automatic semantic verification.

`max_changed_sections` counts distinct source/destination canonical section paths affected by non-preserved dispositions or additions. `max_changed_normative_units` counts distinct normative base units with non-preserved dispositions plus normative added units; matched successors are not counted again. Moves count source units once and both sections. Attested many-to-one supersession counts each base predecessor once. Trusted version-only spans are exempt only from the transform's exact changes, never from nearby client changes. Empty drafts and absence of recognized headings remain inventoryable; existing destructive-output checks still apply.

#### Attempt Storage And Materialization

Each admitted execution allocates a new positive monotonic `M` within round `N`, including technical retries, supplied fixtures and no-ops. `M` is the bridge attempt number, not necessarily the client retry number; record the latter separately. Never reuse even an incomplete attempt number. Before invocation create `rounds/round-N/preservation/attempt-M/admission.json` and immutable input snapshots beneath that directory. Do not overwrite the old round-level `context/bounded_change_surface.json` to change authorization.

Admission schema `preservation-bridge-admission-v1` contains `schema_version`, `capability_version = preservation-bridge-v1`, `round_number` (positive integer or null), `attempt_number` (positive integer), `phase` (`phase_1 | phase_2`), `profile` (nonempty string or null), `origin` (`editor | supplied_revision | orchestrator_noop | phase2_entry`), nullable positive `client_attempt_number`, `base_draft`, `inventory`, `scope_contract`, `allowed_change_surface` (all Refs), `finding_sources` (same records as the manifest), `operator_evidence` (array of Refs), nullable `predecessor_report` (Ref), and `transform_policy_version = bridge-version-transform-v1`. The schema MUST discriminate on `origin`: `round_number` and `profile` MUST both be null if and only if `origin = phase2_entry`; for every other origin, `round_number` MUST be a positive integer and `profile` MUST be a nonempty string. This rule does not change the separately specified `client_attempt_number` nullability. All artifact references point to immutable snapshots. Reviewer contexts remain read-only; Editor contexts additionally identify the admitted surface, exact base and no-expansion instructions. The admission is included by path/hash in context/prompt/attempt manifests.

Persist the original client response through existing attempt storage. Strictly JSON-decode `draft_after_content`; encode that string as UTF-8 without newline, whitespace, Unicode or replacement normalization into `rounds/round-N/full_draft_rewrite_attempt-M.md`. This is the raw draft proposal, not the response envelope. Invalid JSON/Unicode may leave only raw response evidence. Supplied revisions retain exact file bytes; no-op/Phase 2 entry raw proposals equal base bytes.

Persist materialized bytes separately as `rounds/round-N/materialized_draft_attempt-M.md`. The only trusted transform is `version_stamp`, version `bridge-version-transform-v1`, implementing the scheduler's specified round or Phase 2 entry stamp (including its explicitly required `Status: Accepted` demotion). It may replace only selected version/status value spans, preserving all other bytes. Parameters contain exactly `event` (`phase1_revision | phase2_revision | phase2_entry`), `phase` (`phase_1 | phase_2`) and `changes`, an array of `{kind: version | status, base_byte_start: integer, base_byte_end: integer, input_byte_start: integer, input_byte_end: integer, before: string, after: string}`. Ranges are non-negative half-open UTF-8 offsets, ordered, non-overlapping and bound to equal old values in base/raw input; values cannot contain line breaks. Verify new values by the pinned scheduler algorithm, not by trusting parameters. Input/output hashes are separate transformation fields. An ordered transform list is empty for a true no-op or unsupported/absent anchor. Ambiguous anchors fail, as in existing version rules. Editor-altered anchors fail `untrusted_version_edit` before stamping; no automatic restoration is trusted.

For unit correspondence and changed-section counting only, reverse the verified stamp's section-path/title changes to their raw names. The transformation provides the exact line/span mapping, including descendants whose canonical paths include a stamped heading. Materialized inventories and hashes still describe actual final bytes. Treat only recorded version/status value spans as trusted; every other difference on the same line or in descendants remains subject to ordinary preservation. This prevents either rejecting all descendants after a legitimate heading stamp or exempting adjacent Editor changes.

Only a round otherwise eligible for accepted mutation receives a revision stamp. Rejected/unresolved content receives no increment and cannot become authority. A prospective stamp is not an accepted history event. Recompute all transform outputs from immutable inputs under the pinned implementation; do not apply them twice on resume. Materialized inventories, preservation checks and canonical Editor summary hashes are computed only from the final bytes. The compatibility `draft_hash` is separately recorded using the existing normalization algorithm.

Phase 2 entry uses the same contract under `rounds/preservation/phase2-entry/attempt-M/`, with files `admission.json`, `raw_proposal.md`, `materialized_draft.md`, `materialized_inventory.json`, `report.json` and `acceptance.json`, `round_number = null`, `client_attempt_number = null`, and `profile = null`. Its immutable admission inherits the last accepted bridge authorization; it permits ONLY the specified Orchestrator version/status transform over that accepted base, not an Editor call or other content change. This narrowly defined maintenance operation does not rebind an Editor's allowed surface to a new base. Any later editing requires a newly base-bound surface.

An Orchestrator-owned reviewer-only no-op may likewise inherit the accepted marker's prior surface for provenance, with a newly generated inventory of current accepted bytes. In these two maintenance origins only, an older surface/base binding is permitted through the validated acceptance chain, and no mutation except the exact Phase 2 entry stamp is authorized. All other origins require exact current surface/base/inventory equality. Initial seed no-ops without a prior accepted marker require normal admission. Preflight must distinguish a valid maintenance-only path from authorization to invoke an Editor; discovering new findings never converts the former into the latter automatically.

### Current-Runtime Preservation Bridge Report

Every attempt that reaches a terminal outcome MUST persist `rounds/round-N/preservation_bridge_report_attempt-M.json`; incomplete/interrupted attempts retain existing evidence without fabricated outputs. These reports are distinct from vNext `preservation-report-v1` and never confer candidate authority.

```yaml
schema_version: current-runtime-preservation-bridge-report-v1
admission: Ref
stage: admission | client | materialization | comparison | persistence | complete
raw_response: Ref | null
raw_proposal: Ref | null
materialized_draft: Ref | null
materialized_inventory: Ref | null
materialized_draft_hash: sha256 | null  # normalized compatibility hash, not exact SHA-256
transformations:
  - id: version_stamp
    version: bridge-version-transform-v1
    parameters: object  # closed event/phase/changes record defined above
    input_sha256: sha256
    output_sha256: sha256
unit_dispositions:
  - unit_id: string
    disposition: preserved | moved | reworded_equivalent | strengthened | superseded | authorized_deleted | operator_authorized_weakened | unauthorized_deleted | ambiguous
    successor_unit_ids: [string]
    finding_refs: [{artifact_sha256: sha256, feedback_id: string}]
    evidence_refs: [Ref]
    rationale: string
added_unit_ids: [string]
failures:
  - category: invalid_binding | invalid_artifact | unauthorized_deleted | ambiguous | disallowed_weakening | allowed_surface_overrun | unauthenticated_supersession | contract_collapse | untrusted_version_edit | unsupported_transform | client_timeout | transient_client_failure | persistence_failure
    affected_unit_ids: [string]
    reason: string
validation_result: pass | fail | not_completed
outcome: eligible | rejected | paused | technical_failure
next_action: none | technical_resume | new_authorized_attempt | inspect_and_repair
```

For a completed comparison, require both text Refs, the materialized inventory and compatibility hash, exactly one disposition for every base unit, and separate added-unit enumeration. Successors MUST exist; duplicate claims fail unless attested supersession permits them. Every changed/added unit has admitted finding attribution, except exact trusted transform spans. Authorized weakening/deletion and every equivalence/supersession claim MUST name admissible operator evidence. `unauthorized_deleted`/`ambiguous` require matching failures. Include every failed check, not only the first. Empty affected IDs are permitted only for non-unit failures or impossible identity resolution with an explicit reason.

Every added unit also requires `attest_addition` evidence; changed meaning of text retained verbatim must use its actual authorized disposition. `added_unit_ids` is not an evidence loophole. Output unit coverage MUST account for the entire materialized inventory as either a matched successor or an explicitly listed addition, never both.

`pass` requires completed comparison and zero failures; `eligible` is possible only with `pass` and does not itself mean accepted. `paused` requires only the scope/weakening authorization failures allowed by the scheduler, while `rejected` means deterministic failure. `not_completed` means comparison could not finish and cannot claim total dispositions or pass; nullable outputs reflect only actually available evidence. A deterministic pre-comparison error is still rejected without retry, not reclassified as transient because comparison did not finish. Invalid/missing report persistence prevents acceptance even if the comparison would pass.

Before authoritative writes, validate schema, references, inventory reproduction/coverage, transforms, disposition/evidence consistency, outcome and compatibility hash. Persist a separate immutable `acceptance.json` beside `admission.json` only after all normal round gates also pass. Schema `preservation-bridge-acceptance-v1` contains `schema_version`, `admission: Ref`, `report: Ref`, `materialized_draft: Ref`, `materialized_draft_hash: sha256` (normalized), `accepted_noop: boolean`, and `previous_acceptance: Ref | null`. Phase 2 entry uses the same marker in its special directory. The first accepted guarded attempt uses null only for the explicitly recorded original seed. No mutation after validation is permitted.

A failure after a completed report was persisted MUST NOT rewrite it. If storage permits, write `terminal_failure.json` beside admission with schema `preservation-bridge-terminal-failure-v1` and fields `schema_version`, `admission: Ref`, `report: Ref | null`, `category` (`persistence_failure | invalid_binding`), `reason: string`, and `acceptance: Ref | null`. The ordinary terminal report references that artifact. A null acceptance means no commit; a valid non-null acceptance permits only the checked mirror-repair path. If even failure reporting cannot be persisted, return the technical error directly and refuse acceptance; absence of a report is never success.

The marker is the bridge acceptance commit point, not a vNext promotion pointer. Enforce the current single-writer run assumption and atomic create-if-absent for each immutable artifact; interrupted temporary writes never count as artifacts. Identical replay can reuse a completed marker; different bytes at an occupied immutable path halt as `invalid_binding`. An interruption while updating normal mirrors/history after a valid marker is repaired from that marker's checked bytes, without another stamp or duplicated history event. A proposed/report-only file without the marker cannot drive that repair.

Run state/status/terminal reporting MUST include `preservation_bridge` with `mode` (`enforce | legacy_unguarded`), nullable `capability_version`, nullable `latest_attempt_report: Ref`, nullable `accepted: Ref` (acceptance marker), nullable `pending_outcome`, and `next_action`. Effective config retains the pinned manifest and evidence references separately. Missing/broken evidence in an opted-in run MUST NOT be displayed as legacy. Preserve historical failed reports when later attempts succeed. These fields do not replace ordinary issue counts, profile verification or source-write safeguards.

### Decision Points

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

`checkpoint_id` MUST be deterministic:

```text
checkpoint_id = "chk_" + first_16_hex_chars(SHA256(canonical_json({
  "round_number": round_number,
  "profile": profile,
  "source_type": source_type,
  "source_ids": sorted(source_ids),
  "trigger_reason": trigger_reason,
  "question": normalized(question)
})))
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

`checkpoint_cluster` MUST contain:

```yaml
cluster_key: string
checkpoint_count: integer
checkpoint_ids: [string]
highest_severity: blocker | major | minor | nit | null
round_numbers: [integer]
affected_sections: [string]
```

`checkpoint_summary_card` MUST contain the complete checkpoint card fields from `operator_decision_checkpoint.json` plus:

```yaml
cluster_key: string
selection_reason: string
```

Checkpoint summary clusters MUST be mechanical:

- `by_trigger_reason` groups by `trigger_reason`.
- `by_section` groups by the first affected section on each checkpoint card.
- `by_source_type` groups by `decision_point` vs `unresolved_issue`.
- `recommended_operator_review` MUST contain at most five checkpoint cards sorted by deterministic priority: authority boundary, deferred scope boundary, failure/reporting policy, validation policy, then general operator policy choice; ties sort by severity, round number, then checkpoint ID. Severity sort order is `blocker`, `major`, `minor`, `nit`, `null`.

The human-readable Markdown summary MUST expose the same counts, recommended review cards, and clusters without adding semantic interpretation beyond persisted checkpoint fields.

`context_pressure_report.json` MUST contain:

```yaml
schema_version: context-pressure-v1
generated_at: string
root: string
phase: string
round_number: integer
profile: string
behavior: observability_only
action_taken: none
estimate_method: string
report_scope: configured_run_inputs | round_prompt_context
thresholds:
  total_warning_bytes: integer
  component_warning_bytes: integer
  reference_count_warning: integer
totals:
  component_count: integer
  existing_component_count: integer
  byte_count: integer
  char_count: integer
  estimated_tokens: integer
  reference_context_count: integer
components:
  - label: string
    kind: mutable_draft | scope_contract | rubric | reference_context | string
    role: string
    path: string
    required: boolean
    exists: boolean
    byte_count: integer
    char_count: integer
    estimated_tokens: integer
    sha256: string
    read_error: string
referenced_context:
  reference_count: integer
  references:
    - label: string
      path: string
      mention_count: integer
      source_feedback_ids: [string]
warnings:
  - severity: info | warning
    code: string
    message: string
```

The context pressure report is Orchestrator-owned and advisory. It estimates context payload using a simple `ceil(char_count / 4)` estimate. The estimate is not provider tokenizer output.

When `report_scope = configured_run_inputs`, the report measures the configured mutable draft, scope contract, selected rubric, and reference context files. When `report_scope = round_prompt_context`, the report measures the actual context files written into `rounds/round-N/context/` for that round, including generated Reviewer feedback or contract-surface reports when those files are part of the active prompt.

For round prompt context reports, `referenced_context` SHOULD identify reference-context files mentioned by Reviewer findings using deterministic text matching against generated context filenames, reference labels, and reference paths. This field is an observability signal for future context-selection work; it MUST NOT make a reference context authoritative, non-authoritative, included, excluded, resolved, or stale by itself.

The report MUST NOT trim prompt context, alter profile scheduling, halt a run, mark a profile clean, or satisfy convergence. It exists so operators and supervising agents can identify oversized drafts, many reference files, missing required context, or unusually large individual context components before attributing slow runs to model behavior alone.

The Orchestrator SHOULD write `/rounds/context_pressure_report.json` and `/rounds/context_pressure_report.md` at live Phase 1 start, live Phase 2 start, and supported resume entrypoints. It SHOULD also write `/rounds/round-N/context_pressure_report.json` and `.md` for each live round.

`profile_sweep_report.json` MUST contain:

```yaml
schema_version: profile-sweep-report-v1
generated_at: string
root: string
phase: phase_1
review_profile_set: string
draft_hash: string
editor_invoked: false
spec_mutated: false
profiles:
  - profile: string
    round_number: integer
    clean: boolean
    feedback_count: integer
    blocker_count: integer
    major_count: integer
    minor_count: integer
    nit_count: integer
    reviewer_feedback_path: string
clusters:
  by_profile:
    - key: string
      blocker_count: integer
      major_count: integer
      feedback_ids: [string]
  by_issue_type:
    - key: string
      blocker_count: integer
      major_count: integer
      feedback_ids: [string]
  by_section:
    - key: string
      blocker_count: integer
      major_count: integer
      feedback_ids: [string]
recommendation: start_phase_1 | run_bounded_synthesis | run_vertical_phase_1 | manual_scope_review
recommendation_rationale: string
```

`profile_sweep_report.json` is Orchestrator-owned. It is produced by a diagnostic sweep command after Reviewer-only passes across the configured Phase 1 profile set. It MUST NOT be produced by the Reviewer or Editor. It MUST NOT be used as a convergence declaration, accepted-draft artifact, clean-profile proof, apply-back report, or Phase 1/Phase 2 scheduler input.

`profile_sweep_report.md` SHOULD present the same information in operator-readable form, including the recommended next action and the largest blocker/major clusters.

`change_audit_report.json` MUST contain:

```yaml
schema_version: change-audit-report-v1
generated_at: string
audit_brief_hash: string
profile: string
verdict: pass | pass_with_minor_clarification | needs_revision | blocked | audit_failed
boundary_preserved: boolean | null
failure_reason: string | null
feedback_counts:
  blocker: integer
  major: integer
  minor: integer
  nit: integer
in_scope_feedback_ids: [string]
out_of_scope_feedback_ids: [string]
recommended_next_action: none | manual_patch | run_focused_whetstone | run_full_whetstone | fix_audit_setup
source_feedback_path: string
audit_manifest_path: string
```

`change_audit_report.json` is Orchestrator-owned. It summarizes validated Reviewer feedback from `change_audit_feedback.json`; the Reviewer MUST NOT produce the report directly. The report MUST NOT be used as a convergence declaration, terminal report, apply-back report, or Phase 1/Phase 2 scheduler input.

`feedback_counts` MUST count in-scope feedback only. Out-of-scope feedback MUST be represented by `out_of_scope_feedback_ids` and preserved in `change_audit_feedback.json`, but it MUST NOT increment `feedback_counts`.

`failure_reason` MUST be non-null when `verdict = audit_failed`; otherwise it MUST be null.

`audit_manifest.json` MUST contain:

```yaml
schema_version: change-audit-manifest-v1
generated_at: string
audit_notes_path: string
audit_notes_hash: string
profile: string
specs:
  - path: string
    hash: string
client:
  name: string
  version: string
  model: string
```

The manifest binds the audit inputs and reviewer identity. It does not assert convergence or source-spec mutation.

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
4. validate the object against the phase-appropriate client-input schema, which MAY allow placeholders or nulls only for Orchestrator-owned derived fields
5. apply Orchestrator-owned canonicalization steps such as issue IDs, issue fingerprints, normalized severity, Phase 2 `oscillation_key` fingerprint, and opposition-key computation
6. validate the canonicalized artifact against the persisted artifact schema

Client-input schemas and persisted artifact schemas are distinct validation stages. A field that is Orchestrator-owned in the persisted artifact MUST NOT make the client-input artifact invalid solely because the client provided null, a placeholder, or a noncanonical value, unless the field is required as semantic input to compute the canonical value.

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

Guarded Editor attempts are the exception: deterministic schema/content/preservation/binding failures receive no automatic validation retry. Only explicitly classified transient technical failures may use the remaining technical retry allowance under identical frozen admission inputs; timeouts still do not retry automatically. The [bridge lifecycle](SCHEDULER_STATE_AND_RESUME_SPEC.md#preservation-bridge-lifecycle) owns exact classification, pausing and continuation. Reviewer artifact retry behavior is unchanged; it cannot refresh an already frozen Editor admission.

If the retry validates, the Orchestrator continues with the validated artifact.

If the retry fails, the Orchestrator MUST halt with `HALTED_ARTIFACT_INVALID` and produce `/rounds/artifact_validation_error.json`.

If a client invocation times out before returning an artifact, the Orchestrator MUST NOT retry the same prompt automatically. It MUST halt with `HALTED_CLIENT_TIMEOUT`, produce `/rounds/artifact_validation_error.json`, set `failure_type = client_timeout`, and produce the phase-appropriate companion failure report. Timeout halts are distinct from artifact validation failures because no candidate artifact was available to validate.

Terminal reports MUST include `run_artifact_pointers` with the same scope-contract and job-descriptor pointer shape used by `run_state.json`. This lets a standalone terminal report identify the scope/job artifacts that shaped the run without requiring an operator to inspect the full run state first.

When a terminal failure report follows a reviewer-only closeout sweep across multiple profiles, it MUST include `closeout_findings_by_profile`. This block MUST group the closeout reviewer result by profile, including round number, draft hash, clean status, blocker/major counts, feedback IDs, and unresolved blocker/major issue summaries. `last_reviewer_findings` remains the final reviewer pass only and MUST NOT be treated as a complete summary of multi-profile closeout residuals.

When a Phase 1 Editor artifact-validation failure occurs after validated Reviewer feedback, the companion technical failure report MUST preserve the Reviewer blocker/major context. The report's `unresolved_blockers`, `unresolved_major_issues`, and `last_reviewer_findings` MUST be derived from the validated Reviewer artifact because no valid Editor artifact exists to resolve those findings.

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

All SHA256 values in Whetstone artifacts MUST be lowercase hexadecimal SHA-256 digests of UTF-8 bytes.

Canonical text normalization:
- decode input as UTF-8
- normalize line endings to LF
- remove trailing spaces and tabs from each line
- preserve all non-whitespace content
- preserve markdown heading text and order
- preserve frontmatter if present
- ensure exactly one trailing newline

The normalized text hash input is the UTF-8 byte sequence of that canonical text.

Canonical JSON serialization:
- use JSON object syntax with keys sorted lexicographically
- emit no insignificant whitespace
- preserve array order unless a field-specific rule explicitly requires sorting
- serialize strings with standard JSON escaping
- serialize null as JSON `null`
- reject non-finite numbers

Canonical JSON hashes are SHA256 of the UTF-8 bytes of that canonical JSON string. Timestamp fields such as `generated_at` record write time and MUST NOT be used as identity inputs unless a specific artifact contract explicitly says otherwise.

Persisted timestamp strings MUST use RFC 3339 UTC with trailing `Z` and second precision, for example `2026-05-17T00:00:00Z`. Timestamp fields may differ across replayed executions and MUST NOT participate in deterministic identity unless an artifact contract explicitly marks them as identity inputs.

Canonical scalar normalization for semantic fingerprints:
- strings: trim leading/trailing whitespace, collapse internal whitespace to a single space, and lowercase enum-like values
- null: serialize as the literal string `<null>`
- booleans: serialize as `true` or `false`
- arrays: normalize each element and preserve or sort according to the field-specific ordering rule

Canonical Markdown section IDs:
- Build a section tree from ATX headings (`#` through `######`) in document order.
- Exclude the first H1 from descendant section IDs when it appears before any other heading and at least one later heading exists. Do not exclude any other heading automatically.
- A section ID is the hyphen-joined slug path of the remaining heading path.
- Slug each heading component by lowercasing, replacing each contiguous run of non-ASCII alphanumeric characters with `-`, and trimming leading/trailing `-`.
- If slugging produces an empty component, use `section`.
- If the same full section ID occurs more than once in one draft, append `#N` to the second and later occurrences using the one-based occurrence count for that full ID.
- Frontmatter and content before the first heading belong to the synthetic section ID `__frontmatter__`.

The canonical section index produced by this rule is the authority for profile focus anchors, oscillation keys, semantic change records, checkpoint section grouping, and clean-status invalidation.

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
