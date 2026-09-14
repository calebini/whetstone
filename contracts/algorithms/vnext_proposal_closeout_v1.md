# Bounded proposal-only decision and closeout (under development)

This is the unactivated 18.5 D7 consumer over the proposed D8 storage kernel. It does not enable a public mode, register a shipping suite, supply semantic verification, or authorize promotion.

## Failure before registration

Assembly and section-map construction run from the admitted plan, exact normalized patch and hash-checked payloads. A deterministic failure in either stage raises `CandidateAssemblyFailure`. During registration, its closed `vnext-candidate-assembly-failure-v1` diagnostic is immutably published in the owning proposal directory as `assembly_failure.json`. It binds job, transaction, proposal, round, base, plan and patch hashes and retains the exact stage, exception type and message. No candidate ID, map, disposition event or verification decision is fabricated. A diagnostic publication failure remains a storage failure and propagates. Read-only registration inspection never writes diagnostics.

## First candidate decision

`ProposalDecisionJournal` consumes the validated creation chain and independently reproduced candidate/map/report artifacts. In this bounded implementation it owns the first decision only:

- deterministic failure produces semantic `not_run`, final `CANDIDATE_REJECTED`, no promotion permission and concrete rejection codes;
- deterministic pass produces semantic `not_run`, non-final `CANDIDATE_UNVERIFIED` and no promotion permission.

No client is accepted by the decision journal. It cannot claim semantic evidence or add a later decision. Semantic continuation and higher ordinals must be qualified in 18.6 before that policy is extended.

Under the same exclusive storage ownership as registration, it writes the immutable candidate-local `candidate_verification-attempt-1.json`, then `disposition_events/event-2.json`, then an immutable exact pointer snapshot at `candidate_verification_pointer-attempt-1.json`. It atomically replaces `candidate_verification_current.json` from that snapshot only after revalidating source bindings, candidate registration and the expected predecessor. Decision, event and snapshot share the decision's retained timestamp so recovery reproduces exact bytes.

Only the pointer makes the verification event effective. Read-only inspection exposes prepared targets separately and retains the registration-bound initial event until a valid pointer exists. A malformed, stale or partially missing committed target is invalid; inspection never falls back to the initial event. Extra next-ordinal claims, event-without-decision claims and mismatched targets refuse. A single valid prepared decision is reused; its missing event/snapshot may be completed, then its pointer committed. Exact committed replay repeats dependency and pointer barriers without adding ordinals or changing timestamps. Uncertain storage acknowledgement propagates, invalidates ownership and requires actual readback; it is never treated as the intended disposition.

## Terminal projection and bounded round entry

`proposal_terminal_report` selects the highest contiguous creation ordinal, validates each candidate's decision state and projects the effective pointer-bound event. Earlier committed rejections remain listed. Before-registration failure leaves the prior registered candidate latest, or every latest-candidate field null when none exists. Unresolved candidate orphans and corrupt committed evidence require diagnosis/recovery rather than a fabricated valid report.

`finish_proposal_round` connects a completed durable request through exact handoff, registration, first decision and terminal-report-v2 materialization. Deterministic rejection yields `HALTED_ARTIFACT_INVALID` / `vnext_preservation_failed`. Deterministic pass without the 18.6 service yields `TARGET_NOT_REACHED` / `vnext_gate_unavailable`. Both have `resume.permitted=false` and `resume.next_gate=null`; an unavailable semantic gate is not advertised as resumable. Failure before packaging yields `HALTED_ARTIFACT_INVALID` / `vnext_assembly_invalid`, without a synthetic rejection.

`run_proposal_round` additionally invokes the existing durable request policy. Timeout stays `HALTED_CLIENT_TIMEOUT`, including timeout in the exhausted final slot. Other request failures stay artifact-invalid with the retained exact machine cause. Explicit proposal continuation is eligible only under the journal's frozen-input, current-base and remaining-slot rules, or to reuse complete output without another call. Shape exhaustion and deterministic proposal/assembly failures are not technical continuation. A fully materialized candidate endpoint cannot be reopened; a committed decision with missing terminal materialization may complete that materialization without another client call, registration ordinal or decision ordinal.

Terminal projections are immutable and content addressed at `rounds/terminal_reports/terminal-{canonical_report_hash}.json`. They record invocation history and never select current authority. Current status must derive from validated commit data. Public CLI/status wiring and release capability declarations remain pending the audited D8 contract and final consuming suite. Source apply-back is always prohibited by this bounded endpoint.
