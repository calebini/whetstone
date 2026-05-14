from __future__ import annotations

import unittest

from whetstone.scheduler import (
    PhaseScheduler,
    ProfileStep,
    default_phase_1_scheduler,
    default_phase_2_scheduler,
    profile_prompt_guidance,
    resolved_phase_1_profile_budgets,
    resolve_focus_anchors,
)


class SchedulerTests(unittest.TestCase):
    def test_repeats_blocker_profile_until_budget_then_advances(self) -> None:
        scheduler = PhaseScheduler(
            [
                ProfileStep("determinism", repeat_if_blockers=True, max_repeats=2),
                ProfileStep("operability"),
            ]
        )

        self.assertEqual(scheduler.next_profile(), "determinism")
        scheduler.record_result("determinism", blocker_count=1, major_count=0)
        self.assertEqual(scheduler.next_profile(), "determinism")
        scheduler.record_result("determinism", blocker_count=1, major_count=0)
        self.assertEqual(scheduler.next_profile(), "determinism")
        scheduler.record_result("determinism", blocker_count=1, major_count=0)
        self.assertEqual(scheduler.next_profile(), "operability")
        status = scheduler.status()["profiles"][0]
        self.assertEqual(status["residual_status"], "exhausted_with_residuals")

    def test_force_advance_marks_residual_status(self) -> None:
        scheduler = PhaseScheduler([ProfileStep("determinism"), ProfileStep("operability")])

        self.assertEqual(scheduler.next_profile(), "determinism")
        scheduler.force_advance_current(residual_status="halted_oscillation")

        self.assertEqual(scheduler.next_profile(), "operability")
        self.assertEqual(scheduler.status()["profiles"][0]["residual_status"], "halted_oscillation")

    def test_repeats_major_profile_for_clean_verification(self) -> None:
        scheduler = PhaseScheduler(
            [
                ProfileStep("determinism", repeat_if_blockers=True, max_repeats=1),
                ProfileStep("operability"),
            ]
        )

        self.assertEqual(scheduler.next_profile(), "determinism")
        scheduler.record_result("determinism", blocker_count=0, major_count=1)
        self.assertEqual(scheduler.next_profile(), "determinism")
        scheduler.record_result("determinism", blocker_count=0, major_count=0)
        self.assertEqual(scheduler.next_profile(), "operability")

    def test_phase_complete_requires_all_clean_and_accepted_draft(self) -> None:
        scheduler = PhaseScheduler([ProfileStep("a"), ProfileStep("b")])
        scheduler.record_result("a", blocker_count=0, major_count=0)
        scheduler.record_result("b", blocker_count=0, major_count=0)

        self.assertFalse(scheduler.phase_complete(accepted_draft=False))
        self.assertTrue(scheduler.phase_complete(accepted_draft=True))

    def test_mutated_focus_invalidates_clean_profile(self) -> None:
        scheduler = PhaseScheduler([ProfileStep("determinism", focus=frozenset({"hashing"}), skip_if_clean=True)])
        scheduler.record_result("determinism", blocker_count=0, major_count=0)
        self.assertTrue(scheduler.phase_complete(accepted_draft=True))

        scheduler.invalidate_for_mutated_sections(["hashing"])

        self.assertFalse(scheduler.phase_complete(accepted_draft=True))

    def test_default_phase_1_order(self) -> None:
        scheduler = default_phase_1_scheduler()

        self.assertEqual(scheduler.next_profile(), "structural_integrity")

    def test_utility_mvp_profile_set_uses_lightweight_profiles(self) -> None:
        scheduler = default_phase_1_scheduler(profile_set="utility_mvp")

        self.assertEqual([step.profile for step in scheduler.steps], ["buildability", "consistency", "determinism_light", "operability_light"])
        self.assertEqual(scheduler.total_round_budget(), 15)
        self.assertEqual(
            resolved_phase_1_profile_budgets(profile_set="utility_mvp"),
            {"buildability": 4, "consistency": 4, "determinism_light": 4, "operability_light": 3},
        )

    def test_phase_1_profile_sets_preserve_final_profile_always_run_behavior(self) -> None:
        scheduler = default_phase_1_scheduler(profile_set="utility_mvp")

        self.assertTrue(scheduler.steps[0].skip_if_clean)
        self.assertFalse(scheduler.steps[-1].skip_if_clean)

    def test_utility_mvp_phase_2_omits_adversarial(self) -> None:
        scheduler = default_phase_2_scheduler(profile_set="utility_mvp")

        self.assertEqual([step.profile for step in scheduler.steps], ["mvp_readiness_check", "scope_guard", "mvp_readiness_check"])
        self.assertEqual(scheduler.total_round_budget(), 11)

    def test_profile_prompt_guidance_is_defined_for_light_profile(self) -> None:
        guidance = profile_prompt_guidance("determinism_light")

        self.assertIsNotNone(guidance)
        self.assertIn("observable MVP outcomes", guidance or "")

    def test_default_focus_anchor_matches_versioned_section_id_suffix(self) -> None:
        scheduler = default_phase_1_scheduler()
        scheduler.record_result("structural_integrity", blocker_count=0, major_count=0)
        scheduler.record_result("determinism", blocker_count=0, major_count=0)
        scheduler.record_result("operability", blocker_count=0, major_count=0)
        self.assertTrue(scheduler.phase_complete(accepted_draft=True))

        scheduler.invalidate_for_mutated_sections(
            ["whetstone-ai-spec-convergence-orchestrator-0-11-strict-candidate-state-machine-full-transitions"]
        )

        self.assertFalse(scheduler.phase_complete(accepted_draft=True))

    def test_resolve_focus_anchors_requires_exactly_one_suffix_match(self) -> None:
        resolved = resolve_focus_anchors(
            [
                "whetstone-ai-spec-convergence-orchestrator-0-11-strict-candidate-state-machine-full-transitions",
                "whetstone-ai-spec-convergence-orchestrator-0-11-strict-candidate-conflict-model",
            ],
            ["state-machine-full-transitions"],
        )
        self.assertEqual(
            resolved,
            frozenset(
                {
                    "whetstone-ai-spec-convergence-orchestrator-0-11-strict-candidate-state-machine-full-transitions"
                }
            ),
        )

        with self.assertRaises(ValueError):
            resolve_focus_anchors(["a-state-machine-full-transitions", "b-state-machine-full-transitions"], ["state-machine-full-transitions"])

    def test_duplicate_profile_steps_have_independent_state(self) -> None:
        scheduler = PhaseScheduler([ProfileStep("check"), ProfileStep("other"), ProfileStep("check")])

        scheduler.record_result("check", blocker_count=0, major_count=0)
        scheduler.record_result("other", blocker_count=0, major_count=0)

        self.assertFalse(scheduler.phase_complete(accepted_draft=True))
        self.assertEqual(scheduler.next_profile(), "check")


if __name__ == "__main__":
    unittest.main()
