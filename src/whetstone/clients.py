"""Client adapters for reviewer and editor execution."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from whetstone.contracts import SCHEMA_DIR, validate_artifact
from whetstone.hashing import draft_hash
from whetstone.identity import issue_fingerprint, issue_id, normalize_severity
from whetstone.oscillation import canonicalize_phase2_feedback

SEVERITY_FIELDS = (
    "baseline_severity",
    "authority_impact",
    "determinism_impact",
    "rubric_impact",
    "normalized_severity",
)
SEVERITY_ALIASES = {
    "critical": "blocker",
    "severe": "blocker",
    "high": "major",
    "medium": "minor",
    "moderate": "minor",
    "low": "nit",
    "none": None,
    "null": None,
    "na": None,
    "n/a": None,
    "not applicable": None,
    "not_applicable": None,
    "not-applicable": None,
    "no impact": None,
    "no_impact": None,
    "no-impact": None,
    "not impacted": None,
    "no authority impact": None,
    "no determinism impact": None,
    "no rubric impact": None,
    "not applicable to authority": None,
    "not applicable to determinism": None,
    "not applicable to rubric": None,
}
SEVERITY_VALUES = {"blocker", "major", "minor", "nit"}


class ProcessReviewerClient:
    """Run a configured command and parse schema-valid reviewer feedback JSON from stdout."""

    def __init__(self, command: str) -> None:
        self.command = command

    def review(self, prompt: str) -> dict:
        artifact = _run_json_command(self.command, prompt)
        artifact = canonicalize_reviewer_input(artifact)
        validate_artifact(artifact, "reviewer_feedback")
        return artifact


class ProcessEditorClient:
    """Run a configured command and parse schema-valid editor summary JSON from stdout."""

    def __init__(self, command: str) -> None:
        self.command = command

    def revise(self, prompt: str) -> dict:
        artifact = _run_json_command(self.command, prompt)
        artifact = canonicalize_editor_input(artifact)
        validate_artifact(artifact, "editor_summary")
        return artifact


class CodexReviewerClient:
    """Reviewer client backed by `codex exec`."""

    def __init__(
        self,
        *,
        command: str = "codex",
        model: str | None = None,
        cwd: Path | str = ".",
        phase: str = "phase_1",
        section_ids: list[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.command = command
        self.model = model
        self.cwd = Path(cwd)
        self.phase = phase
        self.section_ids = section_ids or []
        self.timeout_seconds = timeout_seconds
        self.schema_name = "phase2_reviewer_feedback_input" if phase == "phase_2" else "reviewer_feedback"
        self.output_schema_name = (
            "phase2_reviewer_feedback_input.codex" if phase == "phase_2" else "reviewer_feedback.codex"
        )

    def review(self, prompt: str) -> dict:
        artifact = _run_codex_exec(
            command=self.command,
            prompt=prompt,
            cwd=self.cwd,
            schema_path=SCHEMA_DIR / f"{self.output_schema_name}.schema.json",
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )
        artifact = canonicalize_reviewer_input(artifact)
        validate_artifact(artifact, self.schema_name)
        if self.phase == "phase_2":
            artifact = canonicalize_phase2_feedback(artifact, self.section_ids)
            validate_artifact(artifact, "phase2_reviewer_feedback")
        return artifact


class ClaudeCodeReviewerClient:
    """Reviewer client backed by Claude Code non-interactive print mode."""

    def __init__(
        self,
        *,
        command: str = "claude",
        model: str | None = None,
        cwd: Path | str = ".",
        phase: str = "phase_1",
        section_ids: list[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.command = command
        self.model = model
        self.cwd = Path(cwd)
        self.phase = phase
        self.section_ids = section_ids or []
        self.timeout_seconds = timeout_seconds
        self.schema_name = "phase2_reviewer_feedback_input" if phase == "phase_2" else "reviewer_feedback"
        self.output_schema_name = (
            "phase2_reviewer_feedback_input.codex" if phase == "phase_2" else "reviewer_feedback.codex"
        )

    def review(self, prompt: str) -> dict:
        artifact = _run_claude_print(
            command=self.command,
            prompt=prompt,
            cwd=self.cwd,
            schema_path=SCHEMA_DIR / f"{self.output_schema_name}.schema.json",
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )
        artifact = canonicalize_reviewer_input(artifact)
        validate_artifact(artifact, self.schema_name)
        if self.phase == "phase_2":
            artifact = canonicalize_phase2_feedback(artifact, self.section_ids)
            validate_artifact(artifact, "phase2_reviewer_feedback")
        return artifact


class CodexEditorClient:
    """Editor client backed by `codex exec`."""

    def __init__(
        self,
        *,
        command: str = "codex",
        model: str | None = None,
        cwd: Path | str = ".",
        timeout_seconds: int | None = None,
    ) -> None:
        self.command = command
        self.model = model
        self.cwd = Path(cwd)
        self.timeout_seconds = timeout_seconds

    def revise(self, prompt: str) -> dict:
        artifact = _run_codex_exec(
            command=self.command,
            prompt=prompt,
            cwd=self.cwd,
            schema_path=SCHEMA_DIR / "editor_summary.codex.schema.json",
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )
        artifact = canonicalize_editor_input(artifact)
        validate_artifact(artifact, "editor_summary")
        return artifact


class ClaudeCodeEditorClient:
    """Editor client backed by Claude Code non-interactive print mode."""

    def __init__(
        self,
        *,
        command: str = "claude",
        model: str | None = None,
        cwd: Path | str = ".",
        timeout_seconds: int | None = None,
    ) -> None:
        self.command = command
        self.model = model
        self.cwd = Path(cwd)
        self.timeout_seconds = timeout_seconds

    def revise(self, prompt: str) -> dict:
        artifact = _run_claude_print(
            command=self.command,
            prompt=prompt,
            cwd=self.cwd,
            schema_path=SCHEMA_DIR / "editor_summary.codex.schema.json",
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )
        artifact = canonicalize_editor_input(artifact)
        validate_artifact(artifact, "editor_summary")
        return artifact


def canonicalize_reviewer_input(artifact: dict) -> dict:
    """Normalize deterministic low-level reviewer fields before schema validation."""
    feedback_items = artifact.get("feedback")
    if not isinstance(feedback_items, list):
        return artifact
    for item in feedback_items:
        if not isinstance(item, dict):
            continue
        for field in SEVERITY_FIELDS:
            value = item.get(field)
            if not isinstance(value, str):
                continue
            normalized = value.strip().lower()
            aliased = SEVERITY_ALIASES.get(normalized, normalized)
            if field != "normalized_severity" and (normalized == "" or aliased is None):
                item[field] = None
            elif field == "normalized_severity" and (normalized == "" or aliased is None):
                item[field] = "nit"
            else:
                item[field] = aliased
        _canonicalize_reviewer_identity(item)
        _canonicalize_normalized_severity(item)
        if item.get("baseline_severity") is None and item.get("severity_rationale") is None:
            item["severity_rationale"] = "Baseline severity was canonicalized to null."
    return artifact


def _canonicalize_reviewer_identity(item: dict) -> None:
    issue_type_value = item.get("issue_type")
    affected_sections_value = item.get("affected_sections")
    claim_value = item.get("claim")
    if not isinstance(issue_type_value, str):
        return
    if not isinstance(affected_sections_value, list) or not all(
        isinstance(section, str) for section in affected_sections_value
    ):
        return
    if not isinstance(claim_value, str):
        return
    invariant_violated_value = item.get("invariant_violated")
    if invariant_violated_value is not None and not isinstance(invariant_violated_value, str):
        invariant_violated_value = None
    fingerprint = issue_fingerprint(
        issue_type_value,
        affected_sections_value,
        invariant_violated_value,
        claim_value,
    )
    item["issue_fingerprint"] = fingerprint
    item["issue_id"] = issue_id(fingerprint)


def _canonicalize_normalized_severity(item: dict) -> None:
    components = [
        item.get("baseline_severity"),
        item.get("authority_impact"),
        item.get("determinism_impact"),
        item.get("rubric_impact"),
    ]
    if all(component is None or component in SEVERITY_VALUES for component in components):
        item["normalized_severity"] = normalize_severity(*components)


def canonicalize_editor_input(artifact: dict) -> dict:
    """Normalize deterministic editor-derived fields before persisted validation."""
    draft_after_content = artifact.get("draft_after_content")
    if isinstance(draft_after_content, str):
        artifact["draft_after_hash"] = draft_hash(draft_after_content)
    return artifact


def _run_json_command(command: str, prompt: str) -> dict:
    completed = subprocess.run(
        [command],
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{command!r} exited {completed.returncode}: {completed.stderr.strip()}")
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{command!r} did not return JSON on stdout") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{command!r} returned non-object JSON")
    return data


def _run_codex_exec(
    *,
    command: str,
    prompt: str,
    cwd: Path,
    schema_path: Path,
    model: str | None,
    timeout_seconds: int | None = None,
) -> dict:
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "last-message.json"
        args = [
            command,
            "exec",
            "--cd",
            str(cwd),
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
        ]
        if model:
            args.extend(["--model", model])
        args.append("-")
        try:
            completed = subprocess.run(
                args,
                input=prompt,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"{command!r} exec timed out after {timeout_seconds} seconds") from exc
        if completed.returncode != 0:
            raise RuntimeError(f"{command!r} exec exited {completed.returncode}: {completed.stderr.strip()}")
        content = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        return _parse_json_object(content, source=f"{command!r} exec")


def _run_claude_print(
    *,
    command: str,
    prompt: str,
    cwd: Path,
    schema_path: Path,
    model: str | None,
    timeout_seconds: int | None = None,
) -> dict:
    args = [
        command,
        "--print",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "",
        "--json-schema",
        schema_path.read_text(encoding="utf-8"),
    ]
    if model:
        args.extend(["--model", model])
    args.append(prompt)
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"{command!r} --print timed out after {timeout_seconds} seconds") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{command!r} --print exited {completed.returncode}: {detail}")
    artifact = _parse_json_object(completed.stdout, source=f"{command!r} --print")
    structured_output = artifact.get("structured_output")
    if isinstance(structured_output, dict):
        return structured_output
    result = artifact.get("result")
    if isinstance(result, str):
        return _parse_json_object(result, source=f"{command!r} --print result")
    return artifact


def _parse_json_object(content: str, *, source: str) -> dict:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = _extract_json_object(content, source=source)
    if not isinstance(data, dict):
        raise ValueError(f"{source} returned non-object JSON")
    return data


def _extract_json_object(content: str, *, source: str) -> dict:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.startswith("json\n"):
                stripped = stripped[5:].strip()
            try:
                data = json.loads(stripped)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"{source} did not return JSON")
    try:
        data = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source} did not return parseable JSON") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{source} returned non-object JSON")
    return data
