# Verified-promotion release decision — 2026-10-28

**Approved by the operator on 2026-10-28. Controlled, explicit config opt-in
activation is implemented for `vnext-verified-consumer-1`.** The exact V gate
entry and six owning specifications now advertise the same supported digest.
All 15 focused shipping-gate/configuration/compatibility checks passed in
64.017 seconds (64.761 seconds supervised at 60% duty). Q4 is complete within
this controlled opt-in release boundary. The activation is part of the 0.2.0 source release checkpoint; no installed
runtime was replaced, no job was launched and nothing was pushed.

This approval carries the disclosed correctness/performance limits into practical
use. It does not resolve the historical failure or grant model/source-write
permission. The [operator procedure](OPERATOR_QUICKSTART.md#operating-a-qualified-v-release)
and existing command/recovery matrices describe the qualified operation.

## Qualified release and supported scope

| Selection | Qualified release binding |
| --- | --- |
| Package | Whetstone `0.2.0`; installed channel promotion is separate |
| Mode | `verified_promotion`, explicitly selected through each new job's run config and validated against its immutable package/descriptor |
| Suite | `vnext-verified-consumer-1` |
| Exact manifest digest | `7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58` |
| Normalization / parser | `whetstone-markdown-normalization-v1` / `markdown-atx-v1` |
| Assembler / inventory / semantic policy | `patch-assembler-v3` / `preservation-inventory-v2` / `semantic-policy-v2` |
| Storage | D8 canonical physical run root on local macOS/APFS; fenced mutation on one root; no distributed-writer or relocation support |
| Workflow / profiles / rubric | `standard`, `stateful_system`, fixed `standard-v1` rubric |
| Routes | Horizontal and vertical Phase 1; separately pinned focused Phase 1; horizontal Phase 2 mid/final × permissive/strict; vertical Phase 2 final/strict |
| Metadata | Existing M3 supported numeric metadata and unversioned paths; any required mutation verified before promotion/entry |
| Commands | Exact [Q1 matrix](VNEXT_18_9_Q1_PROPOSAL.md#ratified-supported-command-matrix) and [Quickstart recovery table](OPERATOR_QUICKSTART.md#exact-v-recovery-and-continuation-routes), without additional fallbacks |

The suite digest pins contracts, not an entire executable build. Runtime/test
source snapshots and their execution scopes remain separately bound in the
qualification receipts. The pre-activation runtime is checkpointed by `dee2258` (included in HEAD
`45eeee2`). This local release change adds only the exact V qualification entry
to runtime behavior, with its smoke checks and source receipt retained under
`rounds/vnext-18-9-q4-activation-001/`; it is included in the scoped 0.2.0 source release checkpoint.

No default-wide enablement, automatic legacy/R/P migration, custom/MVP/governance
workflow, arbitrary supplied-draft edit, generic Phase 2 crash recovery, new
storage backend or run-wide resource controller is part of this decision.
Existing bridge and legacy behavior retain their own contracts. Existing V roots
retain their identities and supported recovery semantics; this decision does not
restart old campaigns or convert scripted fixture evidence into live judgments.

## Activation-gate reconciliation

The [coordinating activation gate](specs/WHETSTONE_COORDINATING_SPEC.md#candidate-safety-activation-gate)
remains normative. All conditions must hold before public enablement.

| Condition | Evidence / current disposition |
| --- | --- |
| Consistent authority amendments | Q1's ratified amendments cover the six specification owners and operational guide; its closure reconciles all 14 authority surfaces and seven integration cases. Subsequent Q4 guidance/history corrections retain strict validation and frozen contracts. This is retained scoped evidence, not a fresh independent spec audit. |
| Same supported suite advertised by owners | **Published for the approved release.** All six owners, the Quickstart and the shipping V qualification entry select the exact suite/digest above. A config alone still cannot qualify another suite or implementation. |
| Versioned contracts and cross-implementation fixtures | Both registered manifests validate unchanged. Q2's independent standard-library reference compares assembly, maps, identities, metadata and persisted selection/disposition within its recorded corpus. It is not a second complete scheduler. Frozen `vnext-contracts-1` is not extended. |
| Every mapped P0 release scenario passes | Q3 retains passing credit for all **22 rows / 78 distinct mapped methods**, including the seven Q2 gaps and their approved boundaries. Its 1,635-method inventory records **1,634 passes and one original failed method outside the P0 map**. Do not present the full regression as all passing. |
| Later runtime changes have affected verification | Current bytes of all eight existing runtime files changed since the Q3 campaign join later tested snapshots. Retained logs cover 33 Editor, 47 Verifier, one selector integration, Phase 1 history cohorts and 28 distinct Phase 2/history methods. The added history module and its final tests match the last history receipt. These overlapping/source-specific cohorts are not summed into a new full-suite pass. |
| Isolated live evidence and proposal inspection | Historical successful promotions and strict rejections are inspected with their source limits. The targeted Phase 1 history probe passed. Q4-015 completed genuine fresh-root Phase 1, distinct entry and Phase 2 declaration acceptance/CONVERGED. No further live campaign is added to this release decision. |
| Explicit new-job mode selection | Implemented admission/config/descriptor checks refuse mismatches and unsupported controls. Public entry checks the exact production qualification entry; the operational package for each job must be prepared and selected explicitly. |

The failed Q3 method is
`test_vnext_semantic_cli.SemanticCLITests.test_three_native_roles_complete_the_normal_command_and_reentry_without_more_calls`.
Its cause remains unknown. The instrumented 26-method diagnostic cohort passed,
without converting the original failure into a pass. The operator explicitly
accepted this residual risk and the measured performance to proceed to Q4.
The approved release carries those disclosed limits into practical use;
it does not claim a fix or waive a failed mapped P0 condition. No additional
correctness retry is proposed without a recurrence or new causal evidence.

Machine reconciliation:
`rounds/vnext-18-9-q4-release-handoff-001/reconciliation.json` records the P0
method credits, source drift/receipt joins, verified log summaries and live seal.
It is read-only evidence reconciliation, with no new runtime-test credit.

## Live observations and operating limits

Q4-015 used Sol 6.1 medium and preserved Codex CLI `0.164.0-alpha.11.1`.
All five reviews passed strict validation on attempt 1: three Phase 1 reviews and
two Phase 2 reviews (strict and adversarial), with no findings or rubric gaps.
The declaration gate accepted the unique required clean profiles on the same
draft, so the scheduled repeated strict step was unused. Exit 0, `phase2_complete`,
accepted declaration and bound `CONVERGED` terminal evidence all agree.

Total elapsed time was **756.223 seconds (12m 36s)** at 60% duty. Provider wall
time totaled **66.937 seconds**. Remaining time includes local proof replay,
publication and throttling; it is not an isolated CPU measurement. The small
fixture did not edit, create/verify/promote a candidate, maintain a version or
exercise nonempty Phase 2 decision history. Live history has a separate bounded
Phase 1 probe; Phase 2 history has local focused/regression evidence. Historical
live Editor/Verifier promotions remain credited on their recorded versions,
not relabeled final-source Sol reliability.

The Q3 performance disposition also retains 74.8- and 71.6-minute whole-test
journeys with multiple operations/faults at 60% duty. These are not individual
command SLAs. Evaluate practical latency before adding replay optimization;
activation neither promises interactive speed nor adds a background scheduler.

Model reliability, every model/route combination, physical power loss and
resistance to arbitrary external filesystem writers remain unqualified. Provider
payload consent, call/time budgets, product/authority decisions and real external
apply-back approvals remain separate operational boundaries. The three unused
Q4-015 calls authorize no further campaign. Runtime distribution/install work is
separate from this release decision.

## Ratified activation decision

The operator approved explicit config opt-in for the exact suite and supported scope above,
carrying the disclosed correctness/performance limits into controlled practical
use, keeping existing defaults and source-write approval requirements. The
authorized local activation implementation:

1. Adds only the exact suite/digest above to
   `src/whetstone/vnext_verified_cli.py::QUALIFIED_VERIFIED_SUITES`. Other public
   qualification maps and frozen suites are not changed by inference.
2. Publishes consistent supported-suite/status text across Coordinating,
   Candidate Editing, Scheduler, Artifacts/Validation, Scope/Decisions and Phase 2
   specification owners, plus the operator/release guide. Reconcile contradictory
   current unavailable statements while preserving historical checkpoints and all
   protocol requirements. No new mode, policy or schema is needed.
3. Verifies the real shipping gate with proportionate offline checks: exact
   qualified-suite admission, unsupported/drifted/conflicting refusal before
   calls/writes, immutable existing-root selection, supported status/recovery and
   representative legacy/bridge compatibility. Existing injected tests alone do
   not establish that the shipping entry was enabled correctly. Record the final
   release source and suite hashes; no new live window is implied.

These are the bounded approved release actions. They do not publish specs
externally, commit, push, start jobs or approve source apply-back. To pause future
automatic work, follow the caller-side procedure in the Quickstart while
preserving existing descriptors, evidence and inspection/recovery capability.


## Activation verification and handoff

The five new smoke methods exercise the actual shipping map without injecting
qualification. They cover exact release identity, dry-run/admission, read-only
status and selected materialization recovery, unknown/unqualified/conflicting
selectors, retained mode/client immutability and a corrupted disposable manifest.
The earlier offline-registration test now explicitly withdraws qualification to
preserve its original negative guarantee. Three existing configuration tests and
six representative legacy/audit/status/bridge checks complete the 15-method
cohort. All pass; no errors, failures or skips. No broad regression rerun or new
live-model qualification is claimed by this activation patch.

The six spec owners advertise one exact suite/digest and retain their existing
normative gates. Both registered manifests and all frozen contract bytes remain
unchanged. Other public proposal/semantic/follow-up qualification maps remain
empty. Scope is controlled V opt-in, not automatic qualification of those
separate interfaces. Existing compatibility and bridge defaults remain intact.

`rounds/vnext-18-9-q4-activation-001/` retains the user authorization, protected
work boundary, supervised test log, final source/contract/document hashes and
static consistency/link checks. Earlier Q4 live manifests remain historical:
their pre-activation verified-CLI source hash is intentionally superseded, while
their run artifacts and observations are preserved. Do not rerun expired private
qualification launchers against the enabled release.

No required implementation or qualification item remains open within the
approved Q1–Q4 scope. The accepted historical Q3 risk, latency and unobserved
live branches above are release limitations, not silently resolved findings.
The scoped 0.2.0 source release checkpoint includes this activation, the
preceding Q4 handoff and updated Markdown/HTML operator documentation. Audit
reports and unrelated runtime distribution/notes work stay outside the checkpoint. Push, installed-runtime
promotion, real jobs and external source writes remain separate actions.


## 0.2.0 source release checkpoint

The package and import versions are 0.2.0. The source checkpoint includes these
release/qualification records, the activated gate, scoped tests, Markdown
operator guidance, release notes and the updated offline HTML field guide.
Eight release smoke methods passed on 0.2.0; the earlier 15-method activation
cohort retains its original scope. Site content/packaging checks and desktop/
narrow rendering checks pass. Exact preparation evidence is under
`rounds/vnext-0-2-0-release-001/` and is not published with the public site.

Unrelated runtime distribution changes, notes and local audit reports are excluded.
The machine's existing stable installation remains separately selected. Candidate
installation, installed-runtime smoke checks, stable promotion, tags, push and
manual Pages publication are follow-on administrative actions, not effects of
this source checkpoint.
