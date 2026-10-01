# Bounded audit of the Q1 amendment proposal

Date: 2026-10-01. Baseline: `fb57a2406074520630fa99242161d9662e18653b`.
Verdict: **needs revision before ratification/implementation** — three P2
specification/interface findings. No critical architectural defect was identified
within this pass. This is a local static review, not an independent model review,
Whetstone `audit-change` execution, convergence verdict or release qualification.

## Scope and method

Reviewed the [proposal and matrix](../VNEXT_18_9_Q1_PROPOSAL.md), its exact
[seven-file amendment patch](../VNEXT_18_9_Q1_SPEC_AMENDMENTS.patch), the relevant
existing D7 rules, approved M3/M4 decisions, M5 handoff and underlying command,
Phase 2 continuation and source-write owners. Checked for authority changes,
cross-document contradictions and gaps in the proposed command contract.

The proposal and patch match their preparation record. All seven authoritative
files and unrelated notes retain their recorded hashes. Patch application check
and diff whitespace check pass. These mechanical checks do not resolve the
semantic findings below. No runtime tests or nested client calls were run; no
provider transmission, source writes, activation, commit or push occurred.
The proposal, patch, implementation plan, specs and runtime were not edited.

Raw input hashes, reviewed proposal/patch snapshots and check results are under
`rounds/vnext-18-9-q1-bounded-audit-001/`; the directory is ignored by Git. The
reviewed proposal SHA-256 is
`dc6e51e314364054c6ffdf1c5e99f2b78187e2d61e7426e83ef6b1368d8d5108`;
the reviewed patch SHA-256 is
`be4a516f875b42d333bf9c50df1f6a57870ece89e120df4c24eaa457e2ebcaaa`.

## Q1-A1 — P2: publish the actual technical-continuation matrix

Location: proposal line 88; patch lines 234–239 (scheduler command execution),
repeated in the proposed Quickstart matrix.

The draft promises “only reported repair or explicit technical continuation” and
reserves `--continue` for Phase 1, but does not enumerate the published
role/phase/gate combinations, the command that invokes each, or the stopping
point after successful continuation. The existing
[D7 continuation rule](../specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#retry-decisions-and-continuation)
requires that explicit publication. Referring to whatever the implementation
reports as supported makes this part of the release contract circular.

Concrete case: a Phase 2 Reviewer timeout has a remaining attempt and fully
repaired failure projections. The internal owner advertises
`explicit_phase2_reviewer_continuation` and requires `continuation=True`.
The proposed matrix does not say whether plain `resume` performs that one call,
how it binds the exact pass/request, or whether a `live-phase2` rerun must refuse
until that explicit continuation occurs. Those choices determine whether a
nominal recovery invocation spends a client allowance. First-pass and later-pass
owners also have different entry points.

Evidence: `src/whetstone/vnext_verified_phase2_failure.py:115` and `:275`,
`src/whetstone/vnext_verified_run.py:191` and `:257`, and
`src/whetstone/vnext_verified_phase2_sequence.py:472`. The separate correction
failure owner does not grant generic correction resume merely because the
Reviewer owner supports continuation.

Bounded correction: add a finite subtable naming each supported repair and
technical-continuation route, its exact evidence selector, invocation, client
permission and end condition. Explicitly refuse the remainder. Reuse the existing
owners and allowances; do not expand Phase 2 resume. Add acceptance cases for
repair-only reentry, one eligible Reviewer continuation, exhausted refusal and
ordinary live-command refusal to retry a halted request implicitly.

## Q1-A2 — P2: separate source-write eligibility from historical recovery

Location: proposal line 94; patch line 480 (combined strop/apply-back row).

The shared scope “Complete eligible V convergence” covers review, apply and
recovery together. It conflicts with the copied M4 rule allowing recovery of a
retained write after the current pointer advances (patch lines 314–319).
Historical reconciliation must not require the current run to qualify for a new
write. Read-only assessment must also remain able to explain ineligibility.

Concrete case: an attempted source replacement retains its approved intent, but
the run's current pointer subsequently differs from the approved pointer. The
new source-write assessment must fail; readback and receipt recovery must still
be able to validate the retained historical intent without applying it to the
new draft. A shared CLI eligibility preflight would block the M4 recovery path.

Evidence: [M4 approved uncertainty policy](../VNEXT_18_8_M4.md#approved-policy--one-bounded-ratification),
`src/whetstone/vnext_apply_back.py:106` (historical intent binding), `:135`
(status), `:164` (current apply) and `:216` (recovery). Only current apply calls
the fresh assessment path. Existing source-drift tests also distinguish historical
completion from current source agreement; they were inspected, not rerun.

Bounded correction: split the row into read-only assessment/status, fresh
apply/retry, and retained-intent recovery subcases. Require current convergence
and exact current approval for a new write; require valid retained historical
evidence and exclusive access for recovery, with no replacement permission.
Carry the pointer-advanced and source-drift distinctions into CLI acceptance.

## Q1-A3 — P2: distinguish the approval packet from review output

Location: proposal lines 115–117; patch lines 488–490.

The proposed stdout contract returns only the existing closed assessment and
invites the operator to save it as the exact approval file. That object cannot
represent the diff, blockers or recovery information required for read-only
review. The implementation already distinguishes a review result from its
optional approval subject: `ApplyBack.review()` returns an envelope containing
`eligible`, `blockers`, `assessment`, and either a diff or recovery information.
Blocked review can legitimately have `assessment=None`.

Evidence: `src/whetstone/vnext_apply_back.py:92` and
`contracts/schemas/vnext_apply_back_review_v1.schema.json`. The latter forbids
additional properties and has no `diff`, `blockers` or `recovery` fields. The
copied M4 review rule explicitly requires diff, evidence and blocker reporting.
Printing only the packet loses required information; printing the existing
envelope and saving it verbatim produces an invalid approval input under the
proposed instructions.

Bounded correction: define the review-result output separately from the canonical
approval subject. Specify how the operator extracts/saves the exact assessment
and which bytes `--approval-hash` covers. Preserve the frozen assessment schema
and read-only behavior. Cover eligible, blocked and existing-intent output, plus
the successful review-to-approval round trip, in Q1 command tests.

## Preserved boundaries and disposition

The proposed config opt-in does not override an admitted descriptor or qualify a
suite. The approved M3/M4 six-rule blocks are carried forward verbatim. Version
maintenance remains before verification; Phase 2 entry stays distinct. Frozen
suites, D8, legacy/bridge behavior and independent Q2–Q4 gates remain protected.
The three findings concern public interface precision, not a need to redesign
the verified-promotion engine or add milestones.

Recommended next action: correct these three points together in the review-only
proposal/patch, refresh its preparation evidence, and perform one focused recheck
of those changes before asking for ratification. No finding has been patched in
this audit, and no normative publication or implementation approval is inferred.
