# Q3 — replay performance and deterministic qualification

Current disposition: **Q3 closed by explicit operator acceptance of the residual
correctness risk and measured performance for proceeding to Q4.** The original
failure remains unexplained; the inventory is not relabeled all-passing.
Performance will be assessed in practice, with optimization reconsidered if
latency proves unacceptable. This establishes no production latency SLA.
See the [correctness acceptance](#q3-005--operator-correctness-risk-acceptance)
and [performance disposition](#q3-005--performance-acceptance-and-q4-handoff).
Earlier open/pending statements below describe their historical checkpoints.

Initial status: **started; release qualification remains open.** The user authorized
Q3 after the Q2 closure checkpoint `83d7198`. This package retains the finite
scope in the [qualification inventory](VNEXT_18_9_INVENTORY.md): replay cost,
the fixed P0/D8/process/CLI cases and full regression on final sources.

Q2's independent comparison and corrected compatibility assertion are committed.
Its final receipt was rechecked against tested files, documentation and logs
before committing. `rounds/vnext-18-9-q2-003/checkpoint.json` joins that immutable
precommit receipt to the checkpoint. Notes and the two local Q1 audit reports
remain outside the checkpoint. There was no push.

## Bounded execution order

1. Establish current consuming-suite replay measurements at one and four
   promotions. Use the retained M5 profiles to identify repeated work, then
   evaluate only an evidence-backed optimization. Require exact output equality,
   read-only behavior and fresh source/fence checks. Retain an optimization only
   when a controlled comparison demonstrates benefit; elapsed time is not a
   correctness verdict or an implicit performance waiver.
2. Freeze the resulting runtime, tests and contract pins. Run affected checks and
   the collected P0/D8/process/CLI/compatibility inventory as one finite campaign.
   Credit each passing method once on its recorded sources. Record failures,
   errors, skips and interrupted methods explicitly; source changes invalidate
   affected evidence rather than silently inheriting it.
3. Reconcile exact method coverage, source cohorts and timing into the release
   performance disposition. Bring back a concrete product decision if accepting
   the remaining latency needs a waiver or an operating limit. Q3 does not
   authorize Q4's live soak or public activation.

Use one `m5_bounded_runner.py` worker with a 60% duty limit, explicit deadline
and actively refreshed 180-second lease. Resume interrupted campaigns from
uncredited methods; do not repeat passing cohorts merely to obtain one large
green log. Existing component suites and injected command qualification retain
their scope. A component test using a generated suite is not automatically a
current consuming-suite route qualification.

## Reproducible collection

`tests/q3_qualification_inventory.py` collects **1,669 discovery occurrences,
1,631 distinct methods in 209 modules** on macOS/Python 3.14.6. There are no
collection errors or declared platform skips on this host. Runtime skips still
need execution accounting.

The 38 duplicate occurrences come from imported `LocalStorageTests` (32 methods)
and `NativeEditorTests` (six). The collector checks identical class and instance
state before deduplicating identities. This avoids repeated work without losing
distinct test cases. All 22 historical P0 rows resolve to collected methods;
the map adds the Q2 negative, budget, recurrence and independent-reference cases.
It also indexes positive simplification, D8, process/prefix faults, command and
compatibility groups. Groups overlap and are indexes, not separate totals or
passing verdicts. The complete inventory includes methods beyond these indexes.

```sh
PYTHONPATH=src:tests /opt/homebrew/bin/python3 tests/q3_qualification_inventory.py \
  --output rounds/<fresh-q3-directory>/collection
```

The source-hashed snapshot is
`rounds/vnext-18-9-q3-001/collection-final/inventory.json`. It is the kickoff
inventory, not a final-source freeze or an execution receipt. A direct-script
import-path issue was corrected during collection; no product test ran during
that failed collection attempt.

## Replay measurement boundary

The retained M5 `2eb4223` profiles used a generated test suite, cProfile and 50%
duty. History/state samples were 5.342s/9.431s at one promotion and
43.682s/77.428s at four. At four promotions, history rebuilt candidate material
34 times and seed inputs 31 times; 31 contract-suite validations accounted for
9.698s cumulative profiled time. These nested costs overlap and cannot be added.
The earlier candidate-material cache experiment showed no speedup and remains
withdrawn. Its existence is not evidence to repeat that experiment.

`tests/q3_replay_profile.py` reuses the whole four-promotion M5 acceptance journey
with the exact registered `vnext-verified-consumer-1` suite. It checks the actual
persisted descriptor and suite path, measures fresh history and Phase 1 state
reads both without and with cProfile, compares their exact outputs and checks
that replay changes no run artifact. It records process CPU time separately
from duty-limited wall time. Native provider entry points are forbidden; clients
are scripted and all sources are disposable fixtures. Public qualification maps
are untouched.

```sh
PYTHONPATH=src:tests /opt/homebrew/bin/python3 tests/m5_bounded_runner.py \
  --output rounds/<fresh-q3-directory>/replay-baseline \
  --wall-seconds 3000 --lease-seconds 180 --duty .6 -- \
  /opt/homebrew/bin/python3 -u tests/q3_replay_profile.py \
  --output rounds/<fresh-q3-directory>/replay-baseline
```

The supervisor owns `status.json`, `tests.log` and the heartbeat. The measurement
driver owns `measurement.json`, individual profiles, sample rows and stage
events. Existing output is refused. An interrupted measurement remains partial;
samples alone cannot supply the whole journey verdict. Historical and current
wall timings use different duty/suite conditions and are not a speedup comparison.
This driver executes a current-suite variant of the collected M5 method; the
ordinary regression method retains its generated-suite fixture. Keep those
execution scopes distinct when reconciling the final campaign.

Any replay optimization remains subject to the pinned
`vnext_verified_history_v1` algorithm: fresh suite/bootstrap/seed validation at
each public entry, ascending proof of exact committed ancestors, fresh current
pointer/descriptor barriers and proof state confined to that invocation. A
process-persistent cache or an inferred authority grant is outside this task.

## Q3-001 baseline and selected optimization target

The current-suite samples on `83d7198` runtime sources are:

| Promotions | Operation | Plain wall | Plain process CPU | Profiled wall |
| --- | --- | --- | --- | --- |
| 1 | History | 2.167s | 1.306s | 4.584s |
| 1 | Phase 1 state | 4.096s | 2.380s | 8.579s |
| 4 | History | 19.644s | 11.599s | 40.082s |
| 4 | Phase 1 state | 32.576s | 19.344s | 69.039s |

These are single diagnostic samples under 60% duty, not a latency distribution,
production SLA or optimization comparison. The eight reads preserve every run
artifact, and each plain/profiled pair returns exactly equal serialized results.
The four promotion stages take 47.106s, 113.302s, 221.105s and 383.142s. Those
stages include multiple protocol operations and scripted clients; they are not
single promotion-call timings.

The four-promotion history profile retains 34 material reconstructions and 31
seed-input revalidations. Suite validation takes 10.995s cumulative within
14.950s of seed-input revalidation, within the 40.082s profiled history read.
These overlapping costs identify a bounded target; they are not additive savings.

**Selected experiment (executed in Q3-002 below):** reduce repeated immutable seed/suite
validation during historical Reviewer input reconstruction
(`_ReviewInputs.values`). Keep fresh public-entry validation, live run and round
selector guards, byte/confined-path rechecks, and invocation-local lifetime.
Compare control and changed replay on the same one/four-promotion fixture in
alternating order, with exact outputs, unchanged artifacts and source/fence
mutation refusal. Do not retain the experiment without demonstrated benefit.
If it fails, preserve that result and bring back a concrete performance
disposition instead of starting an open-ended cache redesign.

The **whole current-suite journey passed in 1160.728s** (one method, no skips,
failures or errors), including the reopened clean review, exact single version
transitions, unchanged committed head/history and five Reviewer/four Editor
calls. This is a baseline, not a performance acceptance or optimization result.

`rounds/vnext-18-9-q3-001/verification.json` joins the source inventory, environment,
measurement, supervisor status, eight samples and evidence hashes. Compilation,
collection integrity and diff checks pass; the supervisor has exited and the
bounded-worker lock is available. Existing runtime/tests/contracts and protected
notes/audits retain their kickoff hashes. Both workspace and fixture parent are
local APFS. All four public qualification maps remain empty.

**At the Q3-001 checkpoint, Q3 remained open.** The bounded optimization experiment,
release performance disposition and final deterministic campaign were outstanding. Runtime, frozen
contracts, authoritative specs, public activation, live providers, external
apply-back and push remain unchanged by this kickoff. The operator subsequently
authorized checkpointing the measurement and inventory tooling and updated
handoff. The original verification receipt retains its precommit source and
documentation hashes; `rounds/vnext-18-9-q3-001/checkpoint.json` records the commit
join and committed file hashes.

## Q3-002 — historical seed-validation experiment

The baseline and inventory are checkpointed at `ff007bf`. On the next resume,
only the protected notes and two local Q1 audit reports were uncommitted, so no
additional feature checkpoint was needed before beginning this experiment.

The bounded change routes historical Reviewer seed checks through a private
callback. Stored-run history uses the existing proof-local `ReplayMemo` to retain
only successful validation (`None`, not a suite, input object or permission).
The key includes proof context and bound selectors; every hit repeats observed
D8 reads and confined contract reads. Live run/round-selector and current
pointer/descriptor guards execute before and after reuse. Public proof
construction remains fresh, and a live borrowed-fence Reviewer input continues
to call the original fresh validation path. The generic historical owner retains
fresh validation as its default. No shared memo implementation, contract, mode,
legacy or bridge code changes are involved.

Four new current-suite methods exercise output isolation, fresh invocations,
changed/missing/symlinked inputs, invalid contract bytes, valid manifest-whitespace
changes, late round-selector resolution, head changes during readback, expired
borrowed fences and fresh live reads. Together with the existing memo,
promoted-history and historical-journal tests, **15 methods pass in 155.466s**.
The initial attempt failed because a test wrongly expected valid manifest
whitespace to be refused. The corrected assertion requires a rebuild and
preserved acceptance; the failed attempt and exact original test source are
retained without passing credit. No production correction was needed for that
fixture error.

`tests/q3_replay_comparison.py` runs the existing current-suite four-promotion
journey. At one and four promotions, it alternates control/reuse/reuse/control
on the same live fixture. Control substitutes the inherited callback that always
performs fresh seed validation. Both arms keep the same dispatch and surrounding
implementation. Plain wall/process times, exact outputs, unchanged artifact
hashes and seed/run/round/proof guard counts are recorded. Guard counts supplement
the fault tests; counts alone do not prove guard correctness. The driver refuses
live native providers and does not alter public qualification gates.

```sh
PYTHONPATH=src:tests /opt/homebrew/bin/python3 tests/m5_bounded_runner.py \
  --output rounds/<fresh-q3-directory>/comparison \
  --wall-seconds 3000 --lease-seconds 180 --duty .6 -- \
  /opt/homebrew/bin/python3 -u tests/q3_replay_comparison.py \
  --output rounds/<fresh-q3-directory>/comparison
```

Evidence is under `rounds/vnext-18-9-q3-002/`. Its source inventory includes
1,635 distinct methods in 210 modules (the prior inventory plus the four new
fault methods). Collection remains an inventory, not a full regression verdict.
The paired plain-read means at 60% duty are:

| Promotions | Operation | Control wall | Reuse wall | Wall change | CPU change |
| --- | --- | --- | --- | --- | --- |
| 1 | History | 2.272s | 2.455s | 8.1% slower | 4.7% slower |
| 1 | Phase 1 state | 4.226s | 4.368s | 3.4% slower | 3.4% slower |
| 4 | History | 19.203s | 16.767s | 12.7% faster | 13.0% faster |
| 4 | Phase 1 state | 32.562s | 28.949s | 11.1% faster | 11.1% faster |

Both four-promotion reuse samples improve on both control samples. Seed
validations fall from 31 to six for history and from 45 to seven for Phase 1
state. Exact serialized outputs match across all four arms, run artifacts remain
unchanged, and run/round/proof guard counts increase. One-promotion reads cost
an additional 0.183s/0.142s on average. These are two repeats per arm on one local
fixture, not a latency distribution or a claim of improvement for every workload.
The whole-journey duration also includes the extra comparison reads and must not
be compared with the earlier profiled baseline as an end-to-end speedup.

The whole current-suite journey passes in **1164.993s**, including the reopened
clean review and all 16 comparison reads (one variant, no failures, errors or
skips). The selected affected-consumer cohort passes **13 methods in 394.519s**:
all seven review-request methods, three Reviewer evidence/fresh-process methods,
two altered-source/same-round-follow-up history methods, and the bound-owner
manifest/input refusal method. Together with the focused cohort this is **28
distinct ordinary methods plus one current-suite journey variant**. Generated
component fixtures retain their scope; this is not a full regression verdict.

**Disposition: retain this bounded optimization.** The two longer-history pairs
show consistent wall/CPU benefit with exact outputs and preserved source/fence
refusals. The documented short-history overhead remains a limitation. Retention
is an implementation decision, not release acceptance of the remaining latency.
No further cache experiment is opened by this result.

`rounds/vnext-18-9-q3-002/verification.json` joins the frozen source inventory,
exact method identities, comparison samples, supervisor exits, evidence hashes
and this handoff. Compilation, diff checks and both registered suite validations
pass. All four public qualification maps remain empty. Protected notes and local
audits retain their kickoff hashes; at verification the staging index was empty
and the bounded worker lock was available. The operator subsequently authorized
checkpointing this bounded optimization, tests and handoff. The verification
receipt retains its precommit hashes; `rounds/vnext-18-9-q3-002/checkpoint.json`
joins that receipt to the commit and committed file hashes. No push, live
provider use, public activation or external apply-back occurred.

**Next: the fixed final deterministic campaign on settled sources.** Reconcile
the 1,635-method inventory and its P0/D8/process/CLI/compatibility indexes,
crediting already passing ordinary methods only when their source cohort and
execution scope match. The current-suite journey variant does not replace the
ordinary generated-suite journey. Record remaining methods, failures, skips and
interruptions explicitly, then bring the complete evidence and remaining latency
back for release performance disposition. Q3 remains open; no SLA, waiver or Q4
live-soak/activation authority is inferred.

## Q3-003 — fixed final qualification campaign

**Inventory execution complete: 1,634 passing methods, one unresolved qualification
failure, and zero unexecuted methods. All qualification workers have exited.
Qualification has NOT passed; performance acceptance is withheld and Q3 remains open.**

The campaign uses committed source `bb2e2be`: runtime, tests, contracts and rubrics
remain byte-identical to Q3-002. Fresh discovery resolved 1,635 distinct methods
in 210 modules (1,673 occurrences, with identical imported instances deduplicated).
Twenty-eight exact-source ordinary passes carry forward from Q3-002. The other
1,607 methods completed in normal cohorts: 1,606 passed and one failed. There are
no errors, skips or fixture errors in those completed cohorts. The current-suite
comparison journey is supplemental and does not replace ordinary regression credit.

### Final inventory and coverage

| Disposition | Distinct methods |
| --- | ---: |
| Passing credit, including 28 carried methods | 1,634 |
| Original unresolved qualification failure | 1 |
| Unexecuted or interrupted without later completion | 0 |
| **Total fixed inventory** | **1,635** |

The renewed instruction to finish the inventory added all 395 remaining passes.
It introduced no new qualification failure. All methods affected by interrupted
cohorts 010, 013 and 017 later completed in fresh cohorts and are credited once.
Passing diagnostic retries do not erase the original failed method.

| Executable index | Passing / mapped |
| --- | ---: |
| P0 executable index | 78 / 78 |
| D8 | 32 / 32 |
| Process/prefix faults | 64 / 64 |
| Q1 commands | 65 / 65 |
| Legacy CLI/live/resume/apply | 91 / 91 |
| Preservation bridge | 215 / 215 |
| Reviewer-only audit/sweep | 35 / 35 |
| Simplification | 4 / 4 |
| Proposal/semantic commands | 23 / 24 |

These indexes overlap and must not be summed. All 22 P0 rows have passing evidence
for their mapped methods. That is the declared fixture coverage, not a broader
conformance or activation claim. Exact method identities, scope limits and row
joins are retained in `reconciliation.json` and `campaign-outcome.json` under
`rounds/vnext-18-9-q3-003/`. The only missing passing credit is the original native
semantic CLI method in the proposal/semantic index.

### Completed and interrupted cohorts

| Cohort | New credited passes | Elapsed | Outcome |
| --- | ---: | ---: | --- |
| batch-001 | 364 | 1817.700s | passed |
| batch-002 | 321 | 2260.326s | passed |
| batch-003 | 2 | 1979.636s | passed |
| batch-004 | 277 | 1801.852s | passed |
| batch-005 | 25 | 1098.431s | 25 passed; one unresolved failure |
| batch-006 | 37 | 4540.485s | passed |
| batch-007 | 9 | 5180.480s | passed |
| batch-008 | 40 | 1855.630s | passed |
| batch-009 | 80 | 2092.184s | passed |
| batch-010 | 0 | 1124.608s | heartbeat expiry; 32 provisional passes and one interrupted method, subsequently rerun |
| batch-011 | 33 | 1964.154s | passed |
| batch-012 | 23 | 2199.853s | passed |
| batch-013 | 0 | 964.131s | heartbeat expiry; 2 provisional passes and one interrupted method, subsequently rerun |
| batch-014 | 8 | 2124.163s | passed |
| batch-015 | 45 | 1915.807s | passed |
| batch-016 | 15 | 1944.976s | passed |
| batch-017 | 0 | 1134.891s | heartbeat expiry; 8 provisional passes and one interrupted method, subsequently rerun |
| batch-018 | 28 | 1948.105s | passed |
| batch-019 | 27 | 1802.414s | passed |
| batch-020 | 17 | 1891.404s | passed |
| batch-021 | 17 | 1959.403s | passed |
| batch-022 | 4 | 2289.030s | passed |
| batch-023 | 16 | 1973.243s | passed |
| batch-024 | 22 | 6232.320s | passed |
| batch-025 | 31 | 2189.929s | passed |
| batch-026 | 30 | 2117.220s | passed |
| batch-027 | 11 | 3791.038s | passed |
| batch-028 | 1 | 4298.066s | passed |
| batch-029 | 23 | 1944.390s | passed |
| batch-030 | 10 | 2040.428s | passed |
| batch-031 | 11 | 1932.616s | passed |
| batch-032 | 21 | 2129.221s | passed |
| batch-033 | 25 | 1894.911s | passed |
| batch-034 | 33 | 683.915s | passed |

The 31 completed cohorts total 73893.332s (approximately 20.53 hours).
This is a sum of cohort monotonic durations, not continuous campaign wall time;
it excludes the 28 carried methods, diagnostic runs and interrupted attempts.
Every completed cohort finished teardown, revalidated source hashes and exited
its supervisor. Cohort 005's passing methods receive individual credit while its
failure remains unresolved. `campaign-initial.py` and
`execution-policy-update.json` retain the explicit bookkeeping change.
Cohort 003 used existing M5 stage logging with profiling disabled. All clients
were injected/scripted clients or local fixture executables.

### Unresolved correctness failure

`test_vnext_semantic_cli.SemanticCLITests.test_three_native_roles_complete_the_normal_command_and_reentry_without_more_calls`
fails in cohort 005: the native fixture command reports a verified candidate,
but immediate read-only `status` returns `HALTED_ARTIFACT_INVALID`. The original
unittest log truncates the diagnostic difference, and the fixture was cleaned up.
No supported root cause or runtime fix has been established.

The same method passed in isolation (139.988s), after full discovery (139.956s),
and in one exact-order replay of the 26-method cohort (1125.217s). Those diagnostic
runs grant no qualification credit and do not clear the original failure. They
retained full packet observations but reproduced no failing packet. Later campaign
failures would retain full comparison operands; none occurred. No runtime source
or test assertion was changed to obtain these results.

The next correctness step is a bounded investigation that captures the failing
status reason and retains its fixture if the fault recurs, then establishes an
evidence-backed fix or explanation. Do not silently clear the failure by repetition.
If sources change, reconcile affected reruns against a new source manifest before
claiming qualification. The full unchanged inventory need not be repeated merely
because the original failure is still open.

### Interruptions and supervision evidence

Cohorts 010, 013 and 017 stopped with `heartbeat_expired`, exit 124. Their
supervisors terminated their process groups and released the worker lock. Source
hashes matched after every stop. Partial cohorts receive no credit: their 33,
three and nine affected methods subsequently completed in cohorts 011, 014 and
018, respectively. No partial cohort was relabeled as a pass.

Read-only power logs confirmed clamshell sleep at 08:12:04 +0200 on 2026-10-05
before cohort 010 stopped at wake. The cause of cohort 013's wall-clock gap remains
unconfirmed. Cohort 017 stopped at 01:55 Paris time on 2026-10-06; a bounded power-log
query returned no matching sleep event, so that stop is not attributed to sleep.

`resume-001.json` joins the operator's renewed instruction to the stopped checkpoint
and verifies its evidence/handoff hashes before resumption. After cohort 017,
`resume-002.json` records one instrumented continuation. Timestamped wall/monotonic
observations surround short waits; no power settings or supervisor limits changed.
The worker remained at 60% duty, with a 180-second lease, a 30-minute soft boundary
between methods and a two-hour hard deadline per cohort. Batches 018–034 completed
without another interruption. The timing trace contains 2,820 running-worker
checks; the largest recorded heartbeat age is 106.420s,
below the lease. The isolated delayed refresh has no established cause.
`heartbeat-summary.json` and the per-cohort observations retain the measurements.

There is no remaining inventory to restart. All supervisors have exited and the
worker lock is available. Historical checkpoint/resume receipts remain in place;
`campaign-outcome.json` is the final execution receipt, explicitly NOT a passing
qualification or release receipt. Earlier mutable failure/performance/environment
summaries are preserved under `before-execution-closeout/`.

### Performance disposition and handoff

**No performance acceptance has been granted.** The paired Q3-002 measurements
remain unchanged: four-promotion history replay at 16.767s and Phase 1 state
projection at 28.949s, improvements of 12.7% and 11.1%. One-promotion measurements
are 2.455s and 4.368s, with 8.1% and 3.4% overhead. These are two samples per arm
on one local fixture at 60% duty, with identical outputs and unchanged artifacts.
They establish neither an interactive latency SLA nor live-provider performance.

The completed inventory also records substantial whole-test costs:

| Whole-test journey | Seconds | Minutes |
| --- | ---: | ---: |
| Post-correction publication/final-state recovery and reentry | 4489.649 | 74.8 |
| Vertical consolidation, re-review and final strict convergence | 4297.808 | 71.6 |
| Native follow-up command journey | 3570.184 | 59.5 |
| Combined follow-up recovery | 3530.009 | 58.8 |
| Versioned final strict convergence | 2157.182 | 36.0 |
| Phase 2 selected-child promotion | 1817.381 | 30.3 |
| Normal follow-up/reopen | 1616.956 | 26.9 |
| Repeated semantic follow-up | 1426.076 | 23.8 |

These journeys include multiple operations, assertions and sometimes injected
faults; they are not single-command latency measurements. Exact methods and timings
are in `performance-proposal.json`. The earlier provisional suggestion to defer
all further tuning until after Q4 is not an accepted decision and must be
reconsidered against this complete evidence.

First resolve the correctness failure, then obtain an explicit decision about
accepting the measured latency limits or requiring further tuning before live
qualification. No further optimization experiment or performance waiver is implied.
Registered suites, compilation, whitespace checks, protected notes/audits and all
four empty public qualification maps are checked by `finish_execution.py` and
joined in `campaign-outcome.json`. Runtime sources remain unchanged. Q4 live soak,
public activation, external transmission/apply-back, commit and push remain deferred.

## Q3-004 — bounded native reentry investigation

The 2026-10-10 investigation starts from `c79a142`. The original Q3-003
failure remains unresolved: its log omitted the full rejection reason and its
temporary fixture was deleted. There is no evidence-backed runtime fix or
environmental explanation. Do not infer either from a passing reproduction.

Inspection covered proposal dispatch/reopening, active-round selection, seed
Reviewer request replay, proposal status, semantic request/decision/terminal
reconstruction, and D8 read/binding checks. The pinned semantic-workflow and
proposal-run contracts require read-only reentry to validate durable evidence;
no check may be bypassed to obtain a passing status. No defect was established
by this bounded inspection.

One unchanged-source instrumented reproduction passed in 140.681s (141.279s
including supervision), at 60% duty with a 180-second lease and 600-second wall
cap. Full command/status/reentry packets and an inert archive of the observed
passing fixture are under `rounds/vnext-18-9-q3-004/native-diagnostic/`.
The archive is forensic evidence, not a relocatable D8 run. No rejection was
captured. All clients were local fixture executables; no live provider was used.
This is a diagnostic observation with zero additional qualification credit.

The affected test now compares both exit code and packet for `status` and
ordinary reentry. On mismatch it retains full expected/actual packets and a
fixture archive in a `whetstone-semantic-cli-failure-*` temporary directory,
prints that location, and leaves the assertion diff untruncated. It preserves
the original assertion if fixture archival fails. Success creates no diagnostic
directory. Two focused harness tests cover capture before fixture cleanup,
both command boundaries, exit-code-only failure, archive failure and the
success path. These two tests are additions outside the frozen 1,635-method
inventory; they must not be counted as clearing its failed method.

The amended native journey and both diagnostic tests pass together: three
methods in 140.751s (141.048s including supervision), under the same limits.
`focused-check/tests.log`, `focused-check/status.json` and
`source-reconciliation.json` retain this focused verification. Only the affected
test file differs from the frozen source manifest, with the diagnostic test
module added separately. Compilation and whitespace checks pass. Both bounded
workers exited; no test worker remains active. `investigation-outcome.json`
joins the source changes, diagnostics and preserved original evidence.

The runtime, contracts, public qualification maps and original campaign evidence
remain unchanged. The next correctness step requires a captured failing
readback or another independently demonstrated cause. Further passing retries
alone cannot close the original failure. Performance acceptance and Q3 closure
remain withheld; no release waiver is inferred.

## Q3-005 — authorized final bounded cohort retest

The operator authorized one replay of the original 26-method cohort in its
original order, with improved failure capture and a 30-minute hard cap, then
requested the result for a Q3 closure decision. The run used committed source
`c9d1dae`, one worker at 60% CPU duty and a 180-second supervision lease.
No runtime, test or contract source was changed for this retest.

**All 26 methods passed: zero failures, errors or skips.** Unittest completed
in 1142.124s; the supervisor completed in 1143.193s (19 minutes 3 seconds),
below the 1800-second cap. The originally failing native method passed its
command, immediate status and ordinary reentry comparisons, with exactly one
call to each native fixture role and unchanged run files on reentry. Full
packets are retained. No failing readback occurred and no failure archive was
needed. All clients were scripted/local; no live provider was contacted.

Evidence is under `rounds/vnext-18-9-q3-005/`: `inputs.json` freezes source
hashes and joins the exact original cohort order; `events.jsonl` records every
method; `packets.jsonl` retains the native command observations; `tests.log`,
`result.json` and `status.json` establish completion. `retest-outcome.json`
joins these records, source readback, protected files and the original campaign
evidence. The supervisor exited and the worker lock is available.

This is a diagnostic pass, not a root-cause finding or a release waiver. The
original inventory remains recorded as 1,634 passes and one unresolved failure;
no additional qualification credit is granted by this retest. Do not run more
retries automatically. The result is now with the operator for explicit
correctness disposition: accept the documented residual risk or keep the gate
blocked pending a demonstrated cause. Performance acceptance remains a separate
open decision. Q3 is not closed; public activation, live qualification and
external apply-back remain deferred. Nothing was committed or pushed by this run.

## Q3-005 — operator correctness-risk acceptance

On 2026-10-11, after receiving the complete bounded cohort result, the operator
explicitly stated: “I accept the the residual correctness risk”. This accepts
the residual risk of the original Q3-003 native semantic CLI status/reentry
failure for Q3 correctness disposition. That issue no longer blocks Q3 on
correctness grounds under this acceptance.

The failure remains unexplained and unfixed. Historical evidence still records
1,634 passes and one failed method; the 26-method diagnostic retest passed but
does not rewrite that record or establish a cause. Failure capture remains in
place for any recurrence. No further automatic correctness retries are planned.

`rounds/vnext-18-9-q3-005/correctness-risk-acceptance.json` binds this decision
to the original campaign, bounded retest and tested source. Existing evidence
receipts remain unchanged. This acceptance supersedes the earlier pending
correctness-disposition statements only. Performance acceptance remains open
and is the next Q3 decision; profiling is recommended before that decision,
but no profiling or optimization run is started by this acceptance. Q3 closure,
public activation, live qualification, external apply-back, commit and push
are not authorized by this decision.

## Q3-005 — performance acceptance and Q4 handoff

After accepting the residual correctness risk, the operator stated:
“Let’s proceed to Q4. I’ll see how it goes in practice and if the performance
proves unbearable, we’ll address it”. This explicitly accepts the measured
performance for proceeding to Q4 and defers further optimization until informed
by practical use. The acceptance includes the documented 74.8- and 71.6-minute
multi-operation journeys at 60% duty; it does not establish single-command
latency or predict live-provider duration.

Together with the prior correctness-risk acceptance, this closes Q3's
disposition. The original failed method and all diagnostic observations remain
intact. No new tests, performance experiment or runtime change are implied.
`rounds/vnext-18-9-q3-005/performance-acceptance.json` joins the decision to
the correctness acceptance and completed qualification/retest receipts.

Q4 preparation is authorized. The [Q4 handoff](VNEXT_18_9_Q4_LIVE_SOAK.md)
names the concrete synthetic input package, provider/model and bounded first
run. Q4's separately authorized provider-payload boundary remains applicable;
public activation, external apply-back and push require their own decisions.
