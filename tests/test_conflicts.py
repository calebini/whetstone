from __future__ import annotations

import unittest

from whetstone.conflicts import ConflictTracker, normalize_conflict


CONFLICT = {
    "conflict_id": "con_bbbbbbbbbbbbbbbb",
    "conflict_fingerprint": "b" * 64,
    "conflict_type": "profile_conflict",
    "conflict_severity": "minor",
    "participating_issue_ids": ["iss_aaaaaaaaaaaaaaaa"],
    "conflict_claim": "Profiles disagree.",
}


class ConflictTrackerTests(unittest.TestCase):
    def test_consecutive_conflict_escalates_on_second_round(self) -> None:
        tracker = ConflictTracker()

        self.assertIsNone(tracker.record_round(round_number=1, conflicts=[CONFLICT]))
        escalation = tracker.record_round(round_number=2, conflicts=[CONFLICT])

        self.assertIsNotNone(escalation)
        assert escalation is not None
        self.assertFalse(escalation.blocker_level)
        self.assertIn("2 consecutive rounds", escalation.reason)

    def test_nonconsecutive_conflict_escalates_on_third_appearance(self) -> None:
        tracker = ConflictTracker()

        self.assertIsNone(tracker.record_round(round_number=1, conflicts=[CONFLICT]))
        self.assertIsNone(tracker.record_round(round_number=3, conflicts=[CONFLICT]))
        escalation = tracker.record_round(round_number=5, conflicts=[CONFLICT])

        self.assertIsNotNone(escalation)
        assert escalation is not None
        self.assertIn("3 times non-consecutively", escalation.reason)

    def test_conflict_severity_is_computed_from_participating_issues_when_available(self) -> None:
        normalized = normalize_conflict(
            CONFLICT,
            {
                "iss_aaaaaaaaaaaaaaaa": {
                    "issue_id": "iss_aaaaaaaaaaaaaaaa",
                    "normalized_severity": "blocker",
                }
            },
        )

        self.assertEqual(normalized["conflict_severity"], "blocker")


if __name__ == "__main__":
    unittest.main()

