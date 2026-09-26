"""Opt-in final-step exhaustion using the existing closeout publication owner."""
from copy import deepcopy

from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_verified_phase2_binding import _ref

ALGORITHM='algorithms/vnext_verified_phase2_termination_v1.md'
SCHEMA='vnext_phase2_failure_closeout_v1'
MIRROR='rounds/convergence_failure_report.json'


def supported(proof):
    return any(r['path']==ALGORITHM for r in proof.reader.suite.manifest['algorithms'])


def pins(proof):
    from whetstone.vnext_verified_phase2_findings import _pins
    _pins(proof)
    entries={r['path']:r['sha256'] for family in ('algorithms','schemas') for r in proof.reader.suite.manifest[family]}
    for path in (ALGORITHM,'schemas/'+SCHEMA+'.schema.json','schemas/convergence_failure_report.schema.json'):
        require(path in entries and entries[path]==sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'Phase 2 termination is outside supported suite or changed',path)


def exhausted_closeout(owner,proof,state,package,findings,rows,blockers):
    require(findings is not None,'final-step termination requires finding reconciliation support')
    blockers=list(dict.fromkeys(blockers+findings['packet']['blocking_reasons']))
    blocked=dict(gate='declaration_reconciliation_required',blockers=blockers,committed=False,phase_complete=False)
    # Undefined maintenance/intervention must never be silently reduced to exhaustion.
    withheld={'authority_resolution_required','rubric_resolution_required','oscillation_resolution_required'}
    if not findings['committed'] or withheld.intersection(findings['packet']['blocking_reasons']):
        return blocked
    frame=state['frames'][-1];step=frame['bound'].request['step'];pass_owner=frame['owner']
    profiles=state['scheduler'].status()
    profile=profiles['profiles'][step['index']-1]
    if step['index']!=len(pass_owner.binding.configuration['profiles']) or profile['rounds_used']<profile['round_budget']:
        return blocked
    require(profile['rounds_used']==profile['round_budget'],'final profile exceeds its configured budget')
    directory='rounds/phase2/closeouts/closeout-'+frame['receipt']['request']['hash']
    path=directory+'/convergence_failure_report.json'
    existing=owner._optional(path)
    generated_at=getattr(owner,'_publication_time',None)
    if existing is not None:
        retained=decode_json(existing)
        proof.reader.suite.registry.validate(retained,'convergence_failure_report')
        generated_at=retained['generated_at']
    if generated_at is None:
        require(owner._optional(directory+'/commit.json') is None,'committed Phase 2 failure lacks report')
        return dict(blocked,gate='failure_report_publication_required',
                    proposed_terminal_state='TARGET_NOT_REACHED',remaining_step_budget=0,halt_complete=False)
    config=pass_owner.binding.configuration
    raw=proof.values(proof.latest)['base'];current_hash=draft_hash(raw.decode())
    latest={f['bound'].request['step']['profile']:f for f in state['frames']
            if f.get('consumed') and f['bound'].request['base_pointer']==proof.latest}
    clean=sorted(name for name,f in latest.items() if not any(
        r['in_scope'] and r['normalized_severity'] in {'major','blocker'} for r in f['review']['feedback']['feedback']))
    profiles['unverified_profiles']=sorted({r['name'] for r in config['profiles']}-set(clean))
    last_rows=frame['review']['feedback']['feedback']
    def issues(severity):
        return [{key:deepcopy(row[key]) for key in
                 ('issue_id','issue_fingerprint','normalized_severity','affected_sections','claim')}
                for row in rows if row['normalized_severity']==severity]
    report=dict(terminal_state='TARGET_NOT_REACHED',generated_at=generated_at,
        round_number=frame['bound'].request['round_number'],draft_hash=current_hash,
        final_draft_path=proof.pointers[-1]['verified_draft_path'],
        final_declaration_path=package['packet']['declaration']['path'],
        target_phase=config['target_phase'],target_mode=config['target_mode'],workflow=config['workflow'],
        rubric_profile=config['rubric']['profile'],rubric_source=config['rubric']['source'],rubric_label=None,
        rubric_manifest_path=package['packet']['rubric_manifest']['path'],
        unresolved_blockers=issues('blocker'),unresolved_major_issues=issues('major'),unresolved_rubric_gaps=[],
        reviewer_final_status='rejected',
        last_accepted_draft_hash=draft_hash(proof.reader.raw(pass_owner.entry.entry['current_verified_draft']).decode()),
        last_draft_hash=current_hash,exit_reason='vnext_phase2_final_step_budget_exhausted',
        recommendation='manual_review_required',profile_status=profiles,
        last_reviewer_findings=dict(round_number=frame['bound'].request['round_number'],profile=step['profile'],
            blocker_count=sum(r['in_scope'] and r['normalized_severity']=='blocker' for r in last_rows),
            major_count=sum(r['in_scope'] and r['normalized_severity']=='major' for r in last_rows),
            feedback_ids=[r['feedback_id'] for r in last_rows
                          if r['in_scope'] and r['normalized_severity'] in {'major','blocker'}]))
    proof.reader.suite.registry.validate(report,'convergence_failure_report')
    failure_ref=_ref(path,report)
    terminal=owner._report(proof,terminal='TARGET_NOT_REACHED',reason=report['exit_reason'])
    terminal_ref=_ref(directory+'/terminal_report.json',terminal)
    packet=dict(schema_version='vnext-phase2-failure-closeout-v1',job_id=config['job_id'],
        current_verified_pointer=deepcopy(proof.latest),configuration=deepcopy(pass_owner.binding.configuration_ref),
        entry=deepcopy(frame['bound'].request['entry']),declaration_binding=package['reference'],
        review_request=frame['bound'].request_ref,review_result=_ref(pass_owner.directory+'/execution/result.json',frame['receipt']),
        review_consumption=_ref(pass_owner.consumption_path,frame['consumption']),failure_report=failure_ref,
        terminal_report=terminal_ref,terminal_state='TARGET_NOT_REACHED',accepted=False,
        reviewer_final_status='rejected',declaration_status='rejected',blockers=blockers,
        profiles=[dict(step_index=i,**r) for i,r in enumerate(profiles['profiles'],1)],clean_profiles=clean,
        apply_back_permitted=False,finding_reconciliation=findings['reference'],
        unresolved_issues=findings['packet']['unresolved_issues'])
    proof.reader.suite.registry.validate(packet,SCHEMA)
    ref=_ref(directory+'/commit.json',packet)
    assets=((path,canonical_json_bytes(report)),(terminal_ref['path'],canonical_json_bytes(terminal)))
    pending=[]
    for name,value in assets+((ref['path'],canonical_json_bytes(packet)),):
        observed=owner._optional(name)
        require(observed is None or observed==value,'Phase 2 failure differs from exact evidence replay',name)
        if observed is None:pending.append(name)
    committed=ref['path'] not in pending
    require(not committed or not pending,'committed Phase 2 failure lacks dependencies')
    pass_owner.store.check(dict(pass_owner.store.reads))
    proof.guard(owner.store.read);owner.run._guard(owner.store.read)
    return dict(gate='closeout_committed' if committed else 'closeout_publication_required',packet=packet,reference=ref,
        assets=assets,committed=committed,phase_complete=False,halt_complete=False,pending_paths=tuple(pending),
        mirror_path=MIRROR,owner=pass_owner,frame=frame)
