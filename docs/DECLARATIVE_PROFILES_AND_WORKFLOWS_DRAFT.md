# Declarative profile lenses and bounded workflows — draft specification

Prepared 2026-10-31 against source checkpoint `3d2eb2d` and the local assessment.
**Status: proposed design for review; not ratified, implemented or qualified.**
The operator authorized this specification work, not the technical choices below,
runtime changes, live calls or release activation. “Required” in this document
describes the proposed contract if ratified; it does not amend current authority.
All new field, policy and format names below are proposed, unavailable names.

Local review revision, 2026-11-02: clarified portable built-in dependencies,
typed step prerequisites/completion obligations, phase-scoped invalidation and
retained time windows. These resolve draft gaps; they do not ratify the proposal
or authorize implementation. Product choices in section 14 remain open.

Tracking: [implementation-plan proposal](../IMPLEMENTATION_PLAN.md#proposed-declarative-profiles-and-workflows)
and [future direction](../notes/future-improvements.md#declarative-profile-lenses-and-configurable-workflows).
This is a bounded design document, not another normative owner or an addition to
the completed verified-promotion delivery milestones.

## 1. Purpose and boundary

Separate reusable review perspectives from executable workflow choices:

- A **lens definition** supplies identity/version, focus, guidance and optional
  declared input dependencies. Adding a perspective requires data, not Python.
- A **workflow definition** selects exact lenses and independently identified
  steps, order, finite budgets, supported repeats/skips and rechecks after edits.
  Rearranging a sequence or changing its bounds requires configuration when the
  resulting plan is legal under an already supported execution contract.
- An **engine contract** supplies allowed operations, phases, role capabilities,
  feedback validation, acceptance/terminal gates and preservation requirements.
  Adding an execution capability can require code, contract versions and testing.

Audits and sharpening loops consume the same resolved definitions. They retain
different outcomes: an audit is an assessment, focused stability is narrower
than full Phase 1 stability, and Phase 2 convergence requires its typed gates.
Guidance cannot authorize mutation, add tools, waive scope, redefine severity,
grant admission, replace a rubric or declare convergence.

Excluded: arbitrary-code plugins, executable templates, dynamic imports, remote
definition registries, distributed writers, storage changes, a generic graph
language, automatic apply-back, and a new consolidation implementation. Existing
provider consent, job-start decisions and exact source-write authorization remain
owned by their current contracts.

## 2. Existing authority and verified implementation gaps

Current owners remain authoritative:

- [Rubrics, profiles and feedback](specs/RUBRICS_PROFILES_AND_FEEDBACK_SPEC.md#review-profiles)
  distinguishes lens from quality bar and defines controlled vocabulary identity.
- [Scheduler and state](specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#round-strategy-adaptive)
  owns independent reviews, accepted versus clean drafts, bounded scheduling,
  canonical changes and invalidation, Phase 1 completion and Phase 2 sequencing.
- [Phase 2 target matrix and reproducibility](specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md#target-matrix-precedence)
  owns target/declaration semantics and attempt evidence.
- [Candidate editing](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#resume-and-replay)
  owns immutable descriptor/suite dispatch, authority, preservation and replay.
- [Scope audit workflow](specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md#change-audit-workflow)
  owns existing single-lens audits. Its objectives extension is still a proposal.
- [Controlled V release](VNEXT_VERIFIED_PROMOTION_RELEASE.md#qualified-release-and-supported-scope)
  records the exact qualified combinations; this draft does not enlarge them.

Inspected implementation, not claims of new behavior:

| Coupling | Source evidence | Required treatment in a later implementation |
| --- | --- | --- |
| Eleven lens definitions, four sets and anchors live in Python | [vocabulary](../src/whetstone/vocabulary.py), [scheduler](../src/whetstone/scheduler.py) | Resolve data into a validated plan; package built-ins as data without changing old defaults. |
| Config selects a set/budgets; constructors supply sequence, repeat and final-Phase-1 always-run behavior | [config](../src/whetstone/config.py), [scheduler](../src/whetstone/scheduler.py) | Make supported step settings explicit; do not infer extensibility from `ProfileStep` alone. |
| Unknown prompt-profile lookup returns no guidance | [prompt lookup](../src/whetstone/scheduler.py), [rendering](../src/whetstone/prompts.py) | New-format compilation rejects unknown definitions before any client. Preserve legacy dispatch rather than silently changing it. |
| Focus invalidation/resolution helpers have unit tests but no runtime callers under `src/` in this inspection | [scheduler](../src/whetstone/scheduler.py), [tests](../tests/test_scheduler.py) | Do not advertise operational selective reuse. Implement and qualify an explicit recheck policy. |
| Bridge clears cleanliness after edits; verified horizontal sequence resets it on promotion | [Phase 1](../src/whetstone/live_phase1.py), [verified sequence](../src/whetstone/vnext_verified_review.py) | Keep conservative invalidation as the proposed new-format default. |
| Phase 2 declaration handling recognizes acceptance-profile names; V pins strict/adversarial/strict and recognizes position three/name | [legacy Phase 2](../src/whetstone/live_phase2.py), [V binding](../src/whetstone/vnext_verified_phase2_binding.py), [V closeout](../src/whetstone/vnext_verified_phase2_closeout.py) | Use typed operations and validated prerequisite steps in a new contract; retain old name/position dispatch for old jobs. |
| Admission restricts names/sets; focused and vertical routes check Phase 1 membership; public V restricts workflow/set | [mutable admission](../src/whetstone/vnext_proposal_admission.py), [selection](../src/whetstone/vnext_review_configuration.py), [V review](../src/whetstone/vnext_verified_review.py), [public V](../src/whetstone/vnext_verified_cli.py) | Definition discovery is not execution qualification. Version admission separately. |
| V Phase 2 pins the complete installed vocabulary packet hash, including unused lenses/sets | [V Phase 2 review](../src/whetstone/vnext_verified_phase2_review.py), [packet producer](../src/whetstone/vocabulary.py) | New identity separates core semantics from selected lens/workflow data. Never change old packet/hash expectations. |
| Legacy resume rebuilds defaults; bridge can restore saved steps; V reproduces frozen request prompts | [resume](../src/whetstone/resume.py), [bridge continuation](../src/whetstone/preservation_continuation.py), [V prompt compatibility](../src/whetstone/vnext_verified_review_protocol.py) | New jobs load retained definitions/plans; preserve historical reconstruction/renderers. |
| Name strings also identify synthetic `vertical` packets and fallback Phase 2 accounting | [proposal admission](../src/whetstone/vnext_proposal_admission.py), [status](../src/whetstone/status.py) | Record phase/operation/step explicitly in new artifacts; never infer them from lens names. |
| Audit has one fixed artifact namespace; diagnostic sweep takes Phase 1 sets | [audit](../src/whetstone/change_audit.py), [sweep](../src/whetstone/diagnostic_sweep.py) | Shared resolver, distinct consumer contracts; neither is already the requested grouped audit. |

The pinned stable installation inspected during the assessment was `0.1.0` at
`6e19fe3`. Vocabulary, scheduler, config, prompt, audit/sweep, legacy loop and
resume files matched this checkout byte-for-byte. Stable's public V qualification
map was empty; the source release has its controlled entry. This is dated source
inspection, not a new runtime qualification or instruction to switch channels.

## 3. Proposed identities and data boundaries

| Object | Identity and responsibility |
| --- | --- |
| Lens | `(id, version, definition_hash)`: exact perspective, independent of where/when used. `version` is an opaque explicit identifier; no latest/range resolution. |
| Step | `step_id`, unique within one workflow, independent of array position and lens ID. Two occurrences of one lens have different step IDs and independent budgets/results. |
| Workflow | `(id, version, effective_workflow_hash)`: ordered steps, expanded defaults, policies, bounds and exact selected lens references. |
| Execution plan | Hash of canonical effective workflow plus exact engine/core-vocabulary references and selected lens snapshot references. Source locations are provenance, not executable semantics. |
| Review occurrence | Job, plan, phase, step ID and positive occurrence number. Attempts are subordinate to the occurrence and retain existing attempt-allocation/journal obligations. |
| Evidence | Source artifact reference plus original finding ID and occurrence identity. Neither lens name nor an issue fingerprint alone identifies an original finding. |

Reordering changes the workflow hash, but does not rename unchanged steps.
Changing guidance, focus or dependencies requires a new lens version by authoring
convention; exact hashes prevent same-label substitution in an admitted job.
Resolution can detect competing definitions in its catalog, not enforce global
version discipline across unrelated machines or historical catalogs.

A repeated lens never shares counters just because its ID matches. A later
declaration review is a separate operation even when it uses the same lens as an
earlier review. One review may support a distinct-lens coverage obligation only
where its typed terminal policy explicitly allows that; it does not silently
satisfy another required step or declaration verification.

## 4. Proposed discovery and deterministic resolution

Recommend UTF-8 JSON objects for lens/workflow documents, using closed versioned
shapes, rejecting duplicate JSON keys, unknown fields and non-finite numbers.
This needs no new parser dependency. Run-config syntax remains separately owned;
the examples below do not add accepted CLI/config operands today.

Proposed configuration selector:

```json
{
  "definition_locations": [
    {"kind": "builtin"},
    {"kind": "directory", "path": "./review-definitions"}
  ],
  "workflow_file": "./workflows/local-phase1.json"
}
```

Resolution rules:

1. With the new-format selector present, an omitted location list means only the
   packaged built-in catalog. An explicit list is the complete search set; no
   ambient home directory, environment, working-directory or network search.
   The workflow file is explicit, not discovered by a guessed name.
2. Relative paths resolve against the containing launch-config file, not process
   cwd. A location is a regular file or a directory of immediate `.json` files.
   No recursion, symlink traversal, executable files or embedded imports. Sort
   directory entries by UTF-8 filename bytes for deterministic diagnostics.
3. Read each definition once into the in-memory resolution set and retain those
   bytes. Reject malformed catalogs, duplicate location/file declarations and
   duplicate `(id, version)` definitions, even byte-identical duplicates. There
   is no first/last-location override, including collisions with built-ins.
   Multiple explicit versions of an ID may coexist.
4. References name an exact ID/version. Unknown references, ambiguous entries,
   optional expected-hash mismatches and unknown engine policy names fail before
   any client. No generic-guidance fallback or automatic version upgrade.
5. Custom IDs use `local.` or an operator namespace; `whetstone.` is reserved for
   packaged definitions. IDs/versions are data, never interpreted as paths.
   A built-in replacement uses a new ID/version and explicit selection.
6. Source-byte hashes and locators are provenance. The definition hash is SHA-256
   of the validated, canonically serialized effective definition after explicit
   defaults. Preserve both hashes when formatting/default expansion differs.
   Candidate canonicalization must use the repository's versioned exact JSON
   rules; no prose/newline normalization of guidance strings.

In new-format jobs, missing required definitions fail compilation even if no
findings would be expected. In old-format jobs, existing dispatch remains intact.
Bundled workflow templates preserve the four built-in sets, their lens order,
default budgets and explicit final-step rules. Do not silently translate every
existing job to these templates.

Portable new-format built-in lenses retain the current focus/guidance but declare
`{"draft": "all"}`. Do not copy `DEFAULT_PROFILE_FOCUS_ANCHORS` into them: several
anchors name Whetstone's own specification headings and are not dependencies of
every spec reviewed through that perspective. Historical anchors, their packet
hashes and route-specific behavior remain in the old compatibility path. This
intentional new-format dependency difference is recorded in catalog-comparison
fixtures, rather than presented as byte-for-byte vocabulary equivalence.

## 5. Proposed lens definition

Closed conceptual shape:

| Field | Proposed meaning |
| --- | --- |
| `format` | Exact supported document-format version. |
| `id`, `version` | Nonempty bounded identifiers; reject path separators/control characters. |
| `focus` | Nonempty ordered list of unique concern labels, used as review emphasis metadata. These are not new severity/oscillation enums. |
| `guidance` | Nonempty literal text. No template evaluation, includes, tool declarations or executable hooks. |
| `dependencies` | Optional bounded declaration of draft-section dependencies; absent means whole draft. It cannot reduce mandatory context/authority barriers. |

For a declared draft dependency, propose either `{"draft": "all"}` or
`{"draft": "sections", "anchors": ["exact-id-or-unique-suffix"]}`. Resolve each
anchor against the canonical section index, requiring exactly one match per
anchor; zero/ambiguous matches fail fresh compilation. Store original selectors,
resolved IDs and parser identity. Rename/move/delete handling is in section 9.
No dependencies on other lens outputs are introduced.

Section dependencies are opt-in, project-specific definitions, not a default
property of a general perspective. A definition with such dependencies must use
its own ID/version; there is no workflow override of an immutable lens. For the
initial format, section selectors are accepted only for a single draft input.
Multi-document audits use whole-input dependencies; reject section selectors
there until a separately defined input-ID/section namespace is supported. Do not
flatten headings across documents or resolve against an arbitrary first file.

Rubric, scope, authority, invariant and reference-context bindings remain required
inputs of the consumer, regardless of section dependencies. Changed context
cannot be hidden behind a narrow draft selector. Dependencies describe possible
reuse conditions, not read restrictions or permission to omit the full draft.
The initial proposed engine still reviews the whole bound draft.

Example, fictional new perspective; not an installed or approved profile:

```json
{
  "format": "lens-definition-v1",
  "id": "local.user-errors",
  "version": "1",
  "focus": ["actionable-errors", "safe-retry"],
  "guidance": "Check whether user-visible errors explain the next safe action. Stay within the declared scope; request a decision for new product policy.",
  "dependencies": {"draft": "all"}
}
```

## 6. Proposed workflow and capability validation

A workflow declares exact format/id/version, a consumer/phase, an engine contract,
ordered steps, a completion policy, recheck policy and finite limits. Each step
declares `step_id`, exact lens ID/version, typed operation, review budget, repeat
and skip policies plus a `requires` array. The workflow also declares an explicit
`required_steps` array for completion. Unknown fields/policies fail; there is no expression evaluator.
Selected definitions are resolved before the effective workflow hash is formed.

Initial scheduling proposals:

- Ordered arrays, sequential execution. Horizontal and vertical sharpening use
  their existing different review/edit-cycle semantics. No parallel calls or
  concurrent writers are introduced by definition discovery.
- Step review budgets are positive integers, scoped to that step across the
  phase, including repeat/recheck/closeout reviews. Every provider invocation,
  including invalid/failed attempts, also consumes the enclosing call limit;
  no free retry or hidden closeout allowance. Historical budget rules stay on
  historical formats. Existing explicit budget grants, where supported, remain
  append-only bound events, never edits to the original workflow snapshot.
- `repeat` is `none` or `until_clean`, within the step's remaining budget. Clean
  uses existing phase-specific valid Reviewer evidence and serious-finding
  rules, not Editor resolution claims. Repeat cannot bypass a decision pause,
  failure, preservation rejection, conflict/oscillation halt or target policy.
- `skip` is `never` or `reuse_valid_same_step`. Reuse requires a valid occurrence
  for that exact step/operation/lens/plan and current input identity. It never
  borrows a different occurrence's budget or treats missing evidence as clean.
  Declaration reviews and any engine-mandatory always-run steps cannot skip.
- Only existing engine-defined minor/nit treatment, invalid-artifact handling,
  declaration maintenance and halt precedence apply. They are not arbitrary
  workflow strings. Engine contracts can restrict these choices further.

For clarity, `review_budget` counts valid completed review occurrences, whether
clean or not; failed/invalid attempts consume the audit/phase plan's retained
`max_client_calls` allowance instead. That total includes every role's calls,
including Editor/Verifier and any separately approved consolidation calls.
Reserve a call before invocation using the consumer's existing journal boundary;
uncertain attempts cannot be silently refunded. Retries still require their
consumer's explicit supported policy. The limits have separate explicit scopes:

| Limit | Proposed scope and continuation rule |
| --- | --- |
| `max_client_calls` | Total across this audit or phase plan, including reentry, retries, rechecks and all roles. Persist reservations/outcomes; never reset on invocation. |
| `max_window_seconds` | One wall-time window across this audit or phase plan, including stops and operator pauses. At its existing audit/phase-start boundary, persist `started_at_utc` and `deadline_utc` once, before the first client. Resume uses the retained deadline, never a new window. |
| `max_invocation_seconds` | Monotonic execution cap for one invocation. A new invocation can receive its own invocation cap only within the original retained window and remaining call allowance. |

All three limits are explicit positive finite values in the proposed effective
plan. Any separately authorized job-wide call limit/deadline is an additional
outer bound; the earliest deadline and smallest remaining allowance govern.
For Phase 2, start the window when entry processing is admitted, before any
entry-metadata Verifier call; do not wait for the eventual entry commit to start
charging its calls/time. This budget record confers no transition authority.
Remaining wall time at invocation start is the retained deadline minus current
UTC time, further constrained by outer authorization; enforce its countdown with
a monotonic clock during execution. A backward clock jump or inability to
establish deadline continuity stops new calls for operator reconciliation, not
a fresh window. Read-only inspection and already-supported recovery without new
calls retain their existing authority boundaries after expiry. No automatic
window extension, crash recovery or change to old jobs' time semantics is added.

A cap stops new work and uses existing cancellation/uncertainty handling; it
cannot fabricate completion or erase previously committed valid evidence.
Numeric defaults/ceilings remain open. Hard token/cost bounds
may be offered only where the transport can enforce them; unknown usage remains
visible and cannot substantiate a hard monetary guarantee.

The compiler validates operations, phase and consumer together:

| Consumer/operation | Allowed effect and terminal boundary |
| --- | --- |
| Bounded audit lens pass | Reviewer only; frozen common inputs/scope; audit-specific response validation; no Phase 1 credit, Editor, mutation or convergence. |
| Focused Phase 1 review | Existing review/correction contract where selected; focused cleanliness alone cannot authorize Phase 2. |
| Full Phase 1 review | Required configured steps, accepted current draft and current cleanliness of every required step before full stability. |
| Phase 2 review | Entry prerequisites, bound rubric/target, required phase feedback and preservation protocol. It cannot be moved into Phase 1 by renaming its lens. |
| Phase 2 declaration review | Explicit typed operation with declaration/context prerequisites and current-draft verification; only its owner can accept the declaration. |

The engine advertises the supported operation/phase/role/policy matrix. A lens
does not advertise itself as a Verifier, Editor or declaration authority. The
compiler rejects a workflow that assigns audit steps mutation, declaration steps
without prerequisites, invalid Phase 1 membership for its contract, missing
mandatory gates, an empty required set, unsupported mode/target combinations,
or settings outside its qualified range. Arbitrary new policy identifiers refuse.

### Explicit prerequisites and completion obligations

`requires` is a finite array of closed objects with exactly `step_id` and
`evidence`. In the proposed initial format, `evidence` is `valid_current` or
`clean_current`: a valid completed review of the active phase's current draft
under that prerequisite step, respectively without or with its cleanliness
requirement. Both bind exact plan/lens/operation/context identity. A step's old
result cannot satisfy a dependency after invalidation. `requires: []` has no
authored step dependencies; it does not remove engine preconditions.

All referenced steps must exist, precede the dependent step in the authored
order, belong to the same phase plan and have an evidence-producing operation
supported for the requested evidence kind. Reject self/duplicate/forward/missing
references and cycles. Reordering steps without preserving legal prerequisites
fails compilation; no implicit reordering or name-based edge inference.

`required_steps` contains unique existing step IDs. Full Phase 1 requires every
configured review step, including repeated lenses; focused completion retains
its narrower typed policy. For Phase 2, the selected engine contract sets the
minimum mandatory operations and allowed early-completion policy. The authored
required set must include that minimum or compilation refuses. Merely listing a
step is not a completion waiver for other engine obligations.

The compiled plan retains ordered step records, explicit prerequisite edges and
`completion_obligations`: the exact required step IDs, typed policy reference,
required distinct lens identities where applicable, target/rubric references and
declaration requirement. These are deterministic outputs of authored data plus
the pinned engine contract, not model-generated instructions. A declaration
operation must include the predecessor evidence edges that its engine policy
requires; omitted/weaker edges fail rather than being silently supplied. At
runtime, its owner additionally verifies the current declaration package,
eligible lineage, accepted draft/target and preservation prerequisites. No
authored edge can stand in for those cross-phase/authority checks.

For example, this proposed Phase 2 final declaration-step fragment explicitly
requires clean current evidence from two earlier steps. It is not a complete
qualified Phase 2 workflow; policy/target admission remains separate:

```json
{
  "step_id": "declare-final",
  "lens": {"id": "whetstone.convergence_strict_check", "version": "builtin-2026-05-17"},
  "operation": "phase2_declaration_review",
  "requires": [
    {"step_id": "readiness-initial", "evidence": "clean_current"},
    {"step_id": "challenge", "evidence": "clean_current"}
  ],
  "review_budget": 2,
  "repeat": "until_clean",
  "skip": "never"
}
```

In Phase 2, exhausting the sequence is not itself a completion gate. A typed
policy may retain today's early-convergence behavior when its distinct-lens
coverage, current declaration and target requirements already hold. Later
unexecuted steps remain `not_run`; do not fabricate their clean results. The
compiler distinguishes scheduled steps from mandatory completion obligations,
and rejects omission of any mandatory operation/prerequisite. Phase 1's proposed
full-stability contract requires each required step, including repeated ones.

Propose replacing name/position tests only in a **new** engine contract with
explicit operation tags and prerequisite step IDs. It may retain a policy that
requires the existing strict/adversarial/strict template. Compilation cannot
turn today's hardcoded checks off. Broader Phase 2 sequences/lens assignments
require a policy decision and qualification, not just schema acceptance.

Example Phase 1 horizontal workflow; all syntax and values are proposed, and
the engine-contract label denotes future qualification, not shipping support:

```json
{
  "format": "workflow-definition-v1",
  "id": "local.error-pass",
  "version": "1",
  "consumer": "phase1_horizontal",
  "engine_contract": "declarative-phase1-v1",
  "completion": "full_phase1_stability",
  "required_steps": ["errors-initial", "errors-final"],
  "recheck": "all_after_edit",
  "limits": {"max_client_calls": 12, "max_window_seconds": 1800, "max_invocation_seconds": 600},
  "steps": [
    {
      "step_id": "errors-initial",
      "lens": {"id": "local.user-errors", "version": "1"},
      "operation": "phase1_review",
      "requires": [],
      "review_budget": 2,
      "repeat": "until_clean",
      "skip": "reuse_valid_same_step"
    },
    {
      "step_id": "errors-final",
      "lens": {"id": "local.user-errors", "version": "1"},
      "operation": "phase1_review",
      "requires": [{"step_id": "errors-initial", "evidence": "clean_current"}],
      "review_budget": 2,
      "repeat": "until_clean",
      "skip": "never"
    }
  ]
}
```

This demonstrates independent repeated steps, not a recommendation that one
perspective is sufficient for every product or a claim that this example is
qualified for V. “Full” refers to the frozen required set approved for that
engine/consumer contract, not universal quality coverage. The numeric limits
are illustrative, not approved defaults.

## 7. Proposed resolution, compilation and admission boundary

Pure local definition preparation, before any model:

1. Parse the explicit selector, catalogs and workflow; validate strict shapes and
   deterministic identities/collisions; resolve the exact selected definitions.
2. Bind the consumer's frozen specification/scope/context inputs, parser, rubric
   and core vocabulary. Resolve and validate declared draft dependencies.
3. Expand built-in defaults, assign/validate authored unique step IDs and compile
   the finite plan. Retain explicit prerequisite edges and derived completion
   obligations. Validate capability matrix, prerequisite ordering, budgets,
   repeats/skips, rechecks and typed terminal requirements. No silent repair,
   dropped step or substitution. Emit inspectable diagnostics before clients.
4. Produce immutable source/effective definition snapshots, workflow/plan and
   their hash references. The final snapshot set is derived from the bytes just
   validated, not reread from a changing catalog. Validate all references before
   publishing a complete plan record. Interrupted preparation is not admission.
5. Admit through the existing consumer's supported storage/job authority owner.
   Validate plan agreement with ordinary config/CLI selections; conflicting old
   set/profile/budget operands refuse rather than choosing precedence. A legacy
   `--profile` alias may map only through a versioned explicit built-in adapter.
6. At every client/authority boundary, check admitted immutable inputs, current
   source/draft barriers and legal next gate as today. A plan is input evidence,
   not an approval, candidate, clean result, entry commit or source-write grant.

Suggested logical records, with final schema/path spelling still subject to
artifact-owner review: selected lens source/effective snapshots, authored and
effective workflow, execution plan, definition provenance manifest, and existing
per-occurrence prompt/feedback/telemetry plus a new step/operation binding.
Use job-local immutable artifacts, not mutable references into installation
directories. No new runtime JSON schemas or frozen-suite files are created here.

The effective workflow references definition hashes, not job IDs. The execution
plan references those artifacts and versioned engine semantics; the job's new
review-configuration format references the plan. Thus construction is acyclic:
definitions → workflow/plan → review configuration → job identity. Preserve
existing client/model, authority, scope and protected-invariant bindings.

Phase 2 may still be prepared after Phase 1. Its separately bound plan/config
references the immutable job and Phase 1 inputs in the entry envelope; it cannot
replace the Phase 1 plan. Publish it under the existing distinct configuration,
request and entry-commit boundaries. Publishing definitions is never Phase 2 entry.

## 8. Proposed immutable identity, manifests and continuation

New jobs retain the exact selected effective definitions and workflow, plus
source-byte provenance, resolved anchors, compilation/renderer/parser versions,
engine capability policy and core-vocabulary hash. A job uses only these retained
definitions for later prompts and replay. Installed discovery is a fresh-job
operation; it is not repeated to resolve an admitted job.

| Continuation condition | Proposed required behavior |
| --- | --- |
| Installed definition changed, removed or location unavailable; retained snapshots valid | Continue using retained bytes and supported pinned engine/renderer; report provenance without adopting installed changes. |
| Retained definition/plan missing or hash-invalid | Refuse continuation. No fallback to installed definitions, name-only defaults or regenerated prompt text. |
| Engine/renderer/schema version unavailable or unqualified for this job | Refuse with exact unsupported-version diagnostic; read-only inspection where already supported. Never silently upgrade. |
| Caller changes workflow order, lens version, guidance, dependencies or original bounds | Require a fresh job/phase binding where permitted; refuse replacement of committed inputs. Only existing qualified budget-grant events can extend allowance. |
| Pending/uncertain publication or client journal exists | Existing recovery rules select the next gate; definition resolution adds no automatic crash recovery or new calls. |

Separate a **core vocabulary** identity (severity, baseline invariants, feedback
classification, oscillation/opposition rules) from selected **lens/workflow**
identities in new manifests. New prompt construction consumes that frozen core
plus the selected snapshots. Adding an unused catalog lens must not change an
admitted plan or its prompts. Selected guidance changes do change identity.
This requires new versioned vocabulary/manifest/consumer contracts; changing the
existing V literal hash or regenerating its old packet is not a migration.

Keep current feedback schemas/normalization semantics wherever compatible. Lens
names/issue types are already strings; severity is still normalized by the engine,
and Phase 2 still requires its controlled classification fields. Bind step and
definition identity in a new owner envelope rather than injecting unknown fields
into old closed schemas. Persist each original review and prompt; a convenience
manifest or consolidated packet cannot replace occurrence/attempt evidence.
Record phase and operation explicitly so status never guesses them from names.

## 9. Proposed coherent recheck policy

**Recommendation for the first new engine contract: `all_after_edit`.** Declared
dependencies are validated and snapshotted, but do not yet authorize selective
clean-result reuse. This is a deliberate proposed subset of the broader anchor
semantics in the scheduler owner, not a claim those semantics operate today or
an amendment to old jobs.

1. A clean result binds the exact step, lens definition, operation, input/context
   hashes and reviewed draft. Editor resolution cannot mark a new draft clean.
2. Any accepted/committed draft-byte change invalidates all review cleanliness
   in the **active phase plan** for the new draft, including declaration-review
   results and dependent step evidence. Rejected/unverified proposals never
   become the next base. Required metadata/version mutation within that phase
   is also an edit for this policy. Historical prior-phase evidence remains
   immutable; it is not relabeled current or erased.
3. A horizontal engine returns to the earliest required unverified step in
   workflow order. It uses remaining step budgets; it cannot loop without bounds.
   Vertical mode reruns its required independent stack on the new draft before
   another edit/stability decision, as its current typed contract requires.
4. A byte-identical accepted no-op does not invalidate results by itself, but
   unresolved findings, invalid feedback or changed authoritative context still
   prevent inappropriate reuse. Context/rubric/scope/authority changes outside
   permitted lifecycle events require a new binding/job, not an automatic recheck.
5. Before active-phase completion, all required step evidence must be valid for
   the current draft under the policy, acceptance must hold, and the typed target/declaration
   gates must pass. If rechecks cannot fit remaining step or call/time limits,
   report verification debt and stop under the consumer's non-success boundary.
   No hidden extra Editor or repeat-until-agreement loop.

At the Phase 1 → Phase 2 boundary, the existing typed entry owner first proves
complete Phase 1 prerequisites on the exact bound Phase 1 pointer. If entry
requires metadata maintenance, its separately admitted system-only candidate
must pass the existing candidate verification/promotion protocol. The distinct
entry commit binds the original Phase 1 closeout plus that exact transition
evidence and Phase 2 start pointer. See [scheduler-authorized metadata](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#scheduler-authorized-system-metadata)
and the [entry implementation](../src/whetstone/vnext_version_entry.py).
The original Phase 1 review hashes remain unchanged; this does not assert they
reviewed the post-transition bytes. Phase 2 starts with no clean step evidence.

After valid entry, an ordinary Phase 2 edit invalidates Phase 2 results and stale
declaration evidence, then follows Phase 2 maintenance, recheck and halt rules.
It does not automatically reopen Phase 1 or require its historical reviews to
match each later Phase 2 draft. Historical entry eligibility is established by
the bound prerequisite/transition chain, not a global clean flag. Invalid/stale
entry lineage refuses under existing owners; a workflow cannot use phase-scoped
invalidation to waive a missing prerequisite or invent another transition.

A later **selective recheck** capability is explicitly deferred. Its minimum
qualification would require persisted producer-authored change records, canonical
old and new section IDs for rename/move/delete/add, unambiguous lineage and
dependency mapping, unchanged mandatory context, and a reuse witness per result.
Missing/invalid/unmappable change records invalidate all; unreadable/invalid draft
artifacts halt. Cross-section/global dependencies must be represented, not guessed
from a lens's prose focus. An absent dependency declaration means whole draft;
an empty set never means unaffected by all edits. Phase 2 declaration/hash gates
and preservation checks cannot be selectively skipped. Do not accept a selective
policy name until that implementation and its consuming routes are qualified.

## 10. Audit consumers and consolidation boundary

Carry forward all [selected-lens audit requirements](../notes/future-improvements.md#selected-lens-reviewer-only-audits-and-consolidation).
An audit selects a unique bounded set of exact lens definitions. Each gets an
independent step/pass against the same frozen specification inputs, notes and
scope. Lens order does not permit later passes to read earlier findings. Shared
input identity differs from lens-specific prompt identity. Workflow-level repeated
lenses are useful in sharpening; they do not imply repeated audit passes here.

For example, the proposed audit selector can reference the shared definitions:

```json
{
  "selected_lenses": [
    {"id": "whetstone.consistency", "version": "builtin-2026-05-17"},
    {"id": "local.user-errors", "version": "1"}
  ]
}
```

This is a selection fragment, **not a complete executable audit request**. The
built-in version label is a proposed packaging label for existing guidance, not
an installed lens version. Exact bounds and the audit/consolidation contract must
be bound before a grouped audit is executable. Single-lens v1 audits stay
supported; using shared definitions must not force an extra model call.

One consolidation stage must retain originals, source attribution/evidence,
distinct concerns and explicit disagreements; account for every original finding,
including out-of-scope findings; and never treat agreement as proof. Duplicate
grouping must preserve original severity/scope claims and distinct source IDs.
Original failed/invalid/incomplete outcomes remain visible, with available raw
evidence labeled as such. A partial audit cannot be presented as complete/clean.
Separate reviewer attempts and any consolidation calls/costs remain attributable;
unavailable usage/model evidence is explicitly unknown, not inferred.

Still open: consolidation algorithm/model and evidence access; severity/verdict
conflict resolution; continue/stop/retry/partial-consolidation and recovery policy;
serial versus parallel audit execution; audit CLI/config and final artifact
shapes; and aggregate/per-lens/consolidation/retry budgets. This draft recommends
sequential execution as a starting option, but does not decide those policies.
Do not use sharpening's `until_clean` to supply missing audit retry authority.

The [audit-objectives proposal](../IMPLEMENTATION_PLAN.md#proposed-audit-change-objectives-release)
remains unratified. Coordinate versioned request/report ownership with it. A lens
set does not establish objective coverage, preservation satisfaction, Phase 1
credit or convergence. Definition/compiler work must be independently useful
without shipping an incomplete grouped audit as a finished feature.

## 11. Migration, ownership and qualification

Recommended opt-in migration:

1. Preserve all existing formats, built-in default behavior, historical hash
   preimages, packets, schemas, suite files and qualification maps. No new-format
   selector means today's path, not automatic conversion or changed rechecks.
   Adding declarative support must not remove currently supported job versions;
   unavailable-version refusal is a compatibility safeguard, not permission to
   drop their existing dispatch paths.
2. Generate and compare packaged declarative built-ins to the current vocabulary
   and profile-set strategies. Require prompt and scheduling equivalence where
   semantics are claimed equivalent; document intentional new-format differences.
   Compare focus/guidance separately from portable whole-draft dependencies; keep
   legacy Whetstone-heading anchors only in their existing compatibility path.
3. Add new strict format/plan envelopes and engine dispatch. New jobs choose
   the format explicitly. Old jobs keep their existing supported runtime and
   replay path; no in-place import by inferring snapshots from current defaults.
   A legacy plan export can be diagnostic only, not retroactive immutable proof.
4. Integrate consumer adapters separately. Legacy sharpening, bridge and V have
   different evidence/storage boundaries; none inherits another's qualification.
   A config accepted by the resolver can still be refused by consumer admission.
5. For V, bind the new plan through a new review-configuration/descriptor contract
   and consuming suite as required by identity changes. Qualify legal matrices
   before public advertisement. Keep the released strict/adversarial/strict,
   whole-vocabulary and fixed-rubric contracts intact for existing jobs.
6. Only after ratification, coordinate amendments with the existing owners:
   profiles/vocabulary; scheduler/completion/rechecks; artifact schemas/manifests;
   scope/audit; Phase 2 declaration/reproducibility; candidate admission/replay;
   coordinating capability map. This draft is not a replacement authority family.

No runtime installation, stable promotion, storage portability change, candidate
pipeline redesign or expansion of the accepted Q3/Q4 evidence is part of this work.

## 12. Proposed acceptance cases

All future qualification below uses deterministic local fixtures/injected clients
first. These are expected cases, **not tests executed or passing credit**.

| Case | Expected result |
| --- | --- |
| Add a new data-only lens; change order/budget within a supported workflow | Compile and execute the qualified consumer without Python edits; persist exact selected identities. |
| Unselected valid definition added or reordered on disk | Selected plan/prompt identity unchanged; provenance may report discovery separately. |
| Same ID/version twice, including identical bytes or built-in collision | Reject before clients; show both locations; no implicit override. |
| Unknown version/field/policy, malformed JSON/duplicate key, wrong expected hash | Reject before clients; no generic lens/default fallback. |
| Two steps use one lens | Distinct state, counters and occurrence evidence; one step cannot overwrite/satisfy the other. |
| Narrow dependency selector has zero or multiple matches | Compilation fails with concrete selector/index evidence. |
| Portable built-in used on an unrelated spec with none of Whetstone's own headings | Whole-draft dependency compiles; historical anchor rules/packets remain unchanged. |
| Section-dependent lens selected for a multi-document audit | Refuse this unsupported binding; no ambiguous cross-document heading resolution. |
| Missing/forward/cyclic prerequisite, weak declaration edge or omitted mandatory step | Refuse before clients; compiled plan cannot infer authority from names/positions. |
| Earlier step becomes stale after a later step edits | Its dependent step is ineligible until the prerequisite is re-established on the current draft. |
| Clean review followed by accepted edit, including version metadata | All relevant phase-step cleanliness invalidated under the initial all-edit policy; rechecks use remaining limits. |
| Second required step edits after the first became clean | Earliest dirty step becomes eligible again; exhaustion reports debt, never false stability. |
| Rejected/uncertain candidate | Existing authority/recovery owner blocks advancement; no review of unverified bytes. |
| Same-step valid no-op, then reentry | Reuse only where legal; no duplicate call or fabricated result. |
| Selective policy requested without implemented qualified capability | Explicit refusal, even though lens dependencies are well formed. |
| Lens installed guidance changed/deleted after admission | Retained snapshots reproduce prompts; installed content is not consulted for execution. |
| Snapshot corrupted/missing, unavailable renderer/engine version | Refuse continuation; never reconstruct from current definitions. |
| Old legacy/bridge/V job resumed under new binary | Existing version dispatch and exact old prompt/hash compatibility preserved or explicit unsupported refusal. |
| Audit assigned Editor/declaration gate; invalid Phase 2 ordering/membership | Compiler or consumer admission refuses; prompt text cannot grant capability. |
| New perspective used in an otherwise legal but unqualified V combination | Refuse admission; discovery does not populate the shipping qualification map. |
| Final/strict configured without declaration/current required review evidence | No convergence; existing target matrix, acceptance and preservation gates apply. |
| Verified metadata entry after Phase 1 closeout | Entry binds original closeout, exact verified transition and new start pointer; no fabricated Phase 1 review or automatically clean Phase 2 step. |
| Ordinary Phase 2 edit after valid entry | Invalidate active Phase 2/declaration results; preserve historical Phase 1 evidence and validate entry lineage without restarting Phase 1. |
| Failed/incomplete lens, conflicting severities or duplicate source IDs in grouped audit | Preserve each outcome/reference; no false complete assessment; final policy remains blocked until the audit contract is decided. |
| Step review, total client-call or elapsed limit exhausted | Stop at the applicable typed boundary with remaining debt/costs; never replenish automatically. |
| Resume after invocation timeout while the retained window remains open | Use original deadline and remaining calls; only the invocation cap restarts within that remainder. |
| Retained window or outer authorization expired; caller supplies the same workflow again | No new calls/window; permitted inspection/recovery does not renew execution authority. |
| Clock continuity cannot be established | Stop new calls for reconciliation; no automatic new window or refunded uncertain call. |

Regression scope includes current audit v1, both scheduling modes, focused/full
Phase 1 distinctions, Phase 2 early-completion/closeout, synthetic vertical
packets, status phase accounting, budget-extension replay and preservation
boundaries. Repeated same-lens steps particularly test name-keyed state leaks.
Do not require another broad performance/live campaign to accept document work.

## 13. Bounded implementation slices — proposed, not authorized

| Slice | Complete deliverable and stop boundary |
| --- | --- |
| D1 — data resolution and compilation | Strict local formats, built-in catalog comparison, deterministic discovery/collision validation, independent step identities, pure compiled plan and negative fixtures. No clients or changed runtime routes. |
| D2 — frozen plan and continuation | New-format immutable snapshot/manifest/version dispatch, exact prompt reconstruction and corruption/unavailable-definition tests. Retain old jobs without conversion; no public activation. |
| D3 — reviewer-only consumer | Shared definitions for one-lens new-format audits and bounded injected-client multi-pass evidence. Preserve audit v1. Grouped assessment publication remains unavailable until consolidation/failure/budget choices are ratified and implemented. |
| D4 — sharpening consumers | Complete new-format horizontal/vertical/focused adapters and all-edit rechecks through typed completion; bounded-budget and interruption fixtures. Bridge/V remain refused until their own contract/evidence adapters qualify. |
| D5 — qualified preservation integration | Versioned bridge/V admission, manifests/core-vocabulary split and typed Phase 2 gate mapping, with exact compatibility and refusal matrix. No edits to frozen suites or activation merely to finish the slice. |

These are finite deliverables, not promises that all routes or grouped-audit
consolidation ship together. Before implementation, turn each selected slice into
an exact owned artifact/test inventory; do not label partial adapters complete.
Selective reuse is a later optional capability, outside these initial slices.

## 14. Decisions for review and smallest next step

Routine technical proposals are concrete above: strict JSON, exact ID/version
resolution, explicit local discovery, collision failure without overrides,
separate step identities, acyclic hashes, job-local snapshots and no installed
definition lookup during resume. They remain draft proposals, not accepted policy.

Essential product choices:

| Decision | Recommendation | Still requires agreement |
| --- | --- | --- |
| Initial recheck scope | Ship `all_after_edit`; validate dependencies now, defer selective reuse. | Accept extra review cost in exchange for a coherent first contract. |
| Meaning of a custom required lens set | Permit full Phase 1 completion only under an explicit supported completion contract; label the selected set, never imply universal coverage. Keep released V matrix fixed initially. | Which custom full-stability/Phase 2 combinations may be admitted and qualified. |
| Arbitrary Phase 2 rearrangement | Permit only sequences admitted by typed prerequisite/terminal policies; retain current template until a new one is approved. | Any broader supported sequence/lens assignment and declaration-review qualification. |
| Execution scope and finite bounds | Sequential initial execution; explicit per-step review and audit/phase-wide retained call/time limits, separate invocation caps and any outer job authorization; no hidden retry allowance. | Product defaults/ceilings, cost/token limits where enforceable, and audit failure/recovery behavior. |
| Grouped-audit consolidation | Retain the existing requirements and prepare a separate small policy decision using duplicate/distinct, disagreement and failed-lens examples. | Mechanism/model, severity resolution, partial publication/retry/recovery, final shapes and budgets. No model is selected here. |

Smallest next step: review this draft's technical contract and the first two
product rows, then select D1's offline deliverable if implementation is desired.
Before any grouped-audit execution, separately settle its consolidation and
failure/budget contract. Before any new V admission, settle and qualify its
explicit compatibility matrix. None of those actions is authorized by writing
this document.
