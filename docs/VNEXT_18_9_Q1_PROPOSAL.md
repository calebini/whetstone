# 18.9 Q1: bounded release-contract proposal

Prepared 2026-10-01 against `fb57a2406074520630fa99242161d9662e18653b`.
**Draft for approval. No authoritative amendment has been applied and no public
verified-promotion capability has been enabled.**

The proposed [amendment patch](VNEXT_18_9_Q1_SPEC_AMENDMENTS.patch) updates six
existing specification owners and the Operator Quickstart. This document is the
review guide and proposed supported-command matrix, not a new normative owner.
The [implementation plan](../IMPLEMENTATION_PLAN.md#q1--config-selected-verified-promotion-release-integration)
and [qualification inventory](VNEXT_18_9_INVENTORY.md) retain Q1–Q4 as the finite
release work. Internal M5 completion does not establish public release readiness.

## Decision and scope

The operator has selected **run-config opt-in**, without a separate CLI mode
flag. This proposal makes its relationship to the immutable descriptor concrete:
the config requests the mode and suite for a fresh job; admission validates and
retains the prepared inputs; existing jobs continue under those immutable bindings.
Editing a config cannot convert a job or bypass suite qualification.

The release surface below is proposed for approval. New config/command operands
are not currently available. Existing internal owners implement the transaction
protocol; Q1 must still provide and test the public adapters, bootstrap, suite
manifest and diagnostics. Merely recognizing a suite is insufficient to enable it.

Carry forward the approved [M3 metadata rules](VNEXT_18_8_M3.md) and
[M4 source-write rules](VNEXT_18_8_M4.md) without reopening their policy. The patch
copies their six-rule decisions into their designated normative owners. Metadata
changes must precede verification; source apply remains a separate exact approval.
Legacy, bridge, reviewer-only and proposal-only interfaces retain their boundaries.

## Configuration and admission

Illustrative future configuration; placeholders are not accepted suite names or
hashes:

```yaml
editing_mode: verified_promotion
contract_suite_version: <qualified-V-suite-version>
vnext_input_package:
  path: inputs/package.json
  hash: <SHA-256-of-exact-package-bytes>
# Needed for Phase 2; this Ref resolves relative to the admitted root.
vnext_phase2_configuration:
  path: inputs/phase2/configuration.json
  hash: <SHA-256-of-exact-configuration-bytes>
```

The input package is explicitly prepared from seed, review configuration,
authority, scope and invariant inputs. It binds an agreeing descriptor and contains
no runtime authority. The package locator resolves relative to the launch config;
package-internal references stay inside the package. Preparation cannot invent
missing product decisions or approvals. This first release therefore requires a
prepared package, not only the two mode/suite settings.

`vnext-admit --root NEW_ROOT --config /absolute/run.yaml --dry-run` validates
without creating the root. Omitting `--dry-run` requests initialization. Keep the
config and package outside the nonexistent destination; even an empty existing
destination refuses under D8. The new V bootstrap opens `VerifiedRun`, not the
proposal-only owner. Ordinary Phase 1 launch may use the same fresh-admission owner.

The proposed top-level `vnext_phase2_configuration` Ref may be prepared after
initialization. Before entry, bind its exact job, review configuration, rubric,
clients, profiles and targets and commit the immutable configuration/request under
D8. Once bound, changed inputs refuse. Configuration publication is not entry.
This does not extend the existing closed two-Ref `vnext` selector block.

On existing roots, retained inputs own mode and lineage. Supplied selectors must
agree. Read-only inspection and supported recovery may resolve retained inputs;
omitting selectors must never trigger legacy fallback. A descriptor-bound change
requires a fresh job. A new consuming suite must pin the delivered contracts and
vectors; `vnext-contracts-1` remains frozen and production activation remains off.

## Proposed supported-command matrix

All rows below are the intended V release contract, **not a claim of current
public support**. Commands execute only qualified route/gate combinations.

| Command | Supported scope | Behavior / boundary | Existing owner or required adapter |
| --- | --- | --- | --- |
| vnext-admit | New V root; --dry-run is read-only | Validate config/package/suite; initialize only a nonexistent destination; no clients | V bootstrap adapter + D8 initializer |
| live-phase1 | Standard horizontal or vertical; new or existing V root | Run bounded verified review/correction gates; stop at Phase 1 terminal/decision/failure; no source apply | review_next/admit_reviewed_round/request/register/verify/promote/finish_phase1 |
| live-focused-phase1 | One profile selected in immutable focused review config | CLI --profile/explicit --budget must match pins; omitted CLI defaults cannot override pins; focused clean never grants Phase 2 | focused review owner + Phase 1 verified owners |
| promote-phase2 | Complete Phase 1; bound Phase 2 configuration | Run required verified metadata transition and distinct entry commit only; no ordinary Phase 2 reviews | bind_phase2_entry/prepare_phase2_version/verify/promote/enter_phase2 |
| live-phase2 | Entered or eligible standard/fixed-rubric V job | Use shared entry owner, then existing bounded sequence through declaration/convergence or blocker | phase2_sequence_status/continue_phase2_pass/phase2 correction and closeout owners |
| status | Any inspectable V root | Read-only current authority/candidate/failure/decision and exact next gate; malformed authority reports invalid | inspect/phase1_status/phase2_state/operator/failure/apply status |
| resume | Existing V root; --dry-run is read-only | Only the exact recovery/continuation subtable below; plain resume stops at its selected boundary; --continue is Phase 1 only | materialization and role-specific recovery/continuation; extend_phase1_budget |
| vnext-decisions | Bound Phase 1 or Phase 2 operator context | Inspect; with explicit --options prepare exact requests; --dry-run writes nothing; no clients | operator_status / phase2_operator_context / request preparation |
| vnext-decide | One exact operator input | Existing --selections; proposed alternatives --repair-request or --gap-acceptance for Phase 2; exactly one input, no clients | response/selection owners; admit_phase2_repair / accept_phase2_gaps |
| vnext-semantic-answers | Explicit --candidate | Read-only original question and retained answers; no implicit latest selection | answers |
| vnext-semantic-answer | Explicit --candidate and --input | Record exact answer; --dry-run read-only; no candidate reopening or client | submit_answer |
| vnext-semantic-followup | Explicit candidate and receipt/hash | Admit exact new child transaction; no client or automatic promotion | select_followup |
| strop / apply-back | V inspection or retained-intent recovery; new writes require complete current eligibility | Separate assessment/status, apply/retry and historical recovery as defined below; recovery never rewrites | review_apply_back/apply_back/recover_apply_back |
| Other commands on a V root | Not in the declared matrix | Refuse unsupported gate before client/writer; standalone audits/intake/decomposition use their own roots | existing protocol preflight refusal |

The initial declared routes are standard workflow with stateful-system profiles
and the fixed `standard-v1` rubric. Horizontal Phase 2 covers mid/final ×
permissive/strict; vertical is final/strict until other combinations are qualified.
Focused Phase 1 never grants Phase 2 entry. Both supported numeric metadata and
unversioned paths retain M3 semantics. Custom/MVP/governance workflows, distributed
writers, generic freeze resume and arbitrary supplied-draft editing are excluded.

### Proposed operation inputs

Reuse existing command names and ordinary selectors. Add only these V inputs:

- `vnext-decide --repair-request FILE` or `--gap-acceptance FILE` as mutually
  exclusive alternatives to `--selections`, for their respective closed Phase 2
  requests. Recording a request does not call an Editor or grant convergence.
- `strop` / `apply-back`: `--config`, `--approval FILE`, `--approval-hash HASH`,
  `--exclusive-source-access`, `--recover`, and `--retry-apply`. These supply
  operation inputs; none selects the editing mode.

### Exact V recovery and continuation routes

This table is the complete initial V `resume` surface. It does not change the
earlier R/P interfaces. Every row requires valid retained inputs, the pinned
consumer and fresh evidence validation under D8. Status reports the exact row,
request/transaction/pass references and proposed invocation; it cannot authorize
another row. Recheck the selected row inside the same fence as its mutation;
if another invocation completed it, return its result rather than falling through
to new work. `--dry-run` on any row performs reads only, with no client or repair.

Selection comes from the unique active committed request/transaction and current
verified lineage, not an arbitrary newest filename. An explicit `--vnext-round N`
must match that selection and is required where shown. Missing, ambiguous, stale
or conflicting evidence refuses before a client. Candidate selection follows
the candidate leaf's ordering/finality rules and its sole prepared-claimant
exception; no operator selector can choose an older candidate for new work.

| Retained condition / gate | Explicit invocation and evidence selector | Owner / client permission | End of this invocation |
| --- | --- | --- | --- |
| Current committed pointer has missing/stale permitted materializations | `resume`; select that pointer and its committed source | Verified materialization owner through its recovery branch; no client and no next promotion | Repair those projections and stop. |
| Interrupted registration or verification-decision publication, with all producer output complete | `resume --vnext-round N`; bind the retained transaction, candidate/creation evidence and exact pending decision | `recover_registration` or the existing verification commit owner; reuse complete bytes, no Editor/Verifier | Finish only that publication and its required projections; stop before verification, promotion or another request. |
| One valid prepared next-ordinal promotion claimant | `resume`; bind its exact intent, verified decision, ordinal and expected base | `promote` prepared-claimant recovery; no client and no fresh claimant selection | Complete that reserved promotion/materialization and stop, even if a later candidate exists. |
| Phase 1 terminal/report/state publication incomplete | `resume`; bind exact current closeout or retained failure/review evidence | Existing Phase 1 publication/reconciliation owner; no client | Publish/repair that outcome and stop before another review. |
| Phase 2 entry already committed but projection incomplete, or pending failure/correction-failure/resolution/signal/findings/blocked/closeout publication | `resume`; bind exact entry or active pass/outcome references | Existing entry and Phase 2 publication/reconciliation owners; no client | Complete that outcome's reports/state and stop. Mere configuration publication cannot authorize entry; uncommitted entry remains with `promote-phase2`. |
| Phase 1 Reviewer request interrupted and journal permits continuation | `resume`; select unique active Phase 1 review request/profile/cycle | `review_next(continuation=True)`; only that Reviewer request may use its remaining attempt/shape allowance | Retain result and required recovery/failure projections, then stop before finding admission or another role. |
| Phase 1 Editor proposal request interrupted and journal permits continuation | `resume --vnext-round N`; exact selected immutable plan/transaction/request | `request(..., continuation=True)`; only that Editor request's existing remaining allowance | Retain the proposal/failure and stop before registration, verification or promotion. |
| Phase 1 semantic request interrupted, candidate non-final and journal permits continuation | `resume --vnext-round N`; exact latest eligible candidate, base and semantic request | `verify(..., continuation=True)`; only that Verifier request's existing remaining allowance | Complete its verification decision/projections and stop before promotion. |
| Phase 2 Reviewer request interrupted, failure projections current and journal permits continuation | `resume`; select exact unique active pass ordinal and committed request | First pass: `run_phase2_review(continuation=True)`; later pass: `continue_phase2_pass(pass_number, action="execute", continuation=True)`; only that Reviewer request's remaining allowance | Retain the review/failure outcome and required projections; stop before consumption, advice, correction or the next pass. |
| Phase 1 additional-budget admission | `resume --extend-review-budget N`; bind the retained budget-exhausted context | `extend_phase1_budget`; explicit grant only, no client | Record grant and stop; a separate `live-phase1` invocation executes ordinary work. |
| External source-write uncertainty | `strop --recover --exclusive-source-access` (or `apply-back` alias); bind retained historical intent | Source readback/receipt owner only; no model and no source replacement | Return the reconciled historical result or explicit operator-attention state. |
| Any other condition | Refuse `resume` | No client or authority write | Includes exhausted/closed requests, final candidate rejection, corrupt/ambiguous authority, generic Phase 2 Editor/Verifier continuation, freeze and unchanged valid declaration disagreement. Supported report repair does not waive these refusals. |

Pending publication/projection recovery takes precedence over client continuation.
If such repair is needed, even `resume --continue` repairs and stops; the operator
must invoke continuation separately after inspecting the new status. Repair must
never silently spend the allowance whose failure it is reporting.

For V, `--continue` is an optional Phase 1 loop request after successful technical
continuation of the selected logical request. It resumes ordinary Phase 1 gates
within existing budgets and stops at a decision, failure, exhaustion or Phase 1
terminal. It is invalid on Phase 2, on source recovery, and when combined with
`--extend-review-budget`. Plain `resume` always ends at the boundary in the table.
Existing automatic shape-retry limits remain within a logical request; this
table grants no new retry slot. Complete retained valid output is reused without
calling a client. A live-command rerun, including `live-phase2` or
`promote-phase2`, cannot implicitly retry an interrupted request; it reports the
explicit continuation above or an unsupported/refused gate. An ordinary live
invocation after successful continuation may consume the retained result.

### Source assessment, write and historical recovery

These are distinct subcases of `strop` / `apply-back`. Do not run fresh-write
eligibility as a shared precondition for read-only diagnostics or historical
recovery. Ordinary config/suite and lineage validation still applies; historical
recovery does not excuse corrupt authority.

| Operation | Eligibility and evidence | Result / permitted effect |
| --- | --- | --- |
| Default read-only review/status | Inspect the V root and descriptor source binding; current convergence is evaluated, not required to produce diagnostics | Return an eligible assessment plus diff, or blockers with `assessment: null`. A retained intent also returns its historical readback status; no repair, new approval or source write. |
| New `--apply --approve` | Exact canonical assessment file/hash, current complete convergence, current verified pointer and unchanged descriptor-bound source; explicit exclusive access | Revalidate under D8 and perform only the approved M4 write/no-op. A different retained intent refuses; the same intent returns its retained result/recovery state without another write. |
| `--apply --approve --retry-apply` | Retained intent reports `apply_required`; same exact assessment/hash plus all current new-write eligibility and exclusive-access checks | Explicit further attempt, never automatic recovery or approval refresh. Stale pointer, convergence, source bytes or physical identity refuse a new write. |
| `--recover --exclusive-source-access` | Valid retained intent and its historical approved pointer/draft/convergence, with exact source identity/readback checks | Reconcile durability and receipt without replacing the source. Current-pointer advancement or loss of current new-write eligibility alone must not block historical reconciliation. Original bytes return `apply_required`; third/missing bytes or identity conflict require attention; completed evidence after drift stays historical. |

`--recover` cannot be combined with `--apply`, `--approve`, `--retry-apply`,
`--approval` or `--approval-hash`; it uses the retained intent rather than a fresh
approval file. No retained intent means `not_started`, with no source write or
receipt fabricated. New writes always require the exact descriptor source;
legacy mismatch/non-converged overrides remain invalid. Exclusivity is the
operator's assertion of actual exclusive source access throughout review, write
and unresolved recovery, not a lock acquired over other editors or runs.

Read-only stdout is the **review-result envelope**, not the approval subject.
It exposes `eligible`, `apply_back_permitted` (false during review), `blockers`
and `assessment`. Eligible review also includes `diff`; existing-intent review
includes `recovery`. For an ineligible review `assessment` is null; a source-less
descriptor yields blockers rather than a write target. The adapter preserves
these existing owner-result distinctions without adding fields to the frozen
`vnext-apply-back-review-v1` assessment schema. Referenced verified bytes and
evidence remain inspectable through their exact retained paths/hashes.

The approval subject is only the non-null `assessment` object. Save its D6
canonical JSON bytes as a separate file outside the run root. `--approval-hash`
is lowercase SHA-256 of those exact file bytes, not the envelope, diff, a pretty
JSON rendering or a newline-terminated variant. The adapter rejects a wrong
digest, noncanonical bytes, duplicate keys, an envelope submitted as assessment,
or a null assessment before the write owner runs. It validates the unchanged
assessment schema and then passes the packet to the existing M4 owner, which
revalidates current approval under D8.

For example, after the operator saves read-only stdout to `review.json` outside
the root, this local extraction creates `approval.json` without overwriting a
file and prints the value for `--approval-hash` (both paths must be outside the
run root):

```python
from pathlib import Path
from whetstone.vnext_contracts import canonical_json_bytes, decode_json, sha256_bytes

review = decode_json(Path("review.json").read_bytes())
if review.get("eligible") is not True or review.get("assessment") is None:
    raise ValueError("review has no approvable assessment")
raw = canonical_json_bytes(review["assessment"])
with Path("approval.json").open("xb") as output:
    output.write(raw)
print(sha256_bytes(raw))
```

Saving/extracting the packet grants no write permission. The operator must still
review the diff and evidence and explicitly invoke `--apply --approve` with the
assessment file/hash and exclusive-access acknowledgement. Read-only strop itself
does not write either file or publish/repair a run artifact.

## Section-addressed amendment set

The patch is the exact proposed text. The following identifies each owner and
why it needs an amendment. Existing D6/D7/D8 rules and public schemas remain intact.

| Owner | Sections changed | Bounded purpose |
| --- | --- | --- |
| Coordinating spec | Spec Family Map; vNext Admission And Capability Negotiation (D7) | Config/package/descriptor authority, fresh-root V bootstrap, Phase 2 Ref, declared commands and separate qualification/activation gates. |
| Candidate Editing And Promotion | Preservation Inventory; Patch Operation; Candidate Assembly; Deterministic Validation; Ratification Delta Map | Publish the exact M3 system-metadata exception while preserving Editor attribution, deletion and weakening gates; point to M4's scheduler owner. |
| Scheduler State And Resume | Accepted Draft Definition; Spec Version Lifecycle; Reporting And Slice Availability; new Verified-Promotion Source Write And Readback | Separate lineage and quality; route commands to existing owners; retain bounded recovery; publish the approved M4 lifecycle. |
| Artifacts Validation And Telemetry | vNext identity and suite-manifest invariant | Pin complete consumers and vectors; preserve closed schemas, immutable evidence and separate status/approval/outcome reporting. |
| Scope Intake And Decisions | vNext Decision Routing (D7) | Phase-aware operator contexts, exact repair/gap requests and new semantic follow-up transactions; no implicit approval or final-candidate reopening. |
| Phase 2 Convergence And Declaration | Phase 2 Failure Handling; Convergence Declaration | Complete fenced entry prerequisites, verified current bytes and current review evidence; no legacy executor or generic Phase 2 resume. |
| Operator Quickstart | Mental Model; Recommended Defaults; Create An Isolated Run; Recover A Timeout; Review Before Apply-Back; Apply Back | Publish the gated matrix/configuration, distinguish proposed operands, and prevent legacy examples from implying V authority. |

### Trace of all 14 existing ratification surfaces

This trace covers the candidate leaf's existing delta map. It records retained
rules as well as proposed changes; it does not mark implementation or release
qualification complete.

| Existing surface | Q1 disposition |
| --- | --- |
| Family routing and role authority | Retain existing candidate/Verifier routing; update coordinating M4 ownership wording. |
| Run inputs, outputs, configuration, and design principle | Add config-selected D7 admission; retain current-pointer authority and untrusted Editor output. |
| Halting and terminal artifacts | Retain D7 precedence/failure categories; require command stops and separate current diagnostics without rewriting historical failures. |
| Verified lineage versus quality state | Add explicit scheduler acceptance distinction and verified metadata lifecycle. |
| Proposal-to-promotion scheduling | Route the declared commands through existing verified owners; prohibit legacy full-draft dispatch. |
| Budgets, retries, resume, and read-only status | Retain pinned budgets/finality and exact recovery; document supported continuations and explicit Phase 1 grants only. |
| Public artifacts, locking, and attempt semantics | Retain D8/closed artifact rules; require the new consuming suite and command diagnostics to bind them. |
| Current full-draft preservation bridge | No new bridge behavior or propagation; retain existing bridge validation and version-restoration refusal. |
| Versioned normalization and hashing | Retain exact-byte descriptor/algorithm binding; new suite pins delivered metadata and source consumers without mutating old suites. |
| Scope, finding admission, authority, and decisions | Retain classification/decision binding; add phase-aware command routing and exact request inputs. |
| Phase 2 and convergence lineage | Add explicit current verified entry/declaration consumption; retain target and reproducibility rules. |
| Operator defaults and recovery guidance | Config opt-in, fresh root, matrix and bounded recovery; no new default activation. |
| Current strop/apply-back operational surface | Exact assessment/approval, source guards, exclusive-access assertion and separate readback recovery. |
| Strop/apply-back normative ownership designation | Publish approved M4 rules in scheduler and update coordinating/candidate references. |

The earlier inventory counted 13 because its parser included the separator and
excluded two rows beginning “Current.” The inventory now records 14 substantive
rows. Frozen raw evidence and the 22 P0 classifications are unchanged.

## Implementation boundary and exit evidence

After approval, deliver Q1 as one package: apply the bounded owner amendments,
stage the immutable consuming suite, implement shared config/bootstrap and command
adapters, and demonstrate the declared supported and refusal routes. Reuse the
internal M1–M5 owners; do not build another scheduler or verification engine.
Keep production qualification maps disabled throughout this work.

The plan's seven acceptance cases remain the finish line:

1. Fresh config-selected admission under an explicitly pinned non-shipping suite.
2. Unknown/unqualified suite and conflicting selectors: zero clients/authority writes.
3. Reopen retains immutable mode; config edits cannot upgrade an existing root.
4. Supported journeys use genuine verification, promotion, distinct Phase 2 entry
   and convergence, including metadata and unversioned paths.
5. Status/recovery expose supported actions without duplicate calls or promotions.
   Cover repair-only reentry (including `--continue`), eligible first/later Phase 2
   Reviewer continuation, exhausted refusal and refusal of an implicit retry
   through an ordinary live command. Verify the exact stop point in each row.
6. Source apply remains separately approved and exact-bound, tested only on
   disposable fixtures, including uncertain-write recovery after pointer advancement
   and historical completion after source drift. Cover eligible/blocked/existing-intent
   review envelopes and canonical assessment extraction, exact-hash apply, and
   refusal of envelope/null/noncanonical/mismatched approval files.
7. Existing legacy/bridge/reviewer-only/proposal behavior and public V refusal persist.

Q2 retains its seven specific P0 gaps. P0-12 still needs the original historical
recurrence golden fixture. P0-13 needs an independent implementation comparison;
replacing that requirement requires a concrete separate normative decision, not
two processes of the same implementation. P0-07 needs exact token/time-budget-stop
evidence; bring back a decision if that requires new accounting policy. Q3 owns
replay performance and final deterministic qualification. Q4 owns separately
authorized provider transmission, live soak and activation. This proposal waives
none of those gates.

## Approval and validation status

The approval requested next is limited to this amendment/interface package and its
Q1 implementation with activation disabled. M3/M4 policy is already approved;
publication into authoritative owners and the new public interface details are
pending. No push, live provider transmission or real source apply-back is implied.

The [initial bounded audit](audits/VNEXT_18_9_Q1_BOUNDED_AUDIT.md) found three
interface gaps. This revision fixes Q1-A1 with the finite recovery/continuation
subtable, Q1-A2 with separate source-operation preconditions, and Q1-A3 with the
review-envelope/canonical-approval contract. The
[focused recheck](audits/VNEXT_18_9_Q1_FIX_RECHECK.md) records their disposition;
the earlier audit remains historical evidence. Ratification and implementation
are still pending.

Preparation validation is document-only: patch application check, source/proposed
hashes, approved-rule preservation, matrix/delta counts, local links and whitespace.
The [proposal evidence record](audits/VNEXT_18_9_Q1_PROPOSAL.json) records results
and baseline hashes. No product test campaign, clients or real source writes were needed for
this preparation. A local canonical-approval round-trip check accompanies the fixes. All changes remain uncommitted.
