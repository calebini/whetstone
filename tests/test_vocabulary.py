from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from whetstone.cli import main
from whetstone.contracts import validate_artifact
from whetstone.scheduler import PROFILE_SETS, REVIEW_PROFILE_DEFINITIONS, profile_prompt_guidance
from whetstone.vocabulary import (
    CONCERN_TYPES,
    REVIEW_INVARIANTS,
    VOCABULARY_SCHEMA_VERSION,
    controlled_vocabulary_hash,
    controlled_vocabulary_packet,
)


class ControlledVocabularyTests(unittest.TestCase):
    def test_controlled_vocabulary_packet_validates(self) -> None:
        packet = controlled_vocabulary_packet()

        validate_artifact(packet, "controlled_vocabulary")

        self.assertEqual(packet["schema_version"], VOCABULARY_SCHEMA_VERSION)
        self.assertEqual(packet["severity_order"], ["nit", "minor", "major", "blocker"])
        self.assertIn("authority_boundary", packet["review_invariants"])
        self.assertIn("precision_gap", packet["oscillation"]["concern_types"])
        self.assertIn("utility_mvp", packet["profile_sets"])
        self.assertIn("mvp_readiness_check", packet["convergence_acceptance_profiles"])

    def test_vocabulary_hash_is_stable_for_packet(self) -> None:
        first = controlled_vocabulary_hash()
        second = controlled_vocabulary_hash()

        self.assertRegex(first, r"^[a-f0-9]{64}$")
        self.assertEqual(first, second)

    def test_scheduler_reads_profile_vocabulary(self) -> None:
        self.assertIs(REVIEW_PROFILE_DEFINITIONS["determinism"], REVIEW_PROFILE_DEFINITIONS["determinism"])
        self.assertIn("determinism_light", REVIEW_PROFILE_DEFINITIONS)
        self.assertIn("utility_mvp", PROFILE_SETS)
        self.assertIn("observable MVP outcomes", profile_prompt_guidance("determinism_light") or "")

    def test_prompt_vocabularies_are_exported(self) -> None:
        packet = controlled_vocabulary_packet()

        self.assertEqual(set(packet["oscillation"]["concern_types"]), set(CONCERN_TYPES))
        self.assertEqual(set(packet["review_invariants"]), set(REVIEW_INVARIANTS))

    def test_cli_exports_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "controlled_vocabulary.json"

            exit_code = main(["vocabulary", "--output", str(output)])

            self.assertEqual(exit_code, 0)
            packet = json.loads(output.read_text(encoding="utf-8"))
            validate_artifact(packet, "controlled_vocabulary")


if __name__ == "__main__":
    unittest.main()
