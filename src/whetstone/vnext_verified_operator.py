"""Unactivated V interpretation answers and explicit child selection."""
from copy import deepcopy

from whetstone.vnext_contracts import CONTRACT_ROOT, VNextSchemaRegistry, confined_file, require, sha256_bytes
from whetstone.vnext_semantic_answers import _inspect_semantic_answers, _submit_semantic_answer
from whetstone.vnext_semantic_followup_admission import _admit_semantic_followup
from whetstone.vnext_verified_history import _VerifiedAnswerSource
from whetstone.vnext_verified_work import VerifiedWork, _Admission


ALGORITHM = 'algorithms/vnext_verified_operator_v1.md'


class VerifiedOperator(VerifiedWork):
    def _proof(self, read):
        proof = super()._proof(read)
        entries = {entry['path']: entry for entry in proof.reader.suite.manifest['algorithms']}
        require(ALGORITHM in entries, 'verified operator algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
                'installed verified operator algorithm differs from pinned suite')
        return proof

    def _source(self, proof, candidate_id, *, current):
        creation = next((item for item in proof.view.creations if item['candidate_id'] == candidate_id), None)
        require(creation is not None, 'operator candidate is not registered')
        arguments = proof.router.load_inputs.for_proposal(self.store.read, creation['round_number'], creation['proposal_id'])
        eligible = creation == proof.view.creations[-1] and arguments['base_pointer_ref'] == proof.latest
        require(not current or eligible, 'new V operator work requires the latest candidate and exact current base')
        return creation, eligible

    def answers(self, *, candidate_id):
        proof = self._proof(self.store.read)
        gate = self._observe(proof)
        if gate.outcome != 'work_available': return gate
        _, eligible = self._source(proof, candidate_id, current=False)
        value = _inspect_semantic_answers(proof.store, admission=proof.router, candidate_id=candidate_id,
                                          source_type=_VerifiedAnswerSource)
        value['submission_permitted'] = value['submission_permitted'] and eligible
        proof.guard(self.store.read)
        return self._view(proof, 'operator_answers', value=value)

    def submit_answer(self, *, packet, dry_run=False):
        frozen = deepcopy(packet)
        VNextSchemaRegistry().validate(frozen, 'vnext_semantic_answer_input_v1')
        require(type(dry_run) is bool, 'V operator dry_run must be an explicit boolean')
        if dry_run:
            proof = self._proof(self.store.read)
            gate = self._observe(proof)
            if gate.outcome != 'work_available': return gate
            self._source(proof, frozen['candidate_id'], current=True)
            value = _submit_semantic_answer(proof.store, admission=proof.router, packet=frozen, dry_run=True,
                                            source_type=_VerifiedAnswerSource)
            proof.guard(self.store.read)
            return self._view(proof, 'answer_preview', value=value)

        def perform(store, proof):
            creation, _ = self._source(proof, frozen['candidate_id'], current=True)
            admission = _Admission(store, proof, creation['round_number'])
            value = _submit_semantic_answer(store, admission=admission, packet=frozen, dry_run=False,
                                            source_type=_VerifiedAnswerSource)
            return self._view(proof, 'answer_recorded', value=value)
        return self._execute(perform)

    def select_followup(self, *, candidate_id, answer_reference):
        frozen = deepcopy(answer_reference)
        def perform(store, proof):
            creation, _ = self._source(proof, candidate_id, current=True)
            admission = _Admission(store, proof, creation['round_number'])
            reference = _admit_semantic_followup(store, original=admission, router=proof.router,
                source_admission=admission, source_type=_VerifiedAnswerSource,
                candidate_id=candidate_id, answer_reference=frozen)
            return self._view(proof, 'followup_selected', value=reference)
        return self._execute(perform)
