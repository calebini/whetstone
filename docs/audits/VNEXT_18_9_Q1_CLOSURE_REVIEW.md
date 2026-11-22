# Bounded Q1 closure review — working audit

> Historical working record retained in the 2026-11-22 documentation cleanup.
> Statements below about uncommitted state and pending release work describe
> the original checkpoint, not current release status. Current status is in
> [the release record](../VNEXT_VERIFIED_PROMOTION_RELEASE.md).

Base: `c2849cd7943ea29eb99cc31353a06dffc14cc95f`. Scope: Q1's seven acceptance
cases, supported command/recovery matrix, final command adapters, retained
evidence and production gates. This is local same-agent static review and
scripted verification, not an independent reviewer verdict. No external
transmission or live client was authorized or attempted. Keep this audit
uncommitted; the durable result belongs in `docs/VNEXT_18_9_Q1_CLOSURE.md`.

## Findings

### C1 — Legacy Phase 2 intent silently ignored

`vnext_verified_cli._controls` did not reject `--closeout-existing` or
`--rubric-label`; `_bound_settings` did not corroborate CLI workflow/rubric.
Consequently a reviewer-only closeout request could enter the ordinary V loop,
or conflicting selectors could be ignored. This violates the existing immutable
binding/unsupported-control contract; no new policy is required.

Fix: refuse closeout/label controls and only accept workflow/rubric selectors
matching supported pins. Two new CLI methods cover refusal before dispatch and
matching corroboration. The latter records dispatch only; it does not claim a
genuine Phase 2 journey. Legacy CLI behavior is unchanged and rerun separately.

### C2 — Post-client failure reporting omitted command-selection fences

After a Phase 1 Reviewer or Phase 2 Editor failure, command adapters invoked the
report and projection owners directly. Those owners retain their own authority
checks, but this path omitted the invocation-selection guard required by
`vnext_verified_commands_v1.md`. A peer could advance the selected boundary
between client completion and reporting.

Fix: bind the retained failed request/outcome, revalidate it at each actual D8
fence, and reuse guarded repair owners. Four new methods cover normal failure,
publication race, projection race and replaced outcome, each for both phases,
using real local D8 storage with recording owners. Existing genuine Reviewer
timeout and Editor report/interruption journeys exercise owner composition.

The first guard batch exposed missing methods in the recording fixture; the
fixture was corrected without relaxing production validation. Review of the
actual proof type also corrected comparison of a latest snapshot Ref to a full
current pointer: the helper now compares the full pointer (`pointers[-1]`). The
final genuine Editor recheck is required before crediting that fix.

### C3 — Status omitted proposed supported recovery invocation

The ratified command matrix requires a proposed invocation alongside retained
gate/identity evidence. Status provided the latter but not the former.

Fix: add read-only `recovery_invocation` argv or null. It uses only finite supported
rows, includes required candidate round selectors, gives pending repair
precedence, and invents no retry/budget/source permission. Two pure tests cover
the closed mapping and refusal. The genuine Editor recovery test asserts the
status field for pending repair and unsupported terminal reentry while retaining
its no-writer/no-mutation status checks.

## Evidence reconciliation and limits

`rounds/vnext-18-9-q1-closure-001/` retains baseline/source cohorts, failed and
corrected runs, exact worker commands/status and verification receipts. The
command batch had a misspelled Editor-recovery test class; that loader error is
not credited as execution. The correctly named method is rerun separately.

All 22 prior delivery-pass log hashes and recorded code/test checkpoint hashes
were checked. Every claimed successful method is present in raw logs. Counts
92/99/72/84 remain historical overlapping inventories, not a fresh aggregate.
Prior route/convergence and source-operation journeys are reused with their
documented limits; they were not silently relabeled runs on closure sources.

Same-byte Phase 2 staging locators were considered and not classified as a
finding: the binding owner derives the immutable canonical Ref from content.
No arbitrary staging-spelling authority or new contract field was invented.

Q2's named P0 gaps, Q3's exhaustive qualification and replay performance, and
Q4's authorized live soak/activation remain open. Advanced-pointer source tests
use proof/readback composition guards, not a new post-convergence scheduler route.
This bounded review makes no physical power-loss, independent-implementation,
all-fault-cross-product or release-readiness claim.

Final disposition: all three findings are resolved within this review scope.
The durable closure handoff records Q1's finite integration completion and
119 distinct fresh passing methods. No Q1 blocker remains; Q2–Q4 are open.

The 61-method final recheck passed all 60 guard methods. Its genuine Editor
journey reached the intended report-publication fault, then failed the new
diagnostic assertion because it compared `/var` to the canonical `/private/var`
root. Corrected the expected path with `resolve()` and reran only that journey.
This is a fixture correction, not a production relaxation or another finding.
The isolated Editor journey then passed in 521.420s, including lost final-state
acknowledgement and stopped reentry with unchanged calls/pointer. Both suites and
all four empty production gates were verified. Workers exited and the index is
empty. No commit or push was performed.
