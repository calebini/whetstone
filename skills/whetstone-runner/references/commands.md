# Command interpretation

Check the selected runtime's `<command> --help` and matching Operator Quickstart.
Use its launcher when configured; direct source invocation is for explicitly
selected development or a checkout without a launcher. Do not assume launcher
channel flags are package CLI flags.

| Command family | Meaning and limits |
| --- | --- |
| `audit-change` | Bounded reviewer-only assessment. No Editor, scheduler credit or convergence. Inspect actual report format: a v1 boundary indicator is not independent semantic proof. |
| `reviewer-smoke` | One reviewer plumbing/assessment call, not a stabilization loop. |
| `intake` | Generate notes or compile a scope contract; inspect deterministic output and actual approval state. |
| `live-phase1` | Iterative stabilization under the selected mode. Per-profile allowances are not total calls or vertical cycles. |
| `live-focused-phase1` | Supported single-profile recheck. Focused stability is not Phase 2 eligibility. |
| `promote-phase2`, `live-phase2` | Supported entry and convergence after actual prerequisites; no source-write consent implied. |
| `status`, `resume` | Inspect first, then only the selected mode's supported dry-run/recovery/continuation. Do not assume every timeout is resumable. |
| `preservation-review`, `preservation-attest`, `preservation-request`, `preservation-accept` | Bridge exact-effect review and local acceptance. No model calls or automatic next round; actual attestations required. |
| `vnext-admit`, `vnext-decisions`, `vnext-decide` | Mode/suite-specific package and decision operations. See verified command matrix; names alone do not advertise availability. |
| `strop`, `apply-back` | Assess and separately authorize source adoption using the mode's exact procedure. Legacy overrides do not apply to verified roots. |
| `decompose` | Existing plan/approve/extract/audit/promote workflow; copy-first provenance, not creative rewriting or convergence. |

Typical outcomes: `PHASE_1_STABLE`, `FOCUSED_PROFILE_STABLE`,
`PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`, `CONVERGED`, `TARGET_NOT_REACHED`,
`PAUSED_DECISION` or a typed client/artifact failure. Use only states actually
reported for the executing mode. Exit zero alone establishes none of these.
