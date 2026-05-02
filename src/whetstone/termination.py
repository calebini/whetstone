"""Deterministic terminal-state precedence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PRECEDENCE = {
    "CONVERGED": 1,
    "HALTED_CONFLICT": 2,
    "HALTED_OSCILLATION": 3,
    "HALTED_ARTIFACT_INVALID": 4,
    "PAUSED_DECISION": 5,
    "TARGET_NOT_REACHED": 6,
}


@dataclass(frozen=True)
class TerminationCandidate:
    terminal_state: str
    round_number: int
    phase: str
    report_path: Path | None = None


def select_terminal_candidate(candidates: list[TerminationCandidate]) -> TerminationCandidate | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda candidate: PRECEDENCE[candidate.terminal_state])[0]

