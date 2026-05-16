from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import stat
import unittest

from whetstone.cli import main
from whetstone.hashing import draft_hash
from whetstone.scope import render_mvp_scope_notes_template, scope_contract_from_notes, write_scope_contract


class CliTests(unittest.TestCase):
    def test_resume_help_includes_recovery_examples(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["resume", "--help"])

        self.assertEqual(raised.exception.code, 0)
        rendered = output.getvalue()
        self.assertIn("whetstone resume --root \"$RUN_ROOT\" --dry-run --continue", rendered)
        self.assertIn("whetstone resume --root \"$RUN_ROOT\" --extend-review-budget 3", rendered)
        self.assertIn("Phase 1 Editor timeouts, or explicit Phase 1 budget extension", rendered)

    def test_live_focused_phase1_help_explains_targeted_rechecks(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["live-focused-phase1", "--help"])

        self.assertEqual(raised.exception.code, 0)
        rendered = output.getvalue()
        self.assertIn("focused Phase 1 mini-run", rendered)
        self.assertIn("--profile", rendered)
        self.assertIn("--budget", rendered)

    def test_apply_back_help_marks_dangerous_flags(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["apply-back", "--help"])

        self.assertEqual(raised.exception.code, 0)
        rendered = output.getvalue()
        self.assertIn("Run without --apply first", rendered)
        self.assertIn("danger: continue when --expected-source-hash", rendered)
        self.assertIn("danger: allow writing back from a non-CONVERGED run", rendered)

    def test_strop_help_marks_preferred_apply_back_alias(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["strop", "--help"])

        self.assertEqual(raised.exception.code, 0)
        rendered = output.getvalue()
        self.assertIn("Preferred operator command", rendered)
        self.assertIn("whetstone strop --source", rendered)
        self.assertIn("Run without --apply first", rendered)

    def test_intake_template_and_from_notes_create_scope_contract(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "scope-notes.md"

            template_stdout = io.StringIO()
            with redirect_stdout(template_stdout):
                template_exit = main(["intake", "--root", str(root), "--template", "mvp", "--output", str(notes)])

            self.assertEqual(template_exit, 0)
            self.assertIn("Core Outcome", notes.read_text(encoding="utf-8"))

            contract_stdout = io.StringIO()
            with redirect_stdout(contract_stdout):
                contract_exit = main(["intake", "--root", str(root), "--from-notes", str(notes), "--approve"])

            self.assertEqual(contract_exit, 0)
            packet = json.loads(root.joinpath("rounds/intake/scope_contract.json").read_text(encoding="utf-8"))
            self.assertTrue(packet["approval"]["approved"])
            self.assertEqual(packet["readiness_target"], "mvp")
            self.assertEqual(json.loads(contract_stdout.getvalue())["status"], "approved")

    def test_decompose_plan_inventory_writes_no_split_artifacts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / "spec.md"
            spec.write_text(
                "\n".join(
                    [
                        "# Spec",
                        "",
                        "## Purpose",
                        "The tool MUST keep source text.",
                        "",
                        "## Schema",
                        "The schema SHOULD be explicit.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            output_dir = root / "decomposition"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["decompose", "plan", "--source", str(spec), "--output-dir", str(output_dir)])

            self.assertEqual(exit_code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["planning_mode"], "inventory_only")
            self.assertEqual(result["authority_topology"], "no_split")
            self.assertEqual(result["target_spec_count"], 1)
            self.assertEqual(result["unassigned_source_section_count"], 0)
            plan = json.loads(output_dir.joinpath("decomposition_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["coverage"]["source_section_count"], 2)
            self.assertEqual(plan["target_specs"][0]["target_spec_id"], "source_spec")
            self.assertEqual(plan["target_specs"][0]["normative_statement_count"], 2)
            self.assertTrue(output_dir.joinpath("decomposition_plan.md").exists())
            self.assertFalse(output_dir.joinpath("docs").exists())

    def test_decompose_plan_with_map_writes_proposed_split(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / "spec.md"
            spec.write_text(
                "\n".join(
                    [
                        "# Spec",
                        "",
                        "## Purpose",
                        "The tool MUST keep source text.",
                        "",
                        "## Schema",
                        "The schema MUST be explicit.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            source_hash = draft_hash(spec.read_text(encoding="utf-8"))
            purpose_id = "spec-purpose"
            schema_id = "spec-schema"
            map_path = root / "map.json"
            map_path.write_text(
                json.dumps(
                    {
                        "planning_mode": "proposed_split",
                        "authority_topology": "coordinated_family",
                        "source_spec_hash": source_hash,
                        "target_specs": [
                            {
                                "target_spec_id": "coordinator",
                                "target_spec_path": "docs/COORDINATING_SPEC.md",
                                "target_spec_role": "coordinating_spec",
                                "owned_authority_surfaces": ["orientation"],
                                "source_section_ids": [purpose_id],
                            },
                            {
                                "target_spec_id": "schema",
                                "target_spec_path": "docs/SCHEMA_SPEC.md",
                                "target_spec_role": "leaf_spec",
                                "owned_authority_surfaces": ["schema"],
                                "source_section_ids": [schema_id],
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            output_dir = root / "decomposition"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "decompose",
                        "plan",
                        "--source",
                        str(spec),
                        "--map",
                        str(map_path),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["source_spec_hash"], source_hash)
            self.assertEqual(result["planning_mode"], "proposed_split")
            self.assertEqual(result["authority_topology"], "coordinated_family")
            plan = json.loads(output_dir.joinpath("decomposition_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(len(plan["target_specs"]), 2)
            self.assertEqual(plan["coverage"]["unassigned_source_section_ids"], [])
            self.assertEqual(plan["target_specs"][1]["source_line_ranges"][0]["section_id"], schema_id)

    def test_decompose_plan_rejects_map_source_hash_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / "spec.md"
            spec.write_text("# Spec\n\n## Purpose\nThe tool MUST keep source text.\n", encoding="utf-8")
            map_path = root / "map.json"
            map_path.write_text(
                json.dumps(
                    {
                        "planning_mode": "proposed_split",
                        "authority_topology": "peer_family",
                        "source_spec_hash": "0" * 64,
                        "target_specs": [
                            {
                                "target_spec_id": "purpose",
                                "target_spec_path": "docs/PURPOSE.md",
                                "target_spec_role": "peer_spec",
                                "owned_authority_surfaces": ["purpose"],
                                "source_section_ids": ["spec-purpose"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "source_spec_hash does not match"):
                main(["decompose", "plan", "--source", str(spec), "--map", str(map_path), "--output-dir", str(root / "out")])

    def test_mvp_live_phase1_requires_approved_scope_contract(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            root.joinpath("orchestrator_config.yaml").write_text(
                """
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
workflow: mvp
clients:
  reviewer:
    name: fixture-reviewer
    command: fixture
    version: "0"
    model: fixture
  editor:
    name: fixture-editor
    command: fixture
    version: "0"
    model: fixture
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                main(["live-phase1", "--root", str(root)])

            error = json.loads(root.joinpath("rounds/config_validation_error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["terminal_state"], "CONFIG_INVALID")
            self.assertIn("MVP workflow requires an approved scope contract", error["invalid_fields"][0]["reason"])

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

    def test_apply_back_dry_run_cli_writes_review_without_mutating_source(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            run_root.joinpath("spec.md").write_text("# Spec\n\nAfter.\n", encoding="utf-8")

            exit_code = main(["apply-back", "--source", str(source), "--run-root", str(run_root)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(source.read_text(encoding="utf-8"), "# Spec\n\nBefore.\n")
            report = json.loads(run_root.joinpath("rounds/apply_back_review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "dry_run")
            self.assertFalse(report["applied"])

    def test_strop_dry_run_cli_writes_review_without_mutating_source(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            run_root.joinpath("spec.md").write_text("# Spec\n\nAfter.\n", encoding="utf-8")

            exit_code = main(["strop", "--source", str(source), "--run-root", str(run_root)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(source.read_text(encoding="utf-8"), "# Spec\n\nBefore.\n")
            report = json.loads(run_root.joinpath("rounds/apply_back_review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "dry_run")
            self.assertFalse(report["applied"])

    def test_apply_back_cli_can_apply_with_approval(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            run_root = root / "run"
            run_root.mkdir()
            source.write_text("# Spec\n\nBefore.\n", encoding="utf-8")
            final_text = "# Spec\n\nAfter.\n"
            run_root.joinpath("spec.md").write_text(final_text, encoding="utf-8")
            run_root.joinpath("rounds").mkdir()
            run_root.joinpath("rounds/run_state.json").write_text(
                json.dumps(
                    {
                        "current_round": 6,
                        "current_draft_hash": draft_hash(final_text),
                        "terminal_state": "CONVERGED",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "apply-back",
                    "--source",
                    str(source),
                    "--run-root",
                    str(run_root),
                    "--apply",
                    "--approve",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(source.read_text(encoding="utf-8"), final_text)
            report = json.loads(run_root.joinpath("rounds/apply_back_review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "apply")
            self.assertTrue(report["applied"])

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

    def test_live_phase2_cli_reaches_converged_with_fake_codex_executables(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = "# Whetstone 0.17\n\n## Rules\n\nDraft.\n"
            root.joinpath("spec.md").write_text(spec, encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            root.joinpath("rounds").mkdir()
            spec_hash = draft_hash(spec)
            root.joinpath("rounds/run_state.json").write_text(
                json.dumps(
                    {
                        "current_round": 3,
                        "phase": "phase_1",
                        "active_profile": None,
                        "current_draft_hash": spec_hash,
                        "last_accepted_draft_hash": spec_hash,
                        "seen_draft_hashes": [spec_hash],
                        "terminal_state": "PHASE_1_STABLE",
                        "ready_for_phase_2": True,
                        "resumable": False,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            reviewer = root / "fake-codex-reviewer"
            reviewer.write_text(
                """#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

out = None
args = sys.argv[1:]
for index, arg in enumerate(args):
    if arg == "--output-last-message":
        out = args[index + 1]
prompt = sys.stdin.read()
profile = re.search(r"^Review profile: (.+)$", prompt, re.M).group(1)
round_number = int(re.search(r"^- round_number: ([0-9]+)$", prompt, re.M).group(1))
draft_hash = re.search(r"^- draft_hash: ([a-f0-9]{64})$", prompt, re.M).group(1)
artifact = {
    "round_number": round_number,
    "profile": profile,
    "reviewer": {"name": "fake-codex", "version": "0", "model": "fixture"},
    "draft_hash": draft_hash,
    "feedback": [],
}
Path(out).write_text(json.dumps(artifact), encoding="utf-8")
""",
                encoding="utf-8",
            )
            reviewer.chmod(reviewer.stat().st_mode | stat.S_IXUSR)

            editor = root / "fake-codex-editor"
            editor.write_text(
                """#!/usr/bin/env python3
import hashlib
import json
import re
import sys
from pathlib import Path

out = None
args = sys.argv[1:]
cd_path = Path.cwd()
for index, arg in enumerate(args):
    if arg == "--output-last-message":
        out = args[index + 1]
    if arg == "--cd" and index + 1 < len(args):
        cd_path = Path(args[index + 1])
prompt = sys.stdin.read()
round_number = int(re.search(r"The top-level object MUST set round_number to ([0-9]+)\\.", prompt).group(1))
before_hash = re.search(r"The draft_before_hash MUST be ([a-f0-9]{64})\\.", prompt).group(1)

def read_draft_from_prompt():
    found = re.search(r"Draft path: ([^\\n]+)", prompt)
    if found:
        return (cd_path / found.group(1)).read_text(encoding="utf-8")
    return prompt.split("\\nDraft:\\n", 1)[1]

draft = read_draft_from_prompt()
after_hash = hashlib.sha256(draft.encode("utf-8")).hexdigest()
artifact = {
    "round_number": round_number,
    "draft_before_hash": before_hash,
    "draft_after_hash": after_hash,
    "accepted_feedback_ids": [],
    "modified_feedback_ids": [],
    "declined_feedback": [],
    "created_conflict_ids": [],
    "resolved_issue_ids": [],
    "unresolved_issue_ids": [],
    "draft_after_content": draft,
}
Path(out).write_text(json.dumps(artifact), encoding="utf-8")
""",
                encoding="utf-8",
            )
            editor.chmod(editor.stat().st_mode | stat.S_IXUSR)

            root.joinpath("orchestrator_config.yaml").write_text(
                f"""
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
declaration_path: ./convergence_declaration.md
clients:
  reviewer:
    name: codex
    command: {reviewer}
    version: "0"
    model: fixture
  editor:
    name: codex
    command: {editor}
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

            exit_code = main(["live-phase2", "--root", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertIn("# Whetstone 1.0", root.joinpath("spec.md").read_text(encoding="utf-8"))
            state = json.loads(root.joinpath("rounds/run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["terminal_state"], "CONVERGED")
            declaration = root.joinpath("convergence_declaration.md").read_text(encoding="utf-8")
            self.assertIn("declaration_status: accepted", declaration)
            self.assertTrue(root.joinpath("rounds/round-4/rubric_gaps.json").exists())
            self.assertTrue(root.joinpath("rounds/round-6/reviewer_feedback.json").exists())
            manifest = json.loads(root.joinpath("rounds/rubric_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow"], "standard")
            self.assertEqual(manifest["rubric_profile"], "standard-v1")

    def test_live_phase2_cli_workflow_and_rubric_overrides_produce_distinct_manifests(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_cli_phase2_root(root)
            _write_approved_scope_contract(root)

            exit_code = main(
                [
                    "live-phase2",
                    "--root",
                    str(root),
                    "--workflow",
                    "mvp",
                    "--rubric",
                    "mvp-v1",
                ]
            )

            self.assertEqual(exit_code, 0)
            mvp_manifest = json.loads(root.joinpath("rounds/rubric_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(mvp_manifest["workflow"], "mvp")
            self.assertEqual(mvp_manifest["rubric_profile"], "mvp-v1")

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_cli_phase2_root(root)

            exit_code = main(
                [
                    "live-phase2",
                    "--root",
                    str(root),
                    "--workflow",
                    "governance",
                    "--rubric",
                    "governance-v6",
                ]
            )

            self.assertEqual(exit_code, 0)
            governance_manifest = json.loads(root.joinpath("rounds/rubric_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(governance_manifest["workflow"], "governance")
            self.assertEqual(governance_manifest["rubric_profile"], "governance-v6")
            self.assertNotEqual(mvp_manifest["rubric_content_hash"], governance_manifest["rubric_content_hash"])

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
            self.assertTrue((output_dir / "decision_summary.json").exists())
            self.assertTrue((output_dir / "decision_summary.md").exists())

    def test_status_reports_run_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("rounds").mkdir()
            root.joinpath("rounds/run_state.json").write_text(
                json.dumps(
                    {
                        "phase": "phase_1",
                        "current_round": 3,
                        "active_profile": None,
                        "terminal_state": "PHASE_1_STABLE",
                        "ready_for_phase_2": True,
                        "current_draft_hash": "a" * 64,
                        "last_accepted_draft_hash": "a" * 64,
                        "resumable": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["status", "--root", str(root)])

            self.assertEqual(exit_code, 0)
            packet = json.loads(output.getvalue())
            self.assertEqual(packet["terminal_state"], "PHASE_1_STABLE")
            self.assertEqual(packet["next_action"], "run_live_phase2")

    def test_status_supports_run_root_and_text_format(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "run"
            run_root.joinpath("rounds").mkdir(parents=True)
            run_root.joinpath("rounds/run_state.json").write_text(
                json.dumps(
                    {
                        "phase": "phase_1",
                        "current_round": 3,
                        "terminal_state": "PHASE_1_STABLE",
                        "ready_for_phase_2": True,
                        "last_accepted_draft_hash": "a" * 64,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["status", "--run-root", str(run_root), "--format", "text"])

            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("Whetstone Status", rendered)
            self.assertIn("terminal_state: PHASE_1_STABLE", rendered)
            self.assertIn("next_action: run_live_phase2", rendered)

    def test_cli_resume_continue_smoke_after_editor_timeout(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("spec.md").write_text("# Toy Spec\n\n## Behavior\n\nInitial draft.\n", encoding="utf-8")
            root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
            fake_codex = root / "fake-codex"
            fake_codex.write_text(
                """#!/usr/bin/env python3
import json
import re
import sys
import time
from pathlib import Path

args = sys.argv[1:]
prompt = sys.stdin.read()
schema_path = ""
output_path = None
cd_path = Path.cwd()
for index, arg in enumerate(args):
    if arg == "--output-schema" and index + 1 < len(args):
        schema_path = args[index + 1]
    if arg == "--output-last-message" and index + 1 < len(args):
        output_path = Path(args[index + 1])
    if arg == "--cd" and index + 1 < len(args):
        cd_path = Path(args[index + 1])

def match(pattern, default=""):
    found = re.search(pattern, prompt)
    return found.group(1) if found else default

def write(packet):
    text = json.dumps(packet)
    if output_path:
        output_path.write_text(text, encoding="utf-8")
    print(text)

if "reviewer_feedback" in schema_path:
    calls_path = cd_path / ".fake_editor_calls"
    feedback = []
    if not calls_path.exists():
        feedback = [{
            "feedback_id": "fb-1",
            "issue_id": "iss_aaaaaaaaaaaaaaaa",
            "issue_fingerprint": "a" * 64,
            "issue_type": "precision_gap",
            "affected_sections": ["spec"],
            "baseline_severity": "major",
            "authority_impact": None,
            "determinism_impact": None,
            "rubric_impact": None,
            "normalized_severity": "major",
            "invariant_violated": None,
            "claim": "Fixture issue.",
            "evidence": "Fixture.",
            "recommended_change": "Clarify.",
            "in_scope": True,
            "severity_rationale": None,
            "oscillation_key": None
        }]
    write({
        "round_number": int(match(r"- round_number: (\\d+)", "1")),
        "profile": match(r"Review profile: ([^\\n]+)", "structural_integrity"),
        "reviewer": {"name": "fake-codex", "version": "0", "model": "fake"},
        "draft_hash": match(r"- draft_hash: ([0-9a-f]{64})", "0" * 64),
        "feedback": feedback
    })
    raise SystemExit(0)

calls_path = cd_path / ".fake_editor_calls"
try:
    calls = int(calls_path.read_text(encoding="utf-8"))
except FileNotFoundError:
    calls = 0
calls += 1
calls_path.write_text(str(calls), encoding="utf-8")
if calls == 1:
    time.sleep(2)

def read_draft_from_prompt():
    found = re.search(r"Draft path: ([^\\n]+)", prompt)
    if found:
        return (cd_path / found.group(1)).read_text(encoding="utf-8")
    return prompt.split("\\nDraft:\\n", 1)[1].split("\\n\\nReviewer feedback JSON:\\n", 1)[0]

draft = read_draft_from_prompt()
if "Clarified by fake editor." not in draft:
    draft = draft.rstrip() + "\\n\\nClarified by fake editor.\\n"
write({
    "round_number": int(match(r"round_number to (\\d+)", "1")),
    "draft_before_hash": match(r"draft_before_hash MUST be ([0-9a-f]{64})", "0" * 64),
    "draft_after_hash": None,
    "accepted_feedback_ids": [],
    "modified_feedback_ids": [],
    "declined_feedback": [],
    "created_conflict_ids": [],
    "resolved_issue_ids": ["iss_aaaaaaaaaaaaaaaa"],
    "unresolved_issue_ids": [],
    "draft_after_content": draft
})
""",
                encoding="utf-8",
            )
            fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)
            root.joinpath("orchestrator_config.yaml").write_text(
                f"""
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
clients:
  reviewer:
    name: codex
    command: {fake_codex}
    version: "0"
    model: fake
  editor:
    name: codex
    command: {fake_codex}
    version: "0"
    model: fake
timeouts:
  reviewer_seconds: 5
  editor_seconds: 1
""",
                encoding="utf-8",
            )

            first_stdout = io.StringIO()
            with redirect_stdout(first_stdout):
                first_exit = main(["live-phase1", "--root", str(root)])
            first_packet = json.loads(first_stdout.getvalue())
            self.assertEqual(first_exit, 0)
            self.assertEqual(first_packet["terminal_state"], "HALTED_CLIENT_TIMEOUT")

            dry_stdout = io.StringIO()
            with redirect_stdout(dry_stdout):
                dry_exit = main(["resume", "--root", str(root), "--continue", "--dry-run"])
            dry_packet = json.loads(dry_stdout.getvalue())
            self.assertEqual(dry_exit, 0)
            self.assertTrue(dry_packet["resumable"])
            self.assertEqual(dry_packet["next_attempt_number"], 2)

            resume_stdout = io.StringIO()
            with redirect_stdout(resume_stdout):
                resume_exit = main(["resume", "--root", str(root), "--continue"])
            resume_packet = json.loads(resume_stdout.getvalue())

            self.assertEqual(resume_exit, 0)
            self.assertEqual(resume_packet["terminal_state"], "PHASE_1_STABLE")
            self.assertEqual(resume_packet["round_number"], 4)
            self.assertTrue(resume_packet["ready_for_phase_2"])
            self.assertFalse(root.joinpath("rounds/artifact_validation_error.json").exists())
            self.assertTrue(root.joinpath("rounds/round-1/editor_invalid_attempt_1.json").exists())
            self.assertIn("Clarified by fake editor.", root.joinpath("spec.md").read_text(encoding="utf-8"))

    def test_decision_summary_writes_mechanical_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "decision-scan"
            output_dir.mkdir()
            register_path = output_dir / "decision_register.json"
            register_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-05-01T00:00:00+00:00",
                        "mode": "end_of_cycle",
                        "terminal_state": "PHASE_1_STABLE",
                        "unresolved_human_decision_count": 1,
                        "decision_points": [
                            {
                                "decision_id": "dec_aaaaaaaaaaaaaaaa",
                                "round_number": 1,
                                "profile": "operability",
                                "source_feedback_ids": ["fb-1"],
                                "affected_sections": ["Rules"],
                                "decision_type": "tighten_requirement",
                                "trigger_types": ["tighten_requirement"],
                                "evidence_lines": ["- Adapter MUST retry."],
                                "question": "Should `Rules` adopt this change?",
                                "options_considered": [
                                    {
                                        "option_id": "selected",
                                        "label": "Keep editor change",
                                        "description": "Keep the revised draft behavior.",
                                    }
                                ],
                                "editor_selected_option_id": "selected",
                                "editor_rationale": "Detected from diff.",
                                "risk_if_wrong": "The spec may encode an unintended decision.",
                                "requires_human_decision": True,
                                "orchestrator_action": "present_at_end",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(["decision-summary", "--register", str(register_path)])

            self.assertEqual(exit_code, 0)
            summary = json.loads((output_dir / "decision_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["summary_method"], "mechanical_v1")
            self.assertEqual(summary["clusters"]["by_section"][0]["cluster_key"], "Rules")
            self.assertTrue((output_dir / "decision_summary.md").exists())


def _seed_cli_phase2_root(root: Path) -> None:
    spec = "# Whetstone 0.17\n\n## Rules\n\nDraft.\n"
    root.joinpath("spec.md").write_text(spec, encoding="utf-8")
    root.joinpath("spec.history.md").write_text("# History\n", encoding="utf-8")
    root.joinpath("rounds").mkdir()
    spec_hash = draft_hash(spec)
    root.joinpath("rounds/run_state.json").write_text(
        json.dumps(
            {
                "current_round": 3,
                "phase": "phase_1",
                "active_profile": None,
                "current_draft_hash": spec_hash,
                "last_accepted_draft_hash": spec_hash,
                "seen_draft_hashes": [spec_hash],
                "terminal_state": "PHASE_1_STABLE",
                "ready_for_phase_2": True,
                "resumable": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reviewer = root / "fake-codex-reviewer"
    reviewer.write_text(
        """#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

out = None
args = sys.argv[1:]
for index, arg in enumerate(args):
    if arg == "--output-last-message":
        out = args[index + 1]
prompt = sys.stdin.read()
profile = re.search(r"^Review profile: (.+)$", prompt, re.M).group(1)
round_number = int(re.search(r"^- round_number: ([0-9]+)$", prompt, re.M).group(1))
draft_hash = re.search(r"^- draft_hash: ([a-f0-9]{64})$", prompt, re.M).group(1)
artifact = {
    "round_number": round_number,
    "profile": profile,
    "reviewer": {"name": "fake-codex", "version": "0", "model": "fixture"},
    "draft_hash": draft_hash,
    "feedback": [],
}
Path(out).write_text(json.dumps(artifact), encoding="utf-8")
""",
        encoding="utf-8",
    )
    reviewer.chmod(reviewer.stat().st_mode | stat.S_IXUSR)
    editor = root / "fake-codex-editor"
    editor.write_text(
        """#!/usr/bin/env python3
import hashlib
import json
import re
import sys
from pathlib import Path

out = None
args = sys.argv[1:]
cd_path = Path.cwd()
for index, arg in enumerate(args):
    if arg == "--output-last-message":
        out = args[index + 1]
    if arg == "--cd" and index + 1 < len(args):
        cd_path = Path(args[index + 1])
prompt = sys.stdin.read()
round_number = int(re.search(r"The top-level object MUST set round_number to ([0-9]+)\\.", prompt).group(1))
before_hash = re.search(r"The draft_before_hash MUST be ([a-f0-9]{64})\\.", prompt).group(1)

def read_draft_from_prompt():
    found = re.search(r"Draft path: ([^\\n]+)", prompt)
    if found:
        return (cd_path / found.group(1)).read_text(encoding="utf-8")
    return prompt.split("\\nDraft:\\n", 1)[1]

draft = read_draft_from_prompt()
after_hash = hashlib.sha256(draft.encode("utf-8")).hexdigest()
artifact = {
    "round_number": round_number,
    "draft_before_hash": before_hash,
    "draft_after_hash": after_hash,
    "accepted_feedback_ids": [],
    "modified_feedback_ids": [],
    "declined_feedback": [],
    "created_conflict_ids": [],
    "resolved_issue_ids": [],
    "unresolved_issue_ids": [],
    "draft_after_content": draft,
}
Path(out).write_text(json.dumps(artifact), encoding="utf-8")
""",
        encoding="utf-8",
    )
    editor.chmod(editor.stat().st_mode | stat.S_IXUSR)
    root.joinpath("orchestrator_config.yaml").write_text(
        f"""
spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
declaration_path: ./convergence_declaration.md
clients:
  reviewer:
    name: codex
    command: {reviewer}
    version: "0"
    model: fixture
  editor:
    name: codex
    command: {editor}
    version: "0"
    model: fixture
convergence:
  enabled: true
  target_phase: final
  target_mode: strict
  max_rounds: 8
""",
        encoding="utf-8",
    )


def _write_approved_scope_contract(root: Path) -> None:
    packet = scope_contract_from_notes(
        render_mvp_scope_notes_template(),
        source_path=str(root / "scope-notes.md"),
        approved=True,
    )
    write_scope_contract(root / "rounds" / "intake" / "scope_contract.json", packet)


if __name__ == "__main__":
    unittest.main()
