# Q1 recovery and operator boundary delivery pass

This is pass 1 of the five remaining Q1 delivery passes agreed in the zoom-out.
It is one delivery package, not a new milestone per fault. Status: **complete in the bounded scope below**.
The preceding selected-execution work remains uncommitted and is preserved.

## Fixed acceptance inventory

| Boundary | Required command-layer evidence | Existing owner evidence to reuse |
| --- | --- | --- |
| Candidate publication | Exact registration claimant/round, prepared verification decision and prepared promotion; read-only status/dry-run; wrong selection refusal; recovery-only stop including Phase 1 `--continue`; source revalidation and no additional clients. | Runtime registration/verification recovery and promotion prefix/claimant tests. |
| Phase 1 stopping and budget | Terminal/report/state repair ends before a new review; explicit budget admission ends before execution; valid retained Verifier output can finish without another provider. | Phase 1 operator, closeout and budget owners. |
| Phase 2 preparation and terminal compositions | Later declaration preparation interruption stays ordinary preparation, not a retry grant; recovery retains terminal/freeze dispositions and cannot start work. | First-review, report, exhaustion, findings command campaigns; signals, closeout, review-only owners. |
| Explicit advice, repair and gap acceptance | Closed payloads pass through their real owners; changed/stale inputs refuse; previews are read-only; retained partial publications can finish without clients or implied convergence. | Advice, repair and gap-acceptance owner tests, plus ten-route command-fence tests. |
| Semantic operator publication | Response/receipt and admission/selection interruptions recover exactly, without reopening a parent, starting a client or accepting altered bindings. | Verified operator prefix, decline/stale and ownership-loss tests; previous real selected-child command journeys. |
| Reconciliation | Trace these cases to the finite scheduler table; record exact new evidence and reused owner evidence, remaining defects and scope limits. | Q1 handoff and seven acceptance rows. |

The owning requirements remain the verified-command, verified-work and verified-
operator algorithms and the scheduler's finite recovery table. Existing Phase 2
repair, gap and advice algorithms own those payloads. No new retry, mode, policy,
source-write permission or public qualification is introduced.

This pass does not include workflow-route/target qualification (pass 2), disposable
source-operation qualification (pass 3), the complete selector/compatibility matrix
(pass 4), or final Q1 review (pass 5). Exhaustive fault combinations and replay
performance remain Q3. Tests below exercise representative command compositions;
existing owner evidence supplies lower-level publication-prefix coverage. A new
case is added only to resolve a concrete required-boundary defect.

## Work and evidence

Evidence directory: `rounds/vnext-18-9-q1-recovery-operators-001/`.
Initial inspection found registration recovery matching `cand_` while the producer
writes `can_`. Recovery selection now uses the validated producer preparation,
including the exact candidate, round and preparation hash, rather than parsing a
second candidate naming convention. Prepared verification selection now
exposes its exact pending decision reference as well as the prior decision. The
corrected candidate command journey passes exact selection, tamper refusal under
the fence, all three publication repairs and the subsequent state-only repair.

All six inventory rows are satisfied by the new command evidence and explicitly
reused owner/command evidence below. No commit, push, public activation, live
provider invocation, real external apply-back or spec amendment occurred.

## Recovery-table trace

The scheduler's “Exact V recovery and continuation routes” is the finite owner of
this inventory. Evidence is composed by row, not inferred from a passing overall
suite or from unchanged cached state:

| Scheduler boundary | Evidence source for this pass |
| --- | --- |
| Current-pointer materialization | Prepared-promotion command journey, plus prior post-promotion recovery campaign. |
| Registration and verification publication | New candidate command journey: exact round/preparation/decision, tamper at fence, read-only preview and repair-only `--continue`. |
| Prepared next-ordinal promotion | Same journey: retained intent, same candidate, exactly one promotion, no next review. |
| Phase 1 terminal/state | New Phase 1 journey: interrupted closeout, lost state acknowledgement, separate repair and stop. |
| Phase 2 entry/reports/findings/closeout | Reuse the recorded entry, Reviewer-resume, report, terminal and findings command campaigns in the Q1 handoff. New composition guards preserve stopped/frozen/terminal identity; these guards are not new owner journeys. |
| Phase 1 Reviewer continuation | Prior Phase 1 and Reviewer-resume command evidence; no additional client policy. |
| Phase 1 Editor continuation | Previous selected-execution command campaign, including exact child request and stop before registration. |
| Phase 1 Verifier continuation | New Phase 1 journey: retained valid raw response, one Verifier call total and no implicit promotion. |
| Phase 2 advice attachment | New exact explicit advice payload and retained-attachment repair; prior direct-handoff campaign also covers later-pass advice. |
| Phase 2 Reviewer continuation | Prior first/later Reviewer-resume command evidence, including retained output, exhaustion and stopped reentry. |
| Explicit Phase 1 budget | New Phase 1 journey: grant publication and state acknowledgement loss, exact reentry and changed-amount refusal, no appended review. |
| External source-write uncertainty | Intentionally remains in delivery pass 3, using the separately acknowledged source owner. |
| Other conditions refuse | New stopped/freeze composition guards, wrong-round and implicit-retry refusals; prior finality/disagreement evidence. |

Later declaration preparation and explicit repair/gap/semantic actions are
ordinary preparation or operator admissions, not additional generic resume rows.
Their new journeys must preserve this distinction and stop before child execution
or convergence. Historical owner evidence is indexed separately in
`reused-owner-evidence.json`; it does not count as a fresh test run or as complete
release qualification.

A third implementation defect was found during this pass: the command adapter
required a stopped Phase 1 gate even when the exact budget grant had already
committed. The existing budget algorithm explicitly permits reentry until an
appended round completes. Selection now exposes that owner's exact recoverable
grant and validates it again under the invocation fence; changed parameters
refuse, and recovery cannot admit a second grant or call a client. CLI control
validation also requires a positive integer for previews as well as mutations
and rejects combining the grant with `--continue`. The new Phase 1 command
journey passes both lost-acknowledgement cases and changed-amount refusal with
unchanged client counts; the remaining journeys and affected regressions also pass.

## Operator interpretation

- Inspect `status` before recovery. Candidate publication recovery requires the
  exact `--vnext-round`; a wrong round refuses even in a preview.
- `resume --continue` still stops after a selected publication/projection repair.
  It cannot turn retained registration output into permission to verify, or a
  retained decision into permission to start another promotion.
- Repeating `resume --extend-review-budget N` after uncertain acknowledgement
  recovers the same committed grant while its owner permits reentry. Status
  identifies its exact reference and event in `budget_reentry`. A different N
  refuses; a separate ordinary invocation executes newly available work.
- Advice attachment recovery uses `resume`. Repair, gap acceptance and semantic
  answers/child selection use their explicit operator commands again with the
  same bound inputs. None is an automatic candidate retry or a convergence grant.
- Incomplete declaration preparation remains with `live-phase2`; `resume` does
  not gain a new generic Phase 2 continuation route from partial preparation.

These are implementation-test semantics under the non-shipping fixture suite.
Public verified-promotion admission remains disabled.

## Verification record

The five new integration methods now pass in their recorded source cohorts. The
final focused/compatibility campaign passes 85 methods on `source-008.json`.
The two affected budget-owner regressions also pass on `source-008.json`: **92
distinct passing methods**, including ten new methods. Historical reused tests
are not added to that count. `verification.json` records commands, method outcomes,
source cohorts, hashes, corrections and scope limits.

| Campaign | Observed result | Credit |
| --- | --- | --- |
| `journeys` | Five methods, 1,244.669s; two passed and three test-setup failures | Passing Phase 1 and semantic-publication methods only. |
| `corrected-journeys` | Three passed, 1,588.669s | Candidate, advice/repair and gap/later-declaration cases. |
| `final-checks` | 85 passed, 14.507s | 45 command/guard methods and 40 legacy CLI/public-refusal methods. |
| `budget-regression` | Two passed, 567.526s | Horizontal/vertical/focused grant lifecycle and retained vertical timeout. |

Preliminary runs are retained rather than rewritten. The first `candidate` run
passed its three publication repairs but had an incorrect final assertion that
ignored the legitimate following Phase 1 state-projection row. The first
`phase1` run exposed the actual budget-command reentry defect. `journeys` then
passed that corrected Phase 1 case and the semantic case, but exposed three
fixture mistakes: comparing unresolved and physical macOS root paths during
fault injection, matching an earlier Phase 1 advice artifact during source
synchronization, and expecting later declaration preparation before the required
intervening adversarial pass. The corrected campaign passes all three cases.
No failed run supplies a full-suite pass claim.

The only production changes after the integration cohorts were the final CLI
budget-argument validation, the materialization-first metadata guard, and passing
the budget owner's already computed completion boundary to its shared recovery
predicate instead of replaying it again. The final focused/compatibility run
covers the first two; the passing owner regressions cover the predicate call.
Full source snapshots identify these cohorts; the first diagnostic candidate
run has no complete retained source snapshot and receives no acceptance credit.

The gap/declaration test deliberately stops immediately after the real later
preparation owner finishes, before binding its next request. Successful ordinary
`live-phase2` is allowed to continue beyond preparation; this fixture does not
claim convergence or a normal preparation-only command stop. The intervening
adversarial review is fixture setup through its real owner. The gap operation and
interrupted preparation themselves call no Reviewer. Repair admission and
semantic child selection likewise stop before child execution; the preceding
selected-execution campaign supplies separate real child-promotion evidence.

Freeze/terminal composition guards exercise adapter precedence and refusal;
they are not substitutes for fresh full freeze/terminal journeys. The previous
command campaigns and separately hashed owner evidence supply those unchanged
underlying boundaries. Exhaustive fault combinations, full release regression,
cross-implementation determinism and replay optimization are not claimed here.

The handoff now has one five-pass execution list instead of overlapping historical
next-slice instructions. The remaining four passes are
supported workflow routes, disposable source operations, configuration and
compatibility, and closure review. Q1 and the four 18.9 release checkboxes remain
open. No product or authority decision has blocked this pass.

All workers exited and the bounded worker lock is available. Each campaign used
one worker, 60% CPU duty, a finite wall deadline and a supervision heartbeat.
Changed Python files compile; whitespace and both offline suite validations pass.
Both suite digests, all four empty production qualification maps, the unrelated
notes and pre-existing audit hashes are unchanged. The prior selected-execution
work and this pass were uncommitted at verification and subsequently checkpointed
in `31e1ff7`. No known defect remained within this fixed inventory; the next
delivery pass at that checkpoint was supported workflow-route qualification.
