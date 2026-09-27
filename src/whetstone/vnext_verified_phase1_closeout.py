"""Bounded horizontal V acceptance and immutable terminal publication.

No clients, global pointer updates, mutable scheduler state or Phase 2 entry.
"""
from copy import deepcopy

from whetstone.vnext_review_configuration import focused_profile
from dataclasses import dataclass

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_validation import validate_terminal
from whetstone.vnext_verified_phase1_status import _profiles
from whetstone.vnext_verified_review import VerifiedReview, _contract, _sequence
from whetstone.vnext_verified_review_requests import _ReviewInputs, _VerifiedReviewRequest
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal
from whetstone.vnext_verified_work import VerifiedWork


ALGORITHM = 'algorithms/vnext_verified_phase1_closeout_v1.md'
SCHEMA = 'vnext_verified_phase1_closeout_v1'


def _ref(path, packet):
    return dict(path=path, hash=sha256_bytes(canonical_json_bytes(packet)))


@dataclass(frozen=True)
class Phase1Closeout:
    review_gate: str
    accepted: bool
    missing_review_profiles: tuple
    unclean_profiles: tuple
    global_blocking_findings: tuple
    report: dict | None
    report_ref: dict | None
    evidence: dict | None
    evidence_ref: dict | None
    pending_paths: tuple
    materialized: bool
    technical_failure: dict | None = None
    technical_failure_ref: dict | None = None


class _Closeout(VerifiedReview):
    def _proof(self, read):
        proof = super()._proof(read)
        entries = {row['path']: row for family in ('algorithms', 'schemas')
                   for row in proof.reader.suite.manifest[family]}
        paths = {ALGORITHM, 'schemas/' + SCHEMA + '.schema.json', 'schemas/terminal_report_v2.schema.json'}
        require(paths <= entries.keys(), 'verified Phase 1 closeout contracts are outside supported suite')
        for path in paths:
            require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == entries[path]['sha256'],
                    'installed verified Phase 1 closeout contract differs from pinned suite', path)
        return proof

    def _report(self, proof, *, terminal, reason):
        registry = proof.router.registry()
        views = []
        if proof.view.creations:
            journal = VerifiedSemanticDecisionJournal(registry, admission=proof.router)
            views = [journal._state(creation)[0] for creation in proof.view.creations]
        promoted = {p['source_candidate_id']: p for p in proof.pointers[1:]}
        latest = views[-1] if views else None
        fields = registry.schemas.load('terminal_report_v2')['properties']['latest_candidate']['properties']
        projection = dict.fromkeys(fields)
        creation = creation_ref = event = event_ref = decision = decision_ref = None
        if latest is not None:
            creation, decision = latest.creation, latest.decision
            require(not latest.prepared and creation['candidate_id'] in promoted,
                    'Phase 1 closeout cannot bypass an unpromoted candidate')
            pointer = promoted[creation['candidate_id']]
            creation_ref = _ref(f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json", creation)
            event_ref = dict(path=pointer['promotion_disposition_event_path'], hash=pointer['promotion_disposition_event_hash'])
            event = proof.reader.json(event_ref, 'candidate_disposition_event_v1')
            decision_ref = dict(path=latest.pointer['current_decision_path'], hash=latest.pointer['current_decision_hash'])
            projection.update(candidate_id=creation['candidate_id'], candidate_creation_ordinal=creation['candidate_creation_ordinal'],
                candidate_creation_event_path=creation_ref['path'], candidate_creation_event_hash=creation_ref['hash'],
                path=creation['candidate_path'], hash=creation['candidate_hash'], disposition=event['new_disposition'],
                disposition_event_path=event_ref['path'], disposition_event_hash=event_ref['hash'],
                verification_decision_path=decision_ref['path'], verification_decision_hash=decision_ref['hash'],
                verification_decision_final=decision['decision_final'])
        pointer = proof.pointers[-1]
        report = dict(schema_version='terminal-report-v2', terminal_state=terminal,
            current_verified_draft_path=pointer['verified_draft_path'], current_verified_draft_hash=pointer['verified_draft_hash'],
            latest_candidate=projection, rejected_candidate_ids=[v.creation['candidate_id'] for v in views
                if v.effective_event['new_disposition'] == 'CANDIDATE_REJECTED'],
            outstanding_decision_ids=deepcopy(decision['outstanding_decision_ids']) if decision else [],
            apply_back_permitted=False, resume=dict(permitted=False, next_gate=None, reason=reason))
        require(not report['outstanding_decision_ids'], 'unresolved operator choice prevents Phase 1 closeout')
        registry.schemas.validate(report, 'terminal_report_v2')
        validate_terminal(report, pointer, creation, creation_ref, event, event_ref, decision, decision_ref)
        return report

    def _optional(self, path):
        try: return self.store.read(path)
        except FileNotFoundError:
            self.store.read_descriptor()
            return None

    def evaluate(self, proof, *, generated_at=None):
        frames, gate, _ = _sequence(proof)
        configured = _contract(proof)
        progress = _profiles(proof, configured, frames)
        current = {frame.request.profile: frame for frame in frames
                   if frame.receipt is not None and frame.header['base_pointer'] == proof.latest}
        missing = tuple(row['name'] for row in configured if row['name'] not in current)
        unclean = tuple(row.profile for row in progress if not row.clean)
        # Global acceptance retains major/blocker debt even outside profile focus.
        blocking = tuple(dict(round_number=frame.request.number, feedback_id=row['feedback_id'],
                              severity=row['normalized_severity'])
                         for frame in sorted(current.values(), key=lambda f: f.request.number)
                         for row in frame.review['feedback']['feedback']
                         if row['normalized_severity'] in {'major', 'blocker'})
        focused = focused_profile(proof.seed_values['review'])
        from whetstone.vnext_verified_vertical_phase1 import enabled, sequence, completed_round
        vertical = enabled(proof.seed_values['review'])
        accepted = focused is None and not missing and not blocking
        report = report_ref = evidence = evidence_ref = None
        pending = ()
        technical = technical_ref = None
        if gate in {'review_complete', 'budget_exhausted'}:
            stable = not missing and not unclean and (focused is not None or not blocking)
            terminal = ('FOCUSED_PROFILE_STABLE' if stable else 'PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS') if focused else (
                'PHASE_1_STABLE' if stable else 'TARGET_NOT_REACHED')
            reason = ('vnext_phase1_review_complete' if stable else
                      'vnext_review_budget_exhausted' if gate == 'budget_exhausted' else 'vnext_global_acceptance_not_established')
            if focused:
                reason = 'vnext_focused_profile_complete' if stable else 'vnext_focused_profile_residuals'
            report = self._report(proof, terminal=terminal, reason=reason)
            report_ref = _ref('rounds/terminal_reports/terminal-' + sha256_bytes(canonical_json_bytes(report)) + '.json', report)
            evidence = dict(schema_version='vnext-verified-phase1-closeout-v1', job_id=proof.seed_values['job']['job_id'],
                current_verified_pointer=deepcopy(proof.latest), review_receipts=[dict(round_number=f.request.number,
                    profile=f.request.profile, base_pointer=deepcopy(f.header['base_pointer']),
                    receipt=_ref(f.request.directory + '/result.json', f.receipt)) for f in frames],
                accepted=accepted, missing_review_profiles=list(missing), unclean_profiles=list(unclean),
                global_blocking_findings=list(blocking), terminal_report=report_ref)
            evidence_schema = SCHEMA
            if focused or vertical:
                from whetstone.vnext_verified_focused_phase1 import directory, failure
                prefix = directory(proof, frames)
                if vertical:
                    from whetstone.vnext_verified_vertical_phase1 import failure
                    prefix = 'rounds/vertical_phase1/' + proof.latest['hash'] + '-' + str(frames[-1].request.number)
                if not stable:
                    path = prefix+'/technical_failure_report.json'
                    technical = failure(proof, frames, progress, existing=self._optional(path), generated_at=generated_at)
                    technical_ref = _ref(path, technical)
                evidence.update(schema_version='vnext-verified-phase1-closeout-v2',
                    review_configuration=deepcopy(self.run._record['review_configuration']),
                    focused_profile=focused, technical_failure=technical_ref)
                evidence_schema = 'vnext_verified_phase1_closeout_v2'
                if vertical:
                    evidence.pop('focused_profile')
                    vertical_state = sequence(proof)
                    evidence.update(schema_version='vnext-verified-phase1-closeout-v3',
                        round_number=completed_round(vertical_state),
                        review_round_budget=sum(p.round_budget for p in progress) + max(p.round_budget for p in progress),
                        vertical_merges=[_ref(f"rounds/round-{m[0]['round_number']}/vertical_merge.json", m[0]) for m in vertical_state.merges])
                    evidence_schema = 'vnext_verified_phase1_closeout_v3'
            proof.reader.suite.registry.validate(evidence, evidence_schema)
            evidence_ref = _ref('rounds/phase1_closeouts/closeout-' + sha256_bytes(canonical_json_bytes(evidence)) + '.json', evidence)
            if focused or vertical: evidence_ref = _ref(prefix+'/closeout.json', evidence)
            stored_report = self._optional(report_ref['path'])
            stored_evidence = self._optional(evidence_ref['path'])
            require(stored_report is None or stored_report == canonical_json_bytes(report), 'Phase 1 terminal report conflicts with replay')
            require(stored_evidence is None or stored_evidence == canonical_json_bytes(evidence), 'Phase 1 closeout evidence conflicts with replay')
            require(stored_evidence is None or stored_report is not None, 'committed Phase 1 closeout is missing its report')
            sources = [(report_ref, stored_report), (evidence_ref, stored_evidence)]
            if technical_ref:
                stored_technical = self._optional(technical_ref['path'])
                require(stored_evidence is None or stored_technical is not None,
                        'committed focused closeout is missing its technical report')
                sources.insert(0, (technical_ref, stored_technical))
            pending = tuple(ref['path'] for ref, raw in sources if raw is None)
        proof.guard(self.store.read)
        self.run._guard(self.store.read)
        return Phase1Closeout(gate, accepted, missing, unclean, blocking, report, report_ref, evidence, evidence_ref,
                              pending, evidence is not None and not pending, technical, technical_ref)

    def inspect_closeout(self):
        proof = self._proof(self.store.read)
        work = VerifiedWork._observe(self, proof)
        if work.outcome != 'work_available':
            proof.guard(self.store.read)
            return work
        return self.evaluate(proof)

    def _synchronize_sources(self, store, proof, closeout):
        frames, _, _ = _sequence(proof)
        for frame in frames:
            request = _VerifiedReviewRequest(_ReviewInputs(store, proof, frame.header['base_pointer']),
                                             frame.request.number, frame.request.profile)
            request.synchronize(store._token, frame.header, frame.outcomes)
            request.finish(store._token, frame.review)
        from whetstone.vnext_verified_vertical_phase1 import enabled, sequence, synchronize
        if enabled(proof.seed_values['review']): synchronize(store, proof, sequence(proof))
        checked = self.evaluate(proof, generated_at=(closeout.technical_failure or {}).get('generated_at'))
        require(checked.evidence == closeout.evidence, 'Phase 1 closeout changed during source synchronization')
        return checked

    def finish(self):
        def publish(store, proof):
            closeout = self.evaluate(proof)
            require(closeout.report is not None, 'Phase 1 has no eligible review terminal to publish')
            checked = self._synchronize_sources(store, proof, closeout)
            # Exact replay repeats barriers even when a lost ack left both visible.
            if checked.technical_failure_ref:
                store.publish(store._token, checked.technical_failure_ref['path'], checked.technical_failure)
            store.publish(store._token, checked.report_ref['path'], checked.report)
            store.publish(store._token, checked.evidence_ref['path'], checked.evidence)
            result = self.evaluate(proof)
            require(result.materialized, 'Phase 1 closeout publication incomplete')
            return result
        return self._execute(publish)


def inspect_verified_phase1_closeout(run):
    return _Closeout(run).inspect_closeout()


def finish_verified_phase1(run):
    return _Closeout(run).finish()
