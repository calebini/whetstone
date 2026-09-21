# First verified Phase 2 Reviewer request v1 (unactivated)

This bounded consumer publishes the first request only. It requires this algorithm,
vnext_phase2_review_request_v1, phase2_reviewer_feedback_input and its reviewer_feedback
and common dependencies, controlled_vocabulary, vnext_review_request_transport_v1 and
review_configuration_v1 pins, in addition to the entry/binding/Phase 1 pins. Validate
installed bytes against every pin. Frozen suite 1 and shipping maps are unchanged.

Require the committed unchanged-draft entry, its matching derived state, current
verified pointer, complete Phase 1 prerequisites and immutable configuration/request.
Do not implicitly bind, enter, repair Phase 1/entry state, or perform version maintenance.
Existing work/materialization recovery precedence applies; recovery ends the invocation.

Select only profile step 1 and pass 1. Retain all ordered configuration steps, including
the repeated strict-check step and their independent explicit budgets. The first round
number is one greater than the maximum completed Phase 1 review round in the bound
closeout. Request preparation/publication consumes zero accepted Reviewer passes.
No second request, profile advancement, retry, budget extension or response is supported.

Bind the exact configured Reviewer identity and caller-supplied immutable transport:
command, cwd, positive timeout and output_schema_hash. Require that hash to equal the
pinned phase2_reviewer_feedback_input schema bytes. This is the ordinary feedback input
contract, not a vNext Phase 1 feedback/advice wrapper or a provider-specific schema.
A future executor must qualify the corresponding transport/response handling separately.
Transport binding does not authorize executing its command or transmitting any inputs.

Snapshot full controlled_vocabulary_packet() with canonical SHA-256
ed361ca15a34bf4d10e2703b4a82088718bc71b0b23fee1ddbc019b38a77ec86;
refuse another vocabulary under this consumer. Include the canonical draft section IDs,
profile lens, severity/invariant and oscillation vocabulary, exact standard-v1 rubric,
final/strict target, all ordered budgets, original seed, current verified draft/map,
authority/invariants/scope and nonexcluded reference context. Embed content in the prompt;
no ambient file reads are requested. Render phase_2 with the shared renderer. No declaration
is supplied and declaration review is explicitly inactive. Include exact schema references
and suite digest in the snapshot. Bind both snapshot and exact prompt bytes in the request.

Under the actual D8 fence, repeat pointer/mirror, Phase 1 receipt, closeout, bound
configuration/request/rubric/draft/map, seed/review/authority/invariant/scope,
reference context, entry and matching state barriers before publication. Revalidate the
immutable descriptor through storage binding checks; its initial durability belongs to
storage initialization, not a consumer synchronization call. Reproduce exact
inputs after source synchronization. Publish immutable inputs.json then prompt.txt under
rounds/phase2/review_requests/first/, reproduce inputs again, and publish request.json last
as the request commit. Reproduce committed evidence before returning. Never overwrite a
conflict or reconstruct a missing dependency of an already committed request.

Exact uncommitted dependency prefixes may be completed. Exact committed reentry repeats
all source/dependency/request barriers, consumes no budget and ends without invoking a
client. A lost final acknowledgement is not successful publication until replay barriers
succeed. Read-only preparation reports visible committed evidence, not durability proof.
Return detached values; mutation of caller inputs or results cannot confer authority.

These APIs do not dispatch a Reviewer, parse feedback, admit candidates, change current
verified authority, mutate run state, perform convergence/declaration/strop/apply-back,
or activate public modes. Historical entry anchoring after later promotion and the first
bounded invocation/result journal remain separate implementation work. Existing Phase 1,
legacy, bridge, versioning and frozen contracts retain their behavior.
