"""Validation and prospective issue eligibility from retained round evidence."""
from __future__ import annotations

from typing import Any

from whetstone.contracts import validate_artifact
from whetstone.hashing import draft_hash
from whetstone.preservation_contracts import require


def validate_round_evidence(base: bytes, raw: bytes, admission: dict[str, Any],
                            feedback: list[dict[str, Any]], summary: dict[str, Any] | None) -> bool:
    """Return prospective stamp eligibility, never an acceptance decision.

    Unknown IDs and omitted serious findings cannot create eligibility. Existing
    residual/state gates remain the responsibility of the acceptance service.
    """
    if admission["origin"] == "phase2_entry":
        require(not feedback and summary is None, "Phase 2 entry cannot fabricate round evidence")
        # Handoff eligibility requires the later accepted-chain service.
        return True
    require(summary is not None, "round proposal requires a summary")
    validate_artifact(summary, "editor_summary")
    require(summary["round_number"] == admission["round_number"], "summary round mismatch")
    require(summary["draft_before_hash"] == draft_hash(base.decode()), "summary base mismatch")
    require(summary["draft_after_hash"] == draft_hash(raw.decode()), "summary raw output mismatch")
    if "draft_after_content" in summary:
        require(summary["draft_after_content"].encode() == raw, "summary content differs from raw proposal")
    issues, feedback_ids = {}, set()
    for artifact in feedback:
        validate_artifact(artifact, "reviewer_feedback")
        require(artifact["round_number"] == admission["round_number"], "feedback round mismatch")
        require(artifact["draft_hash"] == draft_hash(base.decode()), "retained feedback base mismatch")
        for finding in artifact["feedback"]:
            feedback_ids.add(finding["feedback_id"])
            issues.setdefault(finding["issue_id"], []).append(finding)
    resolved = set(summary["resolved_issue_ids"])
    unresolved = set(summary["unresolved_issue_ids"])
    require(not resolved.intersection(unresolved), "summary resolves and retains the same issue")
    require(resolved | unresolved <= issues.keys() | set(summary["created_conflict_ids"]), "summary names an unknown issue")
    named = set(summary["accepted_feedback_ids"] + summary["modified_feedback_ids"])
    named.update(item["feedback_id"] for item in summary["declined_feedback"])
    require(named <= feedback_ids, "summary names unknown feedback")
    if raw == base:
        # A claimed resolution alone never clears serious findings on a no-op.
        resolved = set()
    return not summary["created_conflict_ids"] and not any(uid not in resolved and f["in_scope"] and f["normalized_severity"] in {"major", "blocker"}
                   for uid, findings in issues.items() for f in findings)
