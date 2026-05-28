from __future__ import annotations

import unittest

from whetstone.sections import section_index


class SectionIndexTests(unittest.TestCase):
    def test_section_index_excludes_root_h1_from_descendant_ids(self) -> None:
        sections = section_index(
            "\n".join(
                [
                    "# Spec",
                    "Intro",
                    "## Hashing",
                    "Text",
                    "## Hashing",
                    "More text",
                    "# Other",
                    "## Hashing",
                ]
            )
        )

        self.assertEqual(
            [section.id for section in sections],
            ["spec", "hashing", "hashing#2", "other", "other-hashing"],
        )

    def test_single_h1_is_not_excluded(self) -> None:
        sections = section_index("# Spec\n")

        self.assertEqual([section.id for section in sections], ["spec"])


if __name__ == "__main__":
    unittest.main()
