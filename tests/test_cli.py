from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import stat
import unittest

from whetstone.cli import main
from whetstone.hashing import draft_hash


class CliTests(unittest.TestCase):
    def test_codex_review_writes_schema_valid_output(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
            command = root / "codex"
            command.write_text(
                """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output-last-message" ]; then
    shift
    out="$1"
  fi
  shift
done
cat > /dev/null
cat > "$out" <<'JSON'
{"round_number":1,"profile":"determinism","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","feedback":[]}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)
            output = root / "reviewer_feedback.json"

            exit_code = main(
                [
                    "codex-review",
                    "--root",
                    str(root),
                    "--profile",
                    "determinism",
                    "--output",
                    str(output),
                    "--command",
                    str(command),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["profile"], "determinism")

    def test_codex_phase_2_review_writes_canonicalized_output(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.md").write_text("# Spec\n\n## Hashing\n", encoding="utf-8")
            command = root / "codex"
            command.write_text(
                """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output-last-message" ]; then
    shift
    out="$1"
  fi
  shift
done
cat > /dev/null
cat > "$out" <<'JSON'
{"round_number":4,"profile":"convergence_strict_check","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","feedback":[{"feedback_id":"fb-1","issue_id":"iss_aaaaaaaaaaaaaaaa","issue_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","issue_type":"undefined_behavior","affected_sections":["spec-hashing"],"baseline_severity":"minor","authority_impact":null,"determinism_impact":null,"rubric_impact":null,"normalized_severity":"minor","invariant_violated":null,"claim":"Needs clarity.","evidence":"Fixture.","recommended_change":"Clarify it.","in_scope":true,"severity_rationale":null,"oscillation_key":{"section_id":"spec-hashing","concern_type":"precision_gap","direction":"clarify","scope":"local"}}]}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)
            output = root / "reviewer_feedback.json"

            exit_code = main(
                [
                    "codex-review",
                    "--root",
                    str(root),
                    "--profile",
                    "convergence_strict_check",
                    "--phase",
                    "phase_2",
                    "--output",
                    str(output),
                    "--command",
                    str(command),
                ]
            )

            artifact = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertIn("fingerprint", artifact["feedback"][0]["oscillation_key"])
            self.assertIn("opposition_key", artifact["feedback"][0]["oscillation_key"])

    def test_reviewer_smoke_supports_claude_code_phase_2(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec.md").write_text("# Spec\n\n## Hashing\n", encoding="utf-8")
            command = root / "claude"
            command.write_text(
                """#!/bin/sh
cat <<'JSON'
{"round_number":4,"profile":"convergence_strict_check","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","feedback":[{"feedback_id":"fb-1","issue_id":"iss_aaaaaaaaaaaaaaaa","issue_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","issue_type":"undefined_behavior","affected_sections":["spec-hashing"],"baseline_severity":"minor","authority_impact":null,"determinism_impact":null,"rubric_impact":null,"normalized_severity":"minor","invariant_violated":null,"claim":"Needs clarity.","evidence":"Fixture.","recommended_change":"Clarify it.","in_scope":true,"severity_rationale":null,"oscillation_key":{"section_id":"spec-hashing","concern_type":"precision_gap","direction":"clarify","scope":"local"}}]}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)
            output = root / "reviewer_feedback.json"

            exit_code = main(
                [
                    "reviewer-smoke",
                    "--root",
                    str(root),
                    "--profile",
                    "convergence_strict_check",
                    "--phase",
                    "phase_2",
                    "--client",
                    "claude-code",
                    "--output",
                    str(output),
                    "--command",
                    str(command),
                ]
            )

            artifact = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertIn("fingerprint", artifact["feedback"][0]["oscillation_key"])

    def test_editor_smoke_writes_schema_valid_output_without_mutating_spec(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = "# Spec\n"
            (root / "spec.md").write_text(before, encoding="utf-8")
            reviewer_feedback = root / "reviewer_feedback.json"
            reviewer_feedback.write_text(
                '{"round_number":1,"profile":"fixture","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","feedback":[]}\n',
                encoding="utf-8",
            )
            command = root / "codex"
            command.write_text(
                """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output-last-message" ]; then
    shift
    out="$1"
  fi
  shift
done
cat > /dev/null
cat > "$out" <<'JSON'
{"round_number":1,"draft_before_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","draft_after_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","accepted_feedback_ids":[],"modified_feedback_ids":[],"declined_feedback":[],"created_conflict_ids":[],"resolved_issue_ids":[],"unresolved_issue_ids":[]}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)
            output = root / "editor_summary.json"

            exit_code = main(
                [
                    "editor-smoke",
                    "--root",
                    str(root),
                    "--reviewer-feedback",
                    str(reviewer_feedback),
                    "--output",
                    str(output),
                    "--command",
                    str(command),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), before)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["round_number"], 1)

    def test_live_round_uses_configured_reviewer_and_editor_roles(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = "# Spec\n\n## Hashing\n"
            root.joinpath("spec.md").write_text(spec, encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            spec_hash = draft_hash(spec)

            codex = root / "codex"
            codex.write_text(
                """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output-last-message" ]; then
    shift
    out="$1"
  fi
  shift
done
cat > /dev/null
cat > "$out" <<'JSON'
{"round_number":1,"profile":"convergence_strict_check","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"SPEC_HASH_PLACEHOLDER","feedback":[{"feedback_id":"fb-1","issue_id":"iss_aaaaaaaaaaaaaaaa","issue_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","issue_type":"precision_gap","affected_sections":["spec-hashing"],"baseline_severity":"minor","authority_impact":null,"determinism_impact":null,"rubric_impact":null,"normalized_severity":"minor","invariant_violated":null,"claim":"Needs clarity.","evidence":"Fixture.","recommended_change":"Clarify it.","in_scope":true,"severity_rationale":null,"oscillation_key":{"section_id":"spec-hashing","concern_type":"precision_gap","direction":"clarify","scope":"local"}}]}
JSON
""",
                encoding="utf-8",
            )
            codex.write_text(codex.read_text(encoding="utf-8").replace("SPEC_HASH_PLACEHOLDER", spec_hash), encoding="utf-8")
            codex.chmod(codex.stat().st_mode | stat.S_IXUSR)

            claude = root / "claude"
            claude.write_text(
                f"""#!/bin/sh
cat <<'JSON'
{{"type":"result","structured_output":{{"round_number":1,"draft_before_hash":"{spec_hash}","draft_after_hash":"{spec_hash}","accepted_feedback_ids":[],"modified_feedback_ids":[],"declined_feedback":[],"created_conflict_ids":[],"resolved_issue_ids":[],"unresolved_issue_ids":["iss_aaaaaaaaaaaaaaaa"]}}}}
JSON
""",
                encoding="utf-8",
            )
            claude.chmod(claude.stat().st_mode | stat.S_IXUSR)

            root.joinpath("orchestrator_config.yaml").write_text(
                f"""
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
clients:
  reviewer:
    name: codex
    command: {codex}
    version: "0"
    model: fixture
  editor:
    name: claude-code
    command: {claude}
    version: "0"
    model: fixture
convergence:
  enabled: true
  target_phase: final
  target_mode: strict
  rubric_path: ./convergence_rubric.md
  max_rounds: 8
""",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "live-round",
                    "--root",
                    str(root),
                    "--profile",
                    "convergence_strict_check",
                    "--phase",
                    "phase_2",
                ]
            )

            self.assertEqual(exit_code, 0)
            round_dir = root / "rounds" / "round-1"
            reviewer_feedback = json.loads(round_dir.joinpath("reviewer_feedback.json").read_text(encoding="utf-8"))
            self.assertIn("fingerprint", reviewer_feedback["feedback"][0]["oscillation_key"])
            editor_summary = json.loads(round_dir.joinpath("editor_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(editor_summary["draft_before_hash"], spec_hash)
            self.assertEqual(root.joinpath("spec.md").read_text(encoding="utf-8"), spec)

    def test_decision_scan_writes_register_for_before_after_pair(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = root / "before.md"
            after = root / "after.md"
            output_dir = root / "decision-scan"
            before.write_text("# Spec\n\n## Rules\n\n- Adapter MAY retry.\n", encoding="utf-8")
            after.write_text("# Spec\n\n## Rules\n\n- Adapter MUST retry.\n", encoding="utf-8")

            exit_code = main(
                [
                    "decision-scan",
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            register = json.loads((output_dir / "decision_register.json").read_text(encoding="utf-8"))
            self.assertEqual(register["mode"], "end_of_cycle")
            self.assertGreaterEqual(register["unresolved_human_decision_count"], 1)
            self.assertTrue((output_dir / "decision_register.md").exists())


if __name__ == "__main__":
    unittest.main()
