"""Read-only Phase 2 prerequisites, without a Phase 2 configuration or execution grant."""
from copy import deepcopy

from whetstone.vnext_review_configuration import focused_profile
from dataclasses import dataclass

from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes
from whetstone.vnext_verified_phase1_operator import _OperatorStatus
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal
from whetstone.vnext_verified_work import VerifiedWork


ALGORITHM = 'algorithms/vnext_verified_phase2_eligibility_v1.md'


@dataclass(frozen=True)
class Phase2Eligibility:
    current_pointer: dict
    current_verified_draft: dict
    current_verified_map: dict
    review_configuration: dict
    latest_candidate: dict | None
    outstanding_decision_ids: tuple
    review_gate: str | None
    accepted: bool | None
    closeout_ref: dict | None
    terminal_report_ref: dict | None
    state_current: bool | None
    phase1_prerequisites_met: bool
    phase1_blockers: tuple
    # review-configuration-v1 binds no Phase 2 target/rubric/profile budgets.
    phase2_blockers: tuple = ('phase2_configuration_unbound', 'phase2_execution_unavailable')
    entry_permitted: bool = False
    resume_permitted: bool = False
    apply_back_permitted: bool = False


class _Eligibility(_OperatorStatus):
    def _proof(self, read):
        proof = super()._proof(read)
        entries = {row['path']: row for row in proof.reader.suite.manifest['algorithms']}
        require(ALGORITHM in entries, 'verified Phase 2 eligibility contract is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
                'installed verified Phase 2 eligibility contract differs from pinned suite')
        return proof

    def inspect_eligibility(self):
        proof = self._proof(self.store.read)
        return self._evaluate_eligibility(proof)

    def _evaluate_eligibility(self, proof):
        work = VerifiedWork._observe(self, proof)
        latest = None
        decisions = ()

        def result(blockers, status=None):
            pointer = proof.pointers[-1]
            view = Phase2Eligibility(deepcopy(proof.latest),
                dict(path=pointer['verified_draft_path'], hash=pointer['verified_draft_hash']),
                dict(path=pointer['verified_section_identity_map_path'], hash=pointer['verified_section_identity_map_hash']),
                deepcopy(self.run._record['review_configuration']), deepcopy(latest), decisions,
                status.review_gate if status else None, status.accepted if status else None,
                deepcopy(status.closeout_ref) if status else None,
                deepcopy(status.terminal_report_ref) if status else None,
                status.state_current if status else None, not blockers, tuple(blockers))
            proof.guard(self.store.read)
            self.run._guard(self.store.read)
            return view

        if work.outcome in {'materialization_required', 'registration_recovery_required'}:
            return result([work.outcome])
        latest = proof.view.creations[-1] if proof.view.creations else None
        if latest is not None:
            journal = VerifiedSemanticDecisionJournal(proof.router.registry(), admission=proof.router)
            candidate = journal._state(latest)[0]
            decision = candidate.decision
            decisions = tuple(decision['outstanding_decision_ids']) if decision else ()
            if candidate.prepared:
                return result(['candidate_decision_recovery_required'])
            if decisions:
                return result(['operator_decision_required'])
            promoted = {row['source_candidate_id'] for row in proof.pointers[1:]}
            if latest['candidate_id'] not in promoted:
                if decision is None or not decision['decision_final']:
                    return result(['candidate_verification_required'])
                if decision['candidate_disposition'] == 'CANDIDATE_REJECTED':
                    return result(['candidate_rejected'])
                return result(['promotion_required'])
        if work.outcome != 'work_available':
            return result([work.outcome])
        closeout = self.evaluate(proof)
        status = self._status(proof, closeout)
        blockers = []
        if focused_profile(proof.seed_values['review']) is not None:
            blockers.append('focused_profile_is_not_full_phase1')
        if closeout.review_gate != 'review_complete': blockers.append('phase1_' + closeout.review_gate)
        if not closeout.accepted: blockers.append('phase1_acceptance_not_established')
        if closeout.unclean_profiles: blockers.append('phase1_profiles_not_clean')
        if not closeout.materialized: blockers.append('phase1_closeout_required')
        if not status.state_current: blockers.append('phase1_state_recovery_required')
        return result(blockers, status)


def inspect_verified_phase2_eligibility(run):
    return _Eligibility(run).inspect_eligibility()
