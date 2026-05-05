"""Convergence declaration helpers."""

from __future__ import annotations

from pathlib import Path


DECLARATION_ARTIFACTS = {
    "convergence_declaration.md",
    "rubric_gaps.json",
    "unresolved_issues.json",
}
REVIEWER_FINAL_STATUSES = {"accepted", "rejected", "not_run"}
DECLARATION_STATUSES = {"accepted", "rejected"}


def render_convergence_declaration(
    *,
    target_phase: str,
    target_mode: str,
    workflow: str = "standard",
    rubric_profile: str = "standard-v1",
    rubric_source: str = "builtin",
    rubric_label: str | None = None,
    rubric_manifest_path: str = "rounds/rubric_manifest.json",
    final_draft_hash: str,
    rubric_content_hash: str,
    unresolved_blockers_count: int,
    unresolved_major_issues_count: int,
    unresolved_rubric_gaps_count: int,
    reviewer_final_status: str,
    declaration_status: str,
) -> str:
    if reviewer_final_status not in REVIEWER_FINAL_STATUSES:
        raise ValueError(f"unsupported reviewer_final_status {reviewer_final_status!r}")
    if declaration_status not in DECLARATION_STATUSES:
        raise ValueError(f"unsupported declaration_status {declaration_status!r}")
    return "\n".join(
        [
            "# Convergence Declaration",
            "",
            f"- target_phase: {target_phase}",
            f"- target_mode: {target_mode}",
            f"- workflow: {workflow}",
            f"- rubric_profile: {rubric_profile}",
            f"- rubric_source: {rubric_source}",
            f"- rubric_label: {rubric_label if rubric_label is not None else 'null'}",
            f"- rubric_manifest_path: {rubric_manifest_path}",
            f"- final_draft_hash: {final_draft_hash}",
            f"- rubric_content_hash: {rubric_content_hash}",
            f"- unresolved_blockers count: {unresolved_blockers_count}",
            f"- unresolved_major_issues count: {unresolved_major_issues_count}",
            f"- unresolved_rubric_gaps count: {unresolved_rubric_gaps_count}",
            f"- reviewer_final_status: {reviewer_final_status}",
            f"- declaration_status: {declaration_status}",
            "",
        ]
    )


def write_convergence_declaration(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def declaration_revision_route(issues: list[dict]) -> str | None:
    """Classify unresolved Phase 2 issues as source or declaration revision work."""
    in_scope = [issue for issue in issues if issue.get("in_scope", True)]
    if not in_scope:
        return None
    for issue in in_scope:
        sections = set(issue.get("affected_sections", []))
        if "spec.md" in sections or not sections.issubset(DECLARATION_ARTIFACTS):
            return "CONVERGENCE_REVISION"
    return "DECLARATION_REVISION"


def validate_convergence_declaration(
    content: str,
    *,
    final_draft_hash: str,
    rubric_content_hash: str,
    workflow: str | None = None,
    rubric_profile: str | None = None,
    rubric_source: str | None = None,
    rubric_label: str | None = None,
    rubric_manifest_path: str | None = None,
    unresolved_blockers_count: int,
    unresolved_major_issues_count: int,
    unresolved_rubric_gaps_count: int,
) -> bool:
    fields = _parse_fields(content)
    return (
        fields.get("final_draft_hash") == final_draft_hash
        and fields.get("rubric_content_hash") == rubric_content_hash
        and (workflow is None or fields.get("workflow") == workflow)
        and (rubric_profile is None or fields.get("rubric_profile") == rubric_profile)
        and (rubric_source is None or fields.get("rubric_source") == rubric_source)
        and (rubric_label is None or fields.get("rubric_label") == rubric_label)
        and (rubric_manifest_path is None or fields.get("rubric_manifest_path") == rubric_manifest_path)
        and fields.get("unresolved_blockers count") == str(unresolved_blockers_count)
        and fields.get("unresolved_major_issues count") == str(unresolved_major_issues_count)
        and fields.get("unresolved_rubric_gaps count") == str(unresolved_rubric_gaps_count)
        and fields.get("reviewer_final_status") in REVIEWER_FINAL_STATUSES
        and fields.get("declaration_status") in DECLARATION_STATUSES
    )


def _parse_fields(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in content.splitlines():
        if not line.startswith("- ") or ": " not in line:
            continue
        key, value = line[2:].split(": ", 1)
        fields[key] = value
    return fields
