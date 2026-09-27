"""Unactivated read-only replay of genuine committed promotion evidence.

All proven bases live inside one invocation. Historical access is not current
work admission, and no store pointer is virtualized to make an old base current.
"""
from copy import deepcopy
from dataclasses import dataclass

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_pointer_history import read_committed_pointer_history
from whetstone.vnext_proposal_admission import ProposalAdmission
from whetstone.vnext_proposal_requests import _Journal
from whetstone.vnext_semantic_answers import SemanticAnswerSource
from whetstone.vnext_semantic_followup_admission import SemanticFollowupAdmission, _ReadOnlyStore
from whetstone.vnext_semantic_followup_preflight import _read_followup_evidence
from whetstone.vnext_verified_semantics import ALGORITHM as SEMANTIC_ALGORITHM, VerifiedSemanticDecisionJournal


ALGORITHM = 'algorithms/vnext_verified_history_v1.md'


def _ref(path, value):
    return {'path': path, 'hash': sha256_bytes(canonical_json_bytes(value))}


def _snapshot(pointer):
    return _ref(f"rounds/verified_history/current-verified-{pointer['promotion_ordinal']}.json", pointer)


def _same_store(left, right):
    while isinstance(left, _ReadOnlyStore): left = left._source
    while isinstance(right, _ReadOnlyStore): right = right._source
    require(left is right, 'historical request cannot read another storage owner')


class _VerifiedAnswerSource(SemanticAnswerSource):
    DecisionJournal = VerifiedSemanticDecisionJournal


class _VerifiedTransactions(SemanticFollowupAdmission):
    def __init__(self, store, *, original, selected_ref=None, history_limit=None):
        super().__init__(store, original=original, selected_ref=selected_ref, history_limit=history_limit)
        self.load_inputs.request_journal = self._request_journal

    def _json(self, read, path, schema, digest=None):
        if schema == 'vnext_semantic_followup_input_v1':
            from whetstone.vnext_contracts import decode_json
            if decode_json(read(path)).get('schema_version') == 'vnext-phase2-repair-input-v1':
                from whetstone.vnext_phase2_repair import pins, SCHEMA
                pins(self.original._base(read)[0].suite)
                schema = SCHEMA
        return super()._json(read,path,schema,digest)

    def _derive(self, read, record):
        if record['schema_version'] == 'vnext-phase2-repair-input-v1':
            from whetstone.vnext_verified_phase2_repair import derive
            return derive(self,read,record)
        return super()._derive(read,record)

    def _original_inputs(self, read, record, event):
        from whetstone.vnext_phase2_repair import supported
        if supported(self.original._base(read)[0].suite):
            parent = type(self)(self.store,original=self.original,history_limit=event['candidate_creation_ordinal'])
            return parent.load_inputs.for_proposal(read,event['round_number'],event['proposal_id'])
        return super()._original_inputs(read,record,event)

    def _request_journal(self, store, number, identifier):
        proof = self.original.proof
        _same_store(store, proof.store)
        return _HistoricalJournal(proof, lambda read: self.load_inputs.for_proposal(read, number, identifier)
                                  if identifier is not None else self.load_inputs(read, number))

    def _read_evidence(self, historical, candidate_id, reference):
        return _read_followup_evidence(historical.store, admission=historical,
            candidate_id=candidate_id, reference=reference, source_type=_VerifiedAnswerSource)


class _HistoricalJournal(_Journal):
    def __init__(self, proof, load_inputs):
        self.proof = proof
        super().__init__(proof.store, load_inputs)

    def validate_base(self, arguments):
        self.proof.guard(self.store.read)
        reference = arguments['base_pointer_ref']
        expected = self.proof.values(reference)
        require(sha256_bytes(self.store.read(reference['path'])) == reference['hash']
                and arguments['base'] == expected['base'] and arguments['base_map'] == expected['base_map']
                and arguments.get('base_inventory') == expected.get('base_inventory'),
                'historical Editor request differs from its proven base')


@dataclass(frozen=True)
class VerifiedHistoryView:
    pointers: tuple
    creations: tuple
    orphans: tuple


class _ReplayAdmission:
    """Internal evidence owner; never returned or retained between public calls."""
    def __init__(self, proof):
        self.proof = proof
        self.store = proof.store

    def _base(self, read):
        self.proof.guard(read)
        return self.proof.reader, self.proof.values(self.proof.latest)

    def validate_authority(self, read):
        self.proof.guard(read)

    def load_inputs(self, read, number):
        self.proof.guard(read)
        selectors = self.proof.owner._refs['rounds']
        require(type(number) is int and number in selectors, 'unselected historical Reviewer round')
        record = self.proof.reader.json(selectors[number], 'vnext_proposal_round_input_v1')
        values = self.proof.values(record['base_pointer'])
        phase2 = self.proof.owner._validate_round_review(self.proof, number, record)
        if phase2 is not None: values['phase2'] = phase2
        return self.proof.owner._round_inputs(self.proof.reader, values, number)


class _Proof:
    def __init__(self, owner, read):
        self.owner = owner
        self.store = _ReadOnlyStore(owner.store)
        self.reader, self.seed_values = owner._seed_inputs(read, expected_mode='verified_promotion')
        entries = {entry['path']: entry for entry in self.reader.suite.manifest['algorithms']}
        for path in (ALGORITHM, SEMANTIC_ALGORITHM):
            require(path in entries, 'verified history algorithm is outside supported suite')
            require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == entries[path]['sha256'],
                    'installed verified history algorithm differs from pinned suite', path)
        schemas = {entry['path'] for entry in self.reader.suite.manifest['schemas']}
        require('schemas/promotion_intent_v1.schema.json' in schemas,
                'verified history intent schema is outside supported suite')
        self.head_raw = read('rounds/current_verified.json')
        self.descriptor_raw = owner.store.read_descriptor()
        self.pointers = read_committed_pointer_history(self.reader, job=self.seed_values['job'],
                                                       seed_map_ref=owner._refs['seed_map'])
        require(canonical_json_bytes(self.pointers[-1]) == self.head_raw, 'verified history head changed during structural replay')
        self.latest = _snapshot(self.pointers[0])
        self.bases = {self.latest['path']: (self.latest, None)}
        self.admission = _ReplayAdmission(self)

    def guard(self, read):
        require(read('rounds/current_verified.json') == self.head_raw
                and self.owner.store.read_descriptor() == self.descriptor_raw,
                'verified history authority changed during replay')

    def values(self, reference):
        found = self.bases.get(reference['path'])
        require(found is not None and found[0] == reference,
                'historical transaction base has not been proven in committed ancestry')
        # _round_inputs mutates its returned arguments; isolate each consumer.
        values = {key: value if key == 'suite' else deepcopy(value) for key, value in self.seed_values.items()}
        values['base_pointer_ref'] = deepcopy(reference)
        if found[1] is not None:
            pointer, inventory = found[1]
            values['base'] = self.reader.raw({'path': pointer['verified_draft_path'], 'hash': pointer['verified_draft_hash']})
            values['base_map'] = self.reader.json({'path': pointer['verified_section_identity_map_path'],
                'hash': pointer['verified_section_identity_map_hash']}, 'section_identity_map_v2')
            values['base_inventory'] = deepcopy(inventory)
        return values

    def transactions(self, limit=None):
        return _VerifiedTransactions(self.store, original=self.admission, history_limit=limit)

    def prove_lineage(self):
        for pointer in self.pointers[1:]:
            router = self.transactions(pointer['source_candidate_creation_ordinal'])
            registry = router.registry()
            registered = registry.inspect()
            creation = registered.latest
            require(creation is not None and creation['candidate_id'] == pointer['source_candidate_id']
                    and _ref(pointer['source_candidate_creation_event_path'], creation)['hash']
                        == pointer['source_candidate_creation_event_hash'],
                    'promoted candidate differs from reproduced creation prefix')
            arguments = router.load_inputs.for_proposal(self.store.read, creation['round_number'], creation['proposal_id'])
            require(arguments['base_pointer_ref'] == {
                'path': pointer['previous_verified_pointer_path'], 'hash': pointer['previous_verified_pointer_hash']},
                'promoted transaction does not use its exact committed predecessor')
            journal = VerifiedSemanticDecisionJournal(registry, admission=router)
            view = journal.inspect(creation['candidate_id'])
            require(not view.prepared and view.decision is not None
                    and view.pointer['current_decision_path'] == pointer['candidate_verification_path']
                    and view.pointer['current_decision_hash'] == pointer['candidate_verification_hash']
                    and view.decision['decision_final'] and view.decision['promotion_permitted'],
                    'promoted verification differs from reproduced durable semantic evidence')
            directory = creation['candidate_path'].rsplit('/', 1)[0]
            # Bind subsequent reads to the already reproduced final decision,
            # rather than accepting a different inventory after chain replay.
            report = self.reader.json({'path': directory + '/preservation_report.json',
                'hash': view.decision['preservation_report_hash']}, 'preservation_report_v2')
            inventory = self.reader.json({'path': directory + '/preservation_inventory_candidate.json',
                'hash': report['candidate_inventory_hash']}, 'vnext_preservation_inventory_v2')
            self.latest = _snapshot(pointer)
            self.bases[self.latest['path']] = (self.latest, (pointer, inventory))
        self.guard(self.store.read)
        return self

    def inspect_registry(self):
        self.router = self.transactions()
        registered = self.router.registry().inspect()
        self.guard(self.store.read)
        self.view = VerifiedHistoryView(tuple(deepcopy(self.pointers)), tuple(deepcopy(registered.events)), registered.orphans)
        return self

    def run(self):
        return self.prove_lineage().inspect_registry()


class _HistoricalInputs:
    def __init__(self, owner):
        self.owner = owner

    def __call__(self, read, number):
        proof = self.owner._prove(read)
        values = proof.admission.load_inputs(read, number)
        proof.guard(read)
        return values

    def for_proposal(self, read, number, identifier):
        proof = self.owner._prove(read)
        values = proof.router.load_inputs.for_proposal(read, number, identifier)
        proof.guard(read)
        return values

    def request_journal(self, store, number, identifier):
        _same_store(store, self.owner.store)
        proof = self.owner._prove(self.owner.store.read)
        return proof.router.load_inputs.request_journal(proof.store, number, identifier)


class VerifiedHistoryAdmission(ProposalAdmission):
    """Fresh read-only historical evidence; not a live-work eligibility gate."""
    def __init__(self, store, **selectors):
        super().__init__(_ReadOnlyStore(store), **selectors)
        self.load_inputs = _HistoricalInputs(self)

    def _validate_round_review(self, proof, number, record):
        """Stored-run consumers may require bounded original Reviewer replay."""

    def _prove(self, read):
        return _Proof(self, read).run()

    def inspect(self):
        return self._prove(self.store.read).view

    def _base(self, read):
        proof = self._prove(read)
        return proof.reader, proof.values(proof.latest)

    def validate_authority(self, read):
        self._prove(read)
