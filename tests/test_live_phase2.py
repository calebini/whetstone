from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import OrchestratorConfig, load_config
from whetstone.hashing import draft_hash
from whetstone.live_phase2 import LivePhase2Runner


HASH_RE = re.compile(r"([a-f0-9]{64})")


class CleanPhase2ReviewerClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.profiles: list[str] = []

    def review(self, prompt: str) -> dict:
        profile = _line_value(prompt, "Review profile:")
        round_number = int(_line_value(prompt, "- round_number:"))
        self.profiles.append(profile)
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": [],
        }


class ScriptedPhase2ReviewerClient:
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
                    "affected_sections": ["whetstone-1-0-rules"],
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
                    "oscillation_key": {
                        "section_id": "whetstone-1-0-rules",
                        "concern_type": "clarity_gap",
                        "direction": "clarify",
                        "scope": "local",
                    },
                    "oscillation_fingerprint": "a" * 64,
                    "oscillation_opposition_key": "b" * 64,
                }
            )
        return {
            "round_number": round_number,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": feedback,
        }


class EchoEditorClient:
    def revise(self, prompt: str) -> dict:
        return {
            "round_number": _editor_round_number(prompt),
            "draft_before_hash": _hash_line(prompt, "The draft_before_hash MUST be "),
            "draft_after_hash": None,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [],
            "draft_after_content": _draft_from_prompt(prompt),
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


class ChangingEditorClient:
    def __init__(self) -> None:
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        draft = _draft_from_prompt(prompt)
        if self.calls == 2:
            draft = draft + "\nRound 5 clarification.\n"
        return {
            "round_number": _editor_round_number(prompt),
            "draft_before_hash": _hash_line(prompt, "The draft_before_hash MUST be "),
            "draft_after_hash": None,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [],
            "draft_after_content": draft,
        }


class ResolvingPhase2EditorClient:
    def revise(self, prompt: str) -> dict:
        draft = _draft_from_prompt(prompt)
        issue_ids = re.findall(r'"issue_id": "(iss_[a-f0-9]{16})"', prompt)
        if issue_ids:
            draft += "\nVerified Phase 2 fix.\n"
        return {
            "round_number": _editor_round_number(prompt),
            "draft_before_hash": _hash_line(prompt, "The draft_before_hash MUST be "),
            "draft_after_hash": None,
            "accepted_feedback_ids": [],
            "modified_feedback_ids": ["fb-1"] if issue_ids else [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": issue_ids,
            "unresolved_issue_ids": [],
            "draft_after_content": draft,
        }


class DecisionPointEditorClient:
    def __init__(self) -> None:
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        draft = _draft_from_prompt(prompt)
        if self.calls == 2:
            draft = draft + "\n## Canonicalizer Summary Policy\n\nThe Orchestrator MUST preserve attempt-scoped summaries.\n"
        return {
            "round_number": _editor_round_number(prompt),
            "draft_before_hash": _hash_line(prompt, "The draft_before_hash MUST be "),
            "draft_after_hash": None,
            "accepted_feedback_ids": ["fb-1"],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [],
            "draft_after_content": draft,
        }


class LivePhase2RunnerTests(unittest.TestCase):
    def test_phase2_runner_promotes_then_converges_after_declaration_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_phase1_stable(Path(tmp))
            reviewer = CleanPhase2ReviewerClient(root)

            result = LivePhase2Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=EchoEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "CONVERGED")
            self.assertEqual(result.round_number, 6)
            self.assertEqual(reviewer.profiles, ["convergence_strict_check", "adversarial", "convergence_strict_check"])
            self.assertIn("# Whetstone 1.0", root.joinpath("spec.md").read_text(encoding="utf-8"))
            declaration = root.joinpath("convergence_declaration.md").read_text(encoding="utf-8")
            self.assertIn("reviewer_final_status: accepted", declaration)
            self.assertIn("declaration_status: accepted", declaration)
            self.assertIn("rubric_profile: standard-v1", declaration)
            self.assertTrue(root.joinpath("rounds/rubric_manifest.json").exists())
            self.assertTrue(root.joinpath("rounds/round-4/rubric_gaps.json").exists())
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["phase"], "phase_2")
            self.assertEqual(state["terminal_state"], "CONVERGED")
            self.assertEqual(state["current_absolute_round"], 6)
            self.assertEqual(state["current_phase_round"], 3)
            self.assertEqual(state["phase_1_rounds_completed"], 3)
            self.assertEqual(state["phase_2_rounds_completed"], 3)
            self.assertEqual(state["total_absolute_round_budget"], 20)
            self.assertEqual(state["rubric_manifest_path"], "rounds/rubric_manifest.json")
            self.assertEqual(state["telemetry_totals"]["round_count"], 3)
            self.assertEqual(state["telemetry_totals"]["attempt_count"], 6)
            self.assertEqual(state["telemetry_totals"]["missing_usage_attempts"], 6)

    def test_phase2_editor_resolution_requires_clean_reviewer_pass_before_convergence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_phase1_stable(Path(tmp), convergence_max_rounds=6)
            reviewer = ScriptedPhase2ReviewerClient(root, ["major", None, None, None])

            result = LivePhase2Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=reviewer,
                editor_client=ResolvingPhase2EditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "CONVERGED")
            self.assertEqual(
                reviewer.profiles,
                [
                    "convergence_strict_check",
                    "convergence_strict_check",
                    "adversarial",
                    "convergence_strict_check",
                ],
            )

    def test_phase2_runner_requires_stable_phase1_handoff(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Whetstone 0.17\n\nDraft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                LivePhase2Runner(
                    root,
                    OrchestratorConfig.default(root),
                    reviewer_client=CleanPhase2ReviewerClient(root),
                    editor_client=EchoEditorClient(),
                ).run()

    def test_phase2_max_rounds_writes_convergence_failure_with_candidate_declaration(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_phase1_stable(Path(tmp), convergence_max_rounds=1)

            result = LivePhase2Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=CleanPhase2ReviewerClient(root),
                editor_client=EchoEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "TARGET_NOT_REACHED")
            report = _read_json(root / "rounds" / "convergence_failure_report.json")
            self.assertEqual(report["final_declaration_path"], "convergence_declaration.md")
            self.assertEqual(report["terminal_state"], "TARGET_NOT_REACHED")
            self.assertEqual(report["rubric_profile"], "standard-v1")

    def test_phase2_artifact_validation_failure_stops_loop(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_phase1_stable(Path(tmp))

            result = LivePhase2Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=BadReviewerClient(),
                editor_client=EchoEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "HALTED_ARTIFACT_INVALID")
            self.assertTrue((root / "rounds" / "artifact_validation_error.json").exists())

    def test_phase2_refreshes_candidate_declaration_after_later_draft_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_phase1_stable(Path(tmp))

            result = LivePhase2Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=CleanPhase2ReviewerClient(root),
                editor_client=ChangingEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "CONVERGED")
            final_hash = draft_hash(root.joinpath("spec.md").read_text(encoding="utf-8"))
            declaration = root.joinpath("convergence_declaration.md").read_text(encoding="utf-8")
            self.assertIn(f"final_draft_hash: {final_hash}", declaration)

    def test_phase2_refreshes_decision_register_and_summary_on_convergence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_phase1_stable(Path(tmp))
            stale_register = {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "mode": "end_of_cycle",
                "terminal_state": "PHASE_1_STABLE",
                "decision_points": [],
                "unresolved_human_decision_count": 0,
            }
            root.joinpath("rounds/decision_register.json").write_text(
                json.dumps(stale_register, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            root.joinpath("rounds/decision_summary.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-01-01T00:00:00+00:00",
                        "source_register_path": "rounds/decision_register.json",
                        "mode": "end_of_cycle",
                        "terminal_state": "PHASE_1_STABLE",
                        "decision_count": 0,
                        "unresolved_human_decision_count": 0,
                        "summary_method": "mechanical_v1",
                        "hotspots": {"largest_clusters": [], "human_decision_clusters": []},
                        "clusters": {"by_section": [], "by_round_profile": [], "by_trigger_type": []},
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = LivePhase2Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=CleanPhase2ReviewerClient(root),
                editor_client=DecisionPointEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "CONVERGED")
            register = _read_json(root / "rounds" / "decision_register.json")
            summary = _read_json(root / "rounds" / "decision_summary.json")
            self.assertEqual(register["terminal_state"], "CONVERGED")
            self.assertEqual(summary["terminal_state"], "CONVERGED")
            self.assertEqual(summary["decision_count"], len(register["decision_points"]))
            self.assertGreater(summary["decision_count"], 0)
            self.assertIn(5, {point["round_number"] for point in register["decision_points"]})


def _seed_phase1_stable(root: Path, *, convergence_max_rounds: int | None = None) -> Path:
    spec = "# Whetstone 0.17\n\n## Rules\n\nDraft.\n"
    root.joinpath("spec.md").write_text(spec, encoding="utf-8")
    root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
    root.joinpath("rounds").mkdir()
    spec_hash = draft_hash(spec)
    root.joinpath("rounds/run_state.json").write_text(
        json.dumps(
            {
                "current_round": 3,
                "phase": "phase_1",
                "active_profile": None,
                "current_draft_hash": spec_hash,
                "last_accepted_draft_hash": spec_hash,
                "seen_draft_hashes": [spec_hash],
                "terminal_state": "PHASE_1_STABLE",
                "ready_for_phase_2": True,
                "resumable": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if convergence_max_rounds is not None:
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
convergence:
  enabled: true
  target_phase: final
  target_mode: strict
  rubric_path: convergence_rubric.md
  max_rounds: {convergence_max_rounds}
""".lstrip(),
            encoding="utf-8",
        )
    return root


def _line_value(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise AssertionError(f"missing prompt line {prefix}")


def _draft_from_prompt(prompt: str) -> str:
    marker = "\nDraft:\n"
    if marker not in prompt:
        raise AssertionError("missing Draft block")
    return prompt.split(marker, 1)[1]


def _hash_line(prompt: str, prefix: str) -> str:
    value = _line_value(prompt, prefix).rstrip(".")
    if not HASH_RE.fullmatch(value):
        raise AssertionError(f"invalid hash line for {prefix}: {value}")
    return value


def _editor_round_number(prompt: str) -> int:
    match = re.search(r"The top-level object MUST set round_number to ([0-9]+)\.", prompt)
    if match is None:
        raise AssertionError("missing editor round number")
    return int(match.group(1))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
