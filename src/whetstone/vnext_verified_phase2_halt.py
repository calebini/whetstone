"""Current-lineage maintenance and terminal evidence after ordinary exhaustion."""
from copy import deepcopy

from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import canonical_json_bytes, decode_json, require
from whetstone.vnext_phase2_rubric import report_gaps
from whetstone.vnext_phase2_targets import pins
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_closeout import _bundle, _latest_issues
from whetstone.vnext_verified_phase2_sequence import _Evidence, _Pass


def maintenance_owner(run, proof, state):
    pins(proof.reader.suite)
    require(state['gate'] in {'budget_exhausted','closeout_required'}, 'ordinary exhaustion evidence is required')
    require(state['frames'] and all(not frame.get('resolution') or frame['resolution']['committed']
                                  for frame in state['frames']), 'publish verified resolution receipts before halt maintenance')
    frame=state['frames'][-1];old=frame['owner']
    evidence=_Evidence(run.store)
    owner=_Pass(run,evidence,proof,old.binding,old.entry,ordinal=old.ordinal+1,number=old.number,
        step=old.step,previous=_ref(old.consumption_path,frame['consumption']),scheduler=state['scheduler'],snapshot={})
    owner.directory=old.directory+'/halt'
    owner.source_frames=state['frames'];owner.source_clean=set(state['clean'])
    return owner


def view(publisher, proof, state):
    owner=maintenance_owner(publisher.run,proof,state)
    package=_bundle(owner,state['frames'],state['clean'])
    if not package['committed']:
        return dict(gate='declaration_maintenance_required',sequence_gate=state['gate'],committed=False,phase_complete=False)
    frame=state['frames'][-1];config=owner.binding.configuration
    directory=owner.directory+'/terminal';path=directory+'/convergence_failure_report.json'
    existing=publisher._optional(path);stamp=getattr(publisher,'_publication_time',None)
    if existing is not None:
        retained=decode_json(existing);proof.reader.suite.registry.validate(retained,'convergence_failure_report')
        stamp=retained['generated_at']
    if stamp is None:
        require(publisher._optional(directory+'/commit.json') is None,'committed exhaustion lacks failure report')
        return dict(gate='failure_report_publication_required',proposed_terminal_state='TARGET_NOT_REACHED',
                    committed=False,phase_complete=False,halt_complete=False)
    rows=_latest_issues(state['frames'],proof.latest)
    def issues(severity):
        return [{key:deepcopy(row[key]) for key in ('issue_id','issue_fingerprint','normalized_severity','affected_sections','claim')}
                for row in rows if row['in_scope'] and row['normalized_severity']==severity]
    raw=proof.values(proof.latest)['base'];normalized=draft_hash(raw.decode())
    profiles=state['scheduler'].status()
    profiles['unverified_profiles']=sorted({row['name'] for row in config['profiles']}-set(state['clean']))
    last=frame['review']['feedback']['feedback']
    report=dict(terminal_state='TARGET_NOT_REACHED',generated_at=stamp,round_number=owner.number,draft_hash=normalized,
        final_draft_path=proof.pointers[-1]['verified_draft_path'],final_declaration_path=package['packet']['declaration']['path'],
        target_phase=config['target_phase'],target_mode=config['target_mode'],workflow=config['workflow'],
        rubric_profile=config['rubric']['profile'],rubric_source=config['rubric']['source'],rubric_label=None,
        rubric_manifest_path=package['packet']['rubric_manifest']['path'],unresolved_blockers=issues('blocker'),
        unresolved_major_issues=issues('major'),unresolved_rubric_gaps=report_gaps(proof,state['frames'],proof.latest),
        reviewer_final_status='not_run',last_accepted_draft_hash=draft_hash(proof.reader.raw(owner.entry.entry['current_verified_draft']).decode()),
        last_draft_hash=normalized,exit_reason='vnext_phase2_'+state['gate'],recommendation='manual_review_required',
        profile_status=profiles,last_reviewer_findings=dict(round_number=owner.number,profile=owner.step['profile'],
            blocker_count=sum(row['in_scope'] and row['normalized_severity']=='blocker' for row in last),
            major_count=sum(row['in_scope'] and row['normalized_severity']=='major' for row in last),
            feedback_ids=[row['feedback_id'] for row in last if row['in_scope'] and row['normalized_severity'] in {'major','blocker'}]))
    evidence=dict(schema_version='vnext-phase2-halt-evidence-v1',current_verified_pointer=deepcopy(proof.latest),
        configuration=deepcopy(owner.binding.configuration_ref),declaration=package['reference'],sequence_gate=state['gate'],
        source_consumptions=package['packet']['source_consumptions'],
        resolutions=[row['resolution']['reference'] for row in state['frames'] if row.get('resolution')],
        unresolved_issues=package['packet']['unresolved_issues'],rubric_gaps=package['packet']['rubric_gaps'])
    evidence_ref=_ref(directory+'/evidence.json',evidence)
    terminal=publisher._report(proof,terminal='TARGET_NOT_REACHED',reason=report['exit_reason'])
    terminal_ref=_ref(directory+'/terminal_report.json',terminal);failure_ref=_ref(path,report)
    packet=dict(schema_version='vnext-phase2-failure-closeout-v2',job_id=config['job_id'],
        current_verified_pointer=deepcopy(proof.latest),configuration=deepcopy(owner.binding.configuration_ref),
        entry=deepcopy(frame['bound'].request['entry']),declaration_binding=package['reference'],
        review_request=frame['bound'].request_ref,review_result=_ref(frame['owner'].directory+'/execution/result.json',frame['receipt']),
        review_consumption=_ref(frame['owner'].consumption_path,frame['consumption']),failure_report=failure_ref,
        terminal_report=terminal_ref,terminal_state='TARGET_NOT_REACHED',accepted=False,reviewer_final_status='not_run',
        declaration_status='rejected',blockers=[state['gate'],'current_lineage_verification_incomplete'],
        profiles=[dict(step_index=i,**row) for i,row in enumerate(profiles['profiles'],1)],clean_profiles=state['clean'],
        apply_back_permitted=False,halt_evidence=evidence_ref,unresolved_issues=evidence['unresolved_issues'])
    for data,schema in ((report,'convergence_failure_report'),(evidence,'vnext_phase2_halt_evidence_v1'),
                        (packet,'vnext_phase2_failure_closeout_v2')):proof.reader.suite.registry.validate(data,schema)
    reference=_ref(directory+'/commit.json',packet)
    assets=((path,canonical_json_bytes(report)),(terminal_ref['path'],canonical_json_bytes(terminal)),
            (evidence_ref['path'],canonical_json_bytes(evidence)))
    pending=[]
    for name,raw in assets+((reference['path'],canonical_json_bytes(packet)),):
        observed=publisher._optional(name)
        require(observed is None or observed==raw,'exhaustion evidence differs from exact replay',name)
        if observed is None:pending.append(name)
    committed=reference['path'] not in pending
    require(not committed or not pending,'committed exhaustion lacks dependencies')
    return dict(gate='closeout_committed' if committed else 'closeout_publication_required',packet=packet,reference=reference,
        assets=assets,committed=committed,phase_complete=False,halt_complete=False,pending_paths=tuple(pending),
        mirror_path='rounds/convergence_failure_report.json',owner=owner,frame=frame,general_halt=True)


def synchronize(publisher, store, proof, current):
    from whetstone.vnext_verified_phase2_sequence import sequence
    state=sequence(proof);frame=current['frame'];source=frame['owner']
    source._synchronize_request(store,source.proof,frame['bound'])
    frame['journal'].synchronize(store._token,frame['bound'].request,frame['outcomes'])
    package=_bundle(current['owner'],state['frames'],state['clean'])
    refs=[package['reference'],proof.latest,current['owner'].binding.configuration_ref,
          current['owner'].binding.configuration['rubric']['artifact']]
    refs += [package['packet'][key] for key in ('declaration','rubric_manifest','unresolved_issues','rubric_gaps')]
    refs += package['packet'].get('gap_acceptances',[])
    for item in state['frames']:
        refs.extend([item['bound'].request_ref,_ref(item['owner'].consumption_path,item['consumption']),
                     _ref(item['owner'].directory+'/execution/result.json',item['receipt']),item['receipt']['response']])
        if item.get('resolution'):refs.append(item['resolution']['reference'])
    for ref in refs:publisher.store.synchronize_existing(store._token,ref['path'],expected=proof.reader.raw(ref))
    require(view(publisher,proof,state)['packet']==current['packet'],'exhaustion sources changed during barriers')
