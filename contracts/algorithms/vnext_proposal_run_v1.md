# Stored proposal run inputs and status (under development)

This supplement connects the private 18.5 consumer to reopenable run roots. It does not publish a mode, bypass the shipping contract registry or resolve D8. Existing Reviewer-only configuration and CLI dispatch remain unchanged.

## Retained selectors and initialization

`inputs/proposal_run.json` is a closed `vnext-proposal-run-input-v1` record containing job ID, exact descriptor/review/seed-map references and sorted unique staged round-input references. These are locators, not authority or capability. The descriptor, registered suite, physical storage binding, seed/map/current snapshot, roles and referenced round evidence must independently validate on every use. A record cannot introduce a caller-selected suite digest or replace descriptor-bound input bytes.

Fresh proposal initialization freezes and validates the staged package before destination creation, adds this exact run record, and checks its stored readback. An existing record must match exactly. Initialization now also permits zero staged rounds so the immutable seed can be admitted before Reviewer work exists. Even then, it validates seed normalization, the configured profile/workflow/scope policy, assertion programs and complete seed inventory before creating the root. No Reviewer is invoked by initialization; future Reviewer scheduling remains a separate consuming step.

`open_proposal_run` opens the retained physical root, validates the record against storage and all bound inputs, and reconstructs the admission callbacks. It selects installed suite files from the descriptor's registered version; a relocated suite path is permitted only when its complete digest/pins validate against that same implementation registry. Unknown suite versions refuse before selecting a manifest path. Open and status perform no repair.

## Later round admission

`ProposalRun.admit_round` receives a closed round-input record whose Reviewer, advice and operator decision evidence already exists by exact hash. Under D8 ownership, it runs complete preflight, repeats dependency durability barriers and publishes the immutable canonical `rounds/round-{number}/proposal_input.json`. It rechecks the resulting readback. Initial staged selectors cannot be contradicted, and an existing canonical record cannot be overwritten.

A reopened run uses that canonical record, or its exact staged reference before canonical publication. If both exist, their bytes must agree. No directory enumeration chooses the round: callers explicitly select a positive round number. The public scheduler must retain its own active-round and review-budget evidence before it can remove that explicit selection requirement. This record does not authorize manufacturing a new transaction after rejection or inventing Reviewer/decision evidence.

`ProposalRun.run_round` derives status before mutation, requires explicit continuation for retained incomplete work, refuses unsupported technical continuation and unresolved registration recovery, admits the canonical round record, then invokes the existing private D7 round entry. That entry owns all request budgets, candidate registration, decision commit and terminal projection. Reopening never resets a request budget.

## Read-only status

The closed `vnext-proposal-status-v1` response distinguishes the selected round's request and next processing gate from candidate authority and terminal materialization. It validates the entire creation chain and every registered candidate's decision targets, even when inspecting a future unadmitted round. It never hides damaged committed evidence behind an empty or unrelated selection.

- A seed-only run projects its [durable Reviewer sequence](vnext_seed_review_requests_v1.md): fresh review, bounded technical recovery, finding admission or [phase closeout](vnext_seed_review_closeout_v1.md). An unselected future round cannot inherit the active round's recovery. Externally staged round packages retain explicit selection.
- An unstarted proposal is ordinary new work, not technical resume.
- Interrupted requests retain the exact cause and are resumable only under their request budget or complete-output reuse rule. An exhausted timeout stays a timeout.
- A complete request without registration retains assembly as the first incomplete gate. A sole complete orphan is resumable only when its exact next creation ordinal, predecessor and selected proposal match; incomplete or conflicting orphans require diagnosis.
- A registered candidate with no committed decision retains `verification_commit`; prepared targets are not reported as effective decisions.
- A committed decision with missing terminal output retains only `materialization`. A conflicting content-addressed terminal file is invalid.
- A fully materialized deterministic pass still lacks semantic verification and cannot advertise that unavailable gate as resumable. A final rejection cannot reopen. Historical selected rounds cannot claim the latest candidate's continuation.

Status takes no writer lock, invokes no client and writes no files. It returns actual validated terminal projections, never a historical file selected by filename or time. The [guarded command interface](vnext_proposal_cli_v1.md) and [explicit operator decisions](vnext_operator_decisions_v1.md) now consume these roots. Public qualification, D8 audit/reconciliation and final suite publication remain release work.
