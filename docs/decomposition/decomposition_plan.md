# Decomposition Plan

- Source spec: `spec.md`
- Source hash: `adaa8b719bac1a093f474ad01250cb6da3a56652b7159aed6cc06b033b383d12`
- Planning mode: `approved_split`
- Authority topology: `coordinated_family`
- Extraction mode: `copy_first`
- Target specs: 7

## Coverage

- Extractable units: 49
- Assigned extractable units: 49
- Unassigned extractable units: 0
- Retired extractable units: 0
- Duplicated extractable units: 0

## Target Specs

### whetstone_coordinating_spec

- Path: `docs/specs/WHETSTONE_COORDINATING_SPEC.md`
- Role: `coordinating_spec`
- Owned authority surfaces: purpose, roles, primary_inputs_outputs, configuration_overview, design_principle, multi_reviewer_future_note
- Extractable units: 7
- Normative statements: 16

  - `purpose` lines 3-12: Purpose
  - `core-roles` lines 13-25: CORE ROLES
  - `primary-inputs` lines 26-35: PRIMARY INPUTS
  - `primary-outputs` lines 36-88: PRIMARY OUTPUTS
  - `configuration` lines 89-185: CONFIGURATION
  - `multi-reviewer-non-normative-future-note` lines 2780-2806: MULTI-REVIEWER (NON-NORMATIVE FUTURE NOTE)
  - `design-principle` lines 2807-2816: DESIGN PRINCIPLE

### rubrics_profiles_and_feedback_spec

- Path: `docs/specs/RUBRICS_PROFILES_AND_FEEDBACK_SPEC.md`
- Role: `leaf_spec`
- Owned authority surfaces: canonical_rubrics, workflow_presets, review_profiles, profile_sets, severity_normalization, baseline_invariants, feedback_classification
- Extractable units: 11
- Normative statements: 57

  - `canonical-rubrics-and-workflows::__intro__` lines 187-195: CANONICAL RUBRICS AND WORKFLOWS intro
  - `canonical-rubrics-and-workflows-canonical-rubric-profiles` lines 196-214: Canonical Rubric Profiles
  - `canonical-rubrics-and-workflows-workflow-presets` lines 215-226: Workflow Presets
  - `canonical-rubrics-and-workflows-rubric-manifest` lines 286-343: Rubric Manifest
  - `review-profiles` lines 734-782: REVIEW PROFILES
  - `review-profile-sets` lines 783-911: REVIEW PROFILE SETS
  - `severity-normalization-function` lines 1209-1243: SEVERITY NORMALIZATION FUNCTION
  - `baseline-review-invariants` lines 1244-1257: BASELINE REVIEW INVARIANTS
  - `phase-gated-feedback-classification::__intro__` lines 1325-1354: PHASE-GATED FEEDBACK CLASSIFICATION intro
  - `phase-gated-feedback-classification-oscillation-key-canonicalization` lines 1355-1472: Oscillation Key Canonicalization
  - `phase-gated-feedback-classification-phase-2-reviewer-prompt-requirements` lines 1473-1490: Phase 2 Reviewer Prompt Requirements

### scope_intake_and_decisions_spec

- Path: `docs/specs/SCOPE_INTAKE_AND_DECISIONS_SPEC.md`
- Role: `leaf_spec`
- Owned authority surfaces: scope_contract, contract_surface, decision_register, decision_summary, spec_decomposition
- Extractable units: 4
- Normative statements: 136

  - `canonical-rubrics-and-workflows-scope-contract` lines 227-285: Scope Contract
  - `spec-decomposition-workflow` lines 508-733: SPEC DECOMPOSITION WORKFLOW
  - `expanding-contract-surface` lines 1114-1176: EXPANDING CONTRACT SURFACE
  - `decision-summary` lines 1761-2003: DECISION SUMMARY

### scheduler_state_and_resume_spec

- Path: `docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md`
- Role: `leaf_spec`
- Owned authority surfaces: halting, accepted_draft, version_lifecycle, round_scheduling, budget_handling, phase1_failure, resume, state_machine
- Extractable units: 14
- Normative statements: 121

  - `halting-conditions-ordered-precedence` lines 344-356: HALTING CONDITIONS (ORDERED PRECEDENCE)
  - `halt-artifact-matrix` lines 357-439: HALT ARTIFACT MATRIX
  - `accepted-draft-definition` lines 440-455: ACCEPTED DRAFT DEFINITION
  - `spec-version-lifecycle` lines 456-507: SPEC VERSION LIFECYCLE
  - `round-strategy-adaptive` lines 912-943: ROUND STRATEGY (ADAPTIVE)
  - `round-scheduling-algorithm` lines 944-1113: ROUND SCHEDULING ALGORITHM
  - `definition-clean-profile` lines 1177-1188: DEFINITION: CLEAN PROFILE
  - `round-budget-handling` lines 1189-1208: ROUND BUDGET HANDLING
  - `resume-policy::__intro__` lines 2044-2049: RESUME POLICY intro
  - `resume-policy-editor-timeout-resume` lines 2050-2104: Editor Timeout Resume
  - `resume-policy-budget-extension-resume` lines 2105-2163: Budget-Extension Resume
  - `focused-phase-1-profile-runs` lines 2164-2183: FOCUSED PHASE 1 PROFILE RUNS
  - `phase-1-failure-handling` lines 2549-2595: PHASE 1 FAILURE HANDLING
  - `state-machine-full-transitions` lines 2628-2660: STATE MACHINE (FULL TRANSITIONS)

### artifacts_validation_and_telemetry_spec

- Path: `docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md`
- Role: `leaf_spec`
- Owned authority surfaces: artifact_schemas, artifact_validation, client_telemetry, content_normalization, hashing
- Extractable units: 4
- Normative statements: 103

  - `artifact-schemas-minimum-required-fields` lines 1491-1760: ARTIFACT SCHEMAS (MINIMUM REQUIRED FIELDS)
  - `artifact-validation-policy` lines 2004-2042: ARTIFACT VALIDATION POLICY
  - `client-telemetry` lines 2184-2262: CLIENT TELEMETRY
  - `content-normalization-and-hashing` lines 2263-2310: CONTENT NORMALIZATION AND HASHING

### identity_oscillation_and_conflicts_spec

- Path: `docs/specs/IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md`
- Role: `leaf_spec`
- Owned authority surfaces: issue_identity, conflict_identity, oscillation_detection, conflict_model, editor_decline, conflict_escalation
- Extractable units: 5
- Normative statements: 16

  - `issue-and-conflict-identity` lines 1258-1323: ISSUE AND CONFLICT IDENTITY
  - `oscillation-detection-full-definition` lines 2311-2412: OSCILLATION DETECTION (FULL DEFINITION)
  - `conflict-model` lines 2413-2444: CONFLICT MODEL
  - `editor-decline-taxonomy` lines 2445-2472: EDITOR DECLINE TAXONOMY
  - `conflict-escalation` lines 2473-2487: CONFLICT ESCALATION

### phase2_convergence_and_declaration_spec

- Path: `docs/specs/PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md`
- Role: `leaf_spec`
- Owned authority surfaces: phase2_failure, target_matrix, convergence_declaration, reproducibility
- Extractable units: 4
- Normative statements: 36

  - `phase-2-failure-handling` lines 2488-2548: PHASE 2 FAILURE HANDLING
  - `target-matrix-precedence` lines 2596-2627: TARGET MATRIX PRECEDENCE
  - `convergence-declaration` lines 2661-2711: CONVERGENCE DECLARATION
  - `reproducibility` lines 2712-2779: REPRODUCIBILITY

## Operator Approval

- Approved: true
- Approved plan hash: `49b36fc47c1ac95d1dbe4c83fccc5bb8034a5fd8894748a6aceef4a3a405c601`
