"""Command-line entry points for Whetstone."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from whetstone.apply_back import apply_back
from whetstone.clients import ClaudeCodeEditorClient, ClaudeCodeReviewerClient, CodexEditorClient, CodexReviewerClient
from whetstone.config import load_config
from whetstone.decisions import scan_decision_points, write_decision_scan_outputs, write_decision_summary_outputs
from whetstone.engine import FixtureEngine, fixture_steps_from_json
from whetstone.hashing import draft_hash
from whetstone.live import LiveRoundRunner
from whetstone.live_phase1 import LivePhase1Runner
from whetstone.live_phase2 import LivePhase2Runner
from whetstone.prompts import render_editor_prompt, render_reviewer_prompt
from whetstone.resume import plan_resume_halted_run, resume_halted_run
from whetstone.runner import FixtureRunner
from whetstone.run_state import apply_effective_run_config
from whetstone.rubrics import BUILTIN_RUBRIC_FILES, build_rubric_manifest
from whetstone.sections import section_index
from whetstone.status import read_status, render_status_text
from whetstone.versioning import promote_spec_file_for_phase2


FORMATTER = argparse.RawDescriptionHelpFormatter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="whetstone",
        description="Run AI-assisted spec review, convergence, recovery, and apply-back workflows.",
        formatter_class=FORMATTER,
    )
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
    live_round.add_argument("--reviewer-timeout-seconds", type=int, help="optional reviewer subprocess timeout")
    live_round.add_argument("--editor-timeout-seconds", type=int, help="optional editor subprocess timeout")
    live_round.add_argument("--workflow", choices=["exploratory", "mvp", "standard", "governance", "custom"], help="workflow preset")
    live_round.add_argument("--rubric", help="built-in rubric profile or custom rubric path")
    live_round.add_argument("--rubric-label", help="required label when --rubric points to a custom path")

    live_phase1 = subparsers.add_parser(
        "live-phase1",
        help="run Phase 1 technical stabilization",
        description="Run Phase 1 technical stabilization in an isolated run root.",
        epilog=(
            "Example:\n"
            "  whetstone live-phase1 --root \"$RUN_ROOT\"\n\n"
            "Budget policy is configured in orchestrator_config.yaml:\n"
            "  review.budget_exhaustion_policy: hard  # strict stop\n"
            "  review.budget_exhaustion_policy: soft  # full diagnostic sweep, no Phase 2 unless stable\n\n"
            "Use status after completion:\n"
            "  whetstone status --root \"$RUN_ROOT\" --format text"
        ),
        formatter_class=FORMATTER,
    )
    live_phase1.add_argument("--root", default=".", help="isolated Whetstone run root")
    live_phase1.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")
    live_phase1.add_argument("--overwrite", action="store_true", help="danger: replace existing round directories")
    live_phase1.add_argument("--timeout-seconds", type=int, help="fallback timeout for both live clients")
    live_phase1.add_argument("--reviewer-timeout-seconds", type=int, help="override reviewer subprocess timeout")
    live_phase1.add_argument("--editor-timeout-seconds", type=int, help="override editor subprocess timeout")

    live_phase2 = subparsers.add_parser(
        "live-phase2",
        help="run Phase 2 convergence review",
        description="Run Phase 2 convergence review after Phase 1 reaches PHASE_1_STABLE.",
        epilog=(
            "Examples:\n"
            "  whetstone live-phase2 --root \"$RUN_ROOT\" --workflow standard\n"
            "  whetstone live-phase2 --root \"$RUN_ROOT\" --workflow mvp --rubric mvp-v1\n"
            "  whetstone live-phase2 --root \"$RUN_ROOT\" --workflow custom --rubric /path/domain.md --rubric-label domain-v1"
        ),
        formatter_class=FORMATTER,
    )
    live_phase2.add_argument("--root", default=".", help="isolated Whetstone run root")
    live_phase2.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")
    live_phase2.add_argument("--overwrite", action="store_true", help="danger: replace existing round directories")
    live_phase2.add_argument("--timeout-seconds", type=int, help="fallback timeout for both live clients")
    live_phase2.add_argument("--reviewer-timeout-seconds", type=int, help="override reviewer subprocess timeout")
    live_phase2.add_argument("--editor-timeout-seconds", type=int, help="override editor subprocess timeout")
    live_phase2.add_argument("--workflow", choices=["exploratory", "mvp", "standard", "governance", "custom"], help="rubric workflow preset")
    live_phase2.add_argument("--rubric", help="built-in rubric profile or custom rubric path")
    live_phase2.add_argument("--rubric-label", help="required label when --rubric points to a custom path")

    resume = subparsers.add_parser(
        "resume",
        help="resume a supported halted live run",
        description="Resume a supported Phase 1 Editor timeout after validated Reviewer feedback.",
        epilog=(
            "Examples:\n"
            "  whetstone resume --root \"$RUN_ROOT\" --dry-run --continue\n"
            "  whetstone resume --root \"$RUN_ROOT\" --editor-timeout-seconds 1800 --continue\n\n"
            "Current support is intentionally narrow: Phase 1 Editor timeouts only."
        ),
        formatter_class=FORMATTER,
    )
    resume.add_argument("--root", default=".", help="isolated Whetstone run root")
    resume.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")
    resume.add_argument("--timeout-seconds", type=int, help="fallback timeout for the resumed client call")
    resume.add_argument("--reviewer-timeout-seconds", type=int, help="override reviewer timeout for continued rounds")
    resume.add_argument("--editor-timeout-seconds", type=int, help="override editor timeout for resume and continued rounds")
    resume.add_argument("--continue", dest="continue_run", action="store_true", help="continue Phase 1 after recovering the failed round")
    resume.add_argument("--dry-run", action="store_true", help="validate resume eligibility without invoking the editor")

    status = subparsers.add_parser(
        "status",
        help="summarize run state and next action",
        description=(
            "Read run_state.json and artifacts to show terminal state, next action, resume commands, "
            "telemetry, residual profile status, and apply-back status."
        ),
        epilog=(
            "Example:\n"
            "  whetstone status --root \"$RUN_ROOT\" --format text\n\n"
            "PHASE_1_STABLE can proceed to Phase 2. "
            "PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS is a soft-budget diagnostic stop and requires manual review."
        ),
        formatter_class=FORMATTER,
    )
    status.add_argument("--root", default=".", help="Whetstone run root")
    status.add_argument("--run-root", help="isolated Whetstone run root; overrides --root")
    status.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")
    status.add_argument("--format", choices=["json", "text"], default="json", help="status output format; text is best for operators")

    decision_scan = subparsers.add_parser("decision-scan", help="scan a before/after draft pair for decision points")
    decision_scan.add_argument("--before", required=True, help="starting draft path")
    decision_scan.add_argument("--after", required=True, help="final draft path")
    decision_scan.add_argument("--output-dir", required=True, help="directory for decision artifacts")
    decision_scan.add_argument("--mode", choices=["end_of_cycle", "intervention"], default="end_of_cycle")
    decision_scan.add_argument("--profile", default="decision_scan", help="profile label for emitted decision points")

    decision_summary = subparsers.add_parser("decision-summary", help="summarize an existing decision_register.json")
    decision_summary.add_argument("--register", required=True, help="decision_register.json path")
    decision_summary.add_argument(
        "--output-dir",
        help="directory for summary artifacts; defaults to the register directory",
    )

    promote_phase2 = subparsers.add_parser("promote-phase2", help="promote an accepted Phase 1 spec version for Phase 2")
    promote_phase2.add_argument("--root", default=".", help="repository root")
    promote_phase2.add_argument("--config", default="orchestrator_config.yaml", help="config path relative to root")

    apply_back_parser = subparsers.add_parser(
        "apply-back",
        help="review or apply an isolated run to a source spec",
        description="Compare a completed isolated Whetstone run with its source spec, or apply the final draft after explicit approval.",
        epilog=(
            "Examples:\n"
            "  whetstone apply-back --source \"$SOURCE_SPEC\" --run-root \"$RUN_ROOT\"\n"
            "  whetstone apply-back --source \"$SOURCE_SPEC\" --run-root \"$RUN_ROOT\" --apply --approve\n\n"
            "Run without --apply first. The apply path requires --approve on purpose."
        ),
        formatter_class=FORMATTER,
    )
    apply_back_parser.add_argument("--source", required=True, help="source spec path to compare or update")
    apply_back_parser.add_argument("--run-root", required=True, help="completed isolated Whetstone run root")
    apply_back_parser.add_argument("--output-dir", help="directory for apply-back review artifacts; defaults to RUN_ROOT/rounds")
    apply_back_parser.add_argument("--expected-source-hash", help="optional source hash guard")
    apply_back_parser.add_argument(
        "--allow-source-hash-mismatch",
        action="store_true",
        help="danger: continue when --expected-source-hash does not match the current source hash",
    )
    apply_back_parser.add_argument(
        "--allow-non-converged",
        action="store_true",
        help="danger: allow writing back from a non-CONVERGED run; intended only for manual recovery",
    )
    apply_back_parser.add_argument("--apply", action="store_true", help="write the final Whetstone draft back to --source")
    apply_back_parser.add_argument("--approve", action="store_true", help="required with --apply")

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
            declaration=(root / "convergence_declaration.md").read_text(encoding="utf-8")
            if args.phase == "phase_2" and (root / "convergence_declaration.md").exists()
            else None,
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
            declaration=(root / "convergence_declaration.md").read_text(encoding="utf-8")
            if args.phase == "phase_2" and (root / "convergence_declaration.md").exists()
            else None,
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
        config = _apply_run_profile_overrides(config, root=root, args=args)
        config = _apply_timeout_overrides(config, args=args)
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
                    "rubric_manifest": _manifest_summary(config) if args.phase == "phase_2" else None,
                }
            )
        )
        return 0
    if args.command == "live-phase1":
        root = Path(args.root)
        config = load_config(root / args.config)
        config = _apply_timeout_overrides(config, args=args)
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
    if args.command == "live-phase2":
        root = Path(args.root)
        config = load_config(root / args.config)
        config = _apply_run_profile_overrides(config, root=root, args=args)
        config = _apply_timeout_overrides(config, args=args)
        result = LivePhase2Runner(root, config, timeout_seconds=args.timeout_seconds).run(overwrite=args.overwrite)
        print(
            json.dumps(
                {
                    "terminal_state": result.terminal_state,
                    "round_number": result.round_number,
                    "current_draft_hash": result.current_draft_hash,
                    "last_accepted_draft_hash": result.last_accepted_draft_hash,
                    "declaration_path": str(result.declaration_path) if result.declaration_path else None,
                    "report_path": str(result.report_path) if result.report_path else None,
                    "rubric_manifest": _manifest_summary(config),
                }
            )
        )
        return 0
    if args.command == "resume":
        root = Path(args.root)
        config = load_config(root / args.config)
        config = _apply_resume_run_state_config(config)
        config = _apply_timeout_overrides(config, args=args)
        if args.dry_run:
            plan = plan_resume_halted_run(root, config, continue_run=args.continue_run)
            print(
                json.dumps(
                    {
                        "resumable": plan.resumable,
                        "terminal_state": plan.terminal_state,
                        "failure_type": plan.failure_type,
                        "phase": plan.phase,
                        "client_role": plan.client_role,
                        "round_number": plan.round_number,
                        "profile": plan.profile,
                        "current_draft_hash": plan.current_draft_hash,
                        "expected_draft_hash": plan.expected_draft_hash,
                        "next_attempt_number": plan.next_attempt_number,
                        "continue": plan.continue_run,
                        "next_round_number": plan.next_round_number,
                        "reason": plan.reason,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        result = resume_halted_run(root, config, continue_run=args.continue_run, timeout_seconds=args.timeout_seconds)
        print(
            json.dumps(
                {
                    "resumed": result.resumed,
                    "terminal_state": result.terminal_state,
                    "round_number": result.round_number,
                    "phase": result.phase,
                    "profile": result.profile,
                    "current_draft_hash": result.current_draft_hash,
                    "last_accepted_draft_hash": result.last_accepted_draft_hash,
                    "ready_for_phase_2": result.ready_for_phase_2,
                }
            )
        )
        return 0
    if args.command == "status":
        root = Path(args.run_root or args.root)
        config = load_config(root / args.config)
        packet = read_status(root=root, config=config)
        if args.format == "text":
            print(render_status_text(packet), end="")
        else:
            print(json.dumps(packet, indent=2, sort_keys=True))
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
    if args.command == "decision-summary":
        outputs = write_decision_summary_outputs(
            register_path=Path(args.register),
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        summary = _read_json(outputs["decision_summary"])
        print(
            json.dumps(
                {
                    "decision_count": summary["decision_count"],
                    "unresolved_human_decision_count": summary["unresolved_human_decision_count"],
                    "decision_summary": str(outputs["decision_summary"]),
                    "decision_summary_markdown": str(outputs["decision_summary_markdown"]),
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
    if args.command == "apply-back":
        result = apply_back(
            source_path=Path(args.source),
            run_root=Path(args.run_root),
            apply=args.apply,
            approve=args.approve,
            expected_source_hash=args.expected_source_hash,
            allow_source_hash_mismatch=args.allow_source_hash_mismatch,
            allow_non_converged=args.allow_non_converged,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        print(
            json.dumps(
                {
                    "applied": result.applied,
                    "changed": result.changed,
                    "source_path": str(result.source_path),
                    "final_draft_path": str(result.final_draft_path),
                    "review_json_path": str(result.review_json_path),
                    "review_markdown_path": str(result.review_markdown_path),
                    "source_before_hash": result.source_before_hash,
                    "final_draft_hash": result.final_draft_hash,
                    "source_after_hash": result.source_after_hash,
                }
            )
        )
        return 0
    return 1


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as artifact_file:
        return json.load(artifact_file)


def _apply_run_profile_overrides(config: object, *, root: Path, args: object) -> object:
    workflow = getattr(args, "workflow", None)
    rubric = getattr(args, "rubric", None)
    rubric_label = getattr(args, "rubric_label", None)
    if workflow is None and rubric is None and rubric_label is None:
        return config

    convergence = config.convergence
    updates = {}
    if rubric is not None:
        if rubric in BUILTIN_RUBRIC_FILES:
            updates.update(
                {
                    "rubric_profile": rubric,
                    "rubric_source": "builtin",
                    "rubric_label": None,
                }
            )
        else:
            updates.update(
                {
                    "rubric_profile": "custom",
                    "rubric_source": "custom",
                    "rubric_label": rubric_label,
                    "rubric_path": root / rubric,
                }
            )
    elif rubric_label is not None:
        updates["rubric_label"] = rubric_label

    return replace(config, workflow=workflow or config.workflow, convergence=replace(convergence, **updates))


def _apply_timeout_overrides(config: object, *, args: object) -> object:
    reviewer_timeout = getattr(args, "reviewer_timeout_seconds", None)
    editor_timeout = getattr(args, "editor_timeout_seconds", None)
    if reviewer_timeout is None and editor_timeout is None:
        return config
    return replace(
        config,
        timeouts=replace(
            config.timeouts,
            reviewer_seconds=reviewer_timeout if reviewer_timeout is not None else config.timeouts.reviewer_seconds,
            editor_seconds=editor_timeout if editor_timeout is not None else config.timeouts.editor_seconds,
        ),
    )


def _apply_resume_run_state_config(config: object) -> object:
    state_path = config.rounds_dir / "run_state.json"
    if not state_path.exists():
        return config
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    return apply_effective_run_config(config, state)


def _manifest_summary(config: object) -> dict:
    manifest = build_rubric_manifest(config).packet
    return {
        "workflow": manifest["workflow"],
        "rubric_profile": manifest["rubric_profile"],
        "rubric_source": manifest["rubric_source"],
        "rubric_label": manifest["rubric_label"],
        "rubric_content_hash": manifest["rubric_content_hash"],
        "warnings": manifest["warnings"],
    }


def _read_json_list(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as artifact_file:
        data = json.load(artifact_file)
    if not isinstance(data, list):
        raise ValueError("fixture script must be a JSON array")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
