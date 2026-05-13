"""Live single-round orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from whetstone.artifacts import ArtifactStore
from whetstone.clients import ClaudeCodeEditorClient, ClaudeCodeReviewerClient, CodexEditorClient, CodexReviewerClient
from whetstone.config import ClientConfig, OrchestratorConfig
from whetstone.contracts import validate_artifact
from whetstone.contract_surface import read_contract_surface_report
from whetstone.decisions import detect_decision_points, operator_decision_checkpoint
from whetstone.evaluation import accepted_draft
from whetstone.hashing import draft_hash, rubric_content_hash, semantic_change_hash
from whetstone.prompts import render_editor_prompt, render_reviewer_prompt
from whetstone.reports import ReportWriter
from whetstone.runner import _unresolved_issues
from whetstone.rubrics import read_rubric_text, write_rubric_manifest
from whetstone.sections import section_index
from whetstone.scope import LoadedScopeContract, read_scope_contract, scope_contract_summary
from whetstone.text_validation import validate_generated_text
from whetstone.versioning import promote_spec_file_for_phase2, stamp_spec_text_for_round


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


@dataclass(frozen=True)
class ContextFile:
    label: str
    path: str
    sha256: str


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
            write_rubric_manifest(self.config)
            _maybe_promote_phase2_version(self.config)

        round_dir = self.store.begin_round(round_number, overwrite=overwrite)
        draft_before = self.config.spec_path.read_text(encoding="utf-8")
        draft_before_hash = draft_hash(draft_before)
        explicit_draft_after = draft_after is not None
        draft_after_content = draft_after if draft_after is not None else draft_before
        draft_after_hash = draft_hash(draft_after_content)
        rubric = read_rubric_text(self.config)
        rubric_hash = rubric_content_hash(rubric) if rubric is not None else "0" * 64
        scope_contract = read_scope_contract(self.config.scope_contract.path)
        declaration = (
            _read_optional(self.config.declaration_path)
            if phase == "phase_2" and profile == "convergence_strict_check"
            else None
        )
        section_ids = [section.id for section in section_index(draft_before)] if phase == "phase_2" else []
        reviewer_context_files = self._write_reviewer_context_files(
            round_number=round_number,
            draft_before=draft_before,
            rubric=rubric,
            declaration=declaration,
            scope_contract=scope_contract,
        )
        context_path_by_label = {item.label: item.path for item in reviewer_context_files}
        reference_context_paths = _reference_context_prompt_paths(reviewer_context_files, self.config)

        reviewer_prompt = render_reviewer_prompt(
            profile=profile,
            draft="",
            rubric=None,
            declaration=None,
            draft_path=context_path_by_label.get("draft_before"),
            rubric_path=context_path_by_label.get("rubric"),
            declaration_path=context_path_by_label.get("declaration"),
            scope_contract_path=context_path_by_label.get("scope_contract"),
            reference_context_paths=reference_context_paths,
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
            context_files=reviewer_context_files,
            scope_contract=scope_contract,
        )
        self._write_pre_review_artifacts(
            round_number,
            draft_before,
            draft_after_content,
            prompt_snapshot,
            profile,
            round_kind="review_editor",
        )

        reviewer = self.reviewer_client or create_reviewer_client(
            self.config.reviewer,
            cwd=self.root,
            phase=phase,
            section_ids=section_ids,
            timeout_seconds=self._timeout_for_role("reviewer"),
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
            context_files=reviewer_context_files,
        )
        self.store.write_round_json(round_number, "reviewer_feedback.json", reviewer_feedback)
        if not reviewer_feedback.get("feedback") and not explicit_draft_after:
            editor_summary = _no_op_editor_summary(
                round_number=round_number,
                draft_hash_value=draft_before_hash,
                draft_after_content=draft_before if apply else None,
            )
            _validate_editor_summary(
                editor_summary,
                round_number=round_number,
                draft_before_hash=draft_before_hash,
                draft_after_hash=draft_before_hash,
                require_draft_after_content=False,
                draft_before_content=draft_before if apply else None,
            )
            unresolved: list[dict[str, Any]] = []
            accepted = True
            if apply:
                self.store.write_round_text(round_number, "draft_after.md", draft_before)
            self.store.write_round_json(round_number, "editor_summary.json", editor_summary)
            decision_packet = detect_decision_points(
                draft_before=draft_before,
                draft_after=draft_before,
                round_number=round_number,
                profile=profile,
                reviewer_feedback=reviewer_feedback,
                editor_summary=editor_summary,
                config=self.config.decision_points,
                scope_contract=scope_contract.packet if scope_contract is not None else None,
            )
            self.store.write_round_json(
                round_number,
                "decision_points.json",
                decision_packet,
                schema_name="decision_points",
            )
            self._write_operator_decision_checkpoint(
                round_number=round_number,
                profile=profile,
                draft_hash_value=draft_before_hash,
                reviewer_feedback=reviewer_feedback,
                decision_packet=decision_packet,
                unresolved=[],
            )
            unresolved_packet = {
                "round_number": round_number,
                "draft_hash": draft_before_hash,
                "unresolved_issues": unresolved,
            }
            self.store.write_round_json(
                round_number,
                "unresolved_issues.json",
                unresolved_packet,
                schema_name="unresolved_issues",
            )
            self.store.write_round_text(
                round_number,
                "reviewer_working_notes.md",
                "Live round; reviewer notes are captured in structured feedback.\n",
            )
            return LiveRoundResult(
                round_number=round_number,
                round_dir=round_dir,
                draft_before_hash=draft_before_hash,
                draft_after_hash=draft_before_hash,
                accepted=accepted,
                reviewer_feedback_count=0,
                spec_mutated=False,
            )

        reviewer_feedback_json = json.dumps(reviewer_feedback, indent=2, sort_keys=True)
        editor_context_files = [
            *reviewer_context_files,
            self._write_context_file(
                round_number=round_number,
                label="reviewer_feedback",
                filename="reviewer_feedback.json",
                content=reviewer_feedback_json + "\n",
            ),
        ]
        synthesis_report = read_contract_surface_report(self.config.rounds_dir, profile=profile)
        if synthesis_report is not None:
            editor_context_files.append(
                self._write_context_file(
                    round_number=round_number,
                    label="contract_surface_report",
                    filename="contract_surface_report.json",
                    content=json.dumps(synthesis_report, indent=2, sort_keys=True) + "\n",
                )
            )
        editor_context_path_by_label = {item.label: item.path for item in editor_context_files}
        editor_reference_context_paths = _reference_context_prompt_paths(editor_context_files, self.config)
        editor_prompt = render_editor_prompt(
            draft="",
            reviewer_feedback_json="",
            draft_path=editor_context_path_by_label.get("draft_before"),
            reviewer_feedback_path=editor_context_path_by_label.get("reviewer_feedback"),
            scope_contract_path=editor_context_path_by_label.get("scope_contract"),
            reference_context_paths=editor_reference_context_paths,
            phase=phase,
            round_number=round_number,
            draft_before_hash_value=draft_before_hash,
            draft_after_hash_value=draft_after_hash if explicit_draft_after or not apply else None,
            capture_only=not apply,
            synthesis_report_path=editor_context_path_by_label.get("contract_surface_report"),
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
            context_files=editor_context_files,
            scope_contract=scope_contract,
        )
        self.store.write_round_json(round_number, "prompt_snapshot.json", prompt_snapshot)

        editor = self.editor_client or create_editor_client(
            self.config.editor,
            cwd=self.root,
            timeout_seconds=self._timeout_for_role("editor"),
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
                draft_before_content=draft_before if apply and not explicit_draft_after else None,
            ),
            last_valid_draft_hash=draft_before_hash,
            context_files=editor_context_files,
        )
        if apply and not explicit_draft_after:
            draft_after_content = str(editor_summary["draft_after_content"])
            draft_after_hash = draft_hash(draft_after_content)

        unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
        accepted = accepted_draft(unresolved)
        version_stamp = None
        if apply and accepted and draft_after_content != draft_before:
            version_stamp = _try_stamp_spec_text_for_round(draft_after_content, phase=phase)
            if version_stamp is not None:
                draft_after_content = version_stamp.content
                draft_after_hash = version_stamp.after_hash
                editor_summary["draft_after_hash"] = draft_after_hash
                if "draft_after_content" in editor_summary or not explicit_draft_after:
                    editor_summary["draft_after_content"] = draft_after_content
                _append_version_stamp_history(
                    self.config.history_path,
                    round_number=round_number,
                    phase=phase,
                    result=version_stamp,
                )

        if apply:
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
                context_files=editor_context_files,
                scope_contract=scope_contract,
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
            scope_contract=scope_contract.packet if scope_contract is not None else None,
        )
        self.store.write_round_json(
            round_number,
            "decision_points.json",
            decision_packet,
            schema_name="decision_points",
        )
        self._write_operator_decision_checkpoint(
            round_number=round_number,
            profile=profile,
            draft_hash_value=draft_after_hash,
            reviewer_feedback=reviewer_feedback,
            decision_packet=decision_packet,
            unresolved=unresolved,
        )

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
            accepted=accepted,
            reviewer_feedback_count=len(reviewer_feedback.get("feedback", [])),
            spec_mutated=spec_mutated,
        )

    def run_review_only_round(
        self,
        *,
        round_number: int,
        profile: str,
        phase: str = "phase_1",
        overwrite: bool = False,
    ) -> LiveRoundResult:
        """Run and persist an independent reviewer pass without invoking the Editor."""

        invalid_fields = validate_live_config(self.config)
        if invalid_fields:
            _write_config_error(self.config.rounds_dir, invalid_fields)
            raise ValueError("configuration validation failed")
        round_dir = self.store.begin_round(round_number, overwrite=overwrite)
        draft_before = self.config.spec_path.read_text(encoding="utf-8")
        draft_before_hash = draft_hash(draft_before)
        rubric = read_rubric_text(self.config)
        rubric_hash = rubric_content_hash(rubric) if rubric is not None else "0" * 64
        scope_contract = read_scope_contract(self.config.scope_contract.path)
        section_ids = [section.id for section in section_index(draft_before)] if phase == "phase_2" else []
        reviewer_context_files = self._write_reviewer_context_files(
            round_number=round_number,
            draft_before=draft_before,
            rubric=rubric,
            declaration=None,
            scope_contract=scope_contract,
        )
        context_path_by_label = {item.label: item.path for item in reviewer_context_files}
        reviewer_prompt = render_reviewer_prompt(
            profile=profile,
            draft="",
            rubric=None,
            declaration=None,
            draft_path=context_path_by_label.get("draft_before"),
            rubric_path=context_path_by_label.get("rubric"),
            scope_contract_path=context_path_by_label.get("scope_contract"),
            reference_context_paths=_reference_context_prompt_paths(reviewer_context_files, self.config),
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
            draft_after_hash=draft_before_hash,
            draft_before=draft_before,
            draft_after=draft_before,
            rubric_hash=rubric_hash,
            context_files=reviewer_context_files,
            scope_contract=scope_contract,
        )
        self._write_pre_review_artifacts(
            round_number,
            draft_before,
            draft_before,
            prompt_snapshot,
            profile,
            round_kind="review_only",
        )

        reviewer = self.reviewer_client or create_reviewer_client(
            self.config.reviewer,
            cwd=self.root,
            phase=phase,
            section_ids=section_ids,
            timeout_seconds=self._timeout_for_role("reviewer"),
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
            context_files=reviewer_context_files,
        )
        self.store.write_round_json(round_number, "reviewer_feedback.json", reviewer_feedback)
        editor_summary = _no_op_editor_summary(
            round_number=round_number,
            draft_hash_value=draft_before_hash,
            draft_after_content=draft_before,
        )
        self.store.write_round_json(round_number, "editor_summary.json", editor_summary)
        self.store.write_round_json(
            round_number,
            "decision_points.json",
            detect_decision_points(
                draft_before=draft_before,
                draft_after=draft_before,
                round_number=round_number,
                profile=profile,
                reviewer_feedback=reviewer_feedback,
                editor_summary=editor_summary,
                config=self.config.decision_points,
                scope_contract=scope_contract.packet if scope_contract is not None else None,
            ),
            schema_name="decision_points",
        )
        self.store.write_round_json(
            round_number,
            "unresolved_issues.json",
            {
                "round_number": round_number,
                "draft_hash": draft_before_hash,
                "unresolved_issues": _unresolved_issues(reviewer_feedback, editor_summary),
            },
            schema_name="unresolved_issues",
        )
        self.store.write_round_text(
            round_number,
            "reviewer_working_notes.md",
            "Live review-only round; reviewer notes are captured in structured feedback.\n",
        )
        return LiveRoundResult(
            round_number=round_number,
            round_dir=round_dir,
            draft_before_hash=draft_before_hash,
            draft_after_hash=draft_before_hash,
            accepted=not reviewer_feedback.get("feedback"),
            reviewer_feedback_count=len(reviewer_feedback.get("feedback", [])),
            spec_mutated=False,
        )

    def resume_editor_round(
        self,
        *,
        round_number: int,
        profile: str,
        phase: str = "phase_1",
        apply: bool = True,
        start_attempt_number: int = 2,
    ) -> LiveRoundResult:
        """Resume a round that already has validated reviewer feedback."""

        round_dir = self.store.round_dir(round_number)
        if not round_dir.exists():
            raise ValueError(f"round-{round_number} does not exist")
        draft_before = round_dir.joinpath("draft_before.md").read_text(encoding="utf-8")
        draft_before_hash = draft_hash(draft_before)
        reviewer_feedback = json.loads(round_dir.joinpath("reviewer_feedback.json").read_text(encoding="utf-8"))
        _validate_reviewer_feedback(
            reviewer_feedback,
            round_number=round_number,
            profile=profile,
            draft_hash_value=draft_before_hash,
            schema_name="phase2_reviewer_feedback" if phase == "phase_2" else "reviewer_feedback",
        )
        reviewer_feedback_json = json.dumps(reviewer_feedback, indent=2, sort_keys=True)
        scope_contract = read_scope_contract(self.config.scope_contract.path)
        editor_context_files = [
            self._write_context_file(
                round_number=round_number,
                label="draft_before",
                filename="draft_before.md",
                content=draft_before,
            ),
            self._write_context_file(
                round_number=round_number,
                label="reviewer_feedback",
                filename="reviewer_feedback.json",
                content=reviewer_feedback_json + "\n",
            ),
        ]
        if scope_contract is not None:
            editor_context_files.append(
                self._write_context_file(
                    round_number=round_number,
                    label="scope_contract",
                    filename="scope_contract.json",
                    content=json.dumps(scope_contract.packet, indent=2, sort_keys=True) + "\n",
                )
            )
        editor_context_files.extend(self._write_reference_context_files(round_number=round_number))
        synthesis_report = read_contract_surface_report(self.config.rounds_dir, profile=profile)
        if synthesis_report is not None:
            editor_context_files.append(
                self._write_context_file(
                    round_number=round_number,
                    label="contract_surface_report",
                    filename="contract_surface_report.json",
                    content=json.dumps(synthesis_report, indent=2, sort_keys=True) + "\n",
                )
            )
        editor_context_path_by_label = {item.label: item.path for item in editor_context_files}
        reference_context_paths = _reference_context_prompt_paths(editor_context_files, self.config)
        editor_prompt = render_editor_prompt(
            draft="",
            reviewer_feedback_json="",
            draft_path=editor_context_path_by_label.get("draft_before"),
            reviewer_feedback_path=editor_context_path_by_label.get("reviewer_feedback"),
            scope_contract_path=editor_context_path_by_label.get("scope_contract"),
            reference_context_paths=reference_context_paths,
            phase=phase,
            round_number=round_number,
            draft_before_hash_value=draft_before_hash,
            draft_after_hash_value=None,
            capture_only=not apply,
            synthesis_report_path=editor_context_path_by_label.get("contract_surface_report"),
        )
        prompt_snapshot = self._prompt_snapshot(
            profile=profile,
            phase=phase,
            reviewer_prompt=_read_prompt_snapshot_field(round_dir, "reviewer_prompt_text"),
            editor_prompt=editor_prompt,
            draft_before_hash=draft_before_hash,
            draft_after_hash=draft_before_hash,
            draft_before=draft_before,
            draft_after=draft_before,
            rubric_hash=_read_prompt_snapshot_field(round_dir, "rubric_content_hash") or "0" * 64,
            context_files=editor_context_files,
            scope_contract=scope_contract,
        )
        self.store.write_round_json(round_number, "prompt_snapshot.json", prompt_snapshot)

        editor = self.editor_client or create_editor_client(
            self.config.editor,
            cwd=self.root,
            timeout_seconds=self._timeout_for_role("editor"),
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
                draft_after_hash=None,
                require_draft_after_content=apply,
                draft_before_content=draft_before if apply else None,
            ),
            last_valid_draft_hash=draft_before_hash,
            start_attempt_number=start_attempt_number,
            context_files=editor_context_files,
        )
        draft_after_content = str(editor_summary["draft_after_content"]) if apply else draft_before
        draft_after_hash = draft_hash(draft_after_content)
        unresolved = _unresolved_issues(reviewer_feedback, editor_summary)
        accepted = accepted_draft(unresolved)
        if apply and accepted and draft_after_content != draft_before:
            version_stamp = _try_stamp_spec_text_for_round(draft_after_content, phase=phase)
            if version_stamp is not None:
                draft_after_content = version_stamp.content
                draft_after_hash = version_stamp.after_hash
                editor_summary["draft_after_hash"] = draft_after_hash
                editor_summary["draft_after_content"] = draft_after_content
                _append_version_stamp_history(
                    self.config.history_path,
                    round_number=round_number,
                    phase=phase,
                    result=version_stamp,
                )
        if apply:
            self.store.write_round_text(round_number, "draft_after.md", draft_after_content)
        self.store.write_round_json(round_number, "editor_summary.json", editor_summary)
        decision_packet = detect_decision_points(
            draft_before=draft_before,
            draft_after=draft_after_content,
            round_number=round_number,
            profile=profile,
            reviewer_feedback=reviewer_feedback,
            editor_summary=editor_summary,
            config=self.config.decision_points,
            scope_contract=scope_contract.packet if scope_contract is not None else None,
        )
        self.store.write_round_json(round_number, "decision_points.json", decision_packet, schema_name="decision_points")
        self._write_operator_decision_checkpoint(
            round_number=round_number,
            profile=profile,
            draft_hash_value=draft_after_hash,
            reviewer_feedback=reviewer_feedback,
            decision_packet=decision_packet,
            unresolved=unresolved,
        )
        self.store.write_round_json(
            round_number,
            "unresolved_issues.json",
            {
                "round_number": round_number,
                "draft_hash": draft_after_hash,
                "unresolved_issues": unresolved,
            },
            schema_name="unresolved_issues",
        )
        self.store.write_round_text(round_number, "reviewer_working_notes.md", "Live resumed round; reviewer notes are captured in structured feedback.\n")
        prompt_snapshot = self._prompt_snapshot(
            profile=profile,
            phase=phase,
            reviewer_prompt=_read_prompt_snapshot_field(round_dir, "reviewer_prompt_text"),
            editor_prompt=editor_prompt,
            draft_before_hash=draft_before_hash,
            draft_after_hash=draft_after_hash,
            draft_before=draft_before,
            draft_after=draft_after_content,
            rubric_hash=_read_prompt_snapshot_field(round_dir, "rubric_content_hash") or "0" * 64,
            context_files=editor_context_files,
            scope_contract=scope_contract,
        )
        self.store.write_round_json(round_number, "prompt_snapshot.json", prompt_snapshot)
        spec_mutated = False
        if apply and draft_after_content != draft_before:
            self.config.spec_path.write_text(draft_after_content, encoding="utf-8")
            spec_mutated = True
        _remove_top_level_timeout_artifacts(self.config.rounds_dir)
        return LiveRoundResult(
            round_number=round_number,
            round_dir=round_dir,
            draft_before_hash=draft_before_hash,
            draft_after_hash=draft_after_hash,
            accepted=accepted,
            reviewer_feedback_count=len(reviewer_feedback.get("feedback", [])),
            spec_mutated=spec_mutated,
        )

    def _write_operator_decision_checkpoint(
        self,
        *,
        round_number: int,
        profile: str,
        draft_hash_value: str,
        reviewer_feedback: dict[str, Any],
        decision_packet: dict[str, Any],
        unresolved: list[dict[str, Any]],
    ) -> None:
        unresolved_for_checkpoint = unresolved if self.config.decision_points.enabled else []
        packet = operator_decision_checkpoint(
            round_number=round_number,
            profile=profile,
            draft_hash_value=draft_hash_value,
            reviewer_feedback=reviewer_feedback,
            decision_points=decision_packet,
            unresolved_issues=unresolved_for_checkpoint,
        )
        self.store.write_round_json(
            round_number,
            "operator_decision_checkpoint.json",
            packet,
            schema_name="operator_decision_checkpoint",
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
        start_attempt_number: int = 1,
        context_files: list[ContextFile] | None = None,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        current_prompt = prompt
        current_validation_errors: list[str] = []
        last_valid_draft_path = _last_valid_draft_path(round_number, client_role=client_role)
        for attempt_number in range(start_attempt_number, start_attempt_number + 2):
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
                context_files=context_files or [],
            )

            try:
                artifact = call(current_prompt)
            except Exception as exc:
                telemetry_path = self._write_client_telemetry(
                    round_number=round_number,
                    phase=phase,
                    profile=profile,
                    client_role=client_role,
                    client_config=client_config,
                    artifact_name=artifact_name,
                    attempt_number=attempt_number,
                    call=call,
                )
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
                        "telemetry_path": str(telemetry_path.relative_to(self.root)) if telemetry_path else None,
                    }
                )
                if _is_timeout_error(exc):
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
                        failure_type="client_timeout",
                    )
                    _write_artifact_validation_companion_report(
                        self.root,
                        self.config,
                        round_number=round_number,
                        phase=phase,
                        final_draft_path=last_valid_draft_path,
                        failure_type="client_timeout",
                    )
                    raise ValueError(f"{artifact_name} timed out") from exc
                if attempt_number == start_attempt_number:
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
                    failure_type="client_error",
                )
                _write_artifact_validation_companion_report(
                    self.root,
                    self.config,
                    round_number=round_number,
                    phase=phase,
                    final_draft_path=last_valid_draft_path,
                    failure_type="client_error",
                )
                raise ValueError(f"{artifact_name} validation failed after retry") from exc
            try:
                validate(artifact)
            except Exception as exc:
                telemetry_path = self._write_client_telemetry(
                    round_number=round_number,
                    phase=phase,
                    profile=profile,
                    client_role=client_role,
                    client_config=client_config,
                    artifact_name=artifact_name,
                    attempt_number=attempt_number,
                    call=call,
                )
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
                        "telemetry_path": str(telemetry_path.relative_to(self.root)) if telemetry_path else None,
                    }
                )
                if attempt_number == start_attempt_number:
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
            self._write_client_telemetry(
                round_number=round_number,
                phase=phase,
                profile=profile,
                client_role=client_role,
                client_config=client_config,
                artifact_name=artifact_name,
                attempt_number=attempt_number,
                call=call,
            )
            return artifact
        raise AssertionError("unreachable validation retry state")

    def _timeout_for_role(self, role: str) -> int | None:
        if self.timeout_seconds is not None:
            return self.timeout_seconds
        if role == "reviewer":
            return self.config.timeouts.reviewer_seconds
        if role == "editor":
            return self.config.timeouts.editor_seconds
        raise ValueError(f"unsupported client role {role!r}")

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
        context_files: list[ContextFile],
    ) -> Path:
        round_dir = self.store.round_dir(round_number)
        snapshot_dir = round_dir / "prompt_snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{client_role}-{artifact_name}-attempt-{attempt_number}.json"
        snapshot = {
            "prompt_text": prompt,
            "context_files": _context_file_packets(context_files),
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
                "workflow": self.config.workflow,
                "rubric_profile": self.config.convergence.rubric_profile,
                "rubric_source": self.config.convergence.rubric_source,
                "rubric_label": self.config.convergence.rubric_label,
                "rubric_manifest_path": _rubric_manifest_path(self.config) if phase == "phase_2" else None,
                "reference_context": _reference_context_config_snapshot(self.config, self.root),
            },
        }
        path = snapshot_dir / filename
        path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _write_client_telemetry(
        self,
        *,
        round_number: int,
        phase: str,
        profile: str,
        client_role: str,
        client_config: ClientConfig,
        artifact_name: str,
        attempt_number: int,
        call: Any,
    ) -> Path | None:
        telemetry_dir = self.store.round_dir(round_number) / "client_telemetry"
        stem = f"{client_role}-{artifact_name}-attempt-{attempt_number}"
        path = telemetry_dir / f"{stem}.json"
        try:
            telemetry_dir.mkdir(parents=True, exist_ok=True)
            telemetry = _last_client_telemetry(call)
            raw_envelope_path = _write_telemetry_sidecar(
                telemetry_dir / f"{stem}-raw-envelope.json",
                telemetry.get("raw_envelope") if telemetry else None,
                self.root,
            )
            stdout_path = _write_telemetry_text_sidecar(
                telemetry_dir / f"{stem}-stdout.txt",
                telemetry.get("stdout") if telemetry else None,
                self.root,
            )
            stderr_path = _write_telemetry_text_sidecar(
                telemetry_dir / f"{stem}-stderr.txt",
                telemetry.get("stderr") if telemetry else None,
                self.root,
            )
            packet = _client_telemetry_packet(
                round_number=round_number,
                phase=phase,
                profile=profile,
                client_role=client_role,
                client_config=client_config,
                artifact_name=artifact_name,
                attempt_number=attempt_number,
                telemetry=telemetry,
                raw_envelope_path=raw_envelope_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            validate_artifact(packet, "client_telemetry")
            path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception as exc:
            _record_telemetry_warning_safely(
                round_dir=self.store.round_dir(round_number),
                telemetry_dir=telemetry_dir,
                warning={
                    "artifact_name": artifact_name,
                    "attempt_number": attempt_number,
                    "client_role": client_role,
                    "warning": f"client telemetry persistence failed: {exc}",
                },
            )
            return None
        write_round_telemetry_summary(self.store.round_dir(round_number))
        return path

    def _write_pre_review_artifacts(
        self,
        round_number: int,
        draft_before: str,
        draft_after: str,
        prompt_snapshot: dict[str, Any],
        profile: str,
        round_kind: str,
    ) -> None:
        self.store.write_round_text(round_number, "draft_before.md", draft_before)
        self.store.write_round_text(round_number, "draft_after.md", draft_after)
        self.store.write_round_json(round_number, "profile_used.yaml", {"profile": profile, "round_kind": round_kind})
        self.store.write_round_json(round_number, "prompt_snapshot.json", prompt_snapshot)

    def _write_reviewer_context_files(
        self,
        *,
        round_number: int,
        draft_before: str,
        rubric: str | None,
        declaration: str | None,
        scope_contract: LoadedScopeContract | None = None,
    ) -> list[ContextFile]:
        context_files = [
            self._write_context_file(
                round_number=round_number,
                label="draft_before",
                filename="draft_before.md",
                content=draft_before,
            )
        ]
        if rubric is not None:
            context_files.append(
                self._write_context_file(
                    round_number=round_number,
                    label="rubric",
                    filename="rubric.md",
                    content=rubric,
                )
            )
        if declaration is not None:
            context_files.append(
                self._write_context_file(
                    round_number=round_number,
                    label="declaration",
                    filename="convergence_declaration.md",
                    content=declaration,
                )
            )
        if scope_contract is not None:
            context_files.append(
                self._write_context_file(
                    round_number=round_number,
                    label="scope_contract",
                    filename="scope_contract.json",
                    content=json.dumps(scope_contract.packet, indent=2, sort_keys=True) + "\n",
                )
            )
        context_files.extend(self._write_reference_context_files(round_number=round_number))
        return context_files

    def _write_reference_context_files(self, *, round_number: int) -> list[ContextFile]:
        context_files: list[ContextFile] = []
        for item in self.config.reference_context_files:
            if not item.path.exists():
                continue
            label = f"reference:{item.label}"
            filename = f"reference_{_safe_context_filename(item.label)}{item.path.suffix or '.md'}"
            context_files.append(
                self._write_context_file(
                    round_number=round_number,
                    label=label,
                    filename=filename,
                    content=item.path.read_text(encoding="utf-8"),
                )
            )
        return context_files

    def _write_context_file(self, *, round_number: int, label: str, filename: str, content: str) -> ContextFile:
        context_dir = self.store.round_dir(round_number) / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        path = context_dir / filename
        path.write_text(content, encoding="utf-8")
        return ContextFile(
            label=label,
            path=_relative_path(path, self.root),
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

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
        context_files: list[ContextFile] | None = None,
        scope_contract: LoadedScopeContract | None = None,
    ) -> dict[str, Any]:
        semantic_hash = semantic_change_hash(draft_before, draft_after)
        return {
            "prompt_text": reviewer_prompt,
            "reviewer_prompt_text": reviewer_prompt,
            "editor_prompt_text": editor_prompt,
            "context_files": _context_file_packets(context_files or []),
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
                "workflow": self.config.workflow,
                "rubric_profile": self.config.convergence.rubric_profile,
                "rubric_source": self.config.convergence.rubric_source,
                "rubric_label": self.config.convergence.rubric_label,
                "rubric_manifest_path": _rubric_manifest_path(self.config) if phase == "phase_2" else None,
                "scope_contract": scope_contract_summary(scope_contract, root=self.root),
                "reference_context": _reference_context_config_snapshot(self.config, self.root),
            },
            "workflow": self.config.workflow,
            "rubric_profile": self.config.convergence.rubric_profile,
            "rubric_source": self.config.convergence.rubric_source,
            "rubric_label": self.config.convergence.rubric_label,
            "rubric_manifest_path": _rubric_manifest_path(self.config) if phase == "phase_2" else None,
            "rubric_content_hash": rubric_hash,
            "scope_contract": scope_contract_summary(scope_contract, root=self.root),
            "scope_contract_hash": scope_contract.content_hash if scope_contract is not None else None,
            "reference_context": _reference_context_config_snapshot(self.config, self.root),
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
    for field_name, value in (
        ("timeouts.reviewer_seconds", config.timeouts.reviewer_seconds),
        ("timeouts.editor_seconds", config.timeouts.editor_seconds),
    ):
        if value is not None and value < 1:
            invalid.append({"path": field_name, "reason": "must be null or an integer >= 1"})
    if config.contract_surface.action not in {"recommend_synthesis", "report_only"}:
        invalid.append({"path": "contract_surface_policy.action", "reason": "must be recommend_synthesis or report_only"})
    if config.review_budget_exhaustion_policy not in {"hard", "soft"}:
        invalid.append({"path": "review.budget_exhaustion_policy", "reason": "must be hard or soft"})
    if config.review_mode not in {"horizontal", "vertical"}:
        invalid.append({"path": "review.mode", "reason": "must be horizontal or vertical"})
    scope_contract_path = config.scope_contract.path
    if scope_contract_path.exists():
        try:
            scope_contract = read_scope_contract(scope_contract_path)
        except Exception as exc:
            invalid.append({"path": "scope_contract.path", "reason": f"invalid scope contract: {exc}"})
            scope_contract = None
        if scope_contract is not None and config.workflow == "mvp":
            approval = scope_contract.packet.get("approval") or {}
            if not bool(approval.get("approved")) or scope_contract.packet.get("status") != "approved":
                invalid.append({"path": "scope_contract.path", "reason": "MVP workflow requires an approved scope contract"})
    elif config.workflow == "mvp":
        invalid.append({"path": "scope_contract.path", "reason": "MVP workflow requires an approved scope contract"})
    seen_reference_labels: set[str] = set()
    for item in config.reference_context_files:
        if not item.label:
            invalid.append({"path": "reference_context.files", "reason": "reference context label must be non-empty"})
        if item.label in seen_reference_labels:
            invalid.append({"path": f"reference_context.files.{item.label}", "reason": "duplicate label"})
        seen_reference_labels.add(item.label)
        if item.required and not item.path.exists():
            invalid.append({"path": f"reference_context.files.{item.label}.path", "reason": "required reference file missing"})
        if item.path.exists() and not item.path.is_file():
            invalid.append({"path": f"reference_context.files.{item.label}.path", "reason": "reference path must be a file"})
    for field_name, value in (
        ("contract_surface_policy.min_profile_rounds", config.contract_surface.min_profile_rounds),
        ("contract_surface_policy.recent_window", config.contract_surface.recent_window),
        ("contract_surface_policy.min_recent_serious_rounds", config.contract_surface.min_recent_serious_rounds),
        ("contract_surface_policy.min_contract_families", config.contract_surface.min_contract_families),
    ):
        if value < 1:
            invalid.append({"path": field_name, "reason": "must be an integer >= 1"})
    return invalid


def _last_client_telemetry(call: Any) -> dict[str, Any] | None:
    client = getattr(call, "__self__", None)
    telemetry = getattr(client, "last_telemetry", None)
    return telemetry if isinstance(telemetry, dict) else None


def _client_telemetry_packet(
    *,
    round_number: int,
    phase: str,
    profile: str,
    client_role: str,
    client_config: ClientConfig,
    artifact_name: str,
    attempt_number: int,
    telemetry: dict[str, Any] | None,
    raw_envelope_path: str | None,
    stdout_path: str | None,
    stderr_path: str | None,
) -> dict[str, Any]:
    usage = _usage_packet_from_telemetry(telemetry)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round_number": round_number,
        "phase": phase,
        "profile": profile,
        "client_role": client_role,
        "artifact_name": artifact_name,
        "attempt_number": attempt_number,
        "client": {
            "name": client_config.name,
            "command": client_config.command,
            "configured_version": client_config.version,
            "observed_version": None,
            "model": client_config.model,
        },
        "started_at": str((telemetry or {}).get("started_at") or datetime.now(timezone.utc).isoformat()),
        "finished_at": (telemetry or {}).get("finished_at"),
        "duration_ms": (telemetry or {}).get("duration_ms"),
        "duration_api_ms": (telemetry or {}).get("duration_api_ms"),
        "exit_code": (telemetry or {}).get("exit_code"),
        "timed_out": bool((telemetry or {}).get("timed_out", False)),
        "session_id": (telemetry or {}).get("session_id"),
        "num_turns": (telemetry or {}).get("num_turns"),
        "stop_reason": (telemetry or {}).get("stop_reason"),
        "terminal_reason": (telemetry or {}).get("terminal_reason"),
        "total_cost_usd": (telemetry or {}).get("total_cost_usd"),
        "usage": usage,
        "model_usage": (telemetry or {}).get("model_usage"),
        "raw_envelope_path": raw_envelope_path,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
        "telemetry_source": str((telemetry or {}).get("telemetry_source") or "unavailable"),
    }


def _usage_packet_from_telemetry(telemetry: dict[str, Any] | None) -> dict[str, Any]:
    usage = (telemetry or {}).get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "provider_raw": usage.get("provider_raw") if isinstance(usage.get("provider_raw"), dict) else None,
    }


def _write_telemetry_sidecar(path: Path, content: Any, root: Path) -> str | None:
    if content is None:
        return None
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path.relative_to(root))


def _write_telemetry_text_sidecar(path: Path, content: Any, root: Path) -> str | None:
    if not isinstance(content, str) or content == "":
        return None
    path.write_text(content, encoding="utf-8")
    return str(path.relative_to(root))


def write_round_telemetry_summary(round_dir: Path) -> Path | None:
    telemetry_dir = round_dir / "client_telemetry"
    if not telemetry_dir.exists():
        return None
    packets: list[dict[str, Any]] = []
    for path in sorted(telemetry_dir.glob("*.json")):
        if "-attempt-" not in path.name or path.name.endswith("-raw-envelope.json"):
            continue
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(packet, dict):
            packets.append(packet)
    warnings_path = telemetry_dir / "telemetry_warnings.json"
    warnings = _read_json_list_if_present(warnings_path)
    summary = _telemetry_summary_packet(round_dir=round_dir, packets=packets, warnings=warnings)
    output = round_dir / "telemetry_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def run_telemetry_totals(rounds_dir: Path) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    for path in sorted(rounds_dir.glob("round-*/telemetry_summary.json"), key=_round_summary_sort_key):
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(summary, dict):
            summaries.append(summary)
    total_duration_ms = _sum_nullable(summary.get("total_duration_ms") for summary in summaries)
    total_api_duration_ms = _sum_nullable(summary.get("total_api_duration_ms") for summary in summaries)
    total_tokens = _sum_nullable(summary.get("total_tokens") for summary in summaries)
    total_cost_usd = _sum_nullable_float(summary.get("total_cost_usd") for summary in summaries)
    return {
        "round_count": len(summaries),
        "attempt_count": sum(int(summary.get("attempt_count", 0)) for summary in summaries),
        "total_duration_ms": total_duration_ms,
        "total_api_duration_ms": total_api_duration_ms,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
        "missing_usage_attempts": sum(int(summary.get("missing_usage_attempts", 0)) for summary in summaries),
        "warning_count": sum(len(summary.get("warnings", [])) for summary in summaries if isinstance(summary.get("warnings"), list)),
    }


def _telemetry_summary_packet(
    *,
    round_dir: Path,
    packets: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    token_values = [_nested_int(packet, ("usage", "total_tokens")) for packet in packets]
    cost_values = [_number_or_none(packet.get("total_cost_usd")) for packet in packets]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round_number": _round_number_from_dir(round_dir),
        "attempt_count": len(packets),
        "total_duration_ms": _sum_nullable(packet.get("duration_ms") for packet in packets),
        "total_api_duration_ms": _sum_nullable(packet.get("duration_api_ms") for packet in packets),
        "total_tokens": _sum_nullable(token_values),
        "total_cost_usd": _sum_nullable_float(cost_values),
        "missing_usage_attempts": sum(1 for value in token_values if value is None),
        "by_client_role": {
            role: _role_telemetry_summary(role, packets)
            for role in ("reviewer", "editor")
            if any(packet.get("client_role") == role for packet in packets)
        },
        "warnings": warnings,
    }


def _role_telemetry_summary(role: str, packets: list[dict[str, Any]]) -> dict[str, Any]:
    role_packets = [packet for packet in packets if packet.get("client_role") == role]
    token_values = [_nested_int(packet, ("usage", "total_tokens")) for packet in role_packets]
    return {
        "attempt_count": len(role_packets),
        "total_duration_ms": _sum_nullable(packet.get("duration_ms") for packet in role_packets),
        "total_api_duration_ms": _sum_nullable(packet.get("duration_api_ms") for packet in role_packets),
        "total_tokens": _sum_nullable(token_values),
        "total_cost_usd": _sum_nullable_float(packet.get("total_cost_usd") for packet in role_packets),
        "missing_usage_attempts": sum(1 for value in token_values if value is None),
    }


def _record_telemetry_warning(telemetry_dir: Path, warning: dict[str, Any]) -> None:
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    path = telemetry_dir / "telemetry_warnings.json"
    warnings = _read_json_list_if_present(path)
    warnings.append({**warning, "generated_at": datetime.now(timezone.utc).isoformat()})
    path.write_text(json.dumps(warnings, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record_telemetry_warning_safely(*, round_dir: Path, telemetry_dir: Path, warning: dict[str, Any]) -> None:
    try:
        _record_telemetry_warning(telemetry_dir, warning)
        write_round_telemetry_summary(round_dir)
    except Exception:
        return


def _read_json_list_if_present(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _sum_nullable(values: Any) -> int | None:
    total = 0
    seen = False
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool):
            total += value
            seen = True
    return total if seen else None


def _sum_nullable_float(values: Any) -> float | None:
    total = 0.0
    seen = False
    for value in values:
        if isinstance(value, int | float) and not isinstance(value, bool):
            total += float(value)
            seen = True
    return total if seen else None


def _nested_int(packet: dict[str, Any], path: tuple[str, ...]) -> int | None:
    value: Any = packet
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number_or_none(value: Any) -> int | float | None:
    return value if isinstance(value, int | float) and not isinstance(value, bool) else None


def _round_number_from_dir(round_dir: Path) -> int:
    if round_dir.name.startswith("round-") and round_dir.name.removeprefix("round-").isdigit():
        return int(round_dir.name.removeprefix("round-"))
    return 0


def _round_summary_sort_key(path: Path) -> tuple[int, str]:
    return (_round_number_from_dir(path.parent), path.parent.name)


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
    failure_type: str = "artifact_validation",
) -> None:
    rounds_dir.mkdir(parents=True, exist_ok=True)
    terminal_state = "HALTED_CLIENT_TIMEOUT" if failure_type == "client_timeout" else "HALTED_ARTIFACT_INVALID"
    artifact = {
        "terminal_state": terminal_state,
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
        "failure_type": failure_type,
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
    failure_type: str = "artifact_validation",
) -> None:
    writer = ReportWriter(root)
    terminal_state = "HALTED_CLIENT_TIMEOUT" if failure_type == "client_timeout" else "HALTED_ARTIFACT_INVALID"
    exit_reason = "client invocation timed out before producing a valid artifact" if failure_type == "client_timeout" else "artifact validation retry exhausted"
    if phase == "phase_2":
        writer.write_convergence_failure_report(
            round_number=round_number,
            final_draft_path=final_draft_path,
            final_declaration_path=None,
            target_phase=config.convergence.target_phase,
            target_mode=config.convergence.target_mode,
            workflow=config.workflow,
            rubric_profile=config.convergence.rubric_profile,
            rubric_source=config.convergence.rubric_source,
            rubric_label=config.convergence.rubric_label,
            rubric_manifest_path=_rubric_manifest_path(config),
            unresolved_blockers=[],
            unresolved_major_issues=[],
            unresolved_rubric_gaps=[],
            reviewer_final_status="not_run",
            last_accepted_draft_hash=None,
            exit_reason=exit_reason,
            recommendation="manual_review_required",
            terminal_state=terminal_state,
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
        exit_reason=exit_reason,
        recommendation="manual_review_required",
        terminal_state=terminal_state,
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


def _is_timeout_error(exc: Exception) -> bool:
    return isinstance(exc, TimeoutError)


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
    _reject_reviewer_process_failure_feedback(artifact)
    validate_artifact(artifact, schema_name)


def _validate_editor_summary(
    artifact: dict[str, Any],
    *,
    round_number: int,
    draft_before_hash: str,
    draft_after_hash: str | None,
    require_draft_after_content: bool = False,
    draft_before_content: str | None = None,
) -> None:
    if require_draft_after_content and not isinstance(artifact.get("draft_after_content"), str):
        raise ValueError("editor_summary draft_after_content is required for applied editor-generated revisions")
    if isinstance(artifact.get("draft_after_content"), str):
        validate_generated_text(artifact["draft_after_content"], context="editor_summary draft_after_content")
        _reject_destructive_draft_after(
            draft_before_content=draft_before_content,
            draft_after_content=artifact["draft_after_content"],
        )
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


def _reject_destructive_draft_after(*, draft_before_content: str | None, draft_after_content: str) -> None:
    if draft_before_content is None:
        return
    before_stripped = draft_before_content.strip()
    after_stripped = draft_after_content.strip()
    if not before_stripped:
        return
    if not after_stripped:
        raise ValueError("editor_summary draft_after_content would replace a non-empty draft with empty content")
    if after_stripped.startswith("[Whetstone editor blocked]"):
        raise ValueError("editor_summary draft_after_content is an editor blocked/error placeholder, not a revised draft")
    before_len = len(before_stripped)
    after_len = len(after_stripped)
    if before_len >= 1000 and after_len < 100 and after_len < int(before_len * 0.05):
        raise ValueError(
            "editor_summary draft_after_content is destructively smaller than the non-empty draft; "
            "refusing near-empty replacement"
        )


def _no_op_editor_summary(
    *, round_number: int, draft_hash_value: str, draft_after_content: str | None = None
) -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "round_number": round_number,
        "draft_before_hash": draft_hash_value,
        "draft_after_hash": draft_hash_value,
        "accepted_feedback_ids": [],
        "modified_feedback_ids": [],
        "declined_feedback": [],
        "created_conflict_ids": [],
        "resolved_issue_ids": [],
        "unresolved_issue_ids": [],
    }
    if draft_after_content is not None:
        artifact["draft_after_content"] = draft_after_content
    return artifact


def _read_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _read_prompt_snapshot_field(round_dir: Path, field: str) -> str | None:
    path = round_dir / "prompt_snapshot.json"
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get(field)
    return value if isinstance(value, str) else None


def _remove_top_level_timeout_artifacts(rounds_dir: Path) -> None:
    for filename in ("artifact_validation_error.json", "technical_failure_report.json", "convergence_failure_report.json"):
        path = rounds_dir / filename
        if not path.exists():
            continue
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if packet.get("terminal_state") == "HALTED_CLIENT_TIMEOUT":
            path.unlink()


def _rubric_manifest_path(config: OrchestratorConfig) -> str:
    try:
        return str((config.rounds_dir / "rubric_manifest.json").relative_to(config.rounds_dir.parent))
    except ValueError:
        return str(config.rounds_dir / "rubric_manifest.json")


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _context_file_packets(context_files: list[ContextFile]) -> list[dict[str, str]]:
    return [
        {
            "label": item.label,
            "path": item.path,
            "sha256": item.sha256,
        }
        for item in context_files
    ]


def _reference_context_prompt_paths(context_files: list[ContextFile], config: OrchestratorConfig) -> list[dict[str, str]]:
    role_by_label = {item.label: item.role for item in config.reference_context_files}
    output: list[dict[str, str]] = []
    for item in context_files:
        if not item.label.startswith("reference:"):
            continue
        label = item.label.split(":", 1)[1]
        output.append(
            {
                "label": label,
                "role": role_by_label.get(label, "reference_context"),
                "path": item.path,
            }
        )
    return output


def _reference_context_config_snapshot(config: OrchestratorConfig, root: Path) -> dict[str, Any]:
    return {
        "files": [
            {
                "label": item.label,
                "path": _relative_path(item.path, root),
                "role": item.role,
                "required": item.required,
                "exists": item.path.exists(),
                "sha256": _file_sha256(item.path) if item.path.exists() and item.path.is_file() else None,
            }
            for item in config.reference_context_files
        ]
    }


def _safe_context_filename(label: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in label.strip())
    return safe or "reference"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _append_version_stamp_history(history_path: Path, *, round_number: int, phase: str, result: Any) -> None:
    if not result.stamped:
        return
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as history_file:
        history_file.write(
            f"- Version stamp: round {round_number}, phase `{phase}`, "
            f"`{result.before_version}` -> `{result.after_version}`, "
            f"before `{result.before_hash}`, after `{result.after_hash}`.\n"
        )


def _try_stamp_spec_text_for_round(content: str, *, phase: str) -> Any | None:
    try:
        return stamp_spec_text_for_round(content, phase=phase)
    except ValueError as exc:
        message = str(exc)
        if "root heading" in message or "numeric version" in message:
            return None
        raise


def _maybe_promote_phase2_version(config: OrchestratorConfig) -> None:
    state_path = config.rounds_dir / "run_state.json"
    if not state_path.exists():
        return
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state = {}
    if state.get("phase") == "phase_2":
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


def _reject_reviewer_process_failure_feedback(reviewer_feedback: dict[str, Any]) -> None:
    feedback = reviewer_feedback.get("feedback")
    if not isinstance(feedback, list) or not feedback:
        return
    if all(isinstance(item, dict) and _is_reviewer_process_failure_item(item) for item in feedback):
        raise ValueError(
            "reviewer_feedback reports a process/context-loading failure instead of semantic review; "
            "retry reviewer invocation"
        )


def _is_reviewer_process_failure_item(item: dict[str, Any]) -> bool:
    issue_type = str(item.get("issue_type", "")).strip().lower()
    affected_sections = [str(section).strip().lower() for section in item.get("affected_sections", []) if section is not None]
    if issue_type in {"process_error", "context_loading", "context_unread"}:
        return True
    if any(section in {"context_loading", "context_unread", "process_error"} for section in affected_sections):
        return True
    haystack = " ".join(
        str(item.get(key, ""))
        for key in ("claim", "evidence", "recommended_change", "invariant_violated", "severity_rationale")
    ).lower()
    process_markers = (
        "review cannot be performed",
        "review could not be performed",
        "required context files were not read",
        "context files were not read",
        "no file-reading tool call",
        "did not read",
        "unable to read context",
        "could not read context",
    )
    return any(marker in haystack for marker in process_markers)
