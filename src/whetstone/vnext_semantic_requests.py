"""Unactivated, bounded Verifier requests over registered immutable candidates.

Result receipt commits validated evidence, not a candidate disposition. No
Editor is accepted here, and only new invocations require an open candidate.
"""
from copy import deepcopy
from dataclasses import dataclass
import json

from whetstone.vnext_contracts import (
    CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes, confined_file, content_identifier,
    decode_json, require, sha256_bytes,
)
from whetstone.vnext_proposal_closeout import ProposalDecisionJournal
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_protocol import SemanticShapeError, decode_semantic_response, semantic_verifier_prompt, _semantic_verifier_prompt


REQUEST_SCHEMAS = frozenset({'vnext_semantic_request_v1', 'vnext_semantic_request_transport_v1',
                           'vnext_semantic_invocation_v1', 'vnext_semantic_outcome_v1', 'vnext_semantic_result_v1'})
REQUEST_ALGORITHM = 'algorithms/vnext_semantic_requests_v1.md'


def _hash(value):
    return sha256_bytes(canonical_json_bytes(value))


def _identity(transport):
    return {key: value for key, value in transport.items() if key != 'timeout_seconds'}


@dataclass(frozen=True)
class SemanticRequestStatus:
    request_id: str
    status: str
    attempts: int
    result: object | None = None
    receipt: dict | None = None
    last_outcome: dict | None = None


class SemanticRequestJournal:
    DecisionJournal = ProposalDecisionJournal

    def __init__(self, store, *, admission, candidate_id):
        self.store = store
        self.admission = admission
        self.candidate_id = candidate_id
        self.schemas = VNextSchemaRegistry()
        self.context = self.load()
        self.packet = self.context.packet
        reader, _ = admission._base(store.read)
        pinned = {entry['path'] for entry in reader.suite.manifest['schemas']}
        require({'schemas/' + name + '.schema.json' for name in REQUEST_SCHEMAS} <= pinned,
                'durable semantic request schemas are outside supported suite')
        algorithms = {entry['path']: entry for entry in reader.suite.manifest['algorithms']}
        require(REQUEST_ALGORITHM in algorithms, 'durable semantic request algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, REQUEST_ALGORITHM).read_bytes()) == algorithms[REQUEST_ALGORITHM]['sha256'],
                'installed semantic request algorithm differs from pinned suite')
        self.original_prompt = semantic_verifier_prompt(self.context)
        self.id = content_identifier('req', 'whetstone-logical-client-request-v1',
            [self.packet['job']['job_id'], 'verifier', 'phase1', 'semantic_verification',
             self.packet['creation']['transaction_id'], candidate_id])
        self.directory = 'rounds/client_requests/' + self.id
        self.candidate_directory = self.packet['creation']['candidate_path'].rsplit('/', 1)[0]
        # Only the exact former deterministic rendering is eligible for replay.
        # The existing journal checks still reject arbitrary prompt changes.
        original = self.read('original_prompt.txt')
        if original is not None:
            legacy = _semantic_verifier_prompt(self.context, include_coverage_bindings=False)
            if original == legacy.encode('utf-8'):
                self.original_prompt = legacy


    def load(self):
        return load_registered_semantic_context(self.store, admission=self.admission, candidate_id=self.candidate_id)

    def recheck(self):
        require(self.load().raw == self.context.raw, 'semantic request frozen context changed')

    def require_open(self):
        registry = registry_for_proposal_requests(self.store, load_inputs=self.admission.load_inputs,
                                                  validate_authority=self.admission.validate_authority)
        view = self.DecisionJournal(registry).inspect(self.candidate_id)
        require(view.decision is not None and not view.prepared and not view.decision['decision_final']
                and view.decision['deterministic_result'] == 'pass'
                and view.decision['candidate_disposition'] == 'CANDIDATE_UNVERIFIED',
                'semantic invocation requires a committed nonfinal candidate decision')

    def read(self, name):
        try:
            return self.store.read(self.directory + '/' + name)
        except FileNotFoundError:
            self.store.read_descriptor()
            return None

    def json(self, name, schema):
        raw = self.read(name)
        if raw is None:
            return None
        value = decode_json(raw)
        require(raw == canonical_json_bytes(value), 'noncanonical semantic request artifact', name)
        self.schemas.validate(value, schema)
        return value

    def listing(self, name=''):
        try:
            return self.store.list_directory(self.directory + ('/' + name if name else ''))
        except FileNotFoundError:
            self.store.read_descriptor()
            return ()

    def candidate_read(self, name):
        try:
            return self.store.read(self.candidate_directory + '/' + name)
        except FileNotFoundError:
            self.store.read_descriptor()
            return None

    def candidate_decisions(self):
        try:
            return self.store.list_directory(self.candidate_directory + '/semantic_decisions')
        except FileNotFoundError:
            self.store.read_descriptor()
            return ()

    def publish(self, token, name, value):
        return self.store.publish(token, self.directory + '/' + name, value)

    def check_transport(self, transport):
        self.schemas.validate(transport, 'vnext_semantic_request_transport_v1')
        require(transport['verifier'] == self.packet['review_configuration']['verifier'], 'semantic transport differs from pinned Verifier')
        require(transport['command'].strip() and transport['cwd'].strip(), 'semantic transport command or cwd is empty')
        expected = sha256_bytes(confined_file(CONTRACT_ROOT, 'schemas/semantic_verification_client_v2.codex.schema.json').read_bytes())
        require(transport['output_schema_hash'] == expected, 'semantic transport output schema differs')

    def header(self, transport):
        return {'schema_version': 'vnext-semantic-request-v1', 'request_id': self.id,
            **{key: self.packet['creation'][key] for key in ('job_id', 'transaction_id', 'candidate_id')},
            'role': 'verifier', 'phase': 'phase1', 'gate': 'semantic_verification',
            'context_hash': self.context.input_hash, 'creation_ref': self.packet['creation_ref'],
            'base_pointer': self.packet['base_pointer'], 'prompt_hash': sha256_bytes(self.original_prompt.encode()),
            'transport': deepcopy(transport), 'maximum_attempts': 2, 'maximum_shape_retries': 1}

    def prompt(self, previous):
        if previous and previous['classification'] == 'shape_invalid':
            return ('Correct only response JSON/schema shape under unchanged semantic inputs.\n'
                    'Previous shape errors:\n' + previous['error'] + '\n' + self.original_prompt)
        return self.original_prompt

    def outcome(self, attempt, classification, *, raw=None, result=None, error=None):
        value = {'schema_version': 'vnext-semantic-outcome-v1', 'request_id': self.id, 'attempt': attempt,
            'classification': classification, 'response_hash': sha256_bytes(raw) if raw is not None else None,
            'verification_hash': _hash(result.verification) if result is not None else None, 'error': error}
        self.schemas.validate(value, 'vnext_semantic_outcome_v1')
        return value

    def decode(self, attempt, raw):
        try:
            result = decode_semantic_response(raw, self.context)
        except SemanticShapeError as exc:
            return self.outcome(attempt, 'shape_invalid', raw=raw, error=str(exc)), None
        except ValueError as exc:
            return self.outcome(attempt, 'invalid_semantic', raw=raw, error=str(exc)), None
        return self.outcome(attempt, 'valid_semantic', raw=raw, result=result), result

    def marker(self, attempt, transport, previous):
        return {'schema_version': 'vnext-semantic-invocation-v1', 'request_id': self.id, 'attempt': attempt,
            'context_hash': self.context.input_hash, 'prompt_hash': sha256_bytes(self.prompt(previous).encode()),
            'transport': deepcopy(transport), 'previous_outcome_hash': _hash(previous) if previous else None,
            'reason': 'initial' if previous is None else ('shape_retry' if previous['classification'] == 'shape_invalid' else 'technical_continuation')}

    def receipt(self, result, outcomes):
        attempt = outcomes[-1]['attempt']
        value = {'schema_version': 'vnext-semantic-result-v1', 'request_id': self.id,
            'context_hash': self.context.input_hash, 'creation_ref': self.packet['creation_ref'],
            'verification': {'path': self.candidate_directory + '/semantic_verification.json', 'hash': _hash(result.verification)},
            'authority_request': result.verification['authority_decision_request'],
            'response': {'path': self.directory + f'/attempts/{attempt}/response.json', 'hash': outcomes[-1]['response_hash']},
            'verdict': result.verification['verdict']}
        self.schemas.validate(value, 'vnext_semantic_result_v1')
        return value

    def inspect(self):
        allowed = {'request.json', 'context.json', 'original_prompt.txt', 'attempts', 'result.json'}
        require(all(name.startswith('.vnext-tmp-') or (name in allowed and kind == ('directory' if name == 'attempts' else 'file'))
                    for name, kind in self.listing()), 'unknown semantic request artifact')
        header = self.json('request.json', 'vnext_semantic_request_v1')
        if header is None:
            require(not any(not name.startswith('.vnext-tmp-') for name, _ in self.listing()), 'semantic request evidence lacks its header')
            require(self.candidate_read('semantic_verification.json') is None and not self.candidate_decisions(),
                    'semantic result artifacts lack their durable request')
            return None, [], None, None
        self.check_transport(header['transport'])
        require(header == self.header(header['transport']), 'semantic request binding changed')
        for name, raw in [('context.json', self.context.raw), ('original_prompt.txt', self.original_prompt.encode())]:
            actual = self.read(name)
            require(actual is None or actual == raw, 'semantic request context or original prompt changed')
        require(all(name.startswith('.vnext-tmp-') or (name in {'1', '2'} and kind == 'directory')
                    for name, kind in self.listing('attempts')), 'unknown semantic attempt or allowance extension')
        outcomes = []
        result = None
        previous = None
        for attempt in (1, 2):
            prefix = f'attempts/{attempt}/'
            files = {'prompt.txt', 'invocation.json', 'response.json', 'outcome.json', 'telemetry.json'}
            require(all(name.startswith('.vnext-tmp-') or (name in files and kind == 'file')
                        for name, kind in self.listing(prefix.rstrip('/'))), 'unknown semantic attempt artifact')
            marker = self.json(prefix + 'invocation.json', 'vnext_semantic_invocation_v1')
            raw = self.read(prefix + 'response.json')
            stored = self.json(prefix + 'outcome.json', 'vnext_semantic_outcome_v1')
            actual_prompt = self.read(prefix + 'prompt.txt')
            require(actual_prompt is None or actual_prompt == self.prompt(previous).encode(), 'semantic attempt prompt changed')
            if marker is None:
                require(raw is None and stored is None and self.read(prefix + 'telemetry.json') is None,
                        'semantic response or outcome lacks invocation evidence')
                if attempt == 1:
                    require(not self.listing('attempts/2'), 'semantic invocation chain has a gap')
                break
            require(self.read('context.json') == self.context.raw and self.read('original_prompt.txt') == self.original_prompt.encode(),
                    'semantic invocation lacks bound context or original prompt')
            require(actual_prompt is not None, 'semantic invocation lacks bound prompt')
            self.check_transport(marker['transport'])
            require(_identity(marker['transport']) == _identity(header['transport']), 'semantic invocation transport identity changed')
            require(attempt != 1 or marker['transport'] == header['transport'], 'initial semantic transport differs from request claim')
            if previous:
                require(previous['classification'] in {'shape_invalid', 'timeout', 'transport_failure', 'interrupted'},
                        'semantic attempt reopens a closed result')
                require(self.read('attempts/1/outcome.json') is not None, 'semantic invocation lost its bound predecessor outcome')
            require(marker == self.marker(attempt, marker['transport'], previous), 'semantic invocation lineage changed')
            if raw is not None:
                expected, result = self.decode(attempt, raw)
            else:
                require(stored is None or (stored['classification'] in {'timeout', 'transport_failure', 'interrupted'}
                        and bool(stored['error']) and stored == self.outcome(attempt, stored['classification'], error=stored['error'])),
                        'semantic outcome lacks its response or technical cause')
                expected = stored or self.outcome(attempt, 'interrupted', error='Invocation has no durable response or completion record.')
            require(stored is None or stored == expected, 'semantic outcome contradicts exact response replay')
            outcomes.append(expected)
            previous = expected
        receipt = self.json('result.json', 'vnext_semantic_result_v1')
        retained = self.candidate_read('semantic_verification.json')
        require(retained is None or (result is not None and retained == canonical_json_bytes(result.verification)),
                'semantic verification lacks matching raw evidence')
        decisions = [(name, kind) for name, kind in self.candidate_decisions() if not name.startswith('.vnext-tmp-')]
        if result is None or result.authority_request is None:
            require(not decisions, 'semantic authority artifacts lack matching raw evidence')
        else:
            expected_id = result.authority_request['decision_id']
            require(all(name == expected_id and kind == 'directory' for name, kind in decisions),
                    'semantic authority artifacts contradict exact request')
            if decisions:
                path = self.candidate_directory + '/semantic_decisions/' + expected_id
                entries = self.store.list_directory(path)
                require(all(name.startswith('.vnext-tmp-') or (name == 'request.json' and kind == 'file') for name, kind in entries),
                        'unknown semantic authority artifact')
                retained_request = self.candidate_read('semantic_decisions/' + expected_id + '/request.json')
                require(retained_request is None or retained_request == canonical_json_bytes(result.authority_request),
                        'semantic authority request differs from raw evidence')
        if receipt is not None:
            require(result is not None and receipt == self.receipt(result, outcomes), 'semantic result receipt differs from decoded evidence')
            require(self.store.read(receipt['verification']['path']) == canonical_json_bytes(result.verification), 'retained semantic verification changed')
            if result.authority_request is not None:
                require(self.store.read(receipt['authority_request']['path']) == canonical_json_bytes(result.authority_request),
                        'retained semantic authority request changed')
        return header, outcomes, result, receipt

    def status(self, header, outcomes, result, receipt):
        if receipt is not None: status = 'complete'
        elif result is not None: status = 'valid_response'
        elif outcomes and outcomes[-1]['classification'] == 'invalid_semantic': status = 'invalid_semantic'
        elif len(outcomes) == 2: status = 'attempts_exhausted'
        elif outcomes: status = outcomes[-1]['classification']
        else: status = 'prepared' if header is not None else 'not_started'
        return SemanticRequestStatus(self.id, status, len(outcomes), result, deepcopy(receipt), deepcopy(outcomes[-1]) if outcomes else None)

    def synchronize(self, token, header, outcomes):
        self.recheck()
        # Creation dependencies were durable before its publication. Replaying
        # the exact visible event restores a lost creation acknowledgement.
        self.store.publish(token, self.packet['creation_ref']['path'], self.packet['creation'])
        self.publish(token, 'request.json', header)
        self.publish(token, 'context.json', self.context.raw)
        self.publish(token, 'original_prompt.txt', self.original_prompt.encode())
        for outcome in outcomes:
            prefix = f"attempts/{outcome['attempt']}/"
            for name in ('prompt.txt', 'invocation.json', 'response.json'):
                raw = self.read(prefix + name)
                if raw is not None: self.publish(token, prefix + name, raw)
            self.publish(token, prefix + 'outcome.json', outcome)

    def finish(self, token, result, outcomes):
        self.recheck()
        receipt = self.receipt(result, outcomes)
        if result.authority_request is not None:
            self.store.publish(token, receipt['authority_request']['path'], result.authority_request)
        self.store.publish(token, receipt['verification']['path'], result.verification)
        self.publish(token, 'result.json', receipt)
        return self.inspect()[3]


def inspect_semantic_request(store, *, admission, candidate_id):
    journal = SemanticRequestJournal(store, admission=admission, candidate_id=candidate_id)
    return journal.status(*journal.inspect())


def finish_semantic_request(store, *, admission, candidate_id):
    """Materialize a decoded result without accepting or constructing a client."""
    return _finish_semantic_request(store, admission=admission, candidate_id=candidate_id,
                                    journal_type=SemanticRequestJournal)


def _finish_semantic_request(store, *, admission, candidate_id, journal_type):
    with store.locked(admission.validate_authority) as token:
        journal = journal_type(store, admission=admission, candidate_id=candidate_id)
        header, outcomes, result, _ = journal.inspect()
        require(header is not None and result is not None, 'semantic materialization requires valid retained raw evidence')
        journal.synchronize(token, header, outcomes)
        journal.finish(token, result, outcomes)
        return journal.status(*journal.inspect())


def run_semantic_request(store, *, admission, candidate_id, client=None, continuation=False):
    return _run_semantic_request(store, admission=admission, candidate_id=candidate_id, client=client,
                                 continuation=continuation, journal_type=SemanticRequestJournal)


def _run_semantic_request(store, *, admission, candidate_id, client, continuation, journal_type):
    require(type(continuation) is bool, 'semantic continuation must be an explicit boolean')
    with store.locked(admission.validate_authority) as token:
        journal = journal_type(store, admission=admission, candidate_id=candidate_id)
        header, outcomes, result, receipt = journal.inspect()
        if result is not None:
            journal.synchronize(token, header, outcomes)
            journal.finish(token, result, outcomes)
            return journal.status(*journal.inspect())
        status = journal.status(header, outcomes, result, receipt)
        if status.status in {'invalid_semantic', 'attempts_exhausted'}:
            journal.synchronize(token, header, outcomes)
            return journal.status(*journal.inspect())
        if header is not None and not continuation:
            return SemanticRequestStatus(journal.id, 'continuation_required', len(outcomes), last_outcome=status.last_outcome)
        require(client is not None, 'semantic invocation requires a configured Verifier')
        transport = deepcopy(client.transport_binding)
        journal.check_transport(transport)
        require(client.identity == journal.packet['review_configuration']['verifier'], 'semantic client identity differs from pinned Verifier')
        if header is None:
            header = journal.header(transport)
        else:
            require(_identity(header['transport']) == _identity(transport), 'semantic continuation transport identity changed')
            require(outcomes or transport == header['transport'], 'uninvoked semantic request must retain its claimed timeout')
        journal.require_open()
        journal.synchronize(token, header, outcomes)
        while len(outcomes) < 2:
            previous = outcomes[-1] if outcomes else None
            attempt = len(outcomes) + 1
            journal.recheck()
            journal.require_open()
            require(client.transport_binding == transport, 'semantic transport changed before invocation')
            prompt = journal.prompt(previous)
            prefix = f'attempts/{attempt}/'
            journal.publish(token, prefix + 'prompt.txt', prompt.encode())
            journal.publish(token, prefix + 'invocation.json', journal.marker(attempt, transport, previous))
            raw = None
            failure = None
            try: raw = client.verify(prompt)
            except Exception as exc: failure = exc
            telemetry = getattr(client, 'last_telemetry', None)
            if telemetry is not None:
                journal.publish(token, prefix + 'telemetry.json', json.dumps(telemetry, sort_keys=True).encode())
            if failure is not None:
                outcome = journal.outcome(attempt, 'timeout' if isinstance(failure, TimeoutError) else 'transport_failure',
                                          error=type(failure).__name__ + ': ' + str(failure))
                journal.publish(token, prefix + 'outcome.json', outcome)
                return journal.status(*journal.inspect())
            require(isinstance(raw, bytes), 'semantic transport must return exact bytes')
            journal.publish(token, prefix + 'response.json', raw)
            journal.recheck()
            journal.require_open()
            require(client.transport_binding == transport, 'semantic transport changed during invocation')
            outcome, result = journal.decode(attempt, raw)
            journal.publish(token, prefix + 'outcome.json', outcome)
            outcomes.append(outcome)
            if result is not None:
                journal.finish(token, result, outcomes)
                return journal.status(*journal.inspect())
            if outcome['classification'] == 'invalid_semantic':
                return journal.status(*journal.inspect())
        return journal.status(*journal.inspect())
