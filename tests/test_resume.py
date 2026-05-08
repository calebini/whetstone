from __future__ import annotations

import json
from contextlib import redirect_stdout
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import OrchestratorConfig
from whetstone.cli import main, _apply_resume_run_state_config
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.resume import plan_resume_halted_run, resume_halted_run
from tests.test_live import AppliedDraftEditorClient, GoodEmptyReviewerClient, TimeoutEditorClient


class ResumeTests(unittest.TestCase):
    def test_resume_phase1_editor_timeout_reuses_existing_reviewer_feedback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=TimeoutEditorClient(),
            ).run()

            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            before_resume_feedback = root.joinpath("rounds/round-1/reviewer_feedback.json").read_text(encoding="utf-8")

            resumed = resume_halted_run(
                root,
                OrchestratorConfig.default(root),
                editor_client=AppliedDraftEditorClient("# Spec\n\n## Hashing\n\nDraft.\n\nClarified.\n"),
            )

            self.assertTrue(resumed.resumed)
            self.assertIsNone(resumed.terminal_state)
            self.assertEqual(resumed.round_number, 1)
            self.assertEqual(root.joinpath("rounds/round-1/reviewer_feedback.json").read_text(encoding="utf-8"), before_resume_feedback)
            self.assertTrue(root.joinpath("rounds/round-1/editor_summary.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/prompt_snapshots/editor-editor_summary.json-attempt-2.json").exists())
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertIsNone(state["terminal_state"])
            self.assertEqual(state["current_round"], 1)
            self.assertEqual(state["active_profile"], "structural_integrity")
            self.assertIn("Clarified.", root.joinpath("spec.md").read_text(encoding="utf-8"))

    def test_resume_continue_drives_remaining_phase1_profiles(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=TimeoutEditorClient(),
            ).run()
            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")

            resumed = resume_halted_run(
                root,
                OrchestratorConfig.default(root),
                continue_run=True,
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=AppliedDraftEditorClient("# Spec\n\n## Hashing\n\nDraft.\n\nClarified.\n"),
            )

            self.assertEqual(resumed.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(resumed.ready_for_phase_2)
            self.assertEqual(resumed.round_number, 4)
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])
            self.assertEqual(state["current_round"], 4)
            self.assertTrue(root.joinpath("rounds/round-2/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-3/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-4/reviewer_feedback.json").exists())

    def test_resume_dry_run_validates_plan_without_invoking_editor(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=TimeoutEditorClient(),
            ).run()
            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")

            plan = plan_resume_halted_run(root, OrchestratorConfig.default(root), continue_run=True)

            self.assertTrue(plan.resumable)
            self.assertEqual(plan.round_number, 1)
            self.assertEqual(plan.profile, "structural_integrity")
            self.assertEqual(plan.next_attempt_number, 2)
            self.assertEqual(plan.next_round_number, 2)
            self.assertFalse(root.joinpath("rounds/round-1/editor_summary.json").exists())

    def test_resume_cli_dry_run_outputs_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=TimeoutEditorClient(),
            ).run()
            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["resume", "--root", str(root), "--continue", "--dry-run"])
            packet = json.loads(stdout.getvalue())

            self.assertEqual(exit_code, 0)
            self.assertTrue(packet["resumable"])
            self.assertTrue(packet["continue"])
            self.assertEqual(packet["next_round_number"], 2)

    def test_resume_cli_inherits_effective_run_config(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=TimeoutEditorClient(),
            ).run()
            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")
            state_path = root / "rounds" / "run_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["effective_run_config"] = {
                "review_profile_budgets": {
                    "structural_integrity": 7,
                    "determinism": 8,
                    "operability": 9,
                },
                "convergence_profile_budgets": {
                    "convergence_strict_check": 6,
                    "adversarial": 5,
                },
                "decision_points": {
                    "enabled": True,
                    "mode": "intervention",
                    "intervention_thresholds": {
                        "severities": ["blocker"],
                        "trigger_on_requirement_strength_change": False,
                        "trigger_on_authority_boundary_change": True,
                        "trigger_on_scope_change": False,
                        "trigger_on_new_enum_or_error_code": True,
                    },
                },
                "timeouts": {"reviewer_seconds": 111, "editor_seconds": 222},
            }
            state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            config = _apply_resume_run_state_config(OrchestratorConfig.default(root))

            self.assertEqual(
                config.review_profile_budgets,
                {"structural_integrity": 7, "determinism": 8, "operability": 9},
            )
            self.assertEqual(
                config.convergence_profile_budgets,
                {"convergence_strict_check": 6, "adversarial": 5},
            )
            self.assertEqual(config.decision_points.mode, "intervention")
            self.assertEqual(config.decision_points.severities, ("blocker",))
            self.assertFalse(config.decision_points.trigger_on_requirement_strength_change)
            self.assertTrue(config.decision_points.trigger_on_authority_boundary_change)
            self.assertFalse(config.decision_points.trigger_on_scope_change)
            self.assertTrue(config.decision_points.trigger_on_new_enum_or_error_code)
            self.assertEqual(config.timeouts.reviewer_seconds, 111)
            self.assertEqual(config.timeouts.editor_seconds, 222)


if __name__ == "__main__":
    unittest.main()
