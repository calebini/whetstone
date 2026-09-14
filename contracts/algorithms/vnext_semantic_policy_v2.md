# Semantic policy v2 (unactivated consumer)

The proposed `semantic-policy-v2` is selected only by an immutable descriptor and a future supported consuming suite. The frozen `semantic-policy-v1` and first-suite schemas are unchanged. Neither installed files nor successful isolated tests advertise runtime availability.

The client returns `semantic-verification-v2` under the closed `semantic_verification_client_v2` schema. It copies the exact context hash, supplies full finding/operation/semantic-assertion and preservation coverage, and proposes aggregate findings, uncertainty mappings and a verdict. IDs, creation/input bindings, role identity, persisted request references and raw-response hashes are Orchestrator-owned. Client uncertainty entries use `decision_id = null`; the Orchestrator fills an identity only after constructing and validating a concrete request. Supplying an identity or a contradictory context hash is a binding failure, never shape repair.

The Verifier must assess every admitted finding and operation exactly once, and every semantic assertion exactly once. Each operation's `editor_claim` must copy its exact patch `normative_change`; the Verifier independently supplies its assessment and agreement. A disagreement is evidence, not an automatic semantic failure: an Editor could misclassify a harmless change. Findings, assertions, operation assessments and overall rationale require non-whitespace evidence. Complete exact unit/group/diagnostic coverage follows `vnext_semantic_coverage_v1.md`.

## Exact uncertainty mapping

Each uncertain field has exactly one entry, with its exact field path, rule ID and disposition. Unknown, duplicated, missing, extraneous or version-mismatched mappings are artifact-invalid.

| Uncertain field | Rule ID | Disposition |
|---|---|---|
| `unrelated_semantic_change` | `semantic-policy-v2/unrelated-change-reject` | reject |
| `lost_or_weakened_semantics` | `semantic-policy-v2/semantic-loss-reject` | reject |
| `authority_compliance`, without a concrete valid choice | `semantic-policy-v2/authority-unresolved-reject` | reject |
| `authority_compliance`, with a concrete valid choice | `semantic-policy-v2/authority-choice` | operator_decision_required |
| `semantic_assertions/<assertion_id>` | `semantic-policy-v2/assertion-uncertain-reject` | reject |
| `coverage/results/<obligation_id>` | `semantic-policy-v2/coverage-uncertain-reject` | reject |

This policy declares no assertion operator gate. Advisory assertions may fail without alone preventing pass, but uncertainty still needs the explicit reject mapping. No uncertain value is coerced into pass or `not_applicable`.

If any uncertainty entry rejects, the overall verdict must reject. Otherwise, if an entry requests an operator decision, the overall verdict must be `operator_decision_required`. This follows the candidate leaf's explicit mapping order; a rejected candidate is never retroactively verified by an answer. A valid request can remain evidence alongside a reject-dominant mapping without changing that rejection into an operator verdict.

`pass` requires all admitted findings resolved, no unrelated or lost/weakened semantics, authority compliance, every blocking semantic assertion passing, every preservation coverage result passing and no operator request. `not_applicable` cannot satisfy a blocking assertion. A reasoned reject does not need to invent an uncertain field. An operator verdict always requires a concrete bound request; a bare flag or rationale cannot create one.

## Concrete authority-choice request

The sole operator gate is uncertainty about the interpretation of applicable authorities. The Verifier proposes a question, a mutable-target authority scope, and at least two distinct alternatives. Each alternative names a different admitted mutable-target/normative-authority binding in that scope, gives a distinct nonblank interpretation, and cites a nonblank exact UTF-8 excerpt with byte offsets and content hash. Excluded, undeclared, reference-only, cross-scope or missing documents cannot supply alternatives. The entire document content must match its binding; the excerpt must match those exact bytes. Malformed supplied choices are artifact-invalid, not silently downgraded to unbound operator pauses.

The Orchestrator builds closed `vnext-semantic-authority-request-v1` with job/transaction/candidate, exact context and committed creation reference, authority-map hash, pinned Verifier, exact raw-response hash, concrete choice and `resolution_scope = new_transaction_only_no_authority_change`. The request grants no effects, edits, waiver, replacement authority map or precedence override. Natural-language interpretation remains a matter for the operator and fresh transaction preflight; the existence of the request cannot alter immutable authority policy.

Request identity is `dec_` plus SHA-256 of canonical JSON:

```text
["whetstone-semantic-authority-decision-v1", request_without_decision_id]
```

The request's canonical locator is `<registered candidate directory>/semantic_decisions/<decision_id>/request.json`. The separately derived `semantic-verification-v2` report binds that locator/hash and replaces only the operator uncertainty entry's null decision identity. It also copies all creation/report/input/role bindings from the frozen context and binds the exact raw response. Including the raw response hash does not create a cycle because the client cannot precompute or supply the generated decision identity.

Readback redecodes the original raw bytes under the same context/policy and requires exact report/request equality. A fabricated request, altered evidence or rehashed report cannot pass merely by satisfying a schema. Persisting dependencies, proving native invocation independence, committing a disposition and presenting/answering the operator request remain separate consuming steps. A response must lead to a new transaction and fresh verification; it cannot reopen a final rejected candidate.

## Failure categories

Malformed JSON/schema raises `SemanticShapeError`, eligible only for D7's bounded shape retry. Missing local contracts, unsupported policy, contradictory input/role/claim bindings, incomplete coverage, false excerpt hashes or unsupported policy mappings are technical artifact failures, not valid semantic verdicts and not semantic repair instructions. Missing/timed-out transport likewise cannot be fabricated as rejection by this pure decoder. The durable consumer must keep such candidates unverified and retain the actual cause.

## Registered admission and native boundary

`load_registered_semantic_context` reads the exact committed candidate through the existing request/handoff/registration chain. It refuses registration orphans, unregistered candidates and failed deterministic reports. The descriptor must select this policy, all semantic schema dependencies must be pinned, and every consumed semantic algorithm must match both its pinned suite artifact and installed bytes. Installed files alone cannot activate an older proposal suite. The underlying admission reader currently supports only the committed seed base; it cannot reseed a promoted draft or qualify historical promotion behavior.

`semantic_verifier_prompt` is separate from the Editor prompt and includes the complete immutable context, exact context hash, self-contained response shape and supported uncertainty rule IDs. It labels Editor claims as untrusted, requires complete preservation coverage and explains the no-waiver/new-transaction authority-choice boundary. Prompt instructions supplement, but do not replace, native capability enforcement.

`NativeSemanticVerifierClient` reuses the existing raw process transport with the pinned Verifier identity and dedicated schema. Codex receives the existing read-only sandbox, disabled web search and ephemeral invocation controls. Claude receives no tools and no persistent session. Each call is a new native invocation; same-model Editor/Verifier calls have distinct prompts, output schemas and processes. The native adapter preserves exact raw response bytes and telemetry and performs no automatic retries. Timeout, process/provider errors and schema drift remain transport/technical failures. A scripted real-process test exercises complete registered context through native output decoding without changing any candidate or draft authority. No live model reliability or durable request/decision qualification is claimed by that test.

The caller must still validate candidate decision finality and claim a durable bounded invocation before calling the adapter. This admission reader and adapter are not a public run command, request journal or candidate decision commit. The semantic result cannot advance authority until the separate durable consumer has retained and validated every dependency and committed its candidate-local decision pointer.
