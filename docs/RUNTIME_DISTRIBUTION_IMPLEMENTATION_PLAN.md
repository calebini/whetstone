# Runtime Distribution and Selection Implementation Plan

## Current State

The [runtime distribution contract](specs/RUNTIME_DISTRIBUTION_AND_SELECTION_SPEC.md)
is a reviewed draft. The final focused consistency recheck passed on 2026-10-17
with zero findings and `boundary_preserved=true`. Runtime selection, locking and
distribution are not implemented by this documentation checkpoint.

This plan owns this initiative's delivery progress and next steps. The separate
candidate-pipeline work retains its existing plan and qualification gates. Spine's
people-and-responsibility audit is deferred until this runtime setup is implemented
and verified.

## Review Evidence

The local run `rounds/runtime-distribution-selection-audit-001` found four majors
and one minor. After the first patch, audit-002 found two remaining contradictions:
missing tombstone representation and unconditional channel lookup for exact-runtime
requests. Both were patched. Audit-003 returned `pass`, zero findings and recommended
next action `none`. These are reviewer-only consistency results, not convergence or
implementation qualification.

The reviewed leaf SHA-256 is
`f52add1fa8b39b5505f2e810b21cb0282bf095bfc4c3c3a8e30f68dd6d422533`.
Local reports and their manifests are retained under the run roots; they are not
published with this checkpoint. The four coordinating reference files were unchanged.

## Delivery Sequence

### 1 Portable identities and byte manifests

Codify closed release/development identity variants, the closure manifest and
detached runtime-lock digest rules. Define exact field names, canonical encoding,
format versions and validation fixtures. Implement pure manifest/digest helpers.
Make runtime-root membership, dependency verification and installer exclusions
executable rather than relying on caller discretion.

Exit evidence: independent canonical vectors; identical identities across synthetic
installation paths; byte-change detection; valid development tombstones and rejection
of release tombstones, duplicate paths, escaping paths and malformed identities.
No launcher activation or client calls belong in this slice.

### 2 Local runtime admission and resolution

Implement the local resolver and explicit admission boundary with user-local
installation metadata. Channel requests follow explicit pointers; exact identities
resolve directly. Development selection requires an explicit request and snapshot
verification. Keep `latest-qualified` an administrative query. Resolve nested-client
identity independently and keep local handles out of portable outputs.

Exit evidence: missing/ambiguous/corrupt/unqualified refusal; exact lookup after
channel rollback; dependency and observed-client mismatch handling; no implicit
network/install/promotion; temporary-directory tests across supported platforms.

### 3 Immutable job locks and exact-runtime continuation

Wire resolution and durable lock publication into the supported job launch boundary
before its first mutation or nested call. Bind the detached lock digest in the
applicable job authority. Resume, recovery, focused review, Phase 2 and apply-back
resolve and verify the exact retained identity. Inventory the affected entry points
before wiring, and state legacy-job handling explicitly without guessing missing
locks or changing existing workflow authority.

Exit evidence: lock publication faults prevent launch; tampered/missing locks fail;
channel advances and rollbacks cannot alter a running job; development edits prevent
continuation; unavailable/revoked exact runtimes halt with portable diagnostics.
Retain existing workflow regression coverage and transmit no documents in offline tests.

### 4 Build admission and channel promotion

Produce clean, immutable release artifacts and qualification metadata; implement
explicit candidate admission, stable promotion and rollback. Promotion changes a
pointer without rebuilding artifacts. Reject version reuse for differing bytes.
Channel membership remains separate from immutable identity.

Exit evidence: clean-install qualification, artifact/tag/commit consistency, digest
verification, atomic pointer behavior, identity-preserving promotion and rollback,
and proof that existing jobs retain their locks. Public release publication remains
a separate operator action.

### 5 Qualify and adopt the shared launcher

Exercise the complete contract checklist against an admitted immutable runtime.
Document portable project commands and user-local resolver configuration. Verify
legacy compatibility and that consuming projects no longer import a moving source
checkout through implicit PYTHONPATH when using the new launcher.

Adopt deliberately in selected projects after qualification; do not mass-rewrite
existing commands. An accepted stable target and an offline launch/resume check
must exist before declaring the setup ready for Spine's deferred audit. A live
review still uses its own document-transmission authorization.

## Next Step

Begin Slice 1 when implementation is requested. The next concrete deliverable is
the portable schema/fixture set and pure identity/digest helpers. Record progress
and completion evidence here as each slice advances; use transient handoffs only
for continuation context that does not belong in this durable plan.
