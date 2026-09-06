"""Reproducible bridge version/status transforms over exact UTF-8 byte spans."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any

from whetstone.preservation_inventory import build_inventory, sha256_bytes
from whetstone.versioning import VERSION_RE, promoted_phase2_version, stamped_round_version


class MaterializationError(ValueError):
    def __init__(self, category: str, message: str) -> None:
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class Anchor:
    kind: str
    start: int
    end: int
    value: str
    version: str
    prefix: str


@dataclass(frozen=True)
class MaterializedProposal:
    content: bytes
    transformations: list[dict[str, Any]]


def _lines(data: bytes) -> list[tuple[int, str, str]]:
    inventory = build_inventory(data, path="input.md")
    return [(u["byte_start"], data[u["byte_start"]:u["byte_end"]].decode("utf-8").rstrip("\r\n"), u["kind"])
            for u in inventory["units"]]


def _version_anchor(data: bytes) -> Anchor | None:
    lines = _lines(data)
    roots = [(offset, text) for offset, text, kind in lines
             if kind == "heading" and re.match(r"^ {0,3}#(?:[ \t]|$)", text)]
    # The first root heading is the primary root. Status/Version are fallbacks.
    candidates = [("heading", *roots[0])] if roots else []
    for prefix in ("Status:", "Version:"):
        candidates.extend((prefix, offset, text) for offset, text, kind in lines
                          if kind == "body" and text.startswith(prefix))
    for kind, offset, text in candidates:
        matches = list(VERSION_RE.finditer(text))
        if not matches:
            continue
        if len(matches) != 1:
            raise MaterializationError("unsupported_transform", "ambiguous numeric values in selected version anchor")
        match = matches[0]
        if kind == "Version:" and text[len(kind):match.start()].strip() not in {"", "v"}:
            continue
        prefix = "v" if kind != "heading" and match.start() > 0 and text[match.start()-1] == "v" else ""
        start = match.start() - len(prefix)
        return Anchor(kind, offset + len(text[:start].encode("utf-8")),
                      offset + len(text[:match.end()].encode("utf-8")), text[start:match.end()], match.group(), prefix)
    return None


def _status_anchor(data: bytes) -> tuple[int, int, str] | None:
    statuses = []
    for offset, text, kind in _lines(data):
        if kind != "body":
            continue
        match = re.match(r"^Status:[ \t]+(Accepted|Draft)\b", text)
        if match:
            statuses.append((offset + len(text[:match.start(1)].encode("utf-8")),
                             offset + len(text[:match.end(1)].encode("utf-8")), match[1]))
    if len(statuses) > 1:
        raise MaterializationError("unsupported_transform", "ambiguous Status anchors")
    return statuses[0] if statuses else None


def materialize_proposal(base: bytes, raw: bytes, *, phase: str, origin: str,
                         ordinary_eligible: bool) -> MaterializedProposal:
    """Produce prospective bytes only. Eligibility is derived by the orchestrator.

    Anchor edits are forbidden even when no prospective stamp is due. No bytes
    are normalized, restored, installed or written to history here.
    """
    if phase not in {"phase_1", "phase_2"} or origin not in {"editor", "supplied_revision", "orchestrator_noop", "phase2_entry"}:
        raise MaterializationError("invalid_binding", "unsupported phase or origin")
    if origin == "phase2_entry" and phase != "phase_2":
        raise MaterializationError("invalid_binding", "Phase 2 entry requires phase_2")
    before = _version_anchor(base)
    proposed = _version_anchor(raw)
    if (before is None) != (proposed is None) or (before and proposed and
            (before.kind, before.value) != (proposed.kind, proposed.value)):
        raise MaterializationError("untrusted_version_edit", "proposal changed, introduced or removed the selected version anchor")
    before_status, raw_status = _status_anchor(base), _status_anchor(raw)
    if (before_status is None) != (raw_status is None) or (before_status and raw_status and before_status[2] != raw_status[2]):
        raise MaterializationError("untrusted_version_edit", "proposal altered the orchestrator-owned status anchor")
    if origin in {"orchestrator_noop", "phase2_entry"} and raw != base:
        raise MaterializationError("invalid_binding", "maintenance raw bytes must equal the base")
    if not ordinary_eligible or before is None or (raw == base and origin != "phase2_entry"):
        return MaterializedProposal(raw, [])
    assert proposed is not None
    version = (promoted_phase2_version(before.version) if origin == "phase2_entry"
               else stamped_round_version(before.version, phase=phase))
    changes = []
    if proposed.prefix + version != proposed.value:
        changes.append({"kind": "version", "base_byte_start": before.start, "base_byte_end": before.end,
                        "input_byte_start": proposed.start, "input_byte_end": proposed.end,
                        "before": before.value, "after": proposed.prefix + version})
    if phase == "phase_1" and before_status and before_status[2] == "Accepted":
        assert raw_status is not None
        changes.append({"kind": "status", "base_byte_start": before_status[0], "base_byte_end": before_status[1],
                        "input_byte_start": raw_status[0], "input_byte_end": raw_status[1],
                        "before": "Accepted", "after": "Draft"})
    if not changes:
        return MaterializedProposal(raw, [])
    changes.sort(key=lambda change: change["input_byte_start"])
    if [change["base_byte_start"] for change in changes] != sorted(change["base_byte_start"] for change in changes):
        raise MaterializationError("unsupported_transform", "version/status anchor order changed")
    output = bytearray()
    cursor = 0
    for change in changes:
        start, end = change["input_byte_start"], change["input_byte_end"]
        if start < cursor or raw[start:end] != change["before"].encode() or base[change["base_byte_start"]:change["base_byte_end"]] != change["before"].encode():
            raise MaterializationError("invalid_binding", "overlapping or inconsistent trusted spans")
        output.extend(raw[cursor:start])
        output.extend(change["after"].encode())
        cursor = end
    output.extend(raw[cursor:])
    content = bytes(output)
    event = "phase2_entry" if origin == "phase2_entry" else ("phase1_revision" if phase == "phase_1" else "phase2_revision")
    return MaterializedProposal(content, [{"id": "version_stamp", "version": "bridge-version-transform-v1",
        "parameters": {"event": event, "phase": phase, "changes": changes},
        "input_sha256": sha256_bytes(raw), "output_sha256": sha256_bytes(content)}])


def verify_materialization(base: bytes, raw: bytes, output: bytes, transformations: list[dict[str, Any]], *,
                           phase: str, origin: str, ordinary_eligible: bool) -> None:
    expected = materialize_proposal(base, raw, phase=phase, origin=origin, ordinary_eligible=ordinary_eligible)
    if output != expected.content or transformations != expected.transformations:
        raise MaterializationError("invalid_binding", "materialization differs from pinned algorithm and immutable inputs")


def comparison_inventory(raw: bytes, actual: dict[str, Any]) -> dict[str, Any]:
    """Internal view after independently verifying materialization.

    Retain actual output IDs and byte order, but reverse trusted text/path spans
    to raw names for matching/counting. This view is not a persisted inventory.
    """
    raw_inventory = build_inventory(raw, path="raw.md")
    if len(raw_inventory["units"]) != len(actual["units"]):
        raise MaterializationError("invalid_binding", "trusted transforms changed physical line topology")
    view = deepcopy(actual)
    ids = {a["unit_id"]: b["unit_id"] for a, b in zip(raw_inventory["units"], actual["units"])}
    for source, target in zip(raw_inventory["units"], view["units"]):
        for key in ("section_id", "kind", "ordinal", "content_sha256", "normative"):
            target[key] = source[key]
    view["sections"] = deepcopy(raw_inventory["sections"])
    for section in view["sections"]:
        section["heading_unit_id"] = ids.get(section["heading_unit_id"])
        section["direct_unit_ids"] = [ids[uid] for uid in section["direct_unit_ids"]]
    return view
