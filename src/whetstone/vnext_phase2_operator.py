"""Pinned Phase 2 operator integration; no new decision or retry policy."""
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_verified_phase2_operator_v1.md'


def supported(suite):
    return any(row['path'] == ALGORITHM for row in suite.manifest['algorithms'])


def pins(suite):
    entries = {row['path']: row['sha256'] for row in suite.manifest['algorithms']}
    require(ALGORITHM in entries and entries[ALGORITHM] == sha256_bytes(confined_file(CONTRACT_ROOT, ALGORITHM).read_bytes()),
            'Phase 2 operator integration is outside supported suite or changed')
