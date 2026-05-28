"""Canonical Markdown section indexing."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Section:
    id: str
    heading: str
    level: int
    path: tuple[str, ...]


def section_index(markdown: str) -> list[Section]:
    """Return canonical section IDs derived from Markdown heading paths."""

    lines = markdown.splitlines()
    excluded_root_line = _excluded_root_h1_line(lines)
    sections: list[Section] = []
    path: list[tuple[int, str]] = []
    counters: dict[str, int] = {}
    for line_number, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        heading = match.group(2).strip()
        if line_number == excluded_root_line:
            path = []
            base_id = slug_section_path([heading])
            counters[base_id] = counters.get(base_id, 0) + 1
            section_id = base_id if counters[base_id] == 1 else f"{base_id}#{counters[base_id]}"
            sections.append(Section(id=section_id, heading=heading, level=level, path=(heading,)))
            continue
        path = [item for item in path if item[0] < level]
        path.append((level, heading))
        heading_path = [item[1] for item in path]
        base_id = slug_section_path(heading_path)
        counters[base_id] = counters.get(base_id, 0) + 1
        section_id = base_id if counters[base_id] == 1 else f"{base_id}#{counters[base_id]}"
        sections.append(Section(id=section_id, heading=heading, level=level, path=tuple(heading_path)))
    return sections


def slug_section_path(path: list[str] | tuple[str, ...]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", " ".join(path).lower()).strip("-")
    return slug or "section"


def _excluded_root_h1_line(lines: list[str]) -> int | None:
    heading_lines: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+.+?\s*$", line)
        if match:
            heading_lines.append((index, len(match.group(1))))
    if len(heading_lines) < 2:
        return None
    first_index, first_level = heading_lines[0]
    if first_level != 1:
        return None
    return first_index
