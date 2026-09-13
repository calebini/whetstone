"""Offline vNext byte, identity and pinned-suite validation. No runtime admission."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from whetstone.contracts import SchemaRegistry, SchemaValidationError
from whetstone.hashing import canonical_json_dumps

SUITE_SCHEMA_VERSION = 'whetstone-contract-suite-manifest-v1'
JOB_SCHEMA_VERSION = 'job-descriptor-v2'
JOB_DOMAIN = 'whetstone-job-id-v1'
CONTRACT_ROOT = Path(__file__).resolve().parents[2] / 'contracts'
ALGORITHM_VERSIONS = {
    'normalization_version': 'whetstone-canonical-json-v1',
    'parser_contract_version': 'markdown-atx-v1',
    'assembler_version': 'patch-assembler-v1',
    'inventory_version': 'preservation-inventory-v1',
    'semantic_verifier_policy_version': 'semantic-policy-v1',
}


@dataclass
class ContractSuiteError(ValueError):
    path: str
    message: str

    def __str__(self):
        return f'{self.path}: {self.message}'


def require(condition, message, path='$'):
    if not condition:
        raise ContractSuiteError(path, message)


def _json_value(value):
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, str):
        try:
            value.encode('utf-8')
        except UnicodeError as exc:
            raise ContractSuiteError('$', 'invalid Unicode scalar') from exc
        return
    if isinstance(value, list):
        for item in value: _json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str), 'JSON object keys must be strings')
            _json_value(key); _json_value(item)
        return
    raise ContractSuiteError('$', 'vNext canonical JSON permits integers, not floats or non-JSON values')


def canonical_json_bytes(value: Any) -> bytes:
    _json_value(value)
    return canonical_json_dumps(value).encode('utf-8')


def decode_json(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'duplicate JSON key: {key}')
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs)
    except (UnicodeError, ValueError) as exc:
        raise ContractSuiteError('$', f'invalid JSON: {exc}') from exc
    _json_value(value)
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def content_identifier(prefix: str, domain: str, ordered_preimage: list[Any]) -> str:
    require(re.fullmatch(r'[a-z][a-z0-9]*', prefix) is not None, 'invalid ASCII identity prefix')
    require(isinstance(domain, str) and domain.isascii() and bool(domain), 'invalid identity domain')
    return prefix + '_' + sha256_bytes(canonical_json_bytes([domain, *ordered_preimage]))


def derive_job_id(descriptor: dict[str, Any], contract_suite_digest: str) -> str:
    require(re.fullmatch(r'[0-9a-f]{64}', contract_suite_digest) is not None, 'invalid suite digest')
    return content_identifier('job', JOB_DOMAIN, [
        descriptor['schema_version'], descriptor['editing_mode'], descriptor['contract_suite_version'], contract_suite_digest,
        *[descriptor[k] for k in ('parser_contract_version', 'assembler_version', 'inventory_version', 'normalization_version', 'semantic_verifier_policy_version')],
        descriptor['seed_draft']['hash'], descriptor['authority_map_hash'], descriptor['scope_contract_hash'],
        descriptor['protected_invariants_hash'], descriptor['review_configuration_hash'], descriptor['source_spec']['expected_hash'],
    ])


def confined_file(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative) and '\\' not in relative and '\x00' not in relative, 'invalid logical path')
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts and path.as_posix() == relative, 'path must be normalized and relative')
    base = Path(root).resolve()
    target = base
    for part in path.parts:
        target /= part
        require(not target.is_symlink(), 'symlinks are not allowed', relative)
    require(target.is_file() and target.resolve().is_relative_to(base), 'missing or escaping file', relative)
    return target


class VNextSchemaRegistry(SchemaRegistry):
    """Reject unsupported keywords before delegating to the existing validator."""
    KEYWORDS = {'$schema', '$id', '$ref', '$defs', 'title', 'description', 'type', 'properties', 'required',
                'additionalProperties', 'items', 'minItems', 'maxItems', 'uniqueItems', 'minLength',
                'pattern', 'format', 'minimum', 'const', 'enum', 'allOf', 'anyOf', 'if', 'then', 'x-whetstone'}

    def load(self, name):
        filename = name if name.endswith('.json') else name + '.schema.json'
        require(Path(filename).name == filename, 'schema reference must name a package schema')
        if filename not in self._schemas:
            raw = confined_file(self.schema_dir, filename).read_bytes()
            value = decode_json(raw)
            self._audit(value, filename)
            self._qualify_refs(value, filename)
            self._schemas[filename] = value
        return self._schemas[filename]

    def _audit(self, schema, path):
        require(isinstance(schema, dict), 'boolean/invalid schemas are unsupported', path)
        unknown = set(schema) - self.KEYWORDS
        require(not unknown, f'unsupported schema keywords: {sorted(unknown)}', path)
        if 'additionalProperties' in schema:
            if isinstance(schema['additionalProperties'], dict): self._audit(schema['additionalProperties'], path + '/additionalProperties')
            else: require(isinstance(schema['additionalProperties'], bool), 'invalid additionalProperties', path)
        if 'format' in schema:
            require(schema['format'] == 'date-time', 'unsupported schema format', path)
        if '$ref' in schema:
            require(isinstance(schema['$ref'], str) and bool(schema['$ref']), 'invalid schema reference', path)
        for key in ('properties', '$defs'):
            for name, child in schema.get(key, {}).items(): self._audit(child, path + '/' + name)
        for key in ('items', 'if', 'then'):
            if key in schema: self._audit(schema[key], path + '/' + key)
        for key in ('allOf', 'anyOf'):
            for child in schema.get(key, []): self._audit(child, path + '/' + key)

    @staticmethod
    def _qualify_refs(value, filename):
        if isinstance(value, dict):
            if isinstance(value.get('$ref'), str) and value['$ref'].startswith('#'):
                value['$ref'] = filename + value['$ref']
            for child in value.values(): VNextSchemaRegistry._qualify_refs(child, filename)
        elif isinstance(value, list):
            for child in value: VNextSchemaRegistry._qualify_refs(child, filename)

    def _resolve_ref(self, ref):
        filename, _, pointer = ref.partition('#')
        target = self.load(filename)
        if pointer:
            require(pointer.startswith('/'), 'unsupported schema anchor')
            for part in pointer[1:].split('/'):
                key = part.replace('~1', '/').replace('~0', '~')
                require(isinstance(target, dict) and key in target, 'unresolved schema pointer')
                target = target[key]
        return target

    def validate(self, instance, schema_name):
        _json_value(instance)
        super().validate(instance, schema_name)

    @staticmethod
    def _validate_datetime(value, path):
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value) is None:
            raise SchemaValidationError(path, 'expected UTC second-precision timestamp')
        SchemaRegistry._validate_datetime(value, path)

    def _validate(self, instance, schema, path):
        # Python equates True with 1; JSON contract constants do not.
        if 'const' in schema and self._json_key(instance) != self._json_key(schema['const']):
            raise SchemaValidationError(path, 'value differs from const')
        if 'enum' in schema and all(self._json_key(instance) != self._json_key(v) for v in schema['enum']):
            raise SchemaValidationError(path, 'value is not in enum')
        super()._validate(instance, schema, path)
        if isinstance(instance, dict) and isinstance(schema.get('additionalProperties'), dict):
            for key, value in instance.items():
                if key not in schema.get('properties', {}): self._validate(value, schema['additionalProperties'], path + '.' + key)


@dataclass(frozen=True)
class ValidatedSuite:
    version: str
    digest: str
    root: Path
    registry: VNextSchemaRegistry
    manifest: dict[str, Any]


def _refs(value):
    if isinstance(value, dict):
        if '$ref' in value: yield value['$ref'].split('#', 1)[0]
        for child in value.values(): yield from _refs(child)
    elif isinstance(value, list):
        for child in value: yield from _refs(child)


def validate_contract_suite(manifest_path: Path | None = None) -> ValidatedSuite:
    from whetstone.vnext_registry import SUPPORTED_SUITES
    path = Path(manifest_path) if manifest_path is not None else CONTRACT_ROOT / 'suites/vnext-contracts-1.json'
    # Published suites always live at package-root/suites/<version>.json.
    require(path.parent.name == 'suites', 'manifest must be in the logical suites directory')
    root = path.parent.parent.resolve()
    manifest = decode_json(confined_file(root, 'suites/' + path.name).read_bytes())
    registry = VNextSchemaRegistry(root / 'schemas')
    # Bootstrap the manifest shape from the implementation's trusted schema.
    VNextSchemaRegistry().validate(manifest, 'whetstone_contract_suite_manifest_v1')
    body = {k: v for k, v in manifest.items() if k != 'suite_digest'}
    digest = sha256_bytes(canonical_json_bytes(body))
    require(manifest['suite_digest'] == digest, 'manifest canonical digest mismatch')
    require(SUPPORTED_SUITES.get(manifest['suite_version']) == digest, 'unknown suite or registry digest mismatch')
    require(path.name == manifest['suite_version'] + '.json', 'manifest filename/version mismatch')
    all_paths = set()
    for group in ('schemas', 'algorithms', 'fixtures'):
        entries = manifest[group]
        names = [entry['name'] for entry in entries]
        require(names == sorted(set(names)), 'entries must be sorted with unique logical names', group)
        for entry in entries:
            require(entry['path'] not in all_paths, 'one file cannot claim multiple suite roles', entry['path'])
            all_paths.add(entry['path'])
            raw = confined_file(root, entry['path']).read_bytes()
            require(sha256_bytes(raw) == entry['sha256'], 'pinned file digest differs', entry['path'])
    pinned_schemas = {Path(e['path']).name for e in manifest['schemas']}
    for entry in manifest['schemas']:
        require(entry['path'] == 'schemas/' + Path(entry['path']).name, 'schema must be in schemas directory')
        schema = registry.load(Path(entry['path']).name)
        require(set(_refs(schema)) <= pinned_schemas, 'transitive schema reference is not pinned', entry['path'])
        for ref in _refs(schema): registry.load(ref)
    suite = ValidatedSuite(manifest['suite_version'], digest, root, registry, manifest)
    from whetstone.vnext_conformance import check_fixture
    for entry in manifest['fixtures']:
        packet = decode_json(confined_file(root, entry['path']).read_bytes())
        require(packet.get('expected_result') == entry['expected_result'], 'fixture expectation differs from manifest')
        require(entry['kind'] == ('positive' if entry['expected_result'] == 'pass' else 'negative'), 'fixture kind/expectation mismatch')
        check_fixture(packet, registry)
    return suite


def validate_job_descriptor(descriptor: dict[str, Any], suite: ValidatedSuite) -> None:
    require(isinstance(suite, ValidatedSuite), 'a validated supported suite is required, not a caller-provided digest')
    suite = validate_contract_suite(suite.root / 'suites' / (suite.version + '.json'))
    suite.registry.validate(descriptor, 'job_descriptor_v2')
    require(descriptor['contract_suite_version'] == suite.version, 'descriptor suite version mismatch')
    for key, version in ALGORITHM_VERSIONS.items(): require(descriptor[key] == version, 'unsupported algorithm version', key)
    for path, digest in [(descriptor['scope_contract_path'], descriptor['scope_contract_hash']),
                         (descriptor['source_spec']['path'], descriptor['source_spec']['expected_hash'])]:
        require((path is None) == (digest is None), 'nullable path/hash must be paired')
    require(descriptor['job_id'] == derive_job_id(descriptor, suite.digest), 'job deterministic identity mismatch')


class IdentityRegistry:
    """In-memory collision checking, scoped to a job; never an authority store."""
    def __init__(self): self._seen = {}

    def record(self, job_id, identifier, role, preimage):
        raw = canonical_json_bytes(preimage)
        require(re.fullmatch(r'[a-z][a-z0-9]*_[0-9a-f]{64}', identifier) is not None, 'invalid identity grammar')
        require(identifier.rsplit('_', 1)[1] == sha256_bytes(raw), 'identity does not hash its preimage')
        key = (job_id, identifier)
        require(key not in self._seen or self._seen[key] == (role, raw), 'identity collision or ambiguous artifact role')
        self._seen[key] = (role, raw)
