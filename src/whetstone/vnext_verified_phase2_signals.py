"""Explicit Phase 2 signal reports and recovery; no resolution or client work."""
from copy import deepcopy
from datetime import datetime, timezone

from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import canonical_json_bytes, decode_json, require, sha256_bytes
from whetstone.vnext_phase2_signals import SCHEMA, pins, supported
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_closeout import _latest_issues
from whetstone.vnext_verified_phase2_correction_failure import _CorrectionFailure
from whetstone.vnext_verified_phase2_sequence import sequence
from whetstone.vnext_verified_materialization import STATE_PATH

ROOT = 'rounds/phase2/signals'
STATE_FIELD = 'vnext_phase2_signals'
MIRRORS = dict(oscillation='rounds/oscillation_report.json', conflict='rounds/conflict_report.json',
               conflict_state='rounds/conflict_state.json', failure='rounds/convergence_failure_report.json')


class _Signals(_CorrectionFailure):
    def _proof(self, read):
        proof = super()._proof(read)
        pins(proof)
        return proof

    def _sources(self):
        return {p: r for p, r in super()._sources().items()
                if not p.startswith(ROOT+'/') and p not in MIRRORS.values()}

    def _record_signal(self, proof, frames, index, stage, cause, reference, stamp, *, terminal_state=None):
        frame = frames[index]; owner = frame['owner']; bound = frame['bound']
        directory = ROOT+f'/pass-{owner.ordinal}/{stage}'
        existing = self._optional(directory+'/evidence.json')
        commit = self._optional(directory+'/commit.json')
        if existing is not None:
            value = decode_json(existing)
            stamp = value['generated_at']
        if stamp is None:
            require(commit is None, 'committed signal report lacks evidence')
            return dict(pending=True, committed=False, reference=None, order=(owner.ordinal, 5, 0), stage=stage)
        pointer = next(p for p in proof.pointers if _ref(
            'rounds/verified_history/current-verified-'+str(p['promotion_ordinal'])+'.json', p) == reference)
        raw = proof.reader.raw(dict(path=pointer['verified_draft_path'], hash=pointer['verified_draft_hash']))
        evidence = dict(generated_at=stamp, cause=deepcopy(cause))
        assets = {directory+'/evidence.json': canonical_json_bytes(evidence)}
        refs = {k: None for k in ('oscillation', 'conflict', 'conflict_state', 'failure', 'terminal', 'rubric_manifest')}
        config = owner.binding.configuration
        def asset(key, value, schema):
            proof.reader.suite.registry.validate(value, schema)
            path = directory+'/'+key+'.json'
            assets[path] = canonical_json_bytes(value); refs[key] = _ref(path, value)
        if stage != 'terminal':
            detections = cause['detections']
            # Retain every detection in immutable evidence; root compatibility
            # report carries the strongest recommendation for this event.
            rank = {'stop_iteration': 0, 'escalate_conflict': 1, 'freeze_prior_decision': 2, 'continue_once': 3}
            if detections:
                detection = min(detections, key=lambda d: rank[d['recommendation']])
                asset('oscillation', dict(terminal_state=None, generated_at=stamp, round_number=owner.number,
                    draft_hash=draft_hash(raw.decode()), detected=True, type=detection['oscillation_type'],
                    **{k:deepcopy(detection[k]) for k in ('affected_sections','suspected_feedback_ids',
                        'oscillation_fingerprints','oscillation_opposition_keys','recommendation')}), 'oscillation_report')
            if cause.get('conflicts'):
                asset('conflict', dict(terminal_state=None, generated_at=stamp, round_number=owner.number,
                    draft_hash=draft_hash(raw.decode()), conflicts=cause['conflicts'],
                    exit_reason=cause.get('escalation_reason') or 'Phase 2 feedback escalated for manual review',
                    recommendation='manual_review_required'), 'conflict_report')
            if 'conflict_state' in cause:
                asset('conflict_state', dict(cause['conflict_state'], generated_at=stamp), 'conflict_state')
        else:
            require(reference == proof.latest, 'historical signal terminal cannot become current')
            prior = frames[:index+1]
            # A cycle may be observed immediately after promotion. The new
            # pointer has no review yet; promotion does not resolve its findings.
            rows = _latest_issues(prior, bound.request['base_pointer'])
            from whetstone.vnext_phase2_rubric import report_gaps
            gaps = report_gaps(proof,prior,bound.request['base_pointer'])
            manifest = dict(schema_version='vnext-bound-rubric-v1', configuration=owner.binding.configuration_ref,
                workflow=config['workflow'], rubric_profile=config['rubric']['profile'], rubric_source=config['rubric']['source'],
                rubric_label=None, rubric_path=config['rubric']['artifact']['path'], rubric_content_hash=config['rubric']['artifact']['hash'],
                target_phase=config['target_phase'], target_mode=config['target_mode'])
            from whetstone.vnext_phase2_gap_acceptance import bind_manifest
            bind_manifest(manifest,proof,prior,bound.request['base_pointer'])
            path = directory+'/rubric_manifest.json'; assets[path] = canonical_json_bytes(manifest); refs['rubric_manifest'] = _ref(path,manifest)
            profile_status = deepcopy(frame['signal_profiles'])
            latest = {f['bound'].request['step']['profile']: f for f in prior
                      if f.get('consumed') and f['bound'].request['base_pointer'] == reference}
            profile_status['unverified_profiles'] = sorted({r['name'] for r in config['profiles']} - {
                name for name,f in latest.items() if not any(r['in_scope'] and r['normalized_severity'] in {'major','blocker'}
                    for r in f['review']['feedback']['feedback'])})
            serious = [r for r in frame['review']['feedback']['feedback'] if r['in_scope'] and r['normalized_severity'] in {'major','blocker'}]
            declaration = bound.inputs.get('declaration')
            def issues(severity):
                return [{k:deepcopy(r[k]) for k in ('issue_id','issue_fingerprint','normalized_severity','affected_sections','claim')}
                        for r in rows if r['normalized_severity'] == severity]
            reason = 'vnext_phase2_conflict' if terminal_state == 'HALTED_CONFLICT' else 'vnext_phase2_oscillation'
            failure = dict(terminal_state=terminal_state, generated_at=stamp, round_number=owner.number,
                draft_hash=draft_hash(raw.decode()), final_draft_path=pointer['verified_draft_path'],
                final_declaration_path=declaration['packet']['declaration']['path'] if declaration else None,
                target_phase=config['target_phase'],target_mode=config['target_mode'],workflow=config['workflow'],
                rubric_profile=config['rubric']['profile'],rubric_source=config['rubric']['source'],rubric_label=None,
                rubric_manifest_path=refs['rubric_manifest']['path'], unresolved_blockers=issues('blocker'),
                unresolved_major_issues=issues('major'), unresolved_rubric_gaps=gaps,
                reviewer_final_status='rejected' if declaration else 'not_run',
                last_accepted_draft_hash=draft_hash(proof.reader.raw(owner.entry.entry['current_verified_draft']).decode()),
                last_draft_hash=draft_hash(raw.decode()),exit_reason=reason,recommendation='manual_review_required',
                profile_status=profile_status,last_reviewer_findings=dict(round_number=owner.number,profile=bound.request['step']['profile'],
                    blocker_count=sum(r['normalized_severity']=='blocker' for r in serious),
                    major_count=sum(r['normalized_severity']=='major' for r in serious),feedback_ids=[r['feedback_id'] for r in serious]))
            asset('failure',failure,'convergence_failure_report')
            asset('terminal', self._report(proof,terminal=terminal_state,reason=reason), 'terminal_report_v2')
            signal=frame['signals']
            if signal['detections']:
                rank={'stop_iteration':0,'escalate_conflict':1,'freeze_prior_decision':2,'continue_once':3}
                detection=min(signal['detections'],key=lambda d:rank[d['recommendation']])
                asset('oscillation',dict(terminal_state=terminal_state,generated_at=stamp,round_number=owner.number,
                    draft_hash=draft_hash(raw.decode()),detected=True,type=detection['oscillation_type'],
                    **{k:deepcopy(detection[k]) for k in ('affected_sections','suspected_feedback_ids',
                        'oscillation_fingerprints','oscillation_opposition_keys','recommendation')}),'oscillation_report')
            if signal['conflicts']:
                asset('conflict',dict(terminal_state=terminal_state,generated_at=stamp,round_number=owner.number,
                    draft_hash=draft_hash(raw.decode()),conflicts=signal['conflicts'],
                    exit_reason=signal['escalation_reason'] or 'Phase 2 feedback escalated for manual review',
                    recommendation='manual_review_required'),'conflict_report')
        packet = dict(schema_version='vnext-phase2-signals-v1', stage=stage, round_number=owner.number,
            current_verified_pointer=deepcopy(reference),configuration=owner.binding.configuration_ref,entry=bound.request['entry'],
            review_request=bound.request_ref,source_consumptions=[_ref(f['owner'].consumption_path,f['consumption']) for f in frames[:index+1]],
            evidence=_ref(directory+'/evidence.json',evidence),terminal_state=terminal_state,**refs)
        proof.reader.suite.registry.validate(packet,SCHEMA)
        ref = _ref(directory+'/commit.json',packet); pending=False
        for path,value in [*assets.items(),(ref['path'],canonical_json_bytes(packet))]:
            observed=self._optional(path)
            require(observed is None or observed==value,'signal report differs from exact evidence replay',path)
            pending=pending or observed is None
        require(commit is None or not pending,'committed signal report lacks dependencies')
        return dict(packet=packet,assets=assets,reference=ref,pending=pending,committed=commit is not None,
                    order=(owner.ordinal,5,{'feedback':0,'draft':1,'terminal':2}[stage]),stage=stage)

    def _view_signals(self, proof, stamp=None):
        state=sequence(proof); records=[]; expected=set(); active=None; blocked=[]
        for index,frame in enumerate(state['frames']):
            if not frame.get('consumed'):continue
            signal=frame['signals'];owner=frame['owner']
            def add(stage,cause,reference,terminal_state=None):
                expected.add(f'pass-{owner.ordinal}/{stage}')
                record=self._record_signal(proof,state['frames'],index,stage,cause,reference,stamp,terminal_state=terminal_state)
                records.append(record);return record
            if signal['feedback_detections'] or signal['conflict_state']['conflicts']:
                cause={k:deepcopy(signal[k]) for k in ('conflicts','conflict_state','escalation_reason')}
                cause['detections']=signal['feedback_detections']
                add('feedback',cause,frame['bound'].request['base_pointer'])
            if signal['draft_detection']:
                add('draft',dict(detections=[signal['draft_detection']]),frame['signal_reference'])
            if index == len(state['frames'])-1:
                chosen=signal['terminal_state']
                if state['gate']=='declaration_closeout_required':
                    closeout=self._closeout(proof)
                    if closeout.get('packet',{}).get('terminal_state')=='CONVERGED':chosen=None
                    elif closeout.get('gate')=='signal_preconditions_required':
                        blocked=closeout['signal_preconditions'];chosen=None
                if chosen:
                    rows=[r for f in state['frames'] if f.get('consumed') for r in f['review']['feedback']['feedback']]
                    from whetstone.vnext_phase2_rubric import supported as rubric_supported
                    if not rubric_supported(proof.reader.suite) and any(r['rubric_impact'] is not None or 'rubric_gaps.json' in r['affected_sections'] for r in rows):
                        blocked.append('rubric_resolution_required');chosen=None
                if chosen:
                    cause=dict(conditions=signal['conditions'],recommendations=signal['recommendations'],
                               ordinary_gate=frame.get('ordinary_gate',state['gate']))
                    active=add('terminal',cause,frame['signal_reference'],chosen)
        try:claims=self.store.list_directory(ROOT)
        except FileNotFoundError:claims=()
        for name,kind in claims:
            if name.startswith('.vnext-tmp-'):continue
            require(kind=='directory' and any(e.startswith(name+'/') for e in expected),'unknown signal report pass')
            for leaf,leaf_kind in self.store.list_directory(ROOT+'/'+name):
                if leaf.startswith('.vnext-tmp-'):continue
                require(leaf_kind=='directory' and name+'/'+leaf in expected,'unknown signal report claim')
        return dict(state=state,records=records,active=active,blocked=blocked)

    def _projection(self, view):
        return dict(active=view['active']['reference'] if view['active'] and view['active']['committed'] else None,
                    history=[r['reference'] for r in view['records'] if r['committed']])

    def _public_signals(self, proof, view):
        from whetstone.vnext_phase2_report_projection import projections
        plan=projections(self,proof,signals=view)
        projection=self._projection(view);state=decode_json(self.store.read(STATE_PATH))
        last=view['state']['frames'][-1] if view['state']['frames'] else {}
        active=view['active']
        return dict(gate=view['state']['gate'],blocked=view['blocked'],
            terminal_state=active['packet']['terminal_state'] if active and 'packet' in active else
                last.get('signals',{}).get('terminal_state') if active else None,
            recommendations=last.get('signals',{}).get('recommendations',[]),
            active=projection['active'],history=projection['history'],committed=bool(active and active['committed']),
            publication_required=any(r['pending'] for r in view['records']),
            state_current=state.get(STATE_FIELD)==projection if view['records'] else STATE_FIELD not in state,
            mirrors_current=all(self._optional(path)==target['raw'] for path,target in plan.items()),
            resume_permitted=False,phase_complete=False)

    def status(self):
        proof=self._proof(self.store.read);work=self._observe(proof)
        if work.outcome!='work_available':return work
        view=self._view_signals(proof);result=self._public_signals(proof,view)
        self.store.check(self._sources());return result

    def publish(self):
        def perform(store,proof):
            stamp=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
            view=self._view_signals(proof,stamp);snapshot=self._sources()
            self._barrier(store._token,snapshot)
            for r in view['records']:
                for path,raw in r['assets'].items():store.publish(store._token,path,raw)
                for path,raw in r['assets'].items():self.store.synchronize_existing(store._token,path,expected=raw)
                self.store.check(snapshot)
                store.publish(store._token,r['reference']['path'],r['packet'])
            self.store.check(snapshot)
            return self._public_signals(proof,self._view_signals(proof))
        return self._execute(perform)

    def recover(self):
        def perform(store,proof):
            from whetstone.vnext_phase2_report_projection import recover_projections
            view=self._view_signals(proof)
            require(not any(r['pending'] for r in view['records']),'publish signal evidence before state recovery')
            self._barrier(store._token,self._sources())
            recover_projections(self,store,proof,signals=view)
            before=self.store.read(STATE_PATH);state=decode_json(before)
            if view['records']:state[STATE_FIELD]=self._projection(view)
            else:state.pop(STATE_FIELD,None)
            target=before if state==decode_json(before) else canonical_json_bytes(state)
            snapshot=self._sources()
            def validate(read,path,value):
                self.store.check(snapshot);proof.guard(read);self.run._guard(read)
                require(path==STATE_PATH and read(path)==before and value==target,'signal state changed')
                require(self._projection(self._view_signals(proof))==self._projection(view),'signal evidence changed')
            if target!=before:self.store.materialize(store._token,STATE_PATH,target,validate_target=validate)
            else:self.store.synchronize_existing(store._token,STATE_PATH,expected=target)
            result=self._public_signals(proof,self._view_signals(proof))
            require(result['state_current'] and result['mirrors_current'],'signal recovery incomplete')
            return dict(result,gate='signal_state_recovered')
        return self._execute(perform)
