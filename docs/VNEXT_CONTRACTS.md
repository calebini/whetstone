# Offline vNext contracts

Slice 18.2 publishes `vnext-contracts-1`: 25 pinned schemas, two normative algorithm documents and 52 fixed conformance vectors. The implementation registry binds this version to one exact manifest digest. This is an offline Python API; it does not add CLI modes, run clients, assemble candidates or promote drafts.

From the repository root:

```sh
PYTHONPATH=src python3 -c 'from whetstone.vnext_contracts import validate_contract_suite; suite = validate_contract_suite(); print(suite.version, suite.digest)'
PYTHONPATH=src:tests python3 -m unittest test_vnext_contracts -v
```

The [manifest](../contracts/suites/vnext-contracts-1.json) pins schema, algorithm and fixture bytes. Validation recomputes its canonical digest, matches the [supported registry](../src/whetstone/vnext_registry.py), confines paths, checks every transitive schema dependency, audits supported schema keywords and executes every declared vector. Changed files, unknown versions and caller-selected digests cannot claim the published suite identity. Copying the complete contract package to a different directory preserves its identity. There is no historical artifact migration.

The [identity specification](../contracts/algorithms/vnext_identity_v1.md) owns exact ordered preimages, full SHA-256 identifiers and dependency order. The [invariant specification](../contracts/algorithms/vnext_contract_invariants_v1.md) owns validation order and the offline predicates. Schemas declare required fields, explicit nulls, closed object shapes, field ownership and migration policy. Persisted artifacts use canonical UTF-8 JSON without a BOM or trailing newline. Floats, duplicate keys and invalid Unicode are rejected. Imported finding and policy references retain their original identifier contracts.

Prepare immutable seed, authority, protected-invariant, approved optional scope and review-configuration inputs first. Their hashes plus the registry-derived suite digest determine the job ID. Authority and invariant inputs contain no job backlink; section IDs are computed after the job exists. Descriptor locators may change when a package moves, while internal logical paths and exact input bytes remain bound. The bootstrap API takes a separate review-configuration reference because the descriptor pins its hash without a locator.

`validate_bootstrap(root, descriptor_ref, suite, review_configuration_ref=...)` in [vnext_validation.py](../src/whetstone/vnext_validation.py) returns a reader and validated job, authority and invariant objects. References are `{path, hash}`; the reader checks exact bytes, canonical JSON and schema membership. Use the schema-validated objects with the individual section, plan, patch, report, decision, registration, disposition, pointer and terminal validators in dependency order. These functions are composable evidence checks, not a single runtime admission or promotion gate. `derive_job_id` and the helpers in `vnext_identity` are pure derivation functions; deriving an ID alone does not validate an artifact or admit a suite.

The [toy bundle](../tests/vnext_fixtures.py) models a queue requirement changed from “Wait at least 30 seconds” to “Wait 30 seconds or longer.” Its complete, fictional evidence chain exercises bootstrap through terminal readback without a model or authority write. The [32 focused tests](../tests/test_vnext_contracts.py) also reject altered hashes, missing semantic coverage, unsafe uncertainty, invalid operation counts, stale target maps, wrong candidate identities, broken event ordinals, swapped verification pointers and inconsistent pointer-history bytes. Schema-only vectors test shape; the joined journey and tampered graph cases test cross-artifact consistency.

Passing these checks establishes consistency of supplied evidence. It does not prove the truth of a semantic report, payload assembly, section transfer, operation overlap, exact operator effect authorization, storage ownership or current runtime authority. Those remain later-slice gates. Candidate assembly conformance is required before stable promotion but is not claimed by this foundation. The recognized parser, assembler, inventory and verifier policy names reserve contract bindings; they do not advertise implemented services.

The next slice is 18.3 job admission and mode gates, after D7's processing transition table is resolved. Existing legacy and opt-in preservation-bridge workflows retain their current behavior.

Validation checkpoint: all 547 tests passed in full discovery, including the 32 focused vNext tests. The [D6 audit recheck](audits/VNEXT_D6.md) passed with zero findings. Exact tested-input hashes, suite digest and logs are retained under `rounds/vnext-contracts-001/`.
