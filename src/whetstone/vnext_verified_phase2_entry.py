"""Fenced, unchanged-draft Phase 2 entry and recovery; no Phase 2 execution."""
from copy import deepcopy
from dataclasses import dataclass, replace

from whetstone.versioning import promote_spec_text_for_phase2
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_binding import _Binding, _ref, CONFIG_SCHEMA, REQUEST_PATH, REQUEST_SCHEMA
from whetstone.vnext_verified_work import VerifiedWork


ALGORITHM = 'algorithms/vnext_verified_phase2_entry_v1.md'
SCHEMA = 'vnext_phase2_entry_v1'
ENTRY_PATH = 'rounds/phase2/entry.json'
STATE_FIELD = 'vnext_phase2_entry'


@dataclass(frozen=True)
class Phase2EntryState:
    outcome: str
    entry: dict
    entry_ref: dict
    committed: bool
    state_current: bool
    pending_paths: tuple
    execution_permitted: bool = False
    resume_permitted: bool = False
    apply_back_permitted: bool = False


class _Entry(_Binding):
    def _proof(self, read):
        proof = super()._proof(read)
        entries = {row['path']: row for family in ('algorithms', 'schemas')
                   for row in proof.reader.suite.manifest[family]}
        paths = {ALGORITHM, 'schemas/' + SCHEMA + '.schema.json'}
        require(paths <= entries.keys(), 'verified Phase 2 entry contracts are outside supported suite')
        for path in paths:
            require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == entries[path]['sha256'],
                    'installed verified Phase 2 entry contract differs from pinned suite', path)
        return proof

    def _committed_binding(self, proof):
        raw = self._optional(REQUEST_PATH)
        require(raw is not None, 'Phase 2 entry requires a committed immutable request')
        request = proof.reader.json(dict(path=REQUEST_PATH, hash=sha256_bytes(raw)), REQUEST_SCHEMA)
        from whetstone.vnext_phase2_targets import read_configuration
        config = read_configuration(proof.reader,request['configuration'])
        binding = self._build(proof, config)
        require(binding.materialized, 'Phase 2 entry requires a complete committed binding')
        return binding

    def _entry_view(self, proof, binding):
        raw = proof.reader.raw(binding.request['current_verified_draft'])
        text = raw.decode('utf-8')
        projected, before, after, changed = promote_spec_text_for_phase2(text)
        require(not changed and projected.encode('utf-8') == raw and before == after,
                'Phase 2 version maintenance requires the V candidate protocol; unchanged entry only')
        entry = dict(schema_version='vnext-phase2-entry-v1', phase='phase_2', job_id=binding.request['job_id'],
            entry_request=deepcopy(binding.request_ref), configuration=deepcopy(binding.configuration_ref),
            current_verified_pointer=deepcopy(proof.latest), current_verified_draft=deepcopy(binding.request['current_verified_draft']),
            current_verified_map=deepcopy(binding.request['current_verified_map']),
            phase1_closeout=deepcopy(binding.request['phase1_closeout']),
            version=dict(before=before, after=after, changed=False))
        proof.reader.suite.registry.validate(entry, SCHEMA)
        reference = _ref(ENTRY_PATH, entry)
        existing = self._optional(ENTRY_PATH)
        require(existing is None or existing == canonical_json_bytes(entry), 'Phase 2 entry commit conflicts with current evidence')
        state = decode_json(self.store.read(STATE_PATH))
        require(isinstance(state, dict), 'Phase 2 state projection requires a JSON object')
        require(existing is not None or STATE_FIELD not in state, 'Phase 2 state references a missing entry commit')
        current = existing is not None and state.get(STATE_FIELD) == reference
        pending = (() if existing is not None else (ENTRY_PATH,)) + (() if current else (STATE_PATH,))
        proof.guard(self.store.read)
        self.run._guard(self.store.read)
        return Phase2EntryState('entered' if current else 'entry_state_recovery_required' if existing else 'entry_required',
                                entry, reference, existing is not None, current, pending)

    def inspect_entry(self):
        proof = self._proof(self.store.read)
        work = VerifiedWork._observe(self, proof)
        if work.outcome != 'work_available':
            proof.guard(self.store.read)
            self.run._guard(self.store.read)
            return work
        return self._entry_view(proof, self._committed_binding(proof))

    def _synchronize_entry_sources(self, store, proof, binding):
        closeout = self.evaluate(proof)
        checked = self._synchronize_sources(store, proof, closeout)
        require(checked.materialized, 'Phase 1 closeout disappeared before Phase 2 entry')
        state_raw = self.store.read(STATE_PATH)
        self.store.synchronize_existing(store._token, STATE_PATH, expected=state_raw)
        references = [checked.report_ref, checked.evidence_ref, binding.configuration_ref, binding.request_ref,
                      binding.configuration['rubric']['artifact'], binding.request['current_verified_draft'],
                      binding.request['current_verified_map']]
        for reference in references:
            self.store.synchronize_existing(store._token, reference['path'], expected=proof.reader.raw(reference))
        require(self._committed_binding(proof) == binding, 'Phase 2 binding changed during entry source synchronization')

    def enter(self):
        def publish(store, proof):
            binding = self._committed_binding(proof)
            expected = self._entry_view(proof, binding)
            self._synchronize_entry_sources(store, proof, binding)
            require(self._entry_view(proof, binding) == expected, 'Phase 2 entry changed during source synchronization')
            # Repeat publication barriers for visible commits after uncertain acknowledgement.
            store.publish(store._token, ENTRY_PATH, expected.entry)
            before = self.store.read(STATE_PATH)
            state = decode_json(before)
            target = before if state.get(STATE_FIELD) == expected.entry_ref else canonical_json_bytes(
                {**state, STATE_FIELD: expected.entry_ref})
            def validate_target(read, path, raw):
                proof.guard(read)
                self.run._guard(read)
                require(path == STATE_PATH and raw == target and read(path) == before
                        and read(ENTRY_PATH) == canonical_json_bytes(expected.entry),
                        'Phase 2 state target changed during entry recovery')
            if target != before:
                self.store.materialize(store._token, STATE_PATH, target, validate_target=validate_target)
            else:
                self.store.synchronize_existing(store._token, STATE_PATH, expected=target)
            result = self._entry_view(proof, self._committed_binding(proof))
            require(result.committed and result.state_current, 'Phase 2 entry state recovery incomplete')
            return replace(result, outcome='phase2_entry_recovered' if expected.committed else 'phase2_entered')
        return self._execute(publish)


def enter_verified_phase2(run):
    return _Entry(run).enter()


def inspect_verified_phase2_state(run):
    return _Entry(run).inspect_entry()
