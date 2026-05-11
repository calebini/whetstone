from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.hashing import draft_hash
from whetstone.identity import issue_fingerprint, issue_id
from whetstone.runner import FixtureRunner


class FixtureRunnerTests(unittest.TestCase):
    def test_fixture_round_writes_full_round_packet_and_updates_spec(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = "# Spec\n\nOld.\n"
            after = "# Spec\n\nNew.\n"
            (root / "spec.md").write_text(before, encoding="utf-8")
            (root / "spec.history.md").write_text("# History\n", encoding="utf-8")
            fingerprint = issue_fingerprint("undefined_behavior", ["# Spec"], None, "Old text is vague.")
            identifier = issue_id(fingerprint)
            reviewer_feedback = {
                "profile": "structural_integrity",
                "reviewer": {"name": "fixture-reviewer", "version": "0.0.0", "model": "fixture"},
                "feedback": [
                    {
                        "feedback_id": "fb-1",
                        "issue_id": identifier,
                        "issue_fingerprint": fingerprint,
                        "issue_type": "undefined_behavior",
                        "affected_sections": ["# Spec"],
                        "baseline_severity": "major",
                        "authority_impact": None,
                        "determinism_impact": None,
                        "rubric_impact": None,
                        "normalized_severity": "major",
                        "invariant_violated": None,
                        "claim": "Old text is vague.",
                        "evidence": "Fixture evidence.",
                        "recommended_change": "Replace old text.",
                        "in_scope": True,
                        "severity_rationale": None,
                        "oscillation_key": None,
                    }
                ],
            }
            editor_summary = {
                "accepted_feedback_ids": ["fb-1"],
                "modified_feedback_ids": [],
                "declined_feedback": [],
                "created_conflict_ids": [],
                "resolved_issue_ids": [identifier],
                "unresolved_issue_ids": [],
            }

            result = FixtureRunner(root).run_round(
                round_number=1,
                reviewer_feedback=reviewer_feedback,
                editor_summary=editor_summary,
                draft_after=after,
            )

            self.assertTrue(result.accepted)
            self.assertEqual(result.draft_before_hash, draft_hash(before))
            self.assertEqual((root / "spec.md").read_text(encoding="utf-8"), after)
            expected_files = {
                "draft_before.md",
                "draft_after.md",
                "reviewer_feedback.json",
                "reviewer_working_notes.md",
                "editor_summary.json",
                "unresolved_issues.json",
                "profile_used.yaml",
                "prompt_snapshot.json",
            }
            self.assertEqual({path.name for path in (root / "rounds" / "round-1").iterdir()}, expected_files)
            profile_used = json.loads((root / "rounds" / "round-1" / "profile_used.yaml").read_text())
            self.assertEqual(profile_used["profile"], "structural_integrity")
            self.assertEqual(profile_used["round_kind"], "fixture")
            unresolved = json.loads((root / "rounds" / "round-1" / "unresolved_issues.json").read_text())
            self.assertEqual(unresolved["unresolved_issues"], [])


if __name__ == "__main__":
    unittest.main()
