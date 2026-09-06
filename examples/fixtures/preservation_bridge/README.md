# Preservation bridge toy specs

Seven fictional project specs and fixed proposal variants for observing the two-stage preservation bridge. They deliberately include useful edits as well as changes that should require evidence or fail an independent gate. No live review has been run and these fixtures do not establish bridge qualification.

The live bridge remains unavailable. Its schema/inventory foundations and read-only validators now have [executable tests](../../../contracts/PRESERVATION_BRIDGE.md); transaction and runtime integration remain pending. These are source texts and test-design instructions, not supported CLI inputs for an acceptance command. `cases.json` is a local fixture catalog, not a public Whetstone schema. Do not submit it as a scope contract, finding, surface, proposal, evidence or acceptance request. The implementation must generate and validate those artifacts using the actual supported contracts.

## Start here

1. Begin with C01: one useful clarification, exact output review, then same-root acceptance without another Editor call.
2. Try C04: satisfy that kind of request while quietly removing an unrelated required schema field. The frozen loss must block acceptance.
3. Try C08: identical duplicate text makes automatic matching ambiguous; resolve the precise mapping and deletion explicitly.
4. Try C11/C12: an added exception weakens an unchanged requirement. Inspect the semantic effect and authorize it separately if it is intentional.
5. Continue through the matrix and the lifecycle exercises below.

Use an isolated copy for every scenario. The checked-in base files stay unchanged. Fixed proposals let a scripted Editor or the eventual supplied-revision path exercise the exact case; asking a live model to edit the bases is a later usability experiment and may produce different behavior. A Markdown proposal is extracted draft content, not a complete Editor response: the harness must supply a schema-valid response/summary and eligible ordinary-round evidence. No real model is needed for deterministic tests.

## Setup rules

The case instructions describe approval intent, not fabricated approval. Generate the exact base inventory, approved scope, valid same-base Reviewer findings and the allowed surface before proposal generation. Attribute every changed or added unit to an admitted finding. Apply per-case allowed/frozen units, types, relocation maps and limits literally; permissions for one case do not carry into another. Separators and headings remain protected too.

After materialization, generate exact unit IDs and evidence bindings for affirmative operator adoption (or explicitly scripted operator decisions in tests). `cases.json` stores paths, SHA-256 digests and selected one-based line relations to make this reproducible. Those locators are not stable cross-draft identities or ready-made signed approvals. Recompute relations against the final inventory and account for every untouched unit as well. Never pair independent arrays by position.

A positive outcome always assumes valid artifacts and all ordinary round gates pass. Passing preservation alone cannot clear residual findings, mark a profile clean or declare convergence. A known hard failure takes precedence over missing evidence. Missing evidence can pause a proposal but must reject submitted acceptance.

Semantic examples need honest effect review. The bridge checks exact bindings and permitted dispositions; it does not mechanically prove prose equivalence or expose a knowingly false operator attestation. In particular, C11 must not be reported as guaranteed automatic detection of every disguised exception.

## Case matrix

| Case | Base | Mechanisms and expected observations |
|---|---|---|
| Clarification / no-op | [base](01_clarification/base.md) | C01–C02: pending equivalence, successful approval, unchanged output and residual gates. |
| Ledger export | [base](02_contract_loss/base.md) | C03–C06: positive control; reject lost schema field, table row or failure code on a frozen surface. |
| Dispatch worker | [base](03_correspondence/base.md) | C07–C09: reflow, ambiguous duplicate matching, explicit deletion, conflicting relations and counting. |
| Receipt service | [base](04_semantic_effects/base.md) | C10–C13: harmless addition, exception affecting retained text, new authorization, explicit weakening. |
| Archive store | [base](05_relocation/base.md) | C14–C16: cross-section ownership, exact relocation permission and numeric caps. |
| Parser probe | [base](06_parser_and_versions/base.md) | C17–C20: fences, preamble, duplicate headings, byte coverage and provenance-sensitive version changes. |
| Session gateway | [base](07_supersession/base.md) | C21–C23: complete many-to-one attestation, incomplete groups and output double counting. |

## Detailed scenarios

The setup and expected outcomes below mirror the machine-readable [catalog](cases.json). Relations in the catalog identify the exact selected lines for the correspondence exercises.

### 01_clarification: Useful clarification and exact no-op

Admit one finding asking for equivalent wording of the minimum retry delay. Allow only the first Delivery requirement, with clarify/reword; freeze Storage and the other Delivery requirement. No delete, weaken, move or add permission.

Use an ordinary otherwise-eligible Phase 1 round. This spec has no version anchor, so the trusted transform list is empty.

- **C01 — Equivalent one-to-one rewrite** ([proposal](01_clarification/clarified.md)): Proposal waits for equivalence/correspondence evidence. Exact adopted equivalence plus all ordinary gates allows same-root acceptance with zero further Editor calls.
- **C02 — Byte-identical no-op** ([proposal](01_clarification/base.md)): Use a separate valid no-op admission with no serious residuals and no mutating findings. Empty evidence can pass; no version increment. Replay the committed result without another acceptance or history entry. Also test the same bytes with an unresolved serious finding: no-op handling must not fabricate its resolution.

### 02_contract_loss: Small hidden losses in a large mostly-preserved response

Admit only equivalent wording of the first Delivery requirement. Freeze Record Schema, States, Failure Codes, Recovery and all other units. Allow clarify/reword, with no deletion.

The negative proposals retain most bytes and include the requested clarification. Do not use size ratio or claimed finding resolution as preservation evidence.

- **C03 — Positive control** ([proposal](02_contract_loss/clarified.md)): Pending equivalence; valid exact evidence and ordinary eligibility can pass.
- **C04 — Delete a fenced schema field** ([proposal](02_contract_loss/missing_field.md)): Reject during proposal assessment for a known frozen-surface loss; missing clarification evidence must not downgrade the hard failure to a harmless pause. Submitted acceptance under the same surface also rejects. Authoritative bytes and residuals remain unchanged.
- **C05 — Delete a table row** ([proposal](02_contract_loss/missing_state.md)): Reject during proposal assessment for a known frozen-surface loss; missing clarification evidence must not downgrade the hard failure to a harmless pause. Submitted acceptance under the same surface also rejects. Authoritative bytes and residuals remain unchanged.
- **C06 — Delete an enum-like failure code** ([proposal](02_contract_loss/missing_enum.md)): Reject during proposal assessment for a known frozen-surface loss; missing clarification evidence must not downgrade the hard failure to a harmless pause. Submitted acceptance under the same surface also rejects. Authoritative bytes and residuals remain unchanged.

### 03_correspondence: Duplicate matching and one-to-many reflow

For C07 allow reword of the combined Retry Policy line only, with max_changed_normative_units=1. Preserve both duplicate lines and Audit. The two successor lines must be accounted for as successors, not additions.

For C08/C09 use a separate surface permitting delete for both duplicate candidates (deletion_allowed and both IDs in authorized_deletion_unit_ids), but require the operator to select the exact removed predecessor after output exists. Other lines remain preserved.

- **C07 — One predecessor to two equivalent successor lines** ([proposal](03_correspondence/reflowed.md)): Pending without equivalence; pass with the complete one-to-many attestation and ordinary gates. The normative cap counts the one changed base unit once, not both matched successors.
- **C08 — Ambiguous duplicate removal resolved explicitly** ([proposal](03_correspondence/one_duplicate_removed.md)): The edited direct-content sequence has two possible maximum order-preserving matches for the remaining duplicate. Proposal records pending correspondence/deletion, never guesses. Explicitly preserve the first predecessor and authorize deletion of the second; separate valid evidence kinds can then pass.
- **C09 — Conflicting evidence over the same output** ([proposal](03_correspondence/one_duplicate_removed.md)): Supply C08 evidence plus a second record claiming the second predecessor is preserved to that same successor. Acceptance rejects the conflicting relation/unauthorized successor sharing. Do not infer a pairing from independent ID arrays.

### 04_semantic_effects: Additions and weakening without deleting the old words

For C10 admit an observability finding. For C11/C12 instead admit a finding asking to make maintenance acknowledgment behavior explicit; retain its original round evidence throughout. Initially allow add only in Operations and keep Acknowledgment frozen. Bind evidence only after inspecting exact output. The new C12 authorization must still satisfy the original ordinary-round findings.

For C13 approve a separate retention-policy finding and surface permitting weaken on the retention requirement, with weakening_allowed=true. No other requirement is editable.

These cases exercise accountable semantic attestation. The bridge validates records; it cannot prove a dishonest assertion about arbitrary prose false.

- **C10 — A genuinely additive observability requirement** ([proposal](04_semantic_effects/harmless_addition.md)): Proposal awaits addition evidence. Truthful exact attest_addition with valid finding attribution can pass without weakening any base requirement.
- **C11 — Exception weakens a verbatim retained obligation** ([proposal](04_semantic_effects/maintenance_exception.md)): With no evidence, withhold acceptance. On honest effect review, identify weakening of the storage-before-acknowledgment base unit. The original add-only/frozen authorization cannot accept it; addition approval alone is insufficient. Do not require a semantic detector to infer the exception mechanically.
- **C12 — Deliberately approve the exception in a new acceptance attempt** ([proposal](04_semantic_effects/maintenance_exception.md)): Prepare newly approved same-base scope, findings and surface permitting the exact addition and weakening; remove the affected freeze. Use truthful addition evidence that discloses the separately authorized weakening plus an authorize_weakening record for the retained obligation. Complete checks may pass in the same root, preserving earlier reports.
- **C13 — MUST becomes SHOULD** ([proposal](04_semantic_effects/weakened_retention.md)): With permitted weakening but no exact effect evidence, proposal remains pending and submitted acceptance rejects. Exact authorize_weakening and complete correspondence can pass. A configuration permission or Editor claim alone cannot pass.

### 05_relocation: Moving unchanged words across section ownership

Keep headings, separators, timestamps, access checks and Operations unchanged. The move takes the encryption line from Archive Rules to Retrieval Rules without changing its text.

C14 uses a valid generic delete/add surface: both sections allowed, the source unit allowed for delete with explicit deletion permissions, add allowed at destination, no relocation mapping. C15 instead permits move with an exact source-unit/destination-section relocation; cap changed sections at 2 and normative units at 1.

- **C14 — Delete/add permissions cannot launder a move** ([proposal](05_relocation/moved.md)): The same line disappears from one section and appears in another with changed ownership. Reject known unauthorized relocation; where a matcher cannot decide, require explicit correspondence and still refuse acceptance without relocation authority. Delete plus add approvals are not a substitute.
- **C15 — Explicitly authorized relocation** ([proposal](05_relocation/moved.md)): Pending movement/equivalence evidence, then pass with exact relocation mapping, adopted moved correspondence and ordinary gates. Count both sections and one normative base unit.
- **C16 — Evidence does not waive numeric caps** ([proposal](05_relocation/moved.md)): Use the complete C15 mapping/evidence but a separately approved max_changed_sections=1 surface. Reject for exceeding the two affected section paths.

### 06_parser_and_versions: All-line inventory, exact bytes, and trusted version boundaries

Inventory all physical lines, including preamble, separators, both kinds of fences, duplicate heading ordinals, setext-like body, indented pseudo-heading, Unicode and trailing child content. Only the real root, Payload and two Notes headings create named sections.

For C18 hold the entire content frozen and use a legitimate otherwise-eligible Phase 2 entry maintenance operation from a prior accepted bridge marker. C17, C19 and C20 are separate Editor proposals under a valid nonempty finding set and surface permitting only a Notes clarification; Payload and parent content are frozen.

phase2_materialized.md is expected trusted output, not an Editor input. editor_version_change.md deliberately has identical bytes but a different provenance.

- **C17 — Editor changes the visible version** ([proposal](06_parser_and_versions/editor_version_change.md)): Reject untrusted_version_edit. Do not restore the anchor and claim the edit was trusted.
- **C18 — Legitimate Phase 2 entry stamp** ([proposal](06_parser_and_versions/base.md)): With prior accepted lineage and Phase 1 handoff eligibility, trusted 0.17 -> 1.0 materialization may pass with empty semantic evidence. Reverse only the verified title span for correspondence; descendant path changes are not user changes. No fabricated numbered round or review-budget charge.
- **C19 — A heading-like fence comment must not hide a schema field** ([proposal](06_parser_and_versions/fenced_field_loss.md)): Removing the required_token line from frozen Payload rejects; it remains a covered fence_body unit, not an unowned fragment.
- **C20 — A trusted heading stamp cannot exempt parent content** ([proposal](06_parser_and_versions/raw_adjacent_edit.md)): Reject the changed frozen parent requirement even if a prospective version stamp also changes the root and descendant paths. Trusted spans do not authorize adjacent prose.

Additional parser input: [mixed_endings.md](06_parser_and_versions/mixed_endings.md). Seven physical line units partition all 99 bytes including BOM and mixed terminators; last line is unterminated. Do not normalize this specimen before inventorying it. Byte count is bound by its catalog asset record.

### 07_supersession: Consolidation requires a complete shared-successor group

Admit a finding requesting consolidation without loss. Allow supersede for both Access predecessor units, list both authorized_supersession_unit_ids, allow the successor location, and cap changed normative units at 2. Do not grant delete permission. Freeze Audit.

Both obligations remain in the consolidated line. The expected success is explicitly operator-attested equal coverage, not machine-proven equivalence.

- **C21 — Two predecessors to one successor** ([proposal](07_supersession/consolidated.md)): Pending without supersession evidence. One complete equal-or-stronger attestation containing both predecessors and the shared successor can pass without deletion permission. Count two changed normative base units.
- **C22 — Split or incomplete group approval** ([proposal](07_supersession/consolidated.md)): Submit only one predecessor, or two separate supersession records each approving half the group. Acceptance rejects incomplete shared-group evidence; it cannot combine fragments to manufacture a complete attestation.
- **C23 — Every output unit has exactly one role** ([proposal](07_supersession/consolidated.md)): Start with the complete C21 relation, then also list its shared successor as an addition. Acceptance rejects successor/addition overlap even though all IDs resolve.

## Lifecycle exercises

Run these against C01 or C21 after the bridge service exists. These alter runtime artifacts or execution timing in isolated test roots; they are not additional edits to the toy base files.

| Exercise | Controlled action | Required observation |
|---|---|---|
| New same-root authorization | Retain a pending/rejected proposal, then submit newly approved evidence/surface for its unchanged current base. | New acceptance attempt K, same proposal M, earlier reports intact; no Editor call. |
| Stale base | Prepare approval, then advance authoritative lineage through another valid acceptance before submitting it. | Refuse the old proposal; do not rebase or install it. |
| Exact-byte tampering | After binding a request, alter retained raw/materialized content or only its line endings. | Hash/binding validation fails even if normalized text would match. |
| Frozen round evidence | Substitute config, Reviewer feedback or Editor summary after proposal capture, or choose a smaller acceptance surface to hide residuals. | Reject substitution; retain original ordinary-round gates. |
| Dry-run | Preview a valid acceptance request and compare filesystem/authority/history before and after. | No admission, commit, history mutation or model call. |
| Before commit crash | Interrupt after final report but before marker creation. | No authority advance. Recovery retains frozen inputs and cannot pretend a commit occurred. |
| After commit crash | Interrupt mirror/history/scheduler updates after the marker is created. | Checked repair completes once without a second marker, stamp or budget charge. |
| Historical replay | Commit, subsequently advance authority, then resubmit the original proposal. | Return its historical result without reinstalling it. |
| Competing local operations | Race valid requests from two local processes against the same current base. | Single-writer exclusion and base recheck prevent conflicting commits; pending repair blocks another commit. |
| Rejected-output escape | Attempt supported soft-budget, recovery, Phase 2/declaration and dry/live strop paths after rejection. | Only prior accepted lineage is eligible; no override turns a rejected draft into authority. |

## What to record

For each run record the scenario ID, exact fixture hashes, actual source commit, generated proposal/acceptance references, initial permissions, displayed effects and mappings, adopted evidence, pending obligations/hard failures, authoritative hash before/after, operator interaction count, model-call count, round/budget/history changes and final result. For failures, preserve all reports and confirm the source copy was not advanced. Mark actual observations separately from the expectations in this corpus.

These scenarios cover targeted mechanisms, not every bridge conformance requirement. Invalid UTF-8, every cap boundary, all parser edge cases, status demotion and every recovery permutation still need the owning implementation's focused tests. Live trials require their own bounded scope and payload authorization; they are not triggered by creating these files.

## Design authority

- [Bridge safety and qualification](../../../docs/specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#current-runtime-preservation-bridge)
- [Inventory, materialization and artifact contracts](../../../docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#current-runtime-preservation-bridge-contracts)
- [Operator evidence and explicit correspondence](../../../docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#bridge-operator-authority)
- [Lifecycle, commit and downstream consumers](../../../docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#preservation-bridge-lifecycle)
