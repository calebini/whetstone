"""Fenced immutable resolution publication and recovery-only state projection."""
from copy import deepcopy

from whetstone.vnext_contracts import canonical_json_bytes, decode_json, require
from whetstone.vnext_phase2_resolution import ROOT, STATE_FIELD, pins
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_correction_failure import _CorrectionFailure
from whetstone.vnext_verified_phase2_sequence import sequence


class _Resolution(_CorrectionFailure):
    def _proof(self, read):
        proof = super()._proof(read)
        pins(proof)
        return proof

    def _sources(self):
        return {p:r for p,r in self.store.reads.items() if not p.startswith(ROOT+'/') and p != STATE_PATH}

    def _resolution_view(self, proof):
        state = sequence(proof)
        records = [f['resolution'] for f in state['frames'] if f.get('resolution')]
        return state, records

    @staticmethod
    def _projection(records):
        return [deepcopy(r['reference']) for r in records if r['committed']]

    def _public(self, state, records):
        projection = self._projection(records)
        stored = decode_json(self.store.read(STATE_PATH))
        return dict(gate=state['gate'], records=[{k:deepcopy(v) for k,v in r.items() if k != 'assets'} for r in records],
            publication_required=any(r['pending_paths'] for r in records), history=projection,
            state_current=stored.get(STATE_FIELD) == projection if records else STATE_FIELD not in stored,
            profile_clean=False, phase_complete=False, next_review_authorized=False)

    def status(self):
        proof = self._proof(self.store.read); work = self._observe(proof)
        if work.outcome != 'work_available': return work
        result = self._public(*self._resolution_view(proof))
        self.store.check(self._sources())
        return result

    def publish(self):
        def perform(store, proof):
            state, records = self._resolution_view(proof)
            snapshot = self._sources()
            self._barrier(store._token, snapshot)
            for record in records:
                for path, raw in record['assets'].items(): store.publish(store._token, path, raw)
                for path, raw in record['assets'].items():
                    self.store.synchronize_existing(store._token, path, expected=raw)
                snapshot.update(record['assets'])
                self.store.check(snapshot)
                store.publish(store._token, record['reference']['path'], record['packet'])
                snapshot[record['reference']['path']] = canonical_json_bytes(record['packet'])
                self.store.synchronize_existing(store._token, record['reference']['path'],
                    expected=canonical_json_bytes(record['packet']))
            self.store.check(snapshot)
            return self._public(*self._resolution_view(proof))
        return self._execute(perform)

    def recover(self):
        def perform(store, proof):
            state, records = self._resolution_view(proof)
            require(not any(r['pending_paths'] for r in records), 'publish resolution evidence before state recovery')
            snapshot = self._sources()
            self._barrier(store._token, snapshot)
            for record in records:
                for path, raw in [*record['assets'].items(),
                        (record['reference']['path'], canonical_json_bytes(record['packet']))]:
                    self.store.synchronize_existing(store._token, path, expected=raw)
                    snapshot[path] = raw
            before = self.store.read(STATE_PATH); stored = decode_json(before)
            projection = self._projection(records)
            if records: stored[STATE_FIELD] = projection
            else: stored.pop(STATE_FIELD, None)
            target = before if stored == decode_json(before) else canonical_json_bytes(stored)
            def validate(read, path, value):
                self.store.check(snapshot); proof.guard(read); self.run._guard(read)
                require(path == STATE_PATH and read(path) == before and value == target, 'resolution state changed')
                require(self._projection(self._resolution_view(proof)[1]) == projection, 'resolution evidence changed')
            if target != before: self.store.materialize(store._token, STATE_PATH, target, validate_target=validate)
            else: self.store.synchronize_existing(store._token, STATE_PATH, expected=target)
            result = self._public(*self._resolution_view(proof))
            require(result['state_current'], 'resolution state recovery incomplete')
            return dict(result, gate='resolution_state_recovered')
        return self._execute(perform)
