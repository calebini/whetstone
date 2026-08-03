"""Spec version promotion helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path

from whetstone.hashing import draft_hash


ROOT_HEADING_RE = re.compile(r"^(# .*)$", re.MULTILINE)
VERSION_LABEL = r"\d+(?:\.\d+){0,2}"
STATUS_VERSION_RE = re.compile(rf"^(Status:\s+.*?)(?<![\d.])(v?)({VERSION_LABEL})(?![\d.])(.*)$", re.MULTILINE)
VERSION_FIELD_RE = re.compile(rf"^(Version:\s+)(?<![\d.])(v?)({VERSION_LABEL})(?![\d.])(.*)$", re.MULTILINE)
VERSION_RE = re.compile(rf"(?<![\d.])({VERSION_LABEL})(?![\d.])")


@dataclass(frozen=True)
class VersionPromotionResult:
    promoted: bool
    before_version: str
    after_version: str
    before_hash: str
    after_hash: str


@dataclass(frozen=True)
class VersionStampResult:
    stamped: bool
    before_version: str
    after_version: str
    before_hash: str
    after_hash: str
    content: str


@dataclass(frozen=True)
class VersionAnchorNormalizationResult:
    normalized: bool
    before_version: str
    editor_version: str
    before_hash: str
    editor_hash: str
    normalized_hash: str
    content: str


def promoted_phase2_version(version: str) -> str:
    """Return the Phase 2 whole-major version for a numeric spec version."""
    parsed = _parse_version(version)
    major = parsed.parts[0]
    if len(parsed.parts) == 1 or all(part == 0 for part in parsed.parts[1:]):
        return f"{max(major, 1)}.0"
    return f"{max(major + 1, 1)}.0"


def stamped_round_version(version: str, *, phase: str) -> str:
    """Return the next accepted-round version for a mutating live round."""
    parsed = _parse_version(version)
    if phase == "phase_1":
        return parsed.next_phase1().format()
    if phase == "phase_2":
        return parsed.next_phase2().format()
    raise ValueError(f"unsupported phase {phase!r}")


def stamp_spec_text_for_round(spec_text: str, *, phase: str) -> VersionStampResult:
    """Stamp the primary spec version for an accepted mutating round."""
    target = _find_version_target(spec_text)
    if target is None:
        raise ValueError("spec does not contain a supported numeric version anchor")
    before_version = target.version
    after_version = stamped_round_version(before_version, phase=phase)
    before_hash = draft_hash(spec_text)
    if before_version == after_version:
        return VersionStampResult(False, before_version, after_version, before_hash, before_hash, spec_text)
    stamped_text = target.replace(spec_text, after_version)
    if phase == "phase_1":
        stamped_text = target.demote_accepted_status(stamped_text)
    after_hash = draft_hash(stamped_text)
    return VersionStampResult(True, before_version, after_version, before_hash, after_hash, stamped_text)


def normalize_editor_version_anchor(draft_before: str, draft_after: str) -> VersionAnchorNormalizationResult:
    """Restore the pre-round version label before Orchestrator-owned stamping.

    Editors may rewrite the visible version label while applying substantive edits.
    The version label is Orchestrator-owned, so accepted mutating rounds must stamp
    from the pre-round version rather than from an Editor-chosen value.
    """
    before_target = _find_version_target(draft_before)
    editor_target = _find_version_target(draft_after)
    before_hash = draft_hash(draft_before)
    editor_hash = draft_hash(draft_after)
    if before_target is None or editor_target is None or before_target.version == editor_target.version:
        return VersionAnchorNormalizationResult(
            False,
            before_target.version if before_target is not None else "",
            editor_target.version if editor_target is not None else "",
            before_hash,
            editor_hash,
            editor_hash,
            draft_after,
        )
    normalized = editor_target.replace(draft_after, before_target.version)
    return VersionAnchorNormalizationResult(
        True,
        before_target.version,
        editor_target.version,
        before_hash,
        editor_hash,
        draft_hash(normalized),
        normalized,
    )


def promote_spec_text_for_phase2(spec_text: str) -> tuple[str, str, str, bool]:
    """Promote the primary spec version anchor to the Phase 2 version."""
    target = _find_version_target(spec_text)
    if target is None:
        return spec_text, "", "", False
    before_version = target.version
    after_version = promoted_phase2_version(before_version)
    if before_version == after_version:
        return spec_text, before_version, after_version, False
    promoted_text = target.replace(spec_text, after_version)
    return promoted_text, before_version, after_version, True


def promote_spec_file_for_phase2(*, spec_path: Path, history_path: Path, rounds_dir: Path) -> VersionPromotionResult:
    """Promote a spec file after verifying the Phase 1 stable gate in run_state.json."""
    state_path = rounds_dir / "run_state.json"
    if not state_path.exists():
        raise ValueError("Phase 2 version promotion requires rounds/run_state.json")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("terminal_state") != "PHASE_1_STABLE" or state.get("ready_for_phase_2") is not True:
        raise ValueError("Phase 2 version promotion requires PHASE_1_STABLE with ready_for_phase_2=true")
    spec_text = spec_path.read_text(encoding="utf-8")
    before_hash = draft_hash(spec_text)
    if state.get("last_accepted_draft_hash") != before_hash:
        raise ValueError("Phase 2 version promotion requires current spec hash to match last_accepted_draft_hash")
    promoted_text, before_version, after_version, promoted = promote_spec_text_for_phase2(spec_text)
    after_hash = draft_hash(promoted_text)
    if promoted:
        spec_path.write_text(promoted_text, encoding="utf-8")
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(
                f"- Phase 2 version promotion: `{before_version}` -> `{after_version}`, "
                f"before `{before_hash}`, after `{after_hash}`.\n"
            )
        state["current_draft_hash"] = after_hash
        state["last_accepted_draft_hash"] = after_hash
        seen_hashes = state.get("seen_draft_hashes")
        if isinstance(seen_hashes, list):
            state["seen_draft_hashes"] = [*seen_hashes, after_hash]
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return VersionPromotionResult(promoted, before_version, after_version, before_hash, after_hash)


@dataclass(frozen=True)
class _ParsedVersion:
    parts: tuple[int, ...]
    widths: tuple[int, ...]

    def format(self) -> str:
        formatted = [str(self.parts[0])]
        for part, width in zip(self.parts[1:], self.widths[1:]):
            formatted.append(str(part).zfill(width))
        return ".".join(formatted)

    def next_phase1(self) -> "_ParsedVersion":
        if len(self.parts) == 1:
            return _ParsedVersion((self.parts[0], 1), (self.widths[0], 2))
        if len(self.parts) == 2:
            major, minor = self.parts
            minor_width = self.widths[1]
            next_minor = minor + 1
            if minor_width >= 2 and next_minor >= 10**minor_width:
                return _ParsedVersion((major + 1, 0), self.widths)
            return _ParsedVersion((major, next_minor), self.widths)
        major, minor, patch = self.parts
        return _ParsedVersion((major, minor, patch + 1), self.widths)

    def next_phase2(self) -> "_ParsedVersion":
        if len(self.parts) == 1:
            return _ParsedVersion((self.parts[0], 1), (self.widths[0], 1))
        if len(self.parts) == 2:
            major, minor = self.parts
            return _ParsedVersion((major, minor + 1), self.widths)
        major, minor, patch = self.parts
        return _ParsedVersion((major, minor, patch + 1), self.widths)


def _parse_version(version: str) -> _ParsedVersion:
    parts = version.strip().split(".")
    if not parts or len(parts) > 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"unsupported spec version {version!r}")
    return _ParsedVersion(tuple(int(part) for part in parts), tuple(len(part) for part in parts))


@dataclass(frozen=True)
class _VersionTarget:
    start: int
    end: int
    version: str
    prefix: str = ""
    line_start: int | None = None

    def replace(self, text: str, version: str) -> str:
        return text[: self.start] + self.prefix + version + text[self.end :]

    def demote_accepted_status(self, text: str) -> str:
        if self.line_start is None:
            return text
        line_end = text.find("\n", self.line_start)
        if line_end == -1:
            line_end = len(text)
        line = text[self.line_start : line_end]
        demoted = re.sub(r"^(Status:\s*)Accepted(\b)", r"\1Draft\2", line, count=1)
        if demoted == line:
            return text
        return text[: self.line_start] + demoted + text[line_end:]


def _find_version_target(spec_text: str) -> _VersionTarget | None:
    heading_match = ROOT_HEADING_RE.search(spec_text)
    if heading_match is not None:
        heading = heading_match.group(1)
        version_match = VERSION_RE.search(heading)
        if version_match is not None:
            return _VersionTarget(
                start=heading_match.start(1) + version_match.start(),
                end=heading_match.start(1) + version_match.end(),
                version=version_match.group(0),
            )

    status_match = STATUS_VERSION_RE.search(spec_text)
    if status_match is not None:
        return _VersionTarget(
            start=status_match.start(2),
            end=status_match.end(3),
            version=status_match.group(3),
            prefix=status_match.group(2),
            line_start=status_match.start(0),
        )
    version_field_match = VERSION_FIELD_RE.search(spec_text)
    if version_field_match is not None:
        return _VersionTarget(
            start=version_field_match.start(2),
            end=version_field_match.end(3),
            version=version_field_match.group(3),
            prefix=version_field_match.group(2),
        )
    return None
