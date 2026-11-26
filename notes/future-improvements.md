# Future Improvements

This note captures useful ideas that are not required for the next narrow build step, but should not be lost.

## Reviewer Identity And Execution Provenance

Future patch, recorded 2026-09-27.

Reported discrepancy: an `audit-change` invocation passed `--model gpt-5.6-sol`, correctly recorded in `audit_manifest.json`, while the generated feedback reported `reviewer.model: "gpt-5"`. Validation accepted the mismatch because the reviewer identity fields only require non-empty strings; they are not checked against the invocation. This discrepancy alone does not establish that the wrong model ran.

Required changes:

- Make runner-recorded invocation identity authoritative for canonical reviewer metadata, including client name, version, and requested model. Model-generated identity must not override it.
- Preserve the original model self-reported identity separately, with its source clearly labeled, so normalization does not erase the discrepancy.
- Compare the self-report with the runner-recorded identity and persist a structured mismatch flag with the differing fields and both values. Surface it in the audit report as a provenance warning, without claiming that a label mismatch proves execution by a different model.
- Persist execution telemetry for each audit attempt, including failures: invocation identity, timestamps/duration, exit status, and available client/provider session or request identifiers, reported model metadata, usage, and raw diagnostic references. Bind telemetry to the attempt and its feedback/manifest so provenance checks can trace the evidence. Reuse existing client telemetry machinery where possible.
- Keep requested model, model self-report, and any model identity reported by client/provider telemetry distinct. Mark unavailable execution evidence explicitly; do not infer the actual served model from the requested label or generated prose.
- Update affected schemas and consumers together so the separate self-report and mismatch diagnostics survive validation and reporting.

Regression acceptance criteria:

- Add a deterministic test in `tests/test_change_audit.py` with runner identity `gpt-5.6-sol` and otherwise valid feedback self-reporting `gpt-5`. Assert canonical identity remains `gpt-5.6-sol`, the original `gpt-5` label is retained separately, a mismatch is persisted and surfaced, and execution telemetry is persisted and linked to that attempt.
- Cover matching labels without a false mismatch, and unavailable telemetry without inventing execution evidence. Verify failure paths retain available telemetry.

Implementation starting points: `src/whetstone/change_audit.py`, reviewer validation in `src/whetstone/live.py`, telemetry capture in `src/whetstone/clients.py`, and `contracts/schemas/reviewer_feedback.schema.json`. Apply the same authority rule to shared reviewer paths as appropriate.

## Current Priority Read

This is a living priority read, not a binding implementation plan. It captures the current judgment from recent Whetstone usage across Foreman, Parley, and Whetstone's own decomposed specs.

1. **Controlled invariant / profile vocabulary.**
   This is the strongest foundation item. Profiles, invariants, issue classifications, rubric gaps, decision points, and terminal reports currently share concepts but not a single controlled language. Hardening this early should improve reviewer consistency, artifact validation, decision summaries, profile design, and future project tracking.

2. **First-contact job designer / scope intake.**
   This is the biggest usability lever. Whetstone is powerful, but a fresh operator should not need to know the right workflow, profile set, review mode, budget posture, or scope boundary before the first run. A job designer should inspect a spec, collect a small operator intent payload, produce or update `scope_contract.json`, and emit an executable job descriptor.

3. **Project spec tracking matrix.**
   This started as a possible sidecar, but multi-spec projects have made it feel Whetstone-native. The matrix should not control convergence, but it should track run lineage, source/apply-back state, dependency context, stale sibling specs, decisions, and recommended next actions across a spec ecosystem.

4. **Decision summary standardization.**
   Useful, but less urgent. Agents can already read `decision_register.json` and produce helpful briefs. Baking this in would improve consistency, clustering, and operator handoff, but it is standardization rather than a current bottleneck.

5. **Deeper intervention and conflict machinery.**
   Important eventually, especially for owner-level policy decisions and repeated conflict loops. But broad live intervention can become interrupt-heavy, so it should follow the vocabulary and checkpoint foundations rather than lead them.

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

## Project Spec Tracking Matrix

Multi-spec projects benefit from a compact status artifact that tracks which source docs have been sharpened, which Whetstone drafts are current, which outputs have been applied back, and which specs are stalled, converged, or ready for implementation review.

This should be treated as an optional companion/reporting layer, not core Whetstone sharpening behavior. Whetstone's core job remains improving one spec through review/revision/convergence. A matrix command should help operators make sense of many Whetstone runs across a project without turning Whetstone into a full project-management system.

The important boundary is that project tracking should observe and contextualize execution, not decide convergence. It may summarize lineage, surface stale dependencies, recommend next actions, and warn when a run used outdated context. It must not silently alter scheduler behavior, profile cleanliness, accepted-draft status, or convergence declarations.

This still belongs inside Whetstone rather than as a totally separate project-management utility because the matrix is tightly coupled to Whetstone-specific concepts: run roots, draft hashes, apply-back state, scope contracts, profile sets, terminal states, decisions, and spec lineage. The right shape is a Whetstone companion capability with a clear read-only default and explicit write actions.

Suggested phased shape:

1. **Read-only project matrix.** Scan docs and run roots, then generate a status table and lineage summary. No execution-time coupling.
2. **Dependency-aware context report.** Track which HLDs, indexes, sibling specs, scope contracts, and source hashes were used by each run. Warn when a spec was sharpened against stale or missing project context.
3. **Operator next-action planner.** Recommend apply-back, phase 2, focused pass, synthesis, re-run with dependency context, or lean rewrite. Recommendations remain non-authoritative.
4. **Execution context integration.** Let future runs consume an approved project context artifact so reviewers know which sibling specs are authoritative, which dependencies are informational, and which cross-spec references are out of scope.

Potential command:

```text
whetstone matrix refresh --project-root . --runs-dir ./whetstone_runs --docs-dir ./docs --output ./docs/SPEC_TRACKING_MATRIX.md
```

Potential contents:

- source doc path
- current run-root draft path
- terminal state and phase/round/profile
- source relation: `SOURCE_APPLIED`, `SOURCE_AHEAD_OF_RUN`, `CONVERGED_PENDING_APPLY_BACK`, `NO_RUN_TRACKED`, etc.
- run lineage counted for cumulative accounting
- cumulative tokens and Whetstone wall time
- decision count and unresolved human decision count
- operator confidence / implementation recommendation, for example `BUILD_TARGET`, `LEAN_REWRITE_RECOMMENDED`, `RISK_DISCOVERY_ONLY`, `NEEDS_SYNTHESIS`, or `DEPENDENCY_CONTEXT_ONLY`
- apply-back safety, for example `SAFE_TO_APPLY`, `REVIEW_DECISIONS_FIRST`, `DO_NOT_APPLY_DIRECTLY`, or `SOURCE_ALREADY_AUTHORITY`
- next action
- dependency context used by the run, including HLD/index/sibling spec paths and hashes where available
- dependency freshness: `CURRENT`, `STALE`, `MISSING`, `UNKNOWN`, or `NOT_APPLICABLE`
- cross-spec reference status: unresolved references, referenced specs without runs, and runs that should be rechecked after an upstream spec changed
- lineage notes linking focused runs, synthesis roots, vertical surveys, horizontal closeout runs, Phase 2 runs, and apply-back/strop artifacts

Design constraints:

- The matrix should be mechanically derived where possible and mark any human-supplied recommendation as non-authoritative metadata.
- It should preserve a sharp distinction between Whetstone terminal state and operator implementation judgment. A spec can be `CONVERGED` and still be `LEAN_REWRITE_RECOMMENDED` if the run over-expanded the intended MVP.
- It should avoid mutating source specs or run artifacts unless explicitly asked.
- It should tolerate lineage made of multiple run roots, focused passes, synthesis roots, and apply-back runs.
- It should make decision pressure visible so large runs do not hide behind a green terminal state.
- It should distinguish project-level visibility from run-level authority. A dependency warning may recommend a recheck, but the original run remains historically valid for the context it actually used.
- It should preserve exact source and dependency hashes so operators can reason about whether a sibling spec changed materially or only cosmetically.

Potential UX:

- `whetstone matrix refresh`: regenerate the project matrix from current docs and run roots.
- `whetstone matrix inspect <spec-or-run>`: explain one spec's lineage, current source relation, dependencies, decisions, and recommended next step.
- `whetstone matrix stale`: list specs whose dependency context changed after their latest run.
- `whetstone matrix context --spec <path>`: produce an approved context bundle for a future Whetstone run.

Open design questions:

- Should the matrix live in project docs, under `whetstone_runs`, or both?
- How should Whetstone infer lineage when operators create fresh isolated roots from prior drafts?
- Should dependency context be declared manually, inferred from links, or generated by first-contact job design?
- Should the matrix eventually support cross-spec impact analysis when a leaf spec changes a shared contract?
- How much of this should be general-purpose JSON first versus human-readable Markdown first?

## Decision Summary And Intervention Refinement

Decision capture is useful, but live intervention is likely too interrupt-heavy for normal Whetstone runs. Real runs can produce dozens of decision points, and pausing on each meaningful requirement, scope, or policy change would turn review into an expensive permission flow.

Future improvements:

- Keep `end_of_cycle` as the default decision mode.
- Treat `intervention` as a narrow high-risk escape hatch rather than a general approval workflow.
- Improve end-of-cycle summaries with stronger clustering, de-duplication, and top-N policy choices.
- Add an optional LLM-written decision brief layered on top of the mechanical register, while keeping the mechanical register authoritative.
  - The mechanical register remains the source of truth for decision IDs, sections, trigger types, severities, round/profile provenance, and action status.
  - The LLM brief is explicitly non-authoritative interpretation. It must cite the decision IDs and sections it summarizes, and it must not invent new decision state.
  - The brief should produce an operator-facing top-level digest:
    - top decisions requiring human judgment
    - accepted mechanical hardening
    - scope expansions and possible over-MVP additions
    - deferred items preserved by the scope contract
    - recommended operator actions before apply-back or Phase 2
  - The brief should distinguish "routine precision hardening" from "owner-level policy choice" so large runs do not bury the handful of real decisions inside dozens of small MUST/SHOULD edits.
  - The brief should call out when a `could` or deferred scope-contract surface appears to have become required behavior.
  - The brief should include a confidence / review-needed marker per cluster, not just a polished narrative.

## Implementation Topology Profile Lens

Logic Lens implementation feedback was a strong positive signal for Whetstone: the sharpened specs made the first vertical slice feel like instantiating a contract rather than inventing an app. The remaining friction was not product fog; it was normal implementation design ambiguity around package/module ownership and boundary placement.

This suggests a future optional profile lens, not more general strictness. A lightweight `implementation_topology` lens could review specs for:

- package/module ownership
- generic primitive versus domain-specific fixture boundaries
- dependency direction between packages
- ownership of orchestration helpers
- public versus internal contract surfaces
- package-level test ownership
- duplicated concepts across sibling specs and which spec is authoritative

For Logic Lens, this lens would have surfaced questions such as:

- Should generic adapter primitives live in `@logic-lens/expressions` while sorting-specific adapters live in `@logic-lens/sorting` or a future `@logic-lens/sorting-expressions` package?
- Which package owns `adaptCurrentStep` or equivalent orchestration helpers?
- Is it acceptable for `@logic-lens/expressions` to import sorting types for MVP fixtures, or should that dependency be inverted?
- When both Trace Engine and Expression Adapter discuss adapter orchestration, which spec owns the concrete runtime function?
- Should the UI use core playback state directly, or is local `stepIndex` acceptable for the first slice?

This should not become an always-on architectural ceremony profile. The right shape is probably a new profile set such as `modular_app_mvp`: `utility_mvp` plus `implementation_topology`. The lens should make first-slice package topology explicit enough to avoid accidental dependency drift while still allowing pragmatic MVP placement.
- Distinguish routine spec hardening from true owner-level choices.
- Consider intervention only for high-risk classes such as authority boundary changes, destructive or irreversible behavior, cross-system scope expansion, security/privacy-impacting decisions, or changes that override an explicit human constraint.
- Consider cluster-level intervention instead of line-level intervention, so one pause can cover a coherent group of related decisions.
- Make approval briefs emphasize what happens if the owner accepts all editor choices unchanged.

### Between-Round Operator Decision Checkpoints

Whetstone now has an artifact-only slice that writes nonblocking `operator_decision_checkpoint.json` candidates plus terminal `operator_decision_checkpoint_summary.*` outputs. The remaining future work is to turn those candidates into an optional between-round operator or LLM-guided checkpoint mode.

Potential flow:

1. Reviewer finds blocker or major issues.
2. Orchestrator classifies each issue or issue cluster as one of:
   - `editor_fixable`: missing detail, inconsistency, schema hole, or local contract gap the Editor can resolve without new owner intent.
   - `operator_decision_required`: policy, scope, authority, destructive behavior, product behavior, or tradeoff that the Editor should not invent.
   - `deferable_scope_boundary`: valuable hardening request that should remain outside the current scope contract unless the operator promotes it.
3. Before the next Editor pass, Whetstone may pause and present a compact decision card.
4. Operator selects an option or provides freeform `Other` text.
5. Whetstone persists the response into the decision register.
6. The next Editor prompt treats the operator response as authoritative context.

Decision card shape:

- decision question
- affected sections
- triggering feedback IDs
- 2-4 concrete options
- recommended option
- impact/tradeoff of each option
- freeform `Other`
- default action if the operator skips the checkpoint

Example:

```text
Decision: How strict is anchor confidence mode for MVP?

A. Hard require context-anchor.yaml.
   Missing, schema-invalid, or incomplete anchors fail before writing localization files.

B. Allow partial anchor mode.
   Use anchors where present and fall back to normal confidence for missing keys.

C. Defer anchor mode.
   Treat --confidence-mode anchor as unsupported until post-MVP.

Recommended: A, because anchor mode only has value if its authority input is deterministic.
```

Possible config:

```yaml
decisions:
  mode: end_of_cycle | between_rounds | off
  checkpoint_on:
    - blocker
    - repeated_major
    - scope_escalation
    - authority_conflict
  max_questions_per_checkpoint: 3
  default_when_skipped: continue_without_operator_input | halt_for_operator
```

Possible artifacts:

- `rounds/round-N/operator_decision_checkpoint.json`
- `rounds/operator_decision_checkpoint_summary.json`
- `rounds/operator_decision_checkpoint_summary.md`
- `rounds/round-N/operator_decision_response.json`
- `rounds/decision_register.json`
- `rounds/decision_summary.md`

Design constraints:

- The checkpoint classifier should be conservative. It should not pause for routine precision hardening.
- Multiple related issues should be clustered into one decision whenever possible.
- The operator response must be persisted as a versioned, hashable artifact.
- Editor prompts must distinguish operator decisions from reviewer suggestions.
- The feature should have a noninteractive mode for automation, where checkpoints are recorded but not paused.
- Auto mode should consume the same checkpoint artifact shape as human mode and persist the same response artifact shape, with the selected option marked as LLM-guided rather than operator-selected.

## Vertical Review Pressure Relief

Vertical review is useful because each profile reviews the same draft before any edits are made, which gives operators a cleaner cross-profile read than a long horizontal sequence. The current implementation can still overload the Editor when the merged feedback packet is large or spans unrelated surfaces.

Future work should address this structurally before inventing fuzzy pressure scoring. Two candidate strategies are worth preserving:

1. **Interleaved vertical cadence.** Run each profile independently, then allow an intermediate Editor pass before the next profile or profile cycle. This reduces Editor load but moves closer to horizontal behavior.
2. **Vertical review with sliced editing.** Run the full vertical review stack against one draft, then split the consolidated Editor work into profile-led slices. Each finding has exactly one primary slice owner, optional related-slice awareness, and an auditable deferred status when not handled in the active slice.

The second option is the stronger default candidate because it preserves vertical's main benefit: every Reviewer profile evaluates the same pre-edit draft. The Editor then receives bounded work orders instead of one giant merged packet.

Design constraints:

- Slices are profile-led, not profile-exclusive. The Editor may update adjacent or coupled sections when needed for coherence.
- Every feedback item must have exactly one primary owner in the slice plan so findings cannot disappear between slices.
- Cross-slice edits must be recorded in the Editor summary.
- No profile is considered clean until a later Reviewer pass verifies the post-slice draft for that profile.
- The final authority remains a full vertical re-review on the edited draft.
- This should remain a future scheduler feature until the current scheduler/resume/closeout behavior has had more soak time.

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

## Domain-Specific Rubric Layers

Whetstone may be a strong fit for domain-specific certification and regulated software workflows, where the hard part is not only making a spec buildable, but making it traceable to external standards, controls, evidence expectations, and certification gates.

Swapping a custom convergence rubric already works as a lightweight path, but certification use cases likely deserve a first-class layered model rather than silently replacing the base buildability rubric.

Potential model:

```yaml
rubric_layers:
  - kind: buildability
    profile: standard-v1
    enforcement_mode: blocking
  - kind: domain
    profile: iso-13485-software-v1
    source: custom
    path: ./rubrics/iso-13485-software-v1.md
    authority_refs:
      - ISO 13485:2016
      - FDA QMSR
    enforcement_mode: blocking
    traceability_required: true
```

Design intent:

- Keep the base Whetstone rubric responsible for deterministic buildability, state legality, artifact integrity, and operability.
- Let domain rubric layers evaluate domain-specific obligations such as named controls, required evidence, compliance language, safety categories, auditability, and certification traceability.
- Avoid hiding the active standard by making every rubric layer explicit, versioned, hash-pinned, and persisted in manifests.
- Allow `enforcement_mode: advisory | blocking` so early exploratory reviews can surface domain gaps without making every gap terminal.

Possible artifacts:

- `rounds/rubric_layers_manifest.json`
- `rounds/domain_gap_report.json`
- `rounds/domain_traceability_matrix.json`
- `rounds/domain_evidence_requirements.json`

Potential schema additions:

- Add `rubric_layer` to reviewer findings and rubric gaps.
- Add `authority_ref` or `control_id` for domain findings.
- Add `evidence_required: true|false` and `evidence_type`.
- Add `traceability_status: missing | partial | satisfied | not_applicable`.

Open design questions:

- Should domain layers run in Phase 1, Phase 2, or both?
- Should domain gaps participate in accepted-draft gating, convergence gating, or a separate certification-readiness gate?
- How should Whetstone handle copyrighted or proprietary standards that cannot be fully embedded in prompts?
- Should built-in domain profiles ever exist, or should Whetstone only provide the framework and let users supply domain packs?

## Interactive / LLM-Backed Scope Intake

Whetstone now supports a thin first-contact scope contract path through `intake --template mvp` and deterministic `intake --from-notes`, but a fuller operator experience should remain on the roadmap.

Future direction:

- Interactive questionnaire with structured options plus an `Other` freeform escape hatch.
- LLM-backed canonicalization from operator answers into `scope_contract.json`.
- Review-and-approve loop showing how Whetstone interpreted freeform scope intent.
- Scope promotion workflow when reviewers repeatedly identify valuable deferred work.
- Versioned scope contract revisions during a run, with decision-register entries when scope changes.

The key invariant should remain: freeform operator intent may help generate the contract, but Whetstone should only enforce persisted, approved, schema-valid scope fields.

## First-Contact Job Designer

**Single-spec MVP staging rehearsal, 2026-11-26.** On stable 0.3.0 a fresh
calling agent selected the right review and protections but needed a custom
package script, installed internals and a timestamp conversion to reach scope
approval. In the development rehearsal another fresh agent staged its own ticket
import spec from the runner skill, worked example and public CLI. It encoded the
preview rationale and whole-file rejection as two blocking semantic commitments.
Draft admission dry-run stopped at scope approval (exit 2). After fixture-only
approval it rebuilt in a fresh directory and passed dry-run (exit 0). Both
checks left the run destination absent. The agent needed no procedural coaching.
It flagged `admitted: false` on successful dry-run, now explained in the example.

The agents were given the skill location and used different synthetic specs.
This demonstrates staging after skill discovery. Timing, automatic discovery
and live execution were outside the rehearsal. The development cohort passed
119 tests. The release candidate carries this bounded staging improvement;
the broader job designer below remains a proposal.

Whetstone should eventually have a first-contact job design capability that sits above scope intake. The operator supplies a fresh spec plus a small set of intent markers, and Whetstone produces a concrete job descriptor that downstream commands can execute without guesswork.

This feature is broader than scope-contract generation, but it should produce or update a scope contract as one of its outputs. The scope contract remains the authoritative boundary artifact; the job descriptor explains how Whetstone should pressure the spec.

Potential command shape:

```text
whetstone design-job --spec path/to/spec.md --template mvp --output whetstone_job.json
whetstone run-job --job whetstone_job.json
```

The designer should inspect the spec and classify it along dimensions such as:

- system type: utility tool, stateful workflow, adapter, protocol, data contract, governance process, exploratory concept
- statefulness: none, light, heavy
- artifact intensity: none, light, heavy
- determinism need: low, medium, high
- external effects: none, filesystem, network, user-visible, destructive
- implementation risk: low, medium, high
- over-sharpening risk: low, medium, high

It should also collect a small operator intent payload:

- target intent: exploratory, MVP, standard production readiness, governance
- budget preference: cheap, balanced, thorough
- scope posture: strict MVP, pragmatic, expansive
- apply-back policy: manual only by default
- whether diagnostics, exhaustive reports, retry/resume matrices, governance proof, and broad validation matrices are in scope
- whether the operator wants a one-job run or a survey-then-sharpen strategy

Potential `whetstone_job.json` contents:

```json
{
  "schema_version": "1.0",
  "source_spec_path": "docs/spec.md",
  "job_goal": "mvp_readiness",
  "spec_classification": {
    "system_type": "utility_tool",
    "risk_level": "medium",
    "statefulness": "light",
    "artifact_intensity": "medium",
    "determinism_need": "medium",
    "over_sharpening_risk": "high"
  },
  "operator_intent": {
    "target": "mvp",
    "budget_preference": "balanced",
    "scope_posture": "strict_mvp",
    "apply_back_policy": "manual_only"
  },
  "recommended_strategy": {
    "strategy_kind": "survey_then_sharpen",
    "workflow": "mvp",
    "profile_set": "utility_mvp",
    "review_mode": "vertical",
    "budget_exhaustion_policy": "soft"
  },
  "scope_contract_path": "rounds/intake/scope_contract.json",
  "operator_review_required": true
}
```

The job descriptor should be explicit enough that a later Whetstone command can execute from it, but it should remain reviewable before live client calls begin.

### Survey Then Sharpen Strategy

A promising default for fresh, medium-or-larger specs is a two-job strategy: **Survey -> Sharpen**.

Job 1: Vertical Survey

- Purpose: get full-stack signal efficiently without pretending the first pass should settle everything.
- Use `review.mode: vertical`.
- Use the designer-selected profile set, commonly `utility_mvp`, `balanced_mvp`, or `stateful_system`.
- Use semi-generous per-profile budgets, for example 10.
- Use `budget_exhaustion_policy: soft`.
- Use decision mode `end_of_cycle`.
- Never apply back automatically.

The vertical survey should answer:

- which review profiles bite hardest
- whether the selected profile set fits the spec
- whether scope is expanding
- which decision clusters recur
- whether the spec is being overcooked
- whether a synthesis pass or scope-contract revision is needed before sharpening

After Job 1, an operator or agent should review:

- `decision_summary.md`
- `operator_decision_checkpoint_summary.md`
- `technical_failure_report.json` or `convergence_failure_report.json` if present
- `contract_surface_report.md`
- final draft diff
- token/wall-time totals

This review gate may revise the scope contract or job descriptor before Job 2. The key point is that the first job reveals Whetstone's pressure points before the operator commits to a closing strategy.

Job 2: Horizontal Sharpen

- Purpose: close the spec deliberately, profile by profile.
- Use `review.mode: horizontal`.
- Use the same or adjusted profile set.
- Use harder budgets and stricter profile closure.
- Consider lower budgets than Job 1 because the surface is now known.
- Use round-by-round decision promotion only for high-impact owner decisions, scope promotions, authority changes, destructive behavior, or product policy.
- Keep apply-back manual.
- Enter Phase 2 only after Phase 1 genuinely stabilizes.

This pattern should help Whetstone stay practical: the first run discovers the shape of the problem, and the second run sharpens only the surfaces the operator agrees should be sharpened.

Open design questions:

- Should `survey_then_sharpen` be the default for unknown first-contact specs, or only for specs above a size/risk threshold?
- Should the designer recommend `utility_mvp` automatically when over-sharpening risk is high?
- Should Job 1 produce a revised scope-contract proposal automatically, or only a recommendation?
- Should `run-job` create separate run roots for survey and sharpen, or encode lineage inside one higher-level job directory?
- Should a vertical survey ever proceed directly to Phase 2 if it reaches Phase 1 stable, or should first-contact jobs always stop for operator review before Phase 2?


## Selected-Lens Reviewer-Only Audits And Consolidation

Requirements direction captured 2026-10-31 from explicit operator instruction.
**Status: requirements captured; mechanics are open.** This records the feature
direction only, not approval of mechanics, implementation, spec ratification, a
live review or a new release.
It does not reopen verified-promotion qualification, change its storage contract,
or add work to that initiative. Existing work and single-lens audits are preserved.

### Requested behavior

- One bounded reviewer-only audit accepts an explicit selected set of profile
  lenses, including the existing single-lens case. It must not silently expand
  the selection to every profile or require the operator to manage separate audit
  invocations. No new profile names or automatic lens selection are approved.
- Each selected lens receives its own independent Reviewer pass against the
  same frozen specification inputs, audit intent and scope. Do not combine all
  lenses into one prompt. A lens pass must not be conditioned on findings from
  another lens; how independent client contexts are enforced remains to be defined.
- After the lens passes, one consolidation stage for that audit round produces
  one complete bounded assessment and actionable findings list. Here, audit
  round means this grouped audit assessment, not a Phase 1/Phase 2 scheduler round.
- Merge duplicate findings while retaining distinct concerns, their evidence,
  scope and recommended actions. Preserve every original review and maintain
  traceable attribution from each consolidated finding to its source findings
  and lenses. Every source finding must remain accounted for: no silent omission,
  including out-of-scope findings, and no destructive rewriting of original reviews.
  Source identities must be distinguishable even if separate passes reuse a
  local feedback ID; the concrete identity/reference shape is not yet chosen.
- Surface disagreements explicitly, including incompatible claims, scope
  interpretations, recommended actions and severity judgments. Reviewer agreement
  is corroborating context, not proof of correctness, completeness or preservation.
- Preserve failed, invalid or incomplete per-lens outcomes and the consolidation
  stage's own status. Retain available failed/invalid responses and diagnostics
  as labeled evidence, without treating them as valid reviews. A report may
  expose useful partial findings, but must not
  present a partial audit as a complete bounded assessment or a clean pass.
  Execution completion, assessment content and semantic confidence are distinct.
- Make separate Reviewer calls/attempts and their costs visible, along with any
  consolidation calls. Retain attributable timing, model/client provenance and
  available usage/cost information; mark unavailable measurements explicitly.
  Do not hide extra calls behind a single apparent review or infer served-model
  identity/cost from model-generated prose.
- Keep the workflow bounded and reviewer-only: no automatic Editor, source
  rewrite, apply-back, Phase 1/Phase 2 admission or convergence claim. Existing
  single-lens audit behavior remains supported. No extra review rounds or
  repeat-until-agreement loop is implied. This capture does not change its
  schemas, findings/severity-derived verdicts or failure behavior.

### Fit with inspected machinery

- [Current audit owner](../src/whetstone/change_audit.py):
  `run_change_audit` takes one `profile`, reads the notes/specs, builds a
  self-contained brief/manifest, invokes one Reviewer and writes feedback plus
  JSON/Markdown reports under `change_audit/`. It already preserves valid
  out-of-scope feedback separately from verdict counts and reports Reviewer
  failure as `audit_failed`. This is the natural workflow seam to investigate;
  repeated calls to it are not an implementation of the requested feature.
- The [CLI](../src/whetstone/cli.py) currently has a scalar `--profile` defaulting
  to `consistency`, required notes and repeated spec inputs. Each owner invocation
  reads source files again and writes fixed artifact paths. Running it once per
  lens against one root could overwrite prior evidence and does not establish a
  shared frozen input set. Its brief includes the profile and its hashes use
  normalized text; the design must distinguish common frozen input identity
  from per-lens brief/prompt identity rather than require identical prompt hashes.
- [Diagnostic sweep](../src/whetstone/diagnostic_sweep.py) supplies a related
  reviewer-only per-profile pattern with retained round feedback, source-profile
  attribution, clusters and telemetry totals. It uses configured Phase 1 profile
  sets and a recommendation report. That is useful implementation context, not
  the requested selected-lens audit contract or a consolidation/provenance policy.
- The matching [scope owner](../docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#change-audit-workflow)
  and [Quickstart](../docs/OPERATOR_QUICKSTART.md#run-a-lightweight-change-audit)
  document the current one-profile audit. The
  [existing audit-objectives proposal](../IMPLEMENTATION_PLAN.md#proposed-audit-change-objectives-release)
  is explicitly unratified and unimplemented. Coordinate any later artifact and
  version definitions with it; selecting multiple lenses does not approve that
  proposal or equate lens agreement with objective assessment coverage.
- [Existing audit tests](../tests/test_change_audit.py) cover one Reviewer prompt,
  report/artifact generation, failed review and out-of-scope severity handling.
  They are inspection evidence, not passing multi-lens qualification or tests run
  during this requirements-only capture. The earlier
  [identity/provenance direction](#reviewer-identity-and-execution-provenance)
  is adjacent tracking for cost/provenance design, not an implicit authorization
  to implement or expand it here.

### Open decisions — not approved mechanics

1. **Consolidation mechanism and model:** deterministic grouping, model-backed
   synthesis or another bounded mechanism; model/role selection if needed;
   evidence access; duplicate-versus-distinct criteria; how any consolidation-only
   concern is distinguished from an original finding; and the single-lens path
   without assuming a mandatory extra model call.
2. **Severity and disagreement treatment:** preserve source severities and scope
   judgments, but decide consolidated severity/verdict rules and how unresolved
   conflicts affect the bounded assessment. Neither maximum severity, averaging,
   majority voting nor a deciding model is selected by this capture.
3. **Failure and recovery policy:** behavior when a lens fails, is invalid, times
   out, is cancelled or exhausts budget; whether/when consolidation of partial
   results is allowed; explicit continuation/retry authority; preserving earlier
   successes; interruption during consolidation/publication; and conditions for
   declaring the selected audit complete. Partial results can never be mislabeled
   complete regardless of the chosen policy.
4. **Order and concurrency:** serial versus parallel execution, resource limits,
   independent context boundaries and deterministic attribution. No parallel
   writers, distributed execution or new storage backend is approved.
5. **CLI/config and artifact shape:** lens-selection syntax and validation,
   shared snapshot/scope binding, per-lens/attempt namespaces and stable references,
   report/result/schema versioning, reentry and compatibility with current v1 and
   the separate objectives proposal. No new flag, enum, artifact path or schema
   name in this feature has been ratified.
6. **Budgets:** finite audit-wide and per-lens limits, consolidation and retry
   allowances, wall time, tokens/cost where observable, cancellation and reporting
   of exhausted/unknown amounts. No numeric limits, model or automatic retry
   allowance is selected.

### Smallest next definition step

Prepare one bounded audit-extension decision brief, before coding or normative
amendments. Define the input-freeze/completion boundary and a minimal provenance
and reporting sketch; present concrete choices for the six open decisions above.
Use three small illustrative cases: duplicate plus distinct findings, an explicit
severity/claim disagreement, and one failed or incomplete lens. Show where every
original finding/outcome appears in the assessment and how calls/costs and
incompleteness remain visible. Keep single-lens compatibility explicit and
coordinate artifact ownership with the existing objectives proposal. These are
paper examples for definition, not permission to invoke models or build a broader
review, orchestration or verified-promotion redesign.

## Declarative Profile Lenses And Configurable Workflows

Direction and local assessment captured in the
[bounded draft specification](../docs/DECLARATIVE_PROFILES_AND_WORKFLOWS_DRAFT.md),
2026-10-31. **Draft for review only; implementation and proposed mechanics are
not approved.** The [implementation-plan proposal](../IMPLEMENTATION_PLAN.md#proposed-declarative-profiles-and-workflows)
owns the proposed finite delivery sequence; this note is not another checklist.

Use data-defined, exactly versioned lenses discovered from configured local
locations, with separate workflows selecting steps, order, finite budgets,
supported repeats/skips and edit-triggered rechecks. Repeated lens occurrences
need independent step identities. New jobs freeze selected effective definitions
and plans for resume; installed definition changes must not silently alter them.
New engine capabilities, typed phase/terminal gates, rubric requirements and
preservation remain engine-owned. Old jobs/contracts and current V qualification
remain intact.

The draft recommends strict deterministic resolution, no collision overrides,
job-local snapshots and initially conservative rechecks after all accepted edits.
Current selective-invalidation helpers are not operationally wired. Replacing
name/position-based Phase 2 logic and whole-vocabulary coupling requires new
versioned consumers and qualification, not just new prompt files.

Shared definitions serve single/multiple lens audits and sharpening loops without
equating their completion claims. The
[selected-lens audit requirements](#selected-lens-reviewer-only-audits-and-consolidation)
above remain preserved. Consolidation mechanism/model, severity conflict handling,
failure/recovery, execution order/concurrency and final budget/CLI/artifact policy
remain open; this draft does not approve or implement grouped consolidation.

Local review revision, 2026-11-02: the draft resolves four technical gaps with
portable whole-draft built-ins, explicit prerequisite/completion records,
phase-scoped rechecks and retained execution-window semantics. Historical
anchors, prior-phase evidence, entry verification and existing job contracts
remain preserved. These remain proposed mechanics; product decisions and
implementation authorization are separate.


## Verified Promotion: Phase 1 Policy Independence And Final Human Review

Implementation update: the operator subsequently authorized shared Phase 1
completion and MVP with balanced_mvp/utility_mvp. That bounded work is tracked in
[the implementation plan](../IMPLEMENTATION_PLAN.md#shared-phase-1-completion-and-mvp-qualification-active)
and [qualification record](../docs/PHASE1_COMPLETION_QUALIFICATION.md). The original
discussion below remains historical; other workflows, Phase 2, final human review
and storage changes remain future work.

Discussion captured 2026-11-22. **Future design direction only; no implementation,
contract changes, runtime default change or bridge deprecation is authorized by
this note.** This item concerns compatibility of verified promotion with
existing workflows, not creation of configurable workflows. The separate
[Declarative Profile Lenses And Configurable Workflows](#declarative-profile-lenses-and-configurable-workflows)
proposal is related architectural context, not a prerequisite or an expansion
of this item's scope. Reuse the promotion machinery rather than create an engine
per workflow.

### Separate Phase 1 review policy from change acceptance

Investigate making verified promotion reusable across Phase 1 review policies,
including MVP, exploratory, governance and custom selections. Review purpose and
criteria should be conceptually separate from candidate preservation, semantic
verification and promotion. The operator considers Phase 2 a distinct concern;
this item does not require generalizing Phase 2 at the same time.

Operator priority clarified 2026-11-22: MVP is the most frequently used workflow;
standard applies more review rigor than desired for those jobs. Prioritize MVP
compatibility, with the intended direction that every otherwise supported review
workflow can use verified promotion. Do not require switching to standard to gain
preservation and semantic verification. Preserve each workflow's scope, review
pressure and completion meaning. This is important new-job capability work,
not merely optional configurable-workflow polish. Other existing workflows
remain in scope for compatibility assessment; it is not permission for arbitrary
unvalidated execution or a claim of current support.

Static inspection found reusable candidate/semantic machinery, but broader
workflow support is not merely untested: `vnext_verified_cli.py`,
`vnext_verified_review.py`, `vnext_verified_review_protocol.py`,
`vnext_verified_vertical_phase1.py` and `vnext_review_configuration.py` impose
standard-workflow restrictions. Phase 2 separately pins standard workflow and
rubric through schemas and `vnext_verified_phase2_binding.py`. Existing tests
assert refusals. Recognizing workflow names in admission structures does not
establish executable support.

Next definition step: distinguish first-release qualification restrictions from
real workflow-dependent scheduling, scope, prompt, evidence and completion
semantics. Propose a shared policy boundary and the minimum versioned changes
and qualification needed for Phase 1. Do not merely remove guards, loosen frozen
contracts, or assume end-to-end support. Preserve existing job identities and
recovery behavior. No runtime tests or alternate-workflow execution were performed
for this discussion.



### Separate follow-up: qualification limits versus architectural coupling

Record a future investigation after the current operator-experience exercise.
Do not run that campaign as part of this discussion or assume a refactor is
needed. Static inspection establishes explicit restrictions, but does not settle
whether they are prudent qualification boundaries, removable release-specific
coupling, or symptoms of deeper architectural separation problems.

Trace the boundaries between review policy/profile configuration, scheduling,
candidate preservation, semantic verification, promotion, evidence invalidation
and phase completion. Classify each restriction by its actual dependency and
qualification evidence. Use existing MVP and profile-set selections as concrete
cases: can they consume the shared promotion contract through policy inputs,
without workflow-specific changes inside preservation/promotion? Distinguish
necessary scheduler integration after an accepted revision from accidental
workflow-name coupling. Inspect before prescribing a centralized gate or other
replacement architecture.

Deliver an evidence-backed assessment identifying qualification-only work,
missing behavior, any justified targeted refactoring, and unresolved questions.
Estimate implementation only after that assessment; preserve existing contracts
and runtime gates until separately authorized changes are designed and qualified.
Phase 2 may have genuinely distinct requirements and need not be generalized
alongside Phase 1. This campaign is separate from the immediate documentation,
skill and staging-ergonomics proposals.

Horizontal, vertical and focused Phase 1 routes are covered for the qualified
selection. No concrete missing alternative route was identified; do not carry
forward a speculative "arbitrary alternative routes" gap.

### Phase 1 profile-set compatibility

Direction clarified 2026-11-22: extend verified promotion to existing supported
Phase 1 profile sets by generalizing and qualifying the existing mechanism,
not by implementing a promotion engine per set. This is distinct from inventing
new configurable profiles and complements the existing-workflow compatibility
work above.

Profile sets are presets of profile sequences and default budgets. In the current
vocabulary, `balanced_mvp` uses the same Phase 1 profiles as `stateful_system`
with lower default budgets; `utility_mvp` selects buildability, consistency,
light determinism and light operability profiles. These are not all merely
budget aliases.

Static inspection found that verified Phase 1 sequencing and closeout largely
consume configured profile lists. However, `vnext_verified_cli.py` explicitly
requires `stateful_system`; other sets are not currently supported merely because
their definitions exist. Assess the public restriction and any associated
schema, contract, profile classification, prompt and completion assumptions.
Validate selected sets through review, editing, semantic verification, promotion
and Phase 1 completion, including supported horizontal/vertical/focused routes
and refusal cases as applicable. Preserve frozen job identities and existing
qualification boundaries; do not simply remove the guard and claim support.

Implementation effort is not yet sized. No alternate-set execution or new test
qualification was performed for this capture. Phase 2 profile-set compatibility
remains a separate assessment rather than an implied deliverable of this item.

### Optional final human semantic review

Agreed direction: retain internal candidate verification throughout verified
promotion, with an explicit option for human semantic review of the accumulated
changes against the starting specification before source adoption. Keep review
of meaning distinct from source-write authorization. Final review is not the
same assurance as operator attestation before each accepted revision; determine
whether any per-change human-evidence use case must also be retained.

This is a possible step toward eventual preservation-bridge retirement, not a
current deprecation decision. Consider verified promotion the preferred design
direction for supported new protected-editing jobs, while retaining existing
bridge jobs and explicitly justified exceptions. The bridge's mechanical-or-
operator-attested evidence policy is a substantive distinction from model-based
semantic verification. Fewer interruptions or better outcomes have not been
measured.

Preparation should infer document purpose, authority, expected depth and permitted
change from operator intent and project evidence, with clarification for material
ambiguity. HLDs, leaf specs and machine contracts are examples, not a mandatory
naming scheme or hierarchy. Protect explanatory rationale and nuance where those
serve the document's purpose; do not assume technical requirements exhaust what
matters. Start with skills, documentation and worked examples rather than a new
deterministic preparation subsystem.


## Verified Promotion: Portable Storage Option Assessment

Future investigation captured 2026-11-22; separate from the current operator-
experience exercise and review-policy compatibility work. No storage-contract
change, guard bypass or implementation is authorized by this capture.

The operator considers the current canonical physical-root binding and qualified
local macOS/APFS restriction too demanding for ordinary usage. Evaluate an
optional storage approach closer to the preservation bridge's model: confined
run artifacts, writer exclusion, immutable evidence and durable publication,
without assuming the same physical-directory binding and platform restriction
are necessary for every verified-promotion job.

Compare actual mechanisms and guarantees rather than treating the bridge as
already portable or fully qualified on other filesystems. Identify which strict
requirements serve accidental-concurrency protection, crash consistency,
identity/replay integrity or other threats, and which are qualification limits.
Assess a versioned storage-policy/backend boundary and explicitly state any
changed guarantees. Evaluate relocation/copy/reopen semantics, supported local
filesystems and recovery behavior rather than promising portability by dropping
checks. Preserve existing physically bound jobs under their current contract;
any alternative requires its own design, qualification and explicit selection.

Desired outcome: an evidence-backed recommendation on whether a less restrictive
storage option can meet normal operator needs, its trade-offs and implementation
scope. This is an open option to assess, not a conclusion that existing durability
or identity checks are unnecessary.


## Operator Surface: Staging Guidance Refinement Inputs

Agreed discussion inputs, 2026-11-22. Capture for later documentation and skill
refinement; this note does not implement that refinement. Keep this packaging
work separate from future verified-promotion compatibility, architecture and
storage investigations above.

- Distinguish job outcome (assessment versus stabilization), review expectations
  (workflow/profile set), editing boundaries, semantic verification preference,
  and runtime eligibility. These are related choices, not interchangeable modes.
- Infer preparation choices from operator intent and existing project evidence.
  Present material assumptions; ask only about consequential ambiguity. Do not
  require a document taxonomy or ask operators to classify every line.
- Prefer the question "Which parts are settled decisions, and which remain open
  to design changes?" over the loaded preserve-versus-rethink question. Respect
  for operator intent is assumed. This answer defines boundaries for either
  guarded editing mechanism; it does not select the mechanism itself.
- Explain that bridge semantic preservation evidence can require exact operator
  attestation, whereas verified promotion uses a separate semantic Verifier.
  Neither grants permission for unauthorized requirement changes. Do not imply
  every bridge edit pauses or that fewer verified-mode interruptions are proven.
- Check the complete combination against the selected installed runtime before
  launch. Distinguish workflow names from profile-set names. Explain an MVP /
  verified-promotion incompatibility as an unavailable combination of review
  policy and verification mechanism, not as inability to preserve MVP content.
- Offer concrete supported alternatives without silently switching to standard,
  broadening scope, dropping protection or fabricating attestations. Bridge
  support for any proposed combination must also be verified, not assumed.
- Keep the bridge available where needed today. Verified promotion is a preferred
  future direction for supported new protected-editing jobs, not an unconditional
  current default; no bridge deprecation decision has been made.
- Explain the bridge journey: agent prepares exact boundaries and bindings;
  operator sees concrete before/after effects when attestation is required;
  agent handles local acceptance and supported continuation. Reuse authority
  within its actual scope without automatically rebasing changed bindings.
- Separate data-sharing authority, execution permission, effect acceptance and
  source apply-back. Selecting enforcement does not approve unseen rewrites.
- Use version-consistent docs and worked examples before proposing a universal
  deterministic preparation subsystem. The original feedback concerned staging;
  alleged live-run defects and expensive troubleshooting are not established by
  that experience. Documentation confusion was independently observed.

Remaining walkthrough areas include functional scope/depth, review scheduling
and budgets, client/execution preparation, validation/readiness, and monitoring
and continuation handoffs. Continue the discussion before treating the complete
operator journey as specified.


### Scope intake: purpose, minimum content and clarification discipline

Operator feedback, 2026-11-22: during staging, scope notes accumulated definitions
and prescriptions that the operator considered outside scope intake's purpose.
Clarify this in the agent skill and operator guidance; do not turn intake into a
second specification-authoring exercise.

Proposed guidance for refinement:

- Scope intake directs this review: intended outcome, consumers, in-scope flows
  and surfaces, exclusions/deferrals, appropriate depth, expansion boundaries,
  and a concrete stopping criterion. Keep content proportionate to the job.
- Refer to existing specification definitions instead of duplicating them.
  Record established constraints when they bound the review, but do not invent
  architecture, APIs, schemas, failure policies or new requirements in order to
  fill scope fields. Technical terms are appropriate when identifying a boundary;
  unnecessary technical prescription is the problem.
- Distinguish a review-depth decision (for example, specify failure categories but
  defer exhaustive error codes) from a product decision about what failure
  behavior must be. Intake should not silently settle the latter.
- Infer routine scope from operator intent and project guidance, showing material
  assumptions succinctly. Ask when ambiguity changes what the run may review,
  expand, defer or consider sufficient; do not ask exhaustive design questions
  just to complete the notes.
- Leave in-scope unresolved design questions for the review where appropriate.
  Escalate upfront only when their answer is needed to establish the job boundary
  or required authority. Unknown design details need not all block staging.
- Include concise positive/negative examples and explain how approved scope
  constrains review pressure. Verify the guidance against current intake schema
  and compilation behavior before implementation; no schema change is implied.


### Proposed operator-guide wording: select a review schedule

Draft captured 2026-11-22 for the later operator-guide refinement. This is a
recommendation policy, not a change to runtime defaults or scheduler semantics.

Recommend **vertical review** as the starting choice for broad, interconnected
sharpening. Multiple configured lenses review the same draft, followed by a
consolidated Editor operation when correction is needed. This lets the Editor
consider interacting findings together. Early-stage specifications often fit
this pattern, but project age alone does not determine the schedule.

Recommend **horizontal review** when there is a concrete dependency sequence:
resolving one lens's concerns materially improves the draft that later lenses
should inspect. Explain that dependency briefly rather than claiming horizontal
review inherently resolves stubborn blockers better.

Recommend a **focused review** when the question is isolated to one supported
profile. Focused stability does not establish full Phase 1 stability or Phase 2
eligibility. A missing product decision needs operator input, not a scheduling
change. Verify the selected mode's supported route and immutable configuration
requirements before preparing it.

The operating agent should propose the schedule from the job's concerns and
explain its reason in one sentence. Ask for clarification only when uncertainty
would materially change scope, work or outcome. Vertical is a suggested starting
point, not a demonstrated universal optimum or a silent override of an explicit
operator choice.

Explain budgets separately from schedule selection. Distinguish profile-review
passes, consolidated Editor operations, complete review/edit cycles and persisted
round identifiers; do not imply a round number counts cycles or model calls.
Document the selected mode's actual exhaustion and continuation behavior rather
than deriving it from the horizontal/vertical label alone.

Scope-intake guidance placement also confirmed: the operator guide should explain
prompt effects versus structured admission/finding-handling effects, expected
notes headings and inspection of the compiled contract. The agent skill should
reference that shared explanation rather than duplicate a drifting account.


### Remaining operator-refinement inputs: defaults, readiness and handoff

Discussion consolidated 2026-11-22. Enough product direction has been gathered
for a documentation/skill revision; implementation has not begun.

- Budgets: the agent recommends a bounded allowance using the selected preset
  and job complexity, summarizes it and proceeds within existing authority.
  Do not routinely ask the operator to select round counts. The operator prefers
  more iteration and fewer budget check-ins; no numeric larger default has been
  chosen. Ask about conflicts with explicit time/cost limits or extensions beyond
  actual authority. More review budget does not eliminate required semantic or
  product decisions; review allowances are not model-call or spending caps.
- Model selection: explicitly include model and reasoning effort for Reviewer,
  Editor and Verifier where applicable, alongside client choice. Prefer retained
  role-specific defaults and show resolved choices in the staging summary.
  Explain task-driven deviations and verify client support. No models or efforts
  were selected in this discussion. Verify implementation support rather than
  claiming configuration-only changes suffice: the inspected legacy Codex client
  helper currently hard-codes medium reasoning effort; verified role settings
  must be checked separately. Any required code change should be identified as
  such, not hidden in documentation.
- Readiness: validate explicit inputs, scope, protection bindings, supported
  combinations, client/model settings and allowances locally using supported
  checks. Separate local validation from provider execution. Provide a concise
  handoff describing the intended work, permitted edits, limits and unresolved
  requirements. Do not duplicate authorization already supplied within scope.
- Monitoring/handoff: use evidence-backed status explaining the current
  operation, draft/profile/cycle where known, consumed/remaining allowance,
  required operator decision and exact permitted next action. Distinguish
  workflow state from process liveness, and expected pending output from missing
  committed evidence. Keep detailed diagnostics available. These are proposed
  reporting principles, not claims that the original staged job exposed a live
  status defect. Validate any suspected code defect before proposing a fix.
- Completion: distinguish assessment delivery, Phase 1 stability, focused
  stability, residual issues, convergence and source adoption. Reports should
  state actual outcomes and next options without forcing the operator to read
  every artifact.

### Deferred separately: execution approvals and bounded delegation

Repeated nested-client execution approvals during audit/edit/resubmit loops and
more autonomous Phase 1 decision delegation warrant a separate investigation.
The operator explicitly parked this topic to avoid expanding the current surface
refinement. Diagnose actual prompt origin before proposing reusable execution
permission; distinguish host permissions, provider/input authorization, semantic
attestations, task delegation and source writes. No permission settings, reusable
rules, blanket auto-approval, or human-attestation bypass were approved or changed.
For the immediate guide, explain the applicable approval and reuse existing
in-scope authorization rather than adding redundant confirmation.


### Refinement deliverable: ship a portable Whetstone agent skill

Added to the planned operator-surface refinement on 2026-11-22 at the operator's
request. Reuse and refine the existing locally installed `whetstone-runner`
package rather than inventing an unrelated skill. Inspection found no personal
filesystem paths in its main file or supporting references, but its current
preservation routing defaults to the bridge and needs the capability-aware
selection guidance agreed above.

Include the canonical skill, its supporting references and appropriate agent
metadata in the repository, with clear installation/discovery instructions.
Choose the repository location during refinement; do not assume file presence
makes every agent load it automatically. Align examples, scope intake, scheduling,
budget/model defaults, authorization and readiness guidance with the matching
operator documentation and the selected runtime's actual capabilities. Prefer
shared explanations over duplicated, drifting policies.

Keep machine-local installation paths and personal preferences outside the
portable package. Determine how the local installed copy consumes or is updated
from the repository-owned version without creating two independently maintained
sources. Do not overwrite pinned runtime installations or change runtime release
selection merely to distribute documentation and skills. Identify any necessary
runtime changes separately. This records a deliverable for the future refinement;
no skill has yet been copied, modified, installed or published by this discussion.


## Independent Multi-Model Review Experiment

Idea captured 2026-11-22. Future experiment only; no model calls, provider
integration or parallel execution authorized by this note. Distinct from the
selected-lens audit proposal: this tests multiple model perspectives on the same
lens, rather than multiple lenses alone.

Start with two models independently reviewing the same frozen inputs, scope and
lens. Neither receives the other's findings. Use separate retained audit outputs
and explicit provider/input authorization. The operating agent and operator then
compare overlaps, useful unique findings, false positives and disagreements
before editing. Record attributable cost/usage where available and elapsed time;
measure value against a single-reviewer baseline rather than assume diversity
improves outcomes.

Parallel execution and automatic Editor synthesis are possible later extensions,
not prerequisites for the experiment. Preserve source attribution and unresolved
conflicts; reviewer agreement is not proof and the Editor must not silently decide
conflicting product requirements. Evaluate existing supported transports first;
mentioning another provider does not establish an implemented adapter.
