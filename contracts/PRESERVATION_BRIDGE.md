# Preservation bridge contract foundations

The `preservation-bridge-v1` runtime capability remains unavailable. This first implementation increment publishes the wire shapes and read-only structural checks needed to build it. A `preservation_bridge` configuration block now fails preflight with `CONFIG_INVALID` rather than silently selecting legacy editing.

## Implemented

The ten artifact schemas under `schemas/` cover the bounded surface, line inventory, proposal admission/record, operator evidence, acceptance request/admission, assessment report, acceptance marker and terminal failure. `preservation_bridge.schema.json` contains shared definitions. The existing schema registry now enforces `minItems`, `maxItems` and `uniqueItems`, including JSON object equality and the distinction between booleans and numbers.

[The inventory module](../src/whetstone/preservation_inventory.py) implements strict UTF-8 physical-line partitioning, canonical section paths, duplicate sibling ordinals, fence-aware ownership, normative markers, exact content hashes and `bridge-lines-v1` unit IDs. Its matcher uses exact kind/content and unique maximum order-preserving correspondence within each section. It reports ambiguity rather than guessing; explicitly adopted entries can resolve the remaining correspondence.

[The contract module](../src/whetstone/preservation_contracts.py) provides:

| Function | What it checks |
|---|---|
| `read_ref` / `validate_reference_graph` | Exact bytes, relative confined regular-file references, typed bridge graph shapes and cycles. Raw drafts/client data do not introduce graph edges. |
| `validate_surface_bindings` | Recomputed inventory, exact base, approved scope, admitted same-base findings, allowed/frozen ownership and sensitive permissions. |
| `validate_proposal_bindings` | Raw-response extraction, exact raw/output identities, inventory and retained round-evidence bindings. A transform hash chain alone is not proof that the transform is authorized. |
| `validate_evidence_bindings` | Exact proposal/output/acceptance-authorization bindings, evidence kinds and admitted finding references. This validates an attestation; it does not adopt or prove its semantic claim. |
| `complete_correspondence` | Total coverage, explicit mappings, per-effect evidence, separate additions and complete connected supersession groups. Inputs must already have valid byte bindings. |
| `validate_change_surface` | Permissions, relocation, finding attribution and changed-section/normative-unit caps on a completed relation. |
| `validate_untransformed_change` | Composes these checks for proposals with byte-identical raw and materialized output; returns a read-only `ValidatedChange`, never an acceptance marker. |

The low-level helpers are deliberately composable. Use the composed check for an untransformed artifact packet rather than treating one helper's success as the whole preservation decision. Neither interface checks current live authority or ordinary round acceptance, and neither writes artifacts or grants permission to install a draft.

## Still required for slice 18.1

Immutable proposal/acceptance admission and storage; trusted version/status materialization; preliminary pending/hard-failure assessment reports; local effect adoption and acceptance request/dry-run commands; ordinary-round gates; current-base recheck; single-writer commit and idempotent recovery; maintenance authorization inheritance; live/resumed/supplied/vertical integration; and Phase 2/declaration/strop consumption guards.

In particular, `validate_untransformed_change` refuses transformed proposals. The foundation proposal-binding checker also refuses inherited maintenance surfaces whose base/inventory differs; accepting that case requires the later validated acceptance-chain service. These are explicit implementation boundaries, not restrictions on the final owning specification.

## Verification

Run from the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_preservation*.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

The foundation tests use the [toy corpus](../examples/fixtures/preservation_bridge/README.md), [fixed inventory vectors](../tests/fixtures/preservation/bridge_lines_v1.json), and an exhaustive small-sequence matching oracle. They cover accepted structural/evidence combinations and deliberate frozen losses, ambiguous/conflicting mappings, transitive supersession, relocation/caps, exact-byte tampering and invalid bindings. These tests do not run live models or qualify the entire bridge. Phase 2 stamps, commit crashes and the remaining operator journeys are still future integration tests.

Normative owners remain the [artifact](../docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#current-runtime-preservation-bridge-contracts), [scope](../docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#bridge-operator-authority), [candidate](../docs/specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#current-runtime-preservation-bridge) and [scheduler](../docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#preservation-bridge-lifecycle) leaves. Publishing these foundations does not activate the reserved capability or vNext editing.
