# D8 bounded consistency audit

Result: **needs revision**. The Reviewer reported **0 blockers, 2 major findings,
1 minor finding**, with `boundary_preserved: false`. The ratified single-host
storage design stands, but the D8 design-audit gate is **not closed**. This is
neither a convergence result nor runtime/release qualification.

The completed Reviewer-only pass used **gpt-5.6-sol**, profile `consistency`,
a 360-second timeout and the installed desktop Codex executable
`/Applications/ChatGPT.app/Contents/Resources/codex` version
`0.154.0-alpha.6.2`. It reviewed seven current snapshots: the ratified storage
contract, kernel notes, physical-binding schema, and selected candidate,
scheduler, artifact and implementation-plan text at commit `8b970f6`.
The operator approved the prepared payload and explicitly selected this model.

The first invocation through CLI `0.142.0` failed because the service required
a newer client for the requested model. It returned no valid feedback. The
fresh attempt used the already-installed desktop executable without changing
the model, seven source snapshots or system installation. Both attempts are
preserved under `rounds/vnext-d8-audit-{002,003}/`.

## Findings and local assessment

The [evidence record](vnext-d8-audit.json) preserves the exact Reviewer feedback
and its severity/in-scope classifications. The assessments below are separate;
they do not overwrite the Reviewer verdict.

1. **Descriptor-path representation — major.** The storage-specific contract
   and binding schema do not explicitly define `descriptor.path` resolution.
   Clarify that it is a normalized run-root-relative path, resolved from the
   admitted root independently of the process working directory, with the
   existing confinement checks. The [kernel parser and tree](../../src/whetstone/vnext_local_storage.py)
   already implement that interpretation. The broader candidate leaf also has
   a general logical-package-path rule outside the supplied excerpt. This is
   an accepted contract clarification; no runtime path escape or CWD-dependent
   descriptor lookup was demonstrated.
2. **Two expected-current hashes — major.** Define
   `expected_current_verified_hash` as the current pointer's
   `verified_draft_hash`, and `expected_current_verified_pointer_hash` as
   SHA-256 of the exact canonical pointer bytes. State these comparisons in
   preparation, reconciliation and conditional commit. The
   [promotion producer](../../src/whetstone/vnext_verified_promotion.py) and
   [semantic validator](../../src/whetstone/vnext_verified_semantics.py)
   already distinguish the values. This is an accepted contract clarification;
   the audit did not demonstrate an implementation hashing defect.
3. **`audit-change` versus `audit_change` — minor.** The former is the CLI
   command, the latter the internal workflow/phase identifier. The parser and
   prompt renderer intentionally use those distinct namespaces. A naming note
   may help documentation, but no routing defect or D8 storage inconsistency
   was demonstrated. Local assessment treats this as nonblocking terminology
   outside the storage correction scope; the original minor finding remains
   in the evidence unchanged.

## Evidence and next step

The actual audit brief matched its prepared preview. Source and snapshot hashes
were checked before and after execution; all seven snapshots and the 470 files in the pre-execution source manifest
remained unchanged. Feedback, report
and audit-manifest schemas validate. No new runtime tests were run for this
Reviewer pass. The earlier reconciliation's regression and focused reruns remain
separately scoped historical evidence.

Next: make the two narrow contract clarifications and perform a focused
correction recheck. This pass made no corrective specification, schema or
runtime changes and did not invoke an Editor. No new modes, 18.8–18.9 work,
push or external source apply-back occurred. Existing uncommitted plan,
artifact and scope proposals remain intact. There is no audit pass to infer
from the successful execution of the Reviewer command.
