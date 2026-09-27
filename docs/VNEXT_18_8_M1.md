# 18.8-M1 execution and authority record

Started 2026-09-27 from `25c1825`, with the five-milestone plan and resolution
handoff edits already uncommitted. The user's instruction authorizes pursuing M1
end to end. It does not authorize inventing missing policy, committing, pushing,
public activation, external transmission or apply-back. The unrelated
`notes/future-improvements.md` edit remains outside this work.

## Acceptance boundary

M1 comprises the four bundles in the [delivery plan](../IMPLEMENTATION_PLAN.md#188-delivery-milestones):
operator follow-ups/new repair admission; freeze handling; declaration repair and
review selection; rubric gaps and resulting closeout/halt routing. Reporting,
fenced publication/recovery and focused regression evidence belong to each
bundle. No partial bundle or explicit refusal is credited as general M1 completion.

## Authority and implementation preflight

| Boundary | Existing authority and implementation | Required work / decision |
| --- | --- | --- |
| Interpretation follow-up after semantic rejection | Scheduler D7 explicitly permits an operator-selected new transaction under unchanged current-base/descriptor constraints. Shared V answer and child-selection owners exist; Phase 2 unit preflight explicitly rejects follow-ups. | Carry the exact Phase 2 configuration/request through shared child admission, independent verification and historical replay. Preserve parent finality and review budgets. |
| Pre-admission operator choice | Existing inventory-bound decision request/response and derived-task contracts; Phase 2 round currently requires an empty decision list. | Bind explicit selected decisions to the consumed Phase 2 review and integrate ordinary preflight, promotion and resolution without erasing original classification. |
| Arbitrary repair after semantic rejection | D7 forbids automatic new repair proposals and permits only explicit new transaction/admission. Existing child protocol covers a retained interpretation question. | Do not relabel arbitrary rejection as an interpretation question or invent a retry. Establish a distinct explicit repair-admission contract before claiming this route implemented. |
| Freeze | Identity/oscillation spec defines deterministic recommendations; signal owner already preserves a blocked freeze report. No adoption, enforcement, release or continuation rule is specified. | User approved the evidence-preserving blocked outcome for M1 on 2026-09-27. Resumable freeze is deferred; acceptance must verify the approved blocked boundary. |
| Declaration | Scheduler authorizes regeneration after draft change and removal only of hash-binding findings actually repaired. The 2026-09-26 decision retains unchanged valid-declaration disagreement as a blocked report. | Preserve that decision. Integrate only demonstrated repair and ordinary budgeted successor-review paths; no mechanical-match override or automatic disagreement re-review. |
| Rubric | Scope leaf specifies gap identity, ordering and target-dependent blocking. Bound final-strict configuration exists; closeout rejects every observed rubric signal because a gap resolution owner is absent. | Bind exact rubric requirements and resolution evidence; do not infer that a free-text impact describes exactly one rubric requirement or that later silence resolves it. Reconcile target coverage before claiming general rubric support. |
| Apply-back dependency (M4) | Candidate Ratification Delta Map explicitly leaves the full vNext source-write lifecycle unratified pending the scheduler amendment. | Named future decision dependency; no M4 implementation or authoritative-spec edit in this M1 work. |

The normative sources are the [scheduler/D7](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md),
[candidate protocol](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md),
[Phase 2 declaration rules](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md),
[scope/decision and gap rules](specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md), and
[oscillation rules](specs/IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md).
The prior [declaration decision](VNEXT_18_8_PHASE2_FINDINGS.md#declaration-repair-authority-investigation-2026-09-26)
remains settled.

## Approved freeze boundary — 2026-09-27

The user approved this bounded M1 policy with “Ok I approve” in response to the
explicit freeze-boundary question. When the deterministic recommendation is
`freeze_prior_decision`, preserve the current verified pointer, triggering
evidence and unresolved findings; publish/recover the existing signal report;
expose the existing freeze gate with no technical resume, further Reviewer,
Editor, candidate admission or convergence permission. Do not invent a new
terminal or claim that the recommendation itself resolved the concern. Treat
this blocked outcome as the supported freeze behavior for M1. A future resumable
freeze would need an explicit policy defining the frozen decision, its lifetime,
what mutations it forbids, and who may release it.

This explicit approval narrows the planned freeze-resolution outcome to the
blocked behavior above. Resumable freeze is deferred beyond M1 until its policy
is defined. The approval does not authorize automatic clearing, a waiver,
convergence, an authoritative-spec amendment, public activation, external
apply-back, commit or push. The existing declaration disagreement decision
remains settled. This records a product-scope decision; it does not by itself
establish implementation acceptance or complete M1.

## Operator acceptance cases

1. A real Phase 2 candidate receives a semantic interpretation question and final
   rejection. Explicit answer/selection creates a distinct child transaction,
   independently verified and promoted on the same current base. The original
   decision remains immutable; only verified resolution permits ordinary review.
2. Pre-admission explicit operator choices reproduce current inventory, original
   findings and exact source review. Preview and status write nothing; publication
   selects no option automatically. Decline and missing/stale consent cannot edit.
3. First and later Phase 2 passes retain their original configuration, request,
   feedback/advice and base through promotion and fresh-process reopening.
4. Publication prefixes, lost acknowledgements, source drift and ownership loss
   preserve immutable sources and recovery-only behavior. No duplicate client,
   review credit, retry allowance or candidate resurrection.
5. Suites without the new integration pin retain their prior behavior. Shared
   Phase 1/proposal-only operator and follow-up checks remain compatible.

## Current status

The operator integration is implemented under the separate
`vnext_verified_phase2_operator_v1` algorithm pin and validated at the scope
below. M1, its first bundle (which also requires arbitrary repair admission),
and all four original 18.8 checklist items remain open. The freeze scope decision
is approved; acceptance of that boundary and the remaining implementation work
are still required.

New internal operations are `phase2_operator_context()` (read-only discovery and
exact retained request/response/selection inspection),
`prepare_phase2_operator_requests(..., dry_run=...)`,
`submit_phase2_operator_responses(..., dry_run=...)`, and
`admit_phase2_operator_round(selection)`. Existing `submit_answer()` and
`select_followup()` now support the separately pinned Phase 2 interpretation
path. Publication/admission do not invoke clients. Caller-selected receipts are
required; read-only enumeration grants nothing. Recovery reuses exact immutable
bytes and the original source review.

Independent Verifier context now includes the exact Phase 2 configuration and
request for this pin. Resolution checks the actual admitted finding population,
but deliberately retains broader original findings when only narrower derived
tasks were verified. That follows the candidate leaf's partial-resolution rule;
an operator response cannot silently waive the original concern.
For the new pin, declaration/report issue projections retain that debt across
later silent reviews. Resolution is applied only through the projection's
requested verified-pointer ordinal, so a later successful correction cannot
rewrite a pre-promotion report. Older suites retain their existing projections.

Remaining M1 work is explicit:

- **Approved blocked-freeze acceptance remains to be reconciled.** Verify that
  the existing signal/report path preserves authority and evidence, blocks new
  work and convergence, and permits only report/state recovery. Resumable freeze
  is deferred and needs separate adoption, enforcement and release rules.
- **Repair admission beyond an interpretation answer remains unimplemented.**
  A rejected candidate without that question is not eligible for this child
  protocol. It still needs a distinct explicit admission, not an automatic retry.
- **Declaration repair/further review selection remains incomplete.** Existing
  stale-hash regeneration and the settled blocked-disagreement behavior remain;
  final-review source correction and the resulting profile verification routes
  are not implemented by this operator change.
- **Rubric-gap lifecycle remains incomplete.** Current feedback carries a
  rubric-impact severity, not a structured exact rubric requirement. Gap
  attribution, retained evidence, verified resolution and downstream
  declaration/termination integration still need implementation. Standard
  final-strict support does not establish coverage for other targets/profiles.
- **General Phase 2 halt integration remains incomplete.** The new read-only
  operator context reports retained choices and distinguishes them from technical
  resume. It does not claim a new complete phase-level pause/terminal lifecycle.

No authoritative specification is amended. No public suite is qualified and no
legacy full-draft executor is invoked. The user subsequently authorized a local
checkpoint of this scoped work; push remains deferred. The audit retains its
historical pre-checkpoint validation status.

## Verification record

Evidence is retained under `rounds/vnext-18-8-m1-001/`, indexed with source and log
hashes in the [operator audit](audits/VNEXT_18_8_M1_OPERATOR.json).
**42 distinct methods passed in the six credited cohorts: 11 new runtime methods
and 31 existing checks.** All credited runs used the delivered runtime, contract
and test bytes; 566 source hashes were checked afterward. Earlier passing
development cohorts are superseded rather than counted again.

| Delivered cohort | Methods | Evidence log |
| --- | ---: | --- |
| Operator choices, admission, faults, residual debt and historical boundaries | 9 | `operator-core-final.log` |
| Rejected parent → explicit answer → child verification/promotion → next review | 1 | `child-report-journey.log` |
| Child timeout, separate report and uncertain-publication recovery | 1 | `child-report-fault.log` |
| Shared semantic context/follow-up, unit preflight and resolution rules | 26 | `shared-final.log` |
| Existing Phase 2 sequence and Phase 1 operator journey | 3 | `compatibility-final.log` |
| Existing correction-failure history | 2 | `report-compatibility.log` |

The implemented scope is an internal operator integration, not full M1
acceptance or release qualification. The successful child journey also preserves
the published parent report through promotion and another review. Boundary
checks confirm unchanged authoritative specs and frozen suite, empty public
qualification maps, eight original open 18.8/18.9 items, and no staged changes.

The work uncovered and corrected two implementation problems: an ownership
check was missing after the new publisher's final write, and an initial dispatch
change unnecessarily rebuilt the full Phase 2 sequence for first-pass historical
admission. The delivered reader retains the existing bounded first-pass replay
and adds explicit decision validation. The new residual projection also guards
declaration/closeout against silent loss of broader original findings, while
respecting historical pointer boundaries.

The complete child journey exposed a third integration defect: correction-failure
reporting assumed at most one candidate per round. The new pin follows only the
explicit selected-child chain and gives each child transaction a distinct report
location. It preserves the parent's committed report and failure-time candidate
view, while allowing current status to advance after the child's success. The
existing one-candidate path and its report locations remain unchanged for older
suites.

Superseded evidence is retained: an exploratory child run refused after its pin
changed during development; one test incorrectly reused the old storage object's
publication method after reopening; the initial ownership-loss case exposed the
missing final check; a long child run was deliberately interrupted to correct
the redundant replay; the first completed child journey exposed the reporting
guard described above; and a historical-issue test initially compared an
unsorted expected list with canonical sorted output. Corrected cases are rerun
separately. None of those failed or interrupted runs is credited as a passing
cohort.

Tests use injected clients, local macOS/APFS fixtures, simulated write faults
and one fresh-process readback. They do not qualify actual process death during
a write, physical power loss, live providers, performance or the full repository.

## Resume point

The freeze scope decision is settled as recorded above. Continue the first
bundle with explicit repair admission for rejections without
an interpretation question, then declaration/source repair and rubric-gap
integration. Reconcile the existing freeze evidence against the approved blocked
boundary during M1 acceptance. Those implementation gaps remain after approval.
Use the existing five-milestone order; do not reopen settled declaration policy
or count this operator checkpoint as M1 completion. The local checkpoint is
authorized; the unrelated notes edit remains excluded.
