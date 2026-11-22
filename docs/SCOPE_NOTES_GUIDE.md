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

## What scope intake does

Scope intake directs the review; it does not define the system on the operator's
behalf. The operating agent should infer a concise proposal from intent and
existing guidance, then ask about ambiguity that changes the boundary, authority
or stopping condition. Do not resolve every in-scope design question before the
review; some questions are the reason for running it.

| Include | Avoid unless already an explicit constraint |
| --- | --- |
| Review failure categories; defer exhaustive error codes. | Invent five error codes and a retry algorithm. |
| Clarify component responsibilities while preserving architectural rationale. | Turn explanatory prose into a new schema or remove it as non-normative noise. |
| Make the import/report flow implementable without adding scheduling. | Prescribe a new background worker to make the scope sound complete. |

Reference existing definitions rather than repeat them. Document names do not
establish their purpose: a design note can be authoritative, and one document
can contain explanatory and machine-facing sections with different depth needs.

Scope has two consumers. Reviewer and Editor prompts use its meaning to guide
work. Structured machinery validates it and uses finding scope classifications:
MVP requires an approved contract; guarded paths bind the exact scope to their
inputs; verified classification can defer a finding on a deferred surface or
route excluded work to a scope-change gate. The model still interprets which
surface a concern belongs to. A valid schema is not proof that the scope captures
the operator's intent or prevents every inappropriate suggestion.

## Compile and inspect

The existing `intake` command generates notes or deterministically compiles them;
it is not a model that understands arbitrary prose. Use the exact level-two
headings shown below. Compile without `--approve` first when approval has not yet
been given, inspect the result, and record approval only within actual authority.
Use the executing runtime's `intake --help` for paths and supported flags.

Check the compiled outcome, flows, surface names, depths, deferrals and expansion
rules. Missing sections can generate defaults rather than the intended boundary.
In the current notes compiler, the combined **Deferred / Out Of Scope** heading
produces `deferred` surfaces; it does not infer a permanent `out_of_scope` status
from a sentence. Freeform expansion-rule parsing is also limited. If the intended
boundary is not represented, use the supported contract schema/validation path
and review the resulting artifact rather than claiming the prose was enforced.
Do this before hashing and admission; do not edit a bound scope in place later.

For verified preparation, keep inputs outside the fresh destination and follow
its package procedure. The legacy intake run-root examples are not permission
to precreate a verified destination. See [job preparation](OPERATOR_GUIDE.md).

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
