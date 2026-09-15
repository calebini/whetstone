# Runtime operator follow-up and second promotion checkpoint

This bounded 18.7 checkpoint exercises the production runtime path introduced in
`95c75b2`. It adds integration tests around existing owners; runtime and contract
bytes are unchanged. Validation results are recorded separately below. It does
not complete 18.7, publish a shipping suite or enable a mode.

## Journey under test

| Reviewer round | Base pointer | Candidate and outcome |
|---|---|---|
| 1 | Seed, ordinal 0 | Parent is finally rejected with an outstanding interpretation question. |
| 1, explicit follow-up | Same ordinal 0 | An explicit answer and separate child selection produce a distinct candidate, which is independently verified and promoted to ordinal 1. |
| 2 | Committed ordinal 1 | A new runtime review and canonical round lead to a third candidate, independently verified and promoted to ordinal 2. |
| 3 | Committed ordinal 2 | A clean runtime review observes the new base; no additional candidate or promotion is created. |

The complete journey uses three Reviewer, three Editor and three Verifier calls.
Operator answer publication, child selection and reopening consume no client
calls. Round records come from the production publisher and the two pointer
commits come from the production promotion owner. Fixture setup supplies only
initial inputs, a test-only suite and scripted client responses.

Assertions bind the child to the original admitted editing plan, preserve all
existing parent candidate evidence and its outstanding historical question,
compare the Editor and Verifier interpretation packets, and preserve immutable
root selectors and the first canonical round record. The final fresh subprocess
reconstructs both promotions and all three candidates without clients or writes.
A superseded parent's answer cannot authorize new work.

## Selected recovery and refusal boundaries

The tests interrupt after an answer response and after a child admission, reopen
the run, and finish the original answer/selection without invoking clients.
Repeated selection retains identical bytes; the selected child then completes
independent verification and promotion.

A separate two-promotion runtime journey interrupts after the second current
pointer replacement. Reopening repairs the committed mirrors and ends that
invocation before another Reviewer call. Repeating promotion cannot allocate a
third ordinal. The next review uses ordinal 2, and tampering with the original
round-1 raw Reviewer output prevents further admission even after both promotions.

Explicit decline and stale answer bindings refuse child selection. Interpretation
answers have no authorized editing effects. Rejected bytes remain rejected; an
answer alone neither promotes them nor starts another review.

## Evidence and remaining work

**All four new integration tests pass.** The [validation record](audits/VNEXT_RUNTIME_FOLLOWUP.json) preserves commands, exact log/source hashes, test identities and source-version limits. The final journey/refusal pair and the recovery pair were executed separately. This does not constitute a full regression run.

These cases are bounded integration evidence. The interruptions are injected
exceptions around real publication, not physical power-loss tests or a complete
process-death campaign. P/bridge behavior is preserved by unchanged runtime bytes;
the prior compatibility evidence remains separately scoped. No live provider was
called and no full regression was rerun for these test-only additions.

Next within 18.7: map the remaining registration, verification, promotion and
materialization fault boundaries to current tests and retained evidence; implement
only uncovered high-priority cases. Include process termination and competing
owners at the new runtime boundary where component-only evidence is insufficient.
Repeated interpretation follow-ups, wider profile combinations and all interruption prefixes are not qualified by the single representative child/two-promotion journey. Complete consuming-suite qualification and reconcile the 18.5–18.7 acceptance map
before declaring slices complete. D8 design/audit closure stands. 18.8 scheduler,
Phase 2 and apply-back work, and 18.9 full release qualification/activation remain
outside this checkpoint.
