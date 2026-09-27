"""Explicit Phase 2 choices bound to existing unit-decision contracts."""
from copy import deepcopy
import re
from types import SimpleNamespace

from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_identity import response_id
from whetstone.vnext_operator_decisions import (
    _binding, _directory, _entries, _read_request, _request_arguments, _request_path, _response_path,
    _selection_ref, _validate_receipt,
)
from whetstone.vnext_phase2_operator import pins
from whetstone.vnext_proposal_run import round_input_path
from whetstone.vnext_unit_authorization import bind_unit_response, unit_decision_request
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_round import _constraints
from whetstone.vnext_verified_phase2_sequence import _Continuation, sequence

SCHEMAS = ('vnext_operator_options_v1', 'vnext_operator_response_input_v1', 'vnext_operator_selection_v1')


def admission_preflight(proof, bound, binding, decisions):
    """Reproduce derived work without changing the original classification."""
    pins(proof.reader.suite)
    values = proof.values(bound.request['base_pointer'])
    values.update(feedback=proof.reader.json(binding['feedback'], 'phase2_reviewer_feedback'),
        feedback_ref=binding['feedback'], advice=proof.reader.json(binding['advice'], 'vnext_finding_advice_v1'),
        constraints=_constraints(proof), phase2=dict(configuration=deepcopy(bound.inputs['configuration']),
        request=deepcopy(bound.request)), context={b['binding_id']: proof.reader.raw(dict(path=b['path'], hash=b['content_hash']))
            for b in values['authority']['bindings'] if b['role'] not in {'mutable_target', 'excluded'}})
    if 'rubric_catalogue' in bound.inputs:
        from whetstone.vnext_phase2_rubric import proposal_context
        from whetstone.vnext_verified_phase2_client import _Journal
        from types import SimpleNamespace
        journal = _Journal(SimpleNamespace(),proof,proof.store,bound)
        receipt = proof.reader.json(binding['result'],'vnext_phase2_review_result_v1')
        review_result = journal.decode_review(proof.reader.raw(receipt['response']))
        values['phase2'] = proposal_context(bound,review_result)
    require(len({r['finding_id'] for r in decisions}) == len(decisions), 'duplicate Phase 2 finding decisions')
    require(all(r['finding_id'] in binding['evidence'] for r in decisions), 'unknown Phase 2 finding decision')
    values['decisions'] = [dict(finding_id=r['finding_id'], feedback_refs=binding['evidence'][r['finding_id']]['feedback_refs'],
        request=proof.reader.json(r['request'], 'vnext_mutation_decision_request_v2'),
        response=proof.reader.json(r['response'], 'operator_decision_response_v1')) for r in decisions]
    return prepare_unit_preflight(**values)


class Phase2Operator(_Continuation):
    def _proof(self, read):
        proof = super()._proof(read)
        pins(proof.reader.suite)
        entries = {r['path']: r['sha256'] for r in proof.reader.suite.manifest['schemas']}
        from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file
        for name in SCHEMAS:
            path = 'schemas/'+name+'.schema.json'
            require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                    'Phase 2 operator schema is absent or changed', path)
        return proof

    def _context(self, proof):
        state = sequence(proof)
        require(state['gate'] in {'operator_or_advice_required', 'correction_required'},
                'Phase 2 operator work is blocked by the current sequence gate')
        frame = state['frames'][-1]; owner = frame['owner']; bound = frame['bound']
        require(bound.request['base_pointer'] == proof.latest, 'Phase 2 operator review is stale')
        binding = owner._advice_view(owner.proof, None)[-1]
        require(binding['status'] == 'bound', 'Phase 2 operator work requires committed finding advice')
        binding = binding['binding']
        values = proof.values(proof.latest)
        inventory = values.get('base_inventory')
        if inventory is None:
            from whetstone.vnext_discovery import discovery_rules
            from whetstone.vnext_inventory import seed_inventory
            inventory = seed_inventory(values['base'], values['base_map'], values['job'], rules=discovery_rules(values['invariants']))
        step = SimpleNamespace(round_number=owner.number, review=dict(findings=binding['findings'], evidence=binding['evidence']))
        context = (proof.reader, values, step, inventory, binding['result'])
        return state, frame, binding, context

    def _unadmitted(self, frame):
        require(self._optional(round_input_path(frame['owner'].number)) is None,
                'operator choice cannot alter an admitted Phase 2 round; use a distinct transaction')

    def _synchronize(self, store, proof, frame, binding):
        owner = frame['owner']
        owner._synchronize_request(store, owner.proof, frame['bound'])
        frame['journal'].synchronize(store._token, frame['bound'].request, frame['outcomes'])
        for ref in (binding['result'], binding['consumption'], binding['feedback'], binding['advice'],
                    _ref(owner.binding_path, binding)):
            self.store.synchronize_existing(store._token, ref['path'], expected=proof.reader.raw(ref))

    def context(self):
        proof = self._proof(self.store.read); work = self._observe(proof)
        if work.outcome != 'work_available': return work
        state, frame, binding, context = self._context(proof)
        _, values, step, inventory, result = context
        retained = self._retained(context)
        proof.guard(self.store.read)
        return dict(job_id=values['job']['job_id'], round_number=step.round_number, review_result=deepcopy(result),
            base_pointer=deepcopy(proof.latest), inventory=deepcopy(inventory), section_map=deepcopy(values['base_map']),
            findings=deepcopy(step.review['findings']), evidence=deepcopy(step.review['evidence']),
            gate=state['gate'], admitted=self._optional(round_input_path(step.round_number)) is not None,
            next_review_authorized=False, phase_complete=False,
            resume=dict(permitted=False, next_gate=None, reason='operator_selection_is_not_technical_resume'), **retained)

    def _retained(self, context):
        """Expose every validated choice; enumeration never selects consent."""
        reader, values, step, inventory, _ = context
        number = step.round_number; requests = []; selections = []
        for name, kind in _entries(self.run, _directory(number)):
            require(kind == 'directory', 'invalid Phase 2 operator directory')
            if name == 'selections':
                for leaf, leaf_kind in _entries(self.run, _directory(number)+'/selections'):
                    require(leaf_kind == 'file' and re.fullmatch(r'selection-[0-9a-f]{64}\.json', leaf), 'invalid operator selection entry')
                    path = _directory(number)+'/selections/'+leaf
                    ref = dict(path=path, hash=sha256_bytes(self.store.read(path)))
                    packet = reader.json(ref, 'vnext_operator_selection_v1')
                    require(ref == _selection_ref(number, packet), 'operator selection identity differs')
                    _validate_receipt(self.run, packet, context); selections.append(ref)
                continue
            require(re.fullmatch(r'decision_[0-9a-f]{64}', name), 'invalid operator request directory')
            for leaf, leaf_kind in _entries(self.run, _directory(number)+'/'+name):
                require((leaf, leaf_kind) in {('request.json','file'), ('responses','directory')}, 'invalid operator request artifact')
            path = _request_path(number, name); ref = dict(path=path, hash=sha256_bytes(self.store.read(path)))
            request, arguments = _read_request(reader, values, step, inventory, ref, number)
            answers = []
            for leaf, leaf_kind in _entries(self.run, _directory(number)+'/'+name+'/responses'):
                require(leaf_kind == 'file' and re.fullmatch(r'resp_[0-9a-f]{64}\.json', leaf), 'invalid operator response entry')
                path = _directory(number)+'/'+name+'/responses/'+leaf
                response_ref = dict(path=path, hash=sha256_bytes(self.store.read(path)))
                response = reader.json(response_ref, 'operator_decision_response_v1')
                bind_unit_response(response, request, suite=reader.suite, **arguments)
                require(response_ref == _ref(_response_path(number, name, response['response_id']), response), 'operator response identity differs')
                answers.append(response_ref)
            requests.append(dict(finding_id=request['finding_id'], request=ref, responses=sorted(answers, key=lambda r:r['path'])))
        return dict(requests=sorted(requests, key=lambda r:r['request']['path']), selections=sorted(selections, key=lambda r:r['path']),
            requires_new_job=sorted(key for key, row in step.review['evidence'].items() if row['requires_new_job']))

    def _requests(self, proof, packet, context):
        reader, values, step, inventory, result = context
        reader.suite.registry.validate(packet, 'vnext_operator_options_v1')
        _binding(packet, values, result, step.round_number)
        keys = [r['finding_id'] for r in packet['choices']]
        require(len(keys) == len(set(keys)), 'duplicate Phase 2 finding options')
        requests = []
        for choice in packet['choices']:
            require(all(o['description'].strip() for o in choice['options']), 'operator option requires a concrete description')
            request = unit_decision_request(options=choice['options'],
                **_request_arguments(values, step, inventory, choice['finding_id']))
            requests.append(dict(request=_ref(_request_path(step.round_number, request['decision_id']), request), content=request))
        return sorted(requests, key=lambda r:r['request']['path'])

    def _responses(self, proof, packet, context):
        reader, values, step, inventory, result = context
        reader.suite.registry.validate(packet, 'vnext_operator_response_input_v1')
        number = step.round_number
        _binding(packet, values, result, number)
        records = []; responses = []
        for choice in packet['selections']:
            request, arguments = _read_request(reader, values, step, inventory, choice['request'], number)
            option = next((r for r in request['options'] if r['option_id'] == choice['selected_option_id']), None)
            require(option is not None, 'operator selected an unknown option')
            response = dict(schema_version='operator-decision-response-v1', job_id=values['job']['job_id'], response_id='',
                decision_id=request['decision_id'], decision_request_hash=choice['request']['hash'],
                base_draft_hash=request['base_draft_hash'], authority_map_hash=request['authority_map_hash'],
                scope_contract_hash=request['scope_contract_hash'], selected_option_id=choice['selected_option_id'],
                authorized_effects=deepcopy(option['authorized_effects']),
                authorized_deletion_unit_ids=deepcopy(option['authorized_deletion_unit_ids']),
                **{k:choice[k] for k in ('rationale', 'decided_by', 'decided_at')})
            response['response_id'] = response_id(response)
            bind_unit_response(response, request, suite=reader.suite, **arguments)
            reference = _ref(_response_path(number, request['decision_id'], response['response_id']), response)
            old = self._optional(reference['path'])
            require(old is None or old == canonical_json_bytes(response), 'operator response identity already has different bytes')
            records.append(dict(finding_id=request['finding_id'], request=deepcopy(choice['request']), response=reference))
            responses.append(dict(response=reference, content=response))
        keys = [r['finding_id'] for r in records]
        require(len(keys) == len(set(keys)), 'multiple selections for one finding')
        receipt = dict(schema_version='vnext-operator-selection-v1', job_id=values['job']['job_id'], round_number=number,
            review_result=deepcopy(result), base_pointer=deepcopy(values['base_pointer_ref']),
            decision_refs=sorted(records, key=lambda r:r['finding_id']))
        reader.suite.registry.validate(receipt, 'vnext_operator_selection_v1')
        return dict(selection=_selection_ref(number, receipt), content=receipt, responses=responses)

    def publish(self, packet, *, responses=False, dry_run=False):
        frozen = deepcopy(packet)
        require(type(dry_run) is bool, 'operator dry_run must be an explicit boolean')
        prepare = self._responses if responses else self._requests
        def operation(store, proof):
            _, frame, binding, context = self._context(proof)
            self._unadmitted(frame)
            result = prepare(proof, frozen, context)
            if dry_run: return result
            self._synchronize(store, proof, frame, binding)
            checked = self._context(proof)
            self._unadmitted(checked[1])
            require(prepare(proof, frozen, checked[3]) == result, 'Phase 2 operator sources changed during barriers')
            if responses:
                for entry in result['content']['decision_refs']:
                    ref = entry['request']
                    store.publish(store._token, ref['path'], proof.reader.raw(ref))
                for entry in result['responses']:
                    store.publish(store._token, entry['response']['path'], entry['content'])
                _validate_receipt(self.run, result['content'], self._context(proof)[3])
                store.publish(store._token, result['selection']['path'], result['content'])
            else:
                for entry in result: store.publish(store._token, entry['request']['path'], entry['content'])
            require(prepare(proof, frozen, self._context(proof)[3]) == result, 'Phase 2 operator publication readback differs')
            store.read_descriptor()  # Recheck ownership even after the final write.
            return result
        if not dry_run: return self._execute(operation)
        proof = self._proof(self.store.read); work = self._observe(proof)
        if work.outcome != 'work_available': return work
        return operation(None, proof)

    def admit(self, selection):
        reference = deepcopy(selection)
        def operation(store, proof):
            _, frame, binding, context = self._context(proof)
            receipt = proof.reader.json(reference, 'vnext_operator_selection_v1')
            require(reference == _selection_ref(frame['owner'].number, receipt), 'noncanonical Phase 2 operator selection')
            decisions = _validate_receipt(self.run, receipt, context)
            admission_preflight(proof, frame['bound'], binding, decisions)
            self._synchronize(store, proof, frame, binding)
            store.publish(store._token, reference['path'], proof.reader.raw(reference))
            owner = frame['owner']
            owner._execute = lambda action: action(store, owner.proof)
            return owner.admit(decision_refs=decisions)
        return self._execute(operation)
