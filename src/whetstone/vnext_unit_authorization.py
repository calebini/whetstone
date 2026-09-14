"""Named-unit operator grants, bound through a versioned exact request hash."""
from copy import deepcopy
from dataclasses import dataclass

from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, content_identifier, require, sha256_bytes
from whetstone.vnext_decisions import bind_selected_response, decision_request, derived_task


@dataclass(frozen=True)
class UnitDecisionBinding:
    request: dict
    response: dict
    response_hash: str
    derived_finding_id: str | None

    def units_for(self,effect):
        option=next(o for o in self.request['options'] if o['option_id']==self.response['selected_option_id'])
        return frozenset(u['unit_id'] for u in option['authorized_unit_effects'] if effect in u['effects'])


def unit_decision_request(*,job,base_hash,finding,targets,options,feedback_refs,inventory,section_map):
    """Construct exact choices; the caller must first validate current inventory lineage.

    Unit discovery and approval are different steps. This function creates a
    request and cannot select an option or infer permission from model output.
    """
    VNextSchemaRegistry().validate(inventory,'vnext_preservation_inventory_v2')
    require(inventory['job_id']==job['job_id'] and inventory['draft_hash']==base_hash,
            'decision inventory belongs to another job or base')
    require(inventory['section_map_hash']==sha256_bytes(canonical_json_bytes(section_map)),
            'decision inventory map binding differs')
    active={s['stable_section_id']:s for s in section_map['sections'] if s['status']=='active'}
    require(set(targets)<=active.keys(),'unit decision has an unknown target')
    allowed=set(targets)
    for key in active:
        parent=active[key]['parent_stable_section_id'];seen=set()
        while parent is not None:
            require(parent in active and parent not in seen,'unit decision map has an invalid parent chain')
            if parent in allowed:allowed.add(key);break
            seen.add(parent);parent=active[parent]['parent_stable_section_id']
    available={u['unit_id']:u for u in inventory['units']}
    require(len(available)==len(inventory['units']),'decision inventory contains duplicate units')
    normalized=deepcopy(options)
    for option in normalized:
        grants=option.get('authorized_unit_effects')
        require(isinstance(grants,list),'unit decision option requires explicit unit effects')
        seen=set()
        for grant in grants:
            require(set(grant)=={'unit_id','effects'},'invalid unit effect grant')
            key=grant['unit_id']
            require(key in available and key not in seen,'unknown or duplicate authorized unit');seen.add(key)
            require(available[key]['owning_section_id'] in allowed,'authorized unit lies outside the decision targets')
            require(set(grant['effects'])<={'remove','weaken'} and bool(grant['effects']), 'invalid named-unit effect')
            require(set(grant['effects'])<=set(option['authorized_effects']),'unit effect exceeds the selected option effects')
            grant['effects']=sorted(grant['effects'])
        grants.sort(key=lambda g:g['unit_id'])
        removed=sorted(g['unit_id'] for g in grants if 'remove' in g['effects'])
        require(sorted(option['authorized_deletion_unit_ids'])==removed,'deletion list differs from named removal grants')
        option['authorized_deletion_unit_ids']=removed
        option['authorized_effects']=sorted(option['authorized_effects'])
        for effect in {'remove','weaken'} & set(option['authorized_effects']):
            require(any(effect in g['effects'] for g in grants),'sensitive effect requires named units')
    projected=[{key:value for key,value in o.items() if key!='authorized_unit_effects'} for o in normalized]
    packet=decision_request(job=job,base_hash=base_hash,finding=finding,targets=targets,
                            options=projected,feedback_refs=feedback_refs)
    packet.pop('decision_id')
    packet.update(schema_version='vnext-mutation-decision-request-v2',
                  base_inventory_hash=sha256_bytes(canonical_json_bytes(inventory)),
                  options=sorted(normalized,key=lambda o:o['option_id']))
    packet['decision_id']=content_identifier('decision','whetstone-mutation-decision-v2',[packet])
    VNextSchemaRegistry().validate(packet,'vnext_mutation_decision_request_v2')
    return packet


def bind_unit_response(response,request,*,job,base_hash,finding,targets,feedback_refs,inventory,section_map,suite):
    VNextSchemaRegistry().validate(request,'vnext_mutation_decision_request_v2')
    expected=unit_decision_request(job=job,base_hash=base_hash,finding=finding,targets=targets,
        options=request['options'],feedback_refs=feedback_refs,inventory=inventory,section_map=section_map)
    require(request==expected,'unit decision request identity, inventory or provenance changed')
    response,digest=bind_selected_response(response,request,job=job,base_hash=base_hash,
        request_hash=sha256_bytes(canonical_json_bytes(request)),suite=suite)
    task=derived_task(finding,response,request) if response['authorized_effects'] else None
    return UnitDecisionBinding(deepcopy(request),response,digest,task['finding_id'] if task else None)


def unit_effect_failures(*,diff,base_inventory,proposal,plan,bindings):
    """Check actual removed/weakened units against addressed, hash-bound grants.

    Bindings must come from freshly validated operator-owned artifacts. The
    checks here detect mutations to those values and prohibit borrowing a grant
    for unrelated work. This result alone is not a preservation verdict.
    """
    require(proposal.patch['transaction_id']==plan['transaction_id'],'unit authorization transaction differs')
    inventory_hash=sha256_bytes(canonical_json_bytes(base_inventory))
    by_response={};dispositions={f['finding_id']:f for f in plan['finding_dispositions']}
    for binding in bindings:
        request=binding.request;response=binding.response
        require(sha256_bytes(canonical_json_bytes(response))==binding.response_hash,'bound unit response changed')
        require(sha256_bytes(canonical_json_bytes(request))==response['decision_request_hash'],'bound unit request changed')
        require(request['base_inventory_hash']==inventory_hash
                and request['job_id']==plan['job_id'] and request['base_draft_hash']==plan['base_draft_hash']
                and request['authority_map_hash']==plan['authority_map_hash']
                and request['scope_contract_hash']==plan['scope_contract_hash']
                and request['protected_invariants_hash']==plan['protected_invariants_hash'],
                'unit authorization has stale transaction inputs')
        original={'finding_id':request['finding_id'],'source_feedback_ids':request['source_feedback_ids']}
        expected_task=derived_task(original,response,request)['finding_id'] if response['authorized_effects'] else None
        require(binding.derived_finding_id==expected_task,'bound derived task differs from its operator evidence')
        if expected_task is None:continue  # A deferral grants no units and enters no transaction identity.
        key=response['response_id'];require(key not in by_response,'duplicate bound unit response')
        by_response[key]=binding
    from whetstone.vnext_identity import transaction_id
    used={f['decision_response_id'] for f in plan['finding_dispositions'] if f['decision_response_id'] is not None}
    require(used==by_response.keys(),'unit authorization lacks complete decision bindings')
    require(transaction_id(plan,{key:b.response_hash for key,b in by_response.items()})==plan['transaction_id'],
            'unit authorization response hashes differ from the plan')
    units={u['unit_id']:u for u in base_inventory['units']}
    operations={o['operation_id']:o for o in proposal.patch['operations']};failures=[]
    for delta in diff.deltas:
        effect={'removed':'remove','weakened':'weaken'}.get(delta.change)
        if effect is None:continue
        required={key for key in delta.base_unit_ids if units[key]['protected']
                  and (effect=='remove' or (units[key]['primary'] and units[key]['normative']))}
        if not required:continue
        op=operations.get(delta.operation_id);granted=set()
        if op is not None:
            for finding_id in op['addressed_finding_ids']:
                finding=dispositions.get(finding_id)
                if not finding or not finding['admitted_to_editing']:continue
                binding=by_response.get(finding['decision_response_id'])
                if binding is not None and binding.derived_finding_id==finding_id:
                    granted.update(binding.units_for(effect))
        if effect=='remove':granted.intersection_update(plan['authorized_deletion_unit_ids'])
        if not required<=granted:
            failures.append({'code':'unauthorized_'+effect,'operation_id':delta.operation_id,
                             'unit_ids':sorted(required-granted)})
    return failures
