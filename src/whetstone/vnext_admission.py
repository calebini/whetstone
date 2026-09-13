"""Explicit vNext selection, read-only admission and seed-only initialization."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from whetstone.config import _parse_simple_yaml
from whetstone.hashing import normalize_draft
from whetstone.vnext_contracts import (
    canonical_json_bytes, confined_file, decode_json, sha256_bytes,
    validate_contract_suite, validate_job_descriptor, VNextSchemaRegistry,
    ALGORITHM_VERSIONS,
)
from whetstone.vnext_sections import seed_section_map
from whetstone.vnext_storage import publish, safe_path, sync_directory
from whetstone.vnext_validation import validate_bootstrap, validate_seed_pointer
from whetstone.vocabulary import PROFILE_SETS, REVIEW_PROFILE_DEFINITIONS

ADMISSION_PATH = "rounds/vnext_admission.json"
POINTER_PATH = "rounds/current_verified.json"
HISTORY_PATH = "rounds/verified_history/current-verified-0.json"
SEED_MAP_PATH = "rounds/section_identity_map_seed.json"
ROOT_CLAIM_PATH = ".vnext-initializing"
# Only the admission/seed/reviewer subflow is qualified here. This cannot enable
# proposal, verification, promotion, Phase 2, or source apply-back.
REVIEWER_ONLY_QUALIFIED = True
GATES = ("admission", "seed_initialization", "review", "finding_admission", "complete")


class AdmissionError(ValueError):
    def __init__(self, code: str, message: str, *, terminal="CONFIG_INVALID", action="repair_configuration"):
        super().__init__(message)
        self.code, self.terminal, self.action = code, terminal, action


def check(condition, code, message, **kwargs):
    if not condition:
        raise AdmissionError(code, message, **kwargs)


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def runtime_contract(packet, name):
    VNextSchemaRegistry().validate(packet, name)
    return packet


def root_declares_vnext(root) -> bool:
    root = Path(root)
    if any((root / p).exists() or (root / p).is_symlink()
           for p in (ROOT_CLAIM_PATH, ADMISSION_PATH, POINTER_PATH, "rounds/.vnext-initializing")):
        return True
    descriptor = root / "job_descriptor.json"
    if descriptor.is_file():
        try:
            return json.loads(descriptor.read_bytes()).get("schema_version") == "job-descriptor-v2"
        except (ValueError, OSError, AttributeError):
            # In-flight vNext roots have the earlier runtime markers. Do not
            # reinterpret an unrelated legacy descriptor solely because it is
            # malformed or has a different historical shape.
            return False
    return False


def reject_legacy_writer(root):
    check(not root_declares_vnext(root), "vnext_selection_conflict",
          "legacy writer cannot operate on a vNext root; use its supported mode dispatch")


def config_packet(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    value = decode_json(text.encode()) if text.lstrip().startswith("{") else _parse_simple_yaml(text)
    check(isinstance(value, dict), "vnext_config_invalid", "configuration must be an object")
    # The existing YAML subset handles block mappings; additionally accept the
    # two simple flow-reference mappings printed by the D7 specification.
    if isinstance(value.get("vnext"), dict):
        for key in ("job_descriptor", "review_configuration"):
            item = value["vnext"].get(key)
            if isinstance(item, str) and item.startswith("{") and item.endswith("}"):
                parts = re.fullmatch(r'\{\s*path:\s*([^,]+),\s*hash:\s*([^,}]+)\s*\}', item)
                check(parts is not None, "vnext_config_invalid", "invalid flow reference; use a block mapping")
                value["vnext"][key] = {"path": parts[1].strip().strip('\"\''),
                                        "hash": parts[2].strip().strip('\"\'')}
    return value


def local_ref(root: Path, path: str) -> dict:
    raw = confined_file(root, path).read_bytes()
    return {"path": path, "hash": sha256_bytes(raw)}


def read_ref(root: Path, ref: dict) -> dict:
    check(isinstance(ref, dict) and set(ref) == {"path", "hash"},
          "vnext_config_invalid", "reference requires exactly path and hash")
    raw = confined_file(root, ref["path"]).read_bytes()
    check(sha256_bytes(raw) == ref["hash"], "vnext_input_invalid", "reference hash mismatch: " + ref["path"])
    value = decode_json(raw)
    check(raw == canonical_json_bytes(value), "vnext_input_invalid", "noncanonical input: " + ref["path"])
    return value


def select(root: Path, config: dict, *, descriptor_path=None, review_path=None) -> dict:
    explicit = descriptor_path is not None or review_path is not None
    check(not explicit or bool(descriptor_path and review_path), "vnext_config_invalid",
          "both --vnext-job-descriptor and --vnext-review-configuration are required")
    configured = config.get("vnext")
    if "vnext" in config:
        check(isinstance(configured, dict) and set(configured) == {"job_descriptor", "review_configuration"},
              "vnext_config_invalid", "vnext requires exactly job_descriptor and review_configuration")
        for ref in configured.values():
            read_ref(root, ref)
    cli = ({"job_descriptor": local_ref(root, descriptor_path),
            "review_configuration": local_ref(root, review_path)} if explicit else None)
    if cli and configured:
        check(all(cli[k]["hash"] == configured[k]["hash"] for k in cli),
              "vnext_selection_conflict", "CLI and configuration select different immutable inputs")
    selected = cli or configured
    if selected is None and (root / ADMISSION_PATH).is_file():
        existing = decode_json(confined_file(root, ADMISSION_PATH).read_bytes())
        selected = existing.get("selection")
    check(isinstance(selected, dict), "vnext_config_invalid", "vNext root requires its immutable input selection")
    runtime_contract(selected, "vnext_selection_v1")
    return selected


@dataclass
class Admission:
    root: Path
    selection: dict
    config: dict
    suite: object
    reader: object
    job: dict
    authority: dict
    invariants: dict
    review: dict
    seed: bytes
    section_map: dict

    @property
    def seed_reference(self):
        path = Path(self.job["seed_draft"]["path"])
        if path.is_absolute():
            path = path.relative_to(self.root)
        return {"path": path.as_posix(), "hash": self.job["seed_draft"]["hash"]}

    @property
    def pointer_job(self):
        # Pointer paths are logical run paths; descriptor locators may be host
        # absolute. Their resolved exact bytes and D6 job identity are unchanged.
        return {**self.job, "seed_draft": self.seed_reference}

    def diagnostic(self, gate="admission", *, admitted=False, error=None):
        return diagnostic(self.job, self.suite, gate, admitted=admitted, error=error)


def diagnostic(job=None, suite=None, gate="admission", *, admitted=False, error=None):
    mode = job.get("editing_mode") if job else None
    return runtime_contract({
        "protocol": "vnext",
        "terminal_state": error.terminal if error else None,
        "vnext": {
            "requested_mode": mode,
            "contract_suite_version": suite.version if suite else None,
            "suite_digest": suite.digest if suite else None,
            "available_modes": ["reviewer_only"] if REVIEWER_ONLY_QUALIFIED else [],
            "available_gates": sorted(GATES) if mode == "reviewer_only" and REVIEWER_ONLY_QUALIFIED else [],
            "requested_gate": gate,
            "admitted": admitted and error is None,
            "reason_code": error.code if error else "none",
            "reason": str(error) if error else "Inputs and selected capability validate.",
            "next_action": error.action if error else "run_requested_gate",
        },
    }, "vnext_capability_v1")


def _settings(config, review, job, authority):
    check("preservation_bridge" not in config, "vnext_selection_conflict", "bridge and vNext configuration cannot mix")
    allowed = {"vnext", "clients", "timeouts", "workflow", "review", "scope_contract", "reference_context"}
    check(not (set(config) - allowed), "vnext_config_invalid", "unsupported vNext controls: " + str(sorted(set(config)-allowed)))
    if "workflow" in config:
        check(config["workflow"] == review["workflow"], "vnext_mode_mismatch", "workflow differs from pinned review input")
    settings = config.get("review", {})
    check(isinstance(settings, dict) and not (set(settings) - {"mode", "profile_set", "profile_budgets"}),
          "vnext_config_invalid", "unsupported review settings")
    expected = {"mode": review["review_mode"], "profile_set": review["profile_set"],
                "profile_budgets": {p["name"]: p["budget"] for p in review["profiles"]}}
    check(all(value == expected[key] for key, value in settings.items()),
          "vnext_mode_mismatch", "review settings differ from pinned input")
    scope = config.get("scope_contract")
    if scope is not None:
        check(scope == {"path": job["scope_contract_path"]}, "vnext_mode_mismatch", "scope selector differs")
    contexts = config.get("reference_context", {})
    check(isinstance(contexts, dict) and not (set(contexts)-{"files"}), "vnext_config_invalid", "invalid reference context")
    files = contexts.get("files", {})
    check(isinstance(files, dict), "vnext_config_invalid", "context files must be a mapping")
    allowed_paths = {b["path"] for b in authority["bindings"] if b["role"] != "excluded"}
    for item in files.values():
        path = item if isinstance(item, str) else item.get("path") if isinstance(item, dict) else None
        check(path in allowed_paths, "vnext_input_invalid", "unbound or excluded reference context")
        if isinstance(item, dict):
            check(set(item) <= {"path", "role", "required"}, "vnext_config_invalid", "unknown reference context fields")
            if "role" in item:
                check(any(b["path"] == path and b["role"] == item["role"] for b in authority["bindings"]),
                      "vnext_mode_mismatch", "reference context role contradicts its authority binding")
    clients = config.get("clients", {})
    check(isinstance(clients, dict) and not (set(clients)-{"reviewer", "editor", "verifier"}),
          "vnext_config_invalid", "unknown client role")
    for role, client in clients.items():
        check(isinstance(client, dict) and set(client) <= {"name", "version", "model", "command"},
              "vnext_config_invalid", "unknown client field")
        check("command" not in client or (isinstance(client["command"], str) and bool(client["command"].strip())),
              "vnext_config_invalid", "client command must be a nonempty string")
        check(all(client.get(key, expected) == expected for key, expected in review[role].items()),
              "vnext_mode_mismatch", f"{role} identity differs from pinned input")
    timeouts = config.get("timeouts", {})
    check(isinstance(timeouts, dict) and set(timeouts) <= {"reviewer_seconds", "editor_seconds", "verifier_seconds"},
          "vnext_config_invalid", "invalid timeout settings")
    check(all(type(value) is int and value > 0 for value in timeouts.values()),
          "vnext_config_invalid", "timeouts must be positive integers")


def preflight(root, config=None, *, descriptor_path=None, review_path=None, gate="admission", existing=False) -> Admission:
    root = Path(root)
    check(root.is_dir() and not root.is_symlink(), "vnext_root_incompatible", "root must be an existing real directory")
    root = root.resolve()
    config = {} if config is None else config
    check(isinstance(config, dict), "vnext_config_invalid", "configuration must be an object")
    allowed = {"vnext", "clients", "timeouts", "workflow", "review", "scope_contract", "reference_context", "preservation_bridge"}
    check(not (set(config)-allowed), "vnext_config_invalid", "unsupported vNext controls: " + str(sorted(set(config)-allowed)))
    check("preservation_bridge" not in config, "vnext_selection_conflict", "cannot mix bridge and vNext")
    selection = select(root, config, descriptor_path=descriptor_path, review_path=review_path)
    if not existing:
        check(not any((root / name).exists() or (root / name).is_symlink()
                      for name in ("rounds", ROOT_CLAIM_PATH)),
              "vnext_root_incompatible", "fresh admission requires a root without runtime artifacts", action="new_isolated_root")
    job = read_ref(root, selection["job_descriptor"])
    try:
        VNextSchemaRegistry().validate(job, "job_descriptor_v2")
    except (ValueError, KeyError, TypeError) as exc:
        raise AdmissionError("vnext_descriptor_invalid", str(exc)) from exc
    try:
        suite = validate_contract_suite()
        check(job["contract_suite_version"] == suite.version
              and all(job[key] == value for key, value in ALGORITHM_VERSIONS.items()),
              "vnext_suite_unsupported", "descriptor requests an unsupported suite or algorithm")
    except (OSError, ValueError) as exc:
        raise AdmissionError("vnext_suite_unsupported", str(exc), action="use_supported_implementation") from exc
    try:
        validate_job_descriptor(job, suite)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AdmissionError("vnext_descriptor_invalid", str(exc)) from exc
    try:
        reader, job, authority, invariants = validate_bootstrap(
            root, selection["job_descriptor"], suite, review_configuration_ref=selection["review_configuration"])
        review = read_ref(root, selection["review_configuration"])
        seed = reader.raw(job["seed_draft"])
        if not existing:
            for relative, expected in (("job_descriptor.json", canonical_json_bytes(job)), ("spec.md", seed)):
                target = safe_path(root, relative)
                check(not target.exists() or target.read_bytes() == expected,
                      "vnext_root_incompatible", "initialization output conflicts with a prepared file: " + relative,
                      action="new_isolated_root")
        check(normalize_draft(seed.decode("utf-8")).encode("utf-8") == seed,
              "vnext_input_invalid", "seed must be normalized before its immutable descriptor is created")
        names = [p["name"] for p in review["profiles"]]
        check(bool(names) and len(names) == len(set(names)) and all(p["budget"] > 0 for p in review["profiles"]),
              "vnext_input_invalid", "review profiles must be nonempty, unique, and have positive budgets")
        check(all(name in REVIEW_PROFILE_DEFINITIONS for name in names) and review["profile_set"] in PROFILE_SETS,
              "vnext_input_invalid", "unsupported review profiles")
        check(review["workflow"] in {"standard", "mvp", "exploratory", "governance", "custom"},
              "vnext_input_invalid", "unsupported workflow")
        check(review["workflow"] != "mvp" or job["scope_contract_hash"] is not None,
              "vnext_input_invalid", "MVP requires an approved scope contract")
        _settings(config, review, job, authority)
        binding = next(b for b in authority["bindings"] if b["role"] == "mutable_target")
        section_map = seed_section_map(seed, job, binding["binding_id"])
        suite.registry.validate(section_map, "section_identity_map_v1")
    except AdmissionError:
        raise
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise AdmissionError("vnext_input_invalid", str(exc)) from exc
    admission = Admission(root, selection, config, suite, reader, job, authority, invariants, review, seed, section_map)
    try:
        check(job["editing_mode"] == "reviewer_only" and REVIEWER_ONLY_QUALIFIED,
              "vnext_mode_unavailable", "selected vNext mode has not completed runtime qualification",
              action="use_supported_implementation")
        check(gate in GATES, "vnext_gate_unavailable", "requested gate is not available in reviewer-only mode",
              action="inspect_available_work")
    except AdmissionError as exc:
        exc.job, exc.suite = job, suite
        raise
    if existing:
        validate_initialized(admission)
    return admission


def initialize(admission: Admission) -> dict:
    """The first exclusive marker creation is already a visible vNext claim."""
    root = admission.root
    # Repeat preflight immediately before taking fresh-root ownership.
    fresh = preflight(root, admission.config, descriptor_path=admission.selection["job_descriptor"]["path"],
                      review_path=admission.selection["review_configuration"]["path"])
    check(fresh.job == admission.job and fresh.selection == admission.selection,
          "vnext_input_invalid", "inputs changed since preflight")
    admission = fresh
    claim = safe_path(root, ROOT_CLAIM_PATH)
    try:
        with claim.open("xb") as stream:
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise AdmissionError("vnext_root_incompatible", "another initialization already claimed this root") from exc
    sync_directory(root)
    rounds = safe_path(root, "rounds")
    rounds.mkdir()
    sync_directory(root)
    publish(root, "rounds/.vnext-initializing", b"seed initialization in progress\n")
    publish(root, "job_descriptor.json", admission.job)
    map_ref = publish(root, SEED_MAP_PATH, admission.section_map)
    pointer = {"schema_version": "current-verified-pointer-v1", "job_id": admission.job["job_id"],
               "promotion_ordinal": 0, "verified_draft_path": admission.seed_reference["path"],
               "verified_draft_hash": admission.job["seed_draft"]["hash"],
               "verified_section_identity_map_path": map_ref["path"], "verified_section_identity_map_hash": map_ref["hash"],
               "promoted_at": stamp()}
    schema = admission.suite.registry.load("current_verified_pointer_v1")
    for key in schema["required"]:
        pointer.setdefault(key, None)
    admission.suite.registry.validate(pointer, "current_verified_pointer_v1")
    validate_seed_pointer(pointer, admission.pointer_job, map_ref)
    history = publish(root, HISTORY_PATH, pointer)
    publish(root, POINTER_PATH, pointer)
    publish(root, "spec.md", admission.seed)
    record = {"schema_version": "vnext-admission-v1", "selection": admission.selection,
              "job_id": admission.job["job_id"], "seed_pointer": history, "created_at": stamp()}
    runtime_contract(record, "vnext_admission_v1")
    publish(root, ADMISSION_PATH, record)
    return record


def validate_initialized(admission: Admission) -> dict:
    root = admission.root
    try:
        check(confined_file(root, ROOT_CLAIM_PATH).read_bytes() == b"",
              "vnext_lineage_invalid", "invalid initialization claim marker")
        record_raw = confined_file(root, ADMISSION_PATH).read_bytes()
        record = decode_json(record_raw)
        runtime_contract(record, "vnext_admission_v1")
        check(set(record) == {"schema_version", "selection", "job_id", "seed_pointer", "created_at"}
              and record["schema_version"] == "vnext-admission-v1", "vnext_lineage_invalid", "invalid admission record")
        check(record_raw == canonical_json_bytes(record)
              and all(record["selection"][role]["hash"] == admission.selection[role]["hash"]
                      for role in ("job_descriptor", "review_configuration"))
              and record["job_id"] == admission.job["job_id"], "vnext_lineage_invalid", "admitted selection changed")
        # A selector may name another confined copy of identical bytes. The
        # originally admitted inputs remain immutable and must still validate.
        for reference in record["selection"].values():
            read_ref(root, reference)
        check(confined_file(root, "job_descriptor.json").read_bytes() == canonical_json_bytes(admission.job),
              "vnext_lineage_invalid", "immutable admitted descriptor changed")
        pointer = read_ref(root, record["seed_pointer"])
        check(record["seed_pointer"]["path"] == HISTORY_PATH, "vnext_lineage_invalid", "wrong seed history path")
        admission.suite.registry.validate(pointer, "current_verified_pointer_v1")
        validate_seed_pointer(pointer, admission.pointer_job,
                              {"path": SEED_MAP_PATH, "hash": sha256_bytes(canonical_json_bytes(admission.section_map))})
        check(confined_file(root, POINTER_PATH).read_bytes() == canonical_json_bytes(pointer),
              "vnext_lineage_invalid", "reviewer-only pointer differs from seed snapshot")
        check(confined_file(root, SEED_MAP_PATH).read_bytes() == canonical_json_bytes(admission.section_map),
              "vnext_lineage_invalid", "seed map does not reproduce")
        check(confined_file(root, "spec.md").read_bytes() == admission.seed,
              "vnext_lineage_invalid", "seed materialization is stale; automatic repair is unavailable")
        check(not any((root / "rounds" / name).exists() for name in ("candidate_index", "candidates")),
              "vnext_lineage_invalid", "reviewer-only root contains candidate artifacts")
        return pointer
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise AdmissionError("vnext_lineage_invalid", str(exc), terminal="HALTED_ARTIFACT_INVALID", action="inspect_evidence") from exc
