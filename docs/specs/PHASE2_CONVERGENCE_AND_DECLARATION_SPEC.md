# Phase2 Convergence And Declaration Spec

<!--
Whetstone decomposition provenance:
source_spec_path: spec.md
source_spec_hash: adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12
approved_plan_hash: 49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601
target_spec_id: phase2_convergence_and_declaration_spec
target_spec_role: leaf_spec
-->

## PHASE 2 FAILURE HANDLING

Produces:

/rounds/convergence_failure_report.json

Includes:
- final_draft_path
- final_declaration_path: string | null
- target_phase
- target_mode
- workflow
- rubric_profile
- rubric_source
- rubric_label: string | null
- rubric_manifest_path
- unresolved_blockers
- unresolved_major_issues
- unresolved_rubric_gaps
- reviewer_final_status
- last_accepted_draft_hash
- last_draft_hash
- profile_status
- last_reviewer_findings: object | null
- exit_reason
- recommendation:
  - return_to_phase_1
  - continue_convergence
  - lower_target
  - manual_review_required

ACTION:

Orchestrator MUST halt and require external input.

The system does not auto-apply recommendation.

`reviewer_final_status` is a string enum:
- `accepted`
- `rejected`
- `not_run`

`reviewer_final_status = accepted` means declaration verification passed under the convergence declaration criteria.

`reviewer_final_status = rejected` means declaration verification ran and failed at least one convergence declaration acceptance criterion.

`reviewer_final_status = not_run` means Phase 2 halted before a final declaration verification review could run.

`profile_status` MUST explain verification state at halt time. It MUST include:
- `profiles`: ordered profile-step records with `profile`, `rounds_used`, `round_budget`, `clean`, `exhausted`, `residual_status`, and `active`
- `unverified_profiles`: profile names whose latest relevant Reviewer pass has not verified the current draft clean
- `exhausted_profiles`: profile names whose profile-step budget was consumed without a clean verification result
- `profiles_remaining`: profile names with unconsumed profile-step budget
- `total_round_budget`: sum of profile-step `round_budget` values for the phase

`residual_status` MUST be null when the profile has no residual condition. In Phase 1 soft budget mode, it MUST be `exhausted_with_residuals` or `halted_oscillation` when the Orchestrator advances past a non-clean profile for diagnostic sweep coverage.

`last_reviewer_findings` MUST summarize the last accepted Reviewer batch when available. It MUST include `round_number`, `profile`, `blocker_count`, `major_count`, and `feedback_ids` for in-scope blocker/major feedback. This field exists so a failure report can distinguish unresolved Editor issues from missing Reviewer verification.

---

## TARGET MATRIX PRECEDENCE

At convergence evaluation:

target matrix overrides issue policy.

mid/permissive:
- blockers forbidden
- major issues allowed if documented

mid/strict:
- blockers forbidden
- major issues forbidden
- minor allowed if documented

final/permissive:
- blockers forbidden
- major forbidden
- rubric gaps allowed if accepted

final/strict:
- no blockers
- no major issues
- no unresolved rubric gaps
- declaration required and accepted

The target matrix controls convergence evaluation only. It does not weaken the accepted draft requirement for entering Phase 2.

For permissive targets, this creates an intentional asymmetry: major issues cannot survive from Phase 1 into Phase 2, but documented major issues may be introduced or discovered during Phase 2 and still be allowed when the target matrix permits them.

---

## CONVERGENCE DECLARATION

`convergence_declaration.md` MUST exist before `CONVERGED`.

The convergence declaration is a separate Orchestrator-owned artifact. Editors MUST NOT satisfy declaration requirements by adding declaration text, acceptance statements, or declaration metadata to `spec.md` unless that text is explicitly part of the source spec domain itself.

Minimum declaration content:
- target_phase
- target_mode
- workflow
- rubric_profile
- rubric_source
- rubric_label: string | null
- rubric_manifest_path
- final_draft_hash
- rubric_content_hash
- unresolved_blockers count
- unresolved_major_issues count
- unresolved_rubric_gaps count
- reviewer_final_status
- declaration_status: accepted | rejected

The declaration is verified by a Phase 2 `convergence_strict_check` review whose review scope includes `convergence_declaration.md`, the current draft, the current rubric hash, the target matrix, `unresolved_issues.json`, and `rubric_gaps.json`.

Declaration-scoped issues are issues whose `affected_sections` explicitly contains `convergence_declaration.md`.

Target-matrix issues are issues whose `rubric_impact` is non-null or whose `affected_sections` contains `target-matrix-precedence`, `rubric_gaps.json`, or `unresolved_issues.json`.

The declaration is accepted only when all of the following are true:
- `convergence_declaration.md` exists
- `final_draft_hash` equals the current `draft_hash`
- `rubric_content_hash` equals the current `rubric_content_hash`
- declaration rubric identity equals the current `rubric_manifest.json`
- declaration counts equal the counts derived from `unresolved_issues.json` and `rubric_gaps.json`
- target matrix requirements are satisfied
- `convergence_strict_check` returns zero in-scope blocker declaration-scoped issues
- `convergence_strict_check` returns zero in-scope major declaration-scoped issues
- `convergence_strict_check` returns zero in-scope blocker target-matrix issues
- `convergence_strict_check` returns zero in-scope major target-matrix issues
- final/strict targets have zero unresolved blocking rubric gaps

If all declaration acceptance criteria pass, `declaration_status = accepted` and `reviewer_final_status = accepted`.

If any declaration acceptance criterion fails after the verification review runs, `declaration_status = rejected` and `reviewer_final_status = rejected`.

If Phase 2 halts before declaration verification runs, `declaration_status = rejected` when a declaration exists and `reviewer_final_status = not_run`.

`conditional` is not a terminal declaration status. Conditional convergence concerns MUST be represented as rejected declaration status plus documented unresolved issues, rubric gaps, or recommendations in the relevant failure report.

---

## REPRODUCIBILITY

prompt_snapshot.json MUST include:
- prompt text
- profile
- client
- version
- model
- timestamp
- config snapshot
- workflow
- rubric profile
- rubric source
- rubric content hash
- rubric manifest path in Phase 2
- scope contract path/hash/status when present
- reference context labels/roles/paths/hashes when present
- draft_hash
- semantic_change_hash when a draft mutation is requested
- context_files manifest when file-backed context is used

`prompt_snapshot.json` is the round-level convenience snapshot. It MAY be updated as the round advances from reviewer prompt to editor prompt.

`prompt_snapshots/{client_role}-{artifact_name}-attempt-{attempt_number}.json` is the attempt-level audit trail. It MUST be append-only within a round, MUST NOT overwrite prior attempts, and MUST include:
- prompt text sent for that attempt
- profile
- phase
- client role
- client name, version, and model
- artifact name
- attempt number
- timestamp
- config snapshot
- workflow
- rubric profile
- rubric source
- rubric manifest path in Phase 2
- scope contract path/hash/status when present
- reference context labels/roles/paths/hashes when present
- context_files manifest when file-backed context is used
- validation errors that caused the attempt, or an empty list for the first attempt

Live client prompts MAY use file-backed context for large authoritative inputs. File-backed context MUST be written under `rounds/round-N/context/`, and prompt text MUST reference those files by path instead of duplicating the full content. This mechanism is intended for bulky round inputs such as the draft, rubric, convergence declaration, reviewer feedback, scope contract, and reference context files.

When an approved scope contract is present, it MUST be supplied as file-backed context to Reviewer and Editor prompts. Prompt snapshots MUST include the scope contract context-file hash and a top-level `scope_contract_hash` or equivalent scope-contract summary.

When reference context files are configured and available, the Orchestrator MUST copy each available file into `rounds/round-N/context/`, label it as `reference:<label>` in the context manifest, and include its configured role in prompt text and prompt snapshots. A reference context file's copied round context content and SHA-256 hash are the replay authority for that attempt.

When file-backed context is used:
- the Orchestrator MUST persist each context file before the client attempt begins
- the prompt MUST list only the context files the client is allowed to read
- the prompt MUST explicitly allow the client to read the listed context files
- each prompt snapshot MUST include a `context_files` manifest with `label`, `path`, and exact SHA256 of the context file content
- context file paths SHOULD be workspace-relative when possible
- context files referenced by an attempt snapshot MUST NOT be mutated after that snapshot is persisted
- retry attempts MAY reuse the same context files when the authoritative inputs have not changed
- deterministic replay uses the prompt text plus the referenced context file contents and hashes

Clients MUST treat file-backed context as equivalent to inline prompt context. They MAY use read-only client-native file access or read-only shell commands solely to read the listed context file paths. They MUST NOT inspect unrelated repository files, use web search, or call tools for anything except reading listed context files.

`client_telemetry/{client_role}-{artifact_name}-attempt-{attempt_number}.json` is the attempt-level client runtime telemetry artifact. It MUST be keyed to the same `client_role`, `artifact_name`, and `attempt_number` as the corresponding prompt snapshot when both exist. It MAY reference raw client envelopes or stderr/stdout captures but MUST NOT replace prompt snapshots or canonical reviewer/editor artifacts.

Phase 2 reviewer prompt snapshots MUST include the full oscillation classification table shown to the reviewer.

reviewer_working_notes.md is part of the audit trail and MUST be persisted, but it is not required for deterministic replay.

---
