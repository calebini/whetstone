# 18.7 canonical round decision-reference recovery

Date: 2026-09-18. Starting checkpoint: `c6e5929`.

**Both test methods pass (12.936 seconds, no skips): two replay-flush faults and
five refusal cases.** The first run passed. No runtime or contract change was
required; this closes the previously untested nonempty decision-reference branch
for canonical seed-base round admission.

The [tests](../tests/test_vnext_verified_runtime_decision_refs.py) use
`open_verified_run` on a root with no staged round selectors. A real canonical
Reviewer request produces a finding requesting weakening. The fixture explicitly
publishes an operator request and response granting weakening of one named
normative inventory unit. The grant is bound to the original Reviewer finding,
exact feedback, base, inventory, authority map and scope. It is separate from
semantic interpretation answers and child-transaction selection.

## Boundaries proved

| Case | Required outcome |
| --- | --- |
| Decision request replay flush fails | Reviewer receipt replay precedes the request. The real adapter's final existing-inode flush fails; ownership is invalidated before the caller unwinds. Neither response replay nor round publication follows. |
| Decision response replay flush fails | Reviewer receipt and request replay precede the response. The adapter reports typed uncertainty with the exact response path/hash and invalidates ownership. The round remains unpublished. |
| Missing request or response (two cases) | Admission refuses before any publication; read-only reopening and the failed operation preserve the fixture's remaining bytes. |
| Altered request or response (two cases) | Exact-hash validation refuses before publication. No grant is inferred from otherwise readable JSON. |
| Response changes after request replay | Initial preflight succeeds, then the fixture changes the response. Admission detects the drift before response replay or round publication; it makes no further artifact change. |

The flush faults are injected inside the real adapter while replaying already
existing immutable decision files. They produce `StorageWriteError` with
`outcome_requires_reconciliation`; the tests do not fabricate that classification
after a successful publication. A write attempted with the poisoned token fails
with `OwnershipLost` immediately. The final temporary name has already been
removed at this boundary, so the failed replay changes no fixture bytes.

For each flush fault, a fresh runtime remains at `finding_admission` without
repairing bytes. Explicit admission replays the original Reviewer receipt,
decision request and decision response before publishing the canonical
`proposal_input.json`. That round is the only new file. Its exact decision,
feedback, advice and base references are preserved.

Fresh historical reconstruction and shared preflight reproduce exactly one
decision binding and one derived task. The binding grants `weaken` to the one
selected unit and grants no `remove` effects. Repeated admission returns the
same round reference without changing files. All original evidence, including
the response timestamp, remains exact. The Reviewer total stays at one call;
there is no Editor/Verifier work, candidate registration, second review claim or
promotion.

## Evidence and remaining work

The [validation record](audits/VNEXT_RUNTIME_DECISION_REFERENCES.json) binds the
command, test identities, launch source manifest and log digest. Raw evidence
is retained under ignored `rounds/vnext-runtime-decision-refs-001/`.

```sh
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_runtime_decision_refs -v
```

The preceding reconciliation's three log digests, reported counts and all source
manifest hashes were checked and match. Its 76 tests remain historical evidence
on the same runtime bytes; they were not rerun or added to this checkpoint's
two-test count. Compilation and whitespace checks also pass. No full regression
or consuming-release qualification is claimed.

The [review-sequence contract](../contracts/algorithms/vnext_verified_review_sequence_v1.md)
requires explicit decision selection, shared preflight, dependency durability,
revalidation and immutable round publication in that order. These tests exercise
that existing implementation without changing its contract or shipping pins.

Next: resolve the three narrower runtime publication proofs identified in the
[boundary reconciliation](VNEXT_18_7_BOUNDARY_RECONCILIATION.md): early incomplete
registration, candidate-pointer acknowledgement loss, and early promotion
preparation. Existing component matrices already cover their individual prefixes;
select representative runtime cases against the consuming acceptance requirements
instead of repeating every component permutation.

This checkpoint does not establish nonempty decisions on every promoted base,
multiple simultaneous decisions, or all decision-authoring/transport failures.
Complete consuming-suite qualification and the wider 18.5–18.7 acceptance map
remain open. Batch C and 18.7 remain incomplete. D8 audit closure stands; no
18.8–18.9 work, activation, provider transmission, external specification
apply-back or push is included.
