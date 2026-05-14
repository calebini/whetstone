# Whetstone Operator Quickstart

This guide is for running Whetstone against an existing spec document, especially a spec that lives in another repo.

The safest pattern is an isolated run root: copy the source spec into a Whetstone run directory as `spec.md`, let Whetstone mutate only that copy, inspect the results, then manually apply back to the source file.

## Mental Model

Whetstone has two live phases:

- Phase 1: technical stabilization across structural integrity, determinism, and operability profiles.
- Phase 2: convergence review against a selected rubric workflow.

Whetstone persists every round under `rounds/`. The run is controlled by `rounds/run_state.json`; humans should usually read `status --format text` instead of opening that JSON first.

## Recommended Defaults

Use these defaults for normal spec sharpening:

- workflow: `standard`
- reviewer: Codex `gpt-5.5`
- editor: Codex `gpt-5.2`
- source mutation: manual apply-back only
- decision mode: `end_of_cycle`
- profile budgets: start generous, then tune after observing run shape
- budget exhaustion policy: `hard` for strict gating, `soft` for full Phase 1 diagnostic sweeps
- timeout posture: reviewer shorter, editor longer

Use `mvp` when you want first-useful-build readiness. Use `governance` only when you want the heavy convergence gate. Use `custom` only when you have a named custom rubric and want the run artifacts to make that rubric identity explicit.

MVP runs require an approved scope contract. This is deliberate: MVP review needs a clear first-useful-build boundary or Whetstone will expand the surface area it discovers.

## Inputs

Choose:

- source spec path
- run root
- workflow

Example:

```bash
SOURCE_SPEC="/Users/cwattles/Desktop/Agent-Workspace/repos/personal/cortext1/foreman/docs/MY_SPEC.md"
RUN_ROOT="/Users/cwattles/Desktop/Agent-Workspace/repos/personal/cortext1/whetstone/rounds/foreman-my-spec-standard-001"
WORKFLOW="standard"
```

## Create An Isolated Run

```bash
mkdir -p "$RUN_ROOT"
cp "$SOURCE_SPEC" "$RUN_ROOT/spec.md"
printf '# History\n' > "$RUN_ROOT/spec.history.md"
```

Create `orchestrator_config.yaml` in the run root:

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
  max_rounds: 12
  mode: horizontal
  profile_set: stateful_system
  budget_exhaustion_policy: hard
  profile_budgets:
    structural_integrity: 10
    determinism: 10
    operability: 10

convergence:
  enabled: true
  target_phase: final
  target_mode: strict
  rubric_profile: standard-v1
  rubric_source: builtin
  max_rounds: 8
  profile_budgets:
    convergence_strict_check: 10
    adversarial: 10

decision_points:
  enabled: true
  mode: end_of_cycle
  intervention_thresholds:
    severities: [blocker, major]
    trigger_on_requirement_strength_change: true
    trigger_on_authority_boundary_change: true
    trigger_on_scope_change: true
    trigger_on_new_enum_or_error_code: true

timeouts:
  reviewer_seconds: 360
  editor_seconds: 900

scope_contract:
  path: ./rounds/intake/scope_contract.json

# Optional but strongly recommended when leaf specs depend on an HLD,
# architecture note, policy document, or domain contract.
reference_context:
  files:
    architecture_hld:
      path: /absolute/path/to/docs/hld-architecture.md
      role: architecture_authority
      required: true
YAML
```

For MVP review, change:

```yaml
workflow: mvp
review:
  profile_set: utility_mvp
  profile_budgets:
    buildability: 4
    consistency: 4
    determinism_light: 4
    operability_light: 3
convergence:
  target_phase: mid
  target_mode: strict
  rubric_profile: mvp-v1
  profile_budgets:
    mvp_readiness_check: 4
    scope_guard: 3
```

Then create and approve a scope contract before running Phase 1.

For governance review, use:

```yaml
workflow: governance
convergence:
  target_phase: final
  target_mode: strict
  rubric_profile: governance-v6
```

## Review Mode

Use `horizontal` for the original careful profile-by-profile loop:

```yaml
review:
  mode: horizontal
```

Use `vertical` when you want fewer Editor turns. In vertical mode, Whetstone runs independent structural, determinism, and operability Reviewer passes over the same draft, merges the feedback, then asks the Editor for one consolidated revision:

```yaml
review:
  mode: vertical
```

Vertical mode is usually the better economy choice for MVP and medium-size specs. It preserves separate Reviewer artifacts per profile, but the Editor sees the full cross-profile problem set before changing the draft.

Round folders identify their shape in `profile_used.yaml` with `round_kind`. In vertical runs, profile rounds use `review_only`; the merged Editor round uses `consolidated_editor`.

If a run ends immediately after an Editor mutation, Whetstone may report the draft as accepted but still unverified. That means the edit resolved the known blocker/major feedback, but the revised draft still needs another clean profile-review cycle before Phase 2.

When this happens at the end of the budget, Whetstone can run a verification-only closeout pass. It calls Reviewers only, does not mutate the draft, and either marks Phase 1 stable or stops with the remaining blocker/major verification debt.

## Profile Set

Use `profile_set` to choose the review lenses and default per-profile budgets before changing individual budgets:

```yaml
review:
  profile_set: stateful_system
```

Available profile sets:

- `stateful_system`: default, high-assurance review for stateful/artifact/replay-heavy systems.
- `balanced_mvp`: same review lenses as `stateful_system`, with lower budgets.
- `utility_mvp`: lighter lenses for small CLIs, utilities, and MVP tools where Whetstone should avoid turning the spec into a metropolis.
- `governance`: strongest pressure, including adversarial Phase 1 review.

For Foreman-like specs, start with `stateful_system`. For Parley-like utility specs, start with `utility_mvp` plus a clear MVP scope contract.

## Budget Exhaustion Policy

Use the default `hard` policy when you want Phase 1 to stop as soon as a required profile cannot reach clean verification within its budget:

```yaml
review:
  budget_exhaustion_policy: hard
```

Use `soft` when you want a diagnostic sweep across all Phase 1 profiles before stopping:

```yaml
review:
  budget_exhaustion_policy: soft
```

Soft mode does not mean "good enough." It lets Whetstone advance past exhausted or oscillating Phase 1 profiles, records a per-profile residual status, and then halts with `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS` if Phase 1 is not genuinely stable. Phase 2 is still blocked until status reports `PHASE_1_STABLE`.

## Scope Intake For MVP

Create a starter notes file:

```bash
PYTHONPATH=src python3 -m whetstone.cli intake \
  --root "$RUN_ROOT" \
  --template mvp \
  --output "$RUN_ROOT/scope-notes.md"
```

Edit `scope-notes.md` to define:

- the one core outcome for the run
- in-scope surfaces
- deferred or out-of-scope surfaces
- required depth for validation, schema, report, failure, and operational behavior
- what counts as good enough

See [Scope Notes Guide](SCOPE_NOTES_GUIDE.md) for examples and depth-level guidance.

Generate an approved scope contract:

```bash
PYTHONPATH=src python3 -m whetstone.cli intake \
  --root "$RUN_ROOT" \
  --from-notes "$RUN_ROOT/scope-notes.md" \
  --approve
```

This writes:

```text
$RUN_ROOT/rounds/intake/scope_contract.json
```

Without `--approve`, Whetstone writes a draft scope contract. Draft scope contracts are useful for review, but they do not satisfy MVP preflight.

## Run Phase 1

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase1 \
  --root "$RUN_ROOT"
```

Optional timeout overrides:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase1 \
  --root "$RUN_ROOT" \
  --reviewer-timeout-seconds 360 \
  --editor-timeout-seconds 1200
```

Check status:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

Proceed to Phase 2 only when status says:

```text
terminal_state: PHASE_1_STABLE
next_action: run_live_phase2
```

If status says:

```text
terminal_state: PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS
next_action: manual_review_required
```

read `rounds/technical_failure_report.json`. The run completed a soft Phase 1 diagnostic sweep, but at least one profile still has residual blocker/major or oscillation status. Do not proceed to Phase 2 from this state.

## Run A Focused Profile Recheck

Use a focused Phase 1 profile run when a prior run leaves one profile uncertain and you want normal Whetstone artifacts for a targeted recheck.

Create a new isolated comparison run root, seed it with the latest valid draft from the prior run, copy or recreate the config and scope contract, then run:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-focused-phase1 \
  --root "$FOCUSED_RUN_ROOT" \
  --profile structural_integrity \
  --budget 3
```

Focused profile runs write ordinary round artifacts and `rounds/run_state.json`. A clean focused run ends with:

```text
terminal_state: FOCUSED_PROFILE_STABLE
ready_for_phase_2: false
```

That state means the selected profile is clean for the focused draft. It does not replace a full Phase 1 stable run and does not by itself authorize Phase 2.

## Recover A Timeout

If status says:

```text
terminal_state: HALTED_CLIENT_TIMEOUT
next_action: resume_or_increase_timeout
```

read the resume commands printed by status:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

First validate the recovery plan without invoking the Editor:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --dry-run \
  --continue
```

If the dry-run is resumable, continue the run:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --continue
```

Use a larger Editor timeout when the previous call timed out deep into a large draft:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --editor-timeout-seconds 1800 \
  --continue
```

If status says Phase 1 ended with `TARGET_NOT_REACHED` or `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS` because profile budgets were exhausted, you can append rounds to the same run root instead of overwriting it:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --extend-review-budget 3 \
  --dry-run
```

If the dry-run is resumable, run the same command without `--dry-run`:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --extend-review-budget 3
```

Budget-extension resume appends new `round-N/` directories, preserves prior artifacts, and records the extension in `rounds/run_state.json` under `budget_extensions`. In horizontal mode it appends profile rounds. In vertical mode it appends additional vertical review cycles: profile review passes over the same draft, followed by one consolidated Editor revision when feedback remains.

Current resume support is intentionally narrow. It supports Phase 1 Editor timeouts after validated Reviewer feedback and explicit Phase 1 budget-extension continuation. It does not resume arbitrary artifact validation failures, Reviewer timeouts, Phase 2 timeouts, source hash mismatches, or manually edited run drafts.

## Run Phase 2

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 \
  --root "$RUN_ROOT" \
  --workflow "$WORKFLOW"
```

You can override the built-in rubric profile at runtime:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 \
  --root "$RUN_ROOT" \
  --workflow mvp \
  --rubric mvp-v1
```

For custom rubrics, provide a path and label:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 \
  --root "$RUN_ROOT" \
  --workflow custom \
  --rubric /absolute/path/to/domain-rubric.md \
  --rubric-label "payments-certification-v1"
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
apply_back: available=true
```

## Decision Summaries

Decision artifacts are useful when you do not want to read every round file.

Look first at:

```text
$RUN_ROOT/rounds/decision_summary.md
```

If a run halts for `PAUSED_DECISION`, inspect:

```text
$RUN_ROOT/rounds/decision_intervention_request.json
```

In normal `end_of_cycle` mode, decisions are surfaced for review after the run rather than interrupting every round.

For round-by-round owner-choice hints, inspect:

```text
$RUN_ROOT/rounds/round-N/operator_decision_checkpoint.json
```

These checkpoint artifacts are advisory in the current runtime. They frame likely policy, scope, validation, failure, or reporting choices, but they do not pause the run or change scheduler behavior.

For a compact run-level view, inspect:

```text
$RUN_ROOT/rounds/operator_decision_checkpoint_summary.md
```

This summary clusters checkpoint candidates and shows the top cards worth operator review.

## Review Before Apply-Back

Before changing the source spec, inspect:

- `$RUN_ROOT/spec.md`
- `$RUN_ROOT/spec.history.md`
- `$RUN_ROOT/convergence_declaration.md`
- `$RUN_ROOT/rounds/decision_summary.md`
- `$RUN_ROOT/rounds/run_state.json`

Generate the strop/apply-back review without mutating the source:

```bash
PYTHONPATH=src python3 -m whetstone.cli strop \
  --source "$SOURCE_SPEC" \
  --run-root "$RUN_ROOT"
```

Read:

```text
$RUN_ROOT/rounds/apply_back_review.md
```

The dry-run should show that the run is eligible and the final draft hash matches `run_state.current_draft_hash`.

## Apply Back

Only after human review:

```bash
PYTHONPATH=src python3 -m whetstone.cli strop \
  --source "$SOURCE_SPEC" \
  --run-root "$RUN_ROOT" \
  --apply \
  --approve
```

`apply-back` remains supported as a legacy alias for `strop`.

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

## Artifact Reading Order

When something halts, read in this order:

1. `status --format text`
2. `rounds/run_state.json`
3. terminal report:
   - `rounds/technical_failure_report.json`
   - `rounds/convergence_failure_report.json`
   - `rounds/artifact_validation_error.json`
   - `rounds/oscillation_report.json`
   - `rounds/conflict_report.json`
4. latest `rounds/round-N/reviewer_feedback.json`
5. latest `rounds/round-N/editor_summary.json`
6. `rounds/decision_summary.md`
7. `rounds/operator_decision_checkpoint_summary.md`
7. `rounds/apply_back_review.md`, if apply-back has been dry-run

## Terminal States

- `PHASE_1_STABLE`: Phase 1 is ready for Phase 2.
- `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`: soft Phase 1 sweep finished, but residual profile issues remain; manual review required and Phase 2 is blocked.
- `CONVERGED`: Phase 2 passed; review and apply back.
- `TARGET_NOT_REACHED`: budget exhausted; read the phase failure report.
- `HALTED_CLIENT_TIMEOUT`: a client timed out; status may show resume commands.
- `HALTED_ARTIFACT_INVALID`: a client returned invalid structured output after retry.
- `HALTED_OSCILLATION`: iteration stopped because churn/cycle detection fired.
- `HALTED_CONFLICT`: conflict threshold halted the run.
- `PAUSED_DECISION`: operator decision required before continuing.
- `CONFIG_INVALID`: fix configuration before running.

## Safety Rules

- Keep one run root per source spec attempt. Use suffixes like `-001`, `-002`, `-003`.
- Do not edit the source spec during a Whetstone run.
- Do not manually edit `$RUN_ROOT/spec.md` after a run starts unless you intend to invalidate resume/hash assumptions.
- Do not use `--allow-source-hash-mismatch` unless intentionally overriding a changed source file.
- Do not use `--allow-non-converged` for normal operation.
- Do not auto-apply Whetstone results from an agent run. Run dry-run strop/apply-back first.
- Preserve failed run roots when diagnosing timeouts, oscillation, malformed output, or budget exhaustion.

## Troubleshooting

If status says the latest round is partial, read `missing_round_artifacts` and the terminal report.

If a client times out, use `status --format text`, then `resume --dry-run --continue`. Increase `--editor-timeout-seconds` if the Editor timed out while producing a large draft.

If Phase 1 reaches `TARGET_NOT_REACHED`, check whether the latest failure report says issues remain unresolved or whether a profile simply never got a clean Reviewer verification.

If Phase 1 reaches `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`, check `profile_status.profiles[].residual_status` in `technical_failure_report.json` to see which profiles exhausted budget or hit oscillation during the soft sweep.

If Phase 2 converges suspiciously quickly or every run has the same shape, inspect profile budgets, profile status, and the latest Reviewer findings before trusting the run shape.

If strop/apply-back refuses to write, read `apply_back_review.json`; common causes are non-converged terminal state, source hash mismatch, final draft hash mismatch against `run_state.current_draft_hash`, or final-draft text hygiene failures.

If the source repo diff is empty after apply-back, check whether the file is tracked:

```bash
git -C /path/to/source-repo status --short
git -C /path/to/source-repo ls-files -- docs/MY_SPEC.md
```
