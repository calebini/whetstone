"""Exact operator acceptance evidence; no source-resolution authority."""
from copy import deepcopy

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_verified_phase2_gap_acceptance_v1.md'
SCHEMA = 'vnext_phase2_gap_acceptance_v1'


def supported(suite):
    return suite is not None and any(row['path'] == ALGORITHM for row in suite.manifest['algorithms'])


def pins(suite):
    from whetstone.vnext_phase2_targets import pins as target_pins
    target_pins(suite)
    entries = {row['path']: row['sha256'] for family in ('algorithms','schemas') for row in suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/'+SCHEMA+'.schema.json', 'schemas/vnext_phase2_declaration_v3.schema.json',
                 'schemas/vnext_phase2_finding_reconciliation_v2.schema.json'):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'Phase 2 gap-acceptance contract is absent or changed', path)


def path_for(frame, reference):
    return frame['owner'].directory+'/execution/gap_acceptances/'+reference['hash']+'.json'


def selection(entry):
    gap = entry['gap']
    identity = {key: value for key, value in gap.items() if key not in {'status','blocking_convergence'}}
    return dict(gap_id=gap['gap_id'], gap_fingerprint=gap['gap_fingerprint'],
                requirement_hash=entry['requirement']['requirement_hash'],
                gap_hash=sha256_bytes(canonical_json_bytes(identity)))


def bindings(frame, reference):
    from whetstone.vnext_verified_phase2_binding import _ref
    bound = frame['bound'];config = bound.inputs['configuration']
    resolution = None
    if reference != bound.request['base_pointer']:
        record = frame.get('resolution')
        require(record and record['committed'] and record['packet']['promoted_pointer'] == reference,
                'renewed gap acceptance requires committed current-promotion resolution')
        resolution = record['reference']
    pointer = frame['owner'].proof.reader.json(reference, 'current_verified_pointer_v1')
    return dict(schema_version='vnext-phase2-gap-acceptance-v1', job_id=config['job_id'],
        configuration=deepcopy(bound.request['configuration']), base_pointer=deepcopy(reference),
        verified_draft=dict(path=pointer['verified_draft_path'],hash=pointer['verified_draft_hash']),
        rubric=deepcopy(config['rubric']['artifact']),
        target=dict(phase=config['target_phase'],mode=config['target_mode']),
        source_request=deepcopy(bound.request_ref),
        source_consumption=_ref(frame['owner'].consumption_path,frame['consumption']),
        source_resolution=deepcopy(resolution))


def validate(frame, packet, entries, reference):
    suite = frame['owner'].proof.reader.suite
    pins(suite);suite.registry.validate(packet, SCHEMA)
    expected = bindings(frame, reference)
    require(all(packet[key] == value for key,value in expected.items()), 'gap acceptance has stale source bindings')
    require(packet['target'] == dict(phase='final',mode='permissive'), 'target forbids rubric-gap acceptance')
    require(all(packet[key].strip() for key in ('decided_by','rationale','decided_at')), 'gap acceptance needs explicit operator attribution')
    require(packet['gaps'] == sorted(packet['gaps'],key=lambda row:row['gap_id']), 'gap selections must be canonical')
    ids = [row['gap_id'] for row in packet['gaps']]
    require(len(ids) == len(set(ids)), 'duplicate accepted gap')
    for chosen in packet['gaps']:
        require(chosen['gap_id'] in entries, 'gap acceptance selects an unknown gap')
        entry = entries[chosen['gap_id']]
        require(entry['gap']['status'] == 'unresolved' and chosen == selection(entry),
                'gap acceptance differs from exact unresolved evidence')


def read_record(frame, reference):
    reader = frame['owner'].proof.reader
    if not supported(getattr(reader,'suite',None)): return None
    pins(reader.suite)
    path = path_for(frame, reference)
    try: raw = reader._read_path(path)
    except FileNotFoundError: return None
    reference = dict(path=path,hash=sha256_bytes(raw))
    return reader.json(reference,SCHEMA), reference


def references(frames, reference):
    if not frames: return []
    reader = frames[-1]['owner'].proof.reader
    ordinal = reader.json(reference,'current_verified_pointer_v1')['promotion_ordinal']
    result = []
    for frame in frames:
        if not frame.get('consumed'): continue
        bases = [frame['bound'].request['base_pointer']]
        resolution = frame.get('resolution')
        if resolution and resolution['committed']:bases.append(resolution['packet']['promoted_pointer'])
        for base in bases:
            if reader.json(base,'current_verified_pointer_v1')['promotion_ordinal'] > ordinal:continue
            record = read_record(frame,base)
            if record is not None:result.append(record[1])
    return result


def apply(entries, records, reference):
    """A changed lineage or changed exact gap makes the old decision inactive."""
    for packet, _ in records:
        if packet['base_pointer'] != reference: continue
        for chosen in packet['gaps']:
            row = entries.get(chosen['gap_id'])
            if row and row['gap']['status'] != 'resolved' and selection(row) == chosen:
                row['gap'].update(status='accepted',blocking_convergence=False)


def bind_manifest(manifest, proof, frames, reference):
    """Hash-bind decisions even when reporting has no successor request."""
    if supported(proof.reader.suite):
        manifest.update(schema_version='vnext-bound-rubric-v2',gap_acceptances=references(frames,reference))


def effective_review(frames, reference):
    from whetstone.vnext_phase2_rubric import retained
    review = deepcopy(frames[-1]['review'])
    gaps = {row['gap_id']:row for row in retained(frames,reference)}
    for row in review.get('rubric_findings',[]): row['gap'] = deepcopy(gaps[row['gap']['gap_id']])
    return review


def blocks(frames, reference, rows):
    from whetstone.vnext_phase2_rubric import retained
    # Declaration disagreement remains independent of accepted source gaps.
    return any(row['blocking_convergence'] for row in retained(frames,reference)) or any(
        'rubric_gaps.json' in row['affected_sections'] for row in rows)
