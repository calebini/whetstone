"""Exact-byte ATX section spans and the seed subset of stable section identity.

This module never changes draft bytes or guesses identity transfer after editing.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from whetstone.preservation_inventory import build_inventory
from whetstone.sections import slug_section_path
from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_identity import seed_section_id


@dataclass(frozen=True)
class SectionSpan:
    heading: str
    level: int
    start: int
    heading_end: int
    direct_end: int
    end: int
    parent: int | None
    canonical_id: str


def section_spans(raw: bytes) -> list[SectionSpan]:
    """Reuse the qualified exact-line scanner, with separate vNext identities.

    Section hashes cover complete subtrees; direct bodies exclude headings and
    descendants. Preamble remains bound by the full draft hash. Display anchors
    follow the existing root-title exclusion and duplicate suffix convention.
    """
    inventory = build_inventory(raw, path="draft.md")
    headings = [unit for unit in inventory["units"] if unit["kind"] == "heading"]
    result = []
    stack: list[int] = []
    counts: dict[str, int] = {}
    for ordinal, unit in enumerate(headings):
        line = raw[unit["byte_start"]:unit["byte_end"]].decode("utf-8").rstrip("\r\n")
        match = re.match(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|$)", line)
        assert match is not None
        level = len(match[1])
        title = re.sub(r"(?:^|[ \t]+)#+[ \t]*$", "", match[2] or "").strip(" \t")
        while stack and result[stack[-1]].level >= level:
            stack.pop()
        parent = stack[-1] if stack else None
        display_parents = stack
        if len(headings) > 1 and result and result[0].level == 1:
            display_parents = [index for index in stack if index != 0]
        base = slug_section_path([result[index].heading for index in display_parents] + [title])
        counts[base] = counts.get(base, 0) + 1
        canonical = base if counts[base] == 1 else f"{base}#{counts[base]}"
        direct_end = headings[ordinal + 1]["byte_start"] if ordinal + 1 < len(headings) else len(raw)
        end = len(raw)
        for later in headings[ordinal + 1:]:
            later_line = raw[later["byte_start"]:later["byte_end"]].decode("utf-8")
            later_level = len(re.match(r"^ {0,3}(#{1,6})", later_line)[1])
            if later_level <= level:
                end = later["byte_start"]
                break
        result.append(SectionSpan(title, level, unit["byte_start"], unit["byte_end"],
                                  direct_end, end, parent, canonical))
        stack.append(ordinal)
    return result


def seed_section_map(raw: bytes, job: dict, binding_id: str) -> dict:
    digest = sha256_bytes(raw)
    spans = section_spans(raw)
    identities = [seed_section_id(job["job_id"], digest, binding_id, index + 1)
                  for index in range(len(spans))]
    return {
        "schema_version": "section-identity-map-v1",
        "job_id": job["job_id"],
        "draft_hash": digest,
        "parser_contract_version": job["parser_contract_version"],
        "sections": [
            {
                "stable_section_id": identities[index],
                "canonical_section_id": span.canonical_id,
                "parent_stable_section_id": identities[span.parent] if span.parent is not None else None,
                "heading_level": span.level,
                "heading_text": span.heading,
                "preorder_ordinal": index + 1,
                "section_hash": sha256_bytes(raw[span.start:span.end]),
                "direct_body_hash": sha256_bytes(raw[span.heading_end:span.direct_end]),
                "status": "active",
                "created_by_operation_id": None,
                "previous_stable_section_id": None,
            }
            for index, span in enumerate(spans)
        ],
    }
