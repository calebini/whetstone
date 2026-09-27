"""Pinned target policy; immutable configuration and declaration authority."""
from whetstone.declaration import DECLARATION_ARTIFACTS
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_verified_phase2_targets_v1.md'


def supported(suite):
    return any(row['path']==ALGORITHM for row in suite.manifest['algorithms'])


def pins(suite):
    from whetstone.vnext_phase2_rubric import pins as rubric_pins
    rubric_pins(suite)
    entries={row['path']:row['sha256'] for family in ('algorithms','schemas') for row in suite.manifest[family]}
    for path in (ALGORITHM, *('schemas/'+name+'.schema.json' for name in
            ('vnext_phase2_configuration_v2','vnext_phase2_declaration_v2',
             'vnext_phase2_review_request_v6','vnext_phase2_consumption_v6','vnext_phase2_failure_closeout_v2'))):
        require(path in entries and entries[path]==sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'Phase 2 target contract is absent or changed',path)
    path='schemas/vnext_phase2_halt_evidence_v1.schema.json'
    require(path in entries and entries[path]==sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
            'Phase 2 halt evidence schema is absent or changed')


def configuration_schema(suite):
    from whetstone.vnext_phase2_routes import supported as routes_supported, pins as route_pins
    if routes_supported(suite):
        route_pins(suite)
        return 'vnext_phase2_configuration_v3'
    if supported(suite):
        pins(suite)
        return 'vnext_phase2_configuration_v2'
    return 'vnext_phase2_configuration_v1'


def read_configuration(reader, reference):
    return reader.json(reference,configuration_schema(reader.suite))


def allowed_major(row, config):
    return (config['target_phase'],config['target_mode'])==('mid','permissive') \
        and row['normalized_severity']=='major' and row['in_scope'] and bool(row['affected_sections']) \
        and not set(row['affected_sections']) & (DECLARATION_ARTIFACTS|{'target-matrix-precedence'}) \
        and all(row[key] is None for key in ('authority_impact','determinism_impact','invariant_violated'))


def serious(row, config):
    return row['in_scope'] and row['normalized_severity'] in {'major','blocker'} and not allowed_major(row,config)


def required_profiles(config):
    return {row['name'] for row in config['profiles']} if (config['target_phase'],config['target_mode'])==('final','strict') else set()


def counts_allowed(counts, config):
    return counts['blockers']==0 and (counts['major_issues']==0 or
        (config['target_phase'],config['target_mode'])==('mid','permissive')) and counts['rubric_gaps']==0


def matrix(config):
    return dict(target_phase=config['target_phase'],target_mode=config['target_mode'],blockers_allowed=False,
        major_issues_allowed=(config['target_phase'],config['target_mode'])==('mid','permissive'),
        unresolved_rubric_gaps_allowed=False,declaration_required=True)


def defer_allowed(findings, feedback, config, sections):
    if config['schema_version'] not in {'vnext-phase2-configuration-v2','vnext-phase2-configuration-v3'}:return findings
    rows={row['issue_id']:row for row in feedback['feedback']}
    for finding in findings:
        row=rows[finding['finding_id']]
        if not row['in_scope'] or (allowed_major(row,config) and set(row['affected_sections'])<=set(sections)):
            finding['classification']='deferable'
    return findings


def current_declaration(frames, reference):
    return next((frame for frame in reversed(frames) if frame.get('consumed')
        and frame['bound'].request['schema_version']=='vnext-phase2-review-request-v6'
        and frame['bound'].request['base_pointer']==reference),None)


def cycle_gate(frames, reference, clean, scheduler):
    """Consider completion only against an actually reviewed current package."""
    from whetstone.vnext_verified_phase2_closeout import _bundle, _latest_issues
    from whetstone.vnext_phase2_rubric import retained
    anchor=current_declaration(frames,reference)
    if anchor is None:return None
    signal=frames[-1].get('signals')
    if signal and (signal['terminal_state'] or 'freeze_prior_decision' in signal['recommendations']):return None
    owner=anchor['owner'];config=owner.binding.configuration
    rows=_latest_issues(frames,reference)
    if any(serious(row,config) for row in rows):return None
    if any(row['blocking_convergence'] for row in retained(frames,reference)):return None
    if any(row['in_scope'] and any(row[key] is not None for key in
           ('authority_impact','determinism_impact','invariant_violated')) for row in rows):return None
    package=_bundle(owner,owner.source_frames,owner.source_clean)
    counts=dict(blockers=sum(row['in_scope'] and row['normalized_severity']=='blocker' for row in rows),
                major_issues=sum(row['in_scope'] and row['normalized_severity']=='major' for row in rows),rubric_gaps=0)
    from whetstone.vnext_phase2_gap_acceptance import supported as acceptance_supported, references
    acceptance_changed = acceptance_supported(owner.proof.reader.suite) and package['packet']['gap_acceptances'] != references(frames,reference)
    if counts!=package['packet']['counts'] or acceptance_changed:
        # Count repair is concrete maintenance; it does not waive unchanged disagreement.
        return 'review' if scheduler.index<len(scheduler.steps) else 'declaration_closeout_required'
    if required_profiles(config)<=set(clean):
        if frames[-1]['owner'] is not owner:frames[-1]['owner'].declaration_source=owner
        return 'declaration_closeout_required'
    return None


def initial_owner(run, proof, binding, entry, number):
    from whetstone.scheduler import PhaseScheduler, ProfileStep
    from whetstone.vnext_verified_phase2_sequence import _Evidence, _Pass
    from whetstone.vnext_verified_phase2_closeout import declaration_owner
    scheduler=PhaseScheduler(ProfileStep(row['name'],round_budget=row['budget'],repeat_if_blockers=True)
                             for row in binding.configuration['profiles'])
    step=dict(index=1,profile=scheduler.steps[0].profile,round_budget=scheduler.steps[0].effective_round_budget,
              rounds_used=0,pass_number=1)
    evidence=_Evidence(run.store)
    owner=_Pass(run,evidence,proof,binding,entry,ordinal=1,number=number,step=step,previous=None,
                scheduler=scheduler,snapshot={})
    return declaration_owner(owner,[],set())
