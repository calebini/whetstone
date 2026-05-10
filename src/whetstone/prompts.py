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
    declaration: str | None = None,
    draft_path: str | None = None,
    rubric_path: str | None = None,
    declaration_path: str | None = None,
    scope_contract_path: str | None = None,
    reference_context_paths: list[dict[str, str]] | None = None,
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
        lines.extend(
            [
                "",
                _phase_2_declaration_context(declaration, declaration_path=declaration_path),
                "",
                _phase_2_classification_table(section_ids or []),
            ]
        )
    reference_context_paths = reference_context_paths or []
    if draft_path or rubric_path or scope_contract_path or reference_context_paths:
        lines.extend(
            [
                "",
                "Context files:",
                "- Read the files listed in this section before producing the JSON response.",
                "- Do not read any unlisted file.",
                "- When needed, use read-only client-native file access or read-only shell commands only for the listed context file paths.",
                "- Do not inspect unrelated repository files, use web search, or call tools for anything except reading listed context files.",
            ]
        )
        if draft_path:
            lines.append(f"- Draft path: {draft_path}")
        if rubric_path:
            lines.append(f"- Rubric path: {rubric_path}")
        elif rubric is None:
            lines.append("- Rubric: (no rubric provided)")
        if declaration_path:
            lines.append(f"- Declaration artifact path: {declaration_path}")
        if scope_contract_path:
            lines.append(f"- Scope contract path: {scope_contract_path}")
        for item in reference_context_paths:
            lines.append(
                f"- Reference context [{item['label']}] ({item['role']}): {item['path']}"
            )
        lines.append("Use the listed context files as authoritative input content.")
    else:
        lines.extend(["", "Rubric:", rubric_text, "", "Draft:", draft])
    if scope_contract_path:
        lines.extend(
            [
                "",
                "Scope contract rules:",
                "- The scope contract is authoritative for this run.",
                "- Feedback outside the scope contract MUST set in_scope=false and cite the relevant surface or deferral rule in evidence or recommended_change.",
                "- Out-of-scope or deferred feedback MUST NOT become blocker/major pressure unless it is required to satisfy an in-scope core flow.",
                "- If a concern appears important but exceeds scope, recommend a scope-promotion decision instead of expanding the current spec.",
            ]
        )
    return "\n".join(lines)


def _phase_2_declaration_context(declaration: str | None, *, declaration_path: str | None = None) -> str:
    lines = [
        "Phase 2 declaration artifact rules:",
        "- `Draft` below is spec.md source content only.",
        "- `convergence_declaration.md` is a separate Orchestrator-owned artifact, not a section that must be added to spec.md.",
        "- Do not report the absence of a convergence declaration section inside spec.md as a source-spec issue.",
        "- Do not recommend adding convergence declaration text to spec.md.",
        "- If a declaration artifact is supplied below, evaluate declaration-specific issues against that artifact.",
        "- If no declaration artifact is supplied, assume declaration review is not active for this round.",
        "- A provisional declaration with reviewer_final_status `not_run` and declaration_status `rejected` is an Orchestrator staging artifact, not a source-spec defect.",
        "- During convergence_strict_check declaration verification, do not report reviewer_final_status `not_run` or declaration_status `rejected` as defects by themselves.",
        "- The Orchestrator will change reviewer_final_status and declaration_status to accepted only after this review returns no in-scope declaration or target-matrix blockers/majors.",
        "- Verify declaration hash, rubric hash, issue counts, rubric gap counts, target-matrix alignment, and source-spec readiness; exclude staging status fields from findings.",
    ]
    if declaration_path is not None:
        lines.extend(["", "Declaration artifact:", f"(read from {declaration_path})"])
    elif declaration is None:
        lines.extend(["", "Declaration artifact:", "(not provided for this review)"])
    else:
        lines.extend(["", "Declaration artifact:", declaration])
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
    draft_path: str | None = None,
    reviewer_feedback_path: str | None = None,
    scope_contract_path: str | None = None,
    reference_context_paths: list[dict[str, str]] | None = None,
    phase: str = "phase_1",
    round_number: int = 1,
    draft_before_hash_value: str | None = None,
    draft_after_hash_value: str | None = None,
    capture_only: bool = True,
    synthesis_report_path: str | None = None,
) -> str:
    lines = [
        "You are the Whetstone editor.",
        "Apply or decline feedback according to the spec authority model.",
        "Use only the Draft and Reviewer feedback JSON provided in this prompt or in the listed context files.",
        "If context files are listed, you MUST read those files and may inspect only those files.",
        "When needed, use read-only client-native file access or read-only shell commands only for the listed context file paths.",
        "Do not inspect unrelated repository files, use web search, or call tools for anything except reading listed context files.",
        "Do not rely on external documents, ambient workspace context, or prior run artifacts.",
        "",
        "Return only a single JSON object matching editor_summary.json.",
        "Do not return markdown, explanation, fenced code, an editor object, or a decisions array.",
        f"The top-level object MUST set round_number to {round_number}.",
    ]
    if draft_before_hash_value:
        lines.append(f"The draft_before_hash MUST be {draft_before_hash_value}.")
    if draft_after_hash_value:
        lines.append(f"The draft_after_hash MUST be {draft_after_hash_value}.")
    if phase == "phase_2":
        lines.append("Phase 2 declaration artifact rule: `convergence_declaration.md` is Orchestrator-owned and separate from spec.md.")
        lines.append("Do not add convergence declaration text or acceptance statements to spec.md.")
        lines.append("If feedback asks for a convergence declaration inside spec.md, decline it as out_of_scope unless the Orchestrator explicitly supplied that text in the editable draft.")
    if scope_contract_path:
        lines.extend(
            [
                "",
                "Scope contract rules:",
                "- The scope contract is authoritative for this run.",
                "- Do not implement feedback that exceeds the approved scope contract.",
                "- Decline out-of-scope feedback with decline_reason out_of_scope.",
                "- Decline deferred feedback with deferred_to_later_round when the scope contract defers it to a later phase or profile.",
                "- Preserve operator intent; do not silently promote deferred surfaces into scope.",
            ]
        )
    if synthesis_report_path:
        lines.extend(
            [
                "",
                "Timeout-aware bounded synthesis guidance:",
                "- The previous Editor attempt timed out or this profile shows EXPANDING_CONTRACT_SURFACE.",
                "- Read the contract surface report listed in context files.",
                "- Prefer a bounded synthesis over the report's listed sections and contract families instead of broad unrelated rewriting.",
                "- Preserve global coherence and still return draft_after_content as the complete revised draft text.",
                "- Do not omit unrelated sections from draft_after_content.",
            ]
        )
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
    reference_context_paths = reference_context_paths or []
    if draft_path or reviewer_feedback_path or scope_contract_path or reference_context_paths:
        lines.extend(
            [
                "",
                "Context files:",
                "- Read the files listed in this section before producing the JSON response.",
                "- Do not read any unlisted file.",
            ]
        )
        if reviewer_feedback_path:
            lines.append(f"- Reviewer feedback JSON path: {reviewer_feedback_path}")
        if draft_path:
            lines.append(f"- Draft path: {draft_path}")
        if synthesis_report_path:
            lines.append(f"- Contract surface report path: {synthesis_report_path}")
        if scope_contract_path:
            lines.append(f"- Scope contract path: {scope_contract_path}")
        for item in reference_context_paths:
            lines.append(
                f"- Reference context [{item['label']}] ({item['role']}): {item['path']}"
            )
        lines.append("Use the listed context files as authoritative input content.")
    else:
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
