"""CLI protocol dispatch before any legacy writer/client path is selected."""
import json
from pathlib import Path
import re

from whetstone.vnext_admission import (
    ADMISSION_PATH, AdmissionError, config_packet, diagnostic, initialize,
    preflight, root_declares_vnext,
)
from whetstone.vnext_review import _client, read_state, run_review


def dispatch(args):
    """Return None for legacy dispatch, otherwise the handled exit status."""
    from whetstone.vnext_proposal_cli import dispatch_proposal
    handled=dispatch_proposal(args)
    if handled is not None:return handled
    root = Path(getattr(args, "run_root", None) or getattr(args, "root", "."))
    path = root / getattr(args, "config", "orchestrator_config.yaml")
    selected = bool(getattr(args, "vnext_job_descriptor", None)
                    or getattr(args, "vnext_review_configuration", None))
    declared = root_declares_vnext(root)
    command = args.command
    ticket = None
    gate = "review" if command == "live-phase1" else "admission"
    try:
        # Do not change parsing semantics for unrelated legacy invocations.
        text = path.read_text() if path.is_file() else ""
        config_selected = bool(re.search(r'(?m)^\s*vnext\s*:|"vnext"\s*:', text))
        if not (selected or declared or config_selected or command == "vnext-admit"):
            return None
        config = config_packet(path)
        if command not in {"vnext-admit", "live-phase1", "status"}:
            raise AdmissionError("vnext_gate_unavailable", f"{command} is unavailable for this vNext release",
                                 action="inspect_available_work")
        if getattr(args, "overwrite", False) or getattr(args, "apply", False) or getattr(args, "draft_after", None):
            raise AdmissionError("vnext_selection_conflict", "legacy overwrite/apply/revision controls cannot select vNext editing")
        for name in ("timeout_seconds", "reviewer_timeout_seconds", "editor_timeout_seconds"):
            value = getattr(args, name, None)
            if value is not None and (type(value) is not int or value <= 0):
                raise AdmissionError("vnext_config_invalid", "timeouts must be positive integers")
        existing = (root / ADMISSION_PATH).is_file()
        ticket = preflight(root, config, descriptor_path=getattr(args, "vnext_job_descriptor", None),
                           review_path=getattr(args, "vnext_review_configuration", None), gate=gate,
                           existing=existing and command != "vnext-admit")
        if command == "status":
            packet = ticket.diagnostic(admitted=existing)
            if existing:
                state = read_state(ticket)
                packet["terminal_report"] = state[1] if state else None
                if state:
                    packet["terminal_state"] = state[1]["terminal_state"]
                    packet["vnext"]["requested_gate"] = "complete"
                    packet["vnext"]["next_action"] = (
                        "none" if packet["terminal_state"] == "PHASE_1_STABLE" else "inspect_evidence")
                    packet["vnext"]["reason"] = state[1]["resume"]["reason"]
            if args.format == "text":
                capability = packet["vnext"]
                report = packet.get("terminal_report") or {}
                print("Protocol: vnext")
                print("Mode: " + capability["requested_mode"])
                print("State: " + (packet["terminal_state"] or ("ADMITTED" if existing else "NOT_ADMITTED")))
                print("Next action: " + capability["next_action"])
                print(capability["reason"])
                if report:
                    print("Verified draft: " + report["current_verified_draft_path"])
            else:
                print(json.dumps(packet))
            return 0
        if command == "vnext-admit":
            if not args.dry_run:
                initialize(ticket)
            print(json.dumps(ticket.diagnostic(admitted=not args.dry_run)))
            return 0
        client = _client(ticket, getattr(args, "reviewer_timeout_seconds", None)
                         or getattr(args, "timeout_seconds", None))
        if not existing:
            initialize(ticket)
        result = run_review(ticket, reviewer_client=client)
        print(json.dumps({**ticket.diagnostic(gate="review", admitted=True), "terminal_report": result}))
        return 0 if result["terminal_state"] == "PHASE_1_STABLE" else 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        error = exc if isinstance(exc, AdmissionError) else AdmissionError(
            "vnext_lineage_invalid" if declared else "vnext_config_invalid", str(exc),
            terminal="HALTED_ARTIFACT_INVALID" if declared else "CONFIG_INVALID",
            action="inspect_evidence" if declared else "repair_configuration")
        print(json.dumps(ticket.diagnostic(gate=gate, error=error) if ticket else diagnostic(
            getattr(error, "job", None), getattr(error, "suite", None), gate=gate, error=error)))
        return 2
