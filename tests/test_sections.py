from __future__ import annotations

import unittest

from whetstone.sections import section_index


class SectionIndexTests(unittest.TestCase):
    def test_section_index_uses_heading_path_and_repeat_suffixes(self) -> None:
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
            ["spec", "spec-hashing", "spec-hashing#2", "other", "other-hashing"],
        )


if __name__ == "__main__":
    unittest.main()
