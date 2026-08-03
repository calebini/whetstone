"""Reviewer-only multi-profile diagnostic sweep."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from whetstone.config import OrchestratorConfig
from whetstone.contracts import validate_artifact
from whetstone.context_pressure import write_context_pressure_report
from whetstone.hashing import draft_hash
from whetstone.live import LiveRoundRunner, ReviewerClient, run_telemetry_totals
from whetstone.scheduler import default_phase_1_scheduler


@dataclass(frozen=True)
class DiagnosticSweepResult:
    report_path: Path
    markdown_path: Path
    profile_count: int
    feedback_count: int
    blocker_count: int
    major_count: int
    recommendation: str


def run_diagnostic_sweep(
    root: Path | str,
    config: OrchestratorConfig,
    *,
    reviewer_client: ReviewerClient | None = None,
    overwrite: bool = False,
    timeout_seconds: int | None = None,
) -> DiagnosticSweepResult:
    """Run one reviewer-only pass per configured Phase 1 profile."""

    root_path = Path(root)
    write_context_pressure_report(root=root_path, config=config, phase="phase_1", round_number=0)
    scheduler = default_phase_1_scheduler(config.review_profile_budgets, profile_set=config.review_profile_set)
    profiles = [step.profile for step in scheduler.steps]
    initial_draft_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
    profile_rows: list[dict[str, Any]] = []
    all_feedback: list[dict[str, Any]] = []

    for round_number, profile in enumerate(profiles, start=1):
        result = LiveRoundRunner(
            root_path,
            config,
            reviewer_client=reviewer_client,
            timeout_seconds=timeout_seconds,
        ).run_review_only_round(
            round_number=round_number,
            profile=profile,
            phase="phase_1",
            overwrite=overwrite,
        )
        feedback_path = result.round_dir / "reviewer_feedback.json"
        reviewer_feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
        feedback = list(reviewer_feedback.get("feedback", []))
        all_feedback.extend({**item, "source_profile": profile} for item in feedback)
        counts = _severity_counts(feedback)
        profile_rows.append(
            {
                "profile": profile,
                "round_number": round_number,
                "clean": counts["blocker"] == 0 and counts["major"] == 0,
                "feedback_count": len(feedback),
                "blocker_count": counts["blocker"],
                "major_count": counts["major"],
                "minor_count": counts["minor"],
                "nit_count": counts["nit"],
                "reviewer_feedback_path": str(feedback_path.relative_to(root_path)),
            }
        )

    clusters = {
        "by_profile": _cluster_feedback(all_feedback, key_fn=lambda item: str(item.get("source_profile") or "unknown")),
        "by_issue_type": _cluster_feedback(all_feedback, key_fn=lambda item: str(item.get("issue_type") or "unknown")),
        "by_section": _cluster_feedback_by_section(all_feedback),
    }
    recommendation, rationale = _recommendation(all_feedback, clusters)
    report = {
        "schema_version": "profile-sweep-report-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root_path),
        "phase": "phase_1",
        "review_profile_set": config.review_profile_set,
        "draft_hash": initial_draft_hash,
        "editor_invoked": False,
        "spec_mutated": False,
        "profiles": profile_rows,
        "clusters": clusters,
        "recommendation": recommendation,
        "recommendation_rationale": rationale,
    }
    validate_artifact(report, "profile_sweep_report")
    config.rounds_dir.mkdir(parents=True, exist_ok=True)
    report_path = config.rounds_dir / "profile_sweep_report.json"
    markdown_path = config.rounds_dir / "profile_sweep_report.md"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    run_telemetry_totals(config.rounds_dir)
    counts = _severity_counts(all_feedback)
    return DiagnosticSweepResult(
        report_path=report_path,
        markdown_path=markdown_path,
        profile_count=len(profile_rows),
        feedback_count=len(all_feedback),
        blocker_count=counts["blocker"],
        major_count=counts["major"],
        recommendation=recommendation,
    )


def _severity_counts(feedback: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"blocker": 0, "major": 0, "minor": 0, "nit": 0}
    for item in feedback:
        severity = item.get("normalized_severity")
        if severity in counts:
            counts[severity] += 1
    return counts


def _cluster_feedback(feedback: list[dict[str, Any]], *, key_fn: Any) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in feedback:
        if item.get("normalized_severity") not in {"blocker", "major"}:
            continue
        buckets[key_fn(item)].append(item)
    return _cluster_rows(buckets)


def _cluster_feedback_by_section(feedback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in feedback:
        if item.get("normalized_severity") not in {"blocker", "major"}:
            continue
        sections = item.get("affected_sections") or ["unknown"]
        for section in sections:
            buckets[str(section)].append(item)
    return _cluster_rows(buckets)


def _cluster_rows(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for key, items in buckets.items():
        counts = _severity_counts(items)
        rows.append(
            {
                "key": key,
                "blocker_count": counts["blocker"],
                "major_count": counts["major"],
                "feedback_ids": [
                    f"{item.get('source_profile', 'unknown')}:{item.get('feedback_id', '')}" for item in items
                ],
            }
        )
    return sorted(rows, key=lambda item: (-(item["blocker_count"] + item["major_count"]), item["key"]))


def _recommendation(feedback: list[dict[str, Any]], clusters: dict[str, list[dict[str, Any]]]) -> tuple[str, str]:
    serious = [item for item in feedback if item.get("normalized_severity") in {"blocker", "major"}]
    if not serious:
        return "start_phase_1", "No blocker or major findings were reported by the configured Phase 1 profiles."

    serious_profiles = {str(item.get("source_profile") or "unknown") for item in serious}
    serious_issue_types = {str(item.get("issue_type") or "unknown") for item in serious}
    serious_sections = {
        str(section)
        for item in serious
        for section in (item.get("affected_sections") or ["unknown"])
    }
    scope_issue = any("scope" in issue_type or "out_of_scope" in issue_type for issue_type in serious_issue_types)
    if scope_issue and len(serious_profiles) > 1:
        return (
            "manual_scope_review",
            "Serious findings include scope-boundary concerns across multiple profiles; review the job boundary before mutation.",
        )
    if len(serious_profiles) > 1 or len(serious_sections) >= 4 or len(serious_issue_types) >= 4:
        return (
            "run_bounded_synthesis",
            "Serious findings span multiple profiles, sections, or issue families; a bounded synthesis pass should precede normal Phase 1 loops.",
        )
    return (
        "run_vertical_phase_1",
        "Serious findings are concentrated enough for a normal vertical Phase 1 review/edit cycle.",
    )


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Profile Sweep Report",
        "",
        f"- phase: `{report['phase']}`",
        f"- review_profile_set: `{report['review_profile_set']}`",
        f"- draft_hash: `{report['draft_hash']}`",
        f"- editor_invoked: `{str(report['editor_invoked']).lower()}`",
        f"- spec_mutated: `{str(report['spec_mutated']).lower()}`",
        f"- recommendation: `{report['recommendation']}`",
        "",
        report["recommendation_rationale"],
        "",
        "## Profiles",
        "",
    ]
    for item in report["profiles"]:
        lines.append(
            f"- `{item['profile']}` round `{item['round_number']}`: "
            f"{item['blocker_count']} blockers, {item['major_count']} majors, "
            f"{item['minor_count']} minors, {item['nit_count']} nits"
        )
    lines.extend(["", "## Largest Serious Clusters", ""])
    for label, rows in (
        ("By Profile", report["clusters"]["by_profile"]),
        ("By Issue Type", report["clusters"]["by_issue_type"]),
        ("By Section", report["clusters"]["by_section"]),
    ):
        lines.append(f"### {label}")
        if not rows:
            lines.append("")
            lines.append("- none")
            lines.append("")
            continue
        for row in rows[:8]:
            lines.append(
                f"- `{row['key']}`: {row['blocker_count']} blockers, "
                f"{row['major_count']} majors ({len(row['feedback_ids'])} feedback IDs)"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
