# 18.6 bounded acceptance closeout

Date: 2026-09-19. Starting checkpoint: `48094ba`.

**The three 18.6 implementation tasks are validated at the independent semantic
and scripted same-round follow-up boundary.** Together with the 18.5 and 18.7
maps, this closes G3's bounded implementation reconciliation. No additional
implementation or test case was needed. Overall release qualification remains
open; no public mode is activated.

The assessment compares the [candidate leaf's](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md) independent verification,
verification-decision and disposition-commit requirements with the versioned
semantic context/coverage/[policy](../contracts/algorithms/vnext_semantic_policy_v2.md)
and [follow-up contracts](../contracts/algorithms/vnext_semantic_followup_preflight_v1.md), actual code and retained
results. Older implementation-status paragraphs are historical, not evidence
that the connected consumers remain absent.

## Acceptance map

Each row binds exact implementation files and existing method identities in the
[machine-readable record](audits/VNEXT_18_6_ACCEPTANCE_MAP.json). “Validated” means
this bounded implementation, not full release conformance or live-model quality.

| ID | Requirement and observed behavior | Existing evidence |
| --- | --- | --- |
| S1 | Registered context reproduces the base, candidate, map, patch/payloads, findings, authority, invariants and preservation report. Required unit/group/baseline obligations cannot be omitted. | Context, coverage and admission modules: altered locators, maps, reports, authority/context and incomplete or stale coverage refuse. |
| S2 | The Verifier is a separate invocation with its own prompt/schema and read-only native capability. Exact finding/operation/assertion coverage and uncertainty mappings are validated; partial resolution, unrelated regression or semantic loss cannot pass. | Protocol and native-verifier tests, including same-model distinct processes, tool restrictions, policy mismatch and concrete authority-choice binding. |
| S3 | Invocation claims, raw output and receipts remain immutable. Shape repair is bounded; technical continuation retains the original context and allowance. Invalid bindings cannot become semantic rejection or successful verification. | Seventeen durable-request methods cover timeout, slot consumption, retained-output recovery, altered predecessors and uncertain publication. |
| S4 | Decisions and events append in order. Only the atomic candidate-local pointer makes them effective. Technical failure stays nonfinal/unverified; semantic rejection and operator-required outcomes are final. A final candidate cannot be reopened. | Shared decision/projection and proposal-closeout tests; G2 refreshes the seven semantic-decision methods, including every modeled pre-pointer prefix and lost acknowledgement. |
| S5 | Normal stored-round/CLI processing respects deterministic rejection, separate semantic qualification and explicit recovery. Successful proposal-only verification leaves seed authority unchanged. | Twenty semantic-run/CLI methods include stale selection before lock, invalid output, timeout exhaustion, prepared-decision recovery and three scripted native roles. |
| F1 | Explicit selection or decline grants no effects. A follow-up retains the original immutable base and editing scope, binds the exact answer/source decision and derives a distinct transaction. | Eighteen answer/preflight methods reject stale receipts, scope expansion, reused source output and implied permission. |
| F2 | A fresh child is assembled, registered and independently verified; rejected ancestors, original contexts and scope remain intact. Repeated follow-up produces distinct candidates in the same Reviewer round. | Eight admission/workflow/repeated-follow-up methods, including deterministic child rejection before Verifier invocation and exact completed reentry. |
| F3 | Operator commands separate answering from transaction selection. Recovery preserves client allowances; the native command journey invokes independent verification for the child. | Six workflow-recovery/native/operator/qualification methods. Missing consumer pins refuse before root or adapter creation. |
| V1 | The shared semantic result and finality checks remain valid when consumed through committed verified history. | G2's ten verified-semantic and nine pointer-history methods. These supplement, rather than replace, the proposal-only evidence. |
| V2 | Representative current runtime follow-up and actual Verifier process death preserve authority, invocation slots and recovery ordering. | G2's four runtime-follow-up methods and one Verifier-fault method. Process-death subcases are not counted as additional methods. |

Plan task 1 maps to S1–S3, task 2 to S3–S5 and V1–V2, and task 3 to F1–F3
together with 18.5's immutable proposal/candidate registration. A reduced or
changed patch must pass normal proposal, assembly and verification for its own
identity; an answer cannot edit registered bytes or transfer an old verdict.

## Evidence and source provenance

**171 distinct existing methods have passing evidence:**

| Evidence source | Methods credited | Scope |
| --- | ---: | --- |
| Original reconciliation regression | 140 | Individually passing semantic, proposal-closeout and follow-up methods on unchanged Python dependencies. The complete 1,153-method run still has its recorded two unrelated fixture-import failures. |
| G2 components | 26 | Seven semantic decisions, ten verified semantics and nine pointer-history methods on the current source snapshot. |
| G2 runtime | 5 | Four runtime follow-up methods and the actual Verifier process-death method on the current source snapshot. |

The verifier checks exact retained-log hashes, selected identities and counts.
Static transitive local-import inspection, including function-local imports,
finds **145 Python files with no change from the original validation manifest**
for the carried cohort. No corrected-test substitution is needed. Changed V
runtime dependencies are credited separately through G2, whose full source
manifest still matches. This is source comparison, not dynamic instrumentation
or a new test run.

In particular, the original regression reran the native follow-up, repeated
follow-up, normal workflow and recovery journeys successfully on those unchanged
dependencies. Their earlier stage logs' pre-refactor-import caveats therefore do
not require another bounded rerun. They remain relevant historical limitations
of those older logs, and do not establish release qualification.

The two post-baseline contract changes remain D8 kernel documentation and the
tightened descriptor-path schema, covered by G2's storage/registration evidence
already reconciled in 18.5. Carried semantic results are not represented as fresh
executions against that schema. All other baseline contract bytes still match.

All 17 semantic-stage records were inspected. Their 42 primary referenced logs
were read: 21 supplied historical digests match; the other 21 have current
digests recorded without claiming an earlier digest existed. Counts and available
method identities are checked. Nonverbose logs cannot independently establish
their listed identities. The in-progress record is not completion evidence, and
the earlier failing CLI run and summary-only initial answer failure remain
historical failures rather than passing runs.

Two historical records repeat the final method-name segment in their IDs:
`validation-answer-source-replay-stage.json` (18 entries) and
`validation-pointer-reader-stage.json` (49 entries). The new record explicitly
maps those malformed IDs to the raw logged identities. The old records are
unchanged; selected-method acceptance uses the later regression/G2 logs directly.
Historical stage counts and the 18.5/18.7 totals overlap and must not be added.

Raw reconciliation inputs, source manifest and verification script remain under
ignored `rounds/vnext-18-6-acceptance-001/`. No runtime tests were executed and no
runtime, test, contract or owning-specification bytes changed for this closeout.

## Handoff after G3

Completed: all three bounded implementation tasks in each of 18.5, 18.6 and 18.7;
G1/G2 validation; G3 acceptance reconciliation; D8 design ratification and bounded
audit closure. No concrete additional fault case or local authorization blocker
was identified by this reconciliation. There is no further generic acceptance
or storage-fault loop scheduled within these slices.

Remaining implementation is **18.8's scheduler, Phase 2 and apply-back consumer
integration**: the remaining normal/focused/vertical/retry/resume paths, accepted
draft and convergence consumers, strop/readback eligibility and terminal reporting
must consume verified lineage consistently. Existing bounded integrations do not
mark these four plan tasks complete. This work remains outside the current scope.

Release blockers remain a descriptor-bound shipping consuming suite, complete P0
and cross-implementation coverage, full compatibility/regression and process/CLI
qualification, separately authorized live soak, and controlled activation under
18.9. Scripted providers do not qualify live semantic judgment. Other filesystems,
physical power loss and distributed writers remain unqualified; the ratified
design permits one local mutation owner at a time.

Frozen suite 1 retains SHA-256
`09172fdc498f9d0189f3530b306fe1098a3c1d449482b68d21478d3786e1a950`.
The three shipping qualification maps remain empty. Legacy/bridge bytes are
unchanged. No 18.8–18.9 implementation, external transmission, activation, push or
external specification apply-back is included.
