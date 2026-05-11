"""Minimal live Phase 1 multi-round orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable

from whetstone.config import OrchestratorConfig
from whetstone.contract_surface import ContractSurfacePolicy, maybe_write_contract_surface_report, update_contract_surface_lifecycle
from whetstone.decisions import write_decision_intervention_request, write_decision_register
from whetstone.hashing import draft_hash
from whetstone.live import EditorClient, LiveRoundRunner, ReviewerClient, run_telemetry_totals
from whetstone.reports import ReportWriter
from whetstone.runner import _unresolved_issues
from whetstone.run_state import effective_run_config
from whetstone.scheduler import (
    PhaseScheduler,
    default_phase_1_scheduler,
    default_phase_2_scheduler,
    resolved_phase_1_profile_budgets,
    resolved_phase_2_profile_budgets,
)


_VERSION_IN_LINE_RE = re.compile(r"\bv?\d+(?:\.\d+)+\b")


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
        scheduler_factory: Callable[[dict[str, int]], PhaseScheduler] | None = None,
        state_review_profile_budgets: dict[str, int] | None = None,
        run_mode: str = "phase_1",
        completion_terminal_state: str = "PHASE_1_STABLE",
        completion_ready_for_phase_2: bool = True,
        timeout_seconds: int | None = None,
    ) -> None:
        self.root = Path(root)
        self.config = config
        self.reviewer_client = reviewer_client
        self.editor_client = editor_client
        self.draft_after_provider = draft_after_provider
        self.scheduler_factory = scheduler_factory
        self.state_review_profile_budgets = state_review_profile_budgets
        self.run_mode = run_mode
        self.completion_terminal_state = completion_terminal_state
        self.completion_ready_for_phase_2 = completion_ready_for_phase_2
        self.timeout_seconds = timeout_seconds
        self.report_writer = ReportWriter(self.root)

    def run(self, *, overwrite: bool = False) -> LivePhase1Result:
        if self.config.review_mode == "vertical" and self.scheduler_factory is None:
            return self._run_vertical(overwrite=overwrite)
        if overwrite:
            _clear_top_level_run_artifacts(self.config.rounds_dir)
        scheduler = (
            self.scheduler_factory(self.config.review_profile_budgets)
            if self.scheduler_factory is not None
            else default_phase_1_scheduler(self.config.review_profile_budgets)
        )
        seen_hashes: list[str] = [draft_hash(self.config.spec_path.read_text(encoding="utf-8"))]
        last_accepted_draft_hash: str | None = None
        last_unresolved: list[dict[str, Any]] = []
        last_reviewer_findings: dict[str, Any] | None = None

        self._write_state(
            current_round=0,
            active_profile=None,
            current_draft_hash=seen_hashes[-1],
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_draft_hashes=seen_hashes,
            terminal_state=None,
            ready_for_phase_2=False,
        )

        total_round_budget = scheduler.total_round_budget()
        for round_number in range(1, total_round_budget + 1):
            profile = scheduler.next_profile()
            if profile is None:
                accepted_current_draft = last_accepted_draft_hash == seen_hashes[-1]
                if scheduler.phase_complete(accepted_draft=accepted_current_draft) and last_accepted_draft_hash is not None:
                    return self._complete(
                        round_number=round_number - 1,
                        current_draft_hash=seen_hashes[-1],
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                    )
                if _soft_budget_policy(self.config) and scheduler.sweep_complete():
                    return self._sweep_complete_with_residuals(
                        round_number=round_number - 1,
                        current_draft_hash=seen_hashes[-1],
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                        scheduler=scheduler,
                        last_unresolved=last_unresolved,
                        last_reviewer_findings=last_reviewer_findings,
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
                    error_packet = _read_json(artifact_error)
                    terminal_state = str(error_packet.get("terminal_state", "HALTED_ARTIFACT_INVALID"))
                    current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
                    self._write_state(
                        current_round=round_number,
                        active_profile=profile,
                        current_draft_hash=current_hash,
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                        terminal_state=terminal_state,
                        ready_for_phase_2=False,
                    )
                    write_decision_register(
                        rounds_dir=self.config.rounds_dir,
                        mode=self.config.decision_points.mode,
                        terminal_state=terminal_state,
                    )
                    return LivePhase1Result(
                        terminal_state,
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

            reviewer_blocker_count = _reviewer_count(reviewer_feedback, "blocker")
            reviewer_major_count = _reviewer_count(reviewer_feedback, "major")
            last_reviewer_findings = _last_reviewer_findings(
                round_number=round_number,
                profile=profile,
                reviewer_feedback=reviewer_feedback,
                blocker_count=reviewer_blocker_count,
                major_count=reviewer_major_count,
            )
            reviewer_clean = reviewer_blocker_count == 0 and reviewer_major_count == 0
            mutation_requires_verification = reviewer_clean and _mutation_requires_verification(
                round_dir=round_dir,
                editor_summary=editor_summary,
                spec_mutated=result.spec_mutated,
            )
            unresolved_blocker_count = _count(last_unresolved, "blocker")
            unresolved_major_count = _count(last_unresolved, "major")
            scheduler.record_result(
                profile,
                blocker_count=reviewer_blocker_count,
                major_count=reviewer_major_count + (1 if mutation_requires_verification else 0),
            )

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
                blocker_count=unresolved_blocker_count,
                major_count=unresolved_major_count,
            )
            maybe_write_contract_surface_report(
                rounds_dir=self.config.rounds_dir,
                current_round=round_number,
                profile=profile,
                policy=_contract_surface_policy(self.config),
            )
            update_contract_surface_lifecycle(rounds_dir=self.config.rounds_dir)

            seen_hashes.append(result.draft_after_hash)
            if result.draft_after_hash in seen_hashes[:-1] and (reviewer_blocker_count > 0 or reviewer_major_count > 0):
                report_path = self.report_writer.write_oscillation_report(
                    round_number=round_number,
                    detected=True,
                    oscillation_type="cycle",
                    affected_sections=[],
                    suspected_feedback_ids=[],
                    recommendation="stop_iteration",
                )
                if _soft_budget_policy(self.config):
                    if scheduler.active_profile() == profile:
                        scheduler.force_advance_current(residual_status="halted_oscillation")
                    self._write_state(
                        current_round=round_number,
                        active_profile=scheduler.next_profile(),
                        current_draft_hash=result.draft_after_hash,
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                        terminal_state=None,
                        ready_for_phase_2=False,
                    )
                    continue
                self._write_state(
                    current_round=round_number,
                    active_profile=profile,
                    current_draft_hash=result.draft_after_hash,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    seen_draft_hashes=seen_hashes,
                    terminal_state="HALTED_OSCILLATION",
                    ready_for_phase_2=False,
                )
                write_decision_register(
                    rounds_dir=self.config.rounds_dir,
                    mode=self.config.decision_points.mode,
                    terminal_state="HALTED_OSCILLATION",
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
                terminal_state=self.completion_terminal_state if phase_complete else None,
                ready_for_phase_2=self.completion_ready_for_phase_2 if phase_complete else False,
            )
            if phase_complete:
                write_decision_register(
                    rounds_dir=self.config.rounds_dir,
                    mode=self.config.decision_points.mode,
                    terminal_state=self.completion_terminal_state,
                )
                update_contract_surface_lifecycle(rounds_dir=self.config.rounds_dir, terminal=True)
                return LivePhase1Result(
                    self.completion_terminal_state,
                    round_number,
                    result.draft_after_hash,
                    last_accepted_draft_hash,
                    self.completion_ready_for_phase_2,
                    None,
                )

        current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
        blockers = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "blocker"]
        majors = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "major"]
        report_path = self.report_writer.write_technical_failure_report(
            round_number=max(1, min(total_round_budget, len(seen_hashes) - 1)),
            final_draft_path="./spec.md",
            unresolved_blockers=blockers,
            unresolved_major_issues=majors,
            unresolved_conflicts=[],
            unresolved_oscillation=None,
            last_accepted_draft_hash=last_accepted_draft_hash,
            exit_reason="Phase 1 profile round budgets exhausted before reviewer-verified stable draft",
            recommendation="manual_review_required",
            profile_status=scheduler.status(),
            last_reviewer_findings=last_reviewer_findings,
            terminal_state="PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS" if _soft_budget_policy(self.config) and scheduler.sweep_complete() else "TARGET_NOT_REACHED",
        )
        terminal_state = "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS" if _soft_budget_policy(self.config) and scheduler.sweep_complete() else "TARGET_NOT_REACHED"
        self._write_state(
            current_round=max(1, min(total_round_budget, len(seen_hashes) - 1)),
            active_profile=scheduler.next_profile(),
            current_draft_hash=current_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_draft_hashes=seen_hashes,
            terminal_state=terminal_state,
            ready_for_phase_2=False,
        )
        write_decision_register(
            rounds_dir=self.config.rounds_dir,
            mode=self.config.decision_points.mode,
            terminal_state=terminal_state,
        )
        return LivePhase1Result(terminal_state, len(seen_hashes) - 1, current_hash, last_accepted_draft_hash, False, report_path)

    def _run_vertical(self, *, overwrite: bool = False) -> LivePhase1Result:
        if overwrite:
            _clear_top_level_run_artifacts(self.config.rounds_dir)
        profiles = ["structural_integrity", "determinism", "operability"]
        budgets = resolved_phase_1_profile_budgets(self.config.review_profile_budgets)
        max_cycles = max(budgets.values())
        profile_state = {
            profile: {
                "profile": profile,
                "clean": False,
                "rounds_used": 0,
                "round_budget": budgets[profile],
                "exhausted": False,
                "residual_status": None,
                "active": False,
                "verified_draft_hash": None,
            }
            for profile in profiles
        }
        seen_hashes: list[str] = [draft_hash(self.config.spec_path.read_text(encoding="utf-8"))]
        last_accepted_draft_hash: str | None = None
        last_unresolved: list[dict[str, Any]] = []
        last_reviewer_findings: dict[str, Any] | None = None
        round_number = 0
        self._write_state(
            current_round=0,
            active_profile=None,
            current_draft_hash=seen_hashes[-1],
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_draft_hashes=seen_hashes,
            terminal_state=None,
            ready_for_phase_2=False,
        )

        for _cycle in range(1, max_cycles + 1):
            merged_feedback: list[dict[str, Any]] = []
            reviewer_packets: list[dict[str, Any]] = []
            cycle_clean = True
            draft_hash_at_cycle_start = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))

            for profile in profiles:
                if profile_state[profile]["rounds_used"] >= profile_state[profile]["round_budget"]:
                    continue
                round_number += 1
                self._write_state(
                    current_round=round_number,
                    active_profile=profile,
                    current_draft_hash=draft_hash_at_cycle_start,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    seen_draft_hashes=seen_hashes,
                    terminal_state=None,
                    ready_for_phase_2=False,
                )
                try:
                    review_result = LiveRoundRunner(
                        self.root,
                        self.config,
                        reviewer_client=self.reviewer_client,
                        editor_client=self.editor_client,
                        timeout_seconds=self.timeout_seconds,
                    ).run_review_only_round(
                        round_number=round_number,
                        profile=profile,
                        phase="phase_1",
                        overwrite=overwrite,
                    )
                except ValueError:
                    artifact_error = self.config.rounds_dir / "artifact_validation_error.json"
                    if artifact_error.exists():
                        error_packet = _read_json(artifact_error)
                        terminal_state = str(error_packet.get("terminal_state", "HALTED_ARTIFACT_INVALID"))
                        current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
                        self._write_state(
                            current_round=round_number,
                            active_profile=profile,
                            current_draft_hash=current_hash,
                            last_accepted_draft_hash=last_accepted_draft_hash,
                            seen_draft_hashes=seen_hashes,
                            terminal_state=terminal_state,
                            ready_for_phase_2=False,
                        )
                        write_decision_register(
                            rounds_dir=self.config.rounds_dir,
                            mode=self.config.decision_points.mode,
                            terminal_state=terminal_state,
                        )
                        return LivePhase1Result(terminal_state, round_number, current_hash, last_accepted_draft_hash, False, artifact_error)
                    raise
                reviewer_feedback = _read_json(review_result.round_dir / "reviewer_feedback.json")
                reviewer_packets.append(reviewer_feedback)
                blocker_count = _reviewer_count(reviewer_feedback, "blocker")
                major_count = _reviewer_count(reviewer_feedback, "major")
                profile_state[profile]["rounds_used"] = int(profile_state[profile]["rounds_used"]) + 1
                profile_state[profile]["clean"] = blocker_count == 0 and major_count == 0
                profile_state[profile]["verified_draft_hash"] = review_result.draft_after_hash
                profile_state[profile]["exhausted"] = (
                    not profile_state[profile]["clean"]
                    and profile_state[profile]["rounds_used"] >= profile_state[profile]["round_budget"]
                )
                profile_state[profile]["residual_status"] = "exhausted_with_residuals" if profile_state[profile]["exhausted"] else None
                cycle_clean = cycle_clean and bool(profile_state[profile]["clean"])
                last_reviewer_findings = _last_reviewer_findings(
                    round_number=round_number,
                    profile=profile,
                    reviewer_feedback=reviewer_feedback,
                    blocker_count=blocker_count,
                    major_count=major_count,
                )
                for issue in reviewer_feedback.get("feedback", []):
                    merged_feedback.append({**issue, "feedback_id": f"{profile}:{issue.get('feedback_id')}"})
                self._append_history(
                    round_number=round_number,
                    profile=profile,
                    before_hash=review_result.draft_before_hash,
                    after_hash=review_result.draft_after_hash,
                    accepted=not reviewer_feedback.get("feedback"),
                    blocker_count=blocker_count,
                    major_count=major_count,
                )

            if cycle_clean and not merged_feedback:
                current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
                last_accepted_draft_hash = current_hash
                return self._complete(
                    round_number=round_number,
                    current_draft_hash=current_hash,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    seen_draft_hashes=seen_hashes,
                )

            if merged_feedback:
                round_number += 1
                editor_profile = "vertical"
                draft_before = self.config.spec_path.read_text(encoding="utf-8")
                draft_before_hash = draft_hash(draft_before)
                synthetic_feedback = {
                    "round_number": round_number,
                    "profile": editor_profile,
                    "reviewer": {"name": "whetstone-vertical-merge", "version": "1.0", "model": "orchestrator"},
                    "draft_hash": draft_before_hash,
                    "feedback": merged_feedback,
                }
                round_dir = LiveRoundRunner(self.root, self.config).store.begin_round(round_number, overwrite=overwrite)
                round_dir.joinpath("draft_before.md").write_text(draft_before, encoding="utf-8")
                round_dir.joinpath("draft_after.md").write_text(draft_before, encoding="utf-8")
                round_dir.joinpath("profile_used.yaml").write_text(
                    json.dumps({"profile": editor_profile, "round_kind": "consolidated_editor"}, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                round_dir.joinpath("reviewer_feedback.json").write_text(json.dumps(synthetic_feedback, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                result = LiveRoundRunner(
                    self.root,
                    self.config,
                    reviewer_client=self.reviewer_client,
                    editor_client=self.editor_client,
                    timeout_seconds=self.timeout_seconds,
                ).resume_editor_round(round_number=round_number, profile=editor_profile, phase="phase_1", apply=True, start_attempt_number=1)
                editor_summary = _read_json(round_dir / "editor_summary.json")
                last_unresolved = _unresolved_issues(synthetic_feedback, editor_summary)
                if result.accepted:
                    last_accepted_draft_hash = result.draft_after_hash
                seen_hashes.append(result.draft_after_hash)
                self._append_history(
                    round_number=round_number,
                    profile=editor_profile,
                    before_hash=result.draft_before_hash,
                    after_hash=result.draft_after_hash,
                    accepted=result.accepted,
                    blocker_count=_count(last_unresolved, "blocker"),
                    major_count=_count(last_unresolved, "major"),
                )
                maybe_write_contract_surface_report(
                    rounds_dir=self.config.rounds_dir,
                    current_round=round_number,
                    profile=editor_profile,
                    policy=_contract_surface_policy(self.config),
                )
                update_contract_surface_lifecycle(rounds_dir=self.config.rounds_dir)
                if result.draft_after_hash in seen_hashes[:-1] and not result.accepted:
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
                        active_profile=editor_profile,
                        current_draft_hash=result.draft_after_hash,
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                        terminal_state="HALTED_OSCILLATION",
                        ready_for_phase_2=False,
                    )
                    write_decision_register(
                        rounds_dir=self.config.rounds_dir,
                        mode=self.config.decision_points.mode,
                        terminal_state="HALTED_OSCILLATION",
                    )
                    return LivePhase1Result("HALTED_OSCILLATION", round_number, result.draft_after_hash, last_accepted_draft_hash, False, report_path)
                self._write_state(
                    current_round=round_number,
                    active_profile=editor_profile,
                    current_draft_hash=result.draft_after_hash,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    seen_draft_hashes=seen_hashes,
                    terminal_state=None,
                    ready_for_phase_2=False,
                )

        current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
        profile_status = _vertical_profile_status(profile_state, current_draft_hash=current_hash)
        if _vertical_closeout_eligible(
            current_hash=current_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            last_unresolved=last_unresolved,
            profile_status=profile_status,
        ):
            closeout_result = self._run_vertical_closeout_check(
                start_round=round_number + 1,
                profile_state=profile_state,
                seen_hashes=seen_hashes,
                last_accepted_draft_hash=last_accepted_draft_hash,
                overwrite=overwrite,
            )
            if closeout_result["terminal_state"] == "PHASE_1_STABLE":
                return self._complete(
                    round_number=closeout_result["round_number"],
                    current_draft_hash=closeout_result["current_hash"],
                    last_accepted_draft_hash=closeout_result["last_accepted_draft_hash"],
                    seen_draft_hashes=seen_hashes,
                )
            if closeout_result["terminal_state"] is not None:
                return LivePhase1Result(
                    closeout_result["terminal_state"],
                    closeout_result["round_number"],
                    closeout_result["current_hash"],
                    last_accepted_draft_hash,
                    False,
                    self.config.rounds_dir / "artifact_validation_error.json",
                )
            round_number = closeout_result["round_number"]
            current_hash = closeout_result["current_hash"]
            profile_status = closeout_result["profile_status"]
            last_unresolved = closeout_result["last_unresolved"]
            last_reviewer_findings = closeout_result["last_reviewer_findings"]
        blockers = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "blocker"]
        majors = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "major"]
        report_path = self.report_writer.write_technical_failure_report(
            round_number=max(1, round_number),
            final_draft_path="./spec.md",
            unresolved_blockers=blockers,
            unresolved_major_issues=majors,
            unresolved_conflicts=[],
            unresolved_oscillation=None,
            last_accepted_draft_hash=last_accepted_draft_hash,
            exit_reason="Phase 1 vertical review mode exhausted before reviewer-verified stable draft",
            recommendation="manual_review_required",
            profile_status=profile_status,
            last_reviewer_findings=last_reviewer_findings,
            terminal_state="TARGET_NOT_REACHED",
        )
        self._write_state(
            current_round=round_number,
            active_profile=None,
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
        return LivePhase1Result("TARGET_NOT_REACHED", round_number, current_hash, last_accepted_draft_hash, False, report_path)

    def _run_vertical_closeout_check(
        self,
        *,
        start_round: int,
        profile_state: dict[str, dict[str, Any]],
        seen_hashes: list[str],
        last_accepted_draft_hash: str | None,
        overwrite: bool,
    ) -> dict[str, Any]:
        profiles = ["structural_integrity", "determinism", "operability"]
        round_number = start_round - 1
        closeout_unresolved: list[dict[str, Any]] = []
        last_reviewer_findings: dict[str, Any] | None = None
        for profile in profiles:
            current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
            round_number += 1
            self._write_state(
                current_round=round_number,
                active_profile=profile,
                current_draft_hash=current_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes,
                terminal_state=None,
                ready_for_phase_2=False,
            )
            try:
                review_result = LiveRoundRunner(
                    self.root,
                    self.config,
                    reviewer_client=self.reviewer_client,
                    editor_client=self.editor_client,
                    timeout_seconds=self.timeout_seconds,
                ).run_review_only_round(
                    round_number=round_number,
                    profile=profile,
                    phase="phase_1",
                    overwrite=overwrite,
                )
            except ValueError:
                artifact_error = self.config.rounds_dir / "artifact_validation_error.json"
                if artifact_error.exists():
                    error_packet = _read_json(artifact_error)
                    terminal_state = str(error_packet.get("terminal_state", "HALTED_ARTIFACT_INVALID"))
                    current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
                    self._write_state(
                        current_round=round_number,
                        active_profile=profile,
                        current_draft_hash=current_hash,
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                        terminal_state=terminal_state,
                        ready_for_phase_2=False,
                    )
                    return {
                        "terminal_state": terminal_state,
                        "round_number": round_number,
                        "current_hash": current_hash,
                        "last_accepted_draft_hash": last_accepted_draft_hash,
                        "profile_status": _vertical_profile_status(profile_state, current_draft_hash=current_hash),
                        "last_unresolved": closeout_unresolved,
                        "last_reviewer_findings": last_reviewer_findings,
                    }
                raise
            reviewer_feedback = _read_json(review_result.round_dir / "reviewer_feedback.json")
            editor_summary = _read_json(review_result.round_dir / "editor_summary.json")
            unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
            closeout_unresolved.extend(unresolved)
            blocker_count = _reviewer_count(reviewer_feedback, "blocker")
            major_count = _reviewer_count(reviewer_feedback, "major")
            state = profile_state[profile]
            state["rounds_used"] = int(state["rounds_used"]) + 1
            state["clean"] = blocker_count == 0 and major_count == 0
            state["verified_draft_hash"] = review_result.draft_after_hash
            state["exhausted"] = not state["clean"]
            state["residual_status"] = "exhausted_with_residuals" if state["exhausted"] else None
            last_reviewer_findings = _last_reviewer_findings(
                round_number=round_number,
                profile=profile,
                reviewer_feedback=reviewer_feedback,
                blocker_count=blocker_count,
                major_count=major_count,
            )
            self._append_history(
                round_number=round_number,
                profile=profile,
                before_hash=review_result.draft_before_hash,
                after_hash=review_result.draft_after_hash,
                accepted=blocker_count == 0 and major_count == 0,
                blocker_count=blocker_count,
                major_count=major_count,
            )
        current_hash = draft_hash(self.config.spec_path.read_text(encoding="utf-8"))
        profile_status = _vertical_profile_status(profile_state, current_draft_hash=current_hash)
        terminal_state = None
        if (
            last_accepted_draft_hash == current_hash
            and not profile_status["unverified_profiles"]
            and not profile_status["exhausted_profiles"]
            and not _has_serious_issues(closeout_unresolved)
        ):
            terminal_state = "PHASE_1_STABLE"
        return {
            "terminal_state": terminal_state,
            "round_number": round_number,
            "current_hash": current_hash,
            "last_accepted_draft_hash": last_accepted_draft_hash,
            "profile_status": profile_status,
            "last_unresolved": closeout_unresolved,
            "last_reviewer_findings": last_reviewer_findings,
        }

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
            terminal_state=self.completion_terminal_state,
            ready_for_phase_2=self.completion_ready_for_phase_2,
        )
        write_decision_register(
            rounds_dir=self.config.rounds_dir,
            mode=self.config.decision_points.mode,
            terminal_state=self.completion_terminal_state,
        )
        update_contract_surface_lifecycle(rounds_dir=self.config.rounds_dir, terminal=True)
        return LivePhase1Result(
            self.completion_terminal_state,
            round_number,
            current_draft_hash,
            last_accepted_draft_hash,
            self.completion_ready_for_phase_2,
            None,
        )

    def _sweep_complete_with_residuals(
        self,
        *,
        round_number: int,
        current_draft_hash: str,
        last_accepted_draft_hash: str | None,
        seen_draft_hashes: list[str],
        scheduler: Any,
        last_unresolved: list[dict[str, Any]],
        last_reviewer_findings: dict[str, Any] | None,
    ) -> LivePhase1Result:
        blockers = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "blocker"]
        majors = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "major"]
        report_path = self.report_writer.write_technical_failure_report(
            round_number=max(1, round_number),
            final_draft_path="./spec.md",
            unresolved_blockers=blockers,
            unresolved_major_issues=majors,
            unresolved_conflicts=[],
            unresolved_oscillation=None,
            last_accepted_draft_hash=last_accepted_draft_hash,
            exit_reason="Phase 1 sweep completed with residual unverified or non-clean profiles",
            recommendation="manual_review_required",
            profile_status=scheduler.status(),
            last_reviewer_findings=last_reviewer_findings,
            terminal_state="PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS",
        )
        self._write_state(
            current_round=round_number,
            active_profile=None,
            current_draft_hash=current_draft_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_draft_hashes=seen_draft_hashes,
            terminal_state="PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS",
            ready_for_phase_2=False,
        )
        write_decision_register(
            rounds_dir=self.config.rounds_dir,
            mode=self.config.decision_points.mode,
            terminal_state="PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS",
        )
        update_contract_surface_lifecycle(rounds_dir=self.config.rounds_dir, terminal=True)
        return LivePhase1Result(
            "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS",
            round_number,
            current_draft_hash,
            last_accepted_draft_hash,
            False,
            report_path,
        )

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
        convergence_round_budget = default_phase_2_scheduler(self.config.convergence_profile_budgets).total_round_budget()
        review_profile_budgets = (
            self.state_review_profile_budgets
            if self.state_review_profile_budgets is not None
            else resolved_phase_1_profile_budgets(self.config.review_profile_budgets)
        )
        review_round_budget = sum(review_profile_budgets.values())
        if self.config.review_mode == "vertical" and review_profile_budgets:
            review_round_budget += max(review_profile_budgets.values())
        convergence_profile_budgets = resolved_phase_2_profile_budgets(self.config.convergence_profile_budgets)
        previous_state = _read_json_object(self.config.rounds_dir / "run_state.json")
        budget_extensions = []
        if previous_state and isinstance(previous_state.get("budget_extensions"), list):
            budget_extensions = previous_state["budget_extensions"]
        budget_resumable_states = {"TARGET_NOT_REACHED", "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS"}
        packet = {
            "current_round": current_round,
            "current_absolute_round": current_round,
            "current_phase_round": current_round,
            "phase": "phase_1",
            "run_mode": self.run_mode,
            "phase_1_rounds_completed": current_round,
            "phase_2_rounds_completed": 0,
            "review_max_rounds": self.config.review_max_rounds,
            "review_mode": self.config.review_mode,
            "review_budget_exhaustion_policy": self.config.review_budget_exhaustion_policy,
            "configured_review_profile_budgets": self.config.review_profile_budgets,
            "review_profile_budgets": review_profile_budgets,
            "convergence_max_rounds": self.config.convergence.max_rounds,
            "configured_convergence_profile_budgets": self.config.convergence_profile_budgets,
            "convergence_profile_budgets": convergence_profile_budgets,
            "timeouts": {
                "reviewer_seconds": self.config.timeouts.reviewer_seconds,
                "editor_seconds": self.config.timeouts.editor_seconds,
            },
            "review_round_budget": review_round_budget,
            "convergence_round_budget": convergence_round_budget,
            "total_absolute_round_budget": review_round_budget + convergence_round_budget,
            "effective_run_config": effective_run_config(self.config),
            "active_profile": active_profile,
            "current_draft_hash": current_draft_hash,
            "last_accepted_draft_hash": last_accepted_draft_hash,
            "seen_draft_hashes": seen_draft_hashes,
            "terminal_state": terminal_state,
            "ready_for_phase_2": ready_for_phase_2,
            "telemetry_totals": run_telemetry_totals(self.config.rounds_dir),
            "budget_extensions": budget_extensions,
            "resumable": terminal_state == "HALTED_CLIENT_TIMEOUT" or terminal_state in budget_resumable_states,
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


def _reviewer_count(reviewer_feedback: dict[str, Any], severity: str) -> int:
    return sum(
        1
        for issue in reviewer_feedback.get("feedback", [])
        if issue.get("normalized_severity") == severity and bool(issue.get("in_scope", True))
    )


def _mutation_requires_verification(*, round_dir: Path, editor_summary: dict[str, Any], spec_mutated: bool) -> bool:
    if not spec_mutated:
        return False
    if editor_summary.get("accepted_feedback_ids") or editor_summary.get("modified_feedback_ids"):
        return True
    draft_before_path = round_dir / "draft_before.md"
    draft_after_path = round_dir / "draft_after.md"
    if not draft_before_path.exists() or not draft_after_path.exists():
        return True
    return not _is_version_only_change(
        draft_before_path.read_text(encoding="utf-8"),
        draft_after_path.read_text(encoding="utf-8"),
    )


def _is_version_only_change(before: str, after: str) -> bool:
    return _strip_version_labels(before) == _strip_version_labels(after)


def _strip_version_labels(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            line = _VERSION_IN_LINE_RE.sub("(VERSION)", line)
        elif stripped.lower().startswith("status:") or stripped.lower().startswith("version:"):
            line = _VERSION_IN_LINE_RE.sub("(VERSION)", line)
        lines.append(line)
    return "\n".join(lines)


def _issue_summary(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_id": issue["issue_id"],
        "issue_fingerprint": issue["issue_fingerprint"],
        "normalized_severity": issue["normalized_severity"],
        "affected_sections": issue["affected_sections"],
        "claim": issue["claim"],
    }


def _last_reviewer_findings(
    *,
    round_number: int,
    profile: str,
    reviewer_feedback: dict[str, Any],
    blocker_count: int,
    major_count: int,
) -> dict[str, Any]:
    return {
        "round_number": round_number,
        "profile": profile,
        "blocker_count": blocker_count,
        "major_count": major_count,
        "feedback_ids": [
            str(issue.get("feedback_id"))
            for issue in reviewer_feedback.get("feedback", [])
            if issue.get("normalized_severity") in {"blocker", "major"} and bool(issue.get("in_scope", True))
        ],
    }


def _contract_surface_policy(config: OrchestratorConfig) -> ContractSurfacePolicy:
    return ContractSurfacePolicy(
        enabled=config.contract_surface.enabled,
        action=config.contract_surface.action,
        min_profile_rounds=config.contract_surface.min_profile_rounds,
        recent_window=config.contract_surface.recent_window,
        min_recent_serious_rounds=config.contract_surface.min_recent_serious_rounds,
        min_contract_families=config.contract_surface.min_contract_families,
    )


def _soft_budget_policy(config: OrchestratorConfig) -> bool:
    return config.review_budget_exhaustion_policy == "soft"


def _vertical_closeout_eligible(
    *,
    current_hash: str,
    last_accepted_draft_hash: str | None,
    last_unresolved: list[dict[str, Any]],
    profile_status: dict[str, Any],
) -> bool:
    return (
        last_accepted_draft_hash == current_hash
        and bool(profile_status.get("unverified_profiles"))
        and not _has_serious_issues(last_unresolved)
    )


def _has_serious_issues(issues: list[dict[str, Any]]) -> bool:
    return any(issue.get("normalized_severity") in {"blocker", "major"} for issue in issues)


def _vertical_profile_status(
    profile_state: dict[str, dict[str, Any]],
    *,
    current_draft_hash: str | None = None,
) -> dict[str, object]:
    profiles = [profile_state[key] for key in ("structural_integrity", "determinism", "operability")]
    unverified_profiles = [
        item["profile"]
        for item in profiles
        if (
            not item["clean"]
            or (
                current_draft_hash is not None
                and item.get("verified_draft_hash") != current_draft_hash
            )
        )
    ]
    report_profiles = [
        {key: value for key, value in item.items() if key != "verified_draft_hash"}
        for item in profiles
    ]
    return {
        "profiles": report_profiles,
        "unverified_profiles": unverified_profiles,
        "exhausted_profiles": [item["profile"] for item in profiles if item["exhausted"]],
        "profiles_remaining": [
            item["profile"]
            for item in profiles
            if not item["clean"] and not item["exhausted"] and item["rounds_used"] < item["round_budget"]
        ],
        "total_round_budget": sum(int(item["round_budget"]) for item in profiles),
    }


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


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
        "decision_summary.json",
        "decision_summary.md",
        "decision_intervention_request.json",
        "contract_surface_report.json",
        "contract_surface_report.md",
    ):
        path = rounds_dir / filename
        if path.exists():
            path.unlink()
