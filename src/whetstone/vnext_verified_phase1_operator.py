"""Evidence-derived operator status and recovery-only Phase 1 state projection."""
from whetstone.vnext_phase1_policy import closeout_schema
from copy import deepcopy
from dataclasses import dataclass

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase1_closeout import _Closeout
from whetstone.vnext_verified_work import VerifiedWork, VerifiedWorkView


ALGORITHM = 'algorithms/vnext_verified_phase1_operator_v1.md'
STATE_FIELD = 'vnext_phase1_closeout'


@dataclass(frozen=True)
class VerifiedOperatorStatus:
    work_outcome: str
    current_pointer: dict
    review_gate: str | None
    terminal_report: dict | None
    terminal_report_ref: dict | None
    closeout_ref: dict | None
    accepted: bool | None
    state_current: bool | None
    stale_state: bool
    pending_paths: tuple
    next_action: str
    phase2_permitted: bool = False
    apply_back_permitted: bool = False
    resume_permitted: bool = False


class _OperatorStatus(_Closeout):
    def _proof(self, read):
        proof = super()._proof(read)
        entries = {row['path']: row for row in proof.reader.suite.manifest['algorithms']}
        require(ALGORITHM in entries, 'verified operator status contract is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
                'installed verified operator status contract differs from pinned suite')
        return proof

    def _state_target(self, closeout, proof=None):
        raw = self.store.read(STATE_PATH)  # Base mirror recovery owns absence/malformed state.
        state = decode_json(raw)
        require(isinstance(state, dict), 'Phase 1 state projection requires a JSON object')
        reference = closeout.evidence_ref if closeout.materialized else None
        stale = STATE_FIELD in state and (reference is None or state[STATE_FIELD] != reference)
        if reference is None:
            changed = STATE_FIELD in state
            state.pop(STATE_FIELD, None)
        else:
            changed = state.get(STATE_FIELD) != reference
            state[STATE_FIELD] = deepcopy(reference)
            vertical = (closeout.evidence['schema_version'] == 'vnext-verified-phase1-closeout-v3') or (
                proof is not None and proof.seed_values['review']['review_mode'] == 'vertical')
            if closeout.evidence.get('focused_profile') is not None or vertical:
                focused_state = dict(terminal_state=closeout.report['terminal_state'],
                    ready_for_phase_2=False, current_draft_status='not_accepted',
                    last_accepted_draft_hash=None)
                if vertical:
                    stable = closeout.report['terminal_state'] == 'PHASE_1_STABLE'
                    focused_state.update(ready_for_phase_2=stable,
                        review_round_budget=closeout.evidence['review_round_budget'],
                        current_round=closeout.evidence['round_number'],
                        current_draft_status='phase_1_stable' if stable else 'not_accepted',
                        last_accepted_draft_hash=closeout.report['current_verified_draft_hash'] if stable else None)
                changed = changed or any(state.get(key) != value for key, value in focused_state.items())
                state.update(focused_state)
        if proof is not None:
            from whetstone.vnext_verified_phase1_budget import supported, records, effective_profiles
            if supported(proof.reader.suite):
                from whetstone.vnext_verified_review import _contract, _sequence
                from whetstone.vnext_verified_vertical_phase1 import enabled, sequence, completed_round
                grants = records(proof)
                profiles = effective_profiles(proof, _contract(proof))
                frames, _, _ = _sequence(proof)
                vertical = enabled(proof.seed_values['review'])
                number = completed_round(sequence(proof)) if vertical and frames else max(
                    [f.request.number for f in frames if f.receipt is not None], default=0)
                stable = bool(reference and closeout.report['terminal_state'] == 'PHASE_1_STABLE')
                values = dict(budget_extensions=[v['event'] for _,v in grants], phase='phase_1', current_round=number,
                    current_draft_hash=proof.pointers[-1]['verified_draft_hash'],
                    review_profile_budgets={p['name']:p['budget'] for p in profiles},
                    review_round_budget=sum(p['budget'] for p in profiles)+(max(p['budget'] for p in profiles) if vertical else 0),
                    terminal_state=closeout.report['terminal_state'] if reference else None,
                    ready_for_phase_2=stable, current_draft_status='phase_1_stable' if stable else 'not_accepted',
                    last_accepted_draft_hash=proof.pointers[-1]['verified_draft_hash'] if stable else None)
                changed = changed or any(state.get(k) != v for k,v in values.items())
                state.update(values)
        from whetstone.vnext_phase1_policy import enabled as shared_policy
        if proof is not None and shared_policy(proof.seed_values['review']):
            changed = changed or state.get('ready_for_phase_2') is not False
            state['ready_for_phase_2'] = False
        return raw, canonical_json_bytes(state) if changed else raw, stale

    def _status(self, proof, closeout):
        raw, target, stale = self._state_target(closeout, proof)
        from whetstone.vnext_verified_focused_phase1 import FAILURE_MIRROR
        mirror_pending = bool(closeout.materialized and closeout.technical_failure is not None
            and self._optional(FAILURE_MIRROR) != canonical_json_bytes(closeout.technical_failure))
        current = raw == target and not mirror_pending
        committed = closeout.materialized
        action = ('reconcile_phase1_state' if not current else
                  'phase1_complete' if committed else
                  'finish_phase1' if closeout.report is not None else closeout.review_gate)
        result = VerifiedOperatorStatus('work_available', deepcopy(proof.latest), closeout.review_gate,
            deepcopy(closeout.report) if committed else None,
            deepcopy(closeout.report_ref) if committed else None,
            deepcopy(closeout.evidence_ref) if committed else None,
            closeout.accepted, current, stale,
            ((FAILURE_MIRROR,) if mirror_pending else ())
            + ((STATE_PATH,) if raw != target else ()) + closeout.pending_paths, action)
        proof.guard(self.store.read)
        self.run._guard(self.store.read)
        return result

    def inspect_status(self):
        proof = self._proof(self.store.read)
        work = VerifiedWork._observe(self, proof)
        if work.outcome != 'work_available':
            proof.guard(self.store.read)
            self.run._guard(self.store.read)
            return VerifiedOperatorStatus(work.outcome, deepcopy(proof.latest), None, None, None, None,
                None, None, False, work.pending_paths, work.outcome)
        return self._status(proof, self.evaluate(proof))

    def reconcile(self):
        def synchronize(store, proof):
            from whetstone.vnext_phase2_routes import supported as routes_supported
            from whetstone.vnext_verified_phase1_budget import supported as budget_supported
            if routes_supported(proof.reader.suite) or budget_supported(proof.reader.suite):
                require(self._optional('rounds/phase2/review_requests/first/request.json') is None,
                        'Phase 1 state recovery cannot supersede bound Phase 2 work')
            closeout = self.evaluate(proof)
            before, target, _ = self._state_target(closeout, proof)
            if budget_supported(proof.reader.suite) and not closeout.materialized:
                self._synchronize_sources(store, proof, closeout)
            if closeout.materialized:
                checked = self._synchronize_sources(store, proof, closeout)
                require(checked.materialized, 'committed Phase 1 closeout disappeared during recovery')
                for reference, value in ((checked.report_ref, checked.report), (checked.evidence_ref, checked.evidence)):
                    self.store.synchronize_existing(store._token, reference['path'], expected=canonical_json_bytes(value))
                if checked.technical_failure_ref:
                    from whetstone.vnext_verified_focused_phase1 import FAILURE_MIRROR
                    packet = canonical_json_bytes(checked.technical_failure)
                    self.store.synchronize_existing(store._token, checked.technical_failure_ref['path'], expected=packet)
                    existing = self._optional(FAILURE_MIRROR)
                    from whetstone.vnext_verified_phase1_budget import records
                    historical = [proof.reader.json(v['closeout'], closeout_schema(proof.seed_values['review'], proof.reader.suite))
                                  for _,v in records(proof)]
                    owned = any(c['technical_failure'] is not None and existing == proof.reader.raw(c['technical_failure'])
                                for c in historical)
                    require(existing is None or existing == packet or owned, 'unowned focused failure report conflicts')
                    proof.guard(self.store.read)
                    self.run._guard(self.store.read)
                    if existing is None:
                        store.publish(store._token, FAILURE_MIRROR, packet)
                    elif existing == packet:
                        self.store.synchronize_existing(store._token, FAILURE_MIRROR, expected=packet)
                    else:
                        # Reports are immutable; only their established compatibility mirror changes.
                        def validate_report(read, path, raw):
                            proof.guard(read); self.run._guard(read)
                            require(path == FAILURE_MIRROR and raw == packet and read(path) == existing,
                                    'historical failure mirror changed during projection')
                        self.store.materialize(store._token, FAILURE_MIRROR, packet, validate_target=validate_report)
            # Standard runs keep their namespaced projection. Focused runs also
            # project their terminal and explicit lack of Phase 2 readiness.
            def validate_target(read, path, raw):
                proof.guard(read)
                self.run._guard(read)
                require(path == STATE_PATH and raw == target and read(path) == before,
                        'Phase 1 state target changed during recovery')
            if before != target:
                self.store.materialize(store._token, STATE_PATH, target, validate_target=validate_target)
            else:
                # Equality after a lost final acknowledgement is not durability.
                self.store.synchronize_existing(store._token, STATE_PATH, expected=target)
            # Reuse the provisional failure timestamp for this recovery operation.
            # Uncommitted reports otherwise acquire a new hash when the clock ticks;
            # retained reports still validate against their persisted timestamp.
            checked = self.evaluate(proof, generated_at=(closeout.technical_failure or {}).get('generated_at'))
            require(checked.evidence == closeout.evidence and checked.materialized == closeout.materialized,
                    'Phase 1 evidence changed during state recovery')
            result = self._status(proof, checked)
            require(result.state_current, 'Phase 1 state recovery incomplete')
            return VerifiedWorkView('phase1_state_synchronized', deepcopy(proof.pointers[-1]), value=result)
        return self._execute(synchronize)


def inspect_verified_operator(run):
    return _OperatorStatus(run).inspect_status()


def reconcile_verified_phase1_state(run):
    return _OperatorStatus(run).reconcile()
