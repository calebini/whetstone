# Phase 2 conflict and oscillation reporting

Separately pinned standard horizontal, unversioned verified Phase 2 integration.
Requires the correction failure reporting contract and its dependencies. Preserve
legacy/bridge and suites without this pin. No new mode, retries, client invocation,
resolution receipt, operator admission, version stamping or source apply-back.

Replay deterministic normalized draft cycles only over committed promotions;
replay canonical feedback over consumed Phase 2 passes. Retain simultaneous draft
and feedback reasons. Use existing conflict identity/severity and the consecutive
(two) / cumulative (three) escalation tracker, including absent-round resets.
Oscillation-derived escalation produces a report immediately; only blocker-level
conflict halts. First re-addition continues under existing gates and budgets;
repeated re-addition stops. Freeze remains an explicit unresolved gate and does not
mutate drafts or remove findings. Promotion or missing feedback is not a resolution
receipt and cannot reset churn. No new intervening-resolution authority is invented.

Check D7 authority and incomplete-work recovery preconditions before terminal
selection. Runtime precedence remains timeout, clean convergence, blocker conflict,
oscillation stop, exhausted artifact handling, operator decision, profile budget.
A consumed final declaration review retains declaration validation/reconciliation
preconditions; clean convergence outranks signal halts, signal halts outrank budget
exhaustion. Unsupported rubric/authority maintenance is not silently resolved.
Nonterminal recommendations and historical reports alone cannot establish a halt,
cleanliness or convergence. Existing component owners retain independent gates.

Publish explicit immutable feedback, draft and terminal evidence under
rounds/phase2/signals/pass-N/{feedback,draft,terminal}. Feedback records bind the
original reviewed pointer; draft records bind the committed promoted pointer.
Retain all simultaneous detections in evidence and select the strongest diagnostic
for the compatibility oscillation report. Initial diagnostic terminal_state is
null. The separate terminal commit binds evaluated diagnostic copies carrying the
selected halt, together with the companion convergence failure report. Preserve original entry/configuration, exact consumed
review prefix, current pointer, rubric, real budget counts and final-review status.

Status is read-only. Publication and report/state recovery run under D8, synchronize
validated source and output dependencies, recheck sources before commit, and end
without clients. Current state is a namespaced projection of committed records;
root mirrors replace only exact owned bytes, with later reports taking precedence.
Terminal snapshots do not grant resume. Unknown claims, drift and tampering refuse.
Historical diagnostics survive later accepted promotions and clean/exhausted
closeout. Uncertain final state acknowledgement requires the same barriers on reentry.
