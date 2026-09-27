"""Opt-in Reviewer failure reports and recovery over the existing attempt journal."""
from copy import copy, deepcopy
from datetime import datetime, timezone
from dataclasses import replace

from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_closeout import _Declaration, _latest_issues
from whetstone.vnext_verified_phase2_sequence import sequence
from whetstone.vnext_verified_materialization import STATE_PATH

ALGORITHM='algorithms/vnext_verified_phase2_failure_v1.md'
SCHEMA='vnext_phase2_reviewer_failure_v1'
STATE_FIELD='vnext_phase2_reviewer_failure'
MIRRORS={'error':'rounds/artifact_validation_error.json','failure':'rounds/convergence_failure_report.json'}


def supported(proof):
    return any(r['path']==ALGORITHM for r in proof.reader.suite.manifest['algorithms'])


def _classification(outcomes):
    last=outcomes[-1]
    require(last['classification']!='valid_review','valid Reviewer output is not failure evidence')
    require(len(outcomes)==2 or last['classification']!='shape_invalid',
            'an available shape retry is not an exhausted failure')
    timeout=last['classification']=='timeout'
    terminal='HALTED_CLIENT_TIMEOUT' if timeout else 'HALTED_ARTIFACT_INVALID'
    eligible=len(outcomes)<2 and last['classification']!='invalid_review'
    return terminal,eligible


class _Failure(_Declaration):
    def _proof(self,read):
        proof=super()._proof(read)
        entries={r['path']:r['sha256'] for family in ('algorithms','schemas') for r in proof.reader.suite.manifest[family]}
        for path in (ALGORITHM,'schemas/'+SCHEMA+'.schema.json','schemas/artifact_validation_error.schema.json',
                     'schemas/convergence_failure_report.schema.json'):
            require(path in entries and entries[path]==sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                    'Phase 2 Reviewer failure contract is outside supported suite or changed',path)
        return proof

    def _record(self,proof,frames,index,outcomes,stamp=None):
        frame=frames[index];owner=frame['owner'];bound=frame['bound'];base=owner.proof
        directory=owner.directory+'/execution/failures/attempt-'+str(len(outcomes))
        existing=self._optional(directory+'/failure.json')
        if existing is not None:
            retained=decode_json(existing);proof.reader.suite.registry.validate(retained,'convergence_failure_report')
            stamp=retained['generated_at']
        committed=self._optional(directory+'/commit.json')
        terminal,eligible=_classification(outcomes)
        if stamp is None:
            require(committed is None,'committed Reviewer failure lacks its report')
            return dict(frame=frame,index=index,outcomes=outcomes,committed=False,pending=True,reference=None)
        config=owner.binding.configuration;pointer=base.pointers[-1]
        raw=base.values(base.latest)['base'];normalized=draft_hash(raw.decode())
        prior=frames[:index];rows=_latest_issues(prior,base.latest)
        from whetstone.vnext_phase2_rubric import report_gaps
        gaps = report_gaps(proof,prior,base.latest)
        manifest=dict(schema_version='vnext-bound-rubric-v1',configuration=owner.binding.configuration_ref,
            workflow=config['workflow'],rubric_profile=config['rubric']['profile'],rubric_source=config['rubric']['source'],
            rubric_label=None,rubric_path=config['rubric']['artifact']['path'],rubric_content_hash=config['rubric']['artifact']['hash'],
            target_phase=config['target_phase'],target_mode=config['target_mode'])
        from whetstone.vnext_phase2_gap_acceptance import bind_manifest
        bind_manifest(manifest,proof,prior,base.latest)
        manifest_ref=_ref(directory+'/rubric_manifest.json',manifest)
        declaration=bound.inputs.get('declaration')
        profiles=owner.scheduler.status()
        latest={f['bound'].request['step']['profile']:f for f in prior
                if f.get('consumed') and f['bound'].request['base_pointer']==base.latest}
        clean={name for name,f in latest.items() if not any(r['in_scope'] and r['normalized_severity'] in {'major','blocker'}
                                                           for r in f['review']['feedback']['feedback'])}
        profiles['unverified_profiles']=sorted({r['name'] for r in config['profiles']}-clean)
        last=next((f for f in reversed(prior) if f.get('consumed')),None)
        last_findings=None
        if last is not None:
            serious=[r for r in last['review']['feedback']['feedback'] if r['in_scope'] and r['normalized_severity'] in {'major','blocker'}]
            last_findings=dict(round_number=last['bound'].request['round_number'],profile=last['bound'].request['step']['profile'],
                blocker_count=sum(r['normalized_severity']=='blocker' for r in serious),
                major_count=sum(r['normalized_severity']=='major' for r in serious),feedback_ids=[r['feedback_id'] for r in serious])
        def issues(severity):
            return [{k:deepcopy(r[k]) for k in ('issue_id','issue_fingerprint','normalized_severity','affected_sections','claim')}
                    for r in rows if r['normalized_severity']==severity]
        failure=dict(terminal_state=terminal,generated_at=stamp,round_number=owner.number,draft_hash=normalized,
            final_draft_path=pointer['verified_draft_path'],
            final_declaration_path=declaration['packet']['declaration']['path'] if declaration else None,
            target_phase=config['target_phase'],target_mode=config['target_mode'],workflow=config['workflow'],
            rubric_profile=config['rubric']['profile'],rubric_source=config['rubric']['source'],rubric_label=None,
            rubric_manifest_path=manifest_ref['path'],unresolved_blockers=issues('blocker'),unresolved_major_issues=issues('major'),
            unresolved_rubric_gaps=gaps,reviewer_final_status='not_run',
            last_accepted_draft_hash=draft_hash(proof.reader.raw(owner.entry.entry['current_verified_draft']).decode()),
            last_draft_hash=normalized,exit_reason='vnext_phase2_reviewer_'+outcomes[-1]['classification'],
            recommendation='manual_review_required',profile_status=profiles,last_reviewer_findings=last_findings)
        job=proof.seed_values['job'];descriptor=self.run._record['descriptor']
        failure['run_artifact_pointers']=dict(
            job_descriptor=dict(path=descriptor['path'],exists=True,sha256=descriptor['hash']),
            scope_contract=dict(path=job['scope_contract_path'],exists=job['scope_contract_path'] is not None,
                                sha256=job['scope_contract_hash']))
        error=dict(terminal_state=terminal,generated_at=stamp,round_number=owner.number,phase='phase_2',
            profile=bound.request['step']['profile'],client_role='reviewer',client=deepcopy(config['reviewer']),
            failure_type='client_timeout' if terminal=='HALTED_CLIENT_TIMEOUT' else
                'artifact_validation' if outcomes[-1]['classification'] in {'shape_invalid','invalid_review'} else 'client_error',
            attempts=[dict(attempt_number=o['attempt'],artifact_name='reviewer_feedback.json',validation_errors=[o['error']],
                raw_response_path=frame['journal'].directory+f"/attempts/{o['attempt']}/response.json" if o['response_hash'] else None)
                for o in outcomes],retry_exhausted=not eligible,last_valid_draft_hash=normalized,
            last_valid_draft_path=pointer['verified_draft_path'],recommendation='manual_review_required')
        # Reproduce the candidate projection at this historical request's pointer.
        historical=copy(base)
        limit=pointer.get('source_candidate_id')
        creation=next((r for r in proof.view.creations if r['candidate_id']==limit),None)
        historical.view=replace(proof.view,creations=tuple(r for r in proof.view.creations
            if creation is not None and r['candidate_creation_ordinal']<=creation['candidate_creation_ordinal']))
        report=self._report(historical,terminal=terminal,reason=failure['exit_reason'])
        report['resume']=dict(permitted=eligible,next_gate='review' if eligible else None,
            reason='explicit_phase2_reviewer_continuation' if eligible else 'phase2_reviewer_request_closed')
        for packet,schema in ((failure,'convergence_failure_report'),(error,'artifact_validation_error'),(report,'terminal_report_v2')):
            proof.reader.suite.registry.validate(packet,schema)
        assets={directory+'/failure.json':canonical_json_bytes(failure),directory+'/error.json':canonical_json_bytes(error),
                directory+'/terminal.json':canonical_json_bytes(report),manifest_ref['path']:canonical_json_bytes(manifest)}
        packet=dict(schema_version='vnext-phase2-reviewer-failure-v1',request=bound.request_ref,
            current_verified_pointer=base.latest,configuration=owner.binding.configuration_ref,entry=bound.request['entry'],
            outcomes=[_ref(frame['journal'].directory+f"/attempts/{o['attempt']}/outcome.json",o) for o in outcomes],
            failure=_ref(directory+'/failure.json',failure),error=_ref(directory+'/error.json',error),
            terminal=_ref(directory+'/terminal.json',report),rubric_manifest=manifest_ref)
        proof.reader.suite.registry.validate(packet,SCHEMA)
        reference=_ref(directory+'/commit.json',packet)
        pending=[]
        for path,value in [*assets.items(),(reference['path'],canonical_json_bytes(packet))]:
            observed=self._optional(path)
            require(observed is None or observed==value,'Reviewer failure differs from exact evidence replay',path)
            if observed is None:pending.append(path)
        require(committed is None or not pending,'committed Reviewer failure lacks dependencies')
        return dict(frame=frame,index=index,outcomes=outcomes,packet=packet,assets=assets,reference=reference,
                    committed=committed is not None,pending=bool(pending))

    def _failure_view(self,proof,stamp=None):
        if not hasattr(proof,'view'):proof.inspect_registry()
        state=sequence(proof);records=[];active=None
        for index,frame in enumerate(state['frames']):
            root=frame['journal'].directory+'/failures'
            try:entries=self.store.list_directory(root)
            except FileNotFoundError:entries=()
            require(all(name.startswith('.vnext-tmp-') or (kind=='directory' and name in {'attempt-1','attempt-2'})
                        for name,kind in entries),'unknown Reviewer failure record')
            for count in (1,2):
                present=any(name=='attempt-'+str(count) for name,_ in entries)
                current=(index==len(state['frames'])-1 and frame['review'] is None and count==len(frame['outcomes']) and count>0)
                if current and count==1 and frame['outcomes'][-1]['classification']=='shape_invalid':current=False
                if not (present or current):continue
                require(count<=len(frame['outcomes']),'Reviewer failure lacks its attempt evidence')
                record=self._record(proof,state['frames'],index,frame['outcomes'][:count],stamp)
                records.append(record)
                if current:active=record
        proof.guard(self.store.read);self.run._guard(self.store.read)
        return dict(state=state,records=records,active=active)

    def _sync(self,store,proof,view):
        for frame in view['state']['frames']:
            frame['owner']._synchronize_request(store,frame['owner'].proof,frame['bound'])
            frame['journal'].synchronize(store._token,frame['bound'].request,frame['outcomes'])
            if frame.get('receipt') is not None:
                for ref in (frame['receipt']['feedback'],
                            _ref(frame['journal'].directory+'/result.json',frame['receipt'])):
                    self.store.synchronize_existing(store._token,ref['path'],expected=proof.reader.raw(ref))
            if frame.get('consumed'):
                ref=_ref(frame['owner'].consumption_path,frame['consumption'])
                self.store.synchronize_existing(store._token,ref['path'],expected=proof.reader.raw(ref))
        for record in view['records']:
            if record['committed']:
                for path,raw in [*record['assets'].items(),(record['reference']['path'],canonical_json_bytes(record['packet']))]:
                    self.store.synchronize_existing(store._token,path,expected=raw)
        proof.guard(self.store.read);self.run._guard(self.store.read)

    def _publish(self,store,proof):
        stamp=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
        view=self._failure_view(proof,stamp)
        if not view['records']:return view
        self._sync(store,proof,view)
        check=self._failure_view(proof,stamp)
        require([r.get('packet') for r in check['records']]==[r.get('packet') for r in view['records']],
                'Reviewer failure changed during source barriers')
        for record in view['records']:
            for path,raw in record['assets'].items():store.publish(store._token,path,raw)
            store.publish(store._token,record['reference']['path'],record['packet'])
        return self._failure_view(proof)

    def _projection(self,view):
        active=view['active']
        return dict(active=active['reference'] if active and active['committed'] else None,
                    history=[r['reference'] for r in view['records'] if r['committed']])

    def _public_failure(self,proof,view):
        active=view['active'];projection=self._projection(view)
        state=decode_json(self.store.read(STATE_PATH))
        current=state.get(STATE_FIELD)==projection if view['records'] else STATE_FIELD not in state
        mirrors_current=True
        if view['records'] and not any(r['pending'] for r in view['records']):
            latest=view['records'][-1]
            for key,path in MIRRORS.items():
                expected=latest['assets'][latest['packet'][key]['path']]
                if key=='failure' and view['state']['gate']=='declaration_closeout_required':
                    closeout=self._closeout(proof)
                    if closeout.get('committed') and 'failure_report' in closeout['packet']:
                        expected=closeout['assets'][0][1]
                mirrors_current=mirrors_current and self._optional(path)==expected
        from whetstone.vnext_verified_phase2_correction_failure import supported as correction_supported
        if correction_supported(proof):
            from whetstone.vnext_phase2_report_projection import projections
            plan=projections(self,proof,reviewer=view)
            mirrors_current=all(self._optional(path)==target['raw'] for path,target in plan.items())
        terminal=_classification(active['outcomes'])[0] if active else None
        return dict(gate='reviewer_failure' if active else 'no_active_reviewer_failure',terminal_state=terminal,
            resume_permitted=bool(active and _classification(active['outcomes'])[1]),
            committed=bool(active and active['committed']),state_current=current,mirrors_current=mirrors_current,
            publication_required=any(r['pending'] for r in view['records']),
            active=projection['active'],history=projection['history'],phase_complete=False)

    def status_failure(self):
        proof=self._proof(self.store.read);work=self._observe(proof)
        if work.outcome!='work_available':return work
        view=self._failure_view(proof);result=self._public_failure(proof,view)
        proof.guard(self.store.read);return result

    def publish_failure(self):
        return self._execute(lambda store,proof:self._public_failure(proof,self._publish(store,proof)))

    def _recover(self,store,proof,view):
        require(not any(r['pending'] for r in view['records']),'publish Reviewer failure evidence before state recovery')
        self._sync(store,proof,view)
        from whetstone.vnext_verified_phase2_correction_failure import supported as correction_supported
        if correction_supported(proof):
            from whetstone.vnext_phase2_report_projection import recover_projections
            recover_projections(self,store,proof,reviewer=view)
        else:
            # Report paths are owned projections of immutable records, not materializations.
            latest=view['records'][-1] if view['records'] else None
            for key,path in MIRRORS.items():
                if latest is None:continue
                ref=latest['packet'][key];desired=latest['assets'][ref['path']];old=self._optional(path)
                allowed=[r['assets'][r['packet'][key]['path']] for r in view['records']]
                # A later committed exhaustion report supersedes these historical reports.
                if key=='failure' and view['state']['gate']=='declaration_closeout_required':
                    closeout=self._closeout(proof)
                    if closeout.get('committed') and 'failure_report' in closeout['packet']:
                        ref=closeout['packet']['failure_report'];desired=closeout['assets'][0][1]
                        self._synchronize(store,proof,closeout)
                        for p,v in closeout['assets']+((closeout['reference']['path'],canonical_json_bytes(closeout['packet'])),):
                            self.store.synchronize_existing(store._token,p,expected=v)
                require(old is None or old==desired or old in allowed,'unowned Phase 2 failure report conflicts',path)
                if old==desired:self.store.synchronize_existing(store._token,path,expected=desired)
                elif old is None:store.publish(store._token,path,desired)
                else:
                    def validate(before,after,old=old,desired=desired):
                        require(before==old and after==desired,'Reviewer failure projection changed')
                        proof.guard(self.store.read);self._failure_view(proof)
                    self.store.replace_pointer(store._token,path,expected=old,snapshot=ref,validate_transition=validate)
        before=self.store.read(STATE_PATH);state=decode_json(before)
        if view['records']:state[STATE_FIELD]=self._projection(view)
        else:state.pop(STATE_FIELD,None)
        target=canonical_json_bytes(state) if state!=decode_json(before) else before
        def validate(read,path,value):
            proof.guard(read);self.run._guard(read)
            require(path==STATE_PATH and value==target and read(path)==before,'Reviewer failure state changed')
            fresh=self._failure_view(proof)
            require(self._projection(fresh)==self._projection(view),'Reviewer failure changed before state write')
        if before!=target:self.store.materialize(store._token,STATE_PATH,target,validate_target=validate)
        else:self.store.synchronize_existing(store._token,STATE_PATH,expected=target)
        result=self._public_failure(proof,self._failure_view(proof));require(result['state_current'],'failure state recovery incomplete')
        result['gate']='reviewer_failure_state_recovered';return result

    def recover_failure(self):
        return self._execute(lambda store,proof:self._recover(store,proof,self._failure_view(proof)))

    def execute_review(self,ordinal,*,client=None,continuation=False):
        require(type(ordinal) is int and ordinal>0,'Reviewer failure continuation needs an exact pass')
        require(type(continuation) is bool,'Phase 2 continuation must be an explicit boolean')
        def perform(store,proof):
            view=self._failure_view(proof);frames=view['state']['frames']
            require(frames and frames[-1]['owner'].ordinal==ordinal,'Reviewer request is not the current last pass')
            frame=frames[-1];owner=frame['owner']
            require(owner.proof.latest==proof.latest,'historical Reviewer request cannot execute')
            if any(r['pending'] for r in view['records']):
                return self._public_failure(proof,self._publish(store,proof))
            status=self._public_failure(proof,view)
            if not status['state_current'] or not status['mirrors_current']:
                return dict(status,gate='reviewer_failure_state_recovery_required')
            self._sync(store,proof,view)
            owner.snapshot[STATE_PATH]=self.store.read(STATE_PATH)
            owner._execute=lambda operation:operation(store,owner.proof)
            result=owner.execute(client=client,continuation=continuation)
            self._publish(store,proof)
            return result
        return self._execute(perform)


def owned_failure_mirror(run,raw):
    owner=_Failure(run);proof=owner._proof(owner.store.read);view=owner._failure_view(proof)
    from whetstone.vnext_verified_phase2_correction_failure import supported as correction_supported
    if correction_supported(proof):
        from whetstone.vnext_phase2_report_projection import projections
        plan=projections(owner,proof,reviewer=view)
        return raw in plan.get(MIRRORS['failure'],{}).get('allowed',[])
    return any(r['committed'] and r['assets'][r['packet']['failure']['path']]==raw for r in view['records'])
