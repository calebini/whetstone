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
            "round_number": self.calls,
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "draft_hash": draft_hash((self.root / "spec.md").read_text(encoding="utf-8")),
            "feedback": feedback,
        }


class ResolvingEditorClient:
    def __init__(self) -> None:
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt)
        issue_ids = re.findall(r'"issue_id": "(iss_[a-f0-9]{16})"', prompt)
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
    def __init__(self) -> None:
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt)
        issue_ids = re.findall(r'"issue_id": "(iss_[a-f0-9]{16})"', prompt)
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
                editor_client=ResolvingEditorClient(),
            ).run(overwrite=True)

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertTrue(result.ready_for_phase_2)
            self.assertEqual(reviewer.profiles, ["structural_integrity", "determinism", "operability"])
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())
            state = _read_json(root / "rounds" / "run_state.json")
            self.assertEqual(state["terminal_state"], "PHASE_1_STABLE")
            self.assertTrue(state["ready_for_phase_2"])
            self.assertEqual(state["telemetry_totals"]["round_count"], 3)
            self.assertEqual(state["telemetry_totals"]["attempt_count"], 6)
            self.assertEqual(state["telemetry_totals"]["missing_usage_attempts"], 6)

    def test_blocker_profile_repeats_before_advancing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            reviewer = ScriptedReviewerClient(root, ["blocker", None, None, None])
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=ResolvingMutatingEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertEqual(reviewer.profiles, ["structural_integrity", "structural_integrity", "determinism", "operability"])

    def test_editor_resolution_requires_reviewer_verification_before_profile_advances(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            reviewer = ScriptedReviewerClient(root, ["blocker", None, None, None])
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
                editor_client=ResolvingMutatingEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            self.assertEqual(reviewer.profiles, ["structural_integrity", "structural_integrity", "determinism", "operability"])

    def test_max_rounds_emits_technical_failure_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), review_max_rounds=1)
            result = LivePhase1Runner(
                root,
                load_config(root / "orchestrator_config.yaml"),
                reviewer_client=ScriptedReviewerClient(root, ["major"]),
                editor_client=BlockingEditorClient(),
                draft_after_provider=lambda round_number, profile, draft: draft + "\nChanged.\n",
            ).run()

            self.assertEqual(result.terminal_state, "TARGET_NOT_REACHED")
            self.assertTrue((root / "rounds" / "technical_failure_report.json").exists())

    def test_repeated_blocking_draft_hash_emits_oscillation_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=ScriptedReviewerClient(root, ["blocker"]),
                editor_client=BlockingEditorClient(),
            ).run()

            self.assertEqual(result.terminal_state, "HALTED_OSCILLATION")
            report = _read_json(root / "rounds" / "oscillation_report.json")
            self.assertEqual(report["terminal_state"], "HALTED_OSCILLATION")

    def test_artifact_validation_failure_stops_loop_without_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp))
            before = (root / "spec.md").read_text(encoding="utf-8")
            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=BadReviewerClient(),
                editor_client=ResolvingEditorClient(),
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
                editor_client=ResolvingEditorClient(),
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
                editor_client=ResolvingEditorClient(),
            ).run()
            self.assertEqual(phase1_result.terminal_state, "PHASE_1_STABLE")

            phase2_reviewer = CleanReviewerClient(root)
            LiveRoundRunner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=phase2_reviewer,
                editor_client=ResolvingEditorClient(),
            ).run_round(round_number=4, profile="convergence_strict_check", phase="phase_2")

            self.assertIn("# Whetstone 1.0", root.joinpath("spec.md").read_text(encoding="utf-8"))
            self.assertIn("# Whetstone 1.0", root.joinpath("rounds/round-4/draft_before.md").read_text(encoding="utf-8"))
            history = root.joinpath("spec.history.md").read_text(encoding="utf-8")
            self.assertIn("Phase 2 version promotion: `0.17` -> `1.0`", history)


class BlockingThenResolvingEditorClient:
    def __init__(self) -> None:
        self.calls = 0

    def revise(self, prompt: str) -> dict:
        self.calls += 1
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt)
        issue_ids = re.findall(r'"issue_id": "(iss_[a-f0-9]{16})"', prompt)
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
    def revise(self, prompt: str) -> dict:
        before_hash = _hash_line(prompt, "The draft_before_hash MUST be ")
        explicit_after_hash = _optional_hash_line(prompt, "The draft_after_hash MUST be ")
        draft_after_content = _draft_from_prompt(prompt)
        issue_ids = re.findall(r'"issue_id": "(iss_[a-f0-9]{16})"', prompt)
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


def _seed_root(
    root: Path,
    *,
    review_max_rounds: int | None = None,
    decision_mode: str | None = None,
    spec: str = "# Spec\n\nDraft.\n",
) -> Path:
    root.joinpath("spec.md").write_text(spec, encoding="utf-8")
    root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
    if review_max_rounds is not None or decision_mode is not None:
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
