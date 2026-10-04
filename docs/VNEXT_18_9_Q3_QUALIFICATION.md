# Q3 — replay performance and deterministic qualification

Status: **started; release qualification remains open.** The user authorized
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
