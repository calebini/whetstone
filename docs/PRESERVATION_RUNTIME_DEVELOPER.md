# Preservation runtime and continuation checkpoints

This checkpoint connects the two-stage bridge to ordinary and focused horizontal Phase 1 rounds, scheduler continuation and Reviewer-only verification, plus the first vertical review/consolidation cycle. It is a deterministic developer integration checkpoint within step 4 of slice 18.1. Public `preservation_bridge` configuration remains unavailable until the remaining runtime paths and full qualification pass. There is no new activation flag, and this document does not authorize a live model run.

## Implemented behavior

The runtime adapter initializes a fresh isolated root, checks that its runtime scope matches the approved surface's scope, and records its enforced identity. It refuses legacy conversion, downgrade and overwrite. Fixtures construct `PreservationBridgeConfig` programmatically; production config loading continues to reject the reserved capability.

Before calling the Editor, a round freezes the actual configuration, scheduler context, Editor prompt, resolved timeout and exact Reviewer evidence. The adapter captures the raw Editor body without canonicalizing it or retrying malformed output. Supplied revisions are retained before their summary call, under the same writer exclusion. Trusted materialization and preliminary assessment use the existing proposal service.

A pending proposal produces `PAUSED_DECISION`; a known failure halts. Neither creates authoritative `draft_after.md`, an accepted Editor summary, accepted history, or a changed `spec.md`. Soft budgets and end-of-cycle decision presentation do not override this hold. Unchanged eligible output commits through the same acceptance service, with no Editor invocation for an empty Reviewer result.

The existing local review, effect-adoption, request and acceptance commands select the runtime adapter for a retained developer runtime root. Approval validates the frozen ordinary serious-issue and decision gates as well as preservation. It stops after committing or repairing that operation. It never invokes the next Reviewer/Editor, refreshes resolution claims, or charges another review round. A completion record retains the original Reviewer counts separately from unresolved issues; effect approval cannot turn a serious Reviewer result into a clean profile.

Marker recovery verifies and repairs canonical drafts, summaries, Reviewer evidence, decision output, history, run-state acceptance pointers and completion accounting. Another admission and downstream consumers remain blocked until repair finishes. Conflicting scheduler state is refused rather than overwritten. Replaying acceptance does not duplicate history or round accounting.

## Readback, retry and consumers

`read_status` and run state expose `preservation_bridge`, including the mode, capability version, latest proposal/report, pending acceptance admission, accepted marker, pending outcome and next action. Legacy roots are explicitly `legacy_unguarded`. Readback validates retained evidence and performs no repair. Removing a runtime marker cannot downgrade a run whose state still declares enforcement.

A typed Phase 1 Editor or supplied-summary timeout can retry only the same operation. It retains the original prompt, exact supplied bytes, Reviewer inputs, scope/surface, effective settings and timeout. The new proposal attempt links the prior report; no Reviewer is replayed, and the numbered round is unchanged. Altered input hashes and deterministic preservation failures cannot enter this retry path. `continue_run=True` can continue the original horizontal/focused Phase 1 scheduler after that operation succeeds; pending or rejected preservation work still stops locally.

Reviewer execution now retains immutable `reviewer-attempt-N/{input.json,base.md,prompt.txt,config.json,result.json}` records, plus validated feedback when complete. In horizontal/focused runs, a typed Reviewer timeout retries the same numbered round, links the preceding timeout result, and preserves exact inputs, scope, settings and timeout. Deterministic Reviewer failures require inspection. If valid feedback was retained before a canonical write failed, recovery reuses that feedback without another Reviewer call. A changed input or conflicting canonical artifact blocks recovery.

After local acceptance, `resume --dry-run --continue` reconstructs the original horizontal/focused scheduler from immutable acceptance evidence and completed review receipts. `resume --continue` executes that plan. Acceptance itself remains local and does not invoke another model. Each new editing round requires an approved surface bound to the current accepted base; the runtime does not generate or refresh that approval. A review-only closeout can observe the accepted bytes without new edit authorization. Focused completion remains `FOCUSED_PROFILE_STABLE` and does not advertise Phase 2 readiness.

Reviewer-only closeout records exact input/output hashes, a compatibility no-op summary and an immutable `review_complete.json` receipt. It creates no new acceptance marker, accepted-history entry or Editor call. Serious findings prevent stability. Recovery validates each receipt's acceptance parent and deterministic outputs, keeps earlier closeout findings, and resumes only profiles that have not already completed their closeout. Completed continuation is read-only and does not charge another round. Budget/settings changes and unsolicited review-only rounds are refused; guarded budget extensions remain unavailable. Status and dry-run resume validate scheduler evidence before reporting readiness or resumability.

Phase 2 entry, direct version promotion and declaration creation check preservation authority before consumption. Phase 2 entry remains unavailable because its dedicated maintenance admission is not yet integrated. Pending, rejected, corrupt or incompletely repaired output cannot pass dry or live strop even with non-convergence/source-hash overrides. Guarded dry strop creates no files; its returned review paths are prospective locations. Live strop retains writer exclusion and the existing external-source hash check.

## First vertical cycle

The existing vertical scheduler can now collect its initial profile sweep in a fresh developer guarded root. Each source review has an immutable `vertical_source` input and completion receipt, observes the same admitted seed, and creates no acceptance or accepted-history entry. Original profile names, round numbers, findings and hashes remain intact.

Before consolidated Editor execution, the adapter validates every source receipt and recomputes the merged feedback with the scheduler's existing profile-prefixed identifiers. The proposal retains the merged Reviewer artifact first, followed by all original source artifacts; the frozen configuration binds their ordered `vertical_review_sources` receipt Refs. Admission, materialization and acceptance validate this topology. Ordinary issue checks consume the verified merge once, retaining unrelated serious findings without counting the source copies twice. The first consolidated round follows the source rounds, without consuming another profile-review call.

The consolidated output follows the same proposal/pending/local-acceptance path. It cannot create authoritative `draft_after.md`, history or changed `spec.md` before acceptance. Local acceptance and mirror repair invoke no further Reviewer or Editor. A typed consolidated Editor timeout can retry with the same source evidence, prompt, authorization and settings; the source reviews are never replayed. Altered sources or merged feedback block admission/acceptance and downstream consumption.

An all-empty initial sweep commits the unchanged seed through normal no-op admission before reporting Phase 1 stability; it creates one acceptance marker and invokes no Editor. Repeating completion is read-only. Other accepted first-cycle operations stop without claiming verification after an edit. Later vertical cycles, vertical Reviewer recovery and vertical closeout/replay remain explicitly unavailable in this checkpoint. Use the horizontal/focused path for already-qualified continuation; do not change an existing guarded run's mode to bypass this boundary.

## Qualification and remaining work

Run the scripted checks without live clients:

```sh
PYTHONPATH=src:tests python3 -m unittest test_preservation_runtime test_preservation_clients test_preservation_continuation test_preservation_vertical -q
PYTHONPATH=src:tests python3 -m unittest discover -s tests -q
```

Validation at this checkpoint: **453 full-suite tests passed**, followed by a passing exact-byte regression (454 tests total, including 155 preservation tests and 15 new vertical tests). No live model calls.

The new tests cover pending-to-local-acceptance, malformed raw bodies, frozen contract loss with `apply=True`, supplied revisions, focused runs, a complete three-profile unchanged Phase 1 run, typed timeout retry, altered retry inputs/configuration, stale scheduler state, interrupted scheduler repair, downgrade, and read-only downstream guards.

The continuation regressions also cover local acceptance followed by fresh profile verification, clean and serious focused closeout, soft-budget verification, typed Reviewer retry, retained-feedback and receipt-write recovery, changed timeouts/settings/evidence, false readiness claims, the actual CLI dry-run command, hard oscillation refusal and repeated completion without duplicate calls or accounting.

Retained local toy evidence: `rounds/preservation-continuation-checkpoint-002/RESULTS.md` and `results.json` record focused clean verification and interrupted multi-profile closeout with a retained serious finding. Run artifacts are ignored; the tracked tests reproduce both journeys.

Retained vertical toy evidence: `rounds/preservation-vertical-checkpoint-001/RESULTS.md` and `results.json` record local acceptance of a clarification, rejection of frozen schema loss, and accepted no-op completion of an empty sweep.

The vertical tests cover exact CRLF byte preservation, the first sweep, source/merge binding, pending-to-local-acceptance, frozen schema loss, unrelated serious findings, source-write faults, source corruption, exact Editor retry, marker-backed empty-sweep stability and idempotent acceptance repair.

Step 4 remains open for later vertical cycles, vertical Reviewer recovery and closeout/replay, Phase 2's dedicated maintenance/inherited-authorization path, and full cross-path qualification. These paths fail explicitly rather than falling back to unguarded execution. Do not enable `PRESERVATION_BRIDGE_QUALIFIED` until those paths and the complete acceptance criteria in the implementation plan have evidence.
