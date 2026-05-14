# Whetstone

Whetstone is an AI spec convergence orchestrator. It runs iterative Reviewer and Editor passes over a technical spec, persists every round artifact, and stops on explicit terminal states instead of relying on conversational memory.

The source of truth is [spec.md](spec.md), currently version `0.59`.

## Start Here

For live runs against real specs, use the operator guide:

- [Operator Quickstart](docs/OPERATOR_QUICKSTART.md)

The quickstart covers isolated run roots, scope intake, Phase 1, Phase 2, status, timeout recovery, dry-run resume, decision summaries, and manual strop/apply-back to an external source spec.

## Common Commands

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
```

Run Phase 1 in an isolated run root:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase1 --root "$RUN_ROOT"
```

Create MVP scope notes and an approved scope contract:

```bash
PYTHONPATH=src python3 -m whetstone.cli intake --root "$RUN_ROOT" --template mvp --output "$RUN_ROOT/scope-notes.md"
PYTHONPATH=src python3 -m whetstone.cli intake --root "$RUN_ROOT" --from-notes "$RUN_ROOT/scope-notes.md" --approve
```

Check run status:

```bash
PYTHONPATH=src python3 -m whetstone.cli status --root "$RUN_ROOT" --format text
```

Recover a supported Editor timeout:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --dry-run --continue
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --continue
```

Append rounds after Phase 1 budget exhaustion:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --extend-review-budget 3 --dry-run
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --extend-review-budget 3
```

Run Phase 2:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 --root "$RUN_ROOT" --workflow standard
```

Review or apply an isolated run back to its source spec:

```bash
PYTHONPATH=src python3 -m whetstone.cli strop --source "$SOURCE_SPEC" --run-root "$RUN_ROOT"
PYTHONPATH=src python3 -m whetstone.cli strop --source "$SOURCE_SPEC" --run-root "$RUN_ROOT" --apply --approve
```

`apply-back` remains a supported legacy alias for `strop`.

## Repository Map

- `spec.md` - Whetstone system specification
- `spec.history.md` - append-only spec revision history
- `IMPLEMENTATION_PLAN.md` - traceable implementation checklist
- `docs/OPERATOR_QUICKSTART.md` - command-first live-run guide
- `docs/SCOPE_NOTES_GUIDE.md` - guide for writing scope notes before intake
- `contracts/schemas/` - JSON Schema contracts for persisted artifacts
- `rubrics/` - built-in rubric profiles
- `src/whetstone/` - implementation
- `tests/` - regression tests, including CLI-shaped live-run smoke tests
- `rounds/` - default local artifact output root
