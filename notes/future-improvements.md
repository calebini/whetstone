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
