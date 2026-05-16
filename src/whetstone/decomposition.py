"""Spec decomposition planning primitives."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any

from whetstone.hashing import draft_hash, sha256_text
from whetstone.sections import slug_section_path


AUTHORITY_TOPOLOGIES = {"coordinated_family", "peer_family", "parent_child", "appendix_extraction", "no_split"}
TARGET_SPEC_ROLES = {"coordinating_spec", "leaf_spec", "peer_spec", "appendix_spec"}
PLANNING_MODES = {"inventory_only", "proposed_split", "approved_split"}
NORMATIVE_PATTERN = re.compile(r"\b(MUST NOT|SHOULD NOT|MUST|SHOULD|MAY|REQUIRED|OPTIONAL)\b")
INTRO_TOKEN_THRESHOLD = 12


@dataclass(frozen=True)
class SourceSection:
    id: str
    heading: str
    level: int
    path: tuple[str, ...]
    start_line: int
    end_line: int
    normative_statement_count: int


@dataclass(frozen=True)
class ExtractableUnit:
    id: str
    section_id: str
    scope: str
    heading: str
    start_line: int
    end_line: int
    normative_statement_count: int


def build_decomposition_plan(
    *,
    source_spec_path: Path,
    output_dir: Path,
    map_path: Path | None = None,
    authority_topology: str | None = None,
) -> dict:
    """Write decomposition plan artifacts and return a compact result."""

    source = source_spec_path.read_text(encoding="utf-8")
    sections = section_inventory(source)
    units = extractable_units(source, sections)
    plan_map = _read_map(map_path) if map_path else None
    packet = _plan_packet(
        source_spec_path=source_spec_path,
        source=source,
        sections=sections,
        units=units,
        plan_map=plan_map,
        authority_topology=authority_topology,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "decomposition_plan.json"
    md_path = output_dir / "decomposition_plan.md"
    json_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_decomposition_plan_markdown(packet), encoding="utf-8")
    return {
        "decomposition_plan": str(json_path),
        "decomposition_plan_markdown": str(md_path),
        "source_spec_hash": packet["source_spec_hash"],
        "planning_mode": packet["planning_mode"],
        "authority_topology": packet["authority_topology"],
        "target_spec_count": len(packet["target_specs"]),
        "unassigned_source_section_count": len(packet["coverage"]["unassigned_source_section_ids"]),
    }


def section_inventory(markdown: str) -> list[SourceSection]:
    lines = markdown.splitlines()
    raw: list[tuple[int, int, str, tuple[str, ...], str]] = []
    path: list[str] = []
    counters: dict[str, int] = {}
    for line_number, line in enumerate(lines, start=1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        heading = match.group(2).strip()
        path = path[: level - 1]
        path.append(heading)
        base_id = slug_section_path(path)
        counters[base_id] = counters.get(base_id, 0) + 1
        section_id = base_id if counters[base_id] == 1 else f"{base_id}#{counters[base_id]}"
        raw.append((line_number, level, heading, tuple(path), section_id))
    sections: list[SourceSection] = []
    for index, (start_line, level, heading, heading_path, section_id) in enumerate(raw):
        next_peer_or_parent = next(
            (
                future_start_line
                for future_start_line, future_level, *_rest in raw[index + 1 :]
                if future_level <= level
            ),
            None,
        )
        end_line = (next_peer_or_parent - 1) if next_peer_or_parent else len(lines)
        body = "\n".join(lines[start_line - 1 : end_line])
        sections.append(
            SourceSection(
                id=section_id,
                heading=heading,
                level=level,
                path=heading_path,
                start_line=start_line,
                end_line=end_line,
                normative_statement_count=len(NORMATIVE_PATTERN.findall(body)),
            )
        )
    return sections


def extractable_units(markdown: str, sections: list[SourceSection]) -> list[ExtractableUnit]:
    """Return leaf sections and meaningful parent intro blocks as extractable units."""

    lines = markdown.splitlines()
    children_by_parent = _children_by_parent(sections)
    units: list[ExtractableUnit] = []
    for section in sections:
        if section.level == 1:
            continue
        children = children_by_parent.get(section.id, [])
        if not children:
            units.append(
                ExtractableUnit(
                    id=section.id,
                    section_id=section.id,
                    scope="section",
                    heading=section.heading,
                    start_line=section.start_line,
                    end_line=section.end_line,
                    normative_statement_count=_normative_count_for_line_range(lines, section.start_line, section.end_line),
                )
            )
            continue
        intro_start = section.start_line + 1
        intro_end = children[0].start_line - 1
        if intro_start <= intro_end and _is_meaningful_direct_body(lines[intro_start - 1 : intro_end]):
            units.append(
                ExtractableUnit(
                    id=f"{section.id}::__intro__",
                    section_id=section.id,
                    scope="intro",
                    heading=f"{section.heading} intro",
                    start_line=intro_start,
                    end_line=intro_end,
                    normative_statement_count=_normative_count_for_line_range(lines, intro_start, intro_end),
                )
            )
        direct_trailing = _direct_trailing_body(lines=lines, section=section, children=children)
        if direct_trailing:
            start_line, end_line = direct_trailing
            raise ValueError(
                f"non-leaf section {section.id} has trailing direct body content after child sections "
                f"at lines {start_line}-{end_line}"
            )
    return units


def render_decomposition_plan_markdown(packet: dict) -> str:
    lines = [
        "# Decomposition Plan",
        "",
        f"- Source spec: `{packet['source_spec_path']}`",
        f"- Source hash: `{packet['source_spec_hash']}`",
        f"- Planning mode: `{packet['planning_mode']}`",
        f"- Authority topology: `{packet['authority_topology']}`",
        f"- Target specs: {len(packet['target_specs'])}",
        "",
        "## Coverage",
        "",
        f"- Extractable units: {packet['coverage']['extractable_unit_count']}",
        f"- Assigned extractable units: {packet['coverage']['assigned_extractable_unit_count']}",
        f"- Unassigned extractable units: {len(packet['coverage']['unassigned_extractable_unit_ids'])}",
        f"- Retired extractable units: {len(packet['coverage']['retired_extractable_unit_ids'])}",
        f"- Duplicated extractable units: {len(packet['coverage']['duplicated_extractable_unit_ids'])}",
        "",
        "## Target Specs",
        "",
    ]
    for target in packet["target_specs"]:
        lines.extend(
            [
                f"### {target['target_spec_id']}",
                "",
                f"- Path: `{target['target_spec_path']}`",
                f"- Role: `{target['target_spec_role']}`",
                f"- Owned authority surfaces: {', '.join(target['owned_authority_surfaces']) or 'none'}",
                f"- Extractable units: {len(target['source_units'])}",
                f"- Normative statements: {target['normative_statement_count']}",
                "",
            ]
        )
        for line_range in target["source_line_ranges"]:
            lines.append(
                f"  - `{line_range['unit_id']}` lines {line_range['start_line']}-{line_range['end_line']}: {line_range['heading']}"
            )
        lines.append("")
    if packet["coverage"]["unassigned_extractable_unit_ids"]:
        lines.extend(["## Unassigned Extractable Units", ""])
        for unit_id in packet["coverage"]["unassigned_extractable_unit_ids"]:
            lines.append(f"- `{unit_id}`")
        lines.append("")
    if packet["coverage"]["duplicated_extractable_unit_ids"]:
        lines.extend(["## Duplicated Extractable Units", ""])
        for unit_id in packet["coverage"]["duplicated_extractable_unit_ids"]:
            lines.append(f"- `{unit_id}`")
        lines.append("")
    lines.extend(
        [
            "## Operator Approval",
            "",
            f"- Approved: {str(packet['operator_approval']['approved']).lower()}",
            f"- Approved plan hash: `{packet['operator_approval']['approved_plan_hash'] or 'null'}`",
            "",
        ]
    )
    return "\n".join(lines)


def _plan_packet(
    *,
    source_spec_path: Path,
    source: str,
    sections: list[SourceSection],
    units: list[ExtractableUnit],
    plan_map: dict | None,
    authority_topology: str | None,
) -> dict:
    topology = authority_topology or (plan_map or {}).get("authority_topology") or "no_split"
    if topology not in AUTHORITY_TOPOLOGIES:
        raise ValueError(f"invalid authority_topology: {topology}")
    planning_mode = (plan_map or {}).get("planning_mode") or ("proposed_split" if plan_map else "inventory_only")
    if planning_mode not in PLANNING_MODES:
        raise ValueError(f"invalid planning_mode: {planning_mode}")
    source_lines = source.splitlines()
    if plan_map and plan_map.get("source_spec_hash") not in {None, draft_hash(source)}:
        raise ValueError("decomposition map source_spec_hash does not match source spec")
    targets = _targets_from_map(plan_map, sections, units, source_lines) if plan_map else [_inventory_target(source_spec_path, units, source_lines)]
    assigned = _assigned_unit_ids(targets)
    unit_ids = {unit.id for unit in units}
    retired = list((plan_map or {}).get("retired_extractable_unit_ids", []))
    duplicated = sorted(unit_id for unit_id in unit_ids if assigned.count(unit_id) > 1)
    unassigned = [unit.id for unit in units if unit.id not in assigned and unit.id not in retired]
    packet = {
        "schema_version": "1.0",
        "source_spec_path": str(source_spec_path),
        "source_spec_hash": draft_hash(source),
        "planning_mode": planning_mode,
        "authority_topology": topology,
        "extractable_units": [_unit_packet(unit) for unit in units],
        "target_specs": targets,
        "coverage": {
            "source_section_count": sum(1 for section in sections if section.level > 1),
            "extractable_unit_count": len(units),
            "assigned_source_section_count": len({unit_id for unit_id in assigned if unit_id in unit_ids}),
            "assigned_extractable_unit_count": len({unit_id for unit_id in assigned if unit_id in unit_ids}),
            "unassigned_source_section_ids": unassigned,
            "unassigned_extractable_unit_ids": unassigned,
            "retired_source_section_ids": retired,
            "retired_extractable_unit_ids": retired,
            "duplicated_source_section_ids": duplicated,
            "duplicated_extractable_unit_ids": duplicated,
        },
        "operator_approval": _operator_approval(plan_map),
    }
    if packet["operator_approval"]["approved"] and packet["operator_approval"]["approved_plan_hash"] is None:
        packet["operator_approval"]["approved_plan_hash"] = sha256_text(
            json.dumps({**packet, "operator_approval": {**packet["operator_approval"], "approved_plan_hash": None}}, sort_keys=True)
        )
    return packet


def _inventory_target(source_spec_path: Path, units: list[ExtractableUnit], source_lines: list[str]) -> dict:
    source_ranges = [_line_range(unit) for unit in units]
    return {
        "target_spec_id": "source_spec",
        "target_spec_path": str(source_spec_path),
        "target_spec_role": "peer_spec",
        "owned_authority_surfaces": ["source_spec"],
        "source_section_ids": sorted({unit.section_id for unit in units}),
        "source_units": [_unit_ref(unit) for unit in units],
        "source_line_ranges": source_ranges,
        "normative_statement_count": _normative_count_for_units(units, source_lines),
    }


def _targets_from_map(
    plan_map: dict,
    sections: list[SourceSection],
    units: list[ExtractableUnit],
    source_lines: list[str],
) -> list[dict]:
    sections_by_id = {section.id: section for section in sections}
    units_by_id = {unit.id: unit for unit in units}
    container_section_ids = _container_section_ids(sections)
    targets = []
    if not plan_map.get("target_specs"):
        raise ValueError("decomposition map target_specs must not be empty")
    for target in plan_map.get("target_specs", []):
        role = target.get("target_spec_role")
        if role not in TARGET_SPEC_ROLES:
            raise ValueError(f"invalid target_spec_role: {role}")
        source_units = _source_unit_refs(target)
        resolved_units: list[ExtractableUnit] = []
        for unit_ref in source_units:
            section_id = unit_ref["section_id"]
            scope = unit_ref["scope"]
            if section_id not in sections_by_id:
                raise ValueError(f"unknown source section_id: {section_id}")
            if scope == "section" and section_id in container_section_ids:
                raise ValueError(
                    f"section {section_id} has child sections; assign leaf units explicitly or use scope=intro"
                )
            unit_id = f"{section_id}::__intro__" if scope == "intro" else section_id
            if unit_id not in units_by_id:
                raise ValueError(f"unknown extractable unit: section_id={section_id} scope={scope}")
            resolved_units.append(units_by_id[unit_id])
        targets.append(
            {
                "target_spec_id": target["target_spec_id"],
                "target_spec_path": target["target_spec_path"],
                "target_spec_role": role,
                "owned_authority_surfaces": list(target.get("owned_authority_surfaces", [])),
                "source_section_ids": sorted({unit.section_id for unit in resolved_units}),
                "source_units": [_unit_ref(unit) for unit in resolved_units],
                "source_line_ranges": [_line_range(unit) for unit in resolved_units],
                "normative_statement_count": _normative_count_for_units(resolved_units, source_lines),
            }
        )
    return targets


def _read_map(map_path: Path) -> dict:
    with map_path.open(encoding="utf-8") as artifact_file:
        packet = json.load(artifact_file)
    if not isinstance(packet, dict):
        raise ValueError("decomposition map must be a JSON object")
    return packet


def _line_range(unit: ExtractableUnit) -> dict:
    return {
        "unit_id": unit.id,
        "section_id": unit.section_id,
        "scope": unit.scope,
        "heading": unit.heading,
        "start_line": unit.start_line,
        "end_line": unit.end_line,
    }


def _assigned_unit_ids(targets: list[dict]) -> list[str]:
    assigned: list[str] = []
    for target in targets:
        assigned.extend(unit["unit_id"] for unit in target["source_units"])
    return assigned


def _normative_count_for_units(units: list[ExtractableUnit], source_lines: list[str]) -> int:
    text = "\n".join(
        line
        for start_line, end_line in _merge_ranges((unit.start_line, unit.end_line) for unit in units)
        for line in source_lines[start_line - 1 : end_line]
    )
    return len(NORMATIVE_PATTERN.findall(text))


def _merge_ranges(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start_line, end_line in sorted(ranges):
        if not merged or start_line > merged[-1][1] + 1:
            merged.append((start_line, end_line))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end_line))
    return merged


def _operator_approval(plan_map: dict | None) -> dict[str, Any]:
    approval = (plan_map or {}).get("operator_approval", {})
    return {
        "approved": bool(approval.get("approved", False)),
        "approved_by": approval.get("approved_by"),
        "approved_at": approval.get("approved_at"),
        "approved_plan_hash": approval.get("approved_plan_hash"),
    }


def _children_by_parent(sections: list[SourceSection]) -> dict[str, list[SourceSection]]:
    children: dict[str, list[SourceSection]] = {section.id: [] for section in sections}
    stack: list[SourceSection] = []
    for section in sections:
        while stack and stack[-1].level >= section.level:
            stack.pop()
        if stack:
            children[stack[-1].id].append(section)
        stack.append(section)
    return children


def _container_section_ids(sections: list[SourceSection]) -> set[str]:
    children = _children_by_parent(sections)
    return {section_id for section_id, child_sections in children.items() if child_sections}


def _source_unit_refs(target: dict) -> list[dict]:
    if "source_units" in target:
        refs = target["source_units"]
        if not isinstance(refs, list):
            raise ValueError("source_units must be a list")
        normalized = []
        for ref in refs:
            if not isinstance(ref, dict):
                raise ValueError("source_units entries must be objects")
            scope = ref.get("scope", "section")
            if scope not in {"section", "intro"}:
                raise ValueError(f"invalid source unit scope: {scope}")
            normalized.append({"section_id": ref["section_id"], "scope": scope})
        return normalized
    return [{"section_id": section_id, "scope": "section"} for section_id in target.get("source_section_ids", [])]


def _unit_ref(unit: ExtractableUnit) -> dict:
    return {
        "unit_id": unit.id,
        "section_id": unit.section_id,
        "scope": unit.scope,
    }


def _unit_packet(unit: ExtractableUnit) -> dict:
    return {
        "unit_id": unit.id,
        "section_id": unit.section_id,
        "scope": unit.scope,
        "heading": unit.heading,
        "start_line": unit.start_line,
        "end_line": unit.end_line,
        "normative_statement_count": unit.normative_statement_count,
    }


def _normative_count_for_line_range(lines: list[str], start_line: int, end_line: int) -> int:
    return len(NORMATIVE_PATTERN.findall("\n".join(lines[start_line - 1 : end_line])))


def _is_meaningful_direct_body(lines: list[str]) -> bool:
    content = "\n".join(lines).strip()
    if not content:
        return False
    if NORMATIVE_PATTERN.search(content):
        return True
    if "```" in content or "|" in content:
        return True
    if any(line.lstrip().startswith(("- ", "* ", "1. ")) for line in lines):
        return True
    tokens = re.findall(r"\S+", content)
    return len(tokens) > INTRO_TOKEN_THRESHOLD


def _direct_trailing_body(
    *,
    lines: list[str],
    section: SourceSection,
    children: list[SourceSection],
) -> tuple[int, int] | None:
    if not children:
        return None
    direct_ranges: list[tuple[int, int]] = []
    cursor = section.start_line + 1
    for child in children:
        if cursor <= child.start_line - 1:
            direct_ranges.append((cursor, child.start_line - 1))
        cursor = child.end_line + 1
    if cursor <= section.end_line:
        direct_ranges.append((cursor, section.end_line))
    trailing_ranges = direct_ranges[1:]
    for start_line, end_line in trailing_ranges:
        if _is_meaningful_direct_body(lines[start_line - 1 : end_line]):
            return start_line, end_line
    return None
