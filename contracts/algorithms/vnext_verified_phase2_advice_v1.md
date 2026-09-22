# First Phase 2 advisory attachment v1

This unactivated owner requires the new algorithm and binding schema, the existing
finding-advice schema and mutation-preparation algorithm, and every prerequisite
Phase 2 contract to be pinned before root creation. No frozen-suite mutation or
in-place migration. Only the first committed, consumed Phase 2 result is supported.

Accept an explicitly supplied vnext-finding-advice-v1 packet as untrusted advisory
input under the existing optional-advice contract. This API is an attachment consumer,
not a producer or attestation of Reviewer authorship. It performs no model call,
creates no invocation slot, and consumes no additional successful-review budget.
The existing Phase 2 response remains unchanged. No implicit advice is generated.

Require committed request, result and consumption, with exact replay of entry,
configuration, Phase 1 prerequisites, current pointer, rubric and source barriers.
Run the existing V classifier against exact result feedback and bound inputs. Advice
must cover source feedback IDs exactly and match job, base, feedback reference,
authority, scope and invariants. Classifications, stable targets and evidence are
computed, never accepted from a caller-authored plan or finding projection. Existing
scope/authority/invariant and policy/destructive guards override advisory claims.
Even editor_fixable classification is not canonical round admission or edit authority.

Read-only preparation accepts optional supplied advice, derives the prospective
binding and pending paths, and takes no writer fence. Without supplied or retained
advice it reports advice_required. This is not an operator decision request/pause.
Mutating binding snapshots supplied data, takes the D8 fence, respects existing
recovery/registration/promotion precedence, and repeats complete request/journal,
feedback/result/consumption barriers before any attachment publication.

Publish finding_advice.json first, then advice_binding.json as a distinct commit
under rounds/phase2/review_requests/first/execution/. A retained prefix fixes the
attachment and cannot be replaced after interruption. Reentry with no supplied
packet may use that retained attachment. Completed reentry repeats all barriers,
reproduces classification and the exact binding, and stops. A visible binding with
missing or conflicting dependencies refuses reconstruction even when the caller
supplies matching advice. Errors and lost acknowledgements propagate unchanged.
Return detached views. Do not rewrite consumption or alter its historical no-advice
findings, scheduler counters, original result, current authority or run state.

The binding records canonical_round_admission_not_implemented and false candidate,
next-review and phase-completion grants. It is not a proposal-round selector. The
Phase 1 historical review validator remains unchanged. Canonical Phase 2 round
admission, operator choices, candidate work, historical entry anchoring after
promotion, subsequent requests and automated advice production remain separate
integration boundaries. No external transmission, public mode, strop or apply-back.
