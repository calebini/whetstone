from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import OrchestratorConfig, ReferenceContextFileConfig
from whetstone.hashing import draft_hash
from whetstone.identity import oscillation_fingerprint, oscillation_opposition_key
from whetstone.live import LiveRoundRunner
from whetstone.scope import render_mvp_scope_notes_template, scope_contract_from_notes, write_scope_contract


HASH_RE = re.compile(r"([a-f0-9]{64})")


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


class PromptRecordingReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.prompts: list[str] = []

    def review(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [],
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


class ProcessFailureReviewerClient:
    def __init__(self, root: Path, *, recover: bool = False) -> None:
        self.root = root
        self.recover = recover
        self.calls = 0

    def review(self, prompt: str) -> dict:
        self.calls += 1
        if self.recover and self.calls > 1:
            return {
                "round_number": 1,
                "profile": "determinism",
                "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
                "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
                "feedback": [],
            }
        return {
            "round_number": 1,
            "profile": "determinism",
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [
                {
                    "feedback_id": "fb-context",
                    "issue_id": "iss_aaaaaaaaaaaaaaaa",
                    "issue_fingerprint": "a" * 64,
                    "issue_type": "process_error",
                    "affected_sections": ["context_loading"],
                    "baseline_severity": "blocker",
                    "authority_impact": "blocker",
                    "determinism_impact": "blocker",
                    "rubric_impact": "blocker",
                    "normalized_severity": "blocker",
                    "invariant_violated": "Required context files must be read before review output.",
                    "claim": "The review cannot be performed because the required context files were not read in this turn.",
                    "evidence": "No file-reading tool call was made before this response.",
                    "recommended_change": "Rerun the reviewer with read-only access to the listed context files.",
                    "in_scope": True,
                    "severity_rationale": "Without context, substantive review would be ungrounded.",
                    "oscillation_key": None,
                }
            ],
        }


class GoodEmptyReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def review(self, prompt: str) -> dict:
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [],
        }


class GoodIssueReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def review(self, prompt: str) -> dict:
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        phase = _line_value(prompt, "Phase:")
        oscillation_key = None
        if phase == "phase_2":
            oscillation_key = {
                "section_id": "hashing",
                "concern_type": "precision_gap",
                "direction": "clarify",
                "scope": "local",
                "fingerprint": oscillation_fingerprint("hashing", "precision_gap", "clarify", "local"),
                "opposition_key": oscillation_opposition_key("hashing", "precision_gap", "local"),
            }
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [
                {
                    "feedback_id": "fb-1",
                    "issue_id": "iss_aaaaaaaaaaaaaaaa",
                    "issue_fingerprint": "a" * 64,
                    "issue_type": "precision_gap",
                    "affected_sections": ["spec"],
                    "baseline_severity": "major",
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": "major",
                    "invariant_violated": None,
                    "claim": "The draft needs a deterministic clarification.",
                    "evidence": "Fixture.",
                    "recommended_change": "Clarify deterministic behavior.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": oscillation_key,
                }
            ],
        }


class InvalidTelemetryReviewerClient(GoodEmptyReviewerClient):
    def review(self, prompt: str) -> dict:
        artifact = super().review(prompt)
        self.last_telemetry = {
            "started_at": "2026-05-01T00:00:00+00:00",
            "finished_at": "2026-05-01T00:00:01+00:00",
            "duration_ms": "not-an-integer",
            "telemetry_source": "process_metadata",
        }
        return artifact


class AppliedDraftEditorClient:
    def __init__(self, draft_after_content: str, resolved_issue_ids: list[str] | None = None) -> None:
        self.draft_after_content = draft_after_content
        self.resolved_issue_ids = resolved_issue_ids or []

    def revise(self, prompt: str) -> dict:
        current_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        round_number = _editor_round_number(prompt)
        return {
            "round_number": round_number,
            "draft_before_hash": current_hash,
            "draft_after_hash": None,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": self.resolved_issue_ids,
            "unresolved_issue_ids": [],
            "draft_after_content": self.draft_after_content,
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
            "resolved_issue_ids": ["iss_aaaaaaaaaaaaaaaa"],
            "unresolved_issue_ids": [],
        }


class TimeoutEditorClient:
    def __init__(self) -> None:
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        raise TimeoutError("fixture editor timed out")


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
                "client_telemetry",
                "context",
                "decision_points.json",
                "editor_summary.json",
                "profile_used.yaml",
                "prompt_snapshot.json",
                "prompt_snapshots",
                "reviewer_feedback.json",
                "reviewer_working_notes.md",
                "telemetry_summary.json",
                "unresolved_issues.json",
            }
            self.assertEqual({path.name for path in round_dir.iterdir()}, expected)
            self.assertTrue(round_dir.joinpath("client_telemetry/reviewer-reviewer_feedback.json-attempt-1.json").exists())
            self.assertTrue(round_dir.joinpath("client_telemetry/editor-editor_summary.json-attempt-1.json").exists())
            summary = json.loads(round_dir.joinpath("telemetry_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["attempt_count"], 2)
            self.assertEqual(summary["missing_usage_attempts"], 2)
            self.assertTrue(round_dir.joinpath("context/draft_before.md").exists())
            self.assertTrue(round_dir.joinpath("context/reviewer_feedback.json").exists())
            snapshot = json.loads(round_dir.joinpath("prompt_snapshot.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["label"] == "draft_before" for item in snapshot["context_files"]))
            self.assertTrue(any(item["label"] == "reviewer_feedback" for item in snapshot["context_files"]))
            self.assertIn("Draft path: rounds/round-1/context/draft_before.md", snapshot["editor_prompt_text"])
            self.assertNotIn("\nDraft:\n# Spec", snapshot["editor_prompt_text"])
            unresolved = json.loads(round_dir.joinpath("unresolved_issues.json").read_text(encoding="utf-8"))
            self.assertTrue(unresolved["unresolved_issues"][0]["in_scope"])
            self.assertTrue(unresolved["unresolved_issues"][0]["blocking_acceptance"])

    def test_telemetry_persistence_failure_warns_without_failing_round(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            result = LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=InvalidTelemetryReviewerClient(root),
                editor_client=FakeEditorClient(root),
            ).run_round(round_number=1, profile="determinism")

            self.assertTrue(result.accepted)
            round_dir = root / "rounds" / "round-1"
            self.assertFalse(round_dir.joinpath("client_telemetry/reviewer-reviewer_feedback.json-attempt-1.json").exists())
            warnings = json.loads(
                round_dir.joinpath("client_telemetry/telemetry_warnings.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]["client_role"], "reviewer")
            self.assertIn("client telemetry persistence failed", warnings[0]["warning"])
            summary = json.loads(round_dir.joinpath("telemetry_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["attempt_count"], 0)
            self.assertEqual(len(summary["warnings"]), 1)

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
                workflow=config.workflow,
                editor=config.editor,
                reviewer=type(config.reviewer)(config.reviewer.name, config.reviewer.command, "", config.reviewer.model),
                review_max_rounds=config.review_max_rounds,
                review_mode=config.review_mode,
                review_profile_budgets=config.review_profile_budgets,
                review_budget_exhaustion_policy=config.review_budget_exhaustion_policy,
                convergence=config.convergence,
                convergence_profile_budgets=config.convergence_profile_budgets,
                decision_points=config.decision_points,
                timeouts=config.timeouts,
                contract_surface=config.contract_surface,
                scope_contract=config.scope_contract,
                reference_context_files=config.reference_context_files,
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

    def test_live_round_injects_scope_contract_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            write_scope_contract(
                root / "rounds" / "intake" / "scope_contract.json",
                scope_contract_from_notes(render_mvp_scope_notes_template(), approved=True),
            )
            reviewer = PromptRecordingReviewerClient(root)

            LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=FakeEditorClient(root),
            ).run_round(round_number=1, profile="determinism")

            snapshot = json.loads(root.joinpath("rounds/round-1/prompt_snapshot.json").read_text(encoding="utf-8"))
            labels = [item["label"] for item in snapshot["context_files"]]
            self.assertIn("scope_contract", labels)
            self.assertIn("scope_contract_hash", snapshot)
            self.assertIn("The scope contract is authoritative", reviewer.prompts[0])

    def test_live_round_injects_reference_context_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            hld = root / "docs" / "hld-architecture.md"
            hld.parent.mkdir()
            hld.write_text("# HLD\n\nArchitecture authority.\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                reference_context_files=(
                    ReferenceContextFileConfig(
                        label="parley_hld",
                        path=hld,
                        role="architecture_authority",
                        required=True,
                    ),
                ),
            )
            reviewer = PromptRecordingReviewerClient(root)

            LiveRoundRunner(
                root,
                config,
                reviewer_client=reviewer,
                editor_client=FakeEditorClient(root),
            ).run_round(round_number=1, profile="determinism")

            snapshot = json.loads(root.joinpath("rounds/round-1/prompt_snapshot.json").read_text(encoding="utf-8"))
            context_files = snapshot["context_files"]
            labels = [item["label"] for item in context_files]
            self.assertIn("reference:parley_hld", labels)
            self.assertEqual(snapshot["reference_context"]["files"][0]["role"], "architecture_authority")
            self.assertIn("Reference context [parley_hld] (architecture_authority)", reviewer.prompts[0])
            self.assertEqual(
                root.joinpath("rounds/round-1/context/reference_parley_hld.md").read_text(encoding="utf-8"),
                "# HLD\n\nArchitecture authority.\n",
            )

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
            self.assertEqual(error["failure_type"], "artifact_validation")
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

    def test_reviewer_process_failure_feedback_is_retried_not_sent_to_editor(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
            editor = RecordingEditorClient()
            reviewer = ProcessFailureReviewerClient(root)

            with self.assertRaises(ValueError):
                LiveRoundRunner(
                    root,
                    OrchestratorConfig.default(root),
                    reviewer_client=reviewer,
                    editor_client=editor,
                ).run_round(round_number=1, profile="determinism")

            self.assertEqual(reviewer.calls, 2)
            self.assertFalse(editor.called)
            self.assertFalse(root.joinpath("rounds/round-1/reviewer_feedback.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_invalid_attempt_1.json").exists())
            error = json.loads(root.joinpath("rounds/artifact_validation_error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["client_role"], "reviewer")
            self.assertEqual(error["failure_type"], "artifact_validation")
            self.assertIn("process/context-loading failure", error["attempts"][0]["validation_errors"][0])

    def test_reviewer_process_failure_feedback_can_recover_on_retry(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
            reviewer = ProcessFailureReviewerClient(root, recover=True)

            result = LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=FakeEditorClient(root),
            ).run_round(round_number=1, profile="determinism")

            self.assertTrue(result.accepted)
            self.assertEqual(reviewer.calls, 2)
            self.assertTrue(root.joinpath("rounds/round-1/reviewer_invalid_attempt_1.json").exists())
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())

    def test_clean_reviewer_feedback_skips_editor_client(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = "# Spec\n\nClean.\n"
            root.joinpath("spec.md").write_text(spec, encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            editor = RecordingEditorClient()

            result = LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodEmptyReviewerClient(root),
                editor_client=editor,
            ).run_round(round_number=1, profile="determinism", apply=True)

            self.assertTrue(result.accepted)
            self.assertFalse(editor.called)
            self.assertFalse(root.joinpath("rounds/round-1/context/reviewer_feedback.json").exists())
            self.assertFalse(root.joinpath("rounds/round-1/prompt_snapshots/editor-editor_summary.json-attempt-1.json").exists())
            editor_summary = json.loads(root.joinpath("rounds/round-1/editor_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(editor_summary["draft_before_hash"], draft_hash(spec))
            self.assertEqual(editor_summary["draft_after_hash"], draft_hash(spec))
            self.assertEqual(editor_summary["draft_after_content"], spec)
            summary = json.loads(root.joinpath("rounds/round-1/telemetry_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["attempt_count"], 1)
            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), spec)

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
            self.assertEqual(error["failure_type"], "artifact_validation")
            self.assertEqual(error["client_role"], "editor")
            self.assertEqual(error["last_valid_draft_path"], "rounds/round-1/draft_after.md")
            self.assertTrue(
                root.joinpath("rounds/round-1/prompt_snapshots/editor-editor_summary.json-attempt-2.json").exists()
            )
            convergence = json.loads(root.joinpath("rounds/convergence_failure_report.json").read_text(encoding="utf-8"))
            self.assertEqual(convergence["terminal_state"], "HALTED_ARTIFACT_INVALID")
            self.assertEqual(convergence["final_draft_path"], "rounds/round-1/draft_after.md")

    def test_editor_draft_with_control_character_rejects_before_spec_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = "# Spec\n\n## Hashing\n\nBefore.\n"
            root.joinpath("spec.md").write_text(before, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "editor_summary.json validation failed after retry"):
                LiveRoundRunner(
                    root,
                    OrchestratorConfig.default(root),
                    reviewer_client=GoodIssueReviewerClient(root),
                    editor_client=AppliedDraftEditorClient("# Spec\n\nBad\x1a text.\n"),
                ).run_round(round_number=1, profile="determinism", apply=True)

            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), before)
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_2.json").exists())
            error = json.loads(root.joinpath("rounds/artifact_validation_error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["terminal_state"], "HALTED_ARTIFACT_INVALID")
            self.assertEqual(error["client_role"], "editor")
            self.assertIn("FORBIDDEN_CONTROL_CHARACTER", error["attempts"][0]["validation_errors"][0])

    def test_editor_validation_retry_can_recover_after_valid_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            editor = FlakyEditorClient(root)

            result = LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=editor,
            ).run_round(round_number=1, profile="determinism")

            self.assertTrue(result.accepted)
            self.assertEqual(editor.calls, 2)
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())

    def test_editor_timeout_does_not_retry_same_prompt(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            editor = TimeoutEditorClient()

            with self.assertRaises(ValueError):
                LiveRoundRunner(
                    root,
                    OrchestratorConfig.default(root),
                    reviewer_client=GoodIssueReviewerClient(root),
                    editor_client=editor,
                ).run_round(round_number=1, profile="determinism", apply=True)

            self.assertEqual(editor.calls, 1)
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            self.assertFalse(root.joinpath("rounds/round-1/editor_invalid_attempt_2.json").exists())
            self.assertFalse(
                root.joinpath("rounds/round-1/prompt_snapshots/editor-editor_summary.json-attempt-2.json").exists()
            )
            error = json.loads(root.joinpath("rounds/artifact_validation_error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["terminal_state"], "HALTED_CLIENT_TIMEOUT")
            self.assertEqual(error["failure_type"], "client_timeout")
            self.assertEqual(error["retry_exhausted"], True)
            self.assertEqual(len(error["attempts"]), 1)
            technical = json.loads(root.joinpath("rounds/technical_failure_report.json").read_text(encoding="utf-8"))
            self.assertEqual(technical["terminal_state"], "HALTED_CLIENT_TIMEOUT")

    def test_empty_editor_draft_is_rejected_before_mutating_spec(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = "# Spec\n\n" + ("Required behavior.\n" * 100)
            root.joinpath("spec.md").write_text(spec, encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                LiveRoundRunner(
                    root,
                    OrchestratorConfig.default(root),
                    reviewer_client=GoodIssueReviewerClient(root),
                    editor_client=AppliedDraftEditorClient(""),
                ).run_round(round_number=1, profile="structural_integrity", apply=True)

            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), spec)
            error = json.loads(root.joinpath("rounds/artifact_validation_error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["terminal_state"], "HALTED_ARTIFACT_INVALID")
            self.assertIn("replace a non-empty draft with empty content", error["attempts"][-1]["validation_errors"][0])

    def test_blocked_editor_placeholder_is_rejected_before_mutating_spec(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = "# Spec\n\nRequired behavior.\n"
            root.joinpath("spec.md").write_text(spec, encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                LiveRoundRunner(
                    root,
                    OrchestratorConfig.default(root),
                    reviewer_client=GoodIssueReviewerClient(root),
                    editor_client=AppliedDraftEditorClient("[Whetstone editor blocked] Cannot read context files."),
                ).run_round(round_number=1, profile="structural_integrity", apply=True)

            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), spec)
            error = json.loads(root.joinpath("rounds/artifact_validation_error.json").read_text(encoding="utf-8"))
            self.assertIn("blocked/error placeholder", error["attempts"][-1]["validation_errors"][0])

    def test_accepted_mutating_phase1_round_stamps_version_before_persisted_hash(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = "# Spec 0.17\n\nDraft.\n"
            after = "# Spec 0.17\n\nDraft.\n\nClarified.\n"
            root.joinpath("spec.md").write_text(before, encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            result = LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=AppliedDraftEditorClient(after, resolved_issue_ids=["iss_aaaaaaaaaaaaaaaa"]),
            ).run_round(round_number=1, profile="determinism", phase="phase_1", apply=True)

            stamped = root.joinpath("spec.md").read_text(encoding="utf-8")
            self.assertTrue(result.accepted)
            self.assertTrue(result.spec_mutated)
            self.assertIn("# Spec 0.18", stamped)
            self.assertEqual(result.draft_after_hash, draft_hash(stamped))
            self.assertEqual(root.joinpath("rounds/round-1/draft_after.md").read_text(encoding="utf-8"), stamped)
            editor_summary = json.loads(root.joinpath("rounds/round-1/editor_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(editor_summary["draft_after_hash"], draft_hash(stamped))
            self.assertIn("Version stamp: round 1", root.joinpath("spec.history.md").read_text(encoding="utf-8"))

    def test_accepted_mutating_phase2_round_stamps_version_before_persisted_hash(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = "# Spec 1.0\n\n## Hashing\n\nDraft.\n"
            after = "# Spec 1.0\n\n## Hashing\n\nDraft.\n\nClarified.\n"
            root.joinpath("spec.md").write_text(before, encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            result = LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=GoodIssueReviewerClient(root),
                editor_client=AppliedDraftEditorClient(after, resolved_issue_ids=["iss_aaaaaaaaaaaaaaaa"]),
            ).run_round(round_number=1, profile="convergence_strict_check", phase="phase_2", apply=True)

            stamped = root.joinpath("spec.md").read_text(encoding="utf-8")
            self.assertTrue(result.accepted)
            self.assertIn("# Spec 1.1", stamped)
            self.assertEqual(result.draft_after_hash, draft_hash(stamped))

    def test_phase2_adversarial_prompt_does_not_include_declaration_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec 1.0\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            root.joinpath("convergence_declaration.md").write_text(
                "# Convergence Declaration\n\n- declaration_status: rejected\n",
                encoding="utf-8",
            )
            reviewer = PromptRecordingReviewerClient(root)

            LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=AppliedDraftEditorClient("# Spec 1.0\n\n## Hashing\n\nDraft.\n"),
            ).run_round(round_number=1, profile="adversarial", phase="phase_2", apply=True)

            self.assertIn("Declaration artifact:", reviewer.prompts[0])
            self.assertIn("(not provided for this review)", reviewer.prompts[0])
            self.assertNotIn("declaration_status: rejected", reviewer.prompts[0])

    def test_phase2_convergence_prompt_includes_declaration_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec 1.0\n\n## Hashing\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            root.joinpath("convergence_declaration.md").write_text(
                "# Convergence Declaration\n\n- declaration_status: rejected\n",
                encoding="utf-8",
            )
            reviewer = PromptRecordingReviewerClient(root)

            LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=AppliedDraftEditorClient("# Spec 1.0\n\n## Hashing\n\nDraft.\n"),
            ).run_round(round_number=1, profile="convergence_strict_check", phase="phase_2", apply=True)

            self.assertIn("Declaration artifact:", reviewer.prompts[0])
            self.assertIn("Declaration artifact path:", reviewer.prompts[0])
            declaration_context = root.joinpath("rounds/round-1/context/convergence_declaration.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("declaration_status: rejected", declaration_context)

def _hash_line(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip().rstrip(".")
            if HASH_RE.fullmatch(value):
                return value
    raise AssertionError(f"missing or invalid hash line {prefix}")


def _line_value(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise AssertionError(f"missing prompt line {prefix}")


def _editor_round_number(prompt: str) -> int:
    match = re.search(r"The top-level object MUST set round_number to ([0-9]+)\.", prompt)
    if match is None:
        raise AssertionError("missing editor round number")
    return int(match.group(1))


if __name__ == "__main__":
    unittest.main()
