# Verified Phase 2 intervening resolution v1

This separately pinned internal consumer extends the standard horizontal,
unversioned V Phase 2 sequence and signal owners. Absence of this algorithm
preserves their original behavior. It enables no public mode.

The identity/oscillation spec requires a churn reset between round R and the
next review when accepted/modified feedback names the concern and its issue is
absent from the pre-review unresolved snapshot. The candidate spec requires
Orchestrator-derived resolution status from candidate verification, after
promotion; Editor claims alone have no effect. Profile cleanliness still needs
later Reviewer evidence (scheduler D7 and Phase 2 scheduling).

For each proven Phase 2 promotion, reproduce an immutable record beneath
`rounds/phase2/resolutions/pass-N/` containing `summary.json`,
`unresolved_issues.json` and a last-published `commit.json`. The record binds the
configuration, entry, original request/feedback/advice, consumed review prefix,
previous resolution records, exact predecessor and promoted snapshots, creation,
final candidate decision and semantic verification. Read only an ascending proven
prefix: a candidate cannot use its own promotion to prove its admission.

Require a final passing, promotion-permitted candidate decision reproduced by
committed-lineage replay. Its semantic result must pass with exact whole-finding
`resolved` coverage of this correction's editor-fixable findings. IDs must match
original canonical issue IDs; partial/derived/unrelated IDs do not clear them.

The V compatibility summary records `accepted_or_modified_feedback_ids`, the
union needed by the churn rule, from resolved findings' original feedback IDs.
It does not invent the legacy distinction between literal acceptance and a
substantive correction: candidate verification does not establish that wording
classification. This is a separately versioned summary, not a legacy Editor
response. All observed issues remain in the unresolved snapshot until one of
these verified records resolves their exact identity. Silence, a changed base,
or an unrelated promotion cannot clear them. A later occurrence reopens its
issue. No change to legacy/bridge summaries or root unresolved mirrors is made.

Only a complete exact receipt permits the next review. Missing publication gates
ordinary continuation as `resolution_publication_required`; higher-priority
signal, budget, declaration and authority gates remain intact. Replaying a
committed receipt resets only its opposition keys at the start of the next
review. It never revises the triggering round's diagnostic, conflict history,
flip-flop/re-addition/draft-cycle tracking, budgets, cleanliness or convergence.
Every successor request's source barrier includes the receipt and dependencies.
The namespaced run-state projection is convenience metadata, never authority.

Explicit publication and state recovery run under the existing D8 fence and D7
preconditions. Revalidate input bytes and synchronize source dependencies before
publication, synchronize outputs before the immutable commit, and repeat barriers
on reentry, including lost acknowledgements. A committed record missing any
asset, substituted bytes, unknown claims or stale sources fail closed. Recovery
projects only `vnext_phase2_resolutions`, preserves other state, and stops without
clients, candidate work, a next request, or budget consumption. Status is read-only.

This owner does not resolve freeze recommendations, introduce operator repair
admissions, clear rubric/authority gates, implement declaration repair, enable
version maintenance, resume general Phase 2, strop, or qualify/activate modes.
