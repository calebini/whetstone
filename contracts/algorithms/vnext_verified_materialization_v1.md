# Verified materialization v1 (unactivated)

This component owns only Stage 1 classification and materialization of already committed V-mode authority. Its exact algorithm must be pinned alongside genuine verified-history replay and the local storage kernel. It provides no promotion selection, next-ordinal scan, new intent, disposition event or pointer commit, model invocation, scheduler completion or public activation.

Read-only inspection freshly proves committed seed-to-head lineage, including genuine registration and independent semantic evidence. It does not perform the subsequent full candidate registry scan. It resolves the committed draft bytes and computes these derived targets:

- `spec.md`: exact current verified draft bytes.
- For nonzero promotion ordinal, the pointer-bound source round's `draft_after.md`: the same bytes. Seed initialization has no source round and cannot fabricate one.
- `rounds/run_state.json`: its `vnext_current_verified` member is an exact object copy of the committed current pointer. This member is a derived projection, never authority or a scheduler permission. Preserve all other JSON object members. A missing state file begins as an empty object; malformed JSON or a non-object cannot be repaired by guessing unrelated state. This component does not invent profile counts, terminal states, readiness or convergence.

Missing or mismatched derived targets require materialization recovery. Matching pointer fields do not require rewriting an otherwise unchanged state file merely for formatting. A missing or mismatched committed pointer snapshot, or any invalid committed evidence, remains artifact-invalid and is never repaired as a mirror.

Materialization recovery reacquires the shared D8 fence and freshly proves the actual head. A promotion operation must release its initial promotion critical section before invoking this separate materialization-only operation. If another valid operation advanced the head in between, materialize the newly validated current head, never overwrite it with cached historical bytes. Hold the fence through every derived write so a cooperating writer cannot advance authority midway.

Before writing mirrors, repeat durability barriers on the exact existing current snapshot and current pointer without replacing either or creating missing files. The storage extension verifies exact expected bytes, opens the confined existing regular artifact without following symlinks, flushes its file, synchronizes its parent directory and flushes the file again. Failure invalidates ownership and reports reconciliation required. This operation cannot repair evidence or establish missing authority.

Derived replacement is restricted to the three path families above. The kernel requires a live ownership token and a consumer validator, checks binding/ownership during synchronized temporary publication, atomically replaces the derived target and reports ordinary storage uncertainty. The consumer rechecks the exact current pointer and planned target bytes. It writes only mismatched targets, in spec, source-round draft, run-state order. Reentry preserves already matching bytes and derives remaining work from fresh authority. Return after this operation; never scan or prepare the next promotion ordinal in the same recovery invocation.

Qualification includes seed and promoted repair, no fabricated seed round, unrelated run-state preservation, read-only status, existing-snapshot refusal, interruptions before/after each mirror write, changed head between classification and repair, no next-ordinal scan during recovery, live process exclusion and stale-token refusal. Full promotion, scheduler integration, D8 audit and complete release qualification remain later gates.
