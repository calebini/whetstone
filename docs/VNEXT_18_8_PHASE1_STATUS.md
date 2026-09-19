# 18.8 first slice: verified Phase 1 progress

Date: 2026-09-20. Starting checkpoint: `9a09bc1`.

`VerifiedRun.phase1_status()` adds a read-only view of the existing standard
horizontal V scheduler. Operators and later scheduler consumers can distinguish
the current verified draft, the latest registered candidate, pending recovery or
promotion, and each profile's remaining review capacity without reading cached
reports as authority.

This begins 18.8 under the user's authorization to tackle the next implementation
area. It is a bounded part of scheduler/reporting integration. All four 18.8 plan
tasks remain incomplete. It does not qualify public `verified_promotion`, enter
Phase 2 or perform external apply-back.

## Implemented behavior

The new [status consumer](../src/whetstone/vnext_verified_phase1_status.py) uses the
existing committed-history proof, work precedence and canonical review-sequence
replay. Its [separate algorithm pin](../contracts/algorithms/vnext_verified_phase1_status_v1.md)
must appear in the descriptor-bound consuming suite. The existing shipping suite,
qualification maps and methods retain their behavior; the new method is reached
only by an explicit caller.

| Observation | Meaning |
| --- | --- |
| `current_pointer` | Proven verified authority, independent of later candidate creation or verification. |
| `work_outcome` | Existing precedence: mirror recovery, registration recovery, eligible promotion, then ordinary work. |
| `latest_candidate`, `promotion_candidate` | Registered latest and selected promotion claimant, separately reported. They cannot substitute for current authority. |
| `profiles` | Pinned budget, completed logical reviews, latest completed round, cleanliness and exhaustion for each configured profile. |
| `clean_base_pointer`, `clean_review_receipt` | Exact pointer snapshot and receipt path/hash proving a profile's clean observation. |
| `review_gate`, `selected_profile`, `review_round` | Existing review-sequence selection, subordinate to `work_outcome`. Completion/budget exhaustion do not invent a next round. |
| `pending_review_attempts` | Retained pending request outcome count; no permission to retry is implied. |
| `all_profiles_clean` | Profile evidence only. It does not establish global accepted-draft status, a phase terminal or Phase 2 readiness. |

Completed Reviewer receipts consume logical profile budgets across promotions.
Technical retries do not add logical reviews. Promotion invalidates clean
observations on the old pointer without resetting budgets. Byte-identical pointer
advancement remains a different authority identity. An incomplete raw response
does not establish clean status.

Pending mirror recovery withholds profile, review and orphan projections as null;
unknown evidence is not reported as an empty journal or a clean phase. This also
preserves recovery priority when an unrelated future Reviewer claim is malformed.
After that boundary, malformed consumed evidence refuses inspection. Results are
detached observations, never a write token or cached permission for later work.
Inspection neither acquires the mutation lock nor publishes, repairs or invokes
clients. Mutating commands retain their existing locked admission checks.

## Validation

**All 30 methods passed on their first runs with no skips:** five new integration
methods in 51.091 seconds and 25 existing regressions in 169.182 seconds. No source
fix was required; the recorded runtime/contract/test/spec hashes match throughout
the two invocations.

The focused tests exercise the production journals and promotion writer with
fictional clients and process-local suites: clean multi-profile progress and
reopening, inspection during a held writer lock, detached results, timeout/retry
accounting, missing qualification, damaged raw evidence, orphan registration,
promotion invalidation, budget exhaustion and mirror-recovery precedence.

The existing verified-review sequence and shared scheduler modules are the
regression cohort. Exact commands, results, method identities and source hashes
are recorded in [the validation record](audits/VNEXT_18_8_PHASE1_STATUS.json).
Raw logs and the source manifest remain under ignored
`rounds/vnext-18-8-status-001/`. This is bounded validation, not the full release
regression or live-provider qualification.

## Remaining integration

The subsequent [closeout slice](VNEXT_18_8_PHASE1_CLOSEOUT.md) now implements global
accepted-draft evaluation and immutable Phase 1 terminal publication/recovery for
this horizontal path. Operator status/run-state projection is the next integration. A conjunction of clean profile observations
must not substitute for global acceptance or automatically enable Phase 2.

18.8 still needs the remaining focused/vertical/retry/resume scheduling and budget
extension consumers, phase/version/history/declaration integration, Phase 2 and
convergence, strop/readback eligibility, and terminal/status publication across
their supported paths. Existing normal V transactions and the new status view
are credited; those remaining consumers are not marked complete.

18.9 shipping-suite, complete P0/cross-implementation/compatibility qualification,
live soak and activation remain deferred. D8's ratified single-host/single-writer
boundary stands. Legacy/bridge behavior, frozen suite 1 and all three empty
shipping qualification maps are preserved. No external provider, new mode, push
or external specification apply-back is included.
