"""Terminal report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whetstone.artifacts import ArtifactStore
from whetstone.hashing import draft_hash


class ReportWriter:
    """Write schema-validated terminal reports under rounds/."""

    def __init__(self, root: Path | str) -> None:
        self.store = ArtifactStore(root)

    def write_oscillation_report(
        self,
        *,
        round_number: int,
        detected: bool,
        oscillation_type: str | None,
        affected_sections: list[str],
        suspected_feedback_ids: list[str],
        recommendation: str,
        oscillation_fingerprints: list[str] | None = None,
        oscillation_opposition_keys: list[str] | None = None,
    ) -> Path:
        packet = {
            "terminal_state": "HALTED_OSCILLATION" if recommendation == "stop_iteration" else None,
            "generated_at": _now(),
            "round_number": round_number,
            "draft_hash": draft_hash(self.store.read_spec()),
            "detected": detected,
            "type": oscillation_type,
            "affected_sections": affected_sections,
            "suspected_feedback_ids": suspected_feedback_ids,
            "oscillation_fingerprints": oscillation_fingerprints or [],
            "oscillation_opposition_keys": oscillation_opposition_keys or [],
            "recommendation": recommendation,
        }
        return self._write_terminal_json("oscillation_report.json", packet, "oscillation_report")

    def write_conflict_report(
        self,
        *,
        round_number: int,
        conflicts: list[dict[str, Any]],
        exit_reason: str,
        recommendation: str = "manual_review_required",
        terminal_state: str | None = "HALTED_CONFLICT",
    ) -> Path:
        packet = {
            "terminal_state": terminal_state,
            "generated_at": _now(),
            "round_number": round_number,
            "draft_hash": draft_hash(self.store.read_spec()),
            "conflicts": conflicts,
            "exit_reason": exit_reason,
            "recommendation": recommendation,
        }
        return self._write_terminal_json("conflict_report.json", packet, "conflict_report")

    def write_technical_failure_report(
        self,
        *,
        round_number: int,
        final_draft_path: str,
        unresolved_blockers: list[dict[str, Any]],
        unresolved_major_issues: list[dict[str, Any]],
        unresolved_conflicts: list[dict[str, Any]],
        unresolved_oscillation: dict[str, Any] | None,
        last_accepted_draft_hash: str | None,
        exit_reason: str,
        recommendation: str,
        profile_status: dict[str, Any] | None = None,
        last_reviewer_findings: dict[str, Any] | None = None,
        terminal_state: str = "TARGET_NOT_REACHED",
    ) -> Path:
        current_hash = draft_hash(self.store.read_spec())
        effective_profile_status = profile_status or {
            "profiles": [],
            "unverified_profiles": [],
            "exhausted_profiles": [],
            "profiles_remaining": [],
            "total_round_budget": 0,
        }
        current_draft_status = _current_draft_status(
            current_hash=current_hash,
            last_accepted_draft_hash=last_accepted_draft_hash,
            profile_status=effective_profile_status,
        )
        packet = {
            "terminal_state": terminal_state,
            "generated_at": _now(),
            "round_number": round_number,
            "draft_hash": current_hash,
            "final_draft_path": final_draft_path,
            "unresolved_blockers": unresolved_blockers,
            "unresolved_major_issues": unresolved_major_issues,
            "unresolved_conflicts": unresolved_conflicts,
            "unresolved_oscillation": unresolved_oscillation,
            "last_accepted_draft_hash": last_accepted_draft_hash,
            "current_draft_status": current_draft_status,
            "ready_for_phase_2": current_draft_status == "phase_1_stable",
            "last_draft_hash": current_hash,
            "exit_reason": exit_reason,
            "recommendation": recommendation,
            "profile_status": effective_profile_status,
            "last_reviewer_findings": last_reviewer_findings,
        }
        return self._write_terminal_json("technical_failure_report.json", packet, "technical_failure_report")

    def write_convergence_failure_report(
        self,
        *,
        round_number: int,
        final_draft_path: str,
        final_declaration_path: str | None,
        target_phase: str,
        target_mode: str,
        workflow: str = "standard",
        rubric_profile: str = "standard-v1",
        rubric_source: str = "builtin",
        rubric_label: str | None = None,
        rubric_manifest_path: str = "rounds/rubric_manifest.json",
        unresolved_blockers: list[dict[str, Any]],
        unresolved_major_issues: list[dict[str, Any]],
        unresolved_rubric_gaps: list[dict[str, Any]],
        reviewer_final_status: str,
        last_accepted_draft_hash: str | None,
        exit_reason: str,
        recommendation: str,
        profile_status: dict[str, Any] | None = None,
        last_reviewer_findings: dict[str, Any] | None = None,
        terminal_state: str = "TARGET_NOT_REACHED",
    ) -> Path:
        current_hash = draft_hash(self.store.read_spec())
        packet = {
            "terminal_state": terminal_state,
            "generated_at": _now(),
            "round_number": round_number,
            "draft_hash": current_hash,
            "final_draft_path": final_draft_path,
            "final_declaration_path": final_declaration_path,
            "target_phase": target_phase,
            "target_mode": target_mode,
            "workflow": workflow,
            "rubric_profile": rubric_profile,
            "rubric_source": rubric_source,
            "rubric_label": rubric_label,
            "rubric_manifest_path": rubric_manifest_path,
            "unresolved_blockers": unresolved_blockers,
            "unresolved_major_issues": unresolved_major_issues,
            "unresolved_rubric_gaps": unresolved_rubric_gaps,
            "reviewer_final_status": reviewer_final_status,
            "last_accepted_draft_hash": last_accepted_draft_hash,
            "last_draft_hash": current_hash,
            "exit_reason": exit_reason,
            "recommendation": recommendation,
            "profile_status": profile_status or {
                "profiles": [],
                "unverified_profiles": [],
                "exhausted_profiles": [],
                "profiles_remaining": [],
                "total_round_budget": 0,
            },
            "last_reviewer_findings": last_reviewer_findings,
        }
        return self._write_terminal_json("convergence_failure_report.json", packet, "convergence_failure_report")

    def _write_terminal_json(self, filename: str, packet: dict[str, Any], schema_name: str) -> Path:
        self.store.paths.rounds_dir.mkdir(parents=True, exist_ok=True)
        output = self.store.paths.rounds_dir / filename
        from json import dumps

        from whetstone.contracts import validate_artifact

        validate_artifact(packet, schema_name)
        output.write_text(dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return output


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_draft_status(
    *,
    current_hash: str,
    last_accepted_draft_hash: str | None,
    profile_status: dict[str, Any],
) -> str:
    if last_accepted_draft_hash != current_hash:
        return "not_accepted"
    has_profile_debt = any(
        profile_status.get(key)
        for key in ("unverified_profiles", "exhausted_profiles", "profiles_remaining")
    )
    return "accepted_unverified_profiles" if has_profile_debt else "phase_1_stable"
