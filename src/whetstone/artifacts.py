"""Filesystem artifact store for deterministic fixture-mode runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from whetstone.contracts import validate_artifact


@dataclass(frozen=True)
class ArtifactPaths:
    spec_path: Path
    history_path: Path
    rounds_dir: Path
    declaration_path: Path


class ArtifactStore:
    """Read and write Whetstone artifacts relative to a repository root."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.paths = ArtifactPaths(
            spec_path=self.root / "spec.md",
            history_path=self.root / "spec.history.md",
            rounds_dir=self.root / "rounds",
            declaration_path=self.root / "convergence_declaration.md",
        )

    def read_spec(self) -> str:
        return self.paths.spec_path.read_text(encoding="utf-8")

    def write_spec(self, content: str) -> None:
        self.paths.spec_path.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        normalized = entry.rstrip() + "\n"
        with self.paths.history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(normalized)

    def round_dir(self, round_number: int, *, create: bool = False, overwrite: bool = False) -> Path:
        if round_number < 1:
            raise ValueError("round_number must be >= 1")
        path = self.paths.rounds_dir / f"round-{round_number}"
        if create:
            if path.exists() and not overwrite:
                raise FileExistsError(path)
            if path.exists() and overwrite:
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=False)
        return path

    def begin_round(self, round_number: int, *, overwrite: bool = False) -> Path:
        return self.round_dir(round_number, create=True, overwrite=overwrite)

    def write_round_json(
        self,
        round_number: int,
        filename: str,
        data: dict[str, Any],
        *,
        schema_name: str | None = None,
    ) -> Path:
        if schema_name is not None:
            validate_artifact(data, schema_name)
        round_path = self.round_dir(round_number)
        round_path.mkdir(parents=True, exist_ok=True)
        output_path = round_path / filename
        output_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return output_path

    def write_round_text(self, round_number: int, filename: str, content: str) -> Path:
        round_path = self.round_dir(round_number)
        round_path.mkdir(parents=True, exist_ok=True)
        output_path = round_path / filename
        output_path.write_text(content, encoding="utf-8")
        return output_path
