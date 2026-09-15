# Bounded 18.7 V Reviewer integration

This checkpoint implements the private **standard horizontal** V Reviewer
sequence and canonical round publisher. It does not complete 18.7 or activate a
mode. The new [consuming algorithm](../contracts/algorithms/vnext_verified_review_sequence_v1.md)
is outside shipping suites; the frozen first suite and qualification maps remain
unchanged. This supplement extends the earlier stored-run component boundary only
when the additional sequence contract is pinned.

`VerifiedRun.review_next()` selects one eligible round/profile against the exact
committed pointer. Its durable request retains original seed context and reviews
the selected base. Historical candidate replay validates only the original
Reviewer prefix justified by already proven bases, avoiding a dependency cycle
through later promotions. Changing the pointer invalidates previous clean
observations even when draft bytes are identical; it never restores spent budget.
`review_complete` and `budget_exhausted` are local observations, not Phase 1
terminals or Phase 2 readiness.

`VerifiedRun.admit_reviewed_round()` derives canonical feedback/advice references
from the completed Reviewer receipt and mutation constraints from the immutable
launch package. Decision references remain explicit. It validates the round,
repeats source durability barriers, validates again, and immutably publishes
`rounds/round-N/proposal_input.json`. No fixture publisher or in-memory selector
update is needed for these runtime rounds. Staged roots retain their previous
behavior; runtime journals cannot be mixed into them.

Read-only `review_status()` reports the selected review or an existing recovery
or promotion gate. `review_next()` preserves Stage 1 committed-mirror recovery
precedence and ends after repair. Incomplete review work requires explicit
continuation. Retained raw output and lost result/publication acknowledgements
recover without duplicate calls. Before claiming a later review, the completed
Reviewer prefix repeats its durability barriers.

## Validation and limits

**64 distinct targeted tests pass**: 12 runtime integration tests, 51 existing compatibility tests, and one new staged-recovery regression, with overlapping final stored-run and production-journey reruns. This is 13 new tests in total.

The [validation record](audits/VNEXT_VERIFIED_REVIEW_INTEGRATION.json) records exact
source hashes, commands, counts and log hashes. Scripted clients and temporary,
test-only registered suites exercise the real storage, request, registration,
verification, promotion and round-publication owners. No live provider was called.

The primary journey performs Reviewer → canonical round admission → Editor →
registration → Verifier → promotion → reopening → new-base Reviewer → canonical
round admission. Separate checks cover fresh-process replay, missing original raw
output, same-byte promotion, selected profile/budget refusal, exact packaged
constraints, technical continuation, interrupted round publication, source
barriers after lost acknowledgements, and committed repair before malformed future
claims. Compatibility checks retain the P seed-review, P stored-run, V journal,
bounded-prefix and staged V stored-run behavior.

This is targeted integration evidence, not a full regression or release audit.
Same-round operator follow-ups and multiple successive promotions through this
new runtime sequence still need integrated qualification; existing component
fixtures do not close those rows. Complete fault-prefix/process-death coverage at
this new boundary also remains open. Rejected candidates and outstanding choices
continue through existing work/operator owners; this increment adds no automatic
resolution or replacement review on an unchanged base.

Next bounded work within 18.7: exercise the runtime round producer through a
same-round operator follow-up and a second promotion, preserving original rejected
candidate evidence and exact client counts after reopening. Reconcile remaining
18.5–18.7 acceptance rows before considering completion. Full scheduler terminals,
vertical/focused/closeout integration, extensions, Phase 2 and apply-back remain
18.8; full release qualification and activation remain 18.9. Neither is included.
