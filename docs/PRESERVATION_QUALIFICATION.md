# Preservation bridge qualification

This record maps slice 18.1's integrated implementation and acceptance checks to executable evidence. All clients in these checks are scripted; operator identities and approvals are fictional fixture inputs. Public configuration remains gated by `PRESERVATION_BRIDGE_QUALIFIED = False`. Qualification does not grant permission to run live models or activate vNext.

## Current verification

All 507 distinct tests pass: a clean 504-test full discovery run plus three qualification tests added after that discovery; the strengthened padded-loss assertion also passes its final recheck. This includes 208 preservation tests. The 32-test focused runtime/consumer suite and ten retained journeys pass. No live model calls. The qualification module adds 17 tests to the previous 490-test checkpoint. Logs, exact test-inventory accounting and retained journeys are in `rounds/preservation-qualification-001/`, including `validation.json`, `results.json` and `working-tree-files.json`. The working tree is based on `6da1aa4`; no commit or push was made.

Reproduce from the repository root:

```sh
PYTHONPATH=src:tests python3 -m unittest discover -s tests -v
PYTHONPATH=src:tests python3 -m unittest test_preservation_qualification -v
```

The checked-in fictional inputs are in [the toy corpus](../examples/fixtures/preservation_bridge/README.md). Tests do not depend on ignored historical run artifacts.

## Implementation evidence

The identifiers I1–I11 follow the implementation checklist order in [the plan](../IMPLEMENTATION_PLAN.md#181-current-runtime-preservation-bridge). Test modules below live in `tests/`.

| Check | Implementation and executable evidence |
|---|---|
| I1: closed contracts and acyclic bindings | `test_preservation_contracts.BridgeSchemaTests`; `BridgeBindingTests.test_evidence_binds_all_effect_inputs_and_unknown_fields_reject`; acceptance's graph validation in `test_pending_clarification_to_accepted_without_model_and_idempotent_replay`. |
| I2: all-line inventory and correspondence | `test_preservation_inventory.PreservationInventoryTests`; `test_preservation_contracts.BridgeBindingTests` covers reflow, duplicate selection, connected supersession, ownership and exact caps. |
| I3: raw/materialized identities and trusted stamps | `test_preservation_proposals.MaterializationTests` and `ProposalStoreTests`; runtime maintenance's `test_versioned_vertical_entry_preserves_exact_bytes_and_does_not_charge_budget`. |
| I4: bounded permissions, effect adoption and ordinary eligibility | `test_preservation_contracts`, `test_preservation_acceptance`, and all seven `OperatorJourneyTests` in `test_preservation_qualification`. |
| I5: all supported proposal paths | `test_preservation_runtime` for Editor/supplied/focused; `test_preservation_vertical` for merged-source consolidations; `test_preservation_continuation` and `test_preservation_vertical_recovery` for later work; `OriginJourneyTests` for Editor and supplied no-ops. |
| I6: immutable attempts, errors and budgets | `ProposalStoreTests.test_attempts_never_reused_and_report_never_overwritten`, persistence-failure and timeout tests; `test_preservation_budget` and qualification's `GrantJourneyTests`. |
| I7: marker-first commit, exclusive writer and exactly-once repair | `AcceptanceTests.test_exclusive_writer_refuses_a_competing_invocation`, before/after-marker and mirror/history fault tests; runtime and vertical completion-repair tests. |
| I8: authoritative status and consumer eligibility | `RuntimeTests.test_live_pending_acceptance_repair_and_status`; continuation's changed-completion/readiness tests; qualification's false-convergence, declaration/manifest tampering and status checks. |
| I9: local request acceptance, dry-run, changed authorization and retry | `AcceptanceTests.test_missing_evidence_rejects_then_new_request_can_accept_same_proposal`, `test_frozen_loss_rejects_then_explicit_new_surface_and_deletion_can_accept`; `CLIRuntimeJourneyTests`; typed Reviewer/Editor/supplied retry tests. |
| I10: narrow maintenance inheritance and Phase 2 entry | All `test_preservation_maintenance` journeys, including null round/profile/client and empty evidence, exact-parent enforcement, no double stamp and entry-publication faults. |
| I11: complete downstream chain and legacy compatibility | Runtime pending/rejected/repair consumer guards; maintenance handoff tests; qualification's `ConsumerJourneyTests` and `CloseoutConsumerTests`; existing `test_apply_back`, status and configuration regressions retain legacy behavior. |

## Acceptance evidence

A1–A11 follow the plan's acceptance-evidence order.

| Check | Representative executable evidence |
|---|---|
| A1: parser/conformance, losses and positive controls | Inventory grammar, physical-line partition and exhaustive small-sequence matching oracle; binding tests for table/schema/enum loss and caps; all seven positive operator journeys. |
| A2: inventory/approval/frozen scope and moves | `BridgeBindingTests.test_frozen_schema_table_and_enum_losses_fail_despite_claimed_resolution`, surface-binding tampering tests and `test_relocation_requires_exact_authority_and_counts_both_sections`; preliminary frozen-loss fixtures retain the targeted finding and pending clarification. |
| A3: exact weakening authorization | `test_semantic_weakening_of_verbatim_unit_needs_specific_evidence`; `OperatorJourneyTests.test_weakening` and `test_added_exception_discloses_weakening_of_verbatim_requirement`; per-kind and exact-binding rejection tests. |
| A4: trusted materialization and replay | Materialization tests distinguish identical bytes from different origins, reject Editor-owned anchors and adjacent edits, and reproduce transforms; maintenance entry and acceptance repair prove no double stamping. |
| A5: pending/rejected/technical lifecycle | Runtime pending with soft budgets, deterministic no-retry failures, typed Editor/supplied/Reviewer retry; local acceptance remains one operation. `test_pending_cannot_run_next_round_or_strop_with_overrides`, maintenance handoff refusal and closeout consumer tests cover bypass attempts. |
| A6: destructive rewrite despite size padding | `DestructiveRewriteTests.test_padding_does_not_hide_frozen_schema_loss_or_erase_pending_effect`: checked-in missing-field variant plus 64 KiB of unchanged padding, over 99.9% output/base size ratio, hard frozen loss remains rejected alongside pending clarification. |
| A7: initial, resumed and vertical integration/faults | Runtime and vertical suites cover source/merge tampering, response and receipt persistence, accepted replay and later cycles; grant and closeout suites cover recovery across exhausted schedules. |
| A8: actual CLI-shaped journey | `CLIRuntimeJourneyTests.test_pending_effect_accept_status_resume_and_handoff_through_cli`: real review, attest, request, dry/real acceptance, status and resume dispatch. Configuration/client construction is fixture-injected while the public activation gate stays closed. Handoff and dry strop use the same runtime root. |
| A9: positive operator usability | Seven `OperatorJourneyTests` record the full displayed base/output, exact adopted mappings/effect text, interaction counts and Editor calls. Line selections go through `adopt_effect`; the operator does not construct hashes or evidence/request JSON. |
| A10: rejection, concurrency and historical recovery | Binding tests reject swapped/conflicting/incomplete correspondence and uncovered output. Acceptance tests cover predecessor reports, competing writer exclusion, stale base, old accepted replay after authority advances, commit/publication faults and unrelated residual retention. Runtime tests cover frozen round-evidence corruption and completion repair. |
| A11: origin-specific no-ops and maintenance limits | `OriginJourneyTests`, runtime initial no-op, vertical empty-sweep no-op, maintenance inherited no-op and dedicated entry tests. `test_phase2_timeout_has_no_generic_retry_or_false_consumption` and bounded-closeout tests retain the generic Phase 2 resume prohibition. |

## New joined journeys and corrections

The seven effect-review journeys are clarification, harmless addition, one-to-many reflow, complete many-to-one supersession, explicitly selected duplicate deletion, direct weakening and an added exception weakening a verbatim base obligation. A single grouped effect uses five operator interactions: review, adopt, prepare request, dry acceptance and acceptance. Deletion with explicit duplicate selection and the exception each require two adoptions, for six interactions. Replay is a separate verification action. Each proposal uses one scripted Editor call; acceptance and replay use zero.

The full horizontal grant journey starts with accepted work and a serious closeout result, appends one grant, interrupts the next Editor, retries its frozen operation, accepts locally and verifies all profiles on the current draft before Phase 2 entry. It exposed stale clean-profile state after a later mutation. Guarded execution and scheduler reconstruction now invalidate that state when accepted bytes change. The existing profile order/budgets choose subsequent work; no separate scheduler was added.

Final-consumer qualification exposed two other gaps. Apply-back skipped changes when normalized hashes matched even though accepted bytes differed. Guarded apply-back now compares/writes exact bytes while preserving the existing normalized external-source hash convention, and rechecks source bytes immediately before a changed write. The external source is not part of the run's writer lock; this recheck is not a filesystem compare-and-swap guarantee against an unrelated writer racing after the check.

A mutable `CONVERGED` flag also did not itself prove final verification. Guarded accepted declarations, convergence status and converged apply-back now reconstruct the accepted Phase 2 schedule and bounded closeout, require clean verification on current bytes, compare frozen rubric identity, and validate the exact declaration. Completed closeout consumers additionally validate its terminal receipt. Manual application of accepted non-converged work remains explicit; it cannot bypass a pending, rejected or incomplete preservation operation.

## Readiness and limits

The qualification result applies to the current runtime bridge and its scripted fixtures, not live-model reliability, arbitrary prose semantics, universal filesystem fault tolerance or vNext. Effect evidence records an accountable operator assertion; the bridge cannot mechanically prove a dishonest equivalence or undisclosed weakening claim false.

The frozen Phase 2 rubric binding is part of this private developer checkpoint. Older experimental guarded Phase 2 roots that lack it remain audit evidence but cannot claim this checkpoint's verified convergence; regenerate their scripted journey instead of retroactively filling authorization from current defaults. Historical unguarded runs keep their existing behavior.

The publication switch remains off. The green regression result supports a separate opt-in activation change and its configuration/documentation checks. Generic Phase 2 technical continuation remains unsupported; bounded closeout recovery is the supported exception. There is no new unresolved normative decision in these corrections.
