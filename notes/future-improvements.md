# Future Improvements

This note captures useful ideas that are not required for the next narrow build step, but should not be lost.

## Rollback And Restore Safety

Current round artifacts preserve rollback material through `draft_before.md` and `draft_after.md`, but Whetstone does not yet provide ergonomic rollback.

Potential improvements:

- Add `rounds/run_state.json` with `current_round`, `current_draft_hash`, `last_accepted_draft_hash`, and the round/profile that produced the current draft.
- Append a compact `spec.history.md` entry after each applied live round with round number, profile, before hash, after hash, accepted status, and terminal state if any.
- Add a hash-guarded restore command, for example `whetstone restore --round N --which before|after`.
- Refuse restore when the current `spec.md` hash does not match the expected current hash unless an explicit override is provided.
- Consider storing `last_accepted_draft_path` or deriving it from run state plus round artifacts.

## Minimal Live Phase 1 Runner

The next practical orchestrator milestone does not need full Phase 2 oscillation memory.

Useful first version:

- Add a live Phase 1 loop command that runs configured profiles through the scheduler.
- Persist scheduler/run state after every round.
- Use existing artifact validation retry and halt behavior.
- Mutate `spec.md` only after editor output validates and `draft_after.md` is persisted.
- Stop on accepted Phase 1 draft, max rounds, artifact validation failure, or basic draft-hash cycle.
- Emit `technical_failure_report.json` for Phase 1 terminal failures.

## Deferred Oscillation And Conflict Memory

Full cross-round memory is still important, but can follow the minimal Phase 1 runner.

Deferred improvements:

- Track draft-hash cycles across live rounds.
- Track exact mechanical churn across Phase 1 rounds.
- Track conflict fingerprints across rounds.
- Add Phase 2 feedback-level oscillation memory using canonical `oscillation_opposition_key`.
- Persist cross-round memory in a replayable artifact rather than relying on process-local state.

## Artifact Cleanup And Compaction

Live runs can produce bulky round artifacts, especially prompt snapshots and raw client diagnostics. A cleanup feature would be useful, but it should be archive-first rather than destructive by default.

Potential modes:

- `--cleanup=none`: default behavior; preserve every artifact.
- `--cleanup=compact`: keep essential artifacts in place and move verbose per-round material into an archive area.
- `--cleanup=archive`: bundle older round folders into a timestamped archive under `rounds/archive/`.
- `--cleanup=prune`: destructive cleanup allowed only with an explicit confirmation flag and only after an archive exists.

Essential artifacts to preserve:

- `spec.md`
- `spec.history.md`
- `rounds/run_state.json` once implemented
- terminal reports such as `technical_failure_report.json`, `convergence_failure_report.json`, `conflict_report.json`, `oscillation_report.json`, and `artifact_validation_error.json`
- final accepted or converged draft snapshot
- a compact `rounds/manifest.json` summarizing each round's profile, clients, before/after hashes, issue counts, accepted status, terminal state, and archived artifact paths

Per-round artifacts can be compacted or archived, but should remain recoverable for audit/debug purposes:

- `draft_before.md`
- `draft_after.md`
- `reviewer_feedback.json`
- `editor_summary.json`
- `unresolved_issues.json`
- `profile_used.yaml`
- `prompt_snapshot.json`
- `reviewer_working_notes.md`
- raw invalid client responses and stderr/stdout diagnostics

The first version should probably be named `whetstone compact` or `--archive-round-artifacts` rather than destructive cleanup, so the feature's default mental model is preserving the audit trail while reducing clutter.

## Decision Summary And Intervention Refinement

Decision capture is useful, but live intervention is likely too interrupt-heavy for normal Whetstone runs. Real runs can produce dozens of decision points, and pausing on each meaningful requirement, scope, or policy change would turn review into an expensive permission flow.

Future improvements:

- Keep `end_of_cycle` as the default decision mode.
- Treat `intervention` as a narrow high-risk escape hatch rather than a general approval workflow.
- Improve end-of-cycle summaries with stronger clustering, de-duplication, and top-N policy choices.
- Add an optional LLM-written decision brief layered on top of the mechanical register, while keeping the mechanical register authoritative.
- Distinguish routine spec hardening from true owner-level choices.
- Consider intervention only for high-risk classes such as authority boundary changes, destructive or irreversible behavior, cross-system scope expansion, security/privacy-impacting decisions, or changes that override an explicit human constraint.
- Consider cluster-level intervention instead of line-level intervention, so one pause can cover a coherent group of related decisions.
- Make approval briefs emphasize what happens if the owner accepts all editor choices unchanged.

## Client Capability Notes

Observed live behavior suggests a practical role split:

- Claude Code is viable as a Phase 1 reviewer on the full Whetstone spec.
- Claude Code struggled as a Phase 2 reviewer on the full Whetstone spec under the strict canonical prompt path.
- Codex remains the safer reviewer for Phase 2 strict/rubric/convergence review.
- Claude Code is viable as an editor after the editor prompt was tightened.

These are observations, not permanent compatibility rules. Re-test after CLI/model upgrades or prompt/schema changes.

## MVP Review Mode

Add an `--mvp` mode that evaluates a spec through the lens of minimum buildable precision rather than maximum strictness.

Goal:

- Preserve Whetstone's usefulness for early-stage specs where over-sharpening can create unnecessary surface area.
- Keep the standard high enough for a coherent first implementation.
- Defer nonessential hardening rather than forcing it into v1.

Potential behavior:

- Reclassify feedback so blockers are limited to contradictions, missing authority boundaries, impossible implementation paths, and undefined behavior that prevents a coherent MVP.
- Treat exhaustive observability, broad error-code vocabularies, advanced failure modes, and future-proofing as `post_mvp_hardening` unless they block v1.
- Prefer smaller editor changes and explicit extension points over complete final-policy specification.
- Flag over-sharpening decisions such as unnecessary `SHOULD` -> `MUST` changes, premature enum/status expansion, and policy choices that could be implementation-defined for v1.

Possible artifacts:

- `mvp_scope_report.json`
- `mvp_blockers`
- `mvp_required_decisions`
- `deferred_hardening`
- `over_specification_risks`
- `recommended_v1_cut`

Decision point integration:

- Add labels such as `mvp_required` and `post_mvp_hardening`.
- Approval briefs should separate MVP-critical decisions from future-hardening decisions.

Possible target semantics:

- Map `--mvp` to `mid/permissive` initially, or introduce a future `target_mode: mvp`.
- Consider allowing documented non-MVP majors to remain outside the accepted-draft gate when explicitly classified as deferred hardening.

This should remain a future improvement until the behavior is manually trialed on a few specs and the policy line feels stable.
