"""Apply isolated Whetstone run results back to a source spec."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
from typing import Any

from whetstone.contracts import validate_artifact
from whetstone.hashing import draft_hash
from whetstone.text_validation import validate_generated_text


@dataclass(frozen=True)
class ApplyBackResult:
    source_path: Path
    run_root: Path
    final_draft_path: Path
    review_json_path: Path
    review_markdown_path: Path
    applied: bool
    source_before_hash: str
    final_draft_hash: str
    source_after_hash: str
    changed: bool


def apply_back(
    *,
    source_path: Path | str,
    run_root: Path | str,
    apply: bool = False,
    approve: bool = False,
    expected_source_hash: str | None = None,
    allow_source_hash_mismatch: bool = False,
    allow_non_converged: bool = False,
    output_dir: Path | str | None = None,
) -> ApplyBackResult:
    """Create an apply-back review, optionally writing the final draft to the source spec."""

    source = Path(source_path)
    root = Path(run_root)
    final_draft_path = _final_draft_path(root)
    if not source.exists():
        raise FileNotFoundError(source)
    if apply and not approve:
        raise ValueError("apply-back write requires approve=True")
    run_state_path = root / "rounds" / "run_state.json"
    run_state = _read_json_object(run_state_path)
    terminal_state = _terminal_state(run_state)
    eligible_terminal_state = terminal_state == "CONVERGED"
    if apply and not eligible_terminal_state and not allow_non_converged:
        raise ValueError(
            "apply-back write requires a CONVERGED run; pass allow_non_converged=True only for manual recovery"
        )

    source_text = source.read_text(encoding="utf-8")
    final_text = final_draft_path.read_text(encoding="utf-8")
    validate_generated_text(final_text, context="apply-back final draft")
    source_before_hash = draft_hash(source_text)
    final_draft_hash = draft_hash(final_text)
    run_state_current_draft_hash = _run_state_current_draft_hash(run_state)
    final_draft_matches_run_state = (
        None if run_state_current_draft_hash is None else final_draft_hash == run_state_current_draft_hash
    )
    if apply and final_draft_matches_run_state is False:
        raise ValueError(
            f"final draft hash mismatch: run_state current_draft_hash={run_state_current_draft_hash}, "
            f"final_draft_hash={final_draft_hash}"
        )
    if (
        expected_source_hash is not None
        and expected_source_hash != source_before_hash
        and not allow_source_hash_mismatch
    ):
        raise ValueError(
            f"source hash mismatch: expected {expected_source_hash}, observed {source_before_hash}"
        )

    changed = source_before_hash != final_draft_hash
    diff_lines = _unified_diff(
        source_text=source_text,
        final_text=final_text,
        source_label=str(source),
        final_label=str(final_draft_path),
    )
    applied = False
    if apply and changed:
        source.write_text(final_text, encoding="utf-8")
        applied = True

    source_after_hash = draft_hash(source.read_text(encoding="utf-8"))
    artifact_dir = Path(output_dir) if output_dir is not None else root / "rounds"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    review_json_path = artifact_dir / "apply_back_review.json"
    review_markdown_path = artifact_dir / "apply_back_review.md"
    rubric_identity = _read_rubric_identity(root)
    declaration_path = root / "convergence_declaration.md"
    decision_summary_path = root / "rounds" / "decision_summary.json"

    report = {
        "generated_at": _now(),
        "mode": "apply" if apply else "dry_run",
        "applied": applied,
        "approval_mode": "explicit" if approve else "none",
        "source_path": str(source),
        "run_root": str(root),
        "final_draft_path": str(final_draft_path),
        "run_state_path": str(run_state_path) if run_state_path.exists() else None,
        "terminal_state": terminal_state,
        "eligible_terminal_state": eligible_terminal_state,
        "allow_non_converged": allow_non_converged,
        "source_before_hash": source_before_hash,
        "expected_source_hash": expected_source_hash,
        "source_hash_mismatch_allowed": allow_source_hash_mismatch,
        "final_draft_hash": final_draft_hash,
        "run_state_current_draft_hash": run_state_current_draft_hash,
        "final_draft_matches_run_state": final_draft_matches_run_state,
        "source_after_hash": source_after_hash,
        "changed": changed,
        "declaration_path": str(declaration_path) if declaration_path.exists() else None,
        "declaration_included": declaration_path.exists(),
        "decision_summary_path": str(decision_summary_path) if decision_summary_path.exists() else None,
        "decision_summary_included": decision_summary_path.exists(),
        **rubric_identity,
        "diff_line_count": len(diff_lines),
    }
    validate_artifact(report, "apply_back_report")
    review_json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review_markdown_path.write_text(_markdown_report(report, diff_lines), encoding="utf-8")

    return ApplyBackResult(
        source_path=source,
        run_root=root,
        final_draft_path=final_draft_path,
        review_json_path=review_json_path,
        review_markdown_path=review_markdown_path,
        applied=applied,
        source_before_hash=source_before_hash,
        final_draft_hash=final_draft_hash,
        source_after_hash=source_after_hash,
        changed=changed,
    )


def _final_draft_path(run_root: Path) -> Path:
    spec_path = run_root / "spec.md"
    if spec_path.exists():
        return spec_path

    run_state_path = run_root / "rounds" / "run_state.json"
    if run_state_path.exists():
        run_state = json.loads(run_state_path.read_text(encoding="utf-8"))
        round_number = run_state.get("current_round", run_state.get("round_number"))
        if isinstance(round_number, int):
            candidate = run_root / "rounds" / f"round-{round_number}" / "draft_after.md"
            if candidate.exists():
                return candidate

    candidates = (
        sorted((run_root / "rounds").glob("round-*/draft_after.md"), key=_round_draft_sort_key)
        if (run_root / "rounds").exists()
        else []
    )
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(f"could not locate final draft in {run_root}")


def _round_draft_sort_key(path: Path) -> tuple[int, str]:
    round_name = path.parent.name
    if round_name.startswith("round-"):
        suffix = round_name.removeprefix("round-")
        if suffix.isdigit():
            return (int(suffix), round_name)
    return (-1, round_name)


def _unified_diff(*, source_text: str, final_text: str, source_label: str, final_label: str) -> list[str]:
    return list(
        difflib.unified_diff(
            source_text.splitlines(keepends=True),
            final_text.splitlines(keepends=True),
            fromfile=source_label,
            tofile=final_label,
            lineterm="",
        )
    )


def _markdown_report(report: dict[str, Any], diff_lines: list[str]) -> str:
    lines = [
        "# Apply-Back Review",
        "",
        f"- mode: {report['mode']}",
        f"- applied: {str(report['applied']).lower()}",
        f"- changed: {str(report['changed']).lower()}",
        f"- source_path: {report['source_path']}",
        f"- final_draft_path: {report['final_draft_path']}",
        f"- terminal_state: {report['terminal_state']}",
        f"- eligible_terminal_state: {str(report['eligible_terminal_state']).lower()}",
        f"- allow_non_converged: {str(report['allow_non_converged']).lower()}",
        f"- source_before_hash: {report['source_before_hash']}",
        f"- expected_source_hash: {report['expected_source_hash']}",
        f"- source_hash_mismatch_allowed: {str(report['source_hash_mismatch_allowed']).lower()}",
        f"- final_draft_hash: {report['final_draft_hash']}",
        f"- run_state_current_draft_hash: {report['run_state_current_draft_hash']}",
        f"- final_draft_matches_run_state: {report['final_draft_matches_run_state']}",
        f"- source_after_hash: {report['source_after_hash']}",
        f"- declaration_path: {report['declaration_path']}",
        f"- declaration_included: {str(report['declaration_included']).lower()}",
        f"- decision_summary_path: {report['decision_summary_path']}",
        f"- decision_summary_included: {str(report['decision_summary_included']).lower()}",
        f"- rubric_manifest_path: {report['rubric_manifest_path']}",
        f"- workflow: {report['workflow']}",
        f"- rubric_profile: {report['rubric_profile']}",
        f"- rubric_source: {report['rubric_source']}",
        f"- rubric_label: {report['rubric_label']}",
        f"- rubric_content_hash: {report['rubric_content_hash']}",
        "",
        "## Diff",
        "",
        "```diff",
    ]
    lines.extend(line.rstrip("\n") for line in diff_lines)
    lines.extend(["```", ""])
    return "\n".join(lines)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_rubric_identity(run_root: Path) -> dict[str, Any]:
    manifest_path = run_root / "rounds" / "rubric_manifest.json"
    if not manifest_path.exists():
        return {
            "rubric_manifest_path": None,
            "workflow": None,
            "rubric_profile": None,
            "rubric_source": None,
            "rubric_label": None,
            "rubric_content_hash": None,
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "rubric_manifest_path": str(manifest_path),
        "workflow": manifest.get("workflow"),
        "rubric_profile": manifest.get("rubric_profile"),
        "rubric_source": manifest.get("rubric_source"),
        "rubric_label": manifest.get("rubric_label"),
        "rubric_content_hash": manifest.get("rubric_content_hash"),
    }


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return packet if isinstance(packet, dict) else None


def _terminal_state(run_state: dict[str, Any] | None) -> str | None:
    value = (run_state or {}).get("terminal_state")
    return value if isinstance(value, str) else None


def _run_state_current_draft_hash(run_state: dict[str, Any] | None) -> str | None:
    value = (run_state or {}).get("current_draft_hash")
    return value if isinstance(value, str) else None
