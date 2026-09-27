# Verified Phase 1 explicit budget extension v1 (internal)

Implements the scheduler's Budget-Extension Resume rules without changing the
descriptor or immutable review configuration. Requires explicit positive added
rounds per profile, a committed exhausted Phase 1 closeout, current mirrors and
D8 ownership. Pending work, decisions, stable completion and Phase 2 entry do
not qualify. Focused work retains its selected-profile and non-acceptance limits.

Publish a chained immutable extension record binding the configuration, exact
base, previous extension and exhausted closeout. Derive the scheduler event ID
from its specified canonical fields, excluding its timestamp. Reconstruct each
profile budget as max(previous budget, completed reviews) plus the grant. Replay
each grant only at its original exhausted round boundary; it cannot authorize
earlier overspending. Reviewer claim v3 binds the exact grant references applicable
to that round; later grants cannot rewrite earlier claims or request attempts.
Preserve original journals, synthetic rounds and counts.

The extension record commits the grant. Project its event into run-state
budget_extensions before any appended client; lost acknowledgement permits only
exact recovery of that grant. Repeated publication before a completed appended
round reuses the grant and cannot reset logical request attempts. A pending
request still requires its existing explicit technical continuation. Preserve
historical closeouts; closeout v4 binds the complete grant chain. Derived status
clears superseded terminals and reports effective budgets. Missing/corrupt grant
dependencies refuse; repeat their D8 barriers before dependent work and recovery.

No original configuration replacement, implicit budget, new generic resume,
candidate-finality bypass, public activation or source-write authority.
