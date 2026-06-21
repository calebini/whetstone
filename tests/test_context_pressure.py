from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.config import OrchestratorConfig, load_config
from whetstone.context_pressure import (
    build_context_pressure_report,
    build_round_context_pressure_report,
    write_context_pressure_report,
)
from whetstone.contracts import validate_artifact
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.status import read_status, render_status_text

from tests.test_live_phase1 import ScriptedReviewerClient


class ContextPressureTests(unittest.TestCase):
    def test_builds_valid_report_for_configured_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\nMUST do one thing.\n", encoding="utf-8")
            root.joinpath("reference.md").write_text("# Reference\n\nSupporting context.\n", encoding="utf-8")
            root.joinpath("whetstone.yaml").write_text(
                "\n".join(
                    [
                        "workflow: standard",
                        "reference_context:",
                        "  files:",
                        "    hld:",
                        "      path: reference.md",
                        "      role: authority_reference",
                        "      required: true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config = load_config(root / "whetstone.yaml")

            report = build_context_pressure_report(root=root, config=config, phase="phase_1", round_number=0)

            validate_artifact(report, "context_pressure_report")
            self.assertEqual(report["behavior"], "observability_only")
            self.assertEqual(report["action_taken"], "none")
            self.assertEqual(report["totals"]["reference_context_count"], 1)
            self.assertGreater(report["totals"]["estimated_tokens"], 0)
            self.assertIn("hld", {component["label"] for component in report["components"]})

    def test_round_report_marks_reviewer_cited_reference_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_dir = root / "rounds" / "round-1" / "context"
            context_dir.mkdir(parents=True)
            reference_path = context_dir / "reference_ontology.md"
            reference_path.write_text("# Ontology\n\nCanonical rows.\n", encoding="utf-8")

            report = build_round_context_pressure_report(
                root=root,
                phase="phase_1",
                round_number=1,
                profile="buildability",
                context_files=[
                    {
                        "label": "reference:ontology",
                        "path": "rounds/round-1/context/reference_ontology.md",
                        "sha256": "a" * 64,
                    }
                ],
                reviewer_feedback={
                    "feedback": [
                        {
                            "feedback_id": "fb-ontology-gap",
                            "affected_sections": ["reference_ontology.md §4.1", "draft_before.md §7"],
                            "claim": "The ontology reference is required to resolve this.",
                        }
                    ]
                },
            )

            validate_artifact(report, "context_pressure_report")
            referenced = report["referenced_context"]["references"]
            self.assertEqual(len(referenced), 1)
            self.assertEqual(referenced[0]["label"], "reference:ontology")
            self.assertEqual(referenced[0]["source_feedback_ids"], ["fb-ontology-gap"])

    def test_status_surfaces_written_context_pressure_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\nMUST do one thing.\n", encoding="utf-8")
            config = OrchestratorConfig.default(root)

            write_context_pressure_report(root=root, config=config, phase="phase_1", round_number=0)
            status = read_status(root=root, config=config)
            rendered = render_status_text(status)

            self.assertIsNotNone(status["context_pressure"])
            self.assertEqual(status["context_pressure"]["path"], "rounds/context_pressure_report.json")
            self.assertEqual(status["context_pressure"]["action_taken"], "none")
            self.assertIn("context_pressure:", rendered)
            self.assertIn("action=none", rendered)

    def test_live_phase1_writes_context_pressure_artifacts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n\nMUST be buildable.\n", encoding="utf-8")
            reviewer = ScriptedReviewerClient(root, [None])

            result = LivePhase1Runner(
                root,
                OrchestratorConfig.default(root),
                reviewer_client=reviewer,
            ).run(overwrite=True)

            self.assertEqual(result.terminal_state, "PHASE_1_STABLE")
            report_path = root / "rounds" / "context_pressure_report.json"
            markdown_path = root / "rounds" / "context_pressure_report.md"
            self.assertTrue(report_path.exists())
            self.assertTrue(markdown_path.exists())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["phase"], "phase_1")
            self.assertEqual(report["action_taken"], "none")
            round_report_path = root / "rounds" / "round-1" / "context_pressure_report.json"
            self.assertTrue(round_report_path.exists())
            status = read_status(root=root, config=OrchestratorConfig.default(root))
            self.assertEqual(status["round_context_pressure"]["round_report_count"], result.round_number)
            self.assertEqual(status["round_context_pressure"]["latest"]["round_number"], result.round_number)


if __name__ == "__main__":
    unittest.main()
