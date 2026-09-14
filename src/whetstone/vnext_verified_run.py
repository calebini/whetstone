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
        require(values['job']['job_id'] == self.run._record['job_id'], 'V run selectors belong to another job')
        entries = {entry['path']: entry for entry in reader.suite.manifest['algorithms']}
        require(ALGORITHM in entries, 'verified run algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
                'installed verified run algorithm differs from pinned suite')
        return reader, values

    def _round_inputs(self, reader, values, number):
        result = super()._round_inputs(reader, values, number)
        # The existing seed-only Reviewer protocol cannot validate a V
        # multi-base sequence. Refuse runtime-produced feedback until its V
        # sequence owner is integrated; explicit staged inputs remain usable.
        require(result['feedback_ref']['path'] != f'rounds/round-{number}/reviewer_feedback.json',
                'runtime V Reviewer evidence requires the verified review sequence owner')
        self.run._guard(self.run.store.read)
        return result


def _require_staged_boundary(store):
    try: claims = store.list_directory('rounds/review_index')
    except FileNotFoundError: claims = ()
    require(not claims, 'runtime V Reviewer sequence cannot be bypassed by alternate round inputs')


class _RunOperator(VerifiedOperator):
    def _observe(self, proof):
        view = super()._observe(proof)
        if view.outcome != 'materialization_required': _require_staged_boundary(self.store)
        return view


class _RunPromotion(VerifiedPromotion):
    def _select(self, proof):
        _require_staged_boundary(self.store)
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
    def request(self, **options): return self._operator().request(**options)
    def register(self, **options): return self._operator().register(**options)
    def verify(self, **options): return self._operator().verify(**options)
    def recover_registration(self): return self._operator().recover_registration()
    def answers(self, **options): return self._operator().answers(**options)
    def submit_answer(self, **options): return self._operator().submit_answer(**options)
    def select_followup(self, **options): return self._operator().select_followup(**options)
    def promote(self, **options): return _RunPromotion(self.store, history=self._history()).promote(**options)
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
