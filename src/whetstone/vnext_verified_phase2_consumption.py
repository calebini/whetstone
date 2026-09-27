"""Fenced first-result accounting and conservative V finding projection."""
from copy import deepcopy

from whetstone.scheduler import PhaseScheduler, ProfileStep
from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_client import _Client, _Journal, JOURNAL_PATH
from whetstone.vnext_verified_work import VerifiedWork

ALGORITHM = 'algorithms/vnext_verified_phase2_consumption_v1.md'
SCHEMA = 'vnext_phase2_consumption_v1'
PATH = JOURNAL_PATH + '/consumption.json'


def _projection(bound, review, receipt, *, scheduler=None):
    """Rebuild once from the logical receipt, never increment persisted counters."""
    inputs = bound.inputs
    feedback = review['feedback']
    findings, evidence = classify_feedback(feedback=feedback, feedback_ref=receipt['feedback'],
        advice=None, job=inputs['job'], authority=inputs['authority'], invariants=inputs['invariants'],
        base=inputs['draft'].encode('utf-8'), section_map=inputs['base_map'], scope=inputs['scope'])
    gap_sources = {row['source_issue_id'] for row in review.get('rubric_findings',[]) if row['gap']['blocking_convergence']}
    for row in findings:
        if row['finding_id'] in gap_sources and row['classification']=='deferable':
            row['classification']='operator_decision_required'
    from whetstone.vnext_phase2_targets import defer_allowed
    defer_allowed(findings,feedback,inputs['configuration'],[row['canonical_section_id'] for row in inputs['base_map']['sections']])
    scheduler = deepcopy(scheduler) if scheduler is not None else PhaseScheduler(
        ProfileStep(row['name'], round_budget=row['budget'], repeat_if_blockers=True)
        for row in inputs['configuration']['profiles'])
    counts = {severity: sum(row['in_scope'] and row['normalized_severity'] == severity
                          for row in feedback['feedback']) for severity in ('blocker', 'major')}
    scheduler.record_result(bound.request['step']['profile'],
                            blocker_count=counts['blocker'], major_count=counts['major'])
    profiles = [dict(step_index=index, **row) for index, row in enumerate(scheduler.status()['profiles'], 1)]
    # Scheduler selection is descriptive only: this owner grants no next invocation.
    for row in profiles:
        del row['active']
    next_gate='finding_admission' if findings else 'subsequent_request_not_implemented'
    if bound.request['schema_version']=='vnext-phase2-review-request-v6':
        from whetstone.vnext_phase2_source_correction import source_findings
        if not source_findings(bound,review):next_gate='declaration_closeout_required'
    return dict(schema_version='vnext-phase2-consumption-v6' if bound.request['schema_version']=='vnext-phase2-review-request-v6' else 'vnext-phase2-consumption-v1', request=deepcopy(bound.request_ref),
        result=_ref(JOURNAL_PATH+'/result.json', receipt), base_pointer=deepcopy(bound.request['base_pointer']),
        accepted_passes=1, profiles=profiles, findings=findings, evidence=evidence,
        next_gate=next_gate,
        candidate_authorized=False, next_review_authorized=False, phase_complete=False)


class _Consumption(_Client):
    consumption_path = PATH
    consumption_schema = SCHEMA

    def _project(self, bound, review, receipt):
        return _projection(bound, review, receipt)

    def _proof(self, read):
        proof = super()._proof(read)
        pins = {row['path']: row for family in ('algorithms', 'schemas')
                for row in proof.reader.suite.manifest[family]}
        for path in (ALGORITHM, 'schemas/'+SCHEMA+'.schema.json'):
            require(path in pins, 'Phase 2 consumption contracts are outside supported suite')
            require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == pins[path]['sha256'],
                    'installed Phase 2 consumption contract differs from pinned suite', path)
        return proof

    def _consumption_view(self, proof):
        bound = self._committed_request(proof)
        journal = _Journal(self, proof, self.store, bound)
        outcomes, review, receipt = journal.inspect(bound.request)
        require(receipt is not None, 'Phase 2 consumption requires a committed result; recover its journal first')
        packet = self._project(bound, review, receipt)
        schema='vnext_phase2_consumption_v6' if bound.request['schema_version']=='vnext-phase2-review-request-v6' else self.consumption_schema
        journal.schemas.validate(packet, schema)
        existing = self._optional(self.consumption_path)
        if existing is not None:
            stored = proof.reader.json(dict(path=self.consumption_path, hash=sha256_bytes(existing)), schema)
            require(stored == packet, 'Phase 2 consumption differs from exact result replay')
        journal.recheck()
        return bound, journal, outcomes, packet, existing is not None

    def status(self):
        proof = self._proof(self.store.read)
        work = VerifiedWork._observe(self, proof)
        if work.outcome != 'work_available': return work
        _, _, _, packet, committed = self._consumption_view(proof)
        proof.guard(self.store.read)
        self.run._guard(self.store.read)
        return dict(committed=committed, consumption=deepcopy(packet))

    def consume(self):
        def perform(store, proof):
            bound, journal, outcomes, packet, _ = self._consumption_view(proof)
            self._synchronize_request(store, proof, bound)
            journal.synchronize(store._token, bound.request, outcomes)
            for ref in (packet['result'], journal.receipt(journal.inspect(bound.request)[1])['feedback']):
                raw = proof.reader.raw(ref)
                self.store.synchronize_existing(store._token, ref['path'], expected=raw)
            require(self._consumption_view(proof)[3] == packet, 'Phase 2 result changed during consumption barriers')
            self.store.publish(store._token, self.consumption_path, packet)
            require(self._consumption_view(proof)[3] == packet, 'Phase 2 consumption changed after publication')
            return deepcopy(packet)
        return self._execute(perform)


def consume_phase2_result(run):
    return _Consumption(run).consume()


def phase2_consumption_status(run):
    return _Consumption(run).status()
