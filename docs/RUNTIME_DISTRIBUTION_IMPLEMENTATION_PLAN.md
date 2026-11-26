# Runtime Distribution and Selection Implementation Plan

## Current State

The operator simplified this initiative on 2026-10-17: select the intended
Whetstone version using versioned installations, three channel pointers and one
launcher. The [revised contract](specs/RUNTIME_DISTRIBUTION_AND_SELECTION_SPEC.md)
owns this scope.

Current candidate is `0.4.0rc1-f443a60` ([installed staging qualification](qualification/mvp-staging-0.4.0rc1.json)).
Current stable is `0.4.0-c8f1a3c`. The rollback installation is `0.3.0-4fcfc00`.

### 0.4.0 stable promotion, 2026-11-26

The release was installed from commit `c8f1a3c2808734030ce17fb8cd2048ae5b783329`
in a separate environment. All 1,286 tracked files matched the commit. The final
CLI passed the four installed staging tests and validated all four suite
manifests. Consumer-1 and consumer-3 retain their qualified digests.

From an external caller directory, the installed example reached the expected
draft approval gate, passed approved admission dry-run and rejected a modified
seed. The final CLI also accepted the six retained full MVP packages
(three profile sets, horizontal and vertical) and the package staged from
0.3.0 intake. These checks made zero live provider calls.

After the atomic pointer switch, ordinary PATH lookup and explicit stable
selection reported the exact release. Command help and approved admission
dry-run passed. The runner skill's `SKILL.md` was synced from the selected
installation. Both complete host skill trees matched the installation
(eight runner files and two release files), and both passed skill validation.

The retained 0.3.0 launcher passed admission dry-run after promotion. To roll
back, atomically replace the stable symlink with one pointing to the retained
`0.3.0-4fcfc00` installation, verify the default launcher and dry-run from a
calling project, and reconcile host skills using the release checklist.

Initial local stable pin selected by the operator with known development risk
accepted: commit `6e19fe3e72dedda50a372781a43c08e5d7e7480a`, reported version `0.1.0`.
A separate snapshot and environment are installed outside the development repo.
The machine-local `whetstone` launcher defaults to stable; `--channel development`
selects the working checkout. Candidate was unset at that initial baseline. Machine-specific paths and
pointer records stay outside Git. This is a practical operator-selected baseline,
not a claim that the unfinished verified-promotion feature is release-qualified.

The uncommitted fingerprint implementation and its tests were set aside recoverably
under local ignored root `rounds/runtime-selection-simplification-001/`, alongside
the prior contract and plan. They are not part of the active implementation.
Separate candidate-pipeline work remains untouched.

## Selected Delivery

### 1 Channel Selection and Launcher

Define a small local configuration mapping stable, candidate and development to
targets. Implement the launcher with stable as default, explicit channel selection,
reported-version checking and clear missing-target/mismatch errors. Preserve
argument, exit-code and signal behavior. Use synthetic targets in tests.

The initial machine-local launcher is implemented. Stable/development selection,
reported-version checking and a stable `audit-change --help` smoke test pass.
Do not reintroduce manifests, byte/dependency
fingerprints, qualification identities, new schemas or mandatory runtime locks.

### 2 Local Installation and Adoption

Document how to install a named Whetstone version separately, select a candidate,
move stable and roll back. Test the launcher against an actual selected installation
and confirm its reported version. Keep paths and channel mappings outside Git.

Adopt the shared entry point for selected consuming jobs after this check. Spine's
people-and-responsibility audit stays deferred until the practical setup works;
its document-transmission approval remains separate.

## Decisions

The operator chose correct version selection over strict byte reproducibility.
Development remains a moving checkout selected deliberately. A lightweight version
record can support continuation without changing existing job descriptor/recovery
contracts. Projects can reuse the approach after Whetstone proves it useful.

## Prior Evidence

Checkpoint `6e19fe3` preserves the earlier reviewed contract and five-slice plan.
Its final focused audit passed with no findings, but that result applies only to
the previous design. The archived fingerprint prototype passed 65 selected tests
and independent schema checks. Those results do not claim implementation of the
simplified launcher.

## Next Step

Use the stable launcher for future bounded audits and retain explicit development
selection for Whetstone work. Existing commands that set PYTHONPATH to the working
checkout still bypass the launcher; new jobs should use the shared command.
Spine's audit remains deferred until explicitly resumed. Future release promotion
will deliberately select a new tested checkpoint. These setup/documentation changes
are retained as a documentation checkpoint; this does not publish or promote a runtime. A broader portable launcher implementation and its
tests can follow separately if needed; it is not required to use this local pin.
