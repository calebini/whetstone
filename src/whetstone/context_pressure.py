"""Context pressure observability for Whetstone runs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from math import ceil
from pathlib import Path
from typing import Any, Iterable

from whetstone.config import OrchestratorConfig
from whetstone.contracts import validate_artifact
from whetstone.rubrics import read_rubric_text


SCHEMA_VERSION = "context-pressure-v1"
REPORT_JSON = "context_pressure_report.json"
REPORT_MARKDOWN = "context_pressure_report.md"
TOTAL_WARNING_BYTES = 800_000
COMPONENT_WARNING_BYTES = 300_000
REFERENCE_COUNT_WARNING = 8


def write_context_pressure_report(
    *,
    root: Path | str,
    config: OrchestratorConfig,
    phase: str,
    round_number: int | None = None,
    profile: str | None = None,
) -> dict[str, Path]:
    """Persist an advisory context pressure report for the configured run inputs."""

    root_path = Path(root)
    report = build_context_pressure_report(
        root=root_path,
        config=config,
        phase=phase,
        round_number=round_number,
        profile=profile,
    )
    validate_artifact(report, "context_pressure_report")
    config.rounds_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.rounds_dir / REPORT_JSON
    markdown_path = config.rounds_dir / REPORT_MARKDOWN
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_context_pressure_markdown(report), encoding="utf-8")
    return {
        "context_pressure_report": json_path,
        "context_pressure_report_markdown": markdown_path,
    }


def write_round_context_pressure_report(
    *,
    root: Path | str,
    round_dir: Path,
    phase: str,
    round_number: int,
    profile: str,
    context_files: Iterable[Any],
    reviewer_feedback: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Persist an advisory report for the actual context files used by a round."""

    root_path = Path(root)
    report = build_round_context_pressure_report(
        root=root_path,
        phase=phase,
        round_number=round_number,
        profile=profile,
        context_files=context_files,
        reviewer_feedback=reviewer_feedback,
    )
    validate_artifact(report, "context_pressure_report")
    json_path = round_dir / REPORT_JSON
    markdown_path = round_dir / REPORT_MARKDOWN
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_context_pressure_markdown(report), encoding="utf-8")
    return {
        "context_pressure_report": json_path,
        "context_pressure_report_markdown": markdown_path,
    }


def build_context_pressure_report(
    *,
    root: Path,
    config: OrchestratorConfig,
    phase: str,
    round_number: int | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Build a non-behavioral context pressure report from configured input files."""

    components: list[dict[str, Any]] = []
    components.append(
        _file_component(
            root,
            label="draft",
            kind="mutable_draft",
            role="draft",
            path=config.spec_path,
            required=True,
        )
    )
    components.append(
        _file_component(
            root,
            label="scope_contract",
            kind="scope_contract",
            role="scope_contract",
            path=config.scope_contract.path,
            required=False,
        )
    )
    rubric_text = read_rubric_text(config)
    components.append(_text_component(root, config=config, text=rubric_text))
    for item in config.reference_context_files:
        components.append(
            _file_component(
                root,
                label=item.label,
                kind="reference_context",
                role=item.role,
                path=item.path,
                required=item.required,
            )
        )

    totals = {
        "component_count": len(components),
        "existing_component_count": sum(1 for item in components if item["exists"]),
        "byte_count": sum(item["byte_count"] for item in components),
        "char_count": sum(item["char_count"] for item in components),
        "estimated_tokens": sum(item["estimated_tokens"] for item in components),
        "reference_context_count": len(config.reference_context_files),
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "phase": phase,
        "round_number": round_number if round_number is not None else 0,
        "profile": profile or "",
        "behavior": "observability_only",
        "action_taken": "none",
        "estimate_method": "ceil(char_count / 4); advisory only, not provider tokenizer output",
        "report_scope": "configured_run_inputs",
        "thresholds": {
            "total_warning_bytes": TOTAL_WARNING_BYTES,
            "component_warning_bytes": COMPONENT_WARNING_BYTES,
            "reference_count_warning": REFERENCE_COUNT_WARNING,
        },
        "totals": totals,
        "components": components,
        "referenced_context": {
            "reference_count": 0,
            "references": [],
        },
        "warnings": _warnings(components, totals),
    }
    return report


def build_round_context_pressure_report(
    *,
    root: Path,
    phase: str,
    round_number: int,
    profile: str,
    context_files: Iterable[Any],
    reviewer_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a report from the concrete context files handed to a round prompt."""

    components = [_context_file_component(root, item) for item in context_files]
    totals = {
        "component_count": len(components),
        "existing_component_count": sum(1 for item in components if item["exists"]),
        "byte_count": sum(item["byte_count"] for item in components),
        "char_count": sum(item["char_count"] for item in components),
        "estimated_tokens": sum(item["estimated_tokens"] for item in components),
        "reference_context_count": sum(1 for item in components if item["kind"] == "reference_context"),
    }
    referenced_context = _referenced_context(components, reviewer_feedback or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "phase": phase,
        "round_number": round_number,
        "profile": profile,
        "behavior": "observability_only",
        "action_taken": "none",
        "estimate_method": "ceil(char_count / 4); advisory only, not provider tokenizer output",
        "report_scope": "round_prompt_context",
        "thresholds": {
            "total_warning_bytes": TOTAL_WARNING_BYTES,
            "component_warning_bytes": COMPONENT_WARNING_BYTES,
            "reference_count_warning": REFERENCE_COUNT_WARNING,
        },
        "totals": totals,
        "components": components,
        "referenced_context": referenced_context,
        "warnings": _warnings(components, totals),
    }


def render_context_pressure_markdown(report: dict[str, Any]) -> str:
    """Render a compact operator-facing markdown summary."""

    totals = report["totals"]
    lines = [
        "# Context Pressure Report",
        "",
        f"- behavior: `{report['behavior']}`",
        f"- action_taken: `{report['action_taken']}`",
        f"- report_scope: `{report.get('report_scope', 'unknown')}`",
        f"- phase: `{report['phase']}`",
        f"- round_number: `{report['round_number']}`",
        f"- profile: `{report['profile']}`",
        f"- components: `{totals['existing_component_count']}/{totals['component_count']}` existing",
        f"- bytes: `{totals['byte_count']}`",
        f"- estimated_tokens: `{totals['estimated_tokens']}`",
        "",
        "## Warnings",
        "",
    ]
    warnings = report.get("warnings", [])
    if warnings:
        lines.extend(f"- `{item['severity']}` `{item['code']}`: {item['message']}" for item in warnings)
    else:
        lines.append("- none")
    referenced = report.get("referenced_context") or {}
    references = referenced.get("references") if isinstance(referenced, dict) else []
    lines.extend(["", "## Referenced Context", ""])
    if references:
        for item in references:
            lines.append(
                f"- `{item['label']}`: `{item['mention_count']}` mentions from "
                f"{', '.join(item['source_feedback_ids'])}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Components", ""])
    for item in sorted(report["components"], key=lambda value: value["byte_count"], reverse=True):
        marker = "exists" if item["exists"] else "missing"
        lines.append(
            f"- `{item['label']}` ({item['kind']}, {marker}): "
            f"`{item['byte_count']}` bytes, `{item['estimated_tokens']}` est. tokens, `{item['path']}`"
        )
    return "\n".join(lines) + "\n"


def _context_file_component(root: Path, context_file: Any) -> dict[str, Any]:
    label = _context_attr(context_file, "label")
    path_value = _context_attr(context_file, "path")
    sha256 = _context_attr(context_file, "sha256")
    path = root / path_value
    kind, role = _kind_and_role_from_context_label(label)
    if not path.exists() or not path.is_file():
        return {
            "label": label,
            "kind": kind,
            "role": role,
            "path": path_value,
            "required": True,
            "exists": False,
            "byte_count": 0,
            "char_count": 0,
            "estimated_tokens": 0,
            "sha256": sha256,
            "read_error": "",
        }
    content = path.read_text(encoding="utf-8")
    component = _component_from_text(
        root,
        label=label,
        kind=kind,
        role=role,
        path_display=path_value,
        required=True,
        content=content,
    )
    component["sha256"] = sha256 or component["sha256"]
    return component


def _file_component(
    root: Path,
    *,
    label: str,
    kind: str,
    role: str,
    path: Path,
    required: bool,
) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "label": label,
            "kind": kind,
            "role": role,
            "path": _display_path(root, path),
            "required": required,
            "exists": False,
            "byte_count": 0,
            "char_count": 0,
            "estimated_tokens": 0,
            "sha256": "",
            "read_error": "",
        }
    content = path.read_text(encoding="utf-8")
    return _component_from_text(
        root,
        label=label,
        kind=kind,
        role=role,
        path_display=_display_path(root, path),
        required=required,
        content=content,
    )


def _text_component(root: Path, *, config: OrchestratorConfig, text: str | None) -> dict[str, Any]:
    path_display = (
        _display_path(root, config.convergence.rubric_path)
        if config.convergence.rubric_source == "custom"
        else f"builtin:{config.convergence.rubric_profile}"
    )
    if text is None:
        return {
            "label": "rubric",
            "kind": "rubric",
            "role": "rubric",
            "path": path_display,
            "required": True,
            "exists": False,
            "byte_count": 0,
            "char_count": 0,
            "estimated_tokens": 0,
            "sha256": "",
            "read_error": "rubric text unavailable",
        }
    return _component_from_text(
        root,
        label="rubric",
        kind="rubric",
        role="rubric",
        path_display=path_display,
        required=True,
        content=text,
    )


def _component_from_text(
    root: Path,
    *,
    label: str,
    kind: str,
    role: str,
    path_display: str,
    required: bool,
    content: str,
) -> dict[str, Any]:
    encoded = content.encode("utf-8")
    return {
        "label": label,
        "kind": kind,
        "role": role,
        "path": path_display,
        "required": required,
        "exists": True,
        "byte_count": len(encoded),
        "char_count": len(content),
        "estimated_tokens": _estimated_tokens(len(content)),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "read_error": "",
    }


def _warnings(components: list[dict[str, Any]], totals: dict[str, int]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if totals["byte_count"] >= TOTAL_WARNING_BYTES:
        warnings.append(
            {
                "severity": "warning",
                "code": "large_total_context",
                "message": (
                    f"Configured context totals {totals['byte_count']} bytes "
                    f"({totals['estimated_tokens']} estimated tokens)."
                ),
            }
        )
    if totals["reference_context_count"] > REFERENCE_COUNT_WARNING:
        warnings.append(
            {
                "severity": "info",
                "code": "many_reference_context_files",
                "message": f"{totals['reference_context_count']} reference context files are configured.",
            }
        )
    for item in components:
        if item["required"] and not item["exists"]:
            warnings.append(
                {
                    "severity": "warning",
                    "code": "missing_required_context",
                    "message": f"Required context component {item['label']!r} is missing at {item['path']}.",
                }
            )
        if item["byte_count"] >= COMPONENT_WARNING_BYTES:
            warnings.append(
                {
                    "severity": "warning",
                    "code": "large_context_component",
                    "message": (
                        f"Context component {item['label']!r} is {item['byte_count']} bytes "
                        f"({item['estimated_tokens']} estimated tokens)."
                    ),
                }
            )
    return warnings


def _referenced_context(components: list[dict[str, Any]], reviewer_feedback: dict[str, Any]) -> dict[str, Any]:
    feedback = reviewer_feedback.get("feedback")
    if not isinstance(feedback, list):
        feedback = []
    references: list[dict[str, Any]] = []
    for component in components:
        if component["kind"] != "reference_context":
            continue
        tokens = _reference_tokens(component)
        source_feedback_ids: list[str] = []
        mention_count = 0
        for issue in feedback:
            if not isinstance(issue, dict):
                continue
            issue_text = _issue_text(issue)
            count = sum(issue_text.count(token) for token in tokens if token)
            if count <= 0:
                continue
            mention_count += count
            feedback_id = str(issue.get("feedback_id") or issue.get("issue_id") or "")
            if feedback_id and feedback_id not in source_feedback_ids:
                source_feedback_ids.append(feedback_id)
        if mention_count > 0:
            references.append(
                {
                    "label": component["label"],
                    "path": component["path"],
                    "mention_count": mention_count,
                    "source_feedback_ids": source_feedback_ids,
                }
            )
    return {
        "reference_count": len(references),
        "references": references,
    }


def _reference_tokens(component: dict[str, Any]) -> list[str]:
    path = str(component.get("path") or "")
    basename = Path(path).name
    label = str(component.get("label") or "")
    bare_label = label.split(":", 1)[1] if label.startswith("reference:") else label
    normalized_filename = f"reference_{bare_label}.md"
    tokens = [path, basename, label, bare_label, normalized_filename]
    return sorted({token for token in tokens if token}, key=len, reverse=True)


def _issue_text(issue: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("claim", "evidence", "recommended_change"):
        value = issue.get(key)
        if isinstance(value, str):
            parts.append(value)
    affected = issue.get("affected_sections")
    if isinstance(affected, list):
        parts.extend(str(item) for item in affected)
    return "\n".join(parts)


def _context_attr(context_file: Any, key: str) -> str:
    if isinstance(context_file, dict):
        return str(context_file.get(key) or "")
    return str(getattr(context_file, key, "") or "")


def _kind_and_role_from_context_label(label: str) -> tuple[str, str]:
    if label == "draft_before":
        return "mutable_draft", "draft"
    if label == "scope_contract":
        return "scope_contract", "scope_contract"
    if label == "rubric":
        return "rubric", "rubric"
    if label == "reviewer_feedback":
        return "reviewer_feedback", "reviewer_feedback"
    if label == "contract_surface_report":
        return "contract_surface_report", "contract_surface_report"
    if label == "declaration":
        return "convergence_declaration", "convergence_declaration"
    if label.startswith("reference:"):
        return "reference_context", "reference_context"
    return "round_context", "round_context"


def _estimated_tokens(char_count: int) -> int:
    if char_count <= 0:
        return 0
    return ceil(char_count / 4)


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
