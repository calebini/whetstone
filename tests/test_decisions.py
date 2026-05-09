from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import DecisionPointConfig
from whetstone.decisions import detect_decision_points, summarize_decision_register, write_decision_register, write_decision_summary_outputs


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
        self.assertTrue(all(point["decision_status"] == "operator_required_decision" for point in packet["decision_points"]))

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
            (round_dir / "decision_points.json").write_text(json.dumps(point), encoding="utf-8")

            path = write_decision_register(rounds_dir=rounds_dir, mode="end_of_cycle", terminal_state="PHASE_1_STABLE")

            self.assertIsNotNone(path)
            self.assertTrue((rounds_dir / "decision_register.md").exists())
            self.assertTrue((rounds_dir / "decision_summary.json").exists())
            self.assertTrue((rounds_dir / "decision_summary.md").exists())
            register = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(register["decision_status_counts"], {"operator_review_recommended": 1})

    def test_decision_summary_clusters_mechanically(self) -> None:
        register = {
            "generated_at": "2026-05-01T00:00:00+00:00",
            "mode": "end_of_cycle",
            "terminal_state": "PHASE_1_STABLE",
            "unresolved_human_decision_count": 2,
            "decision_points": [
                _decision_point(
                    decision_id="dec_aaaaaaaaaaaaaaaa",
                    round_number=1,
                    profile="operability",
                    section="Rules",
                    trigger_types=["tighten_requirement", "scope_change"],
                ),
                _decision_point(
                    decision_id="dec_bbbbbbbbbbbbbbbb",
                    round_number=2,
                    profile="determinism",
                    section="Rules",
                    trigger_types=["choose_policy"],
                ),
                _decision_point(
                    decision_id="dec_cccccccccccccccc",
                    round_number=2,
                    profile="determinism",
                    section="Errors",
                    trigger_types=["add_operational_requirement"],
                    requires_human_decision=False,
                    orchestrator_action="record_only",
                ),
            ],
        }

        summary = summarize_decision_register(register, source_register_path="rounds/decision_register.json")

        self.assertEqual(summary["summary_method"], "mechanical_v1")
        self.assertEqual(summary["decision_count"], 3)
        self.assertEqual(
            summary["decision_status_counts"],
            {"operator_review_recommended": 2, "record_only_hardening": 1},
        )
        self.assertEqual(summary["hotspots"]["largest_clusters"][0]["cluster_key"], "Rules")
        self.assertEqual(summary["hotspots"]["largest_clusters"][0]["decision_count"], 2)
        self.assertEqual(summary["hotspots"]["human_decision_clusters"][0]["requires_human_decision_count"], 2)
        by_section = summary["clusters"]["by_section"]
        self.assertEqual([cluster["cluster_key"] for cluster in by_section], ["Errors", "Rules"])
        self.assertEqual(by_section[0]["decision_status_counts"], {"record_only_hardening": 1})
        self.assertEqual(by_section[1]["decision_ids"], ["dec_aaaaaaaaaaaaaaaa", "dec_bbbbbbbbbbbbbbbb"])
        by_round_profile = summary["clusters"]["by_round_profile"]
        self.assertEqual([cluster["cluster_key"] for cluster in by_round_profile], ["round-1|operability", "round-2|determinism"])
        self.assertEqual(by_round_profile[1]["decision_count"], 2)
        by_trigger = summary["clusters"]["by_trigger_type"]
        self.assertEqual(
            [cluster["cluster_key"] for cluster in by_trigger],
            ["add_operational_requirement", "choose_policy", "scope_change", "tighten_requirement"],
        )

    def test_write_decision_summary_outputs(self) -> None:
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            register_path = output_dir / "decision_register.json"
            register_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-05-01T00:00:00+00:00",
                        "mode": "end_of_cycle",
                        "terminal_state": "PHASE_1_STABLE",
                        "unresolved_human_decision_count": 1,
                        "decision_points": [_decision_point()],
                    }
                ),
                encoding="utf-8",
            )

            outputs = write_decision_summary_outputs(register_path=register_path)

            self.assertTrue(outputs["decision_summary"].exists())
            self.assertTrue(outputs["decision_summary_markdown"].exists())
            summary = json.loads(outputs["decision_summary"].read_text(encoding="utf-8"))
            self.assertEqual(summary["clusters"]["by_section"][0]["cluster_key"], "Rules")
            self.assertEqual(summary["decision_status_counts"], {"operator_review_recommended": 1})

    def test_deferred_scope_must_change_is_flagged_as_deferred_scope_decision(self) -> None:
        scope_contract = {
            "scope_surfaces": [
                {
                    "name": "diagnostic mode",
                    "status": "deferred",
                }
            ],
            "core_flows": [],
        }
        packet = detect_decision_points(
            draft_before="# Spec\n\n## Diagnostics\n\nDiagnostic mode is deferred.\n",
            draft_after="# Spec\n\n## Diagnostics\n\nDiagnostic mode MUST emit a full report.\n",
            round_number=1,
            profile="operability",
            reviewer_feedback=_feedback("minor"),
            editor_summary={"accepted_feedback_ids": ["fb-1"], "modified_feedback_ids": []},
            config=DecisionPointConfig(True, "end_of_cycle", ("major",), True, True, True, True),
            scope_contract=scope_contract,
        )

        self.assertEqual(packet["decision_points"][0]["decision_status"], "deferred_scope_decision")
        self.assertTrue(packet["decision_points"][0]["requires_human_decision"])
        self.assertEqual(packet["decision_points"][0]["orchestrator_action"], "present_at_end")


def _feedback(severity: str) -> dict:
    return {
        "feedback": [
            {
                "feedback_id": "fb-1",
                "normalized_severity": severity,
            }
        ]
    }


def _decision_point(
    *,
    decision_id: str = "dec_aaaaaaaaaaaaaaaa",
    round_number: int = 1,
    profile: str = "operability",
    section: str = "Rules",
    trigger_types: list[str] | None = None,
    requires_human_decision: bool = True,
    orchestrator_action: str = "present_at_end",
) -> dict:
    triggers = trigger_types or ["tighten_requirement"]
    return {
        "decision_id": decision_id,
        "round_number": round_number,
        "profile": profile,
        "source_feedback_ids": ["fb-1"],
        "affected_sections": [section],
        "decision_type": triggers[0],
        "trigger_types": triggers,
        "evidence_lines": ["- Adapter MUST retry."],
        "question": f"Should `{section}` adopt this change?",
        "options_considered": [
            {
                "option_id": "selected",
                "label": "Keep editor change",
                "description": "Keep the revised draft behavior.",
            }
        ],
        "editor_selected_option_id": "selected",
        "editor_rationale": "Detected from diff.",
        "risk_if_wrong": "The spec may encode an unintended decision.",
        "decision_status": "operator_review_recommended" if requires_human_decision else "record_only_hardening",
        "requires_human_decision": requires_human_decision,
        "orchestrator_action": orchestrator_action,
    }


if __name__ == "__main__":
    unittest.main()
