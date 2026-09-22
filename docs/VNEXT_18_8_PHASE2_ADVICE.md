# Bounded first Phase 2 finding-advice attachment

Date: 2026-09-22. Clean starting checkpoint: `2cac435`.
This slice was validated unstaged and uncommitted. The user subsequently authorized
a local checkpoint; all recorded source and passing test-log hashes were rechecked
with no source changes or additional test runs. Push remains deferred.

`VerifiedRun.prepare_phase2_advice(advice=None)` validates explicit advisory input
without a writer fence. `bind_phase2_advice(advice=None)` binds it under D8 to the
first committed and consumed Phase 2 result. Both require new algorithm/schema
pins before root creation, plus the existing finding-advice and mutation-preparation
contracts. No in-place suite migration or shipping-map activation is provided.

The supported input is the existing `vnext-finding-advice-v1` advisory packet.
This is a consumer of explicitly supplied, untrusted advice, not an automated
producer, a claim of Reviewer authorship, or an operator authorization response.
The existing optional-advice contract supplies its meaning and exact bindings;
no new authority or invocation-budget policy is assumed. Current Phase 2 Reviewer
responses still contain no advice and are unchanged. No additional client is called.

Advice must cover the exact source feedback IDs and bind job, base, feedback,
authority, scope and invariants. The existing V classifier computes findings,
stable targets and source evidence. Policy, destructive-effect, scope, invariant
and authority checks override claimed classifications. An `editor_fixable` finding
is only a classification here: this owner creates no canonical proposal round,
mutation plan, operator decision, candidate permission or subsequent review grant.

Under `rounds/phase2/review_requests/first/execution/`, publication writes
`finding_advice.json` and then a distinct `advice_binding.json` commit. It repeats
entry, Phase 1 prerequisites, configuration, current-pointer, rubric, source,
request, journal, feedback, result and consumption barriers. The existing consumed
result and its conservative no-advice findings are immutable historical evidence;
the attachment does not rewrite them or count another successful pass.

A retained advice prefix fixes the input; a different attachment is refused even
before its binding commit exists. Reentry without a supplied packet can finish that
prefix or replay the completed binding. Lost acknowledgements propagate. A visible
binding missing its advice or other committed dependencies refuses reconstruction.
Mirror recovery ends the call. Preparation reports `advice_required` if nothing is
supplied or retained; it does not invent an operator pause. Returned views are detached.

## Validation

**17 distinct tests pass** on the final source: four focused methods (70.597
seconds) and 13 classification/accounting regressions (65.440 seconds). Focused
coverage includes read-only preparation, exact binding and source coverage,
deterministic policy/authority overrides, unchanged accounting and authority,
detached replay, unpinned-owner refusal, pre-publication and completed-replay
barriers, lost acknowledgement at both publication steps, immutable-prefix conflict,
mirror recovery, rubric drift, tampered binding and missing committed advice.
`git diff --check` passes; frozen suite 1 and empty shipping maps remain unchanged.

The initial fixture lacked the newly required mutation-preparation algorithm pin;
the owner refused it. A subsequent test expected a weaker scope classification
than the existing classifier's authority-conflict override. Both were corrected,
and both final cohorts were run again on unchanged final source. Earlier logs
remain retained and are excluded from the passing-test count.

See [the validation record](audits/VNEXT_18_8_PHASE2_ADVICE.json) for exact source,
commands, method identities and log hashes. Raw evidence is retained under ignored
`rounds/vnext-18-8-phase2-advice-001/`. Tests use scripted clients and process-local
faults on macOS/APFS, without external transmission. No live producer, promoted-entry
advice campaign, multiprocess-death, power-loss or full-product qualification is claimed.

## Exact next boundary

The advice attachment is implemented; **canonical Phase 2 V round admission remains
unimplemented**. Its next owner must consume the exact committed binding, retain
packaged mutation constraints, and route the new round through full unit preflight.
`_RunHistory._validate_round_review` currently routes runtime review provenance only
to the Phase 1 sequence. Add a separately pinned Phase 2 provenance route that
reproduces the original entry/result/advice against their original verified pointer;
do not relax Phase 1 validation or recursively validate a new current head as its
own historical authority. Qualify seed and promoted entry bases, stale bindings,
round publication recovery and refusal of unrelated round selectors before enabling
candidate execution. Later Phase 2 promotions require historical entry anchoring
and scheduler/current-sequence integration as well.

Automatic advice production, operator decision routing, subsequent requests,
profile progression, version maintenance through V candidates, convergence,
declaration and complete terminal reporting remain open. All four 18.8 tasks remain
incomplete. No 18.9 scope, public modes, external apply-back or push is included. The subsequent
local commit authorization does not expand implementation or validation scope.
