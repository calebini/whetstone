# 18.8 bounded Phase 1 operator status and state recovery

Date: 2026-09-20. Starting checkpoint: `78ff26e`.

`VerifiedRun.operator_status()` now selects the active Phase 1 terminal by replaying
current verified lineage and canonical review evidence. `reconcile_phase1_state()`
synchronizes its derived run-state reference and stops. These are explicit internal
APIs requiring a [separate consuming algorithm pin](../contracts/algorithms/vnext_verified_phase1_operator_v1.md),
building on the [closeout slice](VNEXT_18_8_PHASE1_CLOSEOUT.md).

All four 18.8 tasks remain incomplete. This connects the bounded horizontal Phase 1
closeout to operator status and derived state; it does not dispatch the public CLI,
change legacy/bridge status, or implement all terminal and continuation paths.

## Active evidence and derived state

The reader proves authority and reproduces the expected closeout. Only matching
visible report AND closeout evidence select an active terminal. A report-only
prefix remains unpublished. Historical files are preserved; filesystem ordering
and cached report paths never select success. Corrupt current committed artifacts
refuse without cached fallback. Acceptance is separately evaluated from current
reviews and may be known before publication.

The single new member of `rounds/run_state.json`, `vnext_phase1_closeout`, contains
the exact `{path, hash}` reference to that committed evidence. The evidence in turn
binds job identity, current pointer, review prefix and terminal report. If no current
committed closeout exists, the member must be absent. Other state members are
preserved. Legacy terminal/readiness/accepted-hash fields cannot confer authority
or permission on this V reader, even if those cached fields claim success.

| Observed boundary | Operator result / recovery |
| --- | --- |
| Mirror, registration or promotion work has precedence | Withhold terminal, acceptance and state-currency claims; expose the existing work gate. |
| Current terminal eligible, evidence commit missing | No active terminal; explicitly finish closeout separately. State recovery cannot publish it. |
| Committed closeout, missing or different derived reference | Show the evidence-derived terminal with `state_current = false`; recover state before next work. |
| Stale reference and no current closeout | No active terminal; remove only that derived member in recovery. |
| Matching visible state | `state_current = true` describes correspondence, not past durable acknowledgement. |
| Malformed state or corrupt current evidence | Refuse without overwriting evidence or fabricating a report. |

`phase2_permitted`, `apply_back_permitted` and `resume_permitted` remain false.
The internal next-action label does not advertise generic technical resume or
publish a runtime capability. Phase 1 stable remains distinct from Phase 2 entry
and convergence.

## Recovery and uncertainty

The existing single-host D8 owner holds the actual fence. Missing base mirrors are
repaired first and that invocation ends; a separate invocation projects closeout
state. Before projecting a committed closeout, recovery repeats Reviewer source
and receipt barriers, then synchronizes the exact report and evidence. It validates
the current head, run selectors and captured state at the write boundary. Matching
state is synchronized too: a failed final acknowledgement may leave correct bytes.
Reentry repeats barriers and readback, without clients, new ordinals, promotion,
new terminal artifacts or automatic next work.

The closeout owner's existing source-barrier loop was extracted into a shared
method for this consumer. Its publication semantics and frozen contract remain
unchanged. No storage primitive, allowlist, public status dispatch or shipping map
changed.

## Validation

All **47 methods passed on their first runs, with no skips or fixes**: seven new
operator/state methods in 55.035 seconds and 40 regressions in 309.098 seconds.
The recorded source snapshot remained unchanged throughout both invocations.

Validation results are recorded in [the audit record](audits/VNEXT_18_8_PHASE1_OPERATOR.json).
The new cohort covers report-only prefixes, read-only status, unrelated-field
preservation, stale success, a real promoted budget failure, state-write interruption
before and after publication, visible lost-ack barrier replay, source/evidence
barrier failures, corrupt committed artifacts, missing state, and contract refusal.
The regression cohort covers existing closeout, Phase 1 status, V review and legacy
status. Raw logs and the source snapshot are under ignored
`rounds/vnext-18-8-operator-001/`.

Faults are injected at caller/publication/barrier boundaries. They do not constitute
new physical power-loss, exhaustive syscall, distributed-writer or provider
qualification. Tests use scripted clients and process-local suites on macOS/APFS.
There is no full-product regression claim. Registration/promotion precedence reuses
the work owner; this cohort directly exercises missing-mirror precedence, not every
orphan/operator-decision composition.

## Handoff

The [Phase 2 prerequisite slice](VNEXT_18_8_PHASE2_ELIGIBILITY.md) implements the
read-only Phase 1 side and identifies missing immutable Phase 2 configuration.
Entry and execution remain unavailable. The original next-step scope was:
implement Phase 2 **entry eligibility** against current verified
lineage and complete accepted Phase 1 evidence, checking that stale reports,
unpromoted candidates, unresolved decisions and unsupported configuration cannot
grant entry. Keep eligibility distinct from execution, which still needs a pinned
Phase 2 consumer and verified candidate routing. No live provider is needed for
that scripted integration.

Remaining work: focused/vertical/retry/resume/budget-extension integration;
version/history/declaration consumers; Phase 2 execution and convergence;
strop/readback eligibility; complete operator/terminal reporting across those paths.
Public mode use remains blocked by unqualified consuming suites and the deferred
18.9 release gates. No new blocker prevents the next internal eligibility slice.

No mode activation, external transmission, push, external specification apply-back
or 18.9 implementation is included here.
