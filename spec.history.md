# Spec History

## 2026-04-30

- Created bare-minimum seed scaffold using the Cortext component scaffold's as-needed buildout rule.
- Persisted `AI SPEC CONVERGENCE ORCHESTRATOR (v5 - FINAL STRICT CANDIDATE)` as `spec.md`.
- Revised the spec to `0.06 - STRICT CANDIDATE`.
- Added computable issue/conflict identity, minimum artifact schemas, exact hashing normalization, round scheduling rules, deterministic oscillation recommendation selection, convergence declaration requirements, conflict severity, and target/accepted-draft clarifications.
- Tightened the `0.06` draft with lexicographic conflict fingerprint ordering, one-issue-per-feedback constraints, conditional severity rationale, modified-feedback semantics, nullable failure declaration path, order-insensitive marker rendering note, nit/all-null oscillation handling, and permissive-target Phase 2 asymmetry.
- Added a contract-first implementation plan and initial JSON Schema contracts for required orchestrator artifacts.
- Added the first fixture-mode implementation primitives: schema validation, draft/semantic hashing, identity/severity helpers, artifact store, core evaluators, and regression tests.
- Added config loading, fixture-mode round execution, CLI entry point, terminal report generation, convergence declaration rendering, scheduler primitives, and expanded regression coverage.
- Added the multi-round fixture engine, process client boundary, prompt rendering, and a clean-convergence golden fixture script.
- Added the Codex `exec` reviewer adapter, schema-constrained `codex-review` CLI command, and tests using a fake Codex executable.
- Expanded the implementation plan to explicitly track remaining live-client, cross-round memory, declaration workflow, halt automation, schema completion, CLI, and golden-fixture work.
- Revised oscillation detection to use Phase 2 mandatory structured feedback classification with canonical `oscillation_key` fields, opposition keys, and draft-level detection limited to mechanical churn/cycles.
- Clarified Phase 1 oscillation halt scope, Phase 2 churn counting, symmetric direction opposition, Phase 2 history reset, churn escalation semantics, scope-classification limitations, and the relationship between issue identity and oscillation concern identity.
- Bumped the strict candidate version to `0.07` after the structured Phase 2 oscillation redesign.
- Renamed the mutation-owner role and all related artifacts/code references to `Editor`, including `editor_summary.json` and `editor_summary.schema.json`.
- Updated the spec title to use the Whetstone name and clarified Phase 2 prompt requirements, section anchor semantics, declaration status, recommendation wording, and identity-system operator expectations.
- Reworked the implementation plan into a traceable checklist with live-test gates, acceptance criteria, `0.07` oscillation work items, role-assignment tasks, identity-system notes, and fixture coverage targets.
- Updated implementation contracts, prompt rendering, evaluator recommendations, and tests for the `0.07` Phase 2 `oscillation_key` model.
- Added Phase 2 reviewer schema selection to the Codex reviewer path so live smoke tests can exercise the forward-looking feedback contract.
- Added Orchestrator-owned oscillation key canonicalization: reviewers propose semantic classification, Whetstone validates canonical section IDs and computes `fingerprint` plus `opposition_key`.
- Tightened Phase 2 reviewer schemas with explicit top-level object types for live structured-output compatibility.
- Added a flat Codex-compatible Phase 2 reviewer input schema for live structured-output calls while preserving richer local artifact validation.
- Fixed live-review blocker findings by defining polarity-neutral mechanical churn keys, rubric content hashing, rubric gap identity and persistence, and clearer Phase 2 reviewer-input versus persisted feedback schemas.
- Bumped the strict candidate version to `0.08` to mark the post-live-smoke-test canonicalization, structured-output compatibility, mechanical churn, and rubric gap changes.
- Marked the Codex reviewer smoke-test gate complete after persisting validated live output under `rounds/live-codex-reviewer-smoke/`.
- Added non-mutating editor smoke support with Codex and Claude Code editor adapters, bounded subprocess timeouts, and Codex-compatible editor structured-output schema.
- Added Claude Code reviewer smoke support, including result-field JSON unwrapping, deterministic severity alias canonicalization, and a validated Phase 2 live smoke artifact under `rounds/live-claude-reviewer-smoke/`.
- Ran an observation-only Claude Code Phase 2 reviewer pass against `spec.md` and folded useful findings into `0.09`: computable declaration acceptance criteria, `reviewer_final_status` enum semantics, deterministic Phase 2 scheduling/exhaustion rules, minimum `conflict_report.json` fields, and definitions for `in_scope` plus `blocking_acceptance`.
- Ran Claude Code through full Phase 2 reviewer canonicalization against `0.09` and folded all useful findings into `0.10`: computable `blocking_convergence`, aligned declaration/reviewer-final-status scope rules, final/strict Phase 2 profile coverage, feedback-churn reset semantics, config preflight validation, and conditional non-null deferred-decline fields.
- Completed Gate 3 live single-round plumbing with config-driven reviewer/editor client factories, guarded `live-round` CLI execution, pre-invocation prompt snapshots, reviewer/editor hash validation, capture-only `draft_after.md` persistence, config preflight errors, and full round packet output.
- Hardened the editor prompt after a live Claude editor schema miss, then completed a real Codex reviewer -> Claude Code editor tiny-spec E2E round with validated reviewer feedback, editor summary, unresolved issues, and no spec mutation.
- Ran a Phase 1 Claude Code reviewer -> Codex editor E2E smoke against the full Whetstone spec and folded the useful structural findings into `0.11`: artifact validation retry/halt policy, `HALTED_ARTIFACT_INVALID`, computable profile focus anchors, complete Phase 1 stable-state guard, `CONFIG_INVALID` halt matrix coverage, canonical array serialization for fingerprints, conflict creation authority, unique-by-profile Phase 2 coverage semantics, and computable convergence revision routing.
- Brought the `0.11` runtime forward by adding one-retry live artifact validation, diagnostic invalid-attempt persistence, `HALTED_ARTIFACT_INVALID` report emission with phase companion reports, schema-validated config errors, and suffix-resolved scheduler focus anchors for clean-profile invalidation.
- Updated the implementation plan with an explicit Gate 3.5 for a minimal live Phase 1 multi-round runner, separating Phase 1 stabilization from the later full Gate 4 cross-round memory and convergence workflow.
- Revised the spec to `0.12` to support editor-generated applied revisions via `draft_after_content`, allowing live rounds to verify editor-produced draft hashes, persist `draft_after.md`, and mutate `spec.md` only after validation.
- Completed Gate 3.5 minimal live Phase 1 runner with `live-phase1`, non-resumable `run_state.json`, scheduler-driven profile progression, blocker repeats, safe editor-generated draft application, history entries, max-round failure, artifact-validation halt propagation, and draft-hash cycle halt coverage.
- Ran a real Claude reviewer -> Codex editor toy-spec `live-phase1` smoke that reached `PHASE_1_STABLE` after 3 rounds, and hardened the prompt/schema boundary for Phase 1 `oscillation_key`, Codex strict `draft_after_content`, client-side validation retries, and overwrite cleanup of stale round artifacts.

- Revised the spec to `0.13` and tightened the editor-generated draft contract: Editors provide complete revised draft text, while Whetstone computes and injects `draft_after_hash` before persisted validation and mutation.

- Revised the spec to `0.14` and tightened the reviewer-generated feedback contract: Reviewers provide semantic issue fields, while Whetstone computes `issue_fingerprint`, `issue_id`, and `normalized_severity` before persisted validation.

- Revised the spec to `0.15` with a Decision Point Register release valve, including per-round decision capture, end-of-cycle aggregation, intervention mode, `PAUSED_DECISION`, and decision intervention artifacts.

- Revised the spec to `0.16` with hardened artifact-failure semantics: `technical_failure_report.json` is listed as a primary output, validation halts now record `last_valid_draft_path`, and retry prompts are persisted in attempt-level `prompt_snapshots/` without overwriting the round-level convenience snapshot.

- Revised the spec to `0.17` with a Phase 2 maturity-promotion rule: fractional Phase 1 versions remain stabilization drafts, and the Orchestrator promotes an accepted Phase 1 draft to the next whole major version before the first convergence review.
- Revised the spec to `0.18` with Orchestrator-owned version stamping for accepted mutating rounds, making version labels a human-readable rollback/navigation aid while preserving draft hashes as replay authority.
- Revised the spec to `0.19` with deterministic decision-summary artifacts that cluster decision points by document topology, round/profile, and trigger type, while keeping optional AI interpretation explicitly non-authoritative.
- Revised the spec to `0.20` with per-attempt client telemetry artifacts for live invocations, preserving client-native usage, cost, duration, session, and raw-envelope references when available.
- Revised the spec to `0.21` with canonical rubric profiles and explicit workflows, requiring Phase 2 runs to persist rubric identity, source, hash, target, and workflow in a manifest before convergence review begins.
- Revised the spec to `0.24` with profile-level round budgets and explanatory failure reports that distinguish unresolved Editor issues from missing Reviewer verification.
- Raised default profile-level round budgets to `10` per profile to support observation of natural stabilization behavior during live Foreman-spec evaluation.
- Revised the spec to `0.25` with explicit `HALTED_CLIENT_TIMEOUT` terminal semantics and role-specific Reviewer/Editor timeout configuration.
- Revised the spec to `0.26` with a narrow hash-guarded resume path for Phase 1 Editor timeouts that reuses validated Reviewer feedback and preserves prior timeout diagnostics.
- Revised the spec to `0.27` with `resume --continue`, allowing recovered Phase 1 Editor-timeout runs to continue through the remaining Phase 1 schedule without replaying completed rounds.
- Revised the spec to `0.28` with `resume --dry-run` planning and status guidance that reports exact resume commands for eligible Phase 1 Editor timeout halts.
- Revised the spec to `0.29` with file-backed live prompt context, requiring round-local context files, prompt/path references, and hashed context manifests in prompt snapshots.
- Revised the spec to `0.30` with file-backed context hardening: prompts explicitly allow listed-file reads, destructive Editor draft replacements are rejected, run state exposes resolved profile budgets, and terminal decision registers are always written.
- Revised the spec to `0.31` with resume timeout inheritance, preserving halted run timeout settings from `run_state.json` unless explicit resume CLI overrides are supplied.
- Revised the spec to `0.32` with `effective_run_config` persistence in `run_state.json`, requiring resume to inherit effective profile budgets, decision-point configuration, and timeouts while preserving explicit resume CLI overrides as highest precedence.
- Revised the spec to `0.33` with `EXPANDING_CONTRACT_SURFACE` detection, a persisted synthesis recommendation artifact, and timeout-aware bounded synthesis guidance in Editor prompts when a matching contract surface report exists.
- Revised the spec to `0.34` with opt-in soft Phase 1 budget sweeps, per-profile residual status, `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`, and explicit Phase 2 blocking when residual review profiles remain.
- Revised the spec to `0.35` with first-contact scope contracts, MVP scope-contract preflight, scope-contract prompt injection, and intake template/from-notes CLI support.
- Revised the spec to `0.36` with explicit expanding-contract-surface terminal semantics, next-round context-injection reporting, and a clear distinction between synthesis recommendations and executed synthesis passes.
- Revised the spec to `0.37` with generated-draft text hygiene validation, `whetstone strop` as the preferred apply-back command alias, and effective profile-budget reporting in rubric manifests.
- Revised the spec to `0.38` with explicit decision-point status semantics, separating editor-applied choices, operator review recommendations, intervention-required decisions, and record-only hardening without changing default run-completion behavior.
- Revised the spec to `0.39` with Phase 1 clean/budget precedence, scope-contract deferred-surface escalation labeling, and expanding-contract-surface lifecycle statuses.
- Revised the spec to `0.40` with clearer Phase 1 technical failure report semantics: `current_draft_status` and `ready_for_phase_2` now distinguish accepted-but-unverified drafts from truly Phase 1-stable drafts.
- Revised the spec to `0.41` with reviewer process/context-loading failure handling: self-reported inability to perform review is now a retryable artifact-validation failure rather than semantic profile feedback.
- Revised the spec to `0.42` with focused Phase 1 profile runs, allowing targeted single-profile rechecks to write normal run state, decision, telemetry, and terminal artifacts without claiming full Phase 1 stability.
- Revised the spec to `0.43` with first-class reference context files, allowing HLDs and other architectural/domain authority documents to be injected into live Reviewer and Editor prompts as hash-tracked, read-only file-backed context.
- Revised the spec to `0.44` with Orchestrator-owned no-op Editor summaries for clean Reviewer passes, preventing unnecessary Editor calls when there is no feedback to apply.
- Revised the spec to `0.45` with Phase 2 stale declaration binding repair, requiring the Orchestrator to regenerate mismatched candidate declarations before treating declaration hash mismatches as unresolved feedback churn.
- Revised the spec to `0.46` with Phase 1 vertical review mode, preserving independent profile review artifacts while merging profile feedback into one consolidated Editor revision per cycle.
- Revised the spec to `0.57` with nonblocking per-round operator decision checkpoint artifacts that frame likely owner-level choices while leaving scheduler behavior unchanged.
- Revised the spec to `0.58` with terminal operator decision checkpoint summaries that cluster checkpoint candidates by trigger reason, section, and source type.
- Revised the spec to `0.59` with canonical review profile sets, allowing stateful, balanced MVP, utility MVP, and governance runs to select different profile stacks and default budgets without changing the active rubric.
- Revised the spec to `0.60` with Phase 2 reviewer-only closeout verification for profiles whose clean result became stale after a late accepted draft mutation.
- Revised the spec to `0.61` with a generic spec decomposition workflow for overloaded source specs, including authority topology, lossless extraction phases, decomposition artifacts, coverage invariants, and promotion rules.
- Revised the spec to `0.62` with extractable-unit decomposition semantics, treating leaf sections and meaningful parent intro blocks as assignable units while rejecting direct container-section assignment.
- Revised the spec to `0.63` with hash-bound operator approval for decomposition plans, source-hash verification before extraction, and decomposition section IDs that remain stable across source spec title/version changes.
- Revised the spec to `0.64` with decomposition trigger-threshold rationale, framing configurable defaults as conservative seed values that must be documented and refined from observed runs.
- Revised the spec to `0.65` with lossless copy-first decomposition extraction, target provenance headers, target-path containment checks, overwrite guards, and manifest persistence.
