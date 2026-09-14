"""Orchestrator construction of section-sliced, immutable mutation plans.

The runtime classifier and current-pointer admission gate must supply validated
finding records. This offline builder validates their decision provenance and
constraints; it does not infer permission from a free-form Reviewer suggestion.
"""
from copy import deepcopy

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_decisions import bind_response, derived_task
from whetstone.vnext_validation import validate_plan

CLASSIFICATIONS = {'editor_fixable','operator_decision_required','authority_conflict','scope_change','deferable'}


def build_plan(*, job, authority, section_map, findings, constraints, suite, decisions=(), unit_inventory=None):
    """Build a deterministic plan, preserving original non-editable dispositions.

    findings contain the canonical finding ID, source feedback IDs, original
    classification and exact stable targets. decisions contain original finding
    ID plus exact request/response artifacts and validated feedback references.
    Constraint values are required; this helper supplies no implicit expansion.
    """
    expected_constraints = {'allowed_operation_types','max_operations','max_changed_sections',
                            'max_changed_normative_units','required_context_binding_ids'}
    require(set(constraints) == expected_constraints, 'unknown or missing mutation constraints')
    for name in ('max_operations','max_changed_sections','max_changed_normative_units'):
        require(type(constraints[name]) is int and constraints[name] >= 0, 'mutation budget must be a nonnegative integer')
    require(section_map['job_id'] == job['job_id'], 'section map belongs to another job')
    require(sha256_bytes(canonical_json_bytes(authority)) == job['authority_map_hash'], 'authority map changed')
    suite.registry.validate(authority, 'authority_map_v1')
    if unit_inventory is not None and section_map.get('schema_version')=='section-identity-map-v2':
        # Isolated inventory-bound prototype; the frozen v1 entry point still
        # refuses candidate maps from an unsupported consuming suite.
        from whetstone.vnext_contracts import VNextSchemaRegistry
        VNextSchemaRegistry().validate(section_map,'section_identity_map_v2')
    else:
        suite.registry.validate(section_map, 'section_identity_map_v1')
    sections = {s['stable_section_id'] for s in section_map['sections'] if s['status'] == 'active'}
    records = {}
    for finding in findings:
        require(set(finding) == {'finding_id','source_feedback_ids','classification','target_section_ids'},
                'unknown or missing finding admission field')
        key = finding['finding_id']
        require(key not in records, 'duplicate canonical finding identity')
        require(finding['classification'] in CLASSIFICATIONS, 'unknown finding classification')
        require(bool(finding['source_feedback_ids']) and len(set(finding['source_feedback_ids'])) == len(finding['source_feedback_ids']),
                'finding requires unique source feedback IDs')
        require(bool(finding['target_section_ids']) and set(finding['target_section_ids']) <= sections,
                'finding targets an unknown or retired section')
        require(len(set(finding['target_section_ids'])) == len(finding['target_section_ids']), 'duplicate finding target')
        records[key] = deepcopy(finding)
    responses = []
    provenance = []
    answered = set()
    for decision in decisions:
        require(set(decision) == {'finding_id','request','response','feedback_refs'}, 'invalid decision bundle')
        key = decision['finding_id']
        require(key in records and key not in answered, 'unknown or duplicate finding decision')
        answered.add(key)
        finding = records[key]
        if decision['request'].get('schema_version')=='vnext-mutation-decision-request-v2':
            from whetstone.vnext_unit_authorization import bind_unit_response
            require(unit_inventory is not None,'named-unit decisions require the validated base inventory')
            binding=bind_unit_response(decision['response'],decision['request'],job=job,
                base_hash=section_map['draft_hash'],finding=finding,targets=finding['target_section_ids'],
                feedback_refs=decision['feedback_refs'],inventory=unit_inventory,section_map=section_map,suite=suite)
            response,digest=binding.response,binding.response_hash
        else:
            response, digest = bind_response(decision['response'], decision['request'], job=job,
                base_hash=section_map['draft_hash'], finding=finding, targets=finding['target_section_ids'],
                feedback_refs=decision['feedback_refs'], suite=suite)
        if not response['authorized_effects']:
            # A deferral remains visible and unresolved, but admits no task and
            # cannot masquerade as an exact authorization response in this plan.
            continue
        task = derived_task(finding, response, decision['request'])
        require(task['finding_id'] not in records, 'derived finding identity collision')
        records[task['finding_id']] = {k: task[k] for k in ('finding_id','source_feedback_ids','classification','target_section_ids')}
        responses.append((response, digest))
        provenance.append(task)
    blocking = {key for key,f in records.items() if f['classification'] in {
        'operator_decision_required','authority_conflict','scope_change'} and key not in answered}
    require(not blocking, 'unresolved operator decisions block Editor admission')
    # An explicitly deferred blocking choice still cannot authorize editing of
    # unrelated findings; it requires a new scoped transaction to exclude it.
    require(all(decision['response']['authorized_effects'] or records[decision['finding_id']]['classification']=='deferable'
                for decision in decisions), 'deferred blocking choice requires a new scoped admission')
    by_task = {task['finding_id']:task for task in provenance}
    dispositions = []
    admitted = []
    for key,record in sorted(records.items()):
        editable = record['classification'] == 'editor_fixable'
        dispositions.append({'finding_id':key,'source_feedback_ids':sorted(record['source_feedback_ids']),
                             'classification':record['classification'],'admitted_to_editing':editable,
                             'decision_response_id':by_task[key]['decision_response_id'] if key in by_task else None})
        if editable:admitted.append(record)
    require(bool(admitted), 'no admitted editing work; do not fabricate a transaction')
    # Merge records sharing any section into a single slice. This permits one
    # operation to address several findings without creating conflicting slices.
    groups=[]
    for finding in admitted:
        targets=set(finding['target_section_ids']);keys={finding['finding_id']}
        keep=[]
        for prior_targets,prior_keys in groups:
            if targets & prior_targets:
                targets |= prior_targets;keys |= prior_keys
            else:keep.append((prior_targets,prior_keys))
        # A newly merged group may connect an earlier previously disjoint group.
        changed=True
        while changed:
            changed=False;remaining=[]
            for prior_targets,prior_keys in keep:
                if targets & prior_targets:
                    targets |= prior_targets;keys |= prior_keys;changed=True
                else:remaining.append((prior_targets,prior_keys))
            keep=remaining
        groups=keep+[(targets,keys)]
    slices=[]
    for targets,keys in groups:
        item={'target_section_ids':sorted(targets),'dependency_slice_ids':[], 'admitted_finding_ids':sorted(keys)}
        item['slice_id']=ids.slice_id(item);slices.append(item)
    slices.sort(key=lambda item:item['slice_id'])
    allowed=sorted({target for item in slices for target in item['target_section_ids']})
    require(len(allowed) <= constraints['max_changed_sections'], 'admitted surface exceeds section budget')
    plan={'schema_version':'mutation-plan-v1','job_id':job['job_id'],'transaction_id':'',
          'base_draft_hash':section_map['draft_hash'],'authority_map_hash':job['authority_map_hash'],
          'scope_contract_hash':job['scope_contract_hash'],'protected_invariants_hash':job['protected_invariants_hash'],
          'finding_dispositions':dispositions,'allowed_section_ids':allowed,
          'authorized_deletion_unit_ids':sorted({u for response,_ in responses for u in response['authorized_deletion_unit_ids']}),
          'slices':slices,**deepcopy(constraints)}
    plan['allowed_operation_types']=sorted(plan['allowed_operation_types'])
    plan['required_context_binding_ids']=sorted(plan['required_context_binding_ids'])
    plan['transaction_id']=ids.transaction_id(plan,{response['response_id']:digest for response,digest in responses})
    suite.registry.validate(plan,'mutation_plan_v1')
    validate_plan(plan,job,authority,section_map,responses)
    return plan, provenance, responses
