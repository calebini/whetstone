from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.artifacts import ArtifactStore


HASH = "a" * 64


class ArtifactStoreTests(unittest.TestCase):
    def test_round_dir_creation_refuses_overwrite_by_default(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ArtifactStore(root)

            first = store.round_dir(1, create=True)
            self.assertTrue(first.exists())
            with self.assertRaises(FileExistsError):
                store.round_dir(1, create=True)

    def test_write_round_json_validates_and_writes_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)
            store.begin_round(1)
            artifact = {
                "round_number": 1,
                "draft_hash": HASH,
                "unresolved_issues": [],
            }

            output = store.write_round_json(
                1,
                "unresolved_issues.json",
                artifact,
                schema_name="unresolved_issues",
            )

            self.assertEqual(output.name, "unresolved_issues.json")
            self.assertIn('"unresolved_issues": []', output.read_text(encoding="utf-8"))

    def test_append_history_appends_normalized_entry(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.history.md").write_text("# History\n", encoding="utf-8")
            store = ArtifactStore(root)

            store.append_history("- entry")

            self.assertEqual((root / "spec.history.md").read_text(encoding="utf-8"), "# History\n- entry\n")


if __name__ == "__main__":
    unittest.main()
