"""Versioned Phase 1 closeout consumption at the Phase 2 boundary."""
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, decode_json, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_verified_phase2_routes_v1.md'


def supported(suite):
    return any(r['path'] == ALGORITHM for r in suite.manifest['algorithms'])


def pins(suite):
    from whetstone.vnext_phase2_targets import pins as target_pins
    target_pins(suite)
    entries = {r['path']: r['sha256'] for family in ('algorithms', 'schemas') for r in suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/vnext_phase2_configuration_v3.schema.json'):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'Phase 2 route contract is absent or changed', path)


def first_round(proof, entry):
    reference = entry['phase1_closeout']
    schema = 'vnext_verified_phase1_closeout_v1'
    if supported(proof.reader.suite):
        pins(proof.reader.suite)
        version = decode_json(proof.reader.raw(reference))['schema_version']
        versions = {'vnext-verified-phase1-closeout-v1': schema,
                    'vnext-verified-phase1-closeout-v3': 'vnext_verified_phase1_closeout_v3',
                    'vnext-verified-phase1-closeout-v4': 'vnext_verified_phase1_closeout_v4'}
        require(version in versions, 'Phase 2 requires a complete Phase 1 closeout')
        schema = versions[version]
    closeout = proof.reader.json(reference, schema)
    require(closeout['accepted'] and not closeout['unclean_profiles'] and not closeout.get('focused_profile'),
            'Phase 2 cannot consume partial or focused-only Phase 1')
    # Prerequisite replay proves the exact journal and synthetic-round boundary.
    return closeout.get('round_number', max(r['round_number'] for r in closeout['review_receipts'])) + 1
