from __future__ import annotations

import unittest

from whetstone.hashing import (
    draft_hash,
    mechanical_change_keys,
    normalize_draft,
    rubric_content_hash,
    semantic_change_hash,
)


class HashingTests(unittest.TestCase):
    def test_draft_hash_ignores_line_endings_trailing_space_and_final_newline(self) -> None:
        left = "# Title\r\n\n- item  \r\n"
        right = "# Title\n\n- item\n\n\n"

        self.assertEqual(normalize_draft(left), "# Title\n\n- item\n")
        self.assertEqual(draft_hash(left), draft_hash(right))

    def test_semantic_hash_preserves_default_unordered_list_order(self) -> None:
        left = "# List\n\n- b\n- a\n"
        right = "# List\n\n- a\n- b\n"

        self.assertNotEqual(semantic_change_hash(left, right), semantic_change_hash(left, left))

    def test_semantic_hash_sorts_order_insensitive_list_blocks(self) -> None:
        left = "# List\n\n[ORDER_INSENSITIVE_LIST]\n- b\n- a\n[/ORDER_INSENSITIVE_LIST]\n"
        right = "# List\n\n[ORDER_INSENSITIVE_LIST]\n- a\n- b\n[/ORDER_INSENSITIVE_LIST]\n"

        self.assertEqual(semantic_change_hash(left, right), semantic_change_hash(left, left))

    def test_mechanical_change_key_is_polarity_neutral(self) -> None:
        before = "# Spec\n"
        after = "# Spec\n\n## Added\nText\n"

        self.assertEqual(mechanical_change_keys(before, after), mechanical_change_keys(after, before))
        self.assertNotEqual(semantic_change_hash(before, after), semantic_change_hash(after, before))

    def test_rubric_content_hash_uses_draft_normalization(self) -> None:
        self.assertEqual(rubric_content_hash("# Rubric\r\n"), draft_hash("# Rubric\n\n"))


if __name__ == "__main__":
    unittest.main()
