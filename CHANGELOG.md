# Release notes

## 0.4.0 — 2026-11-26

- `stage-mvp` prepares an offline verified Phase 1 package for one Markdown spec from explicit scope, protected meanings, mutation ceilings and review settings. The runner skill links to the [caller example](docs/OPERATOR_EXAMPLES.md#stage-a-single-spec-mvp).
- Intake writes UTC timestamps at whole-second precision. The builder accepts timestamp spellings from earlier intake, normalizes the staged seed, and reports the source and seed hashes. Draft scope still requires approval before admission.

## 0.3.0 — 2026-11-25

- Adds explicit `vnext-verified-consumer-3` selection for Phase 1 verified promotion on Standard and MVP jobs. Stateful System, Balanced MVP and Utility MVP support horizontal and vertical full reviews and horizontal focused reviews. MVP requires approved scope.
- Closeout v6 records approved deferrals at every Reviewer severity. A finding that requires an operator decision blocks completion at any severity, including a nit.
- Consumer-1 retains its existing Phase 2 support. Phase 1 is the terminal phase for consumer-3. See the [production CLI qualification](docs/PHASE1_COMPLETION_QUALIFICATION.md#consumer-3-production-cli-checks).

## 0.2.0 — 2026-10-28

### Verified promotion, explicitly opted in

- Config-selected `verified_promotion` for the exact qualified
  `vnext-verified-consumer-1` suite. New jobs bind immutable seed, authority,
  invariants, review/client configuration and suite inputs.
- Section-addressed Editor proposals, deterministic preservation checks,
  independent semantic verification and serialized D8 promotion keep unverified
  candidates separate from the current verified draft.
- Standard horizontal/vertical Phase 1, focused review, distinct Phase 2 entry,
  rubric/declaration convergence, exact operator decisions and finite recovery
  commands share the verified owners. Proven decision history accompanies later
  reviews without granting new edit authority.
- Markdown operator guidance and the offline HTML field guide describe admission,
  evidence, recovery, source approval and the release capability boundaries.

### Scope and compatibility

The qualified V release requires local macOS/APFS, standard workflow,
stateful-system profiles and the fixed `standard-v1` rubric. Horizontal Phase 2
covers mid/final × permissive/strict; vertical Phase 2 is final/strict. Focused
stability does not admit Phase 2. Other workflows, distributed writers, root
relocation and generic Phase 2 Editor/Verifier crash recovery are outside this
release. See the [supported matrix](docs/OPERATOR_QUICKSTART.md).

Existing defaults and legacy/bridge behavior are unchanged. V does not migrate
existing jobs or grant provider transmission/source-write permission. Apply-back
still requires its separate exact approval and source-access safeguards.

### Qualification and known limits

All 22 mapped P0 rows have retained passing evidence. The broad Q3 campaign
records 1,634 passes and one unexplained native semantic CLI status/reentry failure
outside that map. Its diagnostic retest passed; the operator accepted the residual
risk. The original failure is not relabeled fixed. Controlled live Phase 1/Phase 2
qualification reached CONVERGED using five Sol reviews in 12m 36s at 60% duty.
That clean run did not edit or promote a candidate or exercise nonempty Phase 2
history; separate historical live and focused local evidence retain their limits.
All 15 focused activation/configuration/compatibility checks passed.

Replay can be slow. The small live journey used 66.937 seconds of provider time;
whole-test Q3 journeys reached roughly 72–75 minutes with multiple operations
and faults at 60% duty. These are not individual-command SLAs. Full evidence,
source boundaries and accepted limitations are in the
[release record](docs/VNEXT_VERIFIED_PROMOTION_RELEASE.md).

Installing a candidate, promoting an installed stable channel, tagging/pushing a
release and publishing the HTML guide are separate administrative actions.
