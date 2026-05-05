"""Client adapters for reviewer and editor execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any

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


@dataclass(frozen=True)
class ClientInvocationResult:
    artifact: dict
    telemetry: dict[str, Any]


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
        self.last_telemetry: dict[str, Any] | None = None

    def review(self, prompt: str) -> dict:
        try:
            result = _run_codex_exec(
                command=self.command,
                prompt=prompt,
                cwd=self.cwd,
                schema_path=SCHEMA_DIR / f"{self.output_schema_name}.schema.json",
                model=self.model,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            self.last_telemetry = getattr(exc, "telemetry", None)
            raise
        self.last_telemetry = result.telemetry
        artifact = result.artifact
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
        self.last_telemetry: dict[str, Any] | None = None

    def review(self, prompt: str) -> dict:
        try:
            result = _run_claude_print(
                command=self.command,
                prompt=prompt,
                cwd=self.cwd,
                schema_path=SCHEMA_DIR / f"{self.output_schema_name}.schema.json",
                model=self.model,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            self.last_telemetry = getattr(exc, "telemetry", None)
            raise
        self.last_telemetry = result.telemetry
        artifact = result.artifact
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
        self.last_telemetry: dict[str, Any] | None = None

    def revise(self, prompt: str) -> dict:
        try:
            result = _run_codex_exec(
                command=self.command,
                prompt=prompt,
                cwd=self.cwd,
                schema_path=SCHEMA_DIR / "editor_summary.codex.schema.json",
                model=self.model,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            self.last_telemetry = getattr(exc, "telemetry", None)
            raise
        self.last_telemetry = result.telemetry
        artifact = result.artifact
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
        self.last_telemetry: dict[str, Any] | None = None

    def revise(self, prompt: str) -> dict:
        try:
            result = _run_claude_print(
                command=self.command,
                prompt=prompt,
                cwd=self.cwd,
                schema_path=SCHEMA_DIR / "editor_summary.codex.schema.json",
                model=self.model,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            self.last_telemetry = getattr(exc, "telemetry", None)
            raise
        self.last_telemetry = result.telemetry
        artifact = result.artifact
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
) -> ClientInvocationResult:
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "last-message.json"
        args = [
            command,
            "exec",
            "--cd",
            str(cwd),
            "-c",
            'web_search="disabled"',
            "-c",
            'model_reasoning_effort="medium"',
            "--ignore-rules",
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
        started_at = _now()
        started_monotonic = monotonic()
        try:
            completed = _run_client_process(
                args,
                input_text=prompt,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            telemetry = _base_telemetry(
                started_at=started_at,
                duration_ms=_duration_ms(started_monotonic),
                exit_code=None,
                timed_out=True,
                telemetry_source="process_metadata",
            )
            error = TimeoutError(f"{command!r} exec timed out after {timeout_seconds} seconds")
            setattr(error, "telemetry", telemetry)
            raise error from exc
        telemetry = _codex_telemetry_from_completed(completed, started_at=started_at, started_monotonic=started_monotonic)
        if completed.returncode != 0:
            telemetry["client_error"] = completed.stderr.strip() or completed.stdout.strip()
            error = RuntimeError(f"{command!r} exec exited {completed.returncode}: {completed.stderr.strip()}")
            setattr(error, "telemetry", telemetry)
            raise error
        content = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        return ClientInvocationResult(_parse_json_object(content, source=f"{command!r} exec"), telemetry)


def _run_claude_print(
    *,
    command: str,
    prompt: str,
    cwd: Path,
    schema_path: Path,
    model: str | None,
    timeout_seconds: int | None = None,
) -> ClientInvocationResult:
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
    started_at = _now()
    started_monotonic = monotonic()
    try:
        completed = _run_client_process(
            args,
            cwd=cwd,
            input_text=None,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        telemetry = _base_telemetry(
            started_at=started_at,
            duration_ms=_duration_ms(started_monotonic),
            exit_code=None,
            timed_out=True,
            telemetry_source="process_metadata",
        )
        error = TimeoutError(f"{command!r} --print timed out after {timeout_seconds} seconds")
        setattr(error, "telemetry", telemetry)
        raise error from exc
    telemetry = _claude_telemetry_from_completed(completed, started_at=started_at, started_monotonic=started_monotonic)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        telemetry["client_error"] = detail
        error = RuntimeError(f"{command!r} --print exited {completed.returncode}: {detail}")
        setattr(error, "telemetry", telemetry)
        raise error
    artifact = _parse_json_object(completed.stdout, source=f"{command!r} --print")
    structured_output = artifact.get("structured_output")
    if isinstance(structured_output, dict):
        return ClientInvocationResult(structured_output, telemetry)
    result = artifact.get("result")
    if isinstance(result, str):
        return ClientInvocationResult(_parse_json_object(result, source=f"{command!r} --print result"), telemetry)
    return ClientInvocationResult(artifact, telemetry)


def _run_client_process(
    args: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None,
    timeout: int | None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_group(process)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(args, timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        process.kill()
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError:
            process.kill()


def _base_telemetry(
    *,
    started_at: str,
    duration_ms: int | None,
    exit_code: int | None,
    timed_out: bool,
    telemetry_source: str,
) -> dict[str, Any]:
    return {
        "started_at": started_at,
        "finished_at": _now() if not timed_out else None,
        "duration_ms": duration_ms,
        "duration_api_ms": None,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "session_id": None,
        "num_turns": None,
        "stop_reason": None,
        "terminal_reason": None,
        "total_cost_usd": None,
        "usage": {
            "input_tokens": None,
            "output_tokens": None,
            "cache_creation_input_tokens": None,
            "cache_read_input_tokens": None,
            "total_tokens": None,
            "provider_raw": None,
        },
        "model_usage": None,
        "raw_envelope": None,
        "stdout": None,
        "stderr": None,
        "telemetry_source": telemetry_source,
    }


def _codex_telemetry_from_completed(
    completed: subprocess.CompletedProcess[str],
    *,
    started_at: str,
    started_monotonic: float,
) -> dict[str, Any]:
    telemetry = _base_telemetry(
        started_at=started_at,
        duration_ms=_duration_ms(started_monotonic),
        exit_code=completed.returncode,
        timed_out=False,
        telemetry_source="process_metadata",
    )
    telemetry["stdout"] = completed.stdout
    telemetry["stderr"] = completed.stderr
    tokens = _parse_codex_tokens_used(completed.stdout + "\n" + completed.stderr)
    if tokens is not None:
        telemetry["usage"]["total_tokens"] = tokens
        telemetry["telemetry_source"] = "codex_stdout"
    return telemetry


def _claude_telemetry_from_completed(
    completed: subprocess.CompletedProcess[str],
    *,
    started_at: str,
    started_monotonic: float,
) -> dict[str, Any]:
    telemetry = _base_telemetry(
        started_at=started_at,
        duration_ms=_duration_ms(started_monotonic),
        exit_code=completed.returncode,
        timed_out=False,
        telemetry_source="process_metadata",
    )
    telemetry["stdout"] = completed.stdout
    telemetry["stderr"] = completed.stderr
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return telemetry
    if not isinstance(envelope, dict):
        return telemetry
    telemetry["raw_envelope"] = envelope
    telemetry["telemetry_source"] = "claude_json_envelope"
    telemetry["duration_api_ms"] = _optional_int(envelope.get("duration_api_ms"))
    telemetry["session_id"] = _optional_str(envelope.get("session_id"))
    telemetry["num_turns"] = _optional_int(envelope.get("num_turns"))
    telemetry["stop_reason"] = _optional_str(envelope.get("stop_reason"))
    telemetry["terminal_reason"] = _optional_str(envelope.get("terminal_reason") or envelope.get("subtype"))
    telemetry["total_cost_usd"] = _optional_number(envelope.get("total_cost_usd"))
    usage = envelope.get("usage")
    if isinstance(usage, dict):
        telemetry["usage"] = _usage_packet(usage)
    model_usage = envelope.get("modelUsage")
    telemetry["model_usage"] = model_usage if isinstance(model_usage, dict) else None
    return telemetry


def _usage_packet(provider_raw: dict[str, Any]) -> dict[str, Any]:
    packet = {
        "input_tokens": _optional_int(provider_raw.get("input_tokens")),
        "output_tokens": _optional_int(provider_raw.get("output_tokens")),
        "cache_creation_input_tokens": _optional_int(provider_raw.get("cache_creation_input_tokens")),
        "cache_read_input_tokens": _optional_int(provider_raw.get("cache_read_input_tokens")),
        "total_tokens": None,
        "provider_raw": provider_raw,
    }
    token_values = [
        packet["input_tokens"],
        packet["output_tokens"],
        packet["cache_creation_input_tokens"],
        packet["cache_read_input_tokens"],
    ]
    if any(value is not None for value in token_values):
        packet["total_tokens"] = sum(value or 0 for value in token_values)
    return packet


def _parse_codex_tokens_used(text: str) -> int | None:
    match = re.search(r"tokens used\s*[:\n]\s*([0-9][0-9,]*)", text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _optional_number(value: Any) -> int | float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value
    return None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_monotonic: float) -> int:
    return max(0, int((monotonic() - started_monotonic) * 1000))


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
