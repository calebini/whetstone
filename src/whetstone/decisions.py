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
    scope_contract: dict[str, Any] | None = None


def detect_decision_points(
    *,
    draft_before: str,
    draft_after: str,
    round_number: int,
    profile: str,
    reviewer_feedback: dict[str, Any],
    editor_summary: dict[str, Any],
    config: DecisionPointConfig,
    scope_contract: dict[str, Any] | None = None,
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
        scope_contract=scope_contract,
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
    scope_contract: dict[str, Any] | None = None,
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
        scope_contract=scope_contract,
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
        "decision_status_counts": _decision_status_counts(packet["decision_points"]),
        "unresolved_human_decision_count": sum(
            1 for point in packet["decision_points"] if point["requires_human_decision"]
        ),
    }
    validate_artifact(register, "decision_register")
    register_path = output_dir / "decision_register.json"
    register_path.write_text(json.dumps(register, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path = output_dir / "decision_register.md"
    markdown_path.write_text(render_decision_register_markdown(register), encoding="utf-8")
    summary_outputs = write_decision_summary_outputs(register_path=register_path)
    return {
        "decision_points": decision_points_path,
        "decision_register": register_path,
        "decision_register_markdown": markdown_path,
        **summary_outputs,
    }


def write_decision_summary_outputs(
    *,
    register_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Write deterministic decision summary artifacts for an existing decision register."""
    register = json.loads(register_path.read_text(encoding="utf-8"))
    validate_artifact(register, "decision_register")
    target_dir = output_dir or register_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_decision_register(register, source_register_path=str(register_path))
    validate_artifact(summary, "decision_summary")
    summary_path = target_dir / "decision_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path = target_dir / "decision_summary.md"
    markdown_path.write_text(render_decision_summary_markdown(summary), encoding="utf-8")
    return {"decision_summary": summary_path, "decision_summary_markdown": markdown_path}


def write_decision_register(
    *,
    rounds_dir: Path,
    mode: str,
    terminal_state: str,
) -> Path | None:
    points = collect_decision_points(rounds_dir)
    packet = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "terminal_state": terminal_state,
        "decision_points": points,
        "decision_status_counts": _decision_status_counts(points),
        "unresolved_human_decision_count": sum(1 for point in points if point["requires_human_decision"]),
    }
    validate_artifact(packet, "decision_register")
    rounds_dir.mkdir(parents=True, exist_ok=True)
    output = rounds_dir / "decision_register.json"
    output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (rounds_dir / "decision_register.md").write_text(render_decision_register_markdown(packet), encoding="utf-8")
    write_decision_summary_outputs(register_path=output)
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
        f"- decision_status_counts: {_format_status_counts(packet.get('decision_status_counts') or _decision_status_counts(packet.get('decision_points', [])))}",
        f"- unresolved_human_decision_count: `{packet['unresolved_human_decision_count']}`",
        "",
    ]
    for point in packet["decision_points"]:
        lines.extend(
            [
                f"## {point['decision_id']}",
                "",
                f"- type: `{point['decision_type']}`",
                f"- status: `{point.get('decision_status') or _legacy_decision_status(point)}`",
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


def summarize_decision_register(register: dict[str, Any], *, source_register_path: str) -> dict[str, Any]:
    """Build a stable mechanical summary from a decision register."""
    points = list(register.get("decision_points", []))
    clusters = {
        "by_section": _clusters_by_section(points),
        "by_round_profile": _clusters_by_round_profile(points),
        "by_trigger_type": _clusters_by_trigger_type(points),
    }
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_register_path": source_register_path,
        "mode": register["mode"],
        "terminal_state": register["terminal_state"],
        "decision_count": len(points),
        "decision_status_counts": _decision_status_counts(points),
        "unresolved_human_decision_count": register["unresolved_human_decision_count"],
        "summary_method": "mechanical_v1",
        "hotspots": _decision_hotspots(clusters),
        "clusters": clusters,
    }
    validate_artifact(summary, "decision_summary")
    return summary


def render_decision_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Decision Summary",
        "",
        f"- source_register_path: `{summary['source_register_path']}`",
        f"- mode: `{summary['mode']}`",
        f"- terminal_state: `{summary['terminal_state']}`",
        f"- decision_count: `{summary['decision_count']}`",
        f"- decision_status_counts: {_format_status_counts(summary['decision_status_counts'])}",
        f"- unresolved_human_decision_count: `{summary['unresolved_human_decision_count']}`",
        f"- summary_method: `{summary['summary_method']}`",
        "",
    ]
    lines.extend(["## Hotspots", ""])
    for name, title in (("largest_clusters", "Largest Clusters"), ("human_decision_clusters", "Human Decision Clusters")):
        lines.extend([f"### {title}", ""])
        hotspots = summary["hotspots"][name]
        if not hotspots:
            lines.extend(["No hotspots.", ""])
            continue
        for hotspot in hotspots:
            lines.append(
                f"- `{hotspot['cluster_group']}` / `{hotspot['cluster_label']}`: "
                f"{hotspot['decision_count']} decisions, "
                f"{hotspot['requires_human_decision_count']} human decisions"
            )
        lines.append("")
    for group_name, title in (
        ("by_section", "By Section"),
        ("by_round_profile", "By Round/Profile"),
        ("by_trigger_type", "By Trigger Type"),
    ):
        lines.extend([f"## {title}", ""])
        clusters = summary["clusters"][group_name]
        if not clusters:
            lines.extend(["No decisions.", ""])
            continue
        for cluster in clusters:
            lines.extend(
                [
                    f"### {cluster['cluster_label']}",
                    "",
                    f"- decisions: `{cluster['decision_count']}`",
                    f"- human decisions: `{cluster['requires_human_decision_count']}`",
                    f"- status_counts: {_format_status_counts(cluster['decision_status_counts'])}",
                    f"- actions: {_format_inline_values(cluster['orchestrator_actions'])}",
                    f"- decision_types: {_format_inline_values(cluster['decision_types'])}",
                    f"- trigger_types: {_format_inline_values(cluster['trigger_types'])}",
                    f"- rounds: {_format_inline_values([str(number) for number in cluster['round_numbers']])}",
                    f"- profiles: {_format_inline_values(cluster['profiles'])}",
                    f"- sections: {_format_inline_values(cluster['affected_sections'])}",
                    f"- decision_ids: {_format_inline_values(cluster['decision_ids'])}",
                    "",
                    "Representative decisions:",
                ]
            )
            for decision in cluster["representative_decisions"]:
                lines.append(f"- `{decision['decision_id']}`: {decision['question']}")
            lines.append("")
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


def _clusters_by_section(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        sections = point.get("affected_sections") or ["(unsectioned)"]
        for section in sections:
            groups.setdefault(str(section), []).append(point)
    return _clusters_from_groups(groups, label_prefix="")


def _clusters_by_round_profile(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        key = f"round-{point['round_number']}|{point['profile']}"
        groups.setdefault(key, []).append(point)
    labels = {key: key.replace("|", " / ") for key in groups}
    return _clusters_from_groups(groups, labels=labels)


def _clusters_by_trigger_type(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        triggers = point.get("trigger_types") or ["(none)"]
        for trigger in triggers:
            groups.setdefault(str(trigger), []).append(point)
    return _clusters_from_groups(groups, label_prefix="")


def _decision_hotspots(clusters: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    flattened = [
        _hotspot(group_name, cluster)
        for group_name, group_clusters in clusters.items()
        for cluster in group_clusters
    ]
    return {
        "largest_clusters": sorted(
            flattened,
            key=lambda hotspot: (
                -int(hotspot["decision_count"]),
                -int(hotspot["requires_human_decision_count"]),
                str(hotspot["cluster_group"]),
                str(hotspot["cluster_key"]),
            ),
        )[:5],
        "human_decision_clusters": sorted(
            [hotspot for hotspot in flattened if int(hotspot["requires_human_decision_count"]) > 0],
            key=lambda hotspot: (
                -int(hotspot["requires_human_decision_count"]),
                -int(hotspot["decision_count"]),
                str(hotspot["cluster_group"]),
                str(hotspot["cluster_key"]),
            ),
        )[:5],
    }


def _hotspot(group_name: str, cluster: dict[str, Any]) -> dict[str, Any]:
    return {
        "cluster_group": group_name,
        "cluster_key": cluster["cluster_key"],
        "cluster_label": cluster["cluster_label"],
        "decision_count": cluster["decision_count"],
        "requires_human_decision_count": cluster["requires_human_decision_count"],
    }


def _clusters_from_groups(
    groups: dict[str, list[dict[str, Any]]],
    *,
    labels: dict[str, str] | None = None,
    label_prefix: str = "",
) -> list[dict[str, Any]]:
    clusters = []
    for key in sorted(groups):
        points = sorted(groups[key], key=lambda point: (int(point["round_number"]), str(point["decision_id"])))
        clusters.append(_cluster(key=key, label=(labels or {}).get(key, f"{label_prefix}{key}"), points=points))
    return clusters


def _cluster(*, key: str, label: str, points: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cluster_key": key,
        "cluster_label": label,
        "decision_count": len(points),
        "requires_human_decision_count": sum(1 for point in points if point.get("requires_human_decision") is True),
        "decision_status_counts": _decision_status_counts(points),
        "orchestrator_actions": _sorted_unique(str(point["orchestrator_action"]) for point in points),
        "decision_types": _sorted_unique(str(point["decision_type"]) for point in points),
        "trigger_types": _sorted_unique(trigger for point in points for trigger in point.get("trigger_types", [])),
        "round_numbers": sorted({int(point["round_number"]) for point in points}),
        "profiles": _sorted_unique(str(point["profile"]) for point in points),
        "affected_sections": _sorted_unique(section for point in points for section in point.get("affected_sections", [])),
        "decision_ids": [str(point["decision_id"]) for point in points],
        "representative_decisions": [
            {
                "decision_id": str(point["decision_id"]),
                "question": str(point["question"]),
                "risk_if_wrong": str(point["risk_if_wrong"]),
            }
            for point in points[:3]
        ],
    }


def _sorted_unique(values: Any) -> list[str]:
    return sorted({str(value) for value in values})


def _format_inline_values(values: list[str]) -> str:
    if not values:
        return "`none`"
    return ", ".join(f"`{value}`" for value in values)


def _format_status_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "`none`"
    return ", ".join(f"`{key}`={value}" for key, value in sorted(counts.items()))


def _decision_status_counts(points: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for point in points:
        status = str(point.get("decision_status") or _legacy_decision_status(point))
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _legacy_decision_status(point: dict[str, Any]) -> str:
    return _decision_status(
        action=str(point.get("orchestrator_action", "record_only")),
        requires_human_decision=bool(point.get("requires_human_decision")),
    )


def _decision_status(*, action: str, requires_human_decision: bool) -> str:
    if action == "pause_for_input":
        return "operator_required_decision"
    if action == "present_at_end" and requires_human_decision:
        return "operator_review_recommended"
    if action == "record_only":
        return "record_only_hardening"
    return "editor_applied_decision"


def _is_scope_escalation(scope_contract: dict[str, Any] | None, *, section: str, evidence_line: str) -> bool:
    if not scope_contract or not _contains_strong_normative(evidence_line):
        return False
    haystack = f"{section} {evidence_line}".lower()
    for surface in scope_contract.get("scope_surfaces", []):
        if not isinstance(surface, dict):
            continue
        status = str(surface.get("status", "")).lower()
        if status not in {"deferred", "out_of_scope"}:
            continue
        if _surface_matches(haystack, str(surface.get("name", ""))):
            return True
    for flow in scope_contract.get("core_flows", []):
        if not isinstance(flow, dict):
            continue
        if str(flow.get("priority", "")).lower() != "could":
            continue
        if _surface_matches(haystack, str(flow.get("description", ""))):
            return True
    return False


def _surface_matches(haystack: str, text: str) -> bool:
    words = [
        word
        for word in re.findall(r"[a-z0-9_]+", text.lower())
        if len(word) >= 5 and word not in {"required", "fields", "behavior", "surface"}
    ]
    if not words:
        return False
    return any(word in haystack for word in words[:8])


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
    scope_escalation = _is_scope_escalation(context.scope_contract, section=section, evidence_line=evidence_line)
    action = "record_only"
    if context.requires_human_decision or scope_escalation:
        action = "pause_for_input" if context.mode == "intervention" else "present_at_end"
    decision_status = (
        "deferred_scope_decision"
        if scope_escalation and action != "pause_for_input"
        else _decision_status(action=action, requires_human_decision=context.requires_human_decision or scope_escalation)
    )
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
        "decision_status": decision_status,
        "requires_human_decision": context.requires_human_decision or scope_escalation,
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
