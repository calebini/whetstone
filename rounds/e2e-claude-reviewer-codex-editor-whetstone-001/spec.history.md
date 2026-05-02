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
