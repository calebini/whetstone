# Run patterns

For complete examples use the matching checkout's `docs/OPERATOR_EXAMPLES.md`.
These patterns are recommendations, not permissions or unimplemented CLI options.

## Bounded audit and manual revision

Freeze the explicit source set and a bounded question. Run a supported reviewer-only
audit in an isolated root. Report findings and failure status separately. The
operator and agent may then edit within their actual authority and resubmit a
new snapshot in another audit root. Reuse scoped authorization when applicable;
do not overwrite prior audit evidence or infer automatic iteration permission.

## Explanatory design

Clarify intent, responsibilities and relationships while preserving valued
rationale and examples. Defer lower-level schemas when they belong elsewhere.
Set scope depth and actual preservation boundaries; names such as HLD are not
required. A standard review with scope is not automatically a custom design rubric.

## MVP stabilization

Prepare a concise scope contract. Recommend lenses and bounded allowances, then
check the entire mode/workflow/profile combination. Consumer-3 supports MVP Phase 1 with approved scope. If the selected
installation only advertises consumer-1, explain its Standard-only boundary.
Assess bridge support and explain any operator-attestation obligation. If no
supported combination meets intent, surface that before launch.

## Focused recheck

Select a supported profile and accepted seed. Existing-root continuation and
fresh focused jobs have different gates. In verified mode the profile and allowance
must match immutable pins. Focused cleanliness never grants complete stability.

## Source adoption

Use the mode-specific assessment before source writes. Inspect the accepted draft,
residuals, exact source binding and required approval. A converged result is not
consent to overwrite the source, and a copied run is not necessarily resumable.
