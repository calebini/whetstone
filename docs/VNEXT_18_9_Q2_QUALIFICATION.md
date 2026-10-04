# Q2 qualification gaps

Started from Q1 closure checkpoint `47cdf33`; the first Q2 package was committed
at `a0d3a4d`. **Six of the seven named gaps now have focused executable coverage.
P0-13 has approved scope but remains unimplemented and unverified.** Q2 is
incomplete. Its finish line is the seven named P0 gaps in the [finite inventory](VNEXT_18_9_INVENTORY.md),
plus positive simplification. This work does not activate a mode, amend normative
specifications, optimize replay, run the Q3 full campaign, call real providers,
write back to external specifications or push. The operator authorized a local
checkpoint of the verified work and both remaining scope decisions.

## Fixed inventory

| Requirement | Work and current boundary |
| --- | --- |
| P0-01: six-section destructive replacement | Joined scripted Editor request, actual registration, deterministic rejection and no-promotion/current-pointer/mirror assertions. Complete within this fixture scope; final recheck passes. |
| P0-02: unrelated enum/table loss | Separate schema enum-member and table-row removal cases assert the exact removed inventory IDs, final rejection, zero Verifier calls and unchanged authority. Complete within this fixture scope; final recheck passes. |
| P0-03: forbidden compatibility | Prospective mutable target, older implementation context and a blocking lexical invariant. Five explicit compatibility identifiers (`legacy`, `transition`, `adapter`, `migration`, `dual-model`) are rejected before semantic verification. This tests exact lexical assertions, not universal detection of compatibility semantics in prose. Complete within this fixture scope; final recheck passes. |
| P0-05: three fixes plus regression | Three resolved findings plus one unrelated report regression must receive a final semantic rejection. A separately admitted transaction on the unchanged immutable base omits the offending operation, fully reassembles and reverifies, and alone promotes once. Rejected evidence remains unchanged; final recheck passes. |
| P0-07: token/time stop | The candidate spec defines persistence outcomes before/after registration, but no public run-wide token/time accounting contract was found. The operator approved qualifying caller-owned stops at those boundaries, without adding built-in accounting controls. Five methods now cover token/time stops around registration and semantic invocation, orphan/latest selection, unchanged authority, apply-back ineligibility and explicit recovery/continuation. Complete within this caller-stop fixture scope; verification is recorded below. Retry slots and profile extensions are not substitutes. |
| P0-12: historical recurrence | Exact original draft pair frozen and replayed with the three evidence boundaries below: original metadata refusal under the current suite, exact loss replay under pinned v2, and body-identical M3 metadata adaptation under the current suite. All three pass. No raw historical acceptance under M3 is claimed. |
| P0-13: independent implementations | The operator approved the inventory's bounded independent reference for assembly, maps, candidate hashes and persisted selection/disposition. Implementation and comparison remain outstanding. No second scheduler, production imports, golden-output lookup or second execution of the production implementation may stand in for an independent implementation. |
| S-01: valid simplification | Many-to-one normative correspondence passes deterministic and scripted semantic verification, then promotes to a shorter draft. Promotion before verification is refused; final recheck passes. |

## Fixture and authority boundaries

The four negative compositions, simplification control and derived historical
companion use the exact offline `vnext-verified-consumer-1` manifest and its
registered algorithm versions. The exact raw historical loss replay separately
pins the existing v2 assembler in a private test suite, as explained below. They supply frozen fictional
Reviewer findings and explicit test admission, then use the actual D8 storage,
Editor request journal, candidate registration, deterministic validation,
semantic request/decision, and promotion owners. They are not new public-command
journeys or live semantic judgments. Production qualification maps remain empty.

The negative cases introduce no runtime feature or policy change. The initial
fixture corrections are retained as failed attempts: prompt targets carry content
rather than heading metadata; enum loss uses the supported JSON-schema inventory
syntax; lexical assertions inspect identifier facts rather than arbitrary prose;
operation attribution must match each admitted section slice. The positive and
negative cases use the existing contracts instead of relaxing these boundaries.

## Historical recurrence provenance

The source is the sibling Spine workspace's
`whetstone_runs/recurrence-flex-synthesis-005/rounds/round-1`:

- `draft_before.md`: 99,006 bytes,
  `3bed5964554f7213a34f4d0da11903c414691250ee5fe72d45c81b4097637853`.
- `draft_after.md`: 44,844 bytes,
  `051ca84cfc7e99c59bd2f0e1cd56a475dfea036af546006ef94f3bdadc4142a1`.

The original Editor summary names those hashes, contains the exact after text,
and claims three resolved issues. The after text omits sections 7, 9, 10, 11 and
12. The checked-in fixture contains only the exact draft pair and compact
provenance, without telemetry, prompt logs or private machine paths. No source
text was changed, scrubbed into different semantics or reconstructed from memory.
The earlier `recurrence-flex-synthesis-001` run was inspected but is not the
identified destructive case.

The old response is a full draft, while vNext accepts patch proposals. The test
therefore derives exact changed top-level subtree/body payloads and explicit
missing-section deletions. Before submission it proves that those edits reproduce
the golden after bytes exactly. The attempted deletions have no operator grant;
rejection at patch admission is the required safe result, before a candidate or
promotion exists. This is not a claim of a registered historical candidate or an
old-protocol runtime replay.

The original `Status: Draft v0.3.1-manual-synthesis-005` label contains two
numeric labels under the current M3 contract. The exact current consumer refuses
that seed before Editor invocation; the test preserves this behavior. A separate
loss-specific replay uses the existing pinned v2 assembler, which predates M3.
That v2 result alone is not current-consumer qualification.

A third, explicitly derived companion keeps every body byte unchanged and replaces
only the copied third-line status with `Status: Draft v0.3.1` in both drafts. This
strips the run suffix and leaves any next version stamp to the current M3 owner.
Its patch-intent translation reproduces those derived bytes exactly and must
reject the same unauthorized deletions under the current v3 consuming suite. The
original checked-in golden files remain untouched. This fixture adaptation does
not authorize changing the external Spine source or broadening version parsing.

## Approved scope and remaining work

The operator accepted both recommendations before checkpoint `a0d3a4d`:

1. P0-07: caller-owned token/time stop fixtures before and after registration.
   Implemented in the subsequent pass below, without public accounting controls.
2. P0-13: an independent reference for candidate assembly, maps and hashes, plus
   persisted selection/disposition, compared against the production implementation
   on the same inputs. It must not import production Whetstone code, substitute
   golden-output lookup, rerun the same implementation or add a second scheduler.

P0-13 is now the only remaining Q2 implementation area. Its approved scope still
requires executable comparison and verification before Q2 can close.

## First package verification (checkpoint `a0d3a4d`)

Evidence and failed attempts are retained in `rounds/vnext-18-9-q2-001/`.
Verification runs one supervised worker at 60% duty with a wall deadline and
heartbeat lease. **47 distinct methods pass**, including eight new Q2 methods.

- `final-checks`: 46 methods pass in 184.232s (184.514s supervised wall time).
  This includes all five joined negative/positive methods, the two original
  historical methods, and 39 existing validation/inventory/semantic-policy methods.
- `historical-final`: all three historical methods pass in 12.409s (12.805s
  supervised). This reruns the two existing methods and covers the newly added
  M3 metadata companion. The overlap is counted once.

`verification.json` records exact commands, method identities, log/status hashes,
source cohorts, platform/Python, suite digests and limits. Earlier failed attempts
remain retained and add no passing credit. In addition to the fixture corrections
above, the three-fix case initially read the base hash from the creation event
instead of its preservation report; the historical synthetic claim initially
triggered the correct sensitive-finding stop. Neither required a production fix.

Targeted compilation, `git diff --check` and both offline suite validations pass.
All four production qualification maps remain empty. At the pre-checkpoint
verification snapshot, all workers had exited, the bounded-worker lock was
available, HEAD was `47cdf33`, and the index was empty. Production code, contracts,
normative specs and existing tests retained their baseline hashes. The subsequent
local checkpoint is authorized; no push is authorized by this request. The
existing notes and both Q1 audit reports remain protected and uncommitted.

## P0-07 caller-owned budget stops

The next pass adds [five focused methods](../tests/test_vnext_q2_budget_stops.py)
covering eight scenarios on the exact offline `vnext-verified-consumer-1` suite:

- A token stop immediately before the creation event preserves an earlier rejected
  candidate as latest; the new complete orphan recovers once at the next ordinal.
- A time stop at the same boundary with no predecessor leaves latest empty and
  recovers once at ordinal 1.
- Token and time stops after candidate bytes but before the full registration
  package leave an incomplete orphan. Recovery refuses and preserves every byte.
- Token and time stops after registration prevent Verifier invocation. Fresh-store
  reentry selects the registered candidate as unverified, without a decision.
- Token and time stops at semantic invocation preserve the initial nonfinal
  deterministic decision and the interrupted request. Ordinary reentry does not
  invoke the Verifier; explicit continuation completes verification once and
  preserves the original decision.

Each boundary reopens the persisted run, checks the real registered/effective
state, preserves the current pointer and `spec.md`, refuses promotion, and finds
apply-back ineligible through the real read-only review owner. The source is a
bound disposable temporary file and remains unchanged. Complete-orphan recovery
writes only its missing creation event and invokes no clients. Verification after
an explicit new caller budget does not itself promote. No public qualification
map is patched or activated.

The test-only budget uses a finite token counter and deterministic clock. It
models cooperative caller cancellation at a checkpoint, including cancellation
before the provider receives a claimed request. It does not measure provider
usage, implement public run-wide accounting, introduce a terminal state, or claim
asynchronous process-kill coverage. Existing D8/process qualification remains Q3.
The only shared-fixture change adds optional temporary source binding; no runtime,
contract or normative specification changes were needed.

Evidence is in `rounds/vnext-18-9-q2-002/`. The initial failed attempts are retained:
the promotion API raises on an orphan rather than returning a recovery status,
and the first cancellation wrapper omitted the pinned transport/actor interface.
The corrected fixture cancels through the existing Verifier's method, retaining
its identity. These failures add no passing credit and required no runtime fixes.
**34 distinct methods pass**, including all five new methods. Both cohorts run
serially through the bounded supervisor at 60% duty with heartbeat leases:

- `budget-recheck`: four new methods pass in 211.536s (212.097s supervised).
- `regression`: 30 methods pass in 218.185s (218.715s supervised): the new
  partial-orphan method, all eight previous Q2 methods and 21 registration methods.

There is no overlap between these two credited cohorts. `verification.json`
records commands, method identities, tested-source/log/status hashes and suite
pins. Targeted compilation, `git diff --check` and both offline suite validations
pass. All four qualification maps remain empty; workers have exited and the
bounded-worker lock is available. Runtime, contracts, normative specs and existing
non-Q2 tests retain their baseline hashes. This pass remains uncommitted with an
empty index; no push was performed. The existing notes and two Q1 audit reports
remain unchanged and uncommitted.

Q2 cannot be declared complete while P0-13 implementation or any required
verification remain outstanding. Q3 still owns final consuming-release regression,
P0/D8/process/CLI qualification and the replay performance disposition. Q4 still
owns separately authorized live soak and activation.
