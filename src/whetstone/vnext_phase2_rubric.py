"""Exact rubric attribution and retained verified gap accounting."""
from copy import deepcopy
import re

from whetstone.identity import rubric_gap_fingerprint, rubric_gap_id
from whetstone.sections import section_index
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_verified_phase2_rubric_v1.md'
RESPONSE_SCHEMA = 'vnext_phase2_rubric_response_v1'


def supported(suite):
    return any(row['path'] == ALGORITHM for row in suite.manifest['algorithms'])


def pins(suite):
    from whetstone.vnext_phase2_source_correction import pins as source_pins
    source_pins(suite)
    entries = {row['path']: row['sha256'] for family in ('algorithms','schemas') for row in suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/'+RESPONSE_SCHEMA+'.schema.json'):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'Phase 2 rubric contract is absent or changed', path)


def catalogue(raw, *, target_phase='final'):
    """Stable atomic textual references, not inferred acceptance judgments."""
    require(target_phase in {'mid', 'final'}, 'unknown rubric target phase')
    # The admitted builtin standard rubric has no explicit mid requirements.
    # Custom rubrics need a separate applicability contract before admission.
    if target_phase == 'mid': return []
    text = raw.decode('utf-8');headings = iter(section_index(text))
    result, section, parts, position = [], None, [], 0
    def flush():
        nonlocal parts, position
        if parts and section is not None:
            value = ''.join(parts).encode('utf-8');position += 1
            result.append(dict(rubric_anchor=section+'/requirement-'+str(position),
                requirement_hash=sha256_bytes(value), text=value.decode(), order=len(result)))
        parts = []
    for line in text.splitlines(keepends=True):
        if re.match(r'^#{1,6}\s+',line):
            flush();section = next(headings).id;position = 0
        elif not line.strip(): flush()
        else:
            if re.match(r'^\s*(?:[-*+] |\d+\. )', line): flush()
            parts.append(line)
    flush()
    return result


def attribute(annotations, feedback, raw, section_ids, *, target_phase='final'):
    requirements = {row['rubric_anchor']:row for row in catalogue(raw, target_phase=target_phase)}
    sources = {row['feedback_id']:row for row in feedback['feedback']}
    selected, attributed, gaps = set(), set(), []
    ordering = {name:i for i,name in enumerate(section_ids)}
    for annotation in annotations:
        key = annotation['feedback_id'], annotation['rubric_anchor']
        require(key not in selected and key[0] in sources and key[1] in requirements,
                'rubric attribution is duplicate or unknown')
        selected.add(key);attributed.add(key[0])
        requirement = requirements[key[1]];row = sources[key[0]]
        require(annotation['requirement_hash'] == requirement['requirement_hash'], 'rubric requirement bytes differ')
        require(row['rubric_impact'] is not None and row['affected_sections']
                and set(row['affected_sections']) <= set(section_ids), 'rubric gap lacks an attributable source finding')
        affected = sorted(set(row['affected_sections']), key=ordering.__getitem__)
        fingerprint = rubric_gap_fingerprint(key[1], affected, row['claim'])
        gap = dict(gap_id=rubric_gap_id(fingerprint), gap_fingerprint=fingerprint, rubric_anchor=key[1],
            affected_sections=affected, normalized_severity=row['normalized_severity'], claim=row['claim'],
            evidence=row['evidence'], recommendation=row['recommended_change'], status='unresolved',
            blocking_convergence=True)
        gaps.append(dict(source_issue_id=row['issue_id'], source_feedback_id=key[0],
                         requirement=deepcopy(requirement), source_section_ordinal=ordering[affected[0]], gap=gap))
    require(attributed == {row['feedback_id'] for row in sources.values() if row['rubric_impact'] is not None},
            'rubric-impact findings require exact requirement attribution')
    identities = [row['gap']['gap_id'] for row in gaps]
    require(len(identities) == len(set(identities)), 'duplicate rubric gap identity')
    return sorted(gaps, key=lambda row:(row['requirement']['order'],
        ordering[row['gap']['affected_sections'][0]], row['gap']['gap_id']))


def retained_entries(frames, reference, *, accept=True):
    """Resolution receipts clear exact source findings; recurrence reopens gaps."""
    gaps, records = {}, []
    if not frames: return []
    reader = frames[-1]['owner'].proof.reader
    ordinal = reader.json(reference, 'current_verified_pointer_v1')['promotion_ordinal']
    for frame in frames:
        if not frame.get('consumed'): continue
        source = reader.json(frame['bound'].request['base_pointer'], 'current_verified_pointer_v1')
        if source['promotion_ordinal'] > ordinal: continue
        for row in frame['review'].get('rubric_findings', []):
            gaps[row['gap']['gap_id']] = deepcopy(row)
        from whetstone.vnext_phase2_gap_acceptance import read_record, validate
        record = read_record(frame, frame['bound'].request['base_pointer'])
        if record is not None:
            validate(frame, record[0], gaps, frame['bound'].request['base_pointer'])
            records.append(record)
        resolution = frame.get('resolution')
        if resolution and resolution['committed']:
            promoted = reader.json(resolution['packet']['promoted_pointer'], 'current_verified_pointer_v1')
            if promoted['promotion_ordinal'] <= ordinal:
                covered = {row['gap']['gap_id'] for row in frame['review'].get('rubric_findings',[])}
                for row in gaps.values():
                    if row['gap']['gap_id'] in covered and row['source_issue_id'] in resolution['resolved_issue_ids']:
                        row['gap'].update(status='resolved',blocking_convergence=False)
                record = read_record(frame, resolution['packet']['promoted_pointer'])
                if record is not None:
                    validate(frame,record[0],gaps,resolution['packet']['promoted_pointer'])
                    records.append(record)
    if accept:
        from whetstone.vnext_phase2_gap_acceptance import apply
        apply(gaps,records,reference)
    return sorted(gaps.values(),key=lambda row:(row['requirement']['order'],
        row['source_section_ordinal'],row['gap']['gap_id']))


def retained(frames, reference):
    return [row['gap'] for row in retained_entries(frames,reference)]


def proposal_context(bound, review):
    context = dict(configuration=deepcopy(bound.inputs['configuration']), request=deepcopy(bound.request))
    if 'rubric_catalogue' in bound.inputs:
        context['rubric'] = dict(content=bound.inputs['rubric'], findings=deepcopy(review['rubric_findings']))
    return context


def report_gaps(proof, frames, reference):
    """Existing failure schema uses issue summaries; full gap identity stays retained."""
    if not supported(proof.reader.suite):
        require(not any(row['rubric_impact'] is not None or 'rubric_gaps.json' in row['affected_sections']
            for frame in frames if frame.get('consumed') for row in frame['review']['feedback']['feedback']),
            'failure reporting cannot invent rubric-gap resolution')
        return []
    pins(proof.reader.suite)
    return [dict(issue_id='iss_'+row['gap_fingerprint'][:16],issue_fingerprint=row['gap_fingerprint'],
        normalized_severity=row['normalized_severity'],affected_sections=deepcopy(row['affected_sections']),claim=row['claim'])
        for row in retained(frames,reference) if row['status']!='resolved'
        and not (row['status']=='accepted' and not row['blocking_convergence'])]
