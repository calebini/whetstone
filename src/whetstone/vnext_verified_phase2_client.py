"""One pinned Phase 2 request journal; no candidate or scheduler advancement."""
from copy import deepcopy

from whetstone.clients import canonicalize_reviewer_input
from whetstone.live import _reject_reviewer_process_failure_feedback
from whetstone.oscillation import canonicalize_phase2_feedback
from whetstone.vnext_contracts import (CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes,
    confined_file, content_identifier, decode_json, require, sha256_bytes)
from whetstone.vnext_review_protocol import ReviewPreflight, ReviewShapeError
from whetstone.vnext_review_requests import _Request, _drive_request, _result
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_review import _FirstReview, REQUEST_PATH, SCHEMA, RESPONSE_SCHEMA, DIRECTORY
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_work import VerifiedWork

ALGORITHM = 'algorithms/vnext_verified_phase2_client_v1.md'
RESULT_SCHEMA = 'vnext_phase2_review_result_v1'
JOURNAL_PATH = DIRECTORY + '/execution'
SCHEMAS = {RESULT_SCHEMA, 'phase2_reviewer_feedback', 'vnext_review_invocation_v1', 'vnext_review_outcome_v1'}


class _Journal(_Request):
    def __init__(self, owner, proof, store, bound):
        self.owner, self.proof, self.store, self.bound = owner, proof, store, bound
        self.schemas = VNextSchemaRegistry()
        self.number, self.profile = bound.request['round_number'], bound.request['step']['profile']
        self.id = content_identifier('req', 'whetstone-phase2-review-request-v1', [bound.request_ref])
        self.index_path = bound.request_ref['path']
        self.directory = self.index_path.rsplit('/', 1)[0] + '/execution'
        self.feedback_path = self.directory + '/reviewer_feedback.json'
        self.preflight = ReviewPreflight(bound.request_ref['hash'],
            dict(job=deepcopy(bound.inputs['job']), review=deepcopy(bound.inputs['configuration'])), bound.prompt)
        self.successful_attempt = None

    def recheck(self):
        require(self.owner._committed_request(self.proof) == self.bound, 'Phase 2 Reviewer frozen request changed')

    def header(self, transport, previous):
        require(previous is None and transport == self.bound.request['transport'],
                'Phase 2 Reviewer transport differs from immutable request')
        return deepcopy(self.bound.request)

    def decode_review(self, raw):
        annotations = None
        classifications = None
        try:
            packet = decode_json(raw)
            require(isinstance(packet, dict), 'Phase 2 Reviewer response must be an object')
            if 'rubric_catalogue' in self.bound.inputs:
                from whetstone.vnext_phase2_rubric import RESPONSE_SCHEMA as rubric_schema, pins as rubric_pins
                rubric_pins(self.proof.reader.suite)
                from whetstone.vnext_phase2_reviewer_advice import supported as advice_supported, pins as advice_pins
                if advice_supported(self.proof.reader.suite):
                    from whetstone.vnext_phase2_reviewer_advice import RESPONSE_SCHEMA as rubric_schema
                    advice_pins(self.proof.reader.suite)
                self.schemas.validate(packet, rubric_schema)
                if advice_supported(self.proof.reader.suite): classifications = packet['classifications']
                annotations = packet['rubric_findings'];packet = packet['review']
        except ValueError as exc:
            raise ReviewShapeError(str(exc)) from exc
        expected = dict(round_number=self.number, profile=self.profile,
            draft_hash=sha256_bytes(self.bound.inputs['draft'].encode('utf-8')),
            reviewer=self.bound.inputs['configuration']['reviewer'])
        for key, value in expected.items():
            if key in packet:
                require(packet[key] == value, 'Phase 2 Reviewer response contradicts request', key)
        try:
            _reject_reviewer_process_failure_feedback(packet)
            self.schemas.validate(packet, RESPONSE_SCHEMA)
        except (ValueError, TypeError) as exc:
            raise ReviewShapeError(str(exc)) from exc
        packet = canonicalize_reviewer_input(packet)
        sections = [row['canonical_section_id'] for row in self.bound.inputs['base_map']['sections']]
        if self.bound.request['schema_version'] in {'vnext-phase2-review-request-v3', 'vnext-phase2-review-request-v4', 'vnext-phase2-review-request-v5', 'vnext-phase2-review-request-v6'}:
            from whetstone.declaration import DECLARATION_ARTIFACTS
            sections += sorted(DECLARATION_ARTIFACTS | {'target-matrix-precedence'})
        packet = canonicalize_phase2_feedback(packet, sections)
        ids = [item['feedback_id'] for item in packet['feedback']]
        require(len(ids) == len(set(ids)), 'Phase 2 Reviewer repeats a feedback ID')
        self.schemas.validate(packet, 'phase2_reviewer_feedback')
        result = dict(feedback=packet)
        if classifications is not None:
            from whetstone.vnext_phase2_reviewer_advice import bind
            # Structurally valid contradictory authority remains invalid_review;
            # missing/extra response fields use the existing shape retry policy.
            result['advice'] = bind(self.proof.reader.suite, self.bound.inputs, packet,
                                    self.feedback_path, classifications)
        if annotations is not None:
            from whetstone.vnext_phase2_rubric import attribute
            try:
                result['rubric_findings'] = attribute(annotations, packet, self.bound.inputs['rubric'].encode(),
                    [row['canonical_section_id'] for row in self.bound.inputs['base_map']['sections']],
                    target_phase=self.bound.inputs['configuration']['target_phase'])
            except (ValueError, TypeError, KeyError) as exc:
                raise ReviewShapeError(str(exc)) from exc
        return result

    def decode(self, attempt, raw):
        outcome, review = super().decode(attempt, raw)
        if review is not None: self.successful_attempt = attempt
        return outcome, review

    def receipt(self, review):
        attempt = self.successful_attempt
        require(attempt in (1, 2), 'Phase 2 result requires a validated invocation')
        raw = self.read(f'attempts/{attempt}/response.json')
        require(raw is not None, 'Phase 2 result requires retained response bytes')
        outcome = self.outcome(attempt, 'valid_review', raw, review=review)
        return dict(schema_version='vnext-phase2-review-result-v1', request_id=self.id,
            request=deepcopy(self.bound.request_ref), input_hash=self.preflight.input_hash, attempt=attempt,
            response=dict(path=self.directory+f'/attempts/{attempt}/response.json', hash=sha256_bytes(raw)),
            outcome=_ref(self.directory+f'/attempts/{attempt}/outcome.json', outcome),
            feedback=_ref(self.feedback_path, review['feedback']), accepted_passes=1)

    def inspect(self, header):
        require(header == self.bound.request, 'Phase 2 journal lacks its committed request')
        try: entries = self.store.list_directory(self.directory+'/attempts')
        except FileNotFoundError: entries = ()
        require(all(name.startswith('.vnext-tmp-') or (name in {'1','2'} and kind=='directory')
                    for name,kind in entries), 'unknown Phase 2 Reviewer attempt or budget extension')
        original = self.read('original_prompt.txt')
        require(original is None or original == self.preflight.prompt.encode(), 'Phase 2 original prompt changed')
        outcomes, review, previous = [], None, None
        for attempt in (1, 2):
            prefix = f'attempts/{attempt}/'
            marker = self.packet(prefix+'invocation.json', 'vnext_review_invocation_v1')
            raw = self.read(prefix+'response.json')
            stored = self.packet(prefix+'outcome.json', 'vnext_review_outcome_v1')
            require(stored is None or (stored['request_id']==self.id and stored['attempt']==attempt),
                    'Phase 2 outcome binding differs')
            if marker is None:
                require(raw is None and stored is None and self.read(prefix+'telemetry.json') is None,
                        'Phase 2 response/outcome lacks invocation')
                pending_prompt = self.read(prefix+'prompt.txt')
                require(pending_prompt is None or (previous is None or previous['classification'] not in {'valid_review','invalid_review'})
                        and pending_prompt == self.prompt(previous).encode(), 'Phase 2 pending prompt conflicts')
                if attempt == 1:
                    require(not any(self.read('attempts/2/'+name) is not None for name in
                        ('invocation.json','response.json','outcome.json','telemetry.json','prompt.txt')),
                        'Phase 2 second attempt lacks first invocation')
                break
            require(original is not None, 'Phase 2 invocation lacks original prompt')
            require(previous is None or previous['classification'] not in {'valid_review','invalid_review'},
                    'closed Phase 2 outcome cannot be retried')
            require(marker['request_id']==self.id and marker['attempt']==attempt
                    and marker['input_hash']==self.preflight.input_hash
                    and marker['transport']==header['transport'], 'Phase 2 invocation binding differs')
            require(marker['previous_outcome_hash']==(sha256_bytes(canonical_json_bytes(previous)) if previous else None),
                    'Phase 2 predecessor outcome differs')
            reason = 'initial' if previous is None else 'shape_retry' if previous['classification']=='shape_invalid' else 'technical_continuation'
            prompt = self.prompt(previous).encode()
            require(marker['reason']==reason and marker['prompt_hash']==sha256_bytes(prompt)
                    and self.read(prefix+'prompt.txt')==prompt, 'Phase 2 invocation prompt or reason differs')
            if attempt == 2:
                require(self.read('attempts/1/outcome.json') is not None, 'Phase 2 predecessor outcome is missing')
            if raw is not None: expected, review = self.decode(attempt, raw)
            else:
                require(stored is None or (stored['classification'] in {'timeout','transport_failure','interrupted'}
                    and stored['response_hash'] is None and stored['review_hash'] is None and bool(stored['error'])),
                    'Phase 2 no-response outcome contradicts evidence')
                expected = stored or self.outcome(attempt, 'interrupted', error='Invocation has no durable response or failure outcome.')
            require(stored is None or stored==expected, 'Phase 2 outcome differs from exact response replay')
            outcomes.append(expected)
            previous = expected
        receipt = self.packet('result.json', RESULT_SCHEMA)
        feedback = self.read('reviewer_feedback.json')
        require(feedback is None or (review is not None and feedback==canonical_json_bytes(review['feedback'])),
                'Phase 2 canonical feedback lacks matching response')
        if receipt is not None:
            require(review is not None and receipt==self.receipt(review) and feedback is not None,
                    'Phase 2 receipt differs from validated evidence')
            for key in ('response', 'outcome'):
                reference=receipt[key]
                require(sha256_bytes(self.store.read(reference['path']))==reference['hash'], 'Phase 2 receipt dependency differs')
        return outcomes, review, receipt

    def finish(self, token, review):
        self.recheck()
        self.store.publish(token, self.feedback_path, review['feedback'])
        receipt = self.receipt(review)
        self.schemas.validate(receipt, RESULT_SCHEMA)
        self.store.publish(token, self.directory+'/result.json', receipt)
        self.recheck()
        return receipt


class _Client(_FirstReview):
    def _proof(self, read):
        proof=super()._proof(read)
        pins={row['path']:row for family in ('algorithms','schemas') for row in proof.reader.suite.manifest[family]}
        paths={ALGORITHM} | {'schemas/'+name+'.schema.json' for name in SCHEMAS}
        require(paths <= pins.keys(), 'Phase 2 client contracts are outside supported suite')
        for path in paths:
            require(sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes())==pins[path]['sha256'],
                    'installed Phase 2 client contract differs from pinned suite', path)
        return proof

    def _committed_request(self, proof):
        raw=self._optional(REQUEST_PATH)
        require(raw is not None, 'Phase 2 client requires a committed Reviewer request')
        from whetstone.vnext_phase2_targets import supported as target_supported
        schema='vnext_phase2_review_request_v6' if target_supported(proof.reader.suite) else SCHEMA
        request=proof.reader.json(dict(path=REQUEST_PATH,hash=sha256_bytes(raw)),schema)
        bound=self._build_review(proof,request['transport'])
        require(bound.committed, 'Phase 2 client requires complete request dependencies')
        return bound

    def _synchronize_request(self, store, proof, bound):
        self._synchronize_entry_sources(store,proof,self._committed_binding(proof))
        references=bound.inputs['sources']+[bound.request['entry'],bound.request['inputs'],bound.request['prompt'],bound.request_ref]
        if bound.inputs['declaration'] is not None:
            context=bound.inputs['declaration']
            references += [context['binding']]+[row['reference'] for row in context['artifacts'].values()]
        for ref in references:
            raw=proof.reader.raw(ref)
            if ref != self.run._record['descriptor']:
                self.store.synchronize_existing(store._token,ref['path'],expected=raw)
        self.store.synchronize_existing(store._token,STATE_PATH,expected=self.store.read(STATE_PATH))
        require(self._committed_request(proof)==bound, 'Phase 2 request changed during source barriers')

    def status(self):
        proof=self._proof(self.store.read)
        work=VerifiedWork._observe(self,proof)
        if work.outcome!='work_available': return work
        bound=self._committed_request(proof)
        journal=_Journal(self,proof,self.store,bound)
        outcomes,review,receipt=journal.inspect(bound.request)
        status=('complete' if receipt else 'valid_response' if review else
                'invalid_review' if outcomes and outcomes[-1]['classification']=='invalid_review' else
                'attempts_exhausted' if len(outcomes)==2 else outcomes[-1]['classification'] if outcomes else 'prepared')
        journal.recheck()
        return _result(status,journal,outcomes,review,receipt)

    def execute(self, *, client=None, continuation=False):
        require(type(continuation) is bool, 'Phase 2 continuation must be an explicit boolean')
        def perform(store,proof):
            bound=self._committed_request(proof)
            journal=_Journal(self,proof,store,bound)
            outcomes,review,receipt=journal.inspect(bound.request)
            self._synchronize_request(store,proof,bound)
            journal.synchronize(store._token,bound.request,outcomes)
            if receipt is not None:
                require(not continuation, 'completed Phase 2 request is not technical continuation')
                return _result('complete',journal,outcomes,review,journal.finish(store._token,review))
            if review is None and outcomes and (outcomes[-1]['classification']=='invalid_review' or len(outcomes)==2):
                return _result('invalid_review' if outcomes[-1]['classification']=='invalid_review' else 'attempts_exhausted',journal,outcomes)
            if outcomes and not continuation:
                return _result('continuation_required',journal,outcomes,review)
            require(outcomes or not continuation, 'unstarted Phase 2 request is not technical continuation')
            if review is not None:
                return _result('complete',journal,outcomes,review,journal.finish(store._token,review))
            require(client is not None, 'Phase 2 invocation requires an explicit raw-response client')
            result=_drive_request(journal,store._token,header=bound.request,outcomes=outcomes,review=review,
                previous=None,client=client,continuation=True)
            journal.recheck()
            journal.inspect(bound.request)
            return result
        return self._execute(perform)


def run_phase2_review(run, *, client=None, continuation=False):
    from whetstone.vnext_verified_phase2_failure import supported, _Failure
    owner=_Client(run)
    if supported(owner._proof(owner.store.read)):
        return _Failure(run).execute_review(1,client=client,continuation=continuation)
    return owner.execute(client=client,continuation=continuation)


def phase2_review_status(run):
    return _Client(run).status()
