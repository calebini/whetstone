# Verified Phase 1 closeout v1 (unactivated)

This bounded consumer evaluates global acceptance and publishes terminal evidence
for the existing standard horizontal V review sequence. Its algorithm and
`vnext_verified_phase1_closeout_v1` schema must be explicitly pinned with the
existing V history/work/review contracts and terminal-report-v2. Installed files
do not qualify a shipping mode. It introduces no client invocation or Phase 2
execution, no mutable scheduler-state replacement and no draft-authority write.

## Evidence-derived acceptance

Prove the current seed-to-head lineage and respect existing work precedence:
materialization recovery first, then registration recovery and eligible promotion.
Read-only inspection returns that blocking work observation; finishing may perform
the existing separate materialization-only recovery and must then stop. It never
combines that recovery with closeout. A pending promotion cannot become acceptance
merely because its candidate is verified. Unsupported/staged review sequences
retain their existing refusal boundaries.

Replay the complete canonical horizontal Reviewer sequence. For each configured
profile, use its latest completed review on the exact current pointer. Acceptance
is established only when every configured profile has such a review and none of
those reviews reports a normalized major or blocker anywhere, including findings
outside profile focus. The profile-clean predicate remains the existing in-scope
major/blocker rule. Preserve each global blocking finding's exact round and
feedback identity; another profile's clean review cannot erase it. An uncompleted
response cannot establish acceptance. Old-pointer reviews and Editor/Verifier
claims cannot discharge the current draft's review debt.

`accepted = false` means acceptance is not established by this bounded evidence;
missing profiles are explicit. It is distinct from a candidate disposition.
Do not publish a terminal while reviews, finding admission or technical recovery
remain pending. At `review_complete` or the existing hard `budget_exhausted` gate,
publish `PHASE_1_STABLE` only when global acceptance and all profile-clean checks
hold. Otherwise publish `TARGET_NOT_REACHED` with the exact global-acceptance or
budget reason. No soft sweep, extra closeout capacity, retry or extension is added.

## Terminal and closeout publication

Reproduce terminal-report-v2 from the proven current pointer and contiguous
candidate chain. Latest candidate is independently selected by creation ordinal.
Require any latest candidate at this boundary to belong to proven committed
promotion history; a candidate-local promotion event alone is insufficient.
Bind its actual committed promotion event and immutable verification decision.
Retain historical rejected candidate IDs; unresolved current decision gates
prevent closeout. Set apply-back permission and technical resume permission false.

Persist a content-addressed terminal report under `rounds/terminal_reports/`.
Then persist content-addressed `vnext-verified-phase1-closeout-v1` evidence under
`rounds/phase1_closeouts/`. The latter is this closeout's publication commit: it
binds job ID, the exact current pointer snapshot, the entire ordered review-receipt
prefix with original bases, missing/unclean profiles, global blocking findings,
acceptance and the terminal-report reference. No timestamp contributes identity.
Repeated closeout of identical evidence reproduces both paths and bytes. Earlier
reports remain intact; directory order never selects a current terminal.

Finishing holds the actual D8 fence. Reestablish current-pointer/mirror barriers
through the existing work owner, then repeat the Reviewer journal's source/output
barriers for every completed receipt. Reproduce evaluation before publication,
publish report then evidence, and recheck readback and current authority. Do this
also when both files are already visible: byte equality after a lost acknowledgement
does not prove the earlier durability barrier succeeded. No new review, candidate,
verification or promotion ordinal is allocated.

Before evidence publication, a report-only prefix is recoverable by exact replay.
An existing committed evidence record with its report missing is corrupt, not an
invitation to reconstruct committed content. Conflicting expected-path bytes or
changed raw/source evidence refuse without repair. Inspection never writes.
`materialized` describes matching visible evidence, not acknowledgement of a past
write; uncertainty requires a fresh successful finish/replay. These guarantees use
the ratified single-host/single-writer storage scope, not a distributed protocol.

The APIs expose immutable terminal artifacts, not cached run-state authority.
They do not write legacy `terminal_state`, `last_accepted_draft_hash` or
`ready_for_phase_2` fields, stamp versions, run declaration generation, enter
Phase 2, declare convergence or apply back to sources. Those remaining consumers
must validate current lineage and their own capability gates before using a
closeout. A stored PHASE_1_STABLE report alone grants none of those operations.
