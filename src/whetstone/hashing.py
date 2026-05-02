"""Content normalization and hashing primitives."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


ORDER_INSENSITIVE_OPEN = "[ORDER_INSENSITIVE_LIST]"
ORDER_INSENSITIVE_CLOSE = "[/ORDER_INSENSITIVE_LIST]"


@dataclass(frozen=True)
class SemanticChange:
    section_id: str
    polarity: str
    before_hash: str | None
    after_hash: str | None

    @property
    def hash(self) -> str:
        payload = "\n".join(
            [
                self.section_id,
                self.polarity,
                self.before_hash or "",
                self.after_hash or "",
            ]
        )
        return sha256_text(payload)

    @property
    def mechanical_key(self) -> str:
        content_hashes = sorted(hash_value or "__absent__" for hash_value in (self.before_hash, self.after_hash))
        payload = "\n".join([self.section_id, *content_hashes])
        return sha256_text(payload)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_draft(text: str) -> str:
    """Normalize full draft content for stable draft hashing."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in normalized.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def draft_hash(text: str) -> str:
    return sha256_text(normalize_draft(text))


def rubric_content_hash(text: str) -> str:
    """Hash rubric content with the same normalization as draft content."""

    return draft_hash(text)


def normalize_for_semantic_diff(text: str) -> str:
    """Normalize content for section-level semantic diff hashing."""

    normalized = normalize_draft(text)
    lines = normalized.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() == ORDER_INSENSITIVE_OPEN:
            block: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != ORDER_INSENSITIVE_CLOSE:
                block.append(lines[index])
                index += 1
            output.append(ORDER_INSENSITIVE_OPEN)
            output.extend(sorted(block))
            output.append(ORDER_INSENSITIVE_CLOSE)
            if index < len(lines):
                index += 1
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output) + "\n"


def semantic_changes(before: str, after: str) -> list[SemanticChange]:
    before_sections = _sections(normalize_for_semantic_diff(before))
    after_sections = _sections(normalize_for_semantic_diff(after))
    changes: list[SemanticChange] = []
    for section_id in sorted(set(before_sections) | set(after_sections)):
        before_content = before_sections.get(section_id)
        after_content = after_sections.get(section_id)
        before_hash = sha256_text(before_content) if before_content is not None else None
        after_hash = sha256_text(after_content) if after_content is not None else None
        if before_hash == after_hash:
            continue
        if before_content is None:
            polarity = "add"
        elif after_content is None:
            polarity = "remove"
        else:
            polarity = "modify"
        changes.append(SemanticChange(section_id, polarity, before_hash, after_hash))
    return changes


def semantic_change_hash(before: str, after: str) -> str:
    payload = "\n".join(change.hash for change in semantic_changes(before, after))
    return sha256_text(payload)


def mechanical_change_keys(before: str, after: str) -> list[str]:
    return [change.mechanical_key for change in semantic_changes(before, after)]


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_id = "__preamble__"
    counters: dict[str, int] = {}
    sections[current_id] = []
    for line in text.splitlines():
        if _is_heading(line):
            base_id = line.strip()
            counters[base_id] = counters.get(base_id, 0) + 1
            current_id = f"{base_id}#{counters[base_id]}"
            sections[current_id] = [line]
        else:
            sections.setdefault(current_id, []).append(line)
    return {section_id: "\n".join(lines).strip() for section_id, lines in sections.items()}


def _is_heading(line: str) -> bool:
    return re.match(r"^#{1,6}\s+\S", line) is not None
