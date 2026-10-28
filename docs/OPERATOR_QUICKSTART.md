# Whetstone Operator Quickstart

This guide is for running Whetstone against an existing spec document, especially a spec that lives in another repo.

Use an isolated run root and inspect the results before separately approving source apply-back. For legacy/bridge workflows, copy the source spec into the run directory as `spec.md`. For V, prepare the seed in an external input package and let fresh-root admission create the destination as described below.

## Mental Model

Whetstone has two live phases:

- Phase 1: technical stabilization across structural integrity, determinism, and operability profiles.
- Phase 2: convergence review against a selected rubric workflow.

Whetstone persists every round under `rounds/`. For legacy/bridge runs, `rounds/run_state.json` records scheduler state. For V, run-state and `spec.md` are projections of committed evidence and current verified authority. Humans should read `status --format text` for the applicable gate rather than treating a projection as independent authority.

## Recommended Defaults

### Verified-promotion command surface (explicit opt-in)

Whetstone 0.2.0 V support is explicitly opted in per job using `vnext-verified-consumer-1`,
manifest digest `7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58`.
It requires the qualified local macOS/APFS runtime and the scope below. Hashes in
the example are placeholders for exact prepared input bytes.

```yaml
editing_mode: verified_promotion
contract_suite_version: vnext-verified-consumer-1
vnext_input_package:
  path: inputs/package.json
  hash: <SHA-256-of-exact-package-bytes>
# Add only after admission and staging Phase 2 inputs in the admitted root.
# Required for Phase 2; paths are root-relative.
vnext_phase2_configuration:
  path: inputs/phase2/configuration.json
  hash: <SHA-256-of-exact-configuration-bytes>
```

Prepare the immutable input package locally from the explicit seed, review,
authority, invariants and approved scope. Its descriptor must agree with the
config mode/suite. This setup requirement is not permission to infer missing
approvals. Use `vnext-admit --root NEW_ROOT --config /absolute/run.yaml --dry-run`
to validate without creating the root; omit `--dry-run` for explicit fresh-root
initialization. Keep the launch config/package outside the nonexistent destination.
Subsequent commands use the admitted root and the same config selection, or
retained inputs where their documented read-only/recovery gate permits it.

For V, `spec.md` and run-state projections are derived views; current verified
pointer plus committed evidence own draft authority. Inspect `status --format
text` for the actual gate. Choosing V does not approve external source writes.
Never use legacy source-mismatch/non-converged overrides or supplied-draft flags
on a V root. Removing config selectors must not route it to a legacy writer.

The command matrix below is the complete supported first-release surface. Existing
legacy/bridge/reviewer-only/proposal interfaces retain their own semantics.

For the new Q1 consuming suite, the Phase 2 Reviewer supplies guidance directly
with each review. Whetstone validates and binds it automatically before admitting
routine corrections. Humans supply product or authority decisions when requested;
there is no routine advice-file handoff at entry or between rounds. Interrupted
advice publication uses the recovery-only row below. Older suites keep their
existing explicit-advice contract.

| Command | Supported scope | Behavior / boundary | Existing owner or required adapter |
| --- | --- | --- | --- |
| vnext-admit | New V root; --dry-run is read-only | Validate config/package/suite; initialize only a nonexistent destination; no clients | V bootstrap adapter + D8 initializer |
| live-phase1 | Standard horizontal or vertical; new or existing V root | Run bounded verified review/correction gates; stop at Phase 1 terminal/decision/failure; no source apply | review_next/admit_reviewed_round/request/register/verify/promote/finish_phase1 |
| live-focused-phase1 | One profile selected in immutable focused review config | CLI --profile/explicit --budget must match pins; omitted CLI defaults cannot override pins; focused clean never grants Phase 2 | focused review owner + Phase 1 verified owners |
| promote-phase2 | Complete Phase 1; bound Phase 2 configuration | Run required verified metadata transition and distinct entry commit only; no ordinary Phase 2 reviews | bind_phase2_entry/prepare_phase2_version/verify/promote/enter_phase2 |
| live-phase2 | Entered or eligible standard/fixed-rubric V job | Use shared entry owner, then existing bounded sequence through declaration/convergence or blocker | phase2_sequence_status/continue_phase2_pass/phase2 correction and closeout owners |
| status | Any inspectable V root | Read-only current authority/candidate/failure/decision and exact next gate; malformed authority reports invalid | inspect/phase1_status/phase2_state/operator/failure/apply status |
| resume | Existing V root; --dry-run is read-only | Only the exact recovery/continuation subtable below; plain resume stops at its selected boundary; --continue is Phase 1 only | materialization and role-specific recovery/continuation; extend_phase1_budget |
| vnext-decisions | Bound Phase 1 or Phase 2 operator context | Inspect; with mutually exclusive explicit `--options FILE` prepare exact requests, or use `--advice FILE` for an exact advice replay (new-suite advice is derived automatically from the Reviewer and cannot be overridden); `--dry-run` writes nothing; no clients | operator_status / phase2_operator_context / request or advice preparation |
| vnext-decide | One exact operator input | Existing --selections; proposed alternatives --repair-request or --gap-acceptance for Phase 2; exactly one input, no clients | response/selection owners; admit_phase2_repair / accept_phase2_gaps |
| vnext-semantic-answers | Explicit --candidate | Read-only original question and retained answers; no implicit latest selection | answers |
| vnext-semantic-answer | Explicit --candidate and --input | Record exact answer; --dry-run read-only; no candidate reopening or client | submit_answer |
| vnext-semantic-followup | Explicit candidate and receipt/hash | Admit exact new child transaction; no client or automatic promotion | select_followup |
| strop / apply-back | V inspection or retained-intent recovery; new writes require complete current eligibility | Separate assessment/status, apply/retry and historical recovery as defined below; recovery never rewrites | review_apply_back/apply_back/recover_apply_back |
| Other commands on a V root | Not in the declared matrix | Refuse unsupported gate before client/writer; standalone audits/intake/decomposition use their own roots | existing protocol preflight refusal |

The following V-only operands share the exact qualified-suite gate:
`vnext-decide --repair-request FILE` and `--gap-acceptance FILE` replace
`--selections` for their one exact request type; `strop`/`apply-back` add
`--config`, `--approval FILE`, `--approval-hash HASH`, `--exclusive-source-access`,
`--recover`, and `--retry-apply`. These are operation inputs, not mode selectors.


#### Operating a qualified V release

Current release status and evidence are in the
[verified-promotion release decision](VNEXT_VERIFIED_PROMOTION_RELEASE.md).
As of 2026-10-28, the exact suite above is publicly qualified for explicit opt-in.
Test harness qualification is not a user setting. There is no configuration, environment variable or CLI switch that can
qualify an implementation.

**Start a new job.** Have the agent prepare a canonical immutable package from
the exact seed, authority, protected invariants, approved scope and review/client
configuration. Copy only the selected source text into the new package; do not
copy an existing run's authority files. Keep the package and launch configuration
outside the destination, which must not exist, including as an empty directory.
Select `editing_mode: verified_promotion` and the advertised exact suite in the
run configuration. The package descriptor must select the same mode and suite.

Validate and admit using the selected runtime's `whetstone` command:

```sh
whetstone vnext-admit --root /absolute/new-run --config /absolute/run.yaml --dry-run
whetstone vnext-admit --root /absolute/new-run --config /absolute/run.yaml
whetstone status --root /absolute/new-run --config /absolute/run.yaml --format json
whetstone live-phase1 --root /absolute/new-run --config /absolute/run.yaml
```

Use only a release that advertises the chosen suite and D8 storage support.
Unknown, altered or unqualified suites refuse before model calls or authority
writes. A package that validates offline is not permission to run V. A partial
initialization is retained for diagnosis; do not overwrite or force-reinitialize
that destination. Prepare a genuinely new job if initialization cannot complete
through its documented owner.

**Keep inputs immutable.** After admission, retained mode, suite, role identities,
seed, authority, invariants and review configuration own the job. Changed bytes
or conflicting selectors refuse. A changed descriptor-bound selection needs a
new job; editing the launch config cannot upgrade a legacy/R/P root or change an
existing V job. Preserve the actual client executable/version recorded by the
job. If an app upgrade replaces it, restore the exact retained client or prepare
a new job with the new identity. Operational timeout changes retain the existing
per-attempt rules; they do not renew authority or spent request slots.

**Enter Phase 2 after full Phase 1 stability.** Prepare its exact job-bound v3
configuration and supported rubric under `inputs/phase2/`, then add the
root-relative `vnext_phase2_configuration` Ref to the launch config. Do this after
admission: a fresh nonexistent root cannot resolve a Phase 2 input path yet.
Focused-profile stability does not establish complete Phase 1 prerequisites.

```sh
whetstone promote-phase2 --root /absolute/new-run --config /absolute/run.yaml
whetstone live-phase2 --root /absolute/new-run --config /absolute/run.yaml
whetstone status --root /absolute/new-run --config /absolute/run.yaml --format json
```

Configuration/request publication and distinct entry are separate commits. Any
required metadata change must pass the verified candidate path before entry.
Read the reported gate and bound terminal evidence; a returned response or zero
finding count alone is not convergence. Top-level legacy fields in a V state
projection may retain earlier values; its V references and `status` resolve the
current committed entry/closeout. Reviewer advice is handed to the owners
automatically. Bring new product or authority choices to the human with their
exact base/effects; history supplies context, not permission for a new edit.

**Inspect before recovery.** Run `status`, then the exact supported `resume
--dry-run` invocation it reports, including a required round selector. Use the
table below to distinguish publication repair from a client continuation. Review
the possible client use and remaining allowance before executing it. Repair
stops at its boundary; spent requests and final candidate rejections cannot be
reopened through ordinary live commands. No generic Phase 2 Editor/Verifier
crash recovery or force-unlock is supplied. Preserve uncertain publication
evidence and reconcile it through the selected owner before new work.

**Pause future automatic work.** Stop the external launcher/scheduler from
starting new Whetstone jobs, disable its queued automatic invocations, and leave
new jobs unadmitted. For assessment while paused, use the existing reviewer-only
audit workflow in a separate root. Keep the qualified runtime, existing launch
configs, descriptors and historical evidence intact for inspection and supported
recovery. Do not edit an active descriptor to another mode, delete its lock file,
or remove config selectors to obtain a legacy writer. Whetstone has no global
pause switch or built-in run-wide token/time controller; limits and scheduling
belong to the caller. A 30-minute Q4 harness cap is not a product default.

For an active invocation, prefer its normal bounded stop. If it is interrupted,
inspect durable status before any further dispatch; cancellation is not proof
that a write or provider call did not occur. Avoid a second mutating invocation
on the same root. D8 requires one canonical physical root on local macOS/APFS;
copied archives permit offline inspection, not relocation or executable resume.
Distributed writers, other storage backends and physical power-loss behavior
are not qualified by the retained tests.

**Approve source writes separately.** A converged root is not apply-back consent.
Use the existing strop/apply-back assessment, exact approval and exclusive source
access procedure below. The qualification runs supply no authority to write a
real external specification. Live transmission also needs its own approved input
scope and caller budget; activating V does not provide blanket provider consent.

#### Exact V recovery and continuation routes

This table is the complete supported V `resume` surface. It does not change the
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
| Phase 2 advice attachment retained without its binding | `resume`; select the exact consumed pass and request | First/later advice owner reconstructs only the exact Reviewer-derived attachment and binding; no clients | Stop after attachment repair, before correction admission, Editor, Verifier or next review. |
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

#### Source assessment, write and historical recovery

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

The declared initial matrix is standard workflow, stateful-system profiles and
fixed standard-v1 rubric. Horizontal Phase 2 targets cover mid/final ×
permissive/strict; vertical is final/strict until other combinations are qualified.
Focused routes never enter Phase 2. Supported numeric metadata and unversioned
routes retain M3 rules. Other workflow/profile/rubric/target combinations refuse;
no custom/MVP/governance, distributed writer or generic freeze-resume support is
inferred. Publication of this matrix is not proof of its implementation.

### Preservation Capability Notice

The qualified `preservation-bridge-v1` capability is available by explicit opt-in in a fresh isolated run root. Add the published `preservation_bridge` block with `mode: enforce`, the capability version and an exact Ref to an approved bounded change surface. Then invoke the normal Phase 1 command. Omission keeps `legacy_unguarded` behavior; scope instructions alone do not enforce preservation.

See [preservation activation](PRESERVATION_ACTIVATION.md) for complete setup, configuration, agent instructions and continuation. A useful request is: **“Run Whetstone on this spec with preservation enforcement; allow clarifications in the retry section, freeze the other sections, and bring exact-effect approvals back to me.”** The agent prepares the concrete boundary and artifacts, and records approvals within their authorized scope. No preservation flag or vNext mode is needed.

The workflow is:

1. Inventory the exact authoritative base and approve the scope, findings and allowed/frozen proposal surface.
2. Generate an isolated proposal and inspect its raw/materialized diff, preservation assessment and outstanding evidence needs. This cannot change the authoritative draft.
3. Review grouped exact effects and explicitly adopt the required correspondence and semantic attestations. Whetstone prepares the IDs and hashes; approval must not require manually constructing evidence JSON.
4. Submit the retained proposal through the local acceptance request operation. It revalidates identical bytes, invokes no Editor, commits only after all gates pass, and completes the pending round once.
5. Re-review accepted changes under the ordinary profile/stability rules before Phase 2 or source apply-back.

Missing effect evidence maps to `PAUSED_DECISION`; known hard violations reject. `preservation-review`, `preservation-attest`, `preservation-request`, and `preservation-accept --dry-run` work with enforced runtime roots and standalone Phase 1 proposals. See the [acceptance guide](PRESERVATION_ACCEPTANCE_DEVELOPER.md) for syntax. Supported runtime paths include Phase 2 entry maintenance, inherited no-ops, guarded Phase 2 rounds, explicit Phase 1 budget extensions and bounded Phase 2 `closeout-existing`. The [qualification record](PRESERVATION_QUALIFICATION.md) covers operator adoption, recovery, exact-byte apply-back and convergence verification.

New authorization may create a new immutable acceptance attempt in the same run root while the exact proposal base remains current. Earlier reports remain intact. Changed content or base requires a new proposal; a pending/rejected draft is never silently chosen as the next base. Technical resume retains frozen inputs and cannot substitute for approval. Generic Phase 2 timeout resume remains unsupported; explicit local acceptance of retained output is a separate operation. A fresh root remains appropriate for a separate job or incompatible capability, not routine approval of a clarification.

### Normal Sharpening

Use these defaults for normal spec sharpening:

- workflow: `standard`
- reviewer: Codex `gpt-5.5`
- editor: Codex `gpt-5.5`
- source mutation: manual apply-back only
- decision mode: `end_of_cycle`
- profile budgets: start generous, then tune after observing run shape
- budget exhaustion policy: `hard` for strict gating, `soft` for full Phase 1 diagnostic sweeps
- timeout posture: reviewer shorter, editor longer

Use `mvp` when you want first-useful-build readiness. Use `governance` only when you want the heavy convergence gate. Use `custom` only when you have a named custom rubric and want the run artifacts to make that rubric identity explicit.

MVP runs require an approved scope contract. This is deliberate: MVP review needs a clear first-useful-build boundary or Whetstone will expand the surface area it discovers.

## Inputs

Choose:

- source spec path
- run root
- workflow

Example:

```bash
SOURCE_SPEC="/Users/cwattles/Desktop/Agent-Workspace/repos/personal/cortext1/foreman/docs/MY_SPEC.md"
RUN_ROOT="/Users/cwattles/Desktop/Agent-Workspace/repos/personal/cortext1/whetstone/rounds/foreman-my-spec-standard-001"
WORKFLOW="standard"
```

## Create An Isolated Run

For a config-selected V job, use the qualification-gated V command matrix
under Recommended Defaults. The following legacy/bridge examples do not grant
V initialization, generic resume, source-mismatch override or unbound apply
approval. In particular, prepare V inputs outside its nonexistent destination;
V source writes require the exact assessment/hash and exclusive-access
acknowledgement, and recovery-only calls never initiate another write.

```bash
mkdir -p "$RUN_ROOT"
cp "$SOURCE_SPEC" "$RUN_ROOT/spec.md"
printf '# History\n' > "$RUN_ROOT/spec.history.md"
```

Create `orchestrator_config.yaml` in the run root:

```bash
cat > "$RUN_ROOT/orchestrator_config.yaml" <<'YAML'
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
declaration_path: ./convergence_declaration.md
workflow: standard

clients:
  reviewer:
    name: codex
    command: codex
    version: "0.128.0"
    model: gpt-5.5
  editor:
    name: codex
    command: codex
    version: "0.128.0"
    model: gpt-5.5

review:
  mode: horizontal
  profile_set: stateful_system
  budget_exhaustion_policy: hard
  profile_budgets:
    structural_integrity: 10
    determinism: 10
    operability: 10

convergence:
  enabled: true
  target_phase: final
  target_mode: strict
  rubric_profile: standard-v1
  rubric_source: builtin
  profile_budgets:
    convergence_strict_check: 10
    adversarial: 10

decision_points:
  enabled: true
  mode: end_of_cycle
  intervention_thresholds:
    severities: [blocker, major]
    trigger_on_requirement_strength_change: true
    trigger_on_authority_boundary_change: true
    trigger_on_scope_change: true
    trigger_on_new_enum_or_error_code: true

timeouts:
  reviewer_seconds: 360
  editor_seconds: 900

scope_contract:
  path: ./rounds/intake/scope_contract.json

# Optional but strongly recommended when leaf specs depend on an HLD,
# architecture note, policy document, or domain contract.
reference_context:
  files:
    architecture_hld:
      path: /absolute/path/to/docs/hld-architecture.md
      role: architecture_authority
      required: true
YAML
```

## Running Whetstone From An Agent

Live Whetstone runs often spawn a second CLI process, such as `codex exec`, from inside the agent that is driving the job. That is a nested-client run. The outer agent sandbox can block the inner Codex CLI from reading its own session files under `~/.codex/sessions`, even when the inner Codex invocation is configured with its own read-only sandbox.

For live runs that invoke Codex or Claude Code clients, tell the driving agent to request the necessary execution approval before running `live-phase1`, `live-phase2`, `live-focused-phase1`, `reviewer-smoke`, or `editor-smoke`. Do not make a first sandboxed attempt "just to see." A sandbox-denied nested client commonly halts as `HALTED_ARTIFACT_INVALID`, is often non-resumable, and wastes a run root without producing semantic signal.

Copy/paste operator instruction:

```text
This Whetstone job invokes nested live clients. Run the Whetstone live command with the approval/escalation needed for Codex/Claude CLI session access. Keep the Whetstone run root isolated, keep client sandbox settings as configured, and do not first attempt a sandboxed live run that is expected to fail on ~/.codex/sessions access. If the only failure is nested CLI session access, treat it as infrastructure setup, not spec feedback or a resumable Whetstone result.
```

For MVP review, change:

```yaml
workflow: mvp
review:
  profile_set: utility_mvp
  profile_budgets:
    buildability: 4
    consistency: 4
    determinism_light: 4
    operability_light: 3
convergence:
  target_phase: mid
  target_mode: strict
  rubric_profile: mvp-v1
  profile_budgets:
    mvp_readiness_check: 4
    scope_guard: 3
```

Then create and approve a scope contract before running Phase 1.

For governance review, use:

```yaml
workflow: governance
convergence:
  target_phase: final
  target_mode: strict
  rubric_profile: governance-v6
```

## Review Mode

Use `horizontal` for the original careful profile-by-profile loop:

```yaml
review:
  mode: horizontal
```

Use `vertical` when you want fewer Editor turns. In vertical mode, Whetstone runs independent structural, determinism, and operability Reviewer passes over the same draft, merges the feedback, then asks the Editor for one consolidated revision:

```yaml
review:
  mode: vertical
```

Vertical mode is usually the better economy choice for MVP and medium-size specs. It preserves separate Reviewer artifacts per profile, but the Editor sees the full cross-profile problem set before changing the draft.

Profile budgets are per-profile, not total-run round limits. In vertical mode, a budget of `10` with three Phase 1 profiles allows up to ten independent Reviewer passes for each profile, plus consolidated Editor rounds between review cycles and any bounded closeout passes. This can multiply into many absolute `round-N/` directories. Use lower per-profile budgets or lighter profile sets when you want a short diagnostic run.

Round folders identify their shape in `profile_used.yaml` with `round_kind`. In vertical runs, profile rounds use `review_only`; the merged Editor round uses `consolidated_editor`.

## Diagnostic Sweep

Use `diagnostic-sweep` when you want to understand the shape of a new or expensive spec before letting the Editor mutate it:

```bash
PYTHONPATH=src python3 -m whetstone.cli diagnostic-sweep \
  --root "$RUN_ROOT" \
  --reviewer-timeout-seconds 420
```

The command runs one Reviewer-only pass for each configured Phase 1 profile against the same current `spec.md`. It does not invoke the Editor, does not mutate `spec.md`, does not mark Phase 1 stable, and does not authorize Phase 2.

Read:

- `rounds/profile_sweep_report.md`
- `rounds/profile_sweep_report.json`
- each `rounds/round-N/reviewer_feedback.json`

Use the recommendation as job-design input:

- `start_phase_1`: run normal Phase 1.
- `run_bounded_synthesis`: do a bounded synthesis pass before normal Phase 1.
- `run_vertical_phase_1`: vertical Phase 1 is likely a reasonable next run shape.
- `manual_scope_review`: revisit the scope contract, reference authority set, or job design before mutation.

In-scope contract authority gaps, such as identity ownership or response authority, usually mean `run_bounded_synthesis`. Reserve `manual_scope_review` for cases where the run boundary itself looks wrong.

If a run ends immediately after an Editor mutation, Whetstone may report the draft as accepted but still unverified. That means the edit resolved the known blocker/major feedback, but the revised draft still needs another clean profile-review cycle before Phase 2.

When this happens at the end of the budget, Whetstone can run a verification-only closeout pass. It calls Reviewers only, does not mutate the draft, and either marks Phase 1 stable or stops with the remaining blocker/major verification debt.

## Profile Set

Use `profile_set` to choose the review lenses and default per-profile budgets before changing individual budgets:

```yaml
review:
  profile_set: stateful_system
```

Each profile set defines profile budgets per profile. For example, a stateful-system Phase 1 stack with structural, determinism, and operability budgets of `10` can consume far more than ten total rounds because each profile receives its own budget.

Available profile sets:

- `stateful_system`: default, high-assurance review for stateful/artifact/replay-heavy systems.
- `balanced_mvp`: same review lenses as `stateful_system`, with lower budgets.
- `utility_mvp`: lighter lenses for small CLIs, utilities, and MVP tools where Whetstone should avoid turning the spec into a metropolis.
- `governance`: strongest pressure, including adversarial Phase 1 review.

For Foreman-like specs, start with `stateful_system`. For Parley-like utility specs, start with `utility_mvp` plus a clear MVP scope contract.

## Spec Decomposition

Use decomposition when a source spec has become too large or owns several separable authority surfaces. Decomposition is not a review run and does not rewrite requirements. It is a copy-first provenance workflow for splitting one source spec into a governed spec family.

Good decomposition candidates include:

- a source spec with several independent subsystems, workflows, artifact families, or protocol surfaces
- a spec where operators keep asking, "which part owns this?"
- a spec that is hard to review because unrelated decisions are packed into one document
- a monolith that should become a coordinating spec plus leaf specs

The lifecycle is:

1. `plan`: inventory the source and propose or validate target ownership.
2. `approve`: bind operator approval to the exact source hash and plan hash.
3. `extract`: write target specs by lossless copy-first extraction.
4. `audit`: verify coverage, target hashes, provenance headers, unmapped units, and duplicated authority.
5. `promote`: mark the audited decomposed family authoritative.

If you do not already have a decomposition map, start with inventory mode:

```bash
PYTHONPATH=src python3 -m whetstone.cli decompose plan \
  --source spec.md \
  --output-dir docs/decomposition/inventory
```

This writes `decomposition_map_template.json` with the current source hash, valid enum values, and the exact extractable units an agent or operator can assign. Copy that template to a map path, fill `target_specs`, then run a mapped plan to validate it.

For a mapped decomposition:

```bash
PYTHONPATH=src python3 -m whetstone.cli decompose plan \
  --source spec.md \
  --map docs/decomposition/whetstone-decomposition-map.json \
  --output-dir docs/decomposition

PYTHONPATH=src python3 -m whetstone.cli decompose approve \
  --plan docs/decomposition/decomposition_plan.json \
  --source spec.md \
  --approved-by "$USER"

PYTHONPATH=src python3 -m whetstone.cli decompose extract \
  --plan docs/decomposition/decomposition_plan.json \
  --source spec.md \
  --output-dir .

PYTHONPATH=src python3 -m whetstone.cli decompose audit \
  --manifest docs/decomposition/decomposition_manifest.json \
  --source spec.md

PYTHONPATH=src python3 -m whetstone.cli decompose promote \
  --manifest docs/decomposition/decomposition_manifest.json \
  --accepted-by "$USER"
```

After extraction, inspect:

- `docs/decomposition/decomposition_plan.md`
- `docs/decomposition/coverage_matrix.md`
- `docs/decomposition/decomposition_manifest.json`
- generated target specs

Promotion means the decomposed family is authoritative for future spec work. It does not mean the target specs have converged, and it does not delete or rewrite the original source spec.

After promotion, use the coordinating spec as the entry point and make future changes in the relevant leaf spec. Keep the decomposition manifest as the provenance record.

## Budget Exhaustion Policy

Use the default `hard` policy when you want Phase 1 to stop as soon as a required profile cannot reach clean verification within its budget:

```yaml
review:
  budget_exhaustion_policy: hard
```

Use `soft` when you want a diagnostic sweep across all Phase 1 profiles before stopping:

```yaml
review:
  budget_exhaustion_policy: soft
```

Soft mode does not mean "good enough." It lets Whetstone advance past exhausted or oscillating Phase 1 profiles, records a per-profile residual status, and then halts with `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS` if Phase 1 is not genuinely stable. Phase 2 is still blocked until status reports `PHASE_1_STABLE`.

## Scope Intake For MVP

Create a starter notes file:

```bash
PYTHONPATH=src python3 -m whetstone.cli intake \
  --root "$RUN_ROOT" \
  --template mvp \
  --output "$RUN_ROOT/scope-notes.md"
```

Edit `scope-notes.md` to define:

- the one core outcome for the run
- in-scope surfaces
- deferred or out-of-scope surfaces
- required depth for validation, schema, report, failure, and operational behavior
- what counts as good enough

See [Scope Notes Guide](SCOPE_NOTES_GUIDE.md) for examples and depth-level guidance.

Generate an approved scope contract:

```bash
PYTHONPATH=src python3 -m whetstone.cli intake \
  --root "$RUN_ROOT" \
  --from-notes "$RUN_ROOT/scope-notes.md" \
  --approve
```

This writes:

```text
$RUN_ROOT/rounds/intake/scope_contract.json
```

Without `--approve`, Whetstone writes a draft scope contract. Draft scope contracts are useful for review, but they do not satisfy MVP preflight.

## Run Phase 1

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase1 \
  --root "$RUN_ROOT"
```

Optional timeout overrides:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase1 \
  --root "$RUN_ROOT" \
  --reviewer-timeout-seconds 360 \
  --editor-timeout-seconds 1200
```

Check status:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

Proceed to Phase 2 only when status says:

```text
terminal_state: PHASE_1_STABLE
next_action: run_live_phase2
```

If status says:

```text
terminal_state: PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS
next_action: manual_review_required
```

read `rounds/technical_failure_report.json`. The run completed a soft Phase 1 diagnostic sweep, but at least one profile still has residual blocker/major or oscillation status. Do not proceed to Phase 2 from this state.

## Run A Lightweight Change Audit

For the separate vNext reviewer-only workflow, see [vNext admission](VNEXT_ADMISSION.md). It uses an immutable descriptor and explicit selectors on `vnext-admit` or `live-phase1`; schema recognition alone does not activate a mode. The historical 18.3 checkpoint did not activate proposal or promotion modes. Current V support is advertised above; the preservation-bridge workflow remains separate.

Use `audit-change` when a small feature or boundary update touched multiple specs and you want a reviewer-only sanity check without starting a Whetstone convergence loop.

Create an audit notes file with the intended contract:

```markdown
# Change Intent

# Expected Boundary

# Specs To Check

# Out Of Scope
```

Then run:

```bash
PYTHONPATH=src python3 -m whetstone.cli audit-change \
  --root "$AUDIT_ROOT" \
  --notes audit-notes.md \
  --spec docs/POLICY_SPEC.md \
  --spec docs/EVIDENCE_LIFECYCLE_SPEC.md \
  --profile consistency
```

This writes:

```text
$AUDIT_ROOT/change_audit/audit_brief.md
$AUDIT_ROOT/change_audit/audit_manifest.json
$AUDIT_ROOT/change_audit/change_audit_feedback.json
$AUDIT_ROOT/change_audit/change_audit_report.md
```

The source specs are not mutated. Treat `pass` and `pass_with_minor_clarification` as low-friction review outcomes. Treat `needs_revision` or `blocked` as a signal to patch manually or run a focused Whetstone job.

## Run A Focused Profile Recheck

Use a focused Phase 1 profile run when a prior run leaves one profile uncertain and you want normal Whetstone artifacts for a targeted recheck.

Create a new isolated comparison run root, seed it with the latest valid draft from the prior run, copy or recreate the config and scope contract, then run:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-focused-phase1 \
  --root "$FOCUSED_RUN_ROOT" \
  --profile structural_integrity \
  --budget 3
```

Focused profile runs write ordinary round artifacts and `rounds/run_state.json`. A clean focused run ends with:

```text
terminal_state: FOCUSED_PROFILE_STABLE
ready_for_phase_2: false
```

That state means the selected profile is clean for the focused draft. It does not replace a full Phase 1 stable run and does not by itself authorize Phase 2.

## Recover A Timeout

For a config-selected V job, use the qualification-gated V command matrix
under Recommended Defaults. The following legacy/bridge examples do not grant
V initialization, generic resume, source-mismatch override or unbound apply
approval. In particular, prepare V inputs outside its nonexistent destination;
V source writes require the exact assessment/hash and exclusive-access
acknowledgement, and recovery-only calls never initiate another write.

If status says:

```text
terminal_state: HALTED_CLIENT_TIMEOUT
next_action: resume_or_increase_timeout
```

read the resume commands printed by status:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

First validate the recovery plan without invoking the Editor:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --dry-run \
  --continue
```

If the dry-run is resumable, continue the run:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --continue
```

Use a larger Editor timeout when the previous call timed out deep into a large draft:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --editor-timeout-seconds 1800 \
  --continue
```

If status says Phase 1 ended with `TARGET_NOT_REACHED` or `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS` because profile budgets were exhausted, you can append rounds to the same run root instead of overwriting it:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --extend-review-budget 3 \
  --dry-run
```

If the dry-run is resumable, run the same command without `--dry-run`:

```bash
PYTHONPATH=src python3 -m whetstone.cli resume \
  --root "$RUN_ROOT" \
  --extend-review-budget 3
```

Budget-extension resume appends new `round-N/` directories, preserves prior artifacts, and records the extension in `rounds/run_state.json` under `budget_extensions`. In horizontal mode it appends profile rounds. In vertical mode it appends additional vertical review cycles: profile review passes over the same draft, followed by one consolidated Editor revision when feedback remains.

Current resume support is intentionally narrow. It supports Phase 1 Reviewer timeouts, Phase 1 Editor timeouts after validated Reviewer feedback, Phase 1 Editor artifact-validation failures after validated Reviewer feedback, and explicit Phase 1 budget-extension continuation. It does not resume Reviewer artifact-validation failures, arbitrary malformed run roots, Phase 2 timeouts, source hash mismatches, or manually edited run drafts.

## Run Phase 2

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 \
  --root "$RUN_ROOT" \
  --workflow "$WORKFLOW"
```

You can override the built-in rubric profile at runtime:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 \
  --root "$RUN_ROOT" \
  --workflow mvp \
  --rubric mvp-v1
```

For custom rubrics, provide a path and label:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 \
  --root "$RUN_ROOT" \
  --workflow custom \
  --rubric /absolute/path/to/domain-rubric.md \
  --rubric-label "payments-certification-v1"
```

Check status again:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

Successful convergence looks like:

```text
terminal_state: CONVERGED
next_action: review_or_apply_back
apply_back: available=true
```

If a late Phase 2 edit makes an earlier clean profile stale, Whetstone may run a bounded reviewer-only closeout pass before converging. Closeout rounds are marked `round_kind: review_only`, do not call the Editor, and do not mutate `spec.md`; they exist only to verify the current draft hash across the remaining required Phase 2 profiles.

If an older run already stopped in Phase 2 as `TARGET_NOT_REACHED` with zero unresolved blockers, majors, and rubric gaps, use the explicit closeout path instead of starting a fresh Phase 2 loop:

```bash
PYTHONPATH=src python3 -m whetstone.cli live-phase2 \
  --root "$RUN_ROOT" \
  --workflow "$WORKFLOW" \
  --closeout-existing
```

This appends reviewer-only closeout rounds in place, preserves earlier terminal reports, and writes `rounds/superseded_terminal_reports.json` when the closeout replaces an earlier failure state.

## Decision Summaries

Decision artifacts are useful when you do not want to read every round file.

Look first at:

```text
$RUN_ROOT/rounds/decision_summary.md
```

If a run halts for `PAUSED_DECISION`, inspect:

```text
$RUN_ROOT/rounds/decision_intervention_request.json
```

In normal `end_of_cycle` mode, decisions are surfaced for review after the run rather than interrupting every round.

For round-by-round owner-choice hints, inspect:

```text
$RUN_ROOT/rounds/round-N/operator_decision_checkpoint.json
```

These checkpoint artifacts are advisory in the current runtime. They frame likely policy, scope, validation, failure, or reporting choices, but they do not pause the run or change scheduler behavior.

For a compact run-level view, inspect:

```text
$RUN_ROOT/rounds/operator_decision_checkpoint_summary.md
```

This summary clusters checkpoint candidates and shows the top cards worth operator review.

## Context Pressure

If a run feels unusually slow, inspect the advisory context report before changing budgets or timeouts:

```text
$RUN_ROOT/rounds/context_pressure_report.md
```

`context_pressure_report.json` and `.md` measure the mutable draft, selected rubric, approved scope contract, and configured reference context files. They report byte counts, rough estimated tokens, large-component warnings, missing required context warnings, and reference-context count. This is observability only: Whetstone does not trim context, change scheduling, halt, or accept/reject a run because of this report.

For actual per-round prompt payloads, inspect:

```text
$RUN_ROOT/rounds/round-N/context_pressure_report.md
```

Per-round reports measure the concrete files written under `round-N/context/`. They also show `referenced_context` when Reviewer findings cite generated reference filenames such as `reference_ontology.md`. This helps identify which references are proving useful before introducing any future profile-aware context selection.

## Review Before Apply-Back

For a config-selected V job, use the qualification-gated V command matrix
under Recommended Defaults. The following legacy/bridge examples do not grant
V initialization, generic resume, source-mismatch override or unbound apply
approval. In particular, prepare V inputs outside its nonexistent destination;
V source writes require the exact assessment/hash and exclusive-access
acknowledgement, and recovery-only calls never initiate another write.

Before changing the source spec, inspect:

- `$RUN_ROOT/spec.md`
- `$RUN_ROOT/spec.history.md`
- `$RUN_ROOT/convergence_declaration.md`
- `$RUN_ROOT/rounds/decision_summary.md`
- `$RUN_ROOT/rounds/run_state.json`

Generate the strop/apply-back review without mutating the source:

```bash
PYTHONPATH=src python3 -m whetstone.cli strop \
  --source "$SOURCE_SPEC" \
  --run-root "$RUN_ROOT"
```

Read:

```text
$RUN_ROOT/rounds/apply_back_review.md
```

The dry-run should show that the run is eligible and the final draft hash matches `run_state.current_draft_hash`.

## Apply Back

For a config-selected V job, use the qualification-gated V command matrix
under Recommended Defaults. The following legacy/bridge examples do not grant
V initialization, generic resume, source-mismatch override or unbound apply
approval. In particular, prepare V inputs outside its nonexistent destination;
V source writes require the exact assessment/hash and exclusive-access
acknowledgement, and recovery-only calls never initiate another write.

Only after human review:

```bash
PYTHONPATH=src python3 -m whetstone.cli strop \
  --source "$SOURCE_SPEC" \
  --run-root "$RUN_ROOT" \
  --apply \
  --approve
```

`apply-back` remains supported as a legacy alias for `strop`.

Confirm:

```bash
PYTHONPATH=src python3 -m whetstone.cli status \
  --root "$RUN_ROOT" \
  --format text
```

Expected:

```text
apply_back: available=true, applied=True
```

## Artifact Reading Order

When something halts, read in this order:

1. `status --format text`
2. `rounds/run_state.json`
3. terminal report:
   - `rounds/technical_failure_report.json`
   - `rounds/convergence_failure_report.json`
   - `rounds/artifact_validation_error.json`
   - `rounds/oscillation_report.json`
   - `rounds/conflict_report.json`
4. latest `rounds/round-N/reviewer_feedback.json`
5. latest `rounds/round-N/editor_summary.json`
6. `rounds/decision_summary.md`
7. `rounds/operator_decision_checkpoint_summary.md`
7. `rounds/apply_back_review.md`, if apply-back has been dry-run

## Terminal States

- `PHASE_1_STABLE`: Phase 1 is ready for Phase 2.
- `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`: soft Phase 1 sweep finished, but residual profile issues remain; manual review required and Phase 2 is blocked.
- `CONVERGED`: Phase 2 passed; review and apply back.
- `TARGET_NOT_REACHED`: budget exhausted; read the phase failure report.
- `HALTED_CLIENT_TIMEOUT`: a client timed out; status may show resume commands.
- `HALTED_ARTIFACT_INVALID`: a client returned invalid structured output after retry.
- `HALTED_OSCILLATION`: iteration stopped because churn/cycle detection fired.
- `HALTED_CONFLICT`: conflict threshold halted the run.
- `PAUSED_DECISION`: operator decision required before continuing.
- `CONFIG_INVALID`: fix configuration before running.

## Safety Rules

- Keep one run root per source spec attempt. Use suffixes like `-001`, `-002`, `-003`.
- Do not edit the source spec during a Whetstone run.
- Do not manually edit `$RUN_ROOT/spec.md` after a run starts unless you intend to invalidate resume/hash assumptions.
- Do not use `--allow-source-hash-mismatch` unless intentionally overriding a changed source file.
- Do not use `--allow-non-converged` for normal operation.
- Do not auto-apply Whetstone results from an agent run. Run dry-run strop/apply-back first.
- Preserve failed run roots when diagnosing timeouts, oscillation, malformed output, or budget exhaustion.

## Troubleshooting

If status says the latest round is partial, read `missing_round_artifacts` and the terminal report.

If a run halts because the nested Codex CLI cannot access `~/.codex/sessions`, do not diagnose the spec and do not burn time probing generic resume. That failure happened before the model could perform a valid review/edit. Rerun from a clean isolated root, or overwrite only when you are certain no semantic round artifacts from the failed attempt should be preserved, using the required execution approval for nested client access.

If a client times out, use `status --format text`, then `resume --dry-run --continue`. Increase `--editor-timeout-seconds` if the Editor timed out while producing a large draft.

If a Phase 1 Editor artifact fails validation after a valid Reviewer handoff, `status --format text` may show a resumable Editor artifact-validation retry. In that case, use `resume --dry-run --continue`, then run the same command without `--dry-run` if the hash guard passes. Do not use this path for Reviewer artifact-validation failures or sandbox/session-access failures that occurred before semantic review.

If Phase 1 reaches `TARGET_NOT_REACHED`, check whether the latest failure report says issues remain unresolved or whether a profile simply never got a clean Reviewer verification.

If Phase 1 reaches `PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS`, check `profile_status.profiles[].residual_status` in `technical_failure_report.json` to see which profiles exhausted budget or hit oscillation during the soft sweep.

If Phase 2 converges suspiciously quickly or every run has the same shape, inspect profile budgets, profile status, and the latest Reviewer findings before trusting the run shape.

If `status --format text` reports `root_draft_matches_run_state: False` or a `root_draft_hash_mismatch` warning, treat `rounds/run_state.json.current_draft_hash` as the authoritative lineage hash. The run-root `spec.md` was changed outside the accepted round chain or after the last run-state update. Restore from the latest accepted `round-N/draft_after.md`, start a fresh seeded run, or perform an explicit operator-approved reconciliation before resuming, promoting to Phase 2, or applying back.

If strop/apply-back refuses to write, read `apply_back_review.json`; common causes are non-converged terminal state, source hash mismatch, final draft hash mismatch against `run_state.current_draft_hash`, or final-draft text hygiene failures.

If the source repo diff is empty after apply-back, check whether the file is tracked:

```bash
git -C /path/to/source-repo status --short
git -C /path/to/source-repo ls-files -- docs/MY_SPEC.md
```
