"""Exact scheduler-owned metadata operations, before candidate verification.

These pure functions confer no scheduler or storage authority. A consuming
owner must validate the bound transition under its fence. Legacy stamping is
deliberately unchanged.
"""
from copy import deepcopy
from dataclasses import dataclass
import re

from whetstone.hashing import normalize_draft
from whetstone.versioning import promoted_phase2_version, stamped_round_version
from whetstone.vnext_contracts import canonical_json_bytes, content_identifier, require, sha256_bytes


ASSEMBLER = 'patch-assembler-v3'
ALGORITHM = 'algorithms/vnext_version_operations_v1.md'
VERSION = re.compile(r'(?<![\w.])v?(?P<number>[0-9]+(?:\.[0-9]+){0,2})(?![\w.]|\.[0-9])')


@dataclass(frozen=True)
class Anchor:
    kind: str
    start: int
    end: int
    version: str


def anchors(raw):
    """Return supported anchors in precedence order, excluding fenced examples.

    Offsets identify UTF-8 bytes, not Unicode character positions. Metadata is
    restricted to the preamble/title body, before the first non-title section.
    """
    text = raw.decode('utf-8')
    result = []; statuses = []; offset = 0; fence = None; frontmatter = False
    lines = text.splitlines(keepends=True)
    root_seen = False; content_section = False
    for index, line in enumerate(lines):
        stripped = line.rstrip('\r\n')
        if index == 0 and stripped == '---':
            frontmatter = True; offset += len(line.encode()); continue
        if frontmatter and stripped in {'---', '...'}:
            frontmatter = False; offset += len(line.encode()); continue
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', stripped)
        if not frontmatter and marker:
            mark = marker.group(1)
            if fence is None: fence = (mark[0], len(mark))
            elif mark[0] == fence[0] and len(mark) >= fence[1] and not stripped[marker.end():].strip(): fence = None
            offset += len(line.encode()); continue
        if fence is not None:
            offset += len(line.encode()); continue
        heading = re.match(r'^ {0,3}(#{1,6})[ \t]+(.*)', stripped) if not frontmatter else None
        kind = None; start = 0
        if heading:
            if len(heading.group(1)) == 1 and not root_seen and not content_section:
                root_seen = True; kind = 'heading'; start = heading.start(2)
            else: content_section = True
        if not content_section:
            field = re.match(r'^Version:[ \t]+', stripped)
            status = re.match(r'^Status:[ \t]+', stripped)
            if field: kind = 'frontmatter' if frontmatter else 'version'; start = field.end()
            elif status:
                kind = 'status'; start = status.end()
                accepted = re.match(r'Accepted\b', stripped[start:])
                if accepted:
                    left = offset + len(stripped[:start].encode())
                    statuses.append((left, left + len('Accepted')))
        if kind:
            matches = list(VERSION.finditer(stripped, start))
            # Multiple numeric labels in a candidate anchor are ambiguous.
            require(len(matches) <= 1, 'ambiguous numeric version anchor')
            if matches:
                match = matches[0]
                left = offset + len(stripped[:match.start('number')].encode())
                right = offset + len(stripped[:match.end('number')].encode())
                result.append(Anchor(kind, left, right, match.group('number')))
        offset += len(line.encode())
    require(not frontmatter, 'unterminated version frontmatter')
    require(len({a.version for a in result}) <= 1, 'conflicting numeric version anchors')
    rank = {'frontmatter': 0, 'version': 1, 'heading': 2, 'status': 3}
    return tuple(sorted(result, key=lambda a: (rank[a.kind], a.start))), tuple(statuses)


def project(base, proposed, *, phase, transition):
    """Compute an exact metadata-only edit over the unnormalized proposal.

    Editor additions/removals/version/status edits are rejected, never restored.
    Synchronize all agreeing supported anchors; adjacent bytes are copied intact.
    """
    require(phase in {'phase_1', 'phase_2'}, 'invalid metadata phase')
    require(transition in {'round', 'phase2_entry'}, 'invalid metadata transition')
    require(transition != 'phase2_entry' or (phase == 'phase_2' and base == proposed),
            'entry metadata requires an unchanged Phase 1 base')
    old, old_status = anchors(base); current, statuses = anchors(proposed)
    require([(a.kind, a.version) for a in old] == [(a.kind, a.version) for a in current]
            and len(old_status) == len(statuses), 'Editor changed protected version/status anchors')
    mutated = normalize_draft(base.decode()) != normalize_draft(proposed.decode())
    before = old[0].version if old else ''
    after = before
    if before and (mutated or transition == 'phase2_entry'):
        after = promoted_phase2_version(before) if transition == 'phase2_entry' else stamped_round_version(before, phase=phase)
    edits = []
    if before != after:
        edits.extend(dict(start=a.start, end=a.end, before=a.version, after=after, kind='version') for a in current)
    if mutated and phase == 'phase_1':
        edits.extend(dict(start=start, end=end, before='Accepted', after='Draft', kind='status') for start, end in statuses)
    edits.sort(key=lambda e: e['start'])
    cursor = 0; pieces = []
    for edit in edits:
        require(cursor <= edit['start'] < edit['end'] <= len(proposed), 'overlapping system metadata spans')
        require(proposed[edit['start']:edit['end']] == edit['before'].encode(), 'system metadata preimage changed')
        pieces.extend((proposed[cursor:edit['start']], edit['after'].encode())); cursor = edit['end']
    pieces.append(proposed[cursor:])
    return b''.join(pieces), dict(before=before, after=after, edits=edits)


def plan_context(*, phase, transition, source, base_pointer):
    """A hash binding only; the caller must prove the referenced scheduler gate."""
    require(phase in {'phase_1', 'phase_2'} and transition in {'round', 'phase2_entry'}, 'invalid system metadata context')
    require(transition != 'phase2_entry' or phase == 'phase_2', 'entry phase differs')
    for ref in (source, base_pointer):
        require(isinstance(ref, dict) and set(ref) == {'path', 'hash'}
                and isinstance(ref['path'], str) and bool(ref['path'])
                and isinstance(ref['hash'], str) and re.fullmatch('[0-9a-f]{64}', ref['hash']) is not None,
                'invalid system metadata authority reference')
    return dict(phase=phase, transition=transition, source=deepcopy(source), base_pointer=deepcopy(base_pointer))


def validate_context(plan):
    context = plan['system_metadata']
    require(context == plan_context(**context), 'system metadata context differs')
    return context


def operation(base, proposed, plan):
    context = validate_context(plan)
    final, version = project(base, proposed, phase=context['phase'], transition=context['transition'])
    packet = dict(schema_version='vnext-version-operation-v1', operation_id='',
        job_id=plan['job_id'], transaction_id=plan['transaction_id'], authority=deepcopy(context),
        base_hash=sha256_bytes(base), input_hash=sha256_bytes(proposed), output_hash=sha256_bytes(final),
        canonical_input_hash=sha256_bytes(normalize_draft(proposed.decode()).encode()),
        candidate_hash=sha256_bytes(normalize_draft(final.decode()).encode()), **version)
    packet['operation_id'] = content_identifier('op', 'whetstone-system-version-operation-v1',
                                              [{k:v for k,v in packet.items() if k != 'operation_id'}])
    from whetstone.vnext_contracts import VNextSchemaRegistry
    VNextSchemaRegistry().validate(packet, 'vnext_version_operation_v1')
    return final, packet


def pins(suite):
    from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file
    paths = {ALGORITHM, 'schemas/mutation_plan_v4.schema.json', 'schemas/vnext_version_operation_v1.schema.json'}
    entries = {r['path']:r for family in ('algorithms','schemas') for r in suite.manifest[family]}
    for path in paths:
        require(path in entries and sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == entries[path]['sha256'],
                'version operation contract absent or changed', path)
