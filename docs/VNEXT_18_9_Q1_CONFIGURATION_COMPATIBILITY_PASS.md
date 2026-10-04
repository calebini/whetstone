# Q1 configuration and compatibility delivery pass

Delivery pass 4 starts at `b947e77`, the committed source-operations pass.
This pass is **complete within the fixed inventory below**, committed in `c2849cd`.
Its checkpoint left one Q1 delivery pass: the [closure review](VNEXT_18_9_Q1_CLOSURE.md),
which now owns the current Q1 disposition. Public qualification and Q2–Q4 remain
incomplete. The verification narrative below describes this pass's pre-commit state.

## Fixed inventory and authority

The coordinating spec's config-selected verified-promotion release surface,
ratified Q1 command matrix and existing D8 owners govern this pass. No normative
amendment, new mode, provider transmission or real external source write is needed.

The new real-CLI matrix covers:

- Unknown, missing, null and conflicting mode/suite/package selectors; mixed
  bridge configuration and unsupported descriptor-bound settings.
- Config-relative package locators, corroborating CLI selectors and conflicts;
  duplicate JSON/YAML keys and the existing closed two-Ref selector block.
- Retained V mode with removed or missing config, refusal of new work without
  opt-in, edited selectors/packages/descriptors, and unsupported commands/controls.
- Phase 2 Ref shape, confined paths, exact bytes/hash, canonical JSON, schema and
  job/review bindings; configuration alone cannot authorize entry; a replacement
  configuration after binding refuses before entry or clients. Separate entry
  checks exercise pinned client identities, profile order, rubric bytes and input
  replacement immediately before the actual D8 fence.
- Empty or wrong-digest qualification for both fresh and retained roots.

Representative compatibility checks cover the existing legacy CLI and config
suites, public bridge opt-in/acceptance/continuation, reviewer-only admission and
review through scripted transport, and proposal-only bootstrap/review/proposal,
reentry and native scripted transport. These are bounded command checks, not the
full release regression inventory. Prior workflow-route coverage supplies focused
pins and target combinations; this pass does not repeat costly convergence runs.

## Changes and evidence

Evidence is retained under `rounds/vnext-18-9-q1-config-compatibility-001/`.
`inventory.json` fixes the batch scope; source snapshots and failures are retained.
A single bounded worker runs at 60% duty with a deadline and supervision lease.

The initial regression demonstrates invalid top-level selectors reaching legacy
configuration loading. Presence of the V-only mode/suite/Phase 2 keys now routes
to validation even when their values are invalid. This grants no permission and
leaves the earlier descriptor/package-only R/P interfaces intact. Canonical
non-object Phase 2 files and malformed retained descriptors now produce structured
refusals instead of uncaught attribute errors.

The red batch also had one overly strict test assertion: incomplete Phase 1 is
revalidated under the D8 fence. The corrected assertion permits that fence and
requires refusal with no file change or entry. That is a test correction, not a
relaxation of production prerequisites.

The first configuration batch passed all ten methods in 90.343s. The compatibility
batch completed 74 methods in 348.056s: 72 passed and two methods failed (four
assertions). Neither failure required a production relaxation:

- The mixed bridge/V cases expected an uncaught legacy exception. The corrected
  test requires structured V refusal, retains direct legacy-loader rejection,
  and still asserts no clients or runtime state.
- The new negative profile-order fixture reversed `strict/adversarial/strict`,
  reproducing the valid sequence. The runtime correctly admitted it. The fixture
  now swaps distinct profiles; the corrected method also checks input drift at
  the fence. The failed method receives no passing credit.

The final focused recheck covers those two methods and the Phase 2 Ref matrix,
including a schema-valid foreign job identifier. Production bytes have remained
unchanged since the original ten-method pass. All three final methods passed in
111.299s. Across these runs, **84 distinct methods pass**, including eleven new
methods. This is per-method reconciliation, not a claim that the original
74-method compatibility batch was wholly green.

## Final verification and handoff

`verification.json` lists exact invocations, successful method identities, failed
attempts, source/log hashes and evidence limits. Source cohorts 001 and 002 use
final production bytes. The changed Phase 2 Ref method, added entry-barrier method
and mixed-selector bridge assertion were rechecked on final test sources; other
credited methods are unchanged. The red batch has no passing credit. No previous
workflow/source campaign is counted as fresh evidence here.

Targeted compilation and `git diff --check` pass. Both contract suites validate
with their unchanged digests; all four production qualification maps remain empty.
All workers exited and the bounded-worker lock is available. HEAD remains
`b947e77`, the index is empty, and unrelated notes and the pre-existing audit
retain their baseline hashes. No new authority decision was needed.

The next pass is **Q1 closure review**: reconcile all seven acceptance rows and
the supported-command matrix with exact evidence, review the final adapters and
fix concrete findings. Do not infer Q1 completion from this campaign alone. Q2
independent P0 obligations, Q3 exhaustive qualification and replay performance,
and Q4 separately authorized live soak/activation remain open. Known slow history
replay is unchanged. No push, activation, real provider call or real external
specification write occurred; source writes in compatibility tests used only
disposable fictional fixtures.
