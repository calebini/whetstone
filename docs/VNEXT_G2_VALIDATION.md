# 18.7 G2 current-source validation

Date: 2026-09-18. Starting checkpoint: `bb1556c`.

This executes the fixed remaining cohort from the [G1 handoff](VNEXT_CONCURRENT_SELECTION.md)
and [18.7 acceptance map](VNEXT_18_7_ACCEPTANCE_MAP.md). It adds no fault cases,
runtime implementation, contract changes or advertised capability.

**All 97 existing methods pass with no skips on their first runs:** eight runtime methods (1240.345 seconds) and 89 component methods (476.585 seconds), in two parallel invocations. No source fix was needed. G2 is closed at this bounded validation scope. Together with the 84 carried methods on unchanged source, the acceptance map has 181 distinct methods with passing evidence. This is not a full product regression or release qualification.

## Exact validation scope

The source manifest was recorded before execution. Static test discovery matched
exactly the 97 method identities selected by G1's evidence record, with no extras
or duplicates. The cohort runs in two independent invocations on that same
snapshot; every fixture owns its own temporary run root.

| Invocation | Existing modules | Methods |
| --- | --- | ---: |
| Runtime | Runtime follow-up, recovery and Verifier faults | 8 |
| Components | Local storage (32), candidate registry (21), shared semantic decisions (7), pointer history (9), verified history (10), V semantics (10) | 89 |

The runtime invocation refreshes the operator-child/two-promotion journey and
readback, answer/selection and lost-ack recovery, killed Reviewer before/after
raw output, orphan registration, prepared verification and killed Verifier
before/after raw output. The component invocation covers the D8 physical binding,
exclusion, ownership and durability primitives plus registration, semantic
finality and committed-history proof.

The separate [G1 checkpoint](audits/VNEXT_CONCURRENT_SELECTION.json) already
refreshed the two Batch A methods. They are credited, not repeated here. Its 16
promotion regressions overlap the acceptance map's earlier 81 current-source
methods. The new G1 method and refreshed Batch A bring that carried set to 84.
The G2 cohort has no overlap with those 84 methods. Counts describe distinct
unittest methods, not subcases or a clean single full-suite execution.

Both retained logs, exit codes, exact method identities, the environment and
source manifest are bound by the [machine-readable record](audits/VNEXT_G2_VALIDATION.json).
Raw evidence and the local verification scripts remain under ignored
`rounds/vnext-g2-refresh-001/`. Earlier failing/intermediate runs remain unchanged.

## Three implementation tasks and remaining gates

The three 18.7 implementation tasks are now checked at the isolated
component/runtime boundary. The containing slice remains incomplete pending
earlier-slice dependencies and consuming-release qualification:

| Plan task | Acceptance-map evidence |
| --- | --- |
| Shared fenced lock, intent/event/snapshot preparation and atomic pointer commit | D8-01–05, R-01, V-01, P-03–04; actual cooperating-process exclusion, released/forked token refusal, immutable replay, conditional commit and uncertainty recovery. |
| Current lineage, sole claimant and ordered materialization recovery | P-01–03 and M-01; G1's latest-of-two selection; prepared reservation, invalid-prefix refusal, exact ancestor bindings and separate repair before later work. Committed history is validated, never reconstructed from mirrors. |
| Explicit rejection/recovery, no stale-holder write, read-only status | D8-02–05, R-01, V-01, P-01–04, M-01 and O-01; component prefix matrices and representative canonical-runtime, process-death and primitive-failure evidence. |

These checks close G2's bounded evidence refresh, not complete consuming-release
qualification. They do not establish every syscall/runtime permutation, another
filesystem, physical power loss, distributed writers or cross-implementation
conformance. Fixtures register unadvertised suites only within their processes.

The next bounded step is **G3: reconcile 18.5 acceptance first**. Map deterministic
assembly, maps/inventory/assertions, immutable registration and proposal-only
request-to-candidate behavior to existing code and retained passing evidence.
Reuse the storage/registry results from this checkpoint. Identify only concrete
missing proofs or consuming-suite blockers; do not start another generic storage
fault batch. Then reconcile 18.6's independent semantic and follow-up acceptance.
Neither earlier slice is declared complete by this 18.7 validation.

D8 design/audit closure stands. A new descriptor-bound consuming suite, remaining
scheduler/Phase 2/apply-back consumers, full P0/cross-implementation and compatibility
qualification, separately authorized live soak and activation remain later gates.
No 18.8–18.9 implementation, external provider invocation, new mode, push or
external specification apply-back is included. Frozen suite 1, empty shipping
qualification maps and legacy/bridge runtime bytes remain unchanged.
