# 18.8 immutable Phase 2 configuration and entry request

Date: 2026-09-20. Starting checkpoint: `d56090c`.

This slice binds explicit Phase 2 inputs to the job, exact current pointer/draft/map,
original review configuration and committed Phase 1 closeout. The
[consumer](../src/whetstone/vnext_verified_phase2_binding.py) exposes three internal APIs:

- `prepare_phase2_entry(configuration)` validates and previews deterministic artifacts without writing.
- `bind_phase2_entry(configuration)` revalidates under the actual D8 fence and publishes configuration then request.
- `phase2_entry_status()` replays an existing request against current evidence; without one, it returns the existing unbound prerequisite view.

The [algorithm](../contracts/algorithms/vnext_verified_phase2_binding_v1.md) and two
new closed schemas require separate consuming-suite pins. Frozen Phase 1 review,
job and prerequisite contracts are unchanged. The prerequisite reader's evaluation
was extracted for reuse within the binding owner's fence; its existing API retains
its original unbound semantics. Select `phase2_entry_status()` to inspect the new
request lifecycle.

**A bound request is not Phase 2 entry.** Entry, execution, generic resume and
apply-back remain unavailable. All four 18.8 tasks remain incomplete.

## Explicit configuration

The bounded supported combination is standard workflow, horizontal review,
stateful_system profile set, final/strict target and builtin standard-v1 rubric.
Other targets/profile sets/custom rubrics are unsupported by this consumer. It
does not change their broader product policy.

The ordered Phase 2 steps match the existing vocabulary: convergence_strict_check,
adversarial, convergence_strict_check. Both occurrences of the final check remain
separate steps with explicit positive integer budgets; no deduplication, inferred
defaults or added capacity. Workflow, mode, profile set, job/review references and
all three role identities must match descriptor-bound inputs. Target and rubric
cannot weaken the accepted-draft requirement.

The caller supplies an exact reference to a staged rubric under `inputs/phase2/`.
The algorithm pins the supported standard-v1 SHA-256. Readback checks exact bytes,
not a normalized hash or a currently installed default. Staging is explicit local
input preparation, outside these APIs; no external artifact is fetched or transmitted.

## Publication and recovery

The new configuration is content-addressed under `rounds/phase2/configurations/`.
The single immutable `rounds/phase2/entry_request.json` binds it to current verified
authority and Phase 1 evidence. This request is the configuration-binding commit.
Only one request can commit in a root in this version. Later budget/configuration
changes require a future explicit lifecycle or a new root; they cannot overwrite it.

Preparation/publication require complete current Phase 1 prerequisites, including
matching derived state. Publication repeats the existing review source/receipt,
report, closeout, state and exact rubric barriers before configuration and request
writes. Reentry repeats barriers even after a lost acknowledgement left the final
request visible. `materialized` describes visible correspondence, not certainty
about a past flush.

A configuration-only prefix has no active request. Exact replay can finish it;
unselected configurations do not confer authority. A committed request with missing
configuration, conflicting bytes, stale/cross-job bindings or changed source evidence
refuses without reconstruction or replacement. Base-mirror repair retains its own
invocation and ends before binding. Missing Phase 1 state projection requires the
existing explicit reconciliation; this consumer does not finish Phase 1 for callers.

No draft authority, phase state, version/history/declaration or logical budget is
changed. No new client, candidate, decision or promotion ordinal is allocated.

## Validation and limits

All **35 methods passed on their first runs, with no skips or fixes**: eight new
binding methods in 103.874 seconds and 27 regressions in 336.224 seconds.
The recorded source snapshot remained unchanged throughout both invocations.

The [audit record](audits/VNEXT_18_8_PHASE2_BINDING.json) records commands, exact
method identities and source/log hashes. Raw evidence is under ignored
`rounds/vnext-18-8-phase2-binding-001/`.

New tests cover deterministic preview/readback/reopen; independent repeated-step
budgets; unsupported/missing/extra/cross-job inputs; real post-promotion binding;
stale pointer/closeout and changed configuration rejection; configuration/request
publication prefixes and lost final acknowledgement; review/closeout/rubric barrier
failures; missing committed configuration and changed rubric bytes; separate mirror
and state recovery; and missing consumer pins. Existing prerequisite, operator-state
and V review methods form the regression cohort.

Tests use fictional clients and process-local suites on macOS/APFS. Publication and
barrier hooks validate caller/replay behavior; they do not add physical power-loss,
exhaustive syscall, distributed-writer, live-provider or full-product qualification.
Legacy/bridge runtime bytes, frozen suite and shipping maps remain unchanged.

## Handoff

Next bounded slice: implement a fenced Phase 2 entry owner consuming this committed
request, with a distinct entry commit and recovery-only reentry. Revalidate current
pointer, Phase 1 prerequisites, configuration and source barriers under that fence.
Start with the no-version-change path; explicitly refuse version maintenance until
it can pass the V candidate protocol. Do not call the legacy full-draft Phase 2
executor or treat configuration publication as phase entry.

Then implement pinned Phase 2 review/candidate routing, including the runtime
profile/rubric/vocabulary evidence required before any client call, convergence and
declaration. Other 18.8 consumers remain: focused/vertical/retry/resume/budget
extension, version/history lifecycle, strop/readback and remaining operator/terminal
paths. 18.9 release qualification and public activation remain deferred.

Per the user's current instruction, checkpoints stay local until the feature is
complete. No push, external transmission, mode activation or external apply-back
is part of this slice.
