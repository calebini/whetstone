# Evidence reading order

1. Read mode-aware `status` and its current gate.
2. Follow its selected current evidence, decision and recovery references.
3. Inspect relevant feedback, accepted change evidence and terminal reports.

Legacy/bridge `rounds/run_state.json` records scheduler state. In verified jobs,
run state and the draft file are projections: committed pointer and evidence own
authority. Do not select the newest filename or treat a projection as permission.

Common diagnostic artifacts, when present for the selected mode:

- `rounds/round-N/reviewer_feedback.json`: findings and scope classifications.
- `rounds/round-N/editor_summary.json`: revision summary; confirm acceptance using
  the mode's acceptance/promotion evidence, not an Editor assertion alone.
- `rounds/technical_failure_report.json`, `convergence_failure_report.json`,
  `artifact_validation_error.json`, `oscillation_report.json`: typed halt evidence.
- `rounds/decision_summary.md`, `decision_register.json`, and operator checkpoint
  artifacts: decisions and advice; advisory cards are not automatically pauses.
- `change_audit/change_audit_report.json` and `.md`, `change_audit_feedback.json`,
  `audit_manifest.json`: bounded assessment and input provenance. Interpret the
  actual version, not a universal preservation claim from an old field name.
- `rounds/apply_back_review.json` and `.md`: adoption assessment where applicable;
  a prospective path is not proof that a dry-run wrote a file or applied content.

Prefer paths returned by the owner over assumed artifact names. A missing pending
artifact is not automatically corruption; incomplete committed evidence must not
be treated as an accepted result.
