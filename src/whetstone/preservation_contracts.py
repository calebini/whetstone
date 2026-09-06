"""Read-only bridge contract checks; no acceptance, stamping or persistence.

These validators establish artifact bindings and structural correspondence.
They are building blocks, NOT the live acceptance service: ordinary round gates,
trusted materialization, commit/replay and downstream integration are still required.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
from typing import Any

from whetstone.contracts import SchemaRegistry, SchemaValidationError, validate_artifact
from whetstone.hashing import canonical_json_hash, draft_hash
from whetstone.preservation_inventory import match_inventory_units, section_path, sha256_bytes, validate_inventory

BRIDGE_SCHEMAS = {
    "bounded-change-surface-v1": "bounded_change_surface",
    "bridge-inventory-v1": "bridge_inventory",
    "preservation-bridge-proposal-admission-v1": "preservation_bridge_proposal_admission",
    "preservation-bridge-proposal-v1": "preservation_bridge_proposal",
    "bridge-operator-evidence-v2": "bridge_operator_evidence",
    "preservation-bridge-acceptance-request-v1": "preservation_bridge_acceptance_request",
    "preservation-bridge-acceptance-admission-v1": "preservation_bridge_acceptance_admission",
    "current-runtime-preservation-bridge-report-v2": "current_runtime_preservation_bridge_report",
    "preservation-bridge-acceptance-v2": "preservation_bridge_acceptance",
    "preservation-bridge-terminal-failure-v1": "preservation_bridge_terminal_failure",
}


class BridgeContractError(ValueError):
    """Invalid immutable inputs or correspondence; never a permission grant."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BridgeContractError(message)


def _definition(value: Any, name: str) -> None:
    SchemaRegistry()._validate(value, {"$ref": f"preservation_bridge.schema.json#/$defs/{name}"}, "$")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise BridgeContractError(f"non-finite JSON value: {value}")


def decode_json(data: bytes) -> Any:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        # Also reject unpaired JSON surrogate escapes and non-finite overflow.
        canonical_json_hash(value)
        return value
    except (UnicodeError, ValueError) as exc:
        raise BridgeContractError(f"invalid UTF-8 JSON: {exc}") from exc


def read_ref(root: Path, reference: dict[str, str]) -> bytes:
    """Verify root confinement, regular-file type and exact persisted bytes."""
    _definition(reference, "ref")
    relative = Path(reference["path"])
    require(not relative.is_absolute(), "reference path must be run-root-relative")
    try:
        base = root.resolve(strict=True)
        target = (base / relative).resolve(strict=True)
        require(target.is_relative_to(base), "reference escapes run root")
        # O_NONBLOCK avoids blocking on a FIFO before the regular-file check.
        fd = os.open(target, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "reference is not a regular file")
            data = stream.read()
    except (OSError, ValueError, RuntimeError) as exc:
        raise BridgeContractError(f"cannot read reference {reference['path']}: {exc}") from exc
    require(sha256_bytes(data) == reference["sha256"], "reference byte hash mismatch")
    return data


def read_artifact(root: Path, reference: dict[str, str], schema: str) -> dict[str, Any]:
    value = decode_json(read_ref(root, reference))
    validate_artifact(value, schema)
    return value


def validate_reference_graph(root: Path, reference: dict[str, str], schema: str) -> None:
    """Validate reachable Ref bytes and bridge shapes, without claiming acceptance.

    Traverse only declared bridge artifacts. Opaque raw drafts, client responses,
    ordinary evidence and scope documents cannot inject new graph edges.
    Specific cross-artifact ownership is checked separately below.
    """
    active: set[str] = set()
    visited: set[tuple[str, str]] = set()

    def refs(value: Any, field: str = ""):
        if isinstance(value, dict):
            if set(value) == {"path", "sha256"}:
                yield value, field
            else:
                for name, item in value.items():
                    yield from refs(item, name)
        elif isinstance(value, list):
            for item in value:
                yield from refs(item, field)

    typed_fields = {
        "inventory": "bridge_inventory", "materialized_inventory": "bridge_inventory",
        "scope_contract": "scope_contract", "allowed_change_surface": "bounded_change_surface",
        "proposal": "preservation_bridge_proposal", "artifact": "reviewer_feedback",
        "reviewer_feedback": "reviewer_feedback", "editor_summary": "editor_summary",
        "operator_evidence": "bridge_operator_evidence", "evidence_refs": "bridge_operator_evidence",
        "request": "preservation_bridge_acceptance_request", "report": "current_runtime_preservation_bridge_report",
        "acceptance": "preservation_bridge_acceptance", "previous_acceptance": "preservation_bridge_acceptance",
    }

    def visit(current: dict[str, str], expected: str | None = None) -> None:
        identity = str((root / current["path"]).resolve())
        require(identity not in active, "cyclic artifact reference")
        key = (identity, current["sha256"])
        if key in visited and expected is None:
            return
        raw = read_ref(root, current)
        value = None
        if expected:
            value = decode_json(raw)
            validate_artifact(value, expected)
        if value is not None:
            active.add(identity)
            for child, field in refs(value):
                child_schema = typed_fields.get(field)
                if field == "admission":
                    proposal_owner = expected == "preservation_bridge_proposal" or (
                        expected == "current_runtime_preservation_bridge_report" and value["assessment"] == "proposal")
                    if expected == "preservation_bridge_terminal_failure":
                        record = decode_json(read_ref(root, child))
                        child_schema = BRIDGE_SCHEMAS.get(record.get("schema_version"))
                        require(child_schema in {"preservation_bridge_proposal_admission", "preservation_bridge_acceptance_admission"}, "invalid terminal failure admission")
                    else:
                        child_schema = "preservation_bridge_proposal_admission" if proposal_owner else "preservation_bridge_acceptance_admission"
                visit(child, child_schema)
            active.remove(identity)
        visited.add(key)

    visit(reference, schema)


@dataclass(frozen=True)
class SurfaceContext:
    surface: dict[str, Any]
    inventory: dict[str, Any]
    base: bytes
    findings: frozenset[tuple[str, str]]


def _indices(inventory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    units = {u["unit_id"]: u for u in inventory["units"]}
    require(len(units) == len(inventory["units"]), "duplicate base/output unit identity")
    return units, {u["unit_id"]: n for n, u in enumerate(inventory["units"])}


def _frozen(section: str, frozen: list[str]) -> bool:
    path = section_path(section)
    return any(path[:len(parent)] == parent for parent in map(section_path, frozen))


def validate_surface_bindings(root: Path, reference: dict[str, str]) -> SurfaceContext:
    surface = read_artifact(root, reference, "bounded_change_surface")
    base = read_ref(root, surface["base_draft"])
    inventory = read_artifact(root, surface["inventory"], "bridge_inventory")
    require(inventory["base_draft"] == surface["base_draft"], "surface inventory/base Ref mismatch")
    validate_inventory(inventory, base)
    scope = read_artifact(root, surface["scope_contract"], "scope_contract")
    require(scope["status"] == "approved", "scope is not approved")
    _definition(scope["approval"], "approval")
    require(bool(scope["approval"]["approved_by"].strip()), "scope operator is blank")
    require(bool(surface["approval"]["approved_by"].strip()), "surface operator is blank")
    units, _ = _indices(inventory)
    existing = {s["section_id"] for s in inventory["sections"]}
    for section in surface["allowed_sections"] + surface["frozen_sections"]:
        section_path(section)
    require(set(surface["frozen_sections"]) <= existing, "unknown frozen section")
    for name in ("allowed_unit_ids", "frozen_unit_ids", "authorized_deletion_unit_ids", "authorized_supersession_unit_ids"):
        require(set(surface[name]) <= units.keys(), f"unknown identity in {name}")
    allowed = set(surface["allowed_unit_ids"])
    require(not allowed.intersection(surface["frozen_unit_ids"]), "allowed/frozen unit conflict")
    for section in surface["allowed_sections"]:
        require(not _frozen(section, surface["frozen_sections"]), "allowed section is frozen, including inherited freeze")
    for uid in allowed:
        section = units[uid]["section_id"]
        require(section in surface["allowed_sections"], "allowed unit lacks explicit allowed section")
        require(not _frozen(section, surface["frozen_sections"]), "allowed unit has frozen owner")
    types = set(surface["allowed_change_types"])
    deletion = set(surface["authorized_deletion_unit_ids"])
    supersession = set(surface["authorized_supersession_unit_ids"])
    require(deletion <= allowed and supersession <= allowed, "sensitive authorization is not within allowed units")
    if surface["deletion_allowed"] or deletion:
        require(surface["deletion_allowed"] and "delete" in types and bool(deletion), "orphan deletion permission")
    if surface["weakening_allowed"]:
        require("weaken" in types and bool(allowed), "orphan weakening permission")
    if supersession:
        require("supersede" in types, "orphan supersession permission")
    for relocation in surface["relocations"]:
        section_path(relocation["destination_section"])
        require(relocation["change_type"] in types, "relocation lacks move/rename permission")
        require(relocation["destination_section"] in surface["allowed_sections"], "relocation destination is not allowed")
        require(set(relocation["source_unit_ids"]) <= allowed, "relocation source is not allowed")
        require(all(units[uid]["section_id"] != relocation["destination_section"] for uid in relocation["source_unit_ids"]),
                "relocation must change ownership")
    findings: set[tuple[str, str]] = set()
    sources: set[str] = set()
    for source in surface["finding_sources"]:
        artifact_hash = source["artifact"]["sha256"]
        require(artifact_hash not in sources, "duplicate finding source")
        sources.add(artifact_hash)
        feedback = read_artifact(root, source["artifact"], "reviewer_feedback")
        require(feedback["draft_hash"] == draft_hash(base.decode("utf-8")), "finding source has stale base hash")
        by_id = {item["feedback_id"]: item for item in feedback["feedback"]}
        require(len(by_id) == len(feedback["feedback"]), "duplicate feedback identity")
        for feedback_id in source["feedback_ids"]:
            require(feedback_id in by_id and by_id[feedback_id]["in_scope"] is True, "unknown or out-of-scope admitted finding")
            findings.add((artifact_hash, feedback_id))
    return SurfaceContext(surface, inventory, base, frozenset(findings))


def validate_proposal_bindings(root: Path, reference: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check immutable proposal identity only, not transform/round eligibility."""
    proposal = read_artifact(root, reference, "preservation_bridge_proposal")
    admission = read_artifact(root, proposal["admission"], "preservation_bridge_proposal_admission")
    approved = validate_surface_bindings(root, admission["allowed_change_surface"])
    for key in ("base_draft", "inventory", "scope_contract", "finding_sources"):
        require(admission[key] == approved.surface[key],
                "proposal admission/surface mismatch; inherited maintenance authority requires later acceptance-chain validation")
    base = read_ref(root, admission["base_draft"])
    inventory = read_artifact(root, admission["inventory"], "bridge_inventory")
    require(inventory["base_draft"] == admission["base_draft"], "proposal admission inventory/base mismatch")
    validate_inventory(inventory, base)
    raw = read_ref(root, proposal["raw_proposal"])
    raw.decode("utf-8", errors="strict")
    output = read_ref(root, proposal["materialized_draft"])
    require(draft_hash(output.decode("utf-8")) == proposal["materialized_draft_hash"], "materialized normalized hash mismatch")
    materialized = read_artifact(root, proposal["materialized_inventory"], "bridge_inventory")
    require(materialized["base_draft"] == proposal["materialized_draft"], "materialized inventory/draft mismatch")
    validate_inventory(materialized, output)
    if not proposal["transformations"]:
        require(raw == output, "unrecorded materialization change")
    else:
        previous = proposal["raw_proposal"]["sha256"]
        for transform in proposal["transformations"]:
            require(transform["input_sha256"] == previous, "broken transformation hash chain")
            previous = transform["output_sha256"]
        require(previous == proposal["materialized_draft"]["sha256"], "transformation output hash mismatch")
    if admission["origin"] == "editor":
        require(proposal["raw_response"] is not None, "editor proposal has no raw response")
        response = decode_json(read_ref(root, proposal["raw_response"]))
        require(isinstance(response, dict) and isinstance(response.get("draft_after_content"), str), "invalid raw Editor draft content")
        require(response["draft_after_content"].encode("utf-8") == raw, "raw draft differs from exact decoded Editor response")
    else:
        require(proposal["raw_response"] is None, "non-editor origin cannot claim a client response")
    if admission["origin"] in {"orchestrator_noop", "phase2_entry"}:
        require(raw == base, "maintenance raw proposal must equal base")
    normal = proposal["normal_round_evidence"]
    config = decode_json(read_ref(root, normal["effective_config"]))
    require(isinstance(config, dict), "effective config must be an object")
    if admission["origin"] == "phase2_entry":
        require(normal["reviewer_feedback"] == [] and normal["editor_summary"] is None, "Phase 2 entry has fabricated round evidence")
    else:
        require(normal["editor_summary"] is not None, "round proposal requires retained Editor/Orchestrator summary")
        summary = read_artifact(root, normal["editor_summary"], "editor_summary")
        require(summary["round_number"] == admission["round_number"], "summary round mismatch")
        require(summary["draft_before_hash"] == draft_hash(base.decode("utf-8")), "summary base mismatch")
    for feedback_ref in normal["reviewer_feedback"]:
        feedback = read_artifact(root, feedback_ref, "reviewer_feedback")
        require(feedback["round_number"] == admission["round_number"], "feedback round mismatch")
        # Vertical editing may retain different review profiles in one round.
        require(feedback["draft_hash"] == draft_hash(base.decode("utf-8")), "retained feedback base mismatch")
    return proposal, admission


def validate_evidence_bindings(root: Path, reference: dict[str, str], *, proposal_ref: dict[str, str],
                               surface_ref: dict[str, str]) -> dict[str, Any]:
    """Pin an attestation to output and acceptance authorization, without adopting it."""
    evidence = read_artifact(root, reference, "bridge_operator_evidence")
    proposal, admission = validate_proposal_bindings(root, proposal_ref)
    surface = validate_surface_bindings(root, surface_ref)
    require(evidence["proposal"] == proposal_ref, "evidence points to a different proposal")
    require(surface.surface["base_draft"] == admission["base_draft"], "acceptance surface uses a different base")
    require(surface.surface["inventory"] == admission["inventory"], "acceptance surface uses a different inventory")
    expected = {"base_draft_sha256": admission["base_draft"]["sha256"],
                "base_inventory_sha256": admission["inventory"]["sha256"],
                "scope_contract_sha256": surface.surface["scope_contract"]["sha256"],
                "allowed_change_surface_sha256": surface_ref["sha256"],
                "raw_proposal_sha256": proposal["raw_proposal"]["sha256"],
                "materialized_draft_sha256": proposal["materialized_draft"]["sha256"],
                "transformations_sha256": canonical_json_hash(proposal["transformations"])}
    require(all(evidence[key] == value for key, value in expected.items()), "evidence exact-effect binding mismatch")
    require(bool(evidence["approval"]["approved_by"].strip()), "evidence operator is blank")
    require(bool(evidence["effect"].strip()) and bool(evidence["rationale"].strip()), "empty effect or rationale")
    require({(f["artifact_sha256"], f["feedback_id"]) for f in evidence["finding_refs"]} <= surface.findings, "evidence finding not admitted")
    require(set(evidence["change_types"]) <= set(surface.surface["allowed_change_types"]),
            "evidence change types are not permitted by acceptance surface")
    if evidence["kind"] == "authorize_scope_expansion":
        require(surface.surface["scope_contract"] != admission["scope_contract"]
                and surface_ref != admission["allowed_change_surface"], "scope expansion requires newly approved scope and surface")
    validate_evidence_kind(evidence)
    return evidence


def validate_evidence_kind(evidence: dict[str, Any]) -> None:
    validate_artifact(evidence, "bridge_operator_evidence")
    entries, additions = evidence["correspondence"], evidence["added_unit_ids"]
    require(len({e["base_unit_id"] for e in entries}) == len(entries), "duplicate predecessor in evidence")
    kinds = {"authorize_deletion": ({"authorized_deleted"}, {"delete"}),
             "authorize_weakening": ({"operator_authorized_weakened"}, {"weaken"}),
             "attest_equivalence": ({"preserved", "moved", "reworded_equivalent"}, {"reword", "clarify", "move", "rename"}),
             "attest_strengthening": ({"strengthened"}, {"strengthen"}),
             "attest_supersession": ({"superseded"}, {"supersede"})}
    kind, types = evidence["kind"], set(evidence["change_types"])
    if kind == "attest_addition":
        require(not entries and bool(additions) and types == {"add"}, "addition evidence must contain only additions and add")
    elif kind == "authorize_scope_expansion":
        require(bool(entries or additions) and bool(types), "empty scope expansion")
    else:
        dispositions, permitted_types = kinds[kind]
        require(bool(entries) and not additions, "effect evidence requires correspondence and no additions")
        require(all(e["disposition"] in dispositions for e in entries), "evidence kind contradicts disposition")
        require(types <= permitted_types, "evidence claims an inapplicable change type")
        unchanged_only = kind == "attest_equivalence" and all(e["disposition"] == "preserved" for e in entries)
        require(bool(types) or unchanged_only, "effect evidence lacks change type")
    for entry in entries:
        require(bool(entry["successor_unit_ids"]) != (entry["disposition"] == "authorized_deleted"), "deletion/successor cardinality mismatch")
        applicable = {"moved": {"move", "rename"}, "reworded_equivalent": {"reword", "clarify"},
                      "strengthened": {"strengthen"}, "superseded": {"supersede"},
                      "authorized_deleted": {"delete"}, "operator_authorized_weakened": {"weaken"}}
        if entry["disposition"] in applicable:
            require(bool(types & applicable[entry["disposition"]]), "evidence type does not apply to its relation")


def complete_correspondence(base: dict[str, Any], output: dict[str, Any], *,
                            evidence: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Compose adopted subsets with unique mechanical matches, enforcing coverage.

    Evidence bindings must be checked separately. The returned relation is not an
    acceptance report and does not certify permissions or semantic truth.
    """
    before, old_order = _indices(base)
    after, new_order = _indices(output)
    entries: dict[str, dict[str, Any]] = {}
    additions: set[str] = set()
    for attestation in evidence:
        validate_evidence_kind(attestation)
        for entry in attestation["correspondence"]:
            uid = entry["base_unit_id"]
            require(uid in before, "unknown predecessor")
            require(set(entry["successor_unit_ids"]) <= after.keys(), "unknown successor")
            require(entry["successor_unit_ids"] == sorted(entry["successor_unit_ids"], key=new_order.__getitem__), "successors not in output byte order")
            require(uid not in entries or entries[uid] == entry, "conflicting correspondence attestations")
            entries[uid] = entry
        require([e["base_unit_id"] for e in attestation["correspondence"]] == sorted(
            (e["base_unit_id"] for e in attestation["correspondence"]), key=old_order.__getitem__), "evidence not in base byte order")
        require(set(attestation["added_unit_ids"]) <= after.keys(), "unknown added unit")
        require(attestation["added_unit_ids"] == sorted(attestation["added_unit_ids"], key=new_order.__getitem__), "additions not in output byte order")
        additions.update(attestation["added_unit_ids"])
    mechanical = match_inventory_units(base, output, adopted=list(entries.values()), added_unit_ids=list(additions))
    require(not mechanical.ambiguous_base and not mechanical.ambiguous_output, "ambiguous mechanical correspondence")
    require(not mechanical.unmatched_base and not mechanical.unmatched_output, "incomplete base/output coverage")
    for old, new in mechanical.pairs:
        entries[old] = {"base_unit_id": old, "successor_unit_ids": [new], "disposition": "preserved"}
    require(entries.keys() == before.keys(), "every base unit requires exactly one disposition")
    users: dict[str, set[str]] = defaultdict(set)
    required_kind = {"moved": "attest_equivalence", "reworded_equivalent": "attest_equivalence",
                     "strengthened": "attest_strengthening", "superseded": "attest_supersession",
                     "authorized_deleted": "authorize_deletion", "operator_authorized_weakened": "authorize_weakening"}
    for uid, entry in entries.items():
        disposition = entry["disposition"]
        if disposition == "preserved":
            require(len(entry["successor_unit_ids"]) == 1, "preserved must have one exact successor")
            target = after[entry["successor_unit_ids"][0]]
            require(all(before[uid][key] == target[key] for key in ("kind", "content_sha256", "section_id")), "preserved content/ownership changed")
            if (uid, target["unit_id"]) not in mechanical.pairs:
                require(any(e["kind"] == "attest_equivalence" and entry in e["correspondence"] for e in evidence), "explicit preserved mapping lacks equivalence evidence")
        else:
            require(any(e["kind"] == required_kind[disposition] and entry in e["correspondence"] for e in evidence), "disposition lacks its specific effect evidence")
        for successor in entry["successor_unit_ids"]:
            users[successor].add(uid)
    require(not additions.intersection(users), "output cannot be both successor and addition")
    require(additions | users.keys() == after.keys(), "output coverage is incomplete")
    for addition in additions:
        require(any(e["kind"] == "attest_addition" and addition in e["added_unit_ids"] for e in evidence), "addition lacks addition attestation")
    # One attestation must cover the entire transitive shared-successor group.
    for successor, predecessors in users.items():
        if len(predecessors) < 2:
            continue
        group = set(predecessors)
        pending = list(group)
        while pending:
            uid = pending.pop()
            for target in entries[uid]["successor_unit_ids"]:
                for related in users[target] - group:
                    group.add(related)
                    pending.append(related)
        require(all(entries[uid]["disposition"] == "superseded" for uid in group), "successor sharing requires supersession")
        require(any(e["kind"] == "attest_supersession" and all(entries[uid] in e["correspondence"] for uid in group) for e in evidence), "incomplete connected supersession attestation")
    return sorted(entries.values(), key=lambda e: old_order[e["base_unit_id"]]), sorted(additions, key=new_order.__getitem__)


def validate_change_surface(context: SurfaceContext, output: dict[str, Any], *,
                            correspondence: list[dict[str, Any]], additions: list[str],
                            evidence: list[dict[str, Any]]) -> dict[str, int]:
    """Check permissions/counts on a completed relation; no trusted-span exemption.

    Call after complete_correspondence and exact evidence-binding validation.
    Future materialization integration must account for its verified spans rather
    than weakening these exact-content checks.
    """
    surface = context.surface
    before, _ = _indices(context.inventory)
    after, _ = _indices(output)
    allowed = set(surface["allowed_unit_ids"])
    allowed_sections = set(surface["allowed_sections"])
    permitted = set(surface["allowed_change_types"])
    changed_sections: set[str] = set()
    changed_normative: set[str] = set()
    accepted_types = {"moved": {"move", "rename"}, "reworded_equivalent": {"clarify", "reword"},
                      "strengthened": {"strengthen"}, "superseded": {"supersede"},
                      "authorized_deleted": {"delete"}, "operator_authorized_weakened": {"weaken"}}
    def attributed(entry: dict[str, Any] | None, addition: str | None = None) -> bool:
        return any((entry in e["correspondence"] if entry is not None else addition in e["added_unit_ids"])
                   and bool({(f["artifact_sha256"], f["feedback_id"]) for f in e["finding_refs"]} & context.findings)
                   for e in evidence)
    for entry in correspondence:
        uid, disposition = entry["base_unit_id"], entry["disposition"]
        if disposition == "preserved":
            continue
        source = before[uid]
        require(uid in allowed and source["section_id"] in allowed_sections, "changed unit outside allowed surface")
        require(not _frozen(source["section_id"], surface["frozen_sections"]) and uid not in surface["frozen_unit_ids"], "changed unit is frozen")
        require(bool(accepted_types[disposition] & permitted), "disposition change type is not allowed")
        require(attributed(entry), "changed unit lacks admitted finding attribution")
        if disposition == "authorized_deleted":
            require(surface["deletion_allowed"] and uid in surface["authorized_deletion_unit_ids"], "deletion not authorized")
        if disposition == "operator_authorized_weakened":
            require(surface["weakening_allowed"], "weakening not authorized")
        if disposition == "superseded":
            require(uid in surface["authorized_supersession_unit_ids"], "supersession not authorized")
        changed_sections.add(source["section_id"])
        if source["normative"]:
            changed_normative.add(uid)
        for successor in entry["successor_unit_ids"]:
            target = after[successor]
            require(target["section_id"] in allowed_sections, "successor destination is not allowed")
            require(not _frozen(target["section_id"], surface["frozen_sections"]), "successor destination is frozen")
            changed_sections.add(target["section_id"])
            if target["section_id"] != source["section_id"]:
                require(any(uid in r["source_unit_ids"] and r["destination_section"] == target["section_id"]
                            and r["change_type"] in permitted for r in surface["relocations"]), "missing exact relocation permission")
    for uid in additions:
        unit = after[uid]
        require("add" in permitted and unit["section_id"] in allowed_sections, "addition is outside allowed surface")
        require(not _frozen(unit["section_id"], surface["frozen_sections"]), "addition destination is frozen")
        require(attributed(None, uid), "addition lacks admitted finding attribution")
        changed_sections.add(unit["section_id"])
        if unit["normative"]:
            changed_normative.add(uid)
    # Known exact cross-owner disappearance/reappearance cannot be laundered as delete+add.
    for entry in correspondence:
        if entry["disposition"] != "authorized_deleted":
            continue
        old = before[entry["base_unit_id"]]
        require(not any(old["kind"] == after[uid]["kind"] and old["content_sha256"] == after[uid]["content_sha256"]
                        and old["section_id"] != after[uid]["section_id"] for uid in additions), "delete/add cannot authorize a known relocation")
    for name, actual in (("max_changed_sections", len(changed_sections)), ("max_changed_normative_units", len(changed_normative))):
        require(surface[name] is None or actual <= surface[name], f"{name} exceeded")
    return {"changed_sections": len(changed_sections), "changed_normative_units": len(changed_normative)}


@dataclass(frozen=True)
class ValidatedChange:
    """Read-only contract result, deliberately not an acceptance report/marker."""

    correspondence: list[dict[str, Any]]
    additions: list[str]
    changed_sections: int
    changed_normative_units: int


def validate_untransformed_change(root: Path, *, proposal_ref: dict[str, str],
                                   surface_ref: dict[str, str],
                                   evidence_refs: list[dict[str, str]]) -> ValidatedChange:
    """Compose foundation checks for exact raw=materialized proposals.

    This is an offline check, not the pending acceptance command. It does not
    check live current authority, adopt approvals, complete a round, or write
    anything. Transformed proposals need the later trusted materializer.
    """
    require(len({(r["path"], r["sha256"]) for r in evidence_refs}) == len(evidence_refs), "duplicate evidence Ref")
    validate_reference_graph(root, proposal_ref, "preservation_bridge_proposal")
    proposal, admission = validate_proposal_bindings(root, proposal_ref)
    require(not proposal["transformations"], "trusted transformations require the later materialization service")
    context = validate_surface_bindings(root, surface_ref)
    require(context.surface["base_draft"] == admission["base_draft"] and context.surface["inventory"] == admission["inventory"],
            "acceptance authorization must retain the exact proposal base and inventory")
    evidence = [validate_evidence_bindings(root, ref, proposal_ref=proposal_ref, surface_ref=surface_ref) for ref in evidence_refs]
    output = read_artifact(root, proposal["materialized_inventory"], "bridge_inventory")
    relation, additions = complete_correspondence(context.inventory, output, evidence=evidence)
    counts = validate_change_surface(context, output, correspondence=relation, additions=additions, evidence=evidence)
    return ValidatedChange(relation, additions, counts["changed_sections"], counts["changed_normative_units"])
