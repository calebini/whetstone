# Seed Reviewer requests for proposal runs (under development)

This private 18.5 consumer joins fresh seed admission to live Reviewer feedback and subsequent explicit round admission. It is not a published capability, D8 ratification or an independent semantic verifier. The shipping suite and existing Reviewer-only implementation remain unchanged.

## Inputs, transport and classification

Revalidate the admitted descriptor, registered suite pins, physical root, seed/current pointer, map, authority, scope, invariants and review configuration before selecting work and before publishing its result. The prompt embeds the seed, section anchors and every permitted bound context document with its declared role. Excluded documents are omitted. The typed input projection and original prompt are immutable request evidence.

The native Reviewer uses the existing read-only Codex/Claude transports with the pinned Reviewer identity and a structural provider schema derived from `vnext-review-response-v1`. Its raw envelope contains `feedback` and `classifications`; it cannot produce plans, grants, candidate decisions or authoritative advice bindings. Canonical validation remains stricter than the provider's structural hint. The orchestrator validates round/profile/draft/actor bindings, canonicalizes source issue identities and severities, constructs exact finding-advice bindings, and independently reruns the existing classification rules. Advice must cover each source feedback ID exactly. Sensitive effects and authority/scope conflicts cannot become editing permission through advice alone.

## Round selection and immutable claims

`ProposalRun.review_next` selects the next seed Reviewer work; callers cannot supply a round or profile to reset its allowance. It accepts only a run with no initially staged proposal rounds. Starting a new sequence requires a seed-only root without prior round processing.

`rounds/review_index/request-N.json` contains a canonical closed `vnext-review-request-v1` claim. Claims begin at one, are contiguous, and bind the job, selected round/profile, input hash, exact transport and previous claim hash. Request IDs use the existing logical-request domain over `[job_id, reviewer, phase1, review, round_number, profile]`. Replay must reproduce both the claim and selection from committed predecessor results. A later claim cannot skip an unfinished request or a finding/budget boundary. An already admitted proposal cannot be bypassed by starting another review.

Use configured profile order and budgets. Horizontal review finishes the current profile before moving on; vertical review rotates after each completed round and skips clean profiles. A committed valid response consumes one profile round; shape repair consumes an invocation slot within that same round. Clean means no in-scope major/blocker feedback under the existing review policy. All configured profiles must be clean for `phase_1_stable`; any uncleared exhausted profile yields `budget_exhausted`. These are seed-review boundary results, not convergence or candidate verification.

Any deterministically classified finding other than `deferable` stops the sequence at `finding_admission`. The consumer neither fabricates operator options nor selects a decision. An editor-fixable response can feed existing explicit round admission with supplied constraints. Other classifications retain the existing exact decision/authority gates. Further review after candidate processing belongs to the later scheduler/promotion consumer.

## Two invocation slots and recovery

Each request directory retains its original prompt, two possible numbered attempts and a final result receipt. Publish each attempt prompt and invocation marker before calling the client. An invocation binds request/input/prompt/transport, its attempt number, reason and previous outcome hash. The second invocation cannot exist without the first retained invocation and the exact stored predecessor outcome.

Only JSON/schema shape failure permits one automatic repair under unchanged inputs. Contradictory bindings or invalid classification evidence are semantic input failures and cannot receive shape repair. Timeout, transport failure or an invocation with no durable result requires explicit technical continuation. Across restarts there are at most two invocation slots total. The first invocation must use the complete originally claimed transport, including after an interrupted claim. A later invocation may change only transport timeout; client/model/command/cwd/schema identity stays frozen. Exhaustion preserves the last actual cause.

Retain exact response bytes before decoding and publish the outcome. Read-only inspection independently decodes responses and derives a missing unbound outcome without writing it. A bound missing predecessor, an orphan response/outcome/telemetry, an unknown attempt, a contradictory outcome or an invocation without a request claim is invalid; it cannot reset the budget. A valid retained response can finish publication on explicit continuation without another client call. A closed invalid response cannot reopen.

Publish canonical `rounds/round-N/reviewer_feedback.json` and `finding_advice.json`, then `result.json` last. The result binds both references and the deterministic classification/evidence hash. Replay repeats prerequisite durability barriers before the result and repeats completed results before claiming a later round, covering a lost publication acknowledgement without duplicating work. All mutations use the proposed D8 ownership/publication kernel; uncertain storage remains an error, never success inferred from client output.

## Admission provenance and status

Once a live Reviewer sequence exists, any round admission must select its exact committed feedback/advice references. Copying the same feedback to another path or substituting rehashed advice cannot evade that provenance check. Externally supplied round packages remain a separate explicit admission route when no live sequence exists.

`review_status` validates and projects the sequence without locks, calls or repairs. Selected-round status projects live review state only for the actual selected round; future rounds do not inherit another round's resumability. Fresh work is not technical continuation. Prepared/interrupted work and valid output awaiting publication expose bounded recovery; invalid/exhausted responses cannot receive another client call. Findings expose `finding_admission`. The [seed phase closeout consumer](vnext_seed_review_closeout_v1.md) derives clean/exhausted/failure terminals and exposes only `materialization` when a final report is missing, or `complete` when it is present. No status claims a candidate or automatic operator choice.

Public package/configuration/CLI routing, decision interaction, reviewed D8 reconciliation and final consuming-suite qualification remain release work. Scripted process fixtures qualify transport/recovery behavior only; no live model or semantic preservation claim follows from them.
