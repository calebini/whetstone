"""Live single-round orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Protocol

from whetstone.artifacts import ArtifactStore
from whetstone.clients import ClaudeCodeEditorClient, ClaudeCodeReviewerClient, CodexEditorClient, CodexReviewerClient
from whetstone.config import ClientConfig, OrchestratorConfig
from whetstone.contracts import validate_artifact
from whetstone.decisions import detect_decision_points
from whetstone.evaluation import accepted_draft
from whetstone.hashing import draft_hash, rubric_content_hash, semantic_change_hash
from whetstone.prompts import render_editor_prompt, render_reviewer_prompt
from whetstone.reports import ReportWriter
from whetstone.runner import _unresolved_issues
from whetstone.sections import section_index
from whetstone.versioning import promote_spec_file_for_phase2


class ReviewerClient(Protocol):
    def review(self, prompt: str) -> dict[str, Any]:
        ...


class EditorClient(Protocol):
    def revise(self, prompt: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class LiveRoundResult:
    round_number: int
    round_dir: Path
    draft_before_hash: str
    draft_after_hash: str
    accepted: bool
    reviewer_feedback_count: int
    spec_mutated: bool


class LiveRoundRunner:
    """Run one guarded live reviewer -> editor round."""

    def __init__(
        self,
        root: Path | str,
        config: OrchestratorConfig,
        *,
        reviewer_client: ReviewerClient | None = None,
        editor_client: EditorClient | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.root = Path(root)
        self.config = config
        self.store = ArtifactStore(self.root)
        self.reviewer_client = reviewer_client
        self.editor_client = editor_client
        self.timeout_seconds = timeout_seconds

    def run_round(
        self,
        *,
        round_number: int,
        profile: str,
        phase: str = "phase_1",
        draft_after: str | None = None,
        apply: bool = False,
        overwrite: bool = False,
    ) -> LiveRoundResult:
        invalid_fields = validate_live_config(self.config)
        if invalid_fields:
            _write_config_error(self.config.rounds_dir, invalid_fields)
            raise ValueError("configuration validation failed")
        if phase == "phase_2":
            _maybe_promote_phase2_version(self.config)

        round_dir = self.store.begin_round(round_number, overwrite=overwrite)
        draft_before = self.config.spec_path.read_text(encoding="utf-8")
        draft_before_hash = draft_hash(draft_before)
        explicit_draft_after = draft_after is not None
        draft_after_content = draft_after if draft_after is not None else draft_before
        draft_after_hash = draft_hash(draft_after_content)
        rubric = _read_optional(self.config.convergence.rubric_path)
        rubric_hash = rubric_content_hash(rubric) if rubric is not None else "0" * 64
        section_ids = [section.id for section in section_index(draft_before)] if phase == "phase_2" else []

        reviewer_prompt = render_reviewer_prompt(
            profile=profile,
            draft=draft_before,
            rubric=rubric,
            phase=phase,
            section_ids=section_ids,
            round_number=round_number,
            draft_hash_value=draft_before_hash,
        )
        prompt_snapshot = self._prompt_snapshot(
            profile=profile,
            phase=phase,
            reviewer_prompt=reviewer_prompt,
            editor_prompt=None,
            draft_before_hash=draft_before_hash,
            draft_after_hash=draft_after_hash,
            draft_before=draft_before,
            draft_after=draft_after_content,
            rubric_hash=rubric_hash,
        )
        self._write_pre_review_artifacts(round_number, draft_before, draft_after_content, prompt_snapshot, profile)

        reviewer = self.reviewer_client or create_reviewer_client(
            self.config.reviewer,
            cwd=self.root,
            phase=phase,
            section_ids=section_ids,
            timeout_seconds=self.timeout_seconds,
        )
        reviewer_feedback = self._call_with_validation_retry(
            round_number=round_number,
            phase=phase,
            profile=profile,
            client_role="reviewer",
            client_config=self.config.reviewer,
            artifact_name="reviewer_feedback.json",
            prompt=reviewer_prompt,
            call=reviewer.review,
            validate=lambda artifact: _validate_reviewer_feedback(
                artifact,
                round_number=round_number,
                profile=profile,
                draft_hash_value=draft_before_hash,
                schema_name="phase2_reviewer_feedback" if phase == "phase_2" else "reviewer_feedback",
            ),
            last_valid_draft_hash=draft_before_hash,
        )
        self.store.write_round_json(round_number, "reviewer_feedback.json", reviewer_feedback)

        reviewer_feedback_json = json.dumps(reviewer_feedback, indent=2, sort_keys=True)
        editor_prompt = render_editor_prompt(
            draft=draft_before,
            reviewer_feedback_json=reviewer_feedback_json,
            round_number=round_number,
            draft_before_hash_value=draft_before_hash,
            draft_after_hash_value=draft_after_hash if explicit_draft_after or not apply else None,
            capture_only=not apply,
        )
        prompt_snapshot = self._prompt_snapshot(
            profile=profile,
            phase=phase,
            reviewer_prompt=reviewer_prompt,
            editor_prompt=editor_prompt,
            draft_before_hash=draft_before_hash,
            draft_after_hash=draft_after_hash,
            draft_before=draft_before,
            draft_after=draft_after_content,
            rubric_hash=rubric_hash,
        )
        self.store.write_round_json(round_number, "prompt_snapshot.json", prompt_snapshot)

        editor = self.editor_client or create_editor_client(
            self.config.editor,
            cwd=self.root,
            timeout_seconds=self.timeout_seconds,
        )
        editor_summary = self._call_with_validation_retry(
            round_number=round_number,
            phase=phase,
            profile=profile,
            client_role="editor",
            client_config=self.config.editor,
            artifact_name="editor_summary.json",
            prompt=editor_prompt,
            call=editor.revise,
            validate=lambda artifact: _validate_editor_summary(
                artifact,
                round_number=round_number,
                draft_before_hash=draft_before_hash,
                draft_after_hash=draft_after_hash if explicit_draft_after or not apply else None,
                require_draft_after_content=apply and not explicit_draft_after,
            ),
            last_valid_draft_hash=draft_before_hash,
        )
        if apply and not explicit_draft_after:
            draft_after_content = str(editor_summary["draft_after_content"])
            draft_after_hash = draft_hash(draft_after_content)
            self.store.write_round_text(round_number, "draft_after.md", draft_after_content)
            prompt_snapshot = self._prompt_snapshot(
                profile=profile,
                phase=phase,
                reviewer_prompt=reviewer_prompt,
                editor_prompt=editor_prompt,
                draft_before_hash=draft_before_hash,
                draft_after_hash=draft_after_hash,
                draft_before=draft_before,
                draft_after=draft_after_content,
                rubric_hash=rubric_hash,
            )
            self.store.write_round_json(round_number, "prompt_snapshot.json", prompt_snapshot)
        self.store.write_round_json(round_number, "editor_summary.json", editor_summary)

        decision_packet = detect_decision_points(
            draft_before=draft_before,
            draft_after=draft_after_content,
            round_number=round_number,
            profile=profile,
            reviewer_feedback=reviewer_feedback,
            editor_summary=editor_summary,
            config=self.config.decision_points,
        )
        self.store.write_round_json(
            round_number,
            "decision_points.json",
            decision_packet,
            schema_name="decision_points",
        )

        unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
        unresolved_packet = {
            "round_number": round_number,
            "draft_hash": draft_after_hash,
            "unresolved_issues": unresolved,
        }
        self.store.write_round_json(round_number, "unresolved_issues.json", unresolved_packet, schema_name="unresolved_issues")
        self.store.write_round_text(round_number, "reviewer_working_notes.md", "Live round; reviewer notes are captured in structured feedback.\n")

        spec_mutated = False
        if apply and draft_after_content != draft_before:
            self.config.spec_path.write_text(draft_after_content, encoding="utf-8")
            spec_mutated = True

        return LiveRoundResult(
            round_number=round_number,
            round_dir=round_dir,
            draft_before_hash=draft_before_hash,
            draft_after_hash=draft_after_hash,
            accepted=accepted_draft(unresolved),
            reviewer_feedback_count=len(reviewer_feedback.get("feedback", [])),
            spec_mutated=spec_mutated,
        )

    def _call_with_validation_retry(
        self,
        *,
        round_number: int,
        phase: str,
        profile: str,
        client_role: str,
        client_config: ClientConfig,
        artifact_name: str,
        prompt: str,
        call: Any,
        validate: Any,
        last_valid_draft_hash: str,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        current_prompt = prompt
        current_validation_errors: list[str] = []
        last_valid_draft_path = _last_valid_draft_path(round_number, client_role=client_role)
        for attempt_number in (1, 2):
            self._write_attempt_prompt_snapshot(
                round_number=round_number,
                phase=phase,
                profile=profile,
                client_role=client_role,
                client_config=client_config,
                artifact_name=artifact_name,
                attempt_number=attempt_number,
                prompt=current_prompt,
                validation_errors=current_validation_errors,
            )
            try:
                artifact = call(current_prompt)
            except Exception as exc:
                validation_errors = [str(exc)]
                raw_path = self._write_invalid_attempt(
                    round_number=round_number,
                    client_role=client_role,
                    attempt_number=attempt_number,
                    artifact={"client_error": str(exc)},
                )
                attempts.append(
                    {
                        "attempt_number": attempt_number,
                        "artifact_name": artifact_name,
                        "validation_errors": validation_errors,
                        "raw_response_path": str(raw_path.relative_to(self.root)),
                    }
                )
                if attempt_number == 1:
                    current_validation_errors = validation_errors
                    current_prompt = _retry_prompt(prompt, artifact_name=artifact_name, validation_errors=validation_errors)
                    continue
                _write_artifact_validation_error(
                    self.config.rounds_dir,
                    round_number=round_number,
                    phase=phase,
                    profile=profile,
                    client_role=client_role,
                    client_config=client_config,
                    attempts=attempts,
                    last_valid_draft_hash=last_valid_draft_hash,
                    last_valid_draft_path=last_valid_draft_path,
                )
                _write_artifact_validation_companion_report(
                    self.root,
                    self.config,
                    round_number=round_number,
                    phase=phase,
                    final_draft_path=last_valid_draft_path,
                )
                raise ValueError(f"{artifact_name} validation failed after retry") from exc
            try:
                validate(artifact)
            except Exception as exc:
                validation_errors = [str(exc)]
                raw_path = self._write_invalid_attempt(
                    round_number=round_number,
                    client_role=client_role,
                    attempt_number=attempt_number,
                    artifact=artifact,
                )
                attempts.append(
                    {
                        "attempt_number": attempt_number,
                        "artifact_name": artifact_name,
                        "validation_errors": validation_errors,
                        "raw_response_path": str(raw_path.relative_to(self.root)),
                    }
                )
                if attempt_number == 1:
                    current_validation_errors = validation_errors
                    current_prompt = _retry_prompt(prompt, artifact_name=artifact_name, validation_errors=validation_errors)
                    continue
                _write_artifact_validation_error(
                    self.config.rounds_dir,
                    round_number=round_number,
                    phase=phase,
                    profile=profile,
                    client_role=client_role,
                    client_config=client_config,
                    attempts=attempts,
                    last_valid_draft_hash=last_valid_draft_hash,
                    last_valid_draft_path=last_valid_draft_path,
                )
                _write_artifact_validation_companion_report(
                    self.root,
                    self.config,
                    round_number=round_number,
                    phase=phase,
                    final_draft_path=last_valid_draft_path,
                )
                raise ValueError(f"{artifact_name} validation failed after retry") from exc
            return artifact
        raise AssertionError("unreachable validation retry state")

    def _write_invalid_attempt(
        self,
        *,
        round_number: int,
        client_role: str,
        attempt_number: int,
        artifact: dict[str, Any],
    ) -> Path:
        filename = f"{client_role}_invalid_attempt_{attempt_number}.json"
        return self.store.write_round_json(round_number, filename, artifact)

    def _write_attempt_prompt_snapshot(
        self,
        *,
        round_number: int,
        phase: str,
        profile: str,
        client_role: str,
        client_config: ClientConfig,
        artifact_name: str,
        attempt_number: int,
        prompt: str,
        validation_errors: list[str],
    ) -> Path:
        round_dir = self.store.round_dir(round_number)
        snapshot_dir = round_dir / "prompt_snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{client_role}-{artifact_name}-attempt-{attempt_number}.json"
        snapshot = {
            "prompt_text": prompt,
            "profile": profile,
            "phase": phase,
            "client_role": client_role,
            "client": {
                "name": client_config.name,
                "version": client_config.version,
                "model": client_config.model,
            },
            "artifact_name": artifact_name,
            "attempt_number": attempt_number,
            "validation_errors": validation_errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config_snapshot": {
                "review_max_rounds": self.config.review_max_rounds,
                "target_phase": self.config.convergence.target_phase,
                "target_mode": self.config.convergence.target_mode,
            },
        }
        path = snapshot_dir / filename
        path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _write_pre_review_artifacts(
        self,
        round_number: int,
        draft_before: str,
        draft_after: str,
        prompt_snapshot: dict[str, Any],
        profile: str,
    ) -> None:
        self.store.write_round_text(round_number, "draft_before.md", draft_before)
        self.store.write_round_text(round_number, "draft_after.md", draft_after)
        self.store.write_round_json(round_number, "profile_used.yaml", {"profile": profile})
        self.store.write_round_json(round_number, "prompt_snapshot.json", prompt_snapshot)

    def _prompt_snapshot(
        self,
        *,
        profile: str,
        phase: str,
        reviewer_prompt: str,
        editor_prompt: str | None,
        draft_before_hash: str,
        draft_after_hash: str,
        draft_before: str,
        draft_after: str,
        rubric_hash: str,
    ) -> dict[str, Any]:
        semantic_hash = semantic_change_hash(draft_before, draft_after)
        return {
            "prompt_text": reviewer_prompt,
            "reviewer_prompt_text": reviewer_prompt,
            "editor_prompt_text": editor_prompt,
            "profile": profile,
            "phase": phase,
            "client": asdict(self.config.reviewer),
            "editor_client": asdict(self.config.editor),
            "version": self.config.reviewer.version,
            "model": self.config.reviewer.model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config_snapshot": {
                "review_max_rounds": self.config.review_max_rounds,
                "target_phase": self.config.convergence.target_phase,
                "target_mode": self.config.convergence.target_mode,
            },
            "rubric_content_hash": rubric_hash,
            "draft_hash": draft_before_hash,
            "draft_after_hash": draft_after_hash,
            "semantic_change_hash": semantic_hash,
        }


def create_reviewer_client(
    config: ClientConfig,
    *,
    cwd: Path,
    phase: str,
    section_ids: list[str],
    timeout_seconds: int | None,
) -> ReviewerClient:
    if config.name == "codex":
        return CodexReviewerClient(
            command=config.command,
            model=config.model,
            cwd=cwd,
            phase=phase,
            section_ids=section_ids,
            timeout_seconds=timeout_seconds,
        )
    if config.name == "claude-code":
        return ClaudeCodeReviewerClient(
            command=config.command,
            model=config.model,
            cwd=cwd,
            phase=phase,
            section_ids=section_ids,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"unsupported reviewer client {config.name!r}")


def create_editor_client(config: ClientConfig, *, cwd: Path, timeout_seconds: int | None) -> EditorClient:
    if config.name == "codex":
        return CodexEditorClient(
            command=config.command,
            model=config.model,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
    if config.name == "claude-code":
        return ClaudeCodeEditorClient(
            command=config.command,
            model=config.model,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"unsupported editor client {config.name!r}")


def validate_live_config(config: OrchestratorConfig) -> list[dict[str, str]]:
    invalid: list[dict[str, str]] = []
    for role_name, client in (("editor", config.editor), ("reviewer", config.reviewer)):
        for field_name in ("version", "model"):
            if not getattr(client, field_name).strip():
                invalid.append({"path": f"clients.{role_name}.{field_name}", "reason": "must be a non-empty string"})
    return invalid


def _write_config_error(rounds_dir: Path, invalid_fields: list[dict[str, str]]) -> None:
    rounds_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "terminal_state": "CONFIG_INVALID",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "invalid_fields": invalid_fields,
    }
    validate_artifact(artifact, "config_validation_error")
    (rounds_dir / "config_validation_error.json").write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_artifact_validation_error(
    rounds_dir: Path,
    *,
    round_number: int,
    phase: str,
    profile: str,
    client_role: str,
    client_config: ClientConfig,
    attempts: list[dict[str, Any]],
    last_valid_draft_hash: str,
    last_valid_draft_path: str,
) -> None:
    rounds_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "terminal_state": "HALTED_ARTIFACT_INVALID",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round_number": round_number,
        "phase": phase,
        "profile": profile,
        "client_role": client_role,
        "client": {
            "name": client_config.name,
            "version": client_config.version,
            "model": client_config.model,
        },
        "attempts": attempts,
        "retry_exhausted": True,
        "last_valid_draft_hash": last_valid_draft_hash,
        "last_valid_draft_path": last_valid_draft_path,
        "recommendation": "manual_review_required",
    }
    validate_artifact(artifact, "artifact_validation_error")
    (rounds_dir / "artifact_validation_error.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _last_valid_draft_path(round_number: int, *, client_role: str) -> str:
    filename = "draft_before.md" if client_role == "reviewer" else "draft_after.md"
    return str(Path("rounds") / f"round-{round_number}" / filename)


def _write_artifact_validation_companion_report(
    root: Path,
    config: OrchestratorConfig,
    *,
    round_number: int,
    phase: str,
    final_draft_path: str,
) -> None:
    writer = ReportWriter(root)
    if phase == "phase_2":
        writer.write_convergence_failure_report(
            round_number=round_number,
            final_draft_path=final_draft_path,
            final_declaration_path=None,
            target_phase=config.convergence.target_phase,
            target_mode=config.convergence.target_mode,
            unresolved_blockers=[],
            unresolved_major_issues=[],
            unresolved_rubric_gaps=[],
            reviewer_final_status="not_run",
            last_accepted_draft_hash=None,
            exit_reason="artifact validation retry exhausted",
            recommendation="manual_review_required",
            terminal_state="HALTED_ARTIFACT_INVALID",
        )
        return
    writer.write_technical_failure_report(
        round_number=round_number,
        final_draft_path=final_draft_path,
        unresolved_blockers=[],
        unresolved_major_issues=[],
        unresolved_conflicts=[],
        unresolved_oscillation=None,
        last_accepted_draft_hash=None,
        exit_reason="artifact validation retry exhausted",
        recommendation="manual_review_required",
        terminal_state="HALTED_ARTIFACT_INVALID",
    )


def _retry_prompt(prompt: str, *, artifact_name: str, validation_errors: list[str]) -> str:
    return (
        prompt.rstrip()
        + "\n\n"
        + "Your previous response did not validate as "
        + artifact_name
        + ". Return one corrected JSON object only. Validation errors:\n"
        + "\n".join(f"- {error}" for error in validation_errors)
        + "\n"
    )


def _validate_reviewer_feedback(
    artifact: dict[str, Any],
    *,
    round_number: int,
    profile: str,
    draft_hash_value: str,
    schema_name: str,
) -> None:
    _require_reviewer_context(
        artifact,
        round_number=round_number,
        profile=profile,
        draft_hash_value=draft_hash_value,
    )
    validate_artifact(artifact, schema_name)


def _validate_editor_summary(
    artifact: dict[str, Any],
    *,
    round_number: int,
    draft_before_hash: str,
    draft_after_hash: str | None,
    require_draft_after_content: bool = False,
) -> None:
    if require_draft_after_content and not isinstance(artifact.get("draft_after_content"), str):
        raise ValueError("editor_summary draft_after_content is required for applied editor-generated revisions")
    if isinstance(artifact.get("draft_after_content"), str):
        computed_hash = draft_hash(artifact["draft_after_content"])
        artifact["draft_after_hash"] = computed_hash
        if draft_after_hash is not None and computed_hash != draft_after_hash:
            raise ValueError(
                f"editor_summary draft_after_content hash mismatch: expected {draft_after_hash!r}, got {computed_hash!r}"
            )
    _require_editor_hashes(
        artifact,
        round_number=round_number,
        draft_before_hash=draft_before_hash,
        draft_after_hash=draft_after_hash,
    )
    validate_artifact(artifact, "editor_summary")


def _read_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _maybe_promote_phase2_version(config: OrchestratorConfig) -> None:
    if not (config.rounds_dir / "run_state.json").exists():
        return
    promote_spec_file_for_phase2(
        spec_path=config.spec_path,
        history_path=config.history_path,
        rounds_dir=config.rounds_dir,
    )


def _require_editor_hashes(
    editor_summary: dict[str, Any],
    *,
    round_number: int,
    draft_before_hash: str,
    draft_after_hash: str | None,
) -> None:
    expected = {
        "round_number": round_number,
        "draft_before_hash": draft_before_hash,
    }
    if draft_after_hash is not None:
        expected["draft_after_hash"] = draft_after_hash
    for key, value in expected.items():
        if editor_summary.get(key) != value:
            raise ValueError(f"editor_summary {key} mismatch: expected {value!r}, got {editor_summary.get(key)!r}")


def _require_reviewer_context(
    reviewer_feedback: dict[str, Any],
    *,
    round_number: int,
    profile: str,
    draft_hash_value: str,
) -> None:
    expected = {
        "round_number": round_number,
        "profile": profile,
        "draft_hash": draft_hash_value,
    }
    for key, value in expected.items():
        if reviewer_feedback.get(key) != value:
            raise ValueError(f"reviewer_feedback {key} mismatch: expected {value!r}, got {reviewer_feedback.get(key)!r}")
