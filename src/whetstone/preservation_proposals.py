"""Immutable proposal attempts for the bridge's pre-acceptance stage.

This library has no installation, acceptance, scheduler or model-client adapter.
A ticket is single-use; interrupted attempts consume their number. Recovery and
maintenance inheritance belong to the subsequent acceptance/runtime increment.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable

from whetstone.contracts import validate_artifact
from whetstone.hashing import canonical_json_dumps, draft_hash
from whetstone.preservation_assessment import assess_proposal
from whetstone.preservation_contracts import (
    BridgeContractError, decode_json, read_artifact, read_ref, require,
    validate_proposal_bindings, validate_reference_graph, validate_surface_bindings,
)
from whetstone.preservation_inventory import build_inventory, sha256_bytes
from whetstone.preservation_materialization import MaterializationError, comparison_inventory, materialize_proposal
from whetstone.preservation_round_evidence import validate_round_evidence
from whetstone.text_validation import validate_generated_text


def json_bytes(value: Any) -> bytes:
    return (canonical_json_dumps(value) + "\n").encode("utf-8")


@dataclass(frozen=True)
class ProposalTicket:
    root: str
    directory: str
    admission_json: bytes
    config_ref_json: bytes
    feedback_refs_json: bytes
    snapshots_json: bytes
    current_draft: str

    @property
    def admission_ref(self) -> dict[str, str]:
        return {"path": f"{self.directory}/admission.json", "sha256": sha256_bytes(self.admission_json)}


@dataclass(frozen=True)
class ProposalInputs:
    """Exact frozen inputs passed to an externally supplied Editor adapter."""
    base: bytes
    admission_json: bytes
    effective_config_json: bytes
    reviewer_feedback_json: tuple[bytes, ...]


class ProposalClientFailure(RuntimeError):
    """An unclassified adapter failure; never eligible for an automatic retry."""


class ProposalStore:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)

    def _path(self, relative: str) -> Path:
        path = Path(relative)
        require(not path.is_absolute() and ".." not in path.parts, "storage path must be confined and relative")
        target = self.root / path
        require(target.resolve().is_relative_to(self.root), "storage path escapes root")
        # Reject symlink aliases, including in-root ones, on write paths.
        current = self.root
        for part in path.parts:
            current /= part
            require(not current.is_symlink(), "storage path contains a symlink")
        return target

    @contextmanager
    def _lock(self):
        path = self._path(".preservation.lock")
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def _sync_directory(self, path: Path) -> None:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _mkdir(self, relative: str) -> Path:
        target = self._path(relative)
        if not target.exists():
            if target.parent != self.root:
                self._mkdir(str(target.parent.relative_to(self.root)))
            target.mkdir()
            self._sync_directory(target.parent)
        require(target.is_dir(), "storage parent is not a directory")
        return target

    def _write(self, relative: str, raw: bytes) -> dict[str, str]:
        """Create-if-absent via durable same-directory link; never truncate a file."""
        target = self._path(relative)
        self._mkdir(str(target.parent.relative_to(self.root)))
        fd, temporary = tempfile.mkstemp(prefix=".bridge-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                require(target.read_bytes() == raw, "immutable artifact already exists with different bytes")
            self._sync_directory(target.parent)
        finally:
            os.unlink(temporary)
        return {"path": relative, "sha256": sha256_bytes(raw)}

    def _artifact(self, relative: str, value: dict[str, Any], schema: str) -> dict[str, str]:
        validate_artifact(value, schema)
        return self._write(relative, json_bytes(value))

    def admit(self, *, surface_ref: dict[str, str], effective_config: dict[str, Any],
              reviewer_feedback_refs: list[dict[str, str]], round_number: int,
              profile: str, phase: str = "phase_1", origin: str = "editor",
              client_attempt_number: int | None = 1, predecessor_report: dict[str, str] | None = None,
              current_draft: str = "spec.md") -> ProposalTicket:
        """Validate and persist inputs before any callback. No effect evidence needed."""
        with self._lock():
            from whetstone.preservation_runtime import active, guard_admission
            if active(self.root):
                guard_admission(self.root, round_number=round_number, phase=phase, predecessor_report=predecessor_report)
            require(origin != "phase2_entry", "Phase 2 entry admission requires the later accepted-chain service")
            if any(self.root.glob("rounds/round-*/preservation/attempt-*/acceptance-attempt-*/acceptance.json")):
                from whetstone.preservation_runtime import acceptance_service
                accepted = acceptance_service(self.root)
                chain = accepted._chain()
                accepted._verify_mirrors(chain)
                if not getattr(accepted, "runtime", False):
                    require(round_number == len(chain) + 1, "proposal must follow the last accepted round")
            context = validate_surface_bindings(self.root, surface_ref)
            validate_reference_graph(self.root, surface_ref, "bounded_change_surface")
            require(self._path(current_draft).read_bytes() == context.base, "current authoritative base differs")
            require(not os.path.samefile(self._path(current_draft), self.root / context.surface["base_draft"]["path"]),
                    "base Ref must identify an immutable snapshot, not the authoritative draft")
            require(isinstance(effective_config, dict), "effective config must be an object")
            require(effective_config.get("phase") == phase and effective_config.get("profile") == profile,
                    "effective config phase/profile must match admission")
            config_bytes = json_bytes(effective_config)
            feedback_refs = decode_json(json_bytes(reviewer_feedback_refs))
            for ref in feedback_refs:
                artifact = read_artifact(self.root, ref, "reviewer_feedback")
                require(artifact["round_number"] == round_number and artifact["draft_hash"] == draft_hash(context.base.decode()),
                        "retained feedback round/base mismatch")
            require(len({ref["sha256"] for ref in feedback_refs}) == len(feedback_refs), "duplicate retained feedback")
            require({s["artifact"]["sha256"] for s in context.surface["finding_sources"]}
                    <= {ref["sha256"] for ref in feedback_refs}, "admitted findings must be retained before execution")
            if predecessor_report:
                validate_reference_graph(self.root, predecessor_report, "current_runtime_preservation_bridge_report")
            parent = f"rounds/round-{round_number}/preservation"
            # Validate the public shape before allocating any attempt directory.
            admission = {"schema_version": "preservation-bridge-proposal-admission-v1",
                "capability_version": "preservation-bridge-v1", "round_number": round_number, "attempt_number": 1,
                "phase": phase, "profile": profile, "origin": origin, "client_attempt_number": client_attempt_number,
                **{key: context.surface[key] for key in ("base_draft", "inventory", "scope_contract", "finding_sources")},
                "allowed_change_surface": surface_ref, "predecessor_report": predecessor_report,
                "transform_policy_version": "bridge-version-transform-v1"}
            validate_artifact(admission, "preservation_bridge_proposal_admission")
            parent_path = self._mkdir(parent)
            numbers = [int(match[1]) for path in parent_path.iterdir()
                       if (match := re.fullmatch(r"attempt-([1-9][0-9]*)", path.name))]
            number = max(numbers, default=0) + 1
            admission["attempt_number"] = number
            directory = f"{parent}/attempt-{number}"
            self._mkdir(directory)
            admission_ref = self._artifact(f"{directory}/admission.json", admission, "preservation_bridge_proposal_admission")
            try:
                config_ref = self._write(f"{directory}/effective_config.json", config_bytes)
                # Byte-identical mirrors retain approval/context evidence without
                # rewriting any internal Ref. Originals stay available and pinned.
                refs = [surface_ref, context.surface["base_draft"], context.surface["inventory"], context.surface["scope_contract"], *feedback_refs]
                if predecessor_report:
                    refs.append(predecessor_report)
                snapshots = []
                for ref in refs:
                    saved = self._write(f"{directory}/inputs/{ref['sha256']}.bin", read_ref(self.root, ref))
                    snapshots.append({"source": ref, "snapshot": saved})
                frozen_feedback = [next(s["snapshot"] for s in snapshots if s["source"] == ref) for ref in feedback_refs]
                ticket = ProposalTicket(str(self.root), directory, json_bytes(admission), json_bytes(config_ref),
                                        json_bytes(frozen_feedback), json_bytes(snapshots), current_draft)
                self._inputs(ticket)
                return ticket
            except (OSError, ValueError) as exc:
                self._terminal(directory, admission_ref, None, exc)
                raise

    def _inputs(self, ticket: ProposalTicket) -> ProposalInputs:
        require(ticket.root == str(self.root), "ticket belongs to another run root")
        admission = read_artifact(self.root, ticket.admission_ref, "preservation_bridge_proposal_admission")
        require(ticket.directory == f"rounds/round-{admission['round_number']}/preservation/attempt-{admission['attempt_number']}",
                "ticket directory differs from admission")
        context = validate_surface_bindings(self.root, admission["allowed_change_surface"])
        for key in ("base_draft", "inventory", "scope_contract", "finding_sources"):
            require(admission[key] == context.surface[key], "frozen admission/surface mismatch")
        for mirror in decode_json(ticket.snapshots_json):
            require(read_ref(self.root, mirror["source"]) == read_ref(self.root, mirror["snapshot"]), "snapshot differs")
        require(self._path(ticket.current_draft).read_bytes() == context.base, "current authoritative base differs")
        config = read_ref(self.root, decode_json(ticket.config_ref_json))
        require(decode_json(config).get("phase") == admission["phase"] and decode_json(config).get("profile") == admission["profile"],
                "frozen config phase/profile differs")
        return ProposalInputs(context.base, ticket.admission_json, config,
                              tuple(read_ref(self.root, ref) for ref in decode_json(ticket.feedback_refs_json)))

    def run_editor(self, ticket: ProposalTicket, editor: Callable[[ProposalInputs], bytes]) -> dict[str, str]:
        """Invoke once, then retain exact response and assess; no retries or writes to authority."""
        return self._execute(ticket, editor=editor)

    def capture_response(self, ticket: ProposalTicket, response: bytes) -> dict[str, str]:
        return self.run_editor(ticket, lambda inputs: response)

    def capture_revision(self, ticket: ProposalTicket, raw: bytes, summary: dict[str, Any]) -> dict[str, str]:
        return self._execute(ticket, revision=(raw, decode_json(json_bytes(summary))))

    def run_supplied(self, ticket: ProposalTicket, raw: bytes, editor: Callable[[ProposalInputs], bytes]):
        """Retain supplied bytes before the single summary call, under exclusion."""
        return self._execute(ticket, supplied=(raw, editor))

    def report(self, ticket: ProposalTicket) -> dict[str, Any]:
        """Read an existing immutable result. This does not replay an execution."""
        raw = self._path(f"{ticket.directory}/report.json").read_bytes()
        result = decode_json(raw)
        validate_artifact(result, "current_runtime_preservation_bridge_report")
        require(result["admission"] == ticket.admission_ref, "report belongs to another admission")
        return result

    def _terminal(self, directory, admission_ref, report_ref, exc):
        if report_ref is None:
            report_path = self._path(f"{directory}/report.json")
            if report_path.is_file():
                raw = report_path.read_bytes()
                persisted = decode_json(raw)
                validate_artifact(persisted, "current_runtime_preservation_bridge_report")
                require(persisted["admission"] == admission_ref, "persisted report/admission mismatch")
                report_ref = {"path": f"{directory}/report.json", "sha256": sha256_bytes(raw)}
        self._artifact(f"{directory}/terminal_failure.json", {
            "schema_version": "preservation-bridge-terminal-failure-v1", "admission": admission_ref,
            "report": report_ref, "category": "persistence_failure" if isinstance(exc, OSError) else "invalid_binding",
            "reason": f"Non-unit persistence/binding failure: {exc}", "acceptance": None}, "preservation_bridge_terminal_failure")

    def _execute(self, ticket, *, editor=None, revision=None, supplied=None):
        with self._lock():
            require(ticket.root == str(self.root), "ticket belongs to another root")
            directory = ticket.directory
            # Refuse replay before calling the client or modifying retained evidence.
            started = f"{directory}/execution_started"
            require(not self._path(started).exists(), "attempt was already started; inspect its report or admit a new attempt")
            read_artifact(self.root, ticket.admission_ref, "preservation_bridge_proposal_admission")
            report = {"schema_version": "current-runtime-preservation-bridge-report-v2", "assessment": "proposal",
                "admission": ticket.admission_ref, "proposal": None, "stage": "admission",
                "raw_response": None, "raw_proposal": None, "materialized_draft": None,
                "materialized_inventory": None, "materialized_draft_hash": None, "transformations": [],
                "unit_dispositions": [], "added_unit_ids": [], "unmapped_output_unit_ids": [],
                "pending_obligations": [], "failures": [], "validation_result": "not_completed",
                "outcome": "technical_failure", "next_action": "inspect_and_repair"}
            report_ref = None
            try:
                self._write(started, json_bytes({"admission": ticket.admission_ref,
                    "effective_config": decode_json(ticket.config_ref_json),
                    "reviewer_feedback": decode_json(ticket.feedback_refs_json),
                    "snapshots": decode_json(ticket.snapshots_json),
                    "supplied_input": {"path": f"{directory}/supplied_input.md", "sha256": sha256_bytes(supplied[0])} if supplied is not None else None}))
                try:
                    inputs = self._inputs(ticket)
                    admission = decode_json(inputs.admission_json)
                    report["stage"] = "client"
                    if supplied is not None:
                        require(admission["origin"] == "supplied_revision", "supplied revision origin mismatch")
                        raw, callback = supplied
                        require(isinstance(raw, bytes), "supplied revision must contain exact bytes")
                        self._write(f"{directory}/supplied_input.md", raw)
                        try:
                            response = callback(inputs)
                        except TimeoutError:
                            raise
                        except Exception as exc:
                            raise ProposalClientFailure(f"{type(exc).__name__}: {exc}") from exc
                        require(isinstance(response, bytes), "summary adapter must return exact response bytes")
                        self._write(f"{directory}/summary_response.json", response)
                        summary = decode_json(response)
                        require(isinstance(summary, dict), "summary response must be an object")
                        summary = {**summary, "draft_after_content": raw.decode("utf-8")}
                    elif editor is not None:
                        require(admission["origin"] == "editor", "client requires Editor origin")
                        try:
                            response = editor(inputs)
                        except TimeoutError:
                            raise
                        except Exception as exc:
                            raise ProposalClientFailure(f"{type(exc).__name__}: {exc}") from exc
                        require(isinstance(response, bytes), "Editor adapter must return exact response bytes")
                        report["raw_response"] = self._write(f"{directory}/raw_response.json", response)
                        try:
                            summary = decode_json(response)
                        except BridgeContractError as exc:
                            raise ValueError(f"invalid Editor response: {exc}") from exc
                        if not isinstance(summary, dict) or not isinstance(summary.get("draft_after_content"), str):
                            raise ValueError("Editor response must contain string draft_after_content")
                        raw = summary["draft_after_content"].encode("utf-8")
                    else:
                        require(admission["origin"] in {"supplied_revision", "orchestrator_noop"}, "revision origin mismatch")
                        raw, summary = revision
                        require(isinstance(raw, bytes), "supplied revision must contain exact bytes")
                    round_dir = f"rounds/round-{admission['round_number']}"
                    number = admission["attempt_number"]
                    report["raw_proposal"] = self._write(f"{round_dir}/full_draft_rewrite_attempt-{number}.md", raw)
                    report["stage"] = "materialization"
                    raw_text = raw.decode("utf-8", errors="strict")
                    # Existing Editor protocol recomputes this value; the original
                    # response is retained separately, including its claimed hash.
                    summary = {**summary, "draft_after_hash": draft_hash(raw_text)}
                    feedback = [decode_json(data) for data in inputs.reviewer_feedback_json]
                    eligible = validate_round_evidence(inputs.base, raw, admission, feedback, summary)
                    hygiene = []
                    try:
                        validate_generated_text(raw_text, context="bridge raw proposal")
                    except ValueError as exc:
                        hygiene.append({"category": "invalid_artifact", "affected_unit_ids": [],
                                        "reason": f"Non-unit text hygiene failure: {exc}"})
                    if (inputs.base.strip() and not raw.strip()) or raw_text.strip().startswith("[Whetstone editor blocked]") or any(
                            token in raw_text for token in ("[...UNCHANGED", "[UNCHANGED")):
                        hygiene.append({"category": "contract_collapse", "affected_unit_ids": [],
                                        "reason": "Non-unit empty or abbreviated/blocked placeholder draft."})
                    report["failures"].extend(hygiene)
                    summary_ref = self._artifact(f"{directory}/editor_summary.json", summary, "editor_summary")
                    # Size ratios are advisory; exact protected-unit checks below
                    # determine losses, including small deletions in large drafts.
                    materialized = materialize_proposal(inputs.base, raw, phase=admission["phase"],
                                                        origin=admission["origin"], ordinary_eligible=eligible)
                    report["transformations"] = materialized.transformations
                    report["materialized_draft"] = self._write(f"{round_dir}/materialized_draft_attempt-{number}.md", materialized.content)
                    inventory = build_inventory(materialized.content, path=report["materialized_draft"]["path"])
                    report["materialized_inventory"] = self._artifact(f"{directory}/materialized_inventory.json", inventory, "bridge_inventory")
                    report["materialized_draft_hash"] = draft_hash(materialized.content.decode())
                    proposal = {"schema_version": "preservation-bridge-proposal-v1", "admission": ticket.admission_ref,
                                **{key: report[key] for key in ("raw_response", "raw_proposal", "materialized_draft", "materialized_inventory",
                                                              "materialized_draft_hash", "transformations")},
                                "normal_round_evidence": {"effective_config": decode_json(ticket.config_ref_json),
                                                          "reviewer_feedback": decode_json(ticket.feedback_refs_json), "editor_summary": summary_ref}}
                    # Detect callback-time changes to admitted inputs before producing
                    # a completed proposal/report. The raw response remains retained.
                    self._inputs(ticket)
                    report["proposal"] = self._artifact(f"{directory}/proposal.json", proposal, "preservation_bridge_proposal")
                    validate_proposal_bindings(self.root, report["proposal"])
                    report["stage"] = "comparison"
                    context = validate_surface_bindings(self.root, admission["allowed_change_surface"])
                    report.update(assess_proposal(context, comparison_inventory(raw, inventory)))
                    report["failures"].extend(hygiene)
                    report["stage"] = "complete"
                    if report["failures"]:
                        report.update(validation_result="fail", outcome="rejected", next_action="new_authorized_attempt")
                    elif report["pending_obligations"]:
                        report.update(validation_result="pending", outcome="awaiting_operator_evidence", next_action="review_proposal")
                    else:
                        report.update(validation_result="pass", outcome="eligible", next_action="submit_acceptance_request")
                except TimeoutError as exc:
                    report.update(validation_result="not_completed", outcome="technical_failure", next_action="technical_resume")
                    report["failures"].append({"category": "client_timeout", "affected_unit_ids": [], "reason": f"Non-unit client timeout: {exc}"})
                except ProposalClientFailure as exc:
                    report.update(validation_result="not_completed", outcome="technical_failure", next_action="inspect_and_repair")
                    report["failures"].append({"category": "invalid_artifact", "affected_unit_ids": [],
                                               "reason": f"Non-unit unclassified client failure; no retry classification: {exc}"})
                except ValueError as exc:
                    category = exc.category if isinstance(exc, MaterializationError) else (
                        "invalid_binding" if isinstance(exc, BridgeContractError) else "invalid_artifact")
                    report.update(validation_result="fail", outcome="rejected", next_action="new_authorized_attempt")
                    report["failures"].append({"category": category, "affected_unit_ids": [], "reason": f"Non-unit or unresolved artifact failure: {exc}"})
                report_ref = self._artifact(f"{directory}/report.json", report, "current_runtime_preservation_bridge_report")
                return report_ref
            except (OSError, BridgeContractError) as exc:
                self._terminal(directory, ticket.admission_ref, report_ref, exc)
                raise
