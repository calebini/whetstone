"""Multi-round fixture orchestration engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from whetstone.config import OrchestratorConfig
from whetstone.conflicts import ConflictTracker
from whetstone.declaration import render_convergence_declaration, write_convergence_declaration
from whetstone.evaluation import target_matrix_satisfied
from whetstone.hashing import draft_hash, semantic_changes
from whetstone.identity import SEVERITY_RANK, conflict_fingerprint, conflict_id
from whetstone.oscillation import OscillationTracker
from whetstone.reports import ReportWriter
from whetstone.runner import FixtureRunner, FixtureRoundResult
from whetstone.scheduler import PhaseScheduler, default_phase_1_scheduler, default_phase_2_scheduler
from whetstone.termination import TerminationCandidate, select_terminal_candidate


@dataclass(frozen=True)
class FixtureScriptStep:
    reviewer_feedback: dict[str, Any]
    editor_summary: dict[str, Any]
    draft_after: str | None = None
    declaration_accepted: bool = False
    unresolved_rubric_gaps: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class EngineResult:
    terminal_state: str
    round_number: int
    phase: str
    last_accepted_draft_hash: str | None
    report_path: Path | None = None


class FixtureEngine:
    """Drive Phase 1 and Phase 2 from scripted fixture artifacts."""

    def __init__(self, root: Path | str, config: OrchestratorConfig | None = None) -> None:
        self.root = Path(root)
        self.config = config or OrchestratorConfig.default(self.root)
        self.runner = FixtureRunner(self.root, self.config)
        self.report_writer = ReportWriter(self.root)

    def run(self, steps: Iterable[FixtureScriptStep], *, overwrite_rounds: bool = False) -> EngineResult:
        phase = "phase_1"
        scheduler: PhaseScheduler = default_phase_1_scheduler()
        last_accepted_draft_hash: str | None = None
        last_result: FixtureRoundResult | None = None
        phase_rounds = 0
        conflict_tracker = ConflictTracker()
        oscillation_tracker = OscillationTracker()
        oscillation_tracker.record_draft(
            round_number=0,
            draft_hash_value=draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            semantic_changes=[],
        )

        for round_number, step in enumerate(steps, start=1):
            phase_rounds += 1
            max_rounds = self.config.review_max_rounds if phase == "phase_1" else self.config.convergence.max_rounds
            if phase_rounds > max_rounds:
                return self._max_rounds_result(
                    phase=phase,
                    round_number=round_number - 1,
                    last_result=last_result,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                )

            expected_profile = scheduler.next_profile()
            if expected_profile is None:
                if phase == "phase_1":
                    phase = "phase_2"
                    phase_rounds = 1
                    scheduler = default_phase_2_scheduler()
                    expected_profile = scheduler.next_profile()
                if expected_profile is None:
                    return EngineResult("TARGET_NOT_REACHED", round_number - 1, phase, last_accepted_draft_hash)

            actual_profile = str(step.reviewer_feedback.get("profile", ""))
            if actual_profile != expected_profile:
                raise ValueError(f"round {round_number} expected profile {expected_profile!r}, got {actual_profile!r}")

            result = self.runner.run_round(
                round_number=round_number,
                reviewer_feedback=step.reviewer_feedback,
                editor_summary=step.editor_summary,
                draft_after=step.draft_after,
                overwrite=overwrite_rounds,
            )
            last_result = result

            blocker_count = _count(result.unresolved_issues, "blocker")
            major_count = _count(result.unresolved_issues, "major")
            scheduler.record_result(actual_profile, blocker_count=blocker_count, major_count=major_count)

            if result.accepted:
                last_accepted_draft_hash = result.draft_after_hash

            terminal_candidates: list[TerminationCandidate] = []
            draft_detection = oscillation_tracker.record_draft(
                round_number=round_number,
                draft_hash_value=result.draft_after_hash,
                semantic_changes=semantic_changes(
                    (result.round_dir / "draft_before.md").read_text(encoding="utf-8"),
                    (result.round_dir / "draft_after.md").read_text(encoding="utf-8"),
                ),
            )
            if draft_detection is not None and draft_detection.recommendation == "stop_iteration":
                report_path = self.report_writer.write_oscillation_report(
                    round_number=round_number,
                    detected=True,
                    oscillation_type=draft_detection.oscillation_type,
                    affected_sections=draft_detection.affected_sections,
                    suspected_feedback_ids=draft_detection.suspected_feedback_ids,
                    recommendation=draft_detection.recommendation,
                    oscillation_fingerprints=draft_detection.oscillation_fingerprints,
                    oscillation_opposition_keys=draft_detection.oscillation_opposition_keys,
                )
                terminal_candidates.append(TerminationCandidate("HALTED_OSCILLATION", round_number, phase, report_path))
            elif draft_detection is not None:
                self.report_writer.write_oscillation_report(
                    round_number=round_number,
                    detected=True,
                    oscillation_type=draft_detection.oscillation_type,
                    affected_sections=draft_detection.affected_sections,
                    suspected_feedback_ids=draft_detection.suspected_feedback_ids,
                    recommendation=draft_detection.recommendation,
                    oscillation_fingerprints=draft_detection.oscillation_fingerprints,
                    oscillation_opposition_keys=draft_detection.oscillation_opposition_keys,
                )

            feedback_detection = None
            if phase == "phase_2":
                feedback_detection = oscillation_tracker.record_phase2_feedback(
                    round_number=round_number,
                    reviewer_feedback=step.reviewer_feedback,
                )
                if feedback_detection is not None:
                    report_path = self.report_writer.write_oscillation_report(
                        round_number=round_number,
                        detected=True,
                        oscillation_type=feedback_detection.oscillation_type,
                        affected_sections=feedback_detection.affected_sections,
                        suspected_feedback_ids=feedback_detection.suspected_feedback_ids,
                        recommendation=feedback_detection.recommendation,
                        oscillation_fingerprints=feedback_detection.oscillation_fingerprints,
                        oscillation_opposition_keys=feedback_detection.oscillation_opposition_keys,
                    )
                    if feedback_detection.recommendation == "stop_iteration":
                        terminal_candidates.append(TerminationCandidate("HALTED_OSCILLATION", round_number, phase, report_path))
                    if feedback_detection.recommendation == "escalate_conflict":
                        conflict = _conflict_from_oscillation(feedback_detection)
                        conflict_report = self.report_writer.write_conflict_report(
                            round_number=round_number,
                            conflicts=[conflict],
                            exit_reason=f"{feedback_detection.oscillation_type} escalated for manual review",
                            terminal_state="HALTED_CONFLICT" if conflict["conflict_severity"] == "blocker" else None,
                        )
                        if conflict["conflict_severity"] == "blocker":
                            terminal_candidates.append(TerminationCandidate("HALTED_CONFLICT", round_number, phase, conflict_report))

            conflict_escalation = conflict_tracker.record_round(
                round_number=round_number,
                conflicts=step.conflicts,
                issues=result.unresolved_issues,
            )
            if conflict_escalation is not None:
                report_path = self.report_writer.write_conflict_report(
                    round_number=round_number,
                    conflicts=conflict_escalation.conflicts,
                    exit_reason=conflict_escalation.reason,
                    terminal_state="HALTED_CONFLICT" if conflict_escalation.blocker_level else None,
                )
                if conflict_escalation.blocker_level:
                    terminal_candidates.append(TerminationCandidate("HALTED_CONFLICT", round_number, phase, report_path))

            if phase == "phase_1" and scheduler.phase_complete(accepted_draft=result.accepted):
                phase = "phase_2"
                phase_rounds = 0
                scheduler = default_phase_2_scheduler()
                continue

            if phase == "phase_2":
                if target_matrix_satisfied(
                    target_phase=self.config.convergence.target_phase,
                    target_mode=self.config.convergence.target_mode,
                    issues=result.unresolved_issues,
                    unresolved_rubric_gaps=step.unresolved_rubric_gaps,
                    declaration_accepted=step.declaration_accepted,
                ):
                    declaration = render_convergence_declaration(
                        target_phase=self.config.convergence.target_phase,
                        target_mode=self.config.convergence.target_mode,
                        final_draft_hash=result.draft_after_hash,
                        rubric_content_hash="0" * 64,
                        unresolved_blockers_count=blocker_count,
                        unresolved_major_issues_count=major_count,
                        unresolved_rubric_gaps_count=len(step.unresolved_rubric_gaps),
                        reviewer_final_status="accepted",
                        declaration_status="accepted",
                    )
                    write_convergence_declaration(self.root / "convergence_declaration.md", declaration)
                    terminal_candidates.append(TerminationCandidate("CONVERGED", round_number, phase, None))

            selected = select_terminal_candidate(terminal_candidates)
            if selected is not None:
                if selected.phase == "phase_2" and selected.terminal_state in {"HALTED_CONFLICT", "HALTED_OSCILLATION"}:
                    self._write_phase2_halt_companion(
                        round_number=selected.round_number,
                        result=result,
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        terminal_state=selected.terminal_state,
                        exit_reason=f"{selected.terminal_state} halted Phase 2 before convergence",
                    )
                return EngineResult(
                    selected.terminal_state,
                    selected.round_number,
                    selected.phase,
                    last_accepted_draft_hash,
                    selected.report_path,
                )

        round_number = last_result.round_number if last_result else 0
        return self._max_rounds_result(
            phase=phase,
            round_number=round_number,
            last_result=last_result,
            last_accepted_draft_hash=last_accepted_draft_hash,
        )

    def _max_rounds_result(
        self,
        *,
        phase: str,
        round_number: int,
        last_result: FixtureRoundResult | None,
        last_accepted_draft_hash: str | None,
    ) -> EngineResult:
        unresolved = last_result.unresolved_issues if last_result else []
        blockers = [_issue_summary(issue) for issue in unresolved if issue["normalized_severity"] == "blocker"]
        majors = [_issue_summary(issue) for issue in unresolved if issue["normalized_severity"] == "major"]
        if phase == "phase_1":
            report_path = self.report_writer.write_technical_failure_report(
                round_number=max(round_number, 1),
                final_draft_path="./spec.md",
                unresolved_blockers=blockers,
                unresolved_major_issues=majors,
                unresolved_conflicts=[],
                unresolved_oscillation=None,
                last_accepted_draft_hash=last_accepted_draft_hash,
                exit_reason="max rounds or fixture script exhausted before Phase 1 completion",
                recommendation="manual_review_required",
            )
        else:
            report_path = self.report_writer.write_convergence_failure_report(
                round_number=max(round_number, 1),
                final_draft_path="./spec.md",
                final_declaration_path=None,
                target_phase=self.config.convergence.target_phase,
                target_mode=self.config.convergence.target_mode,
                unresolved_blockers=blockers,
                unresolved_major_issues=majors,
                unresolved_rubric_gaps=[],
                reviewer_final_status="not_run",
                last_accepted_draft_hash=last_accepted_draft_hash,
                exit_reason="max rounds or fixture script exhausted before convergence",
                recommendation="manual_review_required",
            )
        return EngineResult("TARGET_NOT_REACHED", round_number, phase, last_accepted_draft_hash, report_path)

    def _write_phase2_halt_companion(
        self,
        *,
        round_number: int,
        result: FixtureRoundResult,
        last_accepted_draft_hash: str | None,
        terminal_state: str,
        exit_reason: str,
    ) -> Path:
        blockers = [_issue_summary(issue) for issue in result.unresolved_issues if issue["normalized_severity"] == "blocker"]
        majors = [_issue_summary(issue) for issue in result.unresolved_issues if issue["normalized_severity"] == "major"]
        return self.report_writer.write_convergence_failure_report(
            round_number=round_number,
            final_draft_path=str(Path("rounds") / f"round-{round_number}" / "draft_after.md"),
            final_declaration_path=None,
            target_phase=self.config.convergence.target_phase,
            target_mode=self.config.convergence.target_mode,
            unresolved_blockers=blockers,
            unresolved_major_issues=majors,
            unresolved_rubric_gaps=[],
            reviewer_final_status="not_run",
            last_accepted_draft_hash=last_accepted_draft_hash,
            exit_reason=exit_reason,
            recommendation="manual_review_required",
            terminal_state=terminal_state,
        )


def fixture_steps_from_json(data: list[dict[str, Any]]) -> list[FixtureScriptStep]:
    return [
        FixtureScriptStep(
            reviewer_feedback=item["reviewer_feedback"],
            editor_summary=item["editor_summary"],
            draft_after=item.get("draft_after"),
            declaration_accepted=bool(item.get("declaration_accepted", False)),
            unresolved_rubric_gaps=list(item.get("unresolved_rubric_gaps", [])),
            conflicts=list(item.get("conflicts", [])),
        )
        for item in data
    ]


def _count(issues: Iterable[dict[str, Any]], severity: str) -> int:
    return sum(1 for issue in issues if issue.get("normalized_severity") == severity)


def _issue_summary(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_id": issue["issue_id"],
        "issue_fingerprint": issue["issue_fingerprint"],
        "normalized_severity": issue["normalized_severity"],
        "affected_sections": issue["affected_sections"],
        "claim": issue["claim"],
    }


def _conflict_from_oscillation(detection: Any) -> dict[str, Any]:
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
