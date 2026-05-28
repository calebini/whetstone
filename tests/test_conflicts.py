from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.conflicts import ConflictTracker, normalize_conflict, read_conflict_state


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

    def test_absent_round_resets_consecutive_count_but_preserves_total(self) -> None:
        tracker = ConflictTracker()

        tracker.record_round(round_number=1, conflicts=[CONFLICT])
        tracker.record_round(round_number=2, conflicts=[])
        escalation = tracker.record_round(round_number=3, conflicts=[CONFLICT])
        snapshot = tracker.snapshot(round_number=3)

        self.assertIsNone(escalation)
        self.assertEqual(snapshot["conflicts"][0]["state"], "present")
        self.assertEqual(snapshot["conflicts"][0]["consecutive_present_rounds"], 1)
        self.assertEqual(snapshot["conflicts"][0]["total_present_rounds"], 2)

    def test_conflict_state_round_trips_and_preserves_escalation_counters(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rounds" / "conflict_state.json"
            tracker = ConflictTracker()
            tracker.record_round(round_number=1, conflicts=[CONFLICT])
            tracker.record_round(round_number=2, conflicts=[])
            tracker.write_snapshot(path, round_number=2)

            resumed = read_conflict_state(path)
            assert resumed is not None
            resumed.record_round(round_number=3, conflicts=[CONFLICT])
            escalation = resumed.record_round(round_number=5, conflicts=[CONFLICT])

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
