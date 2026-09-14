"""Stage 1 recovery of derived V-mode mirrors; no promotion work."""
from copy import deepcopy
from dataclasses import dataclass

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_verified_history import _Proof, _same_store, _snapshot


ALGORITHM = 'algorithms/vnext_verified_materialization_v1.md'
STATE_PATH = 'rounds/run_state.json'
STATE_FIELD = 'vnext_current_verified'


@dataclass(frozen=True)
class MaterializationView:
    pointer: dict
    pending_paths: tuple
    recovery_kind: str | None


class VerifiedMaterialization:
    def __init__(self, store, *, history):
        _same_store(store, history.store)
        self.store, self.history = store, history

    def _proof(self, read):
        proof = _Proof(self.history, read).prove_lineage()
        algorithms = {entry['path']: entry for entry in proof.reader.suite.manifest['algorithms']}
        require(ALGORITHM in algorithms, 'verified materialization algorithm is outside supported suite')
        require(sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()) == algorithms[ALGORITHM]['sha256'],
                'installed verified materialization algorithm differs from pinned suite')
        return proof

    def _optional(self, path):
        try: return self.store.read(path)
        except FileNotFoundError:
            self.store.read_descriptor()
            return None

    def _targets(self, proof):
        pointer = proof.pointers[-1]
        raw = proof.reader.raw({'path': pointer['verified_draft_path'], 'hash': pointer['verified_draft_hash']})
        targets = {'spec.md': raw}
        if pointer['promotion_ordinal']:
            creation = proof.reader.json({'path': pointer['source_candidate_creation_event_path'],
                'hash': pointer['source_candidate_creation_event_hash']}, 'candidate_creation_event_v1')
            targets[f"rounds/round-{creation['round_number']}/draft_after.md"] = raw
        state_raw = self._optional(STATE_PATH)
        state = {} if state_raw is None else decode_json(state_raw)
        require(isinstance(state, dict), 'run state materialization requires a JSON object')
        if state.get(STATE_FIELD) != pointer:
            targets[STATE_PATH] = canonical_json_bytes({**state, STATE_FIELD: pointer})
        else:
            targets[STATE_PATH] = state_raw
        return targets

    def _pending(self, targets):
        return {path: data for path, data in targets.items() if self._optional(path) != data}

    def _view(self, proof, targets):
        pointer = proof.pointers[-1]
        kind = ('seed_materialization' if pointer['promotion_ordinal'] == 0 else 'post_commit_materialization') if targets else None
        return MaterializationView(deepcopy(pointer), tuple(targets), kind)

    def inspect(self):
        proof = self._proof(self.store.read)
        targets = self._targets(proof)
        pending = self._pending(targets)
        proof.guard(self.store.read)
        return self._view(proof, pending)

    def repair(self):
        captured = {}
        def validate(read): captured['proof'] = self._proof(read)
        with self.store.locked(validate) as token:
            proof = captured['proof']
            targets = self._targets(proof)
            pending = self._pending(targets)
            pointer = proof.pointers[-1]
            snapshot = _snapshot(pointer)
            self.store.synchronize_existing(token, snapshot['path'], expected=proof.head_raw)
            self.store.synchronize_existing(token, 'rounds/current_verified.json', expected=proof.head_raw)
            def target(read, path, raw):
                proof.guard(read)
                require(path in targets and raw == targets[path], 'materialization target differs from committed projection')
            for path, raw in targets.items():
                if path in pending:
                    self.store.materialize(token, path, raw, validate_target=target)
                else:
                    self.store.synchronize_existing(token, path, expected=raw)
            remaining = self._pending(self._targets(proof))
            proof.guard(self.store.read)
            require(not remaining, 'verified materialization did not produce its committed targets')
            return self._view(proof, remaining)
