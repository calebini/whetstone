from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import OrchestratorConfig
from whetstone.hashing import draft_hash
from whetstone.identity import oscillation_fingerprint, oscillation_opposition_key
from whetstone.live import LiveRoundRunner


class FakeReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def review(self, prompt: str) -> dict:
        snapshot = json.loads((self.root / "rounds" / "round-1" / "prompt_snapshot.json").read_text(encoding="utf-8"))
        assert snapshot["reviewer_prompt_text"] == prompt
        assert snapshot["editor_prompt_text"] is None
        fingerprint = oscillation_fingerprint("spec-hashing", "precision_gap", "clarify", "local")
        opposition_key = oscillation_opposition_key("spec-hashing", "precision_gap", "local")
        return {
            "round_number": 1,
            "profile": "convergence_strict_check",
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [
                {
                    "feedback_id": "fb-1",
                    "issue_id": "iss_aaaaaaaaaaaaaaaa",
                    "issue_fingerprint": "a" * 64,
                    "issue_type": "precision_gap",
                    "affected_sections": ["spec-hashing"],
                    "baseline_severity": "major",
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": "major",
                    "invariant_violated": None,
                    "claim": "Hashing needs precision.",
                    "evidence": "Fixture.",
                    "recommended_change": "Clarify hashing.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": {
                        "section_id": "spec-hashing",
                        "concern_type": "precision_gap",
                        "direction": "clarify",
                        "scope": "local",
                        "fingerprint": fingerprint,
                        "opposition_key": opposition_key,
                    },
                }
            ],
        }


class FakeEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def revise(self, prompt: str) -> dict:
        snapshot = json.loads((self.root / "rounds" / "round-1" / "prompt_snapshot.json").read_text(encoding="utf-8"))
        assert snapshot["editor_prompt_text"] == prompt
        current_hash = draft_hash((self.root / "spec.md").read_text(encoding="utf-8"))
        return {
            "round_number": 1,
            "draft_before_hash": current_hash,
            "draft_after_hash": current_hash,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": ["iss_aaaaaaaaaaaaaaaa"],
        }


class RecordingEditorClient:
    def __init__(self) -> None:
        self.called = False

    def revise(self, prompt: str) -> dict:
        self.called = True
        return {}


class BadReviewerClient:
    def review(self, prompt: str) -> dict:
        return {
            "round_number": 1,
            "profile": "determinism",
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": "b" * 64,
            "feedback": [],
        }


class FlakyReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def review(self, prompt: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "round_number": 1,
                "profile": "determinism",
                "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
                "draft_hash": "b" * 64,
                "feedback": [],
            }
        return {
            "round_number": 1,
            "profile": "determinism",
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [],
        }


class GoodEmptyReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def review(self, prompt: str) -> dict:
        return {
            "round_number": 1,
            "profile": "determinism",
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [],
        }


class BadEditorClient:
    def revise(self, prompt: str) -> dict:
        return {
            "round_number": 1,
            "draft_before_hash": "b" * 64,
            "draft_after_hash": "b" * 64,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [],
        }


class FlakyEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        current_hash = draft_hash((self.root / "spec.md").read_text(encoding="utf-8"))
        if self.calls == 1:
            return {
                "round_number": 1,
                "draft_before_hash": "b" * 64,
                "draft_after_hash": "b" * 64,
                "accepted_feedback_ids": [],
                "modified_feedback_ids": [],
                "declined_feedback": [],
                "created_conflict_ids": [],
                "resolved_issue_ids": [],
                "unresolved_issue_ids": [],
            }
        return {
            "round_number": 1,
            "draft_before_hash": current_hash,
            "draft_after_hash": current_hash,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [],
        }


class LiveRoundRunnerTests(unittest.TestCase):
    def test_live_round_writes_guarded_packet_without_mutating_spec(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = "# Spec\n\n## Hashing\n\nDraft.\n"
            root.joinpath("spec.md").write_text(spec, encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            config = OrchestratorConfig.default(root)

            result = LiveRoundRunner(
                root,
                config,
                reviewer_client=FakeReviewerClient(root),
                editor_client=FakeEditorClient(root),
            ).run_round(round_number=1, profile="convergence_strict_check", phase="phase_2")

            self.assertFalse(result.accepted)
            self.assertFalse(result.spec_mutated)
            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), spec)
            round_dir = root / "rounds" / "round-1"
            expected = {
                "draft_before.md",
                "draft_after.md",
                "decision_points.json",
                "editor_summary.json",
                "profile_used.yaml",
                "prompt_snapshot.json",
                "prompt_snapshots",
                "reviewer_feedback.json",
                "reviewer_working_notes.md",
                "unresolved_issues.json",
            }
            self.assertEqual({path.name for path in round_dir.iterdir()}, expected)
            unresolved = json.loads(round_dir.joinpath("unresolved_issues.json").read_text(encoding="utf-8"))
            self.assertTrue(unresolved["unresolved_issues"][0]["in_scope"])
            self.assertTrue(unresolved["unresolved_issues"][0]["blocking_acceptance"])

    def test_live_round_writes_config_error_before_round_when_client_metadata_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
            config = OrchestratorConfig.default(root)
            bad_config = OrchestratorConfig(
                spec_path=config.spec_path,
                history_path=config.history_path,
                rounds_dir=config.rounds_dir,
                declaration_path=config.declaration_path,
                editor=config.editor,
                reviewer=type(config.reviewer)(config.reviewer.name, config.reviewer.command, "", config.reviewer.model),
                review_max_rounds=config.review_max_rounds,
                convergence=config.convergence,
                decision_points=config.decision_points,
            )

            with self.assertRaises(ValueError):
                LiveRoundRunner(
                    root,
                    bad_config,
                    reviewer_client=FakeReviewerClient(root),
                    editor_client=FakeEditorClient(root),
                ).run_round(round_number=1, profile="determinism")

            error = json.loads(root.joinpath("rounds/config_validation_error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["terminal_state"], "CONFIG_INVALID")
            self.assertFalse(root.joinpath("rounds/round-1").exists())

    def test_malformed_reviewer_output_rejects_before_editor_invocation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
            editor = RecordingEditorClient()

            with self.assertRaises(ValueError):
                LiveRoundRunner(
                    root,
                    OrchestratorConfig.default(root),
                    reviewer_client=BadReviewerClient(),
                    editor_client=editor,
                ).run_round(round_number=1, profile="determinism")

            self.assertFalse(editor.called)
            self.assertFalse(root.joinpath("rounds/round-1/editor_summary.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_invalid_attempt_1.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_invalid_attempt_2.json").exists())
            prompt_snapshots = root / "rounds" / "round-1" / "prompt_snapshots"
            attempt_1 = json.loads(
                prompt_snapshots.joinpath("reviewer-reviewer_feedback.json-attempt-1.json").read_text(encoding="utf-8")
            )
            attempt_2 = json.loads(
                prompt_snapshots.joinpath("reviewer-reviewer_feedback.json-attempt-2.json").read_text(encoding="utf-8")
            )
            self.assertEqual(attempt_1["validation_errors"], [])
            self.assertEqual(attempt_2["artifact_name"], "reviewer_feedback.json")
            self.assertTrue(attempt_2["validation_errors"])
            self.assertIn("previous response did not validate", attempt_2["prompt_text"])
            error = json.loads(root.joinpath("rounds/artifact_validation_error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["terminal_state"], "HALTED_ARTIFACT_INVALID")
            self.assertEqual(error["client_role"], "reviewer")
            self.assertEqual(len(error["attempts"]), 2)
            self.assertEqual(error["last_valid_draft_path"], "rounds/round-1/draft_before.md")
            technical = json.loads(root.joinpath("rounds/technical_failure_report.json").read_text(encoding="utf-8"))
            self.assertEqual(technical["terminal_state"], "HALTED_ARTIFACT_INVALID")
            self.assertEqual(technical["final_draft_path"], "rounds/round-1/draft_before.md")

    def test_reviewer_validation_retry_can_recover(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
            reviewer = FlakyReviewerClient(root)

            result = LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=FakeEditorClient(root),
            ).run_round(round_number=1, profile="determinism")

            self.assertTrue(result.accepted)
            self.assertEqual(reviewer.calls, 2)
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_invalid_attempt_1.json").exists())
            self.assertTrue(
                root.joinpath("rounds/round-1/prompt_snapshots/reviewer-reviewer_feedback.json-attempt-2.json").exists()
            )
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())

    def test_malformed_editor_output_rejects_before_spec_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = "# Spec\n\n## Hashing\n\nBefore.\n"
            after = "# Spec\n\n## Hashing\n\nAfter.\n"
            root.joinpath("spec.md").write_text(before, encoding="utf-8")

            with self.assertRaises(ValueError):
                LiveRoundRunner(
                    root,
                    OrchestratorConfig.default(root),
                    reviewer_client=FakeReviewerClient(root),
                    editor_client=BadEditorClient(),
                ).run_round(
                    round_number=1,
                    profile="convergence_strict_check",
                    phase="phase_2",
                    draft_after=after,
                    apply=True,
                )

            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), before)
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_2.json").exists())
            error = json.loads(root.joinpath("rounds/artifact_validation_error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["terminal_state"], "HALTED_ARTIFACT_INVALID")
            self.assertEqual(error["client_role"], "editor")
            self.assertEqual(error["last_valid_draft_path"], "rounds/round-1/draft_after.md")
            self.assertTrue(
                root.joinpath("rounds/round-1/prompt_snapshots/editor-editor_summary.json-attempt-2.json").exists()
            )
            convergence = json.loads(root.joinpath("rounds/convergence_failure_report.json").read_text(encoding="utf-8"))
            self.assertEqual(convergence["terminal_state"], "HALTED_ARTIFACT_INVALID")
            self.assertEqual(convergence["final_draft_path"], "rounds/round-1/draft_after.md")

    def test_editor_validation_retry_can_recover_after_valid_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            editor = FlakyEditorClient(root)

            result = LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=editor,
            ).run_round(round_number=1, profile="determinism")

            self.assertTrue(result.accepted)
            self.assertEqual(editor.calls, 2)
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())


if __name__ == "__main__":
    unittest.main()
