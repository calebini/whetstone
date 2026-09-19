# 18.5–18.7 reconciliation and checkpoint handoff

Date: 2026-09-14–15. Starting commit: `c726422`.

18.8 closeout follow-up (2026-09-20): [global acceptance and immutable Phase 1 terminal publication](VNEXT_18_8_PHASE1_CLOSEOUT.md) now follow the bounded status view. Complete current-pointer profile coverage and zero global major/blocker debt are required for acceptance; publication binds source receipts and replays durability barriers without clients or new ordinals. All four 18.8 tasks remain incomplete. Operator status/run-state integration is next; Phase 2, public activation, push and external apply-back remain outside this slice.

18.8 follow-on (2026-09-20): the user has authorized beginning the next implementation area. The [first bounded status slice](VNEXT_18_8_PHASE1_STATUS.md) exposes current-verified-pointer-bound profile budgets and cleanliness alongside recovery/promotion precedence. All four 18.8 tasks remain incomplete; accepted-draft evaluation and Phase 1 terminal closeout are next. The 18.5–18.7 checkpoints below remain historical evidence, not a claim that this new source was part of their earlier runs. Public activation, pushing and external apply-back remain excluded.

Current 18.6/G3 closeout (2026-09-19): the [18.6 acceptance map](VNEXT_18_6_ACCEPTANCE_MAP.md) validates its three bounded implementation tasks with 171 distinct retained passing methods (140 original individual passes and 31 current G2 passes). All 145 carried Python dependencies match their validated bytes; no runtime tests or code changes were needed. Two historical records have duplicated method-name suffixes, explicitly reconciled against raw logs without rewriting history. All nine bounded 18.5–18.7 implementation tasks and G3 are now validated. Overall release qualification remains open. The next implementation area is 18.8 scheduler/Phase 2/apply-back integration, outside the current scope; 18.9 consuming-suite/P0/compatibility/soak/activation gates also remain. No generic acceptance/fault rerun is pending. Earlier dated incomplete-task and next-action statements below are historical.

Current 18.5 closeout (2026-09-19): the [bounded acceptance map](VNEXT_18_5_ACCEPTANCE_MAP.md) validates all three 18.5 implementation tasks using 302 distinct retained passing methods (236 original individual passes, 13 corrected stored-run passes and 53 current G2 storage/registry passes). No runtime tests or code changes were required. The source-dependency comparison and retained-log checks support reuse; the original regression remains recorded as a two-failure run. G3’s 18.5 portion is closed. Next is the separate 18.6 semantic/follow-up acceptance reconciliation; no generic 18.5/storage fault batch is pending. Public release qualification remains open, all shipping maps remain empty, and earlier dated status/next-action text below is historical.

Current G2 checkpoint (2026-09-18): the [fixed evidence refresh](VNEXT_G2_VALIDATION.md) passes all 97 existing methods (eight runtime and 89 component) on unchanged source, with no skips or fixes. Combined with 84 distinct carried methods, the 18.7 acceptance map has 181 current-source passing methods; this is not a full-suite run. G1, G2 and the representative Batch C inventory/current-source refresh are closed. The three 18.7 implementation tasks below are checked only at the isolated component/runtime boundary. Overall 18.7 dependency and consuming-release qualification remain incomplete. Next is G3's 18.5 acceptance reconciliation, followed separately by 18.6; no further generic storage fault batch is scheduled. Earlier next-action and missing-proof statements below retain their historical scope.

Current G1 checkpoint (2026-09-18): [joint concurrent selection](VNEXT_CONCURRENT_SELECTION.md) passes both caller lock-winner orders with two genuinely registered, final verified candidates on the same base. The higher creation ordinal is promoted exactly once; the contender is busy without writes, then fresh reentry cannot promote the older candidate. One new parameterized method and 18 promotion/Batch A regressions pass (19 distinct methods); runtime/contracts are unchanged from `64533a4`. G1 is closed at this component/process scope. Current-source passing evidence now covers 84 distinct methods, accounting for overlaps. Next is G2's fixed 97-method refresh: eight runtime and 89 component tests, crediting the two Batch A methods already rerun. 18.7 remains incomplete; earlier-slice dependencies and later release gates remain separate. Earlier G1 next-action statements below are superseded.

Current acceptance reconciliation (2026-09-18): the [18.7 acceptance map](VNEXT_18_7_ACCEPTANCE_MAP.md) closes the representative Batch C boundary inventory and identifies one missing joint P0 fixture: two final verified candidates, no prepared intent, and two competing promotion callers must select the highest creation ordinal regardless of lock winner. Next is that bounded test, followed by a fixed existing-test evidence refresh (ten runtime methods and 89 component methods, crediting identical-source overlap). The 81 distinct current-source passing methods remain separately scoped; no runtime tests were run for this reconciliation. D8 design/audit is closed. 18.7 and earlier-slice dependency/release qualification remain incomplete; later 18.8–18.9 work is excluded. Earlier open-ended Batch C and acceptance-consolidation next steps below are superseded.

Current checkpoint on 2026-09-18: [representative runtime publication prefixes](VNEXT_RUNTIME_PUBLICATION_PREFIXES.md) passes all three journeys above a committed promotion: incomplete registration refuses without inventing artifacts; final candidate-pointer acknowledgement loss requires successful synchronization before global promotion; and an intent-only interruption reuses its original claimant/timestamp. The candidate-pointer journey includes a second failed synchronization before successful recovery. No runtime or contract change was required from `250ec93`. The finite three-item representative gap list is now exercised. Next: consolidate the 18.7 acceptance map against the accumulated evidence and identify exact remaining consuming requirements. Batch C evidence reconciliation, consuming qualification and 18.5–18.7 completion remain open. Earlier three-gap next-step statements below are superseded for these exact cases.

Current checkpoint on 2026-09-18: [nonempty canonical round decision references](VNEXT_RUNTIME_DECISION_REFERENCES.md) now pass two replay-flush faults and five refusal cases in two test methods (12.936 seconds). Request/response replay failures poison ownership before round publication; fresh admission recovers exactly, preserving the original Reviewer and named-unit grant with no extra clients. Missing/altered evidence and mid-replay response drift refuse. No runtime or contract change was needed from `c6e5929`. Next: resolve representative runtime early-registration, candidate-pointer acknowledgement and early-promotion-preparation proofs against the existing component matrices. Consuming qualification and Batch C/18.5–18.7 remain incomplete. Earlier nonempty-decision absence and next-step statements below are superseded for this seed-base, single-decision scope.

Current checkpoint on 2026-09-18: [publication/operator boundary reconciliation](VNEXT_18_7_BOUNDARY_RECONCILIATION.md) found and corrected a final-state durability gap: matching visible mirrors could bypass synchronization after an uncertain final flush. Mutating work/operator/Reviewer and promotion owners now synchronize exact authority/mirrors under their existing fence before proceeding. Read-only status and separate mismatch repair remain unchanged. Two new tests cover final-state reentry and runtime receipt/selection uncertainty; all 76 distinct targeted tests pass, including affected consumer regressions. The original failing reproduction remains retained. Next is nonempty decision-reference synchronization through canonical round admission, followed by resolving the three narrower runtime publication proofs in the reconciled table. Batch C and 18.5–18.7 remain incomplete; full consuming qualification is open. Earlier runtime-unchanged and next-step statements below apply only to their historical checkpoints.

Current checkpoint on 2026-09-17: [Batch C runtime mirror uncertainty](VNEXT_RUNTIME_FAULTS_BATCH_C_MIRROR_UNCERTAINTY.md) passes one runtime journey with two sequential primitive-level flush failures. A failure after spec replacement and a subsequent matching-spec synchronization failure both propagate typed uncertainty and poison ownership before lock-context cleanup. Fresh-owner recovery preserves committed promotion 2, synchronizes the visible spec and writes only the remaining draft/state, without client calls. No runtime change was needed. Next: reconcile remaining publication-prefix/operator/dependency coverage, including the untested runtime case where an uncertain final state write leaves all mirrors visibly matching. Batch C, complete consuming-suite qualification and 18.5–18.7 remain incomplete. No authorization blocker exists for these local scripted tests. Earlier next-step statements below are historical.

Current checkpoint on 2026-09-17: [Batch C Verifier interruption](VNEXT_RUNTIME_FAULTS_BATCH_C_VERIFIER.md) passes both actual process-death cases around raw-response publication (one parameterized test), with no runtime change. A missing response consumes its invocation slot and needs an explicit bounded retry; retained raw completes without another Verifier call. Recovery finalizes only the candidate and preserves global authority at promotion 1. Next is one bounded runtime mirror-uncertainty case, then reconciliation of the finer publication-prefix coverage. Complete consuming-suite qualification remains open; Batch C and 18.5–18.7 are incomplete. No current authorization blocker exists for these local scripted tests. Earlier dated next-step statements below are historical and superseded by this paragraph.

Latest qualification checkpoint on 2026-09-17: [bounded Batch C lock handoff and partial mirrors](VNEXT_RUNTIME_FAULTS_BATCH_C.md) passes three process cases in two test methods with no runtime change from `c9d3409`. A paused, normally released promoter correctly observes a later ordinal-3 promotion; its released token cannot write. Killed partial-mirror writers retain committed authority and recover only remaining targets, without extra client calls. Remaining Batch C boundaries, actual Verifier death, finer publication-prefix mapping and consuming-suite qualification stay open. 18.7 is incomplete.

Latest implementation/qualification checkpoint on 2026-09-17: [18.7 Batch B](VNEXT_RUNTIME_FAULTS_BATCH_B.md) adds four fault cases in three passing test methods and fixes registration recovery after earlier semantic evidence. Committed decisions are revalidated through their bounded historical prefixes before reconciling the pending orphan; live semantic admission guards remain intact. All 25 affected live-work/history regressions pass as well (28 distinct tests on corrected source). The initial hook failures and real registration error are retained separately. Next is bounded Batch C: normal promotion-lock handoff and partial-mirror process death, then remaining fault-prefix reconciliation. Actual Verifier death and complete consuming-suite qualification remain open; 18.7 is incomplete.

Latest qualification checkpoint on 2026-09-16: [18.7 Batch A runtime promotion faults](VNEXT_RUNTIME_FAULTS_BATCH_A.md) passes three fault cases in two test methods (312.819 seconds): killed runtime writer before/after second pointer rename, competing-owner exclusion, and actual adapter uncertainty classification/ownership poisoning followed by fresh runtime recovery. No runtime fix was required. Next is Batch B: killed Reviewer around durable raw output and canonical-runtime registration/verification recovery precedence. Complete fault-boundary and consuming-suite qualification remain open; 18.7 is incomplete.

Latest assessment on 2026-09-15: the [18.7 fault coverage inventory](VNEXT_18_7_FAULT_COVERAGE.md) distinguishes existing component/process tests from uncovered canonical-runtime interruption cases. All 29 inspected retained-log digests and counts match; historical source differences remain explicit. No runtime tests or runtime changes were made for this assessment. Next is its bounded Batch A: process death around the second promotion commit, cross-role ownership exclusion and typed uncertain-write recovery. 18.7 remains incomplete.

Latest qualification checkpoint on 2026-09-15: [runtime operator follow-up and second promotion](VNEXT_RUNTIME_FOLLOWUP.md) adds four passing integration tests over unchanged runtime/contract bytes from `95c75b2`. The representative same-round child and two-promotion journey now uses production round and promotion publishers, preserves rejected evidence and exact client counts, and passes fresh-process readback plus selected recovery/refusal checks. Complete fault-boundary/process qualification and the remaining 18.5–18.7 acceptance map remain open; no slice or mode is activated.

Latest implementation checkpoint on 2026-09-15: the [bounded 18.7 V Reviewer integration](VNEXT_VERIFIED_REVIEW_INTEGRATION.md) adds standard horizontal review selection over exact committed bases and production canonical round publication. It extends the earlier staged-only boundary behind a separate unactivated contract pin. Historical statements below that these components are absent are superseded for this bounded path. 18.5–18.7 and consuming-release qualification remain incomplete. The linked checkpoint records validation and the remaining same-round follow-up/multiple-promotion integration work.

Current status after the authorized recheck on 2026-09-15: **D8 design ratification and bounded design-audit closure are complete**. The [focused recheck](audits/VNEXT_D8.md#correction-recheck-passed) of correction checkpoint `553300c` passed with zero findings and `boundary_preserved: true`. The 65 prior focused tests remain passing evidence; no runtime tests were rerun for this audit. **18.5–18.7 remain incomplete**, consuming-suite qualification remains open, and shipping qualification maps remain empty. Next bounded implementation target: the normal V Reviewer sequence and canonical round admission/publication against committed promoted bases. Earlier dated follow-ups below are historical; their pending-audit and authorization statements are superseded.

Correction follow-up on 2026-09-15: the two major D8 contract findings are patched, 65 focused tests pass, and a [bounded recheck packet is staged](audits/VNEXT_D8.md#correction-follow-up-staged-not-run) for `gpt-5.6-sol`. It has not run; D8 audit closure and consuming-release qualification remain open.

Audit follow-up on 2026-09-15: the authorized `gpt-5.6-sol` [D8 bounded audit](audits/VNEXT_D8.md) completed with two major contract-clarification findings and one minor terminology finding (`needs_revision`). Design ratification stands; audit closure requires the narrow corrections and a focused recheck. The older pending-authorization and not-yet-run statements below describe earlier checkpoints.

Follow-up on 2026-09-15: the operator has now [ratified the D8 storage design](specs/VNEXT_LOCAL_STORAGE_SPEC.md), including the single-host/single-writer scope. That explicit request also authorizes the corresponding local owning-spec and plan updates, which have been recorded. The D8 audit has not run; refreshed exact-payload authorization and release qualification remain open. The reconciliation and approval states below describe the earlier checkpoint and are retained as historical evidence.

This is a checkpoint of existing, unactivated implementation. **18.5, 18.6 and
18.7 remain incomplete.** It is not a release, a D8 ratification, or evidence
that a new runtime mode is supported. The current reconciliation supersedes
historical next-action text; historical evidence and limitations remain intact.

## Authority and scope

Read the [implementation plan](../IMPLEMENTATION_PLAN.md), the evidence under
`rounds/vnext-{assembly,semantic,promotion}-001/`, and the D8 staging record before
using component presence as a capability claim. Normative owners are the
[candidate leaf](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md),
[D7 scheduler table](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#vnext-candidate-processing-d7),
[coordinating activation gate](specs/WHETSTONE_COORDINATING_SPEC.md#candidate-safety-activation-gate),
and the artifact and scope leaves for their respective contracts.

This task preserves existing implementation and legacy/bridge behavior. No
18.8–18.9 implementation, new mode activation, push, external source apply-back,
or live provider qualification is included. Fixture-only suites are not shipping
qualifications. The three shipping proposal/semantic/follow-up qualification maps
in `vnext_proposal_cli.py` remain empty. The frozen `vnext-contracts-1` manifest
has exact-byte SHA-256
`09172fdc498f9d0189f3530b306fe1098a3c1d449482b68d21478d3786e1a950`.

## Inventory against the owning requirements

“Implemented” below means the bounded component exists with executable tests;
it does not mark the containing slice complete. See validation results below
for the actual current-source execution outcome.

| Slice / requirement | Existing implementation and executable evidence | Remaining boundary |
| --- | --- | --- |
| 18.5 deterministic assembly, maps, inventories, assertions, exact effects | `vnext_assembly`, `vnext_section_lineage`, `vnext_unit_*`, `vnext_inventory*`, `vnext_assertions`, `vnext_candidate_validation`; assembly/lineage/unit/assertion/report tests cover exact bytes, changed budgets, tampering, known deletion/weakening and unresolved semantics | Cross-implementation conformance and complete consuming-suite qualification are not established |
| 18.5 candidate identity and contiguous registration | `vnext_candidate_registry` replays exact material, reconciles the sole orphan, publishes initial disposition before the creation-event commit and reuses registered identity; candidate-registry and local-storage tests cover corruption, duplicate/recovery and process boundaries | D8 audit/ratification and qualified descriptor-bound storage remain release blockers |
| 18.5 inspectable proposal-only journey | Native/injected Editor journal, handoff, package/admission, stored run, seed Reviewer/closeout, guarded CLI and operator decisions; corresponding request/recovery/CLI tests | Shipping proposal qualification is empty; historical promoted-base processing belongs to the separate V components |
| 18.6 independent semantics and finality | Semantic context/coverage/protocol, native Verifier, durable requests, decisions and local verification-pointer commits; protocol tests reject partial findings, unrelated regressions, uncertainty, stale bindings and invalid maps | Complete normative coverage and consuming-suite release qualification remain open; independent scripted calls do not measure live model quality |
| 18.6 answers and fresh same-round transactions | Answer receipts, follow-up preflight/admission/workflow and operator CLI preserve original scope, rejected ancestors and exact source evidence; positive/repeated/recovery/native tests exist | Shipping follow-up qualification remains empty; no answer adds an effect grant or reopens a final candidate |
| 18.7 storage, committed history and promotion | Local storage kernel; pointer/history readers; separate materialization and promotion owners; tests cover real process death, stale ownership, prepared claimant reservation, exact pointer binding and lost acknowledgement | D8 is still proposed; physical power-cut, distributed storage and hostile direct writers are unqualified |
| 18.7 live-work/operator/stored-run components | `vnext_verified_work`, `vnext_verified_operator`, `vnext_verified_run`; tests drive actual scripted Editor/registration/Verifier/promotion, explicit child selection and fresh-process reopening | Later canonical round inputs are still fixture-produced; normal Reviewer sequence admission is not integrated |
| 18.7 newer V Reviewer helpers | `vnext_verified_review_protocol`, `vnext_verified_review_requests`, `vnext_review_request_v2` and 11 tests in request/prefix modules bind seed plus original/current pointer, replay raw evidence, and handle bounded request recovery | These files postdate the latest handoff. Private helper presence does not supply sequence selection, canonical round publication or a complete Reviewer → promotion → new Reviewer journey |

The normal V integration guard remains in `_RunHistory._round_inputs` and
`_require_staged_boundary` in `vnext_verified_run.py`. It refuses runtime Reviewer
feedback/claims until an owner validates the actual V sequence. The private
Reviewer journal accepts an already selected round/profile and a proven original
base; it explicitly delegates scheduling admission. Removing the guard would
misrepresent the implementation boundary.

The candidate-leaf development paragraphs and several older `rounds/` handoffs
still describe some now-implemented components as future work. Their safety and
release gates remain applicable; use the inventory above for current component
presence. The plan's previous next action also crossed into 18.8. This checkpoint
does not execute that instruction.

## Evidence verification

Raw reconciliation evidence is retained locally under
`rounds/reconciliation-18-5-18-7-001/`. This directory is intentionally ignored by
Git, like the existing run evidence. `initial-work.tar.gz`, `initial-tracked.patch`
and `initial-manifest.json` preserve all 212 initially dirty files before changes.
`test-source-manifest.json` pins the 464 source/test/contract files used to start
the fresh regression.

`historical-evidence-check.json` checks 44 validation JSON records, 121 referenced
logs and their available digests: every referenced log exists; all 101 supplied
log digests match. All 81 comparable per-log test-count claims match their
actual unittest summaries (`historical-log-counts.json`). Twenty-six records
contain source hashes that differ from the
current checkout. Older passing counts overlap and are not summed as unique
current tests. Preserved failed/cancelled intermediate logs are not passing
release evidence. A hash match verifies bytes, not test adequacy.

Fresh retained-fixture replay passes with the current source: the 339-file
follow-up fixture and the 384-file native CLI fixture both retain their exact
file sets/bytes, original rejected parent, independently verified child and seed
authority. They make no new client calls; the native replay forbids adapter
construction. Compilation and both working/staged whitespace checks pass.

Full regression completed all 1,153 distinct discovered tests (515 baseline,
638 vNext) in 10,155.046 seconds: **1,151 passed; two failed**. Both failures
were subprocess fixture imports under the documented `PYTHONPATH=src`
discovery command. The parent loader's test import path was not inherited by
children in `test_vnext_proposal_run` and `test_vnext_verified_work`. The test
harnesses now explicitly pass or insert their fixture directory; runtime code
is unchanged. All 13 proposal-run module tests pass after correction (47.320 seconds),
as do all 15 V work-owner module tests (181.017 seconds), including the
previously failing process-death/continuation test.

The full run's two failures remain in the log. Across that run and the two
corrected module reruns, all **1,153 distinct tests have passing evidence**;
the overlapping reruns are not added to the total. This is **not a clean single
full-suite run**. Exact commands, durations, log digests, provenance and limits
are recorded in [the validation record](audits/VNEXT_18_5_18_7_VALIDATION.json).
All 11 private V Reviewer helper tests passed,
as did the current-source long native, repeated-follow-up and terminal-recovery
journeys. These close the historical source-version execution gaps for those
specific tests; they do not establish complete normative acceptance coverage.

## D8 authorization and unresolved design gate

`rounds/vnext-d8-audit-001/execution_status.json` says
`not_run_approval_pending`, records automatic approval review rejection of
transmitting the derived storage design/private spec excerpts, and records no
Reviewer invocation. The authorization assertion inside the staged notes is not
a later approval. No affirmative exact-payload approval was present when this
reconciliation began; an explicit decision was requested during this task and
remains pending. D8 stays blocked; no transmission occurred.

All five staged input digests and the notes digest still match `staging.json`.
The candidate-spec and implementation-plan *source* digests have changed since
staging; scheduler, artifact and storage-design source digests still match.
Section-level comparison narrows that drift: all six selected candidate sections,
the scheduler section and both artifact sections still match; only the selected
18.5 and 18.7 plan sections differ (the staged 18.9 boundary remains unchanged).
The comparison is retained in `d8-excerpt-comparison.json`.
An audit of this exact packet would be an audit of the retained snapshots and
would require reconciliation with current sources and the later implementation
notes. Do not silently refresh the payload under an approval for older bytes.

The proposed kernel supplement explicitly says it does not resolve D8. Its
physical binding, fresh-root publication and uncertainty refinements must be
reconciled with the reviewed storage design. Passing process/fault tests does
not ratify a normative storage contract or establish power-loss guarantees.
No external transmission was attempted during local reconciliation.

## Checkpoint ownership

Local checkpoint `c066909a2ade66ab136812499a0cff4cfe3af091` includes 209 files:
the coupled existing 18.5–18.7 runtime,
contracts, tests and candidate-leaf development links. Its scope is deliberately
an unactivated work-in-progress checkpoint, not three completed slices. Separate
implementation commits by slice would conceal shared dependencies in this tree.
The full regression was still running when this explicitly partial checkpoint
was made, as its commit message records. A second local commit,
`2b7b9ac0af9e86b3ace2c30c961f269620469b36`,
fixes the additional V work-owner subprocess fixture import found near the end
of the full regression. Both corrections affect test harnesses only. This
handoff and the final validation record form the separate evidence checkpoint.

A proposed one-paragraph correction to the local implementation plan was rejected
by automatic approval review, including after read-only checks established that
the plan is a regular tracked file in this repository. Review interpreted the
no-external-spec-apply-back constraint as protecting this local plan too. A
specific approval was requested and remains pending; neither rejected command
changed the plan.
Until that decision arrives, this handoff records the bounded next action and
the entire existing plan diff remains preserved and uncommitted.

The unrelated proposed audit-change objectives remain uncommitted and intact:
323 added artifact-leaf lines, 117 added scope-leaf lines and the entire existing
implementation-plan diff (including the 195-line appended audit-change
proposal). They are not candidate-pipeline implementation or
validated audit-change functionality. Historical source files, fixture roots and
frozen suite 1 must not be moved, refrozen or rewritten.

## Remaining work and blockers

1. Obtain an affirmative decision for the exact D8 transmission. If it remains
   blocked, retain that status; do not treat silence or the staged authorization
   assertion as approval. If approved and executed, preserve audit findings and
   reconcile the reviewed design with current owning contracts and kernel
   refinements before declaring D8 resolved.
2. Finish the applicable 18.5 and 18.6 acceptance mapping and exact consuming-suite
   qualification. Keep complete deterministic testing separate from live model
   reliability and public activation.
3. For existing 18.7 work, retain the private V Reviewer helper boundary. The
   normal sequence owner and canonical round-input publisher remain absent;
   staged fixtures do not prove them. Any future integration must reproduce the
   original raw Reviewer evidence over an acyclic proof of exact original bases.
4. Scheduler/profile/budget/terminal integration, Phase 2, version/declaration
   lifecycle and pointer-bound external apply-back belong to excluded 18.8 work.
   Full P0 release qualification, separately authorized live soak and activation
   belong to excluded 18.9 work. Do not begin either under this handoff.
