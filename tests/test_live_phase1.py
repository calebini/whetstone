from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import OrchestratorConfig, load_config
from whetstone.hashing import draft_hash
from whetstone.live import LiveRoundRunner
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.scheduler import focused_phase_1_scheduler
from tests.test_live import TimeoutEditorClient


HASH_RE = re.compile(r"([a-f0-9]{64})")


class ScriptedReviewerClient:
    def __init__(self, root: Path, severities: list[str | None]) -> None:
        self.root = root
        self.severities = severities
        self.calls = 0
        self.profiles: list[str] = []

    def review(self, prompt: str) -> dict:
        self.calls += 1
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        self.profiles.append(profile)
        severity = self.severities[self.calls - 1] if self.calls - 1 < len(self.severities) else None
        feedback = []
        if severity is not None:
            feedback.append(
                {
                    "feedback_id": f"fb-{self.calls}",
                    "issue_id": f"iss_{self.calls:016x}",
                    "issue_fingerprint": f"{self.calls:x}" * 64,
                    "issue_type": "undefined_behavior",
                    "affected_sections": ["Spec"],
                    "baseline_severity": severity,
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": severity,
                    "invariant_violated": "fixture invariant",
                    "claim": f"Fixture {severity}.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Fix it.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            )
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": feedback,
        }


class ContractSurfaceReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def review(self, prompt: str) -> dict:
        self.calls += 1
        profile = _line_value(prompt, "Review profile:")
        feedback = []
        if self.calls <= 4:
            feedback = [
                {
                    "feedback_id": f"fb-{self.calls}",
                    "issue_id": f"iss_{self.calls:016x}",
                    "issue_fingerprint": f"{self.calls:x}" * 64,
                    "issue_type": "schema_validation_failure_mapping_gap",
                    "affected_sections": [f"Contract Section {self.calls}"],
                    "baseline_severity": "major",
                    "authority_impact": None,
                    "determinism_impact": "major",
                    "rubric_impact": None,
                    "normalized_severity": "major",
                    "invariant_violated": "fixture invariant",
                    "claim": "The schema validation failure report mapping is incomplete.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Define schema fields, validation ordering, failure mapping, and report artifact behavior.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            ]
        return {
            "round_number": self.calls,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": feedback,
        }


class AlwaysMajorReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def review(self, prompt: str) -> dict:
        self.calls += 1
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [
                {
                    "feedback_id": f"fb-always-{self.calls}",
                    "issue_id": f"iss_{self.calls:016x}",
                    "issue_fingerprint": f"{self.calls:x}" * 64,
                    "issue_type": "undefined_behavior",
                    "affected_sections": ["Spec"],
                    "baseline_severity": "major",
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": "major",
                    "invariant_violated": "fixture invariant",
                    "claim": "Fixture major.",
                    "evidence": "Fixture evidence.",
                    "recommended_change": "Fix it.",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            ],
        }


class ResolvingEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt, self.root)
        issue_ids = _issue_ids_from_prompt(prompt, self.root)
        round_number = _editor_round_number(prompt)
        return {
            "round_number": round_number,
            "draft_before_hash": before_hash,
            "draft_after_hash": explicit_after_hash,
            "accepted_feedback_ids": [f"fb-{self.calls}"] if issue_ids else [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": issue_ids,
            "unresolved_issue_ids": [],
            **({"draft_after_content": draft_after_content} if explicit_after_hash is None else {}),
        }


class BlockingEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt, self.root)
        issue_ids = _issue_ids_from_prompt(prompt, self.root)
        round_number = _editor_round_number(prompt)
        return {
            "round_number": round_number,
            "draft_before_hash": before_hash,
            "draft_after_hash": explicit_after_hash,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": issue_ids,
            **({"draft_after_content": draft_after_content} if explicit_after_hash is None else {}),
        }


class BadReviewerClient:
    def review(self, prompt: str) -> dict:
        return {
            "round_number": 999,
            "profile": "wrong",
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": "b" * 64,
            "feedback": [],
        }


class CleanReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def review(self, prompt: str) -> dict:
        self.calls += 1
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [],
        }


class LivePhase1RunnerTests(unittest.TestCase):
    def test_phase1_runner_completes_all_profiles_and_updates_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            root.joinpath("rounds").mkdir()
            root.joinpath("rounds/artifact_validation_error.json").write_text("stale\n", encoding="utf-8")
            reviewer = ScriptedReviewerClient(root, [None, None, None])
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=ResolvingMutatingEditorClient(root),
            ).run(overwrite=True)

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(result.ready_for_phase_2)
            self.assertEqual(reviewer.profiles, ["structural_integrity", "determinism", "operability"])
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])
            self.assertEqual(
                state["review_profile_budgets"],
                {"determinism": 10, "operability": 10, "structural_integrity": 10},
            )
            self.assertEqual(state["configured_review_profile_budgets"], {})
            self.assertEqual(
                state["effective_run_config"]["review_profile_budgets"],
                {"determinism": 10, "operability": 10, "structural_integrity": 10},
            )
            self.assertEqual(
                state["effective_run_config"]["convergence_profile_budgets"],
                {"adversarial": 10, "convergence_strict_check": 10},
            )
            self.assertEqual(state["effective_run_config"]["decision_points"]["mode"], "end_of_cycle")
            self.assertEqual(state["effective_run_config"]["timeouts"]["editor_seconds"], 900)
            self.assertEqual(state["telemetry_totals"]["round_count"], 3)
            self.assertEqual(state["telemetry_totals"]["attempt_count"], 3)
            self.assertEqual(state["telemetry_totals"]["missing_usage_attempts"], 3)

    def test_blocker_profile_repeats_before_advancing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            reviewer = ScriptedReviewerClient(root, ["blocker", None, None, None])
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=ResolvingMutatingEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertEqual(reviewer.profiles, ["structural_integrity", "structural_integrity", "determinism", "operability"])

    def test_vertical_review_mode_reviews_all_profiles_before_one_editor_call(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), review_mode="vertical", profile_budget=2)
            reviewer = ScriptedReviewerClient(root, ["major", "major", "major", None, None, None])
            editor = ResolvingMutatingEditorClient(root)

            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=reviewer,
                editor_client=editor,
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertEqual(
                reviewer.profiles,
                [
                    "structural_integrity",
                    "determinism",
                    "operability",
                    "structural_integrity",
                    "determinism",
                    "operability",
                ],
            )
            self.assertEqual(editor.calls, 1)
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["review_mode"], "vertical")
            self.assertEqual(state["current_round"], 7)
            self.assertEqual(state["review_round_budget"], 8)
            self.assertEqual(state["effective_run_config"]["review_mode"], "vertical")
            merged_feedback = _read_json(root / "rounds" / "round-4" / "reviewer_feedback.json")
            self.assertEqual(merged_feedback["profile"], "vertical")
            self.assertEqual(len(merged_feedback["feedback"]), 3)
            review_profile = _read_json(root / "rounds" / "round-1" / "profile_used.yaml")
            editor_profile = _read_json(root / "rounds" / "round-4" / "profile_used.yaml")
            self.assertEqual(review_profile["round_kind"], "review_only")
            self.assertEqual(editor_profile["round_kind"], "consolidated_editor")

    def test_vertical_consolidated_editor_timeout_terminalizes_state_and_summaries(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), review_mode="vertical", profile_budget=1)
            reviewer = ScriptedReviewerClient(root, ["major", "major", "major"])

            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=reviewer,
                editor_client=TimeoutEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "HALTED_CLIENT_TIMEOUT")
            self.assertFalse(result.ready_for_phase_2)
            self.assertEqual(result.round_number, 4)
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "HALTED_CLIENT_TIMEOUT")
            self.assertEqual(state["current_round"], 4)
            self.assertEqual(state["active_profile"], "vertical")
            self.assertEqual(state["current_draft_hash"], state["seen_draft_hashes"][-1])
            technical = _read_json(root / "rounds" / "technical_failure_report.json")
            self.assertEqual(technical["terminal_state"], "HALTED_CLIENT_TIMEOUT")
            self.assertEqual(len(technical["unresolved_major_issues"]), 3)
            self.assertTrue(root.joinpath("rounds/operator_decision_checkpoint_summary.json").exists())
            error = _read_json(root / "rounds" / "artifact_validation_error.json")
            self.assertEqual(error["profile"], "vertical")
            self.assertEqual(error["client_role"], "editor")

    def test_vertical_closeout_check_refuses_when_reviewer_finds_major(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), review_mode="vertical", profile_budget=1)
            reviewer = ScriptedReviewerClient(root, [None, None, "minor", "major", None, None])

            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=reviewer,
                editor_client=ResolvingMutatingEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "TARGET_NOT_REACHED")
            self.assertFalse(result.ready_for_phase_2)
            report = _read_json(root / "rounds" / "technical_failure_report.json")
            self.assertEqual(report["current_draft_status"], "accepted_unverified_profiles")
            self.assertFalse(report["ready_for_phase_2"])
            self.assertEqual(report["last_accepted_draft_hash"], report["last_draft_hash"])
            self.assertIn("structural_integrity", report["profile_status"]["unverified_profiles"])

    def test_vertical_closeout_check_stabilizes_accepted_minor_only_editor_change(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), review_mode="vertical", profile_budget=1)
            reviewer = ScriptedReviewerClient(root, [None, None, "minor", None, None, None])

            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=reviewer,
                editor_client=ResolvingMutatingEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(result.ready_for_phase_2)
            self.assertEqual(result.round_number, 7)
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])

    def test_focused_phase1_runs_one_profile_with_normal_state_artifacts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            reviewer = ScriptedReviewerClient(root, ["major", None])
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=ResolvingMutatingEditorClient(root),
                scheduler_factory=lambda _budgets: focused_phase_1_scheduler("structural_integrity", round_budget=3),
                state_review_profile_budgets={"structural_integrity": 3},
                run_mode="focused_phase_1",
                completion_terminal_state="FOCUSED_PROFILE_STABLE",
                completion_ready_for_phase_2=False,
            ).run()

            self.assertEqual(result.terminal_state, "FOCUSED_PROFILE_STABLE")
            self.assertFalse(result.ready_for_phase_2)
            self.assertEqual(reviewer.profiles, ["structural_integrity", "structural_integrity"])
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "FOCUSED_PROFILE_STABLE")
            self.assertEqual(state["run_mode"], "focused_phase_1")
            self.assertFalse(state["ready_for_phase_2"])
            self.assertEqual(state["review_profile_budgets"], {"structural_integrity": 3})
            self.assertEqual(state["review_round_budget"], 3)
            self.assertTrue(root.joinpath("rounds/decision_register.json").exists())
            self.assertTrue(root.joinpath("rounds/decision_summary.md").exists())

    def test_editor_resolution_requires_reviewer_verification_before_profile_advances(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            reviewer = ScriptedReviewerClient(root, ["blocker", None, None, None])
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=ResolvingMutatingEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertEqual(reviewer.profiles, ["structural_integrity", "structural_integrity", "determinism", "operability"])

    def test_max_rounds_emits_technical_failure_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), review_max_rounds=1, profile_budget=1)
            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=AlwaysMajorReviewerClient(root),
                editor_client=BlockingEditorClient(root),
                draft_after_provider=lambda round_number, profile, draft: draft + "\nChanged.\n",
            ).run()

            self.assertEqual(result.terminal_state, "TARGET_NOT_REACHED")
            self.assertTrue((root / "rounds" / "technical_failure_report.json").exists())

    def test_contract_surface_report_written_after_repeated_serious_contract_findings(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=ContractSurfaceReviewerClient(root),
                editor_client=ResolvingMutatingEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            report = _read_json(root / "rounds" / "contract_surface_report.json")
            self.assertTrue(report["detected"])
            self.assertEqual(report["type"], "EXPANDING_CONTRACT_SURFACE")
            self.assertEqual(report["profile"], "structural_integrity")
            self.assertEqual(report["terminal_effect"], "none")
            self.assertEqual(report["action_taken"], "injected_into_next_round_context")
            self.assertEqual(report["next_round_number"], report["round_number"] + 1)
            self.assertFalse(report["requires_operator_action"])
            self.assertFalse(report["synthesis_pass_executed"])
            self.assertEqual(report["lifecycle_status"], "resolved_by_later_rounds")
            self.assertGreater(report["resolution_round_number"], report["round_number"])
            self.assertIn("schema/data-contract", report["contract_families"])
            self.assertIn("failure-semantics", report["contract_families"])
            self.assertTrue((root / "rounds" / "contract_surface_report.md").exists())

    def test_soft_budget_exhaustion_completes_sweep_with_residuals(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), budget_exhaustion_policy="soft", profile_budget=1)
            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=AlwaysMajorReviewerClient(root),
                editor_client=BlockingEditorClient(root),
                draft_after_provider=lambda round_number, profile, draft: draft + f"\nChanged {round_number}.\n",
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS")
            self.assertFalse(result.ready_for_phase_2)
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS")
            self.assertFalse(state["ready_for_phase_2"])
            report = _read_json(root / "rounds" / "technical_failure_report.json")
            self.assertEqual(report["terminal_state"], "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS")
            self.assertEqual(report["current_draft_status"], "not_accepted")
            self.assertFalse(report["ready_for_phase_2"])
            self.assertEqual(
                report["profile_status"]["exhausted_profiles"],
                ["structural_integrity", "determinism", "operability"],
            )

    def test_horizontal_closeout_stabilizes_accepted_but_unverified_draft(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), budget_exhaustion_policy="soft", profile_budget=1)
            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=ScriptedReviewerClient(root, ["major", None, None]),
                editor_client=ResolvingEditorClient(root),
                draft_after_provider=lambda round_number, profile, draft: draft + f"\nResolved {round_number}.\n",
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(result.ready_for_phase_2)
            self.assertEqual(result.round_number, 6)
            self.assertFalse((root / "rounds" / "technical_failure_report.json").exists())
            profile_used = _read_json(root / "rounds" / "round-4" / "profile_used.yaml")
            self.assertEqual(profile_used["profile"], "structural_integrity")
            self.assertEqual(profile_used["round_kind"], "review_only")
            final_profile_used = _read_json(root / "rounds" / "round-6" / "profile_used.yaml")
            self.assertEqual(final_profile_used["profile"], "operability")
            self.assertEqual(final_profile_used["round_kind"], "review_only")
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])

    def test_clean_final_budget_round_is_not_reported_as_residual_for_version_only_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(
                Path(tmp),
                budget_exhaustion_policy="soft",
                profile_budget=2,
                spec="# Spec\n\nStatus: Draft v1.00\n\nDraft.\n",
            )
            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=ScriptedReviewerClient(root, [None, "major", None, None]),
                editor_client=VersionOnlyOnCleanEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertTrue(state["ready_for_phase_2"])

    def test_soft_budget_no_op_serious_findings_reports_technical_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), budget_exhaustion_policy="soft", profile_budget=10)
            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=ScriptedReviewerClient(root, ["blocker", "blocker", "blocker"]),
                editor_client=BlockingEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "TARGET_NOT_REACHED")
            self.assertFalse((root / "rounds" / "oscillation_report.json").exists())
            report = _read_json(root / "rounds" / "technical_failure_report.json")
            self.assertIn("unchanged draft", report["exit_reason"])

    def test_no_op_editor_with_blocking_findings_emits_technical_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=ScriptedReviewerClient(root, ["blocker"]),
                editor_client=BlockingEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "TARGET_NOT_REACHED")
            self.assertFalse((root / "rounds" / "oscillation_report.json").exists())
            report = _read_json(root / "rounds" / "technical_failure_report.json")
            self.assertEqual(report["terminal_state"], "TARGET_NOT_REACHED")
            self.assertIn("unchanged draft", report["exit_reason"])
            self.assertTrue(root.joinpath("rounds/decision_register.json").exists())

    def test_artifact_validation_failure_stops_loop_without_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            before = (root / "spec.md").read_text(encoding="utf-8")
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=BadReviewerClient(),
                editor_client=ResolvingEditorClient(root),
            ).run()

            self.assertEqual(result.terminal_state, "HALTED_ARTIFACT_INVALID")
            self.assertEqual((root / "spec.md").read_text(encoding="utf-8"), before)
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "HALTED_ARTIFACT_INVALID")

    def test_intervention_mode_pauses_on_decision_point(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), decision_mode="intervention")
            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=ScriptedReviewerClient(root, ["major"]),
                editor_client=ResolvingEditorClient(root),
                draft_after_provider=lambda round_number, profile, draft: draft + "\nAdapter MUST retry.\n",
            ).run()

            self.assertEqual(result.terminal_state, "PAUSED_DECISION")
            self.assertTrue((root / "rounds" / "decision_intervention_request.json").exists())
            self.assertTrue((root / "rounds" / "decision_register.json").exists())
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "PAUSED_DECISION")

    def test_first_phase2_round_promotes_accepted_phase1_version(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), spec="# Whetstone 0.17\n\nDraft.\n")
            phase1_reviewer = ScriptedReviewerClient(root, [None, None, None])
            phase1_result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=phase1_reviewer,
                editor_client=ResolvingEditorClient(root),
            ).run()
            self.assertEqual(phase1_result.terminal_state, "PHASE_1_STABLE")

            phase2_reviewer = CleanReviewerClient(root)
            LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=phase2_reviewer,
                editor_client=ResolvingEditorClient(root),
            ).run_round(round_number=4, profile="convergence_strict_check", phase="phase_2")

            self.assertIn("# Whetstone 1.0", root.joinpath("spec.md").read_text(encoding="utf-8"))
            self.assertIn("# Whetstone 1.0", root.joinpath("rounds/round-4/draft_before.md").read_text(encoding="utf-8"))
            history = root.joinpath("spec.history.md").read_text(encoding="utf-8")
            self.assertIn("Phase 2 version promotion: `0.17` -> `1.0`", history)


class BlockingThenResolvingEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt, self.root)
        issue_ids = _issue_ids_from_prompt(prompt, self.root)
        unresolved = issue_ids if self.calls == 1 else []
        resolved = [] if self.calls == 1 else issue_ids
        round_number = _editor_round_number(prompt)
        return {
            "round_number": round_number,
            "draft_before_hash": before_hash,
            "draft_after_hash": explicit_after_hash,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": resolved,
            "unresolved_issue_ids": unresolved,
            **({"draft_after_content": draft_after_content} if explicit_after_hash is None else {}),
        }


class ResolvingMutatingEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt, self.root)
        issue_ids = _issue_ids_from_prompt(prompt, self.root)
        if issue_ids:
            draft_after_content += "\nVerified fix.\n"
        round_number = _editor_round_number(prompt)
        return {
            "round_number": round_number,
            "draft_before_hash": before_hash,
            "draft_after_hash": explicit_after_hash,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [f"fb-{round_number}"] if issue_ids else [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": issue_ids,
            "unresolved_issue_ids": [],
            **({"draft_after_content": draft_after_content} if explicit_after_hash is None else {}),
        }


class VersionOnlyOnCleanEditorClient:
    def __init__(self, root: Path) -> None:
        self.root = root

    def revise(self, prompt: str) -> dict:
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt, self.root)
        issue_ids = _issue_ids_from_prompt(prompt, self.root)
        if issue_ids:
            draft_after_content += "\nResolved issue.\n"
        else:
            draft_after_content = draft_after_content.replace("Status: Draft v1.00", "Status: Draft v1.01")
        round_number = _editor_round_number(prompt)
        return {
            "round_number": round_number,
            "draft_before_hash": before_hash,
            "draft_after_hash": explicit_after_hash,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [f"fb-{round_number}"] if issue_ids else [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": issue_ids,
            "unresolved_issue_ids": [],
            **({"draft_after_content": draft_after_content} if explicit_after_hash is None else {}),
        }


def _seed_root(
    root: Path,
    *,
    review_max_rounds: int | None = None,
    budget_exhaustion_policy: str | None = None,
    profile_budget: int | None = None,
    review_mode: str | None = None,
    decision_mode: str | None = None,
    spec: str = "# Spec\n\nDraft.\n",
) -> Path:
    root.joinpath("spec.md").write_text(spec, encoding="utf-8")
    root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
    if (
        review_max_rounds is not None
        or budget_exhaustion_policy is not None
        or profile_budget is not None
        or review_mode is not None
        or decision_mode is not None
    ):
        root.joinpath("orchestrator_config.yaml").write_text(
            f"""
spec_path: spec.md
history_path: spec.history.md
rounds_dir: rounds
declaration_path: convergence_declaration.md
clients:
  editor:
    name: fixture-editor
    command: fixture
    version: 0.0.0
    model: fixture
  reviewer:
    name: fixture-reviewer
    command: fixture
    version: 0.0.0
    model: fixture
review:
  max_rounds: {review_max_rounds or 12}
  mode: {review_mode or "horizontal"}
  budget_exhaustion_policy: {budget_exhaustion_policy or "hard"}
  profile_budgets:
    structural_integrity: {profile_budget or 10}
    determinism: {profile_budget or 10}
    operability: {profile_budget or 10}
decision_points:
  enabled: true
  mode: {decision_mode or "end_of_cycle"}
  intervention_thresholds:
    severities: [major]
""".lstrip(),
            encoding="utf-8",
        )
    return root


def _line_value(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise AssertionError(f"missing prompt line {prefix}")


def _draft_from_prompt(prompt: str, root: Path) -> str:
    path_match = re.search(r"Draft path: ([^\n]+)", prompt)
    if path_match:
        return (root / path_match.group(1)).read_text(encoding="utf-8")
    marker = "\nDraft:\n"
    if marker not in prompt:
        raise AssertionError("missing Draft block")
    return prompt.split(marker, 1)[1]


def _issue_ids_from_prompt(prompt: str, root: Path) -> list[str]:
    path_match = re.search(r"Reviewer feedback JSON path: ([^\n]+)", prompt)
    if path_match:
        feedback = (root / path_match.group(1)).read_text(encoding="utf-8")
        return re.findall(r'"issue_id": "(iss_[a-f0-9]{16})"', feedback)
    return re.findall(r'"issue_id": "(iss_[a-f0-9]{16})"', prompt)


def _hash_line(prompt: str, prefix: str) -> str:
    value = _line_value(prompt, prefix).rstrip(".")
    if not HASH_RE.fullmatch(value):
        raise AssertionError(f"invalid hash line for {prefix}: {value}")
    return value


def _optional_hash_line(prompt: str, prefix: str) -> str | None:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip().rstrip(".")
            if not HASH_RE.fullmatch(value):
                raise AssertionError(f"invalid hash line for {prefix}: {value}")
            return value
    return None


def _editor_round_number(prompt: str) -> int:
    match = re.search(r"The top-level object MUST set round_number to ([0-9]+)\.", prompt)
    if match is None:
        raise AssertionError("missing editor round number")
    return int(match.group(1))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
