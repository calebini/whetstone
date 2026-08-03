from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import load_config
from whetstone.diagnostic_sweep import _recommendation, run_diagnostic_sweep

from tests.test_live_phase1 import ScriptedReviewerClient, _seed_root


class DiagnosticSweepTests(unittest.TestCase):
    def test_runs_each_phase1_profile_once_without_mutating_spec(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), profile_budget=2)
            before = root.joinpath("spec.md").read_text(encoding="utf-8")
            reviewer = ScriptedReviewerClient(root, ["major", None, "blocker"])

            result = run_diagnostic_sweep(root, load_config(root / "orchestrator_config.yaml"), reviewer_client=reviewer)

            self.assertEqual(reviewer.profiles, ["structural_integrity", "determinism", "operability"])
            self.assertEqual(result.profile_count, 3)
            self.assertEqual(result.feedback_count, 2)
            self.assertEqual(result.blocker_count, 1)
            self.assertEqual(result.major_count, 1)
            self.assertEqual(result.recommendation, "run_bounded_synthesis")
            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), before)

            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["editor_invoked"])
            self.assertFalse(report["spec_mutated"])
            self.assertEqual(report["draft_hash"], json.loads((root / "rounds" / "round-1" / "reviewer_feedback.json").read_text())["draft_hash"])
            self.assertTrue(result.markdown_path.exists())
            for round_number in (1, 2, 3):
                profile = json.loads(
                    root.joinpath("rounds", f"round-{round_number}", "profile_used.yaml").read_text(encoding="utf-8")
                )
                self.assertEqual(profile["round_kind"], "review_only")
                self.assertTrue(root.joinpath("rounds", f"round-{round_number}", "closeout_summary.json").exists())

    def test_clean_sweep_recommends_phase1(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _seed_root(Path(tmp), profile_budget=2)
            reviewer = ScriptedReviewerClient(root, [None, None, None])

            result = run_diagnostic_sweep(root, load_config(root / "orchestrator_config.yaml"), reviewer_client=reviewer)

            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(result.recommendation, "start_phase_1")
            self.assertTrue(all(profile["clean"] for profile in report["profiles"]))
            self.assertEqual(report["clusters"]["by_profile"], [])

    def test_in_scope_authority_conflict_recommends_synthesis(self) -> None:
        feedback = [
            _feedback("buildability", "conflicting_identifier_authority", ["4. Common Rules"]),
            _feedback("consistency", "artifact_reference_consistency", ["8. Subject Commands"]),
        ]

        recommendation, rationale = _recommendation(feedback, {"by_profile": [], "by_issue_type": [], "by_section": []})

        self.assertEqual(recommendation, "run_bounded_synthesis")
        self.assertIn("multiple profiles", rationale)

    def test_scope_boundary_conflict_recommends_manual_scope_review(self) -> None:
        feedback = [
            _feedback("buildability", "scope_boundary_conflict", ["Scope"]),
            _feedback("operability", "scope_contract_gap", ["Scope"]),
        ]

        recommendation, rationale = _recommendation(feedback, {"by_profile": [], "by_issue_type": [], "by_section": []})

        self.assertEqual(recommendation, "manual_scope_review")
        self.assertIn("scope-boundary", rationale)

def _feedback(source_profile: str, issue_type: str, affected_sections: list[str]) -> dict:
    return {
        "source_profile": source_profile,
        "feedback_id": f"fb-{source_profile}",
        "issue_type": issue_type,
        "affected_sections": affected_sections,
        "normalized_severity": "major",
    }


if __name__ == "__main__":
    unittest.main()
