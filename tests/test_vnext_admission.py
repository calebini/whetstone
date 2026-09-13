"""Seed initialization and admission refusal paths, with no client invocations."""
from copy import deepcopy
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone import vnext_admission as admission
from whetstone.vnext_contracts import canonical_json_bytes, derive_job_id, sha256_bytes, validate_contract_suite
from whetstone.vnext_sections import section_spans, seed_section_map
from vnext_fixtures import Bundle


def _initialize_worker(root, config, ready, release, results):
    admission.REVIEWER_ONLY_QUALIFIED = True
    try:
        ticket = admission.preflight(root, config)
        ready.put(True)
        if not release.wait(10):
            raise RuntimeError("test barrier timed out")
        admission.initialize(ticket)
        results.put("initialized")
    except (ValueError, OSError) as exc:
        results.put(type(exc).__name__)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "run"
        self.root.mkdir()
        self.suite = validate_contract_suite()
        source = Path(self.tmp.name) / "source"
        self.bundle = Bundle(source, self.suite, mode="reviewer_only")
        shutil.copytree(source / "inputs", self.root / "inputs")
        shutil.copyfile(source / "job_descriptor.json", self.root / "job_descriptor.json")
        self.config = {"vnext": {"job_descriptor": self.bundle.job_ref,
                                  "review_configuration": self.bundle.review_ref}}
        self.qualified = patch.object(admission, "REVIEWER_ONLY_QUALIFIED", True)
        self.qualified.start()
        self.addCleanup(self.qualified.stop)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def test_initialization_readback_and_no_implicit_candidates(self):
        before = self.snapshot()
        ticket = admission.preflight(self.root, self.config)
        self.assertEqual(before, self.snapshot())
        record = admission.initialize(ticket)
        current = admission.preflight(self.root, self.config, existing=True)
        pointer = admission.validate_initialized(current)
        self.assertEqual(pointer["promotion_ordinal"], 0)
        self.assertEqual(
            (self.root / "rounds/verified_history/current-verified-0.json").read_bytes(),
            (self.root / "rounds/current_verified.json").read_bytes(),
        )
        self.assertEqual(pointer["verified_draft_hash"], self.bundle.seed["hash"])
        self.assertEqual(record["job_id"], self.bundle.job["job_id"])
        self.assertFalse((self.root / "rounds/candidate_index").exists())
        after = self.snapshot()
        admission.validate_initialized(current)
        self.assertEqual(after, self.snapshot())
        with self.assertRaises(admission.AdmissionError):
            admission.initialize(ticket)
        self.assertEqual(after, self.snapshot())

    def test_existing_selectors_can_name_identical_copies_without_changing_admission(self):
        ticket = admission.preflight(self.root, self.config)
        admission.initialize(ticket)
        for role, name in (("job_descriptor", "descriptor-copy.json"),
                           ("review_configuration", "review-copy.json")):
            shutil.copyfile(self.root / self.config["vnext"][role]["path"], self.root / name)
        before = self.snapshot()
        copied = admission.preflight(self.root, self.config, descriptor_path="descriptor-copy.json",
                                      review_path="review-copy.json", existing=True)
        admission.validate_initialized(copied)
        self.assertEqual(before, self.snapshot())
        # An alternate locator is not permission to remove or replace the
        # immutable inputs recorded by admission.
        original = self.root / self.config["vnext"]["review_configuration"]["path"]
        original.write_bytes(b"{}")
        with self.assertRaises(admission.AdmissionError):
            admission.preflight(self.root, {}, descriptor_path="descriptor-copy.json",
                                review_path="review-copy.json", existing=True)

    def test_modes_fail_before_writes_and_qualification_cannot_be_assumed(self):
        for mode in ("proposal_only", "verified_promotion"):
            job = deepcopy(self.bundle.job)
            job["editing_mode"] = mode
            job["job_id"] = derive_job_id(job, self.suite.digest)
            raw = canonical_json_bytes(job)
            (self.root / "job_descriptor.json").write_bytes(raw)
            config = deepcopy(self.config)
            config["vnext"]["job_descriptor"]["hash"] = sha256_bytes(raw)
            before = self.snapshot()
            with self.assertRaises(admission.AdmissionError) as raised:
                admission.preflight(self.root, config)
            self.assertEqual(raised.exception.code, "vnext_mode_unavailable")
            self.assertEqual(before, self.snapshot())
        (self.root / "job_descriptor.json").write_bytes(canonical_json_bytes(self.bundle.job))
        with patch.object(admission, "REVIEWER_ONLY_QUALIFIED", False):
            with self.assertRaises(admission.AdmissionError):
                admission.preflight(self.root, self.config)

    def test_unknown_controls_and_mixed_protocol_refuse(self):
        for addition, code in [({"preservation_bridge": {}}, "vnext_selection_conflict"),
                               ({"editing_mode": "reviewer_only"}, "vnext_config_invalid"),
                               ({"workflow": "mvp"}, "vnext_mode_mismatch"),
                               ({"review": {"budget_exhaustion_policy": "soft"}}, "vnext_config_invalid")]:
            before = self.snapshot()
            with self.subTest(addition=addition), self.assertRaises(admission.AdmissionError) as raised:
                admission.preflight(self.root, {**self.config, **addition})
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(before, self.snapshot())

    def test_selector_conflicts_and_duplicate_config_keys(self):
        other = deepcopy(self.bundle.review)
        other["profiles"][0]["budget"] = 2
        (self.root / "other.json").write_bytes(canonical_json_bytes(other))
        with self.assertRaises(admission.AdmissionError) as raised:
            admission.preflight(self.root, self.config, descriptor_path="job_descriptor.json", review_path="other.json")
        self.assertEqual(raised.exception.code, "vnext_selection_conflict")
        path = self.root / "config.yaml"
        path.write_text("vnext:\n  job_descriptor: x\n  job_descriptor: y\n")
        with self.assertRaises(ValueError):
            admission.config_packet(path)

    def test_cli_and_yaml_references_with_identical_bytes(self):
        path = self.root / "config.yaml"
        path.write_text("vnext:\n" + "".join(
            f"  {key}: {{path: {ref['path']}, hash: {ref['hash']}}}\n"
            for key, ref in self.config["vnext"].items()))
        config = admission.config_packet(path)
        ticket = admission.preflight(self.root, config, descriptor_path="job_descriptor.json", review_path="inputs/review.json")
        self.assertEqual(ticket.job, self.bundle.job)

    def test_changed_input_and_symlink_refuse_without_writes(self):
        seed = self.root / "inputs/seed.md"
        raw = seed.read_bytes()
        seed.write_bytes(raw + b"Changed\n")
        before = self.snapshot()
        with self.assertRaises(admission.AdmissionError):
            admission.preflight(self.root, self.config)
        self.assertEqual(before, self.snapshot())
        seed.unlink()
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_bytes(raw)
        seed.symlink_to(outside)
        with self.assertRaises(admission.AdmissionError):
            admission.preflight(self.root, self.config)
        self.assertFalse((self.root / "rounds").exists())

    def test_partial_initialization_refuses_reentry_and_never_repairs(self):
        ticket = admission.preflight(self.root, self.config)
        real = admission.publish

        def interrupted(root, path, value, **kwargs):
            if path == admission.POINTER_PATH:
                raise OSError("injected pointer publication interruption")
            return real(root, path, value, **kwargs)

        with patch.object(admission, "publish", interrupted), self.assertRaises(OSError):
            admission.initialize(ticket)
        before = self.snapshot()
        self.assertTrue(admission.root_declares_vnext(self.root))
        with self.assertRaises(admission.AdmissionError):
            admission.preflight(self.root, self.config)
        with self.assertRaises(admission.AdmissionError):
            admission.preflight(self.root, self.config, existing=True)
        self.assertEqual(before, self.snapshot())

    def test_first_claim_crash_cannot_reenter_as_legacy_with_cli_only_inputs(self):
        # No root descriptor or vNext config exists to act as a fallback guard.
        shutil.move(self.root / "job_descriptor.json", self.root / "inputs/descriptor.json")
        config = deepcopy(self.config)
        config["vnext"]["job_descriptor"]["path"] = "inputs/descriptor.json"
        ticket = admission.preflight(self.root, config)
        with patch.object(admission, "sync_directory", side_effect=OSError("first barrier")):
            with self.assertRaises(OSError):
                admission.initialize(ticket)
        self.assertFalse((self.root / "rounds").exists())
        self.assertTrue(admission.root_declares_vnext(self.root))
        before = self.snapshot()
        with self.assertRaises(admission.AdmissionError):
            admission.reject_legacy_writer(self.root)
        with self.assertRaises(admission.AdmissionError):
            admission.preflight(self.root, config)
        self.assertEqual(before, self.snapshot())

    def test_each_seed_lineage_tamper_refuses_readback(self):
        admission.initialize(admission.preflight(self.root, self.config))
        for name in (admission.HISTORY_PATH, admission.POINTER_PATH, admission.SEED_MAP_PATH,
                     admission.ADMISSION_PATH, admission.ROOT_CLAIM_PATH, "spec.md", "job_descriptor.json"):
            path = self.root / name
            raw = path.read_bytes()
            with self.subTest(path=name):
                path.write_bytes(raw + b" ")
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    admission.preflight(self.root, self.config, existing=True)
                self.assertEqual(before, self.snapshot())
                path.write_bytes(raw)

    def test_competing_processes_cannot_both_initialize(self):
        import multiprocessing
        context = multiprocessing.get_context("spawn")
        ready, results, release = context.Queue(), context.Queue(), context.Event()
        workers = [context.Process(target=_initialize_worker,
                                   args=(str(self.root), self.config, ready, release, results)) for _ in range(2)]
        try:
            for worker in workers:
                worker.start()
            for _ in workers:
                self.assertTrue(ready.get(timeout=15))
            release.set()
            outcomes = [results.get(timeout=15) for _ in workers]
            self.assertEqual(outcomes.count("initialized"), 1)
            admission.preflight(self.root, self.config, existing=True)
        finally:
            release.set()
            for worker in workers:
                worker.join(timeout=5)
                if worker.is_alive():
                    worker.terminate()
                    worker.join()

    def test_absolute_seed_locator_is_bound_to_logical_pointer_path(self):
        job = deepcopy(self.bundle.job)
        job["seed_draft"]["path"] = str((self.root / job["seed_draft"]["path"]).resolve())
        self.assertEqual(derive_job_id(job, self.suite.digest), job["job_id"])
        raw = canonical_json_bytes(job)
        (self.root / "job_descriptor.json").write_bytes(raw)
        self.config["vnext"]["job_descriptor"]["hash"] = sha256_bytes(raw)
        ticket = admission.preflight(self.root, self.config)
        admission.initialize(ticket)
        self.assertEqual(admission.validate_initialized(ticket)["verified_draft_path"], "inputs/seed.md")

    def test_conflicting_materialization_refuses_before_claiming_root(self):
        (self.root / "spec.md").write_bytes(b"Different source content\n")
        before = self.snapshot()
        with self.assertRaises(admission.AdmissionError):
            admission.preflight(self.root, self.config)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "rounds").exists())


class SeedParserTests(unittest.TestCase):
    def test_fences_duplicates_preamble_and_exact_subtree_hashes(self):
        raw = b"Preamble\r\n# Root\r\nBody\r\n```md\r\n# False\r\n```\r\n## Child\r\nA\r\n## Child\r\nB"
        spans = section_spans(raw)
        self.assertEqual([s.canonical_id for s in spans], ["root", "child", "child#2"])
        self.assertEqual([s.parent for s in spans], [None, 0, 0])
        self.assertEqual(raw[spans[1].start:spans[1].end], b"## Child\r\nA\r\n")
        self.assertEqual(raw[spans[0].heading_end:spans[0].direct_end], b"Body\r\n```md\r\n# False\r\n```\r\n")
        job = {"job_id": "job_" + "a" * 64, "parser_contract_version": "markdown-atx-v1"}
        mapping = seed_section_map(raw, job, "bind_" + "b" * 64)
        self.assertEqual(mapping["sections"][0]["section_hash"], sha256_bytes(raw[10:]))
        self.assertEqual(mapping, seed_section_map(raw, job, "bind_" + "b" * 64))

    def test_empty_heading_escaped_heading_and_tilde_fence(self):
        raw = b"\\# escaped\n~~~\n## hidden\n~~~\n   #\n## Child ###\n"
        spans = section_spans(raw)
        self.assertEqual([(s.heading, s.level) for s in spans], [("", 1), ("Child", 2)])
        self.assertEqual(section_spans(b"No headings\n"), [])
