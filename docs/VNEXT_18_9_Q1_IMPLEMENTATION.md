# 18.9 Q1 implementation handoff

Started 2026-10-02 from `78dfa8b27b896e3d90e990774aebfd80b7e40486`, following
operator approval of the bounded amendment/interface package. **Q1 is incomplete.**
The operator authorized this partial implementation checkpoint on 2026-10-02.
Production qualification remains empty; no live provider calls, real external
apply-back operations or pushes have occurred during this implementation.

## Applied and implemented so far

The approved amendment patch was applied to the six specification owners and the
Operator Quickstart. The proposal and implementation plan now distinguish that
ratification from implementation and release qualification.

A separate config-selected V dispatcher now opens `VerifiedRun`. Fresh bootstrap
shares the package copier with P but uses a V seed validator; it initializes only a
nonexistent root, retains immutable inputs and materializes the seed through D8.
Reopening resolves retained mode even without config selectors. New work requires
matching V config; public qualification remains an independent exact-digest gate.

`vnext-verified-consumer-1` is staged and registered **offline only**. It pins the
installed schema/algorithm closure and existing vectors plus four Q1 schema
vectors. `vnext-contracts-1` remains unchanged. This consuming manifest
is not release-qualified and does not establish coverage of every pinned feature.

Command adapters have been written over existing owners for Phase 1, distinct
Phase 2 entry and execution, operator/semantic inputs, bounded recovery and source
operations. The new Phase 2 native transport retains the complete review/rubric
response shape and leaves attempts to the existing journal. D8 command selection
is rechecked inside each actual fence, including the promotion projection fence.
These are implementation drafts; the evidence below establishes only tested paths.

## Adopted direct Reviewer handoff decision

On 2026-10-02 the operator selected direct Reviewer-to-Orchestrator guidance,
with human involvement for product or authority decisions. This supersedes the
proposed routine `--advice FILE` handoff. Guidance accompanies each Phase 2 review
that has findings, including later rounds; Phase 2 entry itself requires no advice.

The new [Reviewer advice supplement](../contracts/algorithms/vnext_phase2_reviewer_advice_v1.md)
pins `vnext_phase2_rubric_response_v2`: `review`, `rubric_findings`, and advisory
`classifications`. Whetstone computes all job, draft, feedback and authority
bindings, validates exact finding coverage, and applies the existing conservative
classifier. After result consumption, the command consumer binds that evidence
through the existing D8 advice owner before correction admission. No extra model
request or routine human-authored file is needed. Sensitive product, policy,
scope, protected-invariant and authority findings still stop for explicit decisions.

Old suites retain their v1 response and explicit advice contracts. The optional
`--advice` operand cannot replace new-suite Reviewer guidance: it must exactly
match the retained response's derived packet. Interrupted attachment publication
is recovery-only and cannot start an Editor or another review.

## Acceptance inventory

| Q1 acceptance case | Current evidence / remaining work |
| --- | --- |
| 1. Fresh config-selected admission | Focused CLI tests exercise injected exact qualification, dry-run, fresh initialization and V reopening. Production gate remains empty. |
| 2. Unknown/unqualified/conflicting selectors | Public refusal, suite conflict, existing destination and no-client/no-write assertions covered; expand the selector/Phase 2 Ref matrix. |
| 3. Retained mode | Removed config selectors still select V status; new work without mode refuses. Broaden edited-selector negative cases. |
| 4. Genuine verification/promotion/entry/convergence | Clean unversioned horizontal command journey passes through distinct entry and two real scripted review owners to convergence. A first-pass automatic Reviewer-to-Editor-to-Verifier correction now passes through one durable promotion. Post-correction convergence, versioned entry, vertical/focused and all target combinations still need command-level evidence. Core M1–M5 tests are prior owner evidence, not substitute command qualification. |
| 5. Status/recovery | Storage selection-guard tests pass. Focused Phase 1 stale-selection race, timeout, read-only dry-run, refusal of implicit retry and explicit continuation cases pass. The direct Reviewer campaign also passes a later-pass interrupted advice attachment, read-only dry-run and repair-only resume without another client. The original ratified 12-row table plus the new advice-attachment recovery row remain unqualified as a complete set: prepared registration/decision/promotion, report/state publication, first/later Phase 2 continuation, exhausted refusal and repair-only `--continue` need complete command evidence and any resulting fixes. |
| 6. Separate source approval | Adapter tests cover envelope/null/noncanonical/duplicate-key/hash rejection, explicit operands and recovery bypass of fresh eligibility using a recording owner. Real disposable-fixture command apply/retry, uncertain write, pointer advancement and historical drift journeys remain to run. No real external source was written. |
| 7. Compatibility and disabled production | The package regression and storage/native/proposal CLI batch pass. The final direct-handoff run also passes the legacy CLI suite and old explicit-advice owner tests. Broader legacy/bridge/R/P route qualification remains Q1 work; release-wide qualification remains Q3. |

## Verification

- `PYTHONPATH=src python3 -m unittest discover -s tests -p test_vnext_proposal_package.py -q`: 13 passed, 20.474s.
- `PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_command_guards test_vnext_native_phase2_reviewer test_vnext_proposal_cli -q`: 56 passed, 105.750s. Imported fixture test classes also exercise the existing storage and native Editor regressions.
- The first isolated clean Phase 2 command journey passed in 146.179s. This is useful correctness evidence, not a replay performance qualification.
- `PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_cli test_vnext_verified_source_cli -v`: 10 passed, 191.877s, including the clean Phase 2 journey, Phase 1 race/timeout and source operand tests.
- Subsequent focused `test_bound_configuration_is_not_entry_and_changed_selector_refuses`: passed, 18.336s; config publication cannot authorize resume/entry, and a changed Phase 2 Ref refuses without writes.
- Final public-refusal/reopen tests plus `test_cli`: 41 passed, 8.959s. This also exercises the existing legacy CLI suite, including disposable-fixture apply-back.
- `compileall`, `git diff --check`, reverse applicability of the approved amendment patch, and offline validation of both suites passed. All production qualification maps are empty.
- No test worker remains running. The unrelated notes file still has SHA-256 `d00f59d7e61335a980652d696011fb151f2006a4bcb7cc434bf14cab0279f502`.

The earlier 10-test campaign preceded the final selector/phase-label tightening;
subsequent focused checks cover those boundary changes. Those earlier runs used
the prior response envelope and establish no correction/promotion, versioned,
full recovery-table or real V source-write command journey. They are not final Q1
qualification. The direct Reviewer handoff verification is recorded separately below.

## Direct Reviewer handoff verification

Evidence is retained under `rounds/vnext-18-9-q1-reviewer-handoff-001/`.
The first three-case command campaign passed the product-decision stop and
later-pass interrupted-attachment recovery. Its correction case exposed a
read-only command-selection bug: status constructed a live admission helper
requiring a borrowed fence. Selection now uses the proven read-only transaction
router and checks its exact current base. The correction test explicitly checks
that proposal status takes no writer fence and changes no files.

The next correction run stopped before promotion. Inspection found the staged
consumer selecting `semantic-policy-v1`, whereas the delivered semantic owner
requires `semantic-policy-v2`; the consumer dispatch is corrected.
A focused check now guards this pairing and the frozen older suite's v1 dispatch.
A redundant diagnostic run was deliberately stopped by expiring its supervision
lease; this was not a performance timeout or successful test. Failed/aborted logs
remain evidence and are not counted as passes.

The final combined run passed **52 tests in 912.317s** (912.914s supervised wall
clock, 60% duty limit). It covers the v2 response/authority classifier, exact native
provider projection, v1 response compatibility, older explicit-advice owner
including interruption/tamper checks, the legacy CLI suite, clean Phase 2 entry
and convergence, and one automatic source correction through Editor, independent
Verifier and durable promotion. The correction case asserts exactly one Editor
call, one Verifier call and promotion ordinal 1, then deliberately stops at that
boundary; it does not claim post-correction convergence. The two earlier passing
operator-stop/later-advice-recovery cases used the pre-correction staged policy
selector; they exercise no semantic invocation and are retained as scoped evidence,
not a final full-matrix qualification run.

`compileall`, `git diff --check`, both offline suite validations and a fresh CLI
help check passed. The frozen suite digest is unchanged. The V/P/semantic/follow-up
production qualification maps are empty. The verification workers have all
exited. No live provider, real external apply or push occurred.

Final verification results and the exact runtime input hashes are recorded in
`verification.json` in that directory. Tests use scripted clients, disposable
local D8 roots, one supervised worker, a 60% duty limit and finite deadlines.
This remains bounded implementation evidence, not suite-wide qualification or
permission to activate V, invoke live providers or apply to external sources.

## Resume the implementation

The direct Reviewer handoff decision is resolved. Its implementation and
verification are recorded above; the broader Q1 command qualification remains
open. Continue the **same Q1 package**, without creating another delivery
milestone or marking any acceptance row complete early. Finish the remaining
adapter/recovery paths and their seven-case evidence, reconcile
the supported-command matrix with actual results, then perform the bounded review.
In particular, audit report-publication plus state-projection stop points, semantic
follow-up selection, Phase 2 configuration revalidation and first/later request
selection under the fence. Do not infer that a written adapter has passed those cases.

Keep Q2's seven P0 gaps, Q3 replay/full qualification and Q4 live soak/activation
separate. Preserve `notes/future-improvements.md` and the pre-existing untracked
`docs/audits/VNEXT_18_9_Q1_BOUNDED_AUDIT_002.md`. Audit reports remain uncommitted.
