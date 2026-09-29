"""Unactivated horizontal, focused and pinned vertical V review/admission.

This owner exposes one review at a time. The focused route needs its separate
configuration pin. Vertical aggregation needs its own pin; extensions remain gated.
"""
from copy import deepcopy

from whetstone.vnext_review_configuration import focused_profile

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_proposal_admission import ProposalAdmission
from whetstone.vnext_proposal_package import validate_launch_package
from whetstone.vnext_proposal_run import round_input_path
from whetstone.vnext_review_requests import ReviewStep, _result
from whetstone.vnext_validation import ArtifactReader
from whetstone.vnext_verified_history import _snapshot
from whetstone.vnext_verified_review_requests import (
    _ReviewInputs, _VerifiedReviewRequest, _read_review_prefix, _run_bound_review,
)
from whetstone.vnext_verified_work import VerifiedWork

ALGORITHM = 'algorithms/vnext_verified_review_sequence_v1.md'


def _contract(proof):
    run = proof.owner.run
    require(not run._staged, 'runtime V Reviewer sequence cannot be bypassed or mixed with staged rounds')
    entries = {row['path']: row for row in proof.reader.suite.manifest['algorithms']}
    require(ALGORITHM in entries, 'verified review sequence algorithm is outside supported suite')
    require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == entries[ALGORITHM]['sha256'],
            'installed verified review sequence differs from pinned suite')
    review = proof.seed_values['review']
    from whetstone.vnext_verified_vertical_phase1 import enabled, pins
    if enabled(review):
        pins(proof.reader.suite)
        from whetstone.scheduler import profile_names_for_phase
        require(all(p['name'] in profile_names_for_phase(review['profile_set'], 'phase_1') for p in review['profiles']),
                'vertical selection requires Phase 1 profiles')
    require(review['review_mode'] in {'horizontal', 'vertical'} and review['workflow'] == 'standard',
            'verified review sequence requires standard horizontal or pinned vertical review')
    selected = focused_profile(review)
    return [row for row in review['profiles'] if selected is None or row['name'] == selected]


def _actionable(frame):
    return frame.review is not None and any(row['classification'] != 'deferable' for row in frame.review['findings'])


def _advance(proof, previous, reference):
    """A new base must be the next proven promotion of the preceding review."""
    old = proof.reader.json(previous.header['base_pointer'], 'current_verified_pointer_v1')
    new = proof.reader.json(reference, 'current_verified_pointer_v1')
    require(_actionable(previous) and new['promotion_ordinal'] == old['promotion_ordinal'] + 1
            and new['previous_verified_pointer_path'] == previous.header['base_pointer']['path']
            and new['previous_verified_pointer_hash'] == previous.header['base_pointer']['hash'],
            'Reviewer sequence changed base without its next committed promotion')
    creation = proof.reader.json({'path': new['source_candidate_creation_event_path'],
                                 'hash': new['source_candidate_creation_event_hash']}, 'candidate_creation_event_v1')
    require(creation['round_number'] == previous.request.number,
            'Reviewer base promotion belongs to another source round')


def _gate(profiles, counts, clean):
    if all(clean.values()): return 'review_complete', None
    # This is a bounded review gate, not a Phase 1 terminal or soft-budget sweep.
    for row in profiles:
        if not clean[row['name']]:
            if counts[row['name']] >= row['budget']: return 'budget_exhausted', None
            return 'review', row['name']


def _sequence(proof, *, through_round=None):
    from whetstone.vnext_verified_vertical_phase1 import enabled, sequence
    if enabled(proof.seed_values['review']):
        state = sequence(proof, through_round=through_round)
        return state.frames if through_round is not None else (state.frames, state.gate, state.profile)
    profiles = _contract(proof)
    from whetstone.vnext_verified_phase1_budget import Timeline
    timeline = Timeline(proof, profiles, through_round=through_round)
    profiles = timeline.profiles
    frames = _read_review_prefix(proof, through_round=through_round, require_complete=through_round is not None)
    counts = {row['name']: 0 for row in profiles}
    clean = {name: False for name in counts}
    base = _snapshot(proof.pointers[0])
    previous = None
    for index, frame in enumerate(frames):
        reference = frame.header['base_pointer']
        if reference != base:
            require(previous is not None, 'first V review must use the seed pointer')
            _advance(proof, previous, reference)
            clean = dict.fromkeys(clean, False)
            base = reference
        else:
            require(previous is None or not _actionable(previous),
                    'Reviewer sequence bypassed unresolved findings without promotion')
        timeline.advance(frame.request.number, counts, clean, base, frames[:index])
        gate, profile = _gate(profiles, counts, clean)
        require(gate == 'review' and frame.request.profile == profile,
                'V Reviewer claim differs from eligible profile or budget')
        if frame.receipt is not None:
            counts[profile] += 1
            clean[profile] = not any(row['in_scope'] and row['normalized_severity'] in {'major', 'blocker'}
                                     for row in frame.review['feedback']['feedback'])
        previous = frame
    if through_round is not None:
        timeline.finish()
        return frames
    if frames and frames[-1].receipt is None:
        timeline.finish()
        require(base == proof.latest, 'pending Reviewer request differs from current pointer')
        return frames, 'pending', frames[-1].request.profile
    if proof.latest != base:
        require(previous is not None, 'promoted root has no original Reviewer sequence')
        _advance(proof, previous, proof.latest)
        clean = dict.fromkeys(clean, False)
    elif previous is not None and _actionable(previous):
        timeline.finish()
        return frames, 'finding_admission', previous.request.profile
    timeline.advance(len(frames)+1, counts, clean, proof.latest, frames)
    timeline.finish()
    gate, profile = _gate(profiles, counts, clean)
    return frames, gate, profile


def validate_round_review(proof, number, record):
    """Bounded original replay; never recursively prove the current head."""
    from whetstone.vnext_verified_vertical_phase1 import enabled, validate_round
    vertical = enabled(proof.seed_values['review'])
    if vertical:
        validate_round(proof, number, record)
    else:
        _validate_horizontal_round(proof, number, record)
    run = proof.owner.run
    reference = run._record.get('launch_package')
    require(reference is not None, 'V reviewed round requires packaged mutation constraints')
    constraints = validate_launch_package(proof.reader, reference, descriptor_ref=run._record['descriptor'],
        review_ref=run._record['review_configuration'], authority=proof.seed_values['authority'])
    require(record['constraints'] == constraints, 'V round differs from packaged mutation constraints')


def _validate_horizontal_round(proof, number, record):
    frames = _sequence(proof, through_round=number)
    frame = frames[-1]
    require(_actionable(frame), 'proposal round requires actionable Reviewer findings')
    require(record['base_pointer'] == frame.header['base_pointer']
            and record['feedback'] == frame.receipt['feedback'] and record['advice'] == frame.receipt['advice'],
            'V round differs from original Reviewer base, feedback or advice')


def validate_current_sequence(proof):
    from whetstone.vnext_verified_phase2_sequence import supported as continuation_supported, sequence
    from whetstone.vnext_verified_phase2_entry import ENTRY_PATH
    if continuation_supported(proof):
        try: proof.store.read(ENTRY_PATH)
        except FileNotFoundError: pass
        else:
            from whetstone.vnext_verified_phase2_review import REQUEST_PATH
            try: proof.store.read(REQUEST_PATH)
            except FileNotFoundError: pass
            else: return sequence(proof)

    from whetstone.vnext_verified_phase2_round import supported, current_sequence, BINDING_PATH
    if supported(proof):
        try: proof.store.read(BINDING_PATH)
        except FileNotFoundError: pass
        else: return current_sequence(proof)
    from whetstone.vnext_version_entry import validate_pending_transition
    if validate_pending_transition(proof): return None
    run = proof.owner.run
    try: claims = proof.store.list_directory('rounds/review_index')
    except FileNotFoundError: claims = ()
    if claims or not run._staged: return _sequence(proof)
    return None


class VerifiedReview(VerifiedWork):
    def __init__(self, run):
        self.run = run
        super().__init__(run.store, history=run._history())

    def _observe(self, proof):
        view = super()._observe(proof)
        if view.outcome != 'materialization_required': validate_current_sequence(proof)
        return view

    def status(self):
        proof = self._proof(self.store.read)
        view = self._observe(proof)
        if view.outcome != 'work_available': return view
        frames, gate, profile = _sequence(proof)
        from whetstone.vnext_verified_vertical_phase1 import enabled, sequence
        if enabled(proof.seed_values['review']):
            state = sequence(proof)
            if gate != 'pending': return ReviewStep('not_started' if gate == 'review' else gate, state.number, profile)
        if gate == 'review': return ReviewStep('not_started', len(frames) + 1, profile)
        frame = frames[-1]
        if gate == 'pending':
            gate = ('valid_response' if frame.review is not None else
                    'invalid_review' if frame.outcomes and frame.outcomes[-1]['classification'] == 'invalid_review' else
                    'attempts_exhausted' if len(frame.outcomes) == 2 else
                    frame.outcomes[-1]['classification'] if frame.outcomes else 'prepared')
        return _result(gate, frame.request, frame.outcomes, frame.review, frame.receipt)

    def next(self, *, client=None, continuation=False):
        require(type(continuation) is bool, 'V Reviewer continuation must be an explicit boolean')
        def perform(store, proof):
            from whetstone.vnext_verified_phase1_budget import require_projected, synchronize as sync_budget
            require_projected(proof)
            sync_budget(store, proof)
            from whetstone.vnext_verified_phase2_entry import ENTRY_PATH
            try: store.read(ENTRY_PATH)
            except FileNotFoundError: pass
            else: require(False, 'Phase 1 Reviewer cannot run after committed Phase 2 entry')
            from whetstone.vnext_verified_vertical_phase1 import enabled, sequence, synchronize, publish_merge
            if enabled(proof.seed_values['review']):
                state = sequence(proof)
                synchronize(store, proof, state)
                frames, gate, profile = state.frames, state.gate, state.profile
                if gate == 'merge_required':
                    require(not continuation, 'vertical merge is not client continuation')
                    publish_merge(store, proof, state)
                    return ReviewStep('merge_complete', state.number, 'vertical')
                if gate not in {'review', 'pending'}:
                    require(not continuation, 'no incomplete V Reviewer request remains')
                    return ReviewStep(gate, state.number, profile)
                previous = frames[-2].header if gate == 'pending' and len(frames) > 1 else (
                    frames[-1].header if gate == 'review' and frames else None)
                request = _VerifiedReviewRequest(_ReviewInputs(store, proof, proof.latest), state.number, profile)
                return _run_bound_review(request, store._token,
                    previous=sha256_bytes(canonical_json_bytes(previous)) if previous else None,
                    client=client, continuation=continuation)
            frames, gate, profile = _sequence(proof)
            # Readable receipts may follow a lost durability acknowledgement.
            # Reestablish the completed prefix before any later claim or exit.
            for frame in frames:
                if frame.receipt is None: break
                prior = _VerifiedReviewRequest(_ReviewInputs(store, proof, frame.header['base_pointer']),
                                               frame.request.number, frame.request.profile)
                prior.synchronize(store._token, frame.header, frame.outcomes)
                prior.finish(store._token, frame.review)
            if gate not in {'review', 'pending'}:
                require(not continuation, 'no incomplete V Reviewer request remains')
                frame = frames[-1]
                return _result(gate, frame.request, frame.outcomes, frame.review, frame.receipt)
            number = len(frames) if gate == 'pending' else len(frames) + 1
            previous = frames[-2].header if gate == 'pending' and len(frames) > 1 else (
                frames[-1].header if gate == 'review' and frames else None)
            request = _VerifiedReviewRequest(_ReviewInputs(store, proof, proof.latest), number, profile)
            return _run_bound_review(request, store._token,
                previous=sha256_bytes(canonical_json_bytes(previous)) if previous else None,
                client=client, continuation=continuation)
        def checkpoint(store, proof):
            result = perform(store, proof)
            from whetstone.vnext_verified_phase1_budget import project_review_state
            project_review_state(self.run, store, proof)
            return result
        return self._execute(checkpoint)

    def admit(self, *, decision_refs=()):
        decisions = deepcopy(list(decision_refs))
        def perform(store, proof):
            frames, gate, _ = _sequence(proof)
            require(gate == 'finding_admission', 'no completed V review awaits finding admission')
            frame = frames[-1]
            from whetstone.vnext_verified_vertical_phase1 import enabled, sequence, publish_merge
            vertical = enabled(proof.seed_values['review'])
            if vertical:
                state = sequence(proof)
                merged = publish_merge(store, proof, state)
                number, receipt = state.number, merged
            else:
                number, receipt = frame.request.number, frame.receipt
            reference = self.run._record.get('launch_package')
            require(reference is not None, 'V reviewed round requires packaged mutation constraints')
            constraints = validate_launch_package(proof.reader, reference,
                descriptor_ref=self.run._record['descriptor'], review_ref=self.run._record['review_configuration'],
                authority=proof.seed_values['authority'])
            record = dict(schema_version='vnext-proposal-round-input-v1', job_id=proof.seed_values['job']['job_id'],
                round_number=number, base_pointer=deepcopy(proof.latest),
                feedback=deepcopy(receipt['feedback']), advice=deepcopy(receipt['advice']),
                decision_refs=decisions, constraints=constraints)
            raw = canonical_json_bytes(record)
            path = round_input_path(number)
            ref = dict(path=path, hash=sha256_bytes(raw))
            def read(name): return raw if name == path else store.read(name)
            reader = ArtifactReader(None, proof.reader.suite, read=read)
            admission = ProposalAdmission(store, suite_path=self.run.suite_path,
                descriptor_ref=self.run._record['descriptor'], review_ref=self.run._record['review_configuration'],
                seed_map_ref=self.run._record['seed_section_map'], round_refs={number: ref},
                launch_package_ref=reference)
            def preflight():
                proof.guard(store.read)
                validate_round_review(proof, number, record)
                admission._round_inputs(reader, proof.values(proof.latest), number)
            preflight()
            # Repeat the full durable Reviewer dependencies before exposing the
            # round selector; replay never consumes an additional invocation.
            request = _VerifiedReviewRequest(_ReviewInputs(store, proof, proof.latest), frame.request.number, frame.request.profile)
            request.synchronize(store._token, frame.header, frame.outcomes)
            request.finish(store._token, frame.review)
            for choice in decisions:
                for key in ('request', 'response'):
                    source = choice[key];content = store.read(source['path'])
                    require(sha256_bytes(content) == source['hash'], 'V round decision source changed')
                    store.publish(store._token, source['path'], content)
            preflight()
            store.publish(store._token, path, raw)
            proof.admission.load_inputs(store.read, number)
            return ref
        return self._execute(perform)
