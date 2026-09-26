"""Current-lineage declaration packages, scheduled final review and closeout."""
from copy import deepcopy

from whetstone.declaration import render_convergence_declaration, validate_convergence_declaration
from whetstone.evaluation import target_matrix_satisfied
from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_sequence import _Continuation, _Pass, sequence
from whetstone.vnext_verified_materialization import STATE_PATH

ALGORITHM = 'algorithms/vnext_verified_phase2_closeout_v1.md'
DECLARATION_SCHEMA = 'vnext_phase2_declaration_v1'
CLOSEOUT_SCHEMA = 'vnext_phase2_closeout_v1'
STATE_FIELD = 'vnext_phase2_closeout'
MIRROR = 'convergence_declaration.md'


def supported(proof):
    return any(r['path']==ALGORITHM for r in proof.reader.suite.manifest['algorithms'])


def _pins(proof):
    pins={r['path']:r['sha256'] for family in ('algorithms','schemas') for r in proof.reader.suite.manifest[family]}
    paths=[ALGORITHM]+['schemas/'+name+'.schema.json' for name in
        (DECLARATION_SCHEMA,CLOSEOUT_SCHEMA,'vnext_phase2_review_request_v3','vnext_phase2_consumption_v3',
         'terminal_report_v2','unresolved_issues','rubric_gaps')]
    for path in paths:
        require(path in pins and pins[path]==sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'Phase 2 closeout contract is outside supported suite or changed',path)


def _latest_issues(frames, reference):
    latest={f['bound'].request['step']['profile']:f for f in frames
            if f.get('consumed') and f['bound'].request['base_pointer']==reference}
    issues={}
    for frame in latest.values():
        for row in frame['review']['feedback']['feedback']:
            key=row['issue_id']
            require(key not in issues or issues[key]==row, 'conflicting current Phase 2 issue identity')
            issues[key]=deepcopy(row)
    return [issues[key] for key in sorted(issues)]


def _fields(config, manifest_path, raw, counts):
    return dict(target_phase=config['target_phase'],target_mode=config['target_mode'],workflow=config['workflow'],
        rubric_profile=config['rubric']['profile'],rubric_source=config['rubric']['source'],rubric_label=None,
        rubric_manifest_path=manifest_path,final_draft_hash=draft_hash(raw.decode()),
        rubric_content_hash=config['rubric']['artifact']['hash'],unresolved_blockers_count=counts['blockers'],
        unresolved_major_issues_count=counts['major_issues'],unresolved_rubric_gaps_count=counts['rubric_gaps'])


def _bundle(owner, frames, clean):
    """Derive a new immutable package; existing bytes are checked, never adopted."""
    proof=owner.proof;_pins(proof)
    require(owner.ordinal>1, 'declaration preparation requires a consumed Phase 2 predecessor')
    issues=_latest_issues(frames,proof.latest)
    # No gap-resolution receipts exist in this bounded owner. A later clean
    # review or promotion alone cannot erase an earlier explicit gap signal.
    retained=[r for f in frames if f.get('consumed') for r in f['review']['feedback']['feedback']]
    require(not any(r['rubric_impact'] is not None or 'rubric_gaps.json' in r['affected_sections'] for r in retained),
            'rubric-gap evidence requires its separately implemented resolution owner')
    config=owner.binding.configuration
    raw=proof.values(proof.latest)['base']
    directory=owner.directory+'/declaration'
    manifest=dict(schema_version='vnext-bound-rubric-v1',configuration=deepcopy(owner.binding.configuration_ref),
        workflow=config['workflow'],rubric_profile=config['rubric']['profile'],rubric_source=config['rubric']['source'],
        rubric_label=None,rubric_path=config['rubric']['artifact']['path'],rubric_content_hash=config['rubric']['artifact']['hash'],
        target_phase=config['target_phase'],target_mode=config['target_mode'])
    unresolved=dict(round_number=owner.number,draft_hash=draft_hash(raw.decode()),unresolved_issues=[dict(
        issue_id=r['issue_id'],issue_fingerprint=r['issue_fingerprint'],normalized_severity=r['normalized_severity'],
        affected_sections=deepcopy(r['affected_sections']),claim=r['claim'],in_scope=r['in_scope'],
        blocking_acceptance=r['normalized_severity'] in {'major','blocker'}) for r in issues])
    gaps=dict(round_number=owner.number,draft_hash=unresolved['draft_hash'],
              rubric_content_hash=manifest['rubric_content_hash'],rubric_gaps=[])
    proof.reader.suite.registry.validate(unresolved,'unresolved_issues')
    proof.reader.suite.registry.validate(gaps,'rubric_gaps')
    counts=dict(blockers=sum(r['normalized_severity']=='blocker' for r in issues),
                major_issues=sum(r['normalized_severity']=='major' for r in issues),rubric_gaps=0)
    text=render_convergence_declaration(**_fields(config,directory+'/rubric_manifest.json',raw,counts),
                                       reviewer_final_status='not_run',declaration_status='rejected')
    # Bind the exact V pointer/map lineage in addition to the normalized compatibility hash.
    text+='\n- current_verified_pointer_path: '+proof.latest['path']+'\n'
    text+='- current_verified_pointer_hash: '+proof.latest['hash']+'\n'
    text+='- final_draft_sha256: '+sha256_bytes(raw)+'\n'
    assets={'rubric_manifest':(directory+'/rubric_manifest.json',canonical_json_bytes(manifest)),
            'unresolved_issues':(directory+'/unresolved_issues.json',canonical_json_bytes(unresolved)),
            'rubric_gaps':(directory+'/rubric_gaps.json',canonical_json_bytes(gaps)),
            'declaration':(directory+'/convergence_declaration.md',text.encode())}
    packet=dict(schema_version='vnext-phase2-declaration-v1',job_id=config['job_id'],
        current_verified_pointer=deepcopy(proof.latest),configuration=deepcopy(owner.binding.configuration_ref),
        previous_consumption=deepcopy(owner.previous),round_number=owner.number,
        source_consumptions=[_ref(f['owner'].consumption_path,f['consumption']) for f in frames],
        counts=counts,final_draft_hash=unresolved['draft_hash'],final_draft_sha256=sha256_bytes(raw),clean_profiles=sorted(clean),
        **{key:dict(path=path,hash=sha256_bytes(value)) for key,(path,value) in assets.items()})
    proof.reader.suite.registry.validate(packet,DECLARATION_SCHEMA)
    ref=_ref(directory+'/commit.json',packet)
    pending=[]
    for path,value in list(assets.values())+[(ref['path'],canonical_json_bytes(packet))]:
        existing=owner._optional(path)
        require(existing is None or existing==value, 'declaration package conflicts with reproduced current evidence',path)
        if existing is None: pending.append(path)
    committed=ref['path'] not in pending
    require(not committed or not pending,'committed declaration package lacks dependencies')
    owner.store.check(owner.snapshot)
    proof.guard(owner.store.read)
    return dict(packet=packet,reference=ref,assets=assets,pending_paths=tuple(pending),committed=committed)


class _DeclarationPass(_Pass):
    request_schema='vnext_phase2_review_request_v3'
    consumption_schema='vnext_phase2_consumption_v3'

    def _build_review(self, proof, transport):
        package=_bundle(self,self.source_frames,self.source_clean)
        require(package['committed'],'final strict review requires a committed declaration package')
        required={r['name'] for r in self.binding.configuration['profiles']}-{'convergence_strict_check'}
        require(required<=set(self.source_clean),'final declaration review lacks current prior-profile cleanliness')
        require(not any(package['packet']['counts'].values()), 'final declaration review has unresolved serious debt')
        context=dict(binding=package['reference'],packet=package['packet'],target_matrix=dict(
            target_phase='final',target_mode='strict',blockers_allowed=False,major_issues_allowed=False,
            unresolved_rubric_gaps_allowed=False,declaration_required=True),
            artifacts={key:dict(reference=package['packet'][key],content=value.decode())
                       for key,(_,value) in package['assets'].items()})
        return self._render_review(proof,transport,self.binding,self.entry,self.number,self.step,
            directory=self.directory,previous_consumption=self.previous,declaration=context)

    def _project(self,bound,review,receipt):
        scheduler=deepcopy(self.scheduler)
        rows=review['feedback']['feedback']
        scheduler.record_result(self.step['profile'],blocker_count=sum(r['in_scope'] and r['normalized_severity']=='blocker' for r in rows),
            major_count=sum(r['in_scope'] and r['normalized_severity']=='major' for r in rows))
        profiles=[dict(step_index=i,**r) for i,r in enumerate(scheduler.status()['profiles'],1)]
        for r in profiles:del r['active']
        return dict(schema_version='vnext-phase2-consumption-v3',request=deepcopy(bound.request_ref),
            result=_ref(self.directory+'/execution/result.json',receipt),base_pointer=deepcopy(bound.request['base_pointer']),
            accepted_passes=self.ordinal,profiles=profiles,findings=[],evidence=dict(declaration_review_only=True),
            next_gate='declaration_closeout_required',candidate_authorized=False,next_review_authorized=False,phase_complete=False,
            previous_consumption=deepcopy(self.previous))

    def _synchronize_declaration(self,store):
        package=_bundle(self,self.source_frames,self.source_clean)
        self.store.synchronize(store._token,self.snapshot,self.run._record['descriptor']['path'])
        for path,raw in list(package['assets'].values())+[(package['reference']['path'],canonical_json_bytes(package['packet']))]:
            self.store.synchronize_existing(store._token,path,expected=raw)

    def _synchronize_request(self,store,proof,bound):
        self._synchronize_declaration(store)
        super()._synchronize_request(store,proof,bound)


def declaration_owner(owner,frames,clean):
    if not supported(owner.proof) or owner.step['index']!=3:return owner
    _pins(owner.proof)
    replacement=_DeclarationPass(owner.run,owner.store,owner.proof,owner.binding,owner.entry,ordinal=owner.ordinal,
        number=owner.number,step=owner.step,previous=owner.previous,scheduler=owner.scheduler,snapshot=owner.snapshot)
    # _Pass initialization preserves its old schemas; this owner has its own receipt projection.
    replacement.consumption_schema='vnext_phase2_consumption_v3'
    replacement.source_frames=list(frames);replacement.source_clean=set(clean)
    return replacement


class _Declaration(_Continuation):
    def _proof(self,read):
        proof=super()._proof(read);_pins(proof);return proof

    def prepare(self):
        def publish(store,proof):
            state=sequence(proof)
            require(state['gate']=='review','declaration preparation needs an eligible scheduled request, not an extra pass')
            owner=state['owner'];owner.snapshot[STATE_PATH]=self.store.read(STATE_PATH)
            package=_bundle(owner,state['frames'],state['clean'])
            owner.store.synchronize(store._token,owner.snapshot,self.run._record['descriptor']['path'])
            for ref in (owner.binding.configuration_ref,owner.binding.configuration['rubric']['artifact'],proof.latest):
                self.store.synchronize_existing(store._token,ref['path'],expected=proof.reader.raw(ref))
            require(_bundle(owner,state['frames'],state['clean'])==package,'declaration sources changed during barriers')
            for path,raw in package['assets'].values():store.publish(store._token,path,raw)
            store.publish(store._token,package['reference']['path'],package['packet'])
            result=_bundle(owner,state['frames'],state['clean'])
            require(result['committed'],'declaration publication incomplete')
            return dict(declaration=result['packet'],reference=result['reference'],committed=True,phase_complete=False)
        return self._execute(publish)

    def _closeout(self,proof):
        from whetstone.vnext_verified_phase2_termination import supported as termination_supported, pins as termination_pins, exhausted_closeout
        termination = termination_supported(proof)
        if termination: termination_pins(proof)
        state=sequence(proof)
        if state['gate']!='declaration_closeout_required':
            return dict(gate='declaration_review_not_completed',sequence_gate=state['gate'],committed=False,phase_complete=False)
        frame=state['frames'][-1];owner=frame['owner'];bound=frame['bound']
        require(bound.request['base_pointer']==proof.latest,'declaration review is stale')
        package=_bundle(owner,owner.source_frames,owner.source_clean)
        rows=_latest_issues(state['frames'],proof.latest)
        from whetstone.vnext_verified_phase2_findings import supported as findings_supported, assessment
        findings=assessment(self,proof,state,package,rows) if findings_supported(proof) else None
        blockers=[]
        if findings is not None:
            if not findings['committed']:blockers.append('final_findings_reconciliation_uncommitted')
            if findings['packet']['route']!='closeout_eligible':blockers.append(findings['packet']['route'])
        elif frame['review']['feedback']['feedback']:blockers.append('final_findings_require_reconciliation')
        required={r['name'] for r in owner.binding.configuration['profiles']}
        if not required<=set(state['clean']):blockers.append('current_profile_verification_missing')
        if any(r['normalized_severity'] in {'blocker','major'} for r in rows):blockers.append('serious_findings')
        if any(r['rubric_impact'] is not None or 'rubric_gaps.json' in r['affected_sections'] for r in rows):blockers.append('rubric_resolution_required')
        counts=package['packet']['counts']
        current_counts=dict(blockers=sum(r['normalized_severity']=='blocker' for r in rows),
            major_issues=sum(r['normalized_severity']=='major' for r in rows),rubric_gaps=0)
        if counts!=current_counts:blockers.append('declaration_counts_changed')
        config=owner.binding.configuration;raw=proof.values(proof.latest)['base']
        fields=_fields(config,package['packet']['rubric_manifest']['path'],raw,counts)
        validation={key:value for key,value in fields.items() if key not in {'target_phase','target_mode'}}
        if not validate_convergence_declaration(package['assets']['declaration'][1].decode(),**validation):
            blockers.append('declaration_identity_mismatch')
        if not target_matrix_satisfied(target_phase=config['target_phase'],target_mode=config['target_mode'],
                issues=rows,declaration_accepted=not blockers):blockers.append('target_not_satisfied')
        # This is an ordinary scheduled review, not the optional post-sequence
        # review-only closeout. Findings may require repair/review within its
        # remaining budget; unsupported repair must not become a terminal.
        if blockers:
            if termination:
                return exhausted_closeout(self,proof,state,package,findings,rows,blockers)
            return dict(gate='declaration_reconciliation_required',blockers=blockers,
                        committed=False,phase_complete=False)
        accepted=True
        status='accepted'
        terminal='CONVERGED'
        final=render_convergence_declaration(**_fields(config,package['packet']['rubric_manifest']['path'],raw,current_counts),
                    reviewer_final_status=status,declaration_status=status)
        final+='\n- current_verified_pointer_path: '+proof.latest['path']+'\n'
        final+='- current_verified_pointer_hash: '+proof.latest['hash']+'\n'
        final+='- final_draft_sha256: '+sha256_bytes(raw)+'\n'
        report=self._report(proof,terminal=terminal,reason='vnext_phase2_declaration_accepted')
        directory='rounds/phase2/closeouts/closeout-'+frame['receipt']['request']['hash']
        final_ref=dict(path=directory+'/convergence_declaration.md',hash=sha256_bytes(final.encode()))
        report_ref=_ref(directory+'/terminal_report.json',report)
        packet=dict(schema_version='vnext-phase2-closeout-v1',job_id=config['job_id'],
            current_verified_pointer=deepcopy(proof.latest),configuration=deepcopy(owner.binding.configuration_ref),
            entry=deepcopy(bound.request['entry']),declaration_binding=package['reference'],review_request=bound.request_ref,
            review_result=_ref(owner.directory+'/execution/result.json',frame['receipt']),
            review_consumption=_ref(owner.consumption_path,frame['consumption']),final_declaration=final_ref,terminal_report=report_ref,
            terminal_state=terminal,accepted=accepted,reviewer_final_status=status,declaration_status=status,blockers=blockers,
            profiles=[dict(step_index=i,**r) for i,r in enumerate(state['scheduler'].status()['profiles'],1)],
            clean_profiles=state['clean'],apply_back_permitted=False)
        schema=CLOSEOUT_SCHEMA
        if findings is not None:
            packet.update(schema_version='vnext-phase2-closeout-v2',finding_reconciliation=findings['reference'],
                          unresolved_issues=findings['packet']['unresolved_issues'])
            schema='vnext_phase2_closeout_v2'
        proof.reader.suite.registry.validate(packet,schema)
        ref=_ref(directory+'/commit.json',packet)
        assets=((final_ref['path'],final.encode()),(report_ref['path'],canonical_json_bytes(report)))
        pending=[]
        for path,value in assets+((ref['path'],canonical_json_bytes(packet)),):
            existing=self._optional(path)
            require(existing is None or existing==value,'Phase 2 closeout differs from exact evidence replay',path)
            if existing is None:pending.append(path)
        committed=ref['path'] not in pending
        require(not committed or not pending,'committed Phase 2 closeout lacks dependencies')
        proof.guard(self.store.read);self.run._guard(self.store.read)
        return dict(gate='closeout_committed' if committed else 'closeout_publication_required',packet=packet,reference=ref,
                    assets=assets,committed=committed,phase_complete=committed and accepted,pending_paths=tuple(pending),
                    owner=owner,frame=frame)

    def _public(self,proof,view):
        result={key:deepcopy(value) for key,value in view.items() if key not in {'owner','frame','assets'}}
        if view['committed']:
            before,target,mirror=self._targets(view)
            result.update(state_current=before==target,mirror_current=mirror==view['assets'][0][1])
            result['phase_complete']=result['phase_complete'] and result['state_current'] and result['mirror_current']
            if 'failure_report' in view['packet']:
                result['halt_complete']=result['state_current'] and result['mirror_current']
        proof.guard(self.store.read)
        return result

    def status(self):
        proof=self._proof(self.store.read);work=self._observe(proof)
        if work.outcome!='work_available':return work
        return self._public(proof,self._closeout(proof))

    def _synchronize(self,store,proof,view):
        owner= view['owner'];frame=view['frame']
        owner._synchronize_request(store,owner.proof,frame['bound'])
        frame['journal'].synchronize(store._token,frame['bound'].request,frame['outcomes'])
        for ref in (view['packet']['review_result'],view['packet']['review_consumption'],frame['receipt']['feedback']):
            self.store.synchronize_existing(store._token,ref['path'],expected=proof.reader.raw(ref))
        if 'finding_reconciliation' in view['packet']:
            for ref in (view['packet']['unresolved_issues'],view['packet']['finding_reconciliation']):
                self.store.synchronize_existing(store._token,ref['path'],expected=proof.reader.raw(ref))
        require(self._closeout(proof)['packet']==view['packet'],'Phase 2 closeout changed during source barriers')

    def finish(self):
        def publish(store,proof):
            from datetime import datetime, timezone
            self._publication_time=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
            view=self._closeout(proof)
            require('packet' in view,'Phase 2 declaration acceptance is incomplete; no terminal may be published')
            self._synchronize(store,proof,view)
            for path,raw in view['assets']:store.publish(store._token,path,raw)
            store.publish(store._token,view['reference']['path'],view['packet'])
            result=self._closeout(proof)
            require(result['committed'],'Phase 2 closeout publication incomplete')
            return self._public(proof,result)
        return self._execute(publish)

    def _targets(self,view):
        raw=self.store.read(STATE_PATH);state=decode_json(raw)
        state[STATE_FIELD]=deepcopy(view['reference'])
        target=raw if state==decode_json(raw) else canonical_json_bytes(state)
        mirror=self._optional(view.get('mirror_path',MIRROR))
        # Never overwrite unowned user/external declaration text as recovery.
        owned_failure=False
        if 'failure_report' in view['packet'] and mirror is not None and mirror!=view['assets'][0][1]:
            from whetstone.vnext_verified_phase2_failure import supported as failure_supported, owned_failure_mirror
            if failure_supported(self._proof(self.store.read)):
                owned_failure=owned_failure_mirror(self.run,mirror)
        require(mirror is None or mirror==view['assets'][0][1] or owned_failure,
                'root failure report conflicts with committed closeout' if 'failure_report' in view['packet']
                else 'root declaration conflicts with committed closeout')
        return raw,target,mirror

    def reconcile(self):
        def recover(store,proof):
            view=self._closeout(proof)
            require(view['committed'],'Phase 2 state recovery requires committed closeout')
            self._synchronize(store,proof,view)
            for path,raw in view['assets']+((view['reference']['path'],canonical_json_bytes(view['packet'])),):
                self.store.synchronize_existing(store._token,path,expected=raw)
            before,target,mirror=self._targets(view)
            declaration=view['assets'][0][1]
            mirror_path=view.get('mirror_path',MIRROR)
            for path,old,new in ((mirror_path,mirror,declaration),(STATE_PATH,before,target)):
                def validate(read,name,value,path=path,old=old,new=new):
                    proof.guard(read);self.run._guard(read)
                    try: existing=read(path)
                    except FileNotFoundError:existing=None
                    require(name==path and value==new and existing==old,'Phase 2 derived target changed')
                    require(read(view['reference']['path'])==canonical_json_bytes(view['packet']),'Phase 2 closeout commit changed')
                if path==mirror_path and old!=new:
                    validate(self.store.read,path,new)
                    # Terminal projection is create-only. The frozen storage
                    # materialization whitelist does not include declarations.
                    if old is not None and 'failure_report' in view['packet']:
                        from whetstone.vnext_verified_phase2_failure import _Failure
                        failure=_Failure(self.run);failure._sync(store,proof,failure._failure_view(proof))
                        def transition(before,after):
                            require(before==old and after==new,'failure projection changed')
                            validate(self.store.read,path,new)
                            require(failure._failure_view(proof)['records'],'failure projection lacks historical ownership')
                        self.store.replace_pointer(store._token,path,expected=old,
                            snapshot=view['packet']['failure_report'],validate_transition=transition)
                    else:self.store.publish(store._token,path,new)
                elif old!=new:self.store.materialize(store._token,path,new,validate_target=validate)
                else:self.store.synchronize_existing(store._token,path,expected=new)
            result=self._public(proof,self._closeout(proof))
            require(result['state_current'] and result['mirror_current'],'Phase 2 recovery incomplete')
            result['gate']='phase2_state_recovered'
            return result
        return self._execute(recover)
