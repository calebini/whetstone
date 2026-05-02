"""Schema loading and minimal JSON Schema validation for Whetstone artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "contracts" / "schemas"


@dataclass(frozen=True)
class SchemaValidationError(ValueError):
    """Raised when an artifact does not satisfy its schema."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class SchemaRegistry:
    """Load local schemas and validate the subset of JSON Schema used by Whetstone."""

    def __init__(self, schema_dir: Path = SCHEMA_DIR) -> None:
        self.schema_dir = schema_dir
        self._schemas: dict[str, dict[str, Any]] = {}

    def load(self, name: str) -> dict[str, Any]:
        schema_name = name if name.endswith(".json") else f"{name}.schema.json"
        if schema_name not in self._schemas:
            with (self.schema_dir / schema_name).open(encoding="utf-8") as schema_file:
                self._schemas[schema_name] = json.load(schema_file)
        return self._schemas[schema_name]

    def validate(self, instance: Any, schema_name: str) -> None:
        self._validate(instance, self.load(schema_name), "$")

    def _resolve_ref(self, ref: str) -> Any:
        file_name, _, pointer = ref.partition("#")
        schema = self.load(file_name) if file_name else self.load("common.schema.json")
        target: Any = schema
        if pointer:
            for part in pointer.removeprefix("/").split("/"):
                target = target[part]
        return target

    def _validate(self, instance: Any, schema: dict[str, Any], path: str) -> None:
        if "$ref" in schema:
            self._validate(instance, self._resolve_ref(schema["$ref"]), path)

        for option in schema.get("allOf", []):
            self._validate(instance, option, path)

        if "anyOf" in schema:
            errors: list[str] = []
            for option in schema["anyOf"]:
                try:
                    self._validate(instance, option, path)
                    break
                except SchemaValidationError as exc:
                    errors.append(str(exc))
            else:
                raise SchemaValidationError(path, f"matched no anyOf option: {'; '.join(errors)}")

        if "if" in schema and self._matches(instance, schema["if"], path):
            if "then" in schema:
                self._validate(instance, schema["then"], path)

        if "const" in schema and instance != schema["const"]:
            raise SchemaValidationError(path, f"expected const {schema['const']!r}")

        if "enum" in schema and instance not in schema["enum"]:
            raise SchemaValidationError(path, f"expected one of {schema['enum']!r}")

        if "type" in schema:
            self._validate_type(instance, schema["type"], path)

        if isinstance(instance, str):
            if len(instance) < schema.get("minLength", 0):
                raise SchemaValidationError(path, "string is shorter than minLength")
            if "pattern" in schema and not re.fullmatch(schema["pattern"], instance):
                raise SchemaValidationError(path, f"string does not match pattern {schema['pattern']!r}")
            if schema.get("format") == "date-time":
                self._validate_datetime(instance, path)

        if isinstance(instance, int) and not isinstance(instance, bool) and "minimum" in schema:
            if instance < schema["minimum"]:
                raise SchemaValidationError(path, f"integer is below minimum {schema['minimum']}")

        if isinstance(instance, list) and "items" in schema:
            for index, item in enumerate(instance):
                self._validate(item, schema["items"], f"{path}[{index}]")

        if isinstance(instance, dict):
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    raise SchemaValidationError(path, f"missing required property {key!r}")

            properties = schema.get("properties", {})
            for key, value in instance.items():
                if key in properties:
                    self._validate(value, properties[key], f"{path}.{key}")
                elif schema.get("additionalProperties") is False:
                    raise SchemaValidationError(path, f"unexpected property {key!r}")

    def _matches(self, instance: Any, schema: dict[str, Any], path: str) -> bool:
        try:
            self._validate(instance, schema, path)
        except SchemaValidationError:
            return False
        return True

    @staticmethod
    def _validate_type(instance: Any, expected: str, path: str) -> None:
        checks = {
            "object": lambda value: isinstance(value, dict),
            "array": lambda value: isinstance(value, list),
            "string": lambda value: isinstance(value, str),
            "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
            "boolean": lambda value: isinstance(value, bool),
            "null": lambda value: value is None,
        }
        if expected not in checks:
            raise SchemaValidationError(path, f"unsupported schema type {expected!r}")
        if not checks[expected](instance):
            raise SchemaValidationError(path, f"expected type {expected}")

    @staticmethod
    def _validate_datetime(value: str, path: str) -> None:
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise SchemaValidationError(path, "expected RFC 3339 date-time") from exc


def validate_artifact(instance: Any, schema_name: str) -> None:
    """Validate an artifact against a local Whetstone schema."""

    SchemaRegistry().validate(instance, schema_name)
