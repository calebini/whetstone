"""Unactivated proposal-only semantic decision append and pointer commit.

The first decision records deterministic outcome. One completed semantic result
can append a final second decision; technical attempts stay in their request
journal and leave the first non-final decision intact. Finality never reopens.
"""
from copy import deepcopy

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_proposal_closeout import ProposalDecisionJournal, ProposalDecisionView, proposal_terminal_report
from whetstone.vnext_semantic_requests import SemanticRequestJournal
from whetstone.vnext_validation import validate_decision, validate_verification_pointer


ALGORITHM = 'algorithms/vnext_semantic_decisions_v1.md'


def _ref(path, value):
    return {'path': path, 'hash': sha256_bytes(canonical_json_bytes(value))}


def derive_semantic_decision(*, initial, previous, report, result, job, schemas):
    """Project validated semantic evidence into a final immutable decision.

    The caller must reproduce result from the durable Verifier receipt. This
    pure projection supplies no admission, persistence or promotion authority.
    The existing journal remains guarded to proposal-only jobs.
    """
    require(job['editing_mode'] in {'proposal_only', 'verified_promotion'},
            'semantic decision requires an editing mode')
    schemas.validate(initial, 'candidate_verification_v1')
    schemas.validate(previous, 'candidate_verification_v1')
    require(initial['job_id'] == job['job_id'], 'semantic decision job binding differs')
    validate_decision(initial, report, None, job)
    require(previous['decision_ordinal'] == 1 and not previous['decision_final']
            and previous['deterministic_result'] == 'pass' and previous['semantic_result'] == 'not_run',
            'semantic decision cannot reopen a final or unsupported predecessor')
    require({**previous, 'decided_at': initial['decided_at']} == initial,
            'semantic predecessor differs from reproduced deterministic evidence')
    semantic = result.verification
    passed = semantic['verdict'] == 'pass'
    request = result.authority_request
    decision = {**initial,
        'decision_ordinal': 2, 'previous_decision_hash': sha256_bytes(canonical_json_bytes(previous)),
        'semantic_verification_hash': sha256_bytes(canonical_json_bytes(semantic)), 'semantic_result': semantic['verdict'],
        'candidate_disposition': 'CANDIDATE_VERIFIED' if passed else 'CANDIDATE_REJECTED',
        'decision_final': True, 'promotion_permitted': passed and job['editing_mode'] == 'verified_promotion',
        'outstanding_decision_ids': [request['decision_id']] if request is not None else [],
        'rejection_codes': [] if passed else [
            'vnext_operator_decision_required' if semantic['verdict'] == 'operator_decision_required' else 'vnext_semantic_rejected']}
    schemas.validate(decision, 'candidate_verification_v1')
    validate_decision(decision, report, semantic, job)
    return decision


class SemanticDecisionJournal(ProposalDecisionJournal):
    RequestJournal = SemanticRequestJournal
    DISPOSITION_NAMES = frozenset({'event-1.json', 'event-2.json', 'event-3.json'})

    def __init__(self, registry, *, admission):
        super().__init__(registry)
        self.admission = admission
        reader, _ = admission._base(self.store.read)
        algorithms = {entry['path']: entry for entry in reader.suite.manifest['algorithms']}
        require(ALGORITHM in algorithms, 'semantic decision algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == algorithms[ALGORITHM]['sha256'],
                'installed semantic decision algorithm differs from pinned suite')

    def paths(self, creation, ordinal):
        directory = creation['candidate_path'].rsplit('/', 1)[0]
        return (directory, directory + f'/candidate_verification-attempt-{ordinal}.json',
                directory + f'/disposition_events/event-{ordinal + 1}.json',
                directory + f'/candidate_verification_pointer-attempt-{ordinal}.json',
                directory + '/candidate_verification_current.json')

    def completed(self, creation):
        request = self.RequestJournal(self.store, admission=self.admission, candidate_id=creation['candidate_id'])
        header, outcomes, result, receipt = request.inspect()
        require(result is not None and receipt is not None, 'semantic decision requires a completed durable Verifier receipt')
        return request, header, outcomes, result

    def semantic_decision(self, creation, report, previous, result, stamp):
        return derive_semantic_decision(initial=self._decision(creation, report, stamp), previous=previous,
            report=report, result=result, job=self.registry.job, schemas=self.schemas)

    def semantic_targets(self, creation, previous_event, decision):
        _, decision_path, event_path, _, _ = self.paths(creation, 2)
        decision_ref = _ref(decision_path, decision)
        event = {'schema_version': 'candidate-disposition-event-v1', 'event_id': '',
            'job_id': creation['job_id'], 'candidate_id': creation['candidate_id'],
            'candidate_creation_ordinal': creation['candidate_creation_ordinal'], 'event_ordinal': 3,
            'event_kind': 'verification_decision', 'previous_event_hash': sha256_bytes(canonical_json_bytes(previous_event)),
            'previous_disposition': previous_event['new_disposition'], 'new_disposition': decision['candidate_disposition'],
            'source_artifact_path': decision_ref['path'], 'source_artifact_hash': decision_ref['hash'],
            'recorded_at': decision['decided_at']}
        event['event_id'] = ids.disposition_id(event)
        self.schemas.validate(event, 'candidate_disposition_event_v1')
        event_ref = _ref(event_path, event)
        pointer = {'schema_version': 'candidate-verification-pointer-v1',
            **{key: decision[key] for key in ('job_id', 'transaction_id', 'candidate_id', 'candidate_creation_ordinal',
                'candidate_section_identity_map_path', 'candidate_section_identity_map_hash', 'candidate_disposition', 'decision_final')},
            'current_decision_ordinal': 2, 'current_decision_path': decision_path, 'current_decision_hash': decision_ref['hash'],
            'current_disposition_event_path': event_path, 'current_disposition_event_hash': event_ref['hash'],
            'updated_at': decision['decided_at']}
        self.schemas.validate(pointer, 'candidate_verification_pointer_v1')
        validate_verification_pointer(pointer, decision, decision_ref, event, event_ref, creation)
        return event, pointer

    def _state(self, creation):
        return self._state_with_request(creation)[0]

    def _validate_disposition_claims(self, creation, view, completed):
        directory = creation['candidate_path'].rsplit('/', 1)[0]
        for name, kind in self.registry._listing(directory + '/disposition_events'):
            if name.startswith('.vnext-tmp-'): continue
            require(name in self.DISPOSITION_NAMES and kind == 'file',
                    'unsupported or duplicate semantic disposition claim')

    def _state_with_request(self, creation):
        """Return this replay's state and the exact completed request it used.

        Keep the evidence local to the invocation. A caller needing both the
        decision and its source need not reconstruct the ancestor graph twice;
        the next state read still starts a fresh replay.
        """
        directory, d1_path, e1_path, s1_path, pointer_path = self.paths(creation, 1)
        _, d2_path, e2_path, s2_path, _ = self.paths(creation, 2)
        allowed = {path.rsplit('/', 1)[1] for path in (d1_path, s1_path, d2_path, s2_path, pointer_path)}
        for name, kind in self.registry._listing(directory):
            if name.startswith('candidate_verification'):
                require(name in allowed and kind == 'file', 'unsupported or duplicate semantic decision claim')
        initial = self.registry._json(creation['initial_disposition_event_path'], 'candidate_disposition_event_v1')[0]
        report = self.registry._json(directory + '/preservation_report.json', 'preservation_report_v2')[0]
        d1 = self._optional(d1_path, 'candidate_verification_v1')
        e1 = self._optional(e1_path, 'candidate_disposition_event_v1')
        s1 = self._optional(s1_path, 'candidate_verification_pointer_v1')
        d2 = self._optional(d2_path, 'candidate_verification_v1')
        e2 = self._optional(e2_path, 'candidate_disposition_event_v1')
        s2 = self._optional(s2_path, 'candidate_verification_pointer_v1')
        pointer = self._optional(pointer_path, 'candidate_verification_pointer_v1')
        p1 = p2 = completed = None
        if d1 is None:
            require(all(value is None for value in (e1, s1, d2, e2, s2, pointer)), 'semantic decision chain lacks its first source')
        else:
            require(d1 == self._decision(creation, report, d1['decided_at']), 'initial decision differs from deterministic evidence')
            expected_e1, p1 = self._targets(creation, initial, d1)
            require(e1 is None or e1 == expected_e1, 'initial decision event changed')
            require(s1 is None or (e1 is not None and s1 == p1), 'initial decision snapshot lacks matching targets')
        if d2 is None:
            require(e2 is None and s2 is None, 'semantic targets lack their decision source')
        else:
            require(d1 is not None and e1 is not None and s1 == p1 and pointer is not None,
                    'semantic decision lacks its committed predecessor')
            completed = self.completed(creation)
            _, _, _, result = completed
            require(d2 == self.semantic_decision(creation, report, d1, result, d2['decided_at']),
                    'semantic decision differs from exact receipt or predecessor')
            expected_e2, p2 = self.semantic_targets(creation, e1, d2)
            require(e2 is None or e2 == expected_e2, 'semantic disposition event changed')
            require(s2 is None or (e2 is not None and s2 == p2), 'semantic snapshot lacks matching targets')
        if pointer is not None:
            require((s1 is not None and pointer == p1) or (s2 is not None and pointer == p2),
                    'semantic verification pointer has missing, stale or conflicting targets')
        committed_second = p2 is not None and pointer == p2
        committed_first = p1 is not None and pointer == p1
        decision = d2 if committed_second else d1 if committed_first else None
        effective = e2 if committed_second else e1 if committed_first else initial
        effective_ref = _ref(e2_path, e2) if committed_second else _ref(e1_path, e1) if committed_first else {
            'path': creation['initial_disposition_event_path'], 'hash': creation['initial_disposition_event_hash']}
        prepared = (d2 is not None and not committed_second) or (d1 is not None and pointer is None)
        view = ProposalDecisionView(deepcopy(creation), deepcopy(decision), deepcopy(pointer), deepcopy(effective), effective_ref, prepared)
        self._validate_disposition_claims(creation, view, completed)
        return (view, report, initial, d2 if d2 is not None else d1), completed

    def publish_package(self, token, creation, view, decision, event, pointer):
        _, decision_path, event_path, snapshot_path, pointer_path = self.paths(creation, decision['decision_ordinal'])
        self.store.publish(token, decision_path, decision)
        self.store.publish(token, event_path, event)
        self.store.publish(token, snapshot_path, pointer)
        expected = canonical_json_bytes(view.pointer) if view.pointer is not None else None
        def transition(old, new):
            require(old == expected and new == canonical_json_bytes(pointer), 'semantic pointer transition changed')
            self.registry.validate_authority(self.store.read)
            current = next((event for event in self.registry._chain() if event['candidate_id'] == creation['candidate_id']), None)
            require(current == creation and self._state(creation)[0].pointer == view.pointer,
                    'semantic decision predecessor changed during commit')
        self.store.replace_pointer(token, pointer_path, expected=expected, snapshot=_ref(snapshot_path, pointer), validate_transition=transition)
        return self._state(creation)[0]

    def _creation(self, token, candidate_id):
        events = self.registry._reconcile(token, self.registry._chain())
        creation = next((event for event in events if event['candidate_id'] == candidate_id), None)
        require(creation is not None, 'semantic decision candidate is not registered')
        return creation

    def commit(self, candidate_id, *, decided_at):
        """Ordinary closeout reentry preserves an existing semantic decision."""
        with self.store.locked(self.registry.validate_authority) as token:
            creation = self._creation(token, candidate_id)
            view, report, initial, stored = self._state(creation)
            if stored is not None and stored['decision_ordinal'] == 2:
                return self._commit_semantic(token, creation, decided_at)
            decision = stored if stored is not None else self._decision(creation, report, decided_at)
            event, pointer = self._targets(creation, initial, decision)
            return self.publish_package(token, creation, view, decision, event, pointer)

    def _commit_semantic(self, token, creation, stamp):
        view, report, _, stored = self._state(creation)
        require(view.decision is not None, 'semantic append requires the committed initial decision')
        if stored['decision_ordinal'] == 1:
            require(not view.decision['decision_final'], 'semantic append cannot reopen a final candidate')
        request, header, outcomes, result = self.completed(creation)
        request.synchronize(token, header, outcomes)
        request.finish(token, result, outcomes)
        _, d1_path, e1_path, s1_path, _ = self.paths(creation, 1)
        previous = self.registry._json(d1_path, 'candidate_verification_v1')[0]
        previous_event = self.registry._json(e1_path, 'candidate_disposition_event_v1')[0]
        for path in (d1_path, e1_path, s1_path):
            self.store.publish(token, path, self.store.read(path))
        decision = stored if stored['decision_ordinal'] == 2 else self.semantic_decision(creation, report, previous, result, stamp)
        event, pointer = self.semantic_targets(creation, previous_event, decision)
        return self.publish_package(token, creation, view, decision, event, pointer)

    def commit_semantic(self, candidate_id, *, decided_at):
        with self.store.locked(self.registry.validate_authority) as token:
            return self._commit_semantic(token, self._creation(token, candidate_id), decided_at)

    def terminal(self, **options):
        registered = self.registry.inspect()
        if options:
            latest = self._state(registered.events[-1])[0] if registered.events else None
            return proposal_terminal_report(self.registry, decision_journal=self,
                outstanding_decision_ids=latest.decision['outstanding_decision_ids'] if latest and latest.decision else (), **options)
        require(registered.events and not registered.orphans, 'semantic terminal requires complete candidate registration')
        latest = self._state(registered.events[-1])[0]
        options = {}
        if not latest.prepared and latest.decision is not None and latest.decision['semantic_result'] != 'not_run':
            semantic = latest.decision['semantic_result']
            options = dict(terminal_state='PAUSED_DECISION' if semantic == 'operator_decision_required' else 'TARGET_NOT_REACHED',
                reason={'pass': 'vnext_proposal_only_complete', 'reject': 'vnext_semantic_rejected',
                        'operator_decision_required': 'vnext_operator_decision_required'}[semantic])
        return proposal_terminal_report(self.registry, decision_journal=self,
            outstanding_decision_ids=latest.decision['outstanding_decision_ids'] if latest.decision else (), **options)
