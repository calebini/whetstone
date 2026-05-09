from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.reports import ReportWriter


HASH = "a" * 64
ISSUE = {
    "issue_id": "iss_aaaaaaaaaaaaaaaa",
    "issue_fingerprint": HASH,
    "normalized_severity": "blocker",
    "affected_sections": ["# Spec"],
    "claim": "A blocker exists.",
}
CONFLICT = {
    "conflict_id": "con_bbbbbbbbbbbbbbbb",
    "conflict_fingerprint": "b" * 64,
    "conflict_type": "profile_conflict",
    "conflict_severity": "blocker",
    "participating_issue_ids": ["iss_aaaaaaaaaaaaaaaa"],
    "conflict_claim": "Profiles disagree.",
}


class ReportWriterTests(unittest.TestCase):
    def test_writes_schema_valid_oscillation_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
            output = ReportWriter(root).write_oscillation_report(
                round_number=1,
                detected=True,
                oscillation_type="cycle",
                affected_sections=["# Spec"],
                suspected_feedback_ids=["fb-1"],
                recommendation="stop_iteration",
            )

            packet = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(packet["terminal_state"], "HALTED_OSCILLATION")

    def test_writes_nonhalting_oscillation_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
            output = ReportWriter(root).write_oscillation_report(
                round_number=1,
                detected=True,
                oscillation_type="mechanical_churn",
                affected_sections=["# Spec"],
                suspected_feedback_ids=[],
                recommendation="freeze_prior_decision",
            )

            packet = json.loads(output.read_text(encoding="utf-8"))
            self.assertIsNone(packet["terminal_state"])

    def test_writes_schema_valid_conflict_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
            output = ReportWriter(root).write_conflict_report(
                round_number=1,
                conflicts=[CONFLICT],
                exit_reason="blocker conflict escalated",
            )

            packet = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(packet["conflicts"][0]["conflict_id"], "con_bbbbbbbbbbbbbbbb")

    def test_writes_nonhalting_conflict_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
            output = ReportWriter(root).write_conflict_report(
                round_number=1,
                conflicts=[{**CONFLICT, "conflict_severity": "major"}],
                exit_reason="major conflict escalated for manual review",
                terminal_state=None,
            )

            packet = json.loads(output.read_text(encoding="utf-8"))
            self.assertIsNone(packet["terminal_state"])

    def test_writes_schema_valid_failure_reports(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
            writer = ReportWriter(root)

            technical = writer.write_technical_failure_report(
                round_number=1,
                final_draft_path="./spec.md",
                unresolved_blockers=[ISSUE],
                unresolved_major_issues=[],
                unresolved_conflicts=[CONFLICT],
                unresolved_oscillation=None,
                last_accepted_draft_hash=None,
                exit_reason="max rounds",
                recommendation="manual_review_required",
            )
            convergence = writer.write_convergence_failure_report(
                round_number=1,
                final_draft_path="./spec.md",
                final_declaration_path=None,
                target_phase="final",
                target_mode="strict",
                unresolved_blockers=[ISSUE],
                unresolved_major_issues=[],
                unresolved_rubric_gaps=[],
                reviewer_final_status="rejected",
                last_accepted_draft_hash=None,
                exit_reason="declaration rejected",
                recommendation="manual_review_required",
            )

            self.assertTrue(technical.exists())
            self.assertTrue(convergence.exists())
            packet = json.loads(technical.read_text(encoding="utf-8"))
            self.assertEqual(packet["current_draft_status"], "not_accepted")
            self.assertFalse(packet["ready_for_phase_2"])


if __name__ == "__main__":
    unittest.main()
