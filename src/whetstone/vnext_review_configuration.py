"""Versioned immutable review selection; focused work is never a full sweep."""
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, decode_json, require, sha256_bytes

ALGORITHM = 'algorithms/vnext_verified_focused_phase1_v1.md'


def schema(review):
    require(isinstance(review, dict), 'review configuration must be an object')
    versions = {'review-configuration-v1': 'review_configuration_v1',
                'review-configuration-v2': 'review_configuration_v2'}
    require(isinstance(review.get('schema_version'), str) and review['schema_version'] in versions,
            'unsupported review configuration version')
    return versions[review['schema_version']]


def focused_profile(review):
    return review['phase1_selection']['profile'] if schema(review) == 'review_configuration_v2' else None


def validate(review, registry):
    registry.validate(review, schema(review))
    selected = focused_profile(review)
    if selected is not None:
        require(review['workflow'] == 'standard' and review['review_mode'] == 'horizontal',
                'focused V selection requires standard horizontal review')
        require(sum(row['name'] == selected for row in review['profiles']) == 1,
                'focused selection must name exactly one configured profile')
        from whetstone.scheduler import profile_names_for_phase
        require(selected in profile_names_for_phase(review['profile_set'], 'phase_1'),
                'focused selection must be a Phase 1 profile of the configured set')
    return review


def read(reader, reference):
    review = reader.json(reference, schema(decode_json(reader.raw(reference))))
    validate(review, reader.suite.registry)
    if focused_profile(review) is not None:
        entries = {row['path']: row['sha256'] for family in ('algorithms', 'schemas')
                   for row in reader.suite.manifest[family]}
        for path in (ALGORITHM, 'schemas/review_configuration_v2.schema.json',
                     'schemas/vnext_verified_phase1_closeout_v2.schema.json',
                     'schemas/technical_failure_report.schema.json', 'schemas/editor_summary.schema.json'):
            require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                    'focused Phase 1 contract is absent or changed', path)
    return review
