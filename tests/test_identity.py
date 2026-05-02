from __future__ import annotations

import unittest

from whetstone.identity import (
    conflict_fingerprint,
    conflict_id,
    issue_fingerprint,
    issue_id,
    normalize_severity,
    oscillation_fingerprint,
    oscillation_opposition_key,
    rubric_gap_fingerprint,
    rubric_gap_id,
)


class IdentityTests(unittest.TestCase):
    def test_normalize_severity_uses_highest_component_and_all_null_is_nit(self) -> None:
        self.assertEqual(normalize_severity(None, None), "nit")
        self.assertEqual(normalize_severity("minor", "blocker", "major"), "blocker")

    def test_issue_identity_is_stable_under_whitespace_and_case(self) -> None:
        first = issue_fingerprint("Undefined_Behavior", ["State Machine"], "Invariant", "Bad transition")
        second = issue_fingerprint(" undefined_behavior ", ["State   Machine"], " invariant ", "Bad   transition")

        self.assertEqual(first, second)
        self.assertRegex(issue_id(first), r"^iss_[a-f0-9]{16}$")

    def test_conflict_identity_sorts_participating_issue_fingerprints(self) -> None:
        first = conflict_fingerprint("profile_conflict", ["b" * 64, "a" * 64], "Profiles disagree")
        second = conflict_fingerprint("profile_conflict", ["a" * 64, "b" * 64], "Profiles disagree")

        self.assertEqual(first, second)
        self.assertRegex(conflict_id(first), r"^con_[a-f0-9]{16}$")

    def test_oscillation_identity_uses_classification_not_prose(self) -> None:
        add = oscillation_fingerprint("Hashing", "precision_gap", "add", "local")
        add_again = oscillation_fingerprint(" hashing ", "precision_gap", "add", "local")
        remove = oscillation_fingerprint("Hashing", "precision_gap", "remove", "local")
        add_key = oscillation_opposition_key("Hashing", "precision_gap", "local")
        remove_key = oscillation_opposition_key("Hashing", "precision_gap", "local")

        self.assertEqual(add, add_again)
        self.assertNotEqual(add, remove)
        self.assertEqual(add_key, remove_key)

    def test_rubric_gap_identity_is_stable_under_whitespace_and_case(self) -> None:
        first = rubric_gap_fingerprint("Final Strict", ["Target Matrix"], "Missing gap rule")
        second = rubric_gap_fingerprint(" final   strict ", [" target matrix "], "Missing   gap rule")

        self.assertEqual(first, second)
        self.assertRegex(rubric_gap_id(first), r"^gap_[a-f0-9]{16}$")


if __name__ == "__main__":
    unittest.main()
