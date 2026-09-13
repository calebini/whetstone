# D7 consistency audit staging

Historical staging record. The bounded consistency audit subsequently **passed with zero findings**; see the [completed audit record](VNEXT_D7.md). The preparation details below describe the packet before execution and do not activate slice 18.3.

The [coordinating amendment](../specs/WHETSTONE_COORDINATING_SPEC.md#vnext-admission-and-capability-negotiation-d7) owns descriptor selection, CLI/config conflict rules, mode availability and diagnostic reasons. The [scheduler amendment](../specs/SCHEDULER_STATE_AND_RESUME_SPEC.md#vnext-candidate-processing-d7) owns the processing transition table, failed gates, operator waiting, retry limits and continuation. Candidate, artifact and scope leaves align finality, evidence and decision routing with those rules.

The resolution makes these choices explicit:

- The immutable descriptor selects mode. Mixed protocols, conflicting selectors and unavailable requested gates fail without silent fallback.
- Reviewer-only admission includes validated seed-only initialization: seed map, ordinal-0 snapshot and current pointer. This is a required 18.3 subset; it does not implement candidate assembly or promotion.
- A valid semantic operator-decision verdict finally rejects the candidate while the run may pause. Missing or invalid semantic output leaves it unverified.
- At most one automatic shape-validation retry is allowed per logical request across restarts. Patch/preservation/semantic repairs require explicit new admission; timeouts and transport/persistence failures do not trigger automatic client retries.
- Recovery derives authority from committed evidence. Status never repairs. Final candidate decisions cannot be reopened by operator approval or technical resume.
- The frozen `vnext-contracts-1` suite is unchanged. New admission/config/status contracts belong to 18.3; D8 storage and later mode qualification remain separate gates.

The local packet is [rounds/vnext-d7-audit-001](../../rounds/vnext-d7-audit-001/README.md). It contains six exact excerpt files (coordinating, scheduler, candidate, artifacts, scope and plan), payload notes, a rendered brief, a staging manifest with full-source/excerpt hashes, a local integrity check and the prepared run script. The 124,251-byte preview uses Whetstone's actual brief renderer. The configured future invocation is `audit-change`, profile `consistency`, client `codex`, model `gpt-5.5`, recorded client version `0.142.0`, timeout 360 seconds. No Editor or apply-back is included.

Validate the staged packet from the repository root without invoking a client:

```sh
python3 rounds/vnext-d7-audit-001/check_packet.py
```

When instructed to run the audit:

```sh
sh rounds/vnext-d7-audit-001/run.sh
```

The script refuses changed source/packet hashes and existing audit output. Staging alone does not execute it. A completed review must be recorded separately; do not mark the 18.3 audit prerequisite complete from this document. The ignored local packet is a prepared work artifact; the owning specs and this handoff remain the durable record of scope and intent.
