"""Pinned final-review residual evidence; serious work stays explicitly blocked."""
from copy import deepcopy

from whetstone.declaration import DECLARATION_ARTIFACTS
from whetstone.oscillation import OscillationTracker
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_closeout import _Declaration, _bundle, _latest_issues, _policy_rows
from whetstone.vnext_verified_phase2_sequence import sequence

ALGORITHM='algorithms/vnext_verified_phase2_findings_v1.md'
SCHEMA='vnext_phase2_finding_reconciliation_v1'


def supported(proof):
    return any(r['path']==ALGORITHM for r in proof.reader.suite.manifest['algorithms'])


def _pins(proof):
    pins={r['path']:r['sha256'] for family in ('algorithms','schemas') for r in proof.reader.suite.manifest[family]}
    for path in (ALGORITHM,'schemas/'+SCHEMA+'.schema.json','schemas/vnext_phase2_closeout_v2.schema.json'):
        require(path in pins and pins[path]==sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'Phase 2 finding reconciliation is outside supported suite or changed',path)


def _route(state,rows):
    """Classify evidence without interpreting model prose as a repair certificate."""
    proof=getattr(state['frames'][-1]['owner'],'proof',None)
    if proof is not None:rows = _policy_rows(proof,rows)
    reasons=[]
    if any(r['authority_impact'] is not None or r['determinism_impact'] is not None
           or r['invariant_violated'] is not None for r in rows):
        reasons.append('authority_resolution_required')
    rubric_blocked = any(r['rubric_impact'] is not None or 'rubric_gaps.json' in r['affected_sections'] for r in rows)
    from whetstone.vnext_phase2_gap_acceptance import supported as acceptance_supported, blocks
    if proof is not None and acceptance_supported(proof.reader.suite):
        rubric_blocked = blocks(state['frames'],proof.latest,rows)
    if rubric_blocked:
        reasons.append('rubric_resolution_required')
    from whetstone.vnext_phase2_targets import supported as target_supported, serious as target_serious, required_profiles
    config=state['frames'][-1]['owner'].binding.configuration
    targets=proof is not None and target_supported(proof.reader.suite)
    serious=[r for r in rows if target_serious(r,config)] if targets else [r for r in rows if r['normalized_severity'] in {'major','blocker'}]
    if targets and config['target_phase']=='mid' and 'rubric_resolution_required' in reasons:
        reasons.remove('rubric_resolution_required')
    declaration_sections=DECLARATION_ARTIFACTS|{'target-matrix-precedence'}
    if any(not r['affected_sections'] or not set(r['affected_sections'])<=declaration_sections for r in serious):
        reasons.append('source_revision_required')
    elif serious:
        reasons.append('declaration_revision_required')
    if not state.get('signals_enabled'):
        tracker=OscillationTracker()
        for frame in state['frames']:
            if tracker.record_phase2_feedback(round_number=frame['bound'].request['round_number'],
                                             reviewer_feedback=frame['review']['feedback']) is not None:
                reasons.append('oscillation_resolution_required');break
    # The separately pinned signal owner evaluates current runtime conditions
    # after declaration preconditions. Historical diagnostics are not blockers.
    required={r['name'] for r in state['frames'][-1]['owner'].binding.configuration['profiles']}
    if targets:required=required_profiles(config)
    if not required<=set(state['clean']):reasons.append('profile_verification_required')
    return reasons


def assessment(owner,proof,state,package,rows):
    _pins(proof)
    require(state['gate']=='declaration_closeout_required','final finding reconciliation requires consumed declaration review')
    frame=state['frames'][-1];bound=frame['bound']
    from whetstone.vnext_phase2_targets import supported as target_supported
    require((target_supported(proof.reader.suite) or bound.request['schema_version'] in {'vnext-phase2-review-request-v3', 'vnext-phase2-review-request-v4', 'vnext-phase2-review-request-v5'})
            and bound.request['base_pointer']==proof.latest,'final finding review is not current')
    reasons=_route(state,rows)
    directory=frame['owner'].directory+'/execution/finding_reconciliation'
    unresolved=dict(round_number=bound.request['round_number'],draft_hash=package['packet']['final_draft_hash'],
        unresolved_issues=[dict(issue_id=r['issue_id'],issue_fingerprint=r['issue_fingerprint'],
            normalized_severity=r['normalized_severity'],affected_sections=deepcopy(r['affected_sections']),
            claim=r['claim'],in_scope=r['in_scope'],blocking_acceptance=r in _policy_rows(proof,rows) and r['normalized_severity'] in {'major','blocker'})
            for r in rows])
    proof.reader.suite.registry.validate(unresolved,'unresolved_issues')
    issues_ref=_ref(directory+'/unresolved_issues.json',unresolved)
    profile=frame['consumption']['profiles'][bound.request['step']['index']-1]
    packet=dict(schema_version='vnext-phase2-finding-reconciliation-v1',job_id=bound.request['job_id'],
        current_verified_pointer=deepcopy(proof.latest),configuration=deepcopy(bound.request['configuration']),
        declaration_binding=deepcopy(package['reference']),review_request=deepcopy(bound.request_ref),
        review_result=_ref(frame['owner'].directory+'/execution/result.json',frame['receipt']),
        review_consumption=_ref(frame['owner'].consumption_path,frame['consumption']),
        source_consumptions=[_ref(f['owner'].consumption_path,f['consumption']) for f in state['frames']],
        feedback=deepcopy(frame['receipt']['feedback']),unresolved_issues=issues_ref,
        route=reasons[0] if reasons else 'closeout_eligible',blocking_reasons=reasons,
        residual_issue_ids=[r['issue_id'] for r in rows],
        remaining_step_budget=profile['round_budget']-profile['rounds_used'],
        repaired_issue_ids=[],candidate_authorized=False,next_review_authorized=False,phase_complete=False)
    schema = SCHEMA
    from whetstone.vnext_phase2_gap_acceptance import supported as acceptance_supported, references
    if acceptance_supported(proof.reader.suite):
        packet.update(schema_version='vnext-phase2-finding-reconciliation-v2',gap_acceptances=references(state['frames'],proof.latest))
        schema = 'vnext_phase2_finding_reconciliation_v2'
    proof.reader.suite.registry.validate(packet,schema)
    ref=_ref(directory+'/commit.json',packet)
    assets=((issues_ref['path'],canonical_json_bytes(unresolved)),)
    pending=[]
    for path,raw in assets+((ref['path'],canonical_json_bytes(packet)),):
        existing=owner._optional(path)
        require(existing is None or existing==raw,'final finding reconciliation differs from exact replay',path)
        if existing is None:pending.append(path)
    committed=ref['path'] not in pending
    require(not committed or not pending,'committed final finding reconciliation lacks dependencies')
    proof.guard(owner.store.read);owner.run._guard(owner.store.read)
    return dict(packet=packet,reference=ref,assets=assets,pending_paths=tuple(pending),committed=committed,
                phase_complete=False)


class _Findings(_Declaration):
    def _proof(self,read):
        proof=super()._proof(read);_pins(proof);return proof

    def _finding_view(self,proof):
        state=sequence(proof)
        require(state['gate']=='declaration_closeout_required','final finding reconciliation requires consumed declaration review')
        frame=state['frames'][-1];owner=frame['owner']
        from whetstone.vnext_verified_phase2_review_only import package_for
        package=package_for(owner)
        return state,assessment(self,proof,state,package,_latest_issues(state['frames'],proof.latest))

    @staticmethod
    def _public_findings(view):
        return {k:deepcopy(v) for k,v in view.items() if k!='assets'}

    def inspect(self):
        proof=self._proof(self.store.read);work=self._observe(proof)
        if work.outcome!='work_available':return work
        _,view=self._finding_view(proof)
        return self._public_findings(view)

    def reconcile_findings(self):
        def publish(store,proof):
            state,view=self._finding_view(proof);frame=state['frames'][-1]
            frame['owner']._synchronize_request(store,frame['owner'].proof,frame['bound'])
            frame['journal'].synchronize(store._token,frame['bound'].request,frame['outcomes'])
            for ref in (view['packet']['review_result'],view['packet']['feedback'],*view['packet']['source_consumptions'],
                        *view['packet'].get('gap_acceptances',[])):
                self.store.synchronize_existing(store._token,ref['path'],expected=proof.reader.raw(ref))
            require(self._finding_view(proof)[1]==view,'final finding sources changed during barriers')
            for path,raw in view['assets']:store.publish(store._token,path,raw)
            store.publish(store._token,view['reference']['path'],view['packet'])
            result=self._finding_view(proof)[1]
            require(result['committed'],'final finding reconciliation publication incomplete')
            return self._public_findings(result)
        return self._execute(publish)
