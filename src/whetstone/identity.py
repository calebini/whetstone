"""Severity and identity primitives."""

from __future__ import annotations

import re
from typing import Iterable

from whetstone.hashing import sha256_text


SEVERITY_ORDER = ("nit", "minor", "major", "blocker")
SEVERITY_RANK = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}


def normalize_severity(*components: str | None) -> str:
    applicable = [component for component in components if component is not None]
    if not applicable:
        return "nit"
    return max(applicable, key=lambda severity: SEVERITY_RANK[severity])


def issue_fingerprint(
    issue_type: str,
    affected_sections: Iterable[str],
    invariant_violated: str | None,
    claim: str,
) -> str:
    payload = "\n".join(
        [
            _normalize_scalar(issue_type),
            _normalize_array(affected_sections, sort=False),
            _normalize_scalar(invariant_violated or ""),
            _normalize_scalar(claim),
        ]
    )
    return sha256_text(payload)


def issue_id(fingerprint: str) -> str:
    return f"iss_{fingerprint[:16]}"


def conflict_fingerprint(
    conflict_type: str,
    participating_issue_fingerprints: Iterable[str],
    conflict_claim: str,
) -> str:
    payload = "\n".join(
        [
            _normalize_scalar(conflict_type),
            _normalize_array(participating_issue_fingerprints, sort=True),
            _normalize_scalar(conflict_claim),
        ]
    )
    return sha256_text(payload)


def conflict_id(fingerprint: str) -> str:
    return f"con_{fingerprint[:16]}"


def rubric_gap_fingerprint(rubric_anchor: str, affected_sections: Iterable[str], claim: str) -> str:
    payload = "\n".join(
        [
            _normalize_scalar(rubric_anchor),
            _normalize_array(affected_sections, sort=False),
            _normalize_scalar(claim),
        ]
    )
    return sha256_text(payload)


def rubric_gap_id(fingerprint: str) -> str:
    return f"gap_{fingerprint[:16]}"


def oscillation_fingerprint(section_id: str, concern_type: str, direction: str, scope: str) -> str:
    payload = "|".join(
        [
            _normalize_scalar(section_id),
            _normalize_scalar(concern_type),
            _normalize_scalar(direction),
            _normalize_scalar(scope),
        ]
    )
    return sha256_text(payload)


def oscillation_opposition_key(section_id: str, concern_type: str, scope: str) -> str:
    payload = "|".join(
        [
            _normalize_scalar(section_id),
            _normalize_scalar(concern_type),
            _normalize_scalar(scope),
        ]
    )
    return sha256_text(payload)


def _normalize_scalar(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _normalize_array(values: Iterable[str], *, sort: bool) -> str:
    normalized = [_normalize_scalar(value) for value in values]
    if sort:
        normalized = sorted(normalized)
    return "\n".join(normalized)
