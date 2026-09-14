# Candidate registration journal implementation

Status: isolated implementation for slice 18.5, not a registered runtime capability. The D8 design still awaits external audit. These rules, the preparation schema and conformance tests must be pinned by the consuming suite before public proposal-only admission. The frozen first suite, existing descriptors, legacy jobs and preservation bridge are unchanged.

## Inputs and remaining admission boundary

`CandidateRegistry` uses the proposed `LocalAuthorityStore` and checks the exact storage-bound descriptor, editing mode and implemented parser/assembler/inventory/normalization versions. It refuses the frozen first suite. It requires two read-only domain callbacks: validation of the admitted descriptor/suite and current committed authority, and loading of immutable assessment inputs for a particular round/proposal. These callbacks must not invoke clients or mutate authority. The adapter does not turn an arbitrary suite string or empty callback into runtime admission.

The loader supplies authority, invariants, review configuration, original seed/map, committed base/map/inventory, and exact named-unit decision bindings where needed. Complete Reviewer classification, admitted transaction provenance and committed base-history validation remain the caller's responsibility. Historical candidate readback must load its original committed base; it must not re-seed the current draft. A newly submitted transaction also needs the scheduler's current-base and request-admission checks. The registry reads the canonical round mutation plan, canonical proposal and every referenced payload itself, checks their job/proposal/hash bindings and the descriptor-bound Editor, and independently assembles the candidate and section map.

The registry runs deterministic assessment, preserves its report and retains a candidate inventory only when lineage can be derived. A deterministic failure with a valid assembled section map can be registered as initially unverified; registration is neither acceptance nor a semantic verdict. Failed/ambiguous unit correspondence retains a failed report with explicit unknown inventory, not invented successor identities. Assembly or section-map construction failures before a registration package exists still require the outer proposal-attempt failure-artifact path; this adapter does not claim that remaining integration is implemented.

## Preparation, publication and commit

Canonical artifacts live under `rounds/round-N/candidates/{candidate_id}`. Candidate identity uses the descriptor-bound D6 preimage, including transaction, exact base and canonical patch hash. The adapter prepares candidate bytes, the section map, preservation report, optional candidate inventory, and initial `candidate_created` disposition event. The initial event always records `CANDIDATE_UNVERIFIED`, null previous disposition/event, event ordinal 1, and the same creation ordinal as the pending creation event.

Before publishing those candidate artifacts, the writer publishes a closed canonical `candidate-registration-preparation-v1` record at `registration_preparation.json`. It contains the complete intended `candidate-creation-event-v1` and a sorted exact path/hash list of candidate artifacts and the initial disposition event. A single prepared UTC timestamp supplies both event timestamps. Preparation has no authority and is not a mutable index, lease or alternate commit point. Its new schema does not change the frozen v1 creation-event bytes or identity algorithm.

Under the retained D8 lock, publication proceeds as follows:

1. Validate the current authority and complete existing creation chain, reconcile an orphan before allocating another ordinal, and independently reconstruct the proposed candidate.
2. Publish the preparation record, candidate bytes, section map, deterministic report and optional inventory. Each publication uses the storage adapter's immutable durability protocol.
3. Publish initial disposition event ordinal 1.
4. Read the persisted candidate bytes and section map, require exact independent reproduction, and assess those persisted values again. Require the preparation, report, inventory and initial event to equal the reconstructed immutable artifacts.
5. Publish `rounds/candidate_index/creation-{ordinal}.json` last. This exact immutable creation event is the registration commit point.

The creation event binds candidate/map/initial-event hashes and paths, proposal/transaction identity, and the exact previous creation-event hash. The preparation must contain that byte-identical committed event. Every readback also reconstructs the report/inventory from admitted immutable inputs; a rehashed preparation file cannot redefine candidate meaning or validate changed bytes. Preparation is not a substitute for descriptor, proposal, base lineage or event authority.

## Ordering, replay and recovery

Creation ordinals start at 1 and form a unique contiguous chain. Alternate ordinal spellings, gaps, non-file journal entries, incorrect job or event identity, broken predecessor hashes and duplicate candidate registration halt artifact-invalid. Canonical candidate/map/initial-event paths are derived from the event's exact round and candidate identity and must reproduce. Missing, noncanonical, changed or rehashed-but-inconsistent dependencies halt. Temporary names are excluded from authority; listing is confined, disallows special files and symlink traversal, and never repairs.

`latest` is the highest valid creation ordinal. A later timestamp, round number, lexically greater candidate ID or directory enumeration cannot override it. A byte-identical candidate replay reuses its original creation event, timestamp and ordinal, including when requested from another round. It does not create a second candidate directory or append an event.

An unreferenced candidate directory is an orphan. Read-only inspection returns orphan paths separately from registered events and never selects an orphan as latest. Writer recovery refuses multiple unresolved orphans rather than choosing by enumeration. The sole orphan may finish only if its preparation claims the one next ordinal and exact predecessor and all candidate/map/report/inventory/initial-event artifacts already exist and independently validate. Recovery repeats dependency durability barriers, then publishes the prepared creation event unchanged. Missing or contradictory prepared artifacts are preserved and cause artifact-invalid; the registry does not synthesize missing initial events, overwrite corrupt files, discard the orphan or register later work around it.

A complete visible creation event may have lost its prior acknowledgement before the final storage barrier. Every writer acquisition validates existing events and repeats their exact immutable-publication durability barriers before returning a successful replay, recovering an orphan or allocating another ordinal. Another barrier failure remains uncertain, invalidates ownership and halts. There is no rollback, duplicate registration or model invocation to resolve this condition.

All registration operations share the same storage exclusion that the later verification and promotion consumers must use. Busy acquisition grants no token or mutation. Read-only inspection takes no exclusive lock, may observe a complete newly published event before durable acknowledgement, and never grants source-write permission. This journal does not advance `current_verified.json`, produce `draft_after.md`, verify a candidate, or reopen a final candidate decision.

## Qualification limits

Tests cover all seven publication-stop prefixes of a package with inventory; only a complete prepared orphan can finish, while earlier incomplete prefixes preserve evidence and halt. They also cover two real competing processes, ordinal ordering, exact replay across rounds, failed deterministic reports, missing/changed/rehashed dependencies, ambiguous orphan claims, creation acknowledgement loss followed by a failed and then successful recovery barrier, and read-only listing. Primitive lock/fork/exec/process-death and filesystem-failure tests remain in the storage suite.

The isolated fixtures use an explicitly unregistered test suite and a minimal test authority callback. These results do not qualify complete descriptor/suite admission, committed seed/promotion-chain loading, native Editor-to-registration scheduling, D7 logical-request continuation, semantic verification, promotion, physical power loss or public runtime activation. Those remain the consuming slices' obligations, together with the D8 audit.
