"""Unactivated V-mode semantic requests and candidate-local decisions.

The admission owner must validate the selected transaction's actual base and
registry. A final passing decision permits later promotion checks; it does not
promote, materialize the run draft, or qualify a runtime mode.
"""
from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_proposal_closeout import ProposalDecisionJournal
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from whetstone.vnext_semantic_requests import (
    SemanticRequestJournal, _finish_semantic_request, _run_semantic_request,
)


ALGORITHM = 'algorithms/vnext_verified_semantics_v1.md'


def _check_contract(admission, read):
    reader, values = admission._base(read)
    require(values['job']['editing_mode'] == 'verified_promotion', 'verified semantic consumer requires V mode')
    schemas = {entry['path'] for entry in reader.suite.manifest['schemas']}
    require('schemas/promotion_intent_v1.schema.json' in schemas,
            'verified semantic promotion intent schema is outside supported suite')
    algorithms = {entry['path']: entry for entry in reader.suite.manifest['algorithms']}
    require(ALGORITHM in algorithms, 'verified semantic algorithm is outside supported suite')
    require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == algorithms[ALGORITHM]['sha256'],
            'installed verified semantic algorithm differs from pinned suite')


class _InitialVerifiedDecisionReader(ProposalDecisionJournal):
    MODE = 'verified_promotion'


class VerifiedSemanticRequestJournal(SemanticRequestJournal):
    # Invocation eligibility reads only the initial nonfinal deterministic
    # decision. A final semantic decision cannot reopen through this reader.
    DecisionJournal = _InitialVerifiedDecisionReader

    def __init__(self, store, *, admission, candidate_id):
        _check_contract(admission, store.read)
        super().__init__(store, admission=admission, candidate_id=candidate_id)


class VerifiedSemanticDecisionJournal(SemanticDecisionJournal):
    MODE = 'verified_promotion'
    RequestJournal = VerifiedSemanticRequestJournal
    DISPOSITION_NAMES = SemanticDecisionJournal.DISPOSITION_NAMES | {'event-4.json'}

    def __init__(self, registry, *, admission):
        _check_contract(admission, registry.store.read)
        super().__init__(registry, admission=admission)

    def inspect(self, candidate_id):
        _check_contract(self.admission, self.store.read)
        return super().inspect(candidate_id)

    def commit(self, candidate_id, *, decided_at):
        _check_contract(self.admission, self.store.read)
        return super().commit(candidate_id, decided_at=decided_at)

    def commit_semantic(self, candidate_id, *, decided_at):
        _check_contract(self.admission, self.store.read)
        return super().commit_semantic(candidate_id, decided_at=decided_at)

    def _tail_path(self, creation):
        return creation['candidate_path'].rsplit('/', 1)[0] + '/disposition_events/event-4.json'

    def _require_committed_predecessor(self, previous_raw, ordinal):
        """Check membership in actual head ancestry, without semantic recursion."""
        pointer, head_raw = self.registry._json('rounds/current_verified.json', 'current_verified_pointer_v1')
        raw = head_raw
        while True:
            number = pointer['promotion_ordinal']
            require(pointer['job_id'] == self.registry.job['job_id'] and number >= ordinal,
                    'promotion tail predecessor is outside committed ancestry')
            require(self.store.read(f'rounds/verified_history/current-verified-{number}.json') == raw,
                    'promotion tail ancestry snapshot differs')
            if number == ordinal:
                require(raw == previous_raw, 'promotion tail predecessor is not the committed snapshot')
                break
            path = f'rounds/verified_history/current-verified-{number - 1}.json'
            require(pointer['previous_verified_pointer_path'] == path,
                    'promotion tail ancestry has a noncanonical predecessor')
            predecessor, predecessor_raw = self.registry._json(path, 'current_verified_pointer_v1')
            require(sha256_bytes(predecessor_raw) == pointer['previous_verified_pointer_hash']
                    and predecessor['promotion_ordinal'] == number - 1,
                    'promotion tail ancestry hash or ordinal differs')
            pointer, raw = predecessor, predecessor_raw
        require(self.store.read('rounds/current_verified.json') == head_raw,
                'committed head changed during promotion tail inspection')

    def _validate_disposition_claims(self, creation, view, completed):
        super()._validate_disposition_claims(creation, view, completed)
        event = self._optional(self._tail_path(creation), 'candidate_disposition_event_v1')
        if event is None:
            return
        decision = view.decision
        require(not view.prepared and decision is not None and decision['decision_ordinal'] == 2
                and decision['decision_final'] and decision['promotion_permitted']
                and decision['candidate_disposition'] == 'CANDIDATE_VERIFIED'
                and decision['deterministic_result'] == decision['semantic_result'] == 'pass',
                'promotion tail lacks a committed final semantic pass')
        directory = creation['candidate_path'].rsplit('/', 1)[0]
        intent, intent_raw = self.registry._json(event['source_artifact_path'], 'promotion_intent_v1')
        intent_ref = {'path': event['source_artifact_path'], 'hash': sha256_bytes(intent_raw)}
        require(intent_ref['hash'] == event['source_artifact_hash']
                and intent_ref['path'] == directory + f"/promotion_intents/promotion-intent-{intent['next_promotion_ordinal']}.json"
                and intent['intent_id'] == ids.intent_id(intent),
                'promotion tail intent identity, hash or path differs')
        previous_path = f"rounds/verified_history/current-verified-{intent['expected_current_promotion_ordinal']}.json"
        previous, previous_raw = self.registry._json(previous_path, 'current_verified_pointer_v1')
        require(previous['job_id'] == creation['job_id']
                and previous['promotion_ordinal'] == intent['expected_current_promotion_ordinal'],
                'promotion tail predecessor snapshot differs')
        self._require_committed_predecessor(previous_raw, previous['promotion_ordinal'])
        require(completed is not None and completed[0].context.packet['base_pointer'] == {
            'path': previous_path, 'hash': sha256_bytes(previous_raw)},
            'promotion tail differs from the exact admitted base pointer')
        expected = {
            'job_id': creation['job_id'], 'transaction_id': creation['transaction_id'],
            'candidate_id': creation['candidate_id'],
            'candidate_creation_ordinal': creation['candidate_creation_ordinal'],
            'candidate_creation_event_path': f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json",
            'candidate_creation_event_hash': sha256_bytes(canonical_json_bytes(creation)),
            'candidate_section_identity_map_path': creation['candidate_section_identity_map_path'],
            'candidate_section_identity_map_hash': creation['candidate_section_identity_map_hash'],
            'base_draft_hash': decision['base_draft_hash'], 'candidate_hash': creation['candidate_hash'],
            'candidate_verification_path': view.pointer['current_decision_path'],
            'candidate_verification_hash': view.pointer['current_decision_hash'],
            'expected_current_verified_hash': previous['verified_draft_hash'],
            'expected_current_verified_pointer_hash': sha256_bytes(previous_raw),
            'next_promotion_ordinal': previous['promotion_ordinal'] + 1,
        }
        require(all(intent[key] == value for key, value in expected.items())
                and decision['base_draft_hash'] == previous['verified_draft_hash'],
                'promotion tail differs from registered candidate, final decision or predecessor')
        expected_event = {
            'job_id': creation['job_id'], 'candidate_id': creation['candidate_id'],
            'candidate_creation_ordinal': creation['candidate_creation_ordinal'], 'event_ordinal': 4,
            'event_kind': 'promotion_committed', 'previous_event_hash': view.effective_event_ref['hash'],
            'previous_disposition': 'CANDIDATE_VERIFIED', 'new_disposition': 'CANDIDATE_PROMOTED',
        }
        require(all(event[key] == value for key, value in expected_event.items())
                and event['event_id'] == ids.disposition_id(event),
                'promotion tail does not extend the exact verified disposition')
        # This only proves the directly inspected tail's bindings. The global
        # lineage owner determines whether its pointer was actually committed.
        # Keep the returned view candidate-local and never infer promotion here.

    def _commit_semantic(self, token, creation, stamp):
        if self._optional(self._tail_path(creation), 'candidate_disposition_event_v1') is not None:
            # A validated tail follows an already final semantic decision.
            # Reentry may inspect it but must not publish after promotion prep.
            return self._state(creation)[0]
        return super()._commit_semantic(token, creation, stamp)

    def _creation(self, token, candidate_id):
        events = self.registry._chain()
        creation = next((item for item in events if item['candidate_id'] == candidate_id), None)
        if creation is not None and self._optional(self._tail_path(creation), 'candidate_disposition_event_v1') is not None:
            require(not self.registry._orphans(events),
                    'promotion workflow must reconcile registration orphans before semantic reentry')
            return creation
        events = self.registry._reconcile(token, events)
        creation = next((item for item in events if item['candidate_id'] == candidate_id), None)
        require(creation is not None, 'semantic decision candidate is not registered')
        return creation

    def terminal(self, **options):
        raise ValueError('V-mode terminal projection requires the promotion workflow owner')


def inspect_verified_semantic_request(store, *, admission, candidate_id):
    journal = VerifiedSemanticRequestJournal(store, admission=admission, candidate_id=candidate_id)
    return journal.status(*journal.inspect())


def finish_verified_semantic_request(store, *, admission, candidate_id):
    return _finish_semantic_request(store, admission=admission, candidate_id=candidate_id,
                                    journal_type=VerifiedSemanticRequestJournal)


def run_verified_semantic_request(store, *, admission, candidate_id, client=None, continuation=False):
    return _run_semantic_request(store, admission=admission, candidate_id=candidate_id, client=client,
                                 continuation=continuation, journal_type=VerifiedSemanticRequestJournal)
