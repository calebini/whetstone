# Final Phase 2 nonblocking findings

Started 2026-09-26 from clean local checkpoint `7a90a85`. This bounded slice removes
the blanket stop for nonblocking findings in the final scheduled declaration review.
It preserves the original reviewed artifacts and publishes separate residual
evidence. The user subsequently authorized a local checkpoint on 2026-09-26.
Push, public activation, live calls and external specification writes remain excluded.

## Supported operations

The new algorithm and reconciliation/v2 closeout schemas must be explicitly pinned
by the consuming suite. Older suites keep their original artifacts and behavior;
there is no in-place suite upgrade or shipping qualification-map change.

After consuming the final v3 review, `phase2_final_findings()` is read-only. It
reproduces the review prefix, current verified pointer, configuration, declaration,
result and consumption, then reports the pending or committed reconciliation.
`reconcile_phase2_findings()` repeats those source barriers under D8, publishes an
immutable `unresolved_issues.json` snapshot and then its reconciliation commit. It
ends after publication or recovery, without invoking a client, consuming a review
credit, allocating a successor or publishing a terminal.

The original declaration package's issue file is never overwritten. The new snapshot
retains current-pointer, latest-per-profile issues, including minor/nit and
out-of-scope residuals. The reconciliation binds all source consumptions and the
complete final feedback reference, so claims, recommendations and original evidence
remain available. No issue is marked repaired by this owner.

`closeout_eligible` requires no global major/blocker debt, no rubric/gap signal, no
authority/determinism/invariant signal, no observed feedback oscillation and complete
current-profile cleanliness. Minor/nit findings without those signals remain
documented residuals. Existing declaration identity, count and target checks still
apply. Even an empty final review requires the reconciliation commit on this new
suite extension.

`finish_phase2()` then publishes a v2 closeout binding the exact reconciliation and
residual-issue references. `reconcile_phase2_state()` remains a separate operation.
All source, reconciliation and closeout barriers replay after uncertainty. Root
declaration publication and namespaced state recovery retain their existing rules;
they do not become alternate authority.

## Explicit blocking routes

Authority, determinism or invariant signals route to `authority_resolution_required`;
rubric signals route to `rubric_resolution_required`. Serious source findings,
including a mixture of source and declaration findings, route to
`source_revision_required`. Serious declaration-only findings route to
`declaration_revision_required`. Observed feedback oscillation and missing current
profile verification also block eligibility. The receipt retains all blocking
reasons and the remaining ordinary step budget.

These are descriptive gates, not mutation or review grants. Neither a serious
finding labeled `declaration_hash_mismatch` nor its prose is evidence of completed
repair. The existing immutable package already reproduces the verified current
data; a corrupt package must refuse. Actual declaration-only repair needs a
separately proven revision and verification path. This slice does not invent a
repair, use a repeated review to discard serious findings, extend a budget, emit
TARGET_NOT_REACHED for unfinished support, or call the legacy Phase 2 executor.

This implements the nonblocking-residual portion of the prior handoff. It does not
complete declaration repair or final-review source correction. The relevant rules
remain the [convergence acceptance criteria](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md)
and [scheduler maintenance, target and routing rules](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md).

## Verification and next boundary

**72 distinct tests pass:** five new runtime journeys and three routing checks,
seven prior closeout regressions, 13 shared runtime/continuation checks and 44
contract/declaration/evaluation tests. The new journeys cover minor/nit residual
closeout, fresh-process reopening, remaining-budget preservation, serious mixed
findings, dependency/source refusal and lost reconciliation/closeout/state writes.

The [evidence record](audits/VNEXT_18_8_PHASE2_FINDINGS.json) includes exact commands,
test identities, source snapshots, log hashes and limits. Raw logs are under ignored
`rounds/vnext-18-8-phase2-findings-001/`. The initial private-method naming collision
was corrected before the validation snapshot. Subsequent exploratory failures were
in the fresh-process JSON comparison assertion; the complete corrected findings
cohort passes. Production, contracts and existing test bytes stayed fixed throughout
validation. Exploratory successes are not added to the final count.

`git diff --check` passes. Frozen suite 1, all three empty shipping qualification
maps and the empty index were preserved at validation; no commit, push or external
call occurred during implementation. The subsequent local checkpoint reverified all
533 final snapshot files, changed-source hashes, three manifests and four logs with
72 passing test identities. Only documentation checkpoint metadata changed after
validation, so tests were not rerun. No push or external call is authorized.
New v2 residual journeys use seed-entry fixtures; promoted-lineage closeout is
rechecked with the prior v1 owner, not separately qualified as a v2 residual journey.
Authority/rubric/oscillation combinations have routing-unit coverage; serious mixed
findings also have runtime coverage. Tests use scripted clients and local fault
hooks, not live providers, physical power loss or process death during these writes.
The full repository suite and legacy/bridge campaign were not rerun; unchanged
legacy code and prior compatibility evidence do not constitute fresh qualification.

Next is a proven revision/review path for final declaration-only blocking findings,
including deterministic repair evidence, remaining-budget selection and interruption
recovery. Source corrections continue to require the V candidate protocol. Broader
gap resolution, operator/semantic followups, complete halt/failure reporting, other
scheduler modes, version maintenance and external apply-back remain open. All four
18.8 tasks and 18.9 qualification remain incomplete.


## Declaration repair authority investigation (2026-09-26)

Starting from clean checkpoint `9ad04a3`, the proposed declaration-only repair slice
encountered an unresolved product choice before runtime implementation. This is an
implementation decision for the maintainer, not a new per-run approval requirement.

The scheduler spec (lines 358–406) authorizes Orchestrator-owned regeneration when
a declaration becomes stale after a draft change, and removal of hash-binding
findings only when that regeneration fully repairs them. Its state transitions
(lines 915–931) distinguish declaration work from source work and give source
revision precedence. The Phase 2 acceptance spec (lines 139–160) still requires
zero serious declaration findings from the verification review. Neither provision
defines how an unchanged, mechanically valid declaration can override a contrary
serious Reviewer finding.

The current `_bundle` owner reproduces its immutable package from the verified
pointer, configuration, rubric and consumed review prefix; mismatching stored bytes
refuse. `_DeclarationPass._build_review` requires that package and zero existing
serious debt. Source-promotion regeneration already has a dedicated integration
test. Consequently, that stale-hash case is not evidence that an arbitrary serious
finding from the final v3 review has a supported automatic repair. This does not
prove that the renderer can never have a defect; a real defect must be demonstrated
and corrected under the versioned contract, not hidden by rewriting old evidence.

The investigation presented one decision: when no deterministic repair is established, retain
the serious finding and implement an evidence-backed blocked-status report, or
design budgeted re-review of the unchanged declaration with explicit disagreement
resolution rules. The user subsequently approved retaining the finding and implementing
the report (2026-09-26).
The report should bind the reviewed declaration, current pointer/configuration,
source feedback and field comparisons, identify the remaining review budget, and
state that no repair or successor review is authorized. It must not call the claim
false merely because the mechanical fields match; semantic concerns can remain.
It must not introduce a terminal, operator override, or new acceptance rule.

No runtime, contract, test or authoritative-spec change is made by this
investigation itself. The subsequent user instruction, not this note, ratifies the
reporting scope. The current
reconciliation receipt remains unchanged; arbitrary declaration repair, further
review selection and complete failure/terminal reporting remain open. Evidence is
under `rounds/vnext-18-8-declaration-repair-authority-001/`; the prior 72-test record
remains historical and is not counted as a fresh full rerun. No commit, push,
public activation, live client or external apply-back is included.

Investigation verification: **five existing tests pass** (three finding-route unit
checks, the mixed serious-finding runtime refusal, and regeneration after a verified
source correction). The regeneration journey uses the existing v1 closeout owner;
this is not new v2 promoted-reconciliation qualification or a declaration-repair
implementation. All 533 prior source snapshot files still match; the investigation
snapshot additionally binds the three authority specs. Exact command, test identities,
source/log hashes and limitations are in the local `evidence.json` beside the log.
`git diff --check` passed at the investigation boundary, when only this handoff and
`IMPLEMENTATION_PLAN.md` had changed. The authorized implementation follows in
[the blocked-report handoff](VNEXT_18_8_PHASE2_BLOCKED_REPORT.md).
