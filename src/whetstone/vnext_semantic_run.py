"""Explicit, unactivated semantic-round status, execution and recovery."""
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_proposal_closeout import proposal_terminal_report
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_proposal_requests import inspect_proposal_request
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from whetstone.vnext_semantic_requests import inspect_semantic_request, run_semantic_request


ALGORITHM = 'algorithms/vnext_semantic_run_v1.md'


class _SelectedAdmission:
    """Recheck round selection inside each downstream writer's lock."""
    def __init__(self, run, creation):
        self.run = run
        self.creation = creation
        self.load_inputs = run.load_inputs

    def _base(self, read):
        return self.run._base(read)

    def validate_authority(self, read):
        # Registry inspection calls this same run authority validator before
        # replaying the chain. Do not replay the entire selection proof twice.
        registry = registry_for_proposal_requests(self.run.store, load_inputs=self.run.load_inputs,
                                                  validate_authority=self.run.validate_authority)
        registered = registry.inspect()
        require(not registered.orphans and registered.latest == self.creation,
                'active semantic round changed before locked work')


def _selected(run, number):
    reader, _ = run._base(run.store.read)
    algorithms = {entry['path']: entry for entry in reader.suite.manifest['algorithms']}
    require(ALGORITHM in algorithms, 'semantic round algorithm is outside supported suite')
    require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == algorithms[ALGORITHM]['sha256'],
            'installed semantic round algorithm differs from pinned suite')
    registry = registry_for_proposal_requests(run.store, load_inputs=run.load_inputs,
                                              validate_authority=run.validate_authority)
    registered = registry.inspect()
    require(registered.events and not registered.orphans, 'semantic round requires completed candidate registration')
    request = inspect_proposal_request(run.store, load_inputs=lambda read: run.load_inputs(read, number),
                                       validate_authority=run.validate_authority)
    require(request.status == 'complete', 'semantic round requires its completed Editor request')
    creation = next((event for event in registered.events if event['proposal_id'] == request.proposal.patch['proposal_id']), None)
    require(creation is not None and creation['round_number'] == number, 'selected round has no exact registered proposal')
    require(creation == registered.latest, 'historical candidate is not the active semantic round')
    admission = _SelectedAdmission(run, creation)
    registry = registry_for_proposal_requests(run.store, load_inputs=run.load_inputs,
                                              validate_authority=admission.validate_authority)
    journal = SemanticDecisionJournal(registry, admission=admission)
    for event in registered.events:
        journal._state(event)
    return journal, journal.inspect(creation['candidate_id'])


def _terminal_path(report):
    return 'rounds/terminal_reports/terminal-' + sha256_bytes(canonical_json_bytes(report)) + '.json'


def _inspect(run, number, journal, view):
    packet = dict(schema_version='vnext-proposal-status-v1', job_id=journal.registry.job['job_id'],
        round_number=number, processing_gate='semantic_verification', request_id=None, request_status='not_started',
        request_attempts=0, terminal_report=None, terminal_materialization='not_applicable',
        resume=dict(permitted=False, next_gate=None, reason='vnext_semantic_not_started'))

    def finish(gate, report, *, materialization='not_applicable'):
        packet.update(processing_gate=gate, terminal_report=report, terminal_materialization=materialization,
                      resume=dict(report['resume']))
        journal.schemas.validate(packet, 'vnext_proposal_status_v1')
        return packet

    request = None
    if view.decision is not None and view.decision['deterministic_result'] == 'pass':
        request = inspect_semantic_request(run.store, admission=run, candidate_id=view.creation['candidate_id'])
        packet.update(request_id=request.request_id, request_status=request.status, request_attempts=request.attempts)
    if view.decision is None or view.prepared:
        return finish('verification_commit', journal.terminal())
    if view.decision['decision_final']:
        report = journal.terminal()
        try:
            raw = run.store.read(_terminal_path(report))
        except FileNotFoundError:
            run.store.read_descriptor()
            raw = None
        require(raw is None or raw == canonical_json_bytes(report), 'semantic terminal materialization conflicts with committed evidence')
        packet = finish('complete' if raw is not None else 'materialization', report,
                        materialization='present' if raw is not None else 'missing')
        if raw is None:
            packet['resume'] = dict(permitted=True, next_gate='materialization', reason='vnext_terminal_materialization_incomplete')
        journal.schemas.validate(packet, 'vnext_proposal_status_v1')
        return packet
    require(request is not None, 'nonfinal semantic round lacks a deterministic pass')
    if request.status in {'complete', 'valid_response'}:
        report = proposal_terminal_report(journal.registry, decision_journal=journal, terminal_state='HALTED_ARTIFACT_INVALID',
            reason='vnext_verification_commit_incomplete', next_gate='verification_commit', resume_permitted=True)
        return finish('verification_commit', report)
    if request.status == 'not_started':
        journal.schemas.validate(packet, 'vnext_proposal_status_v1')
        return packet
    classification = (request.last_outcome or {}).get('classification', request.status)
    eligible = request.status not in {'invalid_semantic', 'attempts_exhausted'} and request.attempts < 2
    reason = 'vnext_semantic_' + classification
    if (request.last_outcome or {}).get('error'):
        reason += ': ' + request.last_outcome['error']
    report = proposal_terminal_report(journal.registry, decision_journal=journal,
        terminal_state='HALTED_CLIENT_TIMEOUT' if classification == 'timeout' else 'HALTED_ARTIFACT_INVALID',
        reason=reason, next_gate='semantic_verification', resume_permitted=eligible)
    return finish('semantic_verification', report)


def inspect_semantic_round(run, *, round_number):
    """Validate the selected transaction and project committed state without writes."""
    return _inspect(run, round_number, *_selected(run, round_number))


def _publish_terminal(run, number):
    with run.store.locked(run.validate_authority) as token:
        journal, view = _selected(run, number)
        status = _inspect(run, number, journal, view)
        report = status['terminal_report']
        require(report is not None, 'semantic round has no terminal result to materialize')
        path = _terminal_path(report)
        run.store.publish(token, path, report)
        return report, {'path': path, 'hash': sha256_bytes(canonical_json_bytes(report))}


def run_semantic_round(run, *, round_number, client=None, decided_at, continuation=False):
    """Run only Verifier work or exact recovery; final candidates never reopen."""
    require(type(continuation) is bool, 'semantic continuation must be an explicit boolean')
    journal, view = _selected(run, round_number)
    status = _inspect(run, round_number, journal, view)
    require(not continuation or status['resume']['permitted'], 'selected semantic gate is not technically resumable')
    require(continuation or not status['resume']['permitted'], 'interrupted semantic work requires explicit continuation')
    gate = status['processing_gate']
    if gate in {'complete', 'materialization'}:
        return _publish_terminal(run, round_number)
    identifier = view.creation['candidate_id']
    if gate == 'verification_commit':
        if view.decision is None:
            recovered = journal.commit(identifier, decided_at=decided_at)
            # Initial deterministic decision recovery ends this invocation.
            with run.store.locked(run.validate_authority) as token:
                report = journal.terminal() if recovered.decision['decision_final'] else proposal_terminal_report(
                    journal.registry, decision_journal=journal, terminal_state='TARGET_NOT_REACHED',
                    reason='vnext_semantic_not_started')
                path = _terminal_path(report)
                run.store.publish(token, path, report)
                return report, {'path': path, 'hash': sha256_bytes(canonical_json_bytes(report))}
        # Valid raw evidence and prepared decision targets need no client.
        run_semantic_request(run.store, admission=journal.admission, candidate_id=identifier, client=None, continuation=True)
        journal.commit_semantic(identifier, decided_at=decided_at)
        return _publish_terminal(run, round_number)
    require(gate == 'semantic_verification', 'selected round is outside the semantic processing gate')
    if status['request_status'] in {'invalid_semantic', 'attempts_exhausted'}:
        return _publish_terminal(run, round_number)
    result = run_semantic_request(run.store, admission=journal.admission, candidate_id=identifier, client=client, continuation=continuation)
    if result.status == 'complete':
        journal.commit_semantic(identifier, decided_at=decided_at)
    return _publish_terminal(run, round_number)
