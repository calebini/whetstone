from copy import deepcopy
import sys
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, decode_json, sha256_bytes
from whetstone.vnext_identity import creation_id
from whetstone.vnext_proposal_handoff import register_completed_proposal_request, registry_for_proposal_requests
from whetstone.vnext_proposals import PreparedProposal
from whetstone.vnext_semantic_context import prepare_semantic_context
import test_vnext_proposal_admission as admission_tests
from test_vnext_proposal_requests import Client
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform == 'darwin', 'D8 first target is macOS/local APFS')
class SemanticContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        admission_tests.ProposalAdmissionTests.setUpClass()
        fixture = cls.fixture = admission_tests.ProposalAdmissionTests()
        fixture.setUp()
        cls.addClassCleanup(fixture.doCleanups)
        cls.client = Client()
        fixture.run_request(cls.client)
        event = register_completed_proposal_request(fixture.store, round_number=1,
            load_inputs=fixture.admission.load_inputs, validate_authority=fixture.admission.validate_authority,
            created_at=STAMP)
        cls.registry = registry_for_proposal_requests(fixture.store, load_inputs=fixture.admission.load_inputs,
                                                     validate_authority=fixture.admission.validate_authority)
        if cls.registry.inspect().latest != event:
            raise AssertionError('Registered fixture event failed readback')
        read = fixture.store.read
        prefix = f"rounds/round-1/proposals/{event['proposal_id']}"
        patch = decode_json(read(prefix + '/proposed_patch.json'))
        directory = event['candidate_path'].rsplit('/', 1)[0]
        cls.arguments = dict(
            proposal_inputs=fixture.admission.load_inputs(read, 1),
            proposal=PreparedProposal(patch, {operation['payload']['path']: read(prefix + '/' + operation['payload']['path'])
                                             for operation in patch['operations'] if operation['payload']['path'] is not None}),
            creation=event, creation_ref={'path': 'rounds/candidate_index/creation-1.json',
                                         'hash': sha256_bytes(canonical_json_bytes(event))},
            candidate_bytes=read(event['candidate_path']),
            candidate_map=decode_json(read(event['candidate_section_identity_map_path'])),
            report=decode_json(read(directory + '/preservation_report.json')),
            inventory=decode_json(read(directory + '/preservation_inventory_candidate.json')),
        )

    def inputs(self):
        return deepcopy(self.arguments)

    def test_complete_registered_context_contains_independent_evidence_and_no_writes(self):
        root = self.fixture.root
        before = {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}
        context = prepare_semantic_context(**self.inputs())
        packet = context.packet
        arguments = self.arguments
        self.assertEqual(packet['base'], arguments['proposal_inputs']['base'].decode())
        self.assertEqual(packet['candidate'], arguments['candidate_bytes'].decode())
        self.assertEqual(packet['creation'], arguments['creation'])
        self.assertEqual(packet['creation_ref'], arguments['creation_ref'])
        self.assertEqual(packet['preservation_report'], arguments['report'])
        self.assertEqual(packet['candidate_inventory'], arguments['inventory'])
        self.assertEqual(packet['review_configuration']['verifier'], arguments['proposal_inputs']['review']['verifier'])
        self.assertEqual(packet['editor_proposal']['patch'], arguments['proposal'].patch)
        self.assertIn('untrusted', packet['editor_proposal']['interpretation'])
        admitted = {row['finding_id'] for row in packet['mutation_plan']['finding_dispositions'] if row['admitted_to_editing']}
        self.assertEqual({row['finding_id'] for row in packet['admitted_findings']}, admitted)
        source = packet['admitted_findings'][0]['evidence']['source_items'][0]
        self.assertEqual(source['claim'], arguments['proposal_inputs']['feedback']['feedback'][0]['claim'])
        self.assertEqual(self.client.calls, 1)
        self.assertEqual(self.registry.inspect().latest, arguments['creation'])
        after = {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}
        self.assertEqual(after, before)

    def test_snapshot_is_deterministic_and_nested_mutation_cannot_change_its_hash(self):
        first = prepare_semantic_context(**self.inputs())
        second = prepare_semantic_context(**self.inputs())
        self.assertEqual(first.raw, second.raw)
        self.assertEqual(first.input_hash, sha256_bytes(first.raw))
        packet = first.packet
        packet['editor_proposal']['patch']['editor_claims']['normative_change_summary'] = 'Caller mutation'
        self.assertEqual(first.raw, second.raw)
        self.assertNotEqual(packet, first.packet)

    def test_rehashed_foreign_round_or_transaction_creation_refuses(self):
        for field, value in [('round_number', 2), ('transaction_id', 'txn_' + 'f' * 64),
                             ('proposal_id', 'pro_' + 'f' * 64), ('job_id', 'job_' + 'f' * 64)]:
            arguments = self.inputs()
            event = arguments['creation']
            event[field] = value
            if field == 'round_number':
                event['candidate_path'] = event['candidate_path'].replace('round-1', 'round-2')
                event['candidate_section_identity_map_path'] = event['candidate_section_identity_map_path'].replace('round-1', 'round-2')
            event['creation_event_id'] = creation_id(event)
            arguments['creation_ref']['hash'] = sha256_bytes(canonical_json_bytes(event))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'admitted transaction'):
                prepare_semantic_context(**arguments)

    def test_changed_creation_locator_candidate_or_map_refuses(self):
        for field in ('creation_ref', 'candidate_bytes', 'candidate_map'):
            arguments = self.inputs()
            if field == 'creation_ref':
                arguments[field]['path'] = 'rounds/candidate_index/creation-2.json'
            elif field == 'candidate_bytes':
                arguments[field] += b'Unexpected change.\n'
            else:
                arguments[field]['draft_hash'] = 'f' * 64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'semantic (creation reference|registered candidate)'):
                prepare_semantic_context(**arguments)

    def test_changed_payload_or_report_cannot_enter_a_plausible_context(self):
        for field in ('payload', 'report'):
            arguments = self.inputs()
            if field == 'payload':
                path = next(iter(arguments['proposal'].payloads))
                arguments['proposal'].payloads[path] += b'Unexpected payload.\n'
            else:
                arguments['report']['unit_changes'] = []
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'does not reproduce'):
                prepare_semantic_context(**arguments)

    def test_unbound_context_and_changed_pinned_verifier_refuse(self):
        for field in ('context', 'verifier'):
            arguments = self.inputs()
            if field == 'context':
                arguments['proposal_inputs']['context']['bind_' + 'f' * 64] = b'Undeclared context'
            else:
                arguments['proposal_inputs']['review']['verifier']['model'] = 'unpinned-model'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'dependency context|role configuration'):
                prepare_semantic_context(**arguments)


if __name__ == '__main__':
    unittest.main()
