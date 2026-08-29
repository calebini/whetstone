from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.change_audit import AuditClientIdentity, build_change_audit_report, run_change_audit
from whetstone.hashing import draft_hash


class FixtureReviewer:
    def __init__(self, feedback: list[dict]) -> None:
        self.feedback = feedback
        self.prompts: list[str] = []

    def review(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        draft_hash_value = _line_value(prompt, "- draft_hash:")
        return {
            "round_number": 1,
            "profile": _line_value(prompt, "- profile:"),
            "reviewer": {"name": "fixture", "version": "0", "model": "fixture"},
            "draft_hash": draft_hash_value,
            "feedback": self.feedback,
        }


class BrokenReviewer:
    def review(self, prompt: str) -> dict:
        raise RuntimeError("reviewer unavailable")


class ChangeAuditTests(unittest.TestCase):
    def test_change_audit_writes_brief_manifest_feedback_and_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "audit-notes.md"
            spec_a = root / "policy.md"
            spec_b = root / "lifecycle.md"
            notes.write_text("# Change Intent\n\nPreserve evidence integrity boundary.\n", encoding="utf-8")
            spec_a.write_text("# Policy\n\nPolicy MUST receive integrity status as input.\n", encoding="utf-8")
            spec_b.write_text("# Lifecycle\n\nAcceptance-time integrity MUST be mandatory.\n", encoding="utf-8")

            result = run_change_audit(
                root=root / "audit-run",
                notes_path=notes,
                spec_paths=[spec_a, spec_b],
                profile="consistency",
                reviewer_client=FixtureReviewer([_feedback("minor", True)]),
                client_identity=AuditClientIdentity(name="fixture", version="0", model="fixture"),
            )

            self.assertEqual(result.verdict, "pass_with_minor_clarification")
            self.assertTrue(result.boundary_preserved)
            self.assertTrue(result.brief_path.exists())
            self.assertIn("Workflow: audit_change", result.brief_path.read_text(encoding="utf-8"))
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            feedback = json.loads(result.feedback_path.read_text(encoding="utf-8"))
            self.assertEqual(report["feedback_counts"]["minor"], 1)
            self.assertIsNone(report["failure_reason"])
            self.assertEqual(report["recommended_next_action"], "manual_patch")
            self.assertEqual(feedback["draft_hash"], draft_hash(result.brief_path.read_text(encoding="utf-8")))
            self.assertEqual(manifest["specs"][0]["hash"], draft_hash(spec_a.read_text(encoding="utf-8")))

    def test_change_audit_reviewer_prompt_uses_audit_change_phase_label(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "audit-notes.md"
            spec = root / "policy.md"
            notes.write_text("# Change Intent\n\nKeep the audit bounded.\n", encoding="utf-8")
            spec.write_text("# Policy\n\nThe Evaluator MUST NOT read storage.\n", encoding="utf-8")
            reviewer = FixtureReviewer([])

            run_change_audit(
                root=root / "audit-run",
                notes_path=notes,
                spec_paths=[spec],
                profile="consistency",
                reviewer_client=reviewer,
                client_identity=AuditClientIdentity(name="fixture", version="0", model="fixture"),
            )

            self.assertEqual(len(reviewer.prompts), 1)
            prompt = reviewer.prompts[0]
            self.assertIn("Phase: audit_change", prompt)
            self.assertNotIn("Phase: phase_1", prompt)
            self.assertIn("bounded reviewer-only audit, not Phase 1 or Phase 2", prompt)

    def test_change_audit_writes_audit_failed_report_when_reviewer_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "audit-notes.md"
            spec = root / "policy.md"
            notes.write_text("# Change Intent\n\nCheck boundary.\n", encoding="utf-8")
            spec.write_text("# Policy\n\nDraft.\n", encoding="utf-8")

            result = run_change_audit(
                root=root / "audit-run",
                notes_path=notes,
                spec_paths=[spec],
                profile="consistency",
                reviewer_client=BrokenReviewer(),
                client_identity=AuditClientIdentity(name="fixture", version="0", model="fixture"),
            )

            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(result.verdict, "audit_failed")
            self.assertIsNone(result.boundary_preserved)
            self.assertEqual(report["recommended_next_action"], "fix_audit_setup")
            self.assertIn("reviewer unavailable", report["failure_reason"])

    def test_change_audit_report_ignores_out_of_scope_feedback_for_verdict(self) -> None:
        feedback = {
            "feedback": [
                _feedback("blocker", False),
                _feedback("nit", True, feedback_id="fb-nit"),
            ]
        }

        report = build_change_audit_report(
            feedback=feedback,
            brief_hash="a" * 64,
            profile="consistency",
            feedback_path=Path("change_audit/change_audit_feedback.json"),
            manifest_path=Path("change_audit/audit_manifest.json"),
        )

        self.assertEqual(report["verdict"], "pass_with_minor_clarification")
        self.assertIsNone(report["failure_reason"])
        self.assertEqual(report["feedback_counts"]["blocker"], 0)
        self.assertEqual(report["out_of_scope_feedback_ids"], ["fb-1"])


def _feedback(severity: str, in_scope: bool, *, feedback_id: str = "fb-1") -> dict:
    return {
        "feedback_id": feedback_id,
        "issue_id": "iss_aaaaaaaaaaaaaaaa",
        "issue_fingerprint": "a" * 64,
        "issue_type": "consistency_violation",
        "affected_sections": ["policy"],
        "baseline_severity": severity,
        "authority_impact": None,
        "determinism_impact": None,
        "rubric_impact": None,
        "normalized_severity": severity,
        "invariant_violated": "authority_boundary",
        "claim": "Default evidence scope differs.",
        "evidence": "Fixture evidence.",
        "recommended_change": "Align the scope statement.",
        "in_scope": in_scope,
        "severity_rationale": None,
        "oscillation_key": None,
    }


def _line_value(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise AssertionError(f"missing {prefix}")


if __name__ == "__main__":
    unittest.main()
