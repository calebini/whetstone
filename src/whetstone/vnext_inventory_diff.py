"""Mechanical inventory correspondence and observed changes, without approval.

The output distinguishes structural correspondence from semantic obligations.
It is not a preservation verdict, and cannot authorize registration/promotion.
"""
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass

from whetstone.hashing import normalize_draft
from whetstone.preservation_inventory import build_inventory, _unique_lcs
from whetstone.vnext_assertions import MutationMetrics
from whetstone.vnext_contracts import canonical_json_bytes, content_identifier, require, sha256_bytes
from whetstone.vnext_inventory import scan_units
from whetstone.vnext_proposals import _targets


@dataclass(frozen=True)
class InventoryDelta:
    base_unit_ids: tuple[str,...]
    candidate_unit_ordinals: tuple[int,...]
    operation_id: str | None
    change: str
    semantic_obligation: bool
    correspondence_group_id: str | None = None
    system_operation_id: str | None = None


@dataclass(frozen=True)
class InventoryDiff:
    candidate_scan: tuple[dict,...]
    deltas: tuple[InventoryDelta,...]
    metrics: MutationMetrics
    failures: tuple[str,...]
    baseline_diagnostics: tuple[dict,...]
    editor_metrics: MutationMetrics | None = None


def _facts(unit):
    return {key:value for key,value in unit.items() if key not in {'unit_id','anchor_line_unit_id','anchor_line_start'}}


def _candidate_origins(assembled,units):
    if assembled.editor_assembly is not None:
        from whetstone.vnext_version_inventory import intermediate_units
        return _candidate_origins(assembled.editor_assembly, intermediate_units(assembled, units))
    before=build_inventory(assembled.before_normalization,path='before.md')['units']
    after=build_inventory(assembled.raw,path='after.md')['units']
    require(len(after)<=len(before),'normalization invented source lines')
    for old,new in zip(before,after):
        a=assembled.before_normalization[old['byte_start']:old['byte_end']].decode()
        b=assembled.raw[new['byte_start']:new['byte_end']].decode()
        require(normalize_draft(a)==normalize_draft(b),'normalization line origin does not reproduce')
    starts=[u['byte_start'] for u in after]
    def position(offset):
        index=bisect_right(starts,offset)-1
        require(index>=0,'missing normalized source line')
        old=before[index];new=after[index]
        if offset==new['byte_end']:return old['byte_end']
        return old['byte_start']+offset-new['byte_start']
    result=[]
    for unit in units:
        start=position(unit['byte_start']);end=position(unit['byte_end'])
        pieces=[p for p in assembled.pieces if p.output_start<end and start<p.output_end]
        sources={p.operation_id for p in pieces}
        require(len(sources)==1,'an inventory unit spans mixed assembly sources')
        piece=pieces[0]
        result.append((piece.operation_id,piece.source_start+start-piece.output_start))
    return result


def _force(unit):
    words={s.removeprefix('rfc:') for s in unit['normative_sources'] if s.startswith('rfc:')}
    if words & {'MUST','SHALL','REQUIRED'}:return 3
    if words & {'SHOULD','RECOMMENDED'}:return 2
    if words & {'MAY','OPTIONAL'}:return 1
    return 0


def compare_inventory(*,base,base_map,base_inventory,proposal,assembled,candidate_map,rules=(),plan=None):
    """Compare exact source-bound inventories; ambiguous gaps remain explicit.

    Current-base lineage IDs must already be validated against committed
    history by the caller. This function recomputes all discovery facts and
    derives change counts instead of accepting any client-reported counts.
    """
    if assembled.editor_assembly is not None:
        from whetstone.vnext_version_inventory import compare
        return compare(base=base,base_map=base_map,base_inventory=base_inventory,proposal=proposal,
                       assembled=assembled,candidate_map=candidate_map,rules=rules,plan=plan)
    frontmatter=base_inventory['frontmatter_section_id']
    old_scan,old_diagnostics,rules_hash=scan_units(base,base_map,frontmatter_id=frontmatter,rules=rules)
    require(base_inventory['draft_hash']==sha256_bytes(base)
            and base_inventory['section_map_hash']==sha256_bytes(canonical_json_bytes(base_map))
            and base_inventory['rules_hash']==rules_hash,'base inventory bindings changed')
    old=base_inventory['units']
    require([_facts(u) for u in old]==[_facts(u) for u in old_scan],'base inventory facts do not reproduce')
    require(len({u['unit_id'] for u in old})==len(old),'duplicate base inventory identity')
    new,diagnostics,_=scan_units(assembled.raw,candidate_map,frontmatter_id=frontmatter,rules=rules)
    origins=_candidate_origins(assembled,new)
    if proposal.patch['schema_version']=='patch-set-v2':
        require(plan is not None and plan['schema_version'] in {'mutation-plan-v2','mutation-plan-v3','mutation-plan-v4'},
                'v2 comparison requires its inventory-bound plan')
        require(plan['base_inventory_hash']==sha256_bytes(canonical_json_bytes(base_inventory))
                and plan['base_section_identity_map_hash']==sha256_bytes(canonical_json_bytes(base_map))
                and proposal.patch['mutation_plan_hash']==sha256_bytes(canonical_json_bytes(plan)),
                'v2 correspondence inventory or plan binding changed')
    targets=_targets(base,base_map)
    operations={op['operation_id']:op for op in proposal.patch['operations']}
    require(proposal.patch['base_draft_hash']==sha256_bytes(base),'comparison proposal base changed')
    ranges={}
    for identifier,op in operations.items():
        _,span=targets[op['target_stable_section_id']]
        if op['operation_type']=='replace_section_body':ranges[identifier]=(span.heading_end,span.direct_end)
        elif op['operation_type'] in {'replace_section_subtree','delete_section_subtree'}:ranges[identifier]=(span.start,span.end)
    def producer(unit):
        hits=[identifier for identifier,(start,end) in ranges.items() if start<=unit['byte_start'] and unit['byte_end']<=end]
        require(len(hits)<=1,'base unit belongs to overlapping operations')
        return hits[0] if hits else None
    old_sources=[producer(u) for u in old]
    old_by_start={(u['kind'],u['byte_start']):i for i,u in enumerate(old)}
    matched_old=set();matched_new=set();pairs=[];failures=[];explicit=[];unresolved=[];pair_groups={}
    def pair(i,j,operation):
        require(i not in matched_old and j not in matched_new,'unit correspondence reuses an endpoint')
        matched_old.add(i);matched_new.add(j);pairs.append((i,j,operation))
    if proposal.patch['schema_version']=='patch-set-v2':
        from whetstone.vnext_unit_proposals import correspondence_endpoints
        old_ids={unit['unit_id']:i for i,unit in enumerate(old)}
        new_keys={(operation,start,new[j]['kind']):j for j,(operation,start) in enumerate(origins)}
        for operation,index,base_ids,selected in correspondence_endpoints(proposal,base,base_map,base_inventory,rules=rules):
            before=[old_ids[key] for key in base_ids];after=[]
            for ordinal,fact in selected:
                key=(operation,fact['byte_start'],fact['kind'])
                require(key in new_keys,'correspondence payload unit did not survive assembly')
                successor=new_keys[key]
                require(new[successor]['canonical_content_hash']==fact['canonical_content_hash'],
                        'correspondence successor changed during assembly')
                after.append(successor)
            group_id=content_identifier('corr','whetstone-unit-correspondence-v2',
                                         [proposal.patch['transaction_id'],operation,index+1])
            if len(before)==len(after)==1 and old[before[0]]['kind']==new[after[0]]['kind']:
                pair(before[0],after[0],operation);pair_groups[(before[0],after[0])]=group_id
            else:
                require(not (set(before)&matched_old or set(after)&matched_new),'explicit correspondence reuses an endpoint')
                matched_old.update(before);matched_new.update(after);explicit.append((before,after,operation,group_id))
    # Exact retained origins, including repeated identical base units, are
    # stronger evidence than global text matching or an LCS tie-breaker.
    for j,(operation,start) in enumerate(origins):
        if j in matched_new:continue
        if operation is not None:continue
        i=old_by_start.get((new[j]['kind'],start))
        if i is not None and old[i]['canonical_content_hash']==new[j]['canonical_content_hash']:
            pair(i,j,None)
    groups=defaultdict(lambda:[[],[]])
    for i,u in enumerate(old):
        if i not in matched_old:groups[(old_sources[i],u['owning_section_id'],u['kind'])][0].append(i)
    for j,u in enumerate(new):
        if j not in matched_new:groups[(origins[j][0],u['owning_section_id'],u['kind'])][1].append(j)
    for (operation,owner,kind),(left,right) in groups.items():
        if not left or not right:continue
        if operation is None:
            failures.append('unattributed_inventory_change');continue
        a=[(kind,old[i]['canonical_content_hash']) for i in left]
        b=[(kind,new[j]['canonical_content_hash']) for j in right]
        alignment=list(zip(range(len(left)),range(len(right)))) if a==b else _unique_lcs(a,b)
        if alignment is None:
            failures.append('ambiguous_unit_correspondence')
            matched_old.update(left);matched_new.update(right);unresolved.append((left,right,operation))
            continue
        for i,j in alignment:pair(left[i],right[j],operation)
        # One changed unit between two exact anchors has one structural
        # predecessor. Its meaning still requires independent verification.
        anchors=[(-1,-1),*alignment,(len(left),len(right))]
        for (a0,b0),(a1,b1) in zip(anchors,anchors[1:]):
            gap_old=left[a0+1:a1];gap_new=right[b0+1:b1]
            if len(gap_old)==len(gap_new)==1:pair(gap_old[0],gap_new[0],operation)
            elif gap_old and gap_new:
                failures.append('explicit_unit_correspondence_required')
                matched_old.update(gap_old);matched_new.update(gap_new);unresolved.append((gap_old,gap_new,operation))
    deltas=[];changed_sections=set();normative={}
    def context(mapping,identifier):
        by_id={s['stable_section_id']:s for s in mapping['sections']};path=[]
        while identifier in by_id:
            path.append(identifier);identifier=by_id[identifier]['parent_stable_section_id']
        return tuple(path)
    for i,j,operation in sorted(pairs):
        before=old[i];after=new[j]
        if before['canonical_content_hash']==after['canonical_content_hash']:
            change='unchanged' if context(base_map,before['owning_section_id'])==context(candidate_map,after['owning_section_id']) else 'moved'
        elif before['primary'] and _force(before) and _force(after) and _force(before)>_force(after):change='weakened'
        elif before['primary'] and _force(before) and _force(after) and _force(before)<_force(after):change='strengthened'
        else:change='renamed' if before['kind']=='heading' else 'modified'
        deltas.append(InventoryDelta((before['unit_id'],),(j+1,),operation,change,change!='unchanged',pair_groups.get((i,j))))
        if change!='unchanged':
            sections={before['owning_section_id'],after['owning_section_id']};changed_sections.update(sections)
            if before['primary'] and (before['normative'] or after['normative']):normative[before['unit_id']]=frozenset(sections)
    for before,after,operation,group_id in explicit:
        sections={old[i]['owning_section_id'] for i in before}|{new[j]['owning_section_id'] for j in after}
        old_force=[_force(old[i]) for i in before if old[i]['primary'] and _force(old[i])]
        new_force=[_force(new[j]) for j in after if new[j]['primary'] and _force(new[j])]
        change='weakened' if old_force and new_force and max(new_force)<min(old_force) else 'modified'
        deltas.append(InventoryDelta(tuple(old[i]['unit_id'] for i in before),tuple(j+1 for j in after),operation,change,True,group_id))
        changed_sections.update(sections)
        predecessors=[old[i] for i in before if old[i]['primary'] and old[i]['normative']]
        if predecessors:
            for unit in predecessors:normative[unit['unit_id']]=frozenset(sections)
        else:
            for j in after:
                if new[j]['primary'] and new[j]['normative']:normative['candidate-unit-'+str(j+1)]=frozenset(sections)
    # An unresolved mapping is not evidence of removal. Keep exact known
    # removals in other gaps visible, without asking for deletion permission
    # merely because a split/merge lacks correspondence.
    for before,after,operation in unresolved:
        sections={old[i]['owning_section_id'] for i in before}|{new[j]['owning_section_id'] for j in after}
        deltas.append(InventoryDelta(tuple(old[i]['unit_id'] for i in before),tuple(j+1 for j in after),operation,'ambiguous',True))
        changed_sections.update(sections)
        for i in before:
            if old[i]['primary'] and old[i]['normative']:normative[old[i]['unit_id']]=frozenset(sections)
    for i,unit in enumerate(old):
        if i in matched_old:continue
        deltas.append(InventoryDelta((unit['unit_id'],),(),old_sources[i],'removed',unit['protected']))
        if unit['protected']:
            changed_sections.add(unit['owning_section_id'])
            if unit['primary'] and unit['normative']:normative[unit['unit_id']]=frozenset({unit['owning_section_id']})
    for j,unit in enumerate(new):
        if j in matched_new:continue
        deltas.append(InventoryDelta((),(j+1,),origins[j][0],'added',unit['protected']))
        if unit['protected']:
            changed_sections.add(unit['owning_section_id'])
            if unit['primary'] and unit['normative']:normative['candidate-unit-'+str(j+1)]=frozenset({unit['owning_section_id']})
    for delta in deltas:
        if delta.change!='unchanged' and delta.operation_id is None:
            relevant=any(u['unit_id'] in delta.base_unit_ids and u['protected'] for u in old)
            relevant|=any(new[j-1]['protected'] for j in delta.candidate_unit_ordinals)
            if relevant:failures.append('unattributed_inventory_change')
    # A malformed seed may be the admitted defect being repaired. Retain its
    # incomplete discovery evidence for semantic review; candidate diagnostics
    # still prevent a complete current inventory. No semantic pass is inferred.
    failures.extend(d['code'] for d in diagnostics)
    return InventoryDiff(tuple(new),tuple(deltas),MutationMetrics(frozenset(changed_sections),normative),
                         tuple(sorted(set(failures))),tuple(old_diagnostics))
