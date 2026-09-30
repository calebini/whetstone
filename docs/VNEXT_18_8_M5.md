# M5 integrated acceptance

Started from local M4 checkpoint `72498e5` on 2026-09-29 after the user requested
M5. Status: **in progress; expensive campaigns interrupted for CPU load on 2026-09-30; no 18.8 completion claim**. The unrelated notes edit is
preserved. This campaign uses scripted clients and disposable bound sources;
public activation, normative edits, real specification apply-back and push remain
deferred. The user subsequently authorized this local partial checkpoint.

## Fixed delivery boundary

One acceptance bundle joins the existing internal M1–M4 owners. Correct concrete
integration failures in this bundle; do not introduce a new product policy or
expand unsupported workflow/authority. The original A–D requirements remain the
completion authority. The supported matrix must distinguish implemented internal
routes from advertised public modes and from unqualified cross-products.

| Requirement | Campaign and evidence to reconcile |
| --- | --- |
| A — Scheduler integration | Standard horizontal and vertical Phase 1 promotion, explicit budget extension, retained exhausted history, Phase 2 entry and convergence; focused completion remains bounded; technical continuation preserves original allowances |
| B — Verified lifecycle | Joined system entry `0.17 → 1.0`, verified correction `1.0 → 1.1`, resolution, timeout/failure, explicit continuation, declaration and convergence; no extra version stamp or authority change |
| C — Strop/readback | Joined versioned and unversioned convergence through exact fixture apply; uncertain receipt recovers without rewriting; source binding, approval, old closeout fields and existing legacy/bridge checks preserved |
| D — Terminal/operator evidence | Current authority, latest candidate, retained rejection/orphan/failure, decisions and exact supported gates; existing operator choice, freeze, gap acceptance, target and failure regression cases |

**M5-I1** requires a completed verdict for the joined two-promotion interruption
case on frozen sources. Prior stopped M3 diagnostics remain unpassed historical
evidence. **M5-P1** requires stage measurements and profiling of history replay
at increasing history size. Profile first; any optimization must preserve all
fresh source, contract, descriptor, pointer and ownership barriers. Report cost
limits explicitly; there is no ratified throughput target or performance waiver.

## Authority and scope

The candidate leaf's Safe Terminal Semantics and Ratification Delta Map, D7 in
the scheduler, D8 local storage, and the M1–M4 user decisions control this work.
The M3 metadata-operation and M4 source-write policies are approved internal
contracts. Coordinated normative publication remains separate. Shipping suites
and public selectors stay unchanged. Original A–D checkboxes must not be closed
where broader normative or supported-route requirements remain unmet.

Default evidence directory: `rounds/vnext-18-8-m5-acceptance-001/`. Commands,
source hashes, exact test verdicts, stage measurements and profiles will be
indexed in a tracked audit at closeout. Tests may record measurements through
`WHETSTONE_M5_EVIDENCE`; instrumentation grants no runtime capability.

## Supported internal matrix

| Axis | Implemented/selected scope | Retained boundary |
| --- | --- | --- |
| Mode | Explicit test-suite pins for `verified_promotion`; reviewer-only compatibility checked separately | No public P/V activation, installed-file negotiation, legacy-root conversion or bridge authority import |
| Phase 1 routes | Standard horizontal, selected focused profile, standard vertical; appended budget grants | Focused stability is not full Phase 1 acceptance and cannot enter Phase 2 |
| Phase 2 routes | Standard/stateful-system, fixed exact builtin standard-v1 rubric; horizontal/vertical handoff | No custom/MVP/governance workflow expansion, role replacement or rubric rebinding |
| Targets | Mid/final × permissive/strict on the horizontal target consumer; joined vertical route uses final/strict | This is not a target × route × fault cross-product claim |
| Version | Unversioned route; numeric M3 maintenance through verified candidates; system entry and post-entry correction | Unsupported metadata/topology refuses; no legacy stamping bypass |
| Operator | Exact choice/answer, narrower semantic repair, draft-bound gap acceptance, retained source debt | Freeze remains blocked with report recovery only; unchanged valid declaration disagreement is unresolved, not automatic re-review |
| Continuation | Published Reviewer/Editor/Verifier technical gates and retained-output recovery | No generic Phase 2 resume, retry reset or automatic repair after final rejection |
| Source | M4 exact approved descriptor-bound local source, one same-filesystem APFS file | Exclusive external access is required; no cross-root writer exclusion or real source permission is inferred |

## Ratification-delta reconciliation

| Normative owner/dependency | M5 disposition |
| --- | --- |
| Coordinating admission and public capability negotiation | Internal suite pins and existing public refusal retained; new-root/public activation gate remains 18.9 |
| Scheduler D7 lineage, retry, budget and resume | Existing owners exercised through joined campaigns and selected refusal/recovery checks; unsupported gates remain unavailable |
| Candidate/artifact registration, verification, promotion and D8 | Genuine creation/decision/promotion journals used; orphan/prepared-output recovery checked; exhaustive process/persistence qualification remains 18.9 |
| Scope/decision authority | Explicit choices and selected follow-ups retain original debt and candidate finality; no new product choice supplied by tests |
| Phase 2 declaration/convergence lineage | Every joined completion consumes current verified bytes, configured rubric and current review evidence; non-converged or unresolved work cannot gain source eligibility |
| Scheduler metadata operation | M3 internal decision ratified 2026-09-29; normative publication not performed |
| Scheduler source-write lifecycle | M4 six-rule internal decision ratified 2026-09-29; normative publication not performed |
| Operator defaults, documentation and release suite | Internal handoff documents exact operations; public defaults and frozen suites unchanged; coordinating publication/qualification is deferred |

The original A–D requirements will receive a final scoped disposition after
actual verdicts. A successful campaign does not itself amend the normative family
or close the candidate leaf's complete public-activation ratification checklist.

## Interruption and CPU recovery — 2026-09-30

The user reported that the chat had stopped while the CPU remained hot. Process
inspection identified three task-owned Python workers at 97.9%, 99.4% and 99.8%
CPU, running for about 16–18 minutes. All three received SIGINT; a subsequent
process check confirmed their exit. Their logs and profiles are retained. These
interruptions are not assertion failures and receive no whole-run pass credit.

Completed evidence so far:

- 30 compatibility/retained-output recovery methods passed in 263.076 seconds.
- The new horizontal **and** vertical extended-route journey passed in 1021.500
  seconds, including promotion, preserved Phase 1 exhaustion history, Phase 2
  convergence, exact apply-back and reopened readback.
- One operator-answer/promotion method passed before the matrix's second method
  was interrupted. This is an individual verdict, not a passing matrix run.

M5-I1 remains unpassed: the joined test completed system entry and the second
promotion, then was stopped during profiling before its timeout/continuation,
convergence and apply-back stages. The longer-history test completed three
versioned promotions and was interrupted during its fourth; it has no final
verdict. Do not repeat the previous mistake of crediting partial stage progress
as acceptance.

The retained two-promotion history profile took 64.285 seconds under cProfile,
with 196 Phase 1 closeout evaluations, 197 seed/suite reconstructions and 83
system-entry input reconstructions. The comparable one-promotion baseline took
7.616 seconds with 28 closeout evaluations and 29 suite reconstructions. Profiled
and overlapping-run times are diagnostic, not a production latency benchmark.
The first three longer-history promotion stages took 33.386, 123.479 and 286.874
seconds. No performance acceptance or waiver is inferred from those values.

## Execution controls for continuation

Use `tests/m5_bounded_runner.py` for any further expensive cohort. It holds a
single-worker lock at `rounds/.m5-test-owner.lock`, starts a separate process
group, alternates running/paused periods with a default 50% duty cycle, and
terminates the group on a five-minute wall deadline or stale 90-second heartbeat.
Refresh `OUTPUT/heartbeat` only while actively supervising; never launch an
independent heartbeat daemon. If the chat stops, the lease expires. The deadline
and duty fraction are execution limits, not product performance requirements.
Descendant groups deliberately detached by arbitrary commands and SIGKILL of the
supervisor are outside this small developer harness's guarantees.

Example (one selected acceptance method, no live providers):

```sh
PYTHONPATH=src:tests python3 tests/m5_bounded_runner.py \
  --output rounds/vnext-18-8-m5-acceptance-001/bounded-targets \
  --wall-seconds 300 --lease-seconds 90 --duty 0.5 -- \
  python3 -m unittest -v \
  test_vnext_verified_phase2_targets.TargetRuntimeTests.test_clean_targets_complete_with_current_declaration_and_required_profiles
```

The next corrective investigation is repeated immutable prerequisite replay,
particularly `vnext_version_entry.inputs`, `binding_at`, and Reviewer seed
revalidation. Any reuse must remain local to one proven invocation, retain
fresh input/contract/descriptor/pointer checks, isolate mutable return values,
and preserve source and ownership barriers around clients and publication.
Do not cache live permission or bypass a validation merely to obtain a pass.
The expensive joined/four-promotion campaigns must not be relaunched blindly;
first establish a bounded correction or a deliberate performance disposition.

The supervised four-target check subsequently **passed** in 210.944 seconds
(211.695 seconds including supervision), with measured worker CPU near 46%.
The supervisor exited cleanly. This adds one distinct product method, covering
all four target combinations as subcases, for **33 distinct product methods**:
32 in completed cohorts and one individual verdict from the interrupted matrix.
The three supervisor checks are counted separately. They cover normal completion,
busy ownership, heartbeat/deadline reclamation of a paused worker, and descendant
cleanup. No product runtime code changed and no performance correction is
claimed by introducing the execution harness.

M5 remains incomplete. The immediate work is a bounded replay correction with
fresh-byte/source-barrier tests, followed by the interrupted joined case and
remaining matrix methods under supervision. Neither M5-I1 nor M5-P1 is closed;
the original A–D checkboxes remain open. The user authorized a local checkpoint of these tests, controls and incomplete
evidence, followed by continued M5 work. This checkpoint does not complete M5.
