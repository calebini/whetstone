"""Convergence declaration helpers."""

from __future__ import annotations

from pathlib import Path


def render_convergence_declaration(
    *,
    target_phase: str,
    target_mode: str,
    final_draft_hash: str,
    rubric_content_hash: str,
    unresolved_blockers_count: int,
    unresolved_major_issues_count: int,
    unresolved_rubric_gaps_count: int,
    reviewer_final_status: str,
    declaration_status: str,
) -> str:
    return "\n".join(
        [
            "# Convergence Declaration",
            "",
            f"- target_phase: {target_phase}",
            f"- target_mode: {target_mode}",
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

