# System version operations, version 1

Internal implementation contract under development for 18.8-M3. The operator
ratified the six-rule boundary in `docs/VNEXT_18_8_M3.md` on 2026-09-29. This file
does not activate a public suite or replace any frozen contract.

`patch-assembler-v3` consumes an inventory-bound `mutation-plan-v4`, ordinary
`patch-set-v2` Editor operations, and a distinct system-metadata context. The
descriptor and consuming suite must select and pin this algorithm plus the plan
and operation schemas. Old descriptors keep assembler v2 semantics. The context
binds phase, transition, exact source evidence and verified base pointer. Its
runtime owner must independently prove those sources and the scheduler gate;
a plausible context or operation artifact is not authority.

For ordinary rounds, the context binds the committed Reviewer feedback and
verified base. Editor operations retain their original finding attribution,
section limits and mutation ceilings. Preserve version anchors in Editor
payloads; adding, dropping or changing their kinds/labels, or changing an
Accepted status, refuses before registration. A canonical-content no-op gets
no version increment or status demotion.

Recognize numeric labels of one to three components in frontmatter `Version:`,
visible pre-section `Version:`, the first document title, or pre-section
`Status:`. Exclude fenced examples and non-title section bodies. All supported
anchors must agree exactly. Rank frontmatter, Version, title, then Status;
update all agreeing anchors. Refuse conflicting or ambiguous labels. Reuse
the scheduler's numeric round/entry arithmetic without the legacy selector.
Phase 1 mutating rounds demote an Accepted metadata status to Draft.

Apply exact byte-span system edits to the assembled, unnormalized proposal,
then normalize and hash the final candidate. An immutable version-operation
record binds all spans/preimages/replacements, phase/transition authority,
base/input/output/final candidate hashes and before/after labels. Its identity
is `op_` plus SHA-256 of canonical JSON
`["whetstone-system-version-operation-v1", record_without_operation_id]`.
The plan's existing full-field transaction preimage binds the system context;
the descriptor-bound assembler version participates in candidate identity.
Registration must reproduce and persist the operation with candidate evidence.

Preserve stable heading/unit lineage for exact metadata changes, with no new
headings, deleted units, inferred correspondence or silent reseeding. Refuse
an inventory topology/classification change the metadata comparator cannot
prove. Keep the Editor's actual mutation metrics for its budget; include all
actual system changes in blocking assertion metrics. System changes have
separate operation attribution and semantic obligations with exact final unit
text. They grant no deletion, weakening, invariant or scope waiver. Replay
must reproduce candidate bytes, map, inventory, operation and report exactly.

Independent semantic verification remains mandatory. A deterministic system
stamp is not a semantic pass. Registration, finality and verified-pointer
promotion remain governed by their existing owners. Neither candidate presence
nor a version label grants acceptance, stability, entry or convergence.

System-only Phase 2 entry admission, exact version history materialization and
joined lifecycle/recovery acceptance must be completed by the consuming runtime
before this contract can credit the M3 milestone. No legacy full-draft executor,
post-verification stamp or bridge maintenance shortcut is authorized.
