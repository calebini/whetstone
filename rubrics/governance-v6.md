# Convergence Rubric v6

## 0) Convergence Declaration

The review loop cannot start without a Convergence Declaration.

The Convergence Declaration must include:

- Declared Couplings (project-specific)
- Tier 3 Critical Dimensions
- Review Phase (`early`, `mid`, or `final`)
- Tier 5 Entry Mode (`strict` or `permissive`)

### Phase Preconditions

Early Phase:

- Default starting phase
- No preconditions

Mid Phase:

- All Tier 1 dimensions `>= 2`

Final Phase:

- All Tier 1 dimensions `= 3`
- All Tier 2 dimensions `>= 2`

### Phase Rule

- Phase must be validated against current scoring
- If preconditions are not met, declared phase is invalid
- Phase advancement occurs naturally via re-scoring, not assertion

### Declaration Rules

- Steps 1–5 must reference the Convergence Declaration
- If missing, hard block and do not score
- Tier 5 Entry Mode is immutable once declared
- Changing it requires a new declaration and revalidation

## 1) Scoring Integrity

Scoring must be performed or verified by someone who did not author the section being scored.

Acceptable:

- Peer review
- Cross-agent review
- Independent reviewer

Disallowed:

- Unverified self-scoring

## 2) Coupling Model

Baseline Couplings, always evaluated:

- Terminology ↔ Data Contracts
- State Model ↔ Lifecycle
- Decision Rules ↔ Failure Handling
- Time Semantics ↔ Ordering
- Idempotency ↔ Replay

Declared Couplings:

- Each Convergence Declaration must include additional project-specific couplings.

Rule:

- Declared couplings are part of the spec input, not reviewer discretion

## 3) Phase-Aware Coupling Evaluation

Coupling strictness increases as the spec matures.

Early Phase:

- If both dimensions in a coupling are below `2`, flag

Mid Phase:

- If both dimensions are below `3`, flag

Final Phase:

- If both dimensions are below `3`, block convergence

## 4) Dual-Layer Linting

### A) Prose Lint

Search for:

- system decides
- best effort
- if needed
- eventually
- should
- may (unqualified)

Rule:

- Presence means score `<= 1` for that dimension

### B) Structural Lint

Applies to:

- schemas
- APIs
- config
- pseudocode

Checks for:

- enums referenced but not defined
- fields without type
- nullable vs required mismatch
- missing error responses
- undefined identifiers
- inconsistent key definitions

Rule:

- Any structural ambiguity means score `<= 1` in Tier 3

## 5) Scoring Model

Each dimension scored:

- `0` = missing
- `1` = acknowledged but undefined
- `2` = defined but not validated
- `3` = explicit and validated

## 6) Review Loop

Step 0 - Declare:

- Produce Convergence Declaration and validate phase preconditions

Step 1 - Lint:

- Prose lint
- Structural lint

Step 2 - Score:

- Apply scoring model
- Enforce scoring integrity

Step 3 - Coupling Check:

- Evaluate baseline plus declared couplings
- Apply phase-aware rules

Step 4 - Feedback:

- `0` = blocking gap
- `1` = ambiguity
- `2` = needs validation
- `3` = pass

Step 5 - Convergence Gate:

Tier Requirements:

- Tier 1 - Clarity
  - all dimensions = `3`
- Tier 2 - Determinism
  - all dimensions `>= 2`
  - critical dimensions = `3`
- Tier 3 - Enforceability
  - no dimension `< 2`
  - declared critical dimensions = `3`
- Tier 4 - Resilience
  - no dimension = `0`
  - core dimensions `>= 2`

Final Convergence Condition:

- phase must be `final` and satisfy its preconditions
- all tier requirements must pass
- all couplings must satisfy final-phase alignment (`3` / `3`)

## 7) Tier 5 - Scale & Evolution Gate

Trigger Condition:

- Tier 4 has passed, and
- the system either:
  - accepts external input beyond controlled boundaries, or
  - runs in a multi-node or distributed environment

Entry Modes:

Strict Mode, default:

- All Tier 4 dimensions `>= 2`
- No dimension `= 1`

Permissive Mode:

- Tier 4 gate passed
- Non-core dimensions may remain at `1`

Rules:

- Mode must be declared in the Convergence Declaration
- Mode cannot change mid-convergence
- Changing mode requires revalidation

## Final Properties

This rubric is:

- structurally enforced
- phase-gated by actual system state
- resistant to self-scoring bias
- adaptive without ambiguity
- automatable end-to-end
