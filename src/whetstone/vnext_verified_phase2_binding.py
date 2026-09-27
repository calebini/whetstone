"""Explicit immutable Phase 2 inputs and request publication; no phase transition."""
from copy import deepcopy
from dataclasses import dataclass

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_eligibility import _Eligibility


ALGORITHM = 'algorithms/vnext_verified_phase2_binding_v1.md'
CONFIG_SCHEMA = 'vnext_phase2_configuration_v1'
REQUEST_SCHEMA = 'vnext_phase2_entry_request_v1'
REQUEST_PATH = 'rounds/phase2/entry_request.json'
PROFILE_ORDER = ('convergence_strict_check', 'adversarial', 'convergence_strict_check')
RUBRIC_HASH = 'ddcdfed1b43763d4562febdf6e85fbc0178afb91a737662722ea565d039376fe'


def _ref(path, packet):
    return dict(path=path, hash=sha256_bytes(canonical_json_bytes(packet)))


@dataclass(frozen=True)
class Phase2EntryBinding:
    configuration: dict
    configuration_ref: dict
    request: dict
    request_ref: dict
    pending_paths: tuple
    materialized: bool
    phase2_blockers: tuple = ('phase2_entry_unimplemented', 'phase2_execution_unavailable')
    entry_permitted: bool = False
    resume_permitted: bool = False
    apply_back_permitted: bool = False


class _Binding(_Eligibility):
    def _proof(self, read):
        proof = super()._proof(read)
        entries = {row['path']: row for family in ('algorithms', 'schemas')
                   for row in proof.reader.suite.manifest[family]}
        paths = {ALGORITHM, 'schemas/' + CONFIG_SCHEMA + '.schema.json', 'schemas/' + REQUEST_SCHEMA + '.schema.json'}
        require(paths <= entries.keys(), 'verified Phase 2 binding contracts are outside supported suite')
        for path in paths:
            require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == entries[path]['sha256'],
                    'installed verified Phase 2 binding contract differs from pinned suite', path)
        return proof

    def _build(self, proof, configuration):
        eligible = self._evaluate_eligibility(proof)
        require(eligible.phase1_prerequisites_met, 'Phase 2 binding requires current complete Phase 1 prerequisites: '
                + ', '.join(eligible.phase1_blockers))
        config = deepcopy(configuration)
        from whetstone.vnext_phase2_targets import configuration_schema
        proof.reader.suite.registry.validate(config, configuration_schema(proof.reader.suite))
        review = proof.seed_values['review']
        require(config['job_id'] == proof.seed_values['job']['job_id']
                and config['review_configuration'] == self.run._record['review_configuration'],
                'Phase 2 configuration belongs to another job or review configuration')
        for key in ('workflow', 'review_mode', 'profile_set', 'reviewer', 'editor', 'verifier'):
            require(config[key] == review[key], 'Phase 2 configuration changes a descriptor-bound input', key)
        require(tuple(row['name'] for row in config['profiles']) == PROFILE_ORDER,
                'unsupported Phase 2 profile order; repeated steps must be retained')
        rubric = config['rubric']['artifact']
        require(rubric['path'].startswith('inputs/phase2/'), 'Phase 2 rubric must be an explicit staged input')
        raw = proof.reader.raw(rubric)
        require(sha256_bytes(raw) == RUBRIC_HASH, 'Phase 2 rubric differs from supported standard-v1 bytes')
        config_ref = _ref('rounds/phase2/configurations/config-' + sha256_bytes(canonical_json_bytes(config)) + '.json', config)
        request = dict(schema_version='vnext-phase2-entry-request-v1', job_id=config['job_id'],
            job_descriptor=deepcopy(self.run._record['descriptor']), review_configuration=deepcopy(eligible.review_configuration),
            current_verified_pointer=deepcopy(eligible.current_pointer), current_verified_draft=deepcopy(eligible.current_verified_draft),
            current_verified_map=deepcopy(eligible.current_verified_map), phase1_closeout=deepcopy(eligible.closeout_ref),
            phase1_terminal_report=deepcopy(eligible.terminal_report_ref), configuration=config_ref)
        proof.reader.suite.registry.validate(request, REQUEST_SCHEMA)
        config_raw, request_raw = self._optional(config_ref['path']), self._optional(REQUEST_PATH)
        require(config_raw is None or config_raw == canonical_json_bytes(config), 'Phase 2 configuration conflicts with replay')
        require(request_raw is None or request_raw == canonical_json_bytes(request),
                'Phase 2 entry request is stale, belongs to another job, or selects another configuration')
        require(request_raw is None or config_raw is not None, 'committed Phase 2 request is missing its configuration')
        pending = tuple(path for path, raw in ((config_ref['path'], config_raw), (REQUEST_PATH, request_raw)) if raw is None)
        proof.guard(self.store.read)
        self.run._guard(self.store.read)
        blockers = (('phase2_request_unpublished',) if pending else ()) + ('phase2_entry_unimplemented', 'phase2_execution_unavailable')
        return Phase2EntryBinding(config, config_ref, request, _ref(REQUEST_PATH, request), pending, not pending,
                                  phase2_blockers=blockers)

    def prepare(self, configuration):
        return self._build(self._proof(self.store.read), configuration)

    def inspect_binding(self):
        proof = self._proof(self.store.read)
        raw = self._optional(REQUEST_PATH)
        if raw is None:
            return self._evaluate_eligibility(proof)
        reference = dict(path=REQUEST_PATH, hash=sha256_bytes(raw))
        request = proof.reader.json(reference, REQUEST_SCHEMA)
        from whetstone.vnext_phase2_targets import read_configuration
        configuration = read_configuration(proof.reader,request['configuration'])
        return self._build(proof, configuration)

    def bind(self, configuration):
        config = deepcopy(configuration)
        def publish(store, proof):
            expected = self._build(proof, config)
            state_raw = self.store.read(STATE_PATH)
            closeout = self.evaluate(proof)
            checked = self._synchronize_sources(store, proof, closeout)
            require(checked.materialized, 'Phase 1 closeout disappeared before Phase 2 binding')
            for reference, value in ((checked.report_ref, checked.report), (checked.evidence_ref, checked.evidence)):
                self.store.synchronize_existing(store._token, reference['path'], expected=canonical_json_bytes(value))
            self.store.synchronize_existing(store._token, STATE_PATH, expected=state_raw)
            rubric = config['rubric']['artifact']
            self.store.synchronize_existing(store._token, rubric['path'], expected=proof.reader.raw(rubric))
            require(self._build(proof, config) == expected, 'Phase 2 binding changed during source synchronization')
            # Request publication is the binding commit, not a Phase 2 entry commit.
            store.publish(store._token, expected.configuration_ref['path'], expected.configuration)
            store.publish(store._token, REQUEST_PATH, expected.request)
            result = self._build(proof, config)
            require(result.materialized, 'Phase 2 binding publication incomplete')
            return result
        return self._execute(publish)


def prepare_phase2_entry(run, configuration):
    return _Binding(run).prepare(configuration)


def bind_phase2_entry(run, configuration):
    return _Binding(run).bind(configuration)


def inspect_phase2_entry(run):
    return _Binding(run).inspect_binding()
