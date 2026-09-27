# Verified Phase 2 reviewer-only closeout v1

Internal opt-in extension requiring the declaration-stage source-correction v1
contract. It implements the bounded optional closeout from the scheduler spec.
It grants no public mode, Editor work, candidate admission or budget extension.

Eligibility is reproduced from committed ordinary review consumption, current
verified lineage and verified resolution receipts: the configured sequence has
ended, a clean convergence-acceptance review verified the current declaration,
zero unresolved in-scope blockers/majors or rubric gaps remain, at least one
distinct required profile is not clean on this lineage, and no configured profile
exhausted its budget with residuals. Earlier declarations or clean results on a
different draft cannot establish eligibility.

The immutable closeout plan contains the unverified distinct profile names in
configured order. Each receives at most one logical Reviewer request, with the
existing two-slot technical request protocol. Request/consumption v5 distinguish
this work from ordinary budgeted reviews. Closeout does not increment configured
step counters or permit Editor calls. Requests retain the exact declaration
package already reviewed on this current lineage. Normal review_only round-N
artifacts reproduce the bound draft, profile, request and feedback; publication
is fenced, recoverable, and precedes receipt consumption.

A clean result verifies only its profile on the current draft. All required
profiles must be clean before declaration acceptance and CONVERGED. Any in-scope
blocker/major result stops closeout and produces TARGET_NOT_REACHED with remaining
verification debt, subject to the existing earlier halt/intervention precedence.
No subsequent closeout request or source correction is admitted from that result.
Source barriers, immutable-prefix recovery and post-write ownership validation
apply. Older suites and their artifacts remain unchanged.
