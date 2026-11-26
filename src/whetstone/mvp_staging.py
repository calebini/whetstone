"""Offline preparation of single-seed, full Phase 1 MVP packages."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import re
import shutil

from whetstone import vnext_identity
from whetstone.hashing import normalize_draft
from whetstone.scope import validate_scope_contract
from whetstone.vnext_assertions import validate_assertion_program
from whetstone.vnext_contracts import (
    CONTRACT_ROOT, canonical_json_bytes, decode_json, derive_job_id, require,
    sha256_bytes, validate_contract_suite, validate_job_descriptor,
)
from whetstone.vnext_phase1_policy import POLICY, SUPPORTED_PROFILE_SETS
from whetstone.vnext_registry import SUITE_ALGORITHM_VERSIONS
from whetstone.vnext_review_configuration import validate as validate_review
from whetstone.vnext_sections import section_spans, seed_section_map
from whetstone.vocabulary import PROFILE_SETS

SUITE = "vnext-verified-consumer-3"


def add_parser(commands):
    parser = commands.add_parser("stage-mvp", help="prepare a single-spec verified MVP package offline")
    parser.add_argument("--seed", required=True, type=Path, help="source Markdown specification")
    parser.add_argument("--scope", required=True, type=Path, help="existing draft or approved intake JSON")
    parser.add_argument("--output", required=True, type=Path, help="new package directory, separate from the run")
    parser.add_argument("--authority-scope", required=True, help="authority scope of the mutable seed")
    parser.add_argument("--protect", action="append", nargs=3, required=True,
                        metavar=("HEADING", "MEANING", "RATIONALE"),
                        help="blocking semantic commitment on a unique Markdown heading (repeatable)")
    parser.add_argument("--profile-set", choices=SUPPORTED_PROFILE_SETS, required=True)
    parser.add_argument("--review-mode", choices=("vertical", "horizontal"), required=True)
    parser.add_argument("--client", choices=("codex", "claude-code"), required=True)
    parser.add_argument("--client-version", required=True, help="installed version shared by all three roles")
    parser.add_argument("--model", required=True, help="requested model shared by all three roles")
    for flag in ("max-operations", "max-changed-sections", "max-changed-normative-units"):
        parser.add_argument("--" + flag, type=int, required=True, help="per-proposal mutation ceiling")


def _load_scope(path):
    scope = decode_json(path.read_bytes())
    validate_scope_contract(scope)
    # Older intake wrote datetime.isoformat() in UTC. Convert only its known
    # spelling, in this new staged copy, before calculating any references.
    for record, key in ((scope, "generated_at"), (scope["approval"], "approved_at")):
        value = record[key]
        if value and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00", value):
            record[key] = datetime.fromisoformat(value).strftime("%Y-%m-%dT%H:%M:%SZ")
    return scope


def _commitments(seed, seed_hash, binding_id, protections):
    headings = defaultdict(list)
    for span in section_spans(seed):
        headings[span.heading].append(span.canonical_id)
    assertions = []
    for heading, meaning, rationale in protections:
        require(len(headings[heading]) == 1, f"--protect needs a unique seed heading: {heading!r}")
        require(meaning.strip() and rationale.strip(), "--protect needs both a meaning and a rationale")
        assertion = {
            "assertion_type": "concept_required", "target_scope": "section:" + headings[heading][0],
            "matcher": {"kind": "semantic", "value": meaning}, "enforcement": "semantic",
            "severity": "blocking", "rationale": rationale, "source_authority_binding_ids": [binding_id],
        }
        assertion["assertion_id"] = vnext_identity.assertion_id(seed_hash, assertion)
        assertions.append(assertion)
    return {"schema_version": "protected-invariants-v1", "base_draft_hash": seed_hash, "assertions": assertions}


def stage_mvp(args):
    suite = validate_contract_suite(CONTRACT_ROOT / "suites" / f"{SUITE}.json")
    original = args.seed.read_bytes()
    seed = normalize_draft(original.decode('utf-8')).encode('utf-8')
    scope = _load_scope(args.scope)
    files = {"seed.md": seed}

    def artifact(filename, schema, value):
        suite.registry.validate(value, schema)
        raw = canonical_json_bytes(value)
        files[filename] = raw
        return {"path": filename, "hash": sha256_bytes(raw)}

    seed_ref = {"path": "seed.md", "hash": sha256_bytes(seed)}
    binding = {
        "path": seed_ref["path"], "content_hash": seed_ref["hash"], "role": "mutable_target",
        "authority_scopes": [args.authority_scope], "effective_horizon": "current",
        "mutable": True, "may_introduce_requirements": False,
    }
    binding_id = binding["binding_id"] = vnext_identity.binding_id(binding)
    authority = artifact("authority.json", "authority_map_v1", {
        "schema_version": "authority-map-v1", "bindings": [binding], "precedence": [],
        "prospective_rules": {"report_ratification_delta": True, "introduce_compatibility_policy": "operator_decision"},
    })
    invariants = _commitments(seed, seed_ref["hash"], binding_id, args.protect)
    protected = artifact("protected.json", "protected_invariants_v1", invariants)
    scope_ref = artifact("scope.json", "scope_contract", scope)
    preset = PROFILE_SETS[args.profile_set]
    profiles = [{"name": name, "budget": preset.phase_1_default_budgets[name]} for name in preset.phase_1_profiles]
    client = {"name": args.client, "version": args.client_version, "model": args.model}
    review = {
        "schema_version": "review-configuration-v3", "completion_policy": POLICY, "workflow": "mvp",
        "review_mode": args.review_mode, "profile_set": args.profile_set, "profiles": profiles,
        "reviewer": client, "editor": client, "verifier": client,
    }
    validate_review(review, suite.registry)
    review_ref = artifact("review.json", "review_configuration_v3", review)
    constraints = artifact("constraints.json", "vnext_mutation_constraints_v1", {
        "schema_version": "vnext-mutation-constraints-v1",
        "constraints": {
            "allowed_operation_types": ["replace_section_body"], "required_context_binding_ids": [binding_id],
            "max_operations": args.max_operations, "max_changed_sections": args.max_changed_sections,
            "max_changed_normative_units": args.max_changed_normative_units,
        },
    })
    job = {
        "schema_version": "job-descriptor-v2", "contract_suite_version": SUITE,
        "created_at": scope["generated_at"], "editing_mode": "verified_promotion",
        **SUITE_ALGORITHM_VERSIONS[SUITE], "seed_draft": seed_ref,
        "authority_map_path": authority["path"], "authority_map_hash": authority["hash"],
        "scope_contract_path": scope_ref["path"], "scope_contract_hash": scope_ref["hash"],
        "protected_invariants_path": protected["path"], "protected_invariants_hash": protected["hash"],
        "review_configuration_hash": review_ref["hash"], "source_spec": {"path": None, "expected_hash": None},
    }
    job["job_id"] = derive_job_id(job, suite.digest)
    validate_job_descriptor(job, suite)
    validate_assertion_program(invariants, seed, seed_section_map(seed, job, binding_id))
    descriptor = artifact("descriptor.json", "job_descriptor_v2", job)
    manifest = artifact("package.json", "vnext_proposal_package_v1", {
        "schema_version": "vnext-proposal-package-v1", "job_descriptor": descriptor,
        "review_configuration": review_ref, "mutation_constraints": constraints,
    })
    files["run.yaml.tmp"] = (
        f"editing_mode: verified_promotion\ncontract_suite_version: {SUITE}\n"
        f"vnext_input_package:\n  path: package.json\n  hash: {manifest['hash']}\n"
    ).encode("utf-8")
    # Reserve the directory exclusively and publish the usable config last.
    output = args.output
    output.mkdir(mode=0o700)
    try:
        for filename, raw in files.items():
            (output / filename).write_bytes(raw)
        (output / "run.yaml.tmp").rename(output / "run.yaml")
    except OSError:
        shutil.rmtree(output)
        raise
    return {"config": str((output / "run.yaml").absolute()), "job_id": job["job_id"],
            "source_hash": sha256_bytes(original), "seed_hash": seed_ref["hash"],
            "package_hash": manifest["hash"], "scope_status": scope["status"], "profiles": profiles}
