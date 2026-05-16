# Whetstone

Whetstone is an AI spec convergence orchestrator.

It helps turn messy, ambitious, half-stable technical specs into implementation-ready artifacts by running structured Reviewer and Editor passes, preserving every round, and forcing the work to end in explicit states instead of conversational vibes.

Most AI spec work happens in chat: paste the doc, ask for feedback, patch it manually, repeat, and hope nobody loses the thread. Whetstone makes that loop durable. It gives the models roles, gives the operator controls, gives every decision an artifact, and gives the final spec a trail you can inspect.

The short version:

```text
scope the run
  -> review the spec
  -> edit the draft
  -> verify the fix
  -> detect churn
  -> preserve decisions
  -> converge or explain why not
  -> apply back only when you choose
```

## Why Whetstone Exists

Good software starts with good boundaries. AI is excellent at finding ambiguity, missing contracts, hidden coupling, and unowned decisions, but raw AI review can also sprawl. It can over-sharpen small tools, expand MVPs into cities, and lose track of what was already decided.

Whetstone exists to make that pressure usable.

- **Specs should become buildable.** Review focuses on authority, interfaces, data contracts, states, failure handling, replay/idempotency, artifacts, and acceptance criteria.
- **The process should be inspectable.** Every round produces persisted artifacts: feedback, editor summaries, draft snapshots, telemetry, decision points, reports, and terminal state.
- **The operator should stay in control.** Scope contracts, profile sets, workflow presets, budgets, decision summaries, and manual apply-back prevent the tool from silently taking ownership.
- **The system should know when to stop.** Whetstone converges, halts, pauses, or reports residuals through explicit terminal states.
- **Large specs should not collapse under their own weight.** Decomposition can split an overloaded source spec into a governed family of coordinating and leaf specs without rewriting requirements.

## What Whetstone Does

Whetstone currently supports:

- Live multi-round Phase 1 technical stabilization.
- Phase 2 convergence review against canonical or custom rubric profiles.
- Workflow presets for `exploratory`, `mvp`, `standard`, `governance`, and `custom` runs.
- Review profile sets for stateful systems, lighter MVP utilities, and governance-heavy specs.
- Horizontal and vertical review modes.
- MVP scope intake with approved `scope_contract.json`.
- Decision point capture and end-of-cycle decision summaries.
- Operator decision checkpoint artifacts.
- Contract-surface expansion detection with synthesis recommendations.
- Resume after supported Editor timeouts and budget exhaustion.
- Role-specific timeouts.
- File-backed context for specs, rubrics, scope contracts, and reviewer feedback.
- Client telemetry capture where available.
- Dry-run and approved apply-back through `strop`.
- Spec decomposition: `plan -> approve -> extract -> audit -> promote`.
- Built-in rubrics:
  - `exploratory-v1`
  - `mvp-v1`
  - `standard-v1`
  - `governance-v6`

## The Workflow

Whetstone has two live phases.

**Phase 1: technical stabilization**

Reviewer and Editor passes sharpen the draft across configured review profiles such as structural integrity, determinism, and operability. Phase 1 is where Whetstone finds missing contracts, contradictory state rules, invalid artifact shapes, unclear authority boundaries, and implementation blockers.

**Phase 2: convergence review**

Once Phase 1 is stable, Whetstone reviews against a selected rubric workflow and produces a convergence declaration. Phase 2 is stricter, more classification-heavy, and designed to decide whether the spec is actually ready for the target bar.

## Scope Before Pressure

For MVP work, Whetstone requires an approved scope contract. That is intentional.

Without scope, a strong reviewer will find every path worth paving. Sometimes that is exactly what you want. For an MVP, it is usually not. A scope contract tells Whetstone what the first useful build is, what should be deferred, and how deep validation, reporting, failure handling, and schemas should go.

```bash
PYTHONPATH=src python3 -m whetstone.cli intake \
  --root "$RUN_ROOT" \
  --template mvp \
  --output "$RUN_ROOT/scope-notes.md"

PYTHONPATH=src python3 -m whetstone.cli intake \
  --root "$RUN_ROOT" \
  --from-notes "$RUN_ROOT/scope-notes.md" \
  --approve
```

## Decompose Big Specs

Whetstone can split an overloaded source spec into a governed spec family without paraphrasing or losing normative content.

The decomposition workflow is deliberately conservative:

```text
plan      inventory source units and proposed ownership
approve   bind operator approval to source and plan hashes
extract   copy source content into target specs
audit     verify coverage, hashes, provenance, and authority
promote   mark the decomposed family authoritative
```

This repository now dogfoods that model. The promoted Whetstone spec family lives under:

- [Coordinating Spec](docs/specs/WHETSTONE_COORDINATING_SPEC.md)
- [Rubrics, Profiles, And Feedback](docs/specs/RUBRICS_PROFILES_AND_FEEDBACK_SPEC.md)
- [Scope Intake, Decisions, And Decomposition](docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md)
- [Scheduler, State, And Resume](docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md)
- [Artifacts, Validation, And Telemetry](docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md)
- [Identity, Oscillation, And Conflicts](docs/specs/IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md)
- [Phase 2, Convergence, And Declaration](docs/specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md)

The original [spec.md](spec.md) remains the pre-decomposition source snapshot.

## Quick Start

Install locally from the repo:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Run the test suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
```

Inspect the CLI:

```bash
PYTHONPATH=src python3 -m whetstone.cli --help
```

Create an isolated run root for a source spec:

```bash
SOURCE_SPEC="/absolute/path/to/MY_SPEC.md"
RUN_ROOT="/absolute/path/to/whetstone_runs/my-spec-standard-001"

mkdir -p "$RUN_ROOT"
cp "$SOURCE_SPEC" "$RUN_ROOT/spec.md"
printf '# History\n' > "$RUN_ROOT/spec.history.md"
```

Then create `orchestrator_config.yaml` in the run root. The full operator guide includes a copy/paste-ready config.

Run Phase 1:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase1 --root "$RUN_ROOT"
```

Check status:

```bash
PYTHONPATH=src python3 -m whetstone.cli status --root "$RUN_ROOT" --format text
```

Run Phase 2:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 --root "$RUN_ROOT" --workflow standard
```

Dry-run apply-back:

```bash
PYTHONPATH=src python3 -m whetstone.cli strop \
  --source "$SOURCE_SPEC" \
  --run-root "$RUN_ROOT"
```

Apply back only after review:

```bash
PYTHONPATH=src python3 -m whetstone.cli strop \
  --source "$SOURCE_SPEC" \
  --run-root "$RUN_ROOT" \
  --apply \
  --approve
```

## Common Commands

Resume a supported Editor timeout:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --dry-run --continue
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --continue
```

Append rounds after Phase 1 budget exhaustion:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --extend-review-budget 3 --dry-run
PYTHONPATH=src python3 -m whetstone.cli resume --root "$RUN_ROOT" --extend-review-budget 3
```

Run a focused Phase 1 profile:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-focused-phase1 \
  --root "$RUN_ROOT" \
  --profile determinism
```

Create a decomposition plan:

```bash
PYTHONPATH=src python3 -m whetstone.cli decompose plan \
  --source spec.md \
  --map docs/decomposition/whetstone-decomposition-map.json \
  --output-dir docs/decomposition
```

Audit and promote an extracted spec family:

```bash
PYTHONPATH=src python3 -m whetstone.cli decompose audit \
  --manifest docs/decomposition/decomposition_manifest.json \
  --source spec.md

PYTHONPATH=src python3 -m whetstone.cli decompose promote \
  --manifest docs/decomposition/decomposition_manifest.json \
  --accepted-by "$USER"
```

`apply-back` remains a supported legacy alias for `strop`.

## Artifacts You Can Trust

A Whetstone run is not just a final draft. It is a record of how the draft got there.

Important artifacts include:

- `rounds/run_state.json`
- `rounds/round-N/reviewer_feedback.json`
- `rounds/round-N/editor_summary.json`
- `rounds/round-N/draft_before.md`
- `rounds/round-N/draft_after.md`
- `rounds/round-N/unresolved_issues.json`
- `rounds/round-N/operator_decision_checkpoint.json`
- `rounds/decision_register.json`
- `rounds/decision_summary.md`
- `rounds/technical_failure_report.json`
- `rounds/convergence_failure_report.json`
- `rounds/rubric_manifest.json`
- `convergence_declaration.md`
- `apply_back_review.md`

That artifact trail is the product. It lets a human or another agent ask: what changed, why did it change, what remains unresolved, did the reviewer verify it, and is it safe to apply?

## Documentation

- [Operator Quickstart](docs/OPERATOR_QUICKSTART.md)
- [Scope Notes Guide](docs/SCOPE_NOTES_GUIDE.md)
- [Whetstone Coordinating Spec](docs/specs/WHETSTONE_COORDINATING_SPEC.md)
- [Spec Decomposition Manifest](docs/decomposition/decomposition_manifest.json)
- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [Future Improvements](notes/future-improvements.md)

## Repository Map

- `docs/specs/` - promoted Whetstone spec family
- `docs/decomposition/` - decomposition plan, manifest, and coverage matrix
- `contracts/schemas/` - JSON Schema contracts for persisted artifacts
- `rubrics/` - built-in rubric profiles
- `src/whetstone/` - implementation
- `tests/` - regression tests and CLI-shaped smoke coverage
- `rounds/` - default local artifact output root
- `spec.md` - original pre-decomposition source spec snapshot
- `spec.history.md` - append-only source-spec revision history

## Status

Whetstone is under active development and already useful on real specs. It has been used against Whetstone itself, Foreman specs, and Parley specs to find structural gaps, stabilize drafts, surface decision points, compare review modes, and split the Whetstone spec into a promoted leaf-spec family.

The emphasis now is practical operator ergonomics: better first-contact job design, sharper scope boundaries, clearer project-level spec tracking, and continued reduction of unnecessary token burn without losing the quality signal that makes the tool worth using.
