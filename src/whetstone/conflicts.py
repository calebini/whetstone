"""Cross-round conflict escalation tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from whetstone.evaluation import conflict_severity


@dataclass(frozen=True)
class ConflictEscalation:
    conflicts: list[dict[str, Any]]
    blocker_level: bool
    reason: str


@dataclass
class _ConflictState:
    conflict: dict[str, Any]
    rounds: list[int] = field(default_factory=list)


class ConflictTracker:
    """Track conflicts by fingerprint and detect escalation thresholds."""

    def __init__(self) -> None:
        self._states: dict[str, _ConflictState] = {}

    def record_round(
        self,
        *,
        round_number: int,
        conflicts: Iterable[dict[str, Any]],
        issues: Iterable[dict[str, Any]] = (),
    ) -> ConflictEscalation | None:
        issue_by_id = {str(issue["issue_id"]): issue for issue in issues}
        escalated: list[dict[str, Any]] = []
        reasons: list[str] = []

        for conflict in conflicts:
            normalized = normalize_conflict(conflict, issue_by_id)
            fingerprint = str(normalized["conflict_fingerprint"])
            state = self._states.setdefault(fingerprint, _ConflictState(conflict=normalized))
            state.conflict = normalized
            if not state.rounds or state.rounds[-1] != round_number:
                state.rounds.append(round_number)

            if len(state.rounds) >= 2 and state.rounds[-2] == round_number - 1:
                escalated.append(normalized)
                reasons.append("same conflict persisted for 2 consecutive rounds")
            elif len(state.rounds) >= 3:
                escalated.append(normalized)
                reasons.append("same conflict appeared 3 times non-consecutively")

        if not escalated:
            return None

        deduped = _dedupe_by_fingerprint(escalated)
        blocker_level = any(conflict.get("conflict_severity") == "blocker" for conflict in deduped)
        return ConflictEscalation(deduped, blocker_level, "; ".join(dict.fromkeys(reasons)))


def normalize_conflict(conflict: dict[str, Any], issue_by_id: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return a conflict summary with severity computed from participating issues when available."""
    normalized = dict(conflict)
    issue_by_id = issue_by_id or {}
    participating = [issue_by_id[issue_id] for issue_id in normalized.get("participating_issue_ids", []) if issue_id in issue_by_id]
    if participating:
        normalized["conflict_severity"] = conflict_severity(participating)
    return normalized


def _dedupe_by_fingerprint(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for conflict in conflicts:
        fingerprint = str(conflict["conflict_fingerprint"])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(conflict)
    return deduped

