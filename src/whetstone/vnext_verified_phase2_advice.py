"""Explicit, untrusted advice binding for the first consumed Phase 2 result."""
from copy import deepcopy

from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import (
    CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes,
)
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_consumption import _Consumption, PATH as CONSUMPTION_PATH
from whetstone.vnext_verified_phase2_client import JOURNAL_PATH
from whetstone.vnext_verified_work import VerifiedWork

ALGORITHM = 'algorithms/vnext_verified_phase2_advice_v1.md'
SCHEMA = 'vnext_phase2_advice_binding_v1'
ADVICE_PATH = JOURNAL_PATH + '/finding_advice.json'
BINDING_PATH = JOURNAL_PATH + '/advice_binding.json'


class _Advice(_Consumption):
    def _proof(self, read):
        proof = super()._proof(read)
        pins = {row['path']: row for family in ('algorithms', 'schemas')
                for row in proof.reader.suite.manifest[family]}
        paths = (ALGORITHM, 'schemas/'+SCHEMA+'.schema.json',
                 'schemas/vnext_finding_advice_v1.schema.json',
                 'algorithms/vnext_mutation_preparation_v1.md')
        for path in paths:
            require(path in pins, 'Phase 2 advice contracts are outside supported suite', path)
            require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == pins[path]['sha256'],
                    'installed Phase 2 advice contract differs from pinned suite', path)
        return proof

    def _advice_view(self, proof, supplied):
        bound, journal, outcomes, consumption, committed = self._consumption_view(proof)
        require(committed, 'Phase 2 advice requires committed result consumption')
        existing_advice, existing_binding = self._optional(ADVICE_PATH), self._optional(BINDING_PATH)
        require(existing_binding is None or existing_advice is not None,
                'committed Phase 2 advice binding is missing its advice')
        advice = deepcopy(supplied)
        if existing_advice is not None:
            retained = proof.reader.json(dict(path=ADVICE_PATH, hash=sha256_bytes(existing_advice)),
                                         'vnext_finding_advice_v1')
            require(advice is None or advice == retained, 'Phase 2 advice conflicts with immutable attachment')
            advice = retained
        if advice is None:
            require(existing_binding is None, 'Phase 2 advice binding lacks advice')
            return bound, journal, outcomes, consumption, None, dict(status='advice_required', binding=None, pending_paths=())
        journal.schemas.validate(advice, 'vnext_finding_advice_v1')
        _, review, receipt = journal.inspect(bound.request)
        inputs = bound.inputs
        findings, evidence = classify_feedback(feedback=review['feedback'], feedback_ref=receipt['feedback'],
            advice=advice, job=inputs['job'], authority=inputs['authority'], invariants=inputs['invariants'],
            base=inputs['draft'].encode('utf-8'), section_map=inputs['base_map'], scope=inputs['scope'])
        packet = dict(schema_version='vnext-phase2-advice-binding-v1',
            request=deepcopy(bound.request_ref), result=deepcopy(consumption['result']),
            consumption=_ref(CONSUMPTION_PATH, consumption), base_pointer=deepcopy(bound.request['base_pointer']),
            feedback=deepcopy(receipt['feedback']), advice=_ref(ADVICE_PATH, advice),
            findings=findings, evidence=evidence, next_gate='canonical_round_admission_not_implemented',
            candidate_authorized=False, next_review_authorized=False, phase_complete=False)
        journal.schemas.validate(packet, SCHEMA)
        if existing_binding is not None:
            stored = proof.reader.json(dict(path=BINDING_PATH, hash=sha256_bytes(existing_binding)), SCHEMA)
            require(stored == packet, 'Phase 2 advice binding differs from exact classification replay')
        pending = tuple(path for path, raw in ((ADVICE_PATH, existing_advice), (BINDING_PATH, existing_binding))
                        if raw is None)
        journal.recheck()
        proof.guard(self.store.read)
        self.run._guard(self.store.read)
        view = dict(status='bound' if not pending else 'prepared', binding=packet, pending_paths=pending)
        return bound, journal, outcomes, consumption, advice, view

    def prepare(self, advice=None):
        supplied = deepcopy(advice)
        proof = self._proof(self.store.read)
        work = VerifiedWork._observe(self, proof)
        if work.outcome != 'work_available': return work
        return deepcopy(self._advice_view(proof, supplied)[-1])

    def bind(self, advice=None):
        supplied = deepcopy(advice)
        def perform(store, proof):
            bound, journal, outcomes, consumption, packet, view = self._advice_view(proof, supplied)
            require(packet is not None, 'Phase 2 advice binding requires explicit advisory input or a retained attachment')
            self._synchronize_request(store, proof, bound)
            journal.synchronize(store._token, bound.request, outcomes)
            for reference in (view['binding']['feedback'], consumption['result'], view['binding']['consumption']):
                self.store.synchronize_existing(store._token, reference['path'], expected=proof.reader.raw(reference))
            require(self._advice_view(proof, packet)[-1] == view, 'Phase 2 advice inputs changed during barriers')
            # A retained prefix fixes the attachment. Replay may never substitute it.
            store.publish(store._token, ADVICE_PATH, packet)
            self._advice_view(proof, packet)
            store.publish(store._token, BINDING_PATH, view['binding'])
            result = self._advice_view(proof, packet)[-1]
            require(result['status'] == 'bound', 'Phase 2 advice publication incomplete')
            return deepcopy(result)
        return self._execute(perform)


def prepare_phase2_advice(run, advice=None):
    return _Advice(run).prepare(advice)


def bind_phase2_advice(run, advice=None):
    return _Advice(run).bind(advice)
