# Verified Phase 1 status v1 (unactivated)

This read-only consumer reports progress of the existing standard horizontal V
review sequence. It requires this exact algorithm in the descriptor-bound suite,
in addition to the existing V run, work, history and review-sequence contracts.
Installed files alone grant no capability. No shipping suite or public mode is
changed. Its Python result is an inspection value, not a persisted new envelope.

Prove current verified lineage and apply the existing work precedence:
materialization, registration recovery, eligible promotion, then ordinary work.
Return the proven current pointer separately from latest registered candidate and
promotion claimant. Pending materialization withholds profile/journal projections
as null, so unknown does not look like no candidates or a clean phase. Do not
parse unrelated future review claims ahead of that recovery boundary.

After materialization, replay the complete canonical Reviewer sequence with the
existing profile eligibility, current-base, exact original receipt and budget
checks. Report each configured profile's pinned budget, completed logical reviews,
last completed round and clean/exhausted status. Count completed receipts across
promotions. Technical invocation attempts do not consume additional logical
reviews. An uncompleted raw response cannot mark a profile clean.

Clean means the profile's latest completed review has no in-scope major/blocker
and is bound to the exact current verified pointer snapshot. Return that snapshot
and exact receipt path/hash as evidence. A promotion invalidates prior clean
observations even when draft bytes are identical; it does not reset budgets.
Exhausted means not clean and completed logical reviews meet the pinned budget.
Fresh roots are reportable without inventing a Reviewer frame; existing admission
still requires nonempty unique profiles with positive budgets.

Report the review selection gate separately from work precedence. A
`finding_admission` review observation may coexist with a pending registration or
promotion; it does not override that higher-priority work outcome. `review_round`
is the next review number or pending/finding round, and is null at completion or
budget exhaustion. Pending attempt count is the number of retained outcomes,
not an authorization to retry. Same-round children do not add Reviewer passes.

Recheck current pointer/descriptor and root selectors before returning. Results
are detached read-only observations, possibly of a completed prefix during a
cooperating writer's work. They hold no lock or cross-call authorization. Every
mutating command must freshly validate its own admission under exclusion.
Malformed authority or consumed evidence fails rather than falling back to
`spec.md`, cached run state or terminal reports. Inspection never repairs mirrors,
publishes a receipt, invokes a client or allocates an ordinal.

`all_profiles_clean` is only the conjunction of current profile observations. It
does not prove global accepted-draft requirements, publish `PHASE_1_STABLE`, grant
Phase 2 entry, declare convergence or authorize apply-back. Those integrations,
focused/vertical scheduling, soft sweeps, closeout capacity, budget extensions,
terminal publication and public capability qualification remain separate work.
