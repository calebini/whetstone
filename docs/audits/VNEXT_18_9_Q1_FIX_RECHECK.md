# Q1 proposal fixes and focused recheck

Date: 2026-10-01. Baseline: `fb57a2406074520630fa99242161d9662e18653b`.
Disposition: **Q1-A1, Q1-A2 and Q1-A3 addressed in the review-only proposal.**
Ratification, authoritative publication, implementation and release qualification
remain pending. This is a local focused recheck, not an independent reviewer run
or a product-test verdict.

The operator authorized fixing the findings in the
[initial bounded audit](VNEXT_18_9_Q1_BOUNDED_AUDIT.md). That report and its reviewed
snapshots remain unchanged as historical evidence. The updated
[proposal](../VNEXT_18_9_Q1_PROPOSAL.md) and
[amendment patch](../VNEXT_18_9_Q1_SPEC_AMENDMENTS.patch) contain these fixes:

| Finding | Correction | Focused evidence |
| --- | --- | --- |
| Q1-A1: unspecified continuation surface | Added a finite 12-row recovery/continuation table with exact selectors, owner calls, permitted client work and stop points. Separated first/later Phase 2 Reviewer continuation from unsupported correction continuation. Repair takes precedence and ends the invocation even with `--continue`; ordinary live commands cannot retry implicitly. | Table is identical in proposal, proposed scheduler and Quickstart. Existing `VerifiedRun`/work, promotion, Reviewer-failure and correction-failure owners were inspected for the named operations. Q1 acceptance now explicitly requires repair-only, eligible/exhausted continuation, stopping and implicit-retry refusal cases. |
| Q1-A2: recovery constrained by fresh-write eligibility | Split source operations into read-only assessment/status, fresh apply, explicit retry and retained-intent recovery. Historical recovery validates the recorded approval/lineage without requiring current new-write eligibility; it never replaces source bytes. | Four subcases agree across all three documents. Pointer advancement, drift, absent intent and original/desired/third-byte outcomes are distinguished. Current writes still require complete current convergence and exact current approval. CLI acceptance includes historical recovery after pointer advancement and completion after drift. |
| Q1-A3: review output confused with approval input | Read-only stdout retains the review envelope and diff/blockers/recovery information. Only its non-null assessment is saved in D6 canonical bytes; the approval hash covers those exact file bytes. The frozen assessment schema is unchanged. | Executed the documented extraction on disposable synthetic data: exact bytes/hash round trip passed; existing-file overwrite, blocked/null assessment and existing-intent extraction refused. The existing schema rejects the full review envelope as approval. |

The command summary still has 14 rows; the subcases make its behavior precise
without adding commands or milestones. The independent 14-row authority map and
22 P0 classifications are unchanged. Plain V `resume` and optional Phase 1
`--continue` behavior are proposed interface details; they do not alter the
earlier reviewer-only/proposal-only CLI semantics or advertise public V support.

## Verification and limits

The focused script passed 43 assertions covering consistent contract text,
documented extraction and unchanged authority/runtime inputs. These assertions
do not execute the proposed CLI adapter: wrong-hash, noncanonical-file, recovery
dispatch and other command journeys remain explicit Q1 implementation acceptance
work. The synthetic extraction check is not a genuine apply-back approval or
source-write test, and writes only temporary review/approval fixture files.

The refreshed [preparation record](VNEXT_18_9_Q1_PROPOSAL.json) records the exact
proposal/patch and proposed-owner hashes, successful `git apply --check`, unchanged
authoritative sources, verbatim M3/M4 rules, matrix counts and document checks.
No patch was applied to an authoritative file. No runtime, test or frozen contract
file was changed; the unrelated notes edit remains untouched. No product test
campaign, external client, real apply-back, activation, commit or push occurred.

Raw before snapshots, fix script, recheck script and results are retained under
`rounds/vnext-18-9-q1-fixes-001/`. Shared proposal fragments and regeneration inputs
remain under `rounds/vnext-18-9-q1-proposal-001/`. Both directories are ignored by
Git; this report and the refreshed preparation record preserve the handoff.

The three identified gaps are closed at the proposal level. The next boundary
remains approval of the concrete amendment/interface package, followed by Q1's
seven acceptance cases with production activation disabled.
