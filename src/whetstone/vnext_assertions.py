"""Deterministic assertion compilation/evaluation; no semantic certification."""
from dataclasses import dataclass
import json
import re

from whetstone.vnext_contracts import require, sha256_bytes
from whetstone.vnext_identity import assertion_id
from whetstone.vnext_discovery import discovery_rules
from whetstone.vnext_inventory import scan_units
from whetstone.vnext_section_lineage import validate_lineage_map


IDENTIFIER_KINDS={'identifier','schema_field','schema_required_member'}|{
    'configured_'+kind for kind in ('identifier','command','flag','field','state','role',
                                   'error_code','terminal_state','artifact','concept')}
QUERY_KINDS=IDENTIFIER_KINDS|{'schema_enum_member','enumerated_member','table_cell','table_row',
                             'precondition','postcondition','acceptance_criterion','cross_reference'}
COUNTS={'max_changed_sections','max_changed_normative_units'}


@dataclass(frozen=True)
class MutationMetrics:
    """Orchestrator-computed distinct changes, never client-reported counts.

    A moved normative unit names both source and destination sections but is
    counted once. Added normative units use their new IDs. Facets do not add a
    second normative count for the primary statement that contains them.
    """
    changed_section_ids: frozenset[str]
    normative_unit_sections: dict[str, frozenset[str]]


def _scope(selector,seed_targets,candidate_targets,seed_size,candidate_size):
    if selector=='document':
        return (0,seed_size),(0,candidate_size),set(seed_targets)|set(candidate_targets)
    anchor=selector.removeprefix('section:')
    matches=[(key,span) for key,(item,span) in seed_targets.items() if item['canonical_section_id']==anchor]
    require(len(matches)==1,'assertion scope is not an exact seed section')
    identifier,old=matches[0]
    require(identifier in candidate_targets,'assertion scope was removed or lost its identity')
    _,new=candidate_targets[identifier]
    sections={key for key,(_,span) in seed_targets.items() if old.start<=span.start<old.end}
    sections.update(key for key,(_,span) in candidate_targets.items() if new.start<=span.start<new.end)
    return (old.start,old.end),(new.start,new.end),sections


def _maximum(matcher):
    kind=matcher['kind'];value=matcher['value']
    if kind=='exact':
        require(isinstance(value,str) and re.fullmatch(r'0|[1-9][0-9]*',value) is not None,
                'count ceiling requires a canonical nonnegative decimal')
        return int(value)
    require(kind=='inventory_query' and isinstance(value,dict) and set(value)=={'maximum'},
            'count ceiling query requires exactly maximum')
    require(type(value['maximum']) is int and value['maximum']>=0,'count ceiling must be a nonnegative integer')
    return value['maximum']


def _compile(assertion):
    kind=assertion['assertion_type'];matcher=assertion['matcher'];mode=matcher['kind'];value=matcher['value']
    if assertion['enforcement']=='semantic':
        require(mode=='semantic','semantic enforcement requires a semantic matcher')
        return
    require(mode!='semantic','deterministic enforcement cannot certify a semantic matcher')
    require(kind not in {'concept_required','concept_forbidden'},
            'concept assertions require semantic enforcement; use lexical identifier assertions for terminology')
    if kind in COUNTS:_maximum(matcher);return
    if kind=='canonical_model_count':
        require(mode=='inventory_query' and isinstance(value,dict) and set(value)=={'kind','value','count'},
                'structural model count requires an exact inventory query')
        require(value['kind'] in QUERY_KINDS and isinstance(value['value'],str) and value['value'],
                'model count requires a supported lexical fact and exact value')
        require(type(value['count']) is int and value['count']>=0,'model count must be a nonnegative integer')
        return
    if mode=='inventory_query':
        if kind=='table_row_present':
            require(isinstance(value,dict) and set(value)=={'cells'} and isinstance(value['cells'],list)
                    and value['cells'] and all(isinstance(cell,str) for cell in value['cells']),
                    'table query requires an ordered cells array')
        else:
            require(kind in {'identifier_present','identifier_absent','enum_member_present'}
                    and isinstance(value,dict) and set(value)=={'kind','value'}
                    and value['kind'] in QUERY_KINDS and isinstance(value['value'],str) and value['value'],
                    'unsupported inventory assertion query')
        return
    require(mode in {'exact','canonical_id','regex'} and isinstance(value,str) and value,
            'assertion requires a supported nonempty string matcher')
    if kind=='section_unchanged':
        require(mode in {'exact','canonical_id'},'frozen section requires an exact hash or seed anchor')
        if mode=='exact':require(re.fullmatch(r'[0-9a-f]{64}',value) is not None,'frozen section requires an exact hash')
    elif mode=='regex':
        try:re.compile(value)
        except re.error as exc:raise ValueError('invalid assertion regex') from exc


def validate_assertion_program(invariants,seed,seed_map):
    """Compile supported deterministic semantics before an Editor invocation."""
    discovery_rules(invariants)
    require(invariants['base_draft_hash']==sha256_bytes(seed),'invariant seed hash changed')
    targets=validate_lineage_map(seed_map,seed);seen=set()
    for assertion in invariants['assertions']:
        require(assertion['assertion_id']==assertion_id(sha256_bytes(seed),assertion),'assertion identity mismatch')
        require(assertion['assertion_id'] not in seen,'duplicate assertion identity');seen.add(assertion['assertion_id'])
        _compile(assertion)
        old,_,_=_scope(assertion['target_scope'],targets,targets,len(seed),len(seed))
        if assertion['assertion_type']=='section_unchanged' and assertion['enforcement']=='deterministic':
            matcher=assertion['matcher']
            if matcher['kind']=='exact':require(matcher['value']==sha256_bytes(seed[old[0]:old[1]]),'frozen section hash differs from seed')
            else:require(matcher['value']==assertion['target_scope'].removeprefix('section:'),'frozen section anchor differs from scope')


def _literal(raw,kind):
    text=raw.decode('utf-8').strip()
    if kind.startswith('schema_') and text.startswith('"'):
        try:
            value=json.loads(text)
            if isinstance(value,str):return value
        except ValueError:pass
    if kind.startswith('schema_') and len(text)>=2 and text[0]==text[-1]=="'":return text[1:-1].replace("''","'")
    if kind=='table_cell':return re.sub(r'\\([\\`*_{}\[\]()#+\-.!|>])',r'\1',text)
    return text


def evaluate_assertions(*,invariants,seed,seed_map,candidate,candidate_map,frontmatter_id,rules=None,metrics=None):
    """Return exactly one result per deterministic assertion.

    Unsupported programs are invalid inputs, not an apparent successful empty
    result. Semantic assertions are reserved for the independent verifier.
    """
    validate_assertion_program(invariants,seed,seed_map)
    rules=discovery_rules(invariants,rules)
    seed_targets=validate_lineage_map(seed_map,seed);candidate_targets=validate_lineage_map(candidate_map,candidate)
    require(candidate_map['job_id']==seed_map['job_id'],'assertion maps belong to different jobs')
    units,diagnostics,_=scan_units(candidate,candidate_map,frontmatter_id=frontmatter_id,rules=rules)
    results=[]
    for assertion in invariants['assertions']:
        if assertion['enforcement']=='semantic':continue
        try:
            old,new,section_ids=_scope(assertion['target_scope'],seed_targets,candidate_targets,len(seed),len(candidate))
            kind=assertion['assertion_type'];matcher=assertion['matcher'];mode=matcher['kind'];value=matcher['value']
            scoped=[u for u in units if new[0]<=u['byte_start'] and u['byte_end']<=new[1]]
            evidence=''
            if kind in COUNTS:
                require(isinstance(metrics,MutationMetrics),'change metrics are required for a budget assertion')
                if assertion['target_scope']=='document':
                    observed=len(metrics.changed_section_ids) if kind=='max_changed_sections' else len(metrics.normative_unit_sections)
                else:
                    observed=len(metrics.changed_section_ids & section_ids) if kind=='max_changed_sections' else sum(
                        bool(sections & section_ids) for sections in metrics.normative_unit_sections.values())
                maximum=_maximum(matcher);passed=observed<=maximum;evidence=f'{observed} distinct changes; maximum {maximum}.'
            elif kind=='section_unchanged':
                passed=seed[old[0]:old[1]]==candidate[new[0]:new[1]]
                evidence='Compared exact scoped bytes against the immutable seed.'
            else:
                require(not any(d['byte_start']<new[1] and d['byte_end']>=new[0] for d in diagnostics),
                        'scoped parser diagnostics prevent a complete lexical assertion')
                if kind.startswith('heading_'):
                    values=[item['canonical_section_id'] if mode=='canonical_id' else item['heading_text']
                            for item,span in candidate_targets.values() if new[0]<=span.start<new[1]]
                elif kind=='table_row_present' and mode=='inventory_query':
                    rows={u['byte_start']:[] for u in scoped if u['kind']=='table_row'}
                    for u in scoped:
                        if u['kind']=='table_cell':rows[u['anchor_line_start']].append(_literal(candidate[u['byte_start']:u['byte_end']],u['kind']))
                    passed=value['cells'] in rows.values();evidence='Compared exact ordered table cells.'
                    results.append({'assertion_id':assertion['assertion_id'],'result':'pass' if passed else 'fail','evidence':evidence})
                    continue
                else:
                    if mode=='inventory_query':kinds={value['kind']}
                    elif kind=='enum_member_present':kinds={'schema_enum_member','enumerated_member'}
                    elif kind=='table_row_present':kinds={'table_row'}
                    else:kinds=IDENTIFIER_KINDS
                    values=[_literal(candidate[u['byte_start']:u['byte_end']],u['kind']) for u in scoped if u['kind'] in kinds]
                    if kind=='enum_member_present' and mode!='inventory_query':
                        # A list's initial literal label is its lexical enum member.
                        values += [m.group(1) for text in values if (m:=re.match(r'`?([A-Za-z_][\w.-]*)`?\s*:',text))]
                expected=value['value'] if mode=='inventory_query' else value
                matches=sum(bool(re.search(expected,text)) if mode=='regex' else text==expected for text in values)
                if kind=='canonical_model_count':passed=matches==value['count']
                else:passed=(matches==0) if kind.endswith('_absent') else (matches>0)
                evidence=f'{matches} matching lexical facts.'
                if kind=='canonical_model_count':evidence+=f" Expected {value['count']}; no semantic model-count claim."
            results.append({'assertion_id':assertion['assertion_id'],'result':'pass' if passed else 'fail','evidence':evidence})
        except ValueError as exc:
            results.append({'assertion_id':assertion['assertion_id'],'result':'fail','evidence':str(exc)})
    return results
