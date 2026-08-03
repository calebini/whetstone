# Candidate Editing And Promotion Spec

Status: vNext design draft

Version: `0.1`

Activation: non-operative until ratified by the Whetstone coordinating spec and backed by version-pinned public contracts and conformance tests.

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
5. Every finding targeted for resolution has an allowed terminal disposition.
6. No unresolved operator decision, authority conflict, or scope-change gate applies to the candidate.
7. The candidate hash still identifies the exact bytes evaluated by both validation layers.
8. The transaction's base hash still equals the current verified draft hash at promotion time.
9. Promotion completes through the atomic current-verified-pointer protocol.

Equivalently:

```text
promote(candidate) =
  patch_contract_valid
  AND deterministic_validation_passed
  AND semantic_verification_passed
  AND required_decisions_resolved
  AND candidate_hashes_match
  AND base_hash_is_current
```

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
assembler_version: string
inventory_version: string
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

The Markdown parser contract MUST be version-pinned. It MUST distinguish actual ATX headings from heading-like text inside fenced code blocks. Parser upgrades require a new parser contract version and conformance fixtures.

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

Character count, line count, document size ratios, and generic similarity scores MAY be advisory signals. They MUST NOT satisfy preservation validation.

Every removed normative unit MUST:

- be identified by stable unit ID;
- be attributable to at least one admitted finding;
- appear in `authorized_deletion_unit_ids`;
- be authorized by a valid operator decision response;
- be acknowledged by semantic verification.

Every modified, weakened, moved, or renamed normative unit MUST be attributable to an admitted finding and allowed mutation surface. Requirement weakening always requires an operator decision.

Replacing concrete contracts with placeholders, summaries, ellipses, statements that sections are unchanged, or vague references to removed material MUST fail preservation validation even if overall document size remains above a configured threshold.

## Patch Protocol

### Patch Set

The Editor MUST return metadata as `proposed_patch.json`. Substantial Markdown MUST be stored as separate content-addressed payload artifacts.

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

`proposal_id` MUST be computed by the Orchestrator from the canonicalized patch set after validating all referenced payload hashes. Editor-provided proposal IDs are placeholders.

Client-input and persisted patch contracts MUST be distinct where Orchestrator-owned identities differ. Client input MAY contain a null proposal ID; the persisted patch set MUST contain the computed value.

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
6. Canonicalize the assembled text once under the active text-normalization version.
7. Write `candidate_unverified.md` as an immutable artifact.
8. Compute the candidate hash from the persisted candidate bytes.

The candidate hash evaluated by validators MUST identify the exact bytes eligible for promotion. Promotion-time version stamping, formatting, or cleanup is forbidden because it would create unverified bytes.

Two conforming implementations applying the same validated patch set, payloads, base, parser version, assembler version, and normalization version MUST produce byte-identical candidate artifacts and identical candidate hashes.

### Candidate Identity And Disposition

```text
candidate_id = "can_" + first_16_hex_chars(SHA256(canonical_json({
  "transaction_id": transaction_id,
  "base_draft_hash": base_draft_hash,
  "patch_set_hash": patch_set_hash,
  "assembler_version": assembler_version,
  "normalization_version": normalization_version
})))
```

Candidate disposition is separate from run terminal state:

```text
CANDIDATE_UNVERIFIED
CANDIDATE_DETERMINISTICALLY_VALID
CANDIDATE_VERIFIED
CANDIDATE_REJECTED
CANDIDATE_PROMOTED
CANDIDATE_SUPERSEDED
```

Only `CANDIDATE_VERIFIED` may transition to `CANDIDATE_PROMOTED`.

## Deterministic Validation

Deterministic validation MUST run against the persisted candidate and immutable base. It MUST produce `preservation_report.json` even when validation fails after candidate assembly.

Validation order:

1. Verify job, transaction, base, patch, payload, candidate, parser, assembler, and inventory identities.
2. Reapply the patch independently and require the reproduced candidate hash to match.
3. Validate operation targeting, ordering, dependency, overlap, and mutation budgets.
4. Build base and candidate inventories with the same inventory version.
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
patch_set_hash: sha256
parser_contract_version: string
assembler_version: string
inventory_version: string
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
base_draft_hash: sha256
candidate_hash: sha256
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

`uncertain` fails closed. It MUST produce either rejection or an operator-decision requirement; it MUST NOT be coerced to `pass` by majority fields.

If a safe patch intentionally addresses only part of a broader finding, the Orchestrator MUST create a narrower derived finding before mutation planning. Partial resolution of the broader original finding cannot satisfy promotion for a transaction that admitted the broader finding itself.

Independence policy MUST be versioned. It MAY require a different model or provider for high-assurance jobs. At minimum, the verifier MUST be a distinct invocation, use a verifier-specific prompt, have no editing tool authority, and produce a separately validated artifact.

## Candidate Verification Decision

The Orchestrator MUST combine both verification layers into `candidate_verification.json`.

Minimum fields:

```yaml
schema_version: candidate-verification-v1
job_id: string
transaction_id: string
candidate_id: string
base_draft_hash: sha256
candidate_hash: sha256
patch_set_hash: sha256
preservation_report_hash: sha256
semantic_verification_hash: sha256 | null
deterministic_result: pass | fail
semantic_result: pass | reject | operator_decision_required | not_run
outstanding_decision_ids: [string]
candidate_disposition: CANDIDATE_UNVERIFIED | CANDIDATE_VERIFIED | CANDIDATE_REJECTED
promotion_permitted: boolean
rejection_codes: [string]
decided_at: timestamp
```

This artifact is Orchestrator-owned. Client output MUST NOT set `candidate_disposition` or `promotion_permitted`.

If deterministic validation fails, semantic verification MUST NOT run and the candidate disposition MUST be `CANDIDATE_REJECTED`.

If deterministic validation passes but semantic verification is missing, invalid, timed out, inconclusive, or interrupted, the candidate disposition MUST be `CANDIDATE_UNVERIFIED` and promotion MUST remain prohibited.

`CANDIDATE_DETERMINISTICALLY_VALID` is a transient audit event recorded after deterministic validation passes and before semantic verification finishes. It MUST collapse to `CANDIDATE_UNVERIFIED` in terminal reporting when semantic verification does not complete.

If semantic verification rejects the candidate or requires an unresolved operator decision, the candidate disposition MUST be `CANDIDATE_REJECTED` until a new transaction produces a new candidate. An operator decision does not retroactively turn rejected bytes into verified bytes; the resulting patch must be reassembled and both verification layers rerun.

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
source_transaction_id: string | null
source_candidate_id: string | null
candidate_verification_hash: sha256 | null
previous_verified_draft_hash: sha256 | null
promoted_at: timestamp
```

The initial pointer MUST reference an immutable normalized seed artifact. Subsequent pointers MUST reference immutable promoted candidate artifacts.

`spec.md` becomes a materialized convenience copy of the pointer target, not independent lineage authority. Review, resume, Phase 2 entry, convergence, and apply-back MUST resolve the current verified pointer first and verify any `spec.md` mirror against it.

Before the pointer commit point, the Orchestrator MUST persist `promotion_intent.json`:

```yaml
schema_version: promotion-intent-v1
job_id: string
transaction_id: string
candidate_id: string
base_draft_hash: sha256
candidate_hash: sha256
candidate_verification_hash: sha256
expected_current_verified_hash: sha256
next_promotion_ordinal: integer
status: prepared
prepared_at: timestamp
```

Candidate disposition changes MUST be append-only artifacts rather than in-place mutation of candidate verification:

```yaml
schema_version: candidate-disposition-event-v1
job_id: string
candidate_id: string
event_ordinal: integer
previous_disposition: string | null
new_disposition: string
source_artifact_path: string
source_artifact_hash: sha256
recorded_at: timestamp
```

Disposition event identity MUST exclude `recorded_at` and include the candidate ID, ordinal, previous and new dispositions, and source artifact hash.

Promotion protocol:

1. Revalidate all gate hashes and require the base hash still to be current.
2. Write the immutable verified candidate artifact if it is not already persisted.
3. Write and validate an immutable promotion-intent artifact.
4. Atomically replace `rounds/current_verified.json` with a pointer to the verified candidate.
5. Materialize `spec.md` byte-identically from the pointer target.
6. Write `draft_after.md` byte-identically from the promoted candidate.
7. Append promotion history and update run state.
8. Record candidate disposition `CANDIDATE_PROMOTED` in an append-only disposition event.

The pointer replacement is the authority-advancing commit point. If a crash occurs before it, the previous pointer remains authoritative. If a crash occurs after it but before `spec.md` or run-state materialization completes, recovery MUST rematerialize from the pointer and MUST NOT roll back to an unverified or ambiguous draft.

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
- verify the current pointer and target draft hash;
- verify the transaction base equals the current verified hash;
- reconstruct the exact candidate from the immutable base, patch metadata, payloads, and assembler version;
- require the reconstructed candidate hash to match the persisted candidate hash;
- reuse existing valid deterministic and semantic reports only when all bound hashes match;
- continue at the first incomplete gate;
- never call an Editor merely to reproduce an already persisted candidate;
- never seed a retry or later round from an unverified or rejected candidate.

If required assembler, parser, inventory, normalization, or contract versions are unavailable, resume MUST refuse. It MUST NOT silently replay under newer semantics.

Two implementations resuming the same validated transaction MUST reproduce the same candidate bytes and hashes before either may continue verification or promotion.

## Round Artifact Layout

A mutating vNext round MUST preserve at least:

```text
rounds/round-N/
  draft_before.md
  mutation_plan.json
  section_identity_map_before.json
  context/
  prompt_snapshots/
  client_telemetry/
  proposals/
    proposal-attempt-M.json
    payloads/
      {operation_id}.md
  candidates/
    {candidate_id}/
      candidate_unverified.md
      section_identity_map_candidate.json
      preservation_report.json
      semantic_verification-attempt-M.json
      candidate_verification.json
      disposition_events/
        event-K.json
  draft_after.md                 # only after promotion
  editor_summary.json            # Orchestrator-derived compatibility summary
  unresolved_issues.json
  decision_points.json
```

Candidate and attempt artifacts are immutable. Convenience pointers MAY be updated only when their targets and hashes are explicit. A rejected or unverified candidate MUST remain inspectable but MUST NOT appear at `draft_after.md`.

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
  path: string | null
  hash: sha256 | null
  disposition: CANDIDATE_UNVERIFIED | CANDIDATE_VERIFIED | CANDIDATE_REJECTED | CANDIDATE_PROMOTED | CANDIDATE_SUPERSEDED | null
rejected_candidate_ids: [string]
outstanding_decision_ids: [string]
apply_back_permitted: boolean
resume:
  permitted: boolean
  next_gate: string | null
  reason: string
```

If a token budget, timeout, interruption, or process failure occurs after assembly but before semantic verification completes, the latest candidate disposition MUST be `CANDIDATE_UNVERIFIED`. The prior current verified draft remains authoritative.

If verification passes but promotion has not committed, the candidate may be `CANDIDATE_VERIFIED`, but the prior pointer remains authoritative and apply-back remains prohibited until promotion completes.

Apply-back is permitted only when:

- the selected bytes are referenced by the current verified pointer;
- the pointer traces to a passing candidate-verification artifact or the immutable seed initialization;
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
- candidate verification;
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

The run exhausts its token or time budget after candidate assembly but before semantic verification. Candidate disposition is `CANDIDATE_UNVERIFIED`; apply-back is prohibited.

### Exact Resume

Resume reconstructs the exact candidate from immutable base, patch, and payload hashes without invoking the Editor. Any hash mismatch blocks resume.

### Historical Recurrence Fixture

The destructive first-round recurrence mutation is replayed as a golden fixture and rejected before promotion.

### Cross-Implementation Determinism

Two conforming implementations apply the same validated patch inputs and produce byte-identical candidates, identity maps, and candidate hashes.

### Normative Weakening Without Deletion

An Editor changes `MUST` to `SHOULD` without deletion authorization. The preservation report classifies the unit as weakened and rejects the candidate before semantic verification.

### Stale And Overlapping Patches

A patch has a stale base or target hash, or contains undeclared overlapping operations. Candidate assembly fails without changing the current verified draft.

### Markdown Parser Edge Cases

Headings inside fenced code blocks, duplicate headings, escaped table delimiters, Unicode text, CRLF input, and missing final newlines produce the contract-defined identity and canonical bytes.

### Verifier Failure

The Semantic Verifier times out, returns invalid JSON, reports uncertainty, or requests an operator decision. The candidate does not promote.

### Promotion Crash Recovery

Fault injection at every promotion step yields exactly one authoritative current verified pointer. Recovery either retains the old pointer or completes materialization from the committed new pointer; it never selects an unverified candidate.

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
2. Transactional foundation: introduce immutable base artifacts, candidate isolation, current verified pointers, disposition reporting, and crash-safe promotion without enabling automatic promotion.
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

## Ratification Checklist

Before this leaf becomes operative, the spec family MUST be amended so that:

- the coordinating spec routes candidate editing and promotion authority to this leaf;
- the scheduler distinguishes verified lineage from accepted and profile-clean status;
- scheduler transitions invoke proposal, validation, verification, and promotion gates;
- artifact validation defines the new public contract suite and attempt semantics;
- scope and decision handling classifies findings before Editor invocation;
- Phase 2 evaluates only the current verified draft;
- status exposes current verified and latest candidate identities separately;
- resume uses the current verified pointer and immutable candidate artifacts;
- strop/apply-back selects only promoted verified bytes;
- operator guidance defaults unfamiliar jobs to reviewer-only mode;
- current full-document Editor output is disabled for automatic editing;
- the historical recurrence fixture and all P0 acceptance scenarios pass.

Until every checklist item is satisfied, automatic verified promotion MUST remain unavailable.
