from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import stat
import unittest

from whetstone.contracts import SchemaValidationError
from whetstone.clients import (
    ClaudeCodeEditorClient,
    ClaudeCodeReviewerClient,
    CodexEditorClient,
    CodexReviewerClient,
    ProcessReviewerClient,
    _parse_json_object,
)
from whetstone.hashing import draft_hash
from whetstone.identity import issue_fingerprint, issue_id


class ProcessClientTests(unittest.TestCase):
    def test_process_reviewer_client_requires_json_stdout(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "bad-client"
            command.write_text("#!/bin/sh\necho not-json\n", encoding="utf-8")
            command.chmod(command.stat().st_mode | stat.S_IXUSR)

            with self.assertRaises(ValueError):
                ProcessReviewerClient(str(command)).review("prompt")

    def test_process_reviewer_client_accepts_schema_valid_json(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "good-client"
            command.write_text(
                """#!/bin/sh
cat <<'JSON'
{"round_number":1,"profile":"determinism","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","feedback":[]}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)

            artifact = ProcessReviewerClient(str(command)).review("prompt")

            self.assertEqual(artifact["profile"], "determinism")

    def test_parse_json_object_accepts_fenced_json(self) -> None:
        parsed = _parse_json_object('```json\n{"ok": true}\n```', source="fixture")

        self.assertEqual(parsed, {"ok": True})

    def test_codex_reviewer_client_invokes_codex_exec_with_schema_and_output_file(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "codex"
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

            artifact = CodexReviewerClient(command=str(command), cwd=tmp).review("prompt")

            self.assertEqual(artifact["profile"], "determinism")

    def test_claude_code_reviewer_client_canonicalizes_identity_and_severity(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "claude"
            command.write_text(
                """#!/bin/sh
cat <<'JSON'
{"type":"result","structured_output":{"round_number":1,"profile":"structural_integrity","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","feedback":[{"feedback_id":"fb-1","issue_id":"not-an-id","issue_fingerprint":"not-a-fingerprint","issue_type":"authority_violation","affected_sections":["Section 7"],"baseline_severity":"medium","authority_impact":"No authority impact","determinism_impact":null,"rubric_impact":null,"normalized_severity":"high","invariant_violated":null,"claim":"Field ownership is unclear.","evidence":"Fixture.","recommended_change":"Clarify ownership.","in_scope":true,"severity_rationale":null,"oscillation_key":null}]}}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)

            artifact = ClaudeCodeReviewerClient(command=str(command), cwd=tmp).review("prompt")

            expected_fingerprint = issue_fingerprint(
                "authority_violation",
                ["Section 7"],
                None,
                "Field ownership is unclear.",
            )
            item = artifact["feedback"][0]
            self.assertEqual(item["issue_fingerprint"], expected_fingerprint)
            self.assertEqual(item["issue_id"], issue_id(expected_fingerprint))
            self.assertIsNone(item["authority_impact"])
            self.assertEqual(item["normalized_severity"], "minor")

    def test_codex_phase_2_reviewer_client_uses_phase_2_schema(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "codex"
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
{"round_number":4,"profile":"convergence_strict_check","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","feedback":[{"feedback_id":"fb-1","issue_id":"iss_aaaaaaaaaaaaaaaa","issue_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","issue_type":"undefined_behavior","affected_sections":["Hashing"],"baseline_severity":"minor","authority_impact":null,"determinism_impact":null,"rubric_impact":null,"normalized_severity":"minor","invariant_violated":null,"claim":"Needs clarity.","evidence":"Fixture.","recommended_change":"Clarify it.","in_scope":true,"severity_rationale":null,"oscillation_key":null}]}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)

            with self.assertRaises(SchemaValidationError):
                CodexReviewerClient(command=str(command), cwd=tmp, phase="phase_2").review("prompt")

    def test_codex_phase_2_reviewer_client_canonicalizes_oscillation_key(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "codex"
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

            artifact = CodexReviewerClient(
                command=str(command),
                cwd=tmp,
                phase="phase_2",
                section_ids=["spec-hashing"],
            ).review("prompt")

            key = artifact["feedback"][0]["oscillation_key"]
            self.assertIn("fingerprint", key)
            self.assertIn("opposition_key", key)

    def test_codex_editor_client_invokes_codex_exec_with_schema_and_output_file(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "codex"
            command.write_text(
                """#!/bin/sh
out=""
schema=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output-last-message" ]; then
    shift
    out="$1"
  elif [ "$1" = "--output-schema" ]; then
    shift
    schema="$1"
  fi
  shift
done
case "$schema" in
  *editor_summary.codex.schema.json) ;;
  *) exit 42 ;;
esac
cat > /dev/null
cat > "$out" <<'JSON'
{"round_number":1,"draft_before_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","draft_after_hash":null,"accepted_feedback_ids":[],"modified_feedback_ids":[],"declined_feedback":[],"created_conflict_ids":[],"resolved_issue_ids":[],"unresolved_issue_ids":[],"draft_after_content":"# Spec\\n\\nChanged.\\n"}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)

            artifact = CodexEditorClient(command=str(command), cwd=tmp).revise("prompt")

            self.assertEqual(artifact["round_number"], 1)
            self.assertEqual(artifact["draft_after_hash"], draft_hash("# Spec\n\nChanged.\n"))

    def test_claude_code_editor_client_unwraps_structured_output(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "claude"
            command.write_text(
                """#!/bin/sh
schema_seen=0
format_seen=0
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--json-schema" ]; then
    shift
    case "$1" in
      *editor_summary*) schema_seen=1 ;;
    esac
  elif [ "$1" = "--output-format" ]; then
    shift
    case "$1" in
      json) format_seen=1 ;;
    esac
  fi
  shift
done
if [ "$schema_seen" != "1" ] || [ "$format_seen" != "1" ]; then
  exit 42
fi
cat <<'JSON'
{"type":"result","structured_output":{"round_number":1,"draft_before_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","draft_after_hash":null,"accepted_feedback_ids":[],"modified_feedback_ids":[],"declined_feedback":[],"created_conflict_ids":[],"resolved_issue_ids":[],"unresolved_issue_ids":[],"draft_after_content":"# Spec\\n\\nChanged.\\n"}}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)

            artifact = ClaudeCodeEditorClient(command=str(command), cwd=tmp).revise("prompt")

            self.assertEqual(artifact["round_number"], 1)
            self.assertEqual(artifact["draft_after_hash"], draft_hash("# Spec\n\nChanged.\n"))

    def test_claude_code_editor_client_unwraps_result_json(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "claude"
            command.write_text(
                """#!/bin/sh
cat <<'JSON'
{"type":"result","result":"{\\"round_number\\":1,\\"draft_before_hash\\":\\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\\",\\"draft_after_hash\\":\\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\\",\\"accepted_feedback_ids\\":[],\\"modified_feedback_ids\\":[],\\"declined_feedback\\":[],\\"created_conflict_ids\\":[],\\"resolved_issue_ids\\":[],\\"unresolved_issue_ids\\":[]}"}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)

            artifact = ClaudeCodeEditorClient(command=str(command), cwd=tmp).revise("prompt")

            self.assertEqual(artifact["round_number"], 1)

    def test_claude_code_phase_2_reviewer_client_canonicalizes_oscillation_key(self) -> None:
        with TemporaryDirectory() as tmp:
            command = Path(tmp) / "claude"
            command.write_text(
                """#!/bin/sh
schema_seen=0
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--json-schema" ]; then
    shift
    case "$1" in
      *phase2_reviewer_feedback_input*) schema_seen=1 ;;
    esac
  fi
  shift
done
if [ "$schema_seen" != "1" ]; then
  exit 42
fi
cat <<'JSON'
{"type":"result","structured_output":{"round_number":4,"profile":"convergence_strict_check","reviewer":{"name":"fixture","version":"0","model":"fixture"},"draft_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","feedback":[{"feedback_id":"fb-1","issue_id":"iss_aaaaaaaaaaaaaaaa","issue_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","issue_type":"undefined_behavior","affected_sections":["spec-hashing"],"baseline_severity":"Medium","authority_impact":"None","determinism_impact":"High","rubric_impact":null,"normalized_severity":"High","invariant_violated":null,"claim":"Needs clarity.","evidence":"Fixture.","recommended_change":"Clarify it.","in_scope":true,"severity_rationale":null,"oscillation_key":{"section_id":"spec-hashing","concern_type":"precision_gap","direction":"clarify","scope":"local"}}]}}
JSON
""",
                encoding="utf-8",
            )
            command.chmod(command.stat().st_mode | stat.S_IXUSR)

            artifact = ClaudeCodeReviewerClient(
                command=str(command),
                cwd=tmp,
                phase="phase_2",
                section_ids=["spec-hashing"],
            ).review("prompt")

            key = artifact["feedback"][0]["oscillation_key"]
            self.assertIn("fingerprint", key)
            self.assertIn("opposition_key", key)
            self.assertEqual(artifact["feedback"][0]["baseline_severity"], "minor")
            self.assertIsNone(artifact["feedback"][0]["authority_impact"])
            self.assertEqual(artifact["feedback"][0]["determinism_impact"], "major")
            self.assertEqual(artifact["feedback"][0]["normalized_severity"], "major")


if __name__ == "__main__":
    unittest.main()
