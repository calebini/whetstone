from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import DecisionPointConfig
from whetstone.decisions import detect_decision_points, write_decision_register


class DecisionPointTests(unittest.TestCase):
    def test_hag_style_diff_captures_policy_and_operability_decisions(self) -> None:
        before = """# HAG

## Display Context

- Nested display fields MAY reuse generic names.

## Duplicate Submissions

The Arbiter owns the resolution strategy.

## Adapter Error Codes

- `HAG_ADAPTER_DELIVERY_FAILED`
"""
        after = """# HAG

## Display Context

- Nested fields within `display_context` MUST NOT use keys that match authority-bearing field names at any depth.

## Duplicate Submissions

The Arbiter owns the resolution strategy. For Foreman MVP, the Arbiter MUST apply first-write-wins per (`approval_request_id`, `approver_id`).

## Adapter Error Codes

- `HAG_ADAPTER_DELIVERY_FAILED`
- `HAG_ADAPTER_REQUEST_RETRIEVAL_FAILED`
"""

        packet = detect_decision_points(
            draft_before=before,
            draft_after=after,
            round_number=1,
            profile="determinism",
            reviewer_feedback=_feedback("major"),
            editor_summary={
                "accepted_feedback_ids": ["fb-1"],
                "modified_feedback_ids": [],
            },
            config=DecisionPointConfig(
                enabled=True,
                mode="end_of_cycle",
                severities=("blocker", "major"),
                trigger_on_requirement_strength_change=True,
                trigger_on_authority_boundary_change=True,
                trigger_on_scope_change=True,
                trigger_on_new_enum_or_error_code=True,
            ),
        )

        decision_types = {point["decision_type"] for point in packet["decision_points"]}
        trigger_types = {trigger for point in packet["decision_points"] for trigger in point["trigger_types"]}
        questions = "\n".join(point["question"] for point in packet["decision_points"])
        self.assertIn("tighten_requirement", trigger_types)
        self.assertIn("scope_change", trigger_types)
        self.assertIn("choose_policy", decision_types)
        self.assertIn("add_operational_requirement", trigger_types)
        self.assertIn("first-write-wins", questions)
        self.assertTrue(any(point["orchestrator_action"] == "present_at_end" for point in packet["decision_points"]))
        self.assertEqual(len(packet["decision_points"]), 3)

    def test_intervention_mode_marks_points_for_pause(self) -> None:
        before = "# Spec\n\n## Rules\n\n- Adapter MAY retry.\n"
        after = "# Spec\n\n## Rules\n\n- Adapter MUST retry.\n"
        packet = detect_decision_points(
            draft_before=before,
            draft_after=after,
            round_number=1,
            profile="operability",
            reviewer_feedback=_feedback("major"),
            editor_summary={
                "accepted_feedback_ids": ["fb-1"],
                "modified_feedback_ids": [],
            },
            config=DecisionPointConfig(
                enabled=True,
                mode="intervention",
                severities=("blocker", "major"),
                trigger_on_requirement_strength_change=True,
                trigger_on_authority_boundary_change=True,
                trigger_on_scope_change=True,
                trigger_on_new_enum_or_error_code=True,
            ),
        )

        self.assertTrue(packet["decision_points"])
        self.assertTrue(all(point["orchestrator_action"] == "pause_for_input" for point in packet["decision_points"]))

    def test_write_decision_register_aggregates_round_packets(self) -> None:
        with TemporaryDirectory() as tmp:
            rounds_dir = Path(tmp) / "rounds"
            round_dir = rounds_dir / "round-1"
            round_dir.mkdir(parents=True)
            point = detect_decision_points(
                draft_before="# Spec\n\n## Rules\n\n- Adapter MAY retry.\n",
                draft_after="# Spec\n\n## Rules\n\n- Adapter MUST retry.\n",
                round_number=1,
                profile="operability",
                reviewer_feedback=_feedback("major"),
                editor_summary={"accepted_feedback_ids": ["fb-1"], "modified_feedback_ids": []},
                config=DecisionPointConfig(True, "end_of_cycle", ("major",), True, True, True, True),
            )
            (round_dir / "decision_points.json").write_text(__import__("json").dumps(point), encoding="utf-8")

            path = write_decision_register(rounds_dir=rounds_dir, mode="end_of_cycle", terminal_state="PHASE_1_STABLE")

            self.assertIsNotNone(path)
            self.assertTrue((rounds_dir / "decision_register.md").exists())


def _feedback(severity: str) -> dict:
    return {
        "feedback": [
            {
                "feedback_id": "fb-1",
                "normalized_severity": severity,
            }
        ]
    }


if __name__ == "__main__":
    unittest.main()
