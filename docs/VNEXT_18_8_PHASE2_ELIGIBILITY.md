# 18.8 bounded Phase 2 prerequisite inspection

Date: 2026-09-20. Starting checkpoint: `9687d1f`.

`VerifiedRun.phase2_eligibility()` now checks the Phase 1 side of the Phase 2
handoff against current verified lineage. It returns exact pointer, draft, identity
map and immutable review-configuration references, independently of the latest
registered candidate. This is a separately pinned internal, read-only consumer.

**Phase 2 entry remains unavailable.** The existing `review-configuration-v1` has
Phase 1 profiles and role identities but no Phase 2 target, rubric manifest or
profile budgets. The new result therefore separates `phase1_prerequisites_met`
from `entry_permitted`, and always reports `phase2_configuration_unbound` and
`phase2_execution_unavailable`. Cached convergence settings and legacy defaults
cannot supply an immutable Phase 2 binding. No positive Phase 2 permission is
claimed by this slice; all four 18.8 tasks remain incomplete.

## Implemented checks

The [consumer](../src/whetstone/vnext_verified_phase2_eligibility.py) follows the
[scheduler D7 rules](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#vnext-candidate-processing-d7)
and the candidate leaf's current-pointer/map authority. The
[algorithm](../contracts/algorithms/vnext_verified_phase2_eligibility_v1.md) requires
the existing Phase 1 operator and closeout contracts plus its own pin.

- Prove current lineage and map first; preserve missing-mirror and orphan recovery
  precedence. Inspection does not repair either.
- Expose the latest candidate's actual decision. Prepared or unfinished decisions,
  unresolved operator choices, final rejection and verified-but-unpromoted candidates
  prevent Phase 1 readiness. Report bound outstanding decision IDs without choosing
  an answer. Historical rejection alone does not substitute for the latest decision.
- Require complete current-pointer clean-profile coverage and global acceptance.
  Promotion alone does not discharge review debt. Outside-focus major findings and
  exhausted budgets cannot qualify the draft.
- Require the reproduced closeout report and evidence commit, followed by a matching
  derived state reference. Report-only prefixes and stale cached success fail this
  prerequisite. Damaged current evidence refuses without fallback.
- Return detached observations without a writer lock, client call, new ordinal,
  version/history/declaration write, or any other run mutation.

Read-only correspondence is not proof that an earlier durability acknowledgement
succeeded. A future mutating entry owner must reacquire the actual fence and replay
source, closeout and state barriers against the then-current pointer. An inspection
result is not a durable admission ticket.

## Validation and limits

All **33 methods passed on their first runs, with no skips or fixes**: eight new
prerequisite methods in 121.381 seconds and 25 regressions in 293.600 seconds.
The recorded source snapshot remained unchanged throughout both invocations.

Results and exact method identities are recorded in the
[audit record](audits/VNEXT_18_8_PHASE2_ELIGIBILITY.json); raw logs and the source
snapshot are under ignored `rounds/vnext-18-8-phase2-eligibility-001/`.

New tests exercise multi-profile seed completion; incomplete closeout/state;
global non-focus debt; genuine registration, verification and promotion followed
by fresh review; a real bound semantic operator question and final rejection;
post-promotion budget exhaustion; interrupted review; stale success; corrupted map
and closeout/report; mirror/orphan precedence; unsupported vertical review; missing
consumer pin; read-only operation and detached references. Existing operator,
closeout and V review methods form the regression cohort.

The tests use scripted clients and process-local suites on macOS/APFS. This is not
full product, physical power-loss, live-provider or consuming-release qualification.
Prepared-decision and rejected-parent/promoted-child compositions reuse established
journal rules but are not exhaustively covered by this new cohort. The new API is
not wired into public CLI status or the legacy Phase 2 executor. Legacy/bridge
runtime bytes, shipping maps and frozen suite bytes remain unchanged.

## Handoff

Next bounded slice: define and validate an immutable **Phase 2 configuration and
entry-request binding** to the job, current pointer and Phase 1 closeout. Bind the
target, rubric evidence, profile order/budgets and role identities explicitly;
reject stale/cross-job requests and unsupported settings without reading defaults
from mutable state. This is the missing admission prerequisite discovered here.
Preserve the current frozen review schema rather than extending it in place.

Then implement the fenced entry owner and its recovery boundaries before any
Phase 2 execution. Version maintenance must pass the V candidate protocol; the
legacy stamping exception cannot alter verified bytes. Phase 2 review/candidate
routing, convergence and declaration remain subsequent work.

Other 18.8 work remains: focused/vertical/retry/resume/budget-extension consumers,
version/history lifecycle, strop/readback eligibility and complete terminal/operator
paths. Public activation still requires the deferred 18.9 gates. No external
transmission, push, external specification apply-back or 18.9 implementation occurred.
