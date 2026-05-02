"""Deterministic convergence evaluation primitives."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from whetstone.identity import SEVERITY_RANK, normalize_severity


def accepted_draft(issues: Iterable[Mapping[str, object]]) -> bool:
    """Return true when no global blocker or major issues remain."""

    return all(issue.get("normalized_severity") not in {"blocker", "major"} for issue in issues)


def conflict_severity(issues: Iterable[Mapping[str, object]]) -> str:
    severities = [issue.get("normalized_severity") for issue in issues]
    return normalize_severity(*(severity if isinstance(severity, str) else None for severity in severities))


def target_matrix_satisfied(
    *,
    target_phase: str,
    target_mode: str,
    issues: Iterable[Mapping[str, object]],
    unresolved_rubric_gaps: Iterable[Mapping[str, object]] = (),
    declaration_accepted: bool = False,
) -> bool:
    issue_list = list(issues)
    blocker_count = _count_at_or_above(issue_list, "blocker")
    major_count = _count_exact(issue_list, "major")
    rubric_gap_count = len(list(unresolved_rubric_gaps))

    if target_phase == "mid" and target_mode == "permissive":
        return blocker_count == 0
    if target_phase == "mid" and target_mode == "strict":
        return blocker_count == 0 and major_count == 0
    if target_phase == "final" and target_mode == "permissive":
        return blocker_count == 0 and major_count == 0
    if target_phase == "final" and target_mode == "strict":
        return blocker_count == 0 and major_count == 0 and rubric_gap_count == 0 and declaration_accepted
    raise ValueError(f"unsupported target {target_phase}/{target_mode}")


def oscillation_recommendation(
    oscillation_type: str,
    issue_severities: Iterable[str | None] = (),
    *,
    repeated_readdition: bool = False,
) -> str:
    if oscillation_type == "cycle":
        return "stop_iteration"
    if oscillation_type == "mechanical_churn":
        return "freeze_prior_decision"
    if oscillation_type == "feedback_flip_flop":
        severity = normalize_severity(*issue_severities)
        if SEVERITY_RANK[severity] >= SEVERITY_RANK["major"]:
            return "escalate_conflict"
        return "freeze_prior_decision"
    if oscillation_type == "feedback_re_addition":
        return "stop_iteration" if repeated_readdition else "continue_once"
    if oscillation_type == "feedback_churn":
        return "escalate_conflict"
    raise ValueError(f"unsupported oscillation type {oscillation_type!r}")


def _count_exact(issues: Iterable[Mapping[str, object]], severity: str) -> int:
    return sum(1 for issue in issues if issue.get("normalized_severity") == severity)


def _count_at_or_above(issues: Iterable[Mapping[str, object]], severity: str) -> int:
    minimum = SEVERITY_RANK[severity]
    return sum(
        1
        for issue in issues
        if isinstance(issue.get("normalized_severity"), str)
        and SEVERITY_RANK[issue["normalized_severity"]] >= minimum
    )
