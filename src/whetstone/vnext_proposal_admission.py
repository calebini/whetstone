"""Store-backed seed admission for the bounded proposal-only consumer.

No public capability is enabled here. A registered consuming suite and an
audited storage contract remain release gates. Promoted-base admission belongs
to the later promotion consumer and is deliberately not inferred from bytes.
"""
from copy import deepcopy
from pathlib import PurePosixPath

from whetstone.vnext_review_configuration import read as read_review_configuration
from whetstone.vnext_assembly import ASSEMBLER_VERSION, NORMALIZATION_VERSION
from whetstone.vnext_assertions import validate_assertion_program
from whetstone.hashing import normalize_draft
from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes, validate_contract_suite
from whetstone.vnext_inventory import INVENTORY_VERSION, seed_inventory
from whetstone.vocabulary import PROFILE_SETS, REVIEW_PROFILE_DEFINITIONS
from whetstone.vnext_local_storage import LocalAuthorityStore, initialize_storage
from whetstone.vnext_sections import seed_section_map
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_validation import ArtifactReader, _validate_bootstrap_in_fresh_suite, validate_seed_pointer


# Include schemas used indirectly by the request/handoff/registration consumer.
# Presence in the installed schema directory alone never grants admission.
PROPOSAL_SCHEMAS = frozenset('''job_descriptor_v2 authority_map_v1 protected_invariants_v1
protected_invariants_v2 review_configuration_v1 scope_contract reviewer_feedback
vnext_finding_advice_v1 section_identity_map_v1 section_identity_map_v2
current_verified_pointer_v1 mutation_plan_v1 mutation_plan_v2
vnext_mutation_decision_request_v1 vnext_mutation_decision_request_v2 operator_decision_response_v1
vnext_preservation_inventory_v2 patch_set_client_v2 patch_set_v2 patch_operation_v2
vnext_proposal_response_v2 vnext_proposal_response_v2.codex vnext_proposal_result_v1 vnext_proposal_round_input_v1
vnext_proposal_request_v1 vnext_proposal_request_transport_v1
vnext_proposal_request_invocation_v1 vnext_proposal_request_outcome_v1
vnext_proposal_handoff_v1 preservation_report_v2 candidate_registration_preparation_v1
candidate_creation_event_v1 candidate_disposition_event_v1 vnext_local_storage_binding_v1
candidate_verification_v1 candidate_verification_pointer_v1 terminal_report_v2
vnext_candidate_assembly_failure_v1 vnext_proposal_run_input_v1 vnext_proposal_status_v1
vnext_review_response_v1 vnext_review_response_v1.codex vnext_review_request_transport_v1
vnext_review_request_v1 vnext_review_invocation_v1 vnext_review_outcome_v1 vnext_review_result_v1
vnext_proposal_package_v1 vnext_mutation_constraints_v1
vnext_operator_options_v1 vnext_operator_response_input_v1 vnext_operator_selection_v1 vnext_operator_work_v1'''.split())


class ProposalAdmission:
    """Frozen artifact selectors; all authority is reread on every callback.

    Round selectors point to immutable closed records, not caller-supplied
    findings, grants, context, inventories or plans. Existing request headers
    then bind the complete reconstructed preflight across continuation.
    """
    def __init__(self, store, *, suite_path, descriptor_ref, review_ref, seed_map_ref, round_refs,launch_package_ref=None):
        self.store = store
        self.suite_path = suite_path
        self._refs = deepcopy(dict(descriptor=descriptor_ref, review=review_ref,
                                   seed_map=seed_map_ref, rounds=round_refs,launch_package=launch_package_ref))
        require(all(type(n) is int and n > 0 for n in round_refs), 'invalid admission round selector')

    def _base(self, read):
        reader, values = self._seed_inputs(read, expected_mode='proposal_only')
        require(read('rounds/current_verified.json') == reader.raw(values['base_pointer_ref']),
                'seed proposal admission requires the current committed seed pointer')
        return reader, values

    def _seed_inputs(self, read, *, expected_mode):
        """Read immutable bootstrap and seed evidence, not current authority.

        The proposal entry point separately requires the seed still current.
        A promotion consumer must qualify its complete historical-base replay
        before these seed inputs can participate in that consumer's admission.
        """
        require(expected_mode in {'proposal_only', 'verified_promotion'}, 'unsupported mutable admission mode')
        suite = validate_contract_suite(self.suite_path)
        require(suite.version != 'vnext-contracts-1', 'frozen suite has no proposal admission capability')
        pinned = {entry['path'] for entry in suite.manifest['schemas']}
        require({'schemas/'+name+'.schema.json' for name in PROPOSAL_SCHEMAS} <= pinned,
                'proposal consumer schema is outside supported suite')
        # Some existing pure helpers load installed schemas directly. A suite
        # relocated for inspection cannot mask drift in those consumed files.
        for entry in suite.manifest['schemas']:
            require(sha256_bytes(confined_file(CONTRACT_ROOT,entry['path']).read_bytes()) == entry['sha256'],
                    'installed consumer schema differs from the pinned suite', entry['path'])
        reader, job, authority, invariants = _validate_bootstrap_in_fresh_suite(
            ArtifactReader(None, suite, read=read), self._refs['descriptor'],
            review_configuration_ref=self._refs['review'])
        require(canonical_json_bytes(job) == self.store.read_descriptor(), 'admitted descriptor differs from storage binding')
        require(job['editing_mode'] == expected_mode, 'seed proposal consumer requires ' + expected_mode + ' mode')
        from whetstone.vnext_version_operations import ASSEMBLER, pins as version_pins
        assembler=ASSEMBLER_VERSION
        if job['assembler_version']==ASSEMBLER:
            version_pins(suite); assembler=ASSEMBLER
        for key, value in [('parser_contract_version','markdown-atx-v1'), ('assembler_version',assembler),
                           ('inventory_version',INVENTORY_VERSION), ('normalization_version',NORMALIZATION_VERSION)]:
            require(job[key] == value, 'unsupported proposal consumer algorithm', key)
        snapshot = 'rounds/verified_history/current-verified-0.json'
        pointer_raw = read(snapshot)
        pointer_ref = {'path':snapshot, 'hash':sha256_bytes(pointer_raw)}
        pointer = reader.json(pointer_ref, 'current_verified_pointer_v1')
        validate_seed_pointer(pointer, job, self._refs['seed_map'])
        seed = reader.raw(job['seed_draft'])
        require(normalize_draft(seed.decode('utf-8')).encode('utf-8') == seed,
                'seed must be normalized before its immutable descriptor is created')
        mapping = reader.json(self._refs['seed_map'], 'section_identity_map_v1')
        mutable = next(b for b in authority['bindings'] if b['role'] == 'mutable_target')
        require(mapping == seed_section_map(seed, job, mutable['binding_id']), 'admission seed map does not reproduce')
        scope = reader.json({'path':job['scope_contract_path'], 'hash':job['scope_contract_hash']},
                            'scope_contract') if job['scope_contract_hash'] else None
        review=read_review_configuration(reader, self._refs['review'])
        names=[p['name'] for p in review['profiles']]
        require(bool(names) and len(names)==len(set(names)) and all(p['budget']>0 for p in review['profiles']),
                'review profiles must be nonempty, unique, and have positive budgets')
        require(all(name in REVIEW_PROFILE_DEFINITIONS for name in names) and review['profile_set'] in PROFILE_SETS,
                'unsupported review profiles')
        require(review['workflow'] in {'standard','mvp','exploratory','governance','custom'}, 'unsupported workflow')
        require(review['workflow']!='mvp' or scope is not None, 'MVP requires an approved scope contract')
        if self._refs['launch_package'] is not None:
            from whetstone.vnext_proposal_package import validate_launch_package
            validate_launch_package(reader,self._refs['launch_package'],descriptor_ref=self._refs['descriptor'],
                                    review_ref=self._refs['review'],authority=authority)
        return reader, dict(job=job, authority=authority, invariants=invariants, seed=seed,
            seed_map=mapping, base=seed, base_map=mapping, scope=scope, suite=reader.suite,
            review=review, base_pointer_ref=pointer_ref)

    def validate_authority(self, read):
        self._base(read)

    def load_inputs(self, read, round_number):
        require(type(round_number) is int and round_number in self._refs['rounds'], 'unselected proposal round')
        reader, values = self._base(read)
        return self._round_inputs(reader, values, round_number)

    def _round_inputs(self, reader, values, round_number):
        """Reconstruct a round against the base its admission owner validated."""
        record = reader.json(self._refs['rounds'][round_number], 'vnext_proposal_round_input_v1')
        require(record['job_id'] == values['job']['job_id'] and record['round_number'] == round_number,
                'proposal round input identity differs')
        require(record['base_pointer'] == values['base_pointer_ref'], 'proposal round selected a different base pointer')
        feedback = reader.json(record['feedback'], 'reviewer_feedback')
        require(feedback['round_number'] == round_number, 'Reviewer evidence belongs to a different round')
        advice = reader.json(record['advice'], 'vnext_finding_advice_v1') if record['advice'] else None
        _, evidence = classify_feedback(feedback=feedback, feedback_ref=record['feedback'], advice=advice,
            job=values['job'], authority=values['authority'], invariants=values['invariants'],
            base=values['base'], section_map=values['base_map'], scope=values['scope'])
        decisions = []
        for refs in record['decision_refs']:
            key = refs['finding_id']
            require(key in evidence, 'decision references unknown Reviewer finding')
            decisions.append(dict(finding_id=key, feedback_refs=evidence[key]['feedback_refs'],
                request=reader.json(refs['request'], 'vnext_mutation_decision_request_v2'),
                response=reader.json(refs['response'], 'operator_decision_response_v1')))
        # Read every available authority/context binding by its admitted hash.
        # The prompt constructor selects only plan-required bindings from this.
        context = {b['binding_id']:reader.raw({'path':b['path'], 'hash':b['content_hash']})
                   for b in values['authority']['bindings'] if b['role'] not in {'mutable_target','excluded'}}
        values.update(feedback=feedback, feedback_ref=record['feedback'], advice=advice,
                      constraints=record['constraints'], decisions=decisions, context=context)
        if values['job']['editing_mode'] == 'verified_promotion' and feedback['profile'] == 'vertical':
            from whetstone.vnext_verified_vertical_phase1 import context
            values['vertical'] = context(reader, round_number, review=values['review'],
                job=values['job'], base_pointer=values['base_pointer_ref'])
        prepare_unit_preflight(**values)
        return values


def prepare_proposal_storage_inputs(*, artifacts, suite_path, descriptor_ref, review_ref, seed_map_ref, round_refs,
                                    launch_package_ref=None,input_paths=(), _admission_type=ProposalAdmission):
    """Validate and freeze complete initialization bytes without filesystem writes."""
    frozen = deepcopy(artifacts)
    allowed = {'job_descriptor.json', 'rounds/current_verified.json',
               'rounds/verified_history/current-verified-0.json'}
    require(descriptor_ref['path'] == 'job_descriptor.json', 'staged descriptor must use the canonical path')
    extra=set(input_paths)
    if extra:
        from whetstone.vnext_proposal_package import input_artifact_path
        for path in extra:input_artifact_path(path)
    for path, raw in frozen.items():
        require(isinstance(path,str) and path == PurePosixPath(path).as_posix()
                and not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts
                and '\\' not in path and '\x00' not in path
                and (path in allowed or path.startswith('inputs/') or path in extra),
                'staging may contain only local inputs and initial seed authority')
        require(isinstance(raw,bytes), 'staged artifacts require exact bytes')
    class StagedInputs:
        def read(self, path):
            try:return frozen[path]
            except KeyError as exc:raise FileNotFoundError(path) from exc
        def read_descriptor(self):return self.read('job_descriptor.json')
    staged = StagedInputs()
    selectors = deepcopy(dict(descriptor_ref=descriptor_ref, review_ref=review_ref,
                              seed_map_ref=seed_map_ref, round_refs=round_refs,launch_package_ref=launch_package_ref))
    admission = _admission_type(staged, suite_path=suite_path, **selectors)
    for number in sorted(round_refs):admission.load_inputs(staged.read, number)
    values = admission._base(staged.read)[1]
    job=values['job']
    # Seed-only initialization must qualify these programs before a Reviewer
    # invocation, even when no round feedback exists yet.
    validate_assertion_program(values['invariants'],values['seed'],values['seed_map'])
    from whetstone.vnext_discovery import discovery_rules
    seed_inventory(values['seed'],values['seed_map'],job,rules=discovery_rules(values['invariants']))
    from whetstone.vnext_proposal_run import RUN_INPUT_PATH, run_input_record
    record=run_input_record(job,selectors)
    raw=canonical_json_bytes(record)
    require(RUN_INPUT_PATH not in frozen or frozen[RUN_INPUT_PATH]==raw, 'staged run selectors conflict')
    frozen[RUN_INPUT_PATH]=raw
    return frozen,selectors,job


def initialize_proposal_storage(root, *, artifacts, suite_path, descriptor_ref, review_ref, seed_map_ref, round_refs,
                                launch_package_ref=None,input_paths=(), _admission_type=ProposalAdmission):
    """Validate an exact package, then create a genuinely fresh physical root.

    Existing roots are never upgraded. Failed initialization retains evidence.
    The caller owns and must close the returned store.
    """
    frozen,selectors,job=prepare_proposal_storage_inputs(artifacts=artifacts,suite_path=suite_path,
        descriptor_ref=descriptor_ref,review_ref=review_ref,seed_map_ref=seed_map_ref,round_refs=round_refs,
        launch_package_ref=launch_package_ref,input_paths=input_paths,_admission_type=_admission_type)
    initialize_storage(root, job_id=job['job_id'], descriptor_ref=selectors['descriptor_ref'], artifacts=frozen)
    store = LocalAuthorityStore(root, job_id=job['job_id'])
    try:
        from whetstone.vnext_proposal_run import RUN_INPUT_PATH
        require(store.read(RUN_INPUT_PATH)==frozen[RUN_INPUT_PATH], 'retained proposal run selectors failed readback')
        admitted = _admission_type(store, suite_path=suite_path, **selectors)
        for number in sorted(round_refs):admitted.load_inputs(store.read, number)
    except BaseException:
        store.close()
        raise
    return store, admitted
