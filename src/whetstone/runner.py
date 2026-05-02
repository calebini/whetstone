"""Fixture-mode Whetstone runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whetstone.artifacts import ArtifactStore
from whetstone.config import OrchestratorConfig
from whetstone.evaluation import accepted_draft
from whetstone.hashing import draft_hash, semantic_change_hash


@dataclass(frozen=True)
class FixtureRoundResult:
    round_number: int
    draft_before_hash: str
    draft_after_hash: str
    accepted: bool
    round_dir: Path
    unresolved_issues: list[dict[str, Any]]


class FixtureRunner:
    """Run one deterministic round from fixture reviewer/editor artifacts."""

    def __init__(self, root: Path | str, config: OrchestratorConfig | None = None) -> None:
        self.root = Path(root)
        self.config = config or OrchestratorConfig.default(self.root)
        self.store = ArtifactStore(self.root)

    def run_round(
        self,
        *,
        round_number: int,
        reviewer_feedback: dict[str, Any],
        editor_summary: dict[str, Any],
        draft_after: str | None = None,
        overwrite: bool = False,
    ) -> FixtureRoundResult:
        round_dir = self.store.begin_round(round_number, overwrite=overwrite)
        draft_before = self.store.read_spec()
        actual_before_hash = draft_hash(draft_before)
        draft_after_content = draft_after if draft_after is not None else draft_before
        actual_after_hash = draft_hash(draft_after_content)

        reviewer_feedback = dict(reviewer_feedback)
        reviewer_feedback["round_number"] = round_number
        reviewer_feedback["draft_hash"] = actual_before_hash

        editor_summary = dict(editor_summary)
        editor_summary["round_number"] = round_number
        editor_summary["draft_before_hash"] = actual_before_hash
        editor_summary["draft_after_hash"] = actual_after_hash

        unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
        unresolved_packet = {
            "round_number": round_number,
            "draft_hash": actual_after_hash,
            "unresolved_issues": unresolved,
        }
        prompt_snapshot = self._prompt_snapshot(
            profile=str(reviewer_feedback["profile"]),
            draft_hash_value=actual_before_hash,
            semantic_hash=semantic_change_hash(draft_before, draft_after_content),
        )

        self.store.write_round_text(round_number, "draft_before.md", draft_before)
        self.store.write_round_text(round_number, "draft_after.md", draft_after_content)
        self.store.write_round_text(round_number, "reviewer_working_notes.md", "Fixture-mode review.\n")
        self.store.write_round_json(round_number, "reviewer_feedback.json", reviewer_feedback, schema_name="reviewer_feedback")
        self.store.write_round_json(round_number, "editor_summary.json", editor_summary, schema_name="editor_summary")
        self.store.write_round_json(round_number, "unresolved_issues.json", unresolved_packet, schema_name="unresolved_issues")
        self.store.write_round_json(round_number, "profile_used.yaml", {"profile": reviewer_feedback["profile"]})
        self.store.write_round_json(round_number, "prompt_snapshot.json", prompt_snapshot)

        if draft_after_content != draft_before:
            self.store.write_spec(draft_after_content)

        return FixtureRoundResult(
            round_number=round_number,
            draft_before_hash=actual_before_hash,
            draft_after_hash=actual_after_hash,
            accepted=accepted_draft(unresolved),
            round_dir=round_dir,
            unresolved_issues=unresolved,
        )

    def _prompt_snapshot(self, *, profile: str, draft_hash_value: str, semantic_hash: str) -> dict[str, Any]:
        return {
            "prompt_text": "fixture-mode",
            "profile": profile,
            "client": asdict(self.config.reviewer),
            "version": self.config.reviewer.version,
            "model": self.config.reviewer.model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config_snapshot": {
                "review_max_rounds": self.config.review_max_rounds,
                "target_phase": self.config.convergence.target_phase,
                "target_mode": self.config.convergence.target_mode,
            },
            "rubric_content_hash": "0" * 64,
            "draft_hash": draft_hash_value,
            "semantic_change_hash": semantic_hash,
        }


def _unresolved_issues(reviewer_feedback: dict[str, Any], editor_summary: dict[str, Any]) -> list[dict[str, Any]]:
    resolved = set(editor_summary.get("resolved_issue_ids", []))
    unresolved_ids = set(editor_summary.get("unresolved_issue_ids", []))
    issues: list[dict[str, Any]] = []
    for feedback in reviewer_feedback.get("feedback", []):
        issue_id = feedback["issue_id"]
        if issue_id in resolved:
            continue
        if unresolved_ids and issue_id not in unresolved_ids:
            continue
        severity = feedback["normalized_severity"]
        issues.append(
            {
                "issue_id": issue_id,
                "issue_fingerprint": feedback["issue_fingerprint"],
                "normalized_severity": severity,
                "affected_sections": feedback["affected_sections"],
                "claim": feedback["claim"],
                "in_scope": bool(feedback.get("in_scope", True)),
                "blocking_acceptance": severity in {"blocker", "major"} and bool(feedback.get("in_scope", True)),
            }
        )
    return issues
