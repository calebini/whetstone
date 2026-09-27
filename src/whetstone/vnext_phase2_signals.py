"""Deterministic signal replay for the separately pinned Phase 2 report owner."""
from copy import deepcopy
from dataclasses import asdict

from whetstone.conflicts import ConflictTracker, conflict_from_oscillation_detection
from whetstone.hashing import draft_hash, semantic_changes
from whetstone.oscillation import OscillationTracker
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_verified_phase2_signals_v1.md'
SCHEMA = 'vnext_phase2_signals_v1'


def supported(proof):
    return any(r['path'] == ALGORITHM for r in proof.reader.suite.manifest['algorithms'])


def pins(proof):
    entries = {r['path']: r['sha256'] for family in ('algorithms', 'schemas')
               for r in proof.reader.suite.manifest[family]}
    for path in (ALGORITHM, *('schemas/'+s+'.schema.json' for s in
            (SCHEMA, 'oscillation_report', 'conflict_report', 'conflict_state'))):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'Phase 2 signal contract is absent or changed', path)


def terminal(conditions):
    """D7 preconditions are checked by callers before this runtime ordering."""
    order = ('HALTED_CLIENT_TIMEOUT', 'CONVERGED', 'HALTED_CONFLICT', 'HALTED_OSCILLATION',
             'HALTED_ARTIFACT_INVALID', 'PAUSED_DECISION', 'TARGET_NOT_REACHED')
    return next((value for value in order if value in conditions), None)


def gate_for(signal, ordinary_gate):
    if signal['terminal_state'] == 'HALTED_CONFLICT': return 'conflict_halt_required'
    if signal['terminal_state'] == 'HALTED_OSCILLATION': return 'oscillation_halt_required'
    if 'freeze_prior_decision' in signal['recommendations']: return 'oscillation_freeze_required'
    return ordinary_gate


class SignalTracker:
    def __init__(self, number, raw):
        self.feedback = OscillationTracker()
        self.drafts = OscillationTracker()
        self.conflicts = ConflictTracker()
        self.drafts.record_draft(round_number=number-1, draft_hash_value=draft_hash(raw.decode()), semantic_changes=[])

    def record(self, number, feedback, *, before=None, after=None, resolved_opposition_keys=()):
        detections = []
        draft_detection = None
        if after is not None:
            found = self.drafts.record_draft(round_number=number, draft_hash_value=draft_hash(after.decode()),
                semantic_changes=semantic_changes(before.decode(), after.decode()))
            if found is not None:
                draft_detection = asdict(found)
                detections.append(found)
        # Only the separately pinned resolution owner supplies these keys from
        # committed evidence before this review. Promotion/silence alone do not.
        detections.extend(self.feedback.record_phase2_detections(round_number=number, reviewer_feedback=feedback,
            resolved_opposition_keys=set(resolved_opposition_keys)))
        conflicts = {r['conflict_fingerprint']: r for r in
                     (conflict_from_oscillation_detection(d) for d in detections if d.recommendation == 'escalate_conflict')}
        escalation = self.conflicts.record_round(round_number=number, conflicts=conflicts.values())
        snapshot = self.conflicts.snapshot(round_number=number)
        del snapshot['generated_at']
        conditions = []
        if any(c['conflict_severity'] == 'blocker' for c in conflicts.values()): conditions.append('HALTED_CONFLICT')
        if any(d.recommendation == 'stop_iteration' for d in detections): conditions.append('HALTED_OSCILLATION')
        return dict(detections=[asdict(d) for d in detections], draft_detection=draft_detection,
            feedback_detections=[asdict(d) for d in detections if asdict(d) != draft_detection], conflicts=list(conflicts.values()),
            conflict_state=deepcopy(snapshot), escalation_reason=escalation.reason if escalation else None,
            recommendations=list(dict.fromkeys(d.recommendation for d in detections)),
            conditions=conditions, terminal_state=terminal(conditions))
