"""Detect expanding contract surfaces during live profile review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from whetstone.contracts import validate_artifact
from whetstone.hashing import draft_hash


CONTRACT_KEYWORDS = {
    "schema": "schema/data-contract",
    "field": "schema/data-contract",
    "enum": "schema/data-contract",
    "required": "schema/data-contract",
    "nullable": "schema/data-contract",
    "validation": "validation/error-contract",
    "error": "validation/error-contract",
    "failure": "failure-semantics",
    "classification": "failure-semantics",
    "incident": "failure-semantics",
    "mapping": "mapping/precedence",
    "precedence": "mapping/precedence",
    "ordering": "ordering/determinism",
    "deterministic": "ordering/determinism",
    "checkpoint": "checkpoint/replay-context",
    "replay": "replay-contract",
    "report": "artifact/report-contract",
    "artifact": "artifact/report-contract",
    "interface": "interface/invocation",
    "invocation": "interface/invocation",
}


@dataclass(frozen=True)
class ContractSurfacePolicy:
    enabled: bool = True
    action: str = "recommend_synthesis"
    min_profile_rounds: int = 4
    recent_window: int = 4
    min_recent_serious_rounds: int = 3
    min_contract_families: int = 2


def maybe_write_contract_surface_report(
    *,
    rounds_dir: Path,
    current_round: int,
    profile: str,
    policy: ContractSurfacePolicy = ContractSurfacePolicy(),
) -> Path | None:
    """Write a report when a profile appears to be expanding a contract surface."""

    if not policy.enabled:
        return None
    if policy.action not in {"recommend_synthesis", "report_only"}:
        return None
    profile_rounds = _profile_rounds(rounds_dir, profile=profile, through_round=current_round)
    if len(profile_rounds) < policy.min_profile_rounds:
        return None
    recent = profile_rounds[-policy.recent_window :]
    serious_recent = [item for item in recent if item["blocker_count"] + item["major_count"] > 0]
    families = sorted({family for item in recent for family in item["contract_families"]})
    if len(serious_recent) < policy.min_recent_serious_rounds or len(families) < policy.min_contract_families:
        return None

    affected_sections = sorted({section for item in recent for section in item["affected_sections"]})
    suspected_feedback_ids = [
        feedback_id
        for item in recent
        for feedback_id in item["serious_feedback_ids"]
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "detected": True,
        "type": "EXPANDING_CONTRACT_SURFACE",
        "round_number": current_round,
        "profile": profile,
        "draft_hash": _current_draft_hash(rounds_dir, current_round),
        "profile_rounds_observed": len(profile_rounds),
        "recent_window": len(recent),
        "serious_recent_rounds": len(serious_recent),
        "contract_families": families,
        "affected_sections": affected_sections,
        "suspected_feedback_ids": suspected_feedback_ids,
        "round_evidence": recent,
        "recommendation": "synthesis_pass_recommended" if policy.action == "recommend_synthesis" else "report_only",
        "synthesis_scope": {
            "sections": affected_sections[:12],
            "contract_families": families,
            "instruction": (
                "Suspend narrow patching for this surface. Ask the Editor for a bounded synthesis pass over "
                "the listed sections and contract families, preserving the full draft output contract."
            ),
        },
    }
    validate_artifact(report, "contract_surface_report")
    path = rounds_dir / "contract_surface_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown_report(path.with_suffix(".md"), report)
    return path


def read_contract_surface_report(rounds_dir: Path, *, profile: str | None = None) -> dict[str, Any] | None:
    path = rounds_dir / "contract_surface_report.json"
    if not path.exists():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if profile is not None and report.get("profile") != profile:
        return None
    if report.get("detected") is not True:
        return None
    return report


def _profile_rounds(rounds_dir: Path, *, profile: str, through_round: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for round_number in range(1, through_round + 1):
        feedback_path = rounds_dir / f"round-{round_number}" / "reviewer_feedback.json"
        if not feedback_path.exists():
            continue
        try:
            reviewer_feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if reviewer_feedback.get("profile") != profile:
            continue
        feedback = [
            item
            for item in reviewer_feedback.get("feedback", [])
            if isinstance(item, dict) and bool(item.get("in_scope", True))
        ]
        serious = [
            item
            for item in feedback
            if item.get("normalized_severity") in {"blocker", "major"}
        ]
        rows.append(
            {
                "round_number": round_number,
                "blocker_count": sum(1 for item in serious if item.get("normalized_severity") == "blocker"),
                "major_count": sum(1 for item in serious if item.get("normalized_severity") == "major"),
                "minor_count": sum(1 for item in feedback if item.get("normalized_severity") == "minor"),
                "serious_feedback_ids": [str(item.get("feedback_id")) for item in serious],
                "affected_sections": sorted(
                    {
                        str(section)
                        for item in serious
                        for section in item.get("affected_sections", [])
                    }
                ),
                "contract_families": sorted({family for item in serious for family in _contract_families(item)}),
            }
        )
    return rows


def _contract_families(item: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(item.get(key, ""))
        for key in ("issue_type", "claim", "evidence", "recommended_change")
    ).lower()
    return {family for keyword, family in CONTRACT_KEYWORDS.items() if keyword in text}


def _current_draft_hash(rounds_dir: Path, round_number: int) -> str:
    draft_path = rounds_dir / f"round-{round_number}" / "draft_after.md"
    if not draft_path.exists():
        draft_path = rounds_dir / f"round-{round_number}" / "draft_before.md"
    return draft_hash(draft_path.read_text(encoding="utf-8"))


def _write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Contract Surface Report",
        "",
        f"- type: `{report['type']}`",
        f"- profile: `{report['profile']}`",
        f"- round_number: `{report['round_number']}`",
        f"- recommendation: `{report['recommendation']}`",
        "",
        "## Contract Families",
        "",
    ]
    lines.extend(f"- {family}" for family in report["contract_families"])
    lines.extend(["", "## Affected Sections", ""])
    lines.extend(f"- {section}" for section in report["affected_sections"])
    lines.extend(["", "## Synthesis Instruction", "", report["synthesis_scope"]["instruction"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")
