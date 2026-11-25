# Worked operator examples

These examples illustrate preparation decisions, not installed presets or new
CLI options. Use the selected runtime's matching commands in the
[Quickstart](OPERATOR_QUICKSTART.md) and the [operator guide](OPERATOR_GUIDE.md).
They do not authorize any transmission or source write.

## Bounded assessment, with editing outside Whetstone

**Request:** Check whether an import-policy update and its report specification
agree. The operator and operating agent will decide any edits together.

**Agent recommendation:** Use `audit-change` on the explicitly listed documents,
with notes stating the intended change and bounded consistency question. Keep
source files unchanged during that invocation and use an isolated audit root.
A report with findings can be a successful assessment; it is not Phase 1 stability
or convergence. Include context only through the selected command's supported
input surface; do not invent a context-only flag or silently transmit linked files.

**Handoff:** Identify the exact inputs, selected reviewer/model, permission already
covering them, and any missing authority. After review, summarize useful findings,
out-of-scope concerns and technical failures separately. A v1 audit's
`boundary_preserved` indicator is not independent semantic proof. For an objectives
format, report its actual coverage/preservation fields only when that format is
supported. Check the installed report version rather than impose one vocabulary.

**Next:** If edits are authorized, the agent and operator make them outside the
audit, then explicitly resubmit the revised inputs in a new audit root. Reuse
applicable existing authorization; do not equate it with a host permission bypass.

## Explanatory system design: preserve rationale without freezing every word

**Request:** Sharpen a document that explains system goals, component boundaries
and design tradeoffs. Its rationale and examples are valuable, even where they
are not requirement statements.

**Agent proposal:** Treat the goals and component responsibilities as settled;
allow wording and organization changes that preserve their meaning. Keep open
questions explicit. Clarify relationships and contradictions, but leave field
schemas and exhaustive operational detail to the appropriate supporting documents.
If a rationale seems contradictory, raise that specific issue rather than delete
it as prose noise. The filename need not contain “HLD.”

**Scope notes sketch:**

```markdown
## Core Outcome
Clarify the system's goals and component responsibilities without losing design rationale.

## Primary Actor Or Consumer
A designer or implementer locating the responsibilities that later specifications elaborate.

## Core Flows
- must: trace the main user outcome across component responsibilities

## In Scope
- component responsibilities: define
- interactions and ownership: define
- design rationale and product intent: define

## Deferred / Out Of Scope
- field-by-field schemas
- exhaustive error-code registry

## Expansion Rules
- Defer field schema detail unless needed to explain an in-scope responsibility.

## Good Enough
The reader can explain the intended outcome, component boundaries and unresolved design choices; existing rationale remains represented.
```

Compile and inspect this sketch as described in the
[scope guide](SCOPE_NOTES_GUIDE.md#compile-and-inspect). The notes alone do not
activate preservation. Prepare the actual protected content and permitted effects
using the selected mode's artifacts. A scoped standard review is not automatically
an architecture-specific rubric; explain the limitation if it cannot meet the goal.

**Protection choice:** Where verified promotion is supported and desired, bind
appropriate authority, invariants and mutation constraints, then validate its
package outside the nonexistent destination. Otherwise evaluate the bridge against
the intended review settings and prepare its exact-base surface. Do not change
the review objective just to fit an available enforcement mode.

## MVP review with a compatibility conflict

**Request:** Improve the import/report behavior enough for a first implementation,
using MVP expectations and a lighter profile set, with few routine check-ins.

**Agent recommendation:** Retain the MVP intent. Propose bounded allowances and
vertical review if the concerns interact; do not ask the operator to pick counts
without a consequential reason. Explain the resolved Reviewer/Editor settings.

**Compatibility finding:** In this example the selected installation only advertises consumer-1, which requires
standard/stateful-system. Do not label MVP as incapable of preservation. Explain
that MVP plus this automated verification path is unavailable in that runtime.

**Decision:** After confirming bridge support for the exact combination, offer
that path with its human-attestation implications. An explicit change to standard
is a different alternative with different review expectations. No silent fallback.
If no supported option satisfies the intent, stop before launch and report the gap.

**Bridge handoff:** Show the proposed allowed/frozen surface. The agent creates
snapshots, inventories and exact references. If a later rewrite needs equivalence
attestation, show the original and proposed text and effect. A change from
“at least thirty seconds” to “exactly thirty seconds” is a behavior change, not
mere wording equivalence. Acceptance records the real decision and stops locally;
continuation needs the supported gate and a valid surface for the current base.

## A concise staging summary

Report resolved values, not this illustrative placeholder text:

> Purpose: stabilize the selected import/report draft to the agreed MVP depth.
> Inputs: the explicit draft and policy references; no additional linked files.
> Boundaries: preserve accepted behavior and rationale; clarify the named areas.
> Plan: selected runtime and supported protection mode, vertical review, bounded
> per-profile allowances, resolved clients/models/reasoning/timeouts.
> Readiness: local checks passed or named blockers; actual authority already given
> and any missing decision. Phase 2 is excluded. Source adoption remains separate.

Do not claim a prepared package is authorized, a local check is live qualification,
or an illustrative mode combination has been tested merely because it appears here.
