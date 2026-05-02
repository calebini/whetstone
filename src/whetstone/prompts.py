"""Prompt rendering for reviewer and editor clients."""

from __future__ import annotations


CONCERN_TYPES = {
    "clarity_gap": "section is ambiguous, undefined, or unclear",
    "completeness_gap": "section is missing required content, rule, definition, or edge case",
    "consistency_violation": "section contradicts another section or prior decision",
    "determinism_violation": "section permits non-deterministic behavior",
    "authority_violation": "section violates a defined role, boundary, or authority rule",
    "scope_violation": "section addresses something out of scope or omits something in scope",
    "redundancy": "section duplicates content elsewhere",
    "precision_gap": "section is correct but under-specified",
}

DIRECTIONS = {
    "add": "add missing content or behavior",
    "remove": "remove content or behavior",
    "modify": "change content when no more specific direction applies",
    "clarify": "clarify ambiguous content without materially changing scope or strictness",
    "constrain": "make behavior stricter, narrower, or more bounded",
    "relax": "make behavior looser, broader, or less restrictive",
}

SCOPES = {
    "local": "specific rule, sentence, definition, field, or invariant",
    "structural": "section organization, responsibility boundary, lifecycle shape, or cross-section architecture",
}


def render_reviewer_prompt(
    *,
    profile: str,
    draft: str,
    rubric: str | None = None,
    phase: str = "phase_1",
    section_ids: list[str] | None = None,
    round_number: int = 1,
    draft_hash_value: str | None = None,
) -> str:
    rubric_text = rubric or "(no rubric provided)"
    lines = [
        "You are the Whetstone reviewer.",
        f"Review profile: {profile}",
        f"Phase: {phase}",
        "",
        "Return only a single JSON object. Do not return markdown, explanation, or fenced code.",
        "The top-level object MUST match reviewer_feedback.json and include:",
        f"- round_number: {round_number}",
        f"- profile: {profile}",
        "- reviewer: object with concrete name, version, and model strings",
        f"- draft_hash: {draft_hash_value or 'the provided draft hash if supplied by the orchestrator'}",
        "- feedback: array of feedback items, or [] if no issues are found",
        "",
        "Each feedback item MUST represent exactly one issue and include all required schema fields.",
        "Whetstone computes issue_id, issue_fingerprint, and normalized_severity from the feedback semantic fields before persistence.",
        "The reviewer should return schema-shaped placeholder values for issue_id and issue_fingerprint if required by the client.",
        "issue_id placeholders SHOULD match iss_[16 lowercase hex characters], for example iss_0123456789abcdef.",
        "issue_fingerprint placeholders SHOULD be exactly 64 lowercase hex characters.",
        "draft_hash MUST exactly equal the draft_hash value supplied above.",
        "Severity fields MUST use only blocker, major, minor, nit, or null. Do not use high, medium, low, none, n/a, or similar aliases.",
        "Each feedback item MUST include exactly these base fields:",
        "- feedback_id",
        "- issue_id",
        "- issue_fingerprint",
        "- issue_type",
        "- affected_sections",
        "- baseline_severity",
        "- authority_impact",
        "- determinism_impact",
        "- rubric_impact",
        "- normalized_severity",
        "- invariant_violated",
        "- claim",
        "- evidence",
        "- recommended_change",
        "- in_scope",
        "- severity_rationale",
        "- oscillation_key",
    ]
    if phase == "phase_1":
        lines.append("For Phase 1, set oscillation_key to null.")
    if phase == "phase_2":
        lines.extend(["", _phase_2_classification_table(section_ids or [])])
    lines.extend(["", "Rubric:", rubric_text, "", "Draft:", draft])
    return "\n".join(lines)


def _phase_2_classification_table(section_ids: list[str]) -> str:
    lines = [
        "Phase 2 reviewer prompt requirements:",
        "- Phase 2 oscillation classification is mandatory for every feedback item.",
        "- The full canonical classification table appears below.",
        "- The reviewer MUST choose from the listed concern_type, direction, and scope enums.",
        "- The reviewer MUST NOT invent categories or leave oscillation_key fields blank.",
        "- section_id MUST be chosen from the canonical section IDs listed below.",
        "- The reviewer MUST NOT author fingerprint or opposition_key fields.",
        "- Use modify only when no more specific direction applies.",
        "",
        "Every feedback item MUST include oscillation_key with section_id, concern_type, direction, and scope only.",
        "Whetstone computes fingerprint and opposition_key after validating the section_id.",
        "Choose the nearest enum value.",
        "",
        "Canonical section IDs:",
    ]
    lines.extend(f"- {section_id}" for section_id in section_ids)
    lines.extend(
        [
            "",
            "Concern types:",
        ]
    )
    lines.extend(f"- {name}: {description}" for name, description in CONCERN_TYPES.items())
    lines.append("")
    lines.append("Directions:")
    lines.extend(f"- {name}: {description}" for name, description in DIRECTIONS.items())
    lines.append("")
    lines.append("Scope values:")
    lines.extend(f"- {name}: {description}" for name, description in SCOPES.items())
    lines.extend(
        [
            "",
            "Symmetric opposition pairs:",
            "- add/remove: add <-> remove",
            "- constrain <-> relax",
            "",
            "Examples:",
            '- {"section_id":"oscillation-detection-full-definition","concern_type":"determinism_violation","direction":"constrain","scope":"local"}',
            '- {"section_id":"artifact-schemas-minimum-required-fields","concern_type":"completeness_gap","direction":"add","scope":"local"}',
        ]
    )
    return "\n".join(lines)


def render_editor_prompt(
    *,
    draft: str,
    reviewer_feedback_json: str,
    round_number: int = 1,
    draft_before_hash_value: str | None = None,
    draft_after_hash_value: str | None = None,
    capture_only: bool = True,
) -> str:
    lines = [
        "You are the Whetstone editor.",
        "Apply or decline feedback according to the spec authority model.",
        "",
        "Return only a single JSON object matching editor_summary.json.",
        "Do not return markdown, explanation, fenced code, an editor object, or a decisions array.",
        f"The top-level object MUST set round_number to {round_number}.",
    ]
    if draft_before_hash_value:
        lines.append(f"The draft_before_hash MUST be {draft_before_hash_value}.")
    if draft_after_hash_value:
        lines.append(f"The draft_after_hash MUST be {draft_after_hash_value}.")
    if capture_only:
        lines.append("This live round is capture-only; do not assume the repository draft is mutated by this prompt.")
        lines.append("In capture-only mode, feedback may be accepted in substance while its issue remains unresolved because no draft text changed.")
        lines.append("Set draft_after_content to null.")
    else:
        lines.append("This live round may mutate the draft after validation.")
        lines.append("If you change the draft, include draft_after_content as the complete revised draft text.")
        lines.append("If you make no draft changes, set draft_after_content to the original draft text.")
        lines.append("Whetstone computes draft_after_hash from draft_after_content; set draft_after_hash to null if no explicit hash was provided above.")
    lines.extend(
        [
            "The top-level object MUST include exactly these fields:",
            "- round_number",
            "- draft_before_hash",
            "- draft_after_hash",
            "- accepted_feedback_ids",
            "- modified_feedback_ids",
            "- declined_feedback",
            "- created_conflict_ids",
            "- resolved_issue_ids",
            "- unresolved_issue_ids",
            "- draft_after_content",
            "",
            "Use accepted_feedback_ids for feedback accepted as written.",
            "Use modified_feedback_ids for feedback accepted in substance but implemented differently.",
            "Use declined_feedback only for feedback declined under the allowed decline taxonomy.",
            "Use resolved_issue_ids only when the current draft_after resolves the issue.",
            "Use unresolved_issue_ids for issues still unresolved in the current draft_after.",
            "If there are no entries for an array field, return an empty array for that field.",
        ]
    )
    lines.extend(
        [
            "",
            "Reviewer feedback JSON:",
            reviewer_feedback_json,
            "",
            "Draft:",
            draft,
        ]
    )
    return "\n".join(lines)
