"""Bounded, evidence-derived Phase 2 continuation; no terminal or public mode."""
from copy import copy, deepcopy
import re

from whetstone.hashing import semantic_changes
from whetstone.oscillation import OscillationTracker
from whetstone.scheduler import PhaseScheduler, ProfileStep
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_validation import ArtifactReader
from whetstone.vnext_verified_history import _snapshot
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_client import _Journal
from whetstone.vnext_verified_phase2_consumption import _projection
from whetstone.vnext_verified_phase2_entry import ENTRY_PATH, STATE_FIELD
from whetstone.vnext_verified_phase2_review import DIRECTORY, REQUEST_PATH
from whetstone.vnext_verified_phase2_round import _HistoricalAdvice, _Round, _entry_prefix, _constraints, _pins as round_pins
from whetstone.vnext_verified_work import VerifiedWork

ALGORITHM = 'algorithms/vnext_verified_phase2_sequence_v1.md'
ROOT = 'rounds/phase2/review_requests'


def supported(proof):
    return any(row['path'] == ALGORITHM for row in proof.reader.suite.manifest['algorithms'])


def _pins(proof):
    round_pins(proof)
    pins = {r['path']:r['sha256'] for family in ('algorithms','schemas') for r in proof.reader.suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/vnext_phase2_review_request_v2.schema.json',
                 'schemas/vnext_phase2_consumption_v2.schema.json'):
        require(path in pins and pins[path] == sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'Phase 2 continuation contract is outside supported suite or changed', path)


def _at(proof, reference):
    proof.values(reference)
    index = next(i for i,p in enumerate(proof.pointers) if _snapshot(p) == reference)
    result = copy(proof)
    result.pointers = proof.pointers[:index+1]
    result.latest = deepcopy(reference)
    return result


class _Evidence:
    """Invocation-local byte checks, never a cache or a replacement authority view."""
    def __init__(self, store):
        self.source, self.reads = store, {}
    def __getattr__(self, name): return getattr(self.source, name)
    def read(self, path):
        try: raw = self.source.read(path)
        except FileNotFoundError:
            self.reads[path] = None
            raise
        self.reads[path] = raw
        return raw
    def check(self, snapshot):
        for path, expected in snapshot.items():
            try: raw = self.source.read(path)
            except FileNotFoundError: raw = None
            require(raw == expected, 'Phase 2 predecessor/source changed', path)
    def synchronize(self, token, snapshot, descriptor):
        self.check(snapshot)
        for path, raw in snapshot.items():
            if raw is not None and path != descriptor:
                self.source.synchronize_existing(token, path, expected=raw)
        self.check(snapshot)


class _Pass(_HistoricalAdvice, _Round):
    def __init__(self, run, evidence, proof, binding, entry, *, ordinal, number, step, previous, scheduler, snapshot):
        super().__init__(run)
        self.store = evidence
        self.proof, self.binding, self.entry = proof, binding, entry
        self.ordinal, self.number, self.step = ordinal, number, step
        self.previous, self.scheduler, self.snapshot = previous, deepcopy(scheduler), snapshot
        self.directory = DIRECTORY if ordinal == 1 else ROOT+f'/pass-{ordinal}'
        self.request_path = self.directory+'/request.json'
        self.consumption_path = self.directory+'/execution/consumption.json'
        self.consumption_schema = 'vnext_phase2_consumption_v1' if ordinal == 1 else 'vnext_phase2_consumption_v2'
        self.advice_path = self.directory+'/execution/finding_advice.json'
        self.binding_path = self.directory+'/execution/advice_binding.json'

    def _build_review(self, proof, transport):
        self.store.check(self.snapshot)
        return self._render_review(proof, transport, self.binding, self.entry, self.number, self.step,
            directory=self.directory, previous_consumption=self.previous)

    def _committed_request(self, proof):
        raw = self.store.read(self.request_path)
        schema = getattr(self, 'request_schema',
                         'vnext_phase2_review_request_v1' if self.ordinal == 1 else 'vnext_phase2_review_request_v2')
        request = proof.reader.json(dict(path=self.request_path, hash=sha256_bytes(raw)), schema)
        result = self._build_review(proof, request['transport'])
        require(result.committed, 'Phase 2 continuation requires complete request dependencies')
        return result

    def _project(self, bound, review, receipt):
        packet = _projection(bound, review, receipt, scheduler=self.scheduler)
        if self.ordinal == 1: return packet
        packet.update(schema_version='vnext-phase2-consumption-v2', previous_consumption=deepcopy(self.previous),
            accepted_passes=self.ordinal,
            result=_ref(self.directory+'/execution/result.json',receipt))
        return packet

    def _synchronize_request(self, store, proof, bound):
        self.store.synchronize(store._token, self.snapshot, self.run._record['descriptor']['path'])
        for ref in bound.inputs['sources']+[bound.request['entry'], bound.request['configuration'],
                bound.inputs['configuration']['rubric']['artifact'], bound.request['base_pointer'],
                bound.request['inputs'], bound.request['prompt'], bound.request_ref]:
            raw = proof.reader.raw(ref)
            if ref != self.run._record['descriptor']:
                self.store.synchronize_existing(store._token,ref['path'],expected=raw)
        values = proof.values(proof.latest)
        pointer = proof.pointers[-1]
        for path, raw in ((pointer['verified_draft_path'],values['base']),
                          (pointer['verified_section_identity_map_path'],canonical_json_bytes(values['base_map']))):
            self.store.synchronize_existing(store._token,path,expected=raw)
        require(self._committed_request(proof)==bound, 'Phase 2 continuation request changed during barriers')

    def _validate_round(self, proof, number, packet):
        return _validate_frame(proof, self, number, packet)


def _validate_frame(proof, owner, number, record):
    bound, _, _, _, _, view = owner._advice_view(owner.proof, None)
    require(view['status']=='bound', 'Phase 2 correction requires committed advice')
    binding = view['binding']
    require(number == bound.request['round_number'] == record['round_number']
        and record['base_pointer'] == bound.request['base_pointer']
        and record['feedback'] == binding['feedback'] and record['advice'] == binding['advice']
        and record['constraints'] == _constraints(proof) and not record['decision_refs']
        and record['job_id'] == proof.seed_values['job']['job_id'], 'Phase 2 round differs from sequence evidence')
    require(any(r['classification']=='editor_fixable' for r in binding['findings'])
        and all(r['classification'] in {'editor_fixable','deferable'} for r in binding['findings']),
        'Phase 2 correction has unresolved operator or authority decisions')
    # Stamping versioned corrections is a separate candidate-protocol milestone.
    from whetstone.versioning import _find_version_target
    require(_find_version_target(bound.inputs['draft']) is None, 'Phase 2 version maintenance is not implemented')
    return dict(configuration=deepcopy(bound.inputs['configuration']),request=deepcopy(bound.request))


def _claims(store):
    try: entries = store.list_directory(ROOT)
    except FileNotFoundError: return []
    numbers = []
    for name, kind in entries:
        if name.startswith('.vnext-tmp-'): continue
        require(kind=='directory' and (name=='first' or re.fullmatch(r'pass-([2-9]|[1-9][0-9]+)',name)),
                'unknown Phase 2 request claim',name)
        if name!='first': numbers.append(int(name[5:]))
    numbers.sort()
    require(numbers==list(range(2,len(numbers)+2)), 'Phase 2 request claims are not contiguous')
    return numbers


def sequence(proof, *, through=None):
    """Replay a bounded prefix; future promotions never prove their own inputs."""
    _pins(proof)
    evidence = _Evidence(proof.owner.run.store)
    tracked = copy(proof)
    tracked.store = evidence
    tracked.reader = ArtifactReader(None,proof.reader.suite,read=evidence.read)
    prefix = _entry_prefix(tracked)
    original = _HistoricalAdvice(proof.owner.run)
    original.store = evidence
    binding = original._committed_binding(prefix)
    entry = original._entry_view(prefix,binding)
    first = original._committed_request(prefix)
    scheduler = PhaseScheduler(ProfileStep(r['name'],round_budget=r['budget'],repeat_if_blockers=True)
                               for r in binding.configuration['profiles'])
    claims = _claims(evidence) if through is None else list(range(2,through-first.request['round_number']+2))
    previous, frames, clean = None, [], set()
    reference = deepcopy(prefix.latest)
    feedback_tracker = OscillationTracker()
    draft_tracker = OscillationTracker()
    draft_tracker.record_draft(round_number=first.request['round_number']-1,
        draft_hash_value=sha256_bytes(prefix.values(reference)['base']), semantic_changes=[])
    gate, next_owner = 'review', None
    # Only known claims are traversed. A not-yet-published successor is rendered on demand.
    for ordinal in range(1,len(claims)+3):
        if gate != 'review':
            require(ordinal > len(claims)+1, 'Phase 2 successor bypasses predecessor gate')
            break
        step_index = scheduler.index
        if step_index >= len(scheduler.steps):
            gate='closeout_required';break
        step = scheduler.steps[step_index];state=scheduler.states[step_index]
        step_record=dict(index=step_index+1,profile=step.profile,round_budget=step.effective_round_budget,
                         rounds_used=state.rounds_used,pass_number=state.rounds_used+1)
        baseproof = _at(tracked,reference)
        directory = DIRECTORY if ordinal==1 else ROOT+f'/pass-{ordinal}'
        snapshot = {p:r for p,r in evidence.reads.items() if not p.startswith(directory+'/')}
        owner = _Pass(proof.owner.run,evidence,baseproof,binding,entry,ordinal=ordinal,
            number=first.request['round_number']+ordinal-1,step=step_record,previous=previous,
            scheduler=scheduler,snapshot=snapshot)
        from whetstone.vnext_verified_phase2_closeout import declaration_owner
        owner = declaration_owner(owner, frames, clean)
        raw=owner._optional(owner.request_path)
        if raw is None:
            require(ordinal==len(claims)+2 or ordinal==len(claims)+1, 'missing Phase 2 request before successor')
            next_owner=owner;gate='review';break
        bound=owner._committed_request(baseproof)
        journal=_Journal(owner,baseproof,evidence,bound)
        outcomes,review,receipt=journal.inspect(bound.request)
        frame=dict(owner=owner,bound=bound,journal=journal,outcomes=outcomes,review=review,receipt=receipt)
        frames.append(frame)
        if receipt is None:
            gate='pending_review';break
        _,_,_,consumption,consumed=owner._consumption_view(baseproof)
        frame.update(consumption=consumption,consumed=consumed)
        if not consumed:
            gate='result_consumption_required';break
        if through == owner.number:
            return dict(frames=frames,gate='historical',owner=owner)
        if bound.request['schema_version'] == 'vnext-phase2-review-request-v3':
            serious = any(r['in_scope'] and r['normalized_severity'] in {'major','blocker'}
                          for r in review['feedback']['feedback'])
            scheduler.record_result(step.profile,blocker_count=int(serious),major_count=0)
            if not serious: clean.add(step.profile)
            gate='declaration_closeout_required'
            break
        previous=_ref(owner.consumption_path,consumption)
        finding_rows=consumption['findings']
        advice_raw=owner._optional(owner.binding_path)
        if advice_raw is not None:
            view=owner._advice_view(baseproof,None)[-1]
            finding_rows=view['binding']['findings']
        serious=any(r['in_scope'] and r['normalized_severity'] in {'major','blocker'} for r in review['feedback']['feedback'])
        actionable=any(r['classification']!='deferable' for r in finding_rows)
        unknown=any(r['classification'] not in {'deferable','editor_fixable'} for r in finding_rows)
        # Use only proven successors: during historical replay the current candidate is not proven yet.
        index=next(i for i,p in enumerate(proof.pointers) if _snapshot(p)==reference)
        successor=proof.pointers[index+1] if index+1<len(proof.pointers) and _snapshot(proof.pointers[index+1])['path'] in proof.bases else None
        if successor is not None:
            creation=tracked.reader.json(dict(path=successor['source_candidate_creation_event_path'],
                hash=successor['source_candidate_creation_event_hash']),'candidate_creation_event_v1')
            require(creation['round_number']>=owner.number,'Phase 2 promotion source precedes sequence cursor')
            # Several clean reviews may share a base before a later step edits it.
            # Consume the proven successor only at its actual source review.
            if creation['round_number']>owner.number:successor=None
        mutated=False
        if successor is not None:
            require(actionable and not unknown and advice_raw is not None, 'Phase 2 promotion bypasses unresolved advice')
            require(creation['round_number']==owner.number and successor['previous_verified_pointer_hash']==reference['hash'],
                    'Phase 2 successor is not this review correction')
            newref=_snapshot(successor)
            oldbase=baseproof.values(reference)['base'];newbase=tracked.values(newref)['base']
            mutated=oldbase!=newbase
            detection=draft_tracker.record_draft(round_number=owner.number,draft_hash_value=sha256_bytes(newbase),
                semantic_changes=semantic_changes(oldbase.decode(),newbase.decode()))
            if detection is not None: gate='oscillation_requires_resolution'
            reference=newref
            if mutated: clean.clear()
        elif actionable:
            gate='operator_or_advice_required' if unknown else 'correction_required'
        feedback_detection=feedback_tracker.record_phase2_feedback(round_number=owner.number,reviewer_feedback=review['feedback'])
        if feedback_detection is not None: gate='oscillation_requires_resolution'
        if not serious and not mutated: clean.add(step.profile)
        scheduler.record_result(step.profile,blocker_count=int(serious),major_count=int(not serious and mutated))
        if scheduler.states[step_index].residual_status is not None and gate=='review': gate='budget_exhausted'
        # Existing declarations require their own maintenance/verification owner.
        from whetstone.vnext_verified_phase2_closeout import supported as closeout_supported
        if not closeout_supported(proof) and any(owner._optional(path) is not None for path in
                ('rounds/convergence_declaration.md','convergence_declaration.md')):
            gate='declaration_maintenance_required'
    else:
        raise ValueError('Phase 2 sequence scan did not reach a boundary')
    if through is not None: require(False,'Phase 2 round lacks committed sequence consumption')
    # A suffix cannot lurk beyond a pending result or a terminal gate.
    if frames and gate != 'review':
        require(len(claims)+1<=len(frames),'Phase 2 successor bypasses incomplete predecessor')
    require(reference==proof.latest,'Phase 2 sequence has not accounted for current authority')
    proof.guard(proof.store.read)
    return dict(frames=frames,gate=gate,owner=next_owner,reference=reference,scheduler=scheduler,
                clean=sorted(clean),accepted_passes=sum(bool(f.get('receipt')) for f in frames))


def validate_round(proof, number, record):
    state=sequence(proof,through=number)
    return _validate_frame(proof,state['owner'],number,record)


def _status(state):
    owner=state['owner'] or (state['frames'][-1]['owner'] if state['frames'] else None)
    return dict(gate=state['gate'],accepted_passes=state['accepted_passes'],current_pointer=deepcopy(state['reference']),
        profiles=[dict(step_index=i,**r) for i,r in enumerate(state['scheduler'].status()['profiles'],1)],
        clean_profiles=state['clean'],pass_number=owner.ordinal if owner else None,
        round_number=owner.number if owner else None,phase_complete=False)


class _Continuation(_HistoricalAdvice):
    def _proof(self, read):
        proof=super()._proof(read);_pins(proof);return proof
    def _observe(self, proof):
        result = VerifiedWork._observe(self,proof)
        if result.outcome == 'work_available':
            from whetstone.vnext_verified_materialization import STATE_PATH
            from whetstone.vnext_contracts import decode_json
            entry_raw = self.store.read(ENTRY_PATH)
            state = decode_json(self.store.read(STATE_PATH))
            require(state.get(STATE_FIELD) == dict(path=ENTRY_PATH,hash=sha256_bytes(entry_raw)),
                    'Phase 2 entry state recovery is required before continuation')
        return result

    def status(self):
        proof=self._proof(self.store.read)
        work=self._observe(proof)
        if work.outcome!='work_available': return work
        return _status(sequence(proof))

    def bind_next(self, transport):
        def perform(store,proof):
            state=sequence(proof)
            if state['gate']=='pending_review':
                owner=state['frames'][-1]['owner']
            elif state['gate']=='review': owner=state['owner']
            else: return _status(state)
            require(owner.ordinal>1,'first Phase 2 request uses its existing owner')
            from whetstone.vnext_verified_materialization import STATE_PATH
            owner.snapshot[STATE_PATH] = self.store.read(STATE_PATH)
            expected=owner._build_review(owner.proof,deepcopy(transport))
            owner.store.synchronize(store._token,owner.snapshot,self.run._record['descriptor']['path'])
            if getattr(owner,'request_schema',None)=='vnext_phase2_review_request_v3':
                owner._synchronize_declaration(store)
            for ref in expected.inputs['sources']+[expected.request['entry'],expected.request['configuration'],
                    expected.inputs['configuration']['rubric']['artifact'],expected.request['base_pointer']]:
                if ref != self.run._record['descriptor']:
                    self.store.synchronize_existing(store._token,ref['path'],expected=proof.reader.raw(ref))
            require(owner._build_review(owner.proof,transport)==expected,'Phase 2 inputs changed during barriers')
            for ref,value in ((expected.request['inputs'],expected.inputs),(expected.request['prompt'],expected.prompt.encode()),
                              (expected.request_ref,expected.request)):
                store.publish(store._token,ref['path'],value)
            return owner._committed_request(owner.proof)
        return self._execute(perform)

    def operation(self, ordinal, action, **kwargs):
        require(type(ordinal) is int and ordinal>1,'continuation operations require an explicit later pass')
        def perform(store,proof):
            state=sequence(proof)
            frame=next((f for f in state['frames'] if f['owner'].ordinal==ordinal),None)
            require(frame is not None,'Phase 2 pass is not committed')
            owner=frame['owner']
            require(owner.proof.latest==proof.latest,'historical Phase 2 pass cannot launch current work')
            require(frame is state['frames'][-1], 'completed predecessor replay cannot advance a successor')
            from whetstone.vnext_verified_materialization import STATE_PATH
            owner.snapshot[STATE_PATH] = self.store.read(STATE_PATH)
            owner._execute=lambda operation: operation(store,owner.proof)
            if action=='execute': return owner.execute(**kwargs)
            if action=='consume': return owner.consume()
            if getattr(owner,'request_schema',None)=='vnext_phase2_review_request_v3':
                require(False,'declaration review is read-only; no correction admission is supported')
            if action=='advice': return owner.bind(**kwargs)
            if action=='admit':
                require(state['gate']=='correction_required','Phase 2 round is blocked by sequence gate')
                return owner.admit()
            raise ValueError('unknown Phase 2 continuation operation')
        return self._execute(perform)
