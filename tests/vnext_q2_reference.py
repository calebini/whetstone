"""Independent, stdlib-only P0-13 reference over validated contract inputs.

Contract sources: candidate leaf §§Section Identity, Registration, Terminal
Reporting; identity-v1, candidate-assembly-v2 and version-operations-v1.
This is a comparison oracle, not admission, a semantic verifier or a scheduler.
Byte-tag splicing and a separate tree matcher intentionally do not use the
production assembler, parser, identity, canonicalizer or journal readers.
"""
import base64
from copy import deepcopy
import hashlib
import json
import re
import sys


def require(condition, message):
    if not condition: raise ValueError(message)


def canonical(value):
    def check(v):
        if isinstance(v, dict):
            require(all(isinstance(k, str) for k in v), 'non-string key')
            for k, item in v.items(): check(k); check(item)
        elif isinstance(v, list):
            for item in v: check(item)
        elif isinstance(v, str): v.encode('utf-8')
        else: require(v is None or type(v) in (bool, int), 'unsupported JSON scalar')
    check(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(raw): return hashlib.sha256(raw).hexdigest()
def identity(prefix, domain, *args): return prefix+'_'+digest(canonical([domain, *args]))
def normalize(raw):
    lines = raw.decode().replace('\r\n', '\n').replace('\r', '\n').split('\n')
    return ('\n'.join(line.rstrip(' \t') for line in lines).rstrip('\n')+'\n').encode()


def sections(raw):
    """Independent ATX/fence scanner with exact byte coordinates."""
    raw.decode('utf-8')
    rows = []; fence = None
    for line in re.finditer(rb'[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z', raw):
        text = line[0].decode().rstrip('\r\n')
        if fence:
            if re.fullmatch(r' {0,3}'+re.escape(fence[0])+r'{'+str(fence[1])+r',}[ \t]*', text): fence = None
            continue
        heading = re.fullmatch(r' {0,3}(#{1,6})(?:[ \t]+(.*)|)', text)
        if heading:
            title = re.sub(r'(?:^|[ \t]+)#+[ \t]*$', '', heading[2] or '').strip(' \t')
            rows.append(dict(title=title, level=len(heading[1]), start=line.start(), body=line.end()))
        else:
            marker = re.match(r' {0,3}(`{3,}|~{3,})', text)
            if marker: fence = (marker[1][0], len(marker[1]))
    counts = {}
    for i, row in enumerate(rows):
        row['parent'] = next((j for j in range(i-1, -1, -1) if rows[j]['level'] < row['level']), None)
        row['direct_end'] = rows[i+1]['start'] if i+1 < len(rows) else len(raw)
        row['end'] = next((later['start'] for later in rows[i+1:] if later['level'] <= row['level']), len(raw))
        ancestors = []; parent = row['parent']
        while parent is not None:
            if not (parent == 0 and len(rows) > 1 and rows[0]['level'] == 1): ancestors.insert(0, rows[parent]['title'])
            parent = rows[parent]['parent']
        slug = re.sub('[^a-z0-9]+', '-', ' '.join(ancestors+[row['title']]).lower()).strip('-') or 'section'
        counts[slug] = counts.get(slug, 0)+1
        row['anchor'] = slug if counts[slug] == 1 else slug+'#'+str(counts[slug])
    return rows


def correspondence(old_raw, new_raw):
    """Recursive structural matching; output maps new preorder to old preorder."""
    old, new = sections(old_raw), sections(new_raw)
    matches = {}; used = set()
    def signature(rows, raw, index, title=True):
        root = rows[index]
        return tuple((r['title'] if title or j != index else None, r['level']-root['level'],
                      digest(normalize(raw[r['body']:r['direct_end']])))
                     for j, r in enumerate(rows) if root['start'] <= r['start'] < root['end'])
    def children(rows, parent): return [i for i, r in enumerate(rows) if r['parent'] == parent]
    def stream(rows, raw, roots):
        if not roots: return ()
        # One common depth origin for the entire ordered stream. Normalizing
        # each sibling separately would erase relative-depth ambiguity.
        level = rows[roots[0]]['level']
        return tuple((r['title'], r['level']-level, digest(normalize(raw[r['body']:r['direct_end']])))
                     for root in roots for r in rows
                     if rows[root]['start'] <= r['start'] < rows[root]['end'])
    def bind(left, right):
        require(left not in used and right not in matches, 'identity reused')
        used.add(left); matches[right] = left
        a = children(old, left); b = children(new, right)
        if len(a) == len(b) and stream(old, old_raw, a) == stream(new, new_raw, b):
            for oi, ni in zip(a, b): bind(oi, ni)
            return
        for mode in ('exact', 'name', 'renamed'):
            def key(rows, raw, i):
                return rows[i]['title'] if mode == 'name' else signature(rows, raw, i, mode != 'renamed')
            ak = {i: key(old, old_raw, i) for i in a if i not in used}
            bk = {i: key(new, new_raw, i) for i in b if i not in matches}
            for oi, value in ak.items():
                candidates = [ni for ni, other in bk.items() if other == value]
                if list(ak.values()).count(value) == len(candidates) == 1: bind(oi, candidates[0])
        require(not ({old[i]['title'] for i in a if i not in used} &
                     {new[i]['title'] for i in b if i not in matches}), 'ambiguous sibling identity')
    require(old and new, 'subtree requires headings')
    bind(0, 0)
    # Exact unmatched subtrees can change parents. Match largest roots first;
    # recursion transfers their repeated descendants without arbitrary guesses.
    for oi in range(len(old)):
        if oi in used: continue
        sig = signature(old, old_raw, oi)
        left = [i for i in range(len(old)) if i not in used and signature(old, old_raw, i) == sig]
        right = [i for i in range(len(new)) if i not in matches and signature(new, new_raw, i) == sig]
        if right:
            require(len(left) == len(right) == 1, 'ambiguous moved identity')
            bind(oi, right[0])
    return matches


def version_anchors(raw):
    rows = []; statuses = []; fence = None; front = False; root = False; body = False
    for n, line in enumerate(re.finditer(rb'[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z', raw)):
        text = line[0].decode().rstrip('\r\n')
        if n == 0 and text == '---': front = True; continue
        if front and text in ('---', '...'): front = False; continue
        marker = re.match(r' {0,3}(`{3,}|~{3,})', text)
        if not front and marker:
            if fence is None: fence = (marker[1][0], len(marker[1]))
            elif marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not text[marker.end():].strip(): fence = None
            continue
        if fence: continue
        kind = None; start = 0
        heading = re.match(r' {0,3}(#{1,6})[ \t]+(.*)', text) if not front else None
        if heading:
            if len(heading[1]) == 1 and not root and not body: root = True; kind = 'heading'; start = heading.start(2)
            else: body = True
        if not body:
            field = re.match(r'(Version|Status):[ \t]+', text)
            if field:
                start = field.end(); kind = 'status' if field[1] == 'Status' else 'frontmatter' if front else 'version'
                if kind == 'status' and re.match(r'Accepted\b', text[start:]):
                    begin = line.start()+len(text[:start].encode()); statuses.append((begin, begin+8))
        if kind:
            values = list(re.finditer(r'(?<![\w.])v?([0-9]+(?:\.[0-9]+){0,2})(?![\w.]|\.[0-9])', text[start:]))
            require(len(values) <= 1, 'ambiguous numeric anchor')
            if values:
                m = values[0]; a = start+m.start(1); b = start+m.end(1)
                rows.append((kind, line.start()+len(text[:a].encode()), line.start()+len(text[:b].encode()), m[1]))
    require(not front and len({r[3] for r in rows}) <= 1, 'conflicting or unterminated metadata')
    return sorted(rows, key=lambda r: (('frontmatter','version','heading','status').index(r[0]), r[1])), statuses


def metadata(base, proposed, plan):
    context = plan['system_metadata']; phase = context['phase']; transition = context['transition']
    require(phase in ('phase_1','phase_2') and transition in ('round','phase2_entry'), 'unsupported metadata context')
    require(transition != 'phase2_entry' or (phase == 'phase_2' and base == proposed), 'entry changed base')
    old, old_status = version_anchors(base); current, statuses = version_anchors(proposed)
    require([(r[0],r[3]) for r in old] == [(r[0],r[3]) for r in current] and len(old_status) == len(statuses), 'Editor changed anchors')
    before = old[0][3] if old else ''; after = before
    changed = normalize(base) != normalize(proposed)
    if before and (changed or transition == 'phase2_entry'):
        parts = [int(v) for v in before.split('.')]; widths = [len(v) for v in before.split('.')]
        if transition == 'phase2_entry': after = str(max(1,parts[0]+int(any(parts[1:]))))+'.0'
        else:
            if len(parts) == 1: parts += [1]; widths += [2 if phase == 'phase_1' else 1]
            else:
                parts[-1] += 1
                if phase == 'phase_1' and len(parts) == 2 and widths[1] >= 2 and parts[1] >= 10**widths[1]: parts = [parts[0]+1, 0]
            after = '.'.join([str(parts[0])]+[str(p).zfill(w) for p,w in zip(parts[1:],widths[1:])])
    edits = []
    if before != after: edits += [dict(start=a,end=b,before=v,after=after,kind='version') for _,a,b,v in current]
    if changed and phase == 'phase_1': edits += [dict(start=a,end=b,before='Accepted',after='Draft',kind='status') for a,b in statuses]
    edits.sort(key=lambda e:e['start']); result = proposed
    for e in reversed(edits): result = result[:e['start']]+e['after'].encode()+result[e['end']:]
    record = dict(schema_version='vnext-version-operation-v1',job_id=plan['job_id'],transaction_id=plan['transaction_id'],
                  authority=deepcopy(context),base_hash=digest(base),input_hash=digest(proposed),output_hash=digest(result),
                  canonical_input_hash=digest(normalize(proposed)),candidate_hash=digest(normalize(result)),before=before,after=after,edits=edits)
    record['operation_id'] = identity('op','whetstone-system-version-operation-v1',record)
    return result, record


def assemble(base, mapping, plan, patch, payloads):
    require(mapping['parser_contract_version'] == 'markdown-atx-v1', 'unsupported parser')
    require(plan['schema_version'] in ('mutation-plan-v1','mutation-plan-v2','mutation-plan-v3','mutation-plan-v4'), 'unsupported plan')
    require(digest(base) == mapping['draft_hash'] == plan['base_draft_hash'] == patch['base_draft_hash'], 'base binding mismatch')
    require(digest(canonical(plan)) == patch['mutation_plan_hash'], 'plan binding mismatch')
    if 'base_section_identity_map_hash' in plan: require(digest(canonical(mapping)) == plan['base_section_identity_map_hash'], 'map binding mismatch')
    require(identity('pro','whetstone-proposal-id-v1',{**patch,'proposal_id':None}) == patch['proposal_id'], 'proposal identity mismatch')
    old = sections(base); active = [r for r in mapping['sections'] if r['status'] == 'active']
    require(len(old) == len(active), 'base map topology mismatch')
    by_id = {r['stable_section_id']:i for i,r in enumerate(active)}
    operations = {op['operation_id']:op for op in patch['operations']}; ordered = []
    require(len(operations) == len(patch['operations']), 'duplicate operation')
    while len(ordered) < len(operations):
        ready = sorted(k for k,v in operations.items() if k not in ordered and set(v['depends_on_operation_ids']) <= set(ordered))
        require(ready, 'dependency cycle or missing dependency'); ordered.append(ready[0])
    # Each byte carries its source coordinate. Reverse splices retain immutable
    # coordinates and insertion ordering without the production source-piece sweep.
    tagged = [(v,(None,i)) for i,v in enumerate(base)]; edits = []; intervals = []; payload_rows = {}; transfers = {}
    anchors = {}; target_kinds = {}
    for rank, key in enumerate(ordered):
        op = operations[key]; kind = op['operation_type']; index = by_id[op['target_stable_section_id']]; target = old[index]
        require(digest(base[target['start']:target['end']]) == op['expected_target_hash'], 'target hash mismatch')
        path = op['payload']['path']; raw = payloads[path] if path else b''
        require((path is None and kind == 'delete_section_subtree') or digest(raw) == op['payload']['hash'], 'payload hash mismatch')
        parsed = sections(raw); payload_rows[key] = parsed
        insertion = kind in ('insert_section_before','insert_section_after','append_child_section')
        require(op['target_stable_section_id'] not in target_kinds or (insertion and target_kinds[op['target_stable_section_id']]), 'duplicate target')
        target_kinds[op['target_stable_section_id']] = insertion
        if kind == 'replace_section_body': a,b = target['body'],target['direct_end']
        elif kind in ('replace_section_subtree','delete_section_subtree'):
            require(target['parent'] is not None, 'cannot replace root'); a,b = target['start'],target['end']
        elif insertion: a = target['start'] if kind == 'insert_section_before' else target['end']; b = a
        else: raise ValueError('unsupported operation')
        for x,y in intervals: require(not (max(a,x) < min(b,y) or a == b and x<a<y or x == y and a<x<b), 'overlap')
        intervals.append((a,b))
        if insertion:
            require(a not in anchors or anchors[a] in op['depends_on_operation_ids'], 'unordered insertion'); anchors[a] = key
        edits.append((a,b,rank,[(v,(key,i)) for i,v in enumerate(raw)]))
        if kind == 'replace_section_subtree' and op['preserve_target_identity']:
            local_old = sections(base[a:b]); transfer = correspondence(base[a:b],raw)
            transfers[key] = {parsed[n]['start']:by_id[next(r['stable_section_id'] for j,r in enumerate(active) if old[j]['start'] == a+local_old[o]['start'])] for n,o in transfer.items()}
    for a,b,rank,replacement in sorted(edits,key=lambda e:(e[0],e[1]!=e[0],e[2]),reverse=True): tagged[a:b] = replacement
    proposed = bytes(v for v,_ in tagged); spans = sections(proposed)
    expected = {(None,r['start']) for r in old} | {(key,r['start']) for key,rows in payload_rows.items() for r in rows}
    visible = {i for i,(_,tag) in enumerate(tagged) if tag in expected}
    require(visible == {r['start'] for r in spans}, 'heading boundary or fence spill')
    origins = [tagged[r['start']][1] for r in spans]
    old_starts = {r['start']:i for i,r in enumerate(old)}
    identities = []; prior = []; creators = []
    for r,(key,offset) in zip(spans,origins):
        if key is None: predecessor = old_starts[offset]
        else: predecessor = transfers.get(key,{}).get(offset)
        if predecessor is not None:
            previous = active[predecessor]['stable_section_id']; identifier = previous; creator = active[predecessor]['created_by_operation_id']
        else:
            ordinal = next(i+1 for i,p in enumerate(payload_rows[key]) if p['start'] == offset)
            identifier = identity('sec','whetstone-inserted-section-id-v1',plan['transaction_id'],key) if ordinal == 1 else identity('sec','whetstone-inserted-section-descendant-id-v2',plan['transaction_id'],key,ordinal)
            require(identifier not in {s['stable_section_id'] for s in mapping['sections']}, 'historical ID reused')
            previous = operations[key]['target_stable_section_id'] if offset == 0 and operations[key]['operation_type'] == 'replace_section_subtree' else None
            creator = key
        if key is None or offset == 0:
            if key is None: parent_id = active[predecessor]['parent_stable_section_id']
            else:
                op=operations[key]; target_row=active[by_id[op['target_stable_section_id']]]
                parent_id = target_row['stable_section_id'] if op['operation_type']=='append_child_section' else target_row['parent_stable_section_id']
            if key is None or operations[key]['operation_type']!='replace_section_body':
                require((identities[r['parent']] if r['parent'] is not None else None) == parent_id, 'changed parent')
        identities.append(identifier); prior.append(previous); creators.append(creator)
    require(len(set(identities)) == len(identities), 'section identity collision')
    version = None
    if plan['schema_version']=='mutation-plan-v4': proposed,version = metadata(base,proposed,plan)
    raw = normalize(proposed); final = sections(raw)
    require(len(final)==len(spans) and [(r['level'],r['parent']) for r in final]==[(r['level'],r['parent']) for r in spans], 'metadata topology change')
    rows=[]
    for i,r in enumerate(final):
        rows.append(dict(stable_section_id=identities[i],canonical_section_id=r['anchor'],parent_stable_section_id=identities[r['parent']] if r['parent'] is not None else None,
            heading_level=r['level'],heading_text=r['title'],preorder_ordinal=i+1,section_hash=digest(raw[r['start']:r['end']]),direct_body_hash=digest(raw[r['body']:r['direct_end']]),
            status='active',created_by_operation_id=creators[i],previous_stable_section_id=prior[i]))
    for row in mapping['sections']:
        if row['stable_section_id'] not in identities: rows.append({**deepcopy(row),'status':'retired','preorder_ordinal':len(rows)+1})
    result=dict(schema_version='section-identity-map-v2',identity_algorithm_version='vnext-section-lineage-v2',job_id=mapping['job_id'],draft_hash=digest(raw),parser_contract_version=mapping['parser_contract_version'],sections=rows)
    assembler='patch-assembler-v3' if plan['schema_version']=='mutation-plan-v4' else 'patch-assembler-v2'
    return dict(candidate=base64.b64encode(raw).decode(),candidate_hash=digest(raw),section_map=result,map_hash=digest(canonical(result)),version_operation=version,
        candidate_id=identity('can','whetstone-candidate-id-v1',plan['transaction_id'],digest(base),digest(canonical(patch)),assembler,'whetstone-markdown-normalization-v1'))


def select(artifacts):
    """Independent commit-binding projection, not semantic/admission replay.

    Persisted packages are produced by the real fenced owners. This reader
    checks canonical bytes, hashes, journal order, identities and cross-links;
    it does not rerun the Editor, Verifier, scheduler or preservation policy.
    """
    def read(path, expected=None):
        require(path in artifacts, 'missing artifact: '+path)
        raw=artifacts[path]
        require(expected is None or digest(raw)==expected, 'artifact hash mismatch: '+path)
        def pairs(items):
            require(len(dict(items))==len(items), 'duplicate JSON key'); return dict(items)
        value=json.loads(raw,object_pairs_hook=pairs)
        require(canonical(value)==raw,'noncanonical artifact')
        return value
    def linked(packet, stem): return read(packet[stem+'_path'],packet[stem+'_hash'])
    def minted(packet, field, prefix, domain, stamp):
        require(packet[field]==identity(prefix,domain,{k:v for k,v in packet.items() if k not in (field,stamp)}),'artifact identity mismatch')
    def event(path, hash_value, candidate, ordinal):
        value=read(path,hash_value); minted(value,'event_id','event','whetstone-disposition-id-v1','recorded_at')
        require(value['candidate_id']==candidate and value['candidate_creation_ordinal']==ordinal,'event candidate mismatch')
        return value
    head=read('rounds/current_verified.json')
    require(read(f"rounds/verified_history/current-verified-{head['promotion_ordinal']}.json")==head,'current snapshot mismatch')
    pointer=head
    while pointer['promotion_ordinal']:
        previous=linked(pointer,'previous_verified_pointer')
        require(previous['promotion_ordinal']+1==pointer['promotion_ordinal'] and previous['verified_draft_hash']==pointer['previous_verified_draft_hash'],'broken pointer lineage')
        pointer=previous
    for stem in ('verified_draft','verified_section_identity_map'):
        require(digest(artifacts[head[stem+'_path']])==head[stem+'_hash'],'head artifact changed')
    files={}
    for path in artifacts:
        if path.startswith('rounds/candidate_index/'):
            name=path.rsplit('/',1)[-1]
            if name.startswith('.vnext-tmp-'):continue
            match=re.fullmatch(r'creation-([1-9][0-9]*)\.json',name)
            require(match is not None,'invalid creation filename'); files[int(match[1])]=path
    require(sorted(files)==list(range(1,len(files)+1)),'creation gap')
    creations=[]; states={}; previous_hash=None; registered=set()
    for ordinal in sorted(files):
        path=files[ordinal]; row=read(path)
        minted(row,'creation_event_id','creation','whetstone-creation-id-v1','created_at')
        require(row['candidate_creation_ordinal']==ordinal and row['previous_creation_event_hash']==previous_hash,'creation predecessor mismatch')
        candidate=row['candidate_id']; require(candidate not in states,'duplicate candidate')
        require(row['job_id']==head['job_id'],'foreign candidate')
        require(digest(artifacts[row['candidate_path']])==row['candidate_hash'],'candidate hash mismatch')
        linked(row,'candidate_section_identity_map')
        initial=event(row['initial_disposition_event_path'],row['initial_disposition_event_hash'],candidate,ordinal)
        require(initial['event_ordinal']==1 and initial['previous_event_hash'] is None and initial['previous_disposition'] is None and
                initial['event_kind']=='candidate_created' and initial['new_disposition']=='CANDIDATE_UNVERIFIED' and
                initial['source_artifact_path']==row['candidate_path'] and initial['source_artifact_hash']==row['candidate_hash'],'invalid initial disposition')
        directory=row['candidate_path'].rsplit('/',1)[0]; registered.add(directory)
        effective=initial; reference=dict(path=row['initial_disposition_event_path'],hash=row['initial_disposition_event_hash'])
        decision=None; decision_ref=None; vp=directory+'/candidate_verification_current.json'
        if vp in artifacts:
            verification=read(vp); decision=linked(verification,'current_decision')
            effective=event(verification['current_disposition_event_path'],verification['current_disposition_event_hash'],candidate,ordinal)
            for key in ('job_id','candidate_id','candidate_creation_ordinal','transaction_id','candidate_section_identity_map_path','candidate_section_identity_map_hash'):
                require(verification[key]==decision[key]==row[key],'verification binding mismatch')
            require(decision['candidate_hash']==row['candidate_hash'] and verification['candidate_disposition']==decision['candidate_disposition']==effective['new_disposition'] and
                    verification['decision_final']==decision['decision_final'],'decision disposition mismatch')
            require(effective['event_kind']=='verification_decision' and effective['source_artifact_path']==verification['current_decision_path'] and effective['source_artifact_hash']==verification['current_decision_hash'],'verification source mismatch')
            event_number=effective['event_ordinal']; prior=initial
            for n in range(2,event_number+1):
                current=read(directory+f'/disposition_events/event-{n}.json')
                minted(current,'event_id','event','whetstone-disposition-id-v1','recorded_at')
                require(current['previous_event_hash']==digest(canonical(prior)) and current['previous_disposition']==prior['new_disposition'],'broken disposition chain')
                prior=current
            reference=dict(path=verification['current_disposition_event_path'],hash=verification['current_disposition_event_hash'])
            decision_ref=dict(path=verification['current_decision_path'],hash=verification['current_decision_hash'])
        states[candidate]=dict(creation=row,event=effective,event_ref=reference,decision=decision,decision_ref=decision_ref,directory=directory)
        creations.append(row);previous_hash=digest(artifacts[path])
    all_directories={m[1] for path in artifacts if (m:=re.match(r'(rounds/round-[1-9][0-9]*/candidates/can_[0-9a-f]{64})/',path))}
    orphans=sorted(all_directories-registered)
    if head['promotion_ordinal']:
        candidate=head['source_candidate_id']; require(candidate in states,'head candidate not registered')
        state=states[candidate]; row=state['creation']
        require(linked(head,'source_candidate_creation_event')==row and head['verified_draft_hash']==row['candidate_hash'] and head['verified_draft_path']==row['candidate_path'],'head registration mismatch')
        require(linked(head,'candidate_verification')==state['decision'] and state['decision']['decision_final'] and state['decision']['promotion_permitted'],'head verification mismatch')
        intent=linked(head,'promotion_intent'); minted(intent,'intent_id','intent','whetstone-intent-id-v1','prepared_at')
        promotion=event(head['promotion_disposition_event_path'],head['promotion_disposition_event_hash'],candidate,row['candidate_creation_ordinal'])
        require(intent['candidate_id']==candidate and intent['next_promotion_ordinal']==head['promotion_ordinal'] and intent['candidate_hash']==row['candidate_hash'],'head intent mismatch')
        require(promotion['new_disposition']=='CANDIDATE_PROMOTED' and promotion['source_artifact_path']==head['promotion_intent_path'] and promotion['source_artifact_hash']==head['promotion_intent_hash'] and promotion['previous_event_hash']==state['event_ref']['hash'],'head promotion mismatch')
        state['event']=promotion;state['event_ref']=dict(path=head['promotion_disposition_event_path'],hash=head['promotion_disposition_event_hash'])
    latest=creations[-1] if creations else None
    def eligible(state):
        d=state['decision']
        return bool(d and d['decision_final'] and d['promotion_permitted'] and d['candidate_disposition']=='CANDIDATE_VERIFIED' and
                    d['deterministic_result']==d['semantic_result']=='pass' and not d['outstanding_decision_ids'] and not d['rejection_codes'] and
                    d['base_draft_hash']==head['verified_draft_hash'] and state['event']['new_disposition']=='CANDIDATE_VERIFIED')
    claims=[]; next_ordinal=head['promotion_ordinal']+1
    for candidate,state in states.items():
        path=state['directory']+f'/promotion_intents/promotion-intent-{next_ordinal}.json'
        if path not in artifacts: continue
        intent=read(path);minted(intent,'intent_id','intent','whetstone-intent-id-v1','prepared_at')
        row=state['creation']
        require(eligible(state),'ineligible prepared claimant')
        require(intent['candidate_id']==candidate and intent['candidate_creation_ordinal']==row['candidate_creation_ordinal'] and
                intent['candidate_hash']==row['candidate_hash'] and intent['next_promotion_ordinal']==next_ordinal and
                intent['expected_current_promotion_ordinal']==head['promotion_ordinal'] and intent['expected_current_verified_pointer_hash']==digest(canonical(head)) and
                intent['expected_current_verified_hash']==head['verified_draft_hash'],'prepared intent mismatch')
        require(linked(intent,'candidate_creation_event')==row and linked(intent,'candidate_verification')==state['decision'],'prepared evidence mismatch')
        epath=state['directory']+'/disposition_events/event-4.json'
        snapshot=f'rounds/verified_history/current-verified-{next_ordinal}.json'
        if epath in artifacts:
            e=event(epath,None,candidate,row['candidate_creation_ordinal'])
            require(e['source_artifact_path']==path and e['source_artifact_hash']==digest(artifacts[path]) and e['previous_event_hash']==state['event_ref']['hash'] and
                    e['new_disposition']=='CANDIDATE_PROMOTED','prepared event mismatch')
        if snapshot in artifacts:
            require(epath in artifacts,'non-prefix snapshot'); p=read(snapshot)
            require(p['source_candidate_id']==candidate and p['promotion_intent_hash']==digest(artifacts[path]) and
                    p['promotion_disposition_event_hash']==digest(artifacts[epath]) and p['previous_verified_pointer_hash']==digest(canonical(head)),'prepared snapshot mismatch')
        claims.append(candidate)
    require(len(claims)<=1,'multiple prepared claimants')
    require(claims or f'rounds/verified_history/current-verified-{next_ordinal}.json' not in artifacts,'snapshot lacks claimant')
    selected=None if orphans else claims[0] if claims else latest['candidate_id'] if latest and eligible(states[latest['candidate_id']]) else None
    chosen=states[latest['candidate_id']] if latest else None
    return dict(latest_candidate=latest['candidate_id'] if latest else None,creation_ordinal=latest['candidate_creation_ordinal'] if latest else None,
        disposition=chosen['event']['new_disposition'] if chosen else None,effective_event=chosen['event_ref'] if chosen else None,
        decision=chosen['decision_ref'] if chosen else None,promotion_candidate=selected,orphans=orphans)


def main():
    packet=json.load(sys.stdin)
    if packet['task']=='assemble':
        result=assemble(base64.b64decode(packet['base']),packet['mapping'],packet['plan'],packet['patch'],
                        {p:base64.b64decode(raw) for p,raw in packet['payloads'].items()})
    elif packet['task']=='select': result=select({p:base64.b64decode(raw) for p,raw in packet['artifacts'].items()})
    else: raise ValueError('unsupported reference task')
    sys.stdout.buffer.write(canonical(result))


if __name__=='__main__': main()
