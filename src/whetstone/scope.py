"""Scope contract loading and first-contact intake helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from whetstone.contracts import validate_artifact


SCOPE_CONTRACT_SCHEMA_VERSION = "scope-contract-v1"


@dataclass(frozen=True)
class LoadedScopeContract:
    path: Path
    packet: dict[str, Any]
    content_hash: str


def read_scope_contract(path: Path) -> LoadedScopeContract | None:
    """Read and validate an existing scope contract."""

    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    packet = json.loads(text)
    validate_scope_contract(packet)
    return LoadedScopeContract(path=path, packet=packet, content_hash=_sha256_json(packet))


def validate_scope_contract(packet: dict[str, Any]) -> None:
    validate_artifact(packet, "scope_contract")


def scope_contract_summary(contract: LoadedScopeContract | None, *, root: Path) -> dict[str, Any] | None:
    if contract is None:
        return None
    return {
        "path": _relative_path(contract.path, root),
        "content_hash": contract.content_hash,
        "status": contract.packet.get("status"),
        "readiness_target": contract.packet.get("readiness_target"),
        "approved": bool((contract.packet.get("approval") or {}).get("approved")),
    }


def render_mvp_scope_notes_template() -> str:
    return """# Whetstone MVP Scope Notes

Use this file to tell Whetstone what the first useful build is allowed to include.
Keep answers short and concrete. Delete examples that do not apply.

## Core Outcome

Make <the core job flow> buildable for an MVP without guessing.

## Primary Actor Or Consumer

<engineer, service, adapter, operator, caller, or job>

## Core Flows

- must: <first useful flow>
- should: <important supporting flow>
- could: <nice-to-have flow>

## In Scope

- <surface>: <required depth: mention | define | required_fields | full_schema | exhaustive>
- validation/error behavior: required_fields
- report behavior: required_fields

## Deferred / Out Of Scope

- diagnostic modes
- exhaustive error-code registry
- retry/timeout/resume behavior unless required for MVP correctness
- long-term operations/runbook

## Expansion Rules

- Defer reviewer requests for exhaustive validation matrices unless required for the core flow.
- Defer reviewer requests for complete operational runbooks unless required for MVP correctness.
- Allow reviewer pressure on required fields, authority boundaries, failure categories, and acceptance criteria.

## Good Enough

The MVP is good enough when the core flow, required inputs/outputs, artifacts, state changes, obvious failure categories, and acceptance criteria are explicit enough to build.
"""


def scope_contract_from_notes(notes: str, *, source_path: str | None = None, approved: bool = False) -> dict[str, Any]:
    """Create a conservative scope contract from human scope notes.

    This is intentionally deterministic v1 canonicalization. A future LLM intake
    adapter can produce the same schema, but the artifact shape stays stable.
    """

    sections = _markdown_sections(notes)
    core_outcome = _section_text(sections, "core outcome") or "MVP core outcome was not specified in notes."
    actor = _section_text(sections, "primary actor or consumer") or None
    core_flows = _flows_from_lines(_section_lines(sections, "core flows"))
    in_scope = _scope_surfaces(_section_lines(sections, "in scope"), status="in_scope")
    deferred = _scope_surfaces(_section_lines(sections, "deferred / out of scope"), status="deferred")
    expansion_rules = _rules_from_lines(_section_lines(sections, "expansion rules"))
    good_enough = _section_text(sections, "good enough") or (
        "The run is good enough when the core outcome is buildable without scope expansion."
    )

    if not core_flows:
        core_flows = [{"id": "core-flow-1", "description": core_outcome, "priority": "must"}]
    if not in_scope:
        in_scope = [
            {
                "id": "core-contract",
                "name": "Core MVP contract",
                "status": "in_scope",
                "required_depth": "required_fields",
                "rationale": "Default MVP scope from notes.",
            }
        ]
    if not deferred:
        deferred = [
            {
                "id": "exhaustive-edge-cases",
                "name": "Exhaustive edge-case enumeration",
                "status": "deferred",
                "required_depth": "mention",
                "rationale": "Default MVP deferral.",
            }
        ]
    if not expansion_rules:
        expansion_rules = [
            {
                "id": "defer-exhaustive-expansion",
                "trigger": "Reviewer asks for exhaustive detail beyond the named MVP surface.",
                "action": "defer",
                "decline_reason": "out_of_scope",
                "rationale": "MVP scope contract limits expansion pressure.",
            }
        ]

    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": SCOPE_CONTRACT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "approved" if approved else "draft",
        "readiness_target": "mvp",
        "core_outcome": core_outcome,
        "primary_actor_or_consumer": actor,
        "core_flows": core_flows,
        "scope_surfaces": in_scope + deferred,
        "deferral_rules": expansion_rules,
        "acceptance_floor": {
            "minimum_buildable_result": good_enough,
            "must_answer": [
                "What is the core MVP flow?",
                "What inputs, outputs, artifacts, and obvious failure categories are required?",
            ],
            "may_defer": [
                "Exhaustive error-code registries",
                "Non-core operational runbooks",
                "Post-MVP recovery branches",
            ],
        },
        "review_pressure_limits": {
            "max_depth_default": "required_fields",
            "expansion_policy": "conservative",
        },
        "operator_decisions": [
            {
                "question": "What operator intent did the notes provide?",
                "answer": notes.strip(),
                "rationale": "Preserve original scope notes beside canonical fields.",
            }
        ],
        "source_notes_path": source_path,
        "approval": {
            "approved": approved,
            "approved_by": "operator" if approved else None,
            "approved_at": generated_at if approved else None,
        },
    }


def write_scope_contract(path: Path, packet: dict[str, Any]) -> None:
    validate_scope_contract(packet)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "preamble"
    sections[current] = []
    for line in text.splitlines():
        if line.startswith("## "):
            current = _slug(line[3:].strip())
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _section_text(sections: dict[str, list[str]], name: str) -> str:
    return "\n".join(line.rstrip() for line in sections.get(_slug(name), [])).strip()


def _section_lines(sections: dict[str, list[str]], name: str) -> list[str]:
    output: list[str] = []
    for raw_line in sections.get(_slug(name), []):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        output.append(line)
    return output


def _flows_from_lines(lines: list[str]) -> list[dict[str, str]]:
    flows: list[dict[str, str]] = []
    for index, line in enumerate(lines, start=1):
        priority = "must"
        description = line
        match = re.match(r"^(must|should|could)\s*:\s*(.+)$", line, re.I)
        if match:
            priority = match.group(1).lower()
            description = match.group(2).strip()
        if description:
            flows.append({"id": f"flow-{index}", "description": description, "priority": priority})
    return flows


def _scope_surfaces(lines: list[str], *, status: str) -> list[dict[str, str]]:
    surfaces: list[dict[str, str]] = []
    for index, line in enumerate(lines, start=1):
        name = line
        depth = "mention" if status != "in_scope" else "required_fields"
        if ":" in line:
            name, _, detail = line.partition(":")
            parsed_depth = _parse_depth(detail)
            if parsed_depth:
                depth = parsed_depth
        surfaces.append(
            {
                "id": _stable_id(name, prefix=f"{status}-{index}"),
                "name": name.strip(),
                "status": status,
                "required_depth": depth,
                "rationale": line.strip(),
            }
        )
    return surfaces


def _rules_from_lines(lines: list[str]) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        action = "defer" if "defer" in lowered else "allow_if_core"
        rules.append(
            {
                "id": f"rule-{index}",
                "trigger": line,
                "action": action,
                "decline_reason": "out_of_scope" if action == "defer" else "deferred_to_later_round",
                "rationale": line,
            }
        )
    return rules


def _parse_depth(text: str) -> str | None:
    for depth in ("mention", "define", "required_fields", "full_schema", "exhaustive", "custom"):
        if depth in text.strip().lower().replace(" ", "_"):
            return depth
    return None


def _stable_id(text: str, *, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or prefix


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _sha256_json(packet: dict[str, Any]) -> str:
    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
