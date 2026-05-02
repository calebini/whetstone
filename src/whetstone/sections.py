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

    sections: list[Section] = []
    path: list[str] = []
    counters: dict[str, int] = {}
    for line in markdown.splitlines():
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
        sections.append(Section(id=section_id, heading=heading, level=level, path=tuple(path)))
    return sections


def slug_section_path(path: list[str] | tuple[str, ...]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", " ".join(path).lower()).strip("-")
    return slug or "section"
