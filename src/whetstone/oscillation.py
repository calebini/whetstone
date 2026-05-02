"""Phase 2 oscillation key canonicalization."""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from collections.abc import Iterable, Mapping

from whetstone.hashing import SemanticChange
from whetstone.identity import oscillation_fingerprint, oscillation_opposition_key


class OscillationKeyError(ValueError):
    """Raised when reviewer-proposed oscillation identity cannot be canonicalized."""


OPPOSING_DIRECTIONS = {
    "add": "remove",
    "remove": "add",
    "constrain": "relax",
    "relax": "constrain",
}


@dataclass(frozen=True)
class OscillationDetection:
    oscillation_type: str
    recommendation: str
    affected_sections: list[str]
    suspected_feedback_ids: list[str]
    oscillation_fingerprints: list[str]
    oscillation_opposition_keys: list[str]
    severities: list[str] = field(default_factory=list)
    participating_issue_ids: list[str] = field(default_factory=list)
    participating_issue_fingerprints: list[str] = field(default_factory=list)


@dataclass
class _MechanicalState:
    polarity: str
    round_number: int


@dataclass
class _FeedbackState:
    direction: str
    severity: str
    fingerprint: str
    feedback_id: str
    issue_id: str
    issue_fingerprint: str
    section_id: str
    round_number: int


@dataclass
class _ReadditionState:
    present: bool = False
    removed_once: bool = False
    readded_once: bool = False
    feedback_id: str | None = None
    section_id: str | None = None


class OscillationTracker:
    """Track deterministic draft and Phase 2 feedback oscillation signals."""

    def __init__(self) -> None:
        self._draft_hash_rounds: dict[str, int] = {}
        self._mechanical: dict[str, _MechanicalState] = {}
        self._feedback: dict[str, _FeedbackState] = {}
        self._churn: dict[str, int] = {}
        self._readdition: dict[str, _ReadditionState] = {}

    def record_draft(
        self,
        *,
        round_number: int,
        draft_hash_value: str,
        semantic_changes: Iterable[SemanticChange],
    ) -> OscillationDetection | None:
        changes = list(semantic_changes)
        if draft_hash_value in self._draft_hash_rounds and changes:
            return OscillationDetection(
                oscillation_type="cycle",
                recommendation="stop_iteration",
                affected_sections=[],
                suspected_feedback_ids=[],
                oscillation_fingerprints=[],
                oscillation_opposition_keys=[],
            )
        self._draft_hash_rounds[draft_hash_value] = round_number

        for change in changes:
            previous = self._mechanical.get(change.mechanical_key)
            if (
                previous is not None
                and {previous.polarity, change.polarity} == {"add", "remove"}
            ):
                self._mechanical[change.mechanical_key] = _MechanicalState(change.polarity, round_number)
                return OscillationDetection(
                    oscillation_type="mechanical_churn",
                    recommendation="freeze_prior_decision",
                    affected_sections=[change.section_id],
                    suspected_feedback_ids=[],
                    oscillation_fingerprints=[],
                    oscillation_opposition_keys=[],
                )
            self._mechanical[change.mechanical_key] = _MechanicalState(change.polarity, round_number)
        return None

    def record_phase2_feedback(
        self,
        *,
        round_number: int,
        reviewer_feedback: Mapping[str, object],
        resolved_opposition_keys: set[str] | None = None,
    ) -> OscillationDetection | None:
        for key in resolved_opposition_keys or set():
            self._churn[key] = 0

        feedback_items = reviewer_feedback.get("feedback")
        if not isinstance(feedback_items, list):
            return None

        current_fingerprints = set()
        detections: list[OscillationDetection] = []
        for item in feedback_items:
            if not isinstance(item, dict):
                continue
            key = item.get("oscillation_key")
            if not isinstance(key, dict):
                continue
            fingerprint = str(key.get("fingerprint", ""))
            opposition_key = str(key.get("opposition_key", ""))
            direction = str(key.get("direction", ""))
            section_id = str(key.get("section_id", ""))
            severity = str(item.get("normalized_severity", "nit"))
            feedback_id = str(item.get("feedback_id", ""))
            issue_id = str(item.get("issue_id", ""))
            issue_fingerprint = str(item.get("issue_fingerprint", ""))
            current_fingerprints.add(fingerprint)

            previous = self._feedback.get(opposition_key)
            if previous is not None and OPPOSING_DIRECTIONS.get(previous.direction) == direction:
                severities = [previous.severity, severity]
                detections.append(
                    OscillationDetection(
                        oscillation_type="feedback_flip_flop",
                        recommendation="escalate_conflict" if any(value in {"blocker", "major"} for value in severities) else "freeze_prior_decision",
                        affected_sections=[section_id],
                        suspected_feedback_ids=[previous.feedback_id, feedback_id],
                        oscillation_fingerprints=[previous.fingerprint, fingerprint],
                        oscillation_opposition_keys=[opposition_key],
                        severities=severities,
                        participating_issue_ids=[previous.issue_id, issue_id],
                        participating_issue_fingerprints=[previous.issue_fingerprint, issue_fingerprint],
                    )
                )

            if direction in {"modify", "clarify"}:
                self._churn[opposition_key] = self._churn.get(opposition_key, 0) + 1
                if self._churn[opposition_key] >= 3:
                    detections.append(
                        OscillationDetection(
                            oscillation_type="feedback_churn",
                            recommendation="escalate_conflict",
                            affected_sections=[section_id],
                            suspected_feedback_ids=[feedback_id],
                            oscillation_fingerprints=[fingerprint],
                            oscillation_opposition_keys=[opposition_key],
                            severities=[severity],
                            participating_issue_ids=[issue_id],
                            participating_issue_fingerprints=[issue_fingerprint],
                        )
                    )
            elif opposition_key:
                self._churn.setdefault(opposition_key, 0)

            readdition = self._readdition.setdefault(fingerprint, _ReadditionState())
            if not readdition.present and readdition.removed_once:
                recommendation = "stop_iteration" if readdition.readded_once else "continue_once"
                readdition.readded_once = True
                detections.append(
                    OscillationDetection(
                        oscillation_type="feedback_re_addition",
                        recommendation=recommendation,
                        affected_sections=[section_id],
                        suspected_feedback_ids=[feedback_id],
                        oscillation_fingerprints=[fingerprint],
                        oscillation_opposition_keys=[opposition_key],
                        severities=[severity],
                        participating_issue_ids=[issue_id],
                        participating_issue_fingerprints=[issue_fingerprint],
                    )
                )
            readdition.present = True
            readdition.feedback_id = feedback_id
            readdition.section_id = section_id

            self._feedback[opposition_key] = _FeedbackState(
                direction=direction,
                severity=severity,
                fingerprint=fingerprint,
                feedback_id=feedback_id,
                issue_id=issue_id,
                issue_fingerprint=issue_fingerprint,
                section_id=section_id,
                round_number=round_number,
            )

        for fingerprint, state in self._readdition.items():
            if state.present and fingerprint not in current_fingerprints:
                state.present = False
                state.removed_once = True

        return _highest_precedence_detection(detections)


def canonicalize_phase2_feedback(artifact: Mapping[str, object], allowed_section_ids: Iterable[str]) -> dict:
    """Return a copy with orchestrator-computed oscillation identity fields."""

    allowed = set(allowed_section_ids)
    canonical = deepcopy(dict(artifact))
    feedback_items = canonical.get("feedback")
    if not isinstance(feedback_items, list):
        raise OscillationKeyError("feedback must be a list")
    for index, item in enumerate(feedback_items):
        if not isinstance(item, dict):
            raise OscillationKeyError(f"feedback[{index}] must be an object")
        key = item.get("oscillation_key")
        if not isinstance(key, dict):
            raise OscillationKeyError(f"feedback[{index}].oscillation_key must be an object")
        section_id = _required_string(key, "section_id", index)
        concern_type = _required_string(key, "concern_type", index)
        direction = _required_string(key, "direction", index)
        scope = _required_string(key, "scope", index)
        if section_id not in allowed:
            raise OscillationKeyError(
                f"feedback[{index}].oscillation_key.section_id {section_id!r} is not in the canonical section index"
            )
        item["oscillation_key"] = {
            "section_id": section_id,
            "concern_type": concern_type,
            "direction": direction,
            "scope": scope,
            "fingerprint": oscillation_fingerprint(section_id, concern_type, direction, scope),
            "opposition_key": oscillation_opposition_key(section_id, concern_type, scope),
        }
    return canonical


def _required_string(key: Mapping[str, object], field: str, index: int) -> str:
    value = key.get(field)
    if not isinstance(value, str) or not value.strip():
        raise OscillationKeyError(f"feedback[{index}].oscillation_key.{field} must be a non-empty string")
    return value


def _highest_precedence_detection(detections: list[OscillationDetection]) -> OscillationDetection | None:
    if not detections:
        return None
    order = {
        "stop_iteration": 0,
        "escalate_conflict": 1,
        "freeze_prior_decision": 2,
        "continue_once": 3,
    }
    return sorted(detections, key=lambda detection: order[detection.recommendation])[0]
