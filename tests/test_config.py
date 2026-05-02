from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_file_is_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            config = load_config(Path(tmp) / "orchestrator_config.yaml")

            self.assertEqual(config.spec_path, Path(tmp) / "spec.md")
            self.assertEqual(config.reviewer.name, "fixture-reviewer")
            self.assertEqual(config.convergence.target_mode, "strict")

    def test_load_config_parses_project_yaml_subset(self) -> None:
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "orchestrator_config.yaml"
            config_path.write_text(
                """
spec_path: ./custom-spec.md
history_path: ./history.md
rounds_dir: ./out
declaration_path: ./decl.md
clients:
  editor:
    name: claude-code
    command: claude
    version: "1.2.3"
    model: opus-fixture
  reviewer:
    name: codex
    command: codex
    version: "4.5.6"
    model: gpt-fixture
review:
  max_rounds: 3
convergence:
  enabled: true
  target_phase: mid
  target_mode: permissive
  rubric_path: ./rubric.md
  max_rounds: 2
decision_points:
  enabled: true
  mode: intervention
  intervention_thresholds:
    severities: [major]
    trigger_on_requirement_strength_change: false
""".strip(),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.spec_path, Path(tmp) / "custom-spec.md")
            self.assertEqual(config.editor.version, "1.2.3")
            self.assertEqual(config.reviewer.model, "gpt-fixture")
            self.assertEqual(config.review_max_rounds, 3)
            self.assertEqual(config.convergence.target_phase, "mid")
            self.assertEqual(config.decision_points.mode, "intervention")
            self.assertEqual(config.decision_points.severities, ("major",))
            self.assertFalse(config.decision_points.trigger_on_requirement_strength_change)


if __name__ == "__main__":
    unittest.main()
