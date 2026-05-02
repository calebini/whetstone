from __future__ import annotations

import unittest

from whetstone.declaration import render_convergence_declaration


class DeclarationTests(unittest.TestCase):
    def test_render_convergence_declaration_contains_required_fields(self) -> None:
        rendered = render_convergence_declaration(
            target_phase="final",
            target_mode="strict",
            final_draft_hash="a" * 64,
            rubric_content_hash="b" * 64,
            unresolved_blockers_count=0,
            unresolved_major_issues_count=0,
            unresolved_rubric_gaps_count=0,
            reviewer_final_status="accepted",
            declaration_status="accepted",
        )

        self.assertIn("target_phase: final", rendered)
        self.assertIn("declaration_status: accepted", rendered)


if __name__ == "__main__":
    unittest.main()

