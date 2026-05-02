from __future__ import annotations

import unittest

from whetstone.evaluation import (
    accepted_draft,
    conflict_severity,
    oscillation_recommendation,
    target_matrix_satisfied,
)


class EvaluationTests(unittest.TestCase):
    def test_accepted_draft_rejects_blockers_and_majors(self) -> None:
        self.assertTrue(accepted_draft([{"normalized_severity": "minor"}]))
        self.assertFalse(accepted_draft([{"normalized_severity": "major"}]))
        self.assertFalse(accepted_draft([{"normalized_severity": "blocker"}]))

    def test_conflict_severity_uses_participating_issue_max(self) -> None:
        self.assertEqual(
            conflict_severity([{"normalized_severity": "minor"}, {"normalized_severity": "blocker"}]),
            "blocker",
        )

    def test_target_matrix_final_strict_requires_declaration_and_no_gaps(self) -> None:
        self.assertFalse(
            target_matrix_satisfied(
                target_phase="final",
                target_mode="strict",
                issues=[],
                unresolved_rubric_gaps=[],
                declaration_accepted=False,
            )
        )
        self.assertTrue(
            target_matrix_satisfied(
                target_phase="final",
                target_mode="strict",
                issues=[],
                unresolved_rubric_gaps=[],
                declaration_accepted=True,
            )
        )

    def test_mid_permissive_allows_major_but_not_blocker(self) -> None:
        self.assertTrue(
            target_matrix_satisfied(
                target_phase="mid",
                target_mode="permissive",
                issues=[{"normalized_severity": "major"}],
            )
        )
        self.assertFalse(
            target_matrix_satisfied(
                target_phase="mid",
                target_mode="permissive",
                issues=[{"normalized_severity": "blocker"}],
            )
        )

    def test_oscillation_recommendation_table(self) -> None:
        self.assertEqual(oscillation_recommendation("cycle"), "stop_iteration")
        self.assertEqual(oscillation_recommendation("mechanical_churn"), "freeze_prior_decision")
        self.assertEqual(oscillation_recommendation("feedback_flip_flop", ["major"]), "escalate_conflict")
        self.assertEqual(oscillation_recommendation("feedback_flip_flop", [None]), "freeze_prior_decision")
        self.assertEqual(oscillation_recommendation("feedback_churn"), "escalate_conflict")
        self.assertEqual(oscillation_recommendation("feedback_re_addition"), "continue_once")
        self.assertEqual(
            oscillation_recommendation("feedback_re_addition", repeated_readdition=True),
            "stop_iteration",
        )


if __name__ == "__main__":
    unittest.main()
