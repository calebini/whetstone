# Verified Phase 2 declaration and closeout

Started 2026-09-25 from local checkpoint `7fc003f`. This milestone adds an internal,
separately pinned route from current verified authority through declaration review
to immutable clean closeout. A subsequent local checkpoint was authorized after
validation on 2026-09-25. Public activation, push, live provider calls and external
specification writes remain excluded.

## Supported journey

The existing standard horizontal final/strict configuration remains authoritative.
The first strict step and adversarial step use their existing requests and budgets.
Before the final configured strict step, the operator calls
`prepare_phase2_declaration()`. This fenced operation reproduces current-pointer
findings and publishes immutable declaration, rubric identity, unresolved-issue and
rubric-gap artifacts followed by a binding commit. It consumes no review credit.

`bind_phase2_next_review(transport)` then binds those exact files into the final
scheduled request, using the new v3 schema. Its prompt includes the current draft,
rubric/hash, target matrix, issue/gap files, declaration and declaration-scoped
classification IDs. Existing `continue_phase2_pass(N, action='execute'|'consume')`
operations run the journal and account for exactly one ordinary profile-step pass.
The final review grants no Editor or candidate permission.

`phase2_closeout()` replays the evidence without a lock or writes. A prospective
CONVERGED packet is not a committed terminal. `finish_phase2()` publishes the final
accepted declaration and terminal report, then a distinct immutable closeout commit.
`reconcile_phase2_state()` separately restores the root declaration and namespaced
`vnext_phase2_closeout` state reference under D8 and ends after recovery. It preserves
legacy state fields. `phase_complete` requires accepted committed evidence and both
derived projections; neither cached state nor the root declaration grants authority.

The root declaration is a create-only projection using the existing immutable
publication API. Existing different bytes are preserved and cause refusal. Exact
reentry repeats durability barriers. The frozen storage materialization whitelist
is unchanged; only the already supported run-state path uses replacement.

## Maintenance and limits

Declaration preparation is also available before an eligible earlier later-pass
request. After a supported V correction and promotion, preparing the next package
binds the new pointer and exact draft hash; old packages remain immutable. The
integration test follows this through adversarial verification and final strict
review. This is explicit maintenance at the supported API boundary, not a complete
automatic maintenance loop after every Phase 2 cycle.

That journey exposed and corrected a sequence replay defect: a proven promotion
must be consumed at its candidate's source round, not at an earlier clean review
that happened to share the same base. Replay still requires that source round's
committed advice and exact predecessor pointer; earlier unresolved gates cannot be
bypassed. The original continuation corpus is rechecked with this correction.

The package's `vnext-bound-rubric-v1` identity is derived exactly from the committed
configuration and rubric artifact under the new algorithm. It is not the legacy
full rubric manifest schema. Declarations retain the compatibility normalized draft
hash and additionally bind the exact SHA-256 and verified pointer path/hash.

Current evidence comes from the latest consumed review per distinct profile on the
same verified pointer. Serious global debt prevents final-review binding. Unsupported
rubric-gap signals anywhere in the retained prefix refuse preparation instead of
being presented as resolved gaps after a later review or promotion.
All required distinct profiles must be clean on the current lineage for acceptance.

Any feedback from the final review currently stops at
`declaration_reconciliation_required`, including minor feedback whose reconciliation
is not implemented. This is an incomplete capability, not a stricter product target
or a TARGET_NOT_REACHED terminal. Remaining budget is preserved. A later owner must
route declaration-only repair, source correction and nonblocking residual findings
under the existing specification. No automatic repair, extra pass or schedule loop
is granted here.

The [scheduler](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md) and
[convergence declaration](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md) specifications
require declaration verification and current-lineage profile coverage. This route
uses the existing final scheduled step; it does not invent an additional review
after a completed sequence. Older suites keep their original behavior and refuse
these APIs. Roots whose sequence already ended without declaration-aware evidence
are not retroactively converged or upgraded.

## Validation and handoff

**110 distinct tests pass.** Seven new focused methods cover clean closeout,
fresh-process reopening, declaration regeneration after a verified correction,
publication/recovery faults, retained responses, stale evidence, unowned mirrors,
final findings and unsupported-suite refusal. Affected continuation (9) and
first-pass Phase 2 (21) regressions pass on the corrected source. Legacy scheduler,
declaration and bridge checks (34), plus contract/evaluation checks (39), exercise
unchanged dependencies. The entire repository suite was not run.

The [evidence record](audits/VNEXT_18_8_PHASE2_CLOSEOUT.json) enumerates exact commands,
method identities, source snapshots, log hashes, corrections and limitations. Raw
logs remain under ignored `rounds/vnext-18-8-phase2-closeout-001/`. Exploratory failures
are retained and superseded by corrected-source passing runs; their successes are
not added to the count. The final corrected source snapshot remains unchanged.

`git diff --check` passes. Frozen suite 1 and the three empty shipping qualification
maps are unchanged. Validation finished with an empty index and no commit, push or
external call. Before the subsequently authorized local checkpoint, all source,
manifest and test-log hashes were rechecked successfully. Only documentation
checkpoint metadata changed; tests were not rerun. Pushing remains deferred until
feature completion. These
tests use scripted clients, real local storage and injected faults; they do not
qualify live semantic behavior, physical power loss or process death during writes.
Retained rubric-gap refusal is conservative; a separate historical gap-resolution
journey is not qualified. The continuation batch took 821.754 seconds during
concurrent verification; runtime performance remains unqualified.

The next functional boundary is final-review finding reconciliation: repair a
declaration-only mismatch without asking the Editor to mutate the spec, retain
nonblocking residuals correctly, and use only the supported remaining review budget.
Keep source corrections behind the V candidate protocol. Complete terminal/halt
precedence and failure reports, optional missing-profile closeout, other scheduler
modes, version maintenance, operator/semantic followups and external apply-back
remain open. All four 18.8 tasks and 18.9 qualification remain incomplete.
