# Q4 — isolated live soak and activation decision

Status: **the embedded CLI cleared the provider/model blocker; the second live
window stopped on invalid Reviewer advice. Q4 remains incomplete and public
activation remains disabled.**
Q3 is closed with the operator's explicit correctness-risk and performance
acceptances. Q4 remains incomplete until live evidence is assessed and activation
is explicitly decided. The finite Q4 scope remains the inventory's live soak,
successful/rejected proposal inspection, operator guidance and activation decision.

## Concrete first run

The prepared input is a synthetic, versionless FIFO queue specification under
`rounds/vnext-18-9-q4-001/package/`. It contains no external project specification.
It preserves a 30-second minimum interval, FIFO order, and one start record per
job with identifier and UTC timestamp. Repetitive reporting prose gives the
Reviewer a possible clarification/simplification target; findings and successful
promotion are not scripted or guaranteed. Models must not invent product policy.

The immutable package pins `vnext-verified-consumer-1` with digest
`7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58`.
It selects horizontal structural-integrity, determinism and operability reviews
with two reviews per profile, one operation/changed section/changed normative
unit per proposal, and only `replace_section_body`. It grants no deletion,
weakening, compatibility policy or external source-write authority.

`prepare.py` validated the package with the real bootstrap reader. `launch.py`
passed the real `vnext-admit --dry-run` route without creating a destination or
making a provider call. Sources remain pinned to `c9d1dae`; `prepared.json`
records input and source hashes. The private harness temporarily supplies only
this exact suite's gate inside its process. It does not change production maps,
source code, provider responses or native adapters. The gate is empty again
after the command. This mechanism needs approval as part of the isolated soak;
it is not public release qualification.

## Provider authorization — approved 2026-10-15

The operator approved the exact provider payloads and bounded isolated run on
2026-10-15. `provider-authorization.json` binds the approval to the original
prepared manifest and launcher hashes. The scope below remains unchanged.

- Provider: OpenAI through `/opt/homebrew/bin/codex`, observed CLI version
  `0.142.0`; model `gpt-6.1-sol`, matching the configured local model. The existing
  native adapter selects medium reasoning, disables web search, ignores repository
  rules and uses its read-only client sandbox. No Claude transmission is proposed.
- Permitted source files: `package/inputs/seed.md`, `authority.json`,
  `invariants.json`, `review.json`, `mutation-constraints.json` (all four latter
  names are under `package/inputs/`), `package/job_descriptor.json`, and
  `package/proposal_package.json`, relative to `rounds/vnext-18-9-q4-001/`.
- Also permitted: built-in Reviewer/Editor/Verifier prompt text and output schemas,
  plus this isolated run's derived section maps, inventories, findings, mutation
  plans, candidate text, preservation reports and verification context. These
  future bytes are bounded to the named synthetic inputs and their live outputs;
  they cannot be precomputed before the preceding client returns.
- Command scope: one `live-phase1` invocation against the fresh isolated `run/`
  destination, real native Reviewer/Editor/Verifier clients, at most eight actual
  provider calls including shape retries, 600 seconds per provider call, one
  supervisor at 60% duty, 180-second lease and 1800-second total hard cap.
- Stop on returned halt/operator decision, exhaustion or deadline. No automatic
  new invocation, resume, budget extension, new authority decision, Phase 2,
  external apply-back or activation is included in this first window.

The normal API remains gated. `launch.py --run` requires an affirmative local
authorization receipt bound to the exact prepared manifest and launcher hashes;
that receipt was created after the explicit operator approval. Approval does not
permit substituting a different model or silently repeating the bounded window.

The named boundary comes from the Q4 inventory requirement to “separately authorize
exact provider payloads” and the runner skill's instruction to include an explicit
authorization block naming transmitted files before a live nested-client run.

## Evidence and remaining qualification

The live harness will retain each exact prompt/schema before transmission,
call timing and outcome, the command result and ordinary durable run artifacts.
An interrupted command is not a completed soak. Inspect actual verified pointer,
candidate decisions, status and reentry; do not infer promotion from model prose.

This first window measures actual Phase 1 behavior and can reveal transport,
schema, preservation or latency problems. It does not by itself close Q4. Inspect
successful and rejected proposal evidence, explicitly note any unobserved outcome,
then complete the required live journey/Phase 2 coverage with bound inputs and
operator authority. Never manufacture a passing or rejected verdict to fill a
coverage row. Stop for any product/authority choice. Final operator guidance and
the activation decision follow the live evidence. No commit or push is implied.

## First live-window result

The approved command ran on 2026-10-15. The supervisor exited cleanly with code 2
after 16.128s. Exactly one native Reviewer provider attempt occurred, lasting
3.232s. The provider rejected the configured model with HTTP 400:
“The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account.”
The CLI also reported model-cache metadata warnings; those are retained, but
the explicit unsupported-model response is the blocking result.

No Reviewer response, Editor or Verifier invocation, candidate or promotion was
produced. Whetstone retained the transport failure and reports pending Reviewer
continuation. Read-only `status` returned code 0 without changing run files;
the committed pointer remains at seed ordinal 0. This is a failed live-soak
attempt, not completed live qualification or a measure of useful-work latency.
All workers stopped; no retries, fallback model, Phase 2, external apply-back
or public activation occurred. Runtime, contracts and approved package inputs
remain unchanged.

`provider-calls.jsonl`, the exact prompt/schema, the ordinary request journal,
`live-command.json`, `post-stop-status.json`, `live-supervision/` and
`live-outcome.json` retain and join the evidence. The configured local model
was not evidence of availability through this CLI/account transport.

Next: select an account-supported model and prepare a new bound package for
approval. Review/model identity is immutable, so a different model must not be
substituted into this retained request's technical continuation. Preserve this
failed run and its approval receipt; a changed identity needs a fresh isolated
run. Q4 live success/rejection and subsequent journey coverage remain unobserved.

## Q4-002 — embedded CLI and invalid Reviewer advice

The operator requested the app's embedded CLI, then authorized proceeding with
the newly prepared package. The new run under `rounds/vnext-18-9-q4-002/` uses
`/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`,
version `0.162.0-alpha.17.2`, with the same `gpt-6.1-sol` model. The synthetic seed
and preservation requirements are unchanged. The actor/version and derived
job/configuration identities are newly bound; the first failed root and its
evidence remain intact. Local package/CLI preflight passed before transmission.
The same eight-call, 30-minute, 60%-duty limits apply, with a hash-bound approval.

The supervisor exited cleanly with code 2 after **64.612s**. Two native Reviewer
calls returned model responses, in **10.434s** and **24.960s** respectively. The
first structural-integrity review was valid and clean. The second, determinism
review supplied section IDs in `scope_surface_ids`, despite the package having
no scope contract. Whetstone rejected it as `invalid_review`, with the reason
`$: scope surfaces supplied without a scope contract`. Provider access through
this embedded CLI is therefore demonstrated; successful candidate production
and promotion are not.

The rejected response also suggested a clarification about elapsed time versus
UTC clocks and requested an operator decision about exactly-one recording after
failed or uncertain writes. Those are raw, unadmitted findings, not authorized
edits or committed operator work. No response was repaired or replayed, no model
was substituted, and no product decision was invented. The command returned
pending review with no technical continuation advertised. No Editor or Verifier
ran; no candidate or promotion exists, and the current pointer remains at seed
ordinal 0. Read-only status preserves the retained run files.

The two exact prompts/schemas, responses, request outcomes, command/status packets
and supervisor result are retained and joined by `live-outcome.json`. Runtime and
contract sources are unchanged; all workers stopped. This is not a completed
Q4 soak or rejected-*candidate* coverage: the rejection occurred at Reviewer
advice admission before a candidate could exist.

Next recommended work is a bounded investigation of the native Reviewer guidance
for authority scopes, scope-contract surface IDs and section IDs, followed by
focused verification of any justified guidance fix. The rejection check must
remain intact. Any genuine product choice needed by a subsequent valid review
must return to the operator. No automatic live retry or activation is authorized
by this completed window.

## Reviewer scope guidance fix — 2026-10-16

The retained second prompt embeds `scope: null` and the section/authority maps,
but does not explain the classification identifier namespaces. Its Codex output
schema permits string arrays and cannot express this input-dependent constraint.
The strict classifier correctly rejects the response; this is a prompt guidance
gap, not authority to relax admission or repair retained model output.

Fresh verified Phase 1 Reviewer requests now explicitly distinguish canonical
section anchors, authority scopes, authority binding IDs and scope-contract
surface IDs. With no scope contract, every classification must supply
`scope_surface_ids: []`. With a contract, only its declared surface IDs apply;
unresolved scope cannot create authority. Product decisions still require the
operator. Decoder, classifier, schemas, contracts and legacy/bridge prompts are
unchanged.

Historical replay compares exact prompt bytes. The renderer therefore recognizes
only the exact previous deterministic rendering for retained requests, preserving
their original instructions during readback and authorized technical continuation.
It does not accept arbitrary stored prompt text. Fresh requests use the new
guidance; invalid reviews remain terminal and cannot be retried as shape errors.

Focused offline coverage checks identifier rejection, valid declared surfaces,
no retry after invalid advice, historical prompt replay/continuation and prompt
tampering. The original Q4-002 responses were decoded read-only: round 1 remains
valid and round 2 still fails with the identical scope-contract error. Evidence
is retained separately under `rounds/vnext-18-9-q4-scope-guidance-001/`.

Verification: 40 tests across verified Reviewer requests, classification and
proposal Reviewer requests passed in 117.217s; the separately added historical
continuation test passed in 1.674s (41 distinct methods total). Its initial test
assertion incorrectly expected `continuation_required` at first timeout and was
corrected to the existing `timeout` status. All 112 prior sealed evidence hashes
and protected notes/audits are unchanged; `git diff --check` passes.

This fixes the guidance defect; whether a live model follows it remains untested.
Q4 remains open. Next is a fresh isolated, newly bound live package using the
updated sources, with exact payload authorization before transmission. Neither
completed Q4 root should be modified or resumed to test this fix. No live call,
public activation, external apply-back, commit or push occurred in this fix.
