"""Cross-round conflict escalation tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from whetstone.contracts import validate_artifact
from whetstone.evaluation import conflict_severity
from whetstone.identity import SEVERITY_RANK, conflict_fingerprint, conflict_id


@dataclass(frozen=True)
class ConflictEscalation:
    conflicts: list[dict[str, Any]]
    blocker_level: bool
    reason: str


@dataclass
class _ConflictState:
    conflict: dict[str, Any]
    state: str = "present"
    first_seen_round: int = 0
    last_seen_round: int = 0
    consecutive_present_rounds: int = 0
    total_present_rounds: int = 0
    latest_issue_ids: list[str] = field(default_factory=list)
    participating_issue_fingerprints: list[str] = field(default_factory=list)


class ConflictTracker:
    """Track conflicts by fingerprint and detect escalation thresholds."""

    def __init__(self, states: dict[str, _ConflictState] | None = None) -> None:
        self._states: dict[str, _ConflictState] = states or {}

    @classmethod
    def from_snapshot(cls, packet: dict[str, Any]) -> ConflictTracker:
        states: dict[str, _ConflictState] = {}
        for item in packet.get("conflicts", []):
            conflict = {
                "conflict_id": item["conflict_id"],
                "conflict_fingerprint": item["conflict_fingerprint"],
                "conflict_type": item["conflict_type"],
                "conflict_severity": item["conflict_severity"],
                "participating_issue_ids": list(item.get("latest_issue_ids", [])),
                "conflict_claim": item["latest_conflict_claim"],
            }
            states[str(item["conflict_fingerprint"])] = _ConflictState(
                conflict=conflict,
                state=str(item["state"]),
                first_seen_round=int(item["first_seen_round"]),
                last_seen_round=int(item["last_seen_round"]),
                consecutive_present_rounds=int(item["consecutive_present_rounds"]),
                total_present_rounds=int(item["total_present_rounds"]),
                latest_issue_ids=list(item.get("latest_issue_ids", [])),
                participating_issue_fingerprints=list(item.get("participating_issue_fingerprints", [])),
            )
        return cls(states)

    def record_round(
        self,
        *,
        round_number: int,
        conflicts: Iterable[dict[str, Any]],
        issues: Iterable[dict[str, Any]] = (),
    ) -> ConflictEscalation | None:
        issue_by_id = {str(issue["issue_id"]): issue for issue in issues}
        normalized_conflicts = _dedupe_by_fingerprint([normalize_conflict(conflict, issue_by_id) for conflict in conflicts])
        present_fingerprints = {str(conflict["conflict_fingerprint"]) for conflict in normalized_conflicts}
        for fingerprint, state in self._states.items():
            if fingerprint not in present_fingerprints:
                state.state = "absent"
                state.consecutive_present_rounds = 0

        escalated: list[dict[str, Any]] = []
        reasons: list[str] = []

        for normalized in normalized_conflicts:
            fingerprint = str(normalized["conflict_fingerprint"])
            state = self._states.setdefault(
                fingerprint,
                _ConflictState(
                    conflict=normalized,
                    first_seen_round=round_number,
                    latest_issue_ids=list(normalized.get("participating_issue_ids", [])),
                ),
            )
            previous_last_seen = state.last_seen_round
            state.conflict = normalized
            state.state = "present"
            if state.first_seen_round == 0:
                state.first_seen_round = round_number
            if previous_last_seen != round_number:
                state.total_present_rounds += 1
                state.consecutive_present_rounds = state.consecutive_present_rounds + 1 if previous_last_seen == round_number - 1 else 1
            state.last_seen_round = round_number
            state.latest_issue_ids = list(normalized.get("participating_issue_ids", []))
            state.participating_issue_fingerprints = _participating_issue_fingerprints(normalized, issue_by_id)

            if state.consecutive_present_rounds >= 2:
                escalated.append(normalized)
                reasons.append("same conflict persisted for 2 consecutive rounds")
            elif state.total_present_rounds >= 3:
                escalated.append(normalized)
                reasons.append("same conflict appeared 3 times non-consecutively")

        if not escalated:
            return None

        deduped = _dedupe_by_fingerprint(escalated)
        blocker_level = any(conflict.get("conflict_severity") == "blocker" for conflict in deduped)
        return ConflictEscalation(deduped, blocker_level, "; ".join(dict.fromkeys(reasons)))

    def snapshot(self, *, round_number: int) -> dict[str, Any]:
        conflicts: list[dict[str, Any]] = []
        for fingerprint in sorted(self._states):
            state = self._states[fingerprint]
            conflict = state.conflict
            conflicts.append(
                {
                    "conflict_id": conflict["conflict_id"],
                    "conflict_fingerprint": conflict["conflict_fingerprint"],
                    "conflict_type": conflict["conflict_type"],
                    "conflict_severity": conflict["conflict_severity"],
                    "state": state.state,
                    "first_seen_round": state.first_seen_round,
                    "last_seen_round": state.last_seen_round,
                    "consecutive_present_rounds": state.consecutive_present_rounds,
                    "total_present_rounds": state.total_present_rounds,
                    "participating_issue_fingerprints": state.participating_issue_fingerprints,
                    "latest_issue_ids": state.latest_issue_ids,
                    "latest_conflict_claim": conflict["conflict_claim"],
                }
            )
        return {
            "schema_version": "conflict_state_v1",
            "generated_at": _now(),
            "round_number": round_number,
            "conflicts": conflicts,
        }

    def write_snapshot(self, path: Path, *, round_number: int) -> Path:
        packet = self.snapshot(round_number=round_number)
        validate_artifact(packet, "conflict_state")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path


def normalize_conflict(conflict: dict[str, Any], issue_by_id: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return a conflict summary with severity computed from participating issues when available."""
    normalized = dict(conflict)
    issue_by_id = issue_by_id or {}
    participating = [issue_by_id[issue_id] for issue_id in normalized.get("participating_issue_ids", []) if issue_id in issue_by_id]
    if participating:
        normalized["conflict_severity"] = conflict_severity(participating)
    return normalized


def read_conflict_state(path: Path) -> ConflictTracker | None:
    if not path.exists():
        return None
    packet = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(packet, "conflict_state")
    return ConflictTracker.from_snapshot(packet)


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


def conflict_from_oscillation_detection(detection: Any) -> dict[str, Any]:
    """Create a conflict summary from an escalated Phase 2 oscillation detection."""
    claim = f"{detection.oscillation_type} on {', '.join(detection.oscillation_opposition_keys)}"
    fingerprint = conflict_fingerprint(
        "profile_conflict",
        detection.participating_issue_fingerprints,
        claim,
    )
    severity = max(detection.severities or ["nit"], key=lambda value: SEVERITY_RANK[value])
    return {
        "conflict_id": conflict_id(fingerprint),
        "conflict_fingerprint": fingerprint,
        "conflict_type": "profile_conflict",
        "conflict_severity": severity,
        "participating_issue_ids": detection.participating_issue_ids,
        "conflict_claim": claim,
    }


def _participating_issue_fingerprints(conflict: dict[str, Any], issue_by_id: dict[str, dict[str, Any]]) -> list[str]:
    fingerprints = []
    for issue_id_value in conflict.get("participating_issue_ids", []):
        issue = issue_by_id.get(str(issue_id_value))
        if issue and isinstance(issue.get("issue_fingerprint"), str):
            fingerprints.append(issue["issue_fingerprint"])
    return sorted(fingerprints)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
