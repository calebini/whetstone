# Verified Phase 1 operator projection v1 (unactivated)

This internal consumer requires its own algorithm pin and every contract required
by verified Phase 1 closeout. It supports only the existing standard horizontal
sequence. It neither activates a public status/CLI mode nor changes legacy/bridge
status interpretation. `VerifiedRun.operator_status()` reads;
`reconcile_phase1_state()` synchronizes derived state and ends the invocation.

Prove seed-to-current lineage and preserve materialization, registration recovery,
and eligible promotion precedence. When any takes precedence, withhold acceptance,
terminal and state-currency claims. Mutation may perform the existing separate
mirror recovery only, then stop. Damaged initialized evidence refuses; it cannot
fall back to cached state or a directory-selected report.

Otherwise reproduce the Phase 1 closeout from canonical current-pointer review
receipts. Only its matching, visible report AND evidence commit select the active
terminal. A report-only prefix is not active. Preserve historical artifacts;
never enumerate reports to choose the newest or follow cached paths. The returned
acceptance is the current evaluation, independently of terminal publication.

The sole new run-state member is `vnext_phase1_closeout`, exactly the content-addressed
`{path, hash}` reference to the currently reproduced committed closeout evidence.
That evidence binds the job, verified pointer, review prefix and terminal report.
When no current committed closeout exists, the member must be absent. Preserve all
other members, including `vnext_current_verified` and any legacy fields; those
legacy fields never determine this consumer's status. Status flags a stale member
and reports state recovery before any next work. Missing derived state is recovered
by the existing mirror owner first, then this consumer on a separate invocation.

Status is read-only. It may show a valid committed terminal with a missing/stale
derived reference, but must mark `state_current = false` and recommend recovery.
Matching visible state means byte correspondence, not acknowledgement of a previous
flush. No read-only status can establish the latter.

Recovery holds the single actual D8 fence and inherits the current pointer/mirror
barriers. For a committed closeout, repeat Reviewer source/receipt barriers and
exact report/evidence synchronization before the state projection. A missing or
conflicting committed artifact refuses; this operation never creates a terminal
or closeout. Check the current head, run selectors and captured state bytes at the
state-write boundary. Replace only the derived member, or synchronize matching
bytes even on reentry after a lost final-write acknowledgement. Reevaluate the
closeout and state after writing; return only after successful barriers/readback.
Uncertain storage errors propagate and ownership invalidation remains the storage
owner's responsibility. State recovery never proceeds into review, candidate work,
promotion or closeout publication, and allocates no client attempts or ordinals.

Internal next-action labels describe this consumer's exact supported operations;
they do not grant generic technical resume or publish a capability. Phase 1 stable
is distinct from Phase 2 execution, convergence and apply-back. Their permissions
remain false. This slice writes no legacy readiness/acceptance/terminal fields,
version/history/declaration artifacts, shipping suites or external specifications.
