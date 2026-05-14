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
            self.assertEqual(config.workflow, "standard")
            self.assertEqual(config.convergence.rubric_profile, "standard-v1")
            self.assertEqual(config.convergence.rubric_source, "builtin")
            self.assertEqual(config.convergence.target_mode, "strict")
            self.assertEqual(config.review_budget_exhaustion_policy, "hard")
            self.assertEqual(config.timeouts.reviewer_seconds, 360)
            self.assertEqual(config.timeouts.editor_seconds, 900)
            self.assertTrue(config.contract_surface.enabled)
            self.assertEqual(config.contract_surface.action, "recommend_synthesis")
            self.assertEqual(config.scope_contract.path, Path(tmp) / "rounds" / "intake" / "scope_contract.json")
            self.assertEqual(config.reference_context_files, ())

    def test_load_config_parses_project_yaml_subset(self) -> None:
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "orchestrator_config.yaml"
            config_path.write_text(
                """
spec_path: ./custom-spec.md
history_path: ./history.md
rounds_dir: ./out
declaration_path: ./decl.md
workflow: governance
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
  mode: vertical
  profile_set: utility_mvp
  budget_exhaustion_policy: soft
  profile_budgets:
    structural_integrity: 4
    determinism: 5
convergence:
  enabled: true
  target_phase: mid
  target_mode: permissive
  rubric_profile: governance-v6
  rubric_source: builtin
  rubric_path: ./rubric.md
  max_rounds: 2
  profile_budgets:
    convergence_strict_check: 6
    adversarial: 2
decision_points:
  enabled: true
  mode: intervention
  intervention_thresholds:
    severities: [major]
    trigger_on_requirement_strength_change: false
timeouts:
  reviewer_seconds: 120
  editor_seconds: 900
contract_surface_policy:
  enabled: true
  action: report_only
  min_profile_rounds: 3
  recent_window: 5
  min_recent_serious_rounds: 2
  min_contract_families: 4
scope_contract:
  path: ./intake/scope.json
reference_context:
  files:
    parley_hld:
      path: ./docs/hld-architecture.md
      role: architecture_authority
      required: true
    notes: ./docs/notes.md
""".strip(),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.spec_path, Path(tmp) / "custom-spec.md")
            self.assertEqual(config.editor.version, "1.2.3")
            self.assertEqual(config.reviewer.model, "gpt-fixture")
            self.assertEqual(config.review_max_rounds, 3)
            self.assertEqual(config.review_mode, "vertical")
            self.assertEqual(config.review_profile_set, "utility_mvp")
            self.assertEqual(config.review_budget_exhaustion_policy, "soft")
            self.assertEqual(config.review_profile_budgets["structural_integrity"], 4)
            self.assertEqual(config.review_profile_budgets["determinism"], 5)
            self.assertEqual(config.workflow, "governance")
            self.assertEqual(config.convergence.target_phase, "mid")
            self.assertEqual(config.convergence.rubric_profile, "governance-v6")
            self.assertEqual(config.convergence_profile_budgets["convergence_strict_check"], 6)
            self.assertEqual(config.convergence_profile_budgets["adversarial"], 2)
            self.assertEqual(config.decision_points.mode, "intervention")
            self.assertEqual(config.decision_points.severities, ("major",))
            self.assertFalse(config.decision_points.trigger_on_requirement_strength_change)
            self.assertEqual(config.timeouts.reviewer_seconds, 120)
            self.assertEqual(config.timeouts.editor_seconds, 900)
            self.assertEqual(config.contract_surface.action, "report_only")
            self.assertEqual(config.contract_surface.min_profile_rounds, 3)
            self.assertEqual(config.contract_surface.recent_window, 5)
            self.assertEqual(config.contract_surface.min_recent_serious_rounds, 2)
            self.assertEqual(config.contract_surface.min_contract_families, 4)
            self.assertEqual(config.scope_contract.path, Path(tmp) / "intake" / "scope.json")
            self.assertEqual(len(config.reference_context_files), 2)
            self.assertEqual(config.reference_context_files[0].label, "parley_hld")
            self.assertEqual(config.reference_context_files[0].path, Path(tmp) / "docs/hld-architecture.md")
            self.assertEqual(config.reference_context_files[0].role, "architecture_authority")
            self.assertTrue(config.reference_context_files[0].required)
            self.assertEqual(config.reference_context_files[1].label, "notes")
            self.assertEqual(config.reference_context_files[1].role, "reference_context")


if __name__ == "__main__":
    unittest.main()
