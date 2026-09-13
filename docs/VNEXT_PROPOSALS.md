# Inspectable vNext mutation proposals

Slice 18.4 implements the path from exact Reviewer findings through admission and operator decisions to an immutable section-addressed patch. This is a fixture-driven developer API. Public jobs still support only the [18.3 reviewer-only workflow](VNEXT_ADMISSION.md); proposal mode remains gated on candidate assembly/registration and D8.

The [mutation preparation supplement](../contracts/algorithms/vnext_mutation_preparation_v1.md) owns the executable rules and the five new envelopes. The first frozen contract suite remains unchanged. A later public proposal suite must include the new contracts before advertising them.

## What the toy scenarios establish

| Scenario | Executable evidence |
| --- | --- |
| Clarify the same minimum interval; preserve seed authority | `test_vnext_mutation_admission.MutationAdmissionTests.test_complete_bound_correction_reaches_immutable_proposal_without_candidate_authority` |
| Pause before the Editor for an unresolved choice; admit only a separate task after exact operator authorization | `test_vnext_mutation_admission.MutationAdmissionTests.test_missing_advice_or_unresolved_choice_stops_before_editor_and_writes`, `test_exact_operator_response_yields_derived_task_and_stale_response_never_calls_editor` |
| Reject a forbidden compatibility introduction without rewriting the job's policy | `test_vnext_mutation_admission.MutationAdmissionTests.test_operator_response_cannot_override_immutable_job_policy` |
| Reject unauthorized removal and retain the attempt | `test_vnext_mutation_admission.MutationAdmissionTests.test_mixed_unauthorized_effect_cannot_publish_a_patch_or_change_seed` |
| Exact subtree deletion needs both all removed protected units and the addressed operator response | `test_vnext_patch_operations.PatchOperationTests.test_eligible_subtree_deletion_needs_all_protected_units_and_exact_operator_effect` |
| Every operation family has an eligible target and its payload shape is enforced | `test_vnext_patch_operations.PatchOperationTests.test_each_non_destructive_operation_has_an_eligible_non_root_target`, `test_payload_shape_is_enforced_for_every_operation_family` |
| Ordered insertions reproduce canonical IDs; overlapping subtree edits fail | `test_vnext_patch_operations.PatchOperationTests.test_ordered_insertions_normalize_labels_and_unordered_insertions_refuse`, `test_overlapping_subtrees_refuse_even_when_dependency_is_present` |
| Input drift or a provider timeout cannot publish a patch or change the verified pointer | `test_vnext_mutation_admission.MutationAdmissionTests.test_changed_input_during_editor_retains_raw_attempt_but_no_canonical_proposal`, `test_provider_failure_retains_evidence_and_cannot_restart_the_same_round` |

Additional tests cover source roles, scope deferral, frozen-section policy, repeated findings, response provenance, budget bounds, parser/preimage tampering, transport paths and raw evidence. The fictional operator in these tests authorizes only the toy data; it is not approval of any project specification change.

Run the bounded checks from the repository root:

```sh
PYTHONPATH=src:tests python3 -m unittest \
  test_vnext_classification test_vnext_decisions test_vnext_plans \
  test_vnext_proposals test_vnext_proposal_protocol \
  test_vnext_mutation_admission test_vnext_patch_operations -v
```

## API and artifact inspection

`vnext_mutation_admission.inspect_admission` reads and validates a seed transaction without writing. `prepare_admission` additionally binds explicitly supplied decision artifacts and creates a canonical plan and provenance record in memory. `exercise_proposal` takes these input references, explicit constraints, a fresh round number and an injected `PatchProposalClient`; it persists one inspectable attempt. There is no live proposal command in this slice. The lower-level plan/proposal helpers assume admission has already validated their inputs.

A successful exercise creates these artifacts under `rounds/round-N/`:

- `mutation_plan.json` and `mutation_admission.json`: allowed work, budgets and exact source/decision provenance.
- `proposals/attempts/`: the prompt and original transport bytes, or a provider failure record.
- `proposals/{proposal_id}/proposed_patch.json` and `payloads/`: validated canonical patch and exact payload bytes.
- `proposal_result.json`: explicit non-registration/non-verification/non-promotion result.

The current verified pointer remains unchanged. Inspect an incomplete round before taking another action; this API refuses to reset or silently retry it. An accepted patch is still untrusted proposed content. Actual preservation, changed-unit budgets and candidate-wide assertions require assembly and deterministic validation in 18.5; semantic correctness requires the independent verifier in 18.6. Later slices provide registration, promotion, recovery and scheduler integration.

Evidence for this checkpoint is retained locally under `rounds/vnext-proposals-001/`, with exact test logs, source hashes and inspectable fictional success/rejection runs. No live model or D8 storage qualification is claimed.
