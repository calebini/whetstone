# Preservation runtime checkpoint

This checkpoint connects the two-stage bridge to ordinary and focused horizontal Phase 1 rounds. It is a deterministic developer integration checkpoint within step 4 of slice 18.1. Public `preservation_bridge` configuration remains unavailable until the remaining runtime paths and full qualification pass. There is no new activation flag, and this document does not authorize a live model run.

## Implemented behavior

The runtime adapter initializes a fresh isolated root, checks that its runtime scope matches the approved surface's scope, and records its enforced identity. It refuses legacy conversion, downgrade and overwrite. Fixtures construct `PreservationBridgeConfig` programmatically; production config loading continues to reject the reserved capability.

Before calling the Editor, a round freezes the actual configuration, scheduler context, Editor prompt, resolved timeout and exact Reviewer evidence. The adapter captures the raw Editor body without canonicalizing it or retrying malformed output. Supplied revisions are retained before their summary call, under the same writer exclusion. Trusted materialization and preliminary assessment use the existing proposal service.

A pending proposal produces `PAUSED_DECISION`; a known failure halts. Neither creates authoritative `draft_after.md`, an accepted Editor summary, accepted history, or a changed `spec.md`. Soft budgets and end-of-cycle decision presentation do not override this hold. Unchanged eligible output commits through the same acceptance service, with no Editor invocation for an empty Reviewer result.

The existing local review, effect-adoption, request and acceptance commands select the runtime adapter for a retained developer runtime root. Approval validates the frozen ordinary serious-issue and decision gates as well as preservation. It stops after committing or repairing that operation. It never invokes the next Reviewer/Editor, refreshes resolution claims, or charges another review round. A completion record retains the original Reviewer counts separately from unresolved issues; effect approval cannot turn a serious Reviewer result into a clean profile.

Marker recovery verifies and repairs canonical drafts, summaries, Reviewer evidence, decision output, history, run-state acceptance pointers and completion accounting. Another admission and downstream consumers remain blocked until repair finishes. Conflicting scheduler state is refused rather than overwritten. Replaying acceptance does not duplicate history or round accounting.

## Readback, retry and consumers

`read_status` and run state expose `preservation_bridge`, including the mode, capability version, latest proposal/report, pending acceptance admission, accepted marker, pending outcome and next action. Legacy roots are explicitly `legacy_unguarded`. Readback validates retained evidence and performs no repair. Removing a runtime marker cannot downgrade a run whose state still declares enforcement.

A typed Phase 1 Editor or supplied-summary timeout can retry only the same operation. It retains the original prompt, exact supplied bytes, Reviewer inputs, scope/surface, effective settings and timeout. The new proposal attempt links the prior report; no Reviewer is replayed, and the numbered round is unchanged. Altered input hashes and deterministic preservation failures cannot enter this retry path. `continue_run=True` is refused at this checkpoint.

Phase 2 entry, direct version promotion and declaration creation check preservation authority before consumption. Phase 2 entry remains unavailable because its dedicated maintenance admission is not yet integrated. Pending, rejected, corrupt or incompletely repaired output cannot pass dry or live strop even with non-convergence/source-hash overrides. Guarded dry strop creates no files; its returned review paths are prospective locations. Live strop retains writer exclusion and the existing external-source hash check.

## Qualification and remaining work

Run the scripted checks without live clients:

```sh
PYTHONPATH=src:tests python3 -m unittest test_preservation_runtime test_preservation_clients -q
PYTHONPATH=src:tests python3 -m unittest discover -s tests -q
```

Validation at this checkpoint: **419 tests pass**, including **120 preservation tests** (30 new runtime/client/configuration tests). No live model calls.

The new tests cover pending-to-local-acceptance, malformed raw bodies, frozen contract loss with `apply=True`, supplied revisions, focused runs, a complete three-profile unchanged Phase 1 run, typed timeout retry, altered retry inputs/configuration, stale scheduler state, interrupted scheduler repair, downgrade, and read-only downstream guards.

Step 4 remains open for vertical consolidated editing and its source-review topology, Reviewer timeout continuation, reviewer-only closeout/verification, scheduler continuation after local acceptance, Phase 2's dedicated maintenance/inherited-authorization path, and full cross-path qualification. These paths fail explicitly rather than falling back to unguarded execution. Do not enable `PRESERVATION_BRIDGE_QUALIFIED` until those paths and the complete acceptance criteria in the implementation plan have evidence.
