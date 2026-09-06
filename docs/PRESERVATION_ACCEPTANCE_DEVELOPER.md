# Local preservation acceptance checkpoint

The bridge now has a local acceptance service and developer commands for isolated Phase 1 proposal roots. It validates explicit effect evidence, commits an immutable acceptance marker, installs the exact materialized draft and repairs interrupted installation from that marker. It invokes no model and does not charge another review round.

This is step 3 of slice 18.1. Live scheduler integration and qualification are step 4. The service refuses roots containing `rounds/run_state.json` or `orchestrator_config.yaml`, Phase 2 acceptance, inherited maintenance authorization, and noncontiguous standalone rounds. It does not create scheduler state, mark a profile clean, declare stability/convergence, or enable source apply-back. The reserved `preservation_bridge` run configuration remains unavailable. Do not remove runtime files to bypass the boundary.

## Review and adopt an exact effect

Begin with an isolated root produced by `ProposalStore`, containing an approved immutable base/scope/surface/findings and a complete numbered proposal. The proposal's original report may be pending, rejected or preliminarily eligible. Source approval and a bounded proposal do not replace effect evidence.

All artifact paths below are relative to the selected root. `preservation-review` prints the exact original and final output line inventories, source finding references, trusted transformations and latest assessment reference:

```sh
ROOT=/absolute/path/to/isolated-proposal-root
PROPOSAL=rounds/round-1/preservation/attempt-1/proposal.json
PYTHONPATH=src python3 -m whetstone.cli preservation-review \
  --root "$ROOT" --proposal "$PROPOSAL"
```

For the Parcel Queue toy clarification only, original line 9 corresponds to final line 9. After reviewing that exact wording, an operator can explicitly attest equivalence:

```sh
PYTHONPATH=src python3 -m whetstone.cli preservation-attest \
  --root "$ROOT" --proposal "$PROPOSAL" --output operator/equivalence.json \
  --kind attest_equivalence --base-lines 9 --output-lines 9 \
  --disposition reworded_equivalent --change-type clarify --finding fb-1 \
  --effect "The minimum retry delay remains 30 seconds." \
  --rationale "The selected lines express the same lower bound." \
  --operator "YOUR_OPERATOR_ID" --approve
```

Whetstone resolves the selected lines to final inventory IDs and computes every proposal/base/surface/output/transform hash. It does not infer the operator's semantic claim. Approval is required only for explicit effect adoption; review and dry-run do not adopt anything. Evidence files are immutable and cannot be overwritten.

Comma-separated `--base-lines` and `--output-lines` select one grouped effect: each predecessor maps to the selected successor group. Use separate evidence files for independent effects. Shared successors require a complete supersession group. Additions have output lines and `--kind attest_addition`, with no base lines or disposition; deletion has base lines and an empty output selection. Sensitive effects still require the exact corresponding permissions in the approved surface. Selecting `--surface` explicitly binds evidence to a newly approved same-base surface; it cannot modify the proposal.

Repeat `--finding` for multiple admitted findings. If an ID is ambiguous across reviewers, use the source path shown by review, for example `--finding inputs-1/feedback.json::fb-1`; no hash transcription is needed. Unknown or ambiguous findings and invalid line selections are refused.

## Prepare, preview and accept

```sh
PYTHONPATH=src python3 -m whetstone.cli preservation-request \
  --root "$ROOT" --proposal "$PROPOSAL" \
  --evidence operator/equivalence.json --output operator/request-1.json

PYTHONPATH=src python3 -m whetstone.cli preservation-accept \
  --root "$ROOT" --request operator/request-1.json --dry-run

PYTHONPATH=src python3 -m whetstone.cli preservation-accept \
  --root "$ROOT" --request operator/request-1.json
```

Repeat `--evidence` for multiple adopted effects. A genuine unchanged proposal needs no effect evidence, but ordinary unresolved findings still apply. Request preparation automatically binds the latest assessment as its predecessor. A changed authorization/evidence set uses a new request file and a new acceptance attempt; earlier reports remain unchanged.

Dry-run is read-only, including when no lock file exists. Its report/admission identity is a prospective preview, not a persisted report or permission to write. It checks bindings, complete correspondence, surface permissions and limits, text hygiene, ordinary serious-issue/conflict gates, inherited accepted residuals, current base and canonical-file conflicts. A real operation repeats these checks under the shared exclusive writer lock. Exit status is 0 for an eligible preview or successful acceptance/replay, and 2 for rejection or error.

A successful operation returns `outcome: accepted`, its report Ref and acceptance Ref. It completes only that selected operation and stops. Accepted content still needs ordinary review; this result says nothing about stability or convergence. An unclassified error or a failed gate never permits installation.

## Commit, replay and repair

An acceptance attempt lives below the proposal at `acceptance-attempt-K/`. Its admission freezes the request and input references before assessment. Its immutable report precedes `acceptance.json`, which is the commit point. Only then may checked final bytes become `spec.md`, canonical `draft_before.md`/`draft_after.md`, the accepted Editor summary and `unresolved_issues.json`. Canonical summary hashes/content describe the final materialization. No normalization or second stamp occurs.

The standalone service records the original seed and initial history snapshot under `rounds/preservation/seed.json` and `seed_history.md`. These are internal single-writer bookkeeping, not new public bridge contracts or competing authority pointers. Acceptance markers form the accepted lineage. A deterministic entry in `spec.history.md` identifies each committed round, exact acceptance marker and normalized before/after hashes. Existing history is retained. The accepted chain and immutable normal-round evidence reconstruct inherited unresolved issues; a no-op cannot discard them by claiming resolution. Ordinary acceptance applies the existing global major/blocker gate, including serious out-of-scope findings.

Repeat the same acceptance command after an interrupted operation. A frozen incomplete admission can resume with identical inputs. A committed operation revalidates its complete chain and reconciles only missing or expected old/new mirror states. It never calls an Editor, restamps, allocates another acceptance or duplicates history. An older committed proposal returns its historical result after authority advances; it does not reinstall old text. Pending committed repair blocks new proposal/acceptance admission. Conflicting current bytes or canonical files halt for inspection instead of being overwritten.

When persistence fails, available evidence is retained and a separate `terminal_failure.json` records the failure, including the acceptance Ref if the marker already exists. A completed report is never rewritten. Failure to persist the sidecar propagates as an error. Existing failure sidecars remain historical evidence after successful recovery. Simultaneous cooperating mutating invocations are refused by the root's nonblocking writer lock; this is not a vNext candidate/promotion-lock implementation.

## Executable evidence

`tests/test_preservation_acceptance.py` adds 30 deterministic tests. The complete suite has 389 passing tests, including 90 preservation tests. Coverage includes pending-to-accepted, rejection followed by explicit reauthorization, unchanged acceptance, stale bases, conflicting mappings, changed effect/config bytes, ordinary unresolved findings, retained residuals, transformed output, historical replay, CLI adoption/dry-run, concurrent invocation, and interruptions around admission/report/marker/draft/history persistence. No live models are invoked.

Runtime scheduler completion/readback, profile/budget accounting, Phase 2 maintenance/handoff, source guards and declaration/strop consumers still require the step-4 adapter and qualification scenarios. The [implementation plan](../IMPLEMENTATION_PLAN.md#181-current-runtime-preservation-bridge) retains those checks as open.
