"""Spec decomposition planning primitives."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any, Iterable

from whetstone.hashing import draft_hash, sha256_text
from whetstone.sections import slug_section_path


AUTHORITY_TOPOLOGIES = {"coordinated_family", "peer_family", "parent_child", "appendix_extraction", "no_split"}
TARGET_SPEC_ROLES = {"coordinating_spec", "leaf_spec", "peer_spec", "appendix_spec"}
PLANNING_MODES = {"inventory_only", "proposed_split", "approved_split"}
NORMATIVE_PATTERN = re.compile(r"\b(MUST NOT|SHOULD NOT|MUST|SHOULD|MAY|REQUIRED|OPTIONAL)\b")


@dataclass(frozen=True)
class SourceSection:
    id: str
    heading: str
    level: int
    path: tuple[str, ...]
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
    plan_map = _read_map(map_path) if map_path else None
    packet = _plan_packet(
        source_spec_path=source_spec_path,
        source=source,
        sections=sections,
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
        f"- Source sections: {packet['coverage']['source_section_count']}",
        f"- Assigned source sections: {packet['coverage']['assigned_source_section_count']}",
        f"- Unassigned source sections: {len(packet['coverage']['unassigned_source_section_ids'])}",
        f"- Retired source sections: {len(packet['coverage']['retired_source_section_ids'])}",
        f"- Duplicated source sections: {len(packet['coverage']['duplicated_source_section_ids'])}",
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
                f"- Source sections: {len(target['source_section_ids'])}",
                f"- Normative statements: {target['normative_statement_count']}",
                "",
            ]
        )
        for line_range in target["source_line_ranges"]:
            lines.append(
                f"  - `{line_range['section_id']}` lines {line_range['start_line']}-{line_range['end_line']}: {line_range['heading']}"
            )
        lines.append("")
    if packet["coverage"]["unassigned_source_section_ids"]:
        lines.extend(["## Unassigned Source Sections", ""])
        for section_id in packet["coverage"]["unassigned_source_section_ids"]:
            lines.append(f"- `{section_id}`")
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
    targets = _targets_from_map(plan_map, sections, source_lines) if plan_map else [_inventory_target(source_spec_path, sections, source_lines)]
    assigned = _assigned_source_section_ids(targets)
    coverage_section_ids = {section.id for section in sections if section.level > 1}
    retired = list((plan_map or {}).get("retired_source_section_ids", []))
    duplicated = sorted(
        section_id
        for section_id in assigned
        if section_id in coverage_section_ids and sum(section_id in target["source_section_ids"] for target in targets) > 1
    )
    unassigned = [
        section.id
        for section in sections
        if section.id in coverage_section_ids and section.id not in assigned and section.id not in retired
    ]
    packet = {
        "schema_version": "1.0",
        "source_spec_path": str(source_spec_path),
        "source_spec_hash": draft_hash(source),
        "planning_mode": planning_mode,
        "authority_topology": topology,
        "target_specs": targets,
        "coverage": {
            "source_section_count": len(coverage_section_ids),
            "assigned_source_section_count": len({section_id for section_id in assigned if section_id in coverage_section_ids}),
            "unassigned_source_section_ids": unassigned,
            "retired_source_section_ids": retired,
            "duplicated_source_section_ids": duplicated,
        },
        "operator_approval": _operator_approval(plan_map),
    }
    if packet["operator_approval"]["approved"] and packet["operator_approval"]["approved_plan_hash"] is None:
        packet["operator_approval"]["approved_plan_hash"] = sha256_text(
            json.dumps({**packet, "operator_approval": {**packet["operator_approval"], "approved_plan_hash": None}}, sort_keys=True)
        )
    return packet


def _inventory_target(source_spec_path: Path, sections: list[SourceSection], source_lines: list[str]) -> dict:
    source_ranges = [_line_range(section) for section in sections]
    return {
        "target_spec_id": "source_spec",
        "target_spec_path": str(source_spec_path),
        "target_spec_role": "peer_spec",
        "owned_authority_surfaces": ["source_spec"],
        "source_section_ids": [section.id for section in sections],
        "source_line_ranges": source_ranges,
        "normative_statement_count": _normative_count_for_sections(sections, source_lines),
    }


def _targets_from_map(plan_map: dict, sections: list[SourceSection], source_lines: list[str]) -> list[dict]:
    by_id = {section.id: section for section in sections}
    targets = []
    if not plan_map.get("target_specs"):
        raise ValueError("decomposition map target_specs must not be empty")
    for target in plan_map.get("target_specs", []):
        role = target.get("target_spec_role")
        if role not in TARGET_SPEC_ROLES:
            raise ValueError(f"invalid target_spec_role: {role}")
        section_ids = list(target.get("source_section_ids", []))
        unknown = [section_id for section_id in section_ids if section_id not in by_id]
        if unknown:
            raise ValueError(f"unknown source_section_ids: {', '.join(unknown)}")
        source_sections = [by_id[section_id] for section_id in section_ids]
        targets.append(
            {
                "target_spec_id": target["target_spec_id"],
                "target_spec_path": target["target_spec_path"],
                "target_spec_role": role,
                "owned_authority_surfaces": list(target.get("owned_authority_surfaces", [])),
                "source_section_ids": section_ids,
                "source_line_ranges": [_line_range(section) for section in source_sections],
                "normative_statement_count": _normative_count_for_sections(source_sections, source_lines),
            }
        )
    return targets


def _read_map(map_path: Path) -> dict:
    with map_path.open(encoding="utf-8") as artifact_file:
        packet = json.load(artifact_file)
    if not isinstance(packet, dict):
        raise ValueError("decomposition map must be a JSON object")
    return packet


def _line_range(section: SourceSection) -> dict:
    return {
        "section_id": section.id,
        "heading": section.heading,
        "start_line": section.start_line,
        "end_line": section.end_line,
    }


def _assigned_source_section_ids(targets: list[dict]) -> list[str]:
    assigned: list[str] = []
    for target in targets:
        assigned.extend(target["source_section_ids"])
    return assigned


def _normative_count_for_sections(sections: list[SourceSection], source_lines: list[str]) -> int:
    merged_ranges = _merge_ranges((section.start_line, section.end_line) for section in sections)
    text = "\n".join(
        line
        for start_line, end_line in merged_ranges
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
