"""Unactivated live V work selection over freshly proven committed authority.

The private borrowed store keeps existing journals inside one real fence. Its
proof and admission objects never escape the invocation or authorize a later
operation. Historical replay remains read-only and separate from live input
selection. Scheduler terminals and public activation are separate consumers.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_proposal_handoff import register_completed_proposal_request, registry_for_proposal_requests
from whetstone.vnext_proposal_requests import _Journal, finish_proposal_request, inspect_proposal_request, run_proposal_request
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_verified_history import _VerifiedTransactions
from whetstone.vnext_verified_promotion import VerifiedPromotion
from whetstone.vnext_verified_semantics import (
    VerifiedSemanticDecisionJournal, inspect_verified_semantic_request, run_verified_semantic_request,
)


ALGORITHM = 'algorithms/vnext_verified_work_v1.md'


@dataclass(frozen=True)
class VerifiedWorkView:
    outcome: str
    current_pointer: dict
    latest_candidate: dict | None = None
    promotion_candidate: dict | None = None
    value: object | None = None
    pending_paths: tuple = ()


class _BorrowedFence:
    """Only nested producer calls may borrow this invocation's actual fence."""
    def __init__(self, store, token): self._source, self._token = store, token
    def _check(self): self._source._check_owner(self._token)
    def read(self, path): self._check(); return self._source.read(path)
    def read_descriptor(self): self._check(); return self._source.read_descriptor()
    def list_directory(self, path): self._check(); return self._source.list_directory(path)

    @contextmanager
    def locked(self, validate):
        self._check()
        validate(self.read)
        self._check()
        yield self._token

    def publish(self, token, path, value):
        require(token is self._token, 'live work cannot borrow another ownership token')
        require(path != 'rounds/current_verified.json', 'live work cannot publish global authority')
        self._check()
        return self._source.publish(token, path, value)

    def replace_pointer(self, token, path, **options):
        require(token is self._token, 'live work cannot borrow another ownership token')
        require(path.endswith('/candidate_verification_current.json'),
                'live work may replace only a candidate verification pointer')
        self._check()
        return self._source.replace_pointer(token, path, **options)


class _Inputs:
    def __init__(self, admission): self.admission = admission
    def __call__(self, read, number):
        owner = self.admission
        owner.validate_authority(read)
        require(number == owner.number, 'live work selected another Reviewer round')
        values = owner.router.load_inputs(read, number)
        require(values['base_pointer_ref'] == owner.proof.latest, 'live work requires its exact current base pointer')
        return values

    def for_proposal(self, read, number, identifier):
        owner = self.admission
        owner.validate_authority(read)
        return owner.proof.router.load_inputs.for_proposal(read, number, identifier)

    def request_journal(self, store, number, identifier):
        owner = self.admission
        require(store is owner.store, 'live work cannot read another storage owner')
        if identifier is None:
            return _Journal(store, lambda read: self(read, number))
        return owner.proof.router.load_inputs.request_journal(owner.proof.store, number, identifier)


class _Admission:
    def __init__(self, store, proof, number=None, selected_ref=None):
        self.store, self.proof, self.number = store, proof, number
        self.router = _VerifiedTransactions(proof.store, original=proof.admission, selected_ref=selected_ref)
        if selected_ref is not None: self.router.validate_selected(store.read)
        self.load_inputs = _Inputs(self)

    def _base(self, read):
        self.validate_authority(read)
        return self.proof.reader, self.proof.values(self.proof.latest)

    def validate_authority(self, read):
        self.store._check()
        self.proof.guard(read)
        # Reuse the acyclic history proof only within this fence; do not turn
        # its captured seed values or promoted inventory into a source cache
        # that could hide changed immutable inputs during a client invocation.
        self.proof.owner._seed_inputs(read, expected_mode='verified_promotion')
        promoted = self.proof.bases[self.proof.latest['path']][1]
        if promoted is not None:
            pointer, inventory = promoted
            self.proof.reader.json({
                'path': pointer['verified_draft_path'].rsplit('/', 1)[0] + '/preservation_inventory_candidate.json',
                'hash': sha256_bytes(canonical_json_bytes(inventory)),
            }, 'vnext_preservation_inventory_v2')
        self.proof.guard(read)

    def registry(self):
        return registry_for_proposal_requests(self.store, load_inputs=self.load_inputs,
                                              validate_authority=self.validate_authority)


class VerifiedWork:
    def __init__(self, store, *, history):
        self.store = store
        self.promotion = VerifiedPromotion(store, history=history)

    def _proof(self, read):
        proof = self.promotion._proof(read)
        entries = {entry['path']: entry for entry in proof.reader.suite.manifest['algorithms']}
        require(ALGORITHM in entries, 'verified work algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
                'installed verified work algorithm differs from pinned suite')
        return proof

    def _view(self, proof, outcome, *, promotion=None, value=None, pending=()):
        latest = proof.view.creations[-1] if hasattr(proof, 'view') and proof.view.creations else None
        return VerifiedWorkView(outcome, deepcopy(proof.pointers[-1]), deepcopy(latest),
                                deepcopy(promotion), value, tuple(pending))

    def _observe(self, proof):
        pending = self.promotion._pending(proof)
        if pending:
            proof.guard(self.store.read)
            return self._view(proof, 'materialization_required', pending=pending)
        proof.inspect_registry()
        if proof.view.orphans:
            return self._view(proof, 'registration_recovery_required')
        selected = self.promotion._select(proof)
        if selected is not None:
            return self._view(proof, 'promotion_required', promotion=selected.creation)
        return self._view(proof, 'work_available')

    def inspect(self):
        """Classify recovery/promotion precedence without selecting live clients."""
        proof = self._proof(self.store.read)
        result = self._observe(proof)
        proof.guard(self.store.read)
        return result

    def _execute(self, operation, *, recover_registration=False):
        captured = {}
        def validate(read): captured['proof'] = self._proof(read)
        with self.store.locked(validate) as token:
            proof = captured['proof']
            if not self.promotion._pending(proof):
                self.promotion.materialization._synchronize_complete(token, proof)
            view = self._observe(proof)
            if view.outcome == 'materialization_required': pass
            elif view.outcome == 'registration_recovery_required':
                if not recover_registration: return view
                admission = _Admission(_BorrowedFence(self.store, token), proof)
                # Recheck committed decisions through their historical prefixes.
                # The pending orphan must gate live semantic admission, not the
                # evidence replay needed to recover that same registration.
                for creation in proof.view.creations:
                    historical = proof.transactions(creation['candidate_creation_ordinal'])
                    journal = VerifiedSemanticDecisionJournal(historical.registry(), admission=historical)
                    journal._state(creation)
                value = admission.registry().reconcile()
                return VerifiedWorkView('registration_recovered', deepcopy(proof.pointers[-1]), value.latest, value=value)
            elif view.outcome == 'promotion_required': return view
            else:
                fence = _BorrowedFence(self.store, token)
                result = operation(fence, proof)
                from whetstone.vnext_phase2_source_correction import supported as source_supported
                from whetstone.vnext_phase2_repair import supported as repair_supported
                from whetstone.vnext_review_configuration import focused_profile
                from whetstone.vnext_verified_phase1_budget import supported as budget_supported
                if (source_supported(proof.reader.suite) or repair_supported(proof.reader.suite)
                        or budget_supported(proof.reader.suite)
                        or focused_profile(proof.seed_values['review']) is not None
                        or proof.seed_values['review']['review_mode'] == 'vertical'):
                    fence.read_descriptor()
                return result
        # A distinct fence and fresh current head own mirror repair. Never
        # proceed to the requested work after recovering materializations.
        repaired = self.promotion.materialization.repair()
        return VerifiedWorkView('materialization_recovered', repaired.pointer, pending_paths=repaired.pending_paths)

    def recover_registration(self):
        return self._execute(lambda store, proof: self._view(proof, 'no_registration_recovery'),
                             recover_registration=True)

    def _transaction(self, store, proof, number, selected_ref):
        admission = _Admission(store, proof, number, selected_ref)
        arguments = admission.load_inputs(store.read, number)
        transaction = prepare_unit_preflight(**arguments).plan['transaction_id']
        creations = proof.view.creations
        existing = next((item for item in creations if item['transaction_id'] == transaction), None)
        latest = creations[-1] if creations else None
        require(existing is None or existing == latest, 'live transaction was superseded by a later candidate')
        if latest is not None and existing is None:
            journal = VerifiedSemanticDecisionJournal(proof.router.registry(), admission=proof.router)
            view = journal._state(latest)[0]
            require(not view.prepared and view.decision is not None and view.decision['decision_final'],
                    'latest candidate must finish before a new transaction')
        return admission, existing

    def request(self, *, round_number, client=None, selected_ref=None, continuation=False):
        require(type(continuation) is bool, 'live proposal continuation must be explicit boolean')
        def perform(store, proof):
            admission, existing = self._transaction(store, proof, round_number, selected_ref)
            if existing is not None: return self._view(proof, 'candidate_registered', value=deepcopy(existing))
            load = lambda read: admission.load_inputs(read, round_number)
            status = inspect_proposal_request(store, load_inputs=load, validate_authority=admission.validate_authority)
            if status.status in {'complete', 'invalid_proposal', 'attempts_exhausted'}:
                return self._view(proof, 'proposal_result', value=status)
            if status.status != 'not_started' and not continuation:
                return self._view(proof, 'continuation_required', value=status)
            require(not continuation or status.status != 'not_started', 'new proposal is not technical continuation')
            if status.status == 'valid_response':
                status = finish_proposal_request(store, load_inputs=load,
                    validate_authority=admission.validate_authority, continuation=True)
            else:
                require(client is not None, 'live proposal requires a configured Editor')
                status = run_proposal_request(store, load_inputs=load, validate_authority=admission.validate_authority,
                                              client=client, continuation=continuation)
            return self._view(proof, 'proposal_result', value=status)
        return self._execute(perform)

    def register(self, *, round_number, created_at, selected_ref=None):
        def perform(store, proof):
            admission, _ = self._transaction(store, proof, round_number, selected_ref)
            creation = register_completed_proposal_request(store, round_number=round_number,
                load_inputs=admission.load_inputs, validate_authority=admission.validate_authority, created_at=created_at)
            return VerifiedWorkView('candidate_registered', deepcopy(proof.pointers[-1]), creation, value=creation)
        return self._execute(perform)

    def verify(self, *, client=None, decided_at, continuation=False):
        require(type(continuation) is bool, 'live semantic continuation must be explicit boolean')
        def perform(store, proof):
            require(bool(proof.view.creations), 'live verification requires a registered candidate')
            creation = proof.view.creations[-1]
            arguments = proof.router.load_inputs.for_proposal(store.read, creation['round_number'], creation['proposal_id'])
            require(arguments['base_pointer_ref'] == proof.latest, 'live verification requires its exact current base pointer')
            admission = _Admission(store, proof)
            journal = VerifiedSemanticDecisionJournal(admission.registry(), admission=admission)
            view = journal._state(creation)[0]
            if view.decision is not None and view.decision['decision_final'] and not view.prepared:
                require(not continuation, 'final candidate cannot resume verification')
                return self._view(proof, 'candidate_final', value=view)
            if view.prepared:
                if not continuation: return self._view(proof, 'continuation_required', value=view)
                result = journal.commit(creation['candidate_id'], decided_at=decided_at)
                return self._view(proof, 'verification_recovered', value=result)
            if view.decision is None:
                require(not continuation, 'new verification is not technical continuation')
                view = journal.commit(creation['candidate_id'], decided_at=decided_at)
                if view.decision['decision_final']: return self._view(proof, 'candidate_final', value=view)
            status = inspect_verified_semantic_request(store, admission=admission, candidate_id=creation['candidate_id'])
            if status.status != 'not_started' and not continuation:
                return self._view(proof, 'continuation_required', value=status)
            status = run_verified_semantic_request(store, admission=admission, candidate_id=creation['candidate_id'],
                                                   client=client, continuation=continuation)
            if status.status != 'complete': return self._view(proof, 'semantic_result', value=status)
            view = journal.commit_semantic(creation['candidate_id'], decided_at=decided_at)
            return self._view(proof, 'candidate_final', value=view)
        return self._execute(perform)
