"""Reviewer-only cross-spec change audit workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Protocol

from whetstone.contracts import validate_artifact
from whetstone.hashing import draft_hash
from whetstone.live import _validate_reviewer_feedback
from whetstone.prompts import render_reviewer_prompt


class ReviewerLike(Protocol):
    def review(self, prompt: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class AuditClientIdentity:
    name: str
    version: str
    model: str


@dataclass(frozen=True)
class ChangeAuditResult:
    verdict: str
    boundary_preserved: bool | None
    report_path: Path
    feedback_path: Path
    manifest_path: Path
    brief_path: Path


def run_change_audit(
    *,
    root: Path,
    notes_path: Path,
    spec_paths: list[Path],
    profile: str,
    reviewer_client: ReviewerLike,
    client_identity: AuditClientIdentity,
) -> ChangeAuditResult:
    if not spec_paths:
        raise ValueError("audit-change requires at least one --spec")
    notes = notes_path.read_text(encoding="utf-8")
    specs = [(path, path.read_text(encoding="utf-8")) for path in spec_paths]
    audit_dir = root / "change_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    brief = render_audit_brief(notes_path=notes_path, notes=notes, specs=specs, profile=profile)
    brief_path = audit_dir / "audit_brief.md"
    brief_path.write_text(brief, encoding="utf-8")
    brief_hash = draft_hash(brief)

    manifest = _audit_manifest(
        notes_path=notes_path,
        notes=notes,
        specs=specs,
        profile=profile,
        client_identity=client_identity,
    )
    manifest_path = audit_dir / "audit_manifest.json"
    validate_artifact(manifest, "change_audit_manifest")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    prompt = _audit_reviewer_prompt(profile=profile, brief=brief, brief_hash=brief_hash)
    feedback_path = audit_dir / "change_audit_feedback.json"
    try:
        feedback = reviewer_client.review(prompt)
        _validate_reviewer_feedback(
            feedback,
            round_number=1,
            profile=profile,
            draft_hash_value=brief_hash,
            schema_name="reviewer_feedback",
        )
    except Exception as exc:
        report = build_change_audit_failed_report(
            brief_hash=brief_hash,
            profile=profile,
            feedback_path=feedback_path,
            manifest_path=manifest_path,
            failure_reason=str(exc),
        )
        report_path = audit_dir / "change_audit_report.json"
        validate_artifact(report, "change_audit_report")
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_markdown_path = audit_dir / "change_audit_report.md"
        report_markdown_path.write_text(render_change_audit_report_markdown(report=report, feedback={"feedback": []}), encoding="utf-8")
        return ChangeAuditResult(
            verdict="audit_failed",
            boundary_preserved=None,
            report_path=report_path,
            feedback_path=feedback_path,
            manifest_path=manifest_path,
            brief_path=brief_path,
        )

    feedback_path.write_text(json.dumps(feedback, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = build_change_audit_report(
        feedback=feedback,
        brief_hash=brief_hash,
        profile=profile,
        feedback_path=feedback_path,
        manifest_path=manifest_path,
    )
    report_path = audit_dir / "change_audit_report.json"
    validate_artifact(report, "change_audit_report")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_markdown_path = audit_dir / "change_audit_report.md"
    report_markdown_path.write_text(render_change_audit_report_markdown(report=report, feedback=feedback), encoding="utf-8")

    return ChangeAuditResult(
        verdict=str(report["verdict"]),
        boundary_preserved=report["boundary_preserved"],
        report_path=report_path,
        feedback_path=feedback_path,
        manifest_path=manifest_path,
        brief_path=brief_path,
    )


def render_audit_brief(*, notes_path: Path, notes: str, specs: list[tuple[Path, str]], profile: str) -> str:
    lines = [
        "# Whetstone Change Audit Brief",
        "",
        "Workflow: audit_change",
        f"Profile: {profile}",
        "",
        "Reviewer instructions:",
        "- Evaluate only the stated change intent and expected boundary.",
        "- Do not perform a full convergence review.",
        "- Treat unrelated polish, completeness, or future hardening concerns as out of scope.",
        "- Report an issue only when it directly affects the change intent, expected boundary, or listed source specs.",
        "- If a concern is outside the stated audit boundary, set in_scope=false.",
        "",
        "## Audit Notes",
        "",
        f"Path: {notes_path}",
        f"Hash: {draft_hash(notes)}",
        "",
        notes.rstrip(),
        "",
        "## Specs To Check",
        "",
    ]
    for index, (path, content) in enumerate(specs, start=1):
        lines.extend(
            [
                f"### Spec {index}: {path}",
                "",
                f"Hash: {draft_hash(content)}",
                "",
                "```markdown",
                content.rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_change_audit_report(
    *,
    feedback: dict[str, Any],
    brief_hash: str,
    profile: str,
    feedback_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    counts = {"blocker": 0, "major": 0, "minor": 0, "nit": 0}
    in_scope_ids: list[str] = []
    out_of_scope_ids: list[str] = []
    for item in feedback.get("feedback", []):
        feedback_id = str(item.get("feedback_id", ""))
        if item.get("in_scope") is False:
            out_of_scope_ids.append(feedback_id)
            continue
        severity = item.get("normalized_severity")
        if severity in counts:
            counts[severity] += 1
        in_scope_ids.append(feedback_id)

    if counts["blocker"]:
        verdict = "blocked"
    elif counts["major"]:
        verdict = "needs_revision"
    elif counts["minor"] or counts["nit"]:
        verdict = "pass_with_minor_clarification"
    else:
        verdict = "pass"

    boundary_preserved = verdict in {"pass", "pass_with_minor_clarification"}
    return {
        "schema_version": "change-audit-report-v1",
        "generated_at": _now(),
        "audit_brief_hash": brief_hash,
        "profile": profile,
        "verdict": verdict,
        "boundary_preserved": boundary_preserved,
        "failure_reason": None,
        "feedback_counts": counts,
        "in_scope_feedback_ids": in_scope_ids,
        "out_of_scope_feedback_ids": out_of_scope_ids,
        "recommended_next_action": _recommended_next_action(verdict),
        "source_feedback_path": str(feedback_path),
        "audit_manifest_path": str(manifest_path),
    }


def build_change_audit_failed_report(
    *,
    brief_hash: str,
    profile: str,
    feedback_path: Path,
    manifest_path: Path,
    failure_reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": "change-audit-report-v1",
        "generated_at": _now(),
        "audit_brief_hash": brief_hash,
        "profile": profile,
        "verdict": "audit_failed",
        "boundary_preserved": None,
        "failure_reason": failure_reason or "audit failed",
        "feedback_counts": {"blocker": 0, "major": 0, "minor": 0, "nit": 0},
        "in_scope_feedback_ids": [],
        "out_of_scope_feedback_ids": [],
        "recommended_next_action": "fix_audit_setup",
        "source_feedback_path": str(feedback_path),
        "audit_manifest_path": str(manifest_path),
    }


def render_change_audit_report_markdown(*, report: dict[str, Any], feedback: dict[str, Any]) -> str:
    lines = [
        "# Change Audit Report",
        "",
        f"- verdict: {report['verdict']}",
        f"- boundary_preserved: {report['boundary_preserved']}",
        f"- failure_reason: {report['failure_reason']}",
        f"- recommended_next_action: {report['recommended_next_action']}",
        f"- source_feedback_path: {report['source_feedback_path']}",
        "",
        "## In-Scope Feedback Counts",
        "",
    ]
    counts = report["feedback_counts"]
    for severity in ("blocker", "major", "minor", "nit"):
        lines.append(f"- {severity}: {counts[severity]}")
    lines.extend(["", "## In-Scope Findings", ""])
    in_scope = [item for item in feedback.get("feedback", []) if item.get("feedback_id") in set(report["in_scope_feedback_ids"])]
    if not in_scope:
        lines.append("No in-scope findings.")
    for item in in_scope:
        lines.extend(
            [
                f"### {item.get('feedback_id')} - {item.get('normalized_severity')}",
                "",
                f"- claim: {item.get('claim')}",
                f"- evidence: {item.get('evidence')}",
                f"- recommended_change: {item.get('recommended_change')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _audit_manifest(
    *,
    notes_path: Path,
    notes: str,
    specs: list[tuple[Path, str]],
    profile: str,
    client_identity: AuditClientIdentity,
) -> dict[str, Any]:
    return {
        "schema_version": "change-audit-manifest-v1",
        "generated_at": _now(),
        "audit_notes_path": str(notes_path),
        "audit_notes_hash": draft_hash(notes),
        "profile": profile,
        "specs": [{"path": str(path), "hash": draft_hash(content)} for path, content in specs],
        "client": {
            "name": client_identity.name,
            "version": client_identity.version,
            "model": client_identity.model,
        },
    }


def _audit_reviewer_prompt(*, profile: str, brief: str, brief_hash: str) -> str:
    return render_reviewer_prompt(
        profile=profile,
        draft=brief,
        phase="audit_change",
        round_number=1,
        draft_hash_value=brief_hash,
    )


def _recommended_next_action(verdict: str) -> str:
    if verdict == "pass":
        return "none"
    if verdict == "pass_with_minor_clarification":
        return "manual_patch"
    if verdict == "needs_revision":
        return "manual_patch"
    if verdict == "blocked":
        return "run_focused_whetstone"
    return "fix_audit_setup"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
