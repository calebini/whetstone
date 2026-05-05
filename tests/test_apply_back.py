from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.apply_back import apply_back
from whetstone.hashing import draft_hash


class ApplyBackTests(unittest.TestCase):
    def test_dry_run_writes_review_without_mutating_source(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec 0.1\n\nBefore.\n", encoding="utf-8")
            run_root.joinpath("spec.md").write_text("# Spec 1.0\n\nAfter.\n", encoding="utf-8")
            run_root.joinpath("convergence_declaration.md").write_text("# Declaration\n", encoding="utf-8")

            result = apply_back(source_path=source, run_root=run_root)

            self.assertFalse(result.applied)
            self.assertTrue(result.changed)
            self.assertEqual(source.read_text(encoding="utf-8"), "# Spec 0.1\n\nBefore.\n")
            report = json.loads((run_root / "rounds" / "apply_back_review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "dry_run")
            self.assertTrue(report["declaration_included"])
            self.assertIsNone(report["terminal_state"])
            self.assertFalse(report["eligible_terminal_state"])
            markdown = run_root.joinpath("rounds/apply_back_review.md").read_text(encoding="utf-8")
            self.assertIn("-Before.", markdown)
            self.assertIn("+After.", markdown)
            self.assertNotIn("# Declaration", markdown)

    def test_apply_requires_explicit_approval(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            run_root.joinpath("spec.md").write_text("# Spec\n\nAfter.\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                apply_back(source_path=source, run_root=run_root, apply=True, allow_non_converged=True)

            self.assertEqual(source.read_text(encoding="utf-8"), "# Spec\n\nBefore.\n")

    def test_apply_requires_converged_run_by_default(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            final_text = "# Spec\n\nAfter.\n"
            run_root.joinpath("spec.md").write_text(final_text, encoding="utf-8")
            _write_run_state(run_root, terminal_state="TARGET_NOT_REACHED", current_draft_hash=draft_hash(final_text))

            with self.assertRaises(ValueError):
                apply_back(source_path=source, run_root=run_root, apply=True, approve=True)

            self.assertEqual(source.read_text(encoding="utf-8"), "# Spec\n\nBefore.\n")

    def test_apply_updates_only_source_spec_when_approved(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            sibling = root / "sibling.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            sibling.write_text("untouched\n", encoding="utf-8")
            final_text = "# Spec\n\nAfter.\n"
            run_root.joinpath("spec.md").write_text(final_text, encoding="utf-8")
            _write_run_state(run_root, terminal_state="CONVERGED", current_draft_hash=draft_hash(final_text))

            result = apply_back(source_path=source, run_root=run_root, apply=True, approve=True)

            self.assertTrue(result.applied)
            self.assertEqual(source.read_text(encoding="utf-8"), final_text)
            self.assertEqual(sibling.read_text(encoding="utf-8"), "untouched\n")
            report = json.loads(run_root.joinpath("rounds/apply_back_review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "apply")
            self.assertTrue(report["applied"])
            self.assertEqual(report["source_after_hash"], draft_hash(final_text))
            self.assertEqual(report["terminal_state"], "CONVERGED")
            self.assertTrue(report["eligible_terminal_state"])
            self.assertTrue(report["final_draft_matches_run_state"])

    def test_apply_refuses_when_final_draft_hash_does_not_match_run_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            run_root.joinpath("spec.md").write_text("# Spec\n\nAfter.\n", encoding="utf-8")
            _write_run_state(run_root, terminal_state="CONVERGED", current_draft_hash="a" * 64)

            with self.assertRaises(ValueError):
                apply_back(source_path=source, run_root=run_root, apply=True, approve=True)

            self.assertEqual(source.read_text(encoding="utf-8"), "# Spec\n\nBefore.\n")

    def test_expected_source_hash_mismatch_refuses_apply(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            run_root.joinpath("spec.md").write_text("# Spec\n\nAfter.\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                apply_back(source_path=source, run_root=run_root, expected_source_hash="a" * 64)

            self.assertFalse(run_root.joinpath("rounds/apply_back_review.json").exists())

    def test_expected_source_hash_mismatch_can_be_explicitly_allowed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            run_root.joinpath("spec.md").write_text("# Spec\n\nAfter.\n", encoding="utf-8")

            apply_back(
                source_path=source,
                run_root=run_root,
                expected_source_hash="a" * 64,
                allow_source_hash_mismatch=True,
            )

            report = json.loads(run_root.joinpath("rounds/apply_back_review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["expected_source_hash"], "a" * 64)
            self.assertTrue(report["source_hash_mismatch_allowed"])

    def test_falls_back_to_run_state_round_draft_after(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            round_dir = run_root / "rounds" / "round-3"
            round_dir.mkdir(parents=True)
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            final_text = "# Spec\n\nAfter.\n"
            round_dir.joinpath("draft_after.md").write_text(final_text, encoding="utf-8")
            run_root.joinpath("rounds/run_state.json").write_text('{"current_round": 3}\n', encoding="utf-8")

            result = apply_back(source_path=source, run_root=run_root)

            self.assertEqual(result.final_draft_path, round_dir / "draft_after.md")

    def test_latest_round_fallback_sorts_rounds_numerically(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            round_9 = run_root / "rounds" / "round-9"
            round_10 = run_root / "rounds" / "round-10"
            round_9.mkdir(parents=True)
            round_10.mkdir(parents=True)
            round_9.joinpath("draft_after.md").write_text("# Spec\n\nRound 9.\n", encoding="utf-8")
            round_10.joinpath("draft_after.md").write_text("# Spec\n\nRound 10.\n", encoding="utf-8")

            result = apply_back(source_path=source, run_root=run_root)

            self.assertEqual(result.final_draft_path, round_10 / "draft_after.md")


def _write_run_state(run_root: Path, *, terminal_state: str, current_draft_hash: str) -> None:
    rounds_dir = run_root / "rounds"
    rounds_dir.mkdir(exist_ok=True)
    rounds_dir.joinpath("run_state.json").write_text(
        json.dumps(
            {
                "current_round": 6,
                "phase": "phase_2",
                "current_draft_hash": current_draft_hash,
                "terminal_state": terminal_state,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
