# 18.5 bounded acceptance closeout

Date: 2026-09-19. Starting checkpoint: `833ea21`.

**The three 18.5 implementation tasks are validated at the isolated component
and scripted proposal-only boundary.** No implementation defect or additional
test case was identified by this reconciliation. Public proposal-only release
qualification remains open. This closes the 18.5 portion of G3; the next bounded
step is 18.6 acceptance reconciliation.

This assessment reads the candidate leaf's transaction, registration and
deterministic-validation requirements alongside the v2 assembly supplement,
actual implementation and retained test outcomes. It reuses existing evidence;
it executes no runtime tests, changes no code or contracts, and activates no mode.
Older development-status text in the assembly supplement describes historical
consumer gaps. It does not override the implemented behavior or remove the
remaining release gates.

## Acceptance map

The IDs below bind to exact implementation files and existing test-method
identities in the [machine-readable record](audits/VNEXT_18_5_ACCEPTANCE_MAP.json).
“Validated” means the stated bounded implementation, not every possible input,
filesystem or release consumer.

| ID | Requirement and observed behavior | Existing executable evidence |
| --- | --- | --- |
| A1 | Immutable base and payload hashes are rechecked; operations use canonical dependency order and base coordinates; normalization occurs once. Unrelated sections retain literal bytes. | Assembly and proposal-protocol cases, including shared insertion anchors, altered payloads, overlap and global fence/heading damage. |
| A2 | Candidate section maps reproduce exact origins and identity transfer; tombstones survive; ambiguous correspondence refuses. | Section-lineage cases for repeatable IDs, descendants, moves, renames, duplicate headings and tampered maps/origins. |
| A3 | Inventories cover source bytes and protected facts; assertion evaluation, explicit correspondence and exact named-unit grants remain separate from semantic approval. | Inventory, assertion, inventory-diff, unit-correspondence, unit-lineage and unit-authorization modules. |
| A4 | Persisted candidate bytes/maps are independently replayed. Actual changed-section/unit budgets, finding attribution, blocking assertions, deletion/weakening and text hygiene determine the report. Semantic obligations remain outstanding. | Fourteen candidate-validation methods, including newly inserted descendants, altered reports/maps/bytes, ambiguity, named weakening and placeholders. |
| R1 | Candidate identity is reused; initial disposition is unverified; the creation event commits registration. A unique contiguous chain selects latest. A sole valid orphan is reconciled before later registration; conflicting evidence is preserved and refused. | G2's 21 registry methods, including every modeled publication prefix, duplicate retry, malformed chains, changed maps, lost acknowledgements and two serialized processes. |
| R2 | D8 permits one mutation owner on the admitted local root. Physical binding, fencing, fork/process behavior and uncertain publication require exact readback and durability barriers. | G2's 32 local-storage methods, including the corrected descriptor-path schema and process-CWD independence. Concurrent callers do not enable parallel writes. |
| P1 | Package and descriptor admission bind seed authority, supported algorithms/schemas, Reviewer inputs, scope, rules and assertions before Editor invocation. | Unit-preflight, proposal-admission and package modules; refusal paths assert zero calls or no root creation. |
| P2 | Durable Editor requests enforce invocation budgets and explicit continuation; completed output is handed off through exact receipts and barriers without another Editor call. | Native-editor, retry, request and handoff modules, including scripted shape repair, interrupted publication, wrong selectors and altered source evidence. |
| P3 | Deterministic pass remains `CANDIDATE_UNVERIFIED` with semantics `not_run`; deterministic failure rejects. Missing terminal output can be recovered without inventing a candidate or repeating a client call. Seed authority does not advance. | Closeout and stored-run modules, including corrected fresh-process reopen/replay evidence. |
| P4 | The seed Reviewer, explicit operator responses and selected receipts feed the guarded proposal-only journey. Reentry/status preserve evidence and require no redundant clients. | Seed-review, operator and CLI modules; the scripted endpoint stops at the unavailable semantic gate. Shipping qualification remains empty. |

The plan's repeatability, tampering, duplicate-registration, crash and competing
registration criteria map to A1–A4 and R1–R2. The three plan tasks map respectively
to A1–A4, R1–R2, and P1–P4. Candidate-wide assertions and actual changed-unit
budgets deferred by 18.4 are covered here; they are not silently deferred again.

## Evidence and source provenance

**302 distinct existing methods have passing evidence in this map:**

| Source | Methods credited | Qualification |
| --- | ---: | --- |
| Original reconciliation regression | 236 | Each selected method passed and its test bytes still match. The complete 1,153-method run had two failures; it is not described as a clean regression. |
| Corrected stored-proposal-run rerun | 13 | All passed after the subprocess fixture-import correction. The corrected test-file hash still matches. |
| G2 components | 53 | All 32 storage and 21 registry methods passed on the current source snapshot. They overlap G2/18.7 totals and must not be added to those totals. |

The evidence check verifies retained log digests, method identities and counts.
It also checks all 16 assembly-stage records and their 42 referenced log
digests/counts/success summaries as historical corroboration. Their overlapping
counts are not added to 302.

Static transitive local-import inspection covers 139 Python files used by the
carried proposal tests, including imports inside functions. The only change
within that closure is the already-corrected proposal-run test harness. The five
changed verified-runtime modules are outside it. This is source comparison,
not dynamic-import instrumentation or a new test execution.

Two contract files differ from the original baseline: D8 kernel documentation
and the tightened local-storage descriptor-path schema. G2 directly validates
the corrected storage binding and registry consumers. Earlier proposal results
are carried on unchanged Python; they are not misrepresented as fresh runs
against that schema. All files in G2's source manifest still match. The record
retains every baseline Python/contract difference and its disposition.

Raw reconciliation inputs and the local verification script are retained under
ignored `rounds/vnext-18-5-acceptance-001/`. Previous logs and records remain
unchanged. No blanket rerun was needed to resolve a concrete missing proof.

## Completed work and remaining boundaries

Completed at this checkpoint: the three bounded 18.5 implementation tasks,
including deterministic assembly/reporting, D8-backed registration and the
scripted seed-to-unverified-candidate journey. D8 design ratification and its
bounded audit remain closed.

Still partial: overall dependency/release acceptance across 18.5–18.7. The next
step is to map 18.6's independent semantic coverage/finality and answer/follow-up
criteria to existing evidence, credit current G2 results, and identify only
specific missing proof. No further generic 18.5 or storage fault batch is pending.

Still unqualified: a shipping descriptor-bound consuming suite, full release
P0/cross-implementation and compatibility qualification, other storage
environments and live-provider quality/soak. Scripted test providers and
process-local suites establish the bounded paths above, not these release claims.
Later scheduler/Phase 2/apply-back consumers and controlled activation remain
outside this work. No external transmission or authorization blocker exists for
this local evidence closeout.

Frozen suite 1 retains SHA-256
`09172fdc498f9d0189f3530b306fe1098a3c1d449482b68d21478d3786e1a950`.
All three shipping qualification maps remain empty. Runtime, tests, contracts,
owning specifications and legacy/bridge bytes are unchanged. No 18.8–18.9
implementation, push or external specification apply-back is included.
