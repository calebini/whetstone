# Whetstone Operator Quickstart

This guide is for running Whetstone against an existing spec document from another repo.

Whetstone works in an isolated run root. It copies the source spec into the run root as `spec.md`, mutates only that run copy during review, and leaves the original source file unchanged until a human explicitly runs `apply-back --apply --approve`.

## Recommended Default

Use this default for normal production spec sharpening:

- workflow: `standard`
- reviewer: Codex `gpt-5.5`
- editor: Codex `gpt-5.2`
- Codex reasoning effort: `medium`
- decision mode: `end_of_cycle`
- source mutation: manual apply-back only

Use `mvp` instead of `standard` when the goal is first useful implementation readiness rather than production-ready completeness. Use `governance` only for specs that need the heaviest convergence gate.

## Inputs

You need:

- absolute source spec path
- unique run root under Whetstone `rounds/`
- workflow choice: `mvp`, `standard`, or `governance`

Example variables:

```bash
SOURCE_SPEC="/Users/cwattles/Desktop/Agent-Workspace/repos/personal/cortext1/foreman/docs/MY_SPEC.md"
RUN_ROOT="rounds/foreman-my-spec-standard-001"
WORKFLOW="standard"
```

## Create Run Root

Create an isolated run root and import the source spec:

```bash
mkdir -p "$RUN_ROOT"
cp "$SOURCE_SPEC" "$RUN_ROOT/spec.md"
printf '# History\n' > "$RUN_ROOT/spec.history.md"
```

Create `orchestrator_config.yaml`:

```bash
cat > "$RUN_ROOT/orchestrator_config.yaml" <<'YAML'
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
declaration_path: ./convergence_declaration.md
workflow: standard

clients:
  reviewer:
    name: codex
    command: codex
    version: "0.128.0"
    model: gpt-5.5
  editor:
    name: codex
    command: codex
    version: "0.128.0"
    model: gpt-5.2

review:
  max_rounds: 3

convergence:
  enabled: true
  target_phase: final
  target_mode: strict
  rubric_profile: standard-v1
  rubric_source: builtin
  max_rounds: 3

decision_points:
  enabled: true
  mode: end_of_cycle
  intervention_thresholds:
    severities: [blocker, major]
    trigger_on_requirement_strength_change: true
    trigger_on_authority_boundary_change: true
    trigger_on_scope_change: true
    trigger_on_new_enum_or_error_code: true
YAML
```

For MVP review, change:

```yaml
workflow: mvp
convergence:
  target_phase: mid
  target_mode: strict
  rubric_profile: mvp-v1
```

## Run Phase 1

Run the technical stabilization phase:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase1 \
  --root "$RUN_ROOT" \
  --timeout-seconds 300
```

Check status:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

Proceed only if status says:

```text
terminal_state: PHASE_1_STABLE
next_action: run_live_phase2
```

## Run Phase 2

Run convergence review:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 \
  --root "$RUN_ROOT" \
  --workflow "$WORKFLOW" \
  --timeout-seconds 300
```

Check status again:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

Successful convergence looks like:

```text
terminal_state: CONVERGED
next_action: review_or_apply_back
apply_back: available=true, applied=False
```

If the run halts with `TARGET_NOT_REACHED`, `HALTED_ARTIFACT_INVALID`, `HALTED_CONFLICT`, or `HALTED_OSCILLATION`, do not apply back automatically. Review the terminal report first.

## Review Artifacts

Before applying back, inspect:

- `$RUN_ROOT/spec.md`
- `$RUN_ROOT/spec.history.md`
- `$RUN_ROOT/convergence_declaration.md`
- `$RUN_ROOT/rounds/decision_summary.md`
- `$RUN_ROOT/rounds/run_state.json`

Useful status command:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format json
```

## Dry-Run Apply-Back

Generate the source-vs-final diff without mutating the source:

```bash
PYTHONPATH=src python3 -m whetstone.cli apply-back \
  --source "$SOURCE_SPEC" \
  --run-root "$RUN_ROOT"
```

Review:

```text
$RUN_ROOT/rounds/apply_back_review.md
```

The dry-run report should show:

```text
terminal_state: CONVERGED
eligible_terminal_state: true
final_draft_matches_run_state: True
```

## Apply Back

Only after human approval, write the final draft back to the source spec:

```bash
PYTHONPATH=src python3 -m whetstone.cli apply-back \
  --source "$SOURCE_SPEC" \
  --run-root "$RUN_ROOT" \
  --apply \
  --approve
```

Confirm:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

Expected:

```text
apply_back: available=true, applied=True
```

## Safety Rules

- Do not edit the source spec during a Whetstone run.
- Do not use `--allow-source-hash-mismatch` unless intentionally overriding a source change.
- Do not use `--allow-non-converged` for normal operation.
- Do not auto-apply Whetstone results from an agent run. Always run dry-run apply-back first.
- Keep one run root per source spec attempt. Use a new suffix like `-002` for retries.

## Common Artifacts

Run-level:

- `spec.md`: current run draft
- `spec.history.md`: version and round history
- `convergence_declaration.md`: final declaration when Phase 2 converges
- `rounds/run_state.json`: terminal state and current hash
- `rounds/decision_register.json`: all detected decision points
- `rounds/decision_summary.md`: human-readable decision clusters
- `rounds/apply_back_review.md`: source-vs-final diff and apply-back guard results

Per-round:

- `draft_before.md`
- `draft_after.md`
- `reviewer_feedback.json`
- `editor_summary.json`
- `unresolved_issues.json`
- `decision_points.json`
- `prompt_snapshot.json`
- `telemetry_summary.json`

## Troubleshooting

If `latest_round` is partial, inspect missing artifacts in `status`.

If a client times out, preserve the run root and retry in a new run root unless you know the command supports safe overwrite.

If `apply-back` refuses to write, read `apply_back_review.json`; the usual causes are non-converged terminal state, source hash mismatch, or final draft hash mismatch against `run_state.current_draft_hash`.

If Foreman `git diff` is empty after apply-back, check whether the file is tracked:

```bash
git -C /path/to/foreman status --short
git -C /path/to/foreman ls-files -- docs/MY_SPEC.md
```

