# Runtime Distribution and Selection Contract

Status: **revised draft, simplified by operator direction on 2026-10-17**.
This replaces the earlier fingerprint-based proposal. The earlier passing audit
applied to that previous draft; it does not constitute review of this revision.

## Purpose

Ensure projects launch the intended Whetstone version through a consistent local
entry point. Use versioned installations and explicit stable, candidate and
development targets. Machine-specific paths and executable locations stay in local
configuration outside consuming repositories.

## Installations and Channels

Keep each released version in a separately named installation. Installing a new
version does not overwrite the previous version.

- `stable` selects the released version intended for ordinary jobs and is the
  default when the operator does not choose a channel.
- `candidate` selects a version being tried before promotion.
- `development` explicitly selects the working checkout. It may change as
  development proceeds and does not promise a frozen snapshot.

Stable and candidate may be symbolic links or equivalent local pointer records.
The selection is explicit; do not infer it by sorting installed versions. Promotion
or rollback changes a pointer to an existing installation.

An illustrative layout, not a required machine path:

```text
releases/
  0.1.0/
  0.2.0/
stable      -> releases/0.1.0/
candidate   -> releases/0.2.0/
development -> working checkout
```

## Shared Launcher

Provide one Whetstone entry point used by consuming projects. It resolves the
requested channel, confirms the target exists, checks its reported Whetstone
version against the version expected by local configuration, and invokes that
installation with the supplied job arguments.

For a release target, a missing installation or mismatched reported version
produces a clear error. Do not silently choose another version or fall back to the
development checkout. Development is visibly labeled as such and reports whatever
version its checkout currently provides.

The launcher can show the selected channel, version and local target for operator
diagnostics. Local paths belong in these local diagnostics, not portable project
configuration. The nested Codex executable remains a separately selected tool; this
launcher does not install, upgrade or choose a model for it.

## Job Continuity

Retain the selected channel and reported Whetstone version in available job metadata.
Keep release installations addressable by version so an operator can select the
same version when continuing a job after a channel moves. This is an ordinary
version-selection record, not a cryptographic lock or a new job-admission protocol.

The first implementation need not modify existing job descriptors or recovery
owners. Existing workflow rules continue to govern continuation. Automatic exact
runtime enforcement across every resume path is outside this scope.

## Local Configuration and Administration

Keep installation roots, interpreter paths, checkout locations and channel targets
in user-local configuration. Checked-in project guidance uses the shared command
and logical channel names.

Installing versions, choosing a candidate, promoting stable and rolling back are
explicit administrative actions. A lightweight local procedure is sufficient.
This contract does not introduce a release registry, qualification service, signed
metadata or a distribution server.

## Verification

Demonstrate selection of stable by default and explicit candidate/development;
correct version reporting; clear missing-target/version-mismatch failures; argument,
exit-code and signal forwarding; and pointer promotion/rollback without overwriting
prior installations. Use temporary directories and synthetic runtimes in tests.

No file manifests, source/dependency fingerprints, tamper detection, snapshot
identities, new JSON schemas or immutable job locks are required. Ordinary package
installation manages dependencies. The setup is intended for a trusted local
environment and does not detect modifications that retain the same version label.

## Delivery

Implement and exercise this small launcher in Whetstone first. After a selected
release can be launched and its version confirmed through the shared entry point,
adopt it deliberately for Spine's deferred audit. Existing project workflows are
not rewritten automatically.

The [implementation plan](../RUNTIME_DISTRIBUTION_IMPLEMENTATION_PLAN.md) owns
delivery progress and next steps.
