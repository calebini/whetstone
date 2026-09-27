"""Fenced immutable operator gap acceptance; no clients or implicit selections."""
from copy import copy, deepcopy

from whetstone.vnext_contracts import canonical_json_bytes, decode_json, require
from whetstone.vnext_phase2_gap_acceptance import SCHEMA, bindings, path_for, pins, selection, validate
from whetstone.vnext_phase2_rubric import retained_entries
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_sequence import _Continuation, _Evidence, ROOT, sequence


class GapAcceptance(_Continuation):
    def __init__(self, run):
        tracked = copy(run);tracked.store = _Evidence(run.store)
        super().__init__(tracked)

    def _proof(self, read):
        proof = super()._proof(self.store.read);pins(proof.reader.suite);return proof

    def _context(self, proof, source_request=None):
        state = sequence(proof)
        frames = state['frames']
        if source_request is not None:
            index = next((i for i,row in enumerate(frames) if row['bound'].request_ref == source_request),None)
            require(index is not None, 'gap acceptance source request is unknown')
            frames = frames[:index+1]
        require(frames and frames[-1].get('consumed'), 'gap acceptance needs a consumed current review')
        frame = frames[-1]
        bindings(frame,proof.latest)  # A changed draft requires its committed resolution barrier.
        config = frame['owner'].binding.configuration
        require((config['target_phase'],config['target_mode']) == ('final','permissive'), 'target forbids rubric-gap acceptance')
        entries = {row['gap']['gap_id']:row for row in retained_entries(frames,proof.latest,accept=False)}
        return state, frame, entries

    def _available(self, state, frame, reference):
        require(frame is state['frames'][-1], 'only exact historical decision recovery is permitted')
        require(state['gate'] in {'operator_or_advice_required','correction_required','declaration_closeout_required','review'},
                'gap acceptance is blocked by the current sequence gate')
        signal = frame.get('signals')
        require(not signal or (not signal['terminal_state'] and 'freeze_prior_decision' not in signal['recommendations']),
                'gap acceptance cannot release a signal gate')
        require(frame['bound'].request['schema_version'] != 'vnext-phase2-review-request-v5',
                'review-only closeout cannot authorize new gap decisions')
        # Refuse even prepared consumers: their bound inputs must never change.
        directories = [ROOT+f"/pass-{frame['owner'].ordinal+1}",
            frame['owner'].directory+'/execution/finding_reconciliation',
            'rounds/phase2/closeouts/closeout-'+frame['bound'].request_ref['hash'],
            'rounds/phase2/signals/pass-'+str(frame['owner'].ordinal)]
        for path in directories:
            try: self.store.list_directory(path)
            except FileNotFoundError: continue
            require(False, 'gap acceptance would rewrite a prepared or committed consumer', path)
        from whetstone.vnext_proposal_run import round_input_path
        if reference == frame['bound'].request['base_pointer']:
            for path in (frame['owner'].advice_path, frame['owner'].binding_path, round_input_path(frame['owner'].number)):
                require(self._optional(path) is None, 'gap acceptance follows already selected source work', path)

    def context(self):
        proof = self._proof(self.store.read);work = self._observe(proof)
        if work.outcome != 'work_available': return work
        state, frame, entries = self._context(proof)
        existing = self._optional(path_for(frame,proof.latest))
        if existing is None: self._available(state,frame,proof.latest)
        result = dict(bindings=bindings(frame,proof.latest), gaps=[dict(selection=selection(row),gap=deepcopy(row['gap']))
            for row in entries.values() if row['gap']['status']=='unresolved'],
            committed=existing is not None, decision=proof.reader.json(_ref(path_for(frame,proof.latest),decode_json(existing)),SCHEMA)
            if existing is not None else None, resume_permitted=False, phase_complete=False)
        proof.guard(self.store.read);self.store.check(dict(self.store.reads))
        return result

    def accept(self, packet, *, dry_run=False):
        frozen = deepcopy(packet);require(type(dry_run) is bool, 'gap-acceptance dry_run must be an explicit boolean')
        def perform(store,proof):
            proof.reader.suite.registry.validate(frozen,SCHEMA)
            state, frame, entries = self._context(proof,frozen['source_request'])
            validate(frame,frozen,entries,proof.latest)
            path = path_for(frame,proof.latest);raw = canonical_json_bytes(frozen);observed = self._optional(path)
            require(observed is None or observed == raw, 'gap acceptance conflicts with immutable operator decision')
            if observed is None:self._available(state,frame,proof.latest)
            result = dict(reference=_ref(path,frozen),decision=deepcopy(frozen),committed=observed is not None,
                          phase_complete=False,resume_permitted=False)
            if dry_run:return result
            snapshot = dict(self.store.reads)
            frame['owner']._synchronize_request(store,frame['owner'].proof,frame['bound'])
            frame['journal'].synchronize(store._token,frame['bound'].request,frame['outcomes'])
            self.store.synchronize(store._token,snapshot,self.run._record['descriptor']['path'])
            fresh, current, entries = self._context(proof,frozen['source_request']);validate(current,frozen,entries,proof.latest)
            if observed is None:self._available(fresh,current,proof.latest)
            store.publish(store._token,path,raw)
            require(self.store.read(path) == raw, 'gap acceptance publication incomplete')
            proof.guard(self.store.read);self.run._guard(self.store.read);store.read_descriptor()
            return dict(result,committed=True)
        if dry_run:
            proof = self._proof(self.store.read);work = self._observe(proof)
            return perform(None,proof) if work.outcome=='work_available' else work
        return self._execute(perform)
