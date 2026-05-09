"""Configuration loading for Whetstone."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ClientConfig:
    name: str
    command: str
    version: str
    model: str


@dataclass(frozen=True)
class ConvergenceConfig:
    enabled: bool
    target_phase: str
    target_mode: str
    rubric_profile: str
    rubric_source: str
    rubric_label: str | None
    rubric_path: Path
    max_rounds: int


@dataclass(frozen=True)
class DecisionPointConfig:
    enabled: bool
    mode: str
    severities: tuple[str, ...]
    trigger_on_requirement_strength_change: bool
    trigger_on_authority_boundary_change: bool
    trigger_on_scope_change: bool
    trigger_on_new_enum_or_error_code: bool


@dataclass(frozen=True)
class TimeoutConfig:
    reviewer_seconds: int | None
    editor_seconds: int | None


@dataclass(frozen=True)
class ContractSurfaceConfig:
    enabled: bool
    action: str
    min_profile_rounds: int
    recent_window: int
    min_recent_serious_rounds: int
    min_contract_families: int


@dataclass(frozen=True)
class ScopeContractConfig:
    path: Path


@dataclass(frozen=True)
class OrchestratorConfig:
    spec_path: Path
    history_path: Path
    rounds_dir: Path
    declaration_path: Path
    workflow: str
    editor: ClientConfig
    reviewer: ClientConfig
    review_max_rounds: int
    review_profile_budgets: dict[str, int]
    review_budget_exhaustion_policy: str
    convergence: ConvergenceConfig
    convergence_profile_budgets: dict[str, int]
    decision_points: DecisionPointConfig
    timeouts: TimeoutConfig
    contract_surface: ContractSurfaceConfig
    scope_contract: ScopeContractConfig

    @classmethod
    def default(cls, root: Path | str = ".") -> "OrchestratorConfig":
        base = Path(root)
        return cls(
            spec_path=base / "spec.md",
            history_path=base / "spec.history.md",
            rounds_dir=base / "rounds",
            declaration_path=base / "convergence_declaration.md",
            workflow="standard",
            editor=ClientConfig("fixture-editor", "fixture", "0.0.0", "fixture"),
            reviewer=ClientConfig("fixture-reviewer", "fixture", "0.0.0", "fixture"),
            review_max_rounds=12,
            review_profile_budgets={},
            review_budget_exhaustion_policy="hard",
            convergence=ConvergenceConfig(
                enabled=True,
                target_phase="final",
                target_mode="strict",
                rubric_profile="standard-v1",
                rubric_source="builtin",
                rubric_label=None,
                rubric_path=base / "convergence_rubric.md",
                max_rounds=8,
            ),
            convergence_profile_budgets={},
            decision_points=DecisionPointConfig(
                enabled=True,
                mode="end_of_cycle",
                severities=("blocker", "major"),
                trigger_on_requirement_strength_change=True,
                trigger_on_authority_boundary_change=True,
                trigger_on_scope_change=True,
                trigger_on_new_enum_or_error_code=True,
            ),
            timeouts=TimeoutConfig(reviewer_seconds=360, editor_seconds=900),
            contract_surface=ContractSurfaceConfig(
                enabled=True,
                action="recommend_synthesis",
                min_profile_rounds=4,
                recent_window=4,
                min_recent_serious_rounds=3,
                min_contract_families=2,
            ),
            scope_contract=ScopeContractConfig(path=base / "rounds" / "intake" / "scope_contract.json"),
        )


def load_config(path: Path | str) -> OrchestratorConfig:
    """Load a small YAML subset sufficient for the Whetstone config shape."""

    config_path = Path(path)
    root = config_path.parent
    if not config_path.exists():
        return OrchestratorConfig.default(root)
    parsed = _parse_simple_yaml(config_path.read_text(encoding="utf-8"))
    default = OrchestratorConfig.default(root)

    clients = parsed.get("clients", {})
    editor = clients.get("editor", {})
    reviewer = clients.get("reviewer", {})
    convergence = parsed.get("convergence", {})
    decision_points = parsed.get("decision_points", {})
    timeouts = parsed.get("timeouts", {})
    contract_surface = parsed.get("contract_surface_policy", {})
    scope_contract = parsed.get("scope_contract", {})
    thresholds = decision_points.get("intervention_thresholds", {})
    review = parsed.get("review", {})

    return OrchestratorConfig(
        spec_path=root / str(parsed.get("spec_path", default.spec_path.name)),
        history_path=root / str(parsed.get("history_path", default.history_path.name)),
        rounds_dir=root / str(parsed.get("rounds_dir", default.rounds_dir.name)),
        declaration_path=root / str(parsed.get("declaration_path", default.declaration_path.name)),
        workflow=str(parsed.get("workflow", default.workflow)),
        editor=ClientConfig(
            str(editor.get("name", default.editor.name)),
            str(editor.get("command", default.editor.command)),
            str(editor.get("version", default.editor.version)),
            str(editor.get("model", default.editor.model)),
        ),
        reviewer=ClientConfig(
            str(reviewer.get("name", default.reviewer.name)),
            str(reviewer.get("command", default.reviewer.command)),
            str(reviewer.get("version", default.reviewer.version)),
            str(reviewer.get("model", default.reviewer.model)),
        ),
        review_max_rounds=int(review.get("max_rounds", default.review_max_rounds)),
        review_profile_budgets=_parse_int_mapping(review.get("profile_budgets", default.review_profile_budgets)),
        review_budget_exhaustion_policy=str(
            review.get("budget_exhaustion_policy", default.review_budget_exhaustion_policy)
        ),
        convergence=ConvergenceConfig(
            enabled=bool(convergence.get("enabled", default.convergence.enabled)),
            target_phase=str(convergence.get("target_phase", default.convergence.target_phase)),
            target_mode=str(convergence.get("target_mode", default.convergence.target_mode)),
            rubric_profile=str(convergence.get("rubric_profile", default.convergence.rubric_profile)),
            rubric_source=str(convergence.get("rubric_source", default.convergence.rubric_source)),
            rubric_label=_optional_string(convergence.get("rubric_label", default.convergence.rubric_label)),
            rubric_path=root / str(convergence.get("rubric_path", default.convergence.rubric_path.name)),
            max_rounds=int(convergence.get("max_rounds", default.convergence.max_rounds)),
        ),
        convergence_profile_budgets=_parse_int_mapping(
            convergence.get("profile_budgets", default.convergence_profile_budgets)
        ),
        decision_points=DecisionPointConfig(
            enabled=bool(decision_points.get("enabled", default.decision_points.enabled)),
            mode=str(decision_points.get("mode", default.decision_points.mode)),
            severities=tuple(_parse_string_list(thresholds.get("severities", list(default.decision_points.severities)))),
            trigger_on_requirement_strength_change=bool(
                thresholds.get(
                    "trigger_on_requirement_strength_change",
                    default.decision_points.trigger_on_requirement_strength_change,
                )
            ),
            trigger_on_authority_boundary_change=bool(
                thresholds.get(
                    "trigger_on_authority_boundary_change",
                    default.decision_points.trigger_on_authority_boundary_change,
                )
            ),
            trigger_on_scope_change=bool(
                thresholds.get("trigger_on_scope_change", default.decision_points.trigger_on_scope_change)
            ),
            trigger_on_new_enum_or_error_code=bool(
                thresholds.get(
                    "trigger_on_new_enum_or_error_code",
                    default.decision_points.trigger_on_new_enum_or_error_code,
                )
            ),
        ),
        timeouts=TimeoutConfig(
            reviewer_seconds=_optional_int(timeouts.get("reviewer_seconds", default.timeouts.reviewer_seconds)),
            editor_seconds=_optional_int(timeouts.get("editor_seconds", default.timeouts.editor_seconds)),
        ),
        contract_surface=ContractSurfaceConfig(
            enabled=bool(contract_surface.get("enabled", default.contract_surface.enabled)),
            action=str(contract_surface.get("action", default.contract_surface.action)),
            min_profile_rounds=int(
                contract_surface.get("min_profile_rounds", default.contract_surface.min_profile_rounds)
            ),
            recent_window=int(contract_surface.get("recent_window", default.contract_surface.recent_window)),
            min_recent_serious_rounds=int(
                contract_surface.get(
                    "min_recent_serious_rounds",
                    default.contract_surface.min_recent_serious_rounds,
                )
            ),
            min_contract_families=int(
                contract_surface.get("min_contract_families", default.contract_surface.min_contract_families)
            ),
        ),
        scope_contract=ScopeContractConfig(
            path=root / str(scope_contract.get("path", _relative_default_scope_path(default.scope_contract.path, root)))
        ),
    )


def _relative_default_scope_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, separator, value = line.strip().partition(":")
        if not separator:
            raise ValueError(f"unsupported config line: {raw_line!r}")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if value.strip() == "":
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
        else:
            current[key] = _parse_scalar(value.strip())
    return root


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def _parse_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        return [part.strip().strip('"').strip("'") for part in value[1:-1].split(",") if part.strip()]
    return [str(value)]


def _parse_int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(item) for key, item in value.items()}


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if value == "":
        return None
    return int(value)
