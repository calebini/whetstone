"""Local effect-review helpers: resolve human line selections to exact Ref/IDs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from whetstone.hashing import canonical_json_hash
from whetstone.preservation_acceptance import AcceptanceService
from whetstone.preservation_contracts import read_artifact, read_ref, require, validate_evidence_bindings, validate_surface_bindings


def review_proposal(service: AcceptanceService, proposal_ref: dict[str, str]) -> dict[str, Any]:
    directory, proposal, admission = service._proposal_directory(proposal_ref)
    result = {"proposal": proposal_ref, "latest_report": service._latest_report(directory),
              "base": [], "output": [], "findings": [], "transformations": proposal["transformations"]}
    for side, inventory_ref, text_ref in (("base", admission["inventory"], admission["base_draft"]),
                                          ("output", proposal["materialized_inventory"], proposal["materialized_draft"])):
        inventory = read_artifact(service.root, inventory_ref, "bridge_inventory")
        content = read_ref(service.root, text_ref)
        result[side] = [{"line": n, "unit_id": unit["unit_id"], "section_id": unit["section_id"],
                         "kind": unit["kind"], "text": content[unit["byte_start"]:unit["byte_end"]].decode()}
                        for n, unit in enumerate(inventory["units"], 1)]
    for source in admission["finding_sources"]:
        artifact = read_artifact(service.root, source["artifact"], "reviewer_feedback")
        result["findings"].extend({"artifact": source["artifact"], "feedback_id": item["feedback_id"], "claim": item["claim"]}
                                  for item in artifact["feedback"] if item["feedback_id"] in source["feedback_ids"])
    return result


def adopt_effect(service: AcceptanceService, *, proposal_ref, surface_ref=None, output: str, kind: str,
                 base_lines: list[int], output_lines: list[int], disposition: str | None,
                 change_types: list[str], finding_ids: list[str], effect: str, rationale: str,
                 operator: str, approve: bool):
    """Explicitly adopt one grouped effect; never infer semantic equivalence.

    Each selected predecessor maps to the selected successor group. Independent
    effects use separate evidence files; shared successors require supersession.
    """
    require(approve and bool(operator.strip()), "effect adoption requires explicit approval and operator identity")
    with service._lock():
        service._boundary()
        _, proposal, admission = service._proposal_directory(proposal_ref)
        surface_ref = surface_ref or admission["allowed_change_surface"]
        context = validate_surface_bindings(service.root, surface_ref)
        require(context.surface["base_draft"] == admission["base_draft"] and context.surface["inventory"] == admission["inventory"],
                "effect authority must retain the exact proposal base/inventory")
        if kind == "authorize_scope_expansion":
            require(surface_ref != admission["allowed_change_surface"] and context.surface["scope_contract"] != admission["scope_contract"],
                    "scope expansion requires newly approved scope and surface")
        out_inventory = read_artifact(service.root, proposal["materialized_inventory"], "bridge_inventory")
        def select(lines, inventory):
            require(lines == sorted(set(lines)), "line selections must be unique and in byte order")
            require(all(type(n) is int and 1 <= n <= len(inventory["units"]) for n in lines), "line selection outside inventory")
            return [inventory["units"][n-1]["unit_id"] for n in lines]
        old, new = select(base_lines, context.inventory), select(output_lines, out_inventory)
        findings = []
        for fid in finding_ids:
            source_sha = None
            if "::" in fid:
                source_path, fid = fid.rsplit("::", 1)
                source_sha = service.reference(source_path)["sha256"]
            candidates = [(sha, name) for sha, name in context.findings if name == fid and (source_sha is None or sha == source_sha)]
            require(len(candidates) == 1, "finding ID is unknown or ambiguous across retained Reviewer artifacts")
            sha, name = candidates[0]
            findings.append({"artifact_sha256": sha, "feedback_id": name})
        addition = kind == "attest_addition"
        require((not old and disposition is None) if addition else (bool(old) and disposition is not None), "effect selection/disposition mismatch")
        value = {"schema_version": "bridge-operator-evidence-v2", "kind": kind, "proposal": proposal_ref,
                 "base_draft_sha256": admission["base_draft"]["sha256"], "base_inventory_sha256": admission["inventory"]["sha256"],
                 "scope_contract_sha256": context.surface["scope_contract"]["sha256"], "allowed_change_surface_sha256": surface_ref["sha256"],
                 "raw_proposal_sha256": proposal["raw_proposal"]["sha256"], "materialized_draft_sha256": proposal["materialized_draft"]["sha256"],
                 "transformations_sha256": canonical_json_hash(proposal["transformations"]),
                 "correspondence": [] if addition else [{"base_unit_id": uid, "successor_unit_ids": new, "disposition": disposition} for uid in old],
                 "added_unit_ids": new if addition else [], "change_types": change_types, "finding_refs": findings,
                 "effect": effect, "rationale": rationale, "approval": {"approved": True, "approved_by": operator,
                   "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}}
        # Validate shape and per-kind semantics before persisting operator output.
        from whetstone.preservation_contracts import validate_evidence_kind
        validate_evidence_kind(value)
        require(set(change_types) <= set(context.surface["allowed_change_types"]), "effect types exceed approved surface")
        require(bool(effect.strip()) and bool(rationale.strip()), "effect and rationale must be nonblank")
        ref = service._artifact(output, value, "bridge_operator_evidence")
        validate_evidence_bindings(service.root, ref, proposal_ref=proposal_ref, surface_ref=surface_ref)
        return ref
