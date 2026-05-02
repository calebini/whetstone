"""Command-line entry points for Whetstone."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from whetstone.clients import ClaudeCodeEditorClient, ClaudeCodeReviewerClient, CodexEditorClient, CodexReviewerClient
from whetstone.config import load_config
from whetstone.decisions import scan_decision_points, write_decision_scan_outputs
from whetstone.engine import FixtureEngine, fixture_steps_from_json
from whetstone.hashing import draft_hash
from whetstone.live import LiveRoundRunner
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.prompts import render_editor_prompt, render_reviewer_prompt
from whetstone.runner import FixtureRunner
from whetstone.sections import section_index
from whetstone.versioning import promote_spec_file_for_phase2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="whetstone")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixture = subparsers.add_parser("fixture-round", help="run one deterministic fixture round")
    fixture.add_argument("--root", default=".", help="repository root")
    fixture.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")
    fixture.add_argument("--round", type=int, default=1, help="round number")
    fixture.add_argument("--reviewer-feedback", required=True, help="path to reviewer_feedback fixture")
    fixture.add_argument("--editor-summary", required=True, help="path to editor_summary fixture")
    fixture.add_argument("--draft-after", help="optional path to draft_after fixture")
    fixture.add_argument("--overwrite", action="store_true", help="replace existing round directory")

    script = subparsers.add_parser("fixture-script", help="run a deterministic multi-round fixture script")
    script.add_argument("--root", default=".", help="repository root")
    script.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")
    script.add_argument("--script", required=True, help="path to JSON fixture script")
    script.add_argument("--overwrite", action="store_true", help="replace existing round directories")

    codex_review = subparsers.add_parser("codex-review", help="run Codex as a schema-valid reviewer")
    codex_review.add_argument("--root", default=".", help="repository root")
    codex_review.add_argument("--profile", required=True, help="review profile")
    codex_review.add_argument("--draft", default="spec.md", help="draft path relative to root")
    codex_review.add_argument("--rubric", help="optional rubric path relative to root")
    codex_review.add_argument("--phase", choices=["phase_1", "phase_2"], default="phase_1", help="review phase")
    codex_review.add_argument("--output", required=True, help="reviewer_feedback.json output path")
    codex_review.add_argument("--command", dest="codex_command", default="codex", help="codex executable")
    codex_review.add_argument("--model", help="optional Codex model")
    codex_review.add_argument("--timeout-seconds", type=int, help="optional Codex subprocess timeout")

    reviewer_smoke = subparsers.add_parser("reviewer-smoke", help="run a schema-valid reviewer smoke test")
    reviewer_smoke.add_argument("--root", default=".", help="repository root")
    reviewer_smoke.add_argument("--profile", required=True, help="review profile")
    reviewer_smoke.add_argument("--draft", default="spec.md", help="draft path relative to root")
    reviewer_smoke.add_argument("--rubric", help="optional rubric path relative to root")
    reviewer_smoke.add_argument("--phase", choices=["phase_1", "phase_2"], default="phase_1", help="review phase")
    reviewer_smoke.add_argument("--output", required=True, help="reviewer_feedback.json output path")
    reviewer_smoke.add_argument("--client", choices=["codex", "claude-code"], default="codex", help="reviewer client")
    reviewer_smoke.add_argument("--command", dest="reviewer_command", help="reviewer executable")
    reviewer_smoke.add_argument("--model", help="optional reviewer model")
    reviewer_smoke.add_argument("--timeout-seconds", type=int, help="optional reviewer subprocess timeout")

    editor_smoke = subparsers.add_parser("editor-smoke", help="run a schema-valid non-mutating editor")
    editor_smoke.add_argument("--root", default=".", help="repository root")
    editor_smoke.add_argument("--draft", default="spec.md", help="draft path relative to root")
    editor_smoke.add_argument("--reviewer-feedback", required=True, help="path to reviewer_feedback.json")
    editor_smoke.add_argument("--output", required=True, help="editor_summary.json output path")
    editor_smoke.add_argument("--client", choices=["codex", "claude-code"], default="codex", help="editor client")
    editor_smoke.add_argument("--command", dest="editor_command", help="editor executable")
    editor_smoke.add_argument("--model", help="optional editor model")
    editor_smoke.add_argument("--timeout-seconds", type=int, help="optional editor subprocess timeout")

    live_round = subparsers.add_parser("live-round", help="run one guarded live reviewer/editor round")
    live_round.add_argument("--root", default=".", help="repository root")
    live_round.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")
    live_round.add_argument("--round", type=int, default=1, help="round number")
    live_round.add_argument("--profile", required=True, help="review profile")
    live_round.add_argument("--phase", choices=["phase_1", "phase_2"], default="phase_1", help="review phase")
    live_round.add_argument("--draft-after", help="optional draft_after path relative to root")
    live_round.add_argument("--apply", action="store_true", help="apply validated draft_after to spec.md")
    live_round.add_argument("--overwrite", action="store_true", help="replace existing round directory")
    live_round.add_argument("--timeout-seconds", type=int, help="optional live client subprocess timeout")

    live_phase1 = subparsers.add_parser("live-phase1", help="run the minimal live Phase 1 multi-round loop")
    live_phase1.add_argument("--root", default=".", help="repository root")
    live_phase1.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")
    live_phase1.add_argument("--overwrite", action="store_true", help="replace existing round directories")
    live_phase1.add_argument("--timeout-seconds", type=int, help="optional live client subprocess timeout")

    decision_scan = subparsers.add_parser("decision-scan", help="scan a before/after draft pair for decision points")
    decision_scan.add_argument("--before", required=True, help="starting draft path")
    decision_scan.add_argument("--after", required=True, help="final draft path")
    decision_scan.add_argument("--output-dir", required=True, help="directory for decision artifacts")
    decision_scan.add_argument("--mode", choices=["end_of_cycle", "intervention"], default="end_of_cycle")
    decision_scan.add_argument("--profile", default="decision_scan", help="profile label for emitted decision points")

    promote_phase2 = subparsers.add_parser("promote-phase2", help="promote an accepted Phase 1 spec version for Phase 2")
    promote_phase2.add_argument("--root", default=".", help="repository root")
    promote_phase2.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")

    args = parser.parse_args(argv)
    if args.command == "fixture-round":
        root = Path(args.root)
        config = load_config(root / args.config)
        reviewer_feedback = _read_json(Path(args.reviewer_feedback))
        editor_summary = _read_json(Path(args.editor_summary))
        draft_after = Path(args.draft_after).read_text(encoding="utf-8") if args.draft_after else None
        result = FixtureRunner(root, config).run_round(
            round_number=args.round,
            reviewer_feedback=reviewer_feedback,
            editor_summary=editor_summary,
            draft_after=draft_after,
            overwrite=args.overwrite,
        )
        print(json.dumps({"round_number": result.round_number, "accepted": result.accepted, "round_dir": str(result.round_dir)}))
        return 0
    if args.command == "fixture-script":
        root = Path(args.root)
        config = load_config(root / args.config)
        steps = fixture_steps_from_json(_read_json_list(Path(args.script)))
        result = FixtureEngine(root, config).run(steps, overwrite_rounds=args.overwrite)
        print(
            json.dumps(
                {
                    "terminal_state": result.terminal_state,
                    "round_number": result.round_number,
                    "phase": result.phase,
                    "report_path": str(result.report_path) if result.report_path else None,
                }
            )
        )
        return 0
    if args.command == "codex-review":
        root = Path(args.root)
        draft = (root / args.draft).read_text(encoding="utf-8")
        rubric = (root / args.rubric).read_text(encoding="utf-8") if args.rubric else None
        section_ids = [section.id for section in section_index(draft)] if args.phase == "phase_2" else []
        prompt = render_reviewer_prompt(
            profile=args.profile,
            draft=draft,
            rubric=rubric,
            phase=args.phase,
            section_ids=section_ids,
            draft_hash_value=draft_hash(draft),
        )
        artifact = CodexReviewerClient(
            command=args.codex_command,
            model=args.model,
            cwd=root,
            phase=args.phase,
            section_ids=section_ids,
            timeout_seconds=args.timeout_seconds,
        ).review(prompt)
        output = Path(args.output)
        output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "feedback_count": len(artifact.get("feedback", []))}))
        return 0
    if args.command == "reviewer-smoke":
        root = Path(args.root)
        draft = (root / args.draft).read_text(encoding="utf-8")
        rubric = (root / args.rubric).read_text(encoding="utf-8") if args.rubric else None
        section_ids = [section.id for section in section_index(draft)] if args.phase == "phase_2" else []
        prompt = render_reviewer_prompt(
            profile=args.profile,
            draft=draft,
            rubric=rubric,
            phase=args.phase,
            section_ids=section_ids,
            draft_hash_value=draft_hash(draft),
        )
        if args.client == "claude-code":
            client = ClaudeCodeReviewerClient(
                command=args.reviewer_command or "claude",
                model=args.model,
                cwd=root,
                phase=args.phase,
                section_ids=section_ids,
                timeout_seconds=args.timeout_seconds,
            )
        else:
            client = CodexReviewerClient(
                command=args.reviewer_command or "codex",
                model=args.model,
                cwd=root,
                phase=args.phase,
                section_ids=section_ids,
                timeout_seconds=args.timeout_seconds,
            )
        artifact = client.review(prompt)
        output = Path(args.output)
        output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "feedback_count": len(artifact.get("feedback", []))}))
        return 0
    if args.command == "editor-smoke":
        root = Path(args.root)
        draft = (root / args.draft).read_text(encoding="utf-8")
        reviewer_feedback = Path(args.reviewer_feedback).read_text(encoding="utf-8")
        prompt = render_editor_prompt(draft=draft, reviewer_feedback_json=reviewer_feedback)
        if args.client == "claude-code":
            client = ClaudeCodeEditorClient(
                command=args.editor_command or "claude",
                model=args.model,
                cwd=root,
                timeout_seconds=args.timeout_seconds,
            )
        else:
            client = CodexEditorClient(
                command=args.editor_command or "codex",
                model=args.model,
                cwd=root,
                timeout_seconds=args.timeout_seconds,
            )
        artifact = client.revise(prompt)
        output = Path(args.output)
        output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "declined_feedback_count": len(artifact.get("declined_feedback", []))}))
        return 0
    if args.command == "live-round":
        root = Path(args.root)
        config = load_config(root / args.config)
        draft_after = (root / args.draft_after).read_text(encoding="utf-8") if args.draft_after else None
        result = LiveRoundRunner(root, config, timeout_seconds=args.timeout_seconds).run_round(
            round_number=args.round,
            profile=args.profile,
            phase=args.phase,
            draft_after=draft_after,
            apply=args.apply,
            overwrite=args.overwrite,
        )
        print(
            json.dumps(
                {
                    "round_number": result.round_number,
                    "round_dir": str(result.round_dir),
                    "accepted": result.accepted,
                    "feedback_count": result.reviewer_feedback_count,
                    "spec_mutated": result.spec_mutated,
                }
            )
        )
        return 0
    if args.command == "live-phase1":
        root = Path(args.root)
        config = load_config(root / args.config)
        result = LivePhase1Runner(root, config, timeout_seconds=args.timeout_seconds).run(overwrite=args.overwrite)
        print(
            json.dumps(
                {
                    "terminal_state": result.terminal_state,
                    "round_number": result.round_number,
                    "current_draft_hash": result.current_draft_hash,
                    "last_accepted_draft_hash": result.last_accepted_draft_hash,
                    "ready_for_phase_2": result.ready_for_phase_2,
                    "report_path": str(result.report_path) if result.report_path else None,
                }
            )
        )
        return 0
    if args.command == "decision-scan":
        before = Path(args.before).read_text(encoding="utf-8")
        after = Path(args.after).read_text(encoding="utf-8")
        packet = scan_decision_points(
            draft_before=before,
            draft_after=after,
            mode=args.mode,
            profile=args.profile,
        )
        outputs = write_decision_scan_outputs(
            output_dir=Path(args.output_dir),
            packet=packet,
            mode=args.mode,
        )
        print(
            json.dumps(
                {
                    "decision_count": len(packet["decision_points"]),
                    "decision_points": str(outputs["decision_points"]),
                    "decision_register": str(outputs["decision_register"]),
                    "decision_register_markdown": str(outputs["decision_register_markdown"]),
                }
            )
        )
        return 0
    if args.command == "promote-phase2":
        root = Path(args.root)
        config = load_config(root / args.config)
        result = promote_spec_file_for_phase2(
            spec_path=config.spec_path,
            history_path=config.history_path,
            rounds_dir=config.rounds_dir,
        )
        print(
            json.dumps(
                {
                    "promoted": result.promoted,
                    "before_version": result.before_version,
                    "after_version": result.after_version,
                    "before_hash": result.before_hash,
                    "after_hash": result.after_hash,
                }
            )
        )
        return 0
    return 1


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as artifact_file:
        return json.load(artifact_file)


def _read_json_list(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as artifact_file:
        data = json.load(artifact_file)
    if not isinstance(data, list):
        raise ValueError("fixture script must be a JSON array")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
