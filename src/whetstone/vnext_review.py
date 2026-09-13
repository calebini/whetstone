"""Reviewer-only vNext execution against an immutable initialized seed.

No Editor or Semantic Verifier factory is reachable from this module. Candidate
processing and technical resume are separate, currently unavailable capabilities.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

from whetstone.clients import canonicalize_reviewer_input
from whetstone.config import ClientConfig
from whetstone.contracts import validate_artifact
from whetstone.live import _validate_reviewer_feedback, create_reviewer_client
from whetstone.prompts import render_reviewer_prompt
from whetstone.vnext_admission import (
    ADMISSION_PATH, Admission, AdmissionError, check, local_ref, preflight,
    read_ref, stamp, validate_initialized, runtime_contract,
)
from whetstone.vnext_contracts import canonical_json_bytes, content_identifier, confined_file, decode_json
from whetstone.vnext_storage import make_directory, publish, writer

STATE_PATH = "rounds/vnext_run_state.json"
REPORT_PATH = "rounds/vnext_terminal_report.json"


def _client(ticket: Admission, timeout_seconds=None):
    pinned = ticket.review["reviewer"]
    transport = ticket.config.get("clients", {}).get("reviewer", {})
    command = transport.get("command", {"codex": "codex", "claude-code": "claude"}.get(pinned["name"]))
    check(pinned["name"] in {"codex", "claude-code"} and bool(command),
          "vnext_config_invalid", "reviewer transport must be configured for the pinned client identity")
    timeout = timeout_seconds or ticket.config.get("timeouts", {}).get("reviewer_seconds", 360)
    check(type(timeout) is int and timeout > 0, "vnext_config_invalid", "reviewer timeout must be a positive integer")
    return create_reviewer_client(ClientConfig(**pinned, command=command), cwd=ticket.root,
                                  phase="phase_1", section_ids=[s["canonical_section_id"] for s in ticket.section_map["sections"]],
                                  timeout_seconds=timeout)


def _refresh(ticket):
    return preflight(ticket.root, ticket.config,
                     descriptor_path=ticket.selection["job_descriptor"]["path"],
                     review_path=ticket.selection["review_configuration"]["path"],
                     gate="review", existing=True)


def _context(ticket, directory):
    root = ticket.root
    draft = publish(root, directory + "/context/draft.md", ticket.seed)
    references = []
    # Every non-excluded binding remains visible as context under its declared
    # role. Visibility is independent of mutation authority.
    for index, binding in enumerate(ticket.authority["bindings"]):
        if binding["role"] in {"excluded", "mutable_target"}:
            continue
        raw = ticket.reader.raw({"path": binding["path"], "hash": binding["content_hash"]})
        ref = publish(root, directory + f"/context/binding-{index}.md", raw)
        references.append({"label": binding["binding_id"], "role": binding["role"], "path": str(root / ref["path"])})
    for name, packet in (("authority", ticket.authority), ("invariants", ticket.invariants)):
        ref = publish(root, directory + f"/context/{name}.json", packet)
        references.append({"label": name, "role": "orchestrator_contract", "path": str(root / ref["path"])})
    scope_path = None
    if ticket.job["scope_contract_path"] is not None:
        raw = ticket.reader.raw({"path": ticket.job["scope_contract_path"], "hash": ticket.job["scope_contract_hash"]})
        ref = publish(root, directory + "/context/scope.json", raw)
        scope_path = str(root / ref["path"])
    return str(root / draft["path"]), references, scope_path


def _pending_choices(ticket, feedback, reference):
    """Detect explicit choices during read-only work; this grants no editability.

    Full mutation classification/admission is implemented in slice 18.4. A
    non-matching finding remains unresolved review evidence, never editable work.
    """
    result = []
    for item in feedback["feedback"]:
        if not item["in_scope"]:
            continue
        text = item["claim"] + " " + item["recommended_change"]
        if not re.search(r"\b(choose|decide|whether|operator decision|weaken|supersede|remove normative|delete normative)\b", text, re.I):
            continue
        request = {"schema_version": "vnext-review-decision-request-v1", "job_id": ticket.job["job_id"],
                   "base_draft_hash": ticket.job["seed_draft"]["hash"], "authority_map_hash": ticket.job["authority_map_hash"],
                   "scope_contract_hash": ticket.job["scope_contract_hash"], "feedback": reference,
                   "finding_id": item["issue_id"], "source_feedback_id": item["feedback_id"],
                   "question": item["claim"], "proposed_change": item["recommended_change"],
                   "options": ["defer", "new_authorized_transaction"], "status": "pending"}
        request["decision_id"] = content_identifier("decision", "whetstone-review-decision-v1", [request])
        runtime_contract(request, "vnext_review_decision_request_v1")
        result.append(request)
    return result


def _round(ticket, client, number, profile):
    directory = f"rounds/round-{number}"
    check(not (ticket.root / directory).exists(), "vnext_lineage_invalid",
          "review evidence already exists without a completed run; inspect before new admission",
          terminal="HALTED_ARTIFACT_INVALID", action="inspect_evidence")
    make_directory(ticket.root, directory)
    draft_path, references, scope_path = _context(ticket, directory)
    prompt = render_reviewer_prompt(profile=profile, draft=ticket.seed.decode(), draft_path=draft_path,
                                    reference_context_paths=references, scope_contract_path=scope_path,
                                    section_ids=[s["canonical_section_id"] for s in ticket.section_map["sections"]],
                                    round_number=number, draft_hash_value=ticket.job["seed_draft"]["hash"])
    prompt += "\nThe authority map controls each document's role; reference-only and historical context cannot introduce requirements.\n"
    prompt += "This is reviewer-only. Findings are evidence, not edit instructions or candidate verification.\n"
    errors = []
    for attempt in (1, 2):
        _refresh(ticket)
        attempt_dir = directory + f"/reviewer-attempt-{attempt}"
        current = prompt + ("\nShape validation errors from the preceding attempt:\n" + "\n".join(errors) if errors else "")
        publish(ticket.root, attempt_dir + "/prompt.txt", current.encode())
        publish(ticket.root, attempt_dir + "/invocation.json",
                {"job_id": ticket.job["job_id"], "round_number": number, "profile": profile,
                 "attempt": attempt, "base_hash": ticket.job["seed_draft"]["hash"], "started_at": stamp()})
        try:
            packet = client.review(current)
        except TimeoutError:
            raise
        except ValueError as exc:
            errors.append(str(exc))
            publish(ticket.root, attempt_dir + "/validation_error.txt", str(exc).encode())
            continue
        finally:
            telemetry = getattr(client, "last_telemetry", None)
            if telemetry is not None:
                publish(ticket.root, attempt_dir + "/telemetry.json",
                        json.dumps(telemetry, sort_keys=True).encode())
        publish(ticket.root, attempt_dir + "/response.json", json.dumps(packet, sort_keys=True).encode())
        _refresh(ticket)
        try:
            packet = canonicalize_reviewer_input(deepcopy(packet))
            _validate_reviewer_feedback(packet, round_number=number, profile=profile,
                                       draft_hash_value=ticket.job["seed_draft"]["hash"], schema_name="reviewer_feedback")
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
            publish(ticket.root, attempt_dir + "/validation_error.txt", str(exc).encode())
            continue
        # Pin the configured role identity; client self-description is retained
        # in the raw response but cannot replace this frozen job input.
        packet["reviewer"] = ticket.review["reviewer"]
        ref = publish(ticket.root, directory + "/reviewer_feedback.json", packet)
        serious = [item for item in packet["feedback"] if item["in_scope"] and item["normalized_severity"] in {"blocker", "major"}]
        choices = _pending_choices(ticket, packet, ref)
        decision_refs = [publish(ticket.root, directory + f"/decisions/{item['decision_id']}.json", item) for item in choices]
        receipt = {"job_id": ticket.job["job_id"], "round_number": number, "profile": profile,
                   "base_hash": ticket.job["seed_draft"]["hash"], "feedback": ref,
                   "serious_issue_ids": sorted({item["issue_id"] for item in serious}),
                   "decisions": decision_refs, "clean": not serious, "attempt_count": attempt}
        runtime_contract(receipt, "vnext_review_receipt_v1")
        return publish(ticket.root, directory + "/review_receipt.json", receipt), receipt
    raise AdmissionError("vnext_reviewer_invalid", "; ".join(errors), terminal="HALTED_ARTIFACT_INVALID", action="inspect_evidence")


def _terminal(ticket, terminal, decision_ids, reason):
    packet = {"schema_version": "terminal-report-v2", "terminal_state": terminal,
              "current_verified_draft_path": ticket.seed_reference["path"],
              "current_verified_draft_hash": ticket.job["seed_draft"]["hash"],
              "latest_candidate": {}, "rejected_candidate_ids": [], "outstanding_decision_ids": sorted(decision_ids),
              "apply_back_permitted": False, "resume": {"permitted": False, "next_gate": None, "reason": reason}}
    schema = ticket.suite.registry.load("terminal_report_v2")
    for key in schema["properties"]["latest_candidate"]["required"]:
        packet["latest_candidate"][key] = None
    ticket.suite.registry.validate(packet, "terminal_report_v2")
    return packet


def read_state(ticket):
    validate_initialized(ticket)
    path = ticket.root / STATE_PATH
    if not path.exists():
        check(not any((ticket.root / "rounds").glob("round-*")), "vnext_lineage_invalid",
              "review artifacts are incomplete; technical continuation is unavailable",
              terminal="HALTED_ARTIFACT_INVALID", action="inspect_evidence")
        return None
    state_raw = confined_file(ticket.root, STATE_PATH).read_bytes()
    state = decode_json(state_raw)
    check(state_raw == canonical_json_bytes(state), "vnext_lineage_invalid", "run state is not canonical JSON")
    runtime_contract(state, "vnext_review_run_v1")
    check(set(state) == {"schema_version", "job_id", "admission", "receipts", "terminal_report", "completed_at"}
          and state["schema_version"] == "vnext-review-run-v1" and state["job_id"] == ticket.job["job_id"],
          "vnext_lineage_invalid", "invalid vNext review run state", terminal="HALTED_ARTIFACT_INVALID")
    check(state["admission"] == local_ref(ticket.root, ADMISSION_PATH), "vnext_lineage_invalid", "admission receipt changed")
    seen = []
    counts = {item["name"]: 0 for item in ticket.review["profiles"]}
    latest = {name: None for name in counts}
    decisions = []
    for number, reference in enumerate(state["receipts"], 1):
        receipt = read_ref(ticket.root, reference)
        runtime_contract(receipt, "vnext_review_receipt_v1")
        check(reference["path"] == f"rounds/round-{number}/review_receipt.json"
              and receipt["round_number"] == number and receipt["job_id"] == ticket.job["job_id"]
              and receipt["base_hash"] == ticket.job["seed_draft"]["hash"],
              "vnext_lineage_invalid", "review receipt sequence or base mismatch")
        feedback = read_ref(ticket.root, receipt["feedback"])
        _validate_reviewer_feedback(feedback, round_number=number, profile=receipt["profile"],
                                   draft_hash_value=receipt["base_hash"], schema_name="reviewer_feedback")
        check(feedback["reviewer"] == ticket.review["reviewer"], "vnext_lineage_invalid", "reviewer identity mismatch")
        serious = sorted({item["issue_id"] for item in feedback["feedback"]
                          if item["in_scope"] and item["normalized_severity"] in {"blocker", "major"}})
        check(receipt["serious_issue_ids"] == serious and receipt["clean"] == (not serious),
              "vnext_lineage_invalid", "review receipt misstates finding cleanliness")
        check(receipt["profile"] in counts, "vnext_lineage_invalid", "review receipt names an unconfigured profile")
        counts[receipt["profile"]] += 1
        latest[receipt["profile"]] = not serious
        expected_requests = _pending_choices(ticket, feedback, receipt["feedback"])
        check(len(receipt["decisions"]) == len(expected_requests), "vnext_lineage_invalid", "missing or invented decision request")
        for ref, expected in zip(receipt["decisions"], expected_requests):
            request = read_ref(ticket.root, ref)
            runtime_contract(request, "vnext_review_decision_request_v1")
            check(request == expected,
                  "vnext_lineage_invalid", "decision request is not bound to review")
            decisions.append(request["decision_id"])
        seen.append(receipt)
    check(all(counts[item["name"]] <= item["budget"] for item in ticket.review["profiles"]),
          "vnext_lineage_invalid", "review exceeded its pinned profile budget")
    report = read_ref(ticket.root, state["terminal_report"])
    ticket.suite.registry.validate(report, "terminal_report_v2")
    check(report["current_verified_draft_hash"] == ticket.job["seed_draft"]["hash"]
          and report["current_verified_draft_path"] == ticket.seed_reference["path"]
          and all(v is None for v in report["latest_candidate"].values()) and not report["apply_back_permitted"],
          "vnext_lineage_invalid", "reviewer-only terminal report claims different authority")
    check(report["terminal_state"] in {"PHASE_1_STABLE", "TARGET_NOT_REACHED", "PAUSED_DECISION",
                                        "HALTED_ARTIFACT_INVALID", "HALTED_CLIENT_TIMEOUT"}
          and report["outstanding_decision_ids"] == sorted(decisions)
          and not report["resume"]["permitted"], "vnext_lineage_invalid", "unsupported completion or decision claim")
    if report["terminal_state"] == "PHASE_1_STABLE":
        check(all(value is True for value in latest.values()) and not decisions,
              "vnext_lineage_invalid", "phase completion lacks clean evidence for every pinned profile")
    if report["terminal_state"] == "PAUSED_DECISION":
        check(bool(decisions), "vnext_lineage_invalid", "operator pause has no bound decision")
    return state, report, seen


def run_review(ticket: Admission, *, reviewer_client=None, timeout_seconds=None):
    """One bounded phase-1 review invocation; repeat reads its committed result."""
    with writer(ticket.root):
        ticket = _refresh(ticket)
        previous = read_state(ticket)
        if previous is not None:
            return previous[1]
        check(not any((ticket.root / "rounds").glob("round-*")), "vnext_lineage_invalid",
              "incomplete review artifacts require inspection; generic resume is unavailable",
              terminal="HALTED_ARTIFACT_INVALID", action="inspect_evidence")
        client = reviewer_client or _client(ticket, timeout_seconds)
        receipts, decisions = [], []
        profiles = ticket.review["profiles"]
        counts = {item["name"]: 0 for item in profiles}
        clean = {item["name"]: False for item in profiles}
        terminal = "TARGET_NOT_REACHED"
        reason = "Review budget exhausted with unresolved findings; editing is unavailable in reviewer-only mode."
        try:
            while True:
                for item in profiles:
                    profile = item["name"]
                    if clean[profile] or counts[profile] >= item["budget"]:
                        continue
                    while counts[profile] < item["budget"] and not clean[profile]:
                        reference, receipt = _round(ticket, client, len(receipts) + 1, profile)
                        receipts.append(reference)
                        counts[profile] += 1
                        clean[profile] = receipt["clean"]
                        decisions.extend(read_ref(ticket.root, ref)["decision_id"] for ref in receipt["decisions"])
                        if decisions:
                            terminal, reason = "PAUSED_DECISION", "Resolve the bound choice through a new authorized admission."
                            break
                        if ticket.review["review_mode"] == "vertical":
                            break
                    if decisions or (not clean[profile] and counts[profile] == item["budget"]):
                        break
                if decisions:
                    break
                if all(clean.values()):
                    terminal, reason = "PHASE_1_STABLE", "Reviewer-only phase complete; Phase 2 and source apply-back are unavailable."
                    break
                if any(not clean[item["name"]] and counts[item["name"]] >= item["budget"] for item in profiles):
                    break
        except TimeoutError as exc:
            terminal, reason = "HALTED_CLIENT_TIMEOUT", str(exc) or "Reviewer timeout; no automatic retry."
        except (ValueError, OSError, RuntimeError) as exc:
            terminal, reason = "HALTED_ARTIFACT_INVALID", str(exc)
        # Never emit a valid-looking current-pointer report after lineage loss.
        _refresh(ticket)
        report = _terminal(ticket, terminal, decisions, reason)
        report_ref = publish(ticket.root, REPORT_PATH, report)
        state = {"schema_version": "vnext-review-run-v1", "job_id": ticket.job["job_id"],
                 "admission": local_ref(ticket.root, ADMISSION_PATH), "receipts": receipts,
                 "terminal_report": report_ref, "completed_at": stamp()}
        runtime_contract(state, "vnext_review_run_v1")
        publish(ticket.root, STATE_PATH, state)
        return report
