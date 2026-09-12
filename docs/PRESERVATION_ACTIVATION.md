# Run Whetstone with preservation enforcement

`preservation-bridge-v1` is available by explicit configuration in a fresh isolated run root. It covers the qualified current-runtime paths, including horizontal/vertical Phase 1, focused work, local acceptance and supported continuation, Phase 2 maintenance and bounded closeout, and guarded strop. Omitting the block retains `legacy_unguarded` editing. Candidate editing and `verified_promotion` remain separate, inactive vNext capabilities.

## Ask your agent

> Run Whetstone Phase 1 on this spec with preservation enforcement. Allow clarifications in the retry section, freeze the other sections, and show me the proposed change boundary before starting. Bring any exact-effect approvals back to me, and keep source apply-back separate.

The agent prepares the run, inventory and bounded surface; you review the concrete allowed/frozen boundary. After an Editor proposal exists, it can show the exact changed lines and correspondence for any required effect adoption. Requesting preservation does not itself attest that an unseen rewrite is equivalent. Existing explicit approvals still apply within their stated scope; a new root or repeated confirmation is not required for routine local acceptance of the same proposal.

For an assessment-only request, use the existing reviewer-only workflow. Preservation configuration does not turn an assessment into permission to rewrite.

## Prepare and activate

Follow the [Quickstart](OPERATOR_QUICKSTART.md#create-an-isolated-run) to copy the source into a fresh root and configure the clients, workflow and budgets. Keep the canonical bridge paths: `spec.md`, `spec.history.md` and `rounds/`. An existing legacy run cannot be converted to enforcement, and an enforced run cannot be overwritten or resumed without its bridge configuration.

Before starting a guarded editing run:

1. Retain a separate immutable snapshot of the exact `spec.md` bytes. Use `whetstone.preservation_inventory.build_inventory(raw_bytes, path=relative_snapshot_path)` to generate its `bridge-lines-v1` inventory. Store it as JSON and calculate Refs from exact saved bytes using `sha256_bytes`; normalized draft hashes are not Ref hashes.
2. Prepare an approved scope contract with the existing `intake` workflow. Configure `scope_contract.path` to identify those same bytes. Every guarded workflow requires the approved scope, including `standard`.
3. Prepare a `bounded-change-surface-v1` artifact using [the closed schema](../contracts/schemas/bounded_change_surface.schema.json). Bind the snapshot, inventory, approved scope and any admitted same-base finding artifacts. Select allowed and frozen sections/units, allowed change types, relocation permissions and caps. Unlisted content is preserved by default. Deletion, weakening and supersession need their specific permissions and later exact-effect evidence; a broad editing instruction does not grant them. Record the actual operator's approval of this concrete surface. An empty finding-source list does not authorize inventing finding references.
4. Keep referenced inputs immutable and within the run root. Validate the saved surface with `whetstone.preservation_contracts.validate_surface_bindings(root, surface_ref)`. Its base must equal the current `spec.md` bytes, and its scope must equal the configured scope. The runtime repeats admission and pre-Editor checks; a library validation alone does not authorize installation.
5. Add the block below to `orchestrator_config.yaml`, using the exact hash of the approved surface file. The agent handles artifact serialization and hashes; the operator reviews the scope and effects. There is no surface-generation CLI or standalone activation flag.

```yaml
preservation_bridge:
  mode: enforce
  capability_version: preservation-bridge-v1
  allowed_change_surface:
    path: ./rounds/intake/bounded_change_surface.json
    sha256: "<SHA-256 of exact saved surface bytes>"
  predecessor_report: null
```

`predecessor_report` may be omitted. When used, it is a confined Ref to a prior non-authoritative assessment for a new proposal admission. Exact-effect evidence belongs in a later acceptance request, not this configuration. Unknown fields, partial blocks, duplicate keys, unsupported modes/versions and mixing vNext editing keys fail as `CONFIG_INVALID`; the bridge has no report-only fallback.

Run the normal command from the Whetstone checkout after the job's nested-client payload authorization is established:

```sh
PYTHONPATH=src python3 -m whetstone.cli live-phase1 --root "$RUN_ROOT"
PYTHONPATH=src python3 -m whetstone.cli status --root "$RUN_ROOT" --format json
```

For a focused job, use `live-focused-phase1 --root "$RUN_ROOT" --profile structural_integrity --budget 1`. These commands read the run's config; neither needs a preservation flag. Status exposes `preservation_bridge.mode: enforce` and `capability_version: preservation-bridge-v1`. Inspect terminal state and readiness rather than treating CLI exit 0 as convergence or acceptance.

## Handle a pending proposal

Missing correspondence or semantic evidence normally yields `PAUSED_DECISION`. The proposed output is retained; authoritative `spec.md` stays unchanged. Use the `latest_proposal.path` from status:

```sh
PYTHONPATH=src python3 -m whetstone.cli preservation-review \
  --root "$RUN_ROOT" --proposal "$PROPOSAL"
```

Review the displayed original/final lines, transformations, findings and assessment. Use `preservation-attest` to record an explicitly approved grouped effect, selecting its exact lines, kind, disposition and findings. Whetstone computes IDs and hashes. The [acceptance guide](PRESERVATION_ACCEPTANCE_DEVELOPER.md#review-and-adopt-an-exact-effect) provides concrete syntax; its line-9 clarification is a fictional example, not approval for another spec.

```sh
PYTHONPATH=src python3 -m whetstone.cli preservation-request \
  --root "$RUN_ROOT" --proposal "$PROPOSAL" \
  --evidence operator/effect.json --output operator/request-1.json
PYTHONPATH=src python3 -m whetstone.cli preservation-accept \
  --root "$RUN_ROOT" --request operator/request-1.json --dry-run
PYTHONPATH=src python3 -m whetstone.cli preservation-accept \
  --root "$RUN_ROOT" --request operator/request-1.json
```

An eligible dry-run returns `outcome: eligible` without changing files. Real acceptance revalidates the exact inputs, commits or repairs that one operation, and stops without another model call or review charge. A pending or rejected proposal cannot be consumed by later rounds or strop. A new same-base authorization/evidence set uses a new immutable request; it does not overwrite earlier reports.

After acceptance, inspect status and preview supported continuation:

```sh
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --continue --dry-run
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --continue
```

Each new editing round needs a surface approved for the current accepted base. The runtime does not automatically rebase approval. Review-only closeout can verify accepted bytes without new edit authorization. Technical retries retain frozen inputs; changing config is not a retry mechanism. Generic Phase 2 technical resume remains unsupported; use the documented bounded closeout or local acceptance/repair path when applicable.

Focused stability does not establish full Phase 1 readiness. Use `live-phase2` only after ordinary readiness checks pass. Convergence and source apply-back remain separate decisions, and guarded consumers validate retained acceptance and verification evidence.

## Verification and limits

The [qualification record](PRESERVATION_QUALIFICATION.md) covers the integrated runtime. `tests/test_preservation_activation.py` adds real YAML loading and public CLI journeys with scripted transport clients: positive opt-in, refusal before clients, pending effect adoption, read-only preview, acceptance, replay, continuation and no-op stability. Configuration loading and the qualification switch are not mocked in these journeys.

This release enables the qualified path; it is not evidence of live-model reliability or mechanical proof of semantic equivalence. Effect attestations remain accountable operator assertions. Historical legacy runs remain unguarded.
