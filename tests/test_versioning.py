from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.hashing import draft_hash
from whetstone.versioning import promote_spec_file_for_phase2, promote_spec_text_for_phase2, promoted_phase2_version


class VersioningTests(unittest.TestCase):
    def test_promoted_phase2_version_rounds_up_to_whole_major(self) -> None:
        self.assertEqual(promoted_phase2_version("0.17"), "1.0")
        self.assertEqual(promoted_phase2_version("1.7"), "2.0")
        self.assertEqual(promoted_phase2_version("2.0"), "2.0")

    def test_promote_spec_text_updates_root_heading_only(self) -> None:
        draft = "# Whetstone (0.17 - STRICT CANDIDATE)\n\nVersion 0.17 in body.\n"

        promoted, before_version, after_version, changed = promote_spec_text_for_phase2(draft)

        self.assertTrue(changed)
        self.assertEqual(before_version, "0.17")
        self.assertEqual(after_version, "1.0")
        self.assertIn("# Whetstone (1.0 - STRICT CANDIDATE)", promoted)
        self.assertIn("Version 0.17 in body.", promoted)

    def test_promote_spec_file_requires_stable_phase1_gate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.md"
            history_path = root / "spec.history.md"
            rounds_dir = root / "rounds"
            rounds_dir.mkdir()
            spec_path.write_text("# Spec 0.17\n", encoding="utf-8")
            history_path.write_text("# History\n", encoding="utf-8")
            rounds_dir.joinpath("run_state.json").write_text(
                json.dumps({"terminal_state": None, "ready_for_phase_2": False}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                promote_spec_file_for_phase2(spec_path=spec_path, history_path=history_path, rounds_dir=rounds_dir)

    def test_promote_spec_file_updates_spec_history_and_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.md"
            history_path = root / "spec.history.md"
            rounds_dir = root / "rounds"
            rounds_dir.mkdir()
            spec = "# Spec 0.17\n"
            spec_path.write_text(spec, encoding="utf-8")
            history_path.write_text("# History\n", encoding="utf-8")
            before_hash = draft_hash(spec)
            rounds_dir.joinpath("run_state.json").write_text(
                json.dumps(
                    {
                        "terminal_state": "PHASE_1_STABLE",
                        "ready_for_phase_2": True,
                        "current_draft_hash": before_hash,
                        "last_accepted_draft_hash": before_hash,
                        "seen_draft_hashes": [before_hash],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = promote_spec_file_for_phase2(spec_path=spec_path, history_path=history_path, rounds_dir=rounds_dir)

            self.assertTrue(result.promoted)
            self.assertEqual(result.before_version, "0.17")
            self.assertEqual(result.after_version, "1.0")
            self.assertIn("# Spec 1.0", spec_path.read_text(encoding="utf-8"))
            self.assertIn("Phase 2 version promotion", history_path.read_text(encoding="utf-8"))
            state = json.loads(rounds_dir.joinpath("run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["current_draft_hash"], result.after_hash)
            self.assertEqual(state["last_accepted_draft_hash"], result.after_hash)


if __name__ == "__main__":
    unittest.main()

