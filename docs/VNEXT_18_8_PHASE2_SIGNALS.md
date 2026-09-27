# Phase 2 conflict and oscillation reporting

Implemented and validated from `63806a8` (2026-09-27); the user subsequently
authorized a local checkpoint after source and evidence revalidation. The pre-existing
planning handoff is preserved and updated. The six requirements below are covered
at this bounded internal reporting scope; general Phase 2 and 18.8 completion are
not claimed. No push, public activation or external transmission.

## Fixed bounded acceptance

1. Reproduce normalized committed-draft and canonical consumed-feedback signals,
   with existing conflict identity, severity and consecutive/cumulative history.
2. Distinguish freeze, continue-once, nonblocking conflict, blocker-conflict halt
   and terminal oscillation. Preserve simultaneous reasons and existing budgets.
3. Preserve D7 preconditions and runtime precedence, including clean final
   convergence and conflict/oscillation before budget exhaustion.
4. Publish separately pinned immutable diagnostics and terminal companion reports;
   bind original configuration, entry, review prefix, pointer and rubric. No new
   resolution authority, repair admission or automatic recommendation application.
5. Recover only owned mirrors and namespaced state under D8, including interrupted
   publication and uncertain final state acknowledgement. End without clients.
6. Validate source drift, tampering, historical continuation, terminal competition
   and compatibility. No broad 18.8 completion claim.

Authority: [classification and conflict history](specs/IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md),
[ordered terminal evaluation and D7](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md), and
[Phase 2 companion reports](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md).
The investigated boundary is settled for reporting. A freeze remains a distinct
unresolved gate; implementing its resolution is outside this slice. Promotion is
not the artifact-backed intervening-resolution receipt required to clear churn.

## Operator API

- `phase2_signal_status()` reads validated evidence.
- `publish_phase2_signals()` publishes diagnostics and any eligible terminal.
- `reconcile_phase2_signal_state()` recovers owned report mirrors and
  `vnext_phase2_signals`, then stops without client work.

Root diagnostic files can remain historical. Their presence never grants work or
establishes the current terminal. A separate immutable terminal commit carries the
evaluated halt and companion report. General Phase 2 resume remains unsupported.
Initial diagnostics have null terminal state; once terminal evaluation is eligible,
the terminal commit also binds evaluated diagnostic copies carrying the selected
halt. Recovery projects those copies without rewriting the initial evidence.

Feedback diagnostics bind the original reviewed pointer; draft diagnostics bind
the committed promoted pointer. Thus a nonblocking feedback report does not change
when a later correction promotes. A cycle report uses current verified bytes and
retains findings from the triggering reviewed base: promotion alone cannot prove
their resolution. The report records actual consumed profile budgets and uses
`not_run` for final Reviewer status until a declaration review has actually run.

The shared root report owner recognizes only exact committed owned bytes. Recovery
through an older Reviewer/correction owner also respects newer signal diagnostics.
Conflicting unowned files, unknown report claims and corrupt authority refuse.
Source and report dependency durability barriers repeat after uncertain writes.

## Remaining boundaries

Freeze resolution, artifact-backed intervening-resolution admission, actual
declaration repair, operator followups/new repair admission, rubric handling,
broader scheduler modes, version maintenance, strop/readback and release
qualification remain open. This slice does not interpret recommendation text as
permission to mutate or resolve findings. No product/authority decision blocks the
reporting boundary; a later resolution owner must establish its own authority.

Verification uses local scripted clients and injected failures on macOS/APFS.
Physical power loss, process death during a write, live providers, performance
qualification and a full repository release campaign are not covered here.

## Validation and handoff

The [evidence record](audits/VNEXT_18_8_PHASE2_SIGNALS.json) credits **65 distinct
passing methods**: eight new methods, 53 shared rule/contract/finding-route checks,
and four existing runtime compatibility journeys. All eight new methods passed on
delivered runtime/contract bytes. The 57 existing checks exercise unchanged selected
implementations; this is not a full repository or release qualification claim.

The new checks cover classification and simultaneous precedence, conflict-history
thresholds and absence, freeze and blocker reporting, publication prefixes, source
drift and report tampering, unowned mirrors, uncertain final state acknowledgement,
nonblocking conflict history through promotion/clean closeout, final finding
preconditions, conflict before exhausted final budget, and a genuine two-promotion
draft cycle with current authority and retained findings. Continue-once and
cumulative thresholds have rule coverage; not every combination has a full runtime
journey.

The cycle test's original assertion expected `CANDIDATE_VERIFIED` after promotion;
the corrected standalone test verifies `CANDIDATE_PROMOTED`, the selected terminal
diagnostic and retained findings. Only the individually completed passing history
method is credited from the interrupted two-method cohort. Its redundant obsolete
cycle run, earlier fixture failures, contract-refinement invalidations and duplicate
checks are excluded. Exact method lists and source limits are in the evidence
record. Raw logs/manifests remain in ignored local
`rounds/vnext-18-8-phase2-signals-001/`.

All 556 delivered manifest hashes match; `git diff --check` passes. The index is
empty at validation time, frozen suite 1 and authoritative specs are unchanged,
and public qualification maps remain empty. The evidence record describes the
pre-checkpoint validation snapshot. The user subsequently authorized the local
checkpoint after source and evidence revalidation. All four 18.8 tasks and 18.9 remain
open; the remaining boundaries above are not implemented by this slice.
