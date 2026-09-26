# Phase 2 Reviewer failure lifecycle

Implementation started from `e84995a` with the prior boundary investigation's two
uncommitted documentation files preserved. The user authorized implementation of
[the six-part acceptance boundary](VNEXT_18_8_PHASE2_FAILURE_BOUNDARY.md).
The bounded milestone is implemented and validated (2026-09-27); the user
subsequently authorized a local checkpoint.
The six acceptance requirements are covered at this scope; this is not complete
general Phase 2 failure handling or a complete-feature claim.

The separately pinned `vnext_verified_phase2_failure_v1` extension uses the existing
request journal and two attempt slots. Existing first/later execution APIs publish
failure evidence after a known failed invocation. New internal inspection,
publication recovery and state recovery APIs are `phase2_failure_status()`,
`publish_phase2_failure()` and `reconcile_phase2_failure_state()`. No provider adapter,
CLI, mode activation, external apply-back or generic Phase 2 resume is introduced.

Each failed outcome prefix owns immutable diagnostic, convergence-failure and
terminal reports plus a rubric binding and commit below its existing request's
`execution/failures/attempt-N/`. This is not a new attempt allocator or dispatch
journal. Failure publication leaves current draft authority and review counters
unchanged. Historical reports reproduce against their original request base and
predecessor review evidence, including after a verified promotion. Final declaration
verification remains `not_run` when it yielded no valid result. Earlier requests
need no fabricated declaration; they bind a configuration-derived rubric manifest.
The safe draft path is the actual immutable current-verified snapshot bound by the
request. Failure handling does not invent a legacy numbered-round draft snapshot
or admit a normal round before a valid result exists.

Publication and projection recovery are separate. Execution reports
`reviewer_failure_state_recovery_required` when recovery is pending; callers invoke
`reconcile_phase2_failure_state()` before selecting an eligible explicit continuation.
That operation repeats source/report/commit barriers and always stops after recovery.
After successful result completion, inspection derives no active Reviewer failure;
the old immutable reports remain history. State recovery clears only the namespaced
active reference. Successful review consumption remains owned by its existing API.
An interrupted single shape-validation failure with its allowed retry still
available stays at the existing journal continuation gate; it is not reported as
exhaustion. Calling failure publication before any failure performs no journal write.

Root error/failure files are projections of committed immutable reports. A canonical
snapshot replacement uses the existing D8 conditional replacement primitive, exact
old bytes and domain checks. Unowned conflicting files refuse; the frozen
materialization whitelist is unchanged. A later exhausted-budget closeout can replace
an owned earlier failure projection. Clean convergence leaves those reports as
historical evidence, with its own current closeout authority.

`phase2_failure_status()` describes Reviewer failure state, not the entire run's
terminal status: `terminal_state: null` means no active Reviewer failure. Existing
`phase2_closeout()` remains the source for CONVERGED/final-budget closeout. Cached
run state never grants review credit, continuation permission or accepted status.

For an intact published timeout, the internal operator sequence is:

1. Inspect `phase2_failure_status()` and the bound reports.
2. Run `reconcile_phase2_failure_state()`; it ends after recovery.
3. If eligible, call `run_phase2_review(client=..., continuation=True)` for pass 1,
   or `continue_phase2_pass(n, action='execute', client=..., continuation=True)`
   for the exact later pass.
4. After success, recover the historical/current state projection, then consume the
   result through its existing API. No extra review credit is allocated by recovery.

If report publication was interrupted, `publish_phase2_failure()` finishes its exact
prefix before projection recovery. `resume_permitted` describes the failed request's
remaining component eligibility; publication, `state_current`, `mirrors_current` and
all live guards still apply. It does not authorize bypassing recovery or a third
attempt. No timeout, transport or frozen-input override is added.

## Verification and remaining boundaries

**67 distinct methods passed across 72 successful executions**, with no skips.
The [evidence record](audits/VNEXT_18_8_PHASE2_FAILURE.json) maps the six acceptance
requirements to method identities, exact commands, logs and source hashes:

- Eight initial integration methods passed, including promoted-history replay,
  exact failure classification, both eventual closeouts, repeated failures,
  retained output, tampering and fresh-process recovery after uncertain state write.
- The final boundary check tightened three behaviors: an available shape retry does
  not publish a terminal; empty failure publication performs no journal write; an
  invalid continuation flag refuses before work. Only the new algorithm, module
  and tests changed. Six targeted methods passed on delivered bytes, including one
  new method and expanded before-publication, report-replacement acknowledgement
  and source-drift checks. Three initial integration methods were not rerun after
  these isolated changes.
- Fourteen existing client/closeout/sequence methods passed for older suites without
  the failure pin. Their runtime call sites, contracts and fixture bytes stayed
  unchanged throughout that cohort. Forty-four contract/declaration/evaluation and
  verified-byte checks also passed. This is scoped evidence across snapshots, not
  a claim that every method ran again on the final source or that the whole repo
  was tested.

At the validation and pre-commit recheck, all 548 delivered source snapshot hashes
matched. Frozen suite 1 and all empty public qualification maps were unchanged.
`git diff --check` passed; the index was empty and HEAD was `e84995a`. The original boundary-investigation documents are preserved
alongside this work. Raw evidence is under
`rounds/vnext-18-8-phase2-failure-001/`.

Initial exploratory failures exposed an inherited work-view method-name collision
and an uninitialized registry view during direct historical report inspection.
Both were corrected before the eight-method passing cohort; exploratory results
are retained separately and excluded from the final count.

Tests use scripted clients, source/write fault injection and local subprocess
reopening on macOS/APFS. Live providers, physical power loss, process kills during
a write, a full repository/new legacy-bridge campaign and release qualification
are not claimed.

Other client roles, candidate-rejection terminals, conflict/oscillation publication,
operator/rubric resolution, declaration repair, version maintenance, broader
scheduler modes and strop/readback remain outside this milestone. Storage/authority
failures propagate honestly when safe report publication cannot complete. All four
18.8 tasks and 18.9 qualification remain open. No product or authority decision
blocks the delivered Reviewer scope. The next recommended investigation is the
Phase 2 companion-report/current-status boundary for existing Editor/Verifier and
candidate failure outcomes, preserving their established dispositions and finality;
it is not authorization to add new retries or implement that next milestone.
The user subsequently authorized a local commit after source and evidence
revalidation. No new test execution was needed; the recorded validation limits
remain unchanged. Push, public activation and external transmission remain excluded.
