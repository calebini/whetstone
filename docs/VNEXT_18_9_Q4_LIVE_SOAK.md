# Q4 — isolated live soak and activation decision

Status: **Q4-009 resumed for three remaining calls and promoted the approved
ledger change (ordinal 2), then stopped at round-4 authority finding
iss_721994ea1dcd453a. All eight calls are consumed. Q4 remains incomplete and
public activation remains disabled.**
Q3 is closed with the operator's explicit correctness-risk and performance
acceptances. Q4 remains incomplete until live evidence is assessed and activation
is explicitly decided. The finite Q4 scope remains the inventory's live soak,
successful/rejected proposal inspection, operator guidance and activation decision.

## Later-Reviewer history correction — current handoff

2026-10-18: **Phase 1 correction reviewed and Phase 2 decision-history support
implemented locally. Q4 remains open.** The current pass is recorded below;
the 2026-10-17 evidence remains a historical baseline. Live outcomes and the
unresolved round-4 finding are unchanged.

### Phase 2 implementation and Phase 1 review — 2026-10-18

The local review found one source-recheck gap: a reused proof returned cached
history without rereading its historical files. History reads now recheck every
projected source reference and the current pointer/descriptor guard. The production
integration test removes and tampers with the response under both reused and fresh
proofs; both refuse.

New Phase 2 requests use the same proven-ancestry projection through the shared
first/subsequent/declaration/review-only renderer. History and explanatory guidance
are bound into immutable input/prompt hashes, and historical references join the
existing source synchronization barriers. Historical approval remains explanatory,
not reusable authority. The owning candidate spec records this presentation and
compatibility boundary; no digest-pinned schema or algorithm changed.

Exact prior-format inputs select prior rendering, including an interrupted
inputs-before-prompt prefix. Old timeout continuation preserves prompt bytes and
spent slots. Arbitrary packets, missing committed dependencies and replacement of
new inputs with exact old rendering still refuse under full request validation.

Verification: **8 focused tests passed in 200.184s**, followed by **22 regression
tests in 564.756s** (28 distinct methods across the two cohorts). The later cohort
adds old execution continuation and strengthens the downgrade check to exact old
input bytes; the shared runtime source is unchanged between cohorts. All 320
suite-pinned artifacts, 168 retained live-run files and six unrelated dirty files
retain their recorded hashes; `git diff --check` passes. Evidence is retained in
`rounds/vnext-phase2-decision-history-001/`. The nonempty-history test traverses
real Phase 1 decision admission, verification and promotion into Phase 2 entry and
request binding, including source synchronization failure and tampered history.
Later-sequence and declaration-closeout tests provide regression coverage; they
are not additional decision-bearing full journeys. Decision-bearing orphan and
rejected-candidate journeys remain outside this bounded pass.

No live provider calls, activation, commit, push or external apply-back occurred.
The next live step still requires a supported resolution/fresh-run plan and fresh
provider authorization. Do not silently dismiss or rerun the immutable round-4
finding; the previous eight-call allowance is exhausted.

### Phase 1 baseline — 2026-10-17

`vnext_reviewer_decision_history.py` derives evidence during successful original
transaction and final semantic replay. `_Proof` retains detached canonical history
for each proven base. New Phase 1 Reviewer input and prompt identities include the
selected base's history, with original finding/plan, request/response, effects and
promotion linkage. Guidance distinguishes the actual admitted seed, historical
explanations and current mutation authority; it does not instruct the Reviewer
to pass. Existing exact prompt renderings retain their earlier input identity.
No digest-pinned contract artifact was modified.

The handoff's failing test was reproduced: altered old prompt bytes fail the
immutable claim/input check before the more specific prompt check. Its assertion
now names that earlier refusal and also verifies no writes or client calls.
Investigation additionally reproduced an actual recovery bug: an old request
claim can be published before `original_prompt.txt`, so prompt-only version
selection assigned the new input identity to the interrupted old claim. The fix
recognizes only the exact old input hash when the original prompt is absent;
normal full-header, predecessor, transport and attempt checks still apply. A new
regression verifies read-only inspection, explicit continuation, unchanged claim
bytes and exactly one first invocation. It does not restore spent slots.

Verification on final source:

- `test_vnext_reviewer_decision_history` plus
  `test_vnext_verified_review_requests`: **17 tests passed, 154.476s**.
- Related prefix, replay memo, genuine history, production Reviewer integration
  and Phase 2 request replay cohort: **19 tests passed, 237.995s**.
- `git diff --check` passed. All **320** suite-pinned artifacts and **168** sealed
  live-run files match. Unrelated distribution documents, README, notes and audit
  files retain their starting hashes. No live provider invocation or Q4 restart.

Evidence: `rounds/vnext-reviewer-history-reconciliation-001/`; `reproduce.log` and
`claim-before-fix.log` preserve the two pre-fix failures, `final-cohort/` and
`related/` retain successful commands, supervision and logs. The earlier 16-test
pass predates the claim-only recovery fix and is not the final-source result.

| Boundary | Evidence and limit |
| --- | --- |
| Approved history visibility and original-context binding | Real production admission, candidate registration, semantic verification, promotion and next Reviewer request; checks original source pointer/request/response and current promotion linkage |
| Unpromoted/future exclusion | Real registered candidate has empty history before promotion; reading the seed after promotion still returns empty history; related prefix tests reject future/self-supporting claims |
| Missing/tampered evidence and omission | Production-path tests remove/corrupt a committed response and remove history from the new retained prompt; all refuse without calls or writes |
| No reusable grant | Same production test refuses the old selection for a new weakening choice; historical source remains bound to its original base |
| Old request compatibility | Exact completed replay, timeout continuation, immutable tamper refusal and old claim-before-prompt recovery; existing new-request interruption/slot tests pass |
| Projection isolation/completeness | Five pure tests cover detached values, unused decisions, missing/tampered sources and incomplete used decisions; these alone are not end-to-end qualification |
| Orphan/rejected/unrelated decisions | Excluded structurally because only the proven promoted transaction is projected; this pass does not add separate full journeys with decision-bearing orphan and rejected candidates |
| Phase 2 at this baseline | Request replay regression only; superseded by the 2026-10-18 implementation above |

Baseline readiness was Phase 1 only. The 2026-10-18 pass above completes the
bounded Phase 2 implementation and records the remaining qualification limits.

## Reconciled authority and handoff — 2026-10-17

This section records the reconciliation baseline; the correction handoff above
provides the latest implementation status. Subsequent dated run entries are historical.
The authoritative family routes through the coordinating spec to its owning
leaves. This soak log records evidence and authorization, not new runtime policy.

| Item | Permanent owner / disposition | Evidence and remaining limit |
| --- | --- | --- |
| Reviewer scope guidance | Existing authority/scope contracts; implementation fix already in `1b813be` | Strict scope validation retained; not a new scope grant |
| Phase 1 selector consumption | Scope Intake And Decisions spec, D7 routing | Uncommitted command fix; one integration regression passed in 315.146s, including stale reentry refusal |
| Editor exact payload hashes and automatic correspondence guidance | Candidate Editing And Promotion spec, Client guidance and immutable prompt compatibility | Uncommitted prompt/replay changes; 33 focused tests passed in 12.205s; actual Editor success in Q4-008 and Q4-009 |
| Verifier copyable coverage hashes | Candidate Editing And Promotion spec, Independent Semantic Verification | Uncommitted prompt/replay changes; 47 focused tests passed in 130.515s; actual Verifier success and promotion in Q4-009 |
| Historical Editor/Verifier prompt replay | Candidate leaf, Client guidance and immutable prompt compatibility | Exact known renderings only; completed reuse/tamper rejection tested; no exhausted request reopened |
| Nested skill discovery isolation | Private Q4 wrapper only | Local prompt-render check and observed traces; no production adapter guarantee and no filesystem-read isolation claim |
| Model, round, call and time budgets | Exact run package and provider authorization | Luna/medium, seven rounds/profile are test settings, not Whetstone defaults; five of eight actual calls used in Q4-009; old window expired |
| FIFO start/record, uniqueness, retry/resumption and attempt-ledger policy | Synthetic queue spec plus exact operator selections | Requirements for the document being sharpened, not Whetstone's request journal or scheduler; latest ledger selection bound but no corresponding draft edit yet |

The queue policy covers entry into job execution, durable start recording before
execution, same-ID retries, uniqueness in its record store, automatic same-process
resumption only under the approved conditions, and manual restart reconciliation.
The latest decision adds durable allocation of the ID/job association before the
start-record write. It leaves ID format/storage implementation-defined. These
choices do not amend Whetstone's existing two-slot invocation accounting or its
explicit technical-continuation rules. Approval is scoped to exact run evidence;
it is not a blanket policy for other specs or jobs.

The three relevant algorithm supplements (`vnext_proposal_requests_v1`,
`vnext_semantic_requests_v1`, `vnext_semantic_coverage_v1`) are pinned by
`vnext-verified-consumer-1`. This reconciliation preserves their exact bytes,
the suite digest and all schemas. The owning leaves now explain the compatible
prompt and command behavior; no identity, validation, retry or storage protocol
change is introduced. Historical isolated-component status paragraphs in those
frozen supplements are not the current release capability inventory.

Verification was checked against retained logs, source changes and sealed
outcomes: `rounds/vnext-18-9-q4-selector-fix-001/integration-rerun/tests.log`,
`rounds/vnext-18-9-q4-008/tests.log`, `rounds/vnext-18-9-q4-009/tests.log`,
`rounds/vnext-18-9-q4-009-continuation/live-outcome.json`, and
`rounds/vnext-18-9-q4-009-ledger-decision/binding-outcome.json`.
These are prior execution results, not fresh test runs during reconciliation.
Reconciliation checks: `git diff --check` passed; all 320 manifest-pinned
algorithm/schema/fixture hashes matched; existing notes and audit-file hashes
were preserved. This pass changes documentation only.
One successful live promotion does not establish Phase 1 completion, Phase 2
coverage, equivalent model quality or full Q4 qualification.

Remaining work: assess successful and rejected proposal evidence against the
finite Q4 inventory, complete the outstanding live journey/Phase 2 coverage,
finalize operator guidance, and bring back an explicit activation decision.
Before another transmission, prepare and authorize a new bounded execution
window; the three unused calls do not extend the expired window. Any continuation
must use the bound ledger selection and revalidate the exact package, sources,
current pointer and remaining budgets. Generalizing nested skill isolation would
be a separate production change with adapter tests; it is not completed here.
No live continuation, public activation, external apply-back, commit or push is
part of this reconciliation.

## Concrete first run

The prepared input is a synthetic, versionless FIFO queue specification under
`rounds/vnext-18-9-q4-001/package/`. It contains no external project specification.
It preserves a 30-second minimum interval, FIFO order, and one start record per
job with identifier and UTC timestamp. Repetitive reporting prose gives the
Reviewer a possible clarification/simplification target; findings and successful
promotion are not scripted or guaranteed. Models must not invent product policy.

The immutable package pins `vnext-verified-consumer-1` with digest
`7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58`.
It selects horizontal structural-integrity, determinism and operability reviews
with two reviews per profile, one operation/changed section/changed normative
unit per proposal, and only `replace_section_body`. It grants no deletion,
weakening, compatibility policy or external source-write authority.

`prepare.py` validated the package with the real bootstrap reader. `launch.py`
passed the real `vnext-admit --dry-run` route without creating a destination or
making a provider call. Sources remain pinned to `c9d1dae`; `prepared.json`
records input and source hashes. The private harness temporarily supplies only
this exact suite's gate inside its process. It does not change production maps,
source code, provider responses or native adapters. The gate is empty again
after the command. This mechanism needs approval as part of the isolated soak;
it is not public release qualification.

## Provider authorization — approved 2026-10-15

The operator approved the exact provider payloads and bounded isolated run on
2026-10-15. `provider-authorization.json` binds the approval to the original
prepared manifest and launcher hashes. The scope below remains unchanged.

- Provider: OpenAI through `/opt/homebrew/bin/codex`, observed CLI version
  `0.142.0`; model `gpt-6.1-sol`, matching the configured local model. The existing
  native adapter selects medium reasoning, disables web search, ignores repository
  rules and uses its read-only client sandbox. No Claude transmission is proposed.
- Permitted source files: `package/inputs/seed.md`, `authority.json`,
  `invariants.json`, `review.json`, `mutation-constraints.json` (all four latter
  names are under `package/inputs/`), `package/job_descriptor.json`, and
  `package/proposal_package.json`, relative to `rounds/vnext-18-9-q4-001/`.
- Also permitted: built-in Reviewer/Editor/Verifier prompt text and output schemas,
  plus this isolated run's derived section maps, inventories, findings, mutation
  plans, candidate text, preservation reports and verification context. These
  future bytes are bounded to the named synthetic inputs and their live outputs;
  they cannot be precomputed before the preceding client returns.
- Command scope: one `live-phase1` invocation against the fresh isolated `run/`
  destination, real native Reviewer/Editor/Verifier clients, at most eight actual
  provider calls including shape retries, 600 seconds per provider call, one
  supervisor at 60% duty, 180-second lease and 1800-second total hard cap.
- Stop on returned halt/operator decision, exhaustion or deadline. No automatic
  new invocation, resume, budget extension, new authority decision, Phase 2,
  external apply-back or activation is included in this first window.

The normal API remains gated. `launch.py --run` requires an affirmative local
authorization receipt bound to the exact prepared manifest and launcher hashes;
that receipt was created after the explicit operator approval. Approval does not
permit substituting a different model or silently repeating the bounded window.

The named boundary comes from the Q4 inventory requirement to “separately authorize
exact provider payloads” and the runner skill's instruction to include an explicit
authorization block naming transmitted files before a live nested-client run.

## Evidence and remaining qualification

The live harness will retain each exact prompt/schema before transmission,
call timing and outcome, the command result and ordinary durable run artifacts.
An interrupted command is not a completed soak. Inspect actual verified pointer,
candidate decisions, status and reentry; do not infer promotion from model prose.

This first window measures actual Phase 1 behavior and can reveal transport,
schema, preservation or latency problems. It does not by itself close Q4. Inspect
successful and rejected proposal evidence, explicitly note any unobserved outcome,
then complete the required live journey/Phase 2 coverage with bound inputs and
operator authority. Never manufacture a passing or rejected verdict to fill a
coverage row. Stop for any product/authority choice. Final operator guidance and
the activation decision follow the live evidence. No commit or push is implied.

## First live-window result

The approved command ran on 2026-10-15. The supervisor exited cleanly with code 2
after 16.128s. Exactly one native Reviewer provider attempt occurred, lasting
3.232s. The provider rejected the configured model with HTTP 400:
“The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account.”
The CLI also reported model-cache metadata warnings; those are retained, but
the explicit unsupported-model response is the blocking result.

No Reviewer response, Editor or Verifier invocation, candidate or promotion was
produced. Whetstone retained the transport failure and reports pending Reviewer
continuation. Read-only `status` returned code 0 without changing run files;
the committed pointer remains at seed ordinal 0. This is a failed live-soak
attempt, not completed live qualification or a measure of useful-work latency.
All workers stopped; no retries, fallback model, Phase 2, external apply-back
or public activation occurred. Runtime, contracts and approved package inputs
remain unchanged.

`provider-calls.jsonl`, the exact prompt/schema, the ordinary request journal,
`live-command.json`, `post-stop-status.json`, `live-supervision/` and
`live-outcome.json` retain and join the evidence. The configured local model
was not evidence of availability through this CLI/account transport.

Next: select an account-supported model and prepare a new bound package for
approval. Review/model identity is immutable, so a different model must not be
substituted into this retained request's technical continuation. Preserve this
failed run and its approval receipt; a changed identity needs a fresh isolated
run. Q4 live success/rejection and subsequent journey coverage remain unobserved.

## Q4-002 — embedded CLI and invalid Reviewer advice

The operator requested the app's embedded CLI, then authorized proceeding with
the newly prepared package. The new run under `rounds/vnext-18-9-q4-002/` uses
`/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`,
version `0.162.0-alpha.17.2`, with the same `gpt-6.1-sol` model. The synthetic seed
and preservation requirements are unchanged. The actor/version and derived
job/configuration identities are newly bound; the first failed root and its
evidence remain intact. Local package/CLI preflight passed before transmission.
The same eight-call, 30-minute, 60%-duty limits apply, with a hash-bound approval.

The supervisor exited cleanly with code 2 after **64.612s**. Two native Reviewer
calls returned model responses, in **10.434s** and **24.960s** respectively. The
first structural-integrity review was valid and clean. The second, determinism
review supplied section IDs in `scope_surface_ids`, despite the package having
no scope contract. Whetstone rejected it as `invalid_review`, with the reason
`$: scope surfaces supplied without a scope contract`. Provider access through
this embedded CLI is therefore demonstrated; successful candidate production
and promotion are not.

The rejected response also suggested a clarification about elapsed time versus
UTC clocks and requested an operator decision about exactly-one recording after
failed or uncertain writes. Those are raw, unadmitted findings, not authorized
edits or committed operator work. No response was repaired or replayed, no model
was substituted, and no product decision was invented. The command returned
pending review with no technical continuation advertised. No Editor or Verifier
ran; no candidate or promotion exists, and the current pointer remains at seed
ordinal 0. Read-only status preserves the retained run files.

The two exact prompts/schemas, responses, request outcomes, command/status packets
and supervisor result are retained and joined by `live-outcome.json`. Runtime and
contract sources are unchanged; all workers stopped. This is not a completed
Q4 soak or rejected-*candidate* coverage: the rejection occurred at Reviewer
advice admission before a candidate could exist.

Next recommended work is a bounded investigation of the native Reviewer guidance
for authority scopes, scope-contract surface IDs and section IDs, followed by
focused verification of any justified guidance fix. The rejection check must
remain intact. Any genuine product choice needed by a subsequent valid review
must return to the operator. No automatic live retry or activation is authorized
by this completed window.

## Reviewer scope guidance fix — 2026-10-16

The retained second prompt embeds `scope: null` and the section/authority maps,
but does not explain the classification identifier namespaces. Its Codex output
schema permits string arrays and cannot express this input-dependent constraint.
The strict classifier correctly rejects the response; this is a prompt guidance
gap, not authority to relax admission or repair retained model output.

Fresh verified Phase 1 Reviewer requests now explicitly distinguish canonical
section anchors, authority scopes, authority binding IDs and scope-contract
surface IDs. With no scope contract, every classification must supply
`scope_surface_ids: []`. With a contract, only its declared surface IDs apply;
unresolved scope cannot create authority. Product decisions still require the
operator. Decoder, classifier, schemas, contracts and legacy/bridge prompts are
unchanged.

Historical replay compares exact prompt bytes. The renderer therefore recognizes
only the exact previous deterministic rendering for retained requests, preserving
their original instructions during readback and authorized technical continuation.
It does not accept arbitrary stored prompt text. Fresh requests use the new
guidance; invalid reviews remain terminal and cannot be retried as shape errors.

Focused offline coverage checks identifier rejection, valid declared surfaces,
no retry after invalid advice, historical prompt replay/continuation and prompt
tampering. The original Q4-002 responses were decoded read-only: round 1 remains
valid and round 2 still fails with the identical scope-contract error. Evidence
is retained separately under `rounds/vnext-18-9-q4-scope-guidance-001/`.

Verification: 40 tests across verified Reviewer requests, classification and
proposal Reviewer requests passed in 117.217s; the separately added historical
continuation test passed in 1.674s (41 distinct methods total). Its initial test
assertion incorrectly expected `continuation_required` at first timeout and was
corrected to the existing `timeout` status. All 112 prior sealed evidence hashes
and protected notes/audits are unchanged; `git diff --check` passes.

This fixes the guidance defect; whether a live model follows it remains untested.
Q4 remains open. Next is a fresh isolated, newly bound live package using the
updated sources, with exact payload authorization before transmission. Neither
completed Q4 root should be modified or resumed to test this fix. No live call,
public activation, external apply-back, commit or push occurred in this fix.

## Q4-003 — guidance retest and product-decision stop

On 2026-10-16 the operator authorized committing the guidance fix and running
another test. Commit `1b813be` checkpoints the fix, focused tests and Q3/Q4
handoff. Unrelated notes and audit reports were excluded. The fresh isolated
package under `rounds/vnext-18-9-q4-003/` binds that source commit, the same
synthetic seed and requirements, embedded CLI and `gpt-6.1-sol`. Offline preflight
passed. Authorization is bound to the package/launcher hashes; limits remain
eight calls, 30 minutes, 60% CPU duty and a 180-second supervision lease.

The command completed with exit 2 after **61.272s**, with two returned Reviewer
calls (11.194s and 26.968s). Both responses passed validation. The second used
empty `scope_surface_ids` as required. The first review was clean; the second
raised one valid major determinism finding: the job-start event is undefined
(dispatch, worker acceptance, or entry into execution), affecting the 30-second
interval, FIFO start order and UTC start record. Its admitted classification is
`operator_decision_required`; the command gate is `finding_admission`, and
technical resume is not permitted in place of operator selection.

This demonstrates live compliance with the corrected scope guidance in this run,
not Q4 completion. No Editor, Verifier, candidate or promotion ran; the pointer
remains at seed ordinal 0. No product choice, response repair or automatic retry
was made. Next requires an explicit choice for this synthetic fixture. Recommended
semantics are entry into job execution, used consistently across timing and
reporting, subject to the existing operator route and mutation bounds. The
30-second interval, FIFO order and exactly-one record requirement remain protected.
Do not silently expand the one-section mutation limit to resolve a two-section
finding. Public activation and external apply-back remain disabled.

The retained prompts, responses, receipts, command/status packets and supervisor
result are joined by `live-outcome.json`. This result documentation is subsequent
to the requested checkpoint; it has not been committed or pushed.

### Q4-003 continuation — approved start boundary, section-budget refusal

The operator approved entry into job execution as the job-start boundary and
authorized continuing the bounded test. The ordinary `vnext-decisions` and
`vnext-decide` paths previewed and published the exact round-2 request/response
and selection, retaining the original finding classification. The selected
option authorizes clarification only, with no deletion or weakening, and binds
the shared event to FIFO, the minimum interval and the start record timestamp.

The subsequent `live-phase1 --vnext-decisions <selection>` invocation stopped
after **14.016s**, before any provider call, with `vnext_input_invalid`:
`$: admitted surface exceeds section budget`. Admission counts both target
sections named by the finding (Timing and Reporting); its immutable budget is
one section. A proposed one-section textual clarification does not narrow that
admitted target set. The previous guidance that this might fit one section was
therefore insufficient for this admission rule.

The approved product choice is retained. No candidate, promotion, source change
or new model call occurred. The continuation reserved six remaining provider
calls and 1738 seconds, preserving the original eight-call/30-minute aggregate
live-execution bounds; none of the remaining calls were consumed. Evidence is in
`rounds/vnext-18-9-q4-003-continuation/`, including the options, selection,
authorization, command result, read-only status and sealed outcome.

Next requires a fresh immutable test package. The smallest recommended budget
change is `max_changed_sections: 2`, retaining `max_operations: 1`,
`max_changed_normative_units: 1`, replacement-only editing and every protected
requirement. This admits the two-section finding while still allowing only one
bounded replacement. Do not change the retained package, alter the Reviewer
targets, or relax the admission check to continue. Budget expansion awaits
operator approval; Q4 remains open. No commit or push occurred.

### Q4-004 — approved two-section package, recording-failure decision

The operator approved a fresh package with `max_changed_sections: 2`, retaining
one operation, one changed normative unit and every protected requirement. The
new isolated package under `rounds/vnext-18-9-q4-004/` passed preflight. Its seed,
authority and review configuration remain unchanged; only the mutation budget
and derived package/config references differ. The earlier run and bound start
decision remain intact. Their receipts cannot be transplanted to a new review.

The run retained six available calls and a 1724-second cap, accounting for the
two calls and 75.288 seconds already used in Q4-003 and its continuation. It
completed with exit 2 after **77.379s**, making three valid Reviewer calls
(11.536s, 12.501s, 17.022s). Structural integrity and determinism returned clean;
operability raised a different major finding about failed or uncertain creation
of the exactly-one start record. Its classification is
`operator_decision_required`, with gate `finding_admission`.

The approved execution-entry choice does not specify recording-failure or
reconciliation behavior. It was not broadened or bound to this different finding.
No Editor, Verifier, candidate or promotion ran. The pointer remains at seed
ordinal zero. Three calls remain within the aggregate eight-call cap; no further
call is authorized until the new product decision is resolved. This run shows
fresh-package admission and valid review, not a successful correction or Q4
completion. Read-only status and sealed outcome retain the stopped state.

Next decision: define how record creation relates to entry into execution, what
happens after failed or uncertain creation, and how that failure is exposed,
while preserving exactly one record per started job. Do not invent this policy,
weaken the invariant, or rerun until a model returns clean. No source-code change,
public activation, external apply-back, commit or push occurred.

### Q4-004 continuation — recovery decision, verified promotion and selector boundary

The operator approved pause-on-failure/reconcile-before-retry recovery, retaining
execution entry as the start boundary and excluding automatic crash recovery.
The ordinary decision commands previewed and bound the exact round-3 finding
with clarification/addition effects only, no deletion or weakening grants.
The request preserves stable execution-attempt IDs, same-ID lookup/retry after
uncertain writes, no execution after definite recording failure, visible errors,
and operator reconciliation if execution entry itself is uncertain. All original
invariants and the one-operation/one-normative-unit limits remain enforced.

The authorized continuation used the final **three provider calls** in **341.976s**:
Editor 38.752s, Verifier 32.723s, and post-promotion Reviewer 22.845s. The Editor
appended the approved policy in Reporting through one section-body replacement.
The candidate passed deterministic registration and semantic verification, then
committed as **promotion ordinal 1**, draft hash
`d73f6b31ac3e0e4a447aa2b018ac29204610c13b342638153d56e0f35102cf7c`.
This supplies live successful-candidate/verification/promotion evidence; it does
not establish convergence or complete Q4.

Round 4 structural-integrity review was valid and raised a major
`operator_decision_required` finding: the paused state has no explicit exit actor
or conditions after recording failure/uncertainty is resolved, nor explicit
retention of the pending FIFO job and attempt ID through resumption. No new
policy was inferred from the previous approval.

The CLI returned exit 2 with `vnext_input_invalid: noncanonical operator selection`,
not a normal operator-gate packet. Inspection of the command loop shows the
unchanged round-3 `--vnext-decisions` selector being used again at the subsequent
round-4 finding-admission gate; its exact-round validation correctly refuses.
The live result therefore identifies a command handoff defect to investigate:
consume the selection only for its bound round, preserving rejection of stale
selectors at command entry. No runtime fix or automatic retry was attempted.

Evidence and exact operator inputs are under
`rounds/vnext-18-9-q4-004-continuation/`. The aggregate eight-call budget is now
exhausted. Next work is the bounded selector-lifetime investigation and an
explicit resumption-policy decision before any further live window. Previous
approvals and this verified promotion do not authorize those additional calls.
Public activation, automatic crash recovery and external apply-back remain out
of scope; no commit or push occurred.

Post-stop `status` returned code 0 without changing run files: Phase 1 round 4,
`finding_admission`, no technical continuation or recovery, verified ordinal 1.
The only changed preexisting run artifacts are the current pointer, run-state
projection and `spec.md`; original inputs and review evidence remain unchanged.
All supervised workers stopped, and the single-worker lock is available.

### Selector lifetime fix and proposed queue-resumption policy

The Phase 1 command loop now consumes its invocation-local decision selector
only after successful fenced admission. A later round follows normal admission
and returns its own operator context. The original command arguments, stored
receipt and strict owner checks remain unchanged; a fresh invocation explicitly
supplying the old receipt still refuses against the current round. No validation
fallback, automatic receipt selection or changes to legacy/bridge behavior are
introduced.

The focused offline regression follows real operator publication, selected round
admission, scripted Editor/Verifier calls and promotion, then a later blocking
review. It checks the ordinary operator-gate result and that stale-selector
reentry makes no writes or client calls. Evidence is retained under
`rounds/vnext-18-9-q4-selector-fix-001/`; no live calls are part of this fix.
The first regression attempt exposed a fixture setup error: its inherited
one-round budget stopped the command after promotion, before a later decision
could occur. That failed assertion is retained; the fixture now explicitly binds
two review rounds. No runtime change was needed for this fixture correction.
The corrected end-to-end regression passed in **315.146s** at 60% duty. It proves
one promotion followed by a normal later operator gate, and refusal of the old
selector on fresh reentry with unchanged files and client counts. The supervisor
exited successfully; all retained live Q4 continuation files remain unchanged.
`git diff --check` passes. This is offline regression evidence, not another live
qualification window; no commit or push occurred.

Recommended product choice, **not yet approved or bound**: explicit operator
resume after recording failure/uncertainty. Keep the pending FIFO job and stable
attempt ID; require a confirmed existing start record for that attempt and
confirmation that execution has not begun before resuming it. The 30-second
spacing constraint still applies. If execution entry is uncertain, remain paused
for operator reconciliation; do not automatically reexecute or allocate a new
attempt ID to bypass uncertainty. Resolving the record-write outcome alone does
not automatically resume the queue. The exhausted live-call budget still needs
separate authorization before further testing.

### Q4-005 preparation — automatic same-process resume, manual crash recovery

The operator selected automatic resume for recoverable recording failures,
superseding the unapproved explicit-operator-resume recommendation above. The
approved actor is the same running queue process. It may resume the pending FIFO
job only once the same attempt's start record is confirmed durable, execution is
known not to have begun, and the 30-second spacing rule permits execution. The job,
FIFO position and original attempt ID persist through pause and reconciliation.
Restart, uncertain execution entry or unresolved record state requires remaining
paused for manual reconciliation. No automatic crash recovery, duplicate record,
replacement attempt ID to bypass uncertainty, deletion or weakening is authorized.

Preparation under `rounds/vnext-18-9-q4-005/` binds this choice to the retained
round-4 finding and current promoted base through the ordinary decision commands.
It uses the existing Q4-004 run; it does not reset review budgets or copy receipts
to another job. The one-operation, two-section and one-normative-unit limits
remain unchanged. The prepared source manifest includes the tested, uncommitted
selector-lifetime fix. A later source change requires refreshing that manifest.

The proposed next live window is eight provider calls, a 30-minute hard cap,
600 seconds per provider call, 60% CPU duty and a 180-second supervision lease.
This is a new proposed allowance; the previous eight-call budget stays exhausted.
It uses the same embedded Codex CLI and `gpt-6.1-sol`, starts with the exact
round-4 selection, and stops on a decision, failure, deadline or call cap. No
Phase 2, automatic retries, public activation or external apply-back are included.
Provider authorization remains false until execution is explicitly authorized.
The user requested binding and preparation only; no live call, commit or push
is part of this preparation.

Preparation completed: the exact decision selection is retained under round 4;
provider-free status passed without run-file changes and still reports
`finding_admission` at verified ordinal 1. A launch attempt with the unapproved
authorization file was correctly refused before provider activity. Prior evidence
and preexisting run files are unchanged; only new decision artifacts were added.
`preparation-outcome.json` seals the inputs, launch instructions, checks and run
snapshot. No provider worker was started.

### Q4-005 live result — second verified promotion, review-budget stop

The operator explicitly authorized the prepared eight-call, 30-minute window.
All prepared source/input/run hashes were checked before recording authorization;
the previous false authorization record was retained separately. The command
completed with exit 2 in **847.191s (14m07s)** at 60% CPU duty, below the cap.
Exactly two provider calls returned: Editor **45.682s**, Verifier **44.945s**.

The automatic-same-process-resume correction passed registration and semantic
verification and committed as **promotion ordinal 2**. The prior ordinal-1 draft
remains in history. Mutation limits and protected requirements were unchanged.
The command then returned the ordinary `phase1_stopped` gate, with terminal
`TARGET_NOT_REACHED` and reason `vnext_review_budget_exhausted`. It did not repeat
the stale-selector error. No post-promotion Reviewer call was made in this window.

This is distinct from provider-call exhaustion: six of the authorized eight
calls were unused, but the immutable per-profile Phase 1 review allowance had
been consumed. The window does not grant further review rounds, and no automatic
budget extension or repeat invocation occurred. The run is not Phase-2-ready or
converged. Q4 remains open despite the successful second live promotion.

Next: explicitly authorize a bounded Phase 1 review-budget extension if further
post-correction review is desired, then use the documented grant-only command
and separately continue under a concrete call/time allowance. Preserve both
promotions and the existing decision evidence. Runtime and package sources are
unchanged during this window; no Phase 2, public activation, external apply-back,
Git commit or push occurred. Exact command/status packets, provider prompts and
responses, supervisor result and the final run snapshot are joined in
`rounds/vnext-18-9-q4-005/live-outcome.json`.

### Q4-006 preparation — separate Luna experiment

The operator requested a separate `gpt-6-luna` run for Reviewer, Editor and
Verifier, seven rounds per profile, retaining the eight-call/1800-second caps.
`rounds/vnext-18-9-q4-006/` contains the new immutable package and launch handoff.
Medium reasoning, 600-second provider timeouts, 60% CPU duty and the 180-second
lease remain unchanged. This is preparation only; provider authorization is false.

The new seed is the exact Sol ordinal-2 promoted draft (SHA-256
`7b60d4b716722c342d395acdbf7a1ca9b5cc2b275d38344b7f4fda994021b068`).
Its approved recovery policies are retained and protected alongside the original
queue invariants. One operation, two changed sections and one changed normative
unit remain the mutation bounds. The new job starts fresh review counts; it does
not import Sol reviews, decision receipts or promotion authority. Seed provenance
links the source pointer and candidate without modifying that history.

Real package validation and CLI admission dry run passed with zero provider
calls and no destination created. The unauthorized launch refusal passed, and
all 468 prior Sol evidence files remained unchanged. Sources are hash-pinned to
the current checkout including the tested uncommitted selector fix. Actual Luna
access through this CLI/account remains untested. See preparation-outcome.json
and README.md in the evidence directory for the exact payload and launch scope.

Next is explicit authorization of this prepared live window, then one supervised
Phase 1 invocation. Seven rounds per profile do not override the eight-call cap.
No Phase 2, public activation, external apply-back, commit or push occurred. A
Luna workflow result will not establish equivalent review quality to Sol.

### Q4-006 live result — Luna operator boundary

The operator explicitly authorized the prepared eight-call/1800-second window.
It completed in 45.388 seconds with two successful Luna Reviewer calls (7.106
and 14.132 seconds), then returned `finding_admission` requiring an operator
decision. Structural-integrity review was clean. Determinism review raised
`iss_c2e9b0b87c9a9be4`: stable attempt IDs have no explicit uniqueness boundary,
so distinct attempts could collide during record lookup or deduplication.

Recommendation pending operator approval: an attempt ID identifies exactly one
execution attempt across this queue's record store; distinct attempts must have
distinct IDs, while retries and reconciliation reuse the original ID. This does
not prescribe an ID format/generator or introduce distributed queue operation.
No decision receipt has been invented or bound.

No Editor/Verifier calls, candidates or promotions occurred. The new root remains
at seed ordinal 0 with the imported Sol draft unchanged. Six calls were unused;
no automatic continuation or fresh allowance was launched. Read-only status
passed without changing run files; all 468 prior Sol evidence files and pinned
source/package hashes remained unchanged. Supervisor exited and its worker lock
is available. Exact evidence is sealed in
`rounds/vnext-18-9-q4-006/live-outcome.json`. Luna Reviewer transport is now tested;
Luna Editor/Verifier transport is not yet exercised. Q4 remains open; no Phase 2,
activation, external apply-back, commit or push occurred.

### Q4-006 decision bound — original wall window expired

The operator approved unique attempt identity across this queue's record store,
with distinct IDs for distinct attempts and original-ID reuse for retries and
reconciliation. Bound to round-2 finding `iss_c2e9b0b87c9a9be4` through the normal
options/request/response/selection owners; preview and publication matched.
Evidence: `rounds/vnext-18-9-q4-006-continuation/`. A local response timestamp
initially failed strict format validation; it was corrected to UTC seconds/Z
and validation then passed without changing the validator.

This decision governs the synthetic queue spec, not Whetstone's contracts.
The Editor has not yet implemented it and no new promotion occurred. All prior
run files and 468 Sol evidence files remain unchanged; only decision artifacts
were added. No additional provider calls occurred. The user requested continued
execution within the original 30-minute wall window, but that window had expired
by the time of this turn (original authorization 14:47:57 UTC; check 15:29:28 UTC).
Six calls remain unused, but a new explicit time window is required to execute
them. No deadline reset, new call allowance, activation, commit or push occurred.

### Q4-006 continuation — Luna Editor payload hash rejection

The user authorized a new 1800-second window with only the six remaining calls.
After hash-pinned, provider-free preflight, one supervised Phase 1 continuation
consumed the bound uniqueness selection. It stopped normally after 65.927s,
using one Editor call (37.771s). The result is `proposal` / `invalid_proposal`,
error `$: client payload hash mismatch`. The response declares payload SHA-256
`83d6342b9939285970b565e8beed93de19603b2a54a35519925c4a0b5f9e77bf`,
but its actual UTF-8 content hashes to
`8edb75425e4b49bf2b02443c353ddd9869a0947b53376e8f2d5adb83968fa884`.
The raw response is preserved; no hash was rewritten and strict validation
remains unchanged. This is a malformed proposal, not a semantic Verifier verdict.

Aggregate Luna usage is three of eight calls (two Reviewers and one Editor);
five calls remain unused. No Verifier call, candidate registration or promotion
occurred. The current pointer remains at seed ordinal 0. Read-only status reports
no recovery or continuation invocation; no retry was launched. Status left run
files unchanged, all pinned source/input hashes and 468 Sol evidence files are
unchanged, and the supervisor is stopped with its worker lock available.
`rounds/vnext-18-9-q4-006-continuation/live-outcome.json` seals the result.

Next: investigate the Editor payload-hash production boundary and supported
invalid-proposal retry path before spending further calls. Do not hand-correct
model evidence or infer a semantic preservation pass. Q4 remains incomplete;
no Phase 2, public activation, external apply-back, commit or push occurred.

### Luna Editor hash investigation — no provider calls

The retained trace establishes the exact cause: Luna invoked Python hashlib on
a Base64 representation of its proposed text. That representation contains the
literal `undefined` and decodes to 2366 bytes that are not valid UTF-8. Its hash
exactly equals the declared payload hash. The returned Markdown is instead 2362
UTF-8 bytes with a different digest. This is a model-side computation/input
mismatch, not evidence of a Whetstone transport normalization error. Do not
rewrite either retained value or infer a semantic verdict from the proposed prose.

The v2 prompt in vnext_unit_preflight.py requires SHA-256 of exact payload UTF-8
bytes; vnext_unit_protocol.py preserves those bytes and vnext_proposals.py
checks the digest. No helper currently generates that digest for the model.
The native Codex transport allows read-only computation: the observed hash
command succeeded, so lack of compute tools is not the explanation.

Retry contract: JSON/schema shape failure alone can auto-use a second slot;
timeout/transport/interruption can use explicit technical continuation under
frozen inputs. Hash mismatch is invalid_proposal, which cannot reopen even with
continuation=True. Status correctly advertises no continuation. Five unused
outer-window calls do not override this per-request terminal rule. A fresh
transaction cannot be fabricated merely to reset the allowance.

Four offline checks passed: shape retry, timeout continuation, invalid-binding
reentry refusal, and an exact payload-hash-mismatch fixture refusing ordinary
and explicit reentry with zero further calls (3 tests/1.879s; 1 test/0.565s).
Evidence and reproducible check: rounds/vnext-18-9-q4-luna-hash-investigation-001/.
All sealed Luna run files and 468 Sol evidence files remained unchanged. No
runtime/contracts changes, model calls, commits or pushes.

Recommendation: improve future Editor instructions to compute payload bytes,
digest and final JSON from one in-memory string; avoid independently transcribed
Base64 and validate the serialized JSON payload before returning. Keep strict
hash validation. Preserve the rejected run; a fresh explicitly prepared test can
exercise improved guidance. Reopening this exact request would instead require
an explicit retry-policy/spec amendment, which is not recommended merely to
finish this run. Automatically replacing model-supplied hashes would also change
the current protocol and is not part of this investigation.

Separate observed harness limitation: despite --ignore-rules, the nested Editor
read the external whetstone-runner SKILL.md. Therefore the prior harness cannot
claim complete synthetic-context isolation. Inspect nested skill loading and
containment before another live window; no unrelated project-file read is
established by this trace. This did not cause the demonstrated digest mismatch.

### Q4-007 — hash guidance and isolated fresh Luna preparation

Implemented one-string UTF-8 payload/hash/JSON computation guidance in the v2
Editor prompt. Strict hash checks, response schemas and invalid-proposal retry
policy are unchanged. The request journal recognizes only the exact previous
deterministic prompt rendering when replaying retained requests; it never adopts
arbitrary stored instructions. Legacy/bridge clients are unchanged.

The embedded CLI help establishes that --ignore-rules concerns execution-policy
rules, not skill loading. Local no-model prompt rendering showed host-discovery
and plugin disabling alone still exposed seven skills. Explicit skills.config
disabled entries removed the entire skills catalog. Reference consulted:
https://developers.openai.com/codex/config-reference/ . The private Q4-007 wrapper
applies those per-skill settings with plugins/apps/hooks/skill-search disabled
and project_doc_max_bytes=0. It checks the local rendered prompt before every
exec and refuses if skills appear. All settings are invocation-local; no user
skills/config or production adapter behavior changed. This is skill-discovery
isolation, not a new filesystem read sandbox. Live isolation remains unqualified.

Fresh package: rounds/vnext-18-9-q4-007/, all three roles gpt-6-luna/medium, seven
rounds per profile, FIVE calls including retries (remaining allowance), proposed
1800-second supervised window, 600-second per-call timeout, 60% duty/180-second
lease. The seed is the Sol ordinal-2 draft plus the user's approved uniqueness
clarification, protected as an invariant; it is a new operator-derived seed, not
a successful Luna promotion. Mutation bounds remain one operation, two sections,
one normative unit. The rejected run's receipts are not reused or reopened.

Verification: 27 focused tests passed in 11.047s; historical Sol and Luna status
replays passed without modifying retained files; all 468 prior Sol evidence
files unchanged. Bootstrap validation and admission dry run passed; unauthorized
launch refused, no destination created, zero model calls. Sources, wrapper and
settings are hash-pinned. provider-authorization.json remains approved=false.
The wrapper's guard checks current discovery again at launch to catch drift.
See README.md and preparation-outcome.json in Q4-007 for the handoff. No live
launch, Phase 2, public activation, external apply-back, commit or push occurred.

### Q4-007 live result — manual-reconciliation boundary

The user authorized the prepared five-call/1800-second window. The supervisor
completed in 26.487s after one Luna structural-integrity Reviewer call (12.961s),
stopping at finding_admission for `iss_4c405677c8e70579`. The finding asks which
manual-reconciliation outcomes/actions permit resume or retry when execution
entry or record state is uncertain. No Editor/Verifier calls, candidate or
promotion occurred; the new seed remains at ordinal 0. Four calls remain unused.

The skill-isolation wrapper passed its guard. The retained Reviewer trace shows
no SKILL.md reference or shell command. This supports this invocation's skill
isolation, not a universal filesystem-isolation claim. The improved Editor hash
guidance remains unexercised live. Read-only status passed without changing run
files; 340 prior-window files and all 468 original Sol evidence files are
unchanged. Source/input hashes match, worker lock is available, workers stopped.
Evidence sealed in rounds/vnext-18-9-q4-007/live-outcome.json.

Recommendation for operator consideration (not bound): keep automatic crash
recovery out of scope. Permit manual authorization to resume only when execution
non-entry is established, the original attempt record is durable and spacing
is satisfied; inconclusive execution or record evidence keeps the queue paused.
Do not invent an automated proof mechanism or add execution/reexecution behavior
for already-started attempts merely to satisfy this synthetic test finding.
Acknowledge that the current draft already requires remaining paused while
uncertainty persists; clarification should target the manual handoff only.
Q4 remains open; no automatic continuation, Phase 2, activation, external
apply-back, commit or push occurred.

### Q4-007 continuation — approved manual handoff, Editor declined

Bound the approved manual-reconciliation clarification to round-1 finding
`iss_4c405677c8e70579`: an operator may authorize resumption only after confirming
execution non-entry, durable original-attempt recording and satisfied spacing;
otherwise remain paused. Automatic crash recovery remains out of scope. Normal
options/request/response/selection publication and previews passed.

Continuation remained within the original window: deadline 2026-10-16 19:04:39
UTC, supervisor limited to 1207 remaining seconds, maximum four additional calls.
It stopped in 40.066s after one Editor call (17.063s), at invalid_proposal:
`admitted finding declined; reconcile through a new plan`. Luna returned no
operations/payloads and declined with reason ambiguous. Its rationale says the
clarification is clear but it cannot establish exact payload-unit selectors and
ordinals from the supplied base inventory without guessing. This is the Editor's
claim, not a verified missing-input defect. Inspect correspondence requirements
and prompt guidance before deciding a remedy; do not override strict acceptance
or manufacture a new plan merely to reset this terminal request.

Two of five Q4-007 calls consumed; three unused. No Verifier, registered candidate
or promotion. Seed ordinal 0 unchanged. The Editor received the improved hash
guidance but produced no payload, so successful hashing remains untested live.
No skills references or shell commands appeared in its retained trace. Readonly
status passed without changing run files, pinned source/input checks passed,
340 prior-window files and all 468 original Sol evidence files unchanged. All
workers stopped and lock available. Evidence: Q4-007-continuation/live-outcome.json.
Q4 remains open; no automatic retry, new time window, Phase 2, public activation,
external apply-back, commit or push occurred.

### Q4-007 correspondence refusal — local feasibility established

Offline investigation demonstrates an in-paragraph implementation of the approved
manual-handoff clarification needs no explicit unit correspondence. Using actual
retained plan/base/map/inventory/decision, real proposal preparation, assembly
and inventory comparison pass with unit_correspondence=[], one changed section,
one normative unit and zero failures. The modified unit still requires semantic
verification. The illustrative payload exists only in a temporary probe: no
registered candidate or promoted text, no live call, no rewrite of model evidence.

The complete base inventory was present. Luna mistook the absence of an inventory
for its not-yet-written payload for a mandatory missing input, despite existing
automatic one-to-one alignment. Recommend explaining that automatic path and
when empty correspondence is appropriate, rather than weakening validation or
adding a new protocol immediately. Hard split/merge cases could later benefit
from a read-only payload scanner/preview. Five correspondence tests passed;
retained Luna run and original Sol evidence unchanged. Evidence and proposed
guidance: rounds/vnext-18-9-q4-correspondence-investigation-001/assessment.md.
No runtime guidance change made yet; current invalid request remains terminal.

### Q4-008 — correspondence guidance applied; valid Editor, invalid Verifier

Applied narrow v2 Editor guidance explaining automatic unchanged/one-to-one
alignment and empty explicit correspondence for unambiguous local edits. Strict
validation, semantic obligations, schemas and retry policy unchanged. Journal
replay recognizes exactly both older deterministic renderings (pre-hash-guidance
and hash-guidance-only), never arbitrary persisted instructions. 33 focused
tests passed in 12.205s, including both historical renderings and tamper refusal.

User requested application and another test. Fresh isolated root Q4-008 used
the same Q4-007 seed, Luna/medium for all roles, seven rounds/profile, only three
remaining calls and a new 1800-second cap. Previous roots were not reopened.
After one Reviewer call (14.094s; invocation elapsed 27.885s) raised the same
manual-reconciliation question (`iss_cdd1a97e9a3f3f32`), bound the user's existing
approval to the new finding without inventing a product decision. Continued
with two calls and 1713 seconds remaining before the same deadline.

Continuation completed in 119.115s. Editor call (45.335s) returned valid_proposal
with unit_correspondence=[] and valid payload hash. Candidate
can_6c285ab8dae3b97310165ae29a4de36514767a7d19bb47bd28af2a119a4047e4
registered and passed deterministic verification. Verifier call (10.537s)
returned obligation_hash="UNKNOWN", failing the required 64-hex shape. The
automatic shape-repair attempt encountered the outer call cap before provider
execution, recording a transport failure and consuming its durable attempt
marker. No fourth provider call occurred. Do not assume another Verifier retry
slot remains merely because that marker made no provider transmission.

Current gate verification; candidate CANDIDATE_UNVERIFIED, decision_final=false,
semantic_result=not_run, promotion_permitted=false; pointer remains seed ordinal
0. Three of three provider calls used. Editor hash/correspondence improvements
are now exercised successfully once, not proof of universal model reliability.
Readonly status passed without mutation; all pinned source/input hashes and 388
prior-window files plus original 468 Sol evidence files unchanged. Workers
stopped and lock available. Evidence sealed in Q4-008 and its continuation.
Next investigate Verifier obligation-hash guidance/input and retained request
eligibility locally before further live work. No Phase 2, public activation,
external apply-back, commit or push. Q4 remains open.

### Q4-008 Verifier hash investigation — missing copyable bindings

Concrete input/guidance defect: semantic_verifier_prompt says to copy obligation
IDs and hashes, but context.semantic_obligations contains IDs and subjects only.
Neither the canonical full-packet hash nor per-obligation canonical object hashes
is supplied anywhere in the actual retained prompt. The validator derives both
with canonical_json_bytes/SHA-256; the scripted test client also computes them
in Python, masking this live usability gap. No digest arithmetic is described
in the prompt, which asks for copying instead.

The returned obligations_hash is also incorrect, in addition to the individual
obligation_hash UNKNOWN. Offline reproduction confirms replacing only UNKNOWN
would still fail semantic obligations binding. Computing both expected values
and inserting them into a detached diagnostic copy passes coverage binding
validation only; no semantic verdict, response acceptance or promotion is implied.
The raw response and all run files are unchanged.

Recommendation: derive a prompt-only coverage binding table from the existing
immutable obligation packet: its obligations_hash and each obligation_id/hash.
Instruct the Verifier to copy these exact values, never calculate or substitute
placeholders. Keep canonical coverage validation unchanged and independently
recompute the table. Do not add hashes inside the hashed obligation objects or
change obligation identities/schemas/context; preserve exact historical prompt
replay when implementing the prompt extension. No need to redesign the full
Editor response protocol for this particular issue.

Retry eligibility is exhausted: first durable attempt returned malformed shape;
second durable attempt hit the outer call cap before provider execution and
recorded transport_failure. Both slots are consumed under the current journal
contract; no third attempt or retroactive response repair is authorized. Three
focused offline tests passed for shape exhaustion, marker accounting without
client invocation and invalid-binding refusal. Evidence and reproducible hash
analysis: rounds/vnext-18-9-q4-verifier-hash-investigation-001/. No runtime changes
or model calls in this investigation; retained Luna files and all 468 original
Sol evidence files unchanged. Q4 remains open and candidate unverified.

### Q4-009 — Verifier copy bindings implemented, fresh package prepared

The Verifier prompt now provides a derived coverage_bindings table containing
the canonical whole obligations hash and exact obligation_id/obligation_hash
pairs, with explicit copy instructions. The table is computed from immutable
context, outside the hashed obligation objects. Context bytes/hash, obligation
identities, response schemas and strict coverage validation are unchanged.
Bindings are arithmetic, not a semantic judgment. Historical journals reproduce
only the exact former prompt rendering; arbitrary retained prompt edits refuse.
No retry budget or candidate state is reopened.

47 semantic protocol/request/coverage tests passed in 130.515s, including copy
bindings, packet/item tampering rejection, historical completed-request replay
and prompt tampering refusal. Retained Q4-008 status replay passed without file
changes. Fresh package admission dry run passed with no destination/provider,
unauthorized --run refused, and the local isolation wrapper rendered no skills
catalog. Original Sol evidence remains unchanged.

Prepared rounds/vnext-18-9-q4-009/: same synthetic seed as Q4-007/008, all roles
gpt-6-luna/medium, seven rounds/profile, proposed NEW eight-call/1800-second
window with 600-second call timeouts and 60% duty/180-second lease. Earlier
allowances are exhausted; authorization is false. Existing manual-reconciliation
approval may be rebound only to the same substantive question in a new run.
One operation/two sections/one normative unit remain the mutation bounds.
The exact payload scope includes the deterministic copy table; README.md records
the executable handoff. No live launch, public activation, Phase 2, external
apply-back, commit or push. Live qualification remains outstanding; Q4 is open.

### Q4-009 live result — all-Luna verified promotion, new product boundary

User authorized the prepared eight-call/1800-second test. First invocation
completed in 25.672s using one Reviewer call (12.580s), raising the recurring
manual-reconciliation issue. Bound the previously approved policy to fresh
finding iss_5298a3cfc8477e62 without adding new behavior for already-started
attempts. Continuation used seven-call ceiling and 1708 seconds remaining in
the original window; it stopped in 303.071s after four calls: Editor 28.848s,
Verifier 11.061s, structural Reviewer 6.652s, determinism Reviewer 14.766s.

Editor and Verifier responses were valid. The hash-copy table was exercised
successfully; strict candidate checks and semantic verification passed. Promotion
ordinal 1 is committed for candidate
can_08cf460d86904a38e397749075ee53102b75eb03cd00609a7b2cacb9b4f45d88,
draft SHA-256 191d78011c7fa0a10b959e36903f16ef55a07ed6248ce08107600898bba39108.
Post-promotion structural review was clean. Round-3 determinism review raised
iss_7c80cf1684b9bc63: how attempt IDs are allocated/persisted before record write
and recovered after interruption. This is a new product boundary, not a malformed
response; no allocation or storage policy was invented. Gate finding_admission;
Phase 1 is not complete and no Phase 2 entered. Five of eight calls consumed,
three unused; no automatic extension or new window.

Read-only status passed without run-file changes; source/input hashes match,
491 prior-window files and all 468 original Sol evidence files unchanged. No
skill reads observed in retained traces; shell activity was confined in the
observed commands to supplied seed/candidate reads and Editor hash computation.
Workers stopped and lock available. Sealed evidence in Q4-009/live-outcome.json
and Q4-009-continuation/live-outcome.json. This establishes one successful
all-Luna review/edit/verify/promotion journey, not full Q4 qualification or
equivalent review quality. Next resolve whether the synthetic spec needs a
persistence guarantee and what remains implementation-defined, keeping automatic
crash recovery out of scope. No public activation, apply-back, commit or push.

### Q4-009 ledger decision bound — no live continuation

User explicitly approved the queue-owned durable attempt ledger: allocate a
unique attempt ID when selecting its FIFO job, persist the ID/job association
before attempting the start-record write, and pause on failed/uncertain ledger
persistence without writing the start record or executing until durability is
confirmed. Retries/reconciliation reuse that ID, never a replacement to bypass
uncertainty. Restart recovery remains manual; the ledger does not authorize
automatic resumption. ID format/storage remain implementation-defined.

Bound this approved new persistence requirement to round-3 finding
iss_7c80cf1684b9bc63 using effects add/clarification/strengthen, explicitly not
remove/weaken/authority_change/scope_change. Existing mutation limits, FIFO,
spacing, record content, same-process behavior and bounded manual-resumption
conditions are preserved. Automatic crash recovery/distributed coordination
remain out of scope. Options and selection dry-run/publication matched.
Selection: rounds/round-3/operator_decisions/selections/selection-
cea68616b444868692f94d26a2526877fb67eda9d0f9c8ab9eb4d069df7ae16d.json
(the filename has no newline). Evidence: Q4-009-ledger-decision/binding-outcome.json.
No model calls, draft edits, candidate or promotion. All previously sealed run
files and 468 Sol evidence files unchanged; only new decision artifacts added.
The user requested binding only; no live continuation or time-window extension
was authorized. Three provider calls remain unused from the last window, subject
to a valid execution window. No commit/push/activation/apply-back.

### Q4-009 ledger continuation — promotion followed by authority pause

The operator requested resumption after reconciliation. The retained Luna/medium
run continued in a fresh 30-minute window with only its three remaining actual
provider calls, unchanged seven-round/profile and mutation limits. Authorization
bound the prepared manifest, launcher and round-3 ledger selection. Preflight
status preserved run bytes; source/input/harness pins and local skill-render
check passed. No additional implementation changes were made.

The bounded supervisor completed in 647.220 seconds (10m47s), exit 2:
Editor 58.738s, Verifier 11.058s, then structural Reviewer 10.927s. The ledger
candidate passed and committed promotion ordinal 2, draft SHA-256
`072eb6fa50e8e3658539ad655cbf65fcb80b48fc43a6599b1f2071c9f4171d15`.
This supersedes the earlier handoff's statement that the ledger selection had
not yet edited the draft. The approved policy is now in the verified test draft.

Round-4 structural review raised `iss_721994ea1dcd453a`, an authority blocker:
the added queue lifecycle requirements appear inconsistent with the seed binding's
`may_introduce_requirements: false`. The run stopped at `finding_admission`;
Phase 1 remains incomplete, with no Phase 2 entry. Three calls used here and five
earlier means all eight actual calls are consumed; no automatic extra window.

Local inspection found the exact Reviewer packet contains original authority,
seed/current draft and maps but no prior operator-decision receipts. The ledger
selection hash is absent. `prepare_verified_review` in
`src/whetstone/vnext_verified_review_protocol.py` constructs that packet without
historical decision evidence. This supports a context-gap investigation; it does
not by itself establish that the finding is false or authorize dismissal.
Recommended next work is an offline check of how committed decisions should be
projected to later Reviewers, with exact historical bindings and strict authority
validation. Do not change the immutable authority map, invent new approval or
reopen historical requests to make this finding disappear.

Evidence: `rounds/vnext-18-9-q4-009-ledger-continuation/`, including exact provider
prompts/schemas, call log, command, supervisor and sealed `live-outcome.json`.
Post-stop read-only status passed unchanged; source/input pins and prior evidence
hashes passed; supervisor cleaned up and worker lock was available. No public
activation, external apply-back, commit or push. Q4 remains open.

### Offline authority-context investigation — 2026-10-17

Investigation complete; no runtime fix, new approval, provider call, draft edit or
request reopening. Evidence and executable checks are retained under
`rounds/vnext-18-9-q4-review-authority-investigation-001/`.

**Confirmed causes and limits:**

- The exact round-3 ledger decision ID occurs in both Editor and Verifier prompts
  but not the subsequent round-4 Reviewer prompt. The Reviewer packet includes
  seed/current draft, authority and maps but no historical operator decisions.
  `prepare_verified_review` constructs this omission; `_Proof.values` returns
  seed authority and proven base bytes/map/inventory, not decision history.
- The finding also misstates the supplied seed. The actual Q4-009 seed already
  contains execution-entry semantics, record-store attempt-ID uniqueness,
  durable start recording, retry/reconciliation rules, automatic same-process
  resumption and manual crash recovery. Those are not all newly introduced by
  the latest candidate. The newer ledger persistence rule is absent from that
  seed and is explicitly covered by the round-3 decision. Manual-resumption
  clarification was separately approved and promoted in round 1.
- `may_introduce_requirements: false` does not make every addition absolutely
  forbidden. `vnext_classification.py` routes an otherwise unsupported `add`
  to `new_requirement_needs_authority_or_decision`; the candidate leaf's Finding
  Classification and Operator Decision Response sections permit an exact bound
  decision and derived editor-fixable task. Immutable-policy conflicts still
  require their existing refusal/new-job path. A successful historical promotion
  is not blanket proof against all future substantive findings.
- A fresh offline fixture with false introduction permission rejects an addition
  without a decision, admits a derived task with the exact `add` decision, and
  refuses that same decision on a changed base. Original findings remain
  non-editable. The 25 existing classification/decision/unit-authorization tests
  passed in 0.926s. All 168 retained run-file hashes match the sealed outcome.
  These checks do not claim a live model will judge a repaired prompt correctly.

**Recommended bounded correction (not implemented):**

1. Clarify the candidate/scope owners' distinction between historical approval
   evidence and current mutation authority. Existing specs define exact decision
   admission and staleness, but do not specify a later-Reviewer decision-history
   projection. Define its source, ancestry limit and read-only semantics before
   coding; do not edit the existing digest-pinned algorithms in place.
2. Derive a deterministic evidence packet only from transactions actually committed
   in the selected base's proven ancestry. Include source pointer/round, admitted
   finding and plan linkage, exact decision request/response references and content,
   selected effects and promotion linkage. Exclude orphan, rejected, merely
   prepared, unrelated and future decisions. Validate each response against its
   original transaction inputs, never rebind it to the current base as a new grant.
3. Bind the packet into the new Reviewer's immutable input/prompt identity. Limit
   historical reconstruction to the selected base prefix, avoiding circular
   dependencies on the review being reconstructed. Preserve exact older prompt
   and input-hash replay; do not change existing requests or restore slots.
4. Explain that the actual supplied seed is the admitted starting baseline,
   while verified decisions explain specific subsequent changes. Continue to
   report contradictory authority, effects beyond approval, missing evidence,
   regressions and new product choices. Do not instruct the model to pass.
5. Test exact approved history visibility, omission/tamper refusal, original-base
   validation, exclusion of future/unpromoted decisions, unchanged old request
   replay and new-choice pauses. Inspect Phase 2 parity before claiming general
   Reviewer coverage: its current input builder likewise has no ordinary mutation
   decision-history projection (special gap-acceptance context is separate).

This is a Whetstone context-contract correction, not a request for another queue
product decision. It must not broaden the user's existing approvals. The current
round-4 review remains an immutable validly recorded response and unresolved
finding; fixing future prompts cannot rewrite or rerun it. Any continuation needs
an explicitly supported resolution of that finding or a fresh qualified run,
plus new provider authorization because all eight calls are consumed. Do not
silently mark it resolved based on this investigation. Q4 remains incomplete.
