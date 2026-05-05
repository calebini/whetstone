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
        self.assertIn("convergence_declaration.md` is a separate Orchestrator-owned artifact", prompt)
        self.assertIn("Do not recommend adding convergence declaration text to spec.md", prompt)
        self.assertIn("declaration review is not active for this round", prompt)
        self.assertIn("provisional declaration", prompt)
        self.assertIn("do not report reviewer_final_status `not_run` or declaration_status `rejected` as defects", prompt)
        self.assertIn("exclude staging status fields from findings", prompt)

    def test_phase_2_reviewer_prompt_includes_declaration_artifact_when_supplied(self) -> None:
        prompt = render_reviewer_prompt(
            profile="convergence_strict_check",
            draft="# Spec\n",
            declaration="# Convergence Declaration\n\n- declaration_status: accepted\n",
            phase="phase_2",
            section_ids=["spec"],
        )

        self.assertIn("Declaration artifact:", prompt)
        self.assertIn("declaration_status: accepted", prompt)

    def test_editor_prompt_names_schema_and_includes_feedback(self) -> None:
        prompt = render_editor_prompt(draft="# Spec\n", reviewer_feedback_json='{"feedback": []}')

        self.assertIn("editor_summary.json", prompt)
        self.assertIn("accepted_feedback_ids", prompt)
        self.assertIn("unresolved_issue_ids", prompt)
        self.assertIn("Do not return markdown", prompt)
        self.assertIn("Do not inspect repository files, run shell commands, use web search, or call tools.", prompt)
        self.assertIn('{"feedback": []}', prompt)

    def test_phase_2_editor_prompt_forbids_declaration_in_spec(self) -> None:
        prompt = render_editor_prompt(
            draft="# Spec\n",
            reviewer_feedback_json='{"feedback": []}',
            phase="phase_2",
            capture_only=False,
        )

        self.assertIn("convergence_declaration.md` is Orchestrator-owned", prompt)
        self.assertIn("Do not add convergence declaration text or acceptance statements to spec.md", prompt)

    def test_editor_prompt_says_whetstone_computes_generated_draft_hash(self) -> None:
        prompt = render_editor_prompt(
            draft="# Spec\n",
            reviewer_feedback_json='{"feedback": []}',
            capture_only=False,
        )

        self.assertIn("Whetstone computes draft_after_hash from draft_after_content", prompt)


if __name__ == "__main__":
    unittest.main()
