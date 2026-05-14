"""Canonical rubric profile and workflow manifest support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whetstone.config import OrchestratorConfig
from whetstone.contracts import validate_artifact
from whetstone.hashing import rubric_content_hash
from whetstone.scheduler import default_phase_2_scheduler, resolved_phase_1_profile_budgets, resolved_phase_2_profile_budgets


RUBRICS_DIR = Path(__file__).resolve().parents[2] / "rubrics"

BUILTIN_RUBRIC_FILES = {
    "governance-v6": "governance-v6.md",
    "standard-v1": "standard-v1.md",
    "mvp-v1": "mvp-v1.md",
    "exploratory-v1": "exploratory-v1.md",
}

WORKFLOW_DEFAULTS = {
    "exploratory": {
        "rubric_profile": "exploratory-v1",
        "target_phase": "mid",
        "target_mode": "permissive",
        "convergence_max_rounds": 4,
    },
    "mvp": {"rubric_profile": "mvp-v1", "target_phase": "mid", "target_mode": "strict", "convergence_max_rounds": 5},
    "standard": {
        "rubric_profile": "standard-v1",
        "target_phase": "final",
        "target_mode": "strict",
        "convergence_max_rounds": 8,
    },
    "governance": {
        "rubric_profile": "governance-v6",
        "target_phase": "final",
        "target_mode": "strict",
        "convergence_max_rounds": 8,
    },
    "custom": {"rubric_profile": "custom", "target_phase": "final", "target_mode": "strict", "convergence_max_rounds": 8},
}


@dataclass(frozen=True)
class RubricManifest:
    """Resolved rubric/workflow identity for a Phase 2 run."""

    path: Path
    packet: dict[str, Any]

    @property
    def rubric_content_hash(self) -> str:
        return str(self.packet["rubric_content_hash"])

    @property
    def relative_path(self) -> str:
        return "rounds/rubric_manifest.json"


def build_rubric_manifest(config: OrchestratorConfig) -> RubricManifest:
    """Build and validate the Phase 2 rubric manifest packet."""

    workflow = config.workflow.strip()
    convergence = config.convergence
    warnings: list[str] = []
    invalid: list[str] = []

    if workflow not in WORKFLOW_DEFAULTS:
        invalid.append(f"unsupported workflow {workflow!r}")
        workflow_defaults = WORKFLOW_DEFAULTS["standard"]
    else:
        workflow_defaults = WORKFLOW_DEFAULTS[workflow]

    rubric_source = convergence.rubric_source.strip()
    rubric_profile = convergence.rubric_profile.strip() or str(workflow_defaults["rubric_profile"])
    rubric_label = convergence.rubric_label.strip() if convergence.rubric_label else None

    if rubric_source not in {"builtin", "custom"}:
        invalid.append(f"unsupported rubric_source {rubric_source!r}")

    if rubric_source == "builtin":
        if rubric_profile not in BUILTIN_RUBRIC_FILES:
            invalid.append(f"unknown built-in rubric_profile {rubric_profile!r}")
            rubric_content = ""
            rubric_path = convergence.rubric_path
        else:
            builtin_path = RUBRICS_DIR / BUILTIN_RUBRIC_FILES[rubric_profile]
            rubric_content = builtin_path.read_text(encoding="utf-8")
            rubric_path = builtin_path
            if convergence.rubric_path.exists():
                configured_hash = rubric_content_hash(convergence.rubric_path.read_text(encoding="utf-8"))
                builtin_hash = rubric_content_hash(rubric_content)
                if configured_hash != builtin_hash:
                    invalid.append(
                        "configured rubric_path content does not match built-in "
                        f"rubric_profile {rubric_profile!r}"
                    )
        if rubric_label is not None:
            warnings.append("rubric_label is ignored for built-in rubric profiles")
    else:
        rubric_path = convergence.rubric_path
        if not rubric_label:
            invalid.append("custom rubric_source requires convergence.rubric_label")
        if not rubric_path.exists():
            invalid.append(f"custom rubric_path does not exist: {rubric_path}")
            rubric_content = ""
        else:
            rubric_content = rubric_path.read_text(encoding="utf-8")
        warnings.append("custom rubric identity is hash-based and may not be comparable to built-in profile results")

    if rubric_source == "builtin" and workflow != "custom" and rubric_profile != workflow_defaults["rubric_profile"]:
        warnings.append(
            f"workflow {workflow!r} default rubric is {workflow_defaults['rubric_profile']!r}, "
            f"but configured rubric_profile is {rubric_profile!r}"
        )

    if invalid:
        raise ValueError("; ".join(invalid))

    review_profile_budgets = resolved_phase_1_profile_budgets(config.review_profile_budgets)
    convergence_profile_budgets = resolved_phase_2_profile_budgets(config.convergence_profile_budgets)
    review_round_budget = sum(review_profile_budgets.values())
    convergence_round_budget = default_phase_2_scheduler(config.convergence_profile_budgets).total_round_budget()
    packet = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow": workflow,
        "rubric_profile": rubric_profile,
        "rubric_source": rubric_source,
        "rubric_label": rubric_label,
        "rubric_path": str(rubric_path),
        "rubric_content_hash": rubric_content_hash(rubric_content),
        "target_phase": convergence.target_phase,
        "target_mode": convergence.target_mode,
        "resolved_defaults": {
            "target_phase": str(workflow_defaults["target_phase"]),
            "target_mode": str(workflow_defaults["target_mode"]),
            "convergence_max_rounds": int(workflow_defaults["convergence_max_rounds"]),
            "required_artifacts": _required_artifacts_for_workflow(workflow),
        },
        "configured_budgets": {
            "review_max_rounds": config.review_max_rounds,
            "convergence_max_rounds": config.convergence.max_rounds,
            "review_profile_budgets": dict(sorted(review_profile_budgets.items())),
            "convergence_profile_budgets": dict(sorted(convergence_profile_budgets.items())),
            "review_round_budget": review_round_budget,
            "convergence_round_budget": convergence_round_budget,
            "total_absolute_round_budget": review_round_budget + convergence_round_budget,
            "effective_total_absolute_round_budget": review_round_budget + convergence_round_budget,
        },
        "warnings": warnings,
    }
    validate_artifact(packet, "rubric_manifest")
    return RubricManifest(path=config.rounds_dir / "rubric_manifest.json", packet=packet)


def write_rubric_manifest(config: OrchestratorConfig) -> RubricManifest:
    """Persist the resolved Phase 2 rubric manifest."""

    manifest = build_rubric_manifest(config)
    manifest.path.parent.mkdir(parents=True, exist_ok=True)
    from json import dumps

    manifest.path.write_text(dumps(manifest.packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def read_rubric_text(config: OrchestratorConfig) -> str | None:
    """Read the rubric text selected by config."""

    if config.convergence.rubric_source == "builtin":
        filename = BUILTIN_RUBRIC_FILES.get(config.convergence.rubric_profile)
        if filename is None:
            return None
        return (RUBRICS_DIR / filename).read_text(encoding="utf-8")
    if not config.convergence.rubric_path.exists():
        return None
    return config.convergence.rubric_path.read_text(encoding="utf-8")


def rubric_manifest_identity(manifest: RubricManifest | dict[str, Any]) -> dict[str, Any]:
    packet = manifest.packet if isinstance(manifest, RubricManifest) else manifest
    return {
        "workflow": packet["workflow"],
        "rubric_profile": packet["rubric_profile"],
        "rubric_source": packet["rubric_source"],
        "rubric_label": packet.get("rubric_label"),
        "rubric_content_hash": packet["rubric_content_hash"],
        "target_phase": packet["target_phase"],
        "target_mode": packet["target_mode"],
        "rubric_manifest_path": "rounds/rubric_manifest.json",
    }


def _required_artifacts_for_workflow(workflow: str) -> list[str]:
    common = ["spec.md", "spec.history.md", "run_state.json"]
    if workflow == "exploratory":
        return common + ["decision_register.json", "operator_decision_checkpoint_summary.json"]
    if workflow == "mvp":
        return common + ["decision_register.json", "decision_summary.json", "operator_decision_checkpoint_summary.json"]
    return common + [
        "convergence_declaration.md",
        "decision_register.json",
        "decision_summary.json",
        "operator_decision_checkpoint_summary.json",
    ]
