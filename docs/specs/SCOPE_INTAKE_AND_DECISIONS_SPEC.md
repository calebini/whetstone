# Scope Intake And Decisions Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: scope_intake_and_decisions_spec
target_spec_role: leaf_spec
-->

## Scope Contract

A scope contract is an operator-approved first-contact artifact that defines what Whetstone is allowed to pressure during a run.

The canonical artifact path is configured by `scope_contract.path` and defaults to:

```text
rounds/intake/scope_contract.json
```

The scope contract MUST be treated as authoritative when present and approved. Reviewer prompts MUST instruct reviewers to mark concerns outside the contract as `in_scope = false` and to recommend a scope-promotion decision rather than silently expanding the current run. Editor prompts MUST instruct editors to decline out-of-scope or deferred feedback using the existing decline taxonomy.

`workflow: mvp` requires an approved scope contract before live review begins. If the scope contract is missing, invalid, or not approved, preflight validation MUST halt with `CONFIG_INVALID`. This is intentional: an MVP run has no meaningful boundary unless the operator defines the first useful build and its deferrals.

For other workflows, a scope contract is optional unless explicitly required by future configuration. If an approved scope contract exists, the Orchestrator SHOULD inject it into Reviewer and Editor context files and prompt snapshots.

`scope_contract.json` MUST include:

```yaml
schema_version: scope-contract-v1
status: draft | approved | superseded
readiness_target: exploratory | mvp | standard | governance | custom
core_outcome: string
primary_actor_or_consumer: string | null
core_flows:
  - id: string
    description: string
    priority: must | should | could
scope_surfaces:
  - id: string
    name: string
    status: in_scope | deferred | out_of_scope
    required_depth: mention | define | required_fields | full_schema | exhaustive | custom
    rationale: string
deferral_rules:
  - id: string
    trigger: string
    action: defer | allow_if_core | allow | block
    decline_reason: out_of_scope | deferred_to_later_round | architectural_conflict | ambiguous
    rationale: string
acceptance_floor:
  minimum_buildable_result: string
  must_answer: [string]
  may_defer: [string]
review_pressure_limits:
  max_depth_default: mention | define | required_fields | full_schema | exhaustive | custom
  expansion_policy: conservative | balanced | expansive
operator_decisions:
  - question: string
    answer: string
    rationale: string
approval:
  approved: boolean
  approved_by: string | null
  approved_at: timestamp | null
```

`whetstone intake --template mvp --output scope-notes.md` MUST produce a human-editable scope notes template. `whetstone intake --from-notes scope-notes.md` MUST produce a schema-valid scope contract. Unless `--approve` is supplied, generated contracts MUST remain `status = draft` and MUST NOT satisfy the MVP preflight requirement.

## Bridge Operator Authority

This section specifies the pending two-stage `preservation-bridge-v1` contract. It does not activate current runtime enforcement or vNext promotion. The [candidate leaf](CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#current-runtime-preservation-bridge) owns preservation policy; the [artifact leaf](ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#current-runtime-preservation-bridge-contracts) owns admission, proposal, request and report formats.

A guarded run requires an approved scope contract regardless of workflow. Review scope and edit authority are distinct: Reviewers still inspect and report in-scope problems on frozen/unlisted edit surfaces. They cannot expand the Editor's admitted surface. Checkpoint recommendations, ordinary decision records, Editor resolution claims and clean reviews are not mutation authorizations.

Prepare authority in two stages:

1. Freeze the current authoritative base and generate its inventory. Obtain validated Reviewer findings for that exact base, identified by artifact hash plus feedback ID.
2. Have the operator approve the allowed/frozen sections/units, change types and limits against scope and findings. Persist a proposal admission before any Editor invocation. This permits bounded proposal generation only; no attestation over unknown output bytes is required.
3. Retain the raw proposal, materialized output, inventories and normal-round evidence. Produce a preliminary assessment and an exact-effect review showing changed text, finding attribution, correspondence suggestions, hard failures and outstanding evidence obligations.
4. Mechanically prepare evidence for the operator to review and affirmatively adopt. Explicit correspondence resolves identities; semantic attestations address the meaning of the exact retained effect. An Editor's suggestions cannot become evidence merely by being copied or setting `approved = true`.
5. Supply an explicit immutable acceptance request binding that proposal, approved scope/surface/findings and adopted evidence. Freeze a new acceptance admission, revalidate the identical bytes and every required gate, then commit only if ordinary acceptance also passes. Acceptance invokes no Editor.

Approval may cover a meaningful group of units in one evidence record, provided the exact relation and complete effect are visible. The operator need not construct hashes or JSON manually; the trusted local channel produces and pins the records after affirmative adoption. A read-only preview does not constitute approval. Missing evidence during proposal preparation is expected pending work; a known hard failure remains a rejection. A later request may explicitly change authorization without rewriting the original admission or report.

### Operator Evidence Contract

First-release admissible preservation evidence is exact mechanical identity under the inventory/transform rules or explicit operator attestation. There is no implicit LLM or Semantic Verifier evidence producer. Attestation is an accountable trust decision about meaning, not machine proof of natural-language equivalence. Reports MUST identify it as operator-attested.

`bridge-operator-evidence-v2` contains exactly:

```yaml
schema_version: bridge-operator-evidence-v2
kind: authorize_deletion | authorize_weakening | attest_addition | attest_equivalence | attest_strengthening | attest_supersession | authorize_scope_expansion
proposal: Ref
base_draft_sha256: sha256
base_inventory_sha256: sha256
scope_contract_sha256: sha256
allowed_change_surface_sha256: sha256
raw_proposal_sha256: sha256
materialized_draft_sha256: sha256
transformations_sha256: sha256
correspondence:
  - base_unit_id: string
    successor_unit_ids: [string]
    disposition: preserved | moved | reworded_equivalent | strengthened | superseded | authorized_deleted | operator_authorized_weakened
added_unit_ids: [string]
change_types: [add | clarify | strengthen | move | rename | reword | supersede | delete | weaken]
finding_refs: [{artifact_sha256: sha256, feedback_id: string}]
effect: string
rationale: string
approval:
  approved: true
  approved_by: string
  approved_at: RFC3339 UTC timestamp
```

The shared Ref/hash/closed-field rules apply. `proposal` names the artifact leaf's immutable proposal record, never a preliminary report. Base, inventories, raw/materialized hashes and transformations MUST match that proposal and its admission. Scope/surface hashes MUST match the selected acceptance authorization, which may differ from proposal-generation authorization only through explicit new approval. `transformations_sha256` hashes canonical UTF-8 JSON of the proposal's ordered transform list (compact separators, unescaped Unicode, sorted object keys). Evidence cannot reference its later acceptance request/admission/report. Write a newly approved surface first, then evidence, then the request binding both; do not create a hash cycle.

### Explicit Correspondence Rules

`correspondence` is the sole operator-authorized predecessor/successor relation. Independent aggregate `base_unit_ids` and `successor_unit_ids` fields are removed from evidence; array position never establishes a pairing. The final report combines mechanical matches with adopted entries and gives every base unit exactly one final disposition. Evidence entries cover only the operator-adopted subset, not necessarily the whole inventory.

- Every `base_unit_id` resolves in the exact base inventory and appears once within an evidence record. Every successor resolves in the exact materialized inventory. Emit entries in base byte order and successors/additions in output byte order; ordering is serialization discipline, never implicit mapping.
- `preserved` has exactly one successor with equal content and structural ownership except verified trusted transform spans. An attestation cannot turn different bytes into mechanically preserved content.
- `reworded_equivalent`, `strengthened`, `moved` and `operator_authorized_weakened` have one or more explicit successors. One-to-many mappings support evidenced splitting/reflow; the attestation covers their combined effect. Movement also requires the exact manifest relocation mapping and applicable move/rename permissions.
- `authorized_deleted` has no successors and requires deletion evidence and all deletion permissions. Other successful dispositions require successors.
- `superseded` has one or more successors and requires equal-or-stronger coverage attestation. Successor sharing across base units is permitted only when every sharing entry is `superseded`. One supersession attestation MUST contain the entire connected predecessor/successor group: include every entry sharing any successor transitively. Thus a group cannot be assembled from incomplete approvals over separate predecessors. The report must match those entries exactly.
- Every output unit is accounted for as a successor or an addition, never both. Only the supersession rule permits duplicate successor use. A missing predecessor is not cancelled by an unrelated addition.
- `added_unit_ids` contains units with no predecessors and requires addition evidence. It is not an alternative way to authorize successors.
- Multiple evidence kinds may support the same final entry, for example scope expansion plus weakening. Their exact relation entries and dispositions MUST agree; conflicting evidence rejects. Final report coverage counts each base unit once, regardless of the number of supporting attestations.
- Explicit operator entries may resolve ambiguous mechanical matching. Remove the affected provisional suggestions and revalidate full correspondence, ownership, coverage, permissions and all evidence as one relation. No fuzzy match or Editor identity assertion may fill remaining gaps.
- A container rename must account for descendant units. A move accompanied by weakening needs both relocation permission and weakening evidence; its final semantic disposition is `operator_authorized_weakened`, not equivalent movement. Relocation checks remain independently applicable.

For example, entries `A -> [X]` and `B -> [Y]` authorize exactly those mappings; they cannot be read as `A -> [Y]` and `B -> [X]`. Entries `C -> [Z]` and `D -> [Z]` are allowed only as a complete, explicitly attested supersession group. Entry `E -> [U,V]` may represent equivalent reflow when no other predecessor claims U or V. All IDs and dispositions remain bound to exact proposal and acceptance authorization hashes.

### Evidence Kind And Effect Rules

`authorize_deletion` requires nonempty correspondence consisting of `authorized_deleted` entries, empty additions, `delete`, and exact deletion rationale. `authorize_weakening` requires nonempty `operator_authorized_weakened` entries, empty additions, `weaken`, and an account of reduced obligations. `attest_equivalence` covers only nonempty `preserved`, `reworded_equivalent` or `moved` entries with no additions and the relevant reword/clarify/move/rename types. `attest_strengthening` covers only nonempty `strengthened` entries with `strengthen` and no additions. `attest_supersession` covers only nonempty `superseded` entries with `supersede`, no additions, and complete shared groups where applicable. A `preserved` equivalence entry may explicitly resolve duplicate-unit correspondence only when the exact content/ownership checks pass; it authorizes no text change. Each evidence record must use change types applicable to its entries; unchanged correspondence alone may use an empty change-type list. These evidence kinds cannot claim contradictory normative force for the same effect.

`attest_addition` requires empty correspondence, nonempty `added_unit_ids`, `add`, and an explicit assertion that the added text does not repeal, weaken or supersede any base obligation beyond separately authorized dispositions for this exact proposal. An added global exception or precedence rule requires separate weakening/supersession evidence for affected base units even if their text remains verbatim. Those units receive the actual semantic disposition, overriding a merely provisional mechanical `preserved` classification.

`authorize_scope_expansion` requires at least one affected correspondence entry or addition, newly approved scope/surface, applicable change types and exact effect. It supplies no separate deletion, weakening, addition, equivalence, strengthening or supersession attestation; obtain those kinds as needed. Every changed or added unit needs finding attribution within the acceptance surface, apart from exact trusted transform spans.

At proposal assessment, absent equivalence, addition, strengthening, deletion, weakening, supersession or explicit correspondence evidence is pending only when no independent hard failure exists. At submitted acceptance, missing/stale/conflicting evidence rejects; it cannot be repaired by relabeling the report. A clean Reviewer, Editor claim or line-count ratio is not evidence. Binding checks do not prove the operator's semantic assertion correct.

The trusted local channel MUST preserve adopted records immutably and validate them again before acceptance. `approved_by` is a nonempty accountable operator assertion, not a cryptographic identity service. The bridge does not claim protection against a hostile operator or arbitrary external writes to the root. Pending operator work uses the scheduler's `PAUSED_DECISION` mapping even under `end_of_cycle`; ordinary unguarded decisions are unchanged.

A newly approved surface/evidence set creates a new acceptance admission against the retained proposal when its exact base is still current. It may stay in the same root under the scheduler rules. Earlier reports, including rejection reports, remain unchanged. A changed base or changed proposal requires new proposal admission; rejected output is never silently installed as a seed.

## CHANGE AUDIT WORKFLOW

`audit-change` is a lightweight reviewer-only workflow for checking whether a bounded change preserved its intended contract across one or more specs. It is not a convergence run, not a Phase 1 or Phase 2 round, not an apply-back path, and not an Editor workflow.

Use `audit-change` when an operator has already made or is about to make a small feature, policy, boundary, or terminology update that crosses spec boundaries and wants a low-friction sanity check. The workflow answers:

```text
Did this specific cross-spec change preserve the intended contract?
```

It MUST NOT answer:

```text
Is the full spec converged?
```

The command surface SHOULD be:

```text
whetstone audit-change \
  --root <audit_root> \
  --notes <audit_notes.md> \
  --spec <spec_path> \
  [--spec <spec_path> ...] \
  [--profile consistency] \
  [--client <reviewer_client>] \
  [--model <model>] \
  [--timeout-seconds <seconds>]
```

`--notes` is required. `--spec` MUST be provided at least once. The default review profile SHOULD be `consistency` because the primary use case is boundary, terminology, authority, and artifact consistency across already-authored specs. Operators MAY choose another review profile when the change intent is narrower, but the audit remains reviewer-only.

Audit notes MUST be human-readable Markdown and SHOULD contain:

```markdown
# Change Intent

# Expected Boundary

# Specs To Check

# Out Of Scope
```

The Orchestrator MUST build a self-contained `audit_brief.md` from the audit notes and listed specs. The brief MUST include:

- source audit notes path and content
- each spec path, canonical text hash, and full text content
- profile name
- explicit instruction that the Reviewer evaluates only the stated change intent and expected boundary
- explicit instruction that unrelated convergence, polish, and post-change improvements are out of scope unless they directly contradict the stated boundary

The Orchestrator MUST write audit artifacts under:

```text
<audit_root>/change_audit/
```

Required artifacts:

```text
audit_manifest.json
audit_brief.md
change_audit_feedback.json
change_audit_report.json
change_audit_report.md
```

`audit_manifest.json` MUST bind the inputs:

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

Terminology note:

- `audit-change` is the CLI command and workflow name.
- `audit_change` is the prompt-context phase label used to tell the Reviewer this is not Phase 1 or Phase 2.
- `change_audit/` is the artifact directory under the audit root.
- `change-audit-*` prefixes are schema-version identifiers.

`change_audit_feedback.json` MUST use canonical `reviewer_feedback.json` shape with `round_number = 1`, `phase = audit_change` by prompt context, and `profile` equal to the selected audit profile. The `draft_hash` MUST be the canonical text hash of `audit_brief.md`, not any individual source spec.

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

`feedback_counts` MUST count in-scope feedback only. Out-of-scope feedback MUST be represented by `out_of_scope_feedback_ids` and preserved in `change_audit_feedback.json`, but it MUST NOT increment `feedback_counts`.

Verdict mapping:

- `pass`: zero in-scope feedback items.
- `pass_with_minor_clarification`: one or more in-scope `minor` or `nit` items and zero in-scope `major` or `blocker` items.
- `needs_revision`: one or more in-scope `major` items and zero in-scope `blocker` items.
- `blocked`: one or more in-scope `blocker` items.
- `audit_failed`: readable audit inputs were assembled, but the Reviewer artifact could not be produced or validated, or the audit setup failed after preflight.

`boundary_preserved` MUST be:

- `true` for `pass` and `pass_with_minor_clarification`
- `false` for `needs_revision` and `blocked`
- `null` for `audit_failed`

`failure_reason` MUST be non-null when `verdict = audit_failed`; otherwise it MUST be null.

Recommended next action mapping:

- `pass`: `none`
- `pass_with_minor_clarification`: `manual_patch`
- `needs_revision`: `manual_patch` or `run_focused_whetstone`
- `blocked`: `run_focused_whetstone` or `run_full_whetstone`
- `audit_failed`: `fix_audit_setup`

`audit-change` MUST NOT mutate any listed source spec. It MUST NOT write `spec.md`, `spec.history.md`, `rounds/run_state.json`, `convergence_declaration.md`, or apply-back artifacts. It MAY reuse Reviewer clients, reviewer artifact validation, controlled vocabulary, canonical issue identity, and telemetry helpers, but the resulting artifacts are scoped to `change_audit/`.

If the Reviewer returns valid out-of-scope feedback, the Orchestrator MUST preserve it in `change_audit_feedback.json` and list it in `out_of_scope_feedback_ids`. Out-of-scope feedback MUST NOT affect `feedback_counts`, `verdict`, `boundary_preserved`, or `recommended_next_action`.

The human-readable `change_audit_report.md` MUST include the verdict, boundary-preserved value, in-scope feedback counts, recommended next action, and a concise grouped list of in-scope findings. It MUST NOT add new semantic findings beyond the persisted reviewer feedback.

## SPEC DECOMPOSITION WORKFLOW

Spec decomposition splits an overloaded source spec into a governed spec family while preserving normative content, source provenance, and authority boundaries.

Decomposition MUST NOT assume the source spec is already an HLD. The source spec may be an architecture spec, workflow spec, protocol spec, artifact/schema spec, rubric spec, implementation spec, or any other document that has accumulated multiple separable authority surfaces.

Decomposition trigger thresholds are advisory calibration seeds, not empirical guarantees or convergence requirements. Default thresholds SHOULD be conservative under-triggering starting points: high enough that ordinary medium-sized specs are not decomposed unexpectedly, but low enough to flag documents whose size, section count, cross-reference density, or authority-surface count makes lossless ownership review difficult. If an implementation ships numeric defaults such as section-count, line-count, or cross-reference-density thresholds, the defaults MUST be documented as seed values expected to be refined from observed Whetstone runs, and operator overrides SHOULD be persisted with the resulting decomposition plan or run artifacts.

Definitions:

- `source_spec`: the original spec being considered for decomposition.
- `target_spec`: any spec produced by an approved decomposition.
- `coordinating_spec`: an optional target spec that owns orientation, cross-spec relationships, shared terminology, and authority routing for a decomposed family.
- `leaf_spec`: a target spec that owns detailed requirements for one bounded subsystem, workflow, artifact family, protocol, rubric, or other authority surface.
- `peer_spec`: a target spec in a peer-family split where no coordinating target spec is produced.
- `decomposition_manifest`: the authoritative artifact recording source-to-target provenance, hashes, authority topology, and coverage status.
- `extractable_unit`: the smallest source unit the decomposition plan may assign to a target spec.

Extractable units:

- A leaf section is an extractable unit.
- A non-leaf section is a container by default and MUST NOT be assigned directly.
- A non-leaf section MAY produce a synthetic `intro` extractable unit for direct body content before its first child heading.
- Extractable-unit `section_id` values MUST be stable across source spec title/version changes; the decomposition planner MUST NOT include the document H1 title in generated child section IDs.
- An `intro` unit exists only when the direct body content is meaningful. Meaningful direct body content contains at least one normative token, a code block, a table, a list, or more than a trivial implementation-defined token threshold.
- Meaningless connective prose such as "This section defines the following" SHOULD remain container scaffolding and SHOULD NOT create an extractable unit.
- Meaningful direct body content after a non-leaf section's child sections is invalid for decomposition planning. The planner MUST reject it rather than create an `outro` unit in the MVP implementation.

Authority topology MUST be one of:

- `coordinated_family`: one coordinating spec plus one or more leaf specs.
- `peer_family`: two or more peer specs with no coordinating spec; authority routing is owned by the decomposition manifest or an existing external index.
- `parent_child`: one parent spec remains authoritative for shared flow/intent while child specs own bounded details.
- `appendix_extraction`: one or more detailed appendices, schemas, rubrics, or artifact contracts are extracted while the source spec remains primary for the surrounding behavior.
- `no_split`: the plan determines the source spec should remain a single authority.

Decomposition phases:

1. `plan`
   - Inventory headings, section IDs, extractable units, source line ranges, normative statements, artifacts, schemas, roles, states, and cross-references.
   - Propose target specs, authority topology, extractable-unit assignments, and known duplicated/shared concepts.
   - When run without an operator-supplied map, planning MUST write `decomposition_map_template.json` beside the plan artifacts.
   - The map template MUST include the current `source_spec_hash`, legal enum values, every extractable unit, and a blank target-spec shape suitable for agent-assisted map drafting.
   - MUST NOT mutate the source spec or write target specs.

2. `approve`
   - Operator reviews and approves a specific decomposition plan.
   - Approval MUST bind the source spec hash, plan hash, target paths, authority topology, and extraction mode.
   - Approval MUST re-read the current source spec and reject approval if its current hash differs from the plan's `source_spec_hash`.
   - Approval MUST persist `operator_approval.approved = true`, `approved_by`, `approved_at`, and `approved_plan_hash`.
   - Approval MUST set `planning_mode = approved_split`.
   - `approved_plan_hash` MUST be computed from the approval-bound plan content excluding `operator_approval` metadata, with `planning_mode` normalized to `approved_split`.
   - Re-running approval for the same unchanged plan SHOULD be idempotent.
   - Extraction MUST NOT run without an approved plan.

3. `extract`
   - Create target specs by copy-first extraction from the source spec.
   - Extraction MAY add minimal provenance headers, target titles, and backreference placeholders.
   - Extraction MUST NOT paraphrase, summarize, reorder normative content, or silently remove requirements.
   - Extraction MUST preserve readable heading hierarchy under each generated target title.
   - If an extracted `intro` unit is included, extraction MUST include the source parent heading as structural context before the intro body.
   - If a standalone child section is extracted without its parent section, extraction MUST normalize copied heading levels so the first copied heading is a top-level target section below the generated target title.
   - Extraction MUST require an approved plan whose `operator_approval.approved_plan_hash` still matches the current plan content.
   - Extraction MUST re-read the source spec and reject extraction if its current hash differs from the approved plan's `source_spec_hash`.
   - Extraction MUST write `decomposition_manifest.json`.

4. `audit`
   - Verify every extractable unit and its normative statements are assigned to at least one target spec, intentionally duplicated, or explicitly retired with rationale.
   - Verify target specs preserve source hashes/ranges in provenance metadata.
   - Verify authority surfaces are not duplicated without an explicit shared-authority or supersession rule.
   - Audit MUST write `coverage_matrix.md`.
   - Audit MUST write `unmapped_requirements.md` when extractable units or normative units are unmapped.
   - Audit MUST write `duplicated_authority_report.md` when the same extractable unit appears in more than one target spec without an explicit duplication authority model.
   - Audit MUST update `decomposition_manifest.json.coverage_status`.
   - Audit MUST fail when target files are missing, target hashes drift, provenance headers are missing, source hash drifts, normative units are unmapped, or extractable units are duplicated.

5. `promote`
   - Mark the decomposed spec family as authoritative only after the audit succeeds and the operator accepts the decomposition manifest.
   - Before promotion, the source spec remains authoritative.
   - Promotion MUST require `coverage_status = complete`.
   - Promotion MUST require an `audit` object with no issues, a matching source hash, and passing target existence, target hash, and provenance checks.
   - Promotion MUST persist `promoted = true`, `promoted_at`, `promoted_by`, and `promotion_manifest_hash`.
   - Promotion MUST NOT mutate the source spec or extracted target specs.

Decomposition plan inputs:

- `source_spec_path`
- `source_spec_hash`
- optional operator-supplied decomposition map
- optional target spec path map
- optional authority topology preference
- optional extraction mode
- optional explicit retired-extractable-unit list

Decomposition plan outputs MUST include:

```yaml
schema_version: string
source_spec_path: string
source_spec_hash: string
planning_mode: inventory_only | proposed_split | approved_split
authority_topology: coordinated_family | peer_family | parent_child | appendix_extraction | no_split
extraction_mode: copy_first
target_specs:
  - target_spec_id: string
    target_spec_path: string
    target_spec_role: coordinating_spec | leaf_spec | peer_spec | appendix_spec
    owned_authority_surfaces: [string]
    source_units:
      - section_id: string
        scope: section | intro
        unit_id: string
    source_section_ids: [string] # derived compatibility field listing sections represented by source_units
    source_line_ranges:
      - unit_id: string
        section_id: string
        scope: section | intro
        start_line: integer
        end_line: integer
    normative_statement_count: integer
extractable_units:
  - unit_id: string
    section_id: string
    scope: section | intro
    start_line: integer
    end_line: integer
    normative_statement_count: integer
coverage:
  source_section_count: integer
  extractable_unit_count: integer
  assigned_extractable_unit_count: integer
  unassigned_extractable_unit_ids: [string]
  retired_extractable_unit_ids: [string]
  duplicated_extractable_unit_ids: [string]
  assigned_source_section_count: integer
  unassigned_source_section_ids: [string] # compatibility alias for unassigned_extractable_unit_ids
  retired_source_section_ids: [string] # compatibility alias for retired_extractable_unit_ids
  duplicated_source_section_ids: [string] # compatibility alias for duplicated_extractable_unit_ids
operator_approval:
  approved: boolean
  approved_by: string | null
  approved_at: string | null
  approved_plan_hash: string | null
```

Inventory-only planning MUST also write `decomposition_map_template.json`.

The map template is not an approved plan and is not an executable extraction recipe. It is an agent/operator drafting aid. It SHOULD include:

```yaml
schema_version: string
template_kind: decomposition_map_template
source_spec_path: string
source_spec_hash: string
planning_mode: proposed_split
authority_topology: string
authority_topology_options: [string]
extraction_mode: copy_first
extraction_mode_options: [string]
target_spec_role_options: [string]
source_unit_scope_options: [section, intro]
extractable_units:
  - unit_id: string
    section_id: string
    scope: section | intro
    start_line: integer
    end_line: integer
    normative_statement_count: integer
target_specs: []
target_spec_template: object
retired_extractable_unit_ids: [string]
```

Agents and operators SHOULD draft decomposition maps by assigning only `extractable_units` from the current template. The mapped plan command remains the validator; a map template does not bypass source-hash, section-id, container-assignment, duplication, or coverage checks.

Decomposition map inputs SHOULD use structured `source_units`:

```yaml
target_specs:
  - target_spec_id: string
    target_spec_path: string
    target_spec_role: coordinating_spec | leaf_spec | peer_spec | appendix_spec
    owned_authority_surfaces: [string]
    source_units:
      - section_id: string
        scope: section | intro
```

For backward compatibility, a map MAY supply `source_section_ids`, but each listed section MUST be a leaf section. If a map assigns a non-leaf container section through `source_section_ids`, the planner MUST reject the map with a helpful error. Assigning only a parent intro MUST use structured `source_units` with `scope: intro`.

`decomposition_manifest.json` MUST include:

```yaml
schema_version: string
source_spec_path: string
source_spec_hash: string
approved_plan_hash: string
authority_topology: string
extraction_mode: copy_first
target_specs:
  - target_spec_id: string
    target_spec_path: string
    target_spec_hash: string
    target_spec_role: string
    source_units:
      - unit_id: string
        section_id: string
        scope: section | intro
    source_section_ids: [string]
    source_line_ranges:
      - unit_id: string
        section_id: string
        scope: section | intro
        start_line: integer
        end_line: integer
    provenance_header_present: boolean
coverage_status: complete | incomplete
unmapped_requirements_path: string | null
duplicated_authority_report_path: string | null
audit: object | null
promoted: boolean
promoted_at: string | null
promoted_by: string | null
promotion_manifest_hash: string | null
```

`decomposition_manifest.audit` MUST be null before audit runs. After audit runs, it MUST contain:

```yaml
status: passed | failed
audited_at: string
source_spec_hash: string
approved_plan_hash: string
coverage_status: complete | incomplete
target_existence_status: passed | failed
target_hash_status: passed | failed
provenance_header_status: passed | failed
authority_duplication_status: passed | failed
unmapped_unit_count: integer
duplicated_authority_count: integer
issues:
  - issue_id: string
    severity: blocker | major | minor | nit
    category: missing_target | target_hash_drift | missing_provenance | source_hash_drift | unmapped_unit | duplicated_authority | invalid_manifest
    target_spec_id: string | null
    source_unit_id: string | null
    message: string
coverage_matrix_path: string
unmapped_requirements_path: string | null
duplicated_authority_report_path: string | null
```

Promotion validation MUST treat `audit.status = passed`, `coverage_status = complete`, zero blocker/major audit issues, matching `source_spec_hash`, matching `approved_plan_hash`, passing target existence, passing target hashes, passing provenance headers, and passing authority duplication status as required gates. `promoted = true` MUST NOT be written when any required audit gate fails.

Lossless extraction rules:

- The source spec hash MUST match the approved plan hash guard before extraction.
- Target paths MUST be inside the configured project or run root and MUST NOT overwrite existing files unless `overwrite_targets = true` is explicitly approved.
- Target paths MUST be resolved against an explicit extraction root or the plan directory and MUST NOT escape that root.
- Every copied section MUST preserve its original prose except for heading-level normalization and provenance headers.
- Any summarization, paraphrase, deduplication, terminology normalization, or authority rewrite MUST be deferred to later Whetstone review of the extracted target specs.
- Extraction MUST preserve code blocks, tables, enum values, examples, MUST/SHOULD/MAY language, artifact paths, schema snippets, and rationale notes.
- If a non-leaf section contains meaningful direct intro content, that content MUST be assigned through its synthetic `intro` unit or explicitly retired.
- If a non-leaf section contains meaningful direct trailing content after child sections, planning MUST fail until the source is restructured.
- Extractable units MUST form an exact partition across target specs unless duplication is explicitly introduced by a future non-MVP authority model.

Coverage invariants:

- Every extractable unit MUST have one of: assigned, duplicated, retired, or unassigned.
- Every normative statement inside an extractable unit MUST have one of: assigned, duplicated, retired, or unmapped.
- Decomposition audit MUST fail when any normative statement remains unmapped.
- Retired normative content MUST include an operator-approved rationale.
- Duplicated authority MUST include a precedence, shared-authority, or future-reconciliation rule.

Failure handling:

- Planning failure MUST NOT mutate the source spec or target specs.
- Extraction MUST halt if the source hash no longer matches the approved plan.
- Extraction MUST halt if target paths are invalid or would overwrite unapproved files.
- Audit MUST fail if coverage is incomplete, target hashes are missing, provenance headers are missing, or duplicated authority lacks a rule.
- Promotion MUST fail unless the audit is complete and operator approval is present.

The decomposition workflow is separate from normal review convergence. A decomposed target spec MAY later enter Whetstone review as a normal source spec. Decomposition artifacts are provenance artifacts; they do not by themselves imply that any target spec has converged.

---

## EXPANDING CONTRACT SURFACE

`EXPANDING_CONTRACT_SURFACE` is a non-terminal diagnostic condition. It means repeated serious findings in one profile indicate that the system is no longer merely patching isolated defects; it is discovering or creating an immature contract family whose schemas, enums, validation rules, failure semantics, mapping tables, ordering rules, artifact semantics, or invocation surfaces need a holistic synthesis pass.

When enabled, the Orchestrator SHOULD evaluate expanding-contract-surface evidence after each successful Phase 1 reviewer/editor round. The detector SHOULD consider:

- number of rounds already spent on the current profile
- count of recent rounds with in-scope blocker or major findings
- clustering of serious findings around contract-bearing concepts such as schemas, validation, failure mapping, ordering, artifacts, checkpoints, replay behavior, or interfaces
- affected sections and feedback IDs across the recent window
- whether new serious findings continue to appear after previous Editor fixes

Detection MUST NOT by itself mark a profile clean, halt the run, or waive accepted-draft requirements.

If detected, the Orchestrator MUST persist:

```yaml
/rounds/contract_surface_report.json:
  detected: true
  type: EXPANDING_CONTRACT_SURFACE
  terminal_effect: none
  action_taken: injected_into_next_round_context | report_only
  next_round_number: integer | null
  requires_operator_action: false
  synthesis_pass_executed: false
  lifecycle_status: synthesis_pass_recommended | resolved_by_later_rounds | still_open | operator_review_recommended
  resolution_round_number: integer | null
  round_number: integer
  profile: string
  draft_hash: sha256
  profile_rounds_observed: integer
  recent_window: integer
  serious_recent_rounds: integer
  contract_families: [string]
  affected_sections: [string]
  suspected_feedback_ids: [string]
  round_evidence: [object]
  recommendation: synthesis_pass_recommended
  synthesis_scope:
    sections: [string]
    contract_families: [string]
    instruction: string
```

`terminal_effect` MUST be `none` for this version. `EXPANDING_CONTRACT_SURFACE` is advisory only: it does not halt execution, skip a profile, mark a profile clean, waive accepted-draft requirements, or imply that a synthesis pass has already occurred.

When `action_taken = injected_into_next_round_context`, the Orchestrator MUST expose the report to the next matching Editor round as a context file and set `next_round_number` to the first round where the report is expected to be available. This action is prompt context injection, not an automatic synthesis pass. `synthesis_pass_executed` MUST remain `false` unless a future explicit synthesis-pass workflow is implemented and actually run.

`contract_surface_report.md` SHOULD summarize the same information for operators, including terminal effect, action taken, next round, operator-action requirement, whether synthesis was executed, lifecycle status, and resolution round.

The Orchestrator SHOULD update `lifecycle_status` as later rounds complete:

- `synthesis_pass_recommended`: initial detected state when the report is injected into future Editor context.
- `resolved_by_later_rounds`: a later round for the same profile produced clean Reviewer feedback after the report was generated.
- `still_open`: later profile rounds have occurred, but no later clean Reviewer pass has resolved the surface.
- `operator_review_recommended`: the run reached terminal state while the surface remained unresolved or ambiguous.

When a matching `contract_surface_report.json` exists for the active profile, Editor prompts MAY include timeout-aware bounded synthesis guidance. A resumed Editor prompt after timeout SHOULD tell the Editor to read the contract surface report, prefer bounded synthesis over the report's listed sections and contract families, preserve global coherence, and still return `draft_after_content` as the complete revised draft text.

The initial action is `recommend_synthesis`, which currently means "recommend and prepare bounded synthesis by injecting the report into the next applicable Editor context." Future versions MAY add automatic synthesis-pass scheduling, but automatic synthesis MUST remain explicit in configuration and MUST NOT silently replace normal profile review.

---

## DECISION SUMMARY

Decision summary artifacts are operator-facing review aids derived from `decision_register.json`.

The Orchestrator MUST NOT use decision summary artifacts as authority for convergence, halt selection, conflict escalation, oscillation detection, draft mutation, or replay. The decision register remains the authoritative decision-point artifact.

When `decision_points.summary.enabled = true` and at least one decision point is captured, the Orchestrator MUST produce:

- `/rounds/decision_summary.json`
- `/rounds/decision_summary.md`

The mechanical portion of the decision summary MUST be deterministic and MUST be derivable solely from persisted decision-point artifacts and run metadata.

The mechanical summary MUST include these grouping surfaces:

```yaml
generated_at: string
source_register_path: string
terminal_state: string
decision_point_count: integer
decision_status_counts: object
unresolved_human_decision_count: integer
section_clusters:
  - cluster_id: string
    section_family: string
    affected_sections: [string]
    decision_ids: [string]
    round_numbers: [integer]
    profiles: [string]
    trigger_counts: object
    decision_type_counts: object
    representative_questions: [string]
round_profile_clusters:
  - cluster_id: string
    round_number: integer
    profile: string
    decision_ids: [string]
    trigger_counts: object
    decision_type_counts: object
trigger_clusters:
  - cluster_id: string
    trigger_type: string
    decision_ids: [string]
    affected_sections: [string]
    round_numbers: [integer]
interpretive_summary: object | null
```

`section_clusters` MUST group decision points by document topology, not by semantic guesswork:

- For numbered Markdown sections, `section_family` MUST be the first numeric section component from the first affected section, e.g. `13` for `13.2 Duplicate Identity`.
- For unnumbered sections, `section_family` MUST be the normalized top-level affected section text.
- If a decision point has multiple affected sections, the first affected section in persisted order is the primary grouping anchor; all affected sections MUST still be listed in the cluster.
- Cluster ordering MUST be deterministic: numeric section families in numeric order, then nonnumeric section families lexicographically.

`round_profile_clusters` MUST group decision points by `(round_number, profile)` and MUST sort by `round_number` ascending, then `profile` lexicographically.

`trigger_clusters` MUST group decision points by each value in `trigger_types` and MUST sort by `trigger_type` lexicographically.

Within every cluster:

- `decision_ids` MUST be sorted lexicographically.
- `affected_sections` MUST be de-duplicated and sorted by first observed source order.
- `round_numbers` MUST be de-duplicated and sorted ascending.
- `profiles` MUST be de-duplicated and sorted lexicographically.
- `trigger_counts` and `decision_type_counts` MUST use deterministic key ordering.
- `representative_questions` MUST contain at most three questions, selected by the cluster's decision order after sorting by `(round_number, decision_id)`.

The human-readable `decision_summary.md` MUST clearly separate:

- mechanical counts and clusters
- optional interpretive summary, if present

Mechanical summary text MUST NOT claim semantic theme authority beyond section family, round/profile, trigger type, and directly quoted or paraphrased decision-point fields.

If `decision_points.summary.include_interpretive_summary = false`, then `interpretive_summary = null`.

If `decision_points.summary.include_interpretive_summary = true`, the interpretive summary MAY be produced by an AI client, but it MUST obey these constraints:

- It MUST consume the mechanical summary as input, not raw draft-only context.
- It MUST preserve and cite decision IDs for every interpreted theme.
- It MUST NOT invent decision points, affected sections, approvals, rejections, or source claims.
- It MUST be labeled non-authoritative in both JSON and Markdown.
- It MUST include the client name, version, model, prompt snapshot path, and timestamp used to produce it.
- Failure to produce an interpretive summary MUST NOT invalidate the mechanical summary.

Decision summary generation MUST be read-only with respect to `spec.md`, `spec.history.md`, `convergence_declaration.md`, and all per-round artifacts.

`decision_intervention_request.json` MUST contain:

```yaml
terminal_state: PAUSED_DECISION
generated_at: string
round_number: integer
profile: string
draft_hash: string
decision_points: [decision_point]
recommendation: choose_option | modify_draft_manually | lower_threshold | continue_record_only
```

`unresolved_issues.json` MUST contain:

```yaml
round_number: integer
draft_hash: string
unresolved_issues:
  - issue_id: string
    issue_fingerprint: string
    normalized_severity: blocker | major | minor | nit
    affected_sections: [string]
    claim: string
    in_scope: boolean
    blocking_acceptance: boolean
```

`in_scope` in `unresolved_issues.json` is copied from the source feedback item or set by the Orchestrator when it converts a non-feedback condition into an unresolved issue.

`blocking_acceptance = true` only when the unresolved issue's `normalized_severity` is `blocker` or `major` and `in_scope = true`. `blocking_acceptance = false` for minor, nit, accepted rubric gaps under permissive target policy, and out-of-scope feedback. `blocking_acceptance` is the machine-readable indicator used to explain why an issue prevents accepted-draft status; it does not replace the accepted-draft definition.

`rubric_gaps.json` MUST be produced in Phase 2 and MUST contain:

```yaml
round_number: integer
draft_hash: string
rubric_content_hash: string
rubric_gaps:
  - gap_id: string
    gap_fingerprint: string
    rubric_anchor: string
    affected_sections: [string]
    normalized_severity: blocker | major | minor | nit
    claim: string
    evidence: string
    recommendation: string
    status: unresolved | accepted | resolved
    blocking_convergence: boolean
```

Each rubric gap represents exactly one target-rubric requirement that is missing, contradicted, unverifiable, or explicitly accepted under a permissive target.

`blocking_convergence` MUST be computed from target policy and gap status:
- If `status = resolved`, then `blocking_convergence = false`.
- If `status = accepted`, then `blocking_convergence = false` only when the target matrix permits accepted rubric gaps for the current target.
- If `status = accepted` and the target matrix does not permit accepted rubric gaps for the current target, then `blocking_convergence = true`.
- If `status = unresolved`, then `blocking_convergence = true`.

For `final/strict`, every rubric gap with `status = unresolved` or `status = accepted` is blocking because final/strict forbids unresolved rubric gaps and does not permit accepted gaps.

For `final/permissive`, rubric gaps with `status = accepted` are not blocking and rubric gaps with `status = unresolved` are blocking.

For `mid` targets, rubric gaps are evaluated only when the target rubric explicitly applies to the mid target. If the rubric requirement applies, `status = unresolved` is blocking and `status = accepted` is blocking only when the target matrix forbids accepted gaps for that mid target.

Rubric gap fingerprint:

```text
gap_fingerprint = SHA256(
  normalized(rubric_anchor) + "\n" +
  normalized(affected_sections) + "\n" +
  normalized(claim)
)
```

`gap_id` is a deterministic alias:

```text
gap_id = "gap_" + first_16_hex_chars(gap_fingerprint)
```

`unresolved_rubric_gaps` in convergence evaluation and failure reports is the ordered subset of `rubric_gaps` where:
- `status = unresolved`, and
- `blocking_convergence = true`.

Rubric gap ordering MUST be deterministic:
1. source order of `rubric_anchor` in `convergence_rubric.md`
2. source order of the first affected section in `spec.md`
3. `gap_id` lexicographically

Terminal report schemas MUST include all fields listed in their failure-handling sections plus `terminal_state`, `generated_at`, `round_number`, and `draft_hash`.

`conflict_report.json` MUST contain:

```yaml
terminal_state: HALTED_CONFLICT | null
generated_at: string
round_number: integer
draft_hash: string
conflicts:
  - conflict_id: string
    conflict_fingerprint: string
    conflict_type: architectural_conflict | prior_decision_conflict | profile_conflict | rubric_conflict | ambiguous_feedback | out_of_scope_feedback
    conflict_claim: string
    participating_issue_ids: [string]
    participating_issue_fingerprints: [string]
    conflict_severity: blocker | major | minor | nit
    first_seen_round: integer
    last_seen_round: integer
    consecutive_count: integer
    total_count: integer
    escalated: boolean
    blocker_level: boolean
    manual_review_required: boolean
    recommendation: freeze_prior_decision | continue_once | manual_review_required | stop_iteration
```

When conflict escalation does not halt execution, `terminal_state` MUST be null. When blocker-level conflict escalation halts execution, `terminal_state` MUST be `HALTED_CONFLICT`.

`config_validation_error.json` MUST contain:

```yaml
terminal_state: CONFIG_INVALID
generated_at: string
invalid_fields:
  - path: string
    reason: string
```

`artifact_validation_error.json` MUST contain:

```yaml
terminal_state: HALTED_ARTIFACT_INVALID | HALTED_CLIENT_TIMEOUT
generated_at: string
round_number: integer
phase: phase_1 | phase_2
profile: string
client_role: reviewer | editor
client:
  name: string
  version: string
  model: string
failure_type: artifact_validation | client_timeout | client_error
attempts:
  - attempt_number: integer
    artifact_name: string
    validation_errors: [string]
    raw_response_path: string | null
retry_exhausted: boolean
last_valid_draft_hash: string
last_valid_draft_path: string
recommendation: retry_with_simpler_schema | switch_client | manual_review_required
```

---
