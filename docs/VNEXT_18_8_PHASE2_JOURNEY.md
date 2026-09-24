# First integrated Phase 2 correction journey

Starting checkpoint: `73642ed`. A subsequent local checkpoint was authorized after
validation. Pushing remains deferred until feature completion.

The milestone connects the already committed Phase 2 request/result/advice path to
canonical round admission, the existing V Editor and candidate registry, independent
semantic verification, verified promotion and restart/recovery. It supports the first
standard horizontal Phase 2 correction, using explicit advisory input and scripted
clients. It is not full Phase 2 convergence or a release activation.

`VerifiedRun.admit_phase2_round()` consumes the exact committed advice binding and
original result on the entered pointer. It reproduces all inputs, rejects unresolved
operator choices, retains packaged mutation constraints, runs complete inventory and
assertion preflight, repeats source barriers under D8, and publishes the canonical
`rounds/round-N/proposal_input.json`. Exact replay uses the same record. Existing
`request`, `register`, `verify`, `promote` and recovery methods own the subsequent
transaction. No separate candidate or verification implementation is introduced.

Historical Phase 2 validation reconstructs a bounded view of already proven pointer
ancestry through the original entry. The real current-head guard and storage reader
remain intact. Phase 1 closeout reconstruction uses only its original candidate-history
prefix. Immutable entry is reproduced without using mutable run-state caches to confer
historical permission. The original request, result, accounting and advice are then
replayed in full. This is necessary both when the original entry was already promoted
and after the Phase 2 candidate becomes the next verified draft.

Pure proposal preflight gains an optional, separately pinned Phase 2 context. It
keeps the descriptor-bound review configuration and role identities intact, validates
the original Phase 2 configuration/request/profile, and includes that context in the
input hash and Editor prompt. Calls without Phase 2 context retain their original
preimages and checks. All non-Phase-2 round provenance retains the Phase 1 validator.
The existing proposal journal's historical `phase1` transport discriminator is retained;
actual Phase 2 origin is bound in the request input hash and canonical round provenance.
This internal compatibility label neither selects Phase 1 policy nor consumes review credit.

Phase 1 Reviewer dispatch stops after committed Phase 2 entry. The integrated current
sequence permits only the first correction and at most one promotion beyond that entry.
Old original-base transactions cannot launch another Editor after promotion. Later
review requests and later Phase 2 correction transactions remain unavailable.

## Verification and handoff

**The bounded integrated milestone is validated: 61 distinct methods pass**, comprising
six integrated journey methods, 32 preflight/Phase 1/advice regressions and 23 proposal/
semantic-followup compatibility methods. The unchanged default preflight preimage is
explicitly covered. `git diff --check` passes; frozen suite 1 and all three empty shipping
qualification maps remain unchanged. The original validation ran with an empty index
and no commit. Before the subsequently authorized local checkpoint, all final source
and retained test-log hashes were rechecked successfully. Only documentation checkpoint
metadata changed afterward; no tests were rerun.

The [validation record](audits/VNEXT_18_8_PHASE2_JOURNEY.json) binds exact commands,
source snapshots, method identities and retained log hashes. Raw evidence is under
ignored `rounds/vnext-18-8-phase2-journey-001/`. The original same-byte promoted-entry
case is retained as exploratory evidence but excluded from the distinct-method count;
the strengthened test proves a different draft is promoted from the prior promoted
entry. The seed test was strengthened with read-only fresh-process reopening, and an
explicit deterministic-rejection test was added. Both pass. Other final production,
contract and regression bytes match the initial integration snapshot; three unchanged
integration methods are carried from that batch. The initial seed smoke exposed an
unnecessary candidate-journal construction for an empty historical registry; the
closeout report now constructs that journal only when candidates exist. The failure
is retained, and final evidence uses the corrected implementation.

| Requirement | Evidence |
| --- | --- |
| Complete seed-entry correction | Actual review, advice, round admission, Editor, registration, independent Verifier, promotion and exact reentry |
| Previously promoted entry | Actual Phase 1 promotion, Phase 2 correction with different bytes, second promotion, replay against original ordinal-one base |
| Restart without mutation | Fresh Python process opens the promoted root, reconstructs original transaction inputs and reports current work; files remain identical |
| Prior authority on failure | Invalid proposal, deterministic candidate rejection and semantic rejection never promote; deterministic rejection uses no Verifier |
| Interrupted publication and execution | Round commit, Editor raw response and Verifier raw response lost acknowledgements recover without duplicate clients |
| Promotion and final-state uncertainty | Actual pointer replacement and final state write lose acknowledgements; reopened owners recover without another promotion |
| Source/authority barriers | Changed evidence references, base pointer, constraints, round number, missing advice and unrelated round selector refuse |
| Budget and legacy behavior | Existing accounting and default preflight behavior retained; no additional Reviewer pass is allocated by admission or transaction work |

These are scripted semantic assessments and process-local fault hooks on macOS/APFS.
Fresh-process reopening is tested; physical power loss, process killing, live semantic
truth and public-provider transports are not qualified. Historical replay is expensive:
the strengthened promoted-entry method took 403.723 seconds in the concurrent local
campaign. No performance claim is made, and reducing repeated historical work without
weakening freshness checks merits later attention.

Remaining feature work: automatic advice production, operator decision and semantic
followup routing in Phase 2, subsequent profile requests and corrections, version
maintenance through candidates, convergence/declaration, other scheduler modes, full
terminal reporting, apply-back safeguards and 18.9 qualification/activation. All four
18.8 tasks remain incomplete. No public mode, external transmission or external
specification apply-back is included. The next functional milestone is continuing
review on the newly verified Phase 2 draft through the supported profile sequence;
this milestone alone does not authorize that work or advertise convergence.

Follow-up (2026-09-24): [Phase 2 continuation](VNEXT_18_8_PHASE2_SEQUENCE.md) now
validates later reviews, another correction/promotion and ordered profile advancement
under a separate pin. This first-only checkpoint retains its original scope; the
next open functional boundary is current-lineage closeout/declaration handling.
