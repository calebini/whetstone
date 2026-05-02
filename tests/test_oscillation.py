from __future__ import annotations

import unittest

from whetstone.identity import oscillation_fingerprint, oscillation_opposition_key
from whetstone.hashing import semantic_changes
from whetstone.oscillation import OscillationKeyError, OscillationTracker, canonicalize_phase2_feedback


class OscillationCanonicalizationTests(unittest.TestCase):
    def test_canonicalize_phase_2_feedback_computes_identity_fields(self) -> None:
        artifact = _artifact("spec-hashing")

        canonical = canonicalize_phase2_feedback(artifact, ["spec-hashing"])
        key = canonical["feedback"][0]["oscillation_key"]

        self.assertEqual(
            key["fingerprint"],
            oscillation_fingerprint("spec-hashing", "precision_gap", "clarify", "local"),
        )
        self.assertEqual(
            key["opposition_key"],
            oscillation_opposition_key("spec-hashing", "precision_gap", "local"),
        )
        self.assertNotIn("fingerprint", artifact["feedback"][0]["oscillation_key"])

    def test_canonicalize_phase_2_feedback_rejects_unknown_section_id(self) -> None:
        with self.assertRaises(OscillationKeyError):
            canonicalize_phase2_feedback(_artifact("made-up-section"), ["spec-hashing"])

    def test_tracker_detects_draft_cycle_after_real_change(self) -> None:
        tracker = OscillationTracker()
        first = "# Spec\n\nA.\n"
        second = "# Spec\n\nB.\n"

        self.assertIsNone(tracker.record_draft(round_number=0, draft_hash_value="a" * 64, semantic_changes=[]))
        self.assertIsNone(
            tracker.record_draft(
                round_number=1,
                draft_hash_value="b" * 64,
                semantic_changes=semantic_changes(first, second),
            )
        )
        detection = tracker.record_draft(
            round_number=2,
            draft_hash_value="a" * 64,
            semantic_changes=semantic_changes(second, first),
        )

        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertEqual(detection.oscillation_type, "cycle")
        self.assertEqual(detection.recommendation, "stop_iteration")

    def test_tracker_detects_mechanical_churn_without_stop(self) -> None:
        tracker = OscillationTracker()
        before = "# Spec\n\n"
        after = "# Spec\n\n## Added\n\nA.\n"

        tracker.record_draft(round_number=1, draft_hash_value="b" * 64, semantic_changes=semantic_changes(before, after))
        detection = tracker.record_draft(
            round_number=2,
            draft_hash_value="c" * 64,
            semantic_changes=semantic_changes(after, before),
        )

        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertEqual(detection.oscillation_type, "mechanical_churn")
        self.assertEqual(detection.recommendation, "freeze_prior_decision")

    def test_tracker_detects_feedback_flip_flop(self) -> None:
        tracker = OscillationTracker()
        tracker.record_phase2_feedback(
            round_number=1,
            reviewer_feedback=_artifact("spec-hashing", direction="add", severity="major", include_computed=True),
        )

        detection = tracker.record_phase2_feedback(
            round_number=2,
            reviewer_feedback=_artifact(
                "spec-hashing",
                direction="remove",
                severity="minor",
                feedback_id="fb-2",
                include_computed=True,
            ),
        )

        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertEqual(detection.oscillation_type, "feedback_flip_flop")
        self.assertEqual(detection.recommendation, "escalate_conflict")

    def test_tracker_detects_feedback_churn_after_three_cumulative_appearances(self) -> None:
        tracker = OscillationTracker()

        self.assertIsNone(
            tracker.record_phase2_feedback(
                round_number=1,
                reviewer_feedback=_artifact("spec-hashing", direction="clarify", include_computed=True),
            )
        )
        self.assertIsNone(
            tracker.record_phase2_feedback(
                round_number=2,
                reviewer_feedback=_artifact("spec-hashing", direction="clarify", feedback_id="fb-2", include_computed=True),
            )
        )
        detection = tracker.record_phase2_feedback(
            round_number=3,
            reviewer_feedback=_artifact("spec-hashing", direction="clarify", feedback_id="fb-3", include_computed=True),
        )

        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertEqual(detection.oscillation_type, "feedback_churn")
        self.assertEqual(detection.recommendation, "escalate_conflict")

    def test_tracker_detects_readdition_and_then_repeated_readdition_stop(self) -> None:
        tracker = OscillationTracker()

        self.assertIsNone(tracker.record_phase2_feedback(round_number=1, reviewer_feedback=_artifact("spec-hashing", include_computed=True)))
        self.assertIsNone(
            tracker.record_phase2_feedback(
                round_number=2,
                reviewer_feedback={**_artifact("spec-hashing", include_computed=True), "feedback": []},
            )
        )
        first = tracker.record_phase2_feedback(
            round_number=3,
            reviewer_feedback=_artifact("spec-hashing", feedback_id="fb-3", include_computed=True),
        )
        self.assertEqual(first.recommendation if first else None, "continue_once")
        self.assertIsNone(
            tracker.record_phase2_feedback(
                round_number=4,
                reviewer_feedback={**_artifact("spec-hashing", include_computed=True), "feedback": []},
            )
        )
        second = tracker.record_phase2_feedback(
            round_number=5,
            reviewer_feedback=_artifact("spec-hashing", feedback_id="fb-5", include_computed=True),
        )

        self.assertIsNotNone(second)
        assert second is not None
        self.assertEqual(second.recommendation, "stop_iteration")


def _artifact(
    section_id: str,
    *,
    direction: str = "clarify",
    severity: str = "minor",
    feedback_id: str = "fb-1",
    include_computed: bool = False,
) -> dict:
    fingerprint = oscillation_fingerprint(section_id, "precision_gap", direction, "local")
    opposition_key = oscillation_opposition_key(section_id, "precision_gap", "local")
    key = {
        "section_id": section_id,
        "concern_type": "precision_gap",
        "direction": direction,
        "scope": "local",
    }
    if include_computed:
        key["fingerprint"] = fingerprint
        key["opposition_key"] = opposition_key
    return {
        "round_number": 4,
        "profile": "convergence_strict_check",
        "reviewer": {"name": "fixture", "version": "0", "model": "fixture"},
        "draft_hash": "a" * 64,
        "feedback": [
            {
                "feedback_id": feedback_id,
                "issue_id": "iss_aaaaaaaaaaaaaaaa",
                "issue_fingerprint": "a" * 64,
                "issue_type": "undefined_behavior",
                "affected_sections": [section_id],
                "baseline_severity": severity,
                "authority_impact": None,
                "determinism_impact": None,
                "rubric_impact": None,
                "normalized_severity": severity,
                "invariant_violated": None,
                "claim": "Needs clarity.",
                "evidence": "Fixture.",
                "recommended_change": "Clarify it.",
                "in_scope": True,
                "severity_rationale": None,
                "oscillation_key": key,
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
