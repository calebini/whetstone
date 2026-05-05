"""Spec version promotion helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from pathlib import Path

from whetstone.hashing import draft_hash


ROOT_HEADING_RE = re.compile(r"^(# .*)$", re.MULTILINE)
STATUS_VERSION_RE = re.compile(r"^(Status:\s+.*?)(v?)(\d+(?:\.\d+)?)(.*)$", re.MULTILINE)
VERSION_RE = re.compile(r"(?<!\d)(\d+)(?:\.(\d+))?(?!\d)")


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


def promoted_phase2_version(version: str) -> str:
    """Return the Phase 2 whole-major version for a numeric spec version."""
    parts = version.strip().split(".")
    if not parts or not parts[0].isdigit() or len(parts) > 2:
        raise ValueError(f"unsupported spec version {version!r}")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else None
    if len(parts) == 2 and minor is None:
        raise ValueError(f"unsupported spec version {version!r}")
    if minor is None or minor == 0:
        return f"{max(major, 1)}.0"
    return f"{max(math.floor(major) + 1, 1)}.0"


def stamped_round_version(version: str, *, phase: str) -> str:
    """Return the next accepted-round version for a mutating live round."""
    major, minor = _parse_version(version)
    if phase == "phase_1":
        total = major * 100 + minor + 1
        return f"{total // 100}.{total % 100:02d}"
    if phase == "phase_2":
        return f"{major}.{minor + 1}"
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
    after_hash = draft_hash(stamped_text)
    return VersionStampResult(True, before_version, after_version, before_hash, after_hash, stamped_text)


def promote_spec_text_for_phase2(spec_text: str) -> tuple[str, str, str, bool]:
    """Promote the primary spec version anchor to the Phase 2 version."""
    target = _find_version_target(spec_text)
    if target is None:
        raise ValueError("spec does not contain a supported numeric version anchor")
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


def _parse_version(version: str) -> tuple[int, int]:
    parts = version.strip().split(".")
    if not parts or not parts[0].isdigit() or len(parts) > 2:
        raise ValueError(f"unsupported spec version {version!r}")
    major = int(parts[0])
    if len(parts) == 1:
        return major, 0
    if not parts[1].isdigit():
        raise ValueError(f"unsupported spec version {version!r}")
    return major, int(parts[1])


@dataclass(frozen=True)
class _VersionTarget:
    start: int
    end: int
    version: str
    prefix: str = ""

    def replace(self, text: str, version: str) -> str:
        return text[: self.start] + self.prefix + version + text[self.end :]


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
        )
    return None
