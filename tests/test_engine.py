from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.engine import FixtureEngine, FixtureScriptStep
from whetstone.identity import issue_fingerprint, issue_id, oscillation_fingerprint, oscillation_opposition_key


class FixtureEngineTests(unittest.TestCase):
    def test_fixture_engine_reaches_converged_after_phase_2_declaration(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            steps = [
                _clean_step("structural_integrity"),
                _clean_step("determinism"),
                _clean_step("operability"),
                _clean_step("convergence_strict_check"),
                _clean_step("adversarial"),
                _clean_step("convergence_strict_check", declaration_accepted=True),
            ]

            result = FixtureEngine(root).run(steps)

            self.assertEqual(result.terminal_state, "CONVERGED")
            self.assertEqual(result.phase, "phase_2")
            self.assertTrue((root / "convergence_declaration.md").exists())
            self.assertTrue((root / "rounds" / "round-6" / "prompt_snapshot.json").exists())

    def test_fixture_engine_writes_technical_failure_when_phase_1_script_exhausts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            step = _issue_step("structural_integrity", "blocker")

            result = FixtureEngine(root).run([step])

            self.assertEqual(result.terminal_state, "TARGET_NOT_REACHED")
            self.assertEqual(result.phase, "phase_1")
            report = json.loads((root / "rounds" / "technical_failure_report.json").read_text())
            self.assertEqual(report["unresolved_blockers"][0]["normalized_severity"], "blocker")

    def test_fixture_engine_halts_on_repeated_blocker_conflict(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            conflict = _conflict("blocker")

            result = FixtureEngine(root).run(
                [
                    _clean_step("structural_integrity", conflicts=[conflict]),
                    _clean_step("determinism", conflicts=[conflict]),
                ]
            )

            self.assertEqual(result.terminal_state, "HALTED_CONFLICT")
            self.assertEqual(result.round_number, 2)
            self.assertTrue((root / "rounds" / "conflict_report.json").exists())

    def test_fixture_engine_reports_nonblocker_conflict_without_halting(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            conflict = _conflict("major")
            steps = [
                _clean_step("structural_integrity", conflicts=[conflict]),
                _clean_step("determinism", conflicts=[conflict]),
                _clean_step("operability"),
                _clean_step("convergence_strict_check", declaration_accepted=True),
            ]

            result = FixtureEngine(root).run(steps)

            self.assertEqual(result.terminal_state, "CONVERGED")
            report = json.loads((root / "rounds" / "conflict_report.json").read_text())
            self.assertIsNone(report["terminal_state"])
            self.assertEqual(report["conflicts"][0]["conflict_severity"], "major")

    def test_fixture_engine_escalates_nonconsecutive_conflict_on_third_appearance(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            conflict = _conflict("blocker")
            steps = [
                _clean_step("structural_integrity", conflicts=[conflict]),
                _clean_step("determinism"),
                _clean_step("operability", conflicts=[conflict]),
                _clean_step("convergence_strict_check"),
                _clean_step("adversarial", conflicts=[conflict]),
            ]

            result = FixtureEngine(root).run(steps)

            self.assertEqual(result.terminal_state, "HALTED_CONFLICT")
            self.assertEqual(result.round_number, 5)
            report = json.loads((root / "rounds" / "conflict_report.json").read_text())
            self.assertIn("3 times non-consecutively", report["exit_reason"])

    def test_phase2_feedback_churn_creates_nonhalting_conflict_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            steps = [
                _clean_step("structural_integrity"),
                _clean_step("determinism"),
                _clean_step("operability"),
                _phase2_oscillation_step("convergence_strict_check", "clarify", "major", "fb-1"),
                _phase2_oscillation_step("adversarial", "clarify", "major", "fb-2"),
                _phase2_oscillation_step("convergence_strict_check", "clarify", "major", "fb-3"),
            ]

            result = FixtureEngine(root).run(steps)

            self.assertNotEqual(result.terminal_state, "HALTED_CONFLICT")
            conflict = json.loads((root / "rounds" / "conflict_report.json").read_text())
            self.assertIsNone(conflict["terminal_state"])
            self.assertIn("feedback_churn", conflict["exit_reason"])

    def test_phase2_feedback_churn_halts_when_blocker_level(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            steps = [
                _clean_step("structural_integrity"),
                _clean_step("determinism"),
                _clean_step("operability"),
                _phase2_oscillation_step("convergence_strict_check", "clarify", "blocker", "fb-1"),
                _phase2_oscillation_step("adversarial", "clarify", "blocker", "fb-2"),
                _phase2_oscillation_step("convergence_strict_check", "clarify", "blocker", "fb-3"),
            ]

            result = FixtureEngine(root).run(steps)

            self.assertEqual(result.terminal_state, "HALTED_CONFLICT")
            conflict = json.loads((root / "rounds" / "conflict_report.json").read_text())
            self.assertEqual(conflict["terminal_state"], "HALTED_CONFLICT")
            convergence = json.loads((root / "rounds" / "convergence_failure_report.json").read_text())
            self.assertEqual(convergence["terminal_state"], "HALTED_CONFLICT")
            self.assertEqual(convergence["reviewer_final_status"], "not_run")

    def test_clean_convergence_beats_same_round_blocker_conflict(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            conflict = _conflict("blocker")
            steps = [
                _clean_step("structural_integrity"),
                _clean_step("determinism"),
                _clean_step("operability"),
                _clean_step("convergence_strict_check", conflicts=[conflict]),
                _clean_step("adversarial", conflicts=[conflict], declaration_accepted=True),
            ]

            result = FixtureEngine(root).run(steps)

            self.assertEqual(result.terminal_state, "CONVERGED")
            self.assertTrue((root / "rounds" / "conflict_report.json").exists())

    def test_blocker_conflict_beats_same_round_oscillation_stop(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            conflict = _conflict("blocker")
            start = "# Spec\n\nSeed.\n"
            changed = "# Spec\n\nChanged.\n"
            steps = [
                _clean_step("structural_integrity"),
                _clean_step("determinism"),
                _clean_step("operability"),
                _clean_step("convergence_strict_check", draft_after=changed, conflicts=[conflict]),
                _clean_step("adversarial", draft_after=start, conflicts=[conflict]),
            ]

            result = FixtureEngine(root).run(steps)

            self.assertEqual(result.terminal_state, "HALTED_CONFLICT")
            self.assertTrue((root / "rounds" / "oscillation_report.json").exists())
            self.assertTrue((root / "rounds" / "conflict_report.json").exists())
            self.assertTrue((root / "rounds" / "convergence_failure_report.json").exists())

    def test_phase2_oscillation_halt_emits_convergence_failure_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _repo(tmp)
            start = "# Spec\n\nSeed.\n"
            changed = "# Spec\n\nChanged.\n"
            steps = [
                _clean_step("structural_integrity"),
                _clean_step("determinism"),
                _clean_step("operability"),
                _clean_step("convergence_strict_check", draft_after=changed),
                _clean_step("adversarial", draft_after=start),
            ]

            result = FixtureEngine(root).run(steps)

            self.assertEqual(result.terminal_state, "HALTED_OSCILLATION")
            convergence = json.loads((root / "rounds" / "convergence_failure_report.json").read_text())
            self.assertEqual(convergence["terminal_state"], "HALTED_OSCILLATION")
            self.assertEqual(convergence["final_draft_path"], "rounds/round-5/draft_after.md")


def _repo(tmp: str) -> Path:
    root = Path(tmp)
    (root / "spec.md").write_text("# Spec\n\nSeed.\n", encoding="utf-8")
    (root / "spec.history.md").write_text("# History\n", encoding="utf-8")
    return root


def _clean_step(
    profile: str,
    *,
    declaration_accepted: bool = False,
    conflicts: list[dict] | None = None,
    draft_after: str | None = None,
) -> FixtureScriptStep:
    return FixtureScriptStep(
        reviewer_feedback={
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "feedback": [],
        },
        editor_summary={
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [],
        },
        declaration_accepted=declaration_accepted,
        conflicts=conflicts or [],
        draft_after=draft_after,
    )


def _conflict(severity: str) -> dict:
    return {
        "conflict_id": "con_bbbbbbbbbbbbbbbb",
        "conflict_fingerprint": "b" * 64,
        "conflict_type": "profile_conflict",
        "conflict_severity": severity,
        "participating_issue_ids": ["iss_aaaaaaaaaaaaaaaa"],
        "conflict_claim": "Profiles disagree.",
    }


def _issue_step(profile: str, severity: str) -> FixtureScriptStep:
    fingerprint = issue_fingerprint("undefined_behavior", ["# Spec"], None, f"{severity} issue")
    identifier = issue_id(fingerprint)
    return FixtureScriptStep(
        reviewer_feedback={
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "feedback": [
                {
                    "feedback_id": "fb-1",
                    "issue_id": identifier,
                    "issue_fingerprint": fingerprint,
                    "issue_type": "undefined_behavior",
                    "affected_sections": ["# Spec"],
                    "baseline_severity": severity,
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": severity,
                    "invariant_violated": None,
                    "claim": f"{severity} issue",
                    "evidence": "fixture",
                    "recommended_change": "fix it",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": None,
                }
            ],
        },
        editor_summary={
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [identifier],
        },
    )


def _phase2_oscillation_step(profile: str, direction: str, severity: str, feedback_id: str) -> FixtureScriptStep:
    fingerprint = issue_fingerprint("precision_gap", ["spec"], None, f"{direction} issue")
    identifier = issue_id(fingerprint)
    oscillation_key = {
        "section_id": "spec",
        "concern_type": "precision_gap",
        "direction": direction,
        "scope": "local",
        "fingerprint": oscillation_fingerprint("spec", "precision_gap", direction, "local"),
        "opposition_key": oscillation_opposition_key("spec", "precision_gap", "local"),
    }
    return FixtureScriptStep(
        reviewer_feedback={
            "profile": profile,
            "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
            "feedback": [
                {
                    "feedback_id": feedback_id,
                    "issue_id": identifier,
                    "issue_fingerprint": fingerprint,
                    "issue_type": "precision_gap",
                    "affected_sections": ["spec"],
                    "baseline_severity": severity,
                    "authority_impact": None,
                    "determinism_impact": None,
                    "rubric_impact": None,
                    "normalized_severity": severity,
                    "invariant_violated": None,
                    "claim": f"{direction} issue",
                    "evidence": "fixture",
                    "recommended_change": "fix it",
                    "in_scope": True,
                    "severity_rationale": None,
                    "oscillation_key": oscillation_key,
                }
            ],
        },
        editor_summary={
            "accepted_feedback_ids": [],
            "modified_feedback_ids": [],
            "declined_feedback": [],
            "created_conflict_ids": [],
            "resolved_issue_ids": [],
            "unresolved_issue_ids": [identifier],
        },
    )


if __name__ == "__main__":
    unittest.main()
