"""First Phase 2 correction: acyclic historical provenance and round admission."""
from copy import copy, deepcopy
from types import SimpleNamespace

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_proposal_admission import ProposalAdmission
from whetstone.vnext_proposal_package import validate_launch_package
from whetstone.vnext_proposal_run import round_input_path
from whetstone.vnext_validation import ArtifactReader
from whetstone.vnext_verified_history import _ReplayAdmission, _snapshot, VerifiedHistoryView
from whetstone.vnext_verified_phase2_advice import _Advice, ADVICE_PATH, BINDING_PATH
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_client import JOURNAL_PATH
from whetstone.vnext_verified_phase2_entry import ENTRY_PATH, SCHEMA as ENTRY_SCHEMA, Phase2EntryState
from whetstone.vnext_verified_phase2_eligibility import Phase2Eligibility
from whetstone.vnext_verified_phase2_consumption import PATH as CONSUMPTION_PATH
from whetstone.vnext_verified_phase2_review import REQUEST_PATH
from whetstone.versioning import promote_spec_text_for_phase2

ALGORITHM = 'algorithms/vnext_verified_phase2_round_v1.md'
FEEDBACK_PATH = JOURNAL_PATH + '/reviewer_feedback.json'


def supported(proof):
    return any(row['path'] == ALGORITHM for row in proof.reader.suite.manifest['algorithms'])


def _pins(proof):
    pins = {row['path']: row for family in ('algorithms', 'schemas') for row in proof.reader.suite.manifest[family]}
    names = ('round', 'advice', 'consumption', 'client', 'review', 'entry', 'binding', 'eligibility')
    paths = [ALGORITHM] + ['algorithms/vnext_verified_phase2_'+name+'_v1.md' for name in names[:-1]]
    paths += ['algorithms/vnext_verified_phase2_eligibility_v1.md', 'algorithms/vnext_verified_phase1_closeout_v1.md',
              'algorithms/vnext_verified_phase1_operator_v1.md', 'algorithms/vnext_mutation_preparation_v1.md']
    paths += ['schemas/'+name+'.schema.json' for name in ('vnext_phase2_configuration_v1',
        'vnext_phase2_entry_request_v1', 'vnext_phase2_entry_v1', 'vnext_phase2_review_request_v1',
        'vnext_phase2_review_result_v1', 'vnext_phase2_consumption_v1', 'vnext_phase2_advice_binding_v1',
        'vnext_verified_phase1_closeout_v1', 'phase2_reviewer_feedback_input', 'phase2_reviewer_feedback')]
    for path in paths:
        require(path in pins and sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == pins[path]['sha256'],
                'Phase 2 round contract is absent or changed', path)


def _entry_prefix(proof):
    """Restrict proven ancestry, never replace or virtualize the actual head/read."""
    raw = proof.store.read(ENTRY_PATH)
    from whetstone.vnext_contracts import decode_json
    schema=ENTRY_SCHEMA
    if decode_json(raw).get('schema_version')=='vnext-phase2-entry-v2':
        from whetstone.vnext_version_entry import pins
        pins(proof.reader.suite);schema='vnext_phase2_entry_v2'
    entry = proof.reader.json(dict(path=ENTRY_PATH, hash=sha256_bytes(raw)), schema)
    reference = entry['current_verified_pointer']
    proof.values(reference)  # Must already be proven, even during ascending history replay.
    ordinal = next((i for i, pointer in enumerate(proof.pointers) if _snapshot(pointer) == reference), None)
    require(ordinal is not None, 'Phase 2 entry pointer is outside committed ancestry')
    prefix = copy(proof)
    prefix.pointers = proof.pointers[:ordinal+1]
    prefix.latest = deepcopy(reference)
    prefix.bases = {key:value for key,value in proof.bases.items()
                    if any(_snapshot(pointer) == value[0] for pointer in prefix.pointers)}
    prefix.admission = _ReplayAdmission(prefix)
    limit = prefix.pointers[-1]['source_candidate_creation_ordinal'] or 0
    if limit:
        prefix.router = prefix.transactions(limit)
        registered = prefix.router.registry().inspect()
        prefix.view = VerifiedHistoryView(tuple(prefix.pointers), tuple(registered.events), ())
    else:
        prefix.router = SimpleNamespace(registry=lambda: SimpleNamespace(schemas=proof.reader.suite.registry))
        prefix.view = VerifiedHistoryView(tuple(prefix.pointers), (), ())
    return prefix


class _HistoricalAdvice(_Advice):
    """Replay immutable original prerequisites; mutable mirrors grant no history."""
    def _evaluate_eligibility(self, proof):
        closeout = self.evaluate(proof)
        require(closeout.materialized and closeout.accepted and not closeout.unclean_profiles
                and closeout.review_gate == 'review_complete', 'Phase 2 original Phase 1 closeout is not stable')
        pointer = proof.pointers[-1]
        return Phase2Eligibility(deepcopy(proof.latest),
            dict(path=pointer['verified_draft_path'], hash=pointer['verified_draft_hash']),
            dict(path=pointer['verified_section_identity_map_path'], hash=pointer['verified_section_identity_map_hash']),
            deepcopy(self.run._record['review_configuration']), None, (), closeout.review_gate, True,
            closeout.evidence_ref, closeout.report_ref, True, True, ())

    def _entry_view(self, proof, binding):
        if proof.seed_values['job']['assembler_version']=='patch-assembler-v3':
            from whetstone.vnext_version_entry import entry_view
            result=entry_view(self,proof,binding)
            require(result.committed,'historical version entry is not committed')
            return result
        raw = proof.reader.raw(binding.request['current_verified_draft'])
        text, before, after, changed = promote_spec_text_for_phase2(raw.decode('utf-8'))
        require(not changed and text.encode('utf-8') == raw and before == after,
                'Phase 2 version maintenance requires a V candidate')
        entry = dict(schema_version='vnext-phase2-entry-v1', phase='phase_2', job_id=binding.request['job_id'],
            entry_request=deepcopy(binding.request_ref), configuration=deepcopy(binding.configuration_ref),
            current_verified_pointer=deepcopy(proof.latest), current_verified_draft=deepcopy(binding.request['current_verified_draft']),
            current_verified_map=deepcopy(binding.request['current_verified_map']), phase1_closeout=deepcopy(binding.request['phase1_closeout']),
            version=dict(before=before, after=after, changed=False))
        require(self.store.read(ENTRY_PATH) == canonical_json_bytes(entry), 'historical Phase 2 entry differs')
        return Phase2EntryState('historical_entry', entry, _ref(ENTRY_PATH, entry), True, True, ())


def replay(proof):
    _pins(proof)
    prefix = _entry_prefix(proof)
    owner = _HistoricalAdvice(proof.owner.run)
    result = owner._advice_view(prefix, None)
    require(result[-1]['status'] == 'bound', 'Phase 2 round requires committed advice binding')
    return prefix, owner, result


def _constraints(proof):
    run = proof.owner.run
    reference = run._record.get('launch_package')
    require(reference is not None, 'Phase 2 round requires packaged mutation constraints')
    return validate_launch_package(proof.reader, reference, descriptor_ref=run._record['descriptor'],
        review_ref=run._record['review_configuration'], authority=proof.seed_values['authority'])


def validate_round(proof, number, record):
    prefix, owner, data = replay(proof)
    bound, _, _, _, _, view = data
    binding = view['binding']
    if bound.request['schema_version']=='vnext-phase2-review-request-v6':
        from whetstone.vnext_phase2_source_correction import source_findings
        _,review,_=data[1].inspect(bound.request)
        require(source_findings(bound,review),'declaration review has no wholly source correction')
    require(number == bound.request['round_number'] and record['round_number'] == number
            and record['base_pointer'] == prefix.latest and record['feedback'] == binding['feedback']
            and record['advice'] == binding['advice'] and record['constraints'] == _constraints(proof)
            and record['job_id'] == proof.seed_values['job']['job_id'], 'Phase 2 round differs from bound original evidence')
    if record['decision_refs']:
        from whetstone.vnext_verified_phase2_operator import admission_preflight
        admission_preflight(proof, bound, binding, record['decision_refs'])
    else:
        require(binding['findings'] and any(row['classification'] == 'editor_fixable' for row in binding['findings'])
                and all(row['classification'] in {'editor_fixable', 'deferable'} for row in binding['findings']),
                'Phase 2 round requires admitted advice without unresolved choices')
    from whetstone.vnext_phase2_rubric import proposal_context
    _, review, _ = data[1].inspect(bound.request)
    return proposal_context(bound, review)


def current_sequence(proof):
    """Allow only the first correction; entry, not a clean Phase 1 tail, anchors it."""
    prefix, _, data = replay(proof)
    number = data[0].request['round_number']
    tail = proof.pointers[len(prefix.pointers):]
    require(len(tail) <= 1, 'later Phase 2 correction journeys are not implemented')
    for pointer in tail:
        creation = proof.reader.json(dict(path=pointer['source_candidate_creation_event_path'],
            hash=pointer['source_candidate_creation_event_hash']), 'candidate_creation_event_v1')
        require(creation['round_number'] == number
                and pointer['previous_verified_pointer_hash'] == prefix.latest['hash'],
                'Phase 2 promotion belongs to another round or entry base')
    proof.guard(proof.store.read)
    return number


class _Round(_Advice):
    def _proof(self, read):
        proof = super()._proof(read)
        _pins(proof)
        return proof

    def _validate_round(self, proof, number, packet):
        return validate_round(proof, number, packet)

    def admit(self, *, decision_refs=()):
        decisions = deepcopy(list(decision_refs))
        def perform(store, proof):
            # Live publication requires the actual current entry prerequisites.
            bound, journal, outcomes, consumption, advice, view = self._advice_view(proof, None)
            require(view['status'] == 'bound', 'Phase 2 round requires committed advice binding')
            number = bound.request['round_number']
            packet = dict(schema_version='vnext-proposal-round-input-v1', job_id=bound.request['job_id'],
                round_number=number, base_pointer=deepcopy(proof.latest), feedback=view['binding']['feedback'],
                advice=view['binding']['advice'], decision_refs=decisions, constraints=_constraints(proof))
            path = round_input_path(number)
            raw = canonical_json_bytes(packet)
            reference = _ref(path, packet)
            def preflight():
                context = self._validate_round(proof, number, packet)
                reader = ArtifactReader(None, proof.reader.suite, read=lambda name: raw if name == path else store.read(name))
                admission = ProposalAdmission(store, suite_path=self.run.suite_path,
                    descriptor_ref=self.run._record['descriptor'], review_ref=self.run._record['review_configuration'],
                    seed_map_ref=self.run._record['seed_section_map'], round_refs={number:reference})
                values = proof.values(proof.latest)
                values['phase2'] = context
                admission._round_inputs(reader, values, number)
            preflight()
            self._synchronize_request(store, proof, bound)
            journal.synchronize(store._token, bound.request, outcomes)
            for ref in (view['binding']['feedback'], consumption['result'], view['binding']['consumption'],
                        view['binding']['advice'], _ref(self.binding_path, view['binding'])):
                self.store.synchronize_existing(store._token, ref['path'], expected=proof.reader.raw(ref))
            for decision in decisions:
                for key in ('request', 'response'):
                    ref = decision[key]
                    self.store.synchronize_existing(store._token, ref['path'], expected=proof.reader.raw(ref))
            preflight()
            store.publish(store._token, path, raw)
            proof.admission.load_inputs(store.read, number)
            return reference
        return self._execute(perform)


def admit_phase2_round(run):
    return _Round(run).admit()
