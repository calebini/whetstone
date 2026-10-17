# Runtime Distribution and Selection Contract

Status: **draft; specification only**. This document does not publish a release,
install a runtime, change a project's launcher, or authorize a Whetstone job.

## Purpose

Whetstone jobs must run against an identifiable, reproducible runtime rather than
implicitly importing whichever bytes happen to exist in a developer checkout. This
contract defines portable release channels, runtime selection, job locking, resume
behavior and environment resolution for every consuming project.

The checked-in contract is environment-neutral. User names, absolute paths, host
identifiers, credentials, local application layouts and the machine's current channel
selection are not repository configuration and must not be committed.

## Runtime channels

Whetstone exposes exactly three logical channels:

- `stable`: the immutable release named by the resolver's explicit stable-channel
  pointer. Its target must have completed the published stable qualification. This
  is the default for new jobs.
- `candidate`: a clean immutable build admitted for release qualification but not
  yet promoted to stable.
- `development`: an explicitly selected source checkout for Whetstone development.
  It is never selected implicitly and never substitutes for an unavailable stable or
  candidate runtime.

Ordinary channel resolution follows the channel's explicit pointer, including after
rollback. `latest-qualified` is a separate administrative query that deterministically
returns the highest semantic version admitted to a named release channel; it is never
an implicit job-selection rule. Neither operation means the current branch head, a
dirty checkout, the newest filesystem entry, or a newly downloaded artifact that has
not passed channel admission.

Channel movement changes only the default selection for future jobs. It cannot alter
the runtime locked to an existing job.

## Portable runtime identity

Every runtime identity is a tagged union whose `kind` is either `release` or
`development`.

A release identity contains:

- distribution name and semantic version;
- source repository identity and exact commit hash;
- build and contract format versions;
- digest of the installed distribution closure;
- qualification profile identifier and evidence digest;
- supported Python range and dependency-lock digest.

A development identity contains:

- source repository identity and exact commit hash;
- clean or dirty state;
- runtime-closure format version and development-snapshot digest;
- supported Python range and dependency-lock digest.

Selected channel is provenance in the job runtime lock, not part of either runtime
identity. Promoting identical bytes from candidate to stable preserves their release
identity. Exact-runtime resume resolves identity independently of later channel
membership.

Runtime identity excludes installation paths, account names, host names, inode or
device values, environment variables, credentials and timestamps that do not affect
the distributed bytes. Two installations of the same qualified bytes on different
machines therefore have the same portable identity.

The semantic package version must uniquely identify released content. A release may
not reuse a version for different bytes. Git tags and built artifacts must resolve to
the same source commit and distribution digest.

### Runtime closure digest

Release distribution and development snapshot digests use the same versioned,
path-independent manifest preimage. The manifest is canonical JSON with a format
version and an `entries` array sorted by Unicode code-point order of normalized POSIX
relative paths. Each live entry records its relative path, kind (`file` or `symlink`),
executable bit, byte length and SHA-256 digest of its exact file bytes; a symlink entry
instead hashes and records its normalized relative target text. Absolute paths,
filesystem metadata, timestamps, ownership, extended attributes and inode values are
excluded. Duplicate, escaping, platform-ambiguous or non-normalized paths are invalid.

The release closure is the complete installed Whetstone distribution described by
the build manifest, including executable package resources and generated runtime
assets, but excluding bytecode, caches, logs, run artifacts and installer metadata
declared non-runtime by the closure format. Third-party dependencies are not copied
into this closure: their exact lock-file bytes are a required closure entry and their
resolved environment is verified separately against the dependency-lock digest.

The development snapshot uses that same release membership plus tracked runtime
files changed from the recorded commit and untracked files beneath those runtime
roots. It excludes ignored files and the same generated/cache classes. Deletions are
explicit development-only tombstone entries. A tombstone has exactly two fields:
`path`, the normalized relative path of a deleted runtime entry present at the
recorded source commit, and `kind`, the literal `tombstone`. It has no executable
bit, length, target or content digest. For example,
`{"kind":"tombstone","path":"src/whetstone/removed.py"}` is its canonical JSON
representation. Tombstones participate in the same path ordering and uniqueness
rules as live entries; a path cannot be both live and deleted. Release manifests
reject tombstones. The snapshot digest is SHA-256 of the canonical manifest
bytes. Build, admission, resolution, launch and resume must use the same declared
format version and algorithm; implementations may not infer membership from a live
directory walk without the manifest rules.

## Resolver boundary

A local resolver maps a portable runtime identity or channel to an executable Python
environment. Resolver state belongs in the platform's user configuration and data
locations, outside consuming repositories. It may contain absolute paths and
host-specific installation metadata, but it must never enter a portable runtime
identity or checked-in project configuration.

For a release identity, the resolver must:

1. for a channel request, resolve its explicit pointer to one admitted immutable
   runtime; for an exact release-identity request, locate that identity directly,
   without consulting channel pointers or requiring current channel membership;
2. verify the distribution digest and executable environment before launch;
3. return the portable identity plus an opaque local launch handle;
4. refuse missing, ambiguous, corrupt or unqualified selections;
5. never fetch, install, promote or modify a runtime as an implicit side effect of
   resolving a job;
6. record local diagnostics separately from portable job artifacts.

For an explicitly requested development identity, the resolver instead admits the
source snapshot without release qualification, verifies the complete development
snapshot digest and dependency environment on every launch or continuation, and
returns the same opaque local launch handle. Development resolution may not satisfy a
stable or candidate request, and it remains subject to all no-side-effect and portable
diagnostic rules above.

Installation and channel promotion are explicit administrative operations. Network
access, if any, belongs to those operations rather than ordinary job resolution.

## Job runtime lock

Before the first workflow mutation or nested-client invocation, Whetstone writes an
immutable, canonical runtime lock into the run root. The lock records:

- the complete portable Whetstone runtime identity;
- the selected logical channel;
- Python implementation and version;
- dependency-lock digest;
- Whetstone contract-suite and workflow versions used by the job;
- nested-client product, version and model identity when applicable;
- a lock format version.

The lock uses logical identifiers and digests. It contains no absolute executable,
repository, home-directory or application path. Environment-specific paths may
appear only in local diagnostic output explicitly classified as nonportable and
excluded from send payloads and checked-in fixtures.

The persisted lock contains no embedded digest. Its detached `runtime_lock_digest` is
SHA-256 of the exact canonical JSON bytes of the complete persisted lock and is bound
by the job descriptor or earliest available authority record. Validators recompute
that digest from the persisted bytes before trusting the lock. A lock is immutable
after the job begins. A missing lock on a workflow that
requires this contract is not repaired by guessing from current defaults.

## Launch and resume rules

For a new job, the launcher resolves the explicitly requested channel or `stable`,
verifies the selected runtime and persists the lock before executing the workflow.
Selection is frozen for the lifetime of that job.

For resume, recovery, focused review, Phase 2 and apply-back inspection, the launcher
must resolve the exact runtime identity recorded in the lock. It must not use the
channel's current target. If the exact runtime is unavailable, corrupt or no longer
qualified for use under an explicit revocation policy, the job halts with a precise
runtime-unavailable result. It does not silently upgrade, downgrade, rebuild from a
moving branch or fall back to development.

A deliberate migration to another runtime is a separately specified operation that
must produce a new immutable compatibility decision and preserve the original lock.
This contract does not authorize such migration.

## Development runtime

Development selection requires an explicit operator choice and records the
development identity described above. In particular it records:

- source commit;
- clean or dirty state;
- a portable digest of tracked changes and relevant untracked runtime sources;
- dependency-lock digest and Python identity.

A clean development checkout is identified by commit plus development-snapshot
digest; it is still a development identity rather than qualified release evidence.
A dirty checkout must never claim a release version or enter stable/candidate. Its
change digest is evidence, not a release artifact. Resume requires the same bytes;
mere reuse of the same directory is insufficient.

Production qualification, release evidence and stable promotion must use a clean
immutable build. Tests may use synthetic development identities and temporary
directories without embedding a contributor's actual environment.

## Release and promotion

A releasable Whetstone runtime must be built from a clean commit, carry a unique
semantic version, pass the declared qualification profile, and produce immutable
artifacts whose digests are recorded with the qualification evidence.

Candidate admission verifies those facts and installs the artifact without changing
stable. Stable promotion atomically changes the resolver's local stable-channel
pointer to an already admitted candidate. Promotion never rebuilds the artifact.
Rollback selects a previously admitted stable-qualified runtime for future jobs; it
does not rewrite existing runtime locks.

The repository publishes release metadata and schemas, but not any user's installed
channel pointers or resolver database.

## Nested-client identity

The nested-client executable is resolved independently from the Whetstone runtime.
The launcher records the client product and observed version, not its local path.
Configured and observed versions must agree with any workflow constraint before a
payload is sent. A changed client during a job is handled by the workflow's explicit
compatibility policy and never silently relabeled as the original client.

Runtime selection does not grant document-transmission permission, broaden sandbox
access or replace workflow-specific operator authorization.

## Failure behavior

Selection and launch fail closed for:

- unknown channels or runtime identities;
- reused versions with different bytes;
- dirty sources selected outside explicit development mode;
- digest, tag, commit, qualification or dependency mismatches;
- unavailable exact runtimes during resume;
- malformed or mutable runtime locks;
- environment paths present in portable identity fields;
- configured and observed executable-version conflicts.

Failures occur before workflow mutation or nested-client transmission and identify
the violated check without exposing private local paths in portable reports.

## Required conformance evidence

An implementation must demonstrate:

- stable default and explicit candidate/development selection;
- channel-pointer resolution, including rollback, plus separate deterministic
  `latest-qualified` administrative queries;
- no implicit checkout, network, install or channel mutation during resolution;
- byte and qualification verification before release launch;
- exact development-snapshot verification on every development launch and resume;
- one versioned closure-manifest algorithm shared by build, admission and resolution;
- canonical development tombstones, rejection of tombstones in release manifests,
  and rejection of duplicate live/deleted paths;
- exact-runtime resume after channel advancement and rollback;
- refusal when the locked runtime is absent or altered;
- explicit dirty-development identity and refusal outside development mode;
- atomic promotion of an already admitted candidate;
- detached runtime-lock digest verification over exact canonical persisted bytes;
- portable locks containing no synthetic absolute paths or host identifiers;
- resolver tests using temporary directories on all supported platforms;
- nested-client observed-version capture without storing its executable path;
- compatibility with project-local run roots without copying the Whetstone source
  tree into each project.

Until this evidence passes and a runtime is promoted, existing direct-source launch
commands remain legacy behavior and must not be described as stable-channel use.
