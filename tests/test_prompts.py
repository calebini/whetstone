from __future__ import annotations

import unittest

from whetstone.prompts import render_reviewer_prompt, render_editor_prompt


class PromptTests(unittest.TestCase):
    def test_reviewer_prompt_names_profile_and_schema(self) -> None:
        prompt = render_reviewer_prompt(profile="determinism", draft="# Spec\n")

        self.assertIn("Review profile: determinism", prompt)
        self.assertIn("reviewer_feedback.json", prompt)
        self.assertIn("oscillation_key", prompt)
        self.assertIn("For Phase 1, set oscillation_key to null", prompt)
        self.assertIn("Whetstone computes issue_id, issue_fingerprint, and normalized_severity", prompt)

    def test_phase_2_reviewer_prompt_requires_oscillation_classification(self) -> None:
        prompt = render_reviewer_prompt(
            profile="convergence_strict_check",
            draft="# Spec\n",
            phase="phase_2",
            section_ids=["spec"],
        )

        self.assertIn("Phase 2 reviewer prompt requirements", prompt)
        self.assertIn("section_id MUST be chosen from the canonical section IDs", prompt)
        self.assertIn("- spec", prompt)
        self.assertIn("concern_type", prompt)
        self.assertIn("Use modify only when no more specific direction applies", prompt)
        self.assertIn("add/remove", prompt)

    def test_editor_prompt_names_schema_and_includes_feedback(self) -> None:
        prompt = render_editor_prompt(draft="# Spec\n", reviewer_feedback_json='{"feedback": []}')

        self.assertIn("editor_summary.json", prompt)
        self.assertIn("accepted_feedback_ids", prompt)
        self.assertIn("unresolved_issue_ids", prompt)
        self.assertIn("Do not return markdown", prompt)
        self.assertIn('{"feedback": []}', prompt)

    def test_editor_prompt_says_whetstone_computes_generated_draft_hash(self) -> None:
        prompt = render_editor_prompt(
            draft="# Spec\n",
            reviewer_feedback_json='{"feedback": []}',
            capture_only=False,
        )

        self.assertIn("Whetstone computes draft_after_hash from draft_after_content", prompt)


if __name__ == "__main__":
    unittest.main()
