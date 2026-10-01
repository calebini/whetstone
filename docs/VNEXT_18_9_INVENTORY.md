# 18.9 finite qualification inventory

Date: 2026-10-01. Inspected commit: `648a6ead53efafaf40e5c41f859861a010ec7423`.

**The inventory is complete; release qualification has not been executed.** A
fresh detached local checkout supplied the code, specifications and tests. All
1,145 tracked file hashes remained unchanged during inspection. There were no
product tests, model calls, public activation, normative edits, commits or pushes.
The main workspace's unrelated notes edit is preserved.

The candidate leaf has **22 P0 scenarios**: 15 map to existing executable
coverage, five have partial/composed coverage, one lacks the exact historical
golden fixture, and one lacks a second implementation. These are inventory
classifications, not 15 release passes. All 22 remain release-unqualified until
they pass against the selected version-pinned consuming implementation.

The [machine-readable inventory](audits/VNEXT_18_9_INVENTORY.json) records all
64 P0 method links, exact test-file hashes, audit mentions, separately verified
retained passing logs, historical source differences and all 13 ratification-delta
rows. A named test or audit mention is not credited as a passing execution.

## What the clean checkout established

- Only `vnext-contracts-1` is registered. Its manifest references 79 files; all
  referenced hashes match. This verifies package integrity, not fixture execution.
- Proposal, semantic and semantic-follow-up shipping qualification maps are empty.
- Public dispatch advertises reviewer-only and conditionally proposal-only work.
  It has **no V route into `VerifiedRun`**. The internal M1–M5 API is present;
  exposing its qualified CLI/status/recovery/strop paths needs integration, not
  merely a flag change. Existing public strop refuses vNext roots.
- D8 remains macOS/local APFS. Its 32 storage methods and the existing registry,
  verification, promotion and runtime process/prefix modules provide a concrete
  qualification set. Other filesystems and physical power loss receive no credit.
- All 657 substantive files in the M5 closeout/journal manifests match this
  checkout. Their other three entries are ignored `.DS_Store` metadata, absent
  from a clean checkout. Older evidence has genuine source differences recorded
  separately; its previous passing results are not relabeled current.

The static scan found 1,474 declared test methods. This excludes inherited or
dynamically generated tests and is not an expected full-suite execution count.
No new implementation defect was demonstrated by this inventory.

## P0 map

The table links a representative test for each row; the JSON contains all mapped
methods and their retained evidence. “Mapped” means existing executable assertions
cover the named boundary at their stated component/runtime scope; a final
consuming-suite run is still required. “Partial” names the exact composition or
trigger that remains unproved.

| Requirement | Inventory status | Representative executable coverage | Remaining qualification work |
| --- | --- | --- | --- |
| P0-01 — Destructive Replacement | partial | [test_text_corruption_patch_markers_and_placeholders_fail_even_with_correspondence](../tests/test_vnext_candidate_validation.py#L137) | Add literal six-section replacement and assert prior pointer/spec.md survive; current placeholder and rejection checks are related coverage. |
| P0-02 — Unrelated Enum Or Table Loss | partial | [test_missing_enum_member_has_its_exact_removed_base_unit_id](../tests/test_vnext_inventory_diff.py#L53) | Join unrelated enum and table-row loss to registered rejection/no-promotion with exact removed IDs; current tests demonstrate component facts. |
| P0-03 — Forbidden Compatibility Introduction | partial | [test_prospective_compatibility_introduction_is_forbidden_but_cleanup_is_distinct](../tests/test_vnext_classification.py#L40) | Add the candidate-introduced compatibility scenario with prospective authority and older implementation context; classification is not this joined negative fixture. |
| P0-04 — Legitimate Product Decision | mapped | [test_missing_advice_or_unresolved_choice_stops_before_editor_and_writes](../tests/test_vnext_mutation_admission.py#L62) | Existing zero-call/response-binding checks; qualify against the selected consuming suite. |
| P0-05 — Partial Success With Regression | partial | [test_useful_fix_with_unrelated_regression_cannot_pass_but_can_validly_reject](../tests/test_vnext_semantic_protocol.py#L141) | Add exact three-resolved/one-regression fixture and isolated reduced patch reassembled from immutable base with full verification; existing rejection and repair journeys cover pieces. |
| P0-06 — Invalid Output Or Timeout | mapped | [test_one_shape_retry_keeps_identical_inputs_and_precise_errors](../tests/test_vnext_proposal_retries.py#L19) | Existing retry/timeout checks; preserve explicit continuation and original base under the release suite. |
| P0-07 — Verification Budget Exhaustion | partial | [test_registered_creation_is_unverified_and_replay_reuses_timestamp_and_ordinal](../tests/test_vnext_candidate_registry.py#L120) | No explicit run token/time-budget exhaustion fixture found before/after registration. Retry-slot/profile budgets differ. Demonstrate caller budget-stop boundary; clarify ownership if implementation requires a new policy. |
| P0-08 — Exact Resume | mapped | [test_promoted_recovery_does_not_validate_a_later_candidate_or_next_intent](../tests/test_vnext_verified_materialization.py#L157) | Existing prefix and runtime recovery coverage; refresh final consuming graph, without generic Phase 2 resume. |
| P0-09 — Candidate Identity Map Binding | mapped | [test_missing_committed_map_is_invalid_even_when_candidate_bytes_survive](../tests/test_vnext_candidate_registry.py#L332) | Existing map bindings at registration/context/history/apply; qualify declared consumers. |
| P0-10 — Candidate Ordering And Orphan Recovery | mapped | [test_latest_uses_creation_ordinal_not_round_timestamp_or_identifier](../tests/test_vnext_candidate_registry.py#L137) | Retain exact prefix/ordering coverage; no new generic orphan batch. |
| P0-11 — Verification Decision Commit Recovery | mapped | [test_every_pre_pointer_prefix_is_ineffective_and_recovery_reuses_timestamp](../tests/test_vnext_semantic_decisions.py#L87) | Existing decision/event/pointer prefixes and runtime uncertainty; execute on release sources. |
| P0-12 — Historical Recurrence Fixture | missing exact fixture | [test_text_corruption_patch_markers_and_placeholders_fail_even_with_correspondence](../tests/test_vnext_candidate_validation.py#L137) | No checked-in historical destructive first-round golden fixture located in tests/contracts. Locate original retained input/output and freeze a scrubbed exact fixture with provenance; finding-recurrence tests do not satisfy it. |
| P0-13 — Cross-Implementation Determinism | missing second implementation | [test_published_suite_and_all_fixed_vectors](../tests/test_vnext_contracts.py#L21) | One Python implementation and fixed vectors found. Two processes are not two implementations. Need an independent bounded reference implementation for candidate/map/hash and persisted selection/disposition, or an explicit normative decision. |
| P0-14 — Normative Weakening Without Deletion | mapped | [test_rfc_weakening_is_detected_even_when_the_editor_claims_clarification](../tests/test_vnext_inventory_diff.py#L47) | Existing weakening/authorization failure and no-Verifier gate; qualify consuming suite. |
| P0-15 — Stale And Overlapping Patches | mapped | [test_stale_bindings_and_forged_ids_reject](../tests/test_vnext_proposals.py#L88) | Existing stale base/target and overlap refusal; preserve unchanged authority in qualification. |
| P0-16 — Markdown Parser Edge Cases | mapped | [test_fences_duplicates_preamble_and_exact_subtree_hashes](../tests/test_vnext_admission.py#L252) | Existing parser/normalization/escaped-table cases; pin parser and assembler versions. |
| P0-17 — Verifier Failure | mapped | [test_invalid_semantic_output_is_nonfinal_and_cannot_retry](../tests/test_vnext_semantic_run.py#L151) | Existing technical-failure/uncertainty/operator cases; scripted judgment is not live-soak evidence. |
| P0-18 — Promotion Crash Recovery | mapped | [test_all_precommit_prefixes_reuse_claimant_and_timestamp](../tests/test_vnext_verified_promotion.py#L145) | Component prefix matrix plus real process deaths/runtime representative; no physical power-loss or arbitrary fault cross-product claim. |
| P0-19 — Concurrent Promotion Preparation | mapped | [test_two_verified_candidates_select_latest_with_either_process_holding_first](../tests/test_vnext_verified_concurrent_selection.py#L103) | G1 covers both lock-winner orders; retain reservation/conflicting-prefix evidence, not cross-implementation credit. |
| P0-20 — Promotion Ordinal Continuity | mapped | [test_two_successive_promotions_use_the_production_pointer_owner](../tests/test_vnext_verified_promotion.py#L285) | Existing continuity/corrupt ancestors plus separately scoped M5 four-promotion evidence. |
| P0-21 — Decision Staleness | mapped | [test_stale_binding_unknown_targets_and_cross_section_grants_fail_before_writes](../tests/test_vnext_operator_decisions.py#L87) | Existing stale base/authority/effect checks; qualify consuming suite. |
| P0-22 — Changed External Source | mapped | [test_stale_source_approval_and_corrupt_lineage_refuse_before_intent](../tests/test_vnext_apply_back.py#L146) | M4 source guards/promoted integration exist; public strop and its normative amendment remain gated. |

**S-01 — Valid simplification:** the plan additionally requires positive
simplification coverage. Existing deterministic merge and semantic merge/split
methods are mapped in the JSON. Include their positive vectors in the release
campaign; a shorter candidate is not automatically a preserving candidate.

The one mapped method without an individually passing log in the packaged
selection is `test_two_successive_promotions_use_the_production_pointer_owner`.
Its code is present; P0-20 also has pointer-history checks and M5's whole
four-promotion verdict. This inventory does not invent a pass for that method.

## D8, compatibility and authority

Reuse the existing D8 tests for root/lock identity, competing/paused/dead owners,
stale/forked tokens, client descriptor inheritance, immutable publication,
conditional pointer replacement, uncertain flush/rename, complete reads and
read-only status. Registration/verification/promotion tests cover persisted
prefixes; runtime tests exercise representative actual process deaths. G1's
latest-of-two candidate selection with either lock-winner order is already
implemented and has retained evidence. Do not recreate that proof or prescribe
an arbitrary every-fault × every-route product. Qualification must distinguish
injected failures, actual process termination and untested physical power loss.

The compatibility inventory names existing legacy CLI/live/resume/apply modules,
bridge modules, reviewer/audit/sweep modules and proposal/semantic command
modules. Their existence and earlier passes do not supply a current full-suite
verdict. The final campaign must record discovered tests, actual passes, skips,
failures, Python/platform and exact schema/algorithm/client versions.

All 13 rows of the candidate leaf's ratification-delta map remain explicit in the
JSON. Existing coordinating/D6, scheduler D7 and scope-decision amendments are
present; they must be reconciled with the delivered consuming surface rather
than treated as absent or automatically complete. M3 metadata attribution and
M4 source-write policy were approved internally, but their coordinated normative
publication is still pending. Full public route support and operator guidance
must match the new consuming suite. Frozen suite 1 must not be rewritten.

## Finite remaining packages

| Package | Deliverable and exit condition |
| --- | --- |
| Q1 — Release contract and disabled public integration | Reconcile the 13 authority surfaces; prepare the authorized M3/M4 amendments and a new immutable consuming suite; integrate explicit V command/status/recovery/strop routes with activation disabled. Exit with one supported route matrix, exact pins and scripted positive/refusal command journeys. |
| Q2 — Seven specific P0 gaps | Complete P0-01/02/03/05 composed negative fixtures, P0-07 budget-stop behavior, P0-12 the original recurrence golden fixture and P0-13 independent implementation comparison. Include positive simplification. Exit with exact executable assertions/expected outputs for every row. |
| Q3 — Replay performance and deterministic qualification | Use the recorded one/four-promotion profiles to bound optimization, then run affected checks and the fixed P0/D8/process/CLI and complete regression campaign on final sources. One supervised worker, explicit skip/failure accounting, no redundant passing cohorts. Exit with reproducible timing and a release performance disposition. |
| Q4 — Authorized live soak and activation | After deterministic gates, separately authorize exact provider payloads, run an isolated soak and inspect successful/rejected proposals. Publish accurate operator guidance and decide activation explicitly. No real source apply-back or push is implied. |

These are finite qualification work packages, not estimates of turns or a new
open-ended implementation series. No full campaign should run before the Q1/Q2
sources settle. No public activation is authorized by the inventory.

**Decision before P0-13 implementation:** the current specification requires two
conforming implementations. The recommended bounded approach is an independent
reference implementation of candidate assembly/map/hash and persisted
selection/disposition rules sharing fixed inputs. If that is not wanted, bring
one explicit normative amendment decision; a second process of this code or
existing golden outputs do not satisfy the current wording. Do not build a second
whole Whetstone scheduler merely to satisfy this comparison.

P0-12 also requires locating the actual historical recurrence input/output before
claiming a faithful golden replay. P0-07 needs a concrete caller budget-stop test;
retry slots and profile extensions are not token/time-budget proof. If that work
would invent a new accounting policy, resolve its owner before coding it.

## Evidence and checkout lifecycle

The task preserved 387 explicitly referenced evidence files (9,802,241 raw bytes)
from 16 committed audit records. All supplied recorded hashes match. The archive,
manifest, source/test indexes and inventory scripts live under
`rounds/vnext-18-9-inventory-001/` in the main workspace. The tracked JSON contains
the archive digest. This is the selected evidence needed for the inventory, not
an assertion that every historical audit's transitive artifact graph was copied.
Only inert evidence was copied; no D8 writable run was relocated or rebound.

The temporary checkout and its temporary evidence copy **have been removed**
after preserving the report, JSON, manifest and archive, verifying every archived
file hash, and confirming that the checkout was unchanged. Cleanup is recorded
in the JSON; no temporary worker or product test was started. `rounds/` remains ignored, so a future machine needs this
archive as well as the committed source/docs. The user authorized the inventory documentation
checkpoint on 2026-10-01; no other checkout or user file was removed.
