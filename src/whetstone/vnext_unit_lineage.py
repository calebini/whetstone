"""Reproducible candidate unit identities; no semantic or storage authority.

The caller validates the base inventory's committed lineage first. Reproducing
one candidate is not a substitute for walking that chain back to the seed.
"""
from collections import Counter
from copy import deepcopy

from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_identity import inserted_unit_id
from whetstone.vnext_inventory import scan_units
from whetstone.vnext_inventory_diff import _candidate_origins, _facts, compare_inventory
from whetstone.vnext_section_lineage import candidate_section_map
from whetstone.vnext_unit_proposals import payload_units


def validate_inventory_facts(packet,raw,mapping,*,rules=()):
    """Check facts and local identity consistency, without certifying history."""
    VNextSchemaRegistry().validate(packet,'vnext_preservation_inventory_v2')
    require(packet['job_id']==mapping['job_id'] and packet['draft_hash']==sha256_bytes(raw)
            and packet['section_map_hash']==sha256_bytes(canonical_json_bytes(mapping)),
            'inventory input bindings changed')
    scanned,diagnostics,rules_hash=scan_units(raw,mapping,frontmatter_id=packet['frontmatter_section_id'],rules=rules)
    require(packet['rules_hash']==rules_hash and packet['diagnostics']==diagnostics
            and [_facts(u) for u in packet['units']]==[_facts(u) for u in scanned],
            'inventory facts or diagnostics do not reproduce')
    active=[u['unit_id'] for u in packet['units']];retired=packet['retired_unit_ids']
    require(len(set(active))==len(active),'duplicate active unit identity')
    require(retired==sorted(set(retired)) and not set(active)&set(retired),
            'retired unit identity reused or noncanonical')
    anchors={u['byte_start']:u['unit_id'] for u in packet['units'] if u['primary']}
    require(all(u['anchor_line_unit_id']==anchors[s['anchor_line_start']]
                for u,s in zip(packet['units'],scanned)), 'inventory anchor lineage changed')
    bindings=[packet[key] for key in ('base_inventory_hash','transaction_id','proposal_hash')]
    require(all(value is None for value in bindings) or all(value is not None for value in bindings),
            'partial inventory lineage binding')
    if bindings[0] is None:
        require(packet['draft_hash']==packet['seed_draft_hash'] and not retired,
                'seed inventory cannot claim candidate state')


def candidate_inventory(*,base,base_map,base_inventory,plan,proposal,rules=()):
    """Reassemble, compare and derive a prospective candidate's unit IDs.

    Same-kind one-to-one correspondence retains an ID. Split/merge/kind-change
    successors get new IDs and retire their predecessors. All such changes
    still need the independent preservation decision before promotion.
    """
    require(plan.get('schema_version') in {'mutation-plan-v2','mutation-plan-v3','mutation-plan-v4'}
            and proposal.patch.get('schema_version')=='patch-set-v2',
            'candidate unit lineage requires inventory-bound v2 inputs')
    validate_inventory_facts(base_inventory,base,base_map,rules=rules)
    assembled=assemble_bytes(base=base,section_map=base_map,plan=plan,proposal=proposal)
    mapping=candidate_section_map(base=base,base_map=base_map,proposal=proposal,assembled=assembled)
    diff=compare_inventory(base=base,base_map=base_map,base_inventory=base_inventory,plan=plan,
                           proposal=proposal,assembled=assembled,candidate_map=mapping,rules=rules)
    require(not diff.failures,'candidate inventory comparison failed: '+', '.join(diff.failures))
    old={u['unit_id']:u for u in base_inventory['units']}
    units=deepcopy(list(diff.candidate_scan))
    require(Counter(key for d in diff.deltas for key in d.base_unit_ids)==Counter(old.keys())
            and Counter(j for d in diff.deltas for j in d.candidate_unit_ordinals)==Counter(range(1,len(units)+1)),
            'candidate correspondence does not partition both inventories')
    transferred={};retained=set()
    for delta in diff.deltas:
        if len(delta.base_unit_ids)==len(delta.candidate_unit_ordinals)==1:
            key=delta.base_unit_ids[0];ordinal=delta.candidate_unit_ordinals[0]
            if old[key]['kind']==units[ordinal-1]['kind']:
                transferred[ordinal]=key;retained.add(key)
    origins=_candidate_origins(assembled,units)
    payload_facts={}
    for op in proposal.patch['operations']:
        if op['payload']['path'] is None:continue
        facts=payload_units(proposal.payloads[op['payload']['path']],job_id=plan['job_id'],
                            parser_version=base_map['parser_contract_version'],rules=rules)
        payload_facts[op['operation_id']]={(u['byte_start'],u['kind']):(i+1,u) for i,u in enumerate(facts)}
        require(len(payload_facts[op['operation_id']])==len(facts),'payload unit origin is ambiguous')
    prior=set(old)|set(base_inventory['retired_unit_ids']);minted=set()
    for ordinal,unit in enumerate(units,1):
        if ordinal in transferred:
            unit['unit_id']=transferred[ordinal];continue
        operation,start=origins[ordinal-1]
        require(operation in payload_facts,'new candidate unit has no creating operation')
        selector=payload_facts[operation].get((start,unit['kind']))
        require(selector is not None and selector[1]['canonical_content_hash']==unit['canonical_content_hash'],
                'new candidate unit does not reproduce from its payload')
        identifier=inserted_unit_id(plan['transaction_id'],operation,unit['kind'],selector[0])
        require(identifier not in prior and identifier not in minted,'inserted unit identity collision or reuse')
        unit['unit_id']=identifier;minted.add(identifier)
    anchors={u['byte_start']:u['unit_id'] for u in units if u['primary']}
    for unit in units:unit['anchor_line_unit_id']=anchors[unit.pop('anchor_line_start')]
    result={**deepcopy(base_inventory),'draft_hash':sha256_bytes(assembled.raw),
            'section_map_hash':sha256_bytes(canonical_json_bytes(mapping)),
            'base_inventory_hash':sha256_bytes(canonical_json_bytes(base_inventory)),
            'transaction_id':plan['transaction_id'],'proposal_hash':sha256_bytes(canonical_json_bytes(proposal.patch)),
            'retired_unit_ids':sorted(set(base_inventory['retired_unit_ids'])|(set(old)-retained)),
            'units':units,'diagnostics':[]}
    validate_inventory_facts(result,assembled.raw,mapping,rules=rules)
    return result


def validate_candidate_inventory(packet,**inputs):
    """Exact readback replay, including lineage, tombstones and anchor IDs."""
    VNextSchemaRegistry().validate(packet,'vnext_preservation_inventory_v2')
    require(packet==candidate_inventory(**inputs),'candidate inventory does not reproduce from its exact inputs')
