"""Reproduce resolution receipts from already proven Phase 2 promotions.

This module has no mutation authority. The caller supplies an ascending proven
history prefix; a later candidate cannot prove its own admission prerequisites.
"""
from copy import deepcopy

from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes
from whetstone.vnext_phase2_signals import pins as signal_pins
from whetstone.vnext_verified_history import _snapshot
from whetstone.vnext_verified_phase2_binding import _ref

ALGORITHM = 'algorithms/vnext_verified_phase2_resolution_v1.md'
SCHEMA = 'vnext_phase2_resolution_v1'
SUMMARY_SCHEMA = 'vnext_phase2_resolution_summary_v1'
ROOT = 'rounds/phase2/resolutions'
STATE_FIELD = 'vnext_phase2_resolutions'


def supported(proof):
    return any(r['path'] == ALGORITHM for r in proof.reader.suite.manifest['algorithms'])


def pins(proof):
    signal_pins(proof)
    entries = {r['path']: r['sha256'] for family in ('algorithms', 'schemas')
               for r in proof.reader.suite.manifest[family]}
    for path in (ALGORITHM, *('schemas/'+s+'.schema.json' for s in (SCHEMA, SUMMARY_SCHEMA, 'unresolved_issues'))):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'Phase 2 resolution contract is absent or changed', path)


def resolved_findings(semantic, rows, admitted_ids):
    """Exact whole-finding coverage; partial/derived claims cannot clear originals."""
    results = semantic['finding_results']
    identifiers = [r['finding_id'] for r in results]
    require(semantic['verdict'] == 'pass' and results and len(identifiers) == len(set(identifiers))
            and set(identifiers) == set(admitted_ids)
            and all(r['disposition'] == 'resolved' for r in results),
            'resolution requires exact, wholly resolved admitted findings')
    require(set(identifiers) <= {r['issue_id'] for r in rows},
            'resolution cannot substitute a derived or unrelated finding')
    return set(identifiers)


def residual_rows(frames, resolved):
    """Retain observed issues until a verified receipt clears their exact ID."""
    retained = {}
    for frame in frames:
        if not frame.get('consumed'): continue
        for row in frame['review']['feedback']['feedback']:
            retained[row['issue_id']] = deepcopy(row)
        prior = frame.get('resolution')
        if prior is not None and prior['committed']:
            for identifier in prior['resolved_issue_ids']: retained.pop(identifier, None)
    for identifier in resolved: retained.pop(identifier, None)
    return [retained[key] for key in sorted(retained)]


def record(proof, frames, successor, advice):
    """Derive exact immutable bytes; never adopt existing receipt contents."""
    pins(proof)
    frame = frames[-1]; owner = frame['owner']; bound = frame['bound']
    reference = _snapshot(successor)
    require(reference['path'] in proof.bases and successor['previous_verified_pointer_hash'] == bound.request['base_pointer']['hash'],
            'resolution requires this review\'s proven committed promotion')
    creation_ref = dict(path=successor['source_candidate_creation_event_path'], hash=successor['source_candidate_creation_event_hash'])
    creation = proof.reader.json(creation_ref, 'candidate_creation_event_v1')
    require(creation['round_number'] == owner.number, 'resolution promotion belongs to another review')
    decision_ref = dict(path=successor['candidate_verification_path'], hash=successor['candidate_verification_hash'])
    decision = proof.reader.json(decision_ref, 'candidate_verification_v1')
    require(decision['decision_final'] and decision['promotion_permitted']
            and decision['candidate_disposition'] == 'CANDIDATE_VERIFIED'
            and decision['deterministic_result'] == decision['semantic_result'] == 'pass',
            'resolution requires a final passing candidate decision')
    semantic_ref = dict(path=creation['candidate_path'].rsplit('/', 1)[0]+'/semantic_verification.json',
                        hash=decision['semantic_verification_hash'])
    semantic = proof.reader.json(semantic_ref, 'semantic_verification_v2')
    rows = frame['review']['feedback']['feedback']
    admitted = {r['finding_id'] for r in advice['findings'] if r['classification'] == 'editor_fixable'}
    resolved = resolved_findings(semantic, rows, admitted)
    residual = residual_rows(frames, resolved)
    after = proof.values(reference)['base']
    before = proof.values(bound.request['base_pointer'])['base']
    summary = dict(schema_version='vnext-phase2-resolution-summary-v1', round_number=owner.number,
        draft_before_hash=draft_hash(before.decode()), draft_after_hash=draft_hash(after.decode()),
        accepted_or_modified_feedback_ids=sorted({r['feedback_id'] for r in rows if r['issue_id'] in resolved}),
        resolved_issue_ids=sorted(resolved), unresolved_issue_ids=[r['issue_id'] for r in residual])
    unresolved = dict(round_number=owner.number, draft_hash=summary['draft_after_hash'], unresolved_issues=[dict(
        **{k:deepcopy(r[k]) for k in ('issue_id','issue_fingerprint','normalized_severity','affected_sections','claim','in_scope')},
        blocking_acceptance=r['normalized_severity'] in {'major','blocker'}) for r in residual])
    directory = ROOT+f'/pass-{owner.ordinal}'
    assets = {}; refs = {}
    for key, value, schema in (('summary', summary, SUMMARY_SCHEMA), ('unresolved_issues', unresolved, 'unresolved_issues')):
        proof.reader.suite.registry.validate(value, schema)
        path = directory+'/'+key+'.json'; assets[path] = canonical_json_bytes(value); refs[key] = _ref(path, value)
    keys = sorted({r['oscillation_key']['opposition_key'] for r in rows if r['issue_id'] in resolved})
    packet = dict(schema_version='vnext-phase2-resolution-v1', round_number=owner.number,
        configuration=deepcopy(bound.request['configuration']), entry=deepcopy(bound.request['entry']),
        review_request=deepcopy(bound.request_ref), feedback=deepcopy(frame['receipt']['feedback']),
        advice_binding=_ref(owner.binding_path, advice), base_pointer=deepcopy(bound.request['base_pointer']),
        promoted_pointer=reference, candidate_creation=creation_ref, candidate_verification=decision_ref,
        semantic_verification=semantic_ref, source_consumptions=[_ref(f['owner'].consumption_path, f['consumption']) for f in frames],
        previous_resolutions=[f['resolution']['reference'] for f in frames[:-1] if f.get('resolution')],
        reset_opposition_keys=keys, profile_clean=False, phase_complete=False, next_review_authorized=False, **refs)
    proof.reader.suite.registry.validate(packet, SCHEMA)
    ref = _ref(directory+'/commit.json', packet)
    pending = []
    for path, raw in [*assets.items(), (ref['path'], canonical_json_bytes(packet))]:
        observed = owner._optional(path)
        require(observed is None or observed == raw, 'resolution differs from exact evidence replay', path)
        if observed is None: pending.append(path)
    committed = ref['path'] not in pending
    require(not committed or not pending, 'committed resolution lacks dependencies')
    return dict(packet=packet, reference=ref, assets=assets, pending_paths=tuple(pending), committed=committed,
                resolved_issue_ids=sorted(resolved))


def validate_claims(store, frames):
    expected = {f'pass-{f["owner"].ordinal}': f['resolution'] for f in frames if f.get('resolution')}
    try: claims = store.list_directory(ROOT)
    except FileNotFoundError: claims = ()
    for name, kind in claims:
        if name.startswith('.vnext-tmp-'): continue
        require(kind == 'directory' and name in expected, 'unknown Phase 2 resolution claim', name)
        record = expected[name]
        allowed = {p.rsplit('/', 1)[1] for p in (*record['assets'], record['reference']['path'])}
        for leaf, leaf_kind in store.list_directory(ROOT+'/'+name):
            if leaf.startswith('.vnext-tmp-'): continue
            require(leaf_kind == 'file' and leaf in allowed, 'unknown Phase 2 resolution artifact', leaf)
