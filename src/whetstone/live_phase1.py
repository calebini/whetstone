"""Minimal live Phase 1 multi-round orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable

from whetstone.config import OrchestratorConfig
from whetstone.decisions import write_decision_intervention_request, write_decision_register
from whetstone.hashing import draft_hash
from whetstone.live import EditorClient, LiveRoundRunner, ReviewerClient
from whetstone.reports import ReportWriter
from whetstone.runner import _unresolved_issues
from whetstone.scheduler import default_phase_1_scheduler


@dataclass(frozen=True)
class LivePhase1Result:
    terminal_state: str
    round_number: int
    current_draft_hash: str
    last_accepted_draft_hash: str | None
    ready_for_phase_2: bool
    report_path: Path | None = None


class LivePhase1Runner:
    """Run the minimal non-resumable live Phase 1 loop."""

    def __init__(
        self,
        root: Path | str,
        config: OrchestratorConfig,
        *,
        reviewer_client: ReviewerClient | None = None,
        editor_client: EditorClient | None = None,
        draft_after_provider: Callable[[int, str, str], str | None] | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.root = Path(root)
        self.config = config
        self.reviewer_client = reviewer_client
        self.editor_client = editor_client
        self.draft_after_provider = draft_after_provider
        self.timeout_seconds = timeout_seconds
        self.report_writer = ReportWriter(self.root)

    def run(self, *, overwrite: bool = False) -> LivePhase1Result:
        if overwrite:
            _clear_top_level_run_artifacts(self.config.rounds_dir)
        scheduler = default_phase_1_scheduler()
        seen_hashes: list[str] = [draft_hash(self.config.spec_path.read_text(encoding="utf-8"))]
        last_accepted_draft_hash: str | None = None
        last_unresolved: list[dict[str, Any]] = []

        self._write_state(
            current_round=0,
            active_profile=None,
            current_draft_hash=seen_hashes[-1],
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_draft_hashes=seen_hashes,
            terminal_state=None,
            ready_for_phase_2=False,
        )

        for round_number in range(1, self.config.review_max_rounds + 1):
            profile = scheduler.next_profile()
            if profile is None:
                if last_accepted_draft_hash is not None:
                    return self._complete(
                        round_number=round_number - 1,
                        current_draft_hash=seen_hashes[-1],
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                    )
                break

            self._write_state(
                current_round=round_number,
                active_profile=profile,
                current_draft_hash=seen_hashes[-1],
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes,
                terminal_state=None,
                ready_for_phase_2=False,
            )

            try:
                draft_before_content = self.config.spec_path.read_text(encoding="utf-8")
                draft_after_content = (
                    self.draft_after_provider(round_number, profile, draft_before_content)
                    if self.draft_after_provider is not None
                    else None
                )
                result = LiveRoundRunner(
                    self.root,
                    self.config,
                    reviewer_client=self.reviewer_client,
                    editor_client=self.editor_client,
                    timeout_seconds=self.timeout_seconds,
                ).run_round(
                    round_number=round_number,
                    profile=profile,
                    phase="phase_1",
                    draft_after=draft_after_content,
                    apply=True,
                    overwrite=overwrite,
                )
            except ValueError:
                artifact_error = self.config.rounds_dir / "artifact_validation_error.json"
                if artifact_error.exists():
                    current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
                    self._write_state(
                        current_round=round_number,
                        active_profile=profile,
                        current_draft_hash=current_hash,
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                        terminal_state="HALTED_ARTIFACT_INVALID",
                        ready_for_phase_2=False,
                    )
                    return LivePhase1Result(
                        "HALTED_ARTIFACT_INVALID",
                        round_number,
                        current_hash,
                        last_accepted_draft_hash,
                        False,
                        artifact_error,
                    )
                raise
            round_dir = self.config.rounds_dir / f"round-{round_number}"
            reviewer_feedback = _read_json(round_dir / "reviewer_feedback.json")
            editor_summary = _read_json(round_dir / "editor_summary.json")
            decision_packet = _read_json(round_dir / "decision_points.json")
            last_unresolved = _unresolved_issues(reviewer_feedback, editor_summary)

            blocker_count = _count(last_unresolved, "blocker")
            major_count = _count(last_unresolved, "major")
            scheduler.record_result(profile, blocker_count=blocker_count, major_count=major_count)

            if result.accepted:
                last_accepted_draft_hash = result.draft_after_hash

            pause_points = [
                point
                for point in decision_packet.get("decision_points", [])
                if point.get("orchestrator_action") == "pause_for_input"
            ]
            if pause_points:
                intervention_path = write_decision_intervention_request(
                    rounds_dir=self.config.rounds_dir,
                    round_number=round_number,
                    profile=profile,
                    draft_hash_value=result.draft_after_hash,
                    decision_points=pause_points,
                )
                write_decision_register(
                    rounds_dir=self.config.rounds_dir,
                    mode=self.config.decision_points.mode,
                    terminal_state="PAUSED_DECISION",
                )
                self._write_state(
                    current_round=round_number,
                    active_profile=profile,
                    current_draft_hash=result.draft_after_hash,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    seen_draft_hashes=seen_hashes + [result.draft_after_hash],
                    terminal_state="PAUSED_DECISION",
                    ready_for_phase_2=False,
                )
                return LivePhase1Result(
                    "PAUSED_DECISION",
                    round_number,
                    result.draft_after_hash,
                    last_accepted_draft_hash,
                    False,
                    intervention_path,
                )

            self._append_history(
                round_number=round_number,
                profile=profile,
                before_hash=result.draft_before_hash,
                after_hash=result.draft_after_hash,
                accepted=result.accepted,
                blocker_count=blocker_count,
                major_count=major_count,
            )

            seen_hashes.append(result.draft_after_hash)
            if result.draft_after_hash in seen_hashes[:-1] and (blocker_count > 0 or major_count > 0):
                report_path = self.report_writer.write_oscillation_report(
                    round_number=round_number,
                    detected=True,
                    oscillation_type="cycle",
                    affected_sections=[],
                    suspected_feedback_ids=[],
                    recommendation="stop_iteration",
                )
                self._write_state(
                    current_round=round_number,
                    active_profile=profile,
                    current_draft_hash=result.draft_after_hash,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    seen_draft_hashes=seen_hashes,
                    terminal_state="HALTED_OSCILLATION",
                    ready_for_phase_2=False,
                )
                return LivePhase1Result(
                    "HALTED_OSCILLATION",
                    round_number,
                    result.draft_after_hash,
                    last_accepted_draft_hash,
                    False,
                    report_path,
                )

            phase_complete = scheduler.phase_complete(accepted_draft=result.accepted)
            self._write_state(
                current_round=round_number,
                active_profile=profile,
                current_draft_hash=result.draft_after_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes,
                terminal_state="PHASE_1_STABLE" if phase_complete else None,
                ready_for_phase_2=phase_complete,
            )
            if phase_complete:
                write_decision_register(
                    rounds_dir=self.config.rounds_dir,
                    mode=self.config.decision_points.mode,
                    terminal_state="PHASE_1_STABLE",
                )
                return LivePhase1Result(
                    "PHASE_1_STABLE",
                    round_number,
                    result.draft_after_hash,
                    last_accepted_draft_hash,
                    True,
                    None,
                )

        current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
        blockers = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "blocker"]
        majors = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "major"]
        report_path = self.report_writer.write_technical_failure_report(
            round_number=max(1, min(self.config.review_max_rounds, len(seen_hashes) - 1)),
            final_draft_path="./spec.md",
            unresolved_blockers=blockers,
            unresolved_major_issues=majors,
            unresolved_conflicts=[],
            unresolved_oscillation=None,
            last_accepted_draft_hash=last_accepted_draft_hash,
            exit_reason="Phase 1 max rounds reached before accepted stable draft",
            recommendation="manual_review_required",
        )
        self._write_state(
            current_round=max(1, min(self.config.review_max_rounds, len(seen_hashes) - 1)),
            active_profile=scheduler.next_profile(),
            current_draft_hash=current_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_draft_hashes=seen_hashes,
            terminal_state="TARGET_NOT_REACHED",
            ready_for_phase_2=False,
        )
        write_decision_register(
            rounds_dir=self.config.rounds_dir,
            mode=self.config.decision_points.mode,
            terminal_state="TARGET_NOT_REACHED",
        )
        return LivePhase1Result("TARGET_NOT_REACHED", len(seen_hashes) - 1, current_hash, last_accepted_draft_hash, False, report_path)

    def _complete(
        self,
        *,
        round_number: int,
        current_draft_hash: str,
        last_accepted_draft_hash: str,
        seen_draft_hashes: list[str],
    ) -> LivePhase1Result:
        self._write_state(
            current_round=round_number,
            active_profile=None,
            current_draft_hash=current_draft_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_draft_hashes=seen_draft_hashes,
            terminal_state="PHASE_1_STABLE",
            ready_for_phase_2=True,
        )
        write_decision_register(
            rounds_dir=self.config.rounds_dir,
            mode=self.config.decision_points.mode,
            terminal_state="PHASE_1_STABLE",
        )
        return LivePhase1Result("PHASE_1_STABLE", round_number, current_draft_hash, last_accepted_draft_hash, True, None)

    def _write_state(
        self,
        *,
        current_round: int,
        active_profile: str | None,
        current_draft_hash: str,
        last_accepted_draft_hash: str | None,
        seen_draft_hashes: list[str],
        terminal_state: str | None,
        ready_for_phase_2: bool,
    ) -> None:
        self.config.rounds_dir.mkdir(parents=True, exist_ok=True)
        packet = {
            "current_round": current_round,
            "phase": "phase_1",
            "active_profile": active_profile,
            "current_draft_hash": current_draft_hash,
            "last_accepted_draft_hash": last_accepted_draft_hash,
            "seen_draft_hashes": seen_draft_hashes,
            "terminal_state": terminal_state,
            "ready_for_phase_2": ready_for_phase_2,
            "resumable": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        (self.config.rounds_dir / "run_state.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _append_history(
        self,
        *,
        round_number: int,
        profile: str,
        before_hash: str,
        after_hash: str,
        accepted: bool,
        blocker_count: int,
        major_count: int,
    ) -> None:
        entry = (
            f"- Live Phase 1 round {round_number}: profile `{profile}`, "
            f"before `{before_hash}`, after `{after_hash}`, "
            f"accepted={str(accepted).lower()}, blockers={blocker_count}, majors={major_count}.\n"
        )
        with self.config.history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(entry)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _count(issues: list[dict[str, Any]], severity: str) -> int:
    return sum(1 for issue in issues if issue.get("normalized_severity") == severity)


def _issue_summary(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_id": issue["issue_id"],
        "issue_fingerprint": issue["issue_fingerprint"],
        "normalized_severity": issue["normalized_severity"],
        "affected_sections": issue["affected_sections"],
        "claim": issue["claim"],
    }


def _clear_top_level_run_artifacts(rounds_dir: Path) -> None:
    for filename in (
        "run_state.json",
        "technical_failure_report.json",
        "convergence_failure_report.json",
        "conflict_report.json",
        "oscillation_report.json",
        "artifact_validation_error.json",
        "config_validation_error.json",
        "decision_register.json",
        "decision_register.md",
        "decision_intervention_request.json",
    ):
        path = rounds_dir / filename
        if path.exists():
            path.unlink()
