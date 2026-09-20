# Verified Phase 2 configuration and entry-request binding v1 (unactivated)

This bounded internal consumer pins this algorithm and the new closed
vnext_phase2_configuration_v1 and vnext_phase2_entry_request_v1 schemas, alongside
the existing verified Phase 2 prerequisite and Phase 1 consumer pins. It does not
change frozen review-configuration-v1 or job identity. It adds an explicit subsequent
phase input bound to that job. Descriptor-bound fields cannot change in the same job.

## Supported configuration

All fields are explicit; no defaults from mutable run state, config files or live
environment. This version supports standard workflow, horizontal review,
stateful_system profile set, final/strict target and builtin standard-v1 rubric.
Other workflows, targets, custom rubrics and profile sets are unsupported here,
not forbidden by the broader product specification.

The exact ordered steps are convergence_strict_check, adversarial,
convergence_strict_check. Retain both occurrences of the convergence check and
their independently supplied positive integer budgets. Do not deduplicate, reorder,
fill missing budgets or infer an extra allowance. The target matrix remains
separate from Phase 1 global acceptance and cannot weaken it.

Require job ID, the exact original review-configuration reference, workflow, review
mode, profile set and all three role identities to match immutable job inputs.
The rubric is an explicit root-local staged artifact under inputs/phase2/ with an
exact SHA-256 reference. Confined reads must reject escaping paths and changed
bytes. Supported standard-v1 rubric bytes have SHA-256
`ddcdfed1b43763d4562febdf6e85fbc0178afb91a737662722ea565d039376fe`.
This pin describes exact rubric identity, not its semantic adequacy; do not use a
normalized hash or replace it with whichever installed rubric currently exists.

## Preparation, publication and replay

Prove current verified lineage/map and all existing Phase 1 prerequisites, including
latest candidate decisions, complete accepted/clean review evidence, committed
closeout and matching derived state. Cached success and a prior eligibility object
are not authority. Prepare a deterministic canonical configuration artifact under
rounds/phase2/configurations/config-{configuration_sha256}.json. The request binds
its reference, job/descriptor/original review references, exact current pointer,
draft/map, Phase 1 closeout and terminal report. No timestamp contributes identity.

prepare_phase2_entry is read-only. bind_phase2_entry reacquires the actual D8 fence,
revalidates all bindings and repeats Phase 1 review source/receipt, report, closeout,
derived state and exact rubric barriers. Publish configuration first, then the
single immutable rounds/phase2/entry_request.json. This request is the binding
commit, not a phase transition. Read back and reproduce both artifacts before
returning. phase2_entry_status validates a present request against current evidence;
an absent request returns the existing unbound prerequisite observation.

Only one request may commit in a root in this version. Identical reentry repeats
barriers even if both files are visible after a lost acknowledgement. A conflicting
configuration/request, stale or cross-job binding, missing committed configuration
or damaged committed evidence refuses without replacing it. A configuration-only
publication prefix is retained but has no active request; exact replay may finish
it. Unselected configurations never select authority. New configuration after a
committed request requires a future explicit lifecycle or a new root, not overwrite.

Base-mirror recovery retains the existing separate invocation and stops before
binding. Missing/stale Phase 1 closeout projection requires its existing explicit
recovery; this consumer does not repair it or publish a missing closeout. Inspection
and preparation never recover. Missing Phase 1 prerequisites block binding.

materialized describes visible correspondence, not past durable acknowledgement.
Preview reports phase2_request_unpublished while either binding artifact is absent.
A committed request removes that blocker, but phase2_entry_unimplemented and
phase2_execution_unavailable remain. Entry, technical resume and apply-back
permissions stay false. The old prerequisite API retains its original unbound
contract; callers inspecting this new binding must select the new pinned API.

No client call, logical review charge, candidate/decision/promotion ordinal,
authority update, phase/run-state transition, version/history/declaration mutation,
public CLI activation or external source write is performed. A future entry owner
must revalidate this request under its own fence and implement entry/recovery;
version maintenance cannot use a legacy stamping exception to bypass V verification.
