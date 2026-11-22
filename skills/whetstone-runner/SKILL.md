---
name: whetstone-runner
description: Prepare, run, monitor, and interpret Whetstone specification audits and sharpening jobs, including scope intake, protection selection, continuation and source-adoption review.
metadata:
  short-description: Operate Whetstone specification reviews
---

# Whetstone Runner

Use the user's intent to design a bounded job, handle mechanical preparation,
and present only material choices. Assessment-only intent never authorizes an
Editor loop. Do not require users to choose internal mechanism names.

## Establish the executing runtime

Prefer the configured `whetstone` launcher and its selected stable runtime.
Use `--runtime-info` only when the launcher supports it. Inspect that runtime's
command help and matching docs. Choose development only when requested; do not
silently use `PYTHONPATH` to bypass an installed selection. A direct source checkout
without a launcher can use `PYTHONPATH=src python3 -m whetstone.cli --help`.

Locate the matching Whetstone documentation checkout or installed docs. Read
`docs/OPERATOR_GUIDE.md` for preparation and `docs/OPERATOR_QUICKSTART.md` for exact
mode-specific commands. These are repository-relative identifiers, not paths
relative to an installed skill. If an older release lacks the new guide, use its
matching CLI/docs plus [preparation guidance](references/preparation.md); do not
infer new runtime capabilities from this skill's presence.

## Route by outcome, then check compatibility

- Bounded assessment: `audit-change`; no edits or convergence claim.
- Iterative improvement: Phase 1; stability requires actual terminal evidence.
- Isolated concern: supported focused review; focused stability is not full stability.
- Convergence: Phase 2 only after eligible Phase 1 completion.
- Source adoption: separately assessed/authorized strop or apply-back.
- Decomposition: use the existing copy-first decomposition workflow when requested.

Separate review workflow, profile set, schedule, editing boundaries and semantic
verification preference. Infer document purpose and authority from project evidence,
not filenames or a required HLD/leaf/schema hierarchy. Preserve rationale when it
serves the document's purpose. Ask which decisions are settled versus open only
when the intent is materially ambiguous.

Preservation requests do not automatically select the bridge. Consider verified
promotion where supported and the user wants delegated semantic verification;
otherwise assess bridge compatibility and exact operator-attestation requirements.
Read [protection selection](references/preservation.md) before guarded preparation.
Check the whole combination against the executing runtime. Explain incompatible
MVP/verified selections without silently choosing standard or dropping protection.
Do not invent attestations or claim the bridge is deprecated.

## Prepare and operate

Read [preparation](references/preparation.md) for scope, schedule, allowances,
models and handoff. Use [run patterns](references/run-patterns.md) for examples
and [commands](references/commands.md) for command/artifact interpretation.
The agent assembles snapshots, inventories and hashes; the operator reviews
boundaries and exact effects. Use existing supported builders/validators; no
universal preparation command is supplied by this skill.

Keep data-sharing authority, execution permission, effect acceptance and source
adoption distinct. Reuse actual existing authority within scope; do not ask for
identical confirmations, weaken sandboxes or fabricate approval identities.
Selecting enforcement does not attest equivalence of unseen revisions.

For monitoring, read [status reporting](references/status-reporting.md) and
[artifact map](references/artifact-map.md). Follow the evidence-backed gate;
never infer process liveness, resumability, stability or convergence from a stale
record, exit code, Editor claim or missing pending output alone.

Stop at the authorized outcome, budget/failure boundary or a decision outside
existing authority. Keep diagnostics and supported continuation available without
starting an unrequested next phase or source write.
