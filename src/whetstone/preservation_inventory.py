"""Exact-byte bridge-lines-v1 inventory and conservative structural matching.

These pure functions neither attest semantic effects nor grant draft authority.
The live preservation capability remains unavailable until full qualification.
"""

from __future__ import annotations

from array import array
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from whetstone.contracts import SchemaValidationError, validate_artifact
from whetstone.hashing import canonical_json_dumps

PARSER_VERSION = "bridge-lines-v1"
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|$)")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_NORMATIVE = re.compile(r"(?<![A-Za-z0-9_])(MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)(?![A-Za-z0-9_])")
_LINE = re.compile(rb"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section_path(section_id: str) -> list[list[Any]]:
    """Parse only the canonical bridge path grammar, not review slugs."""
    try:
        segments = json.loads(section_id)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid section path JSON") from exc
    if not isinstance(segments, list) or any(
        not isinstance(item, list) or len(item) != 2
        or not isinstance(item[0], str) or type(item[1]) is not int or item[1] < 1
        for item in segments
    ):
        raise ValueError("invalid section path segments")
    if canonical_json_dumps(segments) != section_id:
        raise ValueError("section path must use canonical compact JSON")
    return segments


def build_inventory(data: bytes, *, path: str) -> dict[str, Any]:
    """Partition strict UTF-8 bytes, preserving BOM and all line terminators."""
    data.decode("utf-8", errors="strict")
    base_hash = sha256_bytes(data)
    root = {"section_id": "[]", "parent_section_id": None, "heading_unit_id": None, "direct_unit_ids": []}
    sections = [root]
    current = root
    stack: list[tuple[int, list[list[Any]]]] = []
    siblings: Counter[tuple[str, str]] = Counter()
    ordinals: Counter[tuple[str, str]] = Counter()
    units: list[dict[str, Any]] = []
    fence: tuple[str, int] | None = None
    for match in _LINE.finditer(data):
        raw = match.group()
        text = raw.decode("utf-8").rstrip("\r\n")
        heading = _HEADING.match(text) if fence is None else None
        marker = _FENCE.match(text)
        if heading:
            depth = len(heading[1])
            title = re.sub(r"(?:^|[ \t]+)#+[ \t]*$", "", heading[2] or "").strip(" \t")
            while stack and stack[-1][0] >= depth:
                stack.pop()
            parent = stack[-1][1] if stack else []
            parent_id = canonical_json_dumps(parent)
            siblings[(parent_id, title)] += 1
            segments = parent + [[title, siblings[(parent_id, title)]]]
            current = {"section_id": canonical_json_dumps(segments), "parent_section_id": parent_id,
                       "heading_unit_id": None, "direct_unit_ids": []}
            sections.append(current)
            stack.append((depth, segments))
            kind = "heading"
        elif fence is not None:
            char, length = fence
            if re.fullmatch(r" {0,3}" + re.escape(char) + "{" + str(length) + r",}[ \t]*", text):
                kind = "fence_delimiter"
                fence = None
            else:
                kind = "fence_body"
        elif marker:
            fence = (marker[1][0], len(marker[1]))
            kind = "fence_delimiter"
        else:
            kind = "separator" if not text.strip(" \t") else "body"
        section_id = current["section_id"]
        ordinals[(section_id, kind)] += 1
        ordinal = ordinals[(section_id, kind)]
        identity = canonical_json_dumps([PARSER_VERSION, base_hash, section_id, kind, ordinal])
        unit_id = "u_" + sha256_bytes(identity.encode("utf-8"))
        unit = {"unit_id": unit_id, "section_id": section_id, "kind": kind, "ordinal": ordinal,
                "byte_start": match.start(), "byte_end": match.end(),
                "content_sha256": sha256_bytes(raw), "normative": bool(_NORMATIVE.search(text))}
        units.append(unit)
        current["direct_unit_ids"].append(unit_id)
        if kind == "heading":
            current["heading_unit_id"] = unit_id
    if len({unit["unit_id"] for unit in units}) != len(units):
        raise ValueError("bridge unit identity collision")
    if sum(unit["byte_end"] - unit["byte_start"] for unit in units) != len(data):
        raise ValueError("bridge inventory does not partition input bytes")
    return {"schema_version": "bridge-inventory-v1", "parser_version": PARSER_VERSION,
            "base_draft": {"path": path, "sha256": base_hash}, "sections": sections, "units": units}


def validate_inventory(inventory: dict[str, Any], data: bytes) -> None:
    """Recompute every field; schema validity alone is insufficient."""
    validate_artifact(inventory, "bridge_inventory")
    expected = build_inventory(data, path=inventory["base_draft"]["path"])
    if inventory != expected:
        raise SchemaValidationError("$", "inventory differs from exact-byte recomputation")


@dataclass(frozen=True)
class MechanicalMatch:
    pairs: tuple[tuple[str, str], ...]
    ambiguous_base: tuple[str, ...]
    ambiguous_output: tuple[str, ...]
    unmatched_base: tuple[str, ...]
    unmatched_output: tuple[str, ...]


def _unique_lcs(left: list[tuple[str, str]], right: list[tuple[str, str]]) -> list[tuple[int, int]] | None:
    """Return the unique maximum matching, or None (distinct alignments).

    Counting dynamic-programming skip paths would incorrectly report ambiguity
    when those paths describe the same alignment. Instead enumerate pairs that
    can occur at each rank of an optimal alignment using prefix/suffix lengths.
    """
    if left == right:
        return list(zip(range(len(left)), range(len(right))))
    n, m = len(left), len(right)
    suffix = [array("I", [0]) * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            suffix[i][j] = 1 + suffix[i + 1][j + 1] if left[i] == right[j] else max(suffix[i + 1][j], suffix[i][j + 1])
    length = suffix[0][0]
    choices: dict[int, tuple[int, int]] = {}
    ambiguous = False
    previous = array("I", [0]) * (m + 1)
    for i in range(n):
        current = array("I", [0]) * (m + 1)
        for j in range(m):
            if left[i] == right[j]:
                rank = previous[j]
                if rank + 1 + suffix[i + 1][j + 1] == length:
                    if rank in choices:
                        ambiguous = True
                    choices[rank] = (i, j)
                current[j + 1] = rank + 1
            else:
                current[j + 1] = max(previous[j + 1], current[j])
        previous = current
    return None if ambiguous else [choices[rank] for rank in range(length)]


def match_inventory_units(base: dict[str, Any], output: dict[str, Any], *,
                          adopted: list[dict[str, Any]] | None = None,
                          added_unit_ids: list[str] | None = None) -> MechanicalMatch:
    """Match remaining units after explicit entries; never authorize those entries.

    Callers must separately validate inventories, adopted evidence and complete
    correspondence. No cross-section matching, fuzzy pairing or trusted stamp
    exemption is applied by this low-level function.
    """
    adopted = adopted or []
    excluded_base = {entry["base_unit_id"] for entry in adopted}
    excluded_output = {uid for entry in adopted for uid in entry["successor_unit_ids"]} | set(added_unit_ids or [])
    old: dict[str, list[dict[str, Any]]] = defaultdict(list)
    new: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in base["units"]:
        if unit["unit_id"] not in excluded_base:
            old[unit["section_id"]].append(unit)
    for unit in output["units"]:
        if unit["unit_id"] not in excluded_output:
            new[unit["section_id"]].append(unit)
    pairs = []
    ambiguous_base: set[str] = set()
    ambiguous_output: set[str] = set()
    for section, left in old.items():
        right = new.get(section, [])
        alignment = _unique_lcs([(u["kind"], u["content_sha256"]) for u in left],
                                [(u["kind"], u["content_sha256"]) for u in right])
        if alignment is None:
            ambiguous_base.update(u["unit_id"] for u in left)
            ambiguous_output.update(u["unit_id"] for u in right)
        else:
            pairs.extend((left[i]["unit_id"], right[j]["unit_id"]) for i, j in alignment)
    paired_base = {a for a, _ in pairs}
    paired_output = {b for _, b in pairs}
    order = {u["unit_id"]: i for i, u in enumerate(base["units"])}
    pairs.sort(key=lambda pair: order[pair[0]])
    return MechanicalMatch(tuple(pairs),
        tuple(u["unit_id"] for u in base["units"] if u["unit_id"] in ambiguous_base),
        tuple(u["unit_id"] for u in output["units"] if u["unit_id"] in ambiguous_output),
        tuple(u["unit_id"] for u in base["units"] if u["unit_id"] not in paired_base | ambiguous_base | excluded_base),
        tuple(u["unit_id"] for u in output["units"] if u["unit_id"] not in paired_output | ambiguous_output | excluded_output))
