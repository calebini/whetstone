# Whetstone Scope Notes Guide

Scope notes tell Whetstone what kind of pressure is useful for this run.

For MVP runs, the goal is not to make the spec maximally complete. The goal is to make the first useful implementation buildable without letting review pressure turn the MVP into a platform, governance, or operations spec.

Answer these questions before generating a scope contract:

1. What is the one core outcome this run should optimize for?
2. Who or what consumes the result?
3. Which flows are definitely in scope?
4. Which surfaces are explicitly deferred or out of scope?
5. How deep should validation, schema, reporting, failure, replay, and operations behavior go?
6. What should reviewers avoid expanding?
7. What counts as good enough for this run?

## Example

```markdown
## Core Outcome

Make deterministic replay over SQLite audit history buildable for an MVP.

## Primary Actor Or Consumer

Foreman implementation engineer.

## Core Flows

- must: run full replay over one SQLite audit history
- must: emit a minimal replay report
- should: classify integrity mismatches into stable categories

## In Scope

- replay invocation contract: required_fields
- replay report schema: required_fields
- validation/error behavior: required_fields
- mismatch classification: define

## Deferred / Out Of Scope

- diagnostic scan mode
- exhaustive error-code registry
- retry/timeout/resume behavior unless required for replay correctness
- operator runbook

## Expansion Rules

- Defer reviewer requests for exhaustive validation matrices unless required for replay correctness.
- Defer reviewer requests for retry/resume semantics unless the core replay flow cannot be built without them.
- Allow reviewer pressure on required fields, artifact ownership, failure categories, and acceptance criteria.

## Good Enough

The MVP is good enough when an engineer can build deterministic replay over SQLite, validate required inputs, emit the minimal report, and test the acceptance criteria without inventing behavior.
```

## Depth Hints

- `mention`: name the responsibility, but do not define detailed behavior.
- `define`: define the behavior or category in prose.
- `required_fields`: define required fields, ownership, nullability when important, and coarse failure categories.
- `full_schema`: define schemas, requiredness, nullability, enum values, and deterministic failure behavior.
- `exhaustive`: define a complete matrix of cases, error codes, and reporting semantics.
- `custom`: preserve the operator's freeform depth rule.

For most MVP specs, `required_fields` is the useful brake pedal. It catches missing implementation contracts without forcing exhaustive error-code or edge-case enumeration.
