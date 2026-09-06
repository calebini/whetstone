"""Conservative preliminary comparison; never supplies semantic authority."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from whetstone.preservation_contracts import SurfaceContext, _frozen
from whetstone.preservation_inventory import match_inventory_units


def assess_proposal(context: SurfaceContext, output: dict[str, Any]) -> dict[str, Any]:
    """Compare a verified materialization view, retaining actual output identities.

    Pending ID sets locate evidence work, not proposed predecessor/successor pairs.
    No absence of text is interpreted as an equivalent rewrite or supersession.
    """
    surface, base = context.surface, context.inventory
    matched = match_inventory_units(base, output)
    pairs = dict(matched.pairs)
    remaining = [u for u in output["units"] if u["unit_id"] not in pairs.values()]
    missing = [u for u in base["units"] if u["unit_id"] not in pairs]
    failures, pending, dispositions = [], [], []
    changed_sections, changed_normative = set(), set()

    def failure(category, ids, reason):
        failures.append({"category": category, "affected_unit_ids": ids, "reason": reason})

    def obligation(kind, before, after, reason):
        pending.append({"kind": kind, "base_unit_ids": before, "output_unit_ids": after, "reason": reason})

    def forbidden(unit, *, original):
        return (unit["section_id"] not in surface["allowed_sections"]
                or _frozen(unit["section_id"], surface["frozen_sections"])
                or (original and unit["unit_id"] not in surface["allowed_unit_ids"]))

    def signature(unit):
        return unit["kind"], unit["content_sha256"]

    # Section content multiplicity changes and frozen losses are decidable
    # even when a duplicate prevents choosing a particular predecessor.
    base_sections, output_sections = defaultdict(list), defaultdict(list)
    for unit in base["units"]:
        base_sections[unit["section_id"]].append(signature(unit))
    for unit in output["units"]:
        output_sections[unit["section_id"]].append(signature(unit))
    changed_sections.update(section for section in base_sections.keys() | output_sections.keys()
                            if Counter(base_sections[section]) != Counter(output_sections[section]))
    protected = defaultdict(list)
    for unit in base["units"]:
        if forbidden(unit, original=True):
            protected[(unit["section_id"], *signature(unit))].append(unit["unit_id"])
    available = Counter((u["section_id"], *signature(u)) for u in output["units"])
    for key, ids in protected.items():
        if len(ids) > available[key]:
            failure("allowed_surface_overrun", ids,
                    "Output cannot preserve the multiplicity of frozen or unlisted exact base units.")
    normative_before = Counter((u["section_id"], *signature(u)) for u in base["units"] if u["normative"])
    normative_after = Counter((u["section_id"], *signature(u)) for u in output["units"] if u["normative"])
    normative_loss_bound = sum((normative_before - normative_after).values())

    for unit in base["units"]:
        uid = unit["unit_id"]
        disposition, successors = "preserved", [pairs[uid]] if uid in pairs else []
        rationale = "Unique same-owner exact-byte mechanical correspondence."
        if uid not in pairs:
            disposition = "ambiguous"
            rationale = "Explicit correspondence and any semantic effect evidence are required."
            exact_same_owner = [u for u in remaining if signature(u) == signature(unit)
                                and u["section_id"] == unit["section_id"]]
            # Duplicate ambiguity is not itself proof of which frozen unit changed.
            if not exact_same_owner:
                changed_sections.add(unit["section_id"])
                if unit["normative"]:
                    changed_normative.add(uid)
                relocated = [u for u in remaining if signature(u) == signature(unit)
                             and u["section_id"] != unit["section_id"]]
                if len(relocated) == 1:
                    destination = relocated[0]["section_id"]
                    # Only a unique source can establish this concrete relocation.
                    sources = [u for u in missing if signature(u) == signature(unit)]
                    if len(sources) == 1:
                        changed_sections.add(destination)
                        if not any(uid in r["source_unit_ids"] and r["destination_section"] == destination
                                   for r in surface["relocations"]):
                            failure("allowed_surface_overrun", [uid, relocated[0]["unit_id"]],
                                    "Exact content relocated without explicit source/destination authority.")
                # An empty remaining output leaves no possible successor. With
                # other output present, pairing remains operator work even if a
                # particular deleted-looking line is very suggestive.
                if not remaining:
                    permitted = surface["deletion_allowed"] and uid in surface["authorized_deletion_unit_ids"]
                    if not permitted and uid not in surface["authorized_supersession_unit_ids"]:
                        disposition = "unauthorized_deleted"
                        failure("unauthorized_deleted", [uid], "No successor remains and deletion is not authorized.")
                    kind = "supersession" if uid in surface["authorized_supersession_unit_ids"] else "deletion"
                    obligation(kind, [uid], [], "Explicit sensitive-effect disposition/evidence is required.")
            obligation("correspondence", [uid], [u["unit_id"] for u in remaining], rationale)
        dispositions.append({"base_unit_id": uid, "disposition": disposition,
                             "successor_unit_ids": successors, "finding_refs": [], "evidence_refs": [], "rationale": rationale})

    # Extra units are provably additions only once every predecessor is matched.
    additions = [u["unit_id"] for u in remaining] if not missing else []
    for unit in remaining:
        uid = unit["unit_id"]
        exact_old = any(signature(u) == signature(unit) and u["section_id"] == unit["section_id"] for u in missing)
        if not exact_old:
            changed_sections.add(unit["section_id"])
            if forbidden(unit, original=False):
                failure("allowed_surface_overrun", [uid], "Output changes a section outside the approved allowed surface.")
        if uid in additions:
            if unit["normative"]:
                changed_normative.add(uid)
            if "add" not in surface["allowed_change_types"]:
                failure("allowed_surface_overrun", [uid], "Addition is not an approved change type.")
            obligation("addition", [], [uid], "Addition needs admitted finding attribution and operator effect evidence.")
    for field, count in (("max_changed_sections", len(changed_sections)),
                         ("max_changed_normative_units", max(len(changed_normative), normative_loss_bound +
                            sum(u["normative"] for u in remaining if u["unit_id"] in additions)))):
        cap = surface[field]
        if cap is not None and count > cap:
            failure("allowed_surface_overrun", [u["unit_id"] for u in missing] + additions,
                    f"Provable lower bound {count} exceeds {field}={cap}.")
    if missing and not surface["allowed_change_types"]:
        # Exact ambiguous rearrangements can still be explicitly preserved; only
        # definitely changed bytes establish a forbidden change here.
        if changed_sections:
            failure("allowed_surface_overrun", [u["unit_id"] for u in missing], "No change type is authorized.")
    return {"unit_dispositions": dispositions, "added_unit_ids": additions,
            "unmapped_output_unit_ids": [] if additions else [u["unit_id"] for u in remaining],
            "pending_obligations": pending, "failures": failures}
