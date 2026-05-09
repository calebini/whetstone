"""Text hygiene validation for generated draft content."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class TextValidationIssue:
    code: str
    line: int
    column: int
    code_point: str
    character_name: str

    def message(self) -> str:
        return (
            f"{self.code} at line {self.line}, column {self.column} "
            f"({self.code_point} {self.character_name})"
        )


class TextValidationError(ValueError):
    """Raised when generated text contains forbidden characters."""

    def __init__(self, issues: list[TextValidationIssue]) -> None:
        self.issues = issues
        joined = "; ".join(issue.message() for issue in issues[:5])
        if len(issues) > 5:
            joined += f"; and {len(issues) - 5} more"
        super().__init__(joined)


def validate_generated_text(text: str, *, context: str = "generated text") -> None:
    """Reject control/replacement characters that indicate text corruption."""

    issues: list[TextValidationIssue] = []
    line = 1
    column = 0
    for character in text:
        if character == "\n":
            line += 1
            column = 0
            continue
        column += 1
        if character == "\r" or character == "\t":
            continue
        if character == "\ufffd" or unicodedata.category(character) == "Cc":
            code = "REPLACEMENT_CHARACTER" if character == "\ufffd" else "FORBIDDEN_CONTROL_CHARACTER"
            issues.append(
                TextValidationIssue(
                    code=code,
                    line=line,
                    column=column,
                    code_point=f"U+{ord(character):04X}",
                    character_name=unicodedata.name(character, "<unnamed>"),
                )
            )
    if issues:
        raise TextValidationError(
            [
                TextValidationIssue(
                    code=f"{context}: {issue.code}",
                    line=issue.line,
                    column=issue.column,
                    code_point=issue.code_point,
                    character_name=issue.character_name,
                )
                for issue in issues
            ]
        )
