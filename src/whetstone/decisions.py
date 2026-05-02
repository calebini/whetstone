"""Decision point detection and register rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import re
from typing import Any

from whetstone.config import DecisionPointConfig
from whetstone.contracts import validate_artifact
from whetstone.hashing import draft_hash, sha256_text


NORMATIVE_WORDS = ("MUST NOT", "MUST", "SHOULD NOT", "SHOULD", "MAY")
AUTHORITY_RE = re.compile(r"\b(authority|authoritative|arbiter|immutable|read-only|preserved|boundary)\b", re.I)
SCOPE_RE = re.compile(r"\b(scope|adapter|orchestrator|foreman|phase|role|component)\b", re.I)
ERROR_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+){2,}\b")


@dataclass(frozen=True)
class DecisionContext:
    round_number: int
    profile: str
    source_feedback_ids: list[str]
    requires_human_decision: bool
    mode: str


def detect_decision_points(
    *,
    draft_before: str,
    draft_after: str,
    round_number: int,
    profile: str,
    reviewer_feedback: dict[str, Any],
    editor_summary: dict[str, Any],
    config: DecisionPointConfig,
) -> dict[str, Any]:
    source_feedback_ids = list(editor_summary.get("accepted_feedback_ids", [])) + list(
        editor_summary.get("modified_feedback_ids", [])
    )
    requires_human = _requires_human_decision(reviewer_feedback, source_feedback_ids, config)
    context = DecisionContext(
        round_number=round_number,
        profile=profile,
        source_feedback_ids=source_feedback_ids,
        requires_human_decision=requires_human,
        mode=config.mode,
    )
    points: list[dict[str, Any]] = []
    if config.enabled:
        points.extend(_detect_added_line_points(draft_before, draft_after, context, config))
    packet = {
        "round_number": round_number,
        "draft_hash": draft_hash(draft_after),
        "decision_points": _dedupe(points),
    }
    validate_artifact(packet, "decision_points")
    return packet


def scan_decision_points(
    *,
    draft_before: str,
    draft_after: str,
    mode: str = "end_of_cycle",
    profile: str = "decision_scan",
) -> dict[str, Any]:
    """Detect decision points for an ad hoc before/after draft pair."""
    config = DecisionPointConfig(
        enabled=True,
        mode=mode,
        severities=("blocker", "major"),
        trigger_on_requirement_strength_change=True,
        trigger_on_authority_boundary_change=True,
        trigger_on_scope_change=True,
        trigger_on_new_enum_or_error_code=True,
    )
    return detect_decision_points(
        draft_before=draft_before,
        draft_after=draft_after,
        round_number=1,
        profile=profile,
        reviewer_feedback={"feedback": [{"feedback_id": "decision-scan", "normalized_severity": "major"}]},
        editor_summary={"accepted_feedback_ids": ["decision-scan"], "modified_feedback_ids": []},
        config=config,
    )


def write_decision_scan_outputs(
    *,
    output_dir: Path,
    packet: dict[str, Any],
    mode: str,
    terminal_state: str = "DECISION_SCAN_COMPLETE",
) -> dict[str, Path]:
    """Write decision-scan artifacts without requiring a round directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    decision_points_path = output_dir / "decision_points.json"
    decision_points_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    register = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "terminal_state": terminal_state,
        "decision_points": packet["decision_points"],
        "unresolved_human_decision_count": sum(
            1 for point in packet["decision_points"] if point["requires_human_decision"]
        ),
    }
    validate_artifact(register, "decision_register")
    register_path = output_dir / "decision_register.json"
    register_path.write_text(json.dumps(register, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path = output_dir / "decision_register.md"
    markdown_path.write_text(render_decision_register_markdown(register), encoding="utf-8")
    return {
        "decision_points": decision_points_path,
        "decision_register": register_path,
        "decision_register_markdown": markdown_path,
    }


def write_decision_register(
    *,
    rounds_dir: Path,
    mode: str,
    terminal_state: str,
) -> Path | None:
    points = collect_decision_points(rounds_dir)
    if not points:
        return None
    packet = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "terminal_state": terminal_state,
        "decision_points": points,
        "unresolved_human_decision_count": sum(1 for point in points if point["requires_human_decision"]),
    }
    validate_artifact(packet, "decision_register")
    rounds_dir.mkdir(parents=True, exist_ok=True)
    output = rounds_dir / "decision_register.json"
    output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (rounds_dir / "decision_register.md").write_text(render_decision_register_markdown(packet), encoding="utf-8")
    return output


def write_decision_intervention_request(
    *,
    rounds_dir: Path,
    round_number: int,
    profile: str,
    draft_hash_value: str,
    decision_points: list[dict[str, Any]],
) -> Path:
    packet = {
        "terminal_state": "PAUSED_DECISION",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round_number": round_number,
        "profile": profile,
        "draft_hash": draft_hash_value,
        "decision_points": decision_points,
        "recommendation": "choose_option",
    }
    validate_artifact(packet, "decision_intervention_request")
    rounds_dir.mkdir(parents=True, exist_ok=True)
    output = rounds_dir / "decision_intervention_request.json"
    output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def collect_decision_points(rounds_dir: Path) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for path in sorted(rounds_dir.glob("round-*/decision_points.json")):
        packet = json.loads(path.read_text(encoding="utf-8"))
        points.extend(packet.get("decision_points", []))
    return _dedupe(points)


def render_decision_register_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Decision Register",
        "",
        f"- mode: `{packet['mode']}`",
        f"- terminal_state: `{packet['terminal_state']}`",
        f"- unresolved_human_decision_count: `{packet['unresolved_human_decision_count']}`",
        "",
    ]
    for point in packet["decision_points"]:
        lines.extend(
            [
                f"## {point['decision_id']}",
                "",
                f"- type: `{point['decision_type']}`",
                f"- triggers: {', '.join(f'`{trigger}`' for trigger in point.get('trigger_types', []))}",
                f"- round: `{point['round_number']}`",
                f"- profile: `{point['profile']}`",
                f"- action: `{point['orchestrator_action']}`",
                f"- requires_human_decision: `{str(point['requires_human_decision']).lower()}`",
                f"- affected_sections: {', '.join(point['affected_sections'])}",
                "",
                point["question"],
                "",
                "Evidence:",
                *[f"- {line}" for line in point.get("evidence_lines", [])],
                "",
                f"Risk if wrong: {point['risk_if_wrong']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _detect_added_line_points(
    draft_before: str,
    draft_after: str,
    context: DecisionContext,
    config: DecisionPointConfig,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    after_sections = _line_sections(draft_after)
    after_line_number = 0
    for line in difflib.ndiff(draft_before.splitlines(), draft_after.splitlines()):
        marker = line[:2]
        text = line[2:]
        if marker == "  ":
            after_line_number += 1
            continue
        if marker != "+ ":
            continue
        after_line_number += 1
        section = after_sections.get(after_line_number, "(root)")
        trigger_types = _trigger_types(text, config)
        if trigger_types:
            points.append(_point(context, trigger_types, section, text))
    return points


def _trigger_types(text: str, config: DecisionPointConfig) -> list[str]:
    trigger_types: list[str] = []
    if config.trigger_on_requirement_strength_change and _contains_normative(text):
        trigger_types.append("tighten_requirement" if _contains_strong_normative(text) else "relax_requirement")
    if config.trigger_on_new_enum_or_error_code and ERROR_CODE_RE.search(text):
        trigger_types.append("add_operational_requirement")
    if config.trigger_on_authority_boundary_change and AUTHORITY_RE.search(text):
        trigger_types.append("choose_policy")
    if config.trigger_on_scope_change and SCOPE_RE.search(text):
        trigger_types.append("scope_change")
    if "first-write-wins" in text.lower():
        trigger_types.append("choose_policy")
    return _dedupe_strings(trigger_types)


def _point(context: DecisionContext, trigger_types: list[str], section: str, evidence_line: str) -> dict[str, Any]:
    decision_type = _primary_decision_type(trigger_types)
    question = _question(trigger_types, section, [evidence_line])
    fingerprint = _decision_fingerprint(decision_type, [section], question)
    action = "record_only"
    if context.requires_human_decision:
        action = "pause_for_input" if context.mode == "intervention" else "present_at_end"
    return {
        "decision_id": f"dec_{fingerprint[:16]}",
        "round_number": context.round_number,
        "profile": context.profile,
        "source_feedback_ids": context.source_feedback_ids,
        "affected_sections": [section],
        "decision_type": decision_type,
        "trigger_types": trigger_types,
        "evidence_lines": [evidence_line.strip()],
        "question": question,
        "options_considered": [
            {
                "option_id": "selected",
                "label": "Keep editor change",
                "description": evidence_line.strip() or "Keep the revised draft behavior.",
            },
            {
                "option_id": "revisit",
                "label": "Revisit decision",
                "description": "Require human review before treating this choice as settled.",
            },
        ],
        "editor_selected_option_id": "selected",
        "editor_rationale": "Detected from the editor-produced draft diff.",
        "risk_if_wrong": "The spec may silently encode a policy, scope, authority, or operational choice the owner did not intend.",
        "requires_human_decision": context.requires_human_decision,
        "orchestrator_action": action,
    }


def _decision_fingerprint(decision_type: str, affected_sections: list[str], question: str) -> str:
    payload = "\n".join([_normalize(decision_type), "\n".join(_normalize(section) for section in affected_sections), _normalize(question)])
    return sha256_text(payload)


def _question(trigger_types: list[str], section: str, evidence_lines: list[str]) -> str:
    compact = re.sub(r"\s+", " ", evidence_lines[0].strip()).strip("- ")
    trigger_text = ", ".join(trigger.replace("_", " ") for trigger in trigger_types)
    return f"Should `{section}` adopt this change ({trigger_text}): {compact}"


def _primary_decision_type(trigger_types: list[str]) -> str:
    priority = [
        "resolve_conflict",
        "choose_policy",
        "scope_change",
        "tighten_requirement",
        "relax_requirement",
        "add_operational_requirement",
        "define_default",
    ]
    for decision_type in priority:
        if decision_type in trigger_types:
            return decision_type
    return trigger_types[0]


def _requires_human_decision(
    reviewer_feedback: dict[str, Any],
    source_feedback_ids: list[str],
    config: DecisionPointConfig,
) -> bool:
    if not source_feedback_ids:
        return False
    severities = set(config.severities)
    for item in reviewer_feedback.get("feedback", []):
        if item.get("feedback_id") in source_feedback_ids and item.get("normalized_severity") in severities:
            return True
    return False


def _line_sections(markdown: str) -> dict[int, str]:
    sections: dict[int, str] = {}
    current = "(root)"
    for index, line in enumerate(markdown.splitlines(), start=1):
        if line.startswith("#"):
            current = line.strip("# ").strip() or current
        sections[index] = current
    return sections


def _contains_normative(text: str) -> bool:
    upper = text.upper()
    return any(word in upper for word in NORMATIVE_WORDS)


def _contains_strong_normative(text: str) -> bool:
    upper = text.upper()
    return "MUST" in upper or "MUST NOT" in upper


def _dedupe(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for point in points:
        identifier = point["decision_id"]
        if identifier in seen:
            continue
        seen.add(identifier)
        deduped.append(point)
    return deduped


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()
