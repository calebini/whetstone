"""Unactivated v2 plan/proposal components with exact unit correspondence."""
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_identity import transaction_id
from whetstone.vnext_inventory import scan_units
from whetstone.vnext_plans import build_plan
from whetstone.vnext_proposals import _prepare_patch, _targets
from whetstone.vnext_sections import seed_section_map
from whetstone.vnext_validation import validate_plan


def build_unit_plan(*,inventory,**arguments):
    """Bind inventory/map lineage before deriving a v2 transaction identity."""
    require(inventory['job_id']==arguments['job']['job_id']
            and inventory['draft_hash']==arguments['section_map']['draft_hash']
            and inventory['section_map_hash']==sha256_bytes(canonical_json_bytes(arguments['section_map'])),
            'unit plan inventory bindings changed')
    plan,provenance,responses=build_plan(**arguments,unit_inventory=inventory)
    plan.update(schema_version='mutation-plan-v2',base_inventory_hash=sha256_bytes(canonical_json_bytes(inventory)),
                base_section_identity_map_hash=sha256_bytes(canonical_json_bytes(arguments['section_map'])))
    plan['transaction_id']=transaction_id(plan,{r['response_id']:h for r,h in responses})
    VNextSchemaRegistry().validate(plan,'mutation_plan_v2')
    validate_plan(plan,arguments['job'],arguments['authority'],arguments['section_map'],responses)
    return plan,provenance,responses


def payload_units(raw,*,job_id,parser_version,rules=()):
    """Inventory selectors in raw payload order; temporary owners never publish.

    Selectors use full inventory ordinal, kind and exact content hash. Temporary
    section owners only let the same lexical scanner operate on a fragment.
    """
    mapping=seed_section_map(raw,{'job_id':job_id,'parser_contract_version':parser_version},'bind_'+'0'*64)
    units,diagnostics,_=scan_units(raw,mapping,frontmatter_id='sec_'+'0'*64,rules=rules)
    require(not diagnostics,'payload inventory is incomplete')
    return units


def correspondence_endpoints(proposal,base,section_map,inventory,*,rules=()):
    """Validate groups and return exact raw-payload facts for each endpoint."""
    targets=_targets(base,section_map);units={u['unit_id']:u for u in inventory['units']}
    require(len(units)==len(inventory['units']),'duplicate correspondence base unit')
    used_base=set();used_payload=set();result=[]
    for op in proposal.patch['operations']:
        groups=op.get('unit_correspondence',[])
        if not groups:continue
        require(op['operation_type'] in {'replace_section_body','replace_section_subtree'},
                'unit correspondence requires a replacement operation')
        _,target=targets[op['target_stable_section_id']]
        start,end=(target.heading_end,target.direct_end) if op['operation_type']=='replace_section_body' else (target.start,target.end)
        raw=proposal.payloads[op['payload']['path']]
        require(sha256_bytes(raw)==op['payload']['hash'],'correspondence payload changed')
        facts=payload_units(raw,job_id=proposal.patch['job_id'],parser_version=section_map['parser_contract_version'],rules=rules)
        for index,group in enumerate(groups):
            for key in group['base_unit_ids']:
                require(key in units and key not in used_base,'unknown or reused correspondence predecessor')
                unit=units[key]
                require(start<=unit['byte_start'] and unit['byte_end']<=end,'correspondence predecessor lies outside its operation')
                used_base.add(key)
            selected=[]
            for selector in group['payload_units']:
                ordinal=selector['ordinal'];key=(op['operation_id'],ordinal)
                require(key not in used_payload and 1<=ordinal<=len(facts),'unknown or reused correspondence successor')
                fact=facts[ordinal-1]
                require(fact['kind']==selector['kind'] and fact['content_hash']==selector['content_hash'],
                        'payload selector differs from exact inventory fact')
                used_payload.add(key);selected.append((ordinal,fact))
            result.append((op['operation_id'],index,tuple(group['base_unit_ids']),tuple(selected)))
    return result


def prepare_unit_patch(raw_response,*,payload_root,plan,base,section_map,inventory,editor,responses=(),rules=()):
    """Prepare an isolated v2 proposal; no public mode or registered suite is implied."""
    registry=VNextSchemaRegistry();registry.validate(inventory,'vnext_preservation_inventory_v2')
    plan_schema={'mutation-plan-v2':'mutation_plan_v2','mutation-plan-v3':'mutation_plan_v3','mutation-plan-v4':'mutation_plan_v4'}.get(plan['schema_version'])
    require(plan_schema is not None,'unit proposal requires an inventory-bound plan')
    require(plan['base_inventory_hash']==sha256_bytes(canonical_json_bytes(inventory))
            and plan['base_section_identity_map_hash']==sha256_bytes(canonical_json_bytes(section_map)),
            'unit proposal inventory or map binding changed')
    require(inventory['job_id']==plan['job_id'] and inventory['draft_hash']==sha256_bytes(base),
            'unit proposal inventory has a stale base')
    scanned,_,rules_hash=scan_units(base,section_map,frontmatter_id=inventory['frontmatter_section_id'],rules=rules)
    def facts(u):return {k:v for k,v in u.items() if k not in {'unit_id','anchor_line_unit_id','anchor_line_start'}}
    require(inventory['rules_hash']==rules_hash and [facts(u) for u in inventory['units']]==[facts(u) for u in scanned],
            'unit proposal inventory facts or rules changed')
    map_schema={'section-identity-map-v1':'section_identity_map_v1','section-identity-map-v2':'section_identity_map_v2'}.get(section_map['schema_version'])
    require(map_schema is not None,'unsupported unit proposal section map')
    proposal=_prepare_patch(raw_response,payload_root=payload_root,plan=plan,base=base,section_map=section_map,
        editor=editor,registry=registry,responses=responses,units={u['unit_id']:u for u in inventory['units']},
        client_schema='patch_set_client_v2',patch_schema='patch_set_v2',plan_schema=plan_schema,map_schema=map_schema)
    correspondence_endpoints(proposal,base,section_map,inventory,rules=rules)
    return proposal
