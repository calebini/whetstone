# vNext reviewer-only admission

Slice 18.3 adds explicit vNext admission and reviewer-only Phase 1 execution on fresh isolated roots. `proposal_only` and `verified_promotion` remain unavailable. The existing legacy defaults and opt-in preservation bridge retain their workflows.

Prepare canonical `job-descriptor-v2` and `review-configuration-v1` inputs using the [offline contracts](VNEXT_CONTRACTS.md). The descriptor must select `reviewer_only`, bind the supported suite and exact normalized seed/authority/invariant/scope/review hashes, and contain the derived D6 job ID. It is immutable once admitted. The selected root may contain prepared inputs but no existing `rounds/` runtime artifacts.

Validate the complete preparation without writes:

```sh
PYTHONPATH=src python3 -m whetstone.cli vnext-admit \
  --root "$RUN_ROOT" \
  --vnext-job-descriptor inputs/job_descriptor.json \
  --vnext-review-configuration inputs/review.json \
  --dry-run
```

Omit `--dry-run` to initialize the seed map, ordinal-0 snapshot at `rounds/verified_history/current-verified-0.json`, current pointer and exact `spec.md` mirror. Alternatively, `live-phase1` accepts those selectors and initializes a fresh root before review. No Editor or Semantic Verifier is invoked.

For persistent configuration, use a `vnext` block in `orchestrator_config.yaml`:

```yaml
vnext:
  job_descriptor:
    path: inputs/job_descriptor.json
    hash: <exact canonical descriptor file SHA-256>
  review_configuration:
    path: inputs/review.json
    hash: <exact canonical review file SHA-256>
clients:
  reviewer:
    name: codex
    version: <same version as the pinned reviewer identity>
    model: <same model as the pinned reviewer identity>
    command: codex
timeouts:
  reviewer_seconds: 360
```

The supported configuration reader accepts the existing block-YAML subset, simple D7 flow references, or JSON. Use JSON for paths requiring YAML escaping outside that subset. CLI and config selectors must resolve to identical bytes when both are supplied. Unused Editor/Verifier executables are not required. Shared review settings must match the pinned review configuration; unbound mutation, convergence and recovery controls reject.

Run and inspect:

```sh
PYTHONPATH=src python3 -m whetstone.cli live-phase1 --root "$RUN_ROOT"
PYTHONPATH=src python3 -m whetstone.cli status --root "$RUN_ROOT" --format json
```

Reviewer-only horizontal and vertical schedules use the pinned profile list and budgets. Clean completion produces `PHASE_1_STABLE`; unresolved serious findings exhaust to `TARGET_NOT_REACHED`; a detected concrete operator choice pauses with a bound read-only decision card. One shape retry is permitted; timeouts and provider/transport errors halt without automatic retry. A completed invocation returns its retained result on repetition. A partial invocation requires inspection and cannot reset its retry allowance by restarting.

Status reports selected versus available capability and validates seed lineage and retained review evidence. It never repairs. Phase 2, generic resume, automatic version stamping, source apply-back, candidate processing and legacy writers are unavailable on these roots. Phase 1 stability here does not advertise those later capabilities. Existing source specifications are never changed by this workflow.

The [seed initialization contract](../contracts/algorithms/vnext_seed_initialization_v1.md) specifies exact parser/hash/publication behavior and limits. The public contracts reject empty heading text; normalize seed content before descriptor construction and use canonical absolute locators or confined relative paths. Future mutation/semantic/promotion slices extend the qualified capability surface without treating offline schema recognition as runtime availability.

Qualification: full discovery from a fixed 18.3 snapshot passed 572 tests. The final atomic-root-claim correction passed all 100 targeted admission/reviewer/offline-contract/configuration/CLI checks, including the earliest crash boundary, competing processes, hash tampering, a real CLI subprocess with a scripted Reviewer executable, horizontal/vertical budgets, retry boundaries, decision pauses, read-only replay and legacy-writer refusal. Exact logs, snapshot/final input hashes and the localized correction are retained under `rounds/vnext-admission-001/`. The initial mixed-version regression run is retained as discarded evidence. No live model qualification is claimed.
