# Verified Phase 2 Reviewer failure lifecycle (unactivated)

Separately pinned extension of the existing Phase 2 sequence/client and closeout
contracts. No public mode, provider adapter, generic resume or new retry allowance.
The exact immutable Reviewer request and its existing two-slot journal own attempts.
Replay entry, configuration, rubric, current verified lineage and all predecessor
request/result/consumption evidence before reporting or continuing. Invalid roots
and persistence/ownership errors propagate; never manufacture successful reports.

Classify known timeout as HALTED_CLIENT_TIMEOUT, other failed/interrupted outcomes
as HALTED_ARTIFACT_INVALID with their exact diagnostic cause. Retained valid output
is completion work, not another client call or a new failure. An invocation marker
without response is interruption, not proof of timeout. A single shape failure with its retry still available is not an exhausted failure
and does not publish a terminal. Closed invalid-review and
two-slot exhausted journals grant no further invocation. One remaining slot is
available only by existing explicit component continuation with identical inputs.

Persist immutable reports under the selected request's execution/failures/attempt-N
(the failed prefix length, not a new attempt counter). Bind request, entry, current
pointer, configuration and every outcome. Publish the full convergence failure
report, artifact-validation diagnostic, terminal-report-v2 and bound rubric manifest
before one failure commit. Retain the first validated failure report timestamp and
reproduce all semantic fields on replay. No draft authority, profile budget,
consumption credit, candidate or declaration is created by failure publication.
The last valid Phase 2 feedback and current-lineage residuals remain evidence;
failed raw output never becomes canonical feedback. Final verification is not_run.

Historical reports reproduce from the original request base, predecessor profiles
and failed outcome prefix. They are never removed or rewritten after continuation.
Only the current last request with no valid retained review has an active failure.
A namespaced run-state projection holds active and historical report references;
status derives both from validated evidence, never from the cache. Successful
result completion supersedes the failure without consuming that result again.

Separate recovery repeats source and committed report barriers, projects the latest
owned error/failure report, then updates namespaced state while preserving legacy
fields. Replacement requires exact old bytes matching a committed historical report,
a canonical immutable new snapshot, transition validation and D8 conditional pointer
replacement. Missing projections are create-only; unowned bytes refuse. The fixed
materialization whitelist is unchanged. A later committed final-budget failure may
supersede this failure-report projection; clean convergence retains old reports as
history. A recovery invocation stops before a client, including after lost final
state acknowledgement. Raw client execution publishes failure evidence but does
not recover its projections. Reentry completes pending publication and requires separate explicit state recovery
before any explicitly allowed remaining attempt. Other suites keep their original behavior.
