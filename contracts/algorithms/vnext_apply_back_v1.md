# Internal verified apply-back v1

Implements the six-rule policy ratified on 2026-09-29 in
`docs/VNEXT_18_8_M4.md`. Consumers must pin this algorithm and all four
`vnext_apply_back_{review,intent,prepared,receipt}_v1` schemas. No shipped suite
or public command acquires this capability from installed files.

Review reproduces complete current verified history, map/inventory and candidate
finality, convergence closeout, decisions and derived mirrors. Only a complete
current CONVERGED V root with a descriptor-bound source and no pending work is
eligible. A converged immutable seed needs no invented promotion. Existing
closeout artifacts retain their original apply_back_permitted field.

The source must have an absolute canonical path outside the run root on the
same qualified local APFS filesystem. The operator attests exclusive external
access. The D8 run lock does not exclude arbitrary external editing or another
run. Reject source drift, symlinks, multiple links and changed parent/device
identity. Retain owner/group and permission bits plus exact Apple provenance
attribute. Refuse flags, special permissions, extended ACLs and other extended
attributes before replacement; do not silently drop them. File content-change
timestamps are not preserved. Unsupported metadata is a refusal, not an override.

Read-only review/status does not lock, write or repair. Approval binds the exact
review packet, including source bytes/hash/identity, pointer, candidate/map and
convergence evidence. A single immutable intent per run records the exact
approval, exclusive-access assertion and source preimage. Caller booleans cannot
retarget that intent. Request identity is content_identifier with prefix `apply`,
domain `whetstone-apply-back-v1`, and the ordered preimage `[review_packet]`.

Under D8 ownership, revalidate full eligibility and exact approval, synchronize
convergence dependencies, publish the preimage and intent, then prepare a fully
flushed same-directory staging file. Publish its identity before replacement.
Revalidate source and full current evidence again before the atomic rename.
No current verified pointer, candidate, version, closeout or source approval is
changed. Source replacement is the external commit; a separately durable receipt
records it. The source and run receipt cannot commit atomically together.

Any attempted replacement with lost acknowledgement/barrier, or failure to
record the completed result, requires reconciliation and relinquishes ownership.
No rollback, new source write or client call follows uncertainty. Fresh recovery
checks immutable approval and proven historical pointer. Desired bytes on the
bound prepared inode allow source durability barriers and receipt publication
without replacement. Unchanged original bytes allow only an `apply_required`
result, never a recovery write; an explicit retry revalidates full current
eligibility against the same approval. Third bytes, missing source or unexpected
identity require operator attention. Original bytes after uncertainty do not
prove that no replacement ever occurred. No-op approval never replaces a file.

Completed receipt replay returns the bound historical result; current-source
match is separately reported, and later external changes are never overwritten.
A later run pointer cannot retarget historical approval. Partial staging files
remain non-authoritative and are preserved; an explicit precommit retry may
prepare a fresh temporary if no prepared record committed. There are no model
calls, implicit retry, metadata stamping, legacy dispatch, public activation,
source mismatch/non-convergence override or authority repair in this consumer.
