# Preservation bridge developer components

The `preservation-bridge-v1` runtime capability remains unavailable. The first three implementation increments provide public contracts, structural checks, immutable proposal capture, trusted materialization, preliminary assessment and isolated local acceptance/repair. A subsequent [horizontal runtime checkpoint](../docs/PRESERVATION_RUNTIME_DEVELOPER.md) exercises the live runner with scripted clients; full runtime integration and qualification remain open. A `preservation_bridge` configuration block now fails preflight with `CONFIG_INVALID` rather than silently selecting legacy editing.

## Implemented

The ten artifact schemas under `schemas/` cover the bounded surface, line inventory, proposal admission/record, operator evidence, acceptance request/admission, assessment report, acceptance marker and terminal failure. `preservation_bridge.schema.json` contains shared definitions. The existing schema registry now enforces `minItems`, `maxItems` and `uniqueItems`, including JSON object equality and the distinction between booleans and numbers.

[The inventory module](../src/whetstone/preservation_inventory.py) implements strict UTF-8 physical-line partitioning, canonical section paths, duplicate sibling ordinals, fence-aware ownership, normative markers, exact content hashes and `bridge-lines-v1` unit IDs. Its matcher uses exact kind/content and unique maximum order-preserving correspondence within each section. It reports ambiguity rather than guessing; explicitly adopted entries can resolve the remaining correspondence.

[The contract module](../src/whetstone/preservation_contracts.py) provides:

| Function | What it checks |
|---|---|
| `read_ref` / `validate_reference_graph` | Exact bytes, relative confined regular-file references, typed bridge graph shapes and cycles. Raw drafts/client data do not introduce graph edges. |
| `validate_surface_bindings` | Recomputed inventory, exact base, approved scope, admitted same-base findings, allowed/frozen ownership and sensitive permissions. |
| `validate_proposal_bindings` | Raw-response extraction, exact raw/output identities, inventory and retained round-evidence bindings. Reproduces the pinned version/status transform from base, raw output and retained normal-round evidence; rejects altered Editor anchors and substituted summary claims. |
| `validate_evidence_bindings` | Exact proposal/output/acceptance-authorization bindings, evidence kinds and admitted finding references. This validates an attestation; it does not adopt or prove its semantic claim. |
| `complete_correspondence` | Total coverage, explicit mappings, per-effect evidence, separate additions and complete connected supersession groups. Inputs must already have valid byte bindings. |
| `validate_change_surface` | Permissions, relocation, finding attribution and changed-section/normative-unit caps on a completed relation. |
| `validate_untransformed_change` | Composes these checks for proposals with byte-identical raw and materialized output; returns a read-only `ValidatedChange`, never an acceptance marker. |

The low-level helpers are deliberately composable. Use the composed check for an untransformed artifact packet rather than treating one helper's success as the whole preservation decision. Neither interface checks current live authority or ordinary round acceptance, and neither writes artifacts or grants permission to install a draft.

## Proposal capture and preliminary assessment

[ProposalStore](../src/whetstone/preservation_proposals.py) is a developer library, with no CLI or production client adapter. `admit(...)` requires a run-root-relative approved surface Ref, an effective-config object with matching `phase`/`profile` and resolved settings, retained Reviewer Refs, round/profile/origin and a current authoritative draft path. The surface's base Ref must identify a separate immutable snapshot; its bytes must match the current draft. Config and byte-identical input mirrors are persisted before returning a single-use `ProposalTicket`. Referenced originals stay available and hash-bound; mirrors do not rewrite nested paths or approval identities.

`run_editor(ticket, callback)` supplies exact frozen `ProposalInputs` and invokes the adapter once. The callback returns original response bytes. `capture_response(ticket, bytes)` supports an already available response; `capture_revision(ticket, raw_bytes, summary)` supports supplied revisions and Orchestrator no-ops. Non-Editor admission requires `client_attempt_number=None`. Both callback-time and pre-execution input changes fail validation. The store keeps the response envelope, exact decoded raw draft, materialized draft, final inventory, normal summary, proposal and preliminary report separately. The retained normal summary describes the raw revision; any eventual canonical accepted summary must describe final materialized bytes.

Writes use create-if-absent atomic links with file/directory synchronization under a local writer lock. Conflicting files and symlink write paths are refused. Incomplete attempts consume their positive round-local number. Starting the same ticket twice is refused before a client call. Read the returned report Ref with `read_ref` for hash-checked inspection; `report(ticket)` is a convenience preview, not acceptance validation. A later persistence failure retains the report and binds it from a separate terminal-failure sidecar. If failure evidence also cannot be persisted, the error propagates.

[Materialization](../src/whetstone/preservation_materialization.py) changes only recorded UTF-8 version/status spans using existing version arithmetic. It computes a prospective stamp from retained round evidence, demotes Accepted status for Phase 1 revisions, and never stamps a true no-op. An unresolved serious finding withholds the prospective stamp; a no-op cannot resolve such findings by assertion. Version/status edits by the Editor fail. Verification reproduces bytes and parameters instead of trusting a hash chain. Comparison reverses only verified stamp spans/path effects into an internal view while keeping actual final output IDs and inventories. Adjacent content changes remain visible.

[Preliminary assessment](../src/whetstone/preservation_assessment.py) gives every base unit a disposition and covers every output unit as a mechanical successor, known addition or unmapped output. Missing correspondence/effect evidence stays pending without inventing a semantic claim. Frozen/unlisted content loss, forbidden concrete relocation/addition, provable limit overruns and corruption remain hard failures even alongside pending work. Duplicate multiplicity loss is checked without pretending to know which identical predecessor disappeared. The store preserves text-corruption and placeholder checks; size ratios do not decide preservation.

A preliminary `pass` means structural preservation is eligible for acceptance review. It does not clear residual issues, install a draft, emit an acceptance marker, advance version/history, or change scheduler state. Proposal client execution is not replayed by this library. The acceptance service can resume an identical incomplete local acceptance or repair a committed result; scheduler transitions remain the next increment. Phase 2 entry admission and inherited maintenance authority are supplied by the runtime adapter described below.

## Isolated acceptance and recovery

[AcceptanceService](../src/whetstone/preservation_acceptance.py) admits explicit requests, adopts validated effect evidence, recomputes complete correspondence and materialization, enforces permissions/limits and ordinary global issue/conflict gates, then creates an immutable acceptance marker before installation. Accepted-chain residuals are retained. Replay and repair use immutable inputs and the marker; old committed proposals never reinstall after authority advances. No acceptance call invokes a model.

[Review/adoption helpers](../src/whetstone/preservation_review.py) and four local CLI commands provide exact line/effect review, explicit adoption, request preparation and read-only dry-run. The [developer acceptance guide](../docs/PRESERVATION_ACCEPTANCE_DEVELOPER.md) documents the commands, persistence ordering and recovery. This service supports isolated contiguous Phase 1 proposal rounds; configured/live scheduler roots and Phase 2 are refused pending their adapter. It writes canonical draft/summary/unresolved/history artifacts, but no scheduler state or convergence result.

## Still required for slice 18.1

The separate [runtime developer adapter](../docs/PRESERVATION_RUNTIME_DEVELOPER.md) now supplies horizontal/focused continuation, supplied revisions, idempotent completion/readback, consumer guards and vertical source/consolidation cycles and closeout recovery. Vertical proposals retain the deterministic merged Reviewer artifact followed by the original source reviews; frozen configuration binds ordered source completion receipts. Source round numbers remain unchanged and every source must observe the same base. Later-cycle sources bind to the immediately preceding accepted consolidation; recovery reconstructs scheduling from receipts and markers. The runtime also supplies dedicated Phase 2 entry admission/acceptance, inherited maintenance no-ops and guarded Phase 2 rounds. Entry records null round/profile/client fields with empty feedback and null summary; it consumes no review budget. Guarded budget extensions, Phase 2 closeout-existing and complete qualification remain open.

In particular, `validate_untransformed_change` refuses transformed proposals. The proposal-binding checker permits a different maintenance base/inventory only when frozen provenance identifies the parent acceptance and the origin is `phase2_entry` or `orchestrator_noop`. Runtime admission and acceptance additionally validate that entire chain and require the immediate parent. This does not grant edit authority. These are explicit implementation boundaries, not restrictions on the final owning specification.

## Verification

Run from the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_preservation*.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

The foundation tests use the [toy corpus](../examples/fixtures/preservation_bridge/README.md), [fixed inventory vectors](../tests/fixtures/preservation/bridge_lines_v1.json), and an exhaustive small-sequence matching oracle. They cover accepted structural/evidence combinations and deliberate frozen losses, ambiguous/conflicting mappings, transitive supersession, relocation/caps, exact-byte tampering and invalid bindings. These tests do not run live models or qualify the entire bridge. The 90 focused preservation tests include proposal/acceptance journeys, commit/repair faults and pure Phase 2 stamping; the isolated step-3 full suite passed 389 tests. The horizontal runtime checkpoint adds runtime operator journeys; the later maintenance checkpoint adds entry, inherited authority, recovery and Phase 2 integration tests; remaining cross-path qualification is still open. No live models were invoked.

Normative owners remain the [artifact](../docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md#current-runtime-preservation-bridge-contracts), [scope](../docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#bridge-operator-authority), [candidate](../docs/specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#current-runtime-preservation-bridge) and [scheduler](../docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#preservation-bridge-lifecycle) leaves. Publishing these foundations does not activate the reserved capability or vNext editing.
