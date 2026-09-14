from copy import deepcopy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from whetstone.vnext_candidate_validation import assess_candidate
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_contracts import decode_json
from whetstone.vnext_proposals import PreparedProposal
from whetstone.vnext_semantic_coverage import prepare_semantic_obligations, validate_semantic_coverage
import test_vnext_candidate_validation as candidate_tests
from test_vnext_candidate_registry import RegistrationFixture


def digest(value):
    return sha256_bytes(canonical_json_bytes(value))


class SemanticCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidate_tests.CandidateValidationTests.setUpClass()

    def setUp(self):
        self.fixture = candidate_tests.CandidateValidationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def prepare(self, payload=b'Queue MUST wait and report.\n', **kwargs):
        self.inputs = self.fixture.inputs(payload, **kwargs)
        self.assessment = assess_candidate(**self.inputs)
        self.obligations = prepare_semantic_obligations(
            report=self.assessment.report, inventory=self.assessment.inventory, **self.inputs)
        return self.obligations

    def response(self):
        return {
            'schema_version': 'vnext-semantic-coverage-v1',
            'obligations_hash': digest(self.obligations),
            'results': [{'obligation_id': item['obligation_id'], 'obligation_hash': digest(item),
                         'result': 'pass', 'evidence': 'Fictional assessment of the exact bound endpoints.'}
                        for item in self.obligations['obligations']],
        }

    def test_merge_covers_each_required_unit_and_separate_complete_group(self):
        packet = self.prepare()
        rows = self.assessment.report['unit_changes']
        units = [item for item in packet['obligations'] if item['kind'] == 'unit']
        self.assertEqual(len(units), sum(row['semantic_required'] for row in rows))
        self.assertEqual({digest(item['report_rows'][0]) for item in units},
                         {digest(row) for row in rows if row['semantic_required']})
        groups = [item for item in packet['obligations'] if item['kind'] == 'correspondence_group']
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['base_units']), 2)
        self.assertEqual(len(groups[0]['candidate_units']), 1)
        self.assertEqual({item['text'] for item in groups[0]['base_units']},
                         {'Queue MUST wait.\n', 'Queue MUST report.\n'})
        self.assertEqual(groups[0]['candidate_units'][0]['text'], 'Queue MUST wait and report.\n')
        self.assertEqual(validate_semantic_coverage(self.response(), obligations=packet), self.response())

    def test_split_binds_all_successors(self):
        self.fixture.f.base(b'# Queue\n## Timing\nQueue MUST wait and report.\n## Reports\nReport.\n')
        packet = self.prepare(b'Queue MUST wait.\nQueue MUST report.\n')
        group = next(item for item in packet['obligations'] if item['kind'] == 'correspondence_group')
        self.assertEqual((len(group['base_units']), len(group['candidate_units'])), (1, 2))
        self.assertEqual({item['text'] for item in group['candidate_units']},
                         {'Queue MUST wait.\n', 'Queue MUST report.\n'})

    def test_unchanged_one_to_one_explicit_group_still_requires_evidence(self):
        self.fixture.f.base(b'# Queue\n## Timing\nQueue MUST wait.\n## Reports\nReport.\n')
        packet = self.prepare(b'Queue MUST wait.\n')
        group = next(item for item in packet['obligations'] if item['kind'] == 'correspondence_group')
        self.assertEqual((len(group['base_units']), len(group['candidate_units'])), (1, 1))
        response = self.response()
        response['results'] = [row for row in response['results'] if row['obligation_id'] != group['obligation_id']]
        with self.assertRaisesRegex(ValueError, 'omitted'):
            validate_semantic_coverage(response, obligations=packet)

    def test_forged_deterministic_pass_or_suppressed_obligation_refuses(self):
        self.prepare()
        for field, value in [('semantic_required', False), ('candidate_unit_ids', [])]:
            report = deepcopy(self.assessment.report)
            row = next(row for row in report['unit_changes'] if row['semantic_required'])
            row[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'does not reproduce'):
                prepare_semantic_obligations(report=report, inventory=self.assessment.inventory, **self.inputs)
        inputs = self.fixture.inputs(b'Queue SHOULD wait and report.\n')
        assessment = assess_candidate(**inputs)
        with self.assertRaisesRegex(ValueError, 'deterministic pass'):
            prepare_semantic_obligations(report=assessment.report, inventory=assessment.inventory, **inputs)

    def test_repaired_seed_syntax_keeps_a_mandatory_baseline_assessment(self):
        self.fixture.f.base(b'# Queue\n\n## Timing\n```json\n{"enum":["READY" "STOP"]}\n```\n## Reports\nReport.\n')
        packet = self.prepare(b'```json\n{"enum":["READY","STOP"]}\n```\n', graph=False)
        diagnostic = next(item for item in packet['obligations'] if item['kind'] == 'baseline_diagnostics')
        self.assertIn('schema_json_invalid', {item['code'] for item in diagnostic['baseline_diagnostics']})
        self.assertEqual(diagnostic['baseline_diagnostics'], self.assessment.report['baseline_diagnostics'])
        response = self.response()
        response['results'] = [row for row in response['results'] if row['obligation_id'] != diagnostic['obligation_id']]
        with self.assertRaisesRegex(ValueError, 'omitted'):
            validate_semantic_coverage(response, obligations=packet)

    def test_missing_unit_or_group_cannot_hide_behind_aggregate_pass(self):
        self.prepare()
        for kind in ('unit', 'correspondence_group'):
            response = self.response()
            omitted = next(item['obligation_id'] for item in self.obligations['obligations'] if item['kind'] == kind)
            response['results'] = [row for row in response['results'] if row['obligation_id'] != omitted]
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'omitted'):
                validate_semantic_coverage(response, obligations=self.obligations)

    def test_duplicate_foreign_and_stale_endpoint_evidence_refuse(self):
        self.prepare()
        for change, message in [('duplicate', 'duplicate'), ('foreign', 'unknown'), ('endpoint', 'endpoints'), ('packet', 'binding')]:
            response = self.response()
            if change == 'duplicate':
                response['results'].append(deepcopy(response['results'][0]))
            elif change == 'foreign':
                response['results'][0]['obligation_id'] = 'sem_' + 'f' * 64
            elif change == 'endpoint':
                response['results'][0]['obligation_hash'] = 'f' * 64
            else:
                response['obligations_hash'] = 'f' * 64
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                validate_semantic_coverage(response, obligations=self.obligations)

    def test_fail_and_uncertainty_remain_evidence_without_invented_verdict(self):
        self.prepare()
        response = self.response()
        response['results'][0]['result'] = 'uncertain'
        response['results'][1]['result'] = 'fail'
        actual = validate_semantic_coverage(response, obligations=self.obligations)
        self.assertEqual(actual, response)
        self.assertNotIn('verdict', actual)
        actual['results'][0]['result'] = 'pass'
        self.assertEqual(response['results'][0]['result'], 'uncertain')

    def test_blank_evidence_and_extra_claims_refuse(self):
        self.prepare()
        response = self.response()
        response['results'][0]['evidence'] = ' \n\t'
        with self.assertRaisesRegex(ValueError, 'substantive evidence'):
            validate_semantic_coverage(response, obligations=self.obligations)
        response = self.response()
        response['verdict'] = 'pass'
        with self.assertRaises(ValueError):
            validate_semantic_coverage(response, obligations=self.obligations)

    def test_context_and_content_are_deterministic_detached_and_bound(self):
        packet = self.prepare()
        before = canonical_json_bytes(self.inputs['base_inventory'])
        again = prepare_semantic_obligations(report=self.assessment.report,
                                             inventory=self.assessment.inventory, **self.inputs)
        self.assertEqual(packet, again)
        self.assertEqual(packet['bindings']['base_inventory_hash'], digest(self.inputs['base_inventory']))
        self.assertEqual(packet['bindings']['preservation_report_hash'], digest(self.assessment.report))
        endpoint = next(item['base_units'][0] for item in packet['obligations'] if item['base_units'])
        self.assertEqual(sha256_bytes(endpoint['text'].encode()), endpoint['unit']['content_hash'])
        endpoint['unit']['features'].append('Caller mutation')
        self.assertEqual(canonical_json_bytes(self.inputs['base_inventory']), before)
        response = self.response()
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            validate_semantic_coverage(response, obligations=packet)


@unittest.skipUnless(sys.platform == 'darwin', 'D8 first target is macOS/local APFS')
class RegisteredCoverageTests(unittest.TestCase):
    def test_registered_readback_builds_coverage_without_changing_authority(self):
        with TemporaryDirectory() as directory:
            fixture = RegistrationFixture(Path(directory))
            self.addCleanup(fixture.store.close)
            event = fixture.registry.register(**fixture.prepare())
            self.assertEqual(fixture.registry.inspect().latest, event)
            before = {path.relative_to(fixture.root): path.read_bytes()
                      for path in fixture.root.rglob('*') if path.is_file()}
            read = fixture.store.read
            inputs = fixture.load_inputs(read, event['round_number'], event['proposal_id'])
            inputs.pop('review')
            prefix = f"rounds/round-1/proposals/{event['proposal_id']}"
            patch = decode_json(read(prefix + '/proposed_patch.json'))
            proposal = PreparedProposal(patch, {operation['payload']['path']: read(prefix + '/' + operation['payload']['path'])
                                               for operation in patch['operations'] if operation['payload']['path'] is not None})
            candidate_directory = event['candidate_path'].rsplit('/', 1)[0]
            report = decode_json(read(candidate_directory + '/preservation_report.json'))
            packet = prepare_semantic_obligations(
                job=fixture.job, report=report,
                inventory=decode_json(read(candidate_directory + '/preservation_inventory_candidate.json')),
                plan=decode_json(read('rounds/round-1/mutation_plan.json')), proposal=proposal,
                candidate_bytes=read(event['candidate_path']),
                candidate_map=decode_json(read(event['candidate_section_identity_map_path'])),
                candidate_map_path=event['candidate_section_identity_map_path'], **inputs)
            for key in ('candidate_id', 'candidate_hash', 'candidate_section_identity_map_path', 'candidate_section_identity_map_hash'):
                self.assertEqual(packet['bindings'][key], event[key])
            self.assertEqual(fixture.registry.inspect().latest, event)
            after = {path.relative_to(fixture.root): path.read_bytes()
                     for path in fixture.root.rglob('*') if path.is_file()}
            self.assertEqual(after, before)
            initial = decode_json(read(event['initial_disposition_event_path']))
            self.assertEqual(initial['new_disposition'], 'CANDIDATE_UNVERIFIED')


if __name__ == '__main__':
    unittest.main()
