# System-only Phase 2 version entry, version 1

Internal M3 consumer under development, implementing the 2026-09-29 ratification
recorded in `docs/VNEXT_18_8_M3.md`. A consuming suite must additionally pin this
algorithm, version admission v1 and Phase 2 entry v2. No public activation.

Require the current complete Phase 1 prerequisites, committed immutable entry
request/configuration/rubric and original verified base. The system-only
transaction has zero admitted findings, zero Editor operations and zero Editor
budget. Bind its admission to the exact request and base. Reuse the last real
prerequisite Reviewer's number solely as a storage locator; never manufacture
a Reviewer/Editor invocation or consume a round. A distinct system request
journal publishes an empty patch, plan and receipt without claiming client work.

Registration, independent semantic verification, finality, promotion intent,
current-pointer commit and D8 recovery remain ordinary candidate operations.
Replay their system inputs from the original proven Phase 1 prefix, never from
a substituted current head. The entry candidate is the unique direct successor
of that prerequisite pointer; any unrelated successor refuses entry. Only after
promotion may entry v2 commit, binding both the original request and new verified
pointer. Configuration publication or promotion alone does not enter Phase 2.

Reentry repeats source/publication barriers and repairs derived state only.
Version operation/history evidence records exact before/after bytes. First
Phase 2 review consumes the promoted entry base; later corrections use assembler
v3 and their own round authority. No generic Phase 2 resume, post-validation
stamp, bridge exception or external write is introduced.
