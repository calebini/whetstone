"""Pure exact-byte assembly kernel for the future candidate runtime.

This is not admission, preservation validation or candidate registration. The
caller supplies an admitted plan/proposal. Runtime suite publication, stable
identity transfer, complete inventory comparison and D8 remain separate gates.
"""
from dataclasses import dataclass

from whetstone.hashing import normalize_draft
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_identity import topological
from whetstone.vnext_proposals import INSERT_OPERATIONS, _PayloadReader, _payload_shape, _targets
from whetstone.vnext_sections import section_spans
from whetstone.vnext_validation import validate_patch


ASSEMBLER_VERSION = 'patch-assembler-v2'
NORMALIZATION_VERSION = 'whetstone-markdown-normalization-v1'


@dataclass(frozen=True)
class SourcePiece:
    """Exact source span and its position before final Markdown normalization."""
    operation_id: str | None  # None means immutable base bytes.
    source_start: int
    source_end: int
    output_start: int
    output_end: int


@dataclass(frozen=True)
class HeadingOrigin:
    operation_id: str | None
    source_start: int
    base_section_id: str | None


@dataclass(frozen=True)
class AssembledBytes:
    raw: bytes
    before_normalization: bytes
    pieces: tuple[SourcePiece, ...]
    heading_origins: tuple[HeadingOrigin, ...]
    assembler_version: str = ASSEMBLER_VERSION
    normalization_version: str = NORMALIZATION_VERSION


def assemble_bytes(*, base, section_map, plan, proposal):
    """Recheck canonical proposal bytes and assemble without writes or models.

    Origin records support subsequent identity/inventory validation; they do
    not themselves authorize an identity transfer or prove semantic retention.
    The result deliberately has no candidate ID, registration or disposition.
    """
    registry=VNextSchemaRegistry()
    versions={'mutation-plan-v1':'mutation_plan_v1','mutation-plan-v2':'mutation_plan_v2','mutation-plan-v3':'mutation_plan_v3',
              'section-identity-map-v1':'section_identity_map_v1','section-identity-map-v2':'section_identity_map_v2',
              'patch-set-v1':'patch_set_v1','patch-set-v2':'patch_set_v2'}
    for packet in (plan,section_map,proposal.patch):
        schema=versions.get(packet.get('schema_version'))
        require(schema is not None,'unsupported assembly input version')
        registry.validate(packet,schema)
    if plan['schema_version'] in {'mutation-plan-v2','mutation-plan-v3'}:
        require(plan['base_section_identity_map_hash']==sha256_bytes(canonical_json_bytes(section_map)),
                'assembly plan section map binding changed')
    require(section_map['job_id']==plan['job_id'],'assembly map belongs to another job')
    require(sha256_bytes(base)==plan['base_draft_hash'],'assembly base changed')
    base.decode('utf-8')
    targets=_targets(base,section_map)
    patch=proposal.patch
    operations=validate_patch(patch,plan,{key:item for key,(item,_) in targets.items()},
        _PayloadReader('proposals/'+patch['proposal_id'],proposal.payloads),
        proposal_directory='proposals/'+patch['proposal_id'])
    required_payloads={op['payload']['path'] for op in operations if op['payload']['path'] is not None}
    require(set(proposal.payloads)==required_payloads,'assembly payload set differs from proposal')
    operations=topological(operations,'operation_id','depends_on_operation_ids')
    inserts={};replacements={};intervals=[];last_anchor={};sources={None:base}
    source_headings={None:{span.start:key for key,(_,span) in targets.items()}}
    for rank,op in enumerate(operations):
        identifier=op['operation_id'];kind=op['operation_type'];target=op['target_stable_section_id']
        _,span=targets[target]
        if kind in {'replace_section_subtree','delete_section_subtree'}:
            require(span.parent is not None,'assembly cannot replace or delete a document root')
        raw=b'' if kind=='delete_section_subtree' else proposal.payloads[op['payload']['path']]
        if kind!='delete_section_subtree':
            _payload_shape(raw,op,span)
            sources[identifier]=raw
            source_headings[identifier]={h.start:None for h in section_spans(raw)}
        if kind=='replace_section_body':start,end=span.heading_end,span.direct_end
        elif kind in {'replace_section_subtree','delete_section_subtree'}:start,end=span.start,span.end
        else:
            start=span.start if kind=='insert_section_before' else span.end
            end=start
        for old_start,old_end,old in intervals:
            require(not ((start<old_end and old_start<end)
                        or (start==end and old_start<start<old_end)
                        or (old_start==old_end and start<old_start<end)),
                    'assembly contains overlapping base mutations')
            require(target!=old['target_stable_section_id']
                    or (kind in INSERT_OPERATIONS and old['operation_type'] in INSERT_OPERATIONS),
                    'assembly contains duplicate mutation targets')
        intervals.append((start,end,op))
        if kind in INSERT_OPERATIONS:
            require(start not in last_anchor or last_anchor[start] in op['depends_on_operation_ids'],
                    'assembly insertion anchor lacks explicit ordering')
            last_anchor[start]=identifier
            inserts.setdefault(start,[]).append((rank,identifier,raw))
        else:
            require(start not in replacements,'assembly contains duplicate replacement positions')
            replacements[start]=(end,identifier,raw)
    # Sweep immutable base coordinates. Operations at a shared insertion point
    # retain canonical dependency order, without reversing after-anchor inserts.
    output=[];pieces=[];output_size=0
    def append(source,start,end):
        nonlocal output_size
        raw=sources[source][start:end]
        if not raw:return
        output.append(raw);pieces.append(SourcePiece(source,start,end,output_size,output_size+len(raw)))
        output_size+=len(raw)
    cursor=0
    for position in sorted(set(inserts)|set(replacements)):
        require(position>=cursor,'assembly mutation points cross a replaced interval')
        append(None,cursor,position);cursor=position
        for _,identifier,raw in inserts.get(position,[]):append(identifier,0,len(raw))
        if position in replacements:
            end,identifier,raw=replacements[position]
            if raw:append(identifier,0,len(raw))
            cursor=end
    append(None,cursor,len(base))
    assembled=b''.join(output)
    expected={}
    for piece in pieces:
        for source_start,section_id in source_headings[piece.operation_id].items():
            if piece.source_start<=source_start<piece.source_end:
                location=piece.output_start+source_start-piece.source_start
                expected[location]=HeadingOrigin(piece.operation_id,source_start,section_id)
    headings=section_spans(assembled)
    require({h.start for h in headings}==expected.keys(),
            'assembly changed heading boundaries through joining or fence context')
    origins=tuple(expected[h.start] for h in headings)
    # Payload shape is local. Verify that combined insertion order still places
    # each new subtree under its declared base parent, rather than a new sibling.
    by_operation={op['operation_id']:op for op in operations}
    for index,origin in enumerate(origins):
        if origin.operation_id is None:
            item,_=targets[origin.base_section_id]
            actual_parent=origins[headings[index].parent].base_section_id if headings[index].parent is not None else None
            require(actual_parent==item['parent_stable_section_id'],
                    'assembly reparented a retained base section')
            continue
        if origin.source_start!=0:continue
        op=by_operation[origin.operation_id];kind=op['operation_type']
        if kind=='replace_section_body':continue
        item,_=targets[op['target_stable_section_id']]
        expected_parent=item['stable_section_id'] if kind=='append_child_section' else item['parent_stable_section_id']
        actual_parent=origins[headings[index].parent].base_section_id if headings[index].parent is not None else None
        require(actual_parent==expected_parent,'combined operations change the declared payload parent')
    normalized=normalize_draft(assembled.decode('utf-8')).encode('utf-8')
    final_headings=section_spans(normalized)
    require([(h.heading,h.level,h.parent) for h in final_headings]==[(h.heading,h.level,h.parent) for h in headings],
            'normalization changed the assembled section hierarchy')
    return AssembledBytes(normalized,assembled,tuple(pieces),origins)
