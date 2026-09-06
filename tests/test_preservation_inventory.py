from __future__ import annotations

from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import unittest

from whetstone.contracts import SchemaValidationError
from whetstone.hashing import draft_hash
from whetstone.preservation_inventory import build_inventory, match_inventory_units, section_path, validate_inventory, sha256_bytes, _unique_lcs

CORPUS = Path(__file__).resolve().parents[1] / "examples/fixtures/preservation_bridge"


class PreservationInventoryTests(unittest.TestCase):
    def test_mixed_endings_bom_and_unterminated_tail_partition_exact_bytes(self):
        raw = (CORPUS / "06_parser_and_versions/mixed_endings.md").read_bytes()
        inventory = build_inventory(raw, path="seed.md")
        expected = [b"\xef\xbb\xbfPreamble MUST remain.\r\n", b"# Byte Probe\n", b"## Payload\r",
                    b"```text\r\n", b"# Literal heading\n", b"```\r", b"Tail MUST survive."]
        self.assertEqual([raw[u["byte_start"]:u["byte_end"]] for u in inventory["units"]], expected)
        self.assertEqual([u["kind"] for u in inventory["units"]],
                         ["body", "heading", "heading", "fence_delimiter", "fence_body", "fence_delimiter", "body"])
        self.assertEqual(inventory["units"][0]["section_id"], "[]")
        self.assertEqual(inventory["units"][-1]["section_id"], '[["Byte Probe",1],["Payload",1]]')
        validate_inventory(inventory, raw)

    def test_parser_probe_has_only_real_headings_and_independent_duplicate_paths(self):
        raw = (CORPUS / "06_parser_and_versions/base.md").read_bytes()
        inventory = build_inventory(raw, path="seed.md")
        self.assertEqual([s["section_id"] for s in inventory["sections"]], ["[]", '[["Parser Probe 0.17",1]]',
            '[["Parser Probe 0.17",1],["Payload",1]]', '[["Parser Probe 0.17",1],["Notes",1]]',
            '[["Parser Probe 0.17",1],["Notes",2]]'])
        self.assertEqual(len(inventory["units"]), 31)
        direct = [uid for section in inventory["sections"] for uid in section["direct_unit_ids"]]
        self.assertCountEqual(direct, [u["unit_id"] for u in inventory["units"]])
        self.assertEqual(len(direct), len(set(direct)))
        self.assertEqual(inventory["units"][-1]["section_id"], inventory["sections"][-1]["section_id"])

    def test_empty_blank_crlf_and_unclosed_fences(self):
        self.assertEqual(build_inventory(b"", path="seed.md")["units"], [])
        self.assertEqual(len(build_inventory(b"\r\n", path="seed.md")["units"]), 1)
        for marker in (b"```", b"~~~~"):
            with self.subTest(marker=marker):
                inventory = build_inventory(marker+b"lang\n# not a heading\n~~~\n# still fenced", path="seed.md")
                self.assertEqual(len(inventory["sections"]), 1)
                self.assertEqual(inventory["units"][-1]["kind"], "fence_body")

    def test_heading_grammar_title_preservation_parentage_and_fence_closers(self):
        raw = '# Root ###\n### Café  Name\n# Root\n## Child\n#### Skipped\n# ###\n    # body\n```\n```` trailing\n# literal\n````\n# After'.encode()
        inventory = build_inventory(raw, path="seed.md")
        self.assertEqual([s["section_id"] for s in inventory["sections"]], ["[]", '[["Root",1]]',
            '[["Root",1],["Café  Name",1]]', '[["Root",2]]', '[["Root",2],["Child",1]]',
            '[["Root",2],["Child",1],["Skipped",1]]', '[["",1]]', '[["After",1]]'])
        self.assertEqual(inventory["units"][9]["kind"], "fence_body")

    def test_normative_ascii_boundaries_and_unicode(self):
        inventory = build_inventory('MUST\nMUST_NOT\nmust\nXSHALL\n(OPTIONAL)\néMUSTé\nSHOULD9\n'.encode(), path="seed.md")
        self.assertEqual([u["normative"] for u in inventory["units"]], [True, False, False, False, True, True, False])

    def test_invalid_utf8_and_inventory_field_tampering_reject(self):
        with self.assertRaises(UnicodeDecodeError): build_inventory(b"\xff", path="seed.md")
        raw = b"# Root\nMUST remain\n"; expected = build_inventory(raw, path="seed.md")
        mutations = [("byte_end", 2), ("ordinal", 4), ("normative", False), ("section_id", "[]"), ("unit_id", "u_"+"a"*64)]
        for key, value in mutations:
            with self.subTest(key=key), self.assertRaises(SchemaValidationError):
                bad = deepcopy(expected); bad["units"][1][key] = value; validate_inventory(bad, raw)
        bad = deepcopy(expected); bad["sections"][1]["direct_unit_ids"] = []
        with self.assertRaises(SchemaValidationError): validate_inventory(bad, raw)

    def test_exact_identity_changes_even_when_normalized_hash_does_not(self):
        a, b = b"# A\nMUST retain.\n", b"# A\r\nMUST retain.\r\n"
        self.assertEqual(draft_hash(a.decode()), draft_hash(b.decode()))
        left, right = build_inventory(a, path="a.md"), build_inventory(b, path="b.md")
        self.assertNotEqual(left["base_draft"]["sha256"], right["base_draft"]["sha256"])
        self.assertNotEqual(left["units"][0]["unit_id"], right["units"][0]["unit_id"])
        self.assertEqual(match_inventory_units(left, right).pairs, ())

    def test_section_path_grammar(self):
        for invalid in ('null', '{}', '[ ["A",1]]', '[["A",true]]', '[["A",0]]', '[[2,1]]', '[["A",1.0]]'):
            with self.subTest(value=invalid), self.assertRaises(ValueError): section_path(invalid)
        self.assertEqual(section_path('[["",1]]'), [["", 1]])

    def test_duplicates_are_positional_only_when_unchanged(self):
        base = build_inventory(b"# A\nMUST stay\nMUST stay\n", path="base.md")
        same = build_inventory(b"# A\nMUST stay\nMUST stay\n", path="same.md")
        self.assertEqual(len(match_inventory_units(base, same).pairs), 3)
        changed = build_inventory(b"# A\nMUST stay\n", path="after.md")
        self.assertTrue(match_inventory_units(base, changed).ambiguous_base)
        adopted = [{"base_unit_id": base["units"][2]["unit_id"], "successor_unit_ids": [], "disposition": "authorized_deleted"}]
        resolved = match_inventory_units(base, changed, adopted=adopted)
        self.assertFalse(resolved.ambiguous_base)
        self.assertEqual(len(resolved.pairs), 2)

    def test_matching_never_crosses_section_ownership(self):
        base = build_inventory(b"# A\nMUST remain\n# B\n", path="base.md")
        output = build_inventory(b"# A\n# B\nMUST remain\n", path="after.md")
        result = match_inventory_units(base, output)
        self.assertIn(base["units"][1]["unit_id"], result.unmatched_base)
        self.assertIn(output["units"][2]["unit_id"], result.unmatched_output)

    def test_lcs_uniqueness_against_exhaustive_alignment_oracle(self):
        def alignments(a, b, i=0, j=0):
            choices = {()}
            for x in range(i, len(a)):
                for y in range(j, len(b)):
                    if a[x] == b[y]:
                        choices.update(((x,y),)+tail for tail in alignments(a,b,x+1,y+1))
            longest = max(map(len, choices))
            return {c for c in choices if len(c)==longest}
        words = [p for n in range(4) for p in product("ab", repeat=n)]
        for a in words:
            for b in words:
                with self.subTest(a=a,b=b):
                    possible = alignments(a,b)
                    actual = _unique_lcs(list(a),list(b))
                    self.assertEqual(actual, list(next(iter(possible))) if len(possible)==1 else None)

    def test_toy_catalog_preserves_exact_fixture_bytes(self):
        for case in json.loads((CORPUS / "cases.json").read_text())["cases"]:
            assets=[case["base"],*case["variants"].values()]
            if "parser_probe" in case: assets.append(case["parser_probe"])
            for asset in assets:
                with self.subTest(path=asset["path"]):
                    raw=(CORPUS/asset["path"]).read_bytes()
                    self.assertEqual(len(raw),asset["bytes"])
                    self.assertEqual(sha256_bytes(raw),asset["sha256"])

    def test_published_conformance_vectors(self):
        path = Path(__file__).parent / "fixtures/preservation/bridge_lines_v1.json"
        for vector in json.loads(path.read_text()):
            with self.subTest(name=vector["name"]):
                self.assertEqual(build_inventory(bytes.fromhex(vector["input_hex"]), path="seed.md"), vector["inventory"])


if __name__ == "__main__": unittest.main()
