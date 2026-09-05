# Candidate Editing And Promotion Spec

Status: vNext design draft

Version: `0.3`

Activation: non-operative until ratified by the Whetstone coordinating spec and backed by version-pinned public contracts and conformance tests.

The separately gated [current-runtime preservation bridge](#current-runtime-preservation-bridge) specifies the near-term full-draft contract. It does not activate the vNext patch, verifier, registration, or promotion protocols elsewhere in this document. Neither capability is implemented merely by publishing these specifications.

## Purpose

This leaf defines the safety boundary between model-proposed specification edits and the verified draft that Whetstone may use as authority.

The governing principle is:

> Editor output is an untrusted change proposal. Only a verified candidate may become the current verified draft.

This leaf replaces whole-document Editor authority with a transactional pipeline:

```text
current verified draft
  -> classified findings and mutation plan
  -> section-addressed patch proposal
  -> assembled unverified candidate
  -> deterministic validation
  -> independent semantic verification
  -> atomic promotion or rejection
```

At no point before promotion may a proposed patch, assembled candidate, Editor resolution claim, or verifier attempt replace the current verified draft or seed a later editing round.

## Activation And Compatibility

This document is a design draft. It does not change the behavior or authority of the current implementation by existing alone.

Ratification requires coordinated amendments to the Whetstone coordinating spec and the leaves that own scheduler state, artifact validation, scope and decisions, Phase 2 convergence, and apply-back. Until those amendments are ratified:

- current runtime behavior remains governed by the existing spec family;
- this document MUST NOT be cited as evidence that automatic candidate promotion is implemented;
- operators SHOULD keep automatic full-draft editing disabled for valuable specifications;
- reviewer-only workflows remain the safe default for unfamiliar, prospective, or authority-dense specifications.

After ratification, this leaf owns:

- the trust boundary around Editor output;
- stable section identity for patch targeting;
- mutation plans and section-addressed patch operations;
- candidate assembly and candidate disposition;
- deterministic preservation validation;
- independent semantic candidate verification;
- current-verified-draft promotion;
- candidate-safe retry, resume, and terminal reporting semantics.

This leaf does not own:

- review-profile definitions or severity normalization;
- convergence rubric policy;
- general client invocation and telemetry rules except where candidate safety tightens them;
- the content of operator choices;
- external source-spec apply-back policy except for the verified-candidate eligibility guard;
- decomposition planning or source-to-target authority transfer.

When a ratified version of this leaf conflicts with older whole-document Editor mutation or accepted-draft semantics, the ratified candidate-safety rule is authoritative for editing and promotion. Other leaf specs remain authoritative for their owned surfaces.

## Core Safety Invariant

The current verified draft pointer may advance if and only if all of the following are true:

1. The candidate was assembled from the exact draft referenced by the transaction's base hash.
2. The patch set and every payload artifact validate against their version-pinned contracts.
3. Deterministic structural and preservation validation returns `pass`.
4. Independent semantic verification returns `pass`.
5. Every finding admitted to the transaction has semantic disposition `resolved` for the exact candidate hash.
6. No unresolved operator decision, authority conflict, or scope-change gate applies to the candidate.
7. The candidate hash still identifies the exact bytes evaluated by both validation layers.
8. The transaction's base hash still equals the current verified draft hash at promotion time.
9. Promotion completes through the atomic current-verified-pointer protocol.

Promotion eligibility is the conjunction of conditions 1 through 8:

```text
promotion_eligible(candidate) =
  assembled_from_declared_base
  AND patch_contract_valid
  AND deterministic_validation_passed
  AND semantic_verification_passed
  AND all_admitted_findings_resolved
  AND required_decisions_resolved
  AND candidate_hashes_match
  AND base_hash_is_current
```

Promotion succeeds only when an eligible candidate completes condition 9:

```text
promotion_succeeded(candidate) =
  promotion_eligible(candidate)
  AND atomic_current_verified_pointer_commit_completed
```

`promotion_eligible` is a pre-commit predicate. It does not advance authority. `promotion_succeeded` becomes true only at the atomic current-verified-pointer commit point; no pre-commit artifact, including a candidate-scoped prepared promotion intent, may be reported as completed promotion.

No configuration flag, Editor claim, budget policy, timeout recovery, manual file copy, or legacy accepted-draft status may bypass this invariant in automatic editing mode.

## Terminology

`source specification`
: A specification outside the isolated Whetstone run root. It remains externally authoritative until an explicit apply-back operation succeeds.

`seed draft`
: The normalized initial content imported into a run. It becomes the first current verified draft through an Orchestrator-owned initialization transaction that performs no model-authored mutation.

`current verified draft`
: The only run-local draft authorized to seed review, editing, convergence evaluation, resume, and apply-back eligibility checks.

`accepted draft`
: A quality status defined by the scheduler and review leaves. Acceptance does not imply candidate verification, and candidate verification does not imply profile cleanliness, Phase 1 stability, or convergence.

`proposal`
: An Editor-produced patch set and associated claims. A proposal is never draft authority.

`admitted finding`
: A finding whose entry in the transaction's immutable mutation plan has `admitted_to_editing = true` and whose ID appears in that plan's admitted finding set. The admitted finding set is fixed before Editor invocation and is the single finding population used by patch attribution, semantic verification, and promotion eligibility.

`candidate`
: The deterministic result of applying a validated patch set to its immutable base draft.

`verified candidate`
: A candidate that passed deterministic validation and independent semantic verification for its exact candidate hash.

`promotion`
: The Orchestrator-owned atomic advance of the current verified draft pointer to a verified candidate.

`rejection`
: A terminal disposition for a candidate that failed a required gate. Rejection never changes the current verified draft.

`normative unit`
: A deterministically inventoried unit whose removal, modification, weakening, relocation, or replacement can affect specified behavior.

`protected invariant`
: A typed, enforceable assertion bound to a job, draft, authority scope, or mutation plan.

`ratification delta`
: A report of intentional differences between a prospective mutable target and a present-day authority or downstream ratification target. It is not permission to add compatibility behavior.

## Trust Model And Roles

### Orchestrator

The Orchestrator is the sole authority for:

- draft, patch, payload, candidate, report, and pointer hashes;
- stable section identities and section-identity transfer;
- patch application order and candidate assembly;
- deterministic inventory and preservation comparison;
- candidate disposition;
- promotion and current verified draft selection;
- deciding whether apply-back is permitted.

The Orchestrator MUST treat every model-produced hash, identifier, resolution claim, normative-change classification, and verification conclusion as proposed input until independently computed or validated under the applicable public contract.

### Reviewer

The Reviewer produces findings. Reviewer findings are review evidence, not mutation commands. Findings MUST be classified and admitted to a mutation plan before they may be sent to an Editor as editable work.

### Editor

The Editor proposes section-addressed patch operations. The Editor:

- MUST NOT return a complete replacement draft in automatic editing mode;
- MUST NOT write `spec.md`, a current verified pointer, or promotion artifacts;
- MUST NOT resolve operator-owned decisions;
- MUST NOT expand the mutation surface beyond the mutation plan;
- MUST NOT declare its proposal verified or promoted.

### Deterministic Validator

The deterministic validator is Orchestrator-owned code. It assembles and compares computable structure, identities, hashes, assertions, and preservation units. It MUST NOT call a model to convert a deterministic failure into a pass.

### Semantic Verifier

The Semantic Verifier is a client role separate from the Editor. It evaluates whether the candidate resolves the intended findings without losing unrelated semantics or violating authority. It has no mutation capability.

The Semantic Verifier's response is itself an untrusted client artifact until contextual and schema validation succeed. A valid verifier artifact may authorize promotion only through the candidate-verification policy in this leaf.

### Operator

The Operator owns product choices, authority precedence changes, scope changes, compatibility policy, normative deletion authorization, and any other decision classified as non-editor-fixable.

## Job Modes And Immediate Containment

The job descriptor MUST select exactly one editing mode:

```yaml
editing_mode: reviewer_only | proposal_only | verified_promotion
```

`reviewer_only`
: No Editor or Semantic Verifier is invoked. No candidate is assembled. This MUST be the default for new jobs until the vNext automatic-editing release gate passes.

`proposal_only`
: The Editor may produce a patch proposal and the Orchestrator may assemble and validate a candidate, but promotion is prohibited. This mode is for inspection and soak testing.

`verified_promotion`
: A verified candidate may be promoted under the full invariant in this leaf. This mode MUST remain unavailable unless the implementation advertises a contract-suite version that passed the release gate.

Whole-document replacement MUST be disabled in all three modes. A future manual-recovery command MAY accept a complete replacement only when all of the following are true:

- a human explicitly invokes the recovery command;
- the replacement is stored as an operator-supplied artifact, not Editor output;
- the current verified draft remains unchanged until the replacement passes the same deterministic and semantic gates;
- the terminal report identifies the recovery path and approving operator;
- automatic retries cannot select the recovery path.

## Versioned Job Descriptor

Every vNext run MUST persist an immutable `job_descriptor.json` before review begins.

Minimum fields:

```yaml
schema_version: job-descriptor-v2
job_id: string
created_at: timestamp
editing_mode: reviewer_only | proposal_only | verified_promotion
contract_suite_version: string
parser_contract_version: string
assembler_version: string
inventory_version: string
normalization_version: string
semantic_verifier_policy_version: string
seed_draft:
  path: string
  hash: sha256
authority_map_path: string
authority_map_hash: sha256
scope_contract_path: string | null
scope_contract_hash: sha256 | null
protected_invariants_path: string
protected_invariants_hash: sha256
review_configuration_hash: sha256
source_spec:
  path: string | null
  expected_hash: sha256 | null
```

`job_id` MUST be deterministic from the canonical job inputs and MUST exclude timestamps. A job descriptor MUST NOT be mutated after the first review attempt. Changed job inputs require a new descriptor and new `job_id`.

The descriptor-bound `parser_contract_version`, `assembler_version`, `inventory_version`, and `normalization_version` are the only versions permitted for section identity, candidate identity, candidate assembly, deterministic validation, and resume or replay within the job. An implementation default, installed latest version, or retry-time override MUST NOT replace a descriptor-bound version.

## Explicit Authority Model

Every supplied document MUST be represented by at least one binding in `authority_map.json`. Unlisted files MUST NOT enter Reviewer, Editor, or Semantic Verifier context.

### Authority Roles

Each binding MUST use exactly one controlled role:

```text
mutable_target
normative_authority
ratification_target
implementation_context
donor_reference
informational_reference
excluded
```

Role semantics:

- `mutable_target`: the only content the transaction may modify. vNext P0 supports exactly one mutable target per job.
- `normative_authority`: read-only requirements that constrain the mutable target within declared authority scopes.
- `ratification_target`: a read-only document expected to change later if the prospective target is ratified. Its current contents do not automatically override prospective target behavior.
- `implementation_context`: read-only evidence of present implementation behavior. It is not normative unless a separate normative-authority binding says so.
- `donor_reference`: material that may inspire structure or wording but cannot introduce requirements by itself.
- `informational_reference`: explanatory context with no requirement authority.
- `excluded`: explicitly unavailable to all clients and validators except for recording that exclusion.

Role constraints are deterministic:

- only `mutable_target` may set `mutable = true`;
- `normative_authority` may set `may_introduce_requirements = true` within its declared scopes;
- `ratification_target`, `implementation_context`, `donor_reference`, `informational_reference`, and `excluded` MUST set `may_introduce_requirements = false`;
- `excluded` content MUST NOT be copied into model context or candidate-verification context.

A file serving more than one role MUST use separate bindings with non-overlapping `authority_scopes`. Ambiguous overlap is a configuration error.

### Authority Map Contract

Minimum fields:

```yaml
schema_version: authority-map-v1
job_id: string
bindings:
  - binding_id: string
    path: string
    content_hash: sha256
    role: mutable_target | normative_authority | ratification_target | implementation_context | donor_reference | informational_reference | excluded
    authority_scopes: [string]
    effective_horizon: current | prospective | downstream_ratification | informational
    mutable: boolean
    may_introduce_requirements: boolean
precedence:
  - authority_scope: string
    ordered_binding_ids: [string]
    conflict_policy: pause | target_wins | named_authority_wins
prospective_rules:
  report_ratification_delta: boolean
  introduce_compatibility_policy: allow | forbid | operator_decision
```

The Orchestrator MUST reject an authority map when:

- a required file is missing or its hash does not match;
- a binding marks a non-`mutable_target` document mutable;
- more than one mutable target exists in P0;
- precedence is absent for an authority scope with more than one potentially normative binding;
- precedence references an unknown binding;
- overlapping bindings make the winning authority non-deterministic.

Precedence MUST be declared per authority scope. A single global document order is insufficient when different documents own different surfaces.

When a prospective mutable target intentionally differs from current implementation context or a ratification target, Whetstone MUST report the delta. It MUST NOT invent adapters, dual-model behavior, legacy aliases, transition states, migrations, or compatibility policy unless an applicable authority rule or operator decision explicitly authorizes them.

The minimum prospective report is `ratification_delta.json`:

```yaml
schema_version: ratification-delta-v1
job_id: string
mutable_target_binding_id: string
target_draft_hash: sha256
compared_binding_ids: [string]
deltas:
  - authority_scope: string
    target_section_ids: [string]
    reference_binding_id: string
    delta_type: intentional_future_change | downstream_ratification_required | current_implementation_mismatch | unresolved_authority_conflict
    description: string
    source_finding_ids: [string]
compatibility_policy:
  status: not_needed | authorized | forbidden | operator_decision_required
  decision_response_id: string | null
```

This report is descriptive. It MUST NOT mutate ratification targets or convert their current behavior into compatibility requirements. P0 MAY use semantic-verifier findings to populate descriptions, but the Orchestrator MUST compute paths, hashes, binding identities, and policy status.

## Protected Invariants

The job MUST bind a versioned protected-invariants artifact. Prompt instructions alone do not satisfy this requirement.

Minimum fields:

```yaml
schema_version: protected-invariants-v1
job_id: string
base_draft_hash: sha256
assertions:
  - assertion_id: string
    assertion_type: heading_present | heading_absent | identifier_present | identifier_absent | enum_member_present | table_row_present | section_unchanged | concept_required | concept_forbidden | max_changed_sections | max_changed_normative_units | canonical_model_count
    target_scope: string
    matcher:
      kind: exact | canonical_id | regex | inventory_query | semantic
      value: string | object
    enforcement: deterministic | semantic
    severity: blocking | warning
    rationale: string
    source_authority_binding_ids: [string]
```

Assertions declared with `enforcement = deterministic` MUST use a deterministic matcher. Assertions requiring semantic interpretation MUST use `enforcement = semantic` and MUST be evaluated by the Semantic Verifier. An implementation MUST NOT claim that a lexical substring check proves a semantic concept.

The following controls MUST be expressible as blocking assertions:

- required headings and concepts;
- forbidden terminology and concepts;
- protected command, field, state, role, artifact, and schema identifiers;
- allowed sections to change;
- maximum mutation surface;
- a single canonical model or recurrence model;
- prohibition of compatibility, legacy, transition, migration, or dual-model behavior.

## Finding Classification And Mutation Admission

Every in-scope finding considered for editing MUST be classified before the Editor is invoked.

Allowed classifications:

```text
editor_fixable
operator_decision_required
authority_conflict
scope_change
deferable
```

Only `editor_fixable` findings may enter an automatic mutation plan.

- `operator_decision_required` MUST pause before Editor invocation until a valid decision response resolves the choice.
- `authority_conflict` MUST pause until authority precedence or the conflicting requirement is resolved by an operator-owned artifact.
- `scope_change` MUST pause until a superseding scope contract or explicit scope decision is bound to the job.
- `deferable` MUST remain unresolved and excluded from the mutation plan unless an operator explicitly promotes it into scope. Deferral need not pause unrelated editor-fixable work.

Reviewer-provided classification is advisory. The Orchestrator MUST validate classification against deterministic triggers and the active authority and scope contracts. Ambiguity fails closed as `operator_decision_required`.

When an operator response resolves a non-editor-fixable finding, the Orchestrator MUST create a derived editor-fixable task that cites both the original finding and the decision response. It MUST NOT relabel the original historical classification in place. Only the derived task may be admitted to a mutation plan.

Within this leaf, `finding_id` means the Orchestrator-owned canonical `issue_id`. Mutation and verification artifacts MUST also retain the source `feedback_id` values that produced or repeated the issue so operators can trace a proposed change back to exact Reviewer artifacts.

Automatic editing MUST pause before introducing or changing any of the following:

- compatibility or migration policy;
- legacy aliases or dual-model behavior;
- authority precedence;
- component or document scope;
- requirement weakening;
- deletion of normative behavior;
- a product, policy, security, safety, or operability choice with multiple viable answers.

## Operator Decision Response

An operator decision MUST be persisted as a versioned artifact before it can change mutation eligibility.

Minimum fields:

```yaml
schema_version: operator-decision-response-v1
job_id: string
response_id: string
decision_id: string
decision_request_hash: sha256
base_draft_hash: sha256
authority_map_hash: sha256
scope_contract_hash: sha256 | null
selected_option_id: string
authorized_effects: [string]
authorized_deletion_unit_ids: [string]
rationale: string
decided_by: string
decided_at: timestamp
```

A response ID MUST be computed by the Orchestrator from the decision request hash, bound input hashes, selected option, authorized effects, authorized deletion unit IDs, rationale, and deciding actor. The timestamp MUST NOT participate in response identity.

A decision response is invalid when any bound hash differs from the active transaction inputs. An invalid or stale response MUST NOT authorize editing or promotion.

## Mutation Plan

The Orchestrator MUST create and validate `mutation_plan.json` before invoking the Editor.

Minimum fields:

```yaml
schema_version: mutation-plan-v1
job_id: string
transaction_id: string
base_draft_hash: sha256
authority_map_hash: sha256
scope_contract_hash: sha256 | null
protected_invariants_hash: sha256
finding_dispositions:
  - finding_id: string
    source_feedback_ids: [string]
    classification: editor_fixable | operator_decision_required | authority_conflict | scope_change | deferable
    admitted_to_editing: boolean
    decision_response_id: string | null
allowed_section_ids: [string]
allowed_operation_types: [string]
max_operations: integer
max_changed_sections: integer
max_changed_normative_units: integer
authorized_deletion_unit_ids: [string]
required_context_binding_ids: [string]
slices:
  - slice_id: string
    target_section_ids: [string]
    dependency_slice_ids: [string]
    admitted_finding_ids: [string]
```

`transaction_id` MUST be deterministic from the job ID, base draft hash, admitted finding IDs, decision-response hashes, and mutation constraints.

The transaction's admitted finding set is exactly the canonical sorted set of `finding_dispositions[].finding_id` values whose `admitted_to_editing` field is `true`. Every `slices[].admitted_finding_ids` value and every patch operation's `addressed_finding_ids` value MUST be a subset of that set. No separate "targeted finding" population exists. Semantic verification MUST emit exactly one `finding_results` entry for every admitted finding, and promotion requires every such entry to have `disposition = resolved` for the candidate hash under review.

The Orchestrator MUST reject a mutation plan that admits any finding whose classification is not `editor_fixable`, references a stale base, exceeds configured mutation budgets, contains a dependency cycle, or authorizes a deletion not backed by an applicable operator decision.

## Stable Section Identity

Heading-path slugs are useful display anchors but are not stable enough to be the sole mutation address. A heading rename, duplicated heading, or insertion can change them.

vNext MUST maintain `section_identity_map.json` with two identities for each section:

- `stable_section_id`: a run-lineage identity used by patch operations;
- `canonical_section_id`: the current heading-path identity used by existing review and oscillation artifacts.

Minimum fields:

```yaml
schema_version: section-identity-map-v1
job_id: string
draft_hash: sha256
parser_contract_version: string
sections:
  - stable_section_id: string
    canonical_section_id: string
    parent_stable_section_id: string | null
    heading_level: integer
    heading_text: string
    preorder_ordinal: integer
    section_hash: sha256
    direct_body_hash: sha256
    status: active | retired
    created_by_operation_id: string | null
    previous_stable_section_id: string | null
```

For the seed draft, stable section IDs MUST be derived by the Orchestrator from the job ID, seed draft hash, document binding ID, and section preorder ordinal. They MUST NOT be supplied by a model.

For verified edits:

- unchanged, moved, or renamed sections retain their stable section ID when the patch operation explicitly preserves identity;
- inserted sections receive an ID derived from the transaction ID and creating operation ID;
- deleted sections are retired and never reused;
- ambiguous identity transfer is a deterministic validation failure;
- manual changes outside the promotion pipeline invalidate the identity map and block resume.

The Markdown parser contract MUST use the job descriptor's `parser_contract_version`. It MUST distinguish actual ATX headings from heading-like text inside fenced code blocks. Parser upgrades require a new parser contract version, conformance fixtures, and a new job descriptor; they MUST NOT alter an existing job's section identities.

## Preservation Inventory

Before invoking the Editor, the Orchestrator MUST inventory the base draft. After candidate assembly, it MUST inventory the candidate with the same inventory version.

The inventory MUST cover at least:

- heading hierarchy and section identity;
- normative statements;
- acceptance criteria;
- tables and table rows;
- enumerated members and list-defined enums;
- commands, flags, fields, states, roles, error codes, terminal states, and artifact names;
- fenced schemas, schema fields, required fields, and enum values;
- explicit preconditions, postconditions, and preimage requirements;
- configured required and forbidden concepts;
- cross-references to other sections and authority documents.

Each inventoried unit MUST include a stable unit ID, unit type, owning stable section ID, canonical content hash, source span, and normative classification.

Seed unit IDs MUST be derived from the seed draft hash, owning stable section ID, unit type, and same-type ordinal within that section. Verified modifications, moves, renames, or strengthenings retain unit identity when the patch and inventory comparison establish one unambiguous predecessor. Inserted units receive identities derived from the transaction ID, creating operation ID, unit type, and payload ordinal. Removed units are retired and their IDs MUST NOT be reused. Ambiguous predecessor mapping is a blocking preservation failure.

Deterministic normative-statement discovery MUST include RFC-style requirement words and configured exact patterns. Semantic requirements without deterministic markers MAY be added by a versioned inventory annotation or semantic assertion, but MUST NOT be silently guessed into deterministic identity.

The preservation comparison MUST classify every base unit as:

```text
unchanged | added | removed | modified | weakened | strengthened | moved | renamed | ambiguous
```

The preservation decision layer MUST then assign every base unit one preservation disposition:

```text
preserved | moved | reworded_equivalent | strengthened | superseded | authorized_deleted | operator_authorized_weakened | unauthorized_deleted | ambiguous
```

Disposition semantics:

- `preserved`: the unit remains present with byte-identical or normalization-equivalent content.
- `moved`: the unit remains present with equivalent semantics under a different valid owning section.
- `reworded_equivalent`: the unit's wording changed, but deterministic comparison or semantic verification confirms that no normative meaning changed.
- `strengthened`: the unit remains present and the change makes the requirement stricter or more explicit without changing authority, scope, or product policy.
- `superseded`: the unit no longer appears as a distinct unit because a new or modified unit covers the same requirement with equal or stronger normative force.
- `authorized_deleted`: the unit is intentionally removed under a valid operator decision and mutation-plan authorization.
- `operator_authorized_weakened`: the exact reduction in normative force is explicitly operator-authorized for the named units and effect. This is successful authorized weakening, not a claim of equivalence or supersession; all other acceptance gates still apply.
- `unauthorized_deleted`: the unit is removed, weakened beyond recognition, replaced by a placeholder, or omitted from the candidate without valid authorization.
- `ambiguous`: the Orchestrator cannot deterministically classify the unit and semantic verification does not provide hash-bound evidence sufficient to resolve it.

`superseded` is permitted only when the report identifies the predecessor unit ID, successor unit ID, admitted finding, allowed mutation surface, and the semantic-verification evidence proving equal or stronger coverage. `superseded` MUST NOT be used to hide broad summarization, section collapse, or deletion of concrete contract details. A superseding unit that changes product policy, authority, lifecycle legality, failure behavior, artifact shape, or acceptance criteria requires an operator decision unless the admitted finding and mutation plan explicitly authorize that exact change.

`unauthorized_deleted` and `ambiguous` are preservation failures for automatic editing. They may produce inspectable candidate artifacts, but they MUST NOT update the current verified draft, mark the candidate verified, satisfy an admitted finding, or permit apply-back.

Character count, line count, document size ratios, and generic similarity scores MAY be advisory signals. They MUST NOT satisfy preservation validation.

Every removed normative unit that is not validly classified as `superseded` MUST:

- be identified by stable unit ID;
- be attributable to at least one admitted finding;
- appear in `authorized_deletion_unit_ids`;
- be authorized by a valid operator decision response;
- be acknowledged by semantic verification.

Every modified, weakened, moved, or renamed normative unit MUST be attributable to an admitted finding and allowed mutation surface. Requirement weakening always requires an operator decision.

Replacing concrete contracts with placeholders, summaries, ellipses, statements that sections are unchanged, or vague references to removed material MUST fail preservation validation even if overall document size remains above a configured threshold.

Large rewrites that may be productively useful but fail preservation MUST be quarantined rather than discarded or accepted. The Orchestrator SHOULD preserve the proposed bytes and related reports for operator inspection, with terminal reporting that explains which units were preserved, superseded, authorized for deletion, unauthorized for deletion, or ambiguous. A registered vNext candidate retains its candidate lifecycle and rejection evidence. Current-runtime full-draft output is instead a `full_draft_rewrite_attempt`, as defined below. Neither rejected form is eligible for Phase 1 stability, Phase 2 convergence, resume-as-current, or apply-back; any later authorized revision must pass the applicable validation path anew.

## Patch Protocol

### Patch Set

The Editor MUST return patch-set metadata. The Orchestrator MUST preserve each raw client response as immutable `proposals/attempts/proposal-attempt-M.json`; an attempt artifact is evidence and is never the authoritative patch set.

After an attempt and all referenced payload hashes pass the client-input contract, the Orchestrator MUST compute all Orchestrator-owned fields, validate the persisted contract, and write the canonical patch set exactly once at `proposals/{proposal_id}/proposed_patch.json`. Substantial Markdown MUST be stored below `proposals/{proposal_id}/payloads/` as content-addressed payload artifacts. This canonical `proposed_patch.json`, and only this file for that `proposal_id`, supplies `patch_set_hash` and candidate-assembly input. A retry that produces different canonical patch bytes receives a different `proposal_id` and path; it MUST NOT overwrite an earlier canonical patch set.

Minimum fields:

```yaml
schema_version: patch-set-v1
job_id: string
transaction_id: string
proposal_id: string
base_draft_hash: sha256
mutation_plan_hash: sha256
editor:
  name: string
  version: string
  model: string
operations: [patch_operation]
declined_findings:
  - finding_id: string
    source_feedback_ids: [string]
    decline_reason: architectural_conflict | ambiguous | out_of_scope | deferred_to_later_round
    rationale: string
editor_claims:
  addressed_finding_ids: [string]
  normative_change_summary: string
```

Client-input and persisted patch contracts MUST be distinct where Orchestrator-owned identities differ. The client-input contract MUST require `proposal_id = null`; any non-null Editor-provided proposal ID is invalid rather than authoritative.

After client-input validation and payload-hash validation, the Orchestrator MUST normalize each payload path to `payloads/{payload_sha256}.md` relative to the proposal root and construct the proposal identity projection from every persisted patch-set field with `proposal_id` fixed to null. No raw-attempt path, timestamp, filesystem root, or eventual proposal directory name may enter this projection.

```text
proposal_identity_bytes = canonical_json_utf8(
  persisted_patch_set_fields_with_proposal_id_null
)

proposal_id = "pro_" + first_16_hex_chars(
  SHA256(proposal_identity_bytes)
)
```

The Orchestrator MUST then inject the computed `proposal_id`, serialize the complete persisted patch set as canonical JSON UTF-8 bytes, and write those exact bytes once at `proposals/{proposal_id}/proposed_patch.json`.

```text
patch_set_hash = SHA256(exact_persisted_proposed_patch_json_bytes)
```

Thus `proposal_id` identifies the normalized patch content under an explicit null-ID projection, while `patch_set_hash` identifies the final persisted bytes containing that computed ID. Candidate identity, validation, resume, and promotion MUST use `patch_set_hash`; they MUST NOT recompute it from the null-ID projection or raw attempt artifact.

An Editor decline is not a patch operation and cannot resolve a finding. If a proposal declines any admitted finding, the Orchestrator MUST reconcile that finding through conflict, decision, scope, or deferral handling before candidate assembly. It MAY create a new mutation plan for independent remaining findings, but it MUST NOT silently drop the declined finding from the existing transaction.

### Patch Operation

Each operation MUST include:

```yaml
operation_id: string
operation_type: replace_section_body | replace_section_subtree | insert_section_before | insert_section_after | append_child_section | delete_section_subtree
target_stable_section_id: string
expected_target_hash: sha256
payload:
  path: string | null
  hash: sha256 | null
addressed_finding_ids: [string]
reason: string
normative_change: none | clarification | add | remove | strengthen | weaken | authority_change | scope_change
preserve_target_identity: boolean
depends_on_operation_ids: [string]
```

Operation semantics:

- `replace_section_body` preserves the target heading and descendant sections and replaces only direct body content between the target heading and its first descendant heading.
- `replace_section_subtree` replaces the target heading, direct body, and all descendants. It is permitted only when the mutation plan explicitly allows subtree replacement.
- `insert_section_before` inserts one payload section immediately before the target subtree.
- `insert_section_after` inserts one payload section immediately after the target subtree.
- `append_child_section` appends one payload section as the final child of the target section and MUST use a heading level exactly one greater than its parent.
- `delete_section_subtree` removes the target and all descendants, requires a null payload, and requires explicit deletion authorization for every removed normative unit.

An operation MUST address at least one admitted finding. `reason`, `addressed_finding_ids`, and `normative_change` are Editor claims and do not satisfy verification by themselves.

Operations claiming `remove`, `weaken`, `authority_change`, or `scope_change` MUST cite a derived editor-fixable finding whose source operator response authorizes that exact effect. Otherwise the proposal is invalid before candidate assembly.

Every operation MUST bind both the full base draft hash through the patch set and the expected target hash through the operation. A stale base or target hash is a deterministic failure.

Payload paths MUST be normalized workspace-relative paths below the proposal's immutable payload directory. Absolute paths, parent traversal, symlinks, paths outside that directory, missing payloads, and payload hash mismatches are artifact-validation failures.

`operation_id` MUST be unique within the patch set and match the versioned patch-contract identifier grammar. Dependency references MUST resolve within the same patch set.

The document root section and synthetic frontmatter section MUST NOT be targets of subtree replacement or deletion in automatic editing mode.

Replacement and insertion payload shape is deterministic:

- a `replace_section_body` payload contains body Markdown only and MUST NOT contain a heading at or above the target level;
- a `replace_section_subtree` payload contains exactly one root section at the target heading level;
- `insert_section_before` and `insert_section_after` payloads contain exactly one root section at the target heading level;
- `append_child_section` contains exactly one root section at the target level plus one;
- any descendant sections in a payload MUST form a valid hierarchy beneath its one payload root.

### Ordering And Overlap

Operations MUST form an acyclic dependency graph. The canonical application order is a stable topological ordering with `operation_id` lexical order as the tie-breaker.

Two operations MUST NOT mutate overlapping base subtrees unless:

- the later operation declares a dependency on the earlier operation;
- the mutation plan explicitly allows the overlap;
- the later operation binds the expected post-operation target hash.

Multiple insertions at one anchor MUST declare ordering dependencies. Implicit response-array ordering is insufficient.

The default transaction policy is atomic patch-set application. No valid subset may be promoted from a failed candidate. Isolation requires creation of a new patch set and candidate from the immutable base.

## Candidate Transaction

### Transaction Preconditions

Before requesting a proposal, the Orchestrator MUST verify:

- the current verified pointer and referenced draft exist and hash correctly;
- the job descriptor, authority map, scope contract, and protected invariants validate;
- the mutation plan base hash equals the current verified draft hash;
- all required decisions are resolved;
- every Editor context file is declared and hash-bound;
- the requested editing mode permits proposal generation.

Failure of a precondition MUST occur before Editor invocation and MUST leave the current verified draft unchanged.

### Proposal Capture

The Editor receives only:

- admitted finding details;
- the affected sections;
- declared dependency context;
- applicable authority bindings;
- applicable protected invariants;
- patch and payload contracts;
- the immutable base and target hashes.

The Editor MUST NOT receive a request to reproduce unrelated sections. Context files are read-only evidence and MUST be recorded with paths, roles, and hashes in the attempt snapshot.

### Candidate Assembly

The Orchestrator MUST:

1. Validate patch metadata and payload hashes.
2. Re-read the current verified base from its immutable artifact path.
3. Verify the base and target preimage hashes.
4. Apply operations in canonical order using the version-pinned assembler.
5. Apply any Orchestrator-owned version stamp as an explicit system operation.
6. Canonicalize the assembled text once under the job descriptor's `normalization_version`.
7. Write `candidate_unverified.md` as an immutable artifact.
8. Compute the candidate hash from the persisted candidate bytes.

The candidate hash evaluated by validators MUST identify the exact bytes eligible for promotion. Promotion-time version stamping, formatting, or cleanup is forbidden because it would create unverified bytes.

Two conforming implementations applying the same validated patch set, payloads, base, and descriptor-bound parser, assembler, inventory, and normalization versions MUST produce byte-identical candidate artifacts and identical candidate hashes.

### Candidate Identity And Disposition

```text
candidate_id = "can_" + first_16_hex_chars(SHA256(canonical_json({
  "transaction_id": transaction_id,
  "base_draft_hash": base_draft_hash,
  "patch_set_hash": patch_set_hash,
  "assembler_version": job_descriptor.assembler_version,
  "normalization_version": job_descriptor.normalization_version
})))
```

Candidate disposition is separate from run terminal state:

```text
CANDIDATE_UNVERIFIED
CANDIDATE_VERIFIED
CANDIDATE_REJECTED
CANDIDATE_PROMOTED
```

Only `CANDIDATE_VERIFIED` may transition to `CANDIDATE_PROMOTED`.

### Candidate Registration And Run-Wide Ordering

Candidate creation order is Orchestrator-owned and independent of content-derived `candidate_id`. Every assembled candidate that becomes visible to status, terminal reporting, or resume MUST be registered by one immutable event at:

```text
rounds/candidate_index/creation-{candidate_creation_ordinal}.json
```

Minimum fields:

```yaml
schema_version: candidate-creation-event-v1
job_id: string
creation_event_id: string
candidate_creation_ordinal: integer
round_number: integer
transaction_id: string
proposal_id: string
candidate_id: string
candidate_path: string
candidate_hash: sha256
candidate_section_identity_map_path: string
candidate_section_identity_map_hash: sha256
initial_disposition_event_path: string
initial_disposition_event_hash: sha256
previous_creation_event_hash: sha256 | null
created_at: timestamp
```

Registration MUST be serialized under the run's single-Orchestrator write lock. Ordinals start at 1, increase contiguously by 1, and bind the exact canonical persisted bytes of the prior creation event through `previous_creation_event_hash`. `creation_event_id` MUST be computed from every field except `creation_event_id` and `created_at`; the persisted event hash includes all fields. Duplicate ordinals, gaps, a broken previous-event hash, duplicate registration of one candidate ID, or a registered candidate path or hash mismatch is `HALTED_ARTIFACT_INVALID`; consumers MUST NOT guess an ordering.

Before allocating a new ordinal, the Orchestrator MUST reconcile any orphan that claims the one next ordinal; it MUST NOT register a later candidate around an unresolved orphan. Under the registration lock it determines the next ordinal and uses that same value in the initial disposition event and creation event.

Candidate assembly and registration commit in this order:

1. Persist and hash the immutable candidate and `section_identity_map_candidate.json`.
2. Persist candidate-local disposition event ordinal 1 with `event_kind = candidate_created`, `previous_disposition = null`, `new_disposition = CANDIDATE_UNVERIFIED`, and the candidate artifact as its source.
3. Persist the next creation event with the exact candidate path and hash, candidate section-identity-map path and hash, and initial disposition-event path and hash.

The creation event is the registration commit point. Its candidate section-identity-map binding is part of registered candidate identity: the map's `job_id`, `draft_hash`, and candidate section inventory MUST match the registered job and candidate bytes. A missing, mismatched, replaced, or corrupt bound map is artifact-invalid even when the candidate bytes still hash correctly.

A candidate directory or initial disposition event not referenced by a valid creation event is an orphan and MUST NOT be selected as latest, resumed, verified, promoted, or reported as registered. Recovery MAY finish the next unoccupied registration ordinal only when the candidate identity, bytes, bound section identity map, initial event, prior creation-event hash, and expected ordinal all validate; otherwise it MUST preserve the orphan for diagnosis and halt artifact-invalid.

Reassembling byte-identical candidate inputs MUST reuse the existing candidate ID, creation event, and creation ordinal. It MUST NOT append a duplicate registration merely because a client or process retry occurred.

The run's `latest_candidate` is the candidate referenced by the highest ordinal in the unique contiguous valid creation-event chain. Terminal reporting, read-only status, pre-commit candidate continuation, and no-claimant promotion selection MUST use that rule and MUST NOT compare candidate IDs, timestamps, proposal attempt numbers, candidate-local event ordinals, or lock-acquisition order across candidates. Resume MUST NOT skip a final latest candidate to continue an older candidate. The only exception is completing the already-reserved promotion protocol for one valid prepared next-ordinal claimant; that recovery does not reopen the claimant's editing or verification. A further editing retry creates or reuses a candidate under the normal registration rule. Post-commit materialization follows the source candidate bound by the current verified pointer even if a later candidate has since registered. Apply-back authority remains the current verified pointer, never the latest-candidate ordering.

## Deterministic Validation

Deterministic validation MUST run against the persisted candidate and immutable base. It MUST produce `preservation_report.json` even when validation fails after candidate assembly.

Validation order:

1. Verify job, transaction, base, patch, payload, candidate, candidate section-identity-map, parser, assembler, inventory, and normalization identities against the job descriptor and candidate creation event.
2. Reapply the patch independently and require the reproduced candidate hash to match.
3. Validate operation targeting, ordering, dependency, overlap, and mutation budgets.
4. Build base and candidate inventories with the descriptor-bound inventory version.
5. Compare heading hierarchy and stable identity transfer.
6. Compare normative and protected units.
7. Evaluate deterministic protected invariants.
8. Verify every change is within allowed sections and attributable to admitted findings.
9. Verify deletion and weakening authorizations.
10. Reject placeholders, unresolved patch markers, forbidden corruption characters, and abbreviated unchanged-section representations.

Minimum preservation report fields:

```yaml
schema_version: preservation-report-v1
job_id: string
transaction_id: string
candidate_id: string
base_draft_hash: sha256
candidate_hash: sha256
candidate_section_identity_map_path: string
candidate_section_identity_map_hash: sha256
patch_set_hash: sha256
parser_contract_version: string
assembler_version: string
inventory_version: string
normalization_version: string
reproduced_candidate_hash: sha256
result: pass | fail
mutation_budget:
  operations_allowed: integer
  operations_observed: integer
  sections_allowed: integer
  sections_observed: integer
  normative_units_allowed: integer
  normative_units_observed: integer
unit_changes:
  - unit_id: string
    unit_type: string
    owning_section_id: string
    change: unchanged | added | removed | modified | weakened | strengthened | moved | renamed | ambiguous
    source_finding_ids: [string]
    authorized: boolean
assertion_results:
  - assertion_id: string
    result: pass | fail | not_applicable
    evidence: string
failures:
  - code: string
    operation_ids: [string]
    section_ids: [string]
    unit_ids: [string]
    message: string
```

Any blocking assertion failure, unattributed normative change, unauthorized deletion or weakening, ambiguous unit identity, non-reproducible candidate hash, or exceeded hard mutation budget MUST produce `result = fail`.

## Independent Semantic Verification

Semantic verification MUST run only after deterministic validation passes. It MUST be a separate client invocation from the Editor and MUST use a role configuration that cannot write draft or patch artifacts.

The Semantic Verifier receives:

- the immutable base draft;
- the patch set and payloads;
- the assembled candidate;
- the candidate's registered section identity map and creation-event binding;
- admitted findings and mutation plan;
- authority map and applicable authority documents;
- protected invariants;
- deterministic preservation report.

The verifier SHOULD NOT receive the Editor's resolved/unresolved conclusion as authority. It MAY receive Editor rationale as a labeled claim.

The verifier MUST answer independently:

- whether each admitted finding was resolved, partially resolved, not resolved, or made worse;
- whether the patch introduced unrelated semantic change;
- whether any base semantics were lost, weakened, obscured, or replaced by placeholders;
- whether authority precedence and prospective-spec rules were followed;
- whether semantic protected invariants hold;
- whether the Editor's normative-change classification was accurate;
- whether operator input is required.

Minimum semantic-verification fields:

```yaml
schema_version: semantic-verification-v1
job_id: string
transaction_id: string
candidate_id: string
semantic_verifier_policy_version: string
base_draft_hash: sha256
candidate_hash: sha256
candidate_section_identity_map_path: string
candidate_section_identity_map_hash: sha256
patch_set_hash: sha256
preservation_report_hash: sha256
verifier:
  name: string
  version: string
  model: string
finding_results:
  - finding_id: string
    disposition: resolved | partially_resolved | not_resolved | made_worse
    evidence: string
unrelated_semantic_change: none | detected | uncertain
lost_or_weakened_semantics: none | detected | uncertain
authority_compliance: pass | fail | uncertain
semantic_assertions:
  - assertion_id: string
    result: pass | fail | uncertain | not_applicable
    evidence: string
normative_change_assessment:
  - operation_id: string
    editor_claim: string
    verifier_assessment: string
    agrees: boolean
operator_decision_required: boolean
uncertainty_resolutions:
  - field_path: string
    policy_rule_id: string
    disposition: reject | operator_decision_required
    decision_id: string | null
verdict: pass | reject | operator_decision_required
rationale: string
```

Automatic promotion requires:

- `verdict = pass`;
- every finding admitted to the transaction has `disposition = resolved`;
- `unrelated_semantic_change = none`;
- `lost_or_weakened_semantics = none`;
- `authority_compliance = pass`;
- every blocking semantic assertion passes;
- `operator_decision_required = false`.

`uncertain` fails closed and MUST be resolved by the job descriptor's versioned semantic-verifier policy. The minimum deterministic mapping is:

- `unrelated_semantic_change = uncertain` maps to `reject`;
- `lost_or_weakened_semantics = uncertain` maps to `reject`;
- `authority_compliance = uncertain` maps to `operator_decision_required` only when the uncertainty identifies a concrete choice among named applicable authorities and supplies a hash-bound decision request; otherwise it maps to `reject`;
- a blocking semantic assertion with `result = uncertain` maps according to its policy rule, and defaults to `reject` unless that rule explicitly declares a hash-bound operator decision gate.

Every uncertain field MUST have one `uncertainty_resolutions` entry naming the applied policy rule. If any entry maps to `reject`, the overall verdict MUST be `reject`. Otherwise, if one or more entries map to `operator_decision_required`, the overall verdict MUST be `operator_decision_required`. An empty, missing, ambiguous, or version-mismatched mapping is artifact-invalid and MUST NOT be interpreted as either verdict. Uncertainty MUST NOT be coerced to `pass` by majority fields or operator waiver.

If a safe patch intentionally addresses only part of a broader finding, the Orchestrator MUST create a narrower derived finding before mutation planning. Partial resolution of the broader original finding cannot satisfy promotion for a transaction that admitted the broader finding itself.

Independence policy MUST be versioned. It MAY require a different model or provider for high-assurance jobs. At minimum, the verifier MUST be a distinct invocation, use a verifier-specific prompt, have no editing tool authority, and produce a separately validated artifact.

The semantic-verification artifact MUST copy the candidate section-identity-map path and hash from the registered creation event. Its result is invalid if that binding or the bound map no longer validates.

## Candidate Verification Decision

The Orchestrator MUST combine both verification layers into an append-only sequence of immutable `candidate_verification-attempt-{decision_ordinal}.json` decision artifacts. It MUST NOT overwrite an earlier decision when semantic verification later completes or resume advances the candidate through another gate.

Minimum fields:

```yaml
schema_version: candidate-verification-v1
job_id: string
transaction_id: string
candidate_id: string
candidate_creation_ordinal: integer
decision_ordinal: integer
previous_decision_hash: sha256 | null
base_draft_hash: sha256
candidate_hash: sha256
candidate_section_identity_map_path: string
candidate_section_identity_map_hash: sha256
patch_set_hash: sha256
preservation_report_hash: sha256
semantic_verification_hash: sha256 | null
deterministic_result: pass | fail
semantic_result: pass | reject | operator_decision_required | not_run
outstanding_decision_ids: [string]
candidate_disposition: CANDIDATE_UNVERIFIED | CANDIDATE_VERIFIED | CANDIDATE_REJECTED
promotion_permitted: boolean
decision_final: boolean
rejection_codes: [string]
decided_at: timestamp
```

This artifact is Orchestrator-owned. Client output MUST NOT set `candidate_disposition` or `promotion_permitted`.

After writing and validating a decision attempt, the Orchestrator MUST commit it with a disposition event under `Candidate Disposition Event Commit Rules`, then atomically update the candidate-scoped convenience pointer `candidate_verification_current.json`:

```yaml
schema_version: candidate-verification-pointer-v1
job_id: string
transaction_id: string
candidate_id: string
candidate_creation_ordinal: integer
current_decision_ordinal: integer
current_decision_path: string
current_decision_hash: sha256
current_disposition_event_path: string
current_disposition_event_hash: sha256
candidate_section_identity_map_path: string
candidate_section_identity_map_hash: sha256
candidate_disposition: CANDIDATE_UNVERIFIED | CANDIDATE_VERIFIED | CANDIDATE_REJECTED
decision_final: boolean
updated_at: timestamp
```

Decision ordinals start at 1 and increase contiguously. The pointer targets are authoritative for the candidate's current verification decision and its corresponding disposition event; the pointer file is not itself a substitute for either immutable target. Both target paths MUST resolve below the same immutable candidate directory and match their recorded hashes. The decision attempt and pointer MUST copy the candidate section-identity-map path and hash from the registered creation event, and validation MUST recheck the bound map before committing either target. The event MUST name the decision attempt as its source artifact, and its `new_disposition` MUST equal both the decision attempt's and pointer's `candidate_disposition`. A pointer update may advance only to the next decision and event ordinals for the same job, transaction, candidate, base, candidate, map, and patch hashes. Every attempt after ordinal 1 MUST bind the prior decision target through `previous_decision_hash`.

If deterministic validation fails, semantic verification MUST NOT run, the candidate disposition MUST be `CANDIDATE_REJECTED`, and `decision_final` MUST be `true`.

If deterministic validation passes but semantic verification is missing, invalid, timed out, inconclusive, or interrupted, the candidate disposition MUST be `CANDIDATE_UNVERIFIED`, `decision_final` MUST be `false`, and promotion MUST remain prohibited. Resume MAY append a higher-ordinal decision for the same candidate after completing the first incomplete gate; it MUST preserve the non-final attempt.

A deterministic-validation pass is a preservation-report milestone, not a candidate disposition. The candidate remains `CANDIDATE_UNVERIFIED` until a final candidate-verification decision establishes `CANDIDATE_VERIFIED` or `CANDIDATE_REJECTED`.

If semantic verification rejects the candidate or requires an unresolved operator decision, the candidate disposition MUST be `CANDIDATE_REJECTED` and `decision_final` MUST be `true`; a new transaction is required to produce a new candidate. An operator decision does not retroactively turn rejected bytes into verified bytes; the resulting patch must be reassembled and both verification layers rerun.

If both validation layers pass and every automatic-promotion semantic requirement holds, the candidate disposition MUST be `CANDIDATE_VERIFIED` and `decision_final` MUST be `true`. A final verification decision MUST NOT be replaced by another verification decision for the same candidate. Later promotion is recorded only through disposition events and the current verified pointer.

Promotion, resume, read-only status, and terminal reporting MUST resolve and hash-check `candidate_verification_current.json` before consuming a candidate decision. Promotion additionally requires `decision_final = true`, `candidate_disposition = CANDIDATE_VERIFIED`, and the selected candidate-scoped promotion intent's `candidate_verification_hash` equal to the current immutable decision target's hash. If the pointer is absent, invalid, stale, or targets a non-final decision, promotion MUST refuse.

## Candidate Disposition Event Commit Rules

Candidate disposition history is an immutable candidate-local hash chain. Each event is stored at `{registered_candidate_directory}/disposition_events/event-{event_ordinal}.json`:

```yaml
schema_version: candidate-disposition-event-v1
event_id: string
job_id: string
candidate_id: string
candidate_creation_ordinal: integer
event_ordinal: integer
event_kind: candidate_created | verification_decision | promotion_committed
previous_event_hash: sha256 | null
previous_disposition: CANDIDATE_UNVERIFIED | CANDIDATE_VERIFIED | CANDIDATE_REJECTED | null
new_disposition: CANDIDATE_UNVERIFIED | CANDIDATE_VERIFIED | CANDIDATE_REJECTED | CANDIDATE_PROMOTED
source_artifact_path: string
source_artifact_hash: sha256
recorded_at: timestamp
```

Event ordinals start at 1 and increase contiguously. `event_id` MUST be computed from every field except `event_id` and `recorded_at`; `previous_event_hash` and all pointer bindings use the SHA-256 hash of the exact canonical persisted prior-event bytes. Gaps, duplicate ordinals, a broken previous-event hash, or an event whose source path and hash do not validate is artifact-invalid.

The only legal event forms are:

- `candidate_created`: ordinal 1, null previous event and disposition, `new_disposition = CANDIDATE_UNVERIFIED`, and the immutable candidate artifact as source;
- `verification_decision`: the next ordinal, the preceding effective disposition as `previous_disposition`, any decision disposition as `new_disposition`, and the immutable candidate-verification attempt as source; an event is required for every committed verification decision even when the disposition remains `CANDIDATE_UNVERIFIED`;
- `promotion_committed`: the next ordinal, `CANDIDATE_VERIFIED` to `CANDIDATE_PROMOTED`, and the immutable promotion intent as source.

Event effectiveness is commit-bound rather than based on directory enumeration:

1. The initial `candidate_created` event becomes effective only when a valid run-wide candidate creation event binds its path and hash.
2. A `verification_decision` event becomes effective only when `candidate_verification_current.json` atomically binds both that event and its source decision attempt.
3. A `promotion_committed` event becomes effective only when `rounds/current_verified.json` atomically binds that event and its source promotion intent while advancing to the same candidate and candidate hash.

For a verification decision, the Orchestrator MUST write and validate the immutable decision attempt at `candidate_verification-attempt-{decision_ordinal}.json`, write and validate its next disposition event, and only then atomically replace `candidate_verification_current.json` with a pointer binding both. For promotion, it MUST use the ordering defined in `Promotion And Current Verified Authority`. A crash before either pointer replacement leaves prepared immutable artifacts but does not change effective disposition.

Before creating a new verification decision, recovery MUST reconcile the one canonical next decision path. A valid next decision attempt without an event requires creation of its exact next event; a valid attempt plus matching event requires completion of the pointer replacement; a pointer already binding both means the decision committed. A conflicting decision at that path, an event with no matching decision source, or multiple artifacts claiming the next decision or event ordinal is artifact-invalid.

Before appending any later event, recovery MUST reconcile a single prepared next event: if its ordinal, previous hash, source artifact, candidate identity, and expected pointer target all match, recovery MUST reuse it and complete the pending pointer replacement; if it conflicts or more than one candidate event claims the next ordinal, recovery MUST halt artifact-invalid. Consumers MUST ignore unbound prepared decisions and events when deriving current disposition, but MUST surface their presence for recovery or diagnosis.

| Lifecycle result | Commit artifact | Effective disposition event |
| --- | --- | --- |
| Candidate registered, no verification decision | Run-wide candidate creation event | Its bound `candidate_created` event |
| Verification incomplete | `candidate_verification_current.json` | Its bound `verification_decision` event with `CANDIDATE_UNVERIFIED` |
| Verification final | `candidate_verification_current.json` | Its bound `verification_decision` event with `CANDIDATE_VERIFIED` or `CANDIDATE_REJECTED` |
| Promotion committed | `rounds/current_verified.json` | Its bound `promotion_committed` event with `CANDIDATE_PROMOTED` |

## Promotion And Current Verified Authority

The authoritative run-local lineage pointer is:

```text
rounds/current_verified.json
```

Minimum fields:

```yaml
schema_version: current-verified-pointer-v1
job_id: string
promotion_ordinal: integer
verified_draft_path: string
verified_draft_hash: sha256
verified_section_identity_map_path: string
verified_section_identity_map_hash: sha256
source_transaction_id: string | null
source_candidate_id: string | null
source_candidate_creation_ordinal: integer | null
source_candidate_creation_event_path: string | null
source_candidate_creation_event_hash: sha256 | null
candidate_verification_path: string | null
candidate_verification_hash: sha256 | null
promotion_intent_path: string | null
promotion_intent_hash: sha256 | null
promotion_disposition_event_path: string | null
promotion_disposition_event_hash: sha256 | null
previous_verified_draft_hash: sha256 | null
previous_verified_pointer_path: string | null
previous_verified_pointer_hash: sha256 | null
promoted_at: timestamp
```

Every canonical pointer version MUST also be persisted byte-identically at `rounds/verified_history/current-verified-{promotion_ordinal}.json`. The snapshot path is derived only from the pointer ordinal. A snapshot is immutable evidence but does not advance authority; only atomic replacement of `rounds/current_verified.json` does. The authoritative current pointer MUST have a byte-identical snapshot at its derived path, and validators MUST walk each snapshot's previous-pointer path and hash to ordinal 0 before accepting the lineage.

The initial pointer and byte-identical ordinal-0 snapshot MUST set `promotion_ordinal = 0`, reference an immutable normalized seed artifact and its immutable seed section identity map, and set all candidate, verification, intent, disposition-event, and previous-pointer fields to null. Every successful candidate promotion MUST set `promotion_ordinal` to exactly the prior pointer's ordinal plus 1 and bind the prior derived snapshot path and exact hash. Reuse, regression, a gap, a broken prior-snapshot binding, or disagreement between the current pointer and its same-ordinal snapshot is artifact-invalid.

Subsequent pointers MUST reference immutable promoted candidate artifacts, copy `verified_section_identity_map_path` and `verified_section_identity_map_hash` from the candidate's registered creation event, and populate every candidate lineage field with mutually consistent paths, hashes, identities, and ordinals. The bound verified section identity map is lineage authority for section-addressed operations against the pointer target; review, editing, resume, Phase 2, and apply-back MUST reject a missing or mismatched map.

`spec.md` becomes a materialized convenience copy of the pointer target, not independent lineage authority. Review, resume, Phase 2 entry, convergence, and apply-back MUST resolve the current verified pointer first and verify any `spec.md` mirror against it.

Promotion preparation and commit MUST be serialized by one run-wide exclusive promotion lock keyed by `job_id`. The promotion critical section and candidate-registration critical section MUST be mutually exclusive for the same job, whether implemented with one shared lock or two storage-enforced conflicting lock modes. The lock MUST be storage-backed, crash-recoverable, and fenced so that a former holder cannot write promotion artifacts after losing ownership. Its acquisition, ownership-validation, loss, reclamation, fencing, and exclusion of concurrent candidate registration are part of the descriptor-bound public contract suite. Only the lock holder may select or create a promotion intent, create its promotion disposition event, publish the next-ordinal pointer snapshot, or replace `rounds/current_verified.json`. Lock loss before pointer replacement MUST stop the attempt without advancing authority; recovery MUST reacquire the lock and reconcile persisted artifacts before continuing.

Before the pointer commit point, the Orchestrator MUST persist one immutable candidate-scoped promotion intent at:

```text
rounds/round-N/candidates/{candidate_id}/promotion_intents/promotion-intent-{next_promotion_ordinal}.json
```

```yaml
schema_version: promotion-intent-v1
intent_id: string
job_id: string
transaction_id: string
candidate_id: string
candidate_creation_ordinal: integer
candidate_creation_event_path: string
candidate_creation_event_hash: sha256
candidate_section_identity_map_path: string
candidate_section_identity_map_hash: sha256
base_draft_hash: sha256
candidate_hash: sha256
candidate_verification_path: string
candidate_verification_hash: sha256
expected_current_verified_hash: sha256
expected_current_verified_pointer_hash: sha256
expected_current_promotion_ordinal: integer
next_promotion_ordinal: integer
status: prepared
prepared_at: timestamp
```

The path is derived from the registered candidate and the current pointer's `promotion_ordinal + 1`; timestamps and directory enumeration MUST NOT select an intent. `expected_current_promotion_ordinal` MUST equal the observed current pointer ordinal, and `next_promotion_ordinal` MUST equal that value plus 1. `intent_id` MUST be computed from every field except `intent_id` and `prepared_at`, and the intent hash MUST cover the exact canonical persisted bytes including both fields. The candidate creation-event path and hash MUST identify the exact run-wide registration selected by `candidate_creation_ordinal`. The candidate section-identity-map path and hash MUST equal that creation event's binding. The candidate verification path and hash MUST identify the final `CANDIDATE_VERIFIED` decision currently bound by `candidate_verification_current.json`. The expected pointer hash MUST identify the exact canonical bytes of `rounds/current_verified.json` observed during preparation and its byte-identical derived history snapshot.

At most one valid intent may exist at the derived candidate-scoped path. Repeated preparation with the same bound inputs MUST reuse the byte-identical persisted intent and MUST NOT rewrite `prepared_at`. If the path already contains different bytes, if multiple files claim the same candidate and next promotion ordinal, or if any bound path or hash mismatches, promotion and resume MUST halt artifact-invalid.

After acquiring the promotion lock, the Orchestrator MUST perform these two reconciliation stages in order.

### Stage 1: Current Committed Lineage

The Orchestrator MUST first re-read and validate `rounds/current_verified.json`, its byte-identical snapshot at the pointer's own `promotion_ordinal`, and the complete previous-pointer chain to ordinal 0. For ordinal 0, it validates the seed initialization and there is no committed promotion intent. For an ordinal greater than 0, it MUST resolve the current pointer's `promotion_intent_path` directly, hash-check that intent and every pointer-bound registration, map, verification, and disposition-event artifact, and require the intent's `next_promotion_ordinal` to equal the current pointer ordinal.

After validating the committed lineage, the Orchestrator MUST compare `spec.md` and the current-pointer fields materialized in run state against the pointer. For an ordinal greater than 0 it MUST also compare the pointer-bound source round's `draft_after.md`; that artifact is not applicable to ordinal-0 seed initialization. If any applicable required materialization is absent or stale, Stage 1 classifies the invocation as seed-materialization recovery at ordinal 0 or post-commit recovery at a later ordinal. The Orchestrator MUST perform only the permitted idempotent materialization actions, then stop that invocation. It MUST NOT scan the next ordinal or prepare another intent as part of the same recovery. If every required materialization already matches, successful current-lineage validation is only a prerequisite and live scheduling or resume proceeds to Stage 2.

An unbound intent whose `next_promotion_ordinal` is less than or equal to the validated current pointer ordinal is stale by ordinal. Earlier stale intents are not enumerated or selected during Stage 2. They MAY be surfaced by an explicit audit or status diagnostic and MUST be validated if directly referenced by an artifact under inspection, but they never affect current authority, `latest_candidate`, or next-ordinal claimant selection.

### Stage 2: Next-Ordinal Claimant

Only after Stage 1 does the Orchestrator derive `next_promotion_ordinal = current_verified.promotion_ordinal + 1`. It MUST inspect that exact ordinal's canonical intent path for every registered candidate in ascending run-wide creation ordinal and inspect the single derived next-ordinal history-snapshot path. Reconciliation MUST produce exactly one of these outcomes:

- No prepared claimant exists. The Orchestrator MUST select the run's `latest_candidate`, defined by the highest valid creation ordinal. It may create an intent only if that exact candidate is registered, its transaction base equals the current verified draft, its current verification decision is final `CANDIDATE_VERIFIED`, and its effective disposition is exactly `CANDIDATE_VERIFIED` rather than already promoted or rejected. If there is no registered candidate or the latest candidate is not eligible, promotion stops without creating an intent; it MUST NOT fall back to an older candidate. Caller choice and lock-acquisition order have no selection authority.
- Exactly one eligible intent exists. Its candidate is the sole prepared claimant, and recovery MUST reuse it, reconcile its optional next disposition event and optional byte-identical next-pointer snapshot in protocol order, and continue its conditional pointer commit before another candidate may prepare. The intent remains the reserved claimant even if a higher creation ordinal was registered after the earlier promotion lock was lost; the later candidate is not a fallback or replacement for that prepared protocol.
- Multiple eligible intents claim the next ordinal, an event exists without its exact intent, a snapshot exists without its exact intent and event, snapshot bytes conflict with the sole claimant, or any other non-prefix combination exists. The state is artifact-invalid.

The only recoverable pre-commit prepared states are prefixes of intent, matching disposition event, and matching next-pointer snapshot for the one claimant. A crash after publishing a valid next-pointer snapshot therefore reserves that ordinal for its bound claimant until the conditional pointer commit is reconciled; another candidate MUST NOT overwrite or bypass it.

An individual prepared intent discovered at the exact Stage 2 next-ordinal path is eligible only if the current verified pointer still matches both expected current hashes, its ordinal equals `expected_current_promotion_ordinal`, and that ordinal plus 1 equals `next_promotion_ordinal`. A mismatch at that exact next-ordinal path is artifact-invalid. Earlier unbound intents are classified as stale only by the Stage 1 ordinal rule. Neither class may be rewritten, promoted, or used to resume candidate verification, and no flag may refresh an intent in place.

Promotion protocol:

The Orchestrator MUST hold the promotion lock continuously from Stage 1 through the conditional pointer replacement. Every stop or post-commit classification before that replacement MUST release the lock without writing another promotion artifact.

1. Acquire the run-wide promotion lock and perform Stage 1 current-lineage validation followed, when applicable, by Stage 2 next-ordinal reconciliation. A Stage 1 post-commit recovery result releases the lock and skips the remaining promotion steps before materialization.
2. While holding the lock, revalidate all gate hashes and require the base hash still to be current.
3. Revalidate the registered immutable candidate and final verification-decision pointer targets.
4. Create or reuse the one eligible immutable candidate-scoped promotion intent selected by reconciliation.
5. Create or reuse the next candidate disposition event with `event_kind = promotion_committed`, source path and hash equal to the intent, and transition `CANDIDATE_VERIFIED -> CANDIDATE_PROMOTED`.
6. Encode the next pointer with `promotion_ordinal = next_promotion_ordinal = expected_current_promotion_ordinal + 1`; bind the prior derived snapshot path and `expected_current_verified_pointer_hash` as `previous_verified_pointer_path` and `previous_verified_pointer_hash`; and bind the candidate registration ordinal and creation-event path and hash, candidate section-identity-map path and hash, final verification path and hash, promotion-intent path and hash, and promotion-disposition-event path and hash. Persist or byte-identically reuse those next-pointer bytes at the derived immutable history-snapshot path.
7. Conditionally and atomically replace `rounds/current_verified.json` with the exact next-pointer snapshot bytes only if its current exact bytes still match `expected_current_verified_pointer_hash`, its ordinal still equals `expected_current_promotion_ordinal`, and the caller still holds the promotion lock. Release the lock after this commit succeeds or the attempt stops.
8. Materialize `spec.md` byte-identically from the pointer target.
9. Write `draft_after.md` byte-identically from the promoted candidate.
10. Update run state from the committed pointer bindings.

The pointer replacement is the authority-advancing commit point and makes the bound promotion disposition event effective. If a crash occurs before it, the previous pointer and prior candidate disposition remain authoritative; the prepared intent, event, and next-pointer snapshot remain unbound and are reconciled under the promotion lock. If a crash occurs after it but before `spec.md`, `draft_after.md`, or run-state materialization completes, recovery MUST treat the promotion as committed, rematerialize from the pointer, and MUST NOT append another promotion event, allocate another ordinal, repair or replace a history snapshot, or roll back to an unverified or ambiguous draft. Because the authoritative pointer replacement uses exact bytes already persisted at its same-ordinal snapshot path, a missing or mismatched committed snapshot is artifact-invalid rather than a repairable post-commit state.

The promoted bytes MUST be byte-identical to the verified candidate bytes. No post-verification mutation is permitted.

## Section-Sliced Operation

Large specifications SHOULD be edited through bounded slices declared in the mutation plan.

Each slice MUST:

- target an explicit set of stable section IDs;
- name admitted findings;
- declare dependency slices;
- receive only affected sections and declared context dependencies;
- use the same immutable transaction base hash;
- produce non-overlapping patch operations unless dependencies explicitly allow overlap.

All slice proposals MUST be assembled into one complete candidate for global deterministic and semantic verification. A locally valid slice is not independently promotable unless it is submitted as its own complete transaction against the current verified base.

Substantial Markdown payloads MUST remain separate from JSON metadata. The Orchestrator MUST record payload sizes and context estimates before invocation and MAY reduce slice size before retrying.

## Preservation-Safe Retry

Invalid output MUST NOT trigger a blind repeat of the same overloaded request.

Retry classes:

`artifact_invalid`
: Retry only the invalid artifact shape using the same base, mutation plan, slice, and context hashes. The retry includes precise validation errors.

`patch_invalid`
: Freeze valid non-overlapping operations by hash, request repairs only for failed operation IDs, and assemble a new patch set from the immutable base. If operation dependencies prevent isolation, reject the full patch set and reduce the slice.

`preservation_failed`
: Return exact affected section IDs, unit IDs, assertion IDs, and failure codes. Retry only when the mutation plan still authorizes a narrower repair. Otherwise stop.

`semantic_rejected`
: Do not edit the rejected candidate in place. Create a new proposal attempt against the same current verified base, restricted to the rejected operations and verifier findings. Reassemble and rerun both verification layers.

`client_timeout`
: Stop. Do not automatically repeat the same request. Preserve the current verified draft and all attempt artifacts.

Every retry MUST preserve:

- the original proposal and candidate;
- attempt-scoped prompt snapshots and telemetry;
- base, plan, context, patch, payload, and candidate hashes;
- precise validation or verification feedback;
- monotonically increasing attempt numbers.

Retry limits MUST be configurable and hard-bounded. Exhaustion MUST stop rather than promote a structurally dubious or semantically uncertain candidate.

## Resume And Replay

Resume authority is the current verified pointer plus immutable transaction artifacts.

Resume MUST:

- verify the job descriptor and contract-suite version;
- verify the current pointer, its byte-identical same-ordinal history snapshot, the complete contiguous snapshot chain to ordinal 0, target draft hash, and bound verified section identity map;
- resolve the current pointer's directly bound lineage at its own ordinal and compare every applicable pointer-derived materialization; when one is absent or stale, classify recovery as seed-materialization recovery at ordinal 0 or post-commit recovery at a later ordinal before selecting `latest_candidate` or applying a transaction-base guard, repair only those materializations, and end the invocation;
- when every current-pointer materialization already matches, validate the unique contiguous run-wide candidate creation-event chain and select `latest_candidate` only by its highest ordinal;
- resolve the selected latest candidate's creation event and require its candidate and section-identity-map paths and hashes to validate;
- classify that candidate's recovery as pre-commit before applying the base-current guard;
- for pre-commit candidate-verification continuation, reconstruct the exact latest candidate from the immutable base, patch metadata, payloads, and the descriptor-bound parser, assembler, inventory, and normalization versions;
- in that continuation path, require the reconstructed candidate hash to match the persisted candidate hash;
- in that continuation path, resolve and hash-check `candidate_verification_current.json` when present, including its immutable target and decision hash chain;
- reuse existing valid deterministic and semantic reports only when all bound hashes match the pre-commit latest candidate;
- when that candidate's current decision is non-final, continue at the first incomplete gate and append `candidate_verification-attempt-{next_decision_ordinal}.json` rather than overwrite the prior decision;
- refuse candidate-verification continuation when that candidate's current decision is final;
- reconcile any single prepared next disposition event under the event commit rules before appending another event;
- before any pre-commit promotion attempt or recovery, acquire the run-wide promotion lock, repeat Stage 1 against the locked current pointer, and then run Stage 2; reuse the sole prepared claimant when one exists, otherwise select the exact locked `latest_candidate` and proceed only if it is final `CANDIDATE_VERIFIED`;
- preserve but never select a stale promotion intent;
- never call an Editor merely to reproduce an already persisted candidate;
- never seed a retry or later round from an unverified or rejected candidate.

Pre-commit recovery applies only after Stage 1 proves the committed pointer lineage and all pointer-derived materializations complete. Before a Stage 2 claimant exists, the pre-commit target MUST be `latest_candidate`; after a valid claimant exists, that reserved candidate remains the target until its prepared protocol is reconciled. In this branch, the transaction base hash MUST equal the current verified draft hash before candidate verification or promotion may continue. A pointer that partially references the target's intent, verification decision, registration event, disposition event, or candidate identity map without satisfying the complete current-lineage predicate is artifact-invalid rather than pre-commit.

Post-commit recovery applies only when the current verified pointer completely and consistently binds its source candidate's creation event and identity map, final verification decision, promotion intent, and promotion disposition event, while at least one required pointer-derived materialization is absent or stale. It does not depend on whether a later `latest_candidate` exists. In this branch:

- the transaction base hash and intent `base_draft_hash` MUST equal `current_verified.json.previous_verified_draft_hash`;
- the pointer's current verified draft hash MUST equal the promoted candidate hash;
- the pointer's `promotion_ordinal` MUST equal the intent's `next_promotion_ordinal`, which MUST equal `expected_current_promotion_ordinal + 1`;
- the pointer's `previous_verified_pointer_path` MUST be the derived history path for `expected_current_promotion_ordinal`;
- the pointer's `previous_verified_pointer_hash` MUST equal the intent's `expected_current_verified_pointer_hash`;
- resume MUST skip all client, validation, decision, and pointer-commit gates and perform only idempotent `spec.md`, `draft_after.md`, and run-state materialization or repair from the committed pointer.

Failure of any post-commit predicate, including absence or mismatch of the committed pointer's byte-identical same-ordinal snapshot, is artifact-invalid. Post-commit recovery MUST NOT reconstruct, replace, or repair pointer-history snapshots. The pre-commit base-current rule MUST NOT be applied after a valid promotion commit.

Resume MUST read every required parser, assembler, inventory, normalization, semantic-verifier-policy, and contract version from the immutable job descriptor. If any descriptor-bound version is unavailable, resume MUST refuse. It MUST NOT silently replay under defaults or newer semantics.

Two implementations resuming the same validated transaction MUST reproduce the same candidate bytes and hashes before either may continue verification or promotion.

## Round Artifact Layout

A mutating vNext run MUST preserve at least:

```text
rounds/
  current_verified.json
  verified_history/
    current-verified-{promotion_ordinal}.json
  candidate_index/
    creation-{candidate_creation_ordinal}.json
  round-N/
    draft_before.md
    mutation_plan.json
    section_identity_map_before.json
    context/
    prompt_snapshots/
    client_telemetry/
    proposals/
      attempts/
        proposal-attempt-M.json       # immutable raw client response
      {proposal_id}/
        proposed_patch.json           # immutable canonical validated patch set
        payloads/
          {payload_sha256}.md
    candidates/
      {candidate_id}/
        candidate_unverified.md
        section_identity_map_candidate.json
        preservation_report.json
        semantic_verification-attempt-M.json
        candidate_verification-attempt-{decision_ordinal}.json
        candidate_verification_current.json
        promotion_intents/
          promotion-intent-{next_promotion_ordinal}.json
        disposition_events/
          event-{event_ordinal}.json
    draft_after.md                 # only after promotion
    editor_summary.json            # Orchestrator-derived compatibility summary
    unresolved_issues.json
    decision_points.json
```

Current-verified history snapshots, candidate creation events, candidates, candidate section identity maps, canonical patch sets, payloads, semantic-verification attempts, candidate-verification attempts, promotion intents, and disposition events are immutable. Each candidate MUST bind one canonical `proposals/{proposal_id}/proposed_patch.json` and one candidate section identity map by hash. `candidate_verification_current.json` is the only mutable candidate-local verification pointer; it MAY advance only under the append-only and hash-chain rules in `Candidate Verification Decision` and `Candidate Disposition Event Commit Rules`. Other convenience pointers MAY be updated only when their targets and hashes are explicit. A rejected or unverified candidate MUST remain inspectable but MUST NOT appear at `draft_after.md`.

An immutable lifecycle artifact MUST be completely written, durability-synchronized under the storage contract, schema-validated, and hash-validated before it is atomically published at its canonical path or referenced by a commit pointer. A partial temporary file is not an artifact and MUST NOT participate in directory enumeration. A partial or mismatched file already visible at a canonical immutable path is artifact-invalid and MUST NOT be overwritten during recovery.

Every braced path component in the layout is the exact validated field named inside the braces; none is derived from timestamps or directory enumeration.

`editor_summary.json` MAY remain as a compatibility and audit artifact, but the Orchestrator MUST derive its persisted resolved/unresolved status from candidate verification. Editor claims alone MUST NOT resolve issues, update `last_accepted_draft_hash`, or authorize scheduling.

## Safe Terminal Semantics

Run terminal state and candidate disposition are orthogonal. Existing terminal states such as `HALTED_CLIENT_TIMEOUT`, `HALTED_ARTIFACT_INVALID`, `PAUSED_DECISION`, and `TARGET_NOT_REACHED` remain available, but terminal reports MUST also identify candidate status.

Every terminal report for a job that entered proposal or candidate processing MUST contain:

```yaml
schema_version: terminal-report-v2
terminal_state: string
current_verified_draft_path: string
current_verified_draft_hash: sha256
latest_candidate:
  candidate_id: string | null
  candidate_creation_ordinal: integer | null
  candidate_creation_event_path: string | null
  candidate_creation_event_hash: sha256 | null
  path: string | null
  hash: sha256 | null
  disposition: CANDIDATE_UNVERIFIED | CANDIDATE_VERIFIED | CANDIDATE_REJECTED | CANDIDATE_PROMOTED | null
  disposition_event_path: string | null
  disposition_event_hash: sha256 | null
  verification_decision_path: string | null
  verification_decision_hash: sha256 | null
  verification_decision_final: boolean | null
rejected_candidate_ids: [string]
outstanding_decision_ids: [string]
apply_back_permitted: boolean
resume:
  permitted: boolean
  next_gate: string | null
  reason: string
```

If the valid creation-event chain is empty and no orphan or invalid candidate artifact requires attention, every `latest_candidate` field MUST be null.

Terminal reporting MUST first select the candidate through the run-wide creation-event chain and copy its ID, creation ordinal, creation-event path and hash, candidate path, and candidate hash from that event. It MUST then select exactly one effective disposition event by commit binding:

1. Use the promotion event bound by `rounds/current_verified.json` when that pointer identifies the selected candidate and validates every candidate, intent, verification, and event binding.
2. Otherwise use the verification-decision event bound by the selected candidate's valid `candidate_verification_current.json`.
3. Otherwise use the initial disposition event bound by the selected candidate's creation event.

The terminal report MUST copy `disposition`, `disposition_event_path`, and `disposition_event_hash` from that effective event. When a verification-decision pointer exists, it MUST also copy `verification_decision_path`, `verification_decision_hash`, and `verification_decision_final` from the validated immutable decision target. When no decision attempt exists, those three verification-decision fields are null. Unbound prepared events and stale promotion intents MUST NOT affect terminal disposition.

If a token budget, timeout, interruption, or process failure occurs after candidate registration but before semantic verification completes, the selected latest candidate disposition MUST be `CANDIDATE_UNVERIFIED`. If failure occurs before the registration commit point, the incomplete candidate remains an orphan and the prior registered candidate, if any, remains latest. In both cases, the prior current verified draft remains authoritative.

If verification passes but promotion has not committed, the candidate may be `CANDIDATE_VERIFIED`, but the prior pointer remains authoritative and apply-back remains prohibited until promotion completes.

Apply-back is permitted only when:

- the selected bytes are referenced by the current verified pointer;
- the pointer's verified section-identity-map path and hash validate and agree with the selected seed or candidate registration;
- the pointer traces to the final `CANDIDATE_VERIFIED` target of a valid `candidate_verification_current.json` or to the immutable seed initialization;
- for a promoted candidate, the pointer's candidate registration, promotion-intent, and promotion-disposition-event paths and hashes all validate and agree;
- the run satisfies the scheduler and convergence policy required by apply-back;
- the external source hash guard passes;
- no unresolved apply-back-blocking decision exists.

Manual recovery flags MUST NOT relabel an unverified candidate as verified. A manual operator may export unverified material for inspection, but such export is not Whetstone apply-back and MUST be clearly reported as outside the verified promotion path.

## Public Contract Suite

Before `verified_promotion` is considered stable, Whetstone MUST publish, version-pin, validate, and contract-test schemas for:

- job descriptor;
- authority map;
- ratification delta;
- protected invariants;
- section identity map;
- mutation plan;
- patch set and patch operations;
- preservation report;
- semantic verification;
- candidate creation event and run-wide candidate index;
- candidate verification decision and current decision pointer;
- candidate disposition event;
- operator decision response;
- promotion intent;
- current verified pointer;
- terminal report.

Every contract MUST define:

- schema version and unknown-field behavior;
- canonical JSON and text normalization version;
- producer and consumer;
- Orchestrator-owned versus client-proposed fields;
- hash and identity inputs;
- validation ordering;
- migration and compatibility policy;
- positive and negative fixtures.

Schema validity alone is insufficient. The contract suite MUST include executable cross-artifact invariants and candidate-assembly conformance vectors.

## Migration From Current Runs

Existing run roots that predate `current_verified.json` MUST remain readable, but MUST NOT be silently upgraded into `verified_promotion` mode.

The supported migration posture is:

- reviewer-only inspection of existing runs remains allowed;
- current apply-back rules continue to govern already-completed legacy runs;
- starting automatic vNext editing requires a new run root and vNext job descriptor;
- a legacy final draft may be imported only as a new seed with an explicit source hash and initialization report;
- legacy `last_accepted_draft_hash` MUST NOT be treated as proof of candidate verification;
- legacy full-document Editor responses MUST NOT be converted into section patches by inference and promoted automatically.

## Current-Runtime Preservation Bridge

### Activation And Ownership

`preservation-bridge-v1` is an explicit opt-in, hard-enforcement contract for current full-draft editing, independent of vNext `editing_mode`. Configuration and release gates are owned by the [coordinating spec](WHETSTONE_COORDINATING_SPEC.md#preservation-bridge-activation). A bounded prompt or scope contract alone MUST NOT imply bridge coverage. Absent opt-in means explicitly legacy/unguarded behavior, not an invisible report-only bridge.

When supported and selected, the bridge MUST gate every full-draft path, including normal and resumed Editor calls, horizontal/focused and vertical consolidated editing, supplied revision fixtures, and Orchestrator-owned no-ops. Its comparison operates before any accepted history, authoritative `draft_after.md`, `spec.md`, accepted hash, stability, Phase 2, or strop consumption. Setting `accepted = false` while still writing proposed bytes is not enforcement.

The [artifact leaf](ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#current-runtime-preservation-bridge-contracts) owns the exact manifest, inventory, attempt, materialization, evidence-reference and report contracts. The [scope leaf](SCOPE_INTAKE_AND_DECISIONS_SPEC.md#bridge-operator-authority) owns operator approval/evidence and the distinction between review visibility and edit authority. The [scheduler leaf](SCHEDULER_STATE_AND_RESUME_SPEC.md#preservation-bridge-lifecycle) owns failure, retry, resume and consumer gates. These bridge-specific rules supersede older whole-draft acceptance rules only for admitted guarded runs.

### Structural Coverage And Correspondence

Generate a deterministic, exact-base-bound inventory before obtaining approval of a change surface. `bridge-inventory-v1` deliberately inventories structural text units rather than claiming to discover all semantic requirements: every physical line is covered, including preamble, parent body, headings, fenced schemas, tables, lists, blank separators and trailing content. Thus a field, enum member, command, failure code, acceptance scenario or reference cannot disappear merely because a semantic classifier did not recognize it. Multi-line concepts are protected through all of their constituent units. Parser and identity rules in the artifact leaf exclude fenced pseudo-headings and are separate from existing review anchors and vNext stable IDs.

Correspondence MUST NOT use fuzzy similarity or an Editor's identity claim. First match identical direct-content sequences inside unchanged canonical section paths; for edited sections, retain exact line matches only when there is one unambiguous order-preserving match. Equal-content duplicates with several possible predecessors remain ambiguous. Explicit operator evidence may supply an exact predecessor/successor mapping for rewording, moves, renames and supersession. Validate every such mapping against both inventories; missing or conflicting mappings fail. A rename of a container MUST account for all descendant units, not only its heading.

Every base unit receives exactly one disposition; added units are enumerated separately. Successor sharing is prohibited except explicitly evidenced supersession. A missing original unit is never cancelled by an addition elsewhere. A source/destination relocation or rename MUST have explicit `move`/`rename` permission and a manifest mapping; without it, report removal plus unrelated addition and reject. Generic `delete` plus `add` permissions MUST NOT launder a move or rename. Where relocation cannot be distinguished deterministically from independent removal/addition, require exact operator evidence rather than assume either interpretation.

### Authorization And Dispositions

Anything not explicitly authorized is preserved. The manifest identifies allowed and frozen sections/units, admitted findings, allowed change types and limits. Frozen sections include descendants; allowed sections do not implicitly include descendants. Conflicting allowed/frozen declarations fail admission. An existing-unit change requires an allowed section, allowed unit, allowed type, finding attribution and both applicable limits. Additions require an allowed destination and `add`; creating a section requires its exact new canonical path in the manifest. No wildcard or parent-wide permission expansion is permitted. Additions also require exact-effect `attest_addition` evidence: retaining the original text does not prove that an added exception or precedence rule has not weakened it. The first bridge intentionally cannot autonomously certify that semantic claim.

Sensitive changes additionally require:

- Deletion: `delete`, `deletion_allowed`, membership in `authorized_deletion_unit_ids`, and an operator decision for those units and the exact final effect.
- Weakening: `weaken`, `weakening_allowed`, and an operator decision for those units and exact reduced obligations; successful disposition is `operator_authorized_weakened`.
- Supersession: `supersede`, predecessor membership in `authorized_supersession_unit_ids`, allowed successor units/sections and admissible evidence of equal-or-stronger coverage. It does not require deletion permission when that evidence passes.
- Moves/renames: the exact manifest source/destination mapping, applicable type, and preservation evidence for all affected units. Any accompanying weakening still needs separate weakening permission.

These are conjunctions, not alternative overrides. Approval does not waive syntax, scope, correspondence, text hygiene, numeric limits, or other failed units. A unit cannot be both successfully weakened and claimed equivalent/superseded. The bridge uses the shared disposition vocabulary, with its own evidence rules below; it does not invent a vNext mutation plan or require the not-yet-operative semantic verifier.

For `preserved`, exact content and structural ownership MUST remain equal, except a recorded trusted version transformation. Changed content cannot pass as preserved merely because normalized draft hashes match. For changed wording, strengthening, movement or supersession, first-release admissible evidence is an explicit hash-bound operator attestation defined in the scope leaf. Without that evidence, assign the unit disposition `ambiguous`, record the corresponding `ambiguous` failure category, and reject; when the unsupported claim is supersession, additionally record `unauthenticated_supersession` in `failures.category`, never as a unit disposition. A clean Reviewer pass, Editor assertion, line-count ratio or generic similarity score is not an attestation. This conservative bridge validates evidence bindings, not the truth of arbitrary natural-language equivalence; reports MUST identify operator-attested claims as such. A future independent verifier needs a separately versioned admission rule.

The bridge MUST reject unrelated contract loss, protected-unit ambiguity, unauthorized deletion/weakening, surface overruns, and concrete contracts replaced by summaries or placeholders without individually valid dispositions. Legitimate removal is possible through explicit deletion or evidenced supersession; preservation does not mean retaining all text forever.

### Materialization And Authority

Preserve exact raw client response bytes, separately extract and hash the exact UTF-8 `draft_after_content`, then materialize separate final bytes using only the versioned trusted transformations listed in the artifact leaf. Compare the base against those final materialized bytes. Reports bind raw proposal, materialized draft, inventories and ordered transform evidence. Normalized `draft_hash` remains compatibility lineage, never a substitute for either exact-byte hash.

An Editor-authored version change is client content. It MUST NOT be silently restored or relabeled as an Orchestrator stamp. The first bridge permits stamping only when the raw version anchor still matches the base; otherwise reject `untrusted_version_edit`. Even explicit wording permission does not let the Editor choose the Orchestrator-owned version. An unchanged proposal receives no increment. A passing materialized output MUST be consumed byte-for-byte; no post-validation restamping or normalization is allowed.

### Failure And Qualification

Every attempt retains immutable inputs and available outputs. Every completed comparison, passing or failing, retains a complete report. A full-draft rewrite attempt is evidence, not a vNext candidate, and a bridge pass alone is not normal round acceptance. Failed/paused bytes MUST NOT become the next base, satisfy issues, erase residuals or pass recovery/strop controls. New authorization never rewrites a failed report; use the scheduler's explicit new-admission procedure. Transient technical continuation retains frozen bindings, whereas deterministic violations receive no automatic retry.

Before advertising the bridge, conformance tests MUST cover: all-line inventory coverage and fenced pseudo-headings; duplicate headings/units; preamble and parent content; exact and ambiguous correspondence; loss of a schema field/table row/enum; explicit and disguised moves/renames; allowed additions; frozen/default-preserved content; genuine operator-authorized deletion/weakening/supersession; stale evidence; raw versus materialized hash tampering; version edits and repeated stamping; deterministic rejection versus legitimate pause versus transient retry; accepted no-op; persistence failure; normal/resumed/vertical acceptance; and Phase 2/strop bypass attempts. Include a schema-valid large rewrite that satisfies Reviewer findings but destroys unrelated contracts, and positive cases proving authorized cleanup can pass.

This release does not introduce patch proposals, candidate registration, current-verified pointers, promotion locks, new semantic-verifier calls or D6-D8 vNext contracts. It remains unavailable until its own complete qualification passes, even though those later vNext mechanisms are not prerequisites for it.

## P0 Release Acceptance

Automatic editing MUST remain disabled until all P0 scenarios pass against version-pinned implementations.

### Destructive Replacement

An Editor replaces six sections with text stating that the sections remain unchanged. Deterministic preservation validation rejects the candidate. The current verified pointer and `spec.md` mirror remain on the prior verified draft.

### Unrelated Enum Or Table Loss

An Editor removes an enum member or table row unrelated to any admitted finding. The candidate is rejected with the removed unit ID and no promotion occurs.

### Forbidden Compatibility Introduction

The authority map marks the target prospective, implementation context describes an older model, and a blocking invariant forbids compatibility behavior. A patch introducing legacy, transition, adapter, migration, or dual-model language is rejected.

### Legitimate Product Decision

A Reviewer raises a valid product choice. Classification produces `operator_decision_required`; the Editor is not invoked for that finding until a hash-bound operator response exists.

### Partial Success With Regression

An Editor resolves three findings but causes one unrelated semantic regression. The candidate is rejected. If the offending operation can be isolated, a new reduced patch set is assembled from the immutable base and fully reverified.

### Invalid Output Or Timeout

An Editor response is invalid or times out. Any retry uses the last current verified draft and the same mutation plan; no partial response becomes the next base.

### Verification Budget Exhaustion

The run exhausts its token or time budget after candidate registration but before semantic verification. Candidate disposition is `CANDIDATE_UNVERIFIED`; apply-back is prohibited. Exhaustion before registration leaves only an orphan and does not change `latest_candidate`.

### Exact Resume

Resume first validates the current pointer's committed lineage at its own ordinal. Missing or stale pointer-derived materializations enter post-commit recovery, require the committed transaction base to equal `previous_verified_draft_hash`, and permit only idempotent `spec.md`, `draft_after.md`, and run-state materialization before the invocation ends. When those materializations already match, pre-commit resume validates `latest_candidate`, reconstructs it and its registered section identity map from immutable base, patch, payload, creation-event, and map hashes without invoking the Editor, and requires its transaction base to remain current. Promotion resume then acquires the run-wide lock and either completes the sole valid prepared next-ordinal claimant or, when none exists, selects only the exact latest candidate. Any hash mismatch, partial commit binding, or missing committed pointer snapshot blocks resume.

### Candidate Identity Map Binding

A candidate's Markdown bytes remain intact while `section_identity_map_candidate.json` is deleted, replaced, or changed. Registration, verification, promotion, resume, and apply-back reject the candidate lineage as artifact-invalid through the creation-event and current-pointer map bindings.

### Candidate Ordering And Orphan Recovery

Two retries produce distinct candidates and one process crashes after writing a third candidate but before registration. The valid contiguous creation-event chain selects the second registered candidate as latest. Recovery either completes the third candidate's exact next registration once or preserves it as an orphan and halts artifact-invalid; candidate IDs, timestamps, and directory order never break the tie.

### Verification Decision Commit Recovery

Fault injection after decision-attempt write, after disposition-event write, and after verification-pointer replacement never exposes a torn decision and disposition. Recovery reuses at most one exact prepared next event, the pointer binds the decision and event together, and terminal reporting selects only the effective bound event.

### Historical Recurrence Fixture

The destructive first-round recurrence mutation is replayed as a golden fixture and rejected before promotion.

### Cross-Implementation Determinism

Two conforming implementations apply the same validated patch inputs and produce byte-identical candidates, identity maps, and candidate hashes. Given the same persisted creation-event, disposition-event, verification-pointer, intent, and current-verified-pointer bytes, they select the same latest candidate and effective disposition.

### Normative Weakening Without Deletion

An Editor changes `MUST` to `SHOULD` without deletion authorization. The preservation report classifies the unit as weakened and rejects the candidate before semantic verification.

### Stale And Overlapping Patches

A patch has a stale base or target hash, or contains undeclared overlapping operations. Candidate assembly fails without changing the current verified draft.

### Markdown Parser Edge Cases

Headings inside fenced code blocks, duplicate headings, escaped table delimiters, Unicode text, CRLF input, and missing final newlines produce the contract-defined identity and canonical bytes.

### Verifier Failure

The Semantic Verifier times out, returns invalid JSON, reports uncertainty, or requests an operator decision. The candidate does not promote.

### Promotion Crash Recovery

Fault injection at every promotion step yields exactly one authoritative current verified pointer. Before pointer commit, the old pointer remains authoritative and a prepared candidate-scoped intent, promotion event, and next-ordinal pointer snapshot remain ineffective. After commit, the pointer's byte-identical snapshot plus its intent, verification, registration, map, and event bindings prove the promotion and recovery completes materialization without allocating another event or ordinal. A stale intent never promotes.

### Concurrent Promotion Preparation

Two final verified candidates already exist when separate callers attempt to prepare the same next promotion ordinal. After acquiring the run-wide promotion lock, both implementations select the higher creation-ordinal `latest_candidate`; the caller and lock winner cannot select the older candidate. A crash after the selected candidate's intent, event, or snapshot write causes recovery to reacquire the lock and complete that same claimant's valid artifact prefix before any other candidate may prepare. If a later candidate registers after lock loss, the prepared claimant remains reserved. Multiple eligible claimants, a non-prefix artifact combination, or conflicting snapshot bytes halt artifact-invalid; no uncommitted candidate can poison or bypass the ordinal.

### Promotion Ordinal Continuity

The seed pointer and immutable history snapshot start at promotion ordinal 0. The first successful candidate promotion commits ordinal 1, and each later successful promotion advances by exactly one. Validation walks the immutable previous-pointer snapshot chain to ordinal 0. An intent, current pointer, or history chain that reuses, regresses, skips, or breaks an ordinal is artifact-invalid and cannot change authority.

### Decision Staleness

An operator response is created for an older base or authority map. It cannot authorize a later transaction.

### Changed External Source

The run converges on a promoted verified candidate, but the external source changed after seeding. Apply-back refuses unless the existing explicit source-reconciliation policy is followed; candidate verification does not bypass the source hash guard.

## P1 Follow-On Capabilities

P1 may add:

- survey-first uncertainty mapping beyond the current diagnostic sweep;
- richer section ownership and multi-target locking;
- downstream ratification bundles and authority-delta visualization;
- token and context preflight estimates;
- adaptive mutation budgets above the P0 hard caps;
- visual patch, preservation, and verification review surfaces;
- decomposition recommendations for oversized targets;
- broader historical regression corpora;
- configurable multi-verifier or quorum policies.

P1 features MUST NOT weaken the P0 promotion invariant.

## Recommended Implementation Sequence

Ratification does not authorize a single broad rewrite. Implementation SHOULD proceed in independently testable stages:

1. Immediate containment: default new jobs to `reviewer_only` and make full-document Editor promotion unavailable.
2. Transactional foundation: introduce immutable base artifacts, candidate isolation, run-wide candidate registration, commit-bound disposition events, current verified pointers, candidate-scoped promotion intents, run-wide fenced promotion serialization, and crash-safe promotion without enabling automatic promotion.
3. Patch protocol: implement stable section identity, payload storage, deterministic patch assembly, and cross-implementation conformance vectors.
4. Deterministic preservation: implement inventories, typed invariants, mutation budgets, and rejection fixtures.
5. Authority and decision controls: add authority maps, pre-edit finding classification, and hash-bound operator decisions.
6. Semantic verification: add the independent verifier and candidate-verification decision while remaining in `proposal_only` soak mode.
7. Sliced editing and safe retry: reduce context and retry blast radius while preserving global verification.
8. Historical soak: replay destructive and non-destructive run fixtures, including recurrence, and satisfy every P0 release scenario.
9. Controlled enablement: expose `verified_promotion` as an explicit opt-in only after the advertised contract-suite version passes the release gate.

Each stage MUST leave the current verified draft authoritative on failure. A later-stage flag MUST NOT activate when an earlier required stage or contract version is unavailable.

## Requirements Traceability

| Requirement area | Owning section in this leaf |
| --- | --- |
| Patch-based editing | `Patch Protocol` |
| Candidate transactions | `Candidate Transaction`, `Candidate Verification Decision` |
| Run-wide candidate ordering | `Candidate Registration And Run-Wide Ordering` |
| Candidate disposition commits | `Candidate Disposition Event Commit Rules` |
| Candidate identity-map lineage | `Stable Section Identity`, `Candidate Registration And Run-Wide Ordering`, `Candidate Verification Decision` |
| Promotion serialization, intent, ordinal continuity, and crash recovery | `Promotion And Current Verified Authority`, `Resume And Replay` |
| Machine-enforced preservation | `Preservation Inventory`, `Deterministic Validation` |
| Explicit authority model | `Explicit Authority Model` |
| Protected invariants and prohibited mutations | `Protected Invariants` |
| Operator-decision gate | `Finding Classification And Mutation Admission`, `Operator Decision Response` |
| Independent candidate verification | `Independent Semantic Verification`, `Candidate Verification Decision` |
| Preservation-safe retries | `Preservation-Safe Retry` |
| Section-sliced operation | `Section-Sliced Operation` |
| Safe terminal semantics | `Safe Terminal Semantics` |
| Versioned public contracts | `Public Contract Suite` |
| Release acceptance scenarios | `P0 Release Acceptance` |
| Follow-on capabilities | `P1 Follow-On Capabilities` |

## Ratification Delta Map

The following table is the section-addressed amendment plan for ratification. Canonical section IDs are the current Markdown heading-path anchors in the named files. If a heading is renamed before ratification, the amendment that renames it MUST update this map in the same change.

| Current authority surface | Canonical section ID | Required bounded amendment |
| --- | --- | --- |
| Family routing and role authority | `docs/specs/WHETSTONE_COORDINATING_SPEC.md#spec-family-map`, `#core-roles` | Add this leaf to the family map; route proposal validation, semantic verification, candidate disposition, and promotion authority; state that Editor output is untrusted. |
| Run inputs, outputs, configuration, and design principle | `docs/specs/WHETSTONE_COORDINATING_SPEC.md#primary-inputs`, `#primary-outputs`, `#configuration`, `#design-principle` | Add the job descriptor, editing modes, current verified pointer, candidate artifacts, and fail-closed promotion principle; stop describing raw full-document Editor output as a directly mutable primary output in vNext mode. |
| Halting and terminal artifacts | `docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#halting-conditions-ordered-precedence`, `#halt-artifact-matrix`, `#phase-1-failure-handling` | Define precedence and required artifacts for proposal, validation, verification, decision, promotion, and recovery failures while preserving the prior verified pointer. |
| Verified lineage versus quality state | `docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#accepted-draft-definition`, `#spec-version-lifecycle`, `#definition-clean-profile` | Distinguish verified lineage from accepted-draft, profile-clean, Phase 1 stable, and converged status; prevent `last_accepted_draft_hash` from serving as candidate-verification proof. |
| Proposal-to-promotion scheduling | `docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#round-scheduling-algorithm`, `#state-machine-full-transitions` | Replace direct full-document mutation transitions in vNext mode with proposal capture, deterministic validation, semantic verification, candidate decision, run-wide serialized promotion, and atomic authority transitions. |
| Budgets, retries, resume, and read-only status | `docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#round-budget-handling`, `#resume-policy` | Bind replay to the immutable descriptor and current verified pointer; preserve incomplete candidates; validate current committed lineage before next-ordinal search; select a no-claimant promotion only from `latest_candidate`; distinguish pre-commit base-current recovery from post-commit materialization; reacquire the promotion lock and reconcile the sole prepared next-ordinal claimant; prohibit retries or resume from unverified bytes. |
| Public artifacts, locking, and attempt semantics | `docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#artifact-schemas-minimum-required-fields`, `#artifact-validation-policy` | Define and validate the vNext contract suite, mutually exclusive candidate-registration and run-wide promotion-lock critical sections, fencing semantics, immutable raw attempts, canonical `proposals/{proposal_id}/proposed_patch.json`, candidate creation events and identity-map bindings, verification artifacts and pointers, candidate-scoped promotion intents, commit-bound disposition events, ordinal-indexed current-verified history snapshots, current verified pointers, and terminal fields. |
| Current full-draft preservation bridge | `docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#artifact-schemas-minimum-required-fields`, `#content-normalization-and-hashing` | Before vNext patch-based editing is operative, require guarded full-draft Editor responses to pass deterministic preservation-bridge validation before `draft_after.md`, `spec.md`, `last_accepted_draft_hash`, Phase 1 stability, Phase 2, or apply-back eligibility can consume them. |
| Versioned normalization and hashing | `docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#content-normalization-and-hashing` | Bind parser, assembler, inventory, normalization, candidate, candidate identity-map, report, pointer, and pointer-history hashes to the immutable job descriptor and exact persisted bytes. |
| Scope, finding admission, authority, and decisions | `docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#scope-contract`, `#expanding-contract-surface`, `#decision-summary` | Add pre-Editor finding classification, authority and prospective-spec gates, hash-bound decision responses, staleness checks, and candidate-blocking decision status. |
| Phase 2 and convergence lineage | `docs/specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md#phase-2-failure-handling`, `#target-matrix-precedence`, `#convergence-declaration`, `#reproducibility` | Require Phase 2, declaration generation, and reproducibility evidence to resolve and bind the promoted current verified draft rather than an unverified candidate or unverified `spec.md` mirror. |
| Operator defaults and recovery guidance | `docs/OPERATOR_QUICKSTART.md#mental-model`, `#recommended-defaults`, `#running-whetstone-from-an-agent`, `#recover-a-timeout`, `#terminal-states`, `#safety-rules` | Default unfamiliar jobs to reviewer-only mode; document proposal-only and verified-promotion opt-in, candidate inspection, safe recovery, and the prohibition on treating Editor output as current. |
| Current strop/apply-back operational surface | `docs/OPERATOR_QUICKSTART.md#review-before-apply-back`, `#apply-back`, `#troubleshooting` | Require strop/apply-back review and write paths to select only bytes referenced by a committed current verified pointer and to refuse unverified, rejected, or merely accepted candidates. |
| Strop/apply-back normative ownership designation | `docs/specs/WHETSTONE_COORDINATING_SPEC.md#spec-family-map` | The coordinating spec now designates `SCHEDULER_STATE_AND_RESUME_SPEC.md` as the target normative owner for the pending bounded amendment to full strop/apply-back eligibility and the external source-write lifecycle, routed to this leaf's verified-candidate eligibility guard. Detailed vNext policy remains unratified until that scheduler amendment is completed. Until then, current operative behavior continues under the scheduler leaf's existing lineage and hash guards together with the Operator Quickstart procedure. This leaf does not otherwise absorb external source-spec apply-back policy. |

## Ratification Checklist

Before this leaf becomes operative, the spec family MUST be amended so that:

- the coordinating spec routes candidate editing and promotion authority to this leaf;
- the scheduler distinguishes verified lineage from accepted and profile-clean status;
- scheduler transitions invoke proposal, validation, verification, and promotion gates;
- artifact validation defines the new public contract suite and attempt semantics;
- candidate registration, candidate identity-map bindings, disposition-event commits, candidate-scoped promotion intents, mutually exclusive registration/promotion serialization, deterministic two-stage promotion search, and ordinal-indexed verified-pointer history have validated append-only and recovery contracts;
- scope and decision handling classifies findings before Editor invocation;
- Phase 2 evaluates only the current verified draft;
- status exposes current verified and latest candidate identities separately;
- resume uses the current verified pointer and immutable candidate artifacts with explicit pre-commit and post-commit guards;
- strop/apply-back selects only promoted verified bytes;
- operator guidance defaults unfamiliar jobs to reviewer-only mode;
- current full-document Editor output is disabled for automatic editing;
- the historical recurrence fixture and all P0 acceptance scenarios pass.

Until every checklist item is satisfied, automatic verified promotion MUST remain unavailable.
