"""Local bridge acceptance, immutable commit records and deterministic mirror repair.

This increment accepts isolated developer proposal roots. Live scheduler roots
remain blocked until the runtime adapter supplies its additional gates/state.
There is deliberately no model client dependency here.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from whetstone.contracts import validate_artifact
from whetstone.evaluation import accepted_draft
from whetstone.hashing import draft_hash
from whetstone.preservation_assessment import assess_proposal
from whetstone.preservation_contracts import (
    BridgeContractError, complete_correspondence, decode_json, read_artifact, read_ref, require,
    validate_change_surface, validate_evidence_bindings, validate_proposal_bindings,
    validate_reference_graph, validate_surface_bindings,
)
from whetstone.preservation_inventory import sha256_bytes
from whetstone.preservation_materialization import comparison_inventory
from whetstone.preservation_proposals import ProposalStore, json_bytes
from whetstone.preservation_round_evidence import validate_round_evidence
from whetstone.text_validation import validate_generated_text


@dataclass(frozen=True)
class AcceptanceResult:
    outcome: str
    report: dict[str, Any]
    report_ref: dict[str, str] | None
    acceptance: dict[str, str] | None
    replayed: bool = False
    historical: bool = False


def failure(category: str, reason: str, ids: list[str] | None = None) -> dict[str, Any]:
    return {"category": category, "affected_unit_ids": ids or [],
            "reason": reason if ids else f"Non-unit or unresolved identity check: {reason}"}


def _category(message: str) -> str:
    if "supersession" in message:
        return "unauthenticated_supersession"
    if "deletion" in message:
        return "unauthorized_deleted"
    if "weakening" in message:
        return "disallowed_weakening"
    if any(word in message for word in ("surface", "frozen", "allowed", "relocation", "exceeded", "attribution")):
        return "allowed_surface_overrun"
    if any(word in message for word in ("ambiguous", "coverage", "correspondence", "successor", "predecessor")):
        return "ambiguous"
    return "invalid_binding"


class AcceptanceService(ProposalStore):
    """Same-root request admission and commit; uses ProposalStore's writer lock."""

    def reference(self, path: str) -> dict[str, str]:
        raw = self._path(path).read_bytes()
        return {"path": path, "sha256": sha256_bytes(raw)}

    def _boundary(self) -> None:
        for path in ("rounds/run_state.json", "orchestrator_config.yaml"):
            require(not self._path(path).exists(),
                    "live/configured scheduler roots require the step-4 runtime adapter; use an isolated developer proposal root")

    def _check_round(self, original, chain):
        require(original["round_number"] == len(chain) + 1, "standalone acceptance rounds must be contiguous from the original seed")

    def _proposal_directory(self, proposal_ref):
        proposal, admission = validate_proposal_bindings(self.root, proposal_ref)
        require(admission["origin"] != "phase2_entry", "maintenance lineage requires the runtime adapter")
        if not getattr(self, "runtime", False):
            require(admission["phase"] == "phase_1", "Phase 2 acceptance requires the runtime handoff adapter")
        directory = f"rounds/round-{admission['round_number']}/preservation/attempt-{admission['attempt_number']}"
        require(proposal_ref["path"] == f"{directory}/proposal.json", "proposal must occupy its admitted immutable attempt path")
        require(proposal["admission"]["path"] == f"{directory}/admission.json", "proposal admission path mismatch")
        return directory, proposal, admission

    def _latest_report(self, directory: str):
        result = self.reference(f"{directory}/report.json")
        read_artifact(self.root, result, "current_runtime_preservation_bridge_report")
        attempts = []
        for path in self._path(directory).iterdir():
            match = re.fullmatch(r"acceptance-attempt-([1-9][0-9]*)", path.name)
            if match and (path / "report.json").is_file():
                attempts.append((int(match[1]), str((path / "report.json").relative_to(self.root))))
        if attempts:
            result = self.reference(max(attempts)[1])
        return result

    def prepare_request(self, *, proposal_ref, evidence_refs, surface_ref=None, output: str):
        with self._lock():
            self._boundary()
            directory, proposal, admission = self._proposal_directory(proposal_ref)
            surface_ref = surface_ref or admission["allowed_change_surface"]
            context = validate_surface_bindings(self.root, surface_ref)
            request = {"schema_version": "preservation-bridge-acceptance-request-v1", "proposal": proposal_ref,
                       "scope_contract": context.surface["scope_contract"], "allowed_change_surface": surface_ref,
                       "finding_sources": context.surface["finding_sources"], "operator_evidence": evidence_refs,
                       "predecessor_report": self._latest_report(directory)}
            self._validate_request(request)
            return self._artifact(output, request, "preservation_bridge_acceptance_request")

    def _validate_request(self, request):
        validate_artifact(request, "preservation_bridge_acceptance_request")
        directory, proposal, admission = self._proposal_directory(request["proposal"])
        validate_reference_graph(self.root, request["proposal"], "preservation_bridge_proposal")
        context = validate_surface_bindings(self.root, request["allowed_change_surface"])
        require(context.surface["base_draft"] == admission["base_draft"] and context.surface["inventory"] == admission["inventory"],
                "acceptance must retain the exact proposal base and inventory")
        for key in ("scope_contract", "finding_sources"):
            require(request[key] == context.surface[key], f"request/surface {key} mismatch")
        for ref in request["operator_evidence"]:
            validate_evidence_bindings(self.root, ref, proposal_ref=request["proposal"], surface_ref=request["allowed_change_surface"])
        if request["predecessor_report"] is not None:
            predecessor = read_artifact(self.root, request["predecessor_report"], "current_runtime_preservation_bridge_report")
            require(predecessor["proposal"] == request["proposal"], "predecessor report belongs to another proposal")
        return directory, proposal, admission, context

    def _predecessor_before(self, directory, number):
        result = self.reference(f"{directory}/report.json")
        for n in range(1, number):
            path = f"{directory}/acceptance-attempt-{n}/report.json"
            if self._path(path).exists():
                result = self.reference(path)
        return result

    def _admission(self, request_ref, request, number):
        _, proposal, original = self._proposal_directory(request["proposal"])
        return {"schema_version": "preservation-bridge-acceptance-admission-v1", "capability_version": "preservation-bridge-v1",
                "acceptance_attempt_number": number, "request": request_ref, "proposal": request["proposal"],
                "base_draft": original["base_draft"], "inventory": original["inventory"],
                **{key: request[key] for key in ("scope_contract", "allowed_change_surface", "finding_sources", "operator_evidence", "predecessor_report")},
                "transform_policy_version": original["transform_policy_version"]}

    def _ordinary(self, proposal, admission, previous_issues):
        normal = proposal["normal_round_evidence"]
        base, raw = read_ref(self.root, admission["base_draft"]), read_ref(self.root, proposal["raw_proposal"])
        feedback = [read_artifact(self.root, ref, "reviewer_feedback") for ref in normal["reviewer_feedback"]]
        summary = read_artifact(self.root, normal["editor_summary"], "editor_summary")
        eligible = validate_round_evidence(base, raw, admission, feedback, summary)
        resolved = set(summary["resolved_issue_ids"]) if raw != base else set()
        issues = {i["issue_id"]: deepcopy(i) for i in previous_issues if i["issue_id"] not in resolved}
        # Retain every unresolved finding; a selective unresolved-ID list is not
        # permission to discard prior serious findings or out-of-scope findings.
        for artifact in feedback:
            for item in artifact["feedback"]:
                if item["issue_id"] in resolved:
                    continue
                issue = {key: item[key] for key in ("issue_id", "issue_fingerprint", "normalized_severity", "affected_sections", "claim", "in_scope")}
                issue["blocking_acceptance"] = item["normalized_severity"] in {"major", "blocker"} and item["in_scope"]
                prior = issues.get(item["issue_id"])
                if prior and prior["normalized_severity"] in {"major", "blocker"}:
                    continue
                issues[item["issue_id"]] = issue
        return bool(eligible and accepted_draft(issues.values())), list(issues.values())

    def _assess(self, request, admission_ref, previous_issues):
        _, proposal, original, context = self._validate_request(request)
        actual = read_artifact(self.root, proposal["materialized_inventory"], "bridge_inventory")
        view = comparison_inventory(read_ref(self.root, proposal["raw_proposal"]), actual)
        report = {"schema_version": "current-runtime-preservation-bridge-report-v2", "assessment": "acceptance",
                  "admission": admission_ref, "proposal": request["proposal"], "stage": "comparison",
                  **{key: proposal[key] for key in ("raw_response", "raw_proposal", "materialized_draft", "materialized_inventory", "materialized_draft_hash", "transformations")},
                  **assess_proposal(context, view), "validation_result": "fail", "outcome": "rejected", "next_action": "new_authorized_attempt"}
        evidence = [read_artifact(self.root, ref, "bridge_operator_evidence") for ref in request["operator_evidence"]]
        try:
            relation, additions = complete_correspondence(context.inventory, view, evidence=evidence)
            # A complete adopted relation supersedes the preliminary mechanical
            # interpretation; recompute permissions under this exact relation.
            report.update(unit_dispositions=[], added_unit_ids=additions, unmapped_output_unit_ids=[], pending_obligations=[], failures=[], stage="complete")
            for entry in relation:
                supporting = [(ref, value) for ref, value in zip(request["operator_evidence"], evidence) if entry in value["correspondence"]]
                findings = {(f["artifact_sha256"], f["feedback_id"]) for _, value in supporting for f in value["finding_refs"]}
                report["unit_dispositions"].append({**entry, "finding_refs": [{"artifact_sha256": sha, "feedback_id": fid} for sha, fid in sorted(findings)],
                    "evidence_refs": [ref for ref, _ in supporting],
                    "rationale": "; ".join(value["rationale"] for _, value in supporting) or "Exact mechanical preservation after verified trusted-span reversal."})
            # Check each relation and addition independently to retain distinct
            # violations, then the whole relation for cross-unit limits/laundering.
            messages = set()
            for entries, added in [(relation, additions)] + [([entry], []) for entry in relation] + [([], [uid]) for uid in additions]:
                try:
                    validate_change_surface(context, view, correspondence=entries, additions=added, evidence=evidence)
                except ValueError as exc:
                    if str(exc) not in messages:
                        messages.add(str(exc));report["failures"].append(failure(_category(str(exc)), str(exc), [e["base_unit_id"] for e in entries] + added))
        except ValueError as exc:
            report["failures"].append(failure(_category(str(exc)), str(exc)))
            # Submitted acceptance cannot leave missing effect/mapping work pending.
            for pending in report["pending_obligations"]:
                report["failures"].append(failure("ambiguous", pending["reason"], pending["base_unit_ids"] + pending["output_unit_ids"]))
            report["pending_obligations"] = []
        for field in ("raw_proposal", "materialized_draft"):
            content = read_ref(self.root, proposal[field]).decode("utf-8")
            try:
                validate_generated_text(content, context=f"acceptance {field}")
            except ValueError as exc:
                report["failures"].append(failure("invalid_artifact", str(exc)))
            if (context.base.strip() and not content.strip()) or content.strip().startswith("[Whetstone editor blocked]") or any(t in content for t in ("[...UNCHANGED", "[UNCHANGED")):
                report["failures"].append(failure("contract_collapse", "empty or placeholder draft"))
        eligible, issues = self._ordinary(proposal, original, previous_issues)
        if not eligible:
            report["failures"].append(failure("invalid_artifact", "ordinary acceptance blocked by unresolved serious findings or conflicts"))
        if not report["failures"]:
            report.update(validation_result="pass", outcome="eligible", next_action="none")
        validate_artifact(report, "current_runtime_preservation_bridge_report")
        return report, issues

    def _seed(self):
        path = self._path("rounds/preservation/seed.json")
        if not path.exists():
            return None
        seed = decode_json(path.read_bytes())
        require(isinstance(seed, dict) and set(seed) == {"base_draft", "history"}, "invalid original seed record")
        read_ref(self.root, seed["base_draft"]);read_ref(self.root, seed["history"])
        return seed

    def _chain(self):
        """Discover immutable markers; every node is independently reproduced."""
        markers = {}
        for path in self.root.glob("rounds/round-*/preservation/attempt-*/acceptance-attempt-*/acceptance.json"):
            ref = self.reference(str(path.relative_to(self.root)))
            marker = read_artifact(self.root, ref, "preservation_bridge_acceptance")
            require(ref["sha256"] not in markers, "duplicate acceptance marker")
            markers[ref["sha256"]] = (ref, marker)
        seed = self._seed()
        require(not markers or seed is not None, "accepted chain has no recorded original seed")
        chain, previous, issues = [], None, []
        while len(chain) < len(markers):
            children = [(ref, marker) for ref, marker in markers.values() if marker["previous_acceptance"] == previous]
            require(len(children) == 1, "forked, disconnected or cyclic acceptance chain")
            ref, marker = children[0]
            require(all(ref != item[0] for item in chain), "cyclic acceptance chain")
            admission = read_artifact(self.root, marker["admission"], "preservation_bridge_acceptance_admission")
            request = read_artifact(self.root, admission["request"], "preservation_bridge_acceptance_request")
            require(admission == self._admission(admission["request"], request, admission["acceptance_attempt_number"]), "acceptance admission source mismatch")
            directory, proposal, original, _ = self._validate_request(request)
            operation = f"{directory}/acceptance-attempt-{admission['acceptance_attempt_number']}"
            require(request["predecessor_report"] == self._predecessor_before(directory, admission["acceptance_attempt_number"]),
                    "accepted request has the wrong historical predecessor report")
            require(marker["admission"]["path"] == f"{operation}/admission.json" and ref["path"] == f"{operation}/acceptance.json", "acceptance marker path mismatch")
            base_ref = seed["base_draft"] if previous is None else chain[-1][1]["materialized_draft"]
            require(read_ref(self.root, original["base_draft"]) == read_ref(self.root, base_ref), "acceptance lineage base mismatch")
            self._check_round(original, chain)
            expected_report, issues = self._assess(request, marker["admission"], issues)
            require(expected_report["validation_result"] == "pass", "committed acceptance no longer passes validation")
            require(marker["report"]["path"] == f"{operation}/report.json", "acceptance report path mismatch")
            require(read_artifact(self.root, marker["report"], "current_runtime_preservation_bridge_report") == expected_report, "acceptance report differs from recomputation")
            expected = self._marker(marker["admission"], marker["report"], request, previous)
            require(marker == expected, "acceptance marker bindings differ")
            chain.append((ref, marker, issues));previous = ref
        return chain

    def _marker(self, admission_ref, report_ref, request, previous):
        _, proposal, original = self._proposal_directory(request["proposal"])
        return {"schema_version": "preservation-bridge-acceptance-v2", "admission": admission_ref, "report": report_ref,
                "proposal": request["proposal"], "materialized_draft": proposal["materialized_draft"],
                "materialized_draft_hash": proposal["materialized_draft_hash"],
                "accepted_noop": read_ref(self.root, proposal["materialized_draft"]) == read_ref(self.root, original["base_draft"]),
                "previous_acceptance": previous}

    def _mirrors(self, chain, *, initial=None):
        seed = self._seed() if initial is None else initial[0]
        require(seed is not None, "original seed is missing")
        history = read_ref(self.root, seed["history"]) if initial is None else initial[1]
        mirrors = {}
        for ref, marker, issues in chain:
            _, proposal, original = self._proposal_directory(marker["proposal"])
            number = original["round_number"];prefix = f"rounds/round-{number}"
            content = read_ref(self.root, marker["materialized_draft"])
            base = read_ref(self.root, original["base_draft"])
            summary = read_artifact(self.root, proposal["normal_round_evidence"]["editor_summary"], "editor_summary")
            summary = {**summary, "draft_after_hash": marker["materialized_draft_hash"], "draft_after_content": content.decode()}
            validate_artifact(summary, "editor_summary")
            unresolved = {"round_number": number, "draft_hash": marker["materialized_draft_hash"], "unresolved_issues": issues}
            validate_artifact(unresolved, "unresolved_issues")
            mirrors.update({f"{prefix}/draft_before.md": base, f"{prefix}/draft_after.md": content,
                            f"{prefix}/editor_summary.json": json_bytes(summary), f"{prefix}/unresolved_issues.json": json_bytes(unresolved)})
            if history and not history.endswith(b"\n"):
                history += b"\n"
            history += (f"- Preservation acceptance: round {number}, phase `{original['phase']}`, "
                        f"marker `{ref['sha256']}`, before `{draft_hash(base.decode())}`, "
                        f"after `{marker['materialized_draft_hash']}`, noop `{str(marker['accepted_noop']).lower()}`.\n").encode()
        if chain:
            mirrors["spec.md"] = read_ref(self.root, chain[-1][1]["materialized_draft"])
        else:
            mirrors["spec.md"] = read_ref(self.root, seed["base_draft"])
        mirrors["spec.history.md"] = history
        return mirrors

    def _verify_mirrors(self, chain, *, allow_last_pending=False, initial=None):
        expected = self._mirrors(chain, initial=initial)
        prior = self._mirrors(chain[:-1], initial=initial) if chain and allow_last_pending else expected
        for path, target in expected.items():
            disk = self._path(path)
            actual = disk.read_bytes() if disk.exists() else None
            if path in {"spec.md", "spec.history.md"}:
                allowed = [target]
                if allow_last_pending:
                    allowed.append(prior[path])
                if path == "spec.history.md" and b"" in allowed:
                    allowed.append(None)
                require(actual in allowed, f"current authority/history differs at {path}")
            elif allow_last_pending and path not in prior:
                require(actual in (None, target), f"conflicting canonical round artifact: {path}")
            else:
                require(actual == target, f"committed repair is pending or conflicting at {path}")
        return expected

    def _replace(self, path, content):
        target = self._path(path);self._mkdir(str(target.parent.relative_to(self.root)))
        fd, temporary = tempfile.mkstemp(prefix=".bridge-mirror-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, target);self._sync_directory(target.parent)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)

    def _repair(self, chain):
        expected = self._verify_mirrors(chain, allow_last_pending=True)
        for path, content in expected.items():
            target = self._path(path)
            if target.exists() and target.read_bytes() == content:
                continue
            if path in {"spec.md", "spec.history.md"}:
                self._verify_mirrors(chain, allow_last_pending=True)
                self._replace(path, content)
            else:
                self._write(path, content)
        self._verify_mirrors(chain)

    def _terminal_acceptance(self, directory, admission_ref, exc):
        def maybe(name):
            return self.reference(f"{directory}/{name}") if self._path(f"{directory}/{name}").is_file() else None
        value = {"schema_version": "preservation-bridge-terminal-failure-v1", "admission": admission_ref,
                 "report": maybe("report.json"), "category": "persistence_failure" if isinstance(exc, OSError) else "invalid_binding",
                 "reason": f"Non-unit acceptance/repair failure: {exc}", "acceptance": maybe("acceptance.json")}
        # A previous failure remains immutable. A failed attempt to report a
        # different later error propagates rather than overwriting evidence.
        self._artifact(f"{directory}/terminal_failure.json", value, "preservation_bridge_terminal_failure")

    def accept(self, request_ref, *, dry_run=False) -> AcceptanceResult:
        # A dry-run must create no lock file or any other artifact. All its reads
        # are advisory; the real operation revalidates under exclusive exclusion.
        if dry_run:
            return self._accept(request_ref, dry_run=True)
        with self._lock():
            return self._accept(request_ref, dry_run=False)

    def _accept(self, request_ref, *, dry_run):
        self._boundary()
        request = read_artifact(self.root, request_ref, "preservation_bridge_acceptance_request")
        directory, proposal, original, context = self._validate_request(request)
        chain = self._chain()
        for ref, marker, _ in chain:
            if marker["proposal"] == request["proposal"]:
                # Replay never adopts new claims, allocates K, or reinstalls an
                # older proposal after another acceptance has advanced authority.
                self._verify_mirrors(chain, allow_last_pending=True)
                if not dry_run:
                    try:self._repair(chain)
                    except (OSError, ValueError) as exc:
                        self._terminal_acceptance(str(Path(chain[-1][1]["admission"]["path"]).parent), chain[-1][1]["admission"], exc)
                        raise
                return AcceptanceResult("accepted", read_artifact(self.root, marker["report"], "current_runtime_preservation_bridge_report"), marker["report"], ref, True, ref != chain[-1][0])
        if chain:
            self._verify_mirrors(chain)
        require(self._path("spec.md").read_bytes() == context.base, "current authoritative base is stale for this proposal")
        self._check_round(original, chain)
        seed = self._seed()
        if seed is not None and not chain:
            require(read_ref(self.root, seed["base_draft"]) == context.base, "proposal differs from recorded original seed")
        attempts = []
        for path in self._path(directory).iterdir():
            match = re.fullmatch(r"acceptance-attempt-([1-9][0-9]*)", path.name)
            if match:
                attempts.append((int(match[1]), path))
        # Resume only an identical frozen incomplete admission. A completed
        # rejection requires a new request pointing to its report.
        resume = None
        for number, path in sorted(attempts):
            if (path / "admission.json").exists():
                ref = self.reference(str((path / "admission.json").relative_to(self.root)))
                old = read_artifact(self.root, ref, "preservation_bridge_acceptance_admission")
                if old["request"] == request_ref:
                    require(old == self._admission(request_ref, request, number), "frozen acceptance admission changed")
                    if (path / "report.json").exists():
                        old_report = read_artifact(self.root, self.reference(str((path / "report.json").relative_to(self.root))), "current_runtime_preservation_bridge_report")
                        if old_report["validation_result"] == "fail":
                            return AcceptanceResult("rejected", old_report, self.reference(str((path / "report.json").relative_to(self.root))), None, True)
                    resume = (number, str(path.relative_to(self.root)), ref)
        if resume is None:
            require(request["predecessor_report"] == self._latest_report(directory), "request must reference the immediately preceding assessment report")
            number = max((n for n, _ in attempts), default=0) + 1
            operation = f"{directory}/acceptance-attempt-{number}"
            admission = self._admission(request_ref, request, number)
            admission_ref = {"path": f"{operation}/admission.json", "sha256": sha256_bytes(json_bytes(admission))}
        else:
            number, operation, admission_ref = resume
            admission = self._admission(request_ref, request, number)
            newer = [n for n, _ in attempts if n > number]
            require(not newer, "a later acceptance attempt supersedes this incomplete operation")
        if not dry_run and resume is None:
            try:
                self._mkdir(operation)
                self._artifact(f"{operation}/admission.json", admission, "preservation_bridge_acceptance_admission")
            except (OSError, ValueError) as exc:
                if self._path(admission_ref["path"]).exists():
                    self._terminal_acceptance(operation, admission_ref, exc)
                raise
        try:
            report, issues = self._assess(request, admission_ref, chain[-1][2] if chain else [])
        except ValueError as exc:
            report = {"schema_version": "current-runtime-preservation-bridge-report-v2", "assessment": "acceptance",
                "admission": admission_ref, "proposal": request["proposal"], "stage": "admission",
                **{key: proposal[key] for key in ("raw_response", "raw_proposal", "materialized_draft", "materialized_inventory", "materialized_draft_hash", "transformations")},
                "unit_dispositions": [], "added_unit_ids": [], "unmapped_output_unit_ids": [], "pending_obligations": [],
                "failures": [failure("invalid_binding", str(exc))], "validation_result": "fail", "outcome": "rejected", "next_action": "new_authorized_attempt"}
            issues = []
        report_path = f"{operation}/report.json"
        if self._path(report_path).exists():
            require(self._path(report_path).read_bytes() == json_bytes(report), "completed report differs from revalidation")
        if dry_run:
            if report["validation_result"] == "pass":
                prospective_report = {"path": report_path, "sha256": sha256_bytes(json_bytes(report))}
                prospective_marker = self._marker(admission_ref, prospective_report, request, chain[-1][0] if chain else None)
                prospective_ref = {"path": f"{operation}/acceptance.json", "sha256": sha256_bytes(json_bytes(prospective_marker))}
                initial = None
                if seed is None:
                    history_path = self._path("spec.history.md")
                    initial = ({"base_draft": original["base_draft"]}, history_path.read_bytes() if history_path.exists() else b"")
                self._verify_mirrors(chain + [(prospective_ref, prospective_marker, issues)], allow_last_pending=True, initial=initial)
            return AcceptanceResult("eligible" if report["validation_result"] == "pass" else "rejected", report, None, None)
        try:
            report_ref = self._artifact(report_path, report, "current_runtime_preservation_bridge_report")
            if report["validation_result"] != "pass":
                return AcceptanceResult("rejected", report, report_ref, None)
            if seed is None:
                history_path = self._path("spec.history.md")
                history = history_path.read_bytes() if history_path.exists() else b""
                history_ref = self._write("rounds/preservation/seed_history.md", history)
                self._write("rounds/preservation/seed.json", json_bytes({"base_draft": original["base_draft"], "history": history_ref}))
            # Revalidate the complete graph/gates and current authority immediately
            # before the marker, while holding the same admission/commit lock.
            require(read_ref(self.root, request_ref) == json_bytes(request) or decode_json(read_ref(self.root, request_ref)) == request, "request changed before commit")
            require(self._assess(request, admission_ref, chain[-1][2] if chain else [])[0] == report, "acceptance inputs changed before commit")
            require(self._path("spec.md").read_bytes() == context.base, "current base changed before marker commit")
            require([item[0] for item in self._chain()] == [item[0] for item in chain], "accepted chain changed before commit")
            marker = self._marker(admission_ref, report_ref, request, chain[-1][0] if chain else None)
            marker_ref = {"path": f"{operation}/acceptance.json", "sha256": sha256_bytes(json_bytes(marker))}
            future_chain = chain + [(marker_ref, marker, issues)]
            self._verify_mirrors(future_chain, allow_last_pending=True)
            self._artifact(marker_ref["path"], marker, "preservation_bridge_acceptance")
            self._repair(future_chain)
            return AcceptanceResult("accepted", report, report_ref, marker_ref)
        except (OSError, ValueError) as exc:
            if self._path(admission_ref["path"]).exists():
                self._terminal_acceptance(operation, admission_ref, exc)
            raise
