"""Read-only run status summaries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
from typing import Any

from whetstone.config import OrchestratorConfig
from whetstone.hashing import draft_hash
from whetstone.live import run_telemetry_totals
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
PHASE_2_PROFILES = {"convergence_strict_check", "adversarial"}


def read_status(*, root: Path, config: OrchestratorConfig) -> dict[str, Any]:
    """Return a stable read-only snapshot of the current Whetstone run."""
    rounds_dir = config.rounds_dir
    state_path = rounds_dir / "run_state.json"
    run_state = _read_json_object(state_path)
    latest_round = _latest_round(rounds_dir, root)
    inferred_rounds = _inferred_round_accounting(rounds_dir, run_state)
    decision_summary = _decision_summary(rounds_dir, root)
    terminal_report_path = _terminal_report_path(rounds_dir, run_state)
    terminal_report = _read_json_object(terminal_report_path) if terminal_report_path else None
    current_draft_status = _current_draft_status(run_state, terminal_report)
    telemetry_totals = _telemetry_totals(rounds_dir, run_state)
    apply_back = _apply_back_status(root, rounds_dir, run_state)
    resume_status = _resume_status(root, rounds_dir, run_state)
    scope_status = _scope_status(root, config)
    default_review_round_budget = default_phase_1_scheduler(config.review_profile_budgets).total_round_budget()
    default_convergence_round_budget = default_phase_2_scheduler(config.convergence_profile_budgets).total_round_budget()
    default_review_profile_budgets = resolved_phase_1_profile_budgets(config.review_profile_budgets)
    default_convergence_profile_budgets = resolved_phase_2_profile_budgets(config.convergence_profile_budgets)
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
        "review_max_rounds": (run_state.get("review_max_rounds") if run_state else None) or config.review_max_rounds,
        "review_round_budget": (run_state.get("review_round_budget") if run_state else None)
        or default_review_round_budget,
        "review_profile_budgets": (run_state.get("review_profile_budgets") if run_state else None)
        or default_review_profile_budgets,
        "convergence_max_rounds": (run_state.get("convergence_max_rounds") if run_state else None)
        or config.convergence.max_rounds,
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
        "last_accepted_draft_hash": run_state.get("last_accepted_draft_hash") if run_state else None,
        "resumable": bool(run_state.get("resumable")) or bool(resume_status.get("eligible")) if run_state else False,
        "resume": resume_status,
        "scope_contract": scope_status,
        "latest_round": latest_round,
        "terminal_report_path": _path_or_none(terminal_report_path, root) if terminal_report_path else None,
        "decision_register": _decision_register(rounds_dir, root),
        "decision_summary": decision_summary,
        "apply_back": apply_back,
        "telemetry_totals": telemetry_totals,
        "next_action": _next_action(run_state, terminal_report_path=terminal_report_path),
    }
    return packet


def render_status_text(status: dict[str, Any]) -> str:
    """Render a compact human-readable status summary."""
    latest_round = status.get("latest_round") or {}
    decision_register = status.get("decision_register") or {}
    decision_summary = status.get("decision_summary") or {}
    telemetry = status.get("telemetry_totals") or {}
    apply_back = status.get("apply_back") or {}
    resume_status = status.get("resume") or {}
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
        f"resumable: {str(bool(status.get('resumable'))).lower()}",
        f"scope_contract: {_scope_display(status.get('scope_contract'))}",
        f"last_accepted_draft_hash: {_display(status.get('last_accepted_draft_hash'))}",
        f"latest_round: {latest_round_text}",
        f"next_action: {_display(status.get('next_action'))}",
        f"terminal_report: {_display(status.get('terminal_report_path'))}",
        (
            "decisions: "
            f"{_display(decision_summary.get('decision_count', decision_register.get('decision_count')))}, "
            f"human: {_display(decision_summary.get('unresolved_human_decision_count', decision_register.get('unresolved_human_decision_count')))}, "
            f"statuses: {_display(decision_summary.get('decision_status_counts', decision_register.get('decision_status_counts')))}"
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


def _terminal_report_path(rounds_dir: Path, run_state: dict[str, Any] | None = None) -> Path | None:
    terminal_state = (run_state or {}).get("terminal_state")
    if terminal_state in {"CONVERGED", "PHASE_1_STABLE", "FOCUSED_PROFILE_STABLE"}:
        return None
    for name in TERMINAL_REPORTS:
        path = rounds_dir / name
        if path.exists():
            return path
    return None


def _current_draft_status(run_state: dict[str, Any] | None, terminal_report: dict[str, Any] | None) -> str | None:
    if run_state and run_state.get("terminal_state") == "PHASE_1_STABLE" and run_state.get("ready_for_phase_2") is True:
        return "phase_1_stable"
    if run_state and run_state.get("terminal_state") == "CONVERGED":
        return "converged"
    return terminal_report.get("current_draft_status") if terminal_report else None


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


def _resume_status(root: Path, rounds_dir: Path, run_state: dict[str, Any] | None) -> dict[str, Any]:
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
    terminal_state = run_state.get("terminal_state")
    if terminal_state in {"TARGET_NOT_REACHED", "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS"} and run_state.get("phase") == "phase_1":
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
    if terminal_state != "HALTED_CLIENT_TIMEOUT":
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
    if error.get("failure_type") != "client_timeout":
        packet["reason"] = "terminal timeout artifact is not failure_type=client_timeout"
        return packet
    if error.get("phase") != "phase_1" or error.get("client_role") != "editor":
        packet["reason"] = "only Phase 1 editor timeouts are resumable"
        return packet
    command_root = shlex.quote(str(root))
    packet.update(
        {
            "eligible": True,
            "reason": "supported Phase 1 Editor timeout",
            "command": f"whetstone resume --root {command_root}",
            "continue_command": f"whetstone resume --root {command_root} --continue",
        }
    )
    return packet


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
