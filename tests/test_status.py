from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import OrchestratorConfig
from whetstone.status import read_status, render_status_text


class StatusTests(unittest.TestCase):
    def test_status_without_run_state_suggests_phase1(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = read_status(root=root, config=OrchestratorConfig.default(root))

            self.assertFalse(status["run_state_exists"])
            self.assertEqual(status["next_action"], "run_live_phase1")
            self.assertIsNone(status["latest_round"])

    def test_status_reports_phase1_handoff_and_decision_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rounds = root / "rounds"
            round_dir = rounds / "round-3"
            round_dir.mkdir(parents=True)
            for artifact in (
                "draft_before.md",
                "draft_after.md",
                "profile_used.yaml",
                "prompt_snapshot.json",
                "reviewer_feedback.json",
                "editor_summary.json",
                "unresolved_issues.json",
                "decision_points.json",
            ):
                round_dir.joinpath(artifact).write_text("{}\n", encoding="utf-8")
            round_dir.joinpath("telemetry_summary.json").write_text(
                json.dumps(
                    {
                        "attempt_count": 6,
                        "total_duration_ms": None,
                        "total_api_duration_ms": None,
                        "total_tokens": None,
                        "total_cost_usd": None,
                        "missing_usage_attempts": 6,
                        "warnings": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rounds.joinpath("run_state.json").write_text(
                json.dumps(
                    {
                        "phase": "phase_1",
                        "current_round": 3,
                        "active_profile": None,
                        "terminal_state": "PHASE_1_STABLE",
                        "ready_for_phase_2": True,
                        "current_draft_hash": "a" * 64,
                        "last_accepted_draft_hash": "a" * 64,
                        "resumable": False,
                        "telemetry_totals": {"round_count": 3, "attempt_count": 6},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rounds.joinpath("decision_register.json").write_text(
                json.dumps({"decision_points": [{}, {}], "unresolved_human_decision_count": 2}),
                encoding="utf-8",
            )
            rounds.joinpath("decision_summary.json").write_text(
                json.dumps(
                    {
                        "decision_count": 2,
                        "unresolved_human_decision_count": 2,
                        "hotspots": {"largest_clusters": [], "human_decision_clusters": []},
                    }
                ),
                encoding="utf-8",
            )

            status = read_status(root=root, config=OrchestratorConfig.default(root))

            self.assertEqual(status["terminal_state"], "PHASE_1_STABLE")
            self.assertEqual(status["current_draft_status"], "phase_1_stable")
            self.assertEqual(status["next_action"], "run_live_phase2")
            self.assertTrue(status["latest_round"]["complete"])
            self.assertEqual(status["decision_register"]["decision_count"], 2)
            self.assertEqual(status["decision_summary"]["decision_count"], 2)
            self.assertEqual(status["telemetry_totals"]["attempt_count"], 6)

    def test_status_prefers_stable_run_state_over_stale_failure_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rounds = root / "rounds"
            rounds.mkdir()
            rounds.joinpath("run_state.json").write_text(
                json.dumps(
                    {
                        "phase": "phase_1",
                        "current_round": 71,
                        "active_profile": None,
                        "terminal_state": "PHASE_1_STABLE",
                        "ready_for_phase_2": True,
                        "current_draft_hash": "a" * 64,
                        "last_accepted_draft_hash": "a" * 64,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rounds.joinpath("technical_failure_report.json").write_text(
                json.dumps(
                    {
                        "terminal_state": "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS",
                        "current_draft_status": "accepted_unverified_profiles",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            status = read_status(root=root, config=OrchestratorConfig.default(root))

            self.assertEqual(status["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(status["ready_for_phase_2"])
            self.assertEqual(status["current_draft_status"], "phase_1_stable")
            self.assertEqual(status["next_action"], "run_live_phase2")

    def test_status_prefers_round_telemetry_over_stale_run_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rounds = root / "rounds"
            round_dir = rounds / "round-1"
            round_dir.mkdir(parents=True)
            round_dir.joinpath("telemetry_summary.json").write_text(
                json.dumps(
                    {
                        "attempt_count": 2,
                        "total_duration_ms": 100,
                        "total_api_duration_ms": 90,
                        "total_tokens": 1234,
                        "total_cost_usd": 0.1,
                        "missing_usage_attempts": 0,
                        "warnings": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rounds.joinpath("run_state.json").write_text(
                json.dumps(
                    {
                        "phase": "phase_1",
                        "current_round": 1,
                        "terminal_state": None,
                        "telemetry_totals": {"round_count": 0, "attempt_count": 0, "total_tokens": None},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            status = read_status(root=root, config=OrchestratorConfig.default(root))

            self.assertEqual(status["telemetry_totals"]["round_count"], 1)
            self.assertEqual(status["telemetry_totals"]["attempt_count"], 2)
            self.assertEqual(status["telemetry_totals"]["total_tokens"], 1234)

    def test_status_reports_incomplete_latest_round(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            round_dir = root / "rounds" / "round-1"
            round_dir.mkdir(parents=True)
            round_dir.joinpath("draft_before.md").write_text("# Spec\n", encoding="utf-8")
            root.joinpath("rounds/run_state.json").write_text(
                json.dumps({"phase": "phase_1", "current_round": 1, "terminal_state": None}) + "\n",
                encoding="utf-8",
            )

            status = read_status(root=root, config=OrchestratorConfig.default(root))

            self.assertFalse(status["latest_round"]["complete"])
            self.assertIn("reviewer_feedback.json", status["latest_round"]["missing_required_artifacts"])
            self.assertEqual(status["next_action"], "continue_or_resume_phase1")

    def test_status_reports_pending_client_attempt_without_telemetry(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            round_dir = root / "rounds" / "round-1"
            prompt_dir = round_dir / "prompt_snapshots"
            telemetry_dir = round_dir / "client_telemetry"
            prompt_dir.mkdir(parents=True)
            telemetry_dir.mkdir()
            prompt_dir.joinpath("reviewer-reviewer_feedback.json-attempt-1.json").write_text("{}", encoding="utf-8")
            telemetry_dir.joinpath("reviewer-reviewer_feedback.json-attempt-1.json").write_text("{}", encoding="utf-8")
            prompt_dir.joinpath("editor-editor_summary.json-attempt-1.json").write_text("{}", encoding="utf-8")
            root.joinpath("rounds/run_state.json").write_text(
                json.dumps({"phase": "phase_1", "current_round": 1, "terminal_state": None}) + "\n",
                encoding="utf-8",
            )

            status = read_status(root=root, config=OrchestratorConfig.default(root))

            pending = status["latest_round"]["pending_client_attempt"]
            self.assertEqual(pending["client_role"], "editor")
            self.assertEqual(pending["artifact_name"], "editor_summary.json")
            self.assertEqual(pending["attempt_number"], 1)

    def test_status_reports_resumable_editor_timeout_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rounds = root / "rounds"
            rounds.mkdir()
            rounds.joinpath("run_state.json").write_text(
                json.dumps(
                    {
                        "phase": "phase_1",
                        "current_round": 7,
                        "terminal_state": "HALTED_CLIENT_TIMEOUT",
                        "resumable": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rounds.joinpath("artifact_validation_error.json").write_text(
                json.dumps(
                    {
                        "terminal_state": "HALTED_CLIENT_TIMEOUT",
                        "failure_type": "client_timeout",
                        "phase": "phase_1",
                        "client_role": "editor",
                        "round_number": 7,
                        "profile": "determinism",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            status = read_status(root=root, config=OrchestratorConfig.default(root))
            rendered = render_status_text(status)

            self.assertEqual(status["next_action"], "resume_or_increase_timeout")
            self.assertTrue(status["resume"]["eligible"])
            self.assertEqual(status["resume"]["round_number"], 7)
            self.assertIn("whetstone resume --root", status["resume"]["command"])
            self.assertIn("--continue", status["resume"]["continue_command"])
            self.assertIn("resume_command:", rendered)
            self.assertIn("resume_continue_command:", rendered)

    def test_status_reports_budget_extension_resume_command(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rounds = root / "rounds"
            rounds.mkdir()
            rounds.joinpath("run_state.json").write_text(
                json.dumps(
                    {
                        "phase": "phase_1",
                        "current_round": 9,
                        "terminal_state": "TARGET_NOT_REACHED",
                        "resumable": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            status = read_status(root=root, config=OrchestratorConfig.default(root))
            rendered = render_status_text(status)

            self.assertTrue(status["resumable"])
            self.assertTrue(status["resume"]["eligible"])
            self.assertEqual(status["resume"]["failure_type"], "budget_exhausted")
            self.assertIn("--extend-review-budget 3", status["resume"]["command"])
            self.assertIn("resume_command:", rendered)

    def test_render_status_text_includes_operator_fields(self) -> None:
        status = {
            "root": "/tmp/run",
            "phase": "phase_1",
            "current_round": 3,
            "terminal_state": "PHASE_1_STABLE",
            "active_profile": None,
            "ready_for_phase_2": True,
            "resumable": False,
            "last_accepted_draft_hash": "a" * 64,
            "latest_round": {"round_number": 3, "complete": True},
            "next_action": "run_live_phase2",
            "terminal_report_path": None,
            "decision_summary": {"decision_count": 9, "unresolved_human_decision_count": 9},
            "decision_register": None,
            "telemetry_totals": {"round_count": 3, "attempt_count": 6, "total_tokens": 123},
        }

        rendered = render_status_text(status)

        self.assertIn("terminal_state: PHASE_1_STABLE", rendered)
        self.assertIn("next_action: run_live_phase2", rendered)
        self.assertIn("decisions: 9, human: 9", rendered)


if __name__ == "__main__":
    unittest.main()
