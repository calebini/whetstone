# D8 bounded consistency audit

Current result: **pass — zero findings**, with `boundary_preserved: true`, on the authorized focused correction recheck. **The D8 design-audit gate is closed.** The single-host design remains ratified; consuming-release qualification and slices 18.5–18.7 remain incomplete.

The original audit reported **needs revision: 0 blockers, 2 major findings, 1 minor finding**, with `boundary_preserved: false`. Its evidence and the local terminology disposition below remain unchanged.

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

## Correction recheck: passed

The user authorized execution of the staged packet on 2026-09-15. One Reviewer-only invocation configured for **gpt-5.6-sol**, consistency, Codex `0.154.0-alpha.6.2`, and a 360-second limit completed successfully. It reviewed correction checkpoint `553300c`, targeting `fb_consistency_001`, `fb_consistency_002` and direct regressions. It returned **pass, zero findings, boundary_preserved: true**. This closes the two major findings; the earlier minor terminology finding retains its separate nonblocking local disposition.

The [recheck evidence](vnext-d8-recheck.json) preserves the exact feedback, report, audit manifest, authorization and source/artifact hashes. All three artifact schemas validate. The actual brief matches the prepared preview byte for byte; its normalized draft hash is separately verified. Sources and packet snapshots were unchanged through execution. No runtime tests were rerun; the 65 focused tests below remain prior patch-validation evidence.

Model metadata limit: the invocation and audit manifest select `gpt-5.6-sol`; the model-authored feedback self-labels `gpt-5`/`1.0.0`. That response is preserved verbatim and is not runtime identity attestation. No independent served-model attestation was captured.

## Correction follow-up: staged, not run

Historical staging checkpoint, superseded by the executed recheck above:

The two major findings have now been patched. The storage contract, kernel
notes and unregistered binding schema explicitly require a normalized path
relative to the run root. The candidate contract defines both expected-current
hashes at declaration, preparation, committed-predecessor replay, next-ordinal
claimant validation and conditional commit. Runtime source is unchanged.

All **65 focused tests pass**: 32 storage tests (including new path-schema and
fresh-process CWD checks), 32 contract tests and the existing same-draft-bytes
stale-pointer promotion regression. This is targeted validation, not a new full
regression or an audit pass.

The [staging evidence](vnext-d8-recheck-staging.json) pins the packet under
`rounds/vnext-d8-audit-004/`. It contains four current contract snapshots, the
original feedback and the exact correction diff, plus notes and the standard
Reviewer prompt/schema. The proposed pass uses `gpt-5.6-sol`, consistency,
CLI `0.154.0-alpha.6.2` and a 360-second limit. `preflight.py` verifies source,
snapshot, prompt and executable hashes without invoking a Reviewer;
`run-command.txt` retains the proposed command. The user requested staging
only. **No recheck or external transmission has occurred; D8 audit closure
remains pending.** The original report and feedback below are unchanged.

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

Next: the normal V Reviewer sequence and canonical round admission/publication against committed promoted bases, followed by consuming-suite qualification. The focused correction recheck is complete. The
original Reviewer pass made no corrective specification, schema or runtime
changes; the subsequent patches are recorded above. Neither step invoked an
Editor. No new modes, 18.8–18.9 work,
push or external source apply-back occurred. Existing uncommitted plan,
artifact and scope proposals remain intact. Audit closure rests on the validated passing feedback and report from the focused recheck, not merely a successful command exit. It does not establish runtime qualification or broader slice completion.
