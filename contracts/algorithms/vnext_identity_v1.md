# vnext-identity-v1

This is the schema-owned identity and byte contract for the offline vNext contract suite. It refines the candidate leaf's D6 rules. It has no runtime admission or promotion capability.

Canonical JSON (`whetstone-canonical-json-v1`) uses UTF-8, no BOM, no trailing newline, lexically sorted object keys, compact separators and unescaped Unicode. Arrays retain order. Integers, booleans and null are distinct; floats, non-finite numbers, duplicate object keys, non-string keys and unpaired Unicode surrogates are invalid. JSON artifact hashes cover these complete canonical bytes, including timestamps. Raw Markdown/payload hashes cover exact bytes. Timestamps are UTC second precision ending in `Z` and are omitted only from the named identity projections below.

For every row, concatenate the prefix, `_`, and all 64 lowercase hex digits of SHA-256 over canonical JSON `[domain, ...arguments]`. `P(object; excluded...)` means the complete object with exactly those named top-level fields omitted. References and metadata are included unless explicitly excluded. No hash truncation or implicit default insertion occurs.

| Identity / collision role | Prefix | Domain | Ordered arguments |
|---|---|---|---|
| Job | job | whetstone-job-id-v1 | schema version, editing mode, suite version, registry-derived suite digest, parser version, assembler version, inventory version, normalization version, verifier policy version, seed hash, authority hash, scope hash/null, invariants hash, review-configuration hash, expected source hash/null |
| Authority binding | bind | whetstone-binding-id-v1 | `P(binding; binding_id, path)` |
| Protected assertion | assert | whetstone-assertion-id-v1 | seed/base hash, `P(assertion; assertion_id)` |
| Operator response | resp | whetstone-response-id-v1 | `P(response; response_id, decided_at)` |
| Slice | slice | whetstone-slice-id-v1 | `P(slice; slice_id)` |
| Transaction | txn | whetstone-transaction-id-v1 | `P(plan; transaction_id)`, array of `[response_id, exact_response_hash]` sorted by response ID |
| Operation | op | whetstone-operation-id-v1 | transaction ID, `P(operation; operation_id)` |
| Proposal | pro | whetstone-proposal-id-v1 | complete canonical patch set with `proposal_id` set to null |
| Candidate | can | whetstone-candidate-id-v1 | transaction ID, base hash, exact persisted patch hash, assembler version, normalization version |
| Seed section | sec | whetstone-seed-section-id-v1 | job ID, seed hash, mutable document binding ID, section preorder ordinal |
| Inserted section | sec | whetstone-inserted-section-id-v1 | transaction ID, creating operation ID |
| Seed inventory unit | unit | whetstone-seed-unit-id-v1 | seed hash, owning stable section ID, unit kind, same-kind ordinal |
| Inserted inventory unit | unit | whetstone-inserted-unit-id-v1 | transaction ID, operation ID, kind, payload ordinal |
| Candidate creation event | creation | whetstone-creation-id-v1 | `P(event; creation_event_id, created_at)` |
| Candidate disposition event | event | whetstone-disposition-id-v1 | `P(event; event_id, recorded_at)` |
| Promotion intent | intent | whetstone-intent-id-v1 | `P(intent; intent_id, prepared_at)` |

Section seed/inserted forms share one stable-section role; unit seed/inserted forms share one inventory-unit role. They have distinct domain labels. Imported issue/feedback IDs and named policy/decision/option references retain their existing owning grammar and are not minted by this algorithm. Artifacts without a minted ID are addressed by their exact canonical hash.

Authority and invariant inputs contain no job ID. Scope and review configuration contain no references to job-derived outputs. Authority scopes are exact named symbols, without wildcard or implicit ancestor expansion. Input paths are normalized relative logical package paths; host relocation leaves those bytes unchanged. Descriptor locator paths and its timestamp are excluded from job identity, but changing any logical input binding changes its hash and requires a new job ID.

Slices are constructed in dependency order before the transaction. Operator responses are supplied and hashed before transaction identity. Operations are constructed in dependency order before proposal identity. The admitted finding set is the sorted set of admitted canonical issue IDs; no second target set exists. Array ordering remains bound by the containing artifact; an order change to a stored plan or claim is a new identity even where its set membership is unchanged.

Before computing persisted operation IDs, the Orchestrator validates the client envelope, resolves local operation labels/dependencies, validates payload bytes, normalizes payload paths to `payloads/{hash}.md`, and replaces labels with derived IDs in dependency order. Duplicate operation labels/IDs, missing dependencies and cycles fail. Lexically smallest currently-ready operation ID determines stable topological order. The proposal projection contains the normalized operations; the final patch hash includes the injected proposal ID.

Within one job, one ID must denote identical canonical preimage bytes and one role. Identical preimage/role is replay. A different preimage or role is a collision and fails closed. Validators recompute identities; labels or client claims cannot override them.

All object contracts are closed except the explicitly typed matcher-value object, whose canonical data is a query/semantic assertion input, not executable code. Required nullable fields must be present. Descriptor scope and external source path/hash pairs are both null or both populated. Unknown schema/algorithm/suite versions have no implicit migration.

Schema ownership: the Orchestrator produces every persisted artifact. Operator response choice/effect/rationale/actor are adopted operator inputs. Patch operation reasons, finding attribution, normative-change claims, payloads and decline explanations are Editor inputs; persisted job/transaction/proposal/operation bindings are validated or derived. The Editor client schema requires a null proposal ID and local operation labels. Verifier client output contains findings, assertions and verdict claims; the Orchestrator injects job/candidate/hash/map/verifier-identity context from frozen inputs. Neither client envelope is a persisted acceptance artifact.
