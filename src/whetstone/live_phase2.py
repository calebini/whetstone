"""Minimal live Phase 2 convergence orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable

from whetstone.artifacts import ArtifactStore
from whetstone.config import OrchestratorConfig
from whetstone.conflicts import ConflictTracker, conflict_from_oscillation_detection
from whetstone.declaration import render_convergence_declaration, validate_convergence_declaration, write_convergence_declaration
from whetstone.decisions import write_decision_register
from whetstone.evaluation import target_matrix_satisfied
from whetstone.hashing import draft_hash, rubric_content_hash, semantic_changes
from whetstone.live import EditorClient, LiveRoundRunner, ReviewerClient, run_telemetry_totals
from whetstone.oscillation import OscillationTracker
from whetstone.reports import ReportWriter
from whetstone.run_state import effective_run_config
from whetstone.rubrics import RubricManifest, read_rubric_text, rubric_manifest_identity, write_rubric_manifest
from whetstone.scheduler import (
    default_phase_1_scheduler,
    default_phase_2_scheduler,
    resolved_phase_1_profile_budgets,
    resolved_phase_2_profile_budgets,
)
from whetstone.termination import TerminationCandidate, select_terminal_candidate
from whetstone.versioning import promote_spec_file_for_phase2


@dataclass(frozen=True)
class LivePhase2Result:
    terminal_state: str
    round_number: int
    current_draft_hash: str
    last_accepted_draft_hash: str | None
    declaration_path: Path | None = None
    report_path: Path | None = None


class LivePhase2Runner:
    """Run the minimal non-resumable live Phase 2 loop."""

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
        self.store = ArtifactStore(self.root)
        self.report_writer = ReportWriter(self.root)
        self.rubric_manifest: RubricManifest | None = None
        self.phase_1_rounds_completed = 0

    def run(self, *, overwrite: bool = False) -> LivePhase2Result:
        state = _read_phase1_handoff(self.config.rounds_dir)
        self.phase_1_rounds_completed = int(state.get("current_round", 0))
        self.rubric_manifest = write_rubric_manifest(self.config)
        promotion = promote_spec_file_for_phase2(
            spec_path=self.config.spec_path,
            history_path=self.config.history_path,
            rounds_dir=self.config.rounds_dir,
        )
        current_hash = promotion.after_hash
        last_accepted_draft_hash: str | None = current_hash
        start_round = int(state.get("current_round", 0)) + 1
        scheduler = default_phase_2_scheduler(self.config.convergence_profile_budgets)
        oscillation_tracker = OscillationTracker()
        conflict_tracker = ConflictTracker()
        if overwrite and self.config.declaration_path.exists():
            self.config.declaration_path.unlink()
        declaration_path: Path | None = None
        last_unresolved: list[dict[str, Any]] = []
        last_rubric_gaps: list[dict[str, Any]] = []
        final_round_number = start_round - 1
        clean_profiles: set[str] = set()
        required_clean_profiles = {step.profile for step in default_phase_2_scheduler(self.config.convergence_profile_budgets).steps}

        oscillation_tracker.record_draft(
            round_number=start_round - 1,
            draft_hash_value=current_hash,
            semantic_changes=[],
        )
        self._write_state(
            current_round=start_round - 1,
            active_profile=None,
            current_draft_hash=current_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            terminal_state=None,
            declaration_path=declaration_path,
        )

        total_round_budget = scheduler.total_round_budget()
        for offset in range(total_round_budget):
            round_number = start_round + offset
            profile = scheduler.next_profile()
            if profile is None:
                break
            final_round_number = round_number
            self._write_state(
                current_round=round_number,
                active_profile=profile,
                current_draft_hash=current_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                terminal_state=None,
                declaration_path=declaration_path,
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
                    phase="phase_2",
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
                        terminal_state=terminal_state,
                        declaration_path=declaration_path,
                    )
                    self._write_decision_register(terminal_state)
                    return LivePhase2Result(
                        terminal_state,
                        round_number,
                        current_hash,
                        last_accepted_draft_hash,
                        declaration_path,
                        artifact_error,
                    )
                raise

            round_dir = self.config.rounds_dir / f"round-{round_number}"
            reviewer_feedback = _read_json(round_dir / "reviewer_feedback.json")
            editor_summary = _read_json(round_dir / "editor_summary.json")
            unresolved_packet = _read_json(round_dir / "unresolved_issues.json")
            last_unresolved = list(unresolved_packet.get("unresolved_issues", []))
            last_rubric_gaps = []
            reviewer_blocker_count = _reviewer_count(reviewer_feedback, "blocker")
            reviewer_major_count = _reviewer_count(reviewer_feedback, "major")
            reviewer_clean = reviewer_blocker_count == 0 and reviewer_major_count == 0
            verified_current_draft_clean = reviewer_clean and not result.spec_mutated
            unresolved_blocker_count = _count(last_unresolved, "blocker")
            unresolved_major_count = _count(last_unresolved, "major")
            scheduler.record_result(
                profile,
                blocker_count=reviewer_blocker_count,
                major_count=reviewer_major_count + (1 if reviewer_clean and result.spec_mutated else 0),
            )
            if result.spec_mutated:
                clean_profiles.clear()
            if verified_current_draft_clean:
                clean_profiles.add(profile)

            if result.accepted:
                last_accepted_draft_hash = result.draft_after_hash
            current_hash = result.draft_after_hash
            self._write_rubric_gaps(round_number=round_number, draft_hash_value=result.draft_after_hash, rubric_gaps=last_rubric_gaps)

            terminal_candidates: list[TerminationCandidate] = []
            draft_detection = oscillation_tracker.record_draft(
                round_number=round_number,
                draft_hash_value=result.draft_after_hash,
                semantic_changes=semantic_changes(
                    (round_dir / "draft_before.md").read_text(encoding="utf-8"),
                    (round_dir / "draft_after.md").read_text(encoding="utf-8"),
                ),
            )
            if draft_detection is not None:
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
                if draft_detection.recommendation == "stop_iteration":
                    terminal_candidates.append(TerminationCandidate("HALTED_OSCILLATION", round_number, "phase_2", report_path))

            feedback_detection = oscillation_tracker.record_phase2_feedback(
                round_number=round_number,
                reviewer_feedback=reviewer_feedback,
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
                    terminal_candidates.append(TerminationCandidate("HALTED_OSCILLATION", round_number, "phase_2", report_path))
                if feedback_detection.recommendation == "escalate_conflict":
                    conflict = conflict_from_oscillation_detection(feedback_detection)
                    conflict_report = self.report_writer.write_conflict_report(
                        round_number=round_number,
                        conflicts=[conflict],
                        exit_reason=f"{feedback_detection.oscillation_type} escalated for manual review",
                        terminal_state="HALTED_CONFLICT" if conflict["conflict_severity"] == "blocker" else None,
                    )
                    if conflict["conflict_severity"] == "blocker":
                        terminal_candidates.append(TerminationCandidate("HALTED_CONFLICT", round_number, "phase_2", conflict_report))

            conflict_escalation = conflict_tracker.record_round(
                round_number=round_number,
                conflicts=[],
                issues=last_unresolved,
            )
            if conflict_escalation is not None:
                report_path = self.report_writer.write_conflict_report(
                    round_number=round_number,
                    conflicts=conflict_escalation.conflicts,
                    exit_reason=conflict_escalation.reason,
                    terminal_state="HALTED_CONFLICT" if conflict_escalation.blocker_level else None,
                )
                if conflict_escalation.blocker_level:
                    terminal_candidates.append(TerminationCandidate("HALTED_CONFLICT", round_number, "phase_2", report_path))

            had_declaration = declaration_path is not None
            target_ready_for_declaration = target_matrix_satisfied(
                target_phase=self.config.convergence.target_phase,
                target_mode=self.config.convergence.target_mode,
                issues=last_unresolved,
                unresolved_rubric_gaps=last_rubric_gaps,
                declaration_accepted=True,
            )
            if target_ready_for_declaration and (
                declaration_path is None
                or _declaration_draft_hash(declaration_path) != result.draft_after_hash
            ):
                declaration_path = self._write_declaration(
                    draft_hash_value=result.draft_after_hash,
                    reviewer_final_status="not_run",
                    declaration_status="rejected",
                    blocker_count=unresolved_blocker_count,
                    major_count=unresolved_major_count,
                    rubric_gap_count=len(last_rubric_gaps),
                )

            if (
                had_declaration
                and profile == "convergence_strict_check"
                and verified_current_draft_clean
                and result.accepted
                and required_clean_profiles.issubset(clean_profiles)
                and target_matrix_satisfied(
                    target_phase=self.config.convergence.target_phase,
                    target_mode=self.config.convergence.target_mode,
                    issues=last_unresolved,
                    unresolved_rubric_gaps=last_rubric_gaps,
                    declaration_accepted=True,
                )
            ):
                declaration_path = self._write_declaration(
                    draft_hash_value=result.draft_after_hash,
                    reviewer_final_status="accepted",
                    declaration_status="accepted",
                    blocker_count=unresolved_blocker_count,
                    major_count=unresolved_major_count,
                    rubric_gap_count=len(last_rubric_gaps),
                )
                terminal_candidates.append(TerminationCandidate("CONVERGED", round_number, "phase_2", None))

            selected = select_terminal_candidate(terminal_candidates)
            if selected is not None:
                report_path = selected.report_path
                if selected.terminal_state in {"HALTED_CONFLICT", "HALTED_OSCILLATION"}:
                    report_path = self._write_failure_report(
                        round_number=round_number,
                        unresolved_issues=last_unresolved,
                        unresolved_rubric_gaps=last_rubric_gaps,
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        declaration_path=declaration_path,
                        terminal_state=selected.terminal_state,
                        exit_reason=f"{selected.terminal_state} halted Phase 2 before convergence",
                    )
                self._append_history(
                    round_number=round_number,
                    profile=profile,
                    before_hash=result.draft_before_hash,
                    after_hash=result.draft_after_hash,
                    accepted=result.accepted,
                    blocker_count=unresolved_blocker_count,
                    major_count=unresolved_major_count,
                    terminal_state=selected.terminal_state,
                )
                self._write_state(
                    current_round=round_number,
                    active_profile=profile,
                    current_draft_hash=result.draft_after_hash,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    terminal_state=selected.terminal_state,
                    declaration_path=declaration_path,
                )
                self._write_decision_register(selected.terminal_state)
                return LivePhase2Result(
                    selected.terminal_state,
                    round_number,
                    result.draft_after_hash,
                    last_accepted_draft_hash,
                    declaration_path,
                    report_path,
                )

            self._append_history(
                round_number=round_number,
                profile=profile,
                before_hash=result.draft_before_hash,
                after_hash=result.draft_after_hash,
                accepted=result.accepted,
                blocker_count=unresolved_blocker_count,
                major_count=unresolved_major_count,
                terminal_state=None,
            )
            self._write_state(
                current_round=round_number,
                active_profile=profile,
                current_draft_hash=result.draft_after_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                terminal_state=None,
                declaration_path=declaration_path,
            )

        report_path = self._write_failure_report(
            round_number=max(final_round_number, 1),
            unresolved_issues=last_unresolved,
            unresolved_rubric_gaps=last_rubric_gaps,
            last_accepted_draft_hash=last_accepted_draft_hash,
            declaration_path=declaration_path,
            terminal_state="TARGET_NOT_REACHED",
            exit_reason="Phase 2 profile round budgets exhausted before convergence",
            profile_status=scheduler.status(),
            last_reviewer_findings=_last_reviewer_findings_from_round(self.config.rounds_dir, final_round_number),
        )
        self._write_state(
            current_round=max(final_round_number, 1),
            active_profile=None,
            current_draft_hash=current_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            terminal_state="TARGET_NOT_REACHED",
            declaration_path=declaration_path,
        )
        self._write_decision_register("TARGET_NOT_REACHED")
        return LivePhase2Result(
            "TARGET_NOT_REACHED",
            max(final_round_number, 1),
            current_hash,
            last_accepted_draft_hash,
            declaration_path,
            report_path,
        )

    def _write_rubric_gaps(self, *, round_number: int, draft_hash_value: str, rubric_gaps: list[dict[str, Any]]) -> None:
        self.store.write_round_json(
            round_number,
            "rubric_gaps.json",
            {
                "round_number": round_number,
                "draft_hash": draft_hash_value,
                "rubric_content_hash": _rubric_hash(self.config),
                "rubric_gaps": rubric_gaps,
            },
            schema_name="rubric_gaps",
        )

    def _write_declaration(
        self,
        *,
        draft_hash_value: str,
        reviewer_final_status: str,
        declaration_status: str,
        blocker_count: int,
        major_count: int,
        rubric_gap_count: int,
    ) -> Path:
        rubric_hash_value = _rubric_hash(self.config)
        manifest_identity = _manifest_identity(self.rubric_manifest)
        declaration = render_convergence_declaration(
            target_phase=self.config.convergence.target_phase,
            target_mode=self.config.convergence.target_mode,
            workflow=manifest_identity["workflow"],
            rubric_profile=manifest_identity["rubric_profile"],
            rubric_source=manifest_identity["rubric_source"],
            rubric_label=manifest_identity["rubric_label"],
            rubric_manifest_path=manifest_identity["rubric_manifest_path"],
            final_draft_hash=draft_hash_value,
            rubric_content_hash=rubric_hash_value,
            unresolved_blockers_count=blocker_count,
            unresolved_major_issues_count=major_count,
            unresolved_rubric_gaps_count=rubric_gap_count,
            reviewer_final_status=reviewer_final_status,
            declaration_status=declaration_status,
        )
        if not validate_convergence_declaration(
            declaration,
            final_draft_hash=draft_hash_value,
            rubric_content_hash=rubric_hash_value,
            workflow=manifest_identity["workflow"],
            rubric_profile=manifest_identity["rubric_profile"],
            rubric_source=manifest_identity["rubric_source"],
            rubric_label=manifest_identity["rubric_label"],
            rubric_manifest_path=manifest_identity["rubric_manifest_path"],
            unresolved_blockers_count=blocker_count,
            unresolved_major_issues_count=major_count,
            unresolved_rubric_gaps_count=rubric_gap_count,
        ):
            raise ValueError("generated convergence declaration failed validation")
        return write_convergence_declaration(self.config.declaration_path, declaration)

    def _write_failure_report(
        self,
        *,
        round_number: int,
        unresolved_issues: list[dict[str, Any]],
        unresolved_rubric_gaps: list[dict[str, Any]],
        last_accepted_draft_hash: str | None,
        declaration_path: Path | None,
        terminal_state: str,
        exit_reason: str,
        profile_status: dict[str, Any] | None = None,
        last_reviewer_findings: dict[str, Any] | None = None,
    ) -> Path:
        blockers = [_issue_summary(issue) for issue in unresolved_issues if issue["normalized_severity"] == "blocker"]
        majors = [_issue_summary(issue) for issue in unresolved_issues if issue["normalized_severity"] == "major"]
        manifest_identity = _manifest_identity(self.rubric_manifest)
        return self.report_writer.write_convergence_failure_report(
            round_number=round_number,
            final_draft_path=str(Path("rounds") / f"round-{round_number}" / "draft_after.md"),
            final_declaration_path=str(declaration_path.relative_to(self.root)) if declaration_path else None,
            target_phase=self.config.convergence.target_phase,
            target_mode=self.config.convergence.target_mode,
            workflow=manifest_identity["workflow"],
            rubric_profile=manifest_identity["rubric_profile"],
            rubric_source=manifest_identity["rubric_source"],
            rubric_label=manifest_identity["rubric_label"],
            rubric_manifest_path=manifest_identity["rubric_manifest_path"],
            unresolved_blockers=blockers,
            unresolved_major_issues=majors,
            unresolved_rubric_gaps=[_rubric_gap_summary(gap) for gap in unresolved_rubric_gaps],
            reviewer_final_status="not_run",
            last_accepted_draft_hash=last_accepted_draft_hash,
            exit_reason=exit_reason,
            recommendation="manual_review_required",
            profile_status=profile_status,
            last_reviewer_findings=last_reviewer_findings,
            terminal_state=terminal_state,
        )

    def _write_state(
        self,
        *,
        current_round: int,
        active_profile: str | None,
        current_draft_hash: str,
        last_accepted_draft_hash: str | None,
        terminal_state: str | None,
        declaration_path: Path | None,
    ) -> None:
        self.config.rounds_dir.mkdir(parents=True, exist_ok=True)
        phase_2_rounds_completed = max(0, current_round - self.phase_1_rounds_completed)
        review_round_budget = default_phase_1_scheduler(self.config.review_profile_budgets).total_round_budget()
        convergence_round_budget = default_phase_2_scheduler(self.config.convergence_profile_budgets).total_round_budget()
        review_profile_budgets = resolved_phase_1_profile_budgets(self.config.review_profile_budgets)
        convergence_profile_budgets = resolved_phase_2_profile_budgets(self.config.convergence_profile_budgets)
        packet = {
            "current_round": current_round,
            "current_absolute_round": current_round,
            "current_phase_round": phase_2_rounds_completed,
            "phase": "phase_2",
            "phase_1_rounds_completed": self.phase_1_rounds_completed,
            "phase_2_rounds_completed": phase_2_rounds_completed,
            "review_max_rounds": self.config.review_max_rounds,
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
            "terminal_state": terminal_state,
            "ready_for_phase_2": False,
            "declaration_path": str(declaration_path.relative_to(self.root)) if declaration_path else None,
            "rubric_manifest_path": self.rubric_manifest.relative_path if self.rubric_manifest else None,
            "telemetry_totals": run_telemetry_totals(self.config.rounds_dir),
            "resumable": terminal_state == "HALTED_CLIENT_TIMEOUT",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        (self.config.rounds_dir / "run_state.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_decision_register(self, terminal_state: str) -> None:
        write_decision_register(
            rounds_dir=self.config.rounds_dir,
            mode=self.config.decision_points.mode,
            terminal_state=terminal_state,
        )

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
        terminal_state: str | None,
    ) -> None:
        terminal = f", terminal_state={terminal_state}" if terminal_state else ""
        entry = (
            f"- Live Phase 2 round {round_number}: profile `{profile}`, "
            f"before `{before_hash}`, after `{after_hash}`, "
            f"accepted={str(accepted).lower()}, blockers={blocker_count}, majors={major_count}{terminal}.\n"
        )
        with self.config.history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(entry)


def _read_phase1_handoff(rounds_dir: Path) -> dict[str, Any]:
    state_path = rounds_dir / "run_state.json"
    if not state_path.exists():
        raise ValueError("live Phase 2 requires rounds/run_state.json from a completed Phase 1 run")
    state = _read_json(state_path)
    if state.get("terminal_state") != "PHASE_1_STABLE" or state.get("ready_for_phase_2") is not True:
        raise ValueError("live Phase 2 requires PHASE_1_STABLE with ready_for_phase_2=true")
    return state


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _last_reviewer_findings_from_round(rounds_dir: Path, round_number: int) -> dict[str, Any] | None:
    path = rounds_dir / f"round-{round_number}" / "reviewer_feedback.json"
    if not path.exists():
        return None
    reviewer_feedback = _read_json(path)
    return {
        "round_number": round_number,
        "profile": str(reviewer_feedback.get("profile", "")),
        "blocker_count": _reviewer_count(reviewer_feedback, "blocker"),
        "major_count": _reviewer_count(reviewer_feedback, "major"),
        "feedback_ids": [
            str(issue.get("feedback_id"))
            for issue in reviewer_feedback.get("feedback", [])
            if issue.get("normalized_severity") in {"blocker", "major"} and bool(issue.get("in_scope", True))
        ],
    }


def _declaration_draft_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- final_draft_hash: "):
            return line.removeprefix("- final_draft_hash: ").strip()
    return None


def _count(issues: list[dict[str, Any]], severity: str) -> int:
    return sum(1 for issue in issues if issue.get("normalized_severity") == severity)


def _reviewer_count(reviewer_feedback: dict[str, Any], severity: str) -> int:
    return sum(
        1
        for issue in reviewer_feedback.get("feedback", [])
        if issue.get("normalized_severity") == severity and bool(issue.get("in_scope", True))
    )


def _issue_summary(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_id": issue["issue_id"],
        "issue_fingerprint": issue["issue_fingerprint"],
        "normalized_severity": issue["normalized_severity"],
        "affected_sections": issue["affected_sections"],
        "claim": issue["claim"],
    }


def _rubric_gap_summary(gap: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_id": "iss_" + str(gap["gap_fingerprint"])[:16],
        "issue_fingerprint": gap["gap_fingerprint"],
        "normalized_severity": gap["normalized_severity"],
        "affected_sections": gap["affected_sections"],
        "claim": gap["claim"],
    }


def _rubric_hash(config: OrchestratorConfig) -> str:
    rubric_text = read_rubric_text(config)
    if rubric_text is None:
        return "0" * 64
    return rubric_content_hash(rubric_text)


def _manifest_identity(manifest: RubricManifest | None) -> dict[str, Any]:
    if manifest is None:
        return {
            "workflow": "standard",
            "rubric_profile": "standard-v1",
            "rubric_source": "builtin",
            "rubric_label": None,
            "rubric_content_hash": "0" * 64,
            "target_phase": "final",
            "target_mode": "strict",
            "rubric_manifest_path": "rounds/rubric_manifest.json",
        }
    return rubric_manifest_identity(manifest)
