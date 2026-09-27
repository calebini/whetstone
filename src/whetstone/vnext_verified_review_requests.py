"""Unactivated V Reviewer journal; scheduling admission is a separate owner.

These private interfaces consume a fresh invocation-local history proof. They
do not select a profile/round, discharge findings or declare phase readiness.
"""
from copy import deepcopy
from dataclasses import dataclass
import re

from whetstone.vnext_contracts import canonical_json_bytes, decode_json, require, sha256_bytes
from whetstone.vnext_review_requests import _Request, _drive_request, _result
from whetstone.vnext_verified_review_protocol import prepare_verified_review, decode_verified_review, validate_verified_review_contract
from whetstone.vnext_verified_work import _BorrowedFence


class _ReviewInputs:
    def __init__(self, store, proof, base_reference):
        self.store, self.proof = store, proof
        self.base_reference = deepcopy(base_reference)
        self.launch_package = deepcopy(proof.owner._refs.get('launch_package'))

    def guard(self):
        if isinstance(self.store, _BorrowedFence): self.store._check()
        self.proof.guard(self.store.read)

    def values(self):
        self.guard()
        self.proof.owner._seed_inputs(self.store.read, expected_mode='verified_promotion')
        values = self.proof.values(self.base_reference)
        pointer = self.proof.reader.json(self.base_reference, 'current_verified_pointer_v1')
        require(sha256_bytes(values['base']) == pointer['verified_draft_hash'],
                'Reviewer base differs from its proven pointer')
        if values.get('base_inventory') is not None:
            self.proof.reader.json({
                'path': pointer['verified_draft_path'].rsplit('/', 1)[0] + '/preservation_inventory_candidate.json',
                'hash': sha256_bytes(canonical_json_bytes(values['base_inventory'])),
            }, 'vnext_preservation_inventory_v2')
        self.guard()
        return self.proof.reader, values, pointer

    def require_live(self):
        require(isinstance(self.store, _BorrowedFence), 'historical Reviewer evidence cannot invoke or publish')
        self.store._check()
        self.guard()
        require(self.base_reference == self.proof.latest, 'live Reviewer requires its exact current base pointer')


class _VerifiedReviewRequest(_Request):
    def schema(self):
        from whetstone.vnext_verified_phase1_budget import supported, pins
        if supported(self.run.proof.reader.suite):
            pins(self.run.proof.reader.suite)
            return 'vnext_review_request_v3'
        return 'vnext_review_request_v2'

    def synchronize(self, token, header, outcomes):
        super().synchronize(token, header, outcomes)
        from whetstone.vnext_verified_focused_phase1 import round_assets
        for path, raw in round_assets(self).items(): self.store.publish(token, path, raw)

    def finish(self, token, review):
        from whetstone.vnext_verified_focused_phase1 import round_assets
        assets = round_assets(self, review)
        if assets: self.recheck()
        for path, raw in assets.items(): self.store.publish(token, path, raw)
        return super().finish(token, review)

    def prepare(self, run, *, round_number, profile):
        return prepare_verified_review(run, round_number=round_number, profile=profile)

    def decode_review(self, raw):
        return decode_verified_review(raw, self.preflight, feedback_path=self.feedback_path)

    def header(self, transport, previous):
        header = super().header(transport, previous)
        header.update(schema_version='vnext-review-request-v2', base_pointer=deepcopy(self.run.base_reference))
        if self.schema() == 'vnext_review_request_v3':
            from whetstone.vnext_verified_phase1_budget import records
            header.update(schema_version='vnext-review-request-v3',
                          budget_extensions=[r[0] for r in records(self.run.proof, through_round=self.number)])
        self.schemas.validate(header, self.schema())
        return header

    def inspect(self, header):
        if header is not None:
            self.schemas.validate(header, self.schema())
            require(header == self.header(header['transport'], header['previous_request_hash']),
                    'V Reviewer claim differs from its original base and inputs')
        result = super().inspect(header)
        outcomes, review, receipt = result
        from whetstone.vnext_verified_focused_phase1 import round_assets
        for path, expected in round_assets(self, review).items():
            try: raw = self.store.read(path)
            except FileNotFoundError: raw = None
            require((raw is None and receipt is None) or raw == expected,
                    'focused round evidence conflicts or is missing', path)
        return result

    def read_claim(self, previous):
        try: raw = self.store.read(self.index_path)
        except FileNotFoundError: raw = None
        header = decode_json(raw) if raw is not None else None
        if header is not None:
            require(raw == canonical_json_bytes(header), 'noncanonical V Reviewer claim')
            self.schemas.validate(header, self.schema())
            require(header['previous_request_hash'] == previous, 'V Reviewer predecessor claim differs')
        return header, *self.inspect(header)


@dataclass(frozen=True)
class _ReviewFrame:
    request: _VerifiedReviewRequest
    header: dict
    outcomes: tuple
    review: dict | None
    receipt: dict | None


def _read_review_prefix(proof, *, through_round=None, require_complete=False):
    """Reproduce original request evidence using only this proof's known bases.

    A bounded caller reads exact paths 1..N without listing future claims.
    This verifies journal bindings, not scheduler/profile/budget eligibility.
    Returned request handles are read-only and must stay in this invocation.
    """
    require(type(require_complete) is bool, 'Reviewer completion requirement must be an explicit boolean')
    validate_verified_review_contract(proof.reader.suite)
    proof.guard(proof.store.read)
    if through_round is None:
        try: entries = proof.store.list_directory('rounds/review_index')
        except FileNotFoundError: entries = ()
        numbers = []
        for name, kind in entries:
            if name.startswith('.vnext-tmp-'): continue
            match = re.fullmatch(r'request-([1-9][0-9]*)\.json', name)
            require(match is not None and kind == 'file', 'invalid V Reviewer sequence claim')
            numbers.append(int(match[1]))
        from whetstone.vnext_verified_vertical_phase1 import enabled
        if not enabled(proof.seed_values['review']):
            require(sorted(numbers) == list(range(1, len(numbers) + 1)), 'V Reviewer sequence has an ordinal gap')
        numbers = sorted(numbers)
    else:
        require(type(through_round) is int and through_round > 0, 'invalid V Reviewer prefix boundary')
        from whetstone.vnext_verified_vertical_phase1 import enabled
        numbers = list(range(1, through_round + 1))
        if enabled(proof.seed_values['review']):
            numbers = []
            for n in range(1, through_round):
                try: proof.store.read(f'rounds/review_index/request-{n}.json')
                except FileNotFoundError: continue
                numbers.append(n)
    frames, previous = [], None
    for number in numbers:
        path = f'rounds/review_index/request-{number}.json'
        raw = proof.store.read(path)
        from whetstone.vnext_verified_phase1_budget import supported
        schema = 'vnext_review_request_v3' if supported(proof.reader.suite) else 'vnext_review_request_v2'
        header = proof.reader.json({'path': path, 'hash': sha256_bytes(raw)}, schema)
        request = _VerifiedReviewRequest(_ReviewInputs(proof.store, proof, header['base_pointer']), number, header['profile'])
        replayed, outcomes, review, receipt = request.read_claim(previous)
        require(replayed == header and canonical_json_bytes(replayed) == raw, 'V Reviewer claim changed during replay')
        require(receipt is not None or (number == numbers[-1] and not require_complete),
                'V Reviewer prefix has an incomplete source request')
        frames.append(_ReviewFrame(request, deepcopy(header), tuple(outcomes), deepcopy(review), deepcopy(receipt)))
        previous = sha256_bytes(raw)
    proof.guard(proof.store.read)
    return tuple(frames)


def _run_bound_review(request, token, *, previous, client=None, continuation=False):
    """Execute one already-selected request within the caller's actual fence."""
    require(type(continuation) is bool, 'V Reviewer continuation must be an explicit boolean')
    request.run.require_live()
    require(token is request.store._token, 'V Reviewer cannot borrow another ownership token')
    header, outcomes, review, receipt = request.read_claim(previous)
    if receipt is not None:
        require(not continuation, 'completed Reviewer request is not technical continuation')
        request.synchronize(token, header, outcomes)
        receipt = request.finish(token, review)
        return _result('complete', request, outcomes, review, receipt)
    if header is not None and not continuation:
        return _result('continuation_required', request, outcomes, review, receipt)
    require(header is not None or not continuation, 'new Reviewer request is not technical continuation')
    if review is not None:
        request.synchronize(token, header, outcomes)
        receipt = request.finish(token, review)
        return _result('complete', request, outcomes, review, receipt)
    if outcomes and (outcomes[-1]['classification'] == 'invalid_review' or len(outcomes) == 2):
        request.synchronize(token, header, outcomes)
        return _result('invalid_review' if outcomes[-1]['classification'] == 'invalid_review' else 'attempts_exhausted',
                       request, outcomes)
    require(client is not None, 'V Reviewer invocation requires a configured client')
    return _drive_request(request, token, header=header, outcomes=outcomes, review=review,
                          previous=previous, client=client, continuation=continuation)
