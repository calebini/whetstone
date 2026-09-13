"""Public reviewer-only journeys, gate refusal and immutable run readback."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
from unittest import TestCase
from unittest.mock import patch

from whetstone.cli import main
from whetstone.config import load_config
from whetstone.vnext_admission import initialize, preflight, AdmissionError
from whetstone.vnext_contracts import canonical_json_bytes, derive_job_id, sha256_bytes
from whetstone.vnext_review import run_review, read_state
import test_vnext_admission as admission_tests
from test_live import GoodEmptyReviewerClient, GoodIssueReviewerClient


class Scripted:
    def __init__(self, root, steps):
        self.root, self.steps, self.calls = root, list(steps), 0

    def review(self, prompt):
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        if step == "invalid":
            return {"invalid": True}
        client = GoodEmptyReviewerClient(self.root) if step == "clean" else GoodIssueReviewerClient(self.root)
        packet = client.review(prompt)
        if step == "decision":
            packet["feedback"][0]["claim"] = "Choose whether this policy should allow fallback."
        return packet


class ReviewTests(TestCase):
    setUp = admission_tests.AdmissionTests.setUp
    snapshot = admission_tests.AdmissionTests.snapshot

    def start(self):
        ticket = preflight(self.root, self.config)
        initialize(ticket)
        return ticket

    def fresh_root(self, name):
        self.root = Path(self.tmp.name) / name
        self.root.mkdir()
        shutil.copytree(self.bundle.root / "inputs", self.root / "inputs")
        shutil.copyfile(self.bundle.root / "job_descriptor.json", self.root / "job_descriptor.json")
        self.config = {"vnext": {"job_descriptor": deepcopy(self.bundle.job_ref),
                                  "review_configuration": deepcopy(self.bundle.review_ref)}}

    def profiles(self, mode):
        review = deepcopy(self.bundle.review)
        review["review_mode"] = mode
        review["profiles"] = [{"name": "structural_integrity", "budget": 2}, {"name": "determinism", "budget": 2}]
        raw = canonical_json_bytes(review)
        (self.root / "inputs/review.json").write_bytes(raw)
        self.config["vnext"]["review_configuration"]["hash"] = sha256_bytes(raw)
        job = deepcopy(self.bundle.job)
        job["review_configuration_hash"] = sha256_bytes(raw)
        job["job_id"] = derive_job_id(job, self.suite.digest)
        raw = canonical_json_bytes(job)
        (self.root / "job_descriptor.json").write_bytes(raw)
        self.config["vnext"]["job_descriptor"]["hash"] = sha256_bytes(raw)

    def test_clean_review_and_repeat_readback_never_invoke_editor_or_verifier(self):
        ticket = self.start()
        client = Scripted(self.root, ["clean"])
        before_seed = (self.root / "spec.md").read_bytes()
        with patch("whetstone.live.create_editor_client", side_effect=AssertionError("Editor forbidden")):
            result = run_review(ticket, reviewer_client=client)
        self.assertEqual(result["terminal_state"], "PHASE_1_STABLE")
        self.assertFalse(result["apply_back_permitted"])
        self.assertTrue(all(value is None for value in result["latest_candidate"].values()))
        self.assertEqual(client.calls, 1)
        self.assertEqual((self.root / "spec.md").read_bytes(), before_seed)
        before = self.snapshot()
        self.assertEqual(run_review(ticket, reviewer_client=client), result)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(client.calls, 1)

    def test_horizontal_and_vertical_profile_budget_order(self):
        for mode, steps, expected in [
            ("horizontal", ["issue", "clean", "clean"], ["structural_integrity", "structural_integrity", "determinism"]),
            ("vertical", ["issue", "clean", "clean"], ["structural_integrity", "determinism", "structural_integrity"]),
        ]:
            with self.subTest(mode=mode):
                self.fresh_root(mode)
                self.profiles(mode)
                ticket = self.start()
                result = run_review(ticket, reviewer_client=Scripted(self.root, steps))
                self.assertEqual(result["terminal_state"], "PHASE_1_STABLE")
                receipts = read_state(ticket)[2]
                self.assertEqual([r["profile"] for r in receipts], expected)

    def test_pending_decision_and_residual_budget_are_distinct(self):
        ticket = self.start()
        result = run_review(ticket, reviewer_client=Scripted(self.root, ["decision"]))
        self.assertEqual(result["terminal_state"], "PAUSED_DECISION")
        self.assertEqual(len(result["outstanding_decision_ids"]), 1)
        self.assertFalse(result["resume"]["permitted"])
        self.assertFalse((self.root / "rounds/candidate_index").exists())

    def test_single_shape_retry_and_timeout_does_not_retry(self):
        for index, (steps, calls, terminal) in enumerate([(["invalid", "clean"], 2, "PHASE_1_STABLE"),
                                       (["invalid", "invalid"], 2, "HALTED_ARTIFACT_INVALID"),
                                       ([TimeoutError("deadline")], 1, "HALTED_CLIENT_TIMEOUT"),
                                       ([RuntimeError("provider exit")], 1, "HALTED_ARTIFACT_INVALID")], 1):
            with self.subTest(terminal=terminal):
                self.fresh_root(f"retry-{index}")
                ticket = self.start()
                client = Scripted(self.root, steps)
                report = run_review(ticket, reviewer_client=client)
                self.assertEqual(report["terminal_state"], terminal)
                self.assertEqual(client.calls, calls)
                before = self.snapshot()
                run_review(ticket, reviewer_client=client)
                self.assertEqual(client.calls, calls)
                self.assertEqual(before, self.snapshot())

    def test_input_change_during_review_never_reports_clean(self):
        ticket = self.start()
        class Changed:
            def review(inner, prompt):
                packet = GoodEmptyReviewerClient(self.root).review(prompt)
                (self.root / "inputs/seed.md").write_bytes(b"Changed\n")
                return packet
        with self.assertRaises(AdmissionError):
            run_review(ticket, reviewer_client=Changed())
        self.assertFalse((self.root / "rounds/vnext_terminal_report.json").exists())

    def test_interruption_after_review_output_is_visible_and_not_auto_resumed(self):
        import whetstone.vnext_review as reviews
        ticket = self.start()
        real = reviews.publish
        def interrupted(root, relative, value, **kwargs):
            if relative.endswith("vnext_run_state.json"):
                raise OSError("injected interruption")
            return real(root, relative, value, **kwargs)
        with patch.object(reviews, "publish", interrupted), self.assertRaises(OSError):
            run_review(ticket, reviewer_client=Scripted(self.root, ["clean"]))
        before = self.snapshot()
        with self.assertRaises(AdmissionError):
            read_state(ticket)
        with self.assertRaises(AdmissionError):
            run_review(ticket, reviewer_client=Scripted(self.root, []))
        self.assertEqual(before, self.snapshot())

    def cli(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(list(args))
        return code, json.loads(output.getvalue())

    def test_public_config_admit_review_status_and_forbidden_legacy_command(self):
        config = self.root / "orchestrator_config.yaml"
        config.write_text(json.dumps(self.config))
        before = self.snapshot()
        code, result = self.cli("vnext-admit", "--root", str(self.root), "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(before, self.snapshot())
        client = Scripted(self.root, ["clean"])
        with patch("whetstone.vnext_cli._client", return_value=client):
            code, result = self.cli("live-phase1", "--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(result["terminal_report"]["terminal_state"], "PHASE_1_STABLE")
        before = self.snapshot()
        code, status = self.cli("status", "--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(status["vnext"]["available_modes"], ["reviewer_only"])
        code, alias = self.cli("status", "--root", str(self.root / "unused"),
                               "--run-root", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(alias, status)
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["status", "--run-root", str(self.root), "--format", "text"])
        self.assertEqual(code, 0)
        self.assertIn("Mode: reviewer_only", output.getvalue())
        self.assertIn("State: PHASE_1_STABLE", output.getvalue())
        code, refused = self.cli("live-phase2", "--root", str(self.root))
        self.assertEqual(code, 2)
        self.assertEqual(refused["vnext"]["reason_code"], "vnext_gate_unavailable")
        self.assertEqual(before, self.snapshot())
        with self.assertRaisesRegex(ValueError, "vNext"):
            load_config(config)

    def test_public_cli_selectors_and_omission_never_downgrade(self):
        code, result = self.cli("vnext-admit", "--root", str(self.root),
                                "--vnext-job-descriptor", "job_descriptor.json",
                                "--vnext-review-configuration", "inputs/review.json")
        self.assertEqual(code, 0)
        before = self.snapshot()
        code, result = self.cli("resume", "--root", str(self.root), "--dry-run")
        self.assertEqual(code, 2)
        self.assertEqual(result["vnext"]["reason_code"], "vnext_gate_unavailable")
        self.assertEqual(before, self.snapshot())

    def test_public_configured_codex_transport_and_unused_roles(self):
        executable = Path(self.tmp.name) / "fake-codex"
        calls = Path(self.tmp.name) / "calls.txt"
        executable.write_text('''#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
args=sys.argv[1:]
assert args[0]=='exec'
assert args[args.index('--sandbox')+1]=='read-only'
out=Path(args[args.index('--output-last-message')+1])
prompt=sys.stdin.read()
profile=re.search(r'^Review profile: (.+)$',prompt,re.M).group(1)
number=int(re.search(r'^- round_number: ([0-9]+)$',prompt,re.M).group(1))
digest=re.search(r'^- draft_hash: ([a-f0-9]{64})$',prompt,re.M).group(1)
draft=Path(re.search(r'^- Draft path: (.+)$',prompt,re.M).group(1))
assert 'Wait at least 30 seconds.' in draft.read_text()
assert 'excluded-secret' not in prompt
out.write_text(json.dumps(dict(round_number=number,profile=profile,draft_hash=digest,
    reviewer=dict(name='client-self-description',version='0',model='fixture'),feedback=[])))
Path(__file__).with_name('calls.txt').write_text('reviewer-called')
''')
        executable.chmod(0o700)
        review = deepcopy(self.bundle.review)
        review["reviewer"] = {"name": "codex", "version": "fixture", "model": "fixture"}
        raw = canonical_json_bytes(review)
        (self.root / "inputs/review.json").write_bytes(raw)
        self.config["vnext"]["review_configuration"]["hash"] = sha256_bytes(raw)
        job = deepcopy(self.bundle.job)
        job["review_configuration_hash"] = sha256_bytes(raw)
        job["job_id"] = derive_job_id(job, self.suite.digest)
        raw = canonical_json_bytes(job)
        (self.root / "job_descriptor.json").write_bytes(raw)
        self.config["vnext"]["job_descriptor"]["hash"] = sha256_bytes(raw)
        self.config["clients"] = {"reviewer": {**review["reviewer"], "command": str(executable)},
                                  "editor": {**review["editor"], "command": "/nonexistent/editor"},
                                  "verifier": {**review["verifier"], "command": "/nonexistent/verifier"}}
        (self.root / "orchestrator_config.yaml").write_text(json.dumps(self.config))
        import os
        import subprocess
        import sys
        completed = subprocess.run(
            [sys.executable, "-m", "whetstone.cli", "live-phase1", "--root", str(self.root)],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        output = json.loads(completed.stdout)
        self.assertEqual(output["terminal_report"]["terminal_state"], "PHASE_1_STABLE")
        self.assertEqual(calls.read_text(), "reviewer-called")
        feedback = json.loads((self.root / "rounds/round-1/reviewer_feedback.json").read_bytes())
        self.assertEqual(feedback["reviewer"], review["reviewer"])
        self.assertTrue((self.root / "rounds/round-1/reviewer-attempt-1/telemetry.json").is_file())

    def test_legacy_python_writers_reject_an_admitted_vnext_root(self):
        from whetstone.config import OrchestratorConfig
        from whetstone.engine import FixtureEngine
        from whetstone.runner import FixtureRunner
        from whetstone.live import LiveRoundRunner
        from whetstone.live_phase1 import LivePhase1Runner
        from whetstone.live_phase2 import LivePhase2Runner
        from whetstone.apply_back import apply_back
        self.start()
        before = self.snapshot()
        config = OrchestratorConfig.default(self.root)
        for factory in (FixtureEngine, FixtureRunner, LiveRoundRunner, LivePhase1Runner, LivePhase2Runner):
            with self.subTest(factory=factory.__name__), self.assertRaises(AdmissionError):
                factory(self.root, config)
        with self.assertRaises(AdmissionError):
            apply_back(source_path=Path(self.tmp.name) / "external.md", run_root=self.root)
        self.assertEqual(before, self.snapshot())

    def test_rehashed_false_clean_receipt_cannot_support_completion(self):
        ticket = self.start()
        run_review(ticket, reviewer_client=Scripted(self.root, ["issue"]))
        receipt_path = self.root / "rounds/round-1/review_receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["clean"], receipt["serious_issue_ids"] = True, []
        raw = canonical_json_bytes(receipt)
        receipt_path.write_bytes(raw)
        state_path = self.root / "rounds/vnext_run_state.json"
        state = json.loads(state_path.read_bytes())
        state["receipts"][0]["hash"] = sha256_bytes(raw)
        state_path.write_bytes(canonical_json_bytes(state))
        before = self.snapshot()
        with self.assertRaises(AdmissionError):
            read_state(ticket)
        self.assertEqual(before, self.snapshot())
