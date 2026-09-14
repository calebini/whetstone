# Staged proposal input packages (under development)

This private 18.5 entry connects exact source inputs to a genuinely fresh proposal run. It does not register a shipping suite, qualify D8 or activate proposal mode. Existing reviewer-only selection and legacy/bridge dispatch remain unchanged.

## Package and limits

`vnext-proposal-package-v1` is a closed canonical JSON envelope containing `job_descriptor`, `review_configuration` and `mutation_constraints` references, each exactly `{path, hash}`. References use confined relative logical paths inside the source package. There is no mode override, caller-selected suite digest, imported run state or implicit mutation limit.

`vnext-mutation-constraints-v1` wraps the existing closed round `constraints` object: explicit allowed operation types, operation/changed-section/changed-normative-unit maxima and required context binding IDs. Every required context must resolve to an admitted non-excluded authority binding. These are explicit default constraints for a later admitted transaction; they grant no removal, weakening, scope or authority change. Required operator evidence remains separate. A separately explicit round admission still follows the existing transaction rules; these defaults are not a new global authorization policy.

The package and its constraint artifact are retained by exact bytes. The optional `launch_package` reference in the unregistered `vnext-proposal-run-input-v1` record selects them. Existing explicitly staged round runs may omit it. Every base validation rechecks the package, its descriptor/review hashes and exact referenced constraints. For packaged live review, the immutable input projection includes the launch-package reference. Rehashing the package and limits after a committed review cannot preserve that request's input binding across reopening.

## Read-only preparation

`prepare_proposal_package` opens a source directory and reads only the manifest and its transitive descriptor-bound inputs: descriptor, review, seed, authority, invariants, optional scope and non-excluded context, plus the explicit constraint artifact. It never recursively copies the directory. Excluded documents are not opened, even if present. References to unknown or excluded required context fail.

Source reads use directory-relative no-follow opens, require regular files and use nonblocking opens so a FIFO cannot stall admission. The physical source root must remain the same. Duplicate reads must yield identical bytes; all captured inputs are reread after the snapshot is built. JSON artifacts require canonical bytes and exact hashes, and the descriptor selects the suite through the implementation registry. An unknown suite is rejected before selecting its manifest path. Installed schema pins must match the admitted suite.

Input paths may live outside `inputs/` when explicitly referenced. Preserve their logical spelling and exact bytes; changing host roots does not relocate embedded authority paths. The `rounds/` namespace, storage temporaries, runtime mirrors/config/state and control directories are reserved. Derived input locations `inputs/proposal_run.json`, `inputs/proposal_package.json` and `inputs/section_identity_map_seed.json` are reserved too. Reservation checks account for case aliases on the supported local filesystem. The canonical descriptor output cannot collide with a different input. Descriptor locators may differ from `job_descriptor.json` only when the copied canonical descriptor has identical bytes.

Preparation derives the seed section map from validated seed bytes and the admitted mutable binding. It derives the ordinal-zero pointer and its byte-identical history snapshot; the seed timestamp uses the descriptor's supplied creation timestamp. It neither normalizes nor rewrites an already bound seed. Full seed/profile/workflow/scope, invariant program and inventory validation occurs before any destination directory exists. The same `prepare_proposal_storage_inputs` validator serves direct staging and package preparation.

The prepared result retains an immutable byte snapshot and exact selectors. It is evidence of input validation, not runtime capability or a storage claim.

## Fresh-root creation and later admission

`PreparedProposalPackage.create` rereads and revalidates the source package and suite, requires equality with the prepared snapshot, and then invokes the existing exclusive D8 initialization. The destination must be outside the read-only source package and must not already exist. No legacy, bridge or previous vNext root is upgraded. Interrupted initialization retains its files for diagnosis; it is not overwritten by a second admission. After initialization, return a reopened `ProposalRun` with all retained selectors and bindings validated.

The source manifest is copied unchanged to `inputs/proposal_package.json`; the canonical descriptor, derived seed map and ordinal-zero snapshot/current pointer are generated at their named runtime locations. Only the named referenced inputs are copied. Seed-first creation includes no Reviewer feedback, mutation plan, candidate or decision.

`ProposalRun.admit_reviewed_round` requires this retained package and a committed live Reviewer result at finding admission. It takes the exact Reviewer feedback/advice references, the committed seed base and explicit packaged constraints, plus any separately supplied already-retained decision references. Existing full preflight and canonical round publication then run under storage ownership. No limit, finding, grant or operator answer is inferred from client prose. Sensitive/unresolved decisions still fail before a round input is published. The existing round entry can subsequently execute the admitted Editor request through its bounded candidate endpoint.

The [guarded command consumer](vnext_proposal_cli_v1.md) adds source/destination selection, operational configuration, status and continuation routing. The [operator consumer](vnext_operator_decisions_v1.md) adds explicit request/response interaction and separately selected decision receipts. Both remain unactivated. D8 audit/reconciliation and final consuming-suite registration remain release work. A package cannot activate any unavailable mode.
