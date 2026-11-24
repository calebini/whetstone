# Preparing and operating a Whetstone job

This guide is the front door for humans and operating agents. It explains the
choices to make before using the command procedures in the
[Operator Quickstart](OPERATOR_QUICKSTART.md). It documents current behavior;
recommendations below do not change runtime defaults. Future work remains in
[Future Improvements](../notes/future-improvements.md).

## Start from the intended outcome

The operating agent should propose a job from the user's intent and existing
project guidance. Summarize material assumptions and ask only when ambiguity
changes scope, authority, cost or the meaning of completion. Routine preparation
is agent work, not a questionnaire about every artifact or line of text.

| Desired outcome | Existing path | Completion means |
| --- | --- | --- |
| Assess a bounded change or explicit cross-document question | `audit-change` | A bounded assessment, possibly with findings; no edits or convergence claim. |
| Iteratively improve a draft | Phase 1 | `PHASE_1_STABLE` only when required current-draft reviews establish stability. Budget exhaustion is not success. |
| Recheck one supported profile | Focused Phase 1 | Focused stability only; it does not grant full Phase 1 credit or Phase 2 eligibility. |
| Establish convergence after eligible Phase 1 completion | Phase 2 | A supported convergence declaration, not merely zero findings or exit code zero. |
| Reconcile the accepted result with source | Strop/apply-back | Separately assessed and authorized source adoption. |

A bounded audit may be followed by edits made with the operating agent and a new
audit. That is not Whetstone's automated Editor loop. Keep each audit's evidence
separate; do not overwrite a prior audit root to manufacture an iterative history.

## Select the runtime before promising capabilities

Development note: shared Phase 1 completion and MVP support have passed targeted
offline qualification under a new, separately registered suite. They are not enabled by the current
production release gate. See the [qualification record](PHASE1_COMPLETION_QUALIFICATION.md);
do not promise this capability from the existing release or upgrade retained jobs.

Prefer an already configured `whetstone` launcher and its selected stable runtime.
If available, `whetstone --runtime-info` reports launcher selection. Launcher-only
channel options are not necessarily supported by the package CLI. Otherwise
inspect the installed command's help and package version using its environment.
Use the matching documentation. A newer checkout does not upgrade an older install.
Do not silently bypass the selected runtime with source imports.

Direct checkout commands such as `PYTHONPATH=src python3 -m whetstone.cli --help`
are appropriate for explicitly selected development work or a source checkout
without a configured launcher. They run from the Whetstone checkout.

Record the chosen runtime, workflow, profile set and editing mode. They are
separate selections. Check their complete combination before launch, rather than
choosing a mode first and discovering incompatible review settings later.

## Identify documents by purpose and authority

Do not impose names such as HLD, leaf spec or schema, or require a three-level
hierarchy. Establish what each selected document or section does: who consumes
it, which claims govern other work, how much detail belongs there, and what is
settled versus open to design changes. Propose that interpretation for correction.

A document explaining system intent may need its rationale, examples and nuance
preserved even when they are not requirements. A technical behavior specification
may permit substantial restructuring. A machine contract may permit replacement
within its parent's obligations. Review criteria and permitted edits must reflect
those purposes; protection alone cannot repair the wrong review expectations.

Select explicit review targets and context. Linked files are not automatically
included or authorized for transmission. Preserve source ownership and section
mapping when preparing a multi-document input. Bundling does not establish a
supported multi-document apply-back procedure. Resolve authority conflicts or
leave them as explicit review questions; do not silently pick a winner.

Legacy/bridge `reference_context.files` entries have descriptive, freeform roles.
A role such as `architecture_authority` informs the prompt; the label itself is
not a preservation gate. Verified jobs use formal authority-map bindings with
roles such as `mutable_target`, `normative_authority`, `implementation_context`
and `informational_reference`, plus explicit authority and mutation settings.
Use the selected mode's actual format, not a new universal document-role schema.

## Set editing boundaries and choose a supported protection mechanism

Ask, when the answer cannot be inferred: **Which parts are settled decisions,
and which remain open to design changes?** Respect for operator intent is assumed.
This determines boundaries, not the editing mode. Exact text may be frozen;
other content may be rewritten while preserving meaning; approved areas may
permit broader changes. Preparation cannot invent permission to delete or weaken
requirements, or attest equivalence of unseen output.

| Mechanism | What it does | Operator consequence |
| --- | --- | --- |
| Preservation bridge | Checks proposed revisions against an approved exact-base surface and required preservation evidence before acceptance. | Mechanical evidence can suffice; semantic effects can require exact operator attestations. Local acceptance stops before another model call. |
| Verified promotion | Assembles a candidate from a structured proposal, runs deterministic checks and a separate semantic Verifier, and promotes only eligible candidates. | Routine semantic judgments can be supplied by the Verifier; product/authority choices still require appropriate decisions. |
| Ordinary editing | Runs the existing editing workflow without these explicit preservation mechanisms. | Do not describe it as enforced preservation or silently substitute it when protection was requested. |

The bridge and verified promotion cannot be combined in one job. Both govern
acceptance inside the run, independently of later source writes. Neither is
proof of arbitrary natural-language equivalence. Human review of the final result
is not equivalent to the bridge's per-proposal attestation. A configurable final
human semantic-review policy is future work, not a current mode selector.

For a supported new protected-editing job, consider verified promotion when the
operator prefers delegated semantic verification. Do not present it as a universal
runtime default or deprecate the bridge. Confirm availability in the executing
runtime and retain bridge routes for existing jobs and justified supported cases.

The checkout's [qualified verified release](VNEXT_VERIFIED_PROMOTION_RELEASE.md)
selects `standard`, `stateful_system`, local macOS/APFS storage and, for Phase 2,
the fixed `standard-v1` rubric. It supports horizontal/vertical Phase 1 and a
separately pinned focused route. MVP, exploratory, governance, custom workflows
and other profile sets are not currently admitted by that verified path.

If the user wants MVP with automated semantic verification, explain that this
combination is unavailable—not that MVP cannot preserve content. Offer only
validated alternatives: retain the desired review policy with a supported bridge
path and its attestation obligations, or explicitly reconsider the review policy.
Do not silently switch to standard, drop protection or claim the bridge supports
an unchecked combination. See [bridge activation](PRESERVATION_ACTIVATION.md)
and the [verified command/recovery matrix](OPERATOR_QUICKSTART.md#recommended-defaults).

## Scope intake directs the review

Use [Scope Notes Guide](SCOPE_NOTES_GUIDE.md) for purpose, expected headings,
compilation and examples. Scope notes identify this review's outcome, relevant
flows/surfaces, exclusions, depth and stopping condition. They are not a second
specification. Refer to existing definitions; do not invent APIs or failure
policies merely to fill scope fields. Unresolved in-scope design questions can be
left for the review when their answers are not needed to authorize the job.

## Recommend a schedule and bounded allowance

| Situation | Suggested schedule | Reason |
| --- | --- | --- |
| Broad, interacting concerns | Vertical | Lenses review the same draft before consolidated editing, allowing findings to be considered together. |
| A concrete dependency between review concerns | Horizontal | Earlier corrections improve the basis for later lenses. |
| An isolated known concern | Focused | Recheck one supported profile without claiming complete stabilization. |

Vertical is a useful starting recommendation, often for early specifications,
not a proven universal optimum or a runtime-default change. Horizontal does not
solve an unresolved product decision. Follow explicit user preferences and the
selected mode's supported routes.

Recommend the selected preset's bounded allowances, adjusted with a stated reason
for complexity or an authorized preference for more iteration. Do not routinely
ask the user to choose counts. Ask when proposed work conflicts with a cost/time
limit or requires authority beyond the existing allowance. No larger numeric
default is introduced by this guide.

Explain units accurately:

- A profile-review pass is a review by one profile.
- A vertical cycle collects eligible profile passes on one draft and may include
  one consolidated Editor operation. An all-clean cycle need not edit.
- Persisted `round-N` directories are evidence identifiers, not cycle counters.
  Separate profile passes and Editor operations can each receive round numbers.
- Verification closeout, retries and Verifier calls have their own semantics;
  review allowances are not total model-call or monetary limits.

In bridge vertical scheduling, exhausted profiles can be skipped while others
continue; skipped profiles do not become clean. Horizontal hard/soft exhaustion
policies differ: a soft sweep may end with residuals rather than stability.
Verified jobs use their bound allowance and continuation rules. Read the actual
selected mode's status and terminal evidence rather than infer behavior from the
schedule label. Phase 2 defaults do not grant Phase 2 spending authority when that
phase is excluded. Report actual model calls/usage only when measured; mark unknown
values instead of deriving them from round numbers.

## Resolve clients, models and execution settings

Show the actual Reviewer, Editor and, where applicable, Verifier client, model,
reasoning effort and timeouts in the staging summary. Reuse supported retained
settings or local preferences; explain meaningful deviations before launch.
Keep personal defaults outside portable documentation and skills.

Verify each client path rather than invent config keys. In this checkout the
legacy Codex helper fixes reasoning effort to `medium`; legacy role configuration
exposes the model but not an independent reasoning field. Verified client identity
and settings follow their own bound schemas. Do not promise that a personal
reasoning preference is honored without checking the selected adapter. Any needed
runtime option is separate implementation work.

Nested-client launch permission, authorization to send selected inputs, approval
of proposed effects and source-write approval are distinct. Name the actual input
scope and clients; reuse applicable existing authorization. Explain a missing
permission at the layer that requires it. The outer execution environment may
need permission for nested CLI session access even when the nested client is
read-only. Do not weaken client sandboxes or add blanket permissions to make a
job run. Approval automation is outside this guide's changes.

## Stage locally, validate, then hand off

The agent handles snapshots, inventories, mappings, schemas and exact hashes.
No model calls are needed merely to prepare the package. There is no universal
job-preparation CLI: use the selected mode's existing intake, builders and checks.

For the bridge, follow the exact inventory/surface procedure and canonical run
layout in the activation guide. For verified promotion, prepare the immutable
package and config outside a nonexistent destination; let admission create it.
Even an empty precreated destination is not the verified fresh-root procedure.
Never copy another run's authority files into a new job.

Validate supported configuration, references, exact bindings and required
approvals. For verified admission, use the documented `vnext-admit --dry-run`.
For bridge preparation, use the published validators; there is no invented
bridge activation flag. Inspect the actual saved artifacts, including compiled
scope, rather than trust a separate prose summary. Local validation establishes
consistency, not future model success or proof of complete semantic coverage.

Hand off a short summary:

- **Purpose and outcome:** what this job should resolve and where it stops.
- **Inputs and boundaries:** selected sources/context, settled commitments and
  permitted edits, with material unresolved choices.
- **Execution:** selected runtime, workflow, profiles, mode, clients/models and
  effective settings, schedule and allowances.
- **Readiness:** validations completed, missing requirements, applicable authority
  and next permitted action.

A package can be prepared but unapproved, or authorized but technically ineligible.
These are reporting distinctions, not new persisted Whetstone state names.
Launch only when both are satisfied; do not add a duplicate confirmation when
launch has already been authorized within that scope.

## Monitor evidence and make decisions concrete

Use the selected runtime's `status` first. Report what is happening, the current
accepted draft and operation, remaining allowance where recorded, whether a
choice is needed, and the supported next action. A persisted active record is not
proof of a live process. Without direct process evidence say liveness is unknown.
Missing output during an active operation may be expected; missing committed
evidence may indicate a problem. Neither assumption justifies automatic repair.

An operating agent can give a concise summary over existing diagnostics; this
guide does not claim the status implementation has been changed. Updates should
focus on meaningful changes unless the operator requests periodic heartbeats.
Keep technical artifacts available without narrating every poll.

For a required preservation decision, present the exact before/after content,
affected source sections, semantic effect, reason and requested decision. Use
existing commands to generate correspondence and bindings. Do not invent an
attestation, carry it onto changed content or treat launch permission as approval
of unseen edits. Bridge acceptance is local and does not itself continue the
scheduler; each subsequent edit requires a valid current-base surface. Reuse
actual authority within scope, never silently rebase evidence.

For verified jobs, follow the gate and candidate references from status. Rejected
or uncertain candidates do not become accepted merely because an agent prefers
them. Use only supported continuation/recovery; generic repair or Phase 2 resume
must not be inferred. In verified mode, draft and run-state projections do not
replace the committed pointer and evidence as authority.

At completion, explain the actual outcome, residual issues, accepted draft,
usage where measured, and next permitted action. A focused pass, audit verdict,
Phase 1 stability and Phase 2 convergence are different claims. Source apply-back
remains separately assessed and authorized.

## Further guidance

- [Worked preparation examples](OPERATOR_EXAMPLES.md)
- [Advanced commands and recovery](OPERATOR_QUICKSTART.md)
- [Scope intake](SCOPE_NOTES_GUIDE.md)
- [Portable agent skill and installation](../skills/README.md)
- [Future design ideas, not available features](../notes/future-improvements.md)
