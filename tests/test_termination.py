from __future__ import annotations

import unittest

from whetstone.termination import TerminationCandidate, select_terminal_candidate


class TerminationTests(unittest.TestCase):
    def test_clean_convergence_beats_blocker_conflict(self) -> None:
        selected = select_terminal_candidate(
            [
                TerminationCandidate("HALTED_CONFLICT", 3, "phase_2"),
                TerminationCandidate("CONVERGED", 3, "phase_2"),
            ]
        )

        self.assertEqual(selected.terminal_state if selected else None, "CONVERGED")

    def test_blocker_conflict_beats_oscillation_stop(self) -> None:
        selected = select_terminal_candidate(
            [
                TerminationCandidate("HALTED_OSCILLATION", 3, "phase_2"),
                TerminationCandidate("HALTED_CONFLICT", 3, "phase_2"),
            ]
        )

        self.assertEqual(selected.terminal_state if selected else None, "HALTED_CONFLICT")

    def test_oscillation_stop_beats_max_rounds(self) -> None:
        selected = select_terminal_candidate(
            [
                TerminationCandidate("TARGET_NOT_REACHED", 3, "phase_2"),
                TerminationCandidate("HALTED_OSCILLATION", 3, "phase_2"),
            ]
        )

        self.assertEqual(selected.terminal_state if selected else None, "HALTED_OSCILLATION")


if __name__ == "__main__":
    unittest.main()

