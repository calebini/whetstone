# 18.8 fenced Phase 2 entry without version changes

Date: 2026-09-20. Clean starting checkpoint: `c87fed0`.
This slice was validated unstaged and uncommitted; the user subsequently authorized
a local checkpoint. Pushing remains deferred until feature completion.

`VerifiedRun.enter_phase2()` now consumes the existing immutable Phase 2 request
under the actual D8 fence and commits phase entry separately. `phase2_state()` is
the new read-only entry/recovery view. Both require the
[new algorithm](../contracts/algorithms/vnext_verified_phase2_entry_v1.md) and
[entry schema](../contracts/schemas/vnext_phase2_entry_v1.schema.json), alongside
the existing binding/Phase 1 consumer pins. No public mode is activated.

## Entry and version boundary

The owner revalidates current pointer/draft/map, all complete Phase 1 prerequisites,
latest candidate decisions, immutable request/configuration, exact rubric and
closeout/state evidence. It does not create a missing request or finish Phase 1.
Configuration publication remains distinct from entry.

The existing pure version policy must return exactly unchanged UTF-8 draft bytes,
unchanged version labels and no promotion. Unversioned drafts and an already
correct whole-major label such as `2.0` can enter. A required rewrite such as
`0.17` to `1.0`, `2` to `2.0`, or a Status-line version promotion refuses explicitly:
version maintenance must pass the V candidate protocol. The owner never calls
the legacy file stamper or full-draft Phase 2 executor.

The immutable `rounds/phase2/entry.json` is the distinct **phase entry commit**.
It binds the request/configuration, job, current pointer/draft/map, Phase 1 closeout
and unchanged version observation. It is not a new draft-authority pointer or a
review/convergence result. Its reference is then projected into the sole new
`vnext_phase2_entry` member of `rounds/run_state.json`. All other state members,
including legacy fields and the Phase 1 closeout reference, are preserved.

## Recovery behavior

Before publishing, the owner repeats current pointer/mirror barriers, canonical
review source/receipt barriers, and exact closeout/report/state/configuration/
request/rubric/draft/map synchronization. It reproduces the binding again before
entry, checks authority/selectors/entry and captured state at the projection write,
and revalidates the request, entry and state afterward.

| Observed boundary | Result |
| --- | --- |
| Bound request, entry absent | `entry_required`; no phase entry inferred from configuration. |
| First successful entry plus state projection | `phase2_entered`. Draft bytes and authority remain unchanged. |
| Entry visible, state missing/stale | `entry_state_recovery_required`; exact reentry repairs only the projection. |
| Already visible entry, including matching state after lost acknowledgement | Repeat source/entry/final-state barriers, return `phase2_entry_recovered`, and stop. |
| Base mirror missing | Existing separate materialization recovery and end invocation before entry work. |
| Phase 1 closeout state projection missing | Require existing explicit Phase 1 reconciliation. |
| Conflicting entry, corrupt sources, or state claiming a missing entry commit | Refuse without reconstruction or overwrite. |

Read-only `committed` and `state_current` describe matching visible evidence, not
proof of an earlier flush acknowledgement. Inspection acquires no writer fence and
never repairs. Recovery allocates no new request, review, candidate, decision or
promotion ordinal, invokes no client and never continues into Phase 2 execution.

## Validation and limits

All **39 methods passed on their first runs, with no skips or fixes**: eight focused
entry methods in 89.349 seconds and 31 regressions in 158.102 seconds. The recorded
source snapshot remained unchanged throughout both invocations. At validation time,
HEAD remained at `c87fed0` and the index was unchanged. Before checkpointing, the
validated source and retained log hashes were rechecked; only handoff metadata was
updated afterward.

The [validation record](audits/VNEXT_18_8_PHASE2_ENTRY.json) binds commands, method
identities and source/log hashes. Raw evidence is under ignored
`rounds/vnext-18-8-phase2-entry-001/`; the initial clean boundary is recorded there.

Focused tests cover distinct entry and state publication; authority and unrelated
state preservation; no-version-change entry and genuine versioned refusal fixtures;
missing request/configuration-only prefix; interruption before/after entry and state
writes; fresh reopen and recovery-only reentry; repeated barriers despite visible
success; corrupt committed sources and missing entry; separate mirror/Phase 1 state
recovery; missing consumer pins; and absence of legacy executor/stamper calls.
The regression cohort covers existing binding, Phase 1 operator recovery and version
policy. No full-product regression is claimed.

Tests use scripted clients and process-local suites on macOS/APFS. Injected caller
publication/barrier failures do not add physical power-loss or exhaustive syscall
qualification. Existing D8 ownership/storage rules remain unchanged; no distributed
writer behavior is added. Legacy/bridge runtime, frozen contracts and shipping maps
remain unchanged. All four broader 18.8 tasks remain incomplete.

## Handoff

The user subsequently authorized a local commit of this validated slice. Push,
external transmission, apply-back, public activation and authoritative-spec
amendment remain excluded.

The [first request follow-up](VNEXT_18_8_PHASE2_REVIEW_REQUEST.md) now implements
request publication on the entered draft, without client invocation. Its bounded
invocation/result journal remains next. The original request boundary was to
freeze exact rubric/profile/vocabulary inputs and client request bindings, honor the explicit per-step budgets, and keep candidate production and
promotion separately gated. This entry reader is scoped to startup before Phase 2
changes the draft; later promotion requires historical entry anchoring and current
verified lineage checks in the consuming owner. Do not use this entry commit as
permission to dispatch the legacy Phase 2 runner.

Version maintenance through V candidates, Phase 2 candidate routing, convergence,
declaration, remaining focused/vertical/retry/resume/budget-extension consumers,
version/history lifecycle, strop/readback and full operator/terminal paths remain.
18.9 release qualification and activation remain deferred. No new product or
authority decision was needed for this explicitly authorized unchanged-draft path.
