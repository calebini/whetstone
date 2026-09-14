# Proposal seed admission and fresh-root staging (under development)

This supplement describes the unactivated 18.5 `vnext_proposal_admission` consumer. It does not register a shipping suite or resolve D8. The published first suite and its Reviewer-only admission retain their existing algorithm versions and behavior.

The [staged package consumer](vnext_proposal_package_v1.md) now shares its no-write validation through `prepare_proposal_storage_inputs`. It copies only exact referenced input paths, derives initial seed authority and retains optional launch-package/default-constraint references. Extra named input paths outside `inputs/` remain confined and cannot occupy runtime storage. Direct prepared-round staging remains supported.

## Contract dispatch and exact reads

A descriptor selects a suite version whose canonical manifest digest must match the implementation registry. Descriptor algorithms must match that suite's complete implementation-owned version mapping. A caller-supplied digest, mutable `ValidatedSuite` object, installed schema filename, or different descriptor algorithm cannot grant a capability. Descriptor validation rereads the registered manifest and all pins before checking D6 identity. The compatibility `ALGORITHM_VERSIONS` name continues to describe only the first suite.

The proposal consumer requires the complete set of schemas used by admission, the durable request journal, handoff and registration, including indirect legacy schema dependencies. It also checks installed schema bytes against the validated pins because existing pure helpers load those files directly. The byte-reader bootstrap adapter applies the existing pre-job, role, authority, invariant and scope checks to confined storage reads; it does not bypass the storage kernel with filesystem paths.

## Seed and round provenance

`ProposalAdmission` freezes descriptor, review, seed-map and round-record selectors. Every callback rereads and revalidates them. This bounded consumer accepts `proposal_only` with the implemented parser, assembler, inventory and normalization versions. It requires the canonical ordinal-zero snapshot, identical current-pointer bytes, exact descriptor-bound seed bytes and a reproduced seed section map. It refuses a promoted or changed current pointer. Historical promoted-base admission remains a later requirement.

A closed `vnext-proposal-round-input-v1` record binds job, round, the exact seed snapshot, Reviewer feedback, optional classification advice, mutation constraints and exact decision request/response references. Feedback must match the selected round, pinned Reviewer/profile, canonical source identities and base hash. The consumer reads authority/context by admitted content hash, classifies the retained source evidence, reconstructs the complete seed inventory and named-unit approvals, and derives the plan and prompt through full preflight. It accepts no caller-authored inventory, findings, derived tasks or plan as authority. The durable request's input/plan/prompt bindings preserve this reconstructed evidence across continuation.

These callbacks connect directly to `run_proposal_request` and the completed-request registration factory. No extra Editor call is made for handoff, admission inspection or completed-result replay. The [bounded closeout consumer](vnext_proposal_closeout_v1.md) adds D7 decisions, terminal projections and failure evidence before candidate packaging.

## Fresh-root initialization

`initialize_proposal_storage` accepts an exact-byte staged package, freezes it, and validates every selected round before any destination creation. Permitted paths are local `inputs/` artifacts, the canonical descriptor, current seed pointer and ordinal-zero snapshot. Runtime requests, candidates and later history cannot be imported as initial authority.

It also retains the closed run-input selectors described in [stored proposal roots](vnext_proposal_run_v1.md). Zero selected rounds permits seed initialization before Reviewer work; normalization, profile/workflow/scope policy, assertion programs and seed inventory still validate first. After successful preflight, it invokes the proposed D8 initializer, which requires a genuinely nonexistent destination. Neither an existing Reviewer root nor an existing empty directory can be upgraded in place. The new physical root is then opened through `LocalAuthorityStore` and all selected inputs are validated again. The source package is unchanged. Initialization failure preserves evidence; it does not delete the destination, roll back publication or silently retry. Callers must close the returned store.

This initializer is not a public CLI or an approved D8 release. Qualification currently uses a temporarily registered test suite and fictional inputs, including scripted native Editor processes. Before shipping, pin the completed consuming contract set, reconcile the storage implementation with the reviewed D8 design, and qualify public configuration, CLI/status and continuation routing for the connected proposal-only endpoint.
