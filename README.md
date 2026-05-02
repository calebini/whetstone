# Whetstone

Whetstone is an AI spec convergence orchestrator.

The current source of truth is [spec.md](spec.md), currently version `0.17`. Runtime review artifacts are expected under `rounds/` once implementation begins.

## Files

- `spec.md` - latest persisted orchestrator spec, currently `0.17`
- `spec.history.md` - append-only spec history
- `IMPLEMENTATION_PLAN.md` - contract-first build plan
- `contracts/schemas/` - initial JSON Schema artifact contracts
- `src/whetstone/` - deterministic implementation primitives
- `tests/` - fixture-mode regression tests
- `examples/fixtures/` - golden fixture scripts for deterministic runs
- `rounds/` - future orchestrator output root

## Current Build State

Implemented:
- schema loading and artifact validation
- draft and semantic-change hashing
- issue/conflict identity and severity helpers
- accepted-draft, target-matrix, conflict, and oscillation evaluators
- guarded artifact store
- fixture-mode round runner and CLI
- multi-round fixture orchestration engine
- terminal report generation
- convergence declaration rendering
- Phase 1/Phase 2 scheduler primitives
- process client adapter boundary and prompt rendering
- Codex `exec` reviewer adapter and CLI probe command
- guarded `live-round` CLI for one reviewer -> editor round packet

## Fixture Run

```bash
PYTHONPATH=src python3 -m whetstone.cli fixture-script \
  --script examples/fixtures/clean_convergence_script.json \
  --overwrite
```

## Codex Reviewer Probe

```bash
PYTHONPATH=src python3 -m whetstone.cli codex-review \
  --profile determinism \
  --output rounds/codex_reviewer_feedback.json
```

The Codex adapter uses `codex exec` with `--sandbox read-only`, `--ephemeral`, `--output-schema`, and `--output-last-message`.

## Live Single Round

```bash
PYTHONPATH=src python3 -m whetstone.cli live-round \
  --profile convergence_strict_check \
  --phase phase_2
```

The live round is guarded: reviewer output validates before editor invocation, generated editor drafts are hashed by Whetstone before persistence, and `spec.md` is not mutated unless `--apply` is explicitly supplied with validated draft content.

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q src tests
```
