# 18.7 representative runtime publication prefixes

Date: 2026-09-18. Starting checkpoint: `250ec93`.

This bounded slice adds three runtime journeys for the remaining representative
publication gaps identified by the boundary reconciliation. Each uses canonical
Reviewer history through `open_verified_run`, with promotion 1 already committed
and a genuine second round. Existing component prefix matrices retain their
separate scope.

**Three distinct test methods now pass, with no skips.** The initial module run
(248.203 seconds) passed the candidate-pointer and intent cases but
failed a registration-test assertion. The assertion incorrectly counted legitimate
proposal-handoff files as registration artifacts. It now captures the registration
boundary after handoff and checks that handoff uses promotion 1. The corrected
registration method passed a targeted rerun (50.42 seconds).

The original failing run and its exact test source are retained. AST comparison
confirms all other methods and helpers are unchanged; those two passing tests
were not repeated. This is three distinct passing methods across two runs,
not a clean full-module rerun. No runtime fix was required; runtime and contract
bytes remain unchanged from `250ec93`. No broad regression was
repeated for this test-only checkpoint.

## Exact cases

| Runtime case | Injection and required result |
| --- | --- |
| Early incomplete registration | Raise `OSError` after successful publication of round 2's registration preparation, before candidate artifacts. After the legitimate completed proposal handoff, only that preparation is added at the candidate-registration boundary. Read-only status reports registration recovery required and retains candidate 1 as latest. Work routes wait; explicit recovery refuses missing artifacts; promotion refuses the orphan. No candidate bytes, initial event, creation-2 commit, later clients or global promotion are manufactured. |
| Final candidate-pointer acknowledgement loss | Execute the real rename of `candidate_verification_current.json` for decision 2, then raise `OSError`. The adapter reports typed uncertainty with the exact pointer path/hash and invalidates ownership before caller cleanup. Fresh runtime reconstruction recognizes the committed final verified decision and routes to promotion, without another Verifier call or global pointer change. |
| Early promotion preparation | Raise `OSError` after successful publication of the second promotion intent, before event 4 or the ordinal-2 snapshot. Fresh runtime retains the sole prepared candidate and blocks new review/Editor/Verifier work. Promotion reentry uses the existing intent's timestamp even when given a later timestamp, then publishes event, snapshot and exactly one second promotion. |

The candidate-pointer case also fails its existing-byte synchronization during
promotion. The failure must poison ownership and stop before any promotion
intent or snapshot is created. Another fresh owner successfully synchronizes
that exact candidate pointer before publishing the intent. Its new promotion
timestamp may differ from the original verification timestamp; the original
verification decision and evidence remain byte-identical.

These are three test methods/journeys with four injected boundaries: two
exceptions after completed immutable publications, one real rename
acknowledgement loss, and one real adapter synchronization-flush failure.
They are not killed-process or physical power-loss tests.

## Authority, evidence and client counts

Early registration deliberately remains incomplete and unregistered. Missing
prepared artifacts are an artifact-invalid refusal, not a supported automatic
resume path. Repeated inspection and attempted work/recovery preserve the exact
partial package and prior authority. The test leaves the orphan intact; no
manual remediation path is added. Reviewer/Editor totals remain two each and
Verifier total remains one from the first promotion.

The candidate-pointer and intent cases each finish with promotion 2, exact
committed mirrors, preserved original history and no third candidate, review
claim or promotion. Repeated promotion is ineligible and fresh readback changes
no files. Each retains two calls per scripted role. No external provider is used.

The [registration contract](../contracts/algorithms/vnext_candidate_registration_v1.md)
requires incomplete-orphan refusal. The [V semantic contract](../contracts/algorithms/vnext_verified_semantics_v1.md)
separates candidate-local verification from global authority. The
[promotion contract](../contracts/algorithms/vnext_verified_promotion_v1.md)
requires candidate-marker synchronization before preparation and exact reuse
of the sole claimant and prepared timestamp.

## Validation and handoff

The [machine-readable record](audits/VNEXT_RUNTIME_PUBLICATION_PREFIXES.json)
binds both commands, their source manifests, passing test identities and log digests. Raw evidence
is retained under ignored `rounds/vnext-runtime-publication-prefixes-001/`.

```sh
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_runtime_publication_prefixes -v
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_runtime_publication_prefixes.RuntimePublicationPrefixTests.test_incomplete_registration_preparation_refuses_without_manufacturing_artifacts -v
```

These representative tests address the finite three-item runtime gap list from
the preceding reconciliation. They do not repeat every component prefix at
runtime or establish every process-death/flush permutation. The source and log
of the prior decision-reference checkpoint were verified against its record;
its counts are not added to this run.

Next: consolidate the 18.7 acceptance map against the implementation and the
accumulated component/runtime evidence. Distinguish implemented behavior from
remaining consuming-suite qualification and list only concrete unresolved
requirements. Add another fault test only if that acceptance mapping identifies
a missing required proof. This checkpoint alone does not close Batch C evidence
reconciliation or complete 18.7, and it does not authorize a release campaign.

D8 design/audit closure stands. The broader 18.5–18.7 acceptance and consuming
qualification gates remain open. No 18.8–18.9 implementation, shipping activation,
external transmission, external specification apply-back or push is included.
