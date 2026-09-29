"""Preserve complete Editor attribution while adding exact system effects."""
from dataclasses import replace

from whetstone.vnext_assertions import MutationMetrics
from whetstone.vnext_contracts import require
from whetstone.vnext_inventory import scan_units
from whetstone.vnext_inventory_diff import compare_inventory
from whetstone.vnext_section_lineage import candidate_section_map


def intermediate_units(assembled, units):
    """Map final unit offsets back through exact, single-line metadata edits."""
    from copy import deepcopy
    # Normalized line numbers remain fixed; metadata edits contain no newlines.
    before = assembled.editor_assembly.raw.splitlines(keepends=True)
    after = assembled.raw.splitlines(keepends=True)
    require(len(before)==len(after), 'metadata changed physical line count')
    old_starts=[];new_starts=[];old=0;new=0
    for a,b in zip(before,after):
        old_starts.append(old);new_starts.append(new);old+=len(a);new+=len(b)
    from bisect import bisect_right
    result=deepcopy(list(units))
    for row in result:
        index=bisect_right(new_starts,row['byte_start'])-1
        require(index>=0, 'metadata unit has no source line')
        # Only inserted units need origin lookup. A system edit cannot create
        # an anchor absent from the base, so changed lines have base lineage.
        if before[index] != after[index]:
            row['byte_start']=old_starts[index]
            row['byte_end']=old_starts[index]+len(before[index])
        else:
            shift=old_starts[index]-new_starts[index]
            row['byte_start']+=shift;row['byte_end']+=shift
    return result


def compare(*,base,base_map,base_inventory,proposal,assembled,candidate_map,rules,plan):
    editor=assembled.editor_assembly
    mapping=candidate_section_map(base=base,base_map=base_map,proposal=proposal,assembled=editor)
    diff=compare_inventory(base=base,base_map=base_map,base_inventory=base_inventory,proposal=proposal,
                           assembled=editor,candidate_map=mapping,rules=rules,plan=plan)
    final,diagnostics,_=scan_units(assembled.raw,candidate_map,
        frontmatter_id=base_inventory['frontmatter_section_id'],rules=rules)
    require(len(final)==len(diff.candidate_scan), 'metadata changed inventory topology')
    changed=set()
    for ordinal,(old,new) in enumerate(zip(diff.candidate_scan,final),1):
        for field in ('kind','primary','owning_section_id','normative','protected'):
            require(old[field]==new[field], 'metadata changed protected inventory classification')
        if old['content_hash']!=new['content_hash']: changed.add(ordinal)
    operation=assembled.version_operation['operation_id']
    sections=set(diff.metrics.changed_section_ids);normative=dict(diff.metrics.normative_unit_sections)
    deltas=[]
    for delta in diff.deltas:
        touched=set(delta.candidate_unit_ordinals)&changed
        if touched:
            # No metadata operation creates/deletes a unit or grants weakening.
            require(len(delta.base_unit_ids)==len(delta.candidate_unit_ordinals)==1,
                    'metadata requires unambiguous existing unit lineage')
            unit=final[next(iter(touched))-1]
            kind='renamed' if unit['kind']=='heading' else 'modified'
            delta=replace(delta,change=kind if delta.change=='unchanged' else delta.change,
                          semantic_obligation=True,system_operation_id=operation)
            sections.add(unit['owning_section_id'])
            if unit['primary'] and unit['normative']:
                normative[delta.base_unit_ids[0]]=frozenset({unit['owning_section_id']})
        deltas.append(delta)
    return replace(diff,candidate_scan=tuple(final),deltas=tuple(deltas),editor_metrics=diff.metrics,
                   metrics=MutationMetrics(frozenset(sections),normative),
                   failures=tuple(sorted(set(diff.failures)|{d['code'] for d in diagnostics})))
