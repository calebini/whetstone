"""Read-only run status summaries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
from typing import Any

from whetstone.config import OrchestratorConfig
from whetstone.context_pressure import REPORT_JSON
from whetstone.hashing import draft_hash
from whetstone.live import run_telemetry_totals
from whetstone.run_state import apply_effective_run_config, run_artifact_pointers
from whetstone.scheduler import (
    default_phase_1_scheduler,
    default_phase_2_scheduler,
    resolved_phase_1_profile_budgets,
    resolved_phase_2_profile_budgets,
)
from whetstone.scope import read_scope_contract, scope_contract_summary


ROUND_REQUIRED_ARTIFACTS = (
    "draft_before.md",
    "draft_after.md",
    "profile_used.yaml",
    "prompt_snapshot.json",
    "reviewer_feedback.json",
    "editor_summary.json",
    "unresolved_issues.json",
    "decision_points.json",
    "operator_decision_checkpoint.json",
    "telemetry_summary.json",
)

TERMINAL_REPORTS = (
    "convergence_failure_report.json",
    "technical_failure_report.json",
    "conflict_report.json",
    "oscillation_report.json",
    "artifact_validation_error.json",
    "config_validation_error.json",
)
PHASE_2_PROFILES = {"convergence_strict_check", "adversarial", "mvp_readiness_check", "scope_guard"}


def read_status(*, root: Path, config: OrchestratorConfig) -> dict[str, Any]:
    """Return a stable read-only snapshot of the current Whetstone run."""
    rounds_dir = config.rounds_dir
    state_path = rounds_dir / "run_state.json"
    run_state = _read_json_object(state_path)
    latest_round = _latest_round(rounds_dir, root)
    inferred_rounds = _inferred_round_accounting(rounds_dir, run_state)
    decision_summary = _decision_summary(rounds_dir, root)
    checkpoint_summary = _checkpoint_summary(rounds_dir, root)
    terminal_report_path = _terminal_report_path(rounds_dir, run_state)
    terminal_report = _read_json_object(terminal_report_path) if terminal_report_path else None
    historical_terminal_reports = _historical_terminal_reports(
        rounds_dir,
        root,
        run_state,
        active_terminal_report_path=terminal_report_path,
    )
    current_draft_status = _current_draft_status(run_state, terminal_report)
    telemetry_totals = _telemetry_totals(rounds_dir, run_state)
    apply_back = _apply_back_status(root, rounds_dir, run_state)
    resume_status = _resume_status(root, rounds_dir, run_state, config)
    scope_status = _scope_status(root, config)
    artifact_pointers = _artifact_pointers(root, config, run_state)
    root_draft_hash = _draft_hash_or_none(root / "spec.md")
    context_pressure = _context_pressure_status(rounds_dir, root)
    round_context_pressure = _round_context_pressure_status(rounds_dir, root)
    status_warnings = _status_warnings(rounds_dir, root, run_state, terminal_report_path=terminal_report_path)
    default_review_round_budget = default_phase_1_scheduler(
        config.review_profile_budgets,
        profile_set=config.review_profile_set,
    ).total_round_budget()
    default_convergence_round_budget = default_phase_2_scheduler(
        config.convergence_profile_budgets,
        profile_set=config.review_profile_set,
    ).total_round_budget()
    default_review_profile_budgets = resolved_phase_1_profile_budgets(
        config.review_profile_budgets,
        profile_set=config.review_profile_set,
    )
    default_convergence_profile_budgets = resolved_phase_2_profile_budgets(
        config.convergence_profile_budgets,
        profile_set=config.review_profile_set,
    )
    packet = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "rounds_dir": _path_or_none(rounds_dir, root),
        "run_state_path": _path_or_none(state_path, root) if state_path.exists() else None,
        "run_state_exists": run_state is not None,
        "run_mode": run_state.get("run_mode") if run_state else None,
        "phase": run_state.get("phase") if run_state else None,
        "current_round": run_state.get("current_round") if run_state else None,
        "current_absolute_round": run_state.get("current_absolute_round", run_state.get("current_round")) if run_state else None,
        "current_phase_round": (run_state.get("current_phase_round") if run_state else None)
        or inferred_rounds.get("current_phase_round"),
        "phase_1_rounds_completed": (run_state.get("phase_1_rounds_completed") if run_state else None)
        or inferred_rounds.get("phase_1_rounds_completed"),
        "phase_2_rounds_completed": (run_state.get("phase_2_rounds_completed") if run_state else None)
        or inferred_rounds.get("phase_2_rounds_completed"),
        "review_profile_set": (run_state.get("review_profile_set") if run_state else None) or config.review_profile_set,
        "review_round_budget": (run_state.get("review_round_budget") if run_state else None)
        or default_review_round_budget,
        "review_profile_budgets": (run_state.get("review_profile_budgets") if run_state else None)
        or default_review_profile_budgets,
        "convergence_round_budget": (run_state.get("convergence_round_budget") if run_state else None)
        or default_convergence_round_budget,
        "convergence_profile_budgets": (run_state.get("convergence_profile_budgets") if run_state else None)
        or default_convergence_profile_budgets,
        "total_absolute_round_budget": (run_state.get("total_absolute_round_budget") if run_state else None)
        or (default_review_round_budget + default_convergence_round_budget),
        "active_profile": run_state.get("active_profile") if run_state else None,
        "terminal_state": run_state.get("terminal_state") if run_state else None,
        "ready_for_phase_2": run_state.get("ready_for_phase_2") if run_state else False,
        "current_draft_status": current_draft_status,
        "current_draft_hash": run_state.get("current_draft_hash") if run_state else None,
        "root_draft_hash": root_draft_hash,
        "root_draft_matches_run_state": (
            None
            if root_draft_hash is None or not run_state or run_state.get("current_draft_hash") is None
            else root_draft_hash == run_state.get("current_draft_hash")
        ),
        "last_accepted_draft_hash": run_state.get("last_accepted_draft_hash") if run_state else None,
        "resumable": bool(run_state.get("resumable")) or bool(resume_status.get("eligible")) if run_state else False,
        "resume": resume_status,
        "scope_contract": scope_status,
        "run_artifact_pointers": artifact_pointers,
        "context_pressure": context_pressure,
        "round_context_pressure": round_context_pressure,
        "latest_round": latest_round,
        "terminal_report_path": _path_or_none(terminal_report_path, root) if terminal_report_path else None,
        "decision_register": _decision_register(rounds_dir, root),
        "decision_summary": decision_summary,
        "operator_decision_checkpoint_summary": checkpoint_summary,
        "apply_back": apply_back,
        "telemetry_totals": telemetry_totals,
        "next_action": _next_action(run_state, terminal_report_path=terminal_report_path),
        "historical_terminal_reports": historical_terminal_reports,
        "status_warnings": status_warnings,
    }
    from whetstone.preservation_runtime import readback, active
    try:
        packet['preservation_bridge'] = readback(root, config)
    except (OSError, ValueError) as exc:
        packet['preservation_bridge'] = {
            'mode': 'enforce' if active(root, config) else 'legacy_unguarded',
            'capability_version': 'preservation-bridge-v1' if active(root, config) else None,
            'latest_proposal': None, 'latest_attempt_report': None, 'pending_acceptance_admission': None,
            'accepted': None, 'pending_outcome': 'technical_failure', 'next_action': 'inspect_and_repair'}
        packet['status_warnings'].append(f'Preservation evidence cannot be verified: {exc}')
    if active(root, config):
        preservation = packet['preservation_bridge']
        packet['next_action'] = preservation['next_action']
        packet['resumable'] = bool(packet['resume']['eligible'])
        verified_complete = bool(packet['resume'].get('verified_complete'))
        packet['ready_for_phase_2'] = verified_complete and packet['terminal_state'] == 'PHASE_1_STABLE'
        packet['apply_back']['available'] = False
        if packet['terminal_state'] == 'CONVERGED':
            try:
                from whetstone.preservation_consumers import verify_convergence
                verify_convergence(root, declaration_required=True)
                packet['apply_back']['available'] = True
                packet['next_action'] = 'none'
            except (OSError, ValueError) as exc:
                packet['next_action'] = 'inspect_and_repair'
                packet['status_warnings'].append(f'Convergence cannot be verified: {exc}')
        if preservation['pending_outcome'] == 'technical_failure' and not packet['resumable']:
            packet['next_action'] = 'inspect_and_repair'
        if preservation['pending_outcome'] is None and packet['terminal_state'] in {'PHASE_1_STABLE', 'FOCUSED_PROFILE_STABLE'} and verified_complete:
            packet['next_action'] = 'none'
    return packet


def render_status_text(status: dict[str, Any]) -> str:
    """Render a compact human-readable status summary."""
    bridge = status.get('preservation_bridge', {})
    latest_round = status.get("latest_round") or {}
    decision_register = status.get("decision_register") or {}
    decision_summary = status.get("decision_summary") or {}
    checkpoint_summary = status.get("operator_decision_checkpoint_summary") or {}
    telemetry = status.get("telemetry_totals") or {}
    apply_back = status.get("apply_back") or {}
    resume_status = status.get("resume") or {}
    artifact_pointers = status.get("run_artifact_pointers") or {}
    context_pressure = status.get("context_pressure") or {}
    round_context_pressure = status.get("round_context_pressure") or {}
    status_warnings = status.get("status_warnings") or []
    latest_round_text = "none"
    if latest_round:
        completeness = "complete" if latest_round.get("complete") else "partial"
        profile = latest_round.get("profile")
        round_kind = latest_round.get("round_kind")
        details = ", ".join(str(item) for item in (profile, round_kind) if item)
        latest_round_text = f"round-{latest_round.get('round_number')} {completeness}"
        if details:
            latest_round_text += f" ({details})"
    lines = [
        "Whetstone Status",
        f"root: {status.get('root')}",
        f"phase: {_display(status.get('phase'))}",
        f"run_mode: {_display(status.get('run_mode'))}",
        f"profile_set: {_display(status.get('review_profile_set'))}",
        f"current_round: {_display(status.get('current_round'))}",
        f"current_absolute_round: {_display(status.get('current_absolute_round'))}",
        f"current_phase_round: {_display(status.get('current_phase_round'))}",
        f"round_budgets: phase1={_display(status.get('review_round_budget'))}, "
        f"phase2={_display(status.get('convergence_round_budget'))}, "
        f"absolute={_display(status.get('total_absolute_round_budget'))}",
        f"terminal_state: {_display(status.get('terminal_state'))}",
        f"active_profile: {_display(status.get('active_profile'))}",
        f"ready_for_phase_2: {str(bool(status.get('ready_for_phase_2'))).lower()}",
        f"current_draft_status: {_display(status.get('current_draft_status'))}",
        f"root_draft_matches_run_state: {_display(status.get('root_draft_matches_run_state'))}",
        f"resumable: {str(bool(status.get('resumable'))).lower()}",
        f"scope_contract: {_scope_display(status.get('scope_contract'))}",
        f"artifact_pointers: {_artifact_pointer_display(artifact_pointers)}",
        f"context_pressure: {_context_pressure_display(context_pressure)}",
        f"round_context_pressure: {_round_context_pressure_display(round_context_pressure)}",
        f"last_accepted_draft_hash: {_display(status.get('last_accepted_draft_hash'))}",
        f"latest_round: {latest_round_text}",
        f"next_action: {_display(status.get('next_action'))}",
        f"terminal_report: {_display(status.get('terminal_report_path'))}",
        f"historical_terminal_reports: {_display(status.get('historical_terminal_reports'))}",
        f"status_warnings: {_display(status_warnings)}",
        (
            "decisions: "
            f"{_display(decision_summary.get('decision_count', decision_register.get('decision_count')))}, "
            f"human: {_display(decision_summary.get('unresolved_human_decision_count', decision_register.get('unresolved_human_decision_count')))}, "
            f"statuses: {_display(decision_summary.get('decision_status_counts', decision_register.get('decision_status_counts')))}"
        ),
        (
            "decision_checkpoints: "
            f"{_display(checkpoint_summary.get('checkpoint_count'))}, "
            f"rounds: {_display(checkpoint_summary.get('rounds_with_checkpoints'))}, "
            f"triggers: {_display(checkpoint_summary.get('trigger_reason_counts'))}"
        ),
        (
            "telemetry: "
            f"{_display(telemetry.get('round_count'))} rounds, "
            f"{_display(telemetry.get('attempt_count'))} attempts, "
            f"{_display(telemetry.get('total_tokens'))} tokens"
        ),
        (
            "apply_back: "
            f"available={str(bool(apply_back.get('available'))).lower()}, "
            f"applied={_display(apply_back.get('applied'))}, "
            f"final_draft={_display(apply_back.get('final_draft_path'))}"
        ),
    ]
    if latest_round and not latest_round.get("complete"):
        missing = ", ".join(latest_round.get("missing_required_artifacts", []))
        lines.append(f"missing_round_artifacts: {missing}")
        pending = latest_round.get("pending_client_attempt")
        if pending:
            lines.append(
                "pending_client_attempt: "
                f"{pending.get('client_role')} {pending.get('artifact_name')} "
                f"attempt {pending.get('attempt_number')}"
            )
    if resume_status.get("eligible"):
        lines.append(f"resume_command: {resume_status.get('command')}")
        lines.append(f"resume_continue_command: {resume_status.get('continue_command')}")
    lines.append(f"Preservation: {bridge.get('mode', 'legacy_unguarded')}; next: {bridge.get('next_action', 'none')}")
    lines.append(f"Preservation: {bridge.get('mode', 'legacy_unguarded')}; next: {bridge.get('next_action', 'none')}")
    return "\n".join(lines) + "\n"


def _latest_round(rounds_dir: Path, root: Path) -> dict[str, Any] | None:
    round_dirs = [
        path
        for path in rounds_dir.glob("round-*")
        if path.is_dir() and path.name.removeprefix("round-").isdigit()
    ]
    if not round_dirs:
        return None
    round_dir = sorted(round_dirs, key=lambda path: int(path.name.removeprefix("round-")))[-1]
    present = sorted(path.name for path in round_dir.iterdir())
    missing = [name for name in ROUND_REQUIRED_ARTIFACTS if not (round_dir / name).exists()]
    return {
        "round_number": int(round_dir.name.removeprefix("round-")),
        "path": _path_or_none(round_dir, root),
        "complete": not missing,
        **_round_profile_metadata(round_dir / "profile_used.yaml"),
        "present_artifacts": present,
        "missing_required_artifacts": missing,
        "pending_client_attempt": _pending_client_attempt(round_dir, root),
    }


def _scope_status(root: Path, config: OrchestratorConfig) -> dict[str, Any]:
    try:
        contract = read_scope_contract(config.scope_contract.path)
    except Exception as exc:
        return {
            "path": _path_or_none(config.scope_contract.path, root),
            "exists": config.scope_contract.path.exists(),
            "valid": False,
            "error": str(exc),
        }
    if contract is None:
        return {
            "path": _path_or_none(config.scope_contract.path, root),
            "exists": False,
            "valid": False,
            "approved": False,
        }
    summary = scope_contract_summary(contract, root=root) or {}
    return {"exists": True, "valid": True, **summary}


def _artifact_pointers(root: Path, config: OrchestratorConfig, run_state: dict[str, Any] | None) -> dict[str, Any]:
    if run_state and isinstance(run_state.get("run_artifact_pointers"), dict):
        return run_state["run_artifact_pointers"]
    return run_artifact_pointers(root, config)


def _context_pressure_status(rounds_dir: Path, root: Path) -> dict[str, Any] | None:
    path = rounds_dir / REPORT_JSON
    packet = _read_json_object(path)
    if packet is None:
        return None
    totals = packet.get("totals") if isinstance(packet.get("totals"), dict) else {}
    warnings = packet.get("warnings") if isinstance(packet.get("warnings"), list) else []
    return {
        "path": _path_or_none(path, root),
        "behavior": packet.get("behavior"),
        "action_taken": packet.get("action_taken"),
        "component_count": totals.get("component_count"),
        "existing_component_count": totals.get("existing_component_count"),
        "byte_count": totals.get("byte_count"),
        "estimated_tokens": totals.get("estimated_tokens"),
        "warning_count": len(warnings),
        "warning_codes": [item.get("code") for item in warnings if isinstance(item, dict)],
    }


def _round_context_pressure_status(rounds_dir: Path, root: Path) -> dict[str, Any] | None:
    reports: list[dict[str, Any]] = []
    round_dirs = [
        path
        for path in rounds_dir.glob("round-*")
        if path.is_dir() and path.name.removeprefix("round-").isdigit()
    ]
    for round_dir in sorted(round_dirs, key=lambda path: int(path.name.removeprefix("round-"))):
        path = round_dir / REPORT_JSON
        packet = _read_json_object(path)
        if packet is None:
            continue
        totals = packet.get("totals") if isinstance(packet.get("totals"), dict) else {}
        referenced = packet.get("referenced_context") if isinstance(packet.get("referenced_context"), dict) else {}
        reports.append(
            {
                "round_number": int(round_dir.name.removeprefix("round-")),
                "path": _path_or_none(path, root),
                "profile": packet.get("profile"),
                "phase": packet.get("phase"),
                "byte_count": totals.get("byte_count", 0),
                "estimated_tokens": totals.get("estimated_tokens", 0),
                "component_count": totals.get("component_count", 0),
                "referenced_context_count": referenced.get("reference_count", 0),
            }
        )
    if not reports:
        return None
    max_by_tokens = max(reports, key=lambda item: int(item.get("estimated_tokens") or 0))
    latest = reports[-1]
    return {
        "round_report_count": len(reports),
        "latest": latest,
        "max_estimated_tokens": max_by_tokens,
        "total_referenced_context_count": sum(int(item.get("referenced_context_count") or 0) for item in reports),
    }


def _decision_register(rounds_dir: Path, root: Path) -> dict[str, Any] | None:
    path = rounds_dir / "decision_register.json"
    packet = _read_json_object(path)
    if packet is None:
        return None
    return {
        "path": _path_or_none(path, root),
        "decision_count": len(packet.get("decision_points", [])),
        "decision_status_counts": packet.get("decision_status_counts"),
        "unresolved_human_decision_count": packet.get("unresolved_human_decision_count"),
    }


def _decision_summary(rounds_dir: Path, root: Path) -> dict[str, Any] | None:
    path = rounds_dir / "decision_summary.json"
    packet = _read_json_object(path)
    if packet is None:
        return None
    return {
        "path": _path_or_none(path, root),
        "decision_count": packet.get("decision_count"),
        "decision_status_counts": packet.get("decision_status_counts"),
        "unresolved_human_decision_count": packet.get("unresolved_human_decision_count"),
        "hotspots": packet.get("hotspots"),
    }


def _checkpoint_summary(rounds_dir: Path, root: Path) -> dict[str, Any] | None:
    path = rounds_dir / "operator_decision_checkpoint_summary.json"
    packet = _read_json_object(path)
    if packet is None:
        return None
    return {
        "path": _path_or_none(path, root),
        "checkpoint_count": packet.get("checkpoint_count"),
        "rounds_with_checkpoints": packet.get("rounds_with_checkpoints"),
        "trigger_reason_counts": packet.get("trigger_reason_counts"),
        "source_type_counts": packet.get("source_type_counts"),
        "recommended_operator_review": packet.get("recommended_operator_review"),
    }


def _terminal_report_path(rounds_dir: Path, run_state: dict[str, Any] | None = None) -> Path | None:
    terminal_state = (run_state or {}).get("terminal_state")
    if terminal_state in {"CONVERGED", "PHASE_1_STABLE", "FOCUSED_PROFILE_STABLE"}:
        return None
    for name in TERMINAL_REPORTS:
        path = rounds_dir / name
        if path.exists():
            packet = _read_json_object(path)
            if _terminal_report_matches_run_state(packet, run_state):
                return path
    return None


def _terminal_report_matches_run_state(packet: dict[str, Any] | None, run_state: dict[str, Any] | None) -> bool:
    if packet is None:
        return False
    if not run_state:
        return True
    if packet.get("terminal_state") != run_state.get("terminal_state"):
        return False
    report_round = packet.get("round_number")
    current_round = run_state.get("current_round")
    if isinstance(report_round, int) and isinstance(current_round, int) and report_round != current_round:
        return False
    report_hash = packet.get("draft_hash") or packet.get("last_draft_hash")
    current_hash = run_state.get("current_draft_hash")
    if isinstance(report_hash, str) and isinstance(current_hash, str) and report_hash != current_hash:
        return False
    return True


def _terminal_report_superseded_by_run_state(packet: dict[str, Any], run_state: dict[str, Any] | None) -> bool:
    if not run_state:
        return False
    current_terminal_state = run_state.get("terminal_state")
    current_round = run_state.get("current_round")
    if current_terminal_state in {"CONVERGED", "PHASE_1_STABLE", "FOCUSED_PROFILE_STABLE"}:
        return True
    if packet.get("terminal_state") != current_terminal_state:
        return True
    report_round = packet.get("round_number")
    if isinstance(current_round, int) and isinstance(report_round, int) and report_round < current_round:
        return True
    report_hash = packet.get("draft_hash") or packet.get("last_draft_hash")
    current_hash = run_state.get("current_draft_hash")
    return isinstance(report_hash, str) and isinstance(current_hash, str) and report_hash != current_hash


def _historical_terminal_reports(
    rounds_dir: Path,
    root: Path,
    run_state: dict[str, Any] | None,
    *,
    active_terminal_report_path: Path | None,
) -> list[dict[str, Any]]:
    current_terminal_state = (run_state or {}).get("terminal_state")
    current_round = (run_state or {}).get("current_round")
    historical: list[dict[str, Any]] = []
    for name in TERMINAL_REPORTS:
        path = rounds_dir / name
        if not path.exists() or path == active_terminal_report_path:
            continue
        packet = _read_json_object(path) or {}
        report_round = packet.get("round_number")
        superseded = _terminal_report_superseded_by_run_state(packet, run_state)
        historical.append(
            {
                "path": _path_or_none(path, root),
                "report_terminal_state": packet.get("terminal_state"),
                "report_round_number": report_round,
                "lifecycle_status": "historical_superseded" if superseded else "historical_non_active",
                "superseded_by_terminal_state": current_terminal_state if superseded else None,
                "superseded_by_round_number": current_round if superseded else None,
            }
        )
    return historical


def _current_draft_status(run_state: dict[str, Any] | None, terminal_report: dict[str, Any] | None) -> str | None:
    if run_state and run_state.get("terminal_state") == "PHASE_1_STABLE" and run_state.get("ready_for_phase_2") is True:
        return "phase_1_stable"
    if run_state and run_state.get("terminal_state") == "CONVERGED":
        return "converged"
    if run_state and run_state.get("terminal_state") is not None:
        current_hash = run_state.get("current_draft_hash")
        accepted_hash = run_state.get("last_accepted_draft_hash")
        if current_hash is not None and accepted_hash is not None:
            return "accepted_unverified_profiles" if current_hash == accepted_hash else "not_accepted"
    return terminal_report.get("current_draft_status") if terminal_report else None


def _status_warnings(
    rounds_dir: Path,
    root: Path,
    run_state: dict[str, Any] | None,
    *,
    terminal_report_path: Path | None,
) -> list[dict[str, Any]]:
    if not run_state:
        return []
    warnings: list[dict[str, Any]] = []
    terminal_state = run_state.get("terminal_state")
    stale_reports = _stale_terminal_reports(rounds_dir, root, run_state, active_terminal_report_path=terminal_report_path)
    if stale_reports:
        warnings.append(
            {
                "code": "stale_terminal_report",
                "message": "terminal report artifact is older than current run_state and is treated as historical",
                "reports": stale_reports,
            }
        )
    if terminal_state in {
        "TARGET_NOT_REACHED",
        "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS",
        "HALTED_CONFLICT",
        "HALTED_OSCILLATION",
        "HALTED_ARTIFACT_INVALID",
        "HALTED_CLIENT_TIMEOUT",
        "CONFIG_INVALID",
    } and terminal_report_path is None and not stale_reports:
        warnings.append(
            {
                "code": "terminal_report_missing",
                "message": "run_state has a terminal failure state but no terminal report artifact was found",
                "terminal_state": terminal_state,
            }
        )
    root_draft_hash = _draft_hash_or_none(root / "spec.md")
    current_draft_hash = run_state.get("current_draft_hash")
    if root_draft_hash is not None and current_draft_hash is not None and root_draft_hash != current_draft_hash:
        warnings.append(
            {
                "code": "root_draft_hash_mismatch",
                "message": "root spec.md hash differs from run_state.current_draft_hash; run_state remains authoritative until the draft is reconciled",
                "root_draft_hash": root_draft_hash,
                "run_state_current_draft_hash": current_draft_hash,
            }
        )
    if run_state.get("phase") is not None and run_state.get("run_mode") is None:
        warnings.append(
            {
                "code": "run_mode_missing",
                "message": "run_state is missing run_mode; status inferred phase from run_state.phase",
                "phase": run_state.get("phase"),
            }
        )
    return warnings


def _stale_terminal_reports(
    rounds_dir: Path,
    root: Path,
    run_state: dict[str, Any] | None,
    *,
    active_terminal_report_path: Path | None,
) -> list[dict[str, Any]]:
    stale: list[dict[str, Any]] = []
    for name in TERMINAL_REPORTS:
        path = rounds_dir / name
        if not path.exists() or path == active_terminal_report_path:
            continue
        packet = _read_json_object(path) or {}
        if not _terminal_report_superseded_by_run_state(packet, run_state):
            continue
        stale.append(
            {
                "path": _path_or_none(path, root),
                "report_terminal_state": packet.get("terminal_state"),
                "report_round_number": packet.get("round_number"),
                "current_terminal_state": (run_state or {}).get("terminal_state"),
                "current_round": (run_state or {}).get("current_round"),
            }
        )
    return stale


def _inferred_round_accounting(rounds_dir: Path, run_state: dict[str, Any] | None) -> dict[str, int | None]:
    current_round = (run_state or {}).get("current_round")
    if not isinstance(current_round, int):
        return {
            "current_phase_round": None,
            "phase_1_rounds_completed": None,
            "phase_2_rounds_completed": None,
        }
    phase2_rounds = 0
    for profile_path in sorted(rounds_dir.glob("round-*/profile_used.yaml"), key=_round_profile_sort_key):
        if _profile_name(profile_path) in PHASE_2_PROFILES:
            phase2_rounds += 1
    phase = (run_state or {}).get("phase")
    if phase == "phase_2":
        phase1_rounds = max(0, current_round - phase2_rounds)
        current_phase_round = phase2_rounds
    else:
        phase1_rounds = current_round
        current_phase_round = current_round
    return {
        "current_phase_round": current_phase_round,
        "phase_1_rounds_completed": phase1_rounds,
        "phase_2_rounds_completed": phase2_rounds if phase == "phase_2" else 0,
    }


def _round_profile_sort_key(path: Path) -> int:
    suffix = path.parent.name.removeprefix("round-")
    return int(suffix) if suffix.isdigit() else -1


def _profile_name(path: Path) -> str | None:
    return _round_profile_metadata(path).get("profile")


def _round_profile_metadata(path: Path) -> dict[str, str | None]:
    metadata: dict[str, str | None] = {"profile": None, "round_kind": None}
    if not path.exists():
        return metadata
    text = path.read_text(encoding="utf-8")
    try:
        packet = json.loads(text)
    except json.JSONDecodeError:
        packet = None
    if isinstance(packet, dict):
        profile = packet.get("profile")
        round_kind = packet.get("round_kind")
        metadata["profile"] = str(profile) if profile is not None else None
        metadata["round_kind"] = str(round_kind) if round_kind is not None else None
        return metadata
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('"profile"'):
            _, _, value = stripped.partition(":")
            metadata["profile"] = value.strip().strip('",')
        if stripped.startswith('"round_kind"'):
            _, _, value = stripped.partition(":")
            metadata["round_kind"] = value.strip().strip('",')
        if stripped.startswith("profile:"):
            metadata["profile"] = stripped.removeprefix("profile:").strip().strip('"')
        if stripped.startswith("round_kind:"):
            metadata["round_kind"] = stripped.removeprefix("round_kind:").strip().strip('"')
    return metadata


def _apply_back_status(root: Path, rounds_dir: Path, run_state: dict[str, Any] | None) -> dict[str, Any]:
    final_draft = root / "spec.md"
    review_path = rounds_dir / "apply_back_review.json"
    review = _read_json_object(review_path)
    terminal_state = (run_state or {}).get("terminal_state")
    packet: dict[str, Any] = {
        "available": terminal_state == "CONVERGED" and final_draft.exists(),
        "final_draft_path": _path_or_none(final_draft, root) if final_draft.exists() else None,
        "final_draft_hash": _draft_hash_or_none(final_draft),
        "review_path": _path_or_none(review_path, root) if review_path.exists() else None,
        "applied": review.get("applied") if review else False,
        "source_path": review.get("source_path") if review else None,
        "source_after_hash": review.get("source_after_hash") if review else None,
    }
    packet["source_matches_final_draft"] = (
        None
        if packet["source_after_hash"] is None or packet["final_draft_hash"] is None
        else packet["source_after_hash"] == packet["final_draft_hash"]
    )
    return packet


def _resume_status(root: Path, rounds_dir: Path, run_state: dict[str, Any] | None, config: OrchestratorConfig) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "eligible": False,
        "command": None,
        "continue_command": None,
        "reason": None,
        "round_number": None,
        "profile": None,
        "client_role": None,
        "failure_type": None,
    }
    if not run_state:
        return packet
    from whetstone.preservation_runtime import active
    if active(root, config):
        from whetstone.resume import plan_resume_halted_run
        try:
            command_root = shlex.quote(str(root))
            if run_state.get('phase') == 'phase_2':
                from whetstone.preservation_phase2_closeout import plan as plan_closeout
                eligible, number, _ = plan_closeout(root,config)
                command = f'whetstone live-phase2 --root {command_root} --closeout-existing'
                packet.update(eligible=eligible,reason='bounded Phase 2 Reviewer-only closeout',round_number=number,
                    client_role='reviewer',failure_type='phase2_closeout_required',
                    command=command if eligible else None,continue_command=command if eligible else None)
                return packet
            if run_state.get('terminal_state') in {'TARGET_NOT_REACHED','PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS'}:
                from whetstone.resume import plan_budget_extension_resume
                from whetstone.preservation_budget import grants
                extensions = grants(root,check_mirror=False)
                amount = (extensions[-1]['event']['added_rounds_per_profile'] if extensions and
                          extensions[-1]['event']['previous_current_round'] == run_state.get('current_round') else 3)
                plan = plan_budget_extension_resume(root,config,extend_review_budget=amount)
                command = f'whetstone resume --root {command_root} --extend-review-budget {amount}'
                packet.update(eligible=True,reason=plan.reason,round_number=plan.round_number,client_role='orchestrator',
                    failure_type='budget_exhausted',command=command,continue_command=command)
                return packet
            plan = plan_resume_halted_run(root, config, continue_run=True)
            command = f"whetstone resume --root {shlex.quote(str(root))}"
            packet.update(verified_complete=not plan.resumable and plan.terminal_state in {'PHASE_1_STABLE','FOCUSED_PROFILE_STABLE'},
                          eligible=plan.resumable, reason=plan.reason, round_number=plan.round_number,
                          profile=plan.profile, client_role=plan.client_role, failure_type=plan.failure_type,
                          command=(command + ' --continue' if plan.client_role == 'orchestrator' else command) if plan.resumable else None,
                          continue_command=command + ' --continue' if plan.resumable else None)
        except (ValueError, OSError) as exc:
            packet.update(eligible=False, reason=str(exc))
        return packet
    terminal_state = run_state.get("terminal_state")
    if terminal_state in {"TARGET_NOT_REACHED", "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS"} and run_state.get("phase") == "phase_1":
        supported, validation_error = _budget_extension_resume_supported(config, run_state)
        if not supported:
            packet.update(
                {
                    "eligible": False,
                    "reason": f"budget-extension resume validation failed: {validation_error}",
                    "round_number": run_state.get("current_round"),
                    "profile": run_state.get("active_profile"),
                    "client_role": "orchestrator",
                    "failure_type": "budget_exhausted",
                }
            )
            return packet
        command_root = shlex.quote(str(root))
        packet.update(
            {
                "eligible": True,
                "reason": "supported Phase 1 budget extension",
                "round_number": run_state.get("current_round"),
                "profile": run_state.get("active_profile"),
                "client_role": "orchestrator",
                "failure_type": "budget_exhausted",
                "command": f"whetstone resume --root {command_root} --extend-review-budget 3",
                "continue_command": f"whetstone resume --root {command_root} --extend-review-budget 3",
            }
        )
        return packet
    if terminal_state == "TARGET_NOT_REACHED" and run_state.get("phase") == "phase_2":
        report = _read_json_object(rounds_dir / "convergence_failure_report.json")
        if (
            report is not None
            and not report.get("unresolved_blockers")
            and not report.get("unresolved_major_issues")
            and not report.get("unresolved_rubric_gaps")
        ):
            command_root = shlex.quote(str(root))
            packet.update(
                {
                    "eligible": True,
                    "reason": "supported Phase 2 Reviewer-only closeout",
                    "round_number": run_state.get("current_round"),
                    "profile": run_state.get("active_profile"),
                    "client_role": "reviewer",
                    "failure_type": "phase2_closeout_required",
                    "command": f"whetstone live-phase2 --root {command_root} --closeout-existing",
                    "continue_command": f"whetstone live-phase2 --root {command_root} --closeout-existing",
                }
            )
            return packet
    if terminal_state not in {"HALTED_CLIENT_TIMEOUT", "HALTED_ARTIFACT_INVALID"}:
        return packet
    error = _read_json_object(rounds_dir / "artifact_validation_error.json")
    if error is None:
        packet["reason"] = "missing artifact_validation_error.json"
        return packet
    packet.update(
        {
            "round_number": error.get("round_number"),
            "profile": error.get("profile"),
            "client_role": error.get("client_role"),
            "failure_type": error.get("failure_type"),
        }
    )
    failure_type = error.get("failure_type")
    client_role = error.get("client_role")
    is_client_timeout = terminal_state == "HALTED_CLIENT_TIMEOUT" and failure_type == "client_timeout"
    is_editor_artifact_validation = (
        terminal_state == "HALTED_ARTIFACT_INVALID"
        and failure_type in {"artifact_validation", "client_error"}
        and client_role == "editor"
    )
    if not is_client_timeout and not is_editor_artifact_validation:
        packet["reason"] = "terminal artifact does not describe a supported resumable failure"
        return packet
    if error.get("phase") != "phase_1":
        packet["reason"] = "only Phase 1 halted runs are resumable"
        return packet
    if is_client_timeout and client_role not in {"reviewer", "editor"}:
        packet["reason"] = "only Phase 1 reviewer/editor timeouts are resumable"
        return packet
    command_root = shlex.quote(str(root))
    client_role = str(client_role)
    reason = (
        "supported Phase 1 Editor artifact-validation retry"
        if is_editor_artifact_validation
        else f"supported Phase 1 {client_role.title()} timeout"
    )
    packet.update(
        {
            "eligible": True,
            "reason": reason,
            "command": f"whetstone resume --root {command_root}",
            "continue_command": f"whetstone resume --root {command_root} --continue",
        }
    )
    return packet


def _budget_extension_resume_supported(config: OrchestratorConfig, run_state: dict[str, Any]) -> tuple[bool, str | None]:
    try:
        from whetstone.resume import _validated_budget_extension_context

        _validated_budget_extension_context(
            apply_effective_run_config(config, run_state),
            extend_review_budget=1,
        )
    except Exception as exc:  # pragma: no cover - exact exception type is operator-facing detail.
        return False, str(exc)
    return True, None


def _telemetry_totals(rounds_dir: Path, run_state: dict[str, Any] | None) -> dict[str, Any]:
    computed_totals = run_telemetry_totals(rounds_dir)
    if computed_totals.get("round_count"):
        return computed_totals
    state_totals = (run_state or {}).get("telemetry_totals")
    if isinstance(state_totals, dict):
        return state_totals
    return computed_totals


def _draft_hash_or_none(path: Path) -> str | None:
    if not path.exists():
        return None
    return draft_hash(path.read_text(encoding="utf-8"))


def _pending_client_attempt(round_dir: Path, root: Path) -> dict[str, Any] | None:
    snapshot_dir = round_dir / "prompt_snapshots"
    if not snapshot_dir.exists():
        return None
    attempts: list[dict[str, Any]] = []
    for snapshot in sorted(snapshot_dir.glob("*-attempt-*.json")):
        parsed = _parse_attempt_snapshot_name(snapshot.name)
        if parsed is None:
            continue
        telemetry_path = (
            round_dir
            / "client_telemetry"
            / f"{parsed['client_role']}-{parsed['artifact_name']}-attempt-{parsed['attempt_number']}.json"
        )
        if telemetry_path.exists():
            continue
        attempts.append(
            {
                **parsed,
                "prompt_snapshot_path": _path_or_none(snapshot, root),
                "expected_telemetry_path": _path_or_none(telemetry_path, root),
            }
        )
    if not attempts:
        return None
    return sorted(attempts, key=lambda item: (item["attempt_number"], item["client_role"], item["artifact_name"]))[-1]


def _parse_attempt_snapshot_name(name: str) -> dict[str, Any] | None:
    prefix, separator, suffix = name.partition("-attempt-")
    if separator != "-attempt-" or not suffix.endswith(".json"):
        return None
    attempt_text = suffix.removesuffix(".json")
    if not attempt_text.isdigit():
        return None
    client_role, separator, artifact_name = prefix.partition("-")
    if separator != "-" or client_role == "" or artifact_name == "":
        return None
    return {
        "client_role": client_role,
        "artifact_name": artifact_name,
        "attempt_number": int(attempt_text),
    }


def _next_action(run_state: dict[str, Any] | None, *, terminal_report_path: Path | None) -> str:
    if run_state is None:
        return "run_live_phase1"
    terminal_state = run_state.get("terminal_state")
    if terminal_state == "CONFIG_INVALID":
        return "fix_config"
    if terminal_state == "PAUSED_DECISION":
        return "resolve_decision_intervention"
    if terminal_state == "PHASE_1_STABLE" and run_state.get("ready_for_phase_2") is True:
        return "run_live_phase2"
    if terminal_state == "FOCUSED_PROFILE_STABLE":
        return "review_focused_result"
    if terminal_state == "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS":
        return "manual_review_required"
    if terminal_state == "CONVERGED":
        return "review_or_apply_back"
    if terminal_state == "HALTED_CLIENT_TIMEOUT":
        return "resume_or_increase_timeout"
    if terminal_state in {"TARGET_NOT_REACHED", "HALTED_CONFLICT", "HALTED_OSCILLATION", "HALTED_ARTIFACT_INVALID"}:
        return "manual_review_required"
    if terminal_report_path is not None:
        return "manual_review_required"
    if run_state.get("phase") == "phase_2":
        return "continue_or_resume_phase2"
    return "continue_or_resume_phase1"


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return packet if isinstance(packet, dict) else None


def _path_or_none(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _display(value: Any) -> str:
    if value is None:
        return "none"
    return str(value)


def _scope_display(value: object) -> str:
    if not isinstance(value, dict):
        return "none"
    if not value.get("exists"):
        return "missing"
    if not value.get("valid"):
        return f"invalid ({value.get('error')})"
    return f"{value.get('path')} approved={str(bool(value.get('approved'))).lower()}"


def _artifact_pointer_display(value: object) -> str:
    if not isinstance(value, dict):
        return "none"
    scope = value.get("scope_contract")
    job = value.get("job_descriptor")
    return (
        f"scope_contract={_single_pointer_display(scope)}, "
        f"job_descriptor={_single_pointer_display(job)}"
    )


def _context_pressure_display(value: object) -> str:
    if not isinstance(value, dict):
        return "none"
    return (
        f"path={_display(value.get('path'))}, "
        f"bytes={_display(value.get('byte_count'))}, "
        f"est_tokens={_display(value.get('estimated_tokens'))}, "
        f"warnings={_display(value.get('warning_count'))}, "
        f"action={_display(value.get('action_taken'))}"
    )


def _round_context_pressure_display(value: object) -> str:
    if not isinstance(value, dict):
        return "none"
    latest = value.get("latest") if isinstance(value.get("latest"), dict) else {}
    max_tokens = value.get("max_estimated_tokens") if isinstance(value.get("max_estimated_tokens"), dict) else {}
    return (
        f"reports={_display(value.get('round_report_count'))}, "
        f"latest_round={_display(latest.get('round_number'))}, "
        f"latest_est_tokens={_display(latest.get('estimated_tokens'))}, "
        f"max_round={_display(max_tokens.get('round_number'))}, "
        f"max_est_tokens={_display(max_tokens.get('estimated_tokens'))}, "
        f"referenced_context_mentions={_display(value.get('total_referenced_context_count'))}"
    )


def _single_pointer_display(value: object) -> str:
    if not isinstance(value, dict):
        return "none"
    path = value.get("path")
    if not path:
        return "missing"
    suffix = "" if value.get("exists") else " (missing)"
    return f"{path}{suffix}"
