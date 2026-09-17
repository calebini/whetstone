# 18.7 publication and operator boundary reconciliation

Date: 2026-09-18. Starting checkpoint: `d2ad1c5`.

Acceptance follow-up: the [18.7 acceptance map](VNEXT_18_7_ACCEPTANCE_MAP.md) now reconciles these publication/operator proofs against D8 and the candidate P0 scenarios. The representative Batch C inventory is closed; the remaining joint two-candidate/process selection proof and current-source refresh are explicit. Earlier next-step statements below are historical. No new runtime test or implementation change was made for this consolidation, and 18.7 remains incomplete.

Latest follow-up: [representative runtime publication prefixes](VNEXT_RUNTIME_PUBLICATION_PREFIXES.md) now cover early incomplete registration, candidate-pointer acknowledgement loss with failed/successful barrier replay, and intent-only promotion recovery. All three journeys pass without runtime changes. This supersedes the table's three representative runtime gaps for those exact boundaries; the historical component/runtime distinctions remain. Next is acceptance/evidence consolidation, with consuming qualification still open.

Subsequent test-only checkpoint: [canonical nonempty decision references](VNEXT_RUNTIME_DECISION_REFERENCES.md) now pass request/response replay-flush recovery and five missing/altered/drift refusals, with no runtime change from `c6e5929`. The table's decision-reference gap and next-slice statement below are superseded for that exact seed-base single-decision path. The other three narrower runtime publication proofs and consuming qualification remain open.

This reconciles the remaining publication/operator inventory against the actual
producers, test bodies and retained results. It also investigates the final
run-state uncertainty case left open by the prior mirror checkpoint.
**The two new test methods and 74 affected consumer regressions pass
(76 distinct tests, no skips).** This is targeted validation, not a full-suite
or consuming-release qualification run. The original failing reproduction is
retained separately and is not counted as passing evidence.

## Confirmed final-state defect and correction

The regression first failed on the original source. Promotion 2 committed;
`run_state.json` was renamed into place; an injected failure prevented its final
full flush. The adapter correctly reported uncertainty and invalidated ownership.
All three mirrors nevertheless compared equal to committed authority. Fresh
promotion and work owners treated that equality as sufficient and skipped the
barriers; a no-op promotion synchronized no mirror paths.

The correction adds an existing-byte synchronization step for mutating owners
when their mirrors already match. Under the current retained fence, the owner
synchronizes the committed snapshot, current pointer, spec, source-round draft
and state before candidate/Reviewer/operator work or promotion selection. Any
barrier failure stops that invocation and invalidates ownership through the
existing adapter. This adds durability work on mutating reentry, with no new
artifact, recovery marker or status. The runtime cannot infer a previous
acknowledgement from readable bytes after a process restart.

Read-only status still performs no synchronization or repair. Matching status
may report ordinary next-work availability; the mutating entry owns the barrier.
Actual byte mismatches retain the existing separate-fence repair path and its
requirement to end the recovery invocation. Legacy/bridge code, contracts and
shipping qualification maps are unchanged.

The new final-state regression exercises both promotion and work reentry with a
second failed state synchronization, requiring no artifact change or new client
call. Successful no-op promotion then synchronizes all five exact paths without
rewriting files or creating another ordinal.

## Reconciled boundary map

| Publication family | Component coverage and canonical-runtime evidence | Remaining proof / disposition |
| --- | --- | --- |
| Registration preparation, candidate artifacts, initial disposition, creation commit | Registry tests interrupt all seven publication prefixes: early incomplete packages refuse without writes; complete orphans reconcile. Typed creation acknowledgement/replay tests also exist. Batch B proves runtime orphan recovery above an earlier semantic candidate and revalidates original Reviewer evidence. | The component matrix exists. Canonical-runtime early incomplete-prefix refusal and typed creation-commit uncertainty have not been separately demonstrated. Do not describe all registration interruption coverage as absent or repeat all seven blindly. |
| Verification decision, disposition event, candidate-pointer snapshot and commit | Shared semantic decisions cover all three preparation prefixes and typed lost pointer acknowledgement. V work covers prepared decision/snapshot recovery; Batch B covers the canonical-runtime prepared event; Batch C covers killed Verifiers on both sides of durable raw. | Canonical-runtime candidate-pointer acknowledgement loss remains narrower than the component proof. A final semantic verdict cannot imply global promotion. |
| Promotion intent, event, next-ordinal snapshot, current-pointer commit | Component promotion tests cover six before/after preparation cases. Batch A's before-commit runtime death retains the complete preparation package and recovers its claimant/timestamp; after-commit death and typed rename uncertainty preserve the committed ordinal. | Early partial preparation has component coverage; it is not a six-case canonical-runtime matrix. Keep that qualification distinction explicit. |
| Spec, source-round draft and state mirrors | Component tests cover all six before/after mirror cases. Runtime tests cover partial-mirror process death and lock handoff across a later promotion. The prior uncertainty checkpoint covers actual adapter post-spec-rename and matching-spec replay flush failures. This correction covers the all-matching final-state gap on promotion/work reentry. | These are specified representative process/primitive failures, not every device/barrier combination or physical power-loss evidence. |
| Operator response and receipt | V operator tests cover both sides of each publication. The earlier canonical-runtime journey interrupts after response. New runtime tests inject real link-acknowledgement loss at the receipt and a failed replay flush, then recover the exact receipt without clients. | Both artifact boundaries now have runtime representatives, including typed uncertainty at receipt. Before-publication combinations remain component-level evidence. |
| Child admission and selection marker | V operator tests cover both sides of each publication. Earlier runtime coverage interrupts after admission. New runtime tests inject real link-acknowledgement loss at the selection marker and failed replay flush, then recover exactly without creating a child or invoking clients. | Both artifact boundaries now have runtime representatives. The existing successful child/promotion journey remains separately scoped; this test does not repeat it. |
| Explicit round decision request/response synchronization | The runtime admission code validates the supplied decisions, replays exact request and response bytes, rechecks preflight, and only then publishes `proposal_input.json`. Proposal-admission tests reconstruct named-unit decisions and refuse rehashed requests. Existing runtime tests use empty decision lists. | **Still untested through canonical-runtime admission with a nonempty decision list.** Code presence and successful empty-list admission do not qualify this branch. This is the next focused test target. |

The seven-prefix registration and eight-prefix operator matrices are verified
from test bodies; semantic preparation coverage is three successive interruptions
in one test, not three independent full journeys. Counts are not added across
overlapping runs. Actual killed registrars/operator writers have not been proved
here; existing process tests establish shared ownership behavior but are not
relabeled as those journeys.

## New operator uncertainty checks

Each case begins with a real canonical Reviewer round and final rejected semantic
candidate awaiting an interpretation answer. The adapter successfully links the
receipt or selection marker, then receives an injected `OSError`. The adapter
classifies uncertainty itself; ownership must be invalid before the producer's
caller unwinds. Read-only reopening and answer preview preserve bytes.

On reentry, an injected failure in publication's temporary-file flush proves the
visible receipt/selection cannot simply short-circuit to success. This second
failure is before the new publication attempt, so it is not claimed as another
uncertain final-name write. Adapter temporaries may remain as evidence. A fresh
owner then replays the exact receipt/selection; repeated success changes no
files. Earlier candidate evidence and the seed pointer remain exact, with one
call per scripted role and no child registration.

## Evidence and bounded handoff

The [machine-readable record](audits/VNEXT_18_7_BOUNDARY_RECONCILIATION.json)
binds the original failing reproduction, final source manifest, focused tests,
affected consumer regressions and retained-log comparisons. Raw evidence lives
under ignored `rounds/vnext-boundary-reconciliation-001/`.

The first corrected-source focused run passed the final-state regression but
reported two operator-test harness errors: its preservation assertion attempted
to read retained adapter temporaries through the consumer API, which correctly
forbids those names. The assertion now reads fixture files directly. That failed
run and its exact source manifest remain retained; it required no further runtime
change. The final focused rerun is recorded separately.

Six retained Batch A–C log digests and test counts match their checked-in
records. These are historical passes on their recorded sources; the current
runtime correction requires its own validation and does not convert them into
a current full-suite pass.

Next: nonempty decision-reference synchronization through canonical admission,
then resolve the three narrower runtime publication proofs in the table
(early registration, candidate-pointer acknowledgement, early promotion
preparation) against the consuming acceptance requirements. This is a finite
remaining map, not a request for every component test to become a full journey.
Complete consuming-suite qualification and the wider 18.5–18.7 acceptance map
remain open. Batch C and 18.7 remain incomplete.

The next slice should bind a valid named-unit operator request/response to an
original Reviewer finding, interrupt request/response durability replay before
canonical round publication, and reopen for exact recovery without another
Reviewer call. Missing or altered decision evidence must refuse without a round
publication. These are round-admission decision references; they are distinct
from the semantic interpretation receipts/child selections tested here.

D8 design/audit closure stands. Local scripted tests need no new external audit
authorization. No 18.8–18.9 work, mode activation, provider transmission, external
specification apply-back or push is included.
