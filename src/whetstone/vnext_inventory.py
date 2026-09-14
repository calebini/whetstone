"""Exact line coverage and protected lexical facts for candidate validation.

Discovery does not prove semantic preservation. Candidate unit correspondence,
authorization and assertions consume this inventory in a separate validator.
"""
from bisect import bisect_right
from collections import Counter
import json
import re

from whetstone.hashing import normalize_draft
from whetstone.preservation_inventory import build_inventory
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, content_identifier, require, sha256_bytes
from whetstone.vnext_identity import seed_unit_id
from whetstone.vnext_section_lineage import validate_lineage_map
from whetstone.vnext_sections import section_spans


INVENTORY_VERSION='preservation-inventory-v2'
RFC=re.compile(r'(?<![A-Za-z0-9_])(MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)(?![A-Za-z0-9_])')
CODE=re.compile(r'(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)',re.DOTALL)
REFERENCE=re.compile(r'\[[^\]\n]+\]\(([^)\s]+)(?:\s+[^)]*)?\)')
LIST=re.compile(r'^\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.+?)\s*$')
LABEL=re.compile(r'\b(preconditions?|postconditions?|acceptance(?: criteria| tests?)?|given|when|then)\s*:',re.I)
YAML_KEY=re.compile(r'^(\s*)(?:-\s+)?((?:"(?:[^"\\]|\\.)*"|\x27[^\x27]*\x27|[A-Za-z_][\w.-]*))\s*:\s*(.*)$')


def frontmatter_section_id(job):
    return content_identifier('sec','whetstone-frontmatter-section-id-v2',
                              [job['job_id'],job['seed_draft']['hash']])


def _rules(rules):
    require(isinstance(rules,list),'inventory rules must be an ordered array')
    names=set()
    for rule in rules:
        require(set(rule)=={'rule_id','text','normative','kind'},'invalid inventory discovery rule')
        require(isinstance(rule['rule_id'],str) and rule['rule_id'] and rule['rule_id'] not in names,'duplicate or empty inventory rule')
        require(isinstance(rule['text'],str) and rule['text'] and '\n' not in rule['text'] and '\r' not in rule['text'],
                'inventory discovery patterns must be nonempty exact line text')
        require(type(rule['normative']) is bool,'inventory rule normative flag must be Boolean')
        require(rule['kind'] in {'concept','identifier','command','flag','field','state','role','error_code','terminal_state','artifact','normative_pattern'},
                'unsupported inventory discovery rule kind')
        names.add(rule['rule_id'])
    return sha256_bytes(canonical_json_bytes(rules))


def _json_facts(text):
    """Strict JSON token spans, including every schema field/required/enum item."""
    decoder=json.JSONDecoder(parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
    facts=[]
    def space(p):
        while p<len(text) and text[p] in ' \t\r\n':p+=1
        return p
    def parse(p,path,depth=0):
        require(depth<128,'schema nesting exceeds inventory bound')
        p=space(p);require(p<len(text),'incomplete JSON schema')
        if text[p]=='{':
            p=space(p+1);seen=set()
            if p<len(text) and text[p]=='}':return p+1
            while True:
                start=p;key,end=decoder.raw_decode(text,p)
                require(isinstance(key,str) and key not in seen,'invalid or duplicate JSON schema field');seen.add(key)
                facts.append(('schema_field',start,end));p=space(end)
                require(p<len(text) and text[p]==':','missing JSON schema colon')
                p=space(parse(p+1,path+[key],depth+1))
                require(p<len(text) and text[p] in ',}','incomplete JSON schema object')
                if text[p]=='}':return p+1
                p=space(p+1)
        if text[p]=='[':
            p=space(p+1)
            if p<len(text) and text[p]==']':return p+1
            while True:
                start=p;p=parse(p,path+[None],depth+1)
                if path and path[-1] in {'required','enum'}:
                    facts.append(('schema_required_member' if path[-1]=='required' else 'schema_enum_member',start,p))
                p=space(p);require(p<len(text) and text[p] in ',]','incomplete JSON schema array')
                if text[p]==']':return p+1
                p=space(p+1)
        _,end=decoder.raw_decode(text,p)
        return end
    end=space(parse(0,[]));require(end==len(text),'extra JSON schema content')
    return facts


def _yaml_flow_members(text):
    require(text.startswith('['),'YAML members require a flow array')
    start=1;position=1;quote=None;spans=[]
    while position<len(text):
        char=text[position]
        if quote:
            if char=='\\' and quote=='"':position+=2;continue
            if char==quote:
                if quote=="'" and position+1<len(text) and text[position+1]=="'":position+=2;continue
                quote=None
        elif char in {'"',"'"}:quote=char
        elif char in '[{}&*':raise ValueError('Unsupported nested or anchored YAML flow member')
        elif char in ',]':
            a=start;b=position
            while a<b and text[a].isspace():a+=1
            while b>a and text[b-1].isspace():b-=1
            if a<b:spans.append((a,b))
            else:require(char==']' and start==1,'Empty YAML flow member')
            if char==']':
                tail=text[position+1:].strip()
                require(not tail or tail.startswith('#'),'Extra YAML flow content')
                return spans
            start=position+1
        position+=1
    raise ValueError('Incomplete YAML flow members')


def scan_units(raw,mapping,*,frontmatter_id,rules=()):
    """Return units without minted lineage IDs plus parser diagnostics.

    Primary line units partition every byte. Overlapping lexical facts carry
    independent IDs after minting, and anchor to a primary line. Normative
    budget counting uses primary normative lines, avoiding facet double counts.
    Rules must be immutable, hash-bound inputs before a runtime invokes this API.
    """
    rules=list(rules);rules_hash=_rules(rules)
    validate_lineage_map(mapping,raw)
    spans=section_spans(raw);active=[s for s in mapping['sections'] if s['status']=='active']
    starts=[s.start for s in spans]
    lines=build_inventory(raw,path='draft.md')['units'];result=[];diagnostics=[];facts=set()
    def owner(start):
        index=bisect_right(starts,start)-1
        return active[index]['stable_section_id'] if index>=0 else frontmatter_id
    def add(kind,start,end,*,primary=False,normative=False,features=(),sources=()):
        if not primary and (kind,start,end) in facts:return
        require(0<=start<end<=len(raw),'invalid inventory span')
        facts.add((kind,start,end));content=raw[start:end]
        result.append({'kind':kind,'owning_section_id':owner(start),'byte_start':start,'byte_end':end,
            'content_hash':sha256_bytes(content),
            'canonical_content_hash':sha256_bytes(normalize_draft(content.decode('utf-8')).encode('utf-8')),
            'primary':primary,'normative':normative,'normative_sources':sorted(set(sources)),
            'protected':bool(content.strip()),'features':sorted(set(features))})
    fence_language=None;fence_start=None;yaml_stack=[]
    for line in lines:
        start,end=line['byte_start'],line['byte_end'];text=raw[start:end].decode('utf-8').rstrip('\r\n')
        offsets=[0]
        for char in text:offsets.append(offsets[-1]+len(char.encode('utf-8')))
        def facet(kind,a,b):
            if a<b:add(kind,start+offsets[a],start+offsets[b])
        sources=['rfc:'+m.group() for m in RFC.finditer(text)]
        for rule in rules:
            if rule['normative'] and rule['text'] in text:sources.append('rule:'+rule['rule_id'])
        features=[]
        if sources:features.append('normative_statement')
        if line['kind']=='heading':features.append('heading_hierarchy')
        add(line['kind'],start,end,primary=True,normative=bool(sources),features=features,sources=sources)
        for rule in rules:
            position=0
            while True:
                position=text.find(rule['text'],position)
                if position<0:break
                facet('configured_'+rule['kind'],position,position+len(rule['text']));position+=len(rule['text'])
        if line['kind']=='fence_delimiter':
            if fence_start is None:
                fence_start=end;fence_language=re.sub(r'^ {0,3}(?:`{3,}|~{3,})','',text).strip().lower();yaml_stack=[]
            else:
                if fence_language in {'json','jsonschema','json-schema'}:
                    content=raw[fence_start:start].decode('utf-8');positions=[0]
                    for char in content:positions.append(positions[-1]+len(char.encode('utf-8')))
                    try:
                        for kind,a,b in _json_facts(content):add(kind,fence_start+positions[a],fence_start+positions[b])
                    except (ValueError,RecursionError) as exc:
                        diagnostics.append({'code':'schema_json_invalid','byte_start':fence_start,'byte_end':start,'message':str(exc)})
                fence_start=None;fence_language=None
            continue
        if line['kind']=='fence_body':
            if fence_language in {'yaml','yml'}:
                match=YAML_KEY.match(text)
                if match:
                    indent=len(match[1]);key=match[2].strip('"\x27')
                    while yaml_stack and yaml_stack[-1][0]>=indent:yaml_stack.pop()
                    yaml_stack.append((indent,key));facet('schema_field',match.start(2),match.end(2))
                    value=match[3]
                    if key in {'required','enum'} and value.startswith('['):
                        # YAML flow members support quoted/unquoted scalars;
                        # nested/anchored forms remain protected opaque bytes.
                        try:
                            for a,b in _yaml_flow_members(value):facet('schema_required_member' if key=='required' else 'schema_enum_member',
                                match.start(3)+a,match.start(3)+b)
                        except ValueError as exc:
                            diagnostics.append({'code':'schema_yaml_opaque_members','byte_start':start,'byte_end':end,'message':str(exc)})
                else:
                    match=LIST.match(text)
                    if match:
                        indent=len(text)-len(text.lstrip())
                        while yaml_stack and yaml_stack[-1][0]>indent:yaml_stack.pop()
                        if yaml_stack and yaml_stack[-1][1] in {'required','enum'}:
                            facet('schema_required_member' if yaml_stack[-1][1]=='required' else 'schema_enum_member',match.start(1),match.end(1))
            continue
        for match in CODE.finditer(text):facet('identifier',match.start(2),match.end(2))
        for match in REFERENCE.finditer(text):facet('cross_reference',match.start(1),match.end(1))
        match=LIST.match(text)
        if match:facet('enumerated_member',match.start(1),match.end(1))
        for match in LABEL.finditer(text):
            word=match[1].lower();kind='precondition' if word.startswith('precondition') else 'postcondition' if word.startswith('postcondition') else 'acceptance_criterion'
            facet(kind,match.start(),len(text))
        # Escape parity distinguishes a literal pipe from a Markdown delimiter.
        pipes=[]
        for position,char in enumerate(text):
            if char!='|':continue
            escapes=0;prior=position-1
            while prior>=0 and text[prior]=='\\':escapes+=1;prior-=1
            if escapes%2==0:pipes.append(position)
        if pipes:
            facet('table_row',0,len(text))
            boundaries=[-1]+pipes+[len(text)]
            for left,right in zip(boundaries,boundaries[1:]):
                a=left+1;b=right
                while a<b and text[a].isspace():a+=1
                while b>a and text[b-1].isspace():b-=1
                if a<b:facet('table_cell',a,b)
    if fence_start is not None:
        diagnostics.append({'code':'unclosed_fence','byte_start':fence_start,'byte_end':len(raw),'message':'Unclosed code fence.'})
    result.sort(key=lambda unit:(unit['byte_start'],not unit['primary'],unit['byte_end'],unit['kind']))
    primary=[unit for unit in result if unit['primary']]
    require(sum(unit['byte_end']-unit['byte_start'] for unit in primary)==len(raw),'inventory does not cover every byte')
    line_starts=[unit['byte_start'] for unit in primary]
    for unit in result:unit['anchor_line_start']=line_starts[bisect_right(line_starts,unit['byte_start'])-1]
    return result,diagnostics,rules_hash


def seed_inventory(raw,mapping,job,*,rules=()):
    require(sha256_bytes(raw)==job['seed_draft']['hash'],'seed inventory requires exact seed bytes')
    require(mapping['job_id']==job['job_id'],'seed inventory belongs to another job')
    frontmatter=frontmatter_section_id(job)
    units,diagnostics,rules_hash=scan_units(raw,mapping,frontmatter_id=frontmatter,rules=rules)
    counts=Counter()
    for unit in units:
        key=(unit['owning_section_id'],unit['kind']);counts[key]+=1
        unit['unit_id']=seed_unit_id(job['seed_draft']['hash'],*key,counts[key])
    require(len({u['unit_id'] for u in units})==len(units),'seed inventory identity collision')
    anchors={u['byte_start']:u['unit_id'] for u in units if u['primary']}
    for unit in units:unit['anchor_line_unit_id']=anchors[unit.pop('anchor_line_start')]
    result={'schema_version':'vnext-preservation-inventory-v2','inventory_version':INVENTORY_VERSION,
        'job_id':job['job_id'],'seed_draft_hash':job['seed_draft']['hash'],'draft_hash':sha256_bytes(raw),
        'section_map_hash':sha256_bytes(canonical_json_bytes(mapping)),'frontmatter_section_id':frontmatter,
        'rules_hash':rules_hash,'units':units,'diagnostics':diagnostics,
        'base_inventory_hash':None,'transaction_id':None,'proposal_hash':None,'retired_unit_ids':[]}
    VNextSchemaRegistry().validate(result,'vnext_preservation_inventory_v2')
    return result


def validate_seed_inventory(packet,raw,mapping,job,*,rules=()):
    VNextSchemaRegistry().validate(packet,'vnext_preservation_inventory_v2')
    require(packet==seed_inventory(raw,mapping,job,rules=rules),
            'seed inventory does not reproduce from its exact inputs')
