"""Reproducible section lineage for the unactivated v2 candidate assembler."""
from collections import defaultdict
from copy import deepcopy

from whetstone.hashing import normalize_draft
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, content_identifier, require, sha256_bytes
from whetstone.vnext_identity import inserted_section_id
from whetstone.vnext_proposals import _targets
from whetstone.vnext_sections import section_spans


IDENTITY_VERSION='vnext-section-lineage-v2'


def inserted_heading_id(transaction,operation,payload_ordinal):
    require(type(payload_ordinal) is int and payload_ordinal>0,'invalid payload heading ordinal')
    if payload_ordinal==1:return inserted_section_id(transaction,operation)
    return content_identifier('sec','whetstone-inserted-section-descendant-id-v2',
                              [transaction,operation,payload_ordinal])


def validate_lineage_map(mapping,raw):
    registry=VNextSchemaRegistry()
    schema={'section-identity-map-v1':'section_identity_map_v1',
            'section-identity-map-v2':'section_identity_map_v2'}.get(mapping.get('schema_version'))
    require(schema is not None,'unsupported section lineage schema')
    registry.validate(mapping,schema)
    targets=_targets(raw,mapping)
    sections=mapping['sections'];seen={};retired=False
    require([s['preorder_ordinal'] for s in sections]==list(range(1,len(sections)+1)),
            'section lineage rows must have contiguous ordinals')
    for item in sections:
        if item['status']=='retired':retired=True
        else:require(not retired,'active section follows a retired tombstone')
        parent=item['parent_stable_section_id']
        require(parent is None or parent in seen,'section parent is not an earlier row')
        if parent is not None and item['status']=='active':
            require(seen[parent]['heading_level']<item['heading_level'],'section parent level is invalid')
            require(seen[parent]['status']=='active','active section has a retired parent')
        seen[item['stable_section_id']]=item
    return targets


def _normalized(raw):return normalize_draft(raw.decode('utf-8')).encode('utf-8')


def _shape(raw,*,without_root_title=False):
    spans=section_spans(raw)
    if not spans:return []
    return [[None if without_root_title and i==0 else span.heading,span.level-spans[0].level,
             sha256_bytes(_normalized(raw[span.heading_end:span.direct_end]))] for i,span in enumerate(spans)]


def _preserved_payload_sections(base,old_spans,payload,new_spans):
    """Return unambiguous payload-index -> base-index transfers within a subtree.

    An unchanged ordered child stream is direct byte evidence, even with
    repeated headings. Otherwise sibling names or exact content must identify
    one predecessor. Duplicate unresolved evidence fails instead of guessing.
    """
    old_children=defaultdict(list);new_children=defaultdict(list)
    for index,span in enumerate(old_spans):old_children[span.parent].append(index)
    for index,span in enumerate(new_spans):new_children[span.parent].append(index)
    mapping={0:0};used={0};pending=[(0,0)]
    def bind(old,new):
        require(old not in used and new not in mapping,'section transfer reuses a predecessor')
        mapping[new]=old;used.add(old);pending.append((old,new))
    def grouped(indices,spans,source,mode):
        result=defaultdict(list)
        for i in indices:
            span=spans[i]
            if mode=='name':key=span.heading
            else:key=sha256_bytes(canonical_json_bytes(_shape(source[span.start:span.end],without_root_title=mode=='body')))
            result[key].append(i)
        return result
    def match_unique(left,right,mode):
        old_keys=grouped(left,old_spans,base,mode);new_keys=grouped(right,new_spans,payload,mode)
        for key in sorted(old_keys.keys() & new_keys.keys()):
            if len(old_keys[key])==len(new_keys[key])==1:bind(old_keys[key][0],new_keys[key][0])
    while pending:
        old_parent,new_parent=pending.pop(0)
        left=[i for i in old_children[old_parent] if i not in used]
        right=[i for i in new_children[new_parent] if i not in mapping]
        if not left or not right:continue
        old_stream=b''.join(base[old_spans[i].start:old_spans[i].end] for i in left)
        new_stream=b''.join(payload[new_spans[i].start:new_spans[i].end] for i in right)
        if len(left)==len(right) and _shape(old_stream)==_shape(new_stream):
            for old,new in zip(left,right):bind(old,new)
            continue
        # Exact subtree evidence disambiguates reordered distinct same-name
        # siblings before a unique name can support a rewritten body.
        for mode in ('subtree','name','body'):
            match_unique([i for i in left if i not in used],[i for i in right if i not in mapping],mode)
        old_names=grouped([i for i in left if i not in used],old_spans,base,'name')
        new_names=grouped([i for i in right if i not in mapping],new_spans,payload,'name')
        require(not (old_names.keys() & new_names.keys()),'ambiguous descendant section identity')
    # Moving an exact subtree across parents is also an unambiguous transfer
    # when only one unmatched predecessor and successor share its full bytes.
    left=[i for i in range(1,len(old_spans)) if i not in used]
    right=[i for i in range(1,len(new_spans)) if i not in mapping]
    old_keys=grouped(left,old_spans,base,'subtree');new_keys=grouped(right,new_spans,payload,'subtree')
    pairs=sorted((old_keys[key][0],new_keys[key][0]) for key in old_keys.keys() & new_keys.keys()
                 if len(old_keys[key])==len(new_keys[key])==1)
    old_starts={span.start:i for i,span in enumerate(old_spans)}
    new_starts={span.start:i for i,span in enumerate(new_spans)}
    for old,new in pairs:
        if old in used or new in mapping:continue
        before=old_spans[old];after=new_spans[new]
        old_raw=base[before.start:before.end];new_raw=payload[after.start:after.end]
        old_local=section_spans(old_raw);new_local=section_spans(new_raw)
        nested=_preserved_payload_sections(old_raw,old_local,new_raw,new_local)
        for successor,predecessor in nested.items():
            bind(old_starts[before.start+old_local[predecessor].start],
                 new_starts[after.start+new_local[successor].start])
    remaining_old=grouped([i for i in left if i not in used],old_spans,base,'subtree')
    remaining_new=grouped([i for i in right if i not in mapping],new_spans,payload,'subtree')
    require(not (remaining_old.keys() & remaining_new.keys()),'ambiguous moved section identity')
    return mapping


def candidate_section_map(*,base,base_map,proposal,assembled):
    """Derive active identities and retained tombstones; no artifact writes.

    Assembly is reproduced by the caller before registration. This helper also
    checks its exact heading-origin coverage and source bindings. A map alone
    is not authorization to remove, weaken or supersede a preservation unit.
    """
    targets=validate_lineage_map(base_map,base)
    require(proposal.patch['job_id']==base_map['job_id'],'section lineage belongs to another job')
    require(proposal.patch['base_draft_hash']==sha256_bytes(base),'section lineage base changed')
    spans=section_spans(assembled.raw)
    require(len(spans)==len(assembled.heading_origins),'candidate heading origins do not cover bytes')
    by_id={s['stable_section_id']:s for s in base_map['sections']}
    operations={op['operation_id']:op for op in proposal.patch['operations']}
    payload_spans={};transfers={}
    for identifier,op in operations.items():
        if op['payload']['path'] is None:continue
        payload=proposal.payloads[op['payload']['path']]
        require(sha256_bytes(payload)==op['payload']['hash'],'lineage payload changed')
        parsed=section_spans(payload);payload_spans[identifier]=parsed
        if op['operation_type']=='replace_section_subtree' and op['preserve_target_identity']:
            _,target=targets[op['target_stable_section_id']]
            subtree=base[target.start:target.end];old=section_spans(subtree)
            matched=_preserved_payload_sections(subtree,old,payload,parsed)
            base_starts={span.start:key for key,(_,span) in targets.items()}
            transfers[identifier]={parsed[new].start:base_starts[target.start+old[prior].start]
                                   for new,prior in matched.items()}
    rows=[];claimed=set()
    for index,(span,origin) in enumerate(zip(spans,assembled.heading_origins)):
        previous=None;created=origin.operation_id
        if origin.operation_id is None:
            require(origin.base_section_id in targets,'retained origin is not an active base section')
            require(targets[origin.base_section_id][1].start==origin.source_start,'retained heading source span changed')
            identifier=origin.base_section_id;previous=identifier;created=by_id[identifier]['created_by_operation_id']
        else:
            require(origin.operation_id in payload_spans,'unknown heading source operation')
            payload=payload_spans[origin.operation_id]
            ordinals={h.start:i+1 for i,h in enumerate(payload)}
            require(origin.source_start in ordinals,'heading source is not in its payload')
            identifier=transfers.get(origin.operation_id,{}).get(origin.source_start)
            if identifier is not None:
                previous=identifier;created=by_id[identifier]['created_by_operation_id']
            else:
                identifier=inserted_heading_id(proposal.patch['transaction_id'],origin.operation_id,ordinals[origin.source_start])
                require(identifier not in by_id,'inserted identity reuses a historical section')
                op=operations[origin.operation_id]
                if op['operation_type']=='replace_section_subtree' and origin.source_start==0:
                    previous=op['target_stable_section_id']
        require(identifier not in claimed,'candidate section identity collision');claimed.add(identifier)
        rows.append({'stable_section_id':identifier,'canonical_section_id':span.canonical_id,
            'parent_stable_section_id':rows[span.parent]['stable_section_id'] if span.parent is not None else None,
            'heading_level':span.level,'heading_text':span.heading,'preorder_ordinal':index+1,
            'section_hash':sha256_bytes(assembled.raw[span.start:span.end]),
            'direct_body_hash':sha256_bytes(assembled.raw[span.heading_end:span.direct_end]),
            'status':'active','created_by_operation_id':created,'previous_stable_section_id':previous})
    for old in base_map['sections']:
        if old['stable_section_id'] in claimed:continue
        retired=deepcopy(old);retired.update(status='retired',preorder_ordinal=len(rows)+1)
        rows.append(retired)
    result={'schema_version':'section-identity-map-v2','identity_algorithm_version':IDENTITY_VERSION,
            'job_id':base_map['job_id'],'draft_hash':sha256_bytes(assembled.raw),
            'parser_contract_version':base_map['parser_contract_version'],'sections':rows}
    validate_lineage_map(result,assembled.raw)
    return result
