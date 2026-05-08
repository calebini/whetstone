"""Run-state configuration helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from whetstone.config import ContractSurfaceConfig, DecisionPointConfig, OrchestratorConfig, TimeoutConfig
from whetstone.scheduler import resolved_phase_1_profile_budgets, resolved_phase_2_profile_budgets


def effective_run_config(config: OrchestratorConfig) -> dict[str, Any]:
    """Return the effective run config that resume must preserve."""

    return {
        "review_profile_budgets": resolved_phase_1_profile_budgets(config.review_profile_budgets),
        "review_budget_exhaustion_policy": config.review_budget_exhaustion_policy,
        "convergence_profile_budgets": resolved_phase_2_profile_budgets(config.convergence_profile_budgets),
        "decision_points": {
            "enabled": config.decision_points.enabled,
            "mode": config.decision_points.mode,
            "intervention_thresholds": {
                "severities": list(config.decision_points.severities),
                "trigger_on_requirement_strength_change": (
                    config.decision_points.trigger_on_requirement_strength_change
                ),
                "trigger_on_authority_boundary_change": config.decision_points.trigger_on_authority_boundary_change,
                "trigger_on_scope_change": config.decision_points.trigger_on_scope_change,
                "trigger_on_new_enum_or_error_code": config.decision_points.trigger_on_new_enum_or_error_code,
            },
        },
        "timeouts": {
            "reviewer_seconds": config.timeouts.reviewer_seconds,
            "editor_seconds": config.timeouts.editor_seconds,
        },
        "contract_surface_policy": {
            "enabled": config.contract_surface.enabled,
            "action": config.contract_surface.action,
            "min_profile_rounds": config.contract_surface.min_profile_rounds,
            "recent_window": config.contract_surface.recent_window,
            "min_recent_serious_rounds": config.contract_surface.min_recent_serious_rounds,
            "min_contract_families": config.contract_surface.min_contract_families,
        },
    }


def apply_effective_run_config(config: OrchestratorConfig, packet: dict[str, Any]) -> OrchestratorConfig:
    """Apply persisted effective run config fields to a loaded config."""

    effective = packet.get("effective_run_config")
    if not isinstance(effective, dict):
        effective = {}

    review_profile_budgets = _int_mapping(
        effective.get("review_profile_budgets", packet.get("review_profile_budgets"))
    )
    review_budget_exhaustion_policy = str(
        effective.get(
            "review_budget_exhaustion_policy",
            getattr(config, "review_budget_exhaustion_policy", "hard"),
        )
    )
    convergence_profile_budgets = _int_mapping(
        effective.get("convergence_profile_budgets", packet.get("convergence_profile_budgets"))
    )
    decision_points = _decision_points_config(
        effective.get("decision_points"),
        fallback=config.decision_points,
    )
    timeouts = _timeout_config(
        effective.get("timeouts", packet.get("timeouts")),
        fallback=config.timeouts,
    )
    contract_surface = _contract_surface_config(
        effective.get("contract_surface_policy"),
        fallback=config.contract_surface,
    )

    return replace(
        config,
        review_profile_budgets=review_profile_budgets or config.review_profile_budgets,
        review_budget_exhaustion_policy=review_budget_exhaustion_policy,
        convergence_profile_budgets=convergence_profile_budgets or config.convergence_profile_budgets,
        decision_points=decision_points,
        timeouts=timeouts,
        contract_surface=contract_surface,
    )


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(item, bool):
            continue
        if isinstance(item, int) and item > 0:
            output[str(key)] = item
    return output


def _decision_points_config(value: Any, *, fallback: DecisionPointConfig) -> DecisionPointConfig:
    if not isinstance(value, dict):
        return fallback
    thresholds = value.get("intervention_thresholds")
    if not isinstance(thresholds, dict):
        thresholds = {}
    severities = thresholds.get("severities")
    if isinstance(severities, list):
        parsed_severities = tuple(str(severity) for severity in severities)
    else:
        parsed_severities = fallback.severities
    return DecisionPointConfig(
        enabled=_bool(value.get("enabled"), fallback.enabled),
        mode=str(value.get("mode", fallback.mode)),
        severities=parsed_severities,
        trigger_on_requirement_strength_change=_bool(
            thresholds.get("trigger_on_requirement_strength_change"),
            fallback.trigger_on_requirement_strength_change,
        ),
        trigger_on_authority_boundary_change=_bool(
            thresholds.get("trigger_on_authority_boundary_change"),
            fallback.trigger_on_authority_boundary_change,
        ),
        trigger_on_scope_change=_bool(thresholds.get("trigger_on_scope_change"), fallback.trigger_on_scope_change),
        trigger_on_new_enum_or_error_code=_bool(
            thresholds.get("trigger_on_new_enum_or_error_code"),
            fallback.trigger_on_new_enum_or_error_code,
        ),
    )


def _timeout_config(value: Any, *, fallback: TimeoutConfig) -> TimeoutConfig:
    if not isinstance(value, dict):
        return fallback
    return TimeoutConfig(
        reviewer_seconds=_optional_timeout(value, "reviewer_seconds", fallback.reviewer_seconds),
        editor_seconds=_optional_timeout(value, "editor_seconds", fallback.editor_seconds),
    )


def _contract_surface_config(value: Any, *, fallback: ContractSurfaceConfig) -> ContractSurfaceConfig:
    if not isinstance(value, dict):
        return fallback
    return ContractSurfaceConfig(
        enabled=_bool(value.get("enabled"), fallback.enabled),
        action=str(value.get("action", fallback.action)),
        min_profile_rounds=_positive_int(value.get("min_profile_rounds"), fallback.min_profile_rounds),
        recent_window=_positive_int(value.get("recent_window"), fallback.recent_window),
        min_recent_serious_rounds=_positive_int(
            value.get("min_recent_serious_rounds"),
            fallback.min_recent_serious_rounds,
        ),
        min_contract_families=_positive_int(value.get("min_contract_families"), fallback.min_contract_families),
    )


def _positive_int(value: Any, fallback: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return fallback


def _optional_timeout(packet: dict[str, Any], key: str, fallback: int | None) -> int | None:
    if key not in packet:
        return fallback
    value = packet.get(key)
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return fallback


def _bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback
