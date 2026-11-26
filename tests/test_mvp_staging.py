"""Operator-facing staging from actual intake through read-only public admission."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from whetstone.cli import main
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes


class MVPStagingTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.seed = self.base / "source.md"
        self.seed.write_bytes(b"# Import\r\n## Preview\r\nPreview before writing.\r\n## Apply\r\nReject an invalid file.\r\n")
        self.notes = self.base / "scope-notes.md"
        self.notes.write_text("## Core Outcome\nClarify the MVP importer.\n## In Scope\n- preview: define\n")
        self.root = self.base / "future-run"
        self.scope = self.base / "intake.json"

    def invoke(self, *args, expected=0):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main([str(arg) for arg in args])
        self.assertEqual(code, expected, stdout.getvalue())
        return json.loads(stdout.getvalue())

    def intake(self, *extra):
        self.invoke("intake", "--root", self.base, "--from-notes", self.notes, "--output", self.scope, *extra)
        return json.loads(self.scope.read_bytes())

    def stage(self, folder, expected=0):
        return self.invoke("stage-mvp", "--seed", self.seed, "--scope", self.scope, "--output", self.base / folder,
                           "--authority-scope", "import", "--profile-set", "utility_mvp", "--review-mode", "vertical",
                           "--model", "fixture", "--client", "codex", "--client-version", "fixture",
                           "--protect", "Preview", "Preview before writing.", "Catch errors early.",
                           "--protect", "Apply", "One invalid row rejects the file.", "Prevent partial writes.",
                           "--max-operations", "2", "--max-changed-sections", "2", "--max-changed-normative-units", "3",
                           expected=expected)

    def dry_run(self, folder, expected=0):
        result = self.invoke("vnext-admit", "--dry-run", "--root", self.root,
                             "--config", self.base / folder / "run.yaml", expected=expected)
        self.assertFalse(self.root.exists())
        return result

    def test_intake_and_exact_reproducible_bindings(self):
        draft = self.intake()
        self.assertRegex(draft["generated_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertIsNone(draft["approval"]["approved_at"])
        first = self.stage("draft")
        self.assertEqual(first["scope_status"], "draft")
        self.assertEqual(self.stage("repeat")["job_id"], first["job_id"])
        package = self.base / "draft"
        self.assertEqual((package / "scope.json").read_bytes(), canonical_json_bytes(draft))
        self.assertEqual((package / "seed.md").read_bytes(), self.seed.read_bytes().replace(b"\r\n", b"\n"))
        self.assertEqual(first["seed_hash"], sha256_bytes((package / "seed.md").read_bytes()))
        self.assertEqual(first["source_hash"], sha256_bytes(self.seed.read_bytes()))
        self.assertNotEqual(first["source_hash"], first["seed_hash"])
        self.assertEqual(first["package_hash"], sha256_bytes((package / "package.json").read_bytes()))
        self.assertIn("file exists", self.stage("draft", expected=2)["error"].lower())
        assertions = json.loads((package / "protected.json").read_bytes())["assertions"]
        self.assertEqual([a["target_scope"] for a in assertions], ["section:preview", "section:apply"])
        self.assertTrue(all(a["enforcement"] == "semantic" and a["severity"] == "blocking" for a in assertions))

    @unittest.skipUnless(sys.platform == "darwin", "verified runtime requires local macOS/APFS")
    def test_scope_approval_rebuild_admission_and_tamper_refusal(self):
        self.intake()
        draft = self.stage("draft")
        self.assertIn("scope must be approved", self.dry_run("draft", 2)["reason"])
        approved = self.intake("--approve")
        self.assertEqual(approved["approval"]["approved_at"], approved["generated_at"])
        ready = self.stage("approved")
        self.assertNotEqual(ready["job_id"], draft["job_id"])
        self.assertNotEqual(ready["package_hash"], draft["package_hash"])
        self.dry_run("approved")
        (self.base / "approved" / "seed.md").write_bytes(self.seed.read_bytes() + b"changed")
        self.assertIn("hash", self.dry_run("approved", 2)["reason"].lower())
        self.assertIn("scope must be approved", self.dry_run("draft", 2)["reason"])

    def test_prior_intake_timestamp_is_canonicalized_only_in_new_package(self):
        approved = self.intake("--approve")
        approved["generated_at"] = approved["approval"]["approved_at"] = "2025-01-02T03:04:05.123456+00:00"
        raw = json.dumps(approved).encode()
        self.scope.write_bytes(raw)
        self.stage("legacy")
        staged = json.loads((self.base / "legacy" / "scope.json").read_bytes())
        self.assertEqual(staged["generated_at"], "2025-01-02T03:04:05Z")
        self.assertEqual(staged["approval"]["approved_at"], staged["generated_at"])
        self.assertEqual(self.scope.read_bytes(), raw)

    def test_ambiguous_protection_leaves_no_package(self):
        self.intake()
        self.seed.write_text("# Import\n## Preview\nFirst\n## Preview\nSecond\n## Apply\nApply\n")
        self.assertIn("unique seed heading", self.stage("ambiguous", 2)["error"])
        self.assertFalse((self.base / "ambiguous").exists())
