# M3 version maintenance through verified candidates

Started on 2026-09-28 from M2 checkpoint `5a12cd5`, after the user authorized
starting M3. **M3 is complete at the documented internal implementation and
acceptance boundary.** The user ratified the proposed rule on 2026-09-29 with
“I approve” and subsequently authorized a local checkpoint. The six numbered
constraints below govern implementation; the earlier preflight audit remains a
historical record of the pending decision. Public activation, live provider
calls, external apply-back, normative specification edits and push remain
excluded. The unrelated notes edit remains untouched.

## Ratified decision (2026-09-29)

**May a narrowly defined, Orchestrator-owned version/status operation use
scheduler evidence as its mutation authority without an admitted Reviewer
finding, while still passing the complete verified-candidate protocol?**

Decision: **yes**, subject to the exact boundary below. This is the approved
clarification to the candidate leaf's admission/attribution rules, not permission
to stamp a verified draft after validation or reuse the preservation bridge.

The concrete case is a clean `0.17` draft entering Phase 2. The scheduler requires
`1.0`, but the clean reviews need not contain any findings. Creating a fictional
finding or attaching the stamp to an unrelated resolved finding would misstate
the authority for the change.

## Why this needs a decision

The governing requirements already settle the desired lifecycle and verification:

- [Scheduler version lifecycle](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#spec-version-lifecycle)
  requires round increments, Phase 1 Accepted-to-Draft demotion, Phase 2 entry
  promotion, and exact version/hash history. Entry requires full Phase 1 acceptance.
- [Candidate assembly](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#candidate-assembly)
  explicitly requires applying an Orchestrator-owned stamp as a system operation
  before normalization and candidate hashing. Promotion-time stamping is forbidden.
- [Patch operations](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#patch-operation)
  require every operation to address at least one admitted finding.
- [Deterministic validation](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#deterministic-validation),
  item 8, requires **every change** to be within allowed sections and attributable
  to admitted findings. It does not state how a finding-free system stamp satisfies
  or narrowly replaces that requirement, including heading/frontmatter anchors
  outside an Editor's allowed surface.

My interpretation is that assembly authority alone does not settle that last
admission/attribution rule. The missing decision concerns the scope of a system
operation; the lack of a new schema or assembler implementation is ordinary M3
engineering work, not itself a reason to ask for approval.

The [bridge Phase 2 handoff](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md#guarded-full-draft-handoff)
already has a maintenance exception, explicitly scoped to the bridge. Importing
it into V would silently broaden its authority. The M3 execution rule in
`IMPLEMENTATION_PLAN.md` explicitly requires stopping an operation when the
candidate contract cannot authorize it; no skill instruction requires this stop.

## Approved rule

1. Define a separately pinned **system metadata operation**, distinct from an
   Editor patch operation. Its authority is the exact scheduler transition and
   immutable base, not a Reviewer finding. Editor patches retain their existing
   finding attribution and allowed-section rules. Do not invent findings.
2. Limit its mutable surface to supported numeric version anchors and the
   scheduler-required Phase 1 `Status: Accepted` to `Status: Draft` token change.
   Bind exact input spans, preimages, output bytes, phase and transition. Support
   heading and frontmatter anchors without granting a whole-root/body rewrite.
   Anchor precedence, conflict refusal and numeric transformations follow the
   existing scheduler rules. Do not infer a general metadata-edit capability.
3. Attribute and count these exact system spans separately from the Editor's
   admitted surface. They do not enlarge the Editor's budgets or allow adjacent
   edits. Existing blocking invariants, authority/scope conflicts and applicable
   deletion/weakening gates still fail closed; metadata authority is not a waiver.
4. For a mutating review round, assemble the Editor changes and required metadata
   into the **same candidate** before final normalization, hashing, preservation
   assessment and independent semantic verification. Editor no-ops receive no
   stamp. Editor-selected version changes cannot supply system authority.
5. For Phase 2 entry requiring a stamp, admit a system-only candidate from the
   fully qualified Phase 1 pointer and committed entry request/configuration.
   The admitted finding set may be empty; the independent Verifier still assesses
   the exact candidate, protected units and assertions. No fabricated Editor
   invocation, review round or review-budget charge is required for the transition.
6. Both forms retain registration, final candidate decisions, exact-base checks,
   D8 fencing and atomic verified-pointer promotion. Preserve before/after versions
   and hashes in immutable evidence and derived history. No rejected or unpromoted
   candidate changes authoritative metadata. Interruption/reentry cannot stamp
   twice. Phase 2 entry remains a distinct commit after its verified prerequisites;
   configuration publication or candidate promotion alone is not entry.

The approval authorizes implementing a new, explicitly pinned consumer. Do not modify existing suite bytes or old descriptors to acquire these
semantics. This decision is recorded in this handoff; the authoritative specification files
have not been edited or applied back externally.

## Implementation inventory and execution

At the start of implementation, existing code retains these boundaries:

- `vnext_validation.validate_patch` rejects operations without admitted finding
  attribution; `vnext_candidate_validation.assess_candidate` reproduces assembly
  and checks actual changes against admitted slices.
- `patch-assembler-v2` has no system metadata operation. Its supplement explicitly
  reserves future version operations before normalization/hashing.
- The Phase 2 entry owner refuses a required stamp before entry writes. Historical
  entry replay and post-entry correction owners also retain version restrictions.
- Existing `versioning.py` has numeric helpers, but its legacy anchor selector is
  heading-first and does not implement the scheduler's full precedence/conflict
  rule. Reusing that selector unchanged is not M3 conformance. Preserve existing
  legacy/bridge behavior while implementing the V selector under its new pin.

Carry the approved delivery through:

1. New pinned system-operation admission/assembly and exact version-anchor replay,
   including preservation inventory/section identity and semantic context.
2. Phase 1 horizontal/focused/vertical and post-entry Phase 2 round integration,
   plus the system-only Phase 2 entry transaction and exact history projection.
3. Joined versioned journeys, no-op/rejection/unpromoted cases, stale sources,
   conflicting anchors, lost acknowledgement and recovery-only reentry. Regress
   unversioned routes and existing legacy/bridge behavior proportionately.

Do not treat the authority preflight or an isolated stamp helper as M3 completion.
M4's source-write decision is separate and remains unresolved; M5 and 18.9 remain
open. Public activation, real external writes and push remain deferred.

## Verification

Evidence is recorded under `rounds/vnext-18-8-m3-authority-001/`; its source manifest
binds the unchanged runtime, tests, contracts and normative specifications at
`5a12cd5`. The selected existing tests cover version helpers, candidate assessment,
required-version entry refusal, and distinct unchanged entry/recovery. **32 existing methods passed** in 27.860 seconds; the
[audit index](audits/VNEXT_18_8_M3_PREFLIGHT.json) records the command, methods and
evidence hashes. All 635 source hashes and the unrelated note hash were rechecked.
These are current-boundary checks, not evidence that M3 has been implemented.

## Implemented internal path (2026-09-29)

The new consumer selects `patch-assembler-v3` and pins the two version algorithms,
`mutation-plan-v4`, the version-operation and version-admission schemas, the
system-entry request schema, and Phase 2 entry v2. Existing descriptors and
shipped suites retain their existing semantics; no public route selects v3.

Ordinary admitted rounds now combine Editor operations and the exact system
version/status spans before normalization and candidate hashing. The candidate
map and inventory preserve established identities. Editor budgets count Editor
effects; blocking assertions and the independent Verifier see the complete final
candidate. Immutable `version_operation.json` records both raw transformation
hashes and canonical hashes. Replayed committed promotions produce
`spec.history.md`; an unpromoted operation never supplies that history.

For a bound entry that requires a version transition, the internal sequence is:

1. `prepare_phase2_version(created_at=...)` revalidates the complete Phase 1
   prefix, its current state, and immutable entry request/configuration/rubric
   under the D8 fence. It registers a system-only candidate. Its request journal
   has no client attempts and its empty patch grants no Editor work.
2. `verify(client=..., decided_at=...)` independently assesses that candidate;
   `promote(prepared_at=...)` may commit the exact candidate only after the
   ordinary final promotion-permitted decision.
3. `enter_phase2()` publishes the distinct entry commit and derived state. A
   promoted version or configuration alone does not enter Phase 2. Reentry
   repeats the barriers and recovers existing evidence without another stamp.

The first Phase 2 `draft_before.md` contains the promoted entry version; it does
not replace the last Phase 1 `draft_after.md`. Later corrections increment within
their own verified candidates. Declaration-only work cannot stamp the draft.
An unversioned/already-whole-major entry uses the unchanged-entry commit and
requires no system candidate. The version-candidate preparation method refuses
that no-op case rather than registering unnecessary work.

Ambiguous/conflicting anchors, Editor-authored version changes, metadata changes
that alter inventory topology/classification, and blocking invariants refuse.
Rejected or unresolved system candidates cannot enter Phase 2. This method does
not invent a finding, invoke an Editor for system repair, or waive an outstanding
semantic/operator decision. Broader metadata or repair authority is outside this
ratification.

Implementation acceptance is recorded separately under
`rounds/vnext-18-8-m3-implementation-001/`, indexed by the
[implementation audit](audits/VNEXT_18_8_M3_IMPLEMENTATION.json). The preflight record above remains
historical; it is not being relabeled as implementation evidence.

The acceptance matrix is deliberately explicit:

| Boundary | Evidence owner |
| --- | --- |
| Numeric schemes, synchronized anchors, exact adjacent bytes, conflicts, immutable assertions and lineage | `test_vnext_version_operations.py` |
| Phase 1 horizontal/focused/vertical promotion, clean-review accounting | `test_vnext_verified_versions.py` |
| Finding-free entry, source barriers, interrupted registration, lost history/state acknowledgements, stale state and tampering | `test_vnext_verified_versions.py` |
| Entry after a real Phase 1 promotion and clean re-review | `test_vnext_version_entry_after_round.py` |
| Post-entry `1.0 → 1.1` verification/promotion and replayed history | `test_vnext_verified_versions.py` |
| No-op/rejection preservation; separate clean declaration/convergence without another stamp | `test_vnext_verified_versions.py` |
| Unchanged consumer behavior, legacy/bridge, storage and pointer recovery | Indexed existing regression commands in the audit |

## Implementation acceptance result

**218 passing method executions cover 211 distinct methods: 18 new and 193
existing.** The core and selected regression commands completed with 134 and 66
passes. Their initial-source limitations are preserved in the audit; they are
not represented as frozen final-source runs.

On unchanged final runtime sources, the version acceptance command recorded
seven individual passing verdicts. After the conversation interruption, its
process was no longer running and the focused-route check had no verdict.
That command has no whole-run pass.
The ten outstanding methods subsequently passed in a separate command, and the
additional entry-after-round method passed separately. Together these cover
all 18 new methods on final sources. All 652 final source-manifest hashes and
the unrelated note hash were revalidated before checkpointing. Python
compilation and diff whitespace checks also passed.

The audit records exact commands, individual methods, log hashes, source
manifests and the interrupted run. Ignored `rounds/` logs remain local evidence;
the audit index is included in the checkpoint. The broader combined interruption
journey described below remains unpassed, and replay performance remains an
explicit M5 concern. This result closes only the documented internal M3
boundary, not all of 18.8 or release qualification.

The implementation and this reconciliation were checkpointed locally in
`a1d46a6`. A subsequent read-only evidence check verified all five indexed log
hashes, four manifest hashes, 652 current source hashes and the exact test-method
counts, including coverage of all 18 new methods on final sources. No additional
runtime test execution is claimed by that evidence check.

## Remaining delivery boundaries

The new algorithm documents remain draft internal consumer contracts pending
suite qualification. Testing the internal implementation does not freeze a
public suite or activate a public mode. Old descriptors cannot acquire these
semantics merely because new code is installed.

M4 still needs the concrete source-write policy ratification documented in the
implementation plan. M3 grants no external apply-back permission. M5 still owns
the combined milestone acceptance and supported-route handoff; 18.9 remains
separate. Real provider behavior and external source writes are not covered by
these scripted local tests. Repeated full-history replay also makes the joined
journeys expensive; the acceptance audit records elapsed times without claiming
a throughput or long-history performance qualification.

An exploratory combined correction/timeout/continuation/convergence test was
stopped after excessive replay time. It had promoted `1.1` and reached timeout
continuation, but it did **not** produce a passing test verdict. Its logs are
retained as diagnostics. M3 acceptance instead checks the complete version
promotion chain and clean declaration/convergence separately. The combined
two-promotion timeout/convergence journey and its replay cost remain explicit
M5 acceptance concerns; neither is silently credited as passed.

The [M5 execution plan](../IMPLEMENTATION_PLAN.md#188-m5--integrated-acceptance-and-handoff)
now tracks these as **M5-I1** (complete the joined interruption journey) and
**M5-P1** (measure and investigate replay cost), with explicit closing evidence.
The recorded entry-after-round test took 593.925 seconds; the 66-test regression
bundle took 1329.967 seconds. These timings establish an investigation need,
not a measured replay-only cost or an accepted performance budget. The stopped
diagnostic log hashes are retained in the implementation audit. Neither item
creates another milestone or qualifies public operation.

The user authorized a local commit after implementation; push remains deferred.
The pre-existing
`notes/future-improvements.md` edit is preserved, with SHA-256
`d00f59d7e61335a980652d696011fb151f2006a4bcb7cc434bf14cab0279f502`.
