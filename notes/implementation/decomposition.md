# Spec Decomposition Implementation Note

## Spec Basis

- Canonical spec: `spec.md`
- Spec version: `0.61`
- Governing section: `SPEC DECOMPOSITION WORKFLOW`

This note defines the intended implementation shape for Whetstone spec decomposition. It is not a replacement for the canonical spec. If this note and `spec.md` disagree, `spec.md` wins.

## Purpose

Spec decomposition lets Whetstone split an overloaded source spec into a governed spec family without losing normative content, provenance, or authority boundaries.

The implementation must support more than HLD extraction. A source spec may decompose into:

- a coordinating spec plus leaf specs
- peer specs
- parent/child specs
- appendix-style extracted contracts
- no split, if the source spec should remain singular

The first production implementation should be conservative: plan and audit before extraction, and never rewrite content during decomposition.

## Full Capability Shape

### 1. Plan

Inventory the source spec and produce a proposed decomposition plan.

Required behavior:

- compute source hash
- inventory Markdown headings and stable section IDs
- record source line ranges
- identify normative statements
- identify obvious artifacts, schemas, roles, states, and cross-references where mechanically detectable
- accept an optional operator-supplied decomposition map
- propose or validate target specs
- assign each source section to a target, duplicated mapping, retired mapping, or unassigned status
- write `decomposition_plan.json`
- write human-readable `decomposition_plan.md`
- avoid source mutation and target file writes

### 2. Approve

Persist operator approval for a specific plan.

Required behavior:

- compute plan hash
- bind approval to source hash, plan hash, authority topology, target paths, and extraction mode
- reject approval when the current source hash differs from the planned source hash
- write an approved plan artifact or update the plan approval block

### 3. Extract

Create target specs from an approved plan by copy-first extraction.

Required behavior:

- validate source hash against approved plan
- validate target paths and overwrite policy
- create target specs with provenance headers
- copy source content without paraphrase, summary, deduplication, or semantic normalization
- preserve code blocks, tables, enum values, examples, artifact paths, schema snippets, and rationale notes
- write `decomposition_manifest.json`

### 4. Audit

Verify decomposition coverage and authority safety.

Required behavior:

- verify every source section is assigned, duplicated, retired, or unassigned
- verify every normative statement is assigned, duplicated, retired, or unmapped
- fail audit when any normative statement remains unmapped
- detect duplicated authority without an explicit precedence, shared-authority, or reconciliation rule
- verify provenance headers and target hashes
- write `coverage_matrix.md`
- write `unmapped_requirements.md` when needed
- write `duplicated_authority_report.md` when needed

### 5. Promote

Mark a decomposed spec family as authoritative.

Required behavior:

- require successful audit
- require operator acceptance of the decomposition manifest
- mark manifest `promoted = true`
- preserve the original source spec as pre-promotion authority history
- optionally write coordinating-spec backreferences after promotion

## Architecture

Recommended modules:

- `decomposition.py`: orchestration and public operations
- `decomposition_inventory.py`: Markdown section, normative statement, and reference inventory
- `decomposition_map.py`: operator map parsing and validation
- `decomposition_plan.py`: plan construction and plan hashing
- `decomposition_extract.py`: copy-first target creation
- `decomposition_audit.py`: coverage, unmapped requirement, and duplicate-authority checks

The first slice may use fewer modules if the code remains small, but the design should not bake Whetstone-specific leaf specs into the core planner.

## Artifact Model

### `decomposition_plan.json`

Purpose: proposed or approved source-to-target mapping.

Minimum fields come from `spec.md` v0.61. Additional implementation fields may be added if they are deterministic and useful.

### `decomposition_plan.md`

Purpose: human-readable review artifact for operator approval.

Should include:

- source path and hash
- authority topology
- proposed target specs
- source sections per target
- normative statement counts
- unassigned sections
- retired sections
- duplicated sections
- extraction risks

### `decomposition_manifest.json`

Purpose: authoritative provenance record after extraction.

Should include:

- approved plan hash
- source spec hash
- target spec hashes
- target roles
- source line ranges
- provenance header status
- coverage status
- promotion status

### `coverage_matrix.md`

Purpose: human-readable proof that source content is covered.

Should group source sections and normative statements by target spec and coverage status.

### `unmapped_requirements.md`

Purpose: list normative statements that prevent a successful audit.

Only written when unmapped normative statements exist.

### `duplicated_authority_report.md`

Purpose: list duplicated authority surfaces that need explicit precedence or shared-authority rules.

Only written when duplicated authority requires review.

## CLI Surface

Preferred command shape:

```text
whetstone decompose plan --source spec.md --output-dir decomposition/
whetstone decompose approve --plan decomposition/decomposition_plan.json
whetstone decompose extract --plan decomposition/decomposition_plan.json
whetstone decompose audit --manifest decomposition/decomposition_manifest.json
whetstone decompose promote --manifest decomposition/decomposition_manifest.json
```

Compatibility shortcuts may be added later, but the subcommand shape keeps the lifecycle explicit.

## Slice Plan

### Slice 1: Plan Only

Goal: deterministic planning artifact with no target writes.

Scope:

- add `whetstone decompose plan`
- source section inventory
- stable section IDs
- source line ranges
- simple normative statement inventory
- optional operator map input
- generic target spec model
- write JSON and Markdown plan artifacts
- no extraction
- no source mutation

Acceptance criteria:

- running against `spec.md` writes valid plan artifacts
- plan includes source hash and line ranges
- plan can represent `coordinated_family`, `peer_family`, `parent_child`, `appendix_extraction`, and `no_split`
- unassigned source sections are explicit
- tests cover plan generation and no target writes

### Slice 2: Approval

Goal: bind operator approval to an exact plan and source hash.

Scope:

- add `whetstone decompose approve`
- compute plan hash
- reject hash drift
- persist approval metadata
- test approval and hash mismatch

### Slice 3: Extract

Goal: create target specs through lossless copy-first extraction.

Scope:

- add `whetstone decompose extract`
- validate approved plan
- validate target paths
- create provenance headers
- copy source ranges
- write manifest
- test no paraphrase and overwrite guards

### Slice 4: Audit

Goal: prove coverage and surface authority risks.

Scope:

- add `whetstone decompose audit`
- produce coverage matrix
- detect unmapped normative statements
- detect duplicated authority lacking a rule
- update manifest coverage status
- test failing and passing audits

### Slice 5: Promote

Goal: mark decomposed family authoritative after audit and operator acceptance.

Scope:

- add `whetstone decompose promote`
- require successful audit
- require operator confirmation
- update manifest promotion fields
- optionally write coordinating-spec backreferences

## Non-Goals

- No LLM rewrite during decomposition.
- No automatic convergence review of target specs.
- No source spec mutation during planning.
- No hidden authority changes.
- No hardcoded Whetstone leaf taxonomy in the generic planner.
- No automatic deletion or replacement of the source spec.

## Design Constraints

- Decomposition is provenance machinery, not a spec-polishing pass.
- Extraction is copy-first and lossless by default.
- Creative cleanup belongs in later Whetstone runs against target specs.
- Operator approval is required before any target spec is written.
- Hash guards are mandatory for approval and extraction.
- Target path safety must be conservative.
- The planner may propose, but the approved plan is the authority.

## Open Questions

- Should Slice 1 include a built-in heuristic proposer, or require an operator map for all non-`no_split` plans?
- What is the minimum useful decomposition map format?
- Should normative statement inventory operate at line, paragraph, bullet, or sentence granularity?
- Should target specs inherit the source version label, start at `0.01`, or use a decomposition-specific version?
- Should promotion write backreferences into a coordinating spec, or should that remain a separate explicit command?
- How should Whetstone represent shared terminology that belongs to multiple target specs but should not be duplicated normatively?

