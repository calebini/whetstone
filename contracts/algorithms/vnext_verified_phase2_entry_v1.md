# Verified unchanged-draft Phase 2 entry v1 (unactivated)

This internal owner requires this algorithm and vnext_phase2_entry_v1 schema pins,
plus all existing immutable Phase 2 binding and Phase 1 consumer pins. It consumes
a committed request; it neither prepares nor binds one on the caller's behalf.
The prior binding/prerequisite APIs retain their separately pinned contracts.
Use enter_phase2 for this entry operation and phase2_state for read-only inspection.

## Preconditions and no-version-change boundary

Under the actual D8 fence, prove current verified lineage/map and complete Phase 1
prerequisites again. Reproduce the exact committed request and configuration:
descriptor, original review configuration, current pointer/draft/map, accepted and
clean current reviews, committed closeout, matching derived state, exact rubric,
explicit target, ordered budgets and immutable role identities. Cached eligibility
or configuration publication alone is not entry. Missing, changed, stale/cross-job
or unsupported evidence refuses without reconstructing or replacing it.

Evaluate the existing pure versioning.promote_spec_text_for_phase2 policy on exact
verified draft UTF-8 bytes. Require no promotion, identical before/after version
labels and byte-identical output. This admits an unversioned no-op and an already
correct whole-major label such as 2.0. Any required rewrite, including formatting
changes such as 2 to 2.0, refuses with version maintenance requiring the V candidate
protocol. Do not write the projected text, call the legacy file stamper or invoke
the legacy full-draft Phase 2 executor. No metadata exception bypasses verification.

## Entry commit and derived state

Publish a deterministic, immutable rounds/phase2/entry.json, distinct from
entry_request.json. It records phase_2, job identity, the exact request/configuration,
current pointer/draft/map, Phase 1 closeout and unchanged version observation.
This is the phase entry commit, not a draft-authority pointer, review receipt,
convergence result or execution grant. It allocates no timestamp or ordinal.

Then materialize only the vnext_phase2_entry member of rounds/run_state.json as the
exact {path, hash} reference to that entry. Preserve every other state member,
including Phase 1 closeout and all legacy fields. An entry commit with missing or
stale derived state requires recovery; a cached state member with the entry missing
refuses rather than reconstructing a claimed commit. Conflicting entry bytes refuse.
The exact current pointer remains sole draft authority.

Before entry publication, repeat current-pointer/mirror barriers through the work
owner, every Phase 1 review source/receipt barrier, and exact synchronization of
closeout report/evidence, state, configuration, request, rubric, draft and map.
Reproduce all bindings again before the entry commit. Validate current authority,
selectors, the committed entry and captured state at the state-write boundary;
reproduce request/entry/state afterward before reporting success.

## Recovery and inspection

Failure before entry publication leaves a bound request, not an entered phase.
Failure after publication leaves committed entry with derived-state recovery work.
Reentry repeats all source and entry publication barriers, even if a lost final
acknowledgement left matching entry/state bytes visible. Matching state is also
synchronized after entry publication. Propagate failures; never report success
merely from equality. Visible committed/state-current observations do not certify
past durability acknowledgements.

A successful first operation returns phase2_entered. A successful call with an
already visible entry returns phase2_entry_recovered and ends after synchronization
or repair. It never advances review or invokes a client, even with fully matching
state. The existing separate base-mirror repair retains precedence and ends its
invocation. Missing Phase 1 state projection requires its existing reconciliation
before entry; this owner cannot publish a missing Phase 1 closeout. Read-only
inspection has no writer fence and never repairs, publishes or advances work.

Execution, generic resume, convergence, declaration, version maintenance and
apply-back remain unavailable. Future Phase 2 execution must consume and revalidate
this entry under its own separately pinned lifecycle, not infer readiness from
legacy run-state fields. No public activation, shipping-suite publication or source
apply-back is included. D8 remains single-host/single-writer.
