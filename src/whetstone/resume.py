"""Resume helpers for halted live runs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from whetstone.config import OrchestratorConfig
from whetstone.contract_surface import ContractSurfacePolicy, maybe_write_contract_surface_report, update_contract_surface_lifecycle
from whetstone.decisions import write_decision_intervention_request, write_decision_register
from whetstone.hashing import draft_hash
from whetstone.live import EditorClient, LiveRoundRunner, ReviewerClient, _validate_reviewer_feedback, run_telemetry_totals
from whetstone.reports import ReportWriter
from whetstone.runner import _unresolved_issues
from whetstone.run_state import effective_run_config
from whetstone.scheduler import (
    default_phase_1_scheduler,
    default_phase_2_scheduler,
    resolved_phase_1_profile_budgets,
    resolved_phase_2_profile_budgets,
)


_VERSION_IN_LINE_RE = re.compile(r"\bv?\d+(?:\.\d+)+\b")


@dataclass(frozen=True)
class ResumeResult:
    resumed: bool
    terminal_state: str | None
    round_number: int
    phase: str
    profile: str
    current_draft_hash: str
    last_accepted_draft_hash: str | None
    ready_for_phase_2: bool


@dataclass(frozen=True)
class ResumePlan:
    resumable: bool
    terminal_state: str
    failure_type: str
    phase: str
    client_role: str
    round_number: int
    profile: str
    current_draft_hash: str
    expected_draft_hash: str
    next_attempt_number: int
    continue_run: bool
    next_round_number: int | None
    reason: str


def resume_halted_run(
    root: Path | str,
    config: OrchestratorConfig,
    *,
    continue_run: bool = False,
    reviewer_client: ReviewerClient | None = None,
    editor_client: EditorClient | None = None,
    timeout_seconds: int | None = None,
) -> ResumeResult:
    """Resume the narrow safe path: a Phase 1 editor timeout with validated reviewer feedback."""

    root = Path(root)
    context = _validated_resume_context(config, continue_run=continue_run)
    round_number = context["round_number"]
    profile = context["profile"]
    scheduler = context["scheduler"]
    last_accepted_draft_hash = context["last_accepted_draft_hash"]
    seen_hashes = context["seen_hashes"]
    start_attempt_number = context["next_attempt_number"]
    result = LiveRoundRunner(
        root,
        config,
        editor_client=editor_client,
        timeout_seconds=timeout_seconds,
    ).resume_editor_round(
        round_number=round_number,
        profile=profile,
        phase="phase_1",
        apply=True,
        start_attempt_number=start_attempt_number,
    )

    reviewer_feedback = _read_json(config.rounds_dir / f"round-{round_number}" / "reviewer_feedback.json")
    editor_summary = _read_json(config.rounds_dir / f"round-{round_number}" / "editor_summary.json")
    unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
    reviewer_blocker_count = _reviewer_count(reviewer_feedback, "blocker")
    reviewer_major_count = _reviewer_count(reviewer_feedback, "major")
    reviewer_clean = reviewer_blocker_count == 0 and reviewer_major_count == 0
    scheduler.record_result(
        profile,
        blocker_count=reviewer_blocker_count,
        major_count=reviewer_major_count + (
            1
            if reviewer_clean
            and _mutation_requires_verification(
                round_dir=config.rounds_dir / f"round-{round_number}",
                editor_summary=editor_summary,
                spec_mutated=result.spec_mutated,
            )
            else 0
        ),
    )
    if result.accepted:
        last_accepted_draft_hash = result.draft_after_hash
    seen_hashes.append(result.draft_after_hash)
    phase_complete = scheduler.phase_complete(accepted_draft=result.accepted)
    terminal_state = "PHASE_1_STABLE" if phase_complete else None
    if phase_complete:
        write_decision_register(
            rounds_dir=config.rounds_dir,
            mode=config.decision_points.mode,
            terminal_state="PHASE_1_STABLE",
        )
    _append_resume_history(
        config.history_path,
        round_number=round_number,
        profile=profile,
        before_hash=result.draft_before_hash,
        after_hash=result.draft_after_hash,
        accepted=result.accepted,
        blocker_count=_count(unresolved, "blocker"),
        major_count=_count(unresolved, "major"),
    )
    maybe_write_contract_surface_report(
        rounds_dir=config.rounds_dir,
        current_round=round_number,
        profile=profile,
        policy=_contract_surface_policy(config),
    )
    update_contract_surface_lifecycle(rounds_dir=config.rounds_dir, terminal=phase_complete)
    _write_phase1_state(
        config=config,
        current_round=round_number,
        active_profile=None if phase_complete else scheduler.next_profile(),
        current_draft_hash=result.draft_after_hash,
        last_accepted_draft_hash=last_accepted_draft_hash,
        seen_draft_hashes=seen_hashes,
        terminal_state=terminal_state,
        ready_for_phase_2=phase_complete,
    )
    if continue_run and not phase_complete:
        return _continue_phase1(
            root,
            config,
            scheduler=scheduler,
            start_round=round_number + 1,
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_hashes=seen_hashes,
            reviewer_client=reviewer_client,
            editor_client=editor_client,
            timeout_seconds=timeout_seconds,
        )
    return ResumeResult(
        resumed=True,
        terminal_state=terminal_state,
        round_number=round_number,
        phase="phase_1",
        profile=profile,
        current_draft_hash=result.draft_after_hash,
        last_accepted_draft_hash=last_accepted_draft_hash,
        ready_for_phase_2=phase_complete,
    )


def resume_budget_exhausted_run(
    root: Path | str,
    config: OrchestratorConfig,
    *,
    extend_review_budget: int,
    reviewer_client: ReviewerClient | None = None,
    editor_client: EditorClient | None = None,
    timeout_seconds: int | None = None,
) -> ResumeResult:
    """Append Phase 1 rounds after a budget-exhausted terminal state."""

    root = Path(root)
    state = _validated_budget_extension_context(config, extend_review_budget=extend_review_budget)
    original_budgets = resolved_phase_1_profile_budgets(config.review_profile_budgets)
    current_round = int(state["current_round"])
    if config.review_mode == "vertical":
        vertical_state = _reconstruct_vertical_phase1_state(config, through_round=current_round)
        extended_budgets = _extended_vertical_budgets(
            original_budgets,
            vertical_state["profile_state"],
            extend_review_budget=extend_review_budget,
        )
        extended_config = replace(config, review_profile_budgets=extended_budgets)
        _write_budget_extension_event(
            config=extended_config,
            previous_state=state,
            original_budgets=original_budgets,
            extended_budgets=extended_budgets,
            extension_rounds=extend_review_budget,
        )
        return _continue_vertical_phase1(
            root,
            extended_config,
            profile_state=_extend_vertical_profile_state(vertical_state["profile_state"], extended_budgets),
            start_round=current_round + 1,
            last_accepted_draft_hash=vertical_state["last_accepted_draft_hash"],
            seen_hashes=vertical_state["seen_hashes"],
            last_unresolved=vertical_state["last_unresolved"],
            last_reviewer_findings=vertical_state["last_reviewer_findings"],
            reviewer_client=reviewer_client,
            editor_client=editor_client,
            timeout_seconds=timeout_seconds,
        )
    scheduler, last_accepted_draft_hash, seen_hashes = _reconstruct_phase1_state(
        config,
        through_round=current_round,
    )
    extended_budgets = _extended_horizontal_budgets(
        original_budgets,
        scheduler,
        extend_review_budget=extend_review_budget,
    )
    _extend_phase1_scheduler_budgets(scheduler, extended_budgets)
    extended_config = replace(config, review_profile_budgets=extended_budgets)
    _write_budget_extension_event(
        config=extended_config,
        previous_state=state,
        original_budgets=original_budgets,
        extended_budgets=extended_budgets,
        extension_rounds=extend_review_budget,
    )
    return _continue_phase1(
        root,
        extended_config,
        scheduler=scheduler,
        start_round=current_round + 1,
        last_accepted_draft_hash=last_accepted_draft_hash,
        seen_hashes=seen_hashes,
        reviewer_client=reviewer_client,
        editor_client=editor_client,
        timeout_seconds=timeout_seconds,
    )


def plan_resume_halted_run(
    root: Path | str,
    config: OrchestratorConfig,
    *,
    continue_run: bool = False,
) -> ResumePlan:
    """Validate a resumable halt without invoking clients."""

    _ = Path(root)
    context = _validated_resume_context(config, continue_run=continue_run)
    scheduler = context["scheduler"]
    next_round_number = None
    if continue_run:
        next_profile = scheduler.next_profile()
        next_round_number = context["round_number"] + 1 if next_profile is not None else None
    return ResumePlan(
        resumable=True,
        terminal_state=context["terminal_state"],
        failure_type=context["failure_type"],
        phase=context["phase"],
        client_role=context["client_role"],
        round_number=context["round_number"],
        profile=context["profile"],
        current_draft_hash=context["current_hash"],
        expected_draft_hash=context["expected_hash"],
        next_attempt_number=context["next_attempt_number"],
        continue_run=continue_run,
        next_round_number=next_round_number,
        reason="supported Phase 1 Editor timeout with validated Reviewer feedback",
    )


def plan_budget_extension_resume(
    root: Path | str,
    config: OrchestratorConfig,
    *,
    extend_review_budget: int,
) -> ResumePlan:
    """Validate a budget-extension continuation without invoking clients."""

    _ = Path(root)
    state = _validated_budget_extension_context(config, extend_review_budget=extend_review_budget)
    current_round = int(state["current_round"])
    current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
    return ResumePlan(
        resumable=True,
        terminal_state=str(state["terminal_state"]),
        failure_type="budget_exhausted",
        phase=str(state.get("phase", "phase_1")),
        client_role="orchestrator",
        round_number=current_round,
        profile=str(state.get("active_profile") or ""),
        current_draft_hash=current_hash,
        expected_draft_hash=str(state["current_draft_hash"]),
        next_attempt_number=1,
        continue_run=True,
        next_round_number=current_round + 1,
        reason=f"supported Phase 1 budget extension by {extend_review_budget} round(s) per profile",
    )


BUDGET_EXTENSION_TERMINAL_STATES = {"TARGET_NOT_REACHED", "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS"}


def _continue_phase1(
    root: Path,
    config: OrchestratorConfig,
    *,
    scheduler: Any,
    start_round: int,
    last_accepted_draft_hash: str | None,
    seen_hashes: list[str],
    reviewer_client: ReviewerClient | None,
    editor_client: EditorClient | None,
    timeout_seconds: int | None,
) -> ResumeResult:
    total_budget = scheduler.total_round_budget()
    current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
    final_profile = scheduler.next_profile()
    last_unresolved: list[dict[str, Any]] = []
    last_reviewer_findings: dict[str, Any] | None = None
    for round_number in range(start_round, total_budget + 1):
        profile = scheduler.next_profile()
        if profile is None:
            phase_complete = scheduler.phase_complete(accepted_draft=last_accepted_draft_hash == current_hash)
            terminal_state = (
                "PHASE_1_STABLE"
                if phase_complete
                else "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS"
                if _soft_budget_policy(config) and scheduler.sweep_complete()
                else "TARGET_NOT_REACHED"
            )
            _write_phase1_state(
                config=config,
                current_round=round_number - 1,
                active_profile=None,
                current_draft_hash=current_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes,
                terminal_state=terminal_state,
                ready_for_phase_2=phase_complete,
            )
            write_decision_register(
                rounds_dir=config.rounds_dir,
                mode=config.decision_points.mode,
                terminal_state=terminal_state,
            )
            if terminal_state == "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS":
                ReportWriter(root).write_technical_failure_report(
                    round_number=round_number - 1,
                    final_draft_path="./spec.md",
                    unresolved_blockers=[],
                    unresolved_major_issues=[],
                    unresolved_conflicts=[],
                    unresolved_oscillation=None,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    exit_reason="Phase 1 sweep completed with residual unverified or non-clean profiles during resume continuation",
                    recommendation="manual_review_required",
                    profile_status=scheduler.status(),
                    last_reviewer_findings=last_reviewer_findings,
                    terminal_state=terminal_state,
                )
            return ResumeResult(True, terminal_state, round_number - 1, "phase_1", final_profile or "", current_hash, last_accepted_draft_hash, phase_complete)
        final_profile = profile
        try:
            result = LiveRoundRunner(
                root,
                config,
                reviewer_client=reviewer_client,
                editor_client=editor_client,
                timeout_seconds=timeout_seconds,
            ).run_round(round_number=round_number, profile=profile, phase="phase_1", apply=True)
        except ValueError:
            artifact_error = config.rounds_dir / "artifact_validation_error.json"
            if artifact_error.exists():
                packet = _read_json(artifact_error)
                terminal_state = str(packet.get("terminal_state", "HALTED_ARTIFACT_INVALID"))
                current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
                _write_phase1_state(
                    config=config,
                    current_round=round_number,
                    active_profile=profile,
                    current_draft_hash=current_hash,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    seen_draft_hashes=seen_hashes,
                    terminal_state=terminal_state,
                    ready_for_phase_2=False,
                )
                return ResumeResult(True, terminal_state, round_number, "phase_1", profile, current_hash, last_accepted_draft_hash, False)
            raise
        round_dir = config.rounds_dir / f"round-{round_number}"
        reviewer_feedback = _read_json(round_dir / "reviewer_feedback.json")
        editor_summary = _read_json(round_dir / "editor_summary.json")
        decision_packet = _read_json(round_dir / "decision_points.json")
        unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
        last_unresolved = unresolved
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
        scheduler.record_result(
            profile,
            blocker_count=reviewer_blocker_count,
            major_count=reviewer_major_count + (
                1
                if reviewer_clean
                and _mutation_requires_verification(
                    round_dir=round_dir,
                    editor_summary=editor_summary,
                    spec_mutated=result.spec_mutated,
                )
                else 0
            ),
        )
        if result.accepted:
            last_accepted_draft_hash = result.draft_after_hash
        current_hash = result.draft_after_hash

        pause_points = [
            point
            for point in decision_packet.get("decision_points", [])
            if point.get("orchestrator_action") == "pause_for_input"
        ]
        if pause_points:
            write_decision_intervention_request(
                rounds_dir=config.rounds_dir,
                round_number=round_number,
                profile=profile,
                draft_hash_value=result.draft_after_hash,
                decision_points=pause_points,
            )
            write_decision_register(
                rounds_dir=config.rounds_dir,
                mode=config.decision_points.mode,
                terminal_state="PAUSED_DECISION",
            )
            _write_phase1_state(
                config=config,
                current_round=round_number,
                active_profile=profile,
                current_draft_hash=result.draft_after_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes + [result.draft_after_hash],
                terminal_state="PAUSED_DECISION",
                ready_for_phase_2=False,
            )
            return ResumeResult(True, "PAUSED_DECISION", round_number, "phase_1", profile, result.draft_after_hash, last_accepted_draft_hash, False)

        seen_hashes.append(result.draft_after_hash)
        if result.draft_after_hash in seen_hashes[:-1] and (reviewer_blocker_count > 0 or reviewer_major_count > 0):
            ReportWriter(root).write_oscillation_report(
                round_number=round_number,
                detected=True,
                oscillation_type="cycle",
                affected_sections=[],
                suspected_feedback_ids=[],
                recommendation="stop_iteration",
            )
            if _soft_budget_policy(config):
                if scheduler.active_profile() == profile:
                    scheduler.force_advance_current(residual_status="halted_oscillation")
                _write_phase1_state(
                    config=config,
                    current_round=round_number,
                    active_profile=scheduler.next_profile(),
                    current_draft_hash=result.draft_after_hash,
                    last_accepted_draft_hash=last_accepted_draft_hash,
                    seen_draft_hashes=seen_hashes,
                    terminal_state=None,
                    ready_for_phase_2=False,
                )
                continue
            _write_phase1_state(
                config=config,
                current_round=round_number,
                active_profile=profile,
                current_draft_hash=result.draft_after_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes,
                terminal_state="HALTED_OSCILLATION",
                ready_for_phase_2=False,
            )
            return ResumeResult(True, "HALTED_OSCILLATION", round_number, "phase_1", profile, result.draft_after_hash, last_accepted_draft_hash, False)

        phase_complete = scheduler.phase_complete(accepted_draft=result.accepted)
        _append_continue_history(
            config.history_path,
            round_number=round_number,
            profile=profile,
            before_hash=result.draft_before_hash,
            after_hash=result.draft_after_hash,
            accepted=result.accepted,
            blocker_count=_count(unresolved, "blocker"),
            major_count=_count(unresolved, "major"),
        )
        maybe_write_contract_surface_report(
            rounds_dir=config.rounds_dir,
            current_round=round_number,
            profile=profile,
            policy=_contract_surface_policy(config),
        )
        update_contract_surface_lifecycle(rounds_dir=config.rounds_dir, terminal=phase_complete)
        _write_phase1_state(
            config=config,
            current_round=round_number,
            active_profile=None if phase_complete else scheduler.next_profile(),
            current_draft_hash=result.draft_after_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            seen_draft_hashes=seen_hashes,
            terminal_state="PHASE_1_STABLE" if phase_complete else None,
            ready_for_phase_2=phase_complete,
        )
        if phase_complete:
            write_decision_register(
                rounds_dir=config.rounds_dir,
                mode=config.decision_points.mode,
                terminal_state="PHASE_1_STABLE",
            )
            return ResumeResult(True, "PHASE_1_STABLE", round_number, "phase_1", profile, result.draft_after_hash, last_accepted_draft_hash, True)

    blockers = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "blocker"]
    majors = [_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "major"]
    ReportWriter(root).write_technical_failure_report(
        round_number=max(start_round, total_budget),
        final_draft_path="./spec.md",
        unresolved_blockers=blockers,
        unresolved_major_issues=majors,
        unresolved_conflicts=[],
        unresolved_oscillation=None,
        last_accepted_draft_hash=last_accepted_draft_hash,
        exit_reason="Phase 1 profile round budgets exhausted during resume continuation",
        recommendation="manual_review_required",
        profile_status=scheduler.status(),
        last_reviewer_findings=last_reviewer_findings,
        terminal_state="PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS" if _soft_budget_policy(config) and scheduler.sweep_complete() else "TARGET_NOT_REACHED",
    )
    terminal_state = "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS" if _soft_budget_policy(config) and scheduler.sweep_complete() else "TARGET_NOT_REACHED"
    _write_phase1_state(
        config=config,
        current_round=total_budget,
        active_profile=scheduler.next_profile(),
        current_draft_hash=current_hash,
        last_accepted_draft_hash=last_accepted_draft_hash,
        seen_draft_hashes=seen_hashes,
        terminal_state=terminal_state,
        ready_for_phase_2=False,
    )
    write_decision_register(
        rounds_dir=config.rounds_dir,
        mode=config.decision_points.mode,
        terminal_state=terminal_state,
    )
    update_contract_surface_lifecycle(rounds_dir=config.rounds_dir, terminal=True)
    return ResumeResult(True, terminal_state, total_budget, "phase_1", final_profile or "", current_hash, last_accepted_draft_hash, False)


def _continue_vertical_phase1(
    root: Path,
    config: OrchestratorConfig,
    *,
    profile_state: dict[str, dict[str, Any]],
    start_round: int,
    last_accepted_draft_hash: str | None,
    seen_hashes: list[str],
    last_unresolved: list[dict[str, Any]],
    last_reviewer_findings: dict[str, Any] | None,
    reviewer_client: ReviewerClient | None,
    editor_client: EditorClient | None,
    timeout_seconds: int | None,
) -> ResumeResult:
    profiles = ["structural_integrity", "determinism", "operability"]
    round_number = start_round - 1
    current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
    while any(int(profile_state[profile]["rounds_used"]) < int(profile_state[profile]["round_budget"]) for profile in profiles):
        merged_feedback: list[dict[str, Any]] = []
        draft_hash_at_cycle_start = draft_hash(config.spec_path.read_text(encoding="utf-8"))
        for profile in profiles:
            if int(profile_state[profile]["rounds_used"]) >= int(profile_state[profile]["round_budget"]):
                continue
            round_number += 1
            _write_phase1_state(
                config=config,
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
                    root,
                    config,
                    reviewer_client=reviewer_client,
                    editor_client=editor_client,
                    timeout_seconds=timeout_seconds,
                ).run_review_only_round(round_number=round_number, profile=profile, phase="phase_1", overwrite=False)
            except ValueError:
                artifact_error = config.rounds_dir / "artifact_validation_error.json"
                if artifact_error.exists():
                    packet = _read_json(artifact_error)
                    terminal_state = str(packet.get("terminal_state", "HALTED_ARTIFACT_INVALID"))
                    current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
                    _write_phase1_state(
                        config=config,
                        current_round=round_number,
                        active_profile=profile,
                        current_draft_hash=current_hash,
                        last_accepted_draft_hash=last_accepted_draft_hash,
                        seen_draft_hashes=seen_hashes,
                        terminal_state=terminal_state,
                        ready_for_phase_2=False,
                    )
                    return ResumeResult(True, terminal_state, round_number, "phase_1", profile, current_hash, last_accepted_draft_hash, False)
                raise
            reviewer_feedback = _read_json(review_result.round_dir / "reviewer_feedback.json")
            blocker_count = _reviewer_count(reviewer_feedback, "blocker")
            major_count = _reviewer_count(reviewer_feedback, "major")
            state = profile_state[profile]
            state["rounds_used"] = int(state["rounds_used"]) + 1
            state["clean"] = blocker_count == 0 and major_count == 0
            state["verified_draft_hash"] = review_result.draft_after_hash
            state["exhausted"] = not state["clean"] and int(state["rounds_used"]) >= int(state["round_budget"])
            state["residual_status"] = "exhausted_with_residuals" if state["exhausted"] else None
            last_reviewer_findings = _last_reviewer_findings(
                round_number=round_number,
                profile=profile,
                reviewer_feedback=reviewer_feedback,
                blocker_count=blocker_count,
                major_count=major_count,
            )
            for issue in reviewer_feedback.get("feedback", []):
                merged_feedback.append({**issue, "feedback_id": f"{profile}:{issue.get('feedback_id')}"})
            _append_continue_history(
                config.history_path,
                round_number=round_number,
                profile=profile,
                before_hash=review_result.draft_before_hash,
                after_hash=review_result.draft_after_hash,
                accepted=not reviewer_feedback.get("feedback"),
                blocker_count=blocker_count,
                major_count=major_count,
            )

        if all(bool(profile_state[profile]["clean"]) for profile in profiles) and not merged_feedback:
            current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
            last_accepted_draft_hash = current_hash
            _write_phase1_state(
                config=config,
                current_round=round_number,
                active_profile=None,
                current_draft_hash=current_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes,
                terminal_state="PHASE_1_STABLE",
                ready_for_phase_2=True,
            )
            write_decision_register(
                rounds_dir=config.rounds_dir,
                mode=config.decision_points.mode,
                terminal_state="PHASE_1_STABLE",
            )
            update_contract_surface_lifecycle(rounds_dir=config.rounds_dir, terminal=True)
            return ResumeResult(True, "PHASE_1_STABLE", round_number, "phase_1", "operability", current_hash, last_accepted_draft_hash, True)

        if merged_feedback:
            round_number += 1
            editor_profile = "vertical"
            draft_before = config.spec_path.read_text(encoding="utf-8")
            draft_before_hash = draft_hash(draft_before)
            synthetic_feedback = {
                "round_number": round_number,
                "profile": editor_profile,
                "reviewer": {"name": "whetstone-vertical-merge", "version": "1.0", "model": "orchestrator"},
                "draft_hash": draft_before_hash,
                "feedback": merged_feedback,
            }
            round_dir = LiveRoundRunner(root, config).store.begin_round(round_number, overwrite=False)
            round_dir.joinpath("draft_before.md").write_text(draft_before, encoding="utf-8")
            round_dir.joinpath("draft_after.md").write_text(draft_before, encoding="utf-8")
            round_dir.joinpath("profile_used.yaml").write_text(
                json.dumps({"profile": editor_profile, "round_kind": "consolidated_editor"}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            round_dir.joinpath("reviewer_feedback.json").write_text(json.dumps(synthetic_feedback, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = LiveRoundRunner(
                root,
                config,
                reviewer_client=reviewer_client,
                editor_client=editor_client,
                timeout_seconds=timeout_seconds,
            ).resume_editor_round(round_number=round_number, profile=editor_profile, phase="phase_1", apply=True, start_attempt_number=1)
            editor_summary = _read_json(round_dir / "editor_summary.json")
            last_unresolved = _unresolved_issues(synthetic_feedback, editor_summary)
            if result.accepted:
                last_accepted_draft_hash = result.draft_after_hash
            current_hash = result.draft_after_hash
            seen_hashes.append(result.draft_after_hash)
            _append_continue_history(
                config.history_path,
                round_number=round_number,
                profile=editor_profile,
                before_hash=result.draft_before_hash,
                after_hash=result.draft_after_hash,
                accepted=result.accepted,
                blocker_count=_count(last_unresolved, "blocker"),
                major_count=_count(last_unresolved, "major"),
            )
            maybe_write_contract_surface_report(
                rounds_dir=config.rounds_dir,
                current_round=round_number,
                profile=editor_profile,
                policy=_contract_surface_policy(config),
            )
            update_contract_surface_lifecycle(rounds_dir=config.rounds_dir)
            _write_phase1_state(
                config=config,
                current_round=round_number,
                active_profile=editor_profile,
                current_draft_hash=result.draft_after_hash,
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes,
                terminal_state=None,
                ready_for_phase_2=False,
            )

    current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
    terminal_state = "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS" if _soft_budget_policy(config) else "TARGET_NOT_REACHED"
    profile_status = _vertical_profile_status(profile_state, current_draft_hash=current_hash)
    if _vertical_closeout_eligible(
        current_hash=current_hash,
        last_accepted_draft_hash=last_accepted_draft_hash,
        last_unresolved=last_unresolved,
        profile_status=profile_status,
    ):
        closeout_result = _run_vertical_closeout_check(
            root,
            config,
            start_round=round_number + 1,
            profile_state=profile_state,
            seen_hashes=seen_hashes,
            last_accepted_draft_hash=last_accepted_draft_hash,
            reviewer_client=reviewer_client,
            editor_client=editor_client,
            timeout_seconds=timeout_seconds,
        )
        if closeout_result["terminal_state"] == "PHASE_1_STABLE":
            _write_phase1_state(
                config=config,
                current_round=closeout_result["round_number"],
                active_profile=None,
                current_draft_hash=closeout_result["current_hash"],
                last_accepted_draft_hash=last_accepted_draft_hash,
                seen_draft_hashes=seen_hashes,
                terminal_state="PHASE_1_STABLE",
                ready_for_phase_2=True,
            )
            write_decision_register(
                rounds_dir=config.rounds_dir,
                mode=config.decision_points.mode,
                terminal_state="PHASE_1_STABLE",
            )
            update_contract_surface_lifecycle(rounds_dir=config.rounds_dir, terminal=True)
            return ResumeResult(
                True,
                "PHASE_1_STABLE",
                closeout_result["round_number"],
                "phase_1",
                "operability",
                closeout_result["current_hash"],
                last_accepted_draft_hash,
                True,
            )
        if closeout_result["terminal_state"] is not None:
            return ResumeResult(
                True,
                closeout_result["terminal_state"],
                closeout_result["round_number"],
                "phase_1",
                "vertical",
                closeout_result["current_hash"],
                last_accepted_draft_hash,
                False,
            )
        round_number = closeout_result["round_number"]
        current_hash = closeout_result["current_hash"]
        profile_status = closeout_result["profile_status"]
        last_unresolved = closeout_result["last_unresolved"]
        last_reviewer_findings = closeout_result["last_reviewer_findings"]
    ReportWriter(root).write_technical_failure_report(
        round_number=round_number,
        final_draft_path="./spec.md",
        unresolved_blockers=[_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "blocker"],
        unresolved_major_issues=[_issue_summary(issue) for issue in last_unresolved if issue["normalized_severity"] == "major"],
        unresolved_conflicts=[],
        unresolved_oscillation=None,
        last_accepted_draft_hash=last_accepted_draft_hash,
        exit_reason="Phase 1 vertical review mode exhausted before reviewer-verified stable draft during resume continuation",
        recommendation="manual_review_required",
        profile_status=profile_status,
        last_reviewer_findings=last_reviewer_findings,
        terminal_state=terminal_state,
    )
    _write_phase1_state(
        config=config,
        current_round=round_number,
        active_profile=None,
        current_draft_hash=current_hash,
        last_accepted_draft_hash=last_accepted_draft_hash,
        seen_draft_hashes=seen_hashes,
        terminal_state=terminal_state,
        ready_for_phase_2=False,
    )
    write_decision_register(
        rounds_dir=config.rounds_dir,
        mode=config.decision_points.mode,
        terminal_state=terminal_state,
    )
    update_contract_surface_lifecycle(rounds_dir=config.rounds_dir, terminal=True)
    return ResumeResult(True, terminal_state, round_number, "phase_1", "vertical", current_hash, last_accepted_draft_hash, False)


def _run_vertical_closeout_check(
    root: Path,
    config: OrchestratorConfig,
    *,
    start_round: int,
    profile_state: dict[str, dict[str, Any]],
    seen_hashes: list[str],
    last_accepted_draft_hash: str | None,
    reviewer_client: ReviewerClient | None,
    editor_client: EditorClient | None,
    timeout_seconds: int | None,
) -> dict[str, Any]:
    profiles = ["structural_integrity", "determinism", "operability"]
    round_number = start_round - 1
    closeout_unresolved: list[dict[str, Any]] = []
    last_reviewer_findings: dict[str, Any] | None = None
    for profile in profiles:
        current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
        round_number += 1
        _write_phase1_state(
            config=config,
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
                root,
                config,
                reviewer_client=reviewer_client,
                editor_client=editor_client,
                timeout_seconds=timeout_seconds,
            ).run_review_only_round(round_number=round_number, profile=profile, phase="phase_1", overwrite=False)
        except ValueError:
            artifact_error = config.rounds_dir / "artifact_validation_error.json"
            if artifact_error.exists():
                packet = _read_json(artifact_error)
                terminal_state = str(packet.get("terminal_state", "HALTED_ARTIFACT_INVALID"))
                current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
                _write_phase1_state(
                    config=config,
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
        _append_continue_history(
            config.history_path,
            round_number=round_number,
            profile=profile,
            before_hash=review_result.draft_before_hash,
            after_hash=review_result.draft_after_hash,
            accepted=blocker_count == 0 and major_count == 0,
            blocker_count=blocker_count,
            major_count=major_count,
        )
    current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
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
        "profile_status": profile_status,
        "last_unresolved": closeout_unresolved,
        "last_reviewer_findings": last_reviewer_findings,
    }


def _validated_resume_context(config: OrchestratorConfig, *, continue_run: bool) -> dict[str, Any]:
    state_path = config.rounds_dir / "run_state.json"
    error_path = config.rounds_dir / "artifact_validation_error.json"
    if not state_path.exists() or not error_path.exists():
        raise ValueError("resume requires rounds/run_state.json and rounds/artifact_validation_error.json")
    state = _read_json(state_path)
    error = _read_json(error_path)
    if state.get("terminal_state") != "HALTED_CLIENT_TIMEOUT" or error.get("terminal_state") != "HALTED_CLIENT_TIMEOUT":
        raise ValueError("resume currently supports only HALTED_CLIENT_TIMEOUT")
    if error.get("failure_type") != "client_timeout":
        raise ValueError("resume currently supports only client_timeout failures")
    if error.get("client_role") != "editor":
        raise ValueError("resume currently supports only editor timeouts")
    if error.get("phase") != "phase_1":
        raise ValueError("resume currently supports only Phase 1 editor timeouts")

    current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
    expected_hash = str(error.get("last_valid_draft_hash") or state.get("current_draft_hash"))
    if current_hash != expected_hash:
        raise ValueError(f"current spec hash mismatch: expected {expected_hash}, got {current_hash}")

    round_number = int(error["round_number"])
    profile = str(error["profile"])
    scheduler, last_accepted_draft_hash, seen_hashes = _reconstruct_phase1_state(config, through_round=round_number - 1)
    if scheduler.next_profile() != profile:
        raise ValueError(f"resume profile mismatch: expected {scheduler.next_profile()!r}, artifact has {profile!r}")

    round_dir = config.rounds_dir / f"round-{round_number}"
    draft_before_path = round_dir / "draft_before.md"
    reviewer_feedback_path = round_dir / "reviewer_feedback.json"
    if not draft_before_path.exists() or not reviewer_feedback_path.exists():
        raise ValueError(f"resume requires round-{round_number}/draft_before.md and reviewer_feedback.json")
    draft_before_hash = draft_hash(draft_before_path.read_text(encoding="utf-8"))
    reviewer_feedback = _read_json(reviewer_feedback_path)
    _validate_reviewer_feedback(
        reviewer_feedback,
        round_number=round_number,
        profile=profile,
        draft_hash_value=draft_before_hash,
        schema_name="reviewer_feedback",
    )
    return {
        "state": state,
        "error": error,
        "terminal_state": str(error["terminal_state"]),
        "failure_type": str(error["failure_type"]),
        "phase": str(error["phase"]),
        "client_role": str(error["client_role"]),
        "round_number": round_number,
        "profile": profile,
        "scheduler": scheduler,
        "last_accepted_draft_hash": last_accepted_draft_hash,
        "seen_hashes": seen_hashes,
        "current_hash": current_hash,
        "expected_hash": expected_hash,
        "next_attempt_number": _next_attempt_number(error),
    }


def _validated_budget_extension_context(config: OrchestratorConfig, *, extend_review_budget: int) -> dict[str, Any]:
    if extend_review_budget < 1:
        raise ValueError("--extend-review-budget must be greater than or equal to 1")
    state_path = config.rounds_dir / "run_state.json"
    if not state_path.exists():
        raise ValueError("budget-extension resume requires rounds/run_state.json")
    state = _read_json(state_path)
    terminal_state = str(state.get("terminal_state") or "")
    if terminal_state not in BUDGET_EXTENSION_TERMINAL_STATES:
        raise ValueError(
            "budget-extension resume supports only TARGET_NOT_REACHED or "
            "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS"
        )
    if state.get("phase") != "phase_1":
        raise ValueError("budget-extension resume currently supports only Phase 1 runs")
    if config.review_mode not in {"horizontal", "vertical"}:
        raise ValueError("budget-extension resume currently supports only horizontal or vertical review mode")
    current_round = int(state.get("current_round") or 0)
    if current_round < 1:
        raise ValueError("budget-extension resume requires at least one completed round")
    current_hash = draft_hash(config.spec_path.read_text(encoding="utf-8"))
    expected_hash = str(state.get("current_draft_hash") or "")
    if current_hash != expected_hash:
        raise ValueError(f"current spec hash mismatch: expected {expected_hash}, got {current_hash}")
    if config.review_mode == "vertical":
        _reconstruct_vertical_phase1_state(config, through_round=current_round)
    else:
        _reconstruct_phase1_state(config, through_round=current_round)
    return state


def _empty_vertical_profile_state(budgets: dict[str, int]) -> dict[str, dict[str, Any]]:
    return {
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
        for profile in ("structural_integrity", "determinism", "operability")
    }


def _reconstruct_vertical_phase1_state(config: OrchestratorConfig, *, through_round: int) -> dict[str, Any]:
    budgets = resolved_phase_1_profile_budgets(config.review_profile_budgets)
    profile_state = _empty_vertical_profile_state(budgets)
    seen_hashes: list[str] = []
    last_accepted_draft_hash: str | None = None
    last_unresolved: list[dict[str, Any]] = []
    last_reviewer_findings: dict[str, Any] | None = None
    if through_round < 1:
        seen_hashes.append(draft_hash(config.spec_path.read_text(encoding="utf-8")))
        return {
            "profile_state": profile_state,
            "last_accepted_draft_hash": last_accepted_draft_hash,
            "seen_hashes": seen_hashes,
            "last_unresolved": last_unresolved,
            "last_reviewer_findings": last_reviewer_findings,
        }
    for round_number in range(1, through_round + 1):
        round_dir = config.rounds_dir / f"round-{round_number}"
        reviewer_feedback = _read_json(round_dir / "reviewer_feedback.json")
        editor_summary = _read_json(round_dir / "editor_summary.json")
        draft_before_hash = draft_hash(round_dir.joinpath("draft_before.md").read_text(encoding="utf-8"))
        draft_after_hash = draft_hash(round_dir.joinpath("draft_after.md").read_text(encoding="utf-8"))
        if round_number == 1:
            seen_hashes.append(draft_before_hash)
        profile = str(reviewer_feedback["profile"])
        if profile in profile_state:
            state = profile_state[profile]
            blocker_count = _reviewer_count(reviewer_feedback, "blocker")
            major_count = _reviewer_count(reviewer_feedback, "major")
            state["rounds_used"] = int(state["rounds_used"]) + 1
            state["clean"] = blocker_count == 0 and major_count == 0
            state["verified_draft_hash"] = draft_after_hash
            state["exhausted"] = not state["clean"] and int(state["rounds_used"]) >= int(state["round_budget"])
            state["residual_status"] = "exhausted_with_residuals" if state["exhausted"] else None
            last_reviewer_findings = _last_reviewer_findings(
                round_number=round_number,
                profile=profile,
                reviewer_feedback=reviewer_feedback,
                blocker_count=blocker_count,
                major_count=major_count,
            )
        elif profile == "vertical":
            last_unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
            if not any(issue.get("normalized_severity") in {"blocker", "major"} for issue in last_unresolved):
                last_accepted_draft_hash = draft_after_hash
            seen_hashes.append(draft_after_hash)
        else:
            raise ValueError(f"round-{round_number} has unsupported vertical resume profile {profile!r}")
    return {
        "profile_state": profile_state,
        "last_accepted_draft_hash": last_accepted_draft_hash,
        "seen_hashes": seen_hashes,
        "last_unresolved": last_unresolved,
        "last_reviewer_findings": last_reviewer_findings,
    }


def _extend_vertical_profile_state(
    profile_state: dict[str, dict[str, Any]],
    extended_budgets: dict[str, int],
) -> dict[str, dict[str, Any]]:
    for profile, state in profile_state.items():
        state["round_budget"] = extended_budgets[profile]
        if bool(state["clean"]):
            state["exhausted"] = False
            state["residual_status"] = None
        else:
            state["exhausted"] = int(state["rounds_used"]) >= int(state["round_budget"])
            state["residual_status"] = "exhausted_with_residuals" if state["exhausted"] else None
    return profile_state


def _extended_vertical_budgets(
    original_budgets: dict[str, int],
    profile_state: dict[str, dict[str, Any]],
    *,
    extend_review_budget: int,
) -> dict[str, int]:
    return {
        profile: max(original_budgets[profile], int(profile_state[profile]["rounds_used"])) + extend_review_budget
        for profile in original_budgets
    }


def _extended_horizontal_budgets(
    original_budgets: dict[str, int],
    scheduler: Any,
    *,
    extend_review_budget: int,
) -> dict[str, int]:
    return {
        step.profile: max(original_budgets[step.profile], int(state.rounds_used)) + extend_review_budget
        for step, state in zip(scheduler.steps, scheduler.states)
    }


def _extend_phase1_scheduler_budgets(scheduler: Any, extended_budgets: dict[str, int]) -> None:
    for index, step in enumerate(scheduler.steps):
        scheduler.steps[index] = replace(step, round_budget=extended_budgets[step.profile])
    for index, (step, state) in enumerate(zip(scheduler.steps, scheduler.states)):
        if not state.clean and state.rounds_used < step.effective_round_budget:
            scheduler.index = index
            return
    scheduler.index = len(scheduler.steps)


def _reconstruct_phase1_state(config: OrchestratorConfig, *, through_round: int) -> tuple[Any, str | None, list[str]]:
    scheduler = default_phase_1_scheduler(config.review_profile_budgets)
    seen_hashes: list[str] = []
    last_accepted_draft_hash: str | None = None
    if through_round < 1:
        seen_hashes.append(draft_hash(config.spec_path.read_text(encoding="utf-8")))
        return scheduler, last_accepted_draft_hash, seen_hashes
    for round_number in range(1, through_round + 1):
        round_dir = config.rounds_dir / f"round-{round_number}"
        reviewer_feedback = _read_json(round_dir / "reviewer_feedback.json")
        editor_summary = _read_json(round_dir / "editor_summary.json")
        draft_before_hash = draft_hash(round_dir.joinpath("draft_before.md").read_text(encoding="utf-8"))
        draft_after_hash = draft_hash(round_dir.joinpath("draft_after.md").read_text(encoding="utf-8"))
        if round_number == 1:
            seen_hashes.append(draft_before_hash)
        profile = str(reviewer_feedback["profile"])
        if scheduler.next_profile() != profile:
            raise ValueError(f"round-{round_number} profile does not match scheduler")
        reviewer_blocker_count = _reviewer_count(reviewer_feedback, "blocker")
        reviewer_major_count = _reviewer_count(reviewer_feedback, "major")
        reviewer_clean = reviewer_blocker_count == 0 and reviewer_major_count == 0
        scheduler.record_result(
            profile,
            blocker_count=reviewer_blocker_count,
            major_count=reviewer_major_count + (
                1
                if reviewer_clean
                and _mutation_requires_verification(
                    round_dir=round_dir,
                    editor_summary=editor_summary,
                    spec_mutated=draft_before_hash != draft_after_hash,
                )
                else 0
            ),
        )
        unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
        if not any(issue.get("normalized_severity") in {"blocker", "major"} for issue in unresolved):
            last_accepted_draft_hash = draft_after_hash
        seen_hashes.append(draft_after_hash)
    return scheduler, last_accepted_draft_hash, seen_hashes


def _write_phase1_state(
    *,
    config: OrchestratorConfig,
    current_round: int,
    active_profile: str | None,
    current_draft_hash: str,
    last_accepted_draft_hash: str | None,
    seen_draft_hashes: list[str],
    terminal_state: str | None,
    ready_for_phase_2: bool,
) -> None:
    config.rounds_dir.mkdir(parents=True, exist_ok=True)
    review_round_budget = default_phase_1_scheduler(config.review_profile_budgets).total_round_budget()
    convergence_round_budget = default_phase_2_scheduler(config.convergence_profile_budgets).total_round_budget()
    review_profile_budgets = resolved_phase_1_profile_budgets(config.review_profile_budgets)
    if config.review_mode == "vertical" and review_profile_budgets:
        review_round_budget += max(review_profile_budgets.values())
    convergence_profile_budgets = resolved_phase_2_profile_budgets(config.convergence_profile_budgets)
    existing_state = _read_json_object(config.rounds_dir / "run_state.json")
    budget_extensions = []
    if existing_state and isinstance(existing_state.get("budget_extensions"), list):
        budget_extensions = existing_state["budget_extensions"]
    packet = {
        "current_round": current_round,
        "current_absolute_round": current_round,
        "current_phase_round": current_round,
        "phase": "phase_1",
        "phase_1_rounds_completed": current_round,
        "phase_2_rounds_completed": 0,
        "review_max_rounds": config.review_max_rounds,
        "review_mode": config.review_mode,
        "review_budget_exhaustion_policy": config.review_budget_exhaustion_policy,
        "configured_review_profile_budgets": config.review_profile_budgets,
        "review_profile_budgets": review_profile_budgets,
        "review_round_budget": review_round_budget,
        "convergence_max_rounds": config.convergence.max_rounds,
        "configured_convergence_profile_budgets": config.convergence_profile_budgets,
        "convergence_profile_budgets": convergence_profile_budgets,
        "convergence_round_budget": convergence_round_budget,
        "total_absolute_round_budget": review_round_budget + convergence_round_budget,
        "timeouts": {
            "reviewer_seconds": config.timeouts.reviewer_seconds,
            "editor_seconds": config.timeouts.editor_seconds,
        },
        "effective_run_config": effective_run_config(config),
        "active_profile": active_profile,
        "current_draft_hash": current_draft_hash,
        "last_accepted_draft_hash": last_accepted_draft_hash,
        "seen_draft_hashes": seen_draft_hashes,
        "terminal_state": terminal_state,
        "ready_for_phase_2": ready_for_phase_2,
        "telemetry_totals": run_telemetry_totals(config.rounds_dir),
        "budget_extensions": budget_extensions,
        "resumable": terminal_state == "HALTED_CLIENT_TIMEOUT" or terminal_state in BUDGET_EXTENSION_TERMINAL_STATES,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    (config.rounds_dir / "run_state.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_budget_extension_event(
    *,
    config: OrchestratorConfig,
    previous_state: dict[str, Any],
    original_budgets: dict[str, int],
    extended_budgets: dict[str, int],
    extension_rounds: int,
) -> None:
    state_path = config.rounds_dir / "run_state.json"
    state = _read_json_object(state_path) or previous_state
    events = state.get("budget_extensions")
    if not isinstance(events, list):
        events = []
    events.append(
        {
            "event_id": f"budget_extension_{len(events) + 1:03d}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phase": "phase_1",
            "previous_terminal_state": previous_state.get("terminal_state"),
            "previous_current_round": previous_state.get("current_round"),
            "previous_review_profile_budgets": original_budgets,
            "new_review_profile_budgets": extended_budgets,
            "added_rounds_per_profile": extension_rounds,
            "reason": "operator_requested_resume_budget_extension",
        }
    )
    state["budget_extensions"] = events
    state["review_profile_budgets"] = extended_budgets
    state["effective_run_config"] = effective_run_config(config)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_resume_history(
    history_path: Path,
    *,
    round_number: int,
    profile: str,
    before_hash: str,
    after_hash: str,
    accepted: bool,
    blocker_count: int,
    major_count: int,
) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as history_file:
        history_file.write(
            f"- Resumed Phase 1 round {round_number}: profile `{profile}`, "
            f"before `{before_hash}`, after `{after_hash}`, "
            f"accepted={str(accepted).lower()}, blockers={blocker_count}, majors={major_count}.\n"
        )


def _append_continue_history(
    history_path: Path,
    *,
    round_number: int,
    profile: str,
    before_hash: str,
    after_hash: str,
    accepted: bool,
    blocker_count: int,
    major_count: int,
) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as history_file:
        history_file.write(
            f"- Continued Phase 1 round {round_number} after resume: profile `{profile}`, "
            f"before `{before_hash}`, after `{after_hash}`, "
            f"accepted={str(accepted).lower()}, blockers={blocker_count}, majors={major_count}.\n"
        )


def _next_attempt_number(error: dict[str, Any]) -> int:
    attempts = error.get("attempts", [])
    if not isinstance(attempts, list) or not attempts:
        return 1
    return max(int(attempt.get("attempt_number", 0)) for attempt in attempts) + 1


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


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
            if not item["clean"] and not item["exhausted"] and int(item["rounds_used"]) < int(item["round_budget"])
        ],
        "total_round_budget": sum(int(item["round_budget"]) for item in profiles),
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
