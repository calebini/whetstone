# Phase 2 continuation after promotion

Started 2026-09-23 from checkpoint `a1cb794`; verification continued on 2026-09-24.
A subsequent local checkpoint was authorized on 2026-09-25;
public modes, live clients, external specification apply-back and push are excluded.

The internal continuation owner follows the first correction with further Phase 2
reviews and supported V corrections. It preserves the existing first request,
result, consumption and advice formats. A separately pinned sequence algorithm and
v2 later-request/consumption schemas bind each subsequent pass to its predecessor
consumption, original entry/configuration and exact proven current pointer.

## Internal operations

- `phase2_sequence_status()` reads the supported next gate, accepted result count,
  ordered profile-step budgets, and distinct profiles clean on the current lineage.
- `bind_phase2_next_review(transport)` publishes or recovers the next immutable
  request. It returns a blocking gate if continuation is unavailable; no client runs.
- `continue_phase2_pass(N, action='execute', client=..., continuation=False)` runs
  the explicitly selected later pass through the existing two-attempt journal.
- The same explicit selector with `action='consume'` publishes cumulative result
  accounting; `action='advice', advice=...` attaches existing untrusted advice;
  `action='admit'` publishes its canonical proposal round after complete preflight.
- Existing `request`, `register`, `verify`, `promote` and recovery operations own
  Editor work and candidate authority. There is no second candidate implementation.

Pass selectors are logical sequence positions, distinct from a step's pass number
and the run-wide round number. Replaying a completed pass does not select its
successor. The first pass still uses its original explicit APIs.

## Scheduling and authority

The owning rules are the [scheduler specification](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md)
(Phase 2 ordered execution, Reviewer-only cleanliness, profile-step budgets and the
vNext downstream transition table) and the
[Phase 2 convergence specification](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md).
The shared scheduler supplies scheduling mechanics; it cannot grant convergence
without the separate declaration and target-matrix conditions.

The sequence reconstructs `PhaseScheduler` from committed results in order. Repeated
profile names retain separate step budgets. Only a validated result counts as one
pass; transport attempts, advice, candidate verification, promotion and recovery do
not grant another review credit. Consumption records are reproduced rather than
incrementing mutable counters. The originally committed consumption remains intact.

A later request reads the actual current verified draft/map. Its entry context stays
bound to original Phase 1 closeout; the additional current-draft reference identifies
the later base. Original prerequisites are reproduced on the proven entry ancestry,
with the actual head guard intact. Historical round validation reads only its
original request prefix; it cannot rely on its own unproven promotion or future
requests. It never replaces storage reads with a simulated current pointer.

A correction must be promoted from that exact preceding review before another
review can start. A clean review followed by a byte-changing correction needs later
verification; promotion clears distinct-profile cleanliness for changed bytes and
never replenishes budgets. Exhausted residual budgets stop continuation. A completed
configured sequence returns `closeout_required`, never `CONVERGED` or phase completion.

D8 owns every mutation and client invocation. Exact predecessor/source bytes are
rechecked before and after client activity and synchronized before publication.
Materialization, registration and promotion recovery retain precedence. Mutable
entry state must agree with immutable entry but cannot grant historical permission.
Legacy Phase 1 and the old first-only suite paths retain their original dispatch.

## Boundaries and handoff

Unresolved authority/operator choices stop before candidate admission or another
review. Versioned corrections remain refused until version maintenance has a V
candidate protocol. Observed oscillation/conflict signals and an existing declaration
stop at an explicit unsupported-resolution/maintenance gate. This is conservative
internal coverage, not full halt precedence or terminal-report qualification.
A rejected candidate leaves the sequence at `correction_required`; the existing
candidate inspection supplies its rejection evidence. This owner does not yet emit
a comprehensive terminal report or authorize an automatic repair proposal.
Automatic advice, operator/semantic followups, declaration maintenance and final
verification, optional closeout review, other scheduler modes, external apply-back,
and 18.9 qualification remain open. No budget extension or schedule loop is added.
Historical admission's shared Editor transport label remains `phase1`; its actual
Phase 2 configuration/request are separately bound in the preflight hash.

## Validation and next boundary

The bounded continuation milestone is validated: **88 distinct tests pass**. Nine
new integration methods cover continued reviews, a further independent correction
and second promotion, original-base replay, read-only fresh-process reopening,
repeated profile names, budget exhaustion, source/entry-state refusal, explicit
technical continuation, lost request/response/consumption/advice/round acknowledgements,
and later semantic rejection. The other 79 checks cover first-pass Phase 2 (21),
shared preflight/Phase 1 (29), and legacy scheduler/Phase 2/bridge behavior (29).

The [validation record](audits/VNEXT_18_8_PHASE2_SEQUENCE.json) includes exact commands,
method identities, source hashes and retained log hashes. Raw evidence is under
ignored `rounds/vnext-18-8-phase2-sequence-001/`. All production/contracts and existing
test bytes match the validation snapshot. One rejection/recovery method was appended
after the eight-method sequence batch started and passes separately; the preceding
eight-method file bytes are unchanged. Early schema and accounting failures are
retained as exploratory evidence, superseded by the final passing runs.

`git diff --check` passes. Frozen suite 1 and all three empty shipping qualification
maps are unchanged. Validation finished with an empty index and no commit, push or
external call. Before the subsequently authorized local checkpoint, all final source,
manifest and test-log hashes were rechecked successfully. Only documentation checkpoint
metadata changed; no tests were rerun. Pushing remains deferred until feature completion.
The eight-method continuation batch took 707.277 seconds during concurrent local
verification. Historical replay remains expensive; performance is not qualified.
Scripted clients and local fault hooks qualify these boundaries, not live semantic
truth, physical power loss, or process death during the new sequence.

The next functional milestone is verified Phase 2 closeout/declaration handling on
the current lineage, including maintenance and final review evidence, before any
convergence claim. Other remaining boundaries above stay explicit. All four 18.8
tasks and 18.9 qualification remain incomplete.

Subsequent work (2026-09-25, after local checkpoint `7fc003f`): the authorized
[declaration/closeout milestone](VNEXT_18_8_PHASE2_CLOSEOUT.md) is validated separately
and has subsequent local checkpoint authorization. The evidence and limits above describe this continuation
checkpoint; they do not qualify the subsequent closeout owner.
