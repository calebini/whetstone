from __future__ import annotations

import unittest

from whetstone.contracts import SchemaValidationError, validate_artifact
from whetstone.identity import oscillation_fingerprint, oscillation_opposition_key


HASH = "a" * 64
ISSUE_ID = "iss_aaaaaaaaaaaaaaaa"
CONFLICT_ID = "con_bbbbbbbbbbbbbbbb"


class ContractValidationTests(unittest.TestCase):
    def test_reviewer_feedback_validates(self) -> None:
        artifact = {
            "round_number": 1,
            "profile": "determinism",
            "reviewer": {"name": "codex", "version": "1.0.0", "model": "fixture"},
            "draft_hash": HASH,
            "feedback": [
                {
                    "feedback_id": "fb-1",
                    "issue_id": ISSUE_ID,
                    "issue_fingerprint": HASH,
                    "issue_type": "undefined_behavior",
                    "affected_sections": ["Hashing"],
                    "baseline_severity": "major",
                    "authority_impact": None,
                    "determinism_impact": "major",
                    "rubric_impact": None,
                    "normalized_severity": "major",
                    "invariant_violated": "replay/hash determinism violations",
                    "claim": "Hash normalization is underspecified.",
                    "evidence": "The draft does not define line endings.",
                    "recommended_change": "Define line ending normalization.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            ],
        }

        validate_artifact(artifact, "reviewer_feedback")

    def test_phase_2_reviewer_feedback_requires_oscillation_key(self) -> None:
        artifact = {
            "round_number": 4,
            "profile": "convergence_strict_check",
            "reviewer": {"name": "codex", "version": "1.0.0", "model": "fixture"},
            "draft_hash": HASH,
            "feedback": [
                {
                    "feedback_id": "fb-1",
                    "issue_id": ISSUE_ID,
                    "issue_fingerprint": HASH,
                    "issue_type": "undefined_behavior",
                    "affected_sections": ["Hashing"],
                    "baseline_severity": "minor",
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": "minor",
                    "invariant_violated": None,
                    "claim": "Hashing needs one more exact rule.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Clarify the rule.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            ],
        }

        with self.assertRaises(SchemaValidationError):
            validate_artifact(artifact, "phase2_reviewer_feedback")

        artifact["feedback"][0]["oscillation_key"] = {
            "section_id": "Hashing",
            "concern_type": "precision_gap",
            "direction": "clarify",
            "scope": "local",
            "fingerprint": oscillation_fingerprint("Hashing", "precision_gap", "clarify", "local"),
            "opposition_key": oscillation_opposition_key("Hashing", "precision_gap", "local"),
        }

        validate_artifact(artifact, "phase2_reviewer_feedback")

        artifact["feedback"][0]["oscillation_key"] = {
            "section_id": "Hashing",
            "concern_type": "precision_gap",
            "direction": "clarify",
            "scope": "local",
        }

        validate_artifact(artifact, "phase2_reviewer_feedback_input")

    def test_reviewer_feedback_requires_rationale_when_baseline_is_null(self) -> None:
        artifact = {
            "round_number": 1,
            "profile": "determinism",
            "reviewer": {"name": "codex", "version": "1.0.0", "model": "fixture"},
            "draft_hash": HASH,
            "feedback": [
                {
                    "feedback_id": "fb-1",
                    "issue_id": ISSUE_ID,
                    "issue_fingerprint": HASH,
                    "issue_type": "undefined_behavior",
                    "affected_sections": ["Hashing"],
                    "baseline_severity": None,
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": "nit",
                    "invariant_violated": None,
                    "claim": "Small note.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Fixture recommendation.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            ],
        }

        with self.assertRaises(SchemaValidationError):
            validate_artifact(artifact, "reviewer_feedback")

    def test_editor_summary_validates_deferred_decline_requirements(self) -> None:
        artifact = {
            "round_number": 1,
            "draft_before_hash": HASH,
            "draft_after_hash": HASH,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": ["fb-1"],
            "declined_feedback": [
                {
                    "feedback_id": "fb-2",
                    "decline_reason": "deferred_to_later_round",
                    "rationale": "Needs the adversarial profile.",
                    "target_profile": "adversarial",
                    "target_round_or_phase": "phase_2",
                }
            ],
            "created_conflict_ids": [CONFLICT_ID],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [ISSUE_ID],
        }

        validate_artifact(artifact, "editor_summary")

    def test_unresolved_issues_validates(self) -> None:
        artifact = {
            "round_number": 1,
            "draft_hash": HASH,
            "unresolved_issues": [
                {
                    "issue_id": ISSUE_ID,
                    "issue_fingerprint": HASH,
                    "normalized_severity": "blocker",
                    "affected_sections": ["State Machine"],
                    "claim": "Illegal transition is possible.",
                    "in_scope": True,
                    "blocking_acceptance": True,
                }
            ],
        }

        validate_artifact(artifact, "unresolved_issues")

    def test_rubric_gaps_validates(self) -> None:
        artifact = {
            "round_number": 2,
            "draft_hash": HASH,
            "rubric_content_hash": HASH,
            "rubric_gaps": [
                {
                    "gap_id": "gap_cccccccccccccccc",
                    "gap_fingerprint": "c" * 64,
                    "rubric_anchor": "final/strict",
                    "affected_sections": ["Target Matrix"],
                    "normalized_severity": "major",
                    "claim": "A rubric requirement is not satisfied.",
                    "evidence": "Fixture evidence.",
                    "recommendation": "Resolve the gap.",
                    "status": "unresolved",
                    "blocking_convergence": True,
                }
            ],
        }

        validate_artifact(artifact, "rubric_gaps")

    def test_rubric_manifest_validates(self) -> None:
        artifact = {
            "generated_at": "2026-05-01T00:00:00+00:00",
            "workflow": "governance",
            "rubric_profile": "governance-v6",
            "rubric_source": "builtin",
            "rubric_label": None,
            "rubric_path": "/tmp/whetstone/rubrics/governance-v6.md",
            "rubric_content_hash": HASH,
            "target_phase": "final",
            "target_mode": "strict",
            "resolved_defaults": {
                "target_phase": "final",
                "target_mode": "strict",
                "convergence_max_rounds": 8,
                "required_artifacts": ["spec.md", "convergence_declaration.md"],
            },
            "configured_budgets": {
                "review_max_rounds": 12,
                "convergence_max_rounds": 8,
                "total_absolute_round_budget": 20,
            },
            "warnings": [],
        }

        validate_artifact(artifact, "rubric_manifest")

    def test_config_validation_error_validates(self) -> None:
        artifact = {
            "terminal_state": "CONFIG_INVALID",
            "generated_at": "2026-05-01T00:00:00+00:00",
            "invalid_fields": [
                {"path": "clients.reviewer.model", "reason": "must be a non-empty string"}
            ],
        }

        validate_artifact(artifact, "config_validation_error")

    def test_artifact_validation_error_validates(self) -> None:
        artifact = {
            "terminal_state": "HALTED_ARTIFACT_INVALID",
            "generated_at": "2026-05-01T00:00:00+00:00",
            "round_number": 1,
            "phase": "phase_2",
            "profile": "convergence_strict_check",
            "client_role": "reviewer",
            "client": {"name": "claude-code", "version": "1.0.47", "model": "claude-sonnet-4-6"},
            "failure_type": "artifact_validation",
            "attempts": [
                {
                    "attempt_number": 1,
                    "artifact_name": "reviewer_feedback.json",
                    "validation_errors": ["$.feedback[0].oscillation_key.section_id: unknown section"],
                    "raw_response_path": "rounds/round-1/reviewer_raw_response.json",
                    "telemetry_path": "rounds/round-1/client_telemetry/reviewer-reviewer_feedback.json-attempt-1.json",
                }
            ],
            "retry_exhausted": True,
            "last_valid_draft_hash": HASH,
            "last_valid_draft_path": "rounds/round-1/draft_before.md",
            "recommendation": "switch_client",
        }

        validate_artifact(artifact, "artifact_validation_error")

    def test_client_telemetry_validates(self) -> None:
        artifact = {
            "generated_at": "2026-05-01T00:00:00+00:00",
            "round_number": 1,
            "phase": "phase_2",
            "profile": "convergence_strict_check",
            "client_role": "reviewer",
            "artifact_name": "reviewer_feedback.json",
            "attempt_number": 1,
            "client": {
                "name": "claude-code",
                "command": "claude",
                "configured_version": "1.0.47",
                "observed_version": None,
                "model": "claude-sonnet-4-6",
            },
            "started_at": "2026-05-01T00:00:00+00:00",
            "finished_at": "2026-05-01T00:00:01+00:00",
            "duration_ms": 1000,
            "duration_api_ms": 900,
            "exit_code": 0,
            "timed_out": False,
            "session_id": "session-1",
            "num_turns": 2,
            "stop_reason": "end_turn",
            "terminal_reason": "success",
            "total_cost_usd": 0.12,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "cache_creation_input_tokens": 30,
                "cache_read_input_tokens": 40,
                "total_tokens": 100,
                "provider_raw": {"input_tokens": 10},
            },
            "model_usage": {"claude-sonnet": {"inputTokens": 10}},
            "raw_envelope_path": "rounds/round-1/client_telemetry/raw.json",
            "stdout_path": "rounds/round-1/client_telemetry/stdout.txt",
            "stderr_path": None,
            "telemetry_source": "claude_json_envelope",
        }

        validate_artifact(artifact, "client_telemetry")

    def test_apply_back_report_validates(self) -> None:
        artifact = {
            "generated_at": "2026-05-01T00:00:00+00:00",
            "mode": "dry_run",
            "applied": False,
            "approval_mode": "none",
            "source_path": "/tmp/source.md",
            "run_root": "/tmp/run",
            "final_draft_path": "/tmp/run/spec.md",
            "run_state_path": "/tmp/run/rounds/run_state.json",
            "terminal_state": "CONVERGED",
            "eligible_terminal_state": True,
            "allow_non_converged": False,
            "source_before_hash": HASH,
            "expected_source_hash": None,
            "source_hash_mismatch_allowed": False,
            "final_draft_hash": HASH,
            "run_state_current_draft_hash": HASH,
            "final_draft_matches_run_state": True,
            "source_after_hash": HASH,
            "changed": False,
            "declaration_path": "/tmp/run/convergence_declaration.md",
            "declaration_included": False,
            "decision_summary_path": "/tmp/run/rounds/decision_summary.json",
            "decision_summary_included": True,
            "rubric_manifest_path": None,
            "workflow": None,
            "rubric_profile": None,
            "rubric_source": None,
            "rubric_label": None,
            "rubric_content_hash": None,
            "diff_line_count": 0,
        }

        validate_artifact(artifact, "apply_back_report")

    def test_decision_artifacts_validate(self) -> None:
        point = {
            "decision_id": "dec_aaaaaaaaaaaaaaaa",
            "round_number": 1,
            "profile": "determinism",
            "source_feedback_ids": ["fb-1"],
            "affected_sections": ["Adapter Receipt"],
            "decision_type": "add_operational_requirement",
            "trigger_types": ["add_operational_requirement"],
            "evidence_lines": ["- `HAG_ADAPTER_DELIVERY_FAILED`"],
            "question": "Should `Adapter Receipt` add this operational requirement?",
            "options_considered": [
                {
                    "option_id": "selected",
                    "label": "Keep editor change",
                    "description": "Keep the revised draft behavior.",
                }
            ],
            "editor_selected_option_id": "selected",
            "editor_rationale": "Detected from diff.",
            "risk_if_wrong": "The spec may encode an unintended operational requirement.",
            "requires_human_decision": True,
            "orchestrator_action": "present_at_end",
        }

        validate_artifact({"round_number": 1, "draft_hash": HASH, "decision_points": [point]}, "decision_points")
        validate_artifact(
            {
                "generated_at": "2026-05-01T00:00:00+00:00",
                "mode": "end_of_cycle",
                "terminal_state": "PHASE_1_STABLE",
                "decision_points": [point],
                "unresolved_human_decision_count": 1,
            },
            "decision_register",
        )
        validate_artifact(
            {
                "generated_at": "2026-05-01T00:00:00+00:00",
                "source_register_path": "rounds/decision_register.json",
                "mode": "end_of_cycle",
                "terminal_state": "PHASE_1_STABLE",
                "decision_count": 1,
                "unresolved_human_decision_count": 1,
                "summary_method": "mechanical_v1",
                "hotspots": {
                    "largest_clusters": [
                        {
                            "cluster_group": "by_section",
                            "cluster_key": "Adapter Receipt",
                            "cluster_label": "Adapter Receipt",
                            "decision_count": 1,
                            "requires_human_decision_count": 1,
                        }
                    ],
                    "human_decision_clusters": [
                        {
                            "cluster_group": "by_section",
                            "cluster_key": "Adapter Receipt",
                            "cluster_label": "Adapter Receipt",
                            "decision_count": 1,
                            "requires_human_decision_count": 1,
                        }
                    ],
                },
                "clusters": {
                    "by_section": [
                        {
                            "cluster_key": "Adapter Receipt",
                            "cluster_label": "Adapter Receipt",
                            "decision_count": 1,
                            "requires_human_decision_count": 1,
                            "orchestrator_actions": ["present_at_end"],
                            "decision_types": ["add_operational_requirement"],
                            "trigger_types": ["add_operational_requirement"],
                            "round_numbers": [1],
                            "profiles": ["determinism"],
                            "affected_sections": ["Adapter Receipt"],
                            "decision_ids": ["dec_aaaaaaaaaaaaaaaa"],
                            "representative_decisions": [
                                {
                                    "decision_id": "dec_aaaaaaaaaaaaaaaa",
                                    "question": "Should `Adapter Receipt` add this operational requirement?",
                                    "risk_if_wrong": "The spec may encode an unintended operational requirement.",
                                }
                            ],
                        }
                    ],
                    "by_round_profile": [],
                    "by_trigger_type": [],
                },
            },
            "decision_summary",
        )
        point = dict(point)
        point["orchestrator_action"] = "pause_for_input"
        validate_artifact(
            {
                "terminal_state": "PAUSED_DECISION",
                "generated_at": "2026-05-01T00:00:00+00:00",
                "round_number": 1,
                "profile": "determinism",
                "draft_hash": HASH,
                "decision_points": [point],
                "recommendation": "choose_option",
            },
            "decision_intervention_request",
        )


if __name__ == "__main__":
    unittest.main()
