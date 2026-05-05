from __future__ import annotations

import unittest

from whetstone.declaration import declaration_revision_route, render_convergence_declaration, validate_convergence_declaration


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

    def test_render_convergence_declaration_rejects_conditional_status(self) -> None:
        with self.assertRaises(ValueError):
            render_convergence_declaration(
                target_phase="final",
                target_mode="strict",
                final_draft_hash="a" * 64,
                rubric_content_hash="b" * 64,
                unresolved_blockers_count=0,
                unresolved_major_issues_count=0,
                unresolved_rubric_gaps_count=0,
                reviewer_final_status="accepted",
                declaration_status="conditional",
            )

    def test_validate_convergence_declaration_checks_hashes_and_counts(self) -> None:
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

        self.assertTrue(
            validate_convergence_declaration(
                rendered,
                final_draft_hash="a" * 64,
                rubric_content_hash="b" * 64,
                unresolved_blockers_count=0,
                unresolved_major_issues_count=0,
                unresolved_rubric_gaps_count=0,
            )
        )
        self.assertFalse(
            validate_convergence_declaration(
                rendered,
                final_draft_hash="c" * 64,
                rubric_content_hash="b" * 64,
                unresolved_blockers_count=0,
                unresolved_major_issues_count=0,
                unresolved_rubric_gaps_count=0,
            )
        )

    def test_declaration_revision_route_detects_declaration_only_work(self) -> None:
        route = declaration_revision_route(
            [
                {
                    "affected_sections": ["convergence_declaration.md"],
                    "in_scope": True,
                }
            ]
        )

        self.assertEqual(route, "DECLARATION_REVISION")

    def test_declaration_revision_route_prefers_source_spec_work(self) -> None:
        route = declaration_revision_route(
            [
                {
                    "affected_sections": ["convergence_declaration.md"],
                    "in_scope": True,
                },
                {
                    "affected_sections": ["spec.md"],
                    "in_scope": True,
                },
            ]
        )

        self.assertEqual(route, "CONVERGENCE_REVISION")


if __name__ == "__main__":
    unittest.main()
