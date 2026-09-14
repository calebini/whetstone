# Semantic preservation coverage v1 (unactivated 18.6 component)

This proposed supplement consumes inventory-v2 deterministic evidence. It does not change the frozen first contract suite, register a shipping consumer, invoke a verifier, decide uncertainty policy, or advance candidate/draft authority. Storage-backed registration, complete verifier context, independent invocation, aggregate semantic validation, and decision journaling remain separate requirements.

## Derivation and bindings

`prepare_semantic_obligations` independently replays the complete preservation assessment and candidate inventory from their exact assessment inputs. It refuses altered evidence, incomplete metrics, missing candidate inventory, and deterministic failure before producing any semantic obligations. The caller must first validate committed base lineage and the candidate's registration; local replay cannot establish either.

The closed `vnext-semantic-obligations-v1` packet binds the job and transaction, candidate, base/candidate bytes, registered candidate map locator/hash, patch, both inventories, preservation report, mutation plan and job descriptor. The registered map locator is supplied through assessment inputs; it is not chosen by the Verifier. These hashes bind authority, invariants, role configuration and policy through the immutable descriptor and plan, but do not substitute for giving their actual content to the independent Verifier.

Every `semantic_required` report row creates one unit obligation, including addition rows for newly minted successor units. Every explicit correspondence group creates a separate group obligation, even when a one-to-one group has unchanged content. Its exact base and successor endpoint sets come from the independently reproduced report. Group coverage cannot replace individual-unit coverage. Multiple rows referring to one successor do not duplicate that successor within a group.

Each endpoint contains its side (`base` or `candidate`), complete inventory unit record, and exact UTF-8 text at that record's byte offsets. The text must reproduce the unit's content hash. A retained unit ID on both sides therefore cannot hide a changed content hash or position. Source parser diagnostics generate an additional mandatory baseline assessment even after candidate syntax is repaired. Complete base/candidate documents remain required verifier context; endpoint excerpts alone are insufficient to assess unrelated change or obscured semantics.

An obligation ID is `sem_` plus SHA-256 of canonical JSON:

```text
["whetstone-semantic-obligation-v1", bindings, subject]
```

`subject` contains exactly `kind`, `report_rows`, `base_units`, `candidate_units`, and `baseline_diagnostics`. Rows are sorted by canonical JSON bytes; endpoint sets by unit ID; obligations by obligation ID. Diagnostics preserve the reproduced report's order. An obligation hash is the SHA-256 of the complete canonical obligation including its ID. Any bound input or endpoint change changes the obligation identity. Generated packets are detached from input objects.

## Coverage response

The closed `vnext-semantic-coverage-v1` response names the exact complete obligations packet hash and supplies exactly one result for every obligation. Each result copies the obligation ID/hash, contains non-whitespace evidence, and has `result = pass | fail | uncertain`. Unknown, duplicate, omitted, stale or malformed subjects are artifact-invalid. Row ordering does not grant authority and need not match request order.

The coverage validator consumes trusted, independently generated or exactly replayed obligations, never client-provided replacement obligations. It rechecks obligation identities and response bindings. Hashes prevent substitution and omission; they do not prove that prose evidence is true or sufficient. That judgment belongs to the separate Verifier, with complete context.

`pass` means the Verifier's assessment that the bound subject satisfies the admitted preservation requirements, including any exact authorized effects. Structural correspondence and a deterministic `authorized` flag are not semantic equivalence. The consumer retains `fail` and `uncertain` unchanged for the separately versioned fail-closed semantic policy. It emits no aggregate verdict, operator approval, disposition or promotion signal. Complete passing coverage cannot substitute for finding resolution, authority compliance, unrelated/lost-semantic assessment, operation classification or semantic assertions.

The schemas and algorithm are proposed and unregistered. The future semantic consuming suite must pin them before any runtime invocation uses them. The frozen first suite and the current proposal-only qualification map remain unchanged.
