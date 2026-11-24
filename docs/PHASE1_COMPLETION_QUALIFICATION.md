# Shared Phase 1 completion and MVP qualification

Status: implementation complete; targeted offline qualification passed. Not a release
activation, installed-runtime upgrade, or live-provider qualification.

## Design and scope

The [shared completion spec](specs/PHASE1_COMPLETION_POLICY_SPEC.md) governs new
`review-configuration-v3` jobs using `scope-aware-phase1-v1`. The implementation
reuses candidate assembly, semantic verification, materialization and promotion;
no workflow/profile branches were added to those mechanisms.

`vnext-verified-consumer-2` is registered with digest
`bc6657ad4a098f2f6a9a2652b0d4be412e5ca452be4723c8d3c8ba82443c9820`.
Registration does not activate the public CLI: its production qualification map
continues to advertise only the existing release. Qualification tests explicitly
inject the new entry within their own process. Do not copy that override into an
operator setup or change a retained job's suite/configuration.

The new capability admission matrix is Standard/MVP × stateful_system/balanced_mvp/
utility_mvp, with horizontal/vertical full review or horizontal focused selection.
The shared completion evaluator has no workflow or profile-name branches. Presets
remain capability/configuration inputs. MVP requires approved scope. Phase 2
binding/entry is explicitly unavailable for new-policy jobs, including Standard
jobs; existing-suite Phase 2 and both frozen suite digests remain unchanged.

A finding is deferred only when the bound approved scope and consistent advisory/
canonical evidence justify it. Bare scope flags cannot waive major findings.
Decision, authority, dependency and blocking-invariant conflicts remain blocking.
The same predicate feeds scheduling, status and closeout; v5 closeout records
approved deferrals, source receipts and scope hash. Evidence must cover the current
draft. Focused stability is not full-phase acceptance; budget exhaustion is not
success. State projections do not advertise Phase 2 readiness for this suite.

## Preparing a new-policy package after activation

Use the existing immutable package preparation process, with these fields in the
**review configuration artifact**, not as additional top-level launcher settings:

```json
{
  "schema_version": "review-configuration-v3",
  "completion_policy": "scope-aware-phase1-v1",
  "workflow": "mvp",
  "review_mode": "vertical",
  "profile_set": "utility_mvp"
}
```

This is a fragment: retain the bound Reviewer/Editor/Verifier identities and a
nonempty, unique `profiles` list with positive budgets. Utility MVP's Phase 1
lenses are buildability, consistency, determinism_light and operability_light;
balanced MVP uses structural_integrity, determinism and operability. For focused
horizontal work add `phase1_selection: {"kind":"focused","profile":"buildability"}`
with that profile present in the configured utility set. Bind approved scope and
select `vnext-verified-consumer-2` in the new descriptor and run configuration.
Changing these bytes changes job identity; never retrofit an existing root.
Phase 1 has no new rubric selection. Do not attach a Phase 2 configuration.

## Evidence and reproducibility

Run tests from the repository with `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests
python3 -m unittest -v ...`. Runtime cohorts require local macOS/APFS and use
scripted clients, real request journals, candidate verification, promotion and
recovery. They do not make provider calls. The CLI cohort uses coherent packages
for the actual registered suite; other runtime fixtures use explicitly registered
test-only consuming suites and are not production activation evidence.

Final evidence: **96 distinct passing test methods** across 129
executions (targeted reruns overlap; counts are not additive coverage).
The [machine-readable receipt](qualification/phase1-completion-2026-11-22.json)
records exact method IDs, cohort results/log hashes, and final source hashes.

| Cohort | Tests passed | Recorded elapsed |
| --- | ---: | ---: |
| components | 67 | 9.985s |
| new-runtime | 7 | 497.457s |
| compatibility | 11 | 518.142s |
| public-cli | 5 | 260.169s |
| registered-promotion | 1 | 219.225s |
| final-projection | 4 | 132.673s |
| actionability | 17 | 170.735s |
| final-dispatch | 17 | 1.096s |

Cohorts ran concurrently; elapsed times are not a latency benchmark. The final
projection, actionability and dispatch cohorts rechecked affected paths after
late fixes. This is targeted regression evidence, not a full-repository pass.

Covered journeys include all four MVP preset/route combinations, a Standard
shared-policy deferral journey, focused MVP completion without full-phase
acceptance, a 12-combination coherent admission matrix, missing scope refusal,
real scripted candidate editing/verification/promotion on the final registered
suite, current-draft re-review, budget exhaustion and extension, lost closeout
acknowledgement, and old-suite Phase 1/Phase 2 behavior. Optional-only minor
findings complete with no Editor call on either route. New-policy Phase 2 is
refused, including its readiness projection.

Initial test-fixture timestamp/status-pin failures were corrected. Review also
found and fixed new-schema route inference and optional-only findings forcing
edits; final targeted tests cover both. No unresolved failure remains in the
recorded cohorts. Both old registered suite digests validate unchanged.


## Live-provider spec audit — 2026-11-22

The explicitly authorized findings-only audit ran through the installed stable
0.1.0 runtime (`6e19fe3e72dedda50a372781a43c08e5d7e7480a`), using the Codex CLI
and the consistency profile. It reviewed frozen copies of the new policy, its
pinned algorithm and all six amended owner specs. Result: **pass**, boundary
preserved, zero findings at every severity. No audit-driven correction was needed.
All eight source hashes still match the audited snapshots.

The [audit receipt](qualification/phase1-completion-spec-audit-2026-11-22.json)
retains the report, feedback, source hashes and artifact hashes. The client used
its default model; the feedback self-reports `gpt-6`, which is not an independently
pinned model identity. The legacy adapter requests medium reasoning. This is one
bounded consistency assessment, not proof of correctness or live qualification
of the new suite's Reviewer/Editor/Verifier journey. That qualification remains
outstanding. The production gate still contains only consumer-1; activation,
installation and release are unchanged.

## Release boundary

No runtime version/pin, old manifest, production qualification entry, installation,
tag, remote branch, or external project specification was changed by this implementation.
Release review must assess the recorded offline coverage and remaining limits,
including whether a bounded live-model probe is required for the new Reviewer
guidance. Only then should the new suite digest be added to the production
qualification map and the separately identifiable runtime release be published.
Do not describe these tests as proving semantic correctness for arbitrary specs.


## Readiness checkpoint — 2026-11-24

All implementation hashes in the offline receipt still match; reuse the 96-method
evidence. The separate live spec audit remains a pass, not execution qualification.
A fresh 15-test pure policy run passed. No new provider calls were made.

A local snapshot candidate `0.3.0rc1` is staged at
`rounds/phase1-readiness-20261124/releases/0.3.0rc1`, with its own virtual environment
and isolated launcher. Source version remains 0.2.0. The snapshot is uncommitted,
not published and not selected by machine candidate/stable pointers. Its production
gate remains disabled. The snapshot hash inventory and checks reside beside it.
This follows the existing source-snapshot installation method; it is not wheel
packaging qualification or an activated release artifact.

| Workflow | Profile sets | Full horizontal / vertical | Focused horizontal |
| --- | --- | --- | --- |
| Standard | stateful_system, balanced_mvp, utility_mvp | admitted | every member lens admitted |
| MVP | stateful_system, balanced_mvp, utility_mvp | admitted; approved scope required | every member lens admitted; approved scope required |

The isolated installed snapshot passed version/CLI help, 12 full configuration
checks and 20 focused member-lens checks; all 20 vertical-focused combinations
were rejected. All three suite digests validate. These are installed configuration
checks, not 32 end-to-end runs. Existing source admission/journal tests supply the
separate execution evidence. No general custom-workflow support is claimed.

Remaining gates: bounded live Reviewer/Editor/Verifier qualification on frozen
synthetic inputs; inspection of genuine correction, promotion/current-draft
re-review and blocking/deferral behavior; release evidence review; then separately
authorized production qualification-map and six-owner/Quickstart advertisement
updates plus unpatched activated-package admission tests. Phase 2 stays unavailable
for consumer-2, including Standard jobs. Preserve consumer-1 and bridge behavior.
The candidate cannot yet be called release-ready.

### Stable activation and rollback procedure (not executed)

1. After live evidence review and explicit activation authorization, add only
   consumer-2's exact validated digest to the production map, retaining consumer-1.
   Update suite advertisements consistently and run actual shipping-map admission,
   re-entry and refusal checks. Rebuild a new versioned snapshot; do not mutate this
   candidate or any frozen suite/job. A separately authorized commit supplies the
   final source checkpoint; use final version 0.3.0 only after release approval.
2. Install the final snapshot and its environment at the new, nonexistent local
   `/Users/Shared/Agent-Workspace/tools/whetstone/releases/0.3.0-<commit>` path.
   Record actual version and commit in `.whetstone-installation.json`. Validate its
   version, full contract resources and command surface before pointing any lane.
3. Save current stable's resolved target (observed 2026-11-24:
   `/Users/Shared/Agent-Workspace/tools/whetstone/releases/0.1.0-6e19fe3`).
   For each separately authorized lane change, create a temporary symlink in
   `/Users/Shared/Agent-Workspace/tools/whetstone/channels`, pointing at the tested
   installation, then use Python `os.replace(temp_link, lane_path)` for an atomic
   candidate or stable pointer replacement. Verify with
   `whetstone --channel candidate --runtime-info` before stable adoption and
   `whetstone --channel stable --runtime-info` afterwards.
4. Rollback uses the same temporary-symlink/`os.replace` operation on `stable`,
   pointing to the saved old installation; verify runtime-info and audit help.
   Retain both installations. Do not resume consumer-2 jobs under the old stable:
   use their matching retained runtime explicitly. Lane rollback is not job migration.

No pointer change, commit, publish, activation or external source write is authorized
by this procedure. The final activation artifact must be rechecked after its gate
and version changes; this disabled snapshot cannot stand in for that evidence.


### Live window — stopped at decision, 2026-11-24

The approved OpenAI/Codex window used eight calls with gpt-6.1-sol, medium.
The first four-call attempt was stopped for a staging error: single-level scope
headings compiled generic defaults. It receives no qualification credit. A fresh
root with correct two-level headings bound the intended scope surfaces; all four
Utility MVP vertical reviewers returned findings for the intended empty-dequeue gap.
The immutable first root was retained, not repaired in place.

The corrected run stopped at `finding_admission`, ordinal 0. Buildability advice
was editor_fixable, but canonical classification elevated it to
operator_decision_required with `visible_policy_or_destructive_trigger`. Its
recommendation includes an example after the last task is removed. No Editor,
Verifier or promotion occurred. The approved stop-on-unresolved-decision boundary
was honored; no blanket attestation or gate bypass was used.

See [live receipt](qualification/phase1-live-2026-11-24.json). This is partial live
review/decision-gate evidence, not a successful execution qualification. Balanced
MVP confirmation and the deliberate dependency-conflict case remain unrun. No
runtime source or production gate changed. Next resolve the exact decision gate
or investigate the conservative trigger before resuming a separately bounded
window; remaining calls are not an automatic new 30-minute allowance.


### Trigger investigation and continuation preparation

Exact reproduction confirms the sole lexical match is `removed` in the example
“after the last task is removed.” This is a false positive about requirement
mutation: it describes queue behavior. Reviewer advice was clarification-only;
no destructive effect, invariant violation or authority change caused this gate.
The retained classifier deliberately scans claim plus recommendation without
semantic role analysis. Removing past-tense matches would also suppress legitimate
warnings such as “the requirement is removed”; no such exemption was implemented.

A general automatic-classifier correction remains unresolved, not fixed. Changing
classification for admitted jobs would also change replay of retained evidence.
The safe prepared continuation uses the existing exact operator-decision protocol,
not a regex exception or rewritten Reviewer artifact. Its single option authorizes
only the empty-result clarification and examples, with no deletion units, weakening,
scope or authority change. `live-campaign-002/clarification-options.json` and
`clarification-preflight.json` under the readiness evidence root retain the option
and successful verified Phase 1 dry-run. No response/attestation was fabricated,
no request was committed to the run, and no provider was called.

34 existing classification, decision and shared-policy regression tests pass.
The general classifier design and exact decision disposition remain distinct:
the prepared decision can unblock this run after explicit selection; it does not
claim to fix false positives for future jobs. Before live continuation, recheck
source/package bindings and a fresh authorized campaign time/call allowance.
Activation and the installed stable pin remain unchanged.


### Authorized clarification and resumed live window

The operator explicitly approved the exact clarification-only option and a fresh
30-minute window with the remaining 12 calls. The verified decision owner published
its request/response/selection with no deletion or weakening authority. Source
hashes still matched prior offline qualification. Six additional calls completed:
one Editor, one semantic Verifier and four current-draft Utility MVP reviews.
The candidate was promoted at ordinal 1. The EMPTY result and examples preserve
FIFO and identifier allocation. This establishes a genuine live edit/verification/
promotion/re-review chain, not full Phase 1 completion.

Post-edit review produced a minor operator-decision finding: define invalid enqueue
input's observable result and queue/identifier effects. Canonical classification
kept it blocking (`explicit_decision_prevents_deferral` and
`new_requirement_needs_authority_or_decision`). The run stopped at finding_admission
without treating minor severity as permission to accept an unresolved decision.
No further authority was inferred. Total calls across attempts: 14; six unused.
The [resume receipt](qualification/phase1-live-resume-2026-11-24.json) records evidence.

Balanced MVP confirmation is locally staged from the promoted synthetic draft but
was not launched. Its package does not claim a clean result. The deliberate
scope-dependency case also remains unrun. Release readiness is still incomplete;
activation, stable pin, frozen suites and runtime source remain unchanged.


### Invalid-input continuation — runtime blocker

The user approved an explicit invalid-input result with unchanged queue contents
and identifier allocation. That exact decision was published through the verified
Phase 1 decision owner. The authorized continuation used two of its six remaining
calls: Editor and semantic Verifier. Verification reported pass and a verified
history entry at ordinal 2 was written for draft
`ca8f88bfc22209efc768283c82c9142c3175e9f7611f07c5301bfdd61a824a7f`.
The command then returned exit 2 / `vnext_input_invalid` with
“Phase 1 evidence changed during state recovery.” No post-edit re-review or
Phase 1 completion is claimed. Preserve the original run for diagnosis; do not
rewrite evidence, retry past the check, or activate the suite.

[Failure receipt](qualification/phase1-live-invalid-input-2026-11-24.json) retains
the exact outcome and relevant artifact hashes. Total provider calls: 16;
four remain unused. Balanced confirmation and deliberate dependency-conflict
qualification remain outstanding. Local evidence replay took several minutes
between provider calls; this is a performance limitation, distinct from provider
latency. Diagnose the state-projection recovery failure before further live work.
No runtime source, frozen identity, stable pin or production activation changed.


### Recovery failure fixed and qualified offline

Root cause: an uncommitted technical-failure report uses a generated timestamp.
Recovery's source synchronization already reused the initial timestamp, but its
final evaluation did not. Crossing a clock second changed the report reference
hash and therefore the closeout evidence. No actual authority change was required.
The fix passes the initial timestamp to the final evaluation, leaving both evidence
and materialization equality checks intact. Retained reports still use their
persisted timestamps; no frozen schema, suite or job identity changed.

The deterministic clock-tick regression failed with the exact production error
before the fix and passed afterwards. All eight operator recovery tests passed
(96.334 seconds), including lost acknowledgements, source barriers, corrupted
committed artifacts and preservation of existing state fields. A read-only check
on the real failed run reproduced equal evidence with the timestamp pinned; all
253 run files retain their sealed hashes. No live calls or repair writes occurred.
See [fix receipt](qualification/phase1-recovery-fix-2026-11-24.json).

The live run currently derives an uncommitted TARGET_NOT_REACHED budget closeout,
not stability. Next continuation must use supported recovery, commit the legitimate
failure closeout, and explicitly extend review allowance before spending the four
remaining calls on the promoted draft. Do not fake completion or edit run metadata.
Preserve a forensic archive before any authorized recovery writes. The prior
0.3.0rc1 snapshot predates this fix and must be rebuilt/rechecked before release;
its smoke evidence does not qualify the corrected executable. Activation is off.

## Utility MVP vertical live closeout

Recovery on the canonical root synchronized the ordinal-2 projection and committed
the prior TARGET_NOT_REACHED closeout. The pre-recovery archive verified against
all 253 sealed file hashes. Grant 1 raised each of the four lens budgets from two
to three. Calls 17–20 reviewed the same ordinal-2 draft and returned zero findings.
Whetstone committed accepted PHASE_1_STABLE evidence and synchronized run state
with Phase 2 readiness false. The campaign used its full 20-call allowance.

The [final re-review receipt](qualification/phase1-live-rereview-2026-11-24.json)
records the archive, grant, draft, responses and closeout references. Balanced MVP
live confirmation, the deliberate dependency-conflict probe, a refreshed installed
candidate and release review remain outstanding. Production activation is off.
