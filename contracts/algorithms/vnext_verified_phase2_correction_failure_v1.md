# Phase 2 correction failure reporting

Separately pinned internal reporting only, over the standard horizontal unversioned
Phase 2 sequence and already admitted original correction transactions. Requires
the Reviewer failure reporting pin and its schemas for shared mirror ownership. No new
client, attempt, candidate decision, promotion, repair admission or generic resume.
The shared journals retain their legacy phase1 discriminator; Phase 2 provenance
comes from the bound consumed review and canonical round, never that label.

Revalidate committed authority, original entry/configuration/rubric, consumed review,
advice, round admission, proposal journal, registration and committed decisions.
Derive Editor and Verifier technical failures from exact outcome prefixes; a retained
valid response or an available shape retry is not a terminal. Timeouts halt as
HALTED_CLIENT_TIMEOUT; transport/interruption/invalid/exhausted shape halt as
HALTED_ARTIFACT_INVALID. Reproduce recorded assembly failure without registering a
candidate. Final deterministic rejection halts with vnext_preservation_failed;
semantic reject uses TARGET_NOT_REACHED/vnext_semantic_rejected; a concrete bound
operator request uses PAUSED_DECISION/vnext_operator_decision_required. Prepared
decisions never supply their intended final disposition. Corruption and unsafe
storage errors propagate without manufacturing a durable report.

Each failure record binds its original pointer, Phase 2 request/configuration/entry,
canonical round, exact client request reference (null for non-client outcomes),
request/invocation/outcome-prefix cause digest, convergence failure report, terminal-report-v2 and
rubric manifest. Technical/deterministic/assembly halts also bind a diagnostic using
the separately pinned vnext_correction_artifact_error_v1 schema: verifier is explicit;
assembly/deterministic validation have null client rather than impersonating Editor.
Legacy schemas remain unchanged. Reports use the last verified draft, actual consumed
review budgets and unresolved findings; no final declaration review means not_run.

Record paths are derived from validated rounds, stage and existing attempt count.
Reproduce historical prefixes even after later valid output, final decisions and
promotion. Failure publication is explicit and separate from projection recovery.
Both run under D8, repeat full source barriers and end without client work.
Recheck captured source bytes after report assets and before each commit publication. Status
is read-only. The namespace vnext_phase2_correction_failure is advisory; it never
grants authority. Explicit existing request continuation may supersede technical
failure, but final rejection cannot resume. No new continuation route is advertised
by this report owner: resume.permitted is false and next_gate is null. Existing
component APIs retain their independent gates.

Root error/failure reports are owned projections of immutable committed records.
Order Reviewer and correction records by consumed pass, then Reviewer, Editor,
assembly, Verifier and final candidate stage, then attempt. A committed final
exhaustion report supersedes failure projections. Replace only exact owned bytes;
refuse unowned conflicts. Missing/stale cached state cannot override evidence.
Recovery revalidates sources and commits before projection, including equality
barriers after uncertain acknowledgements; it stops after state repair. Keep prior
reports immutable and recover current status independently of history.

Not included: new Phase 2 operator followup admission, automatic repair/retries,
conflict/oscillation/rubric resolution, version maintenance, public modes, external
transmission/apply-back, or complete 18.8/18.9 qualification.
