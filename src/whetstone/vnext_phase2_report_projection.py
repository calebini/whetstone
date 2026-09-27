"""Shared ownership and ordering for opt-in Phase 2 failure report mirrors."""
from whetstone.vnext_contracts import canonical_json_bytes, require

MIRRORS = {'error':'rounds/artifact_validation_error.json', 'failure':'rounds/convergence_failure_report.json'}


def projections(owner, proof, *, reviewer=None, correction=None):
    from whetstone.vnext_verified_phase2_failure import _Failure, supported as reviewer_supported
    from whetstone.vnext_verified_phase2_correction_failure import _CorrectionFailure, supported as correction_supported
    records=[]; sources=[]; state=None; correction_reader=None; correction_proof=None
    if reviewer_supported(proof):
        reader=_Failure(owner.run)
        view=reviewer if reviewer is not None else reader._failure_view(proof)
        state=view['state']
        for r in view['records']:
            if r['committed']:
                records.append(((r['frame']['owner'].ordinal,0,len(r['outcomes'])),r))
    if correction_supported(proof):
        reader=owner if isinstance(owner,_CorrectionFailure) else _CorrectionFailure(owner.run)
        checked=proof if reader is owner else reader._proof(reader.store.read)
        if reader is not owner: checked.inspect_registry()
        view=correction if correction is not None else reader._view_failures(checked)
        state=view['state']
        correction_reader,correction_proof=reader,checked
        for r in view['records']:
            if r['committed']:records.append((r['order'],r))
    records.sort(key=lambda pair:pair[0]); plan={}
    dependencies=[]
    for _,r in records:
        dependencies.extend(r['assets'].items())
        dependencies.append((r['reference']['path'],canonical_json_bytes(r['packet'])))
        for key,path in MIRRORS.items():
            ref=r['packet'][key]
            if ref is None:continue
            raw=r['assets'][ref['path']]
            allowed=plan[path]['allowed'] if path in plan else []
            plan[path]=dict(ref=ref,raw=raw,allowed=allowed+[raw],dependencies=dependencies,sources=sources)
    if state and state['gate']=='declaration_closeout_required':
        closeout=(correction_reader._closeout(correction_proof) if correction_reader is not None else owner._closeout(proof))
        if closeout.get('committed') and 'failure_report' in closeout['packet']:
            ref=closeout['packet']['failure_report'];raw=closeout['assets'][0][1]
            path=MIRRORS['failure'];allowed=plan[path]['allowed'] if path in plan else []
            dependencies.extend(closeout['assets'])
            dependencies.append((closeout['reference']['path'],canonical_json_bytes(closeout['packet'])))
            plan[path]=dict(ref=ref,raw=raw,allowed=allowed+[raw],dependencies=dependencies,sources=sources)
    if correction_reader is not None:
        sources.append((correction_reader,correction_reader._sources()))
    return plan


def recover_projections(owner, store, proof, **views):
    plan=projections(owner,proof,**views)
    for path,target in plan.items():
        for reader,snapshot in target['sources']:reader._barrier(store._token,snapshot)
        for p,raw in target['dependencies']:
            owner.store.synchronize_existing(store._token,p,expected=raw)
        old=owner._optional(path);desired=target['raw']
        require(old is None or old in target['allowed'],'unowned Phase 2 failure report conflicts',path)
        def check():
            proof.guard(owner.store.read);owner.run._guard(owner.store.read)
            # These values were fully reproduced inside this invocation/fence.
            # Recheck their exact inputs and committed outputs, not a cached status.
            for reader,snapshot in target['sources']:reader.store.check(snapshot)
            for dependency,raw in target['dependencies']:
                require(owner.store.read(dependency)==raw,'Phase 2 report dependency changed',dependency)
        check()
        if old==desired:owner.store.synchronize_existing(store._token,path,expected=desired)
        elif old is None:store.publish(store._token,path,desired)
        else:
            def validate(before,after):
                require(before==old and after==desired,'Phase 2 report projection changed')
                check()
            owner.store.replace_pointer(store._token,path,expected=old,snapshot=target['ref'],validate_transition=validate)
