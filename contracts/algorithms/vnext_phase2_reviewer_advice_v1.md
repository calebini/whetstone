# Direct Phase 2 Reviewer advice v1

Operator decision, 2026-10-02: Phase 2 Reviewers hand classification guidance to
Whetstone directly alongside each review; human participation is for product,
authority, scope and other protected decisions. No routine advice-file handoff.

A new consuming suite pins this algorithm and vnext-phase2-rubric-response-v2.
Older suites retain their exact v1 envelope, prompts, result hashes and explicit
attachment behavior. Never infer the protocol from model output or a config edit.
The v2 response requires review, rubric_findings and classifications. There must
be exactly one classification item per feedback_id, including non-actionable
findings; an empty review requires an empty list. Extra, missing, duplicate or
unknown items and invalid authority citations refuse under existing bounded
Reviewer response validation. This creates no additional request or retry budget.

The Reviewer proposes classification, requested effects and authority/scope
citations. The orchestrator computes job, current draft, feedback path/hash and
bound authority/scope/invariant hashes from the committed request and canonical
feedback. A model-supplied run binding cannot replace them. The existing classifier
owns the effective classification; sensitive effects, policy, scope, invariants
and authority checks still override advisory editor_fixable claims. These checks
do not claim lexical proof of semantic intent; independent verification remains
required. Operator decisions remain separately authenticated artifacts.

The exact raw response and existing outcome/result journal retain provenance of
the complete response, including classifications. Advice is reproduced from those
bytes on every replay. After result consumption, the existing advice owner binds
that exact derived packet under D8 and repeats request/result/consumption source
barriers before publishing advice and its binding commit. A supplied or retained
attachment must equal the reproduced packet. No regenerated guidance, user-file
substitution, extra model call or changed successful-pass count is permitted.

Ordinary live Phase 2 processing performs this handoff automatically when a
consumed review needs correction or an operator decision, for first and later
passes, including source findings from declaration review. Clean reviews do not
need a correction attachment. Advice-only publication recovery binds the exact
active pass/request, rechecks selection under D8, repairs that attachment and stops
before correction admission. Read-only status/dry-run never publish advice.

Only independently admitted editor_fixable work reaches the Editor. Product or
authority decisions expose the existing exact operator context and stop before any
Editor invocation. Recording an operator response does not itself execute or
promote a candidate. Frozen contracts, legacy/bridge behavior, external source
approval, suite qualification and production activation are unchanged.
