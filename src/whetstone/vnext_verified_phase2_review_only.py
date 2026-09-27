"""Finite, evidence-derived Reviewer-only verification after the ordinary sweep."""
from copy import deepcopy

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_closeout import _DeclarationPass, _bundle, _latest_issues
from whetstone.vnext_verified_phase2_sequence import _Pass

ALGORITHM = 'algorithms/vnext_verified_phase2_review_only_v1.md'


def supported(suite):
    return any(row['path'] == ALGORITHM for row in suite.manifest['algorithms'])


def pins(suite):
    from whetstone.vnext_phase2_source_correction import pins as source_pins
    source_pins(suite)
    entries = {row['path']: row['sha256'] for family in ('algorithms', 'schemas')
               for row in suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/vnext_phase2_review_request_v5.schema.json',
                 'schemas/vnext_phase2_consumption_v5.schema.json'):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'Phase 2 review-only contract is absent or changed', path)


def plan(frames, reference, scheduler):
    """A single bounded plan; later closeout results cannot expand its population."""
    anchors = [frame for frame in frames if frame.get('consumed')
               and frame['bound'].request['schema_version'] in {'vnext-phase2-review-request-v4','vnext-phase2-review-request-v6'}]
    if not anchors or scheduler.index < len(scheduler.steps): return None
    anchor = anchors[-1]
    signal = anchor.get('signals')
    if signal and (signal['terminal_state'] or 'freeze_prior_decision' in signal['recommendations']): return None
    if anchor['bound'].request['base_pointer'] != reference: return None
    if any(row['in_scope'] and row['normalized_severity'] in {'major', 'blocker'}
           for row in anchor['review']['feedback']['feedback']): return None
    if any(state.residual_status is not None for state in scheduler.states): return None
    if any(frame['review'].get('rubric_findings') for frame in frames if frame.get('consumed')):
        from whetstone.vnext_phase2_rubric import retained
        if any(row['blocking_convergence'] for row in retained(frames, reference)): return None
    rows = _latest_issues(frames, reference)
    from whetstone.vnext_phase2_gap_acceptance import supported as acceptance_supported, blocks
    accepts = acceptance_supported(anchor['owner'].proof.reader.suite)
    if any(row['in_scope'] and (row['normalized_severity'] in {'major', 'blocker'}
            or (not accepts and row['rubric_impact'] is not None) or 'rubric_gaps.json' in row['affected_sections']) for row in rows): return None
    if accepts and blocks(frames,reference,rows):return None
    names = list(dict.fromkeys(row['name'] for row in anchor['owner'].binding.configuration['profiles']))
    missing = [name for name in names if name not in anchor['clean_after']]
    if not missing: return None
    completed = [frame for frame in frames if frame['bound'].request['schema_version'] == 'vnext-phase2-review-request-v5']
    require(all(frame['bound'].request['base_pointer'] == reference for frame in completed),
            'review-only closeout changed verified lineage')
    if len(completed) >= len(missing): return None
    return anchor, dict(index=len(completed)+1, profiles=missing, source_review=deepcopy(anchor['bound'].request_ref))


def package_for(owner):
    anchor = getattr(owner, 'declaration_source', owner)
    return _bundle(anchor, anchor.source_frames, anchor.source_clean)


class ReviewOnlyPass(_DeclarationPass):
    request_schema = 'vnext_phase2_review_request_v5'

    def _build_review(self, proof, transport):
        pins(proof.reader.suite)
        self.store.check(self.snapshot)
        package = package_for(self)
        require(package['committed'] and package['packet']['current_verified_pointer'] == proof.latest,
                'review-only closeout lacks current verified declaration')
        context = dict(binding=package['reference'], packet=package['packet'], target_matrix=dict(
            target_phase='final', target_mode='strict', blockers_allowed=False, major_issues_allowed=False,
            unresolved_rubric_gaps_allowed=False, declaration_required=True),
            artifacts={key: dict(reference=package['packet'][key], content=value.decode())
                       for key, (_, value) in package['assets'].items()})
        return self._render_review(proof, transport, self.binding, self.entry, self.number, self.step,
            directory=self.directory, previous_consumption=self.previous, declaration=context,
            review_only=self.closeout_plan)

    def _project(self, bound, review, receipt):
        profiles = [dict(step_index=i, **row) for i, row in enumerate(self.scheduler.status()['profiles'], 1)]
        for row in profiles: del row['active']
        return dict(schema_version='vnext-phase2-consumption-v5', request=deepcopy(bound.request_ref),
            result=_ref(self.directory+'/execution/result.json', receipt), base_pointer=deepcopy(bound.request['base_pointer']),
            accepted_passes=self.ordinal, profiles=profiles, findings=[],
            evidence=dict(review_only=deepcopy(self.closeout_plan)), next_gate='declaration_closeout_required',
            candidate_authorized=False, next_review_authorized=False, phase_complete=False,
            previous_consumption=deepcopy(self.previous))

    def _synchronize_declaration(self, store):
        package = package_for(self)
        self.store.synchronize(store._token, self.snapshot, self.run._record['descriptor']['path'])
        for path, raw in list(package['assets'].values())+[(package['reference']['path'], canonical_json_bytes(package['packet']))]:
            self.store.synchronize_existing(store._token, path, expected=raw)

    def _round_assets(self, bound, review):
        directory = f'rounds/round-{self.number}'
        raw = bound.inputs['draft'].encode()
        return {directory+'/draft_before.md': raw, directory+'/draft_after.md': raw,
            directory+'/profile_used.yaml': canonical_json_bytes(dict(profile=self.step['profile'], round_kind='review_only')),
            directory+'/prompt_snapshot.json': canonical_json_bytes(dict(request=bound.request_ref, inputs=bound.request['inputs'],
                prompt=bound.request['prompt'], declaration=bound.request['declaration'], review_only=self.closeout_plan)),
            directory+'/reviewer_feedback.json': canonical_json_bytes(review['feedback'])}

    def _consumption_view(self, proof):
        result = super()._consumption_view(proof)
        bound, journal, _, _, committed = result
        _, review, _ = journal.inspect(bound.request)
        for path, raw in self._round_assets(bound, review).items():
            existing = self._optional(path)
            require(existing is None and not committed or existing == raw,
                    'review-only round evidence conflicts or is missing', path)
        return result

    def consume(self):
        def publish(store, proof):
            bound, journal, outcomes, packet, _ = self._consumption_view(proof)
            self._synchronize_request(store, proof, bound)
            journal.synchronize(store._token, bound.request, outcomes)
            _, review, receipt = journal.inspect(bound.request)
            for ref in (packet['result'], receipt['feedback']):
                self.store.synchronize_existing(store._token, ref['path'], expected=proof.reader.raw(ref))
            for path, raw in self._round_assets(bound, review).items(): store.publish(store._token, path, raw)
            require(self._consumption_view(proof)[3] == packet, 'review-only consumption sources changed')
            store.publish(store._token, self.consumption_path, packet)
            require(self._consumption_view(proof)[4], 'review-only consumption publication incomplete')
            self.run._guard(self.store.read)
            store.read_descriptor()
            return deepcopy(packet)
        return self._execute(publish)


def owner(base_owner, frames, scheduler):
    selection = plan(frames, base_owner.proof.latest, scheduler)
    if selection is None: return None
    anchor, packet = selection
    name = packet['profiles'][packet['index']-1]
    index = next(i for i, row in enumerate(base_owner.binding.configuration['profiles']) if row['name'] == name)
    state = scheduler.states[index];step = scheduler.steps[index]
    result = ReviewOnlyPass(base_owner.run, base_owner.store, base_owner.proof, base_owner.binding, base_owner.entry,
        ordinal=base_owner.ordinal, number=base_owner.number,
        step=dict(index=index+1, profile=name, round_budget=step.effective_round_budget,
                  rounds_used=state.rounds_used, pass_number=state.rounds_used+1), previous=base_owner.previous,
        scheduler=scheduler, snapshot=base_owner.snapshot)
    result.consumption_schema = 'vnext_phase2_consumption_v5'
    result.closeout_plan = packet
    result.declaration_source = anchor['owner']
    return result
