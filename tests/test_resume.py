from __future__ import annotations

import json
from contextlib import redirect_stdout
from dataclasses import replace
import io
import re
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import OrchestratorConfig
from whetstone.cli import main, _apply_resume_run_state_config
from whetstone.hashing import draft_hash
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.resume import (
    _budget_extension_event_id,
    plan_budget_extension_resume,
    plan_resume_halted_run,
    resume_budget_exhausted_run,
    resume_halted_run,
)
from whetstone.status import read_status
from tests.test_live import (
    AppliedDraftEditorClient,
    GoodEmptyReviewerClient,
    GoodIssueReviewerClient,
    TimeoutEditorClient,
    _editor_round_number,
    _hash_line,
    _line_value,
)


class UniqueAppliedDraftEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def revise(self, prompt: str) -> dict:
        round_number = _editor_round_number(prompt)
        current_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        draft_after_content = self.root.joinpath("spec.md").read_text(encoding="utf-8")
        draft_after_content += f"\nClarified in round {round_number}.\n"
        return {
            "round_number": round_number,
            "draft_before_hash": current_hash,
            "draft_after_hash": None,
            "accepted_feedback_ids": ["fb-1"],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": ["iss_aaaaaaaaaaaaaaaa"],
            "unresolved_issue_ids": [],
            "draft_after_content": draft_after_content,
        }


class NoopEditorClient:
    def revise(self, prompt: str) -> dict:
        round_number = _editor_round_number(prompt)
        current_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        return {
            "round_number": round_number,
            "draft_before_hash": current_hash,
            "draft_after_hash": current_hash,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [],
        }


class TimeoutReviewerClient:
    def review(self, prompt: str) -> dict:
        raise TimeoutError("fixture reviewer timed out")


class TimeoutOnSecondReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def review(self, prompt: str) -> dict:
        self.calls += 1
        if self.calls == 2:
            raise TimeoutError("fixture reviewer timed out")
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash(self.root.joinpath("spec.md").read_text(encoding="utf-8")),
            "feedback": [
                {
                    "feedback_id": "fb-1",
                    "issue_id": "iss_aaaaaaaaaaaaaaaa",
                    "issue_fingerprint": "a" * 64,
                    "issue_type": "precision_gap",
                    "affected_sections": ["Spec"],
                    "baseline_severity": "major",
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": "major",
                    "invariant_violated": None,
                    "claim": "Fixture major.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Clarify issue.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            ],
        }


class ScriptedSeverityReviewerClient:
    def __init__(self, root: Path, severities: list[str | None]) -> None:
        self.root = root
        self.severities = severities
        self.calls = 0

    def review(self, prompt: str) -> dict:
        self.calls += 1
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        severity = self.severities[self.calls - 1] if self.calls - 1 < len(self.severities) else None
        feedback = []
        if severity is not None:
            feedback.append(
                {
                    "feedback_id": f"fb-{self.calls}",
                    "issue_id": f"iss_{self.calls:016x}",
                    "issue_fingerprint": f"{self.calls:x}" * 64,
                    "issue_type": "precision_gap",
                    "affected_sections": ["Spec"],
                    "baseline_severity": severity,
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": severity,
                    "invariant_violated": None,
                    "claim": f"Fixture {severity}.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Clarify the behavior.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            )
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash(self.root.joinpath("spec.md").read_text(encoding="utf-8")),
            "feedback": feedback,
        }


class MissingDraftContentEditorClient:
    def revise(self, prompt: str) -> dict:
        round_number = _editor_round_number(prompt)
        current_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        return {
            "round_number": round_number,
            "draft_before_hash": current_hash,
            "draft_after_hash": current_hash,
            "accepted_feedback_ids": ["fb-1"],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": ["iss_aaaaaaaaaaaaaaaa"],
            "unresolved_issue_ids": [],
            "draft_after_content": None,
        }


class OperabilityMinorReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def review(self, prompt: str) -> dict:
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        feedback = []
        if profile == "operability":
            feedback.append(
                {
                    "feedback_id": "fb-minor",
                    "issue_id": "iss_bbbbbbbbbbbbbbbb",
                    "issue_fingerprint": "b" * 64,
                    "issue_type": "precision_gap",
                    "affected_sections": ["Spec"],
                    "baseline_severity": "minor",
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": "minor",
                    "invariant_violated": None,
                    "claim": "Fixture minor.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Clarify minor issue.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            )
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash(self.root.joinpath("spec.md").read_text(encoding="utf-8")),
            "feedback": feedback,
        }


class ScriptedVerticalReviewerClient:
    def __init__(self, root: Path, severities: list[str | None]) -> None:
        self.root = root
        self.severities = severities
        self.calls = 0

    def review(self, prompt: str) -> dict:
        self.calls += 1
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        severity = self.severities[self.calls - 1] if self.calls - 1 < len(self.severities) else None
        feedback = []
        if severity is not None:
            feedback.append(
                {
                    "feedback_id": f"fb-{self.calls}",
                    "issue_id": f"iss_{self.calls:016x}",
                    "issue_fingerprint": f"{self.calls:x}" * 64,
                    "issue_type": "precision_gap",
                    "affected_sections": ["Spec"],
                    "baseline_severity": severity,
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": severity,
                    "invariant_violated": None,
                    "claim": f"Fixture {severity}.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Clarify issue.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            )
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash(self.root.joinpath("spec.md").read_text(encoding="utf-8")),
            "feedback": feedback,
        }


class ResolvingPromptEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def revise(self, prompt: str) -> dict:
        round_number = _editor_round_number(prompt)
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        feedback_text = _feedback_text_from_prompt(prompt, self.root)
        issue_ids = sorted(set(re.findall(r'"issue_id": "(iss_[a-f0-9]{16})"', feedback_text)))
        feedback_ids = sorted(set(re.findall(r'"feedback_id": "([^"]+)"', feedback_text)))
        draft_after_content = self.root.joinpath("spec.md").read_text(encoding="utf-8")
        if issue_ids:
            draft_after_content += f"\nResolved in round {round_number}.\n"
        return {
            "round_number": round_number,
            "draft_before_hash": before_hash,
            "draft_after_hash": None,
            "accepted_feedback_ids": feedback_ids,
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": issue_ids,
            "unresolved_issue_ids": [],
            "draft_after_content": draft_after_content,
        }


class ResumeTests(unittest.TestCase):
    def test_resume_phase1_reviewer_timeout_retries_reviewer_and_completes_round(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=TimeoutReviewerClient(),
                editor_client=NoopEditorClient(),
            ).run()

            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_invalid_attempt_1.json").exists())
            self.assertFalse(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())

            plan = plan_resume_halted_run(root, OrchestratorConfig.default(root), continue_run=True)
            self.assertTrue(plan.resumable)
            self.assertEqual(plan.client_role, "reviewer")
            self.assertEqual(plan.next_attempt_number, 2)
            self.assertIn("Reviewer timeout", plan.reason)

            resumed = resume_halted_run(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=AppliedDraftEditorClient(
                    "# Spec\n\n## Hashing\n\nDraft.\n\nClarified after reviewer retry.\n",
                    resolved_issue_ids=["iss_aaaaaaaaaaaaaaaa"],
                ),
            )

            self.assertTrue(resumed.resumed)
            self.assertIsNone(resumed.terminal_state)
            self.assertEqual(resumed.round_number, 1)
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_summary.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_invalid_attempt_1.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/prompt_snapshots/reviewer-reviewer_feedback.json-attempt-2.json").exists())
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())
            self.assertIn("Clarified after reviewer retry.", root.joinpath("spec.md").read_text(encoding="utf-8"))

    def test_resume_vertical_reviewer_timeout_preserves_partial_cycle_feedback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_mode="vertical",
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )

            halted = LivePhase1Runner(
                root,
                config,
                reviewer_client=TimeoutOnSecondReviewerClient(root),
                editor_client=NoopEditorClient(),
            ).run()

            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")
            self.assertEqual(halted.round_number, 2)
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())
            self.assertFalse(root.joinpath("rounds/round-2/reviewer_feedback.json").exists())

            plan = plan_resume_halted_run(root, config, continue_run=True)
            self.assertTrue(plan.resumable)
            self.assertEqual(plan.client_role, "reviewer")
            self.assertEqual(plan.profile, "determinism")
            self.assertEqual(plan.next_attempt_number, 2)
            self.assertEqual(plan.next_round_number, 3)

            resumed = resume_halted_run(
                root,
                config,
                continue_run=True,
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=ResolvingPromptEditorClient(root),
            )

            self.assertEqual(resumed.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(resumed.ready_for_phase_2)
            self.assertEqual(resumed.round_number, 7)
            synthetic_feedback = json.loads(root.joinpath("rounds/round-4/reviewer_feedback.json").read_text(encoding="utf-8"))
            self.assertEqual(synthetic_feedback["profile"], "vertical")
            self.assertEqual(synthetic_feedback["feedback"][0]["feedback_id"], "structural_integrity:fb-1")
            self.assertTrue(root.joinpath("rounds/round-2/prompt_snapshots/reviewer-reviewer_feedback.json-attempt-2.json").exists())
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])

    def test_resume_horizontal_continuation_runs_closeout_when_no_profiles_remain(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )

            halted = LivePhase1Runner(
                root,
                config,
                reviewer_client=TimeoutOnSecondReviewerClient(root),
                editor_client=ResolvingPromptEditorClient(root),
            ).run()

            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")
            self.assertEqual(halted.round_number, 2)
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())
            self.assertFalse(root.joinpath("rounds/round-2/reviewer_feedback.json").exists())

            resumed = resume_halted_run(
                root,
                config,
                continue_run=True,
                reviewer_client=ScriptedSeverityReviewerClient(root, ["major", None, None, None]),
                editor_client=ResolvingPromptEditorClient(root),
            )

            self.assertEqual(resumed.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(resumed.ready_for_phase_2)
            self.assertEqual(resumed.round_number, 5)
            expected_schedule = [
                ("structural_integrity", "review_editor"),
                ("determinism", "review_editor"),
                ("operability", "review_editor"),
                ("structural_integrity", "review_only"),
                ("determinism", "review_only"),
            ]
            for round_number, expected in enumerate(expected_schedule, start=1):
                profile_used = json.loads(
                    root.joinpath(f"rounds/round-{round_number}/profile_used.yaml").read_text(encoding="utf-8")
                )
                self.assertEqual((profile_used["profile"], profile_used["round_kind"]), expected)
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])
            self.assertFalse(root.joinpath("rounds/technical_failure_report.json").exists())

    def test_resume_phase1_editor_timeout_reuses_existing_reviewer_feedback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=TimeoutEditorClient(),
            ).run()

            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            before_resume_feedback = root.joinpath("rounds/round-1/reviewer_feedback.json").read_text(encoding="utf-8")

            resumed = resume_halted_run(
                root,
                OrchestratorConfig.default(root),
                editor_client=AppliedDraftEditorClient(
                    "# Spec\n\n## Hashing\n\nDraft.\n\nClarified.\n",
                    resolved_issue_ids=["iss_aaaaaaaaaaaaaaaa"],
                ),
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

    def test_resume_phase1_editor_artifact_validation_reuses_existing_reviewer_feedback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=MissingDraftContentEditorClient(),
            ).run()

            self.assertEqual(halted.terminal_state, "HALTED_ARTIFACT_INVALID")
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_2.json").exists())
            report = json.loads(root.joinpath("rounds/technical_failure_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["last_reviewer_findings"]["profile"], "structural_integrity")
            self.assertEqual(report["last_reviewer_findings"]["blocker_count"], 0)
            self.assertEqual(report["last_reviewer_findings"]["major_count"], 1)
            self.assertEqual(report["last_reviewer_findings"]["feedback_ids"], ["fb-1"])
            self.assertEqual(report["unresolved_major_issues"][0]["issue_id"], "iss_aaaaaaaaaaaaaaaa")
            before_resume_feedback = root.joinpath("rounds/round-1/reviewer_feedback.json").read_text(encoding="utf-8")

            plan = plan_resume_halted_run(root, OrchestratorConfig.default(root), continue_run=True)
            self.assertTrue(plan.resumable)
            self.assertEqual(plan.terminal_state, "HALTED_ARTIFACT_INVALID")
            self.assertEqual(plan.failure_type, "artifact_validation")
            self.assertEqual(plan.client_role, "editor")
            self.assertEqual(plan.next_attempt_number, 3)
            self.assertIn("artifact-validation", plan.reason)

            resumed = resume_halted_run(
                root,
                OrchestratorConfig.default(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            )

            self.assertTrue(resumed.resumed)
            self.assertIsNone(resumed.terminal_state)
            self.assertEqual(resumed.round_number, 1)
            self.assertEqual(root.joinpath("rounds/round-1/reviewer_feedback.json").read_text(encoding="utf-8"), before_resume_feedback)
            self.assertTrue(root.joinpath("rounds/round-1/editor_summary.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/prompt_snapshots/editor-editor_summary.json-attempt-3.json").exists())
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())
            self.assertIn("Clarified in round 1.", root.joinpath("spec.md").read_text(encoding="utf-8"))

    def test_resume_continue_drives_remaining_phase1_profiles(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            halted = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=TimeoutEditorClient(),
            ).run()
            self.assertEqual(halted.terminal_state, "HALTED_CLIENT_TIMEOUT")

            resumed = resume_halted_run(
                root,
                OrchestratorConfig.default(root),
                continue_run=True,
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=AppliedDraftEditorClient(
                    "# Spec\n\n## Hashing\n\nDraft.\n\nClarified.\n",
                    resolved_issue_ids=["iss_aaaaaaaaaaaaaaaa"],
                ),
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
                reviewer_client=GoodIssueReviewerClient(root),
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
                reviewer_client=GoodIssueReviewerClient(root),
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
                reviewer_client=GoodIssueReviewerClient(root),
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

    def test_budget_extension_resume_appends_rounds_and_records_event(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )

            exhausted = LivePhase1Runner(
                root,
                config,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            ).run()
            self.assertEqual(exhausted.terminal_state, "TARGET_NOT_REACHED")
            self.assertEqual(exhausted.round_number, 6)
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())
            round_1_before = root.joinpath("rounds/round-1/reviewer_feedback.json").read_text(encoding="utf-8")

            plan = plan_budget_extension_resume(root, config, extend_review_budget=1)
            self.assertTrue(plan.resumable)
            self.assertEqual(plan.failure_type, "budget_exhausted")
            self.assertEqual(plan.next_round_number, 7)

            resumed = resume_budget_exhausted_run(
                root,
                config,
                extend_review_budget=1,
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=NoopEditorClient(),
            )

            self.assertEqual(resumed.terminal_state, "PHASE_1_STABLE")
            self.assertEqual(resumed.round_number, 9)
            self.assertEqual(root.joinpath("rounds/round-1/reviewer_feedback.json").read_text(encoding="utf-8"), round_1_before)
            self.assertTrue(root.joinpath("rounds/round-7/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-9/reviewer_feedback.json").exists())
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertEqual(state["review_profile_budgets"]["structural_integrity"], 3)
            self.assertEqual(state["effective_run_config"]["review_profile_budgets"]["determinism"], 3)
            self.assertEqual(len(state["budget_extensions"]), 1)
            self.assertEqual(state["budget_extensions"][0]["previous_terminal_state"], "TARGET_NOT_REACHED")
            self.assertEqual(state["budget_extensions"][0]["added_rounds_per_profile"], 1)
            self.assertRegex(state["budget_extensions"][0]["event_id"], r"^bxe_[a-f0-9]{16}$")

    def test_budget_extension_second_budget_stop_refreshes_terminal_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )

            exhausted = LivePhase1Runner(
                root,
                config,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            ).run()
            self.assertEqual(exhausted.terminal_state, "TARGET_NOT_REACHED")
            first_report = json.loads(root.joinpath("rounds/technical_failure_report.json").read_text(encoding="utf-8"))

            resumed = resume_budget_exhausted_run(
                root,
                config,
                extend_review_budget=1,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            )

            self.assertEqual(resumed.terminal_state, "TARGET_NOT_REACHED")
            self.assertGreater(resumed.round_number, first_report["round_number"])
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            report = json.loads(root.joinpath("rounds/technical_failure_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["terminal_state"], "TARGET_NOT_REACHED")
            self.assertEqual(report["round_number"], state["current_round"])
            self.assertEqual(report["round_number"], resumed.round_number)
            self.assertEqual(report["draft_hash"], state["current_draft_hash"])
            self.assertEqual(report["current_draft_status"], "accepted_unverified_profiles")

    def test_budget_extension_event_id_is_stable_and_excludes_timestamp(self) -> None:
        previous_state = {
            "terminal_state": "TARGET_NOT_REACHED",
            "current_round": 6,
            "current_draft_hash": "a" * 64,
            "updated_at": "2026-05-01T00:00:00Z",
        }
        original_budgets = {"structural_integrity": 2, "determinism": 2, "operability": 2}
        extended_budgets = {"structural_integrity": 3, "determinism": 3, "operability": 3}

        first = _budget_extension_event_id(
            previous_state=previous_state,
            original_budgets=original_budgets,
            extended_budgets=extended_budgets,
            extension_rounds=1,
            reason="operator_requested_resume_budget_extension",
            extension_ordinal=1,
        )
        second = _budget_extension_event_id(
            previous_state={**previous_state, "updated_at": "2026-05-02T00:00:00Z"},
            original_budgets=dict(reversed(original_budgets.items())),
            extended_budgets=dict(reversed(extended_budgets.items())),
            extension_rounds=1,
            reason="operator_requested_resume_budget_extension",
            extension_ordinal=1,
        )
        third = _budget_extension_event_id(
            previous_state=previous_state,
            original_budgets=original_budgets,
            extended_budgets=extended_budgets,
            extension_rounds=1,
            reason="operator_requested_resume_budget_extension",
            extension_ordinal=2,
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_vertical_budget_extension_resume_appends_cycles_and_records_event(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_mode="vertical",
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )

            exhausted = LivePhase1Runner(
                root,
                config,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            ).run()
            self.assertEqual(exhausted.terminal_state, "TARGET_NOT_REACHED")
            self.assertEqual(exhausted.round_number, 7)
            self.assertEqual(json.loads(root.joinpath("rounds/round-4/reviewer_feedback.json").read_text())["profile"], "vertical")

            plan = plan_budget_extension_resume(root, config, extend_review_budget=1)
            self.assertTrue(plan.resumable)
            self.assertEqual(plan.next_round_number, 8)

            resumed = resume_budget_exhausted_run(
                root,
                config,
                extend_review_budget=1,
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=NoopEditorClient(),
            )

            self.assertEqual(resumed.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(resumed.ready_for_phase_2)
            self.assertEqual(resumed.round_number, 10)
            self.assertTrue(root.joinpath("rounds/round-8/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-9/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-10/reviewer_feedback.json").exists())
            self.assertFalse(root.joinpath("rounds/round-11").exists())
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertEqual(state["review_mode"], "vertical")
            self.assertEqual(state["review_profile_budgets"]["structural_integrity"], 3)
            self.assertEqual(state["review_round_budget"], 12)
            self.assertEqual(len(state["budget_extensions"]), 1)
            self.assertEqual(state["budget_extensions"][0]["new_review_profile_budgets"]["operability"], 3)

    def test_vertical_budget_extension_consolidated_editor_timeout_terminalizes_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_mode="vertical",
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )

            exhausted = LivePhase1Runner(
                root,
                config,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            ).run()
            self.assertEqual(exhausted.terminal_state, "TARGET_NOT_REACHED")

            resumed = resume_budget_exhausted_run(
                root,
                config,
                extend_review_budget=1,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=TimeoutEditorClient(),
            )

            self.assertEqual(resumed.terminal_state, "HALTED_CLIENT_TIMEOUT")
            self.assertFalse(resumed.ready_for_phase_2)
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "HALTED_CLIENT_TIMEOUT")
            self.assertEqual(state["active_profile"], "vertical")
            self.assertEqual(state["current_round"], 11)
            technical = json.loads(root.joinpath("rounds/technical_failure_report.json").read_text(encoding="utf-8"))
            self.assertEqual(technical["terminal_state"], "HALTED_CLIENT_TIMEOUT")
            self.assertEqual(len(technical["unresolved_major_issues"]), 3)
            self.assertTrue(root.joinpath("rounds/operator_decision_checkpoint_summary.json").exists())

    def test_vertical_budget_extension_closeout_stabilizes_final_editor_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_mode="vertical",
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )

            exhausted = LivePhase1Runner(
                root,
                config,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            ).run()
            self.assertEqual(exhausted.terminal_state, "TARGET_NOT_REACHED")

            resumed = resume_budget_exhausted_run(
                root,
                config,
                extend_review_budget=1,
                reviewer_client=OperabilityMinorReviewerClient(root),
                editor_client=ResolvingPromptEditorClient(root),
            )

            self.assertEqual(resumed.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(resumed.ready_for_phase_2)
            self.assertEqual(resumed.round_number, 14)
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])

    def test_vertical_budget_extension_closeout_clears_stale_exhausted_profile(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_mode="vertical",
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )

            exhausted = LivePhase1Runner(
                root,
                config,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            ).run()
            self.assertEqual(exhausted.terminal_state, "TARGET_NOT_REACHED")

            reviewer = ScriptedVerticalReviewerClient(root, ["major", None, "minor", None, None, None])
            resumed = resume_budget_exhausted_run(
                root,
                config,
                extend_review_budget=1,
                reviewer_client=reviewer,
                editor_client=ResolvingPromptEditorClient(root),
            )

            self.assertEqual(resumed.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(resumed.ready_for_phase_2)
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])
            self.assertEqual(reviewer.calls, 6)

    def test_resume_cli_budget_extension_dry_run_outputs_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                review_profile_budgets={
                    "structural_integrity": 1,
                    "determinism": 1,
                    "operability": 1,
                },
            )
            root.joinpath("orchestrator_config.yaml").write_text(
                "review:\n"
                "  profile_budgets:\n"
                "    structural_integrity: 1\n"
                "    determinism: 1\n"
                "    operability: 1\n",
                encoding="utf-8",
            )
            exhausted = LivePhase1Runner(
                root,
                config,
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=UniqueAppliedDraftEditorClient(root),
            ).run()
            self.assertEqual(exhausted.terminal_state, "TARGET_NOT_REACHED")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["resume", "--root", str(root), "--extend-review-budget", "2", "--dry-run"])
            packet = json.loads(stdout.getvalue())

            self.assertEqual(exit_code, 0)
            self.assertTrue(packet["resumable"])
            self.assertEqual(packet["failure_type"], "budget_exhausted")
            self.assertEqual(packet["extend_review_budget"], 2)
            self.assertEqual(packet["next_round_number"], 7)

    def test_budget_extension_dry_run_accepts_horizontal_blocks_with_closeout_after_prior_extension(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            original_budgets = {
                "structural_integrity": 2,
                "determinism": 2,
                "operability": 1,
            }
            extended_budgets = {
                "structural_integrity": 5,
                "determinism": 5,
                "operability": 4,
            }
            config = replace(OrchestratorConfig.default(root), review_profile_budgets=original_budgets)
            result = LivePhase1Runner(
                root,
                config,
                reviewer_client=ScriptedSeverityReviewerClient(
                    root,
                    [
                        "major",
                        "major",
                        "major",
                        "major",
                        None,
                        "major",
                        "major",
                    ],
                ),
                editor_client=ResolvingPromptEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "TARGET_NOT_REACHED")
            self.assertEqual(result.round_number, 7)
            expected_schedule = [
                ("structural_integrity", "review_editor"),
                ("structural_integrity", "review_editor"),
                ("determinism", "review_editor"),
                ("determinism", "review_editor"),
                ("operability", "review_editor"),
                ("structural_integrity", "review_only"),
                ("determinism", "review_only"),
            ]
            for round_number, expected in enumerate(expected_schedule, start=1):
                profile_used = json.loads(
                    root.joinpath(f"rounds/round-{round_number}/profile_used.yaml").read_text(encoding="utf-8")
                )
                self.assertEqual((profile_used["profile"], profile_used["round_kind"]), expected)

            state_path = root / "rounds" / "run_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["review_profile_budgets"] = extended_budgets
            state["configured_review_profile_budgets"] = extended_budgets
            state["review_round_budget"] = sum(extended_budgets.values())
            state["effective_run_config"]["review_profile_budgets"] = extended_budgets
            state["budget_extensions"] = [
                {
                    "added_rounds_per_profile": 3,
                    "event_id": "bxe_fixture000000",
                    "generated_at": "2026-06-20T00:00:00+00:00",
                    "new_review_profile_budgets": extended_budgets,
                    "phase": "phase_1",
                    "previous_current_round": 5,
                    "previous_review_profile_budgets": original_budgets,
                    "previous_terminal_state": "TARGET_NOT_REACHED",
                    "reason": "operator_requested_resume_budget_extension",
                }
            ]
            state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            resume_config = _apply_resume_run_state_config(OrchestratorConfig.default(root))
            plan = plan_budget_extension_resume(root, resume_config, extend_review_budget=3)
            self.assertTrue(plan.resumable)
            self.assertEqual(plan.next_round_number, 8)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["resume", "--root", str(root), "--extend-review-budget", "3", "--dry-run"])
            packet = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(packet["resumable"])
            self.assertEqual(packet["next_round_number"], 8)

            status = read_status(root=root, config=OrchestratorConfig.default(root))
            self.assertTrue(status["resume"]["eligible"])
            self.assertIn("--extend-review-budget 3", status["resume"]["command"])


def _feedback_text_from_prompt(prompt: str, root: Path) -> str:
    path_match = re.search(r"Reviewer feedback JSON path: ([^\n]+)", prompt)
    if path_match:
        return (root / path_match.group(1)).read_text(encoding="utf-8")
    return prompt


if __name__ == "__main__":
    unittest.main()
