"""Public client protocols."""

from __future__ import annotations

from typing import Protocol


class ReviewerClient(Protocol):
    def review(self, prompt: str) -> dict:
        """Return reviewer_feedback.json-compatible data."""


class EditorClient(Protocol):
    def revise(self, prompt: str) -> dict:
        """Return editor_summary.json-compatible data."""

