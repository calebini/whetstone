# 18.7 two-candidate concurrent selection

Date: 2026-09-18. Starting checkpoint: `64533a4`.

This is the G1 joint selection proof from the [18.7 acceptance map](VNEXT_18_7_ACCEPTANCE_MAP.md).
It exercises the candidate leaf's [Concurrent Promotion Preparation](specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md#concurrent-promotion-preparation)
requirement with two actual caller processes and two already-final verified
candidates. Runtime scheduling and its promotion-before-new-work gate are unchanged.

**All 19 distinct methods pass with no skips:** the new method covers both lock-winner orders (94.036 seconds); the 16 existing promotion and two Batch A methods pass separately (935.697 seconds). Both runs passed on their first attempt. No runtime fix was needed.

## Exact proof

One test method has two independent cases: caller A acquires first, then caller B
acquires first on a fresh fixture. Each fixture creates two distinct candidates
through the existing Editor/registration/independent Verifier producers on the
same ordinal-0 base. Both are final verified and promotion-permitted; their
creation ordinals are 1 and 2. Neither has a promotion intent initially.
Reviewer inputs and round selectors use the existing component fixture. This is
not a new canonical-runtime or cross-implementation journey.

Both subprocesses receive identical complete authority selectors and the same
fictional suite registration. A test wrapper pauses the chosen caller immediately
after real lock acquisition, before selection or publication. The other caller
attempts production promotion and must report busy. All run bytes and fixture
client counts must remain unchanged at this boundary.

The first caller resumes the production promotion path. It must select creation
ordinal 2 and bind that candidate in the sole intent, event, snapshot and committed
pointer, using that caller's timestamp. The pointer advances exactly once to
promotion ordinal 1. Spec, source-round draft and state match committed authority.
All original evidence is preserved except the three mutable authority/mirror
files. Exactly the intent, event, snapshot and round-2 draft are newly created.

The losing process then opens a fresh storage/history owner and retries. It must
return `not_eligible`, retain the same pointer, and create neither another
promotion nor an older-candidate fallback. Parent read-only inspection also
changes no bytes. Both child processes exit successfully. Each case retains
exactly two scripted Editor calls and two scripted Verifier calls from fixture
preparation; promotion invokes no role workflow.

Existing promotion tests separately cover interrupted preparation, reservation
over later registrations, multiple claimants and nonprefix rejection. The Batch A
runtime tests separately cover actual process death around second commit and
typed rename uncertainty. Their scopes are preserved rather than folded into
this new test's case count.

## Validation and handoff

The [machine-readable record](audits/VNEXT_CONCURRENT_SELECTION.json) binds both
commands, source manifests, exact test identities and retained logs under ignored
`rounds/vnext-concurrent-selection-001/`.

```sh
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_concurrent_selection -v
PYTHONPATH=src:tests python3 -m unittest test_vnext_verified_promotion test_vnext_verified_runtime_faults -v
```

This checkpoint closes G1 at the declared component/process scope. The acceptance map now has 84 distinct methods with current-source passing evidence (81 prior + one new method + two refreshed Batch A methods; the 16 promotion regressions overlap). G2's fixed evidence refresh,
18.5–18.6 dependency acceptance and later consuming-release gates remain separate.
The current-source Batch A rerun is credited toward G2: 97 existing methods remain (eight runtime and 89 component).
18.7 stays incomplete. D8 design/audit closure stands; frozen suite 1 and shipping
qualification maps are unchanged. No external provider, activation, 18.8–18.9
implementation, push or external specification apply-back is included.
