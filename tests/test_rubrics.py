from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import ConvergenceConfig, OrchestratorConfig
from whetstone.hashing import rubric_content_hash
from whetstone.rubrics import build_rubric_manifest, read_rubric_text, write_rubric_manifest


class RubricManifestTests(unittest.TestCase):
    def test_builtin_manifest_uses_packaged_content_hash(self) -> None:
        with TemporaryDirectory() as tmp:
            config = OrchestratorConfig.default(Path(tmp))

            manifest = build_rubric_manifest(config)

            self.assertEqual(manifest.packet["workflow"], "standard")
            self.assertEqual(manifest.packet["rubric_profile"], "standard-v1")
            self.assertEqual(manifest.packet["rubric_source"], "builtin")
            self.assertEqual(manifest.packet["resolved_defaults"]["convergence_max_rounds"], 8)
            self.assertEqual(manifest.packet["configured_budgets"]["review_max_rounds"], config.review_max_rounds)
            self.assertEqual(manifest.packet["configured_budgets"]["convergence_max_rounds"], config.convergence.max_rounds)
            self.assertEqual(manifest.packet["rubric_content_hash"], rubric_content_hash(read_rubric_text(config) or ""))

    def test_workflow_rubric_mismatch_is_visible_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            config = OrchestratorConfig.default(Path(tmp))
            governance_config = replace(
                config,
                workflow="mvp",
                convergence=replace(config.convergence, rubric_profile="governance-v6"),
            )

            manifest = build_rubric_manifest(governance_config)

            self.assertEqual(manifest.packet["workflow"], "mvp")
            self.assertEqual(manifest.packet["rubric_profile"], "governance-v6")
            self.assertTrue(any("default rubric" in warning for warning in manifest.packet["warnings"]))

    def test_custom_rubric_requires_label(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rubric_path = root / "soft.md"
            rubric_path.write_text("# Soft Rubric\n", encoding="utf-8")
            config = OrchestratorConfig.default(root)
            custom_config = replace(
                config,
                workflow="custom",
                convergence=ConvergenceConfig(
                    enabled=True,
                    target_phase="final",
                    target_mode="strict",
                    rubric_profile="custom",
                    rubric_source="custom",
                    rubric_label=None,
                    rubric_path=rubric_path,
                    max_rounds=8,
                ),
            )

            with self.assertRaisesRegex(ValueError, "rubric_label"):
                build_rubric_manifest(custom_config)

    def test_write_manifest_persists_custom_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rubric_path = root / "soft.md"
            rubric_path.write_text("# Soft Rubric\n", encoding="utf-8")
            config = replace(
                OrchestratorConfig.default(root),
                workflow="custom",
                convergence=ConvergenceConfig(
                    enabled=True,
                    target_phase="final",
                    target_mode="strict",
                    rubric_profile="custom",
                    rubric_source="custom",
                    rubric_label="approval-soft-observation",
                    rubric_path=rubric_path,
                    max_rounds=8,
                ),
            )

            manifest = write_rubric_manifest(config)
            packet = json.loads(manifest.path.read_text(encoding="utf-8"))

            self.assertEqual(packet["rubric_source"], "custom")
            self.assertEqual(packet["rubric_label"], "approval-soft-observation")
            self.assertTrue(packet["warnings"])


if __name__ == "__main__":
    unittest.main()
