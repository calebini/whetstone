"""Unactivated reopening of V roots from immutable persisted input selectors.

Round locators are resolved only when an explicitly selected round or validated
history needs them. Directory contents cannot choose a round or grant work.
Reviewer scheduling and new runtime round publication remain separate owners.
"""
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from whetstone.vnext_contracts import (
    CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes,
)
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_proposal_run import RUN_INPUT_PATH, round_input_path
from whetstone.vnext_verified_history import VerifiedHistoryAdmission
from whetstone.vnext_verified_operator import VerifiedOperator
from whetstone.vnext_verified_promotion import VerifiedPromotion


ALGORITHM = 'algorithms/vnext_verified_run_v1.md'


class _RoundSelectors(Mapping):
    def __init__(self, run):
        self.run = run
        self.cached = {}

    def _resolve(self, number):
        path = round_input_path(number)
        try: raw = self.run.store.read(path)
        except FileNotFoundError: raw = None
        staged = self.run._staged.get(number)
        if staged is not None:
            staged_raw = self.run.store.read(staged['path'])
            require(sha256_bytes(staged_raw) == staged['hash'], 'staged V round selector changed')
            require(raw is None or raw == staged_raw, 'canonical V round differs from its staged input')
            if raw is None: return deepcopy(staged)
        if raw is None: raise KeyError(number)
        return {'path': path, 'hash': sha256_bytes(raw)}

    def __getitem__(self, number):
        reference = self._resolve(number)
        old = self.cached.get(number)
        require(old is None or old['hash'] == reference['hash'], 'resolved V round input changed during invocation')
        if old is None: self.cached[number] = reference
        return deepcopy(self.cached[number])

    def __contains__(self, number):
        try: self[number]
        except KeyError: return False
        return True

    def __iter__(self): return iter(sorted(set(self.run._staged) | set(self.cached)))
    def __len__(self): return len(set(self.run._staged) | set(self.cached))

    def guard(self):
        for number in tuple(self.cached): self[number]


class _RunHistory(VerifiedHistoryAdmission):
    def __init__(self, run):
        self.run = run
        record = run._record
        super().__init__(run.store, suite_path=run.suite_path, descriptor_ref=record['descriptor'],
            review_ref=record['review_configuration'], seed_map_ref=record['seed_section_map'], round_refs={},
            launch_package_ref=record.get('launch_package'))
        self._refs['rounds'] = _RoundSelectors(run)

    def _seed_inputs(self, read, *, expected_mode):
        self.run._guard(read)
        self._refs['rounds'].guard()
        reader, values = super()._seed_inputs(read, expected_mode=expected_mode)
        from whetstone.vnext_review_configuration import focused_profile
        require(focused_profile(values['review']) is None or not self.run._staged,
                'focused V runs cannot import staged rounds')
        require(values['job']['job_id'] == self.run._record['job_id'], 'V run selectors belong to another job')
        entries = {entry['path']: entry for entry in reader.suite.manifest['algorithms']}
        require(ALGORITHM in entries, 'verified run algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
                'installed verified run algorithm differs from pinned suite')
        return reader, values

    def _validate_round_review(self, proof, number, record):
        from whetstone.vnext_verified_phase2_round import FEEDBACK_PATH, validate_round
        if record['feedback']['path'].startswith('rounds/phase2/review_requests/pass-'):
            from whetstone.vnext_verified_phase2_sequence import validate_round as validate_sequence_round
            return validate_sequence_round(proof, number, record)
        if record['feedback']['path'] == FEEDBACK_PATH:
            return validate_round(proof, number, record)
        # Historical staged sources remain readable during Stage 1 recovery.
        # Unrelated future claims are checked by the live owner after repair.
        if not self.run._staged or record['feedback']['path'] == f'rounds/round-{number}/reviewer_feedback.json':
            from whetstone.vnext_verified_review import validate_round_review
            validate_round_review(proof, number, record)
        self.run._guard(self.run.store.read)


class _RunOperator(VerifiedOperator):
    def _observe(self, proof):
        view = super()._observe(proof)
        if view.outcome != 'materialization_required':
            from whetstone.vnext_verified_review import validate_current_sequence
            validate_current_sequence(proof)
        return view


class _RunPromotion(VerifiedPromotion):
    def _select(self, proof):
        from whetstone.vnext_verified_review import validate_current_sequence
        validate_current_sequence(proof)
        return super()._select(proof)


class VerifiedRun:
    def __init__(self, store, *, suite_path):
        self.store, self.suite_path = store, Path(suite_path)
        self._raw = store.read(RUN_INPUT_PATH)
        self._record = decode_json(self._raw)
        VNextSchemaRegistry().validate(self._record, 'vnext_proposal_run_input_v1')
        require(self._raw == canonical_json_bytes(self._record), 'noncanonical V run input record')
        rows = self._record['staged_rounds']
        numbers = [row['round_number'] for row in rows]
        require(numbers == sorted(set(numbers)), 'staged V round selectors must be sorted and unique')
        self._staged = {row['round_number']: deepcopy(row['input']) for row in rows}

    def _guard(self, read):
        require(read(RUN_INPUT_PATH) == self._raw, 'retained V run selectors changed')

    def _history(self):
        self._guard(self.store.read)
        return _RunHistory(self)

    def _operator(self): return _RunOperator(self.store, history=self._history())
    def inspect(self): return self._operator().inspect()
    def review_apply_back(self):
        from whetstone.vnext_apply_back import ApplyBack
        return ApplyBack(self).review()
    def apply_back_status(self):
        from whetstone.vnext_apply_back import ApplyBack
        return ApplyBack(self).status()
    def apply_back(self, **options):
        from whetstone.vnext_apply_back import ApplyBack
        return ApplyBack(self).apply(**options)
    def recover_apply_back(self, **options):
        from whetstone.vnext_apply_back import ApplyBack
        return ApplyBack(self).recover(**options)
    def phase1_status(self):
        from whetstone.vnext_verified_phase1_status import inspect_verified_phase1
        return inspect_verified_phase1(self)

    def extend_phase1_budget(self, *, added_rounds_per_profile, **options):
        from whetstone.vnext_verified_phase1_budget import extend
        return extend(self, added_rounds_per_profile=added_rounds_per_profile, **options)
    def phase1_closeout(self):
        from whetstone.vnext_verified_phase1_closeout import inspect_verified_phase1_closeout
        return inspect_verified_phase1_closeout(self)
    def finish_phase1(self):
        from whetstone.vnext_verified_phase1_closeout import finish_verified_phase1
        return finish_verified_phase1(self)
    def operator_status(self):
        from whetstone.vnext_verified_phase1_operator import inspect_verified_operator
        return inspect_verified_operator(self)
    def reconcile_phase1_state(self):
        from whetstone.vnext_verified_phase1_operator import reconcile_verified_phase1_state
        return reconcile_verified_phase1_state(self)
    def phase2_eligibility(self):
        from whetstone.vnext_verified_phase2_eligibility import inspect_verified_phase2_eligibility
        return inspect_verified_phase2_eligibility(self)
    def prepare_phase2_entry(self, configuration):
        from whetstone.vnext_verified_phase2_binding import prepare_phase2_entry
        return prepare_phase2_entry(self, configuration)
    def bind_phase2_entry(self, configuration):
        from whetstone.vnext_verified_phase2_binding import bind_phase2_entry
        return bind_phase2_entry(self, configuration)
    def phase2_entry_status(self):
        from whetstone.vnext_verified_phase2_binding import inspect_phase2_entry
        return inspect_phase2_entry(self)
    def enter_phase2(self):
        from whetstone.vnext_verified_phase2_entry import enter_verified_phase2
        return enter_verified_phase2(self)
    def prepare_phase2_version(self, *, created_at):
        from whetstone.vnext_version_entry import prepare
        return prepare(self,created_at=created_at)
    def prepare_phase2_review(self, transport):
        from whetstone.vnext_verified_phase2_review import prepare_phase2_review
        return prepare_phase2_review(self, transport)
    def bind_phase2_review(self, transport):
        from whetstone.vnext_verified_phase2_review import bind_phase2_review
        return bind_phase2_review(self, transport)
    def run_phase2_review(self, *, client=None, continuation=False):
        from whetstone.vnext_verified_phase2_client import run_phase2_review
        return run_phase2_review(self, client=client, continuation=continuation)
    def prepare_phase2_declaration(self):
        from whetstone.vnext_verified_phase2_closeout import _Declaration
        return _Declaration(self).prepare()
    def phase2_failure_status(self):
        from whetstone.vnext_verified_phase2_failure import _Failure
        return _Failure(self).status_failure()
    def publish_phase2_failure(self):
        from whetstone.vnext_verified_phase2_failure import _Failure
        return _Failure(self).publish_failure()
    def reconcile_phase2_failure_state(self):
        from whetstone.vnext_verified_phase2_failure import _Failure
        return _Failure(self).recover_failure()
    def phase2_correction_failure_status(self):
        from whetstone.vnext_verified_phase2_correction_failure import _CorrectionFailure
        return _CorrectionFailure(self).status()
    def publish_phase2_correction_failure(self):
        from whetstone.vnext_verified_phase2_correction_failure import _CorrectionFailure
        return _CorrectionFailure(self).publish()
    def reconcile_phase2_correction_failure_state(self):
        from whetstone.vnext_verified_phase2_correction_failure import _CorrectionFailure
        return _CorrectionFailure(self).recover()
    def phase2_closeout(self):
        from whetstone.vnext_verified_phase2_closeout import _Declaration
        return _Declaration(self).status()
    def phase2_signal_status(self):
        from whetstone.vnext_verified_phase2_signals import _Signals
        return _Signals(self).status()
    def phase2_resolution_status(self):
        from whetstone.vnext_verified_phase2_resolution import _Resolution
        return _Resolution(self).status()
    def publish_phase2_resolutions(self):
        from whetstone.vnext_verified_phase2_resolution import _Resolution
        return _Resolution(self).publish()
    def reconcile_phase2_resolution_state(self):
        from whetstone.vnext_verified_phase2_resolution import _Resolution
        return _Resolution(self).recover()
    def publish_phase2_signals(self):
        from whetstone.vnext_verified_phase2_signals import _Signals
        return _Signals(self).publish()
    def reconcile_phase2_signal_state(self):
        from whetstone.vnext_verified_phase2_signals import _Signals
        return _Signals(self).recover()
    def phase2_final_findings(self):
        from whetstone.vnext_verified_phase2_findings import _Findings
        return _Findings(self).inspect()
    def phase2_blocked_report(self):
        from whetstone.vnext_verified_phase2_blocked import _BlockedReport
        return _BlockedReport(self).inspect_report()
    def reconcile_phase2_findings(self):
        from whetstone.vnext_verified_phase2_findings import _Findings
        return _Findings(self).reconcile_findings()
    def finish_phase2(self):
        from whetstone.vnext_verified_phase2_closeout import _Declaration
        return _Declaration(self).finish()
    def reconcile_phase2_state(self):
        from whetstone.vnext_verified_phase2_closeout import _Declaration
        return _Declaration(self).reconcile()
    def phase2_sequence_status(self):
        from whetstone.vnext_verified_phase2_sequence import _Continuation
        return _Continuation(self).status()
    def bind_phase2_next_review(self, transport):
        from whetstone.vnext_verified_phase2_sequence import _Continuation
        return _Continuation(self).bind_next(transport)
    def continue_phase2_pass(self, pass_number, *, action, **options):
        from whetstone.vnext_verified_phase2_sequence import _Continuation
        return _Continuation(self).operation(pass_number, action, **options)
    def prepare_phase2_continuation_advice(self, pass_number, advice):
        from whetstone.vnext_verified_phase2_sequence import _Continuation
        return _Continuation(self).prepare_advice(pass_number, advice)
    def admit_phase2_round(self):
        from whetstone.vnext_verified_phase2_round import admit_phase2_round
        return admit_phase2_round(self)

    def phase2_operator_context(self):
        from whetstone.vnext_verified_phase2_operator import Phase2Operator
        return Phase2Operator(self).context()

    def prepare_phase2_operator_requests(self, packet, *, dry_run=False):
        from whetstone.vnext_verified_phase2_operator import Phase2Operator
        return Phase2Operator(self).publish(packet, dry_run=dry_run)

    def submit_phase2_operator_responses(self, packet, *, dry_run=False):
        from whetstone.vnext_verified_phase2_operator import Phase2Operator
        return Phase2Operator(self).publish(packet, responses=True, dry_run=dry_run)

    def admit_phase2_operator_round(self, selection):
        from whetstone.vnext_verified_phase2_operator import Phase2Operator
        return Phase2Operator(self).admit(selection)
    def prepare_phase2_advice(self, advice=None):
        from whetstone.vnext_verified_phase2_advice import prepare_phase2_advice
        return prepare_phase2_advice(self, advice)
    def bind_phase2_advice(self, advice=None):
        from whetstone.vnext_verified_phase2_advice import bind_phase2_advice
        return bind_phase2_advice(self, advice)
    def consume_phase2_result(self):
        from whetstone.vnext_verified_phase2_consumption import consume_phase2_result
        return consume_phase2_result(self)
    def phase2_consumption_status(self):
        from whetstone.vnext_verified_phase2_consumption import phase2_consumption_status
        return phase2_consumption_status(self)
    def phase2_review_status(self):
        from whetstone.vnext_verified_phase2_client import phase2_review_status
        return phase2_review_status(self)
    def phase2_state(self):
        from whetstone.vnext_verified_phase2_entry import inspect_verified_phase2_state
        return inspect_verified_phase2_state(self)
    def request(self, **options): return self._operator().request(**options)
    def register(self, **options): return self._operator().register(**options)
    def verify(self, **options): return self._operator().verify(**options)
    def recover_registration(self): return self._operator().recover_registration()
    def answers(self, **options): return self._operator().answers(**options)
    def submit_answer(self, **options): return self._operator().submit_answer(**options)
    def select_followup(self, **options): return self._operator().select_followup(**options)

    def phase2_repair_context(self, **options):
        from whetstone.vnext_verified_phase2_repair import Phase2Repair
        return Phase2Repair(self).context(**options)

    def phase2_gap_acceptance_context(self):
        from whetstone.vnext_verified_phase2_gap_acceptance import GapAcceptance
        return GapAcceptance(self).context()

    def accept_phase2_gaps(self, packet, **options):
        from whetstone.vnext_verified_phase2_gap_acceptance import GapAcceptance
        return GapAcceptance(self).accept(packet, **options)

    def admit_phase2_repair(self, packet, **options):
        from whetstone.vnext_verified_phase2_repair import Phase2Repair
        return Phase2Repair(self).admit(packet, **options)
    def promote(self, **options): return _RunPromotion(self.store, history=self._history()).promote(**options)
    def review_status(self):
        from whetstone.vnext_verified_review import VerifiedReview
        return VerifiedReview(self).status()

    def review_next(self, *, client=None, continuation=False):
        from whetstone.vnext_verified_review import VerifiedReview
        return VerifiedReview(self).next(client=client, continuation=continuation)

    def admit_reviewed_round(self, *, decision_refs=()):
        from whetstone.vnext_verified_review import VerifiedReview
        return VerifiedReview(self).admit(decision_refs=decision_refs)

    def consolidate_phase1_review(self):
        from whetstone.vnext_verified_review import VerifiedReview
        return VerifiedReview(self).consolidate()

    def close(self): self.store.close()
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


def open_verified_run(root, *, suite_path=None):
    """Read locators, establish physical binding, then validate V authority."""
    raw = confined_file(Path(root), RUN_INPUT_PATH).read_bytes()
    record = decode_json(raw)
    VNextSchemaRegistry().validate(record, 'vnext_proposal_run_input_v1')
    require(raw == canonical_json_bytes(record), 'noncanonical V run input record')
    store = LocalAuthorityStore(root, job_id=record['job_id'])
    try:
        require(store.read(RUN_INPUT_PATH) == raw, 'V run selectors changed while opening')
        job = decode_json(store.read_descriptor())
        from whetstone.vnext_registry import SUPPORTED_SUITES
        require(job['contract_suite_version'] in SUPPORTED_SUITES, 'unknown V contract suite')
        path = suite_path if suite_path is not None else CONTRACT_ROOT / 'suites' / (job['contract_suite_version'] + '.json')
        run = VerifiedRun(store, suite_path=path)
        run.inspect()
        return run
    except BaseException:
        store.close()
        raise
