"""First Phase 2 Reviewer request publication; no invocation or scheduler advance."""
from copy import deepcopy
from dataclasses import dataclass

from whetstone.prompts import render_reviewer_prompt
from whetstone.vocabulary import controlled_vocabulary_packet
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_entry import _Entry
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_work import VerifiedWork

ALGORITHM = 'algorithms/vnext_verified_phase2_review_v1.md'
SCHEMA = 'vnext_phase2_review_request_v1'
RESPONSE_SCHEMA = 'phase2_reviewer_feedback_input'
SCHEMAS = {SCHEMA, RESPONSE_SCHEMA, 'reviewer_feedback', 'common', 'controlled_vocabulary',
           'vnext_review_request_transport_v1', 'review_configuration_v1'}
DIRECTORY = 'rounds/phase2/review_requests/first'
REQUEST_PATH = DIRECTORY + '/request.json'
INPUT_PATH = DIRECTORY + '/inputs.json'
PROMPT_PATH = DIRECTORY + '/prompt.txt'
VOCABULARY_HASH = 'ed361ca15a34bf4d10e2703b4a82088718bc71b0b23fee1ddbc019b38a77ec86'


@dataclass(frozen=True)
class Phase2ReviewRequest:
    request: dict
    request_ref: dict
    inputs: dict
    prompt: str
    pending_paths: tuple
    committed: bool
    execution_permitted: bool = False
    resume_permitted: bool = False
    apply_back_permitted: bool = False


class _FirstReview(_Entry):
    def _proof(self, read):
        proof = super()._proof(read)
        pins = {row['path']: row for family in ('algorithms', 'schemas') for row in proof.reader.suite.manifest[family]}
        paths = {ALGORITHM} | {'schemas/' + name + '.schema.json' for name in SCHEMAS}
        require(paths <= pins.keys(), 'Phase 2 Reviewer request contracts are outside supported suite')
        for path in paths:
            require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == pins[path]['sha256'],
                    'installed Phase 2 Reviewer request contract differs from pinned suite', path)
        return proof

    def _build_review(self, proof, transport):
        binding = self._committed_binding(proof)
        entry = self._entry_view(proof, binding)
        require(entry.committed and entry.state_current, 'Phase 2 Reviewer requires committed entry and recovered state')
        closeout = proof.reader.json(entry.entry['phase1_closeout'], 'vnext_verified_phase1_closeout_v1')
        number = max(row['round_number'] for row in closeout['review_receipts']) + 1
        config = binding.configuration
        step = dict(index=1, profile=config['profiles'][0]['name'], round_budget=config['profiles'][0]['budget'],
                    rounds_used=0, pass_number=1)
        return self._render_review(proof, transport, binding, entry, number, step)

    def _render_review(self, proof, transport, binding, entry, number, step, *, directory=DIRECTORY,
                       previous_consumption=None):
        # Internal renderer only. The selecting owner must prove the base and schedule.
        config = binding.configuration
        schema = SCHEMA if previous_consumption is None else 'vnext_phase2_review_request_v2'
        input_path, prompt_path, request_path = (directory+'/'+name for name in ('inputs.json','prompt.txt','request.json'))
        proof.reader.suite.registry.validate(transport, 'vnext_review_request_transport_v1')
        schemas = {name: dict(path='schemas/' + name + '.schema.json',
            hash=sha256_bytes(confined_file(CONTRACT_ROOT, 'schemas/' + name + '.schema.json').read_bytes()))
            for name in sorted(SCHEMAS)}
        require(transport['reviewer'] == config['reviewer'], 'Phase 2 Reviewer transport changes pinned role')
        require(transport['output_schema_hash'] == schemas[RESPONSE_SCHEMA]['hash'],
                'Phase 2 Reviewer transport output schema differs')
        vocabulary = controlled_vocabulary_packet()
        proof.reader.suite.registry.validate(vocabulary, 'controlled_vocabulary')
        require(sha256_bytes(canonical_json_bytes(vocabulary)) == VOCABULARY_HASH,
                'Phase 2 Reviewer vocabulary differs from supported version')
        values = proof.values(proof.latest)
        references = [deepcopy(self.run._record[key]) for key in ('descriptor', 'review_configuration', 'seed_section_map')]
        references.append(deepcopy(values['job']['seed_draft']))
        for key in ('authority_map', 'protected_invariants', 'scope_contract'):
            if values['job'][key + '_hash']:
                references.append(dict(path=values['job'][key + '_path'], hash=values['job'][key + '_hash']))
        context = []
        for row in values['authority']['bindings']:
            if row['role'] in {'mutable_target', 'excluded'}: continue
            reference = dict(path=row['path'], hash=row['content_hash'])
            references.append(reference)
            context.append(dict(binding=deepcopy(row), content=proof.reader.raw(reference).decode('utf-8')))
        for reference in references: proof.reader.raw(reference)
        inputs = dict(schema_version='vnext-phase2-review-inputs-v1', phase='phase_2',
            suite_digest=proof.reader.suite.digest, entry=entry.entry, configuration=config,
            round_number=number, step=step, vocabulary=vocabulary, response_schemas=schemas,
            sources=references, context=context, declaration=None,
            **{key:deepcopy(values[key]) for key in ('job', 'authority', 'invariants', 'scope', 'base_map', 'seed_map')},
            draft=values['base'].decode('utf-8'), seed=values['seed'].decode('utf-8'),
            rubric=proof.reader.raw(config['rubric']['artifact']).decode('utf-8'))
        if previous_consumption is not None:
            inputs.update(schema_version='vnext-phase2-review-inputs-v2', previous_consumption=deepcopy(previous_consumption),
                current_verified_draft=dict(path=proof.pointers[-1]['verified_draft_path'], hash=sha256_bytes(values['base'])))
        prompt = render_reviewer_prompt(profile=step['profile'], draft=inputs['draft'], rubric=inputs['rubric'],
            phase='phase_2', section_ids=[row['canonical_section_id'] for row in values['base_map']['sections']],
            round_number=number, draft_hash_value=sha256_bytes(values['base']))
        prompt += '\nAll bound inputs are embedded below. Preserve their declared authority and scope; excluded sources are unavailable.\n'
        prompt += 'Use the exact configured Reviewer identity. Return Phase 2 feedback only; no declaration review is active.\n'
        prompt += canonical_json_bytes(inputs).decode('utf-8')
        request = dict(schema_version=schema.replace('_','-'), phase='phase_2',
            job_id=config['job_id'], entry=entry.entry_ref, configuration=binding.configuration_ref,
            base_pointer=deepcopy(proof.latest), round_number=number, step=step, transport=deepcopy(transport),
            response_schema=schemas[RESPONSE_SCHEMA], inputs=_ref(input_path, inputs),
            prompt=dict(path=prompt_path, hash=sha256_bytes(prompt.encode('utf-8'))))
        if previous_consumption is not None: request['previous_consumption'] = deepcopy(previous_consumption)
        proof.reader.suite.registry.validate(request, schema)
        expected = ((input_path, canonical_json_bytes(inputs)), (prompt_path, prompt.encode('utf-8')),
                    (request_path, canonical_json_bytes(request)))
        pending = []
        for path, raw in expected:
            existing = self._optional(path)
            require(existing is None or existing == raw, 'Phase 2 Reviewer request conflicts with frozen inputs', path)
            if existing is None: pending.append(path)
        committed = request_path not in pending
        require(not committed or not pending, 'committed Phase 2 Reviewer request is missing its dependencies')
        proof.guard(self.store.read)
        self.run._guard(self.store.read)
        return Phase2ReviewRequest(request, _ref(request_path, request), inputs, prompt, tuple(pending), committed)

    def prepare_review(self, transport):
        proof = self._proof(self.store.read)
        work = VerifiedWork._observe(self, proof)
        if work.outcome != 'work_available': return work
        return self._build_review(proof, deepcopy(transport))

    def bind_review(self, transport):
        transport = deepcopy(transport)
        def publish(store, proof):
            expected = self._build_review(proof, transport)
            binding = self._committed_binding(proof)
            self._synchronize_entry_sources(store, proof, binding)
            for reference in expected.inputs['sources'] + [expected.request['entry']]:
                # Descriptor durability belongs to storage initialization; consumer
                # synchronization cannot touch storage control artifacts.
                if reference == self.run._record['descriptor']:
                    proof.reader.raw(reference)
                    continue
                self.store.synchronize_existing(store._token, reference['path'], expected=proof.reader.raw(reference))
            state_raw = self.store.read(STATE_PATH)
            self.store.synchronize_existing(store._token, STATE_PATH, expected=state_raw)
            require(self._build_review(proof, transport) == expected, 'Phase 2 Reviewer inputs changed during source synchronization')
            # Dependencies precede the commit. Visible prefixes repeat every barrier.
            store.publish(store._token, INPUT_PATH, expected.inputs)
            store.publish(store._token, PROMPT_PATH, expected.prompt.encode('utf-8'))
            checked = self._build_review(proof, transport)
            require(checked.request == expected.request, 'Phase 2 Reviewer request changed before commit')
            store.publish(store._token, REQUEST_PATH, expected.request)
            result = self._build_review(proof, transport)
            require(result.committed, 'Phase 2 Reviewer request publication incomplete')
            return result
        return self._execute(publish)


def prepare_phase2_review(run, transport):
    return _FirstReview(run).prepare_review(transport)


def bind_phase2_review(run, transport):
    return _FirstReview(run).bind_review(transport)
