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
            "attempts": [
                {
                    "attempt_number": 1,
                    "artifact_name": "reviewer_feedback.json",
                    "validation_errors": ["$.feedback[0].oscillation_key.section_id: unknown section"],
                    "raw_response_path": "rounds/round-1/reviewer_raw_response.json",
                }
            ],
            "retry_exhausted": True,
            "last_valid_draft_hash": HASH,
            "last_valid_draft_path": "rounds/round-1/draft_before.md",
            "recommendation": "switch_client",
        }

        validate_artifact(artifact, "artifact_validation_error")

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
