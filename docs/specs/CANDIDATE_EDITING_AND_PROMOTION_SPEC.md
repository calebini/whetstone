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
initial_disposition_event_path: string
initial_disposition_event_hash: sha256
previous_creation_event_hash: sha256 | null
created_at: timestamp
```

Registration MUST be serialized under the run's single-Orchestrator write lock. Ordinals start at 1, increase contiguously by 1, and bind the exact canonical persisted bytes of the prior creation event through `previous_creation_event_hash`. `creation_event_id` MUST be computed from every field except `creation_event_id` and `created_at`; the persisted event hash includes all fields. Duplicate ordinals, gaps, a broken previous-event hash, duplicate registration of one candidate ID, or a registered candidate path or hash mismatch is `HALTED_ARTIFACT_INVALID`; consumers MUST NOT guess an ordering.

Before allocating a new ordinal, the Orchestrator MUST reconcile any orphan that claims the one next ordinal; it MUST NOT register a later candidate around an unresolved orphan. Under the registration lock it determines the next ordinal and uses that same value in the initial disposition event and creation event.

Candidate assembly and registration commit in this order:

1. Persist and hash the immutable candidate and section identity map.
2. Persist candidate-local disposition event ordinal 1 with `event_kind = candidate_created`, `previous_disposition = null`, `new_disposition = CANDIDATE_UNVERIFIED`, and the candidate artifact as its source.
3. Persist the next creation event with the exact initial disposition-event path and hash.

The creation event is the registration commit point. A candidate directory or initial disposition event not referenced by a valid creation event is an orphan and MUST NOT be selected as latest, resumed, verified, promoted, or reported as registered. Recovery MAY finish the next unoccupied registration ordinal only when the candidate identity, bytes, initial event, prior creation-event hash, and expected ordinal all validate; otherwise it MUST preserve the orphan for diagnosis and halt artifact-invalid.

Reassembling byte-identical candidate inputs MUST reuse the existing candidate ID, creation event, and creation ordinal. It MUST NOT append a duplicate registration merely because a client or process retry occurred.

The run's `latest_candidate` is the candidate referenced by the highest ordinal in the unique contiguous valid creation-event chain. Terminal reporting, read-only status, and candidate resume selection MUST use that rule and MUST NOT compare candidate IDs, timestamps, proposal attempt numbers, or candidate-local event ordinals across candidates. Resume MUST NOT skip a final latest candidate to continue an older candidate; a further editing retry creates or reuses a candidate under the normal registration rule. Apply-back authority remains the current verified pointer, never the latest-candidate ordering.

## Deterministic Validation

Deterministic validation MUST run against the persisted candidate and immutable base. It MUST produce `preservation_report.json` even when validation fails after candidate assembly.

Validation order:

1. Verify job, transaction, base, patch, payload, candidate, parser, assembler, inventory, and normalization identities against the job descriptor.
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
candidate_disposition: CANDIDATE_UNVERIFIED | CANDIDATE_VERIFIED | CANDIDATE_REJECTED
decision_final: boolean
updated_at: timestamp
```

Decision ordinals start at 1 and increase contiguously. The pointer targets are authoritative for the candidate's current verification decision and its corresponding disposition event; the pointer file is not itself a substitute for either immutable target. Both target paths MUST resolve below the same immutable candidate directory and match their recorded hashes. The event MUST name the decision attempt as its source artifact, and its `new_disposition` MUST equal both the decision attempt's and pointer's `candidate_disposition`. A pointer update may advance only to the next decision and event ordinals for the same job, transaction, candidate, base, candidate, and patch hashes. Every attempt after ordinal 1 MUST bind the prior decision target through `previous_decision_hash`.

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
previous_verified_pointer_hash: sha256 | null
promoted_at: timestamp
```

The initial pointer MUST reference an immutable normalized seed artifact and set all candidate, verification, intent, disposition-event, and previous-pointer fields to null. Subsequent pointers MUST reference immutable promoted candidate artifacts and populate every such field with mutually consistent paths, hashes, identities, and ordinals.

`spec.md` becomes a materialized convenience copy of the pointer target, not independent lineage authority. Review, resume, Phase 2 entry, convergence, and apply-back MUST resolve the current verified pointer first and verify any `spec.md` mirror against it.

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
base_draft_hash: sha256
candidate_hash: sha256
candidate_verification_path: string
candidate_verification_hash: sha256
expected_current_verified_hash: sha256
expected_current_verified_pointer_hash: sha256
next_promotion_ordinal: integer
status: prepared
prepared_at: timestamp
```

The path is derived from the registered candidate and the current pointer's `promotion_ordinal + 1`; timestamps and directory enumeration MUST NOT select an intent. `intent_id` MUST be computed from every field except `intent_id` and `prepared_at`, and the intent hash MUST cover the exact canonical persisted bytes including both fields. The candidate creation-event path and hash MUST identify the exact run-wide registration selected by `candidate_creation_ordinal`. The candidate verification path and hash MUST identify the final `CANDIDATE_VERIFIED` decision currently bound by `candidate_verification_current.json`. The expected pointer hash MUST identify the exact canonical bytes of `rounds/current_verified.json` observed during preparation.

At most one valid intent may exist at the derived path. Repeated preparation with the same bound inputs MUST reuse the byte-identical persisted intent and MUST NOT rewrite `prepared_at`. If the path already contains different bytes, if multiple files claim the same candidate and next promotion ordinal, or if any bound path or hash mismatches, promotion and resume MUST halt artifact-invalid.

Intent selection and recovery are deterministic:

- If the current verified pointer still matches both expected current fields and its next ordinal equals the intent's `next_promotion_ordinal`, the prepared intent is eligible to continue.
- If the current verified pointer already binds the intent path and hash, advances to the same candidate, candidate hash, verification decision, registration event, and promotion ordinal, and its bound promotion event validates, promotion has committed; recovery MUST continue only post-commit materialization and history repair.
- Otherwise the intent is stale. It remains immutable evidence but MUST NOT be selected, rewritten, promoted, or used to resume candidate verification. No flag may refresh it in place; changed pointer inputs require a newly eligible transaction and candidate under the normal base-current rules.

Promotion protocol:

1. Revalidate all gate hashes and require the base hash still to be current.
2. Revalidate the registered immutable candidate and final verification-decision pointer targets.
3. Create or reuse the one eligible immutable candidate-scoped promotion intent.
4. Create or reuse the next candidate disposition event with `event_kind = promotion_committed`, source path and hash equal to the intent, and transition `CANDIDATE_VERIFIED -> CANDIDATE_PROMOTED`.
5. Conditionally and atomically replace `rounds/current_verified.json` only if its exact bytes still match `expected_current_verified_pointer_hash`; the new pointer MUST bind that value as `previous_verified_pointer_hash` together with the candidate registration ordinal and creation-event path and hash, final verification path and hash, promotion-intent path and hash, and promotion-disposition-event path and hash.
6. Materialize `spec.md` byte-identically from the pointer target.
7. Write `draft_after.md` byte-identically from the promoted candidate.
8. Append promotion history and update run state from the committed pointer bindings.

The pointer replacement is the authority-advancing commit point and makes the bound promotion disposition event effective. If a crash occurs before it, the previous pointer and prior candidate disposition remain authoritative; the prepared intent and event remain unbound. If a crash occurs after it but before `spec.md`, `draft_after.md`, history, or run-state materialization completes, recovery MUST treat the promotion as committed, rematerialize from the pointer, and MUST NOT append another promotion event, allocate another ordinal, or roll back to an unverified or ambiguous draft.

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
- validate the unique contiguous run-wide candidate creation-event chain and select `latest_candidate` only by its highest ordinal;
- verify the transaction base equals the current verified hash;
- reconstruct the exact candidate from the immutable base, patch metadata, payloads, and the descriptor-bound parser, assembler, inventory, and normalization versions;
- require the reconstructed candidate hash to match the persisted candidate hash;
- resolve and hash-check `candidate_verification_current.json` when present, including its immutable target and decision hash chain;
- reuse existing valid deterministic and semantic reports only when all bound hashes match;
- when the current decision is non-final, continue at the first incomplete gate and append `candidate_verification-attempt-{next_decision_ordinal}.json` rather than overwrite the prior decision;
- refuse candidate-verification continuation when the current decision is final;
- reconcile any single prepared next disposition event under the event commit rules before appending another event;
- for a final verified latest candidate, derive the only eligible promotion-intent path from the candidate path and current pointer's next promotion ordinal, then continue pre-commit promotion or post-commit materialization according to the intent recovery rules;
- preserve but never select a stale promotion intent;
- never call an Editor merely to reproduce an already persisted candidate;
- never seed a retry or later round from an unverified or rejected candidate.

Resume MUST read every required parser, assembler, inventory, normalization, semantic-verifier-policy, and contract version from the immutable job descriptor. If any descriptor-bound version is unavailable, resume MUST refuse. It MUST NOT silently replay under defaults or newer semantics.

Two implementations resuming the same validated transaction MUST reproduce the same candidate bytes and hashes before either may continue verification or promotion.

## Round Artifact Layout

A mutating vNext run MUST preserve at least:

```text
rounds/
  current_verified.json
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

Candidate creation events, candidates, canonical patch sets, payloads, semantic-verification attempts, candidate-verification attempts, promotion intents, and disposition events are immutable. Each candidate MUST bind one canonical `proposals/{proposal_id}/proposed_patch.json` by hash. `candidate_verification_current.json` is the only mutable candidate-local verification pointer; it MAY advance only under the append-only and hash-chain rules in `Candidate Verification Decision` and `Candidate Disposition Event Commit Rules`. Other convenience pointers MAY be updated only when their targets and hashes are explicit. A rejected or unverified candidate MUST remain inspectable but MUST NOT appear at `draft_after.md`.

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

Resume reconstructs the exact candidate from immutable base, patch, and payload hashes without invoking the Editor. Any hash mismatch blocks resume.

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

Fault injection at every promotion step yields exactly one authoritative current verified pointer. Before pointer commit, the old pointer remains authoritative and a prepared candidate-scoped intent and promotion event remain ineffective. After commit, the pointer's intent, verification, registration, and event bindings prove the promotion and recovery completes materialization without allocating another event or ordinal. A stale intent never promotes.

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
2. Transactional foundation: introduce immutable base artifacts, candidate isolation, run-wide candidate registration, commit-bound disposition events, current verified pointers, candidate-scoped promotion intents, and crash-safe promotion without enabling automatic promotion.
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
| Promotion intent and crash recovery | `Promotion And Current Verified Authority` |
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
| Proposal-to-promotion scheduling | `docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#round-scheduling-algorithm`, `#state-machine-full-transitions` | Replace direct full-document mutation transitions in vNext mode with proposal capture, deterministic validation, semantic verification, candidate decision, and atomic promotion transitions. |
| Budgets, retries, resume, and read-only status | `docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#round-budget-handling`, `#resume-policy` | Bind replay to the immutable descriptor and current verified pointer; preserve incomplete candidates; select latest candidate only through the run-wide creation-event chain; reconcile prepared decision and promotion artifacts; prohibit retries or resume from unverified bytes. |
| Public artifacts and attempt semantics | `docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#artifact-schemas-minimum-required-fields`, `#artifact-validation-policy` | Define and validate the vNext contract suite, immutable raw attempts, canonical `proposals/{proposal_id}/proposed_patch.json`, candidate creation events, verification artifacts and pointers, candidate-scoped promotion intents, commit-bound disposition events, current verified pointers, and terminal fields. |
| Versioned normalization and hashing | `docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#content-normalization-and-hashing` | Bind parser, assembler, inventory, normalization, candidate, report, and pointer hashes to the immutable job descriptor and exact persisted bytes. |
| Scope, finding admission, authority, and decisions | `docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#scope-contract`, `#expanding-contract-surface`, `#decision-summary` | Add pre-Editor finding classification, authority and prospective-spec gates, hash-bound decision responses, staleness checks, and candidate-blocking decision status. |
| Phase 2 and convergence lineage | `docs/specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md#phase-2-failure-handling`, `#target-matrix-precedence`, `#convergence-declaration`, `#reproducibility` | Require Phase 2, declaration generation, and reproducibility evidence to resolve and bind the promoted current verified draft rather than an unverified candidate or unverified `spec.md` mirror. |
| Operator defaults and recovery guidance | `docs/OPERATOR_QUICKSTART.md#mental-model`, `#recommended-defaults`, `#running-whetstone-from-an-agent`, `#recover-a-timeout`, `#terminal-states`, `#safety-rules` | Default unfamiliar jobs to reviewer-only mode; document proposal-only and verified-promotion opt-in, candidate inspection, safe recovery, and the prohibition on treating Editor output as current. |
| Current strop/apply-back operational surface | `docs/OPERATOR_QUICKSTART.md#review-before-apply-back`, `#apply-back`, `#troubleshooting` | Require strop/apply-back review and write paths to select only bytes referenced by a committed current verified pointer and to refuse unverified, rejected, or merely accepted candidates. |
| Strop/apply-back normative ownership gap | `docs/specs/WHETSTONE_COORDINATING_SPEC.md#spec-family-map` | The current family has no dedicated normative apply-back owner; the Quickstart is the current operational surface. Ratification MUST designate a normative owner for full strop/apply-back policy and route that owner to this leaf's verified-candidate eligibility guard. This leaf does not otherwise absorb external source-spec apply-back policy. |

## Ratification Checklist

Before this leaf becomes operative, the spec family MUST be amended so that:

- the coordinating spec routes candidate editing and promotion authority to this leaf;
- the scheduler distinguishes verified lineage from accepted and profile-clean status;
- scheduler transitions invoke proposal, validation, verification, and promotion gates;
- artifact validation defines the new public contract suite and attempt semantics;
- candidate registration, disposition-event commits, and candidate-scoped promotion intents have validated append-only and recovery contracts;
- scope and decision handling classifies findings before Editor invocation;
- Phase 2 evaluates only the current verified draft;
- status exposes current verified and latest candidate identities separately;
- resume uses the current verified pointer and immutable candidate artifacts;
- strop/apply-back selects only promoted verified bytes;
- operator guidance defaults unfamiliar jobs to reviewer-only mode;
- current full-document Editor output is disabled for automatic editing;
- the historical recurrence fixture and all P0 acceptance scenarios pass.

Until every checklist item is satisfied, automatic verified promotion MUST remain unavailable.
