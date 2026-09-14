from copy import deepcopy
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, decode_json
from whetstone.vnext_proposal_handoff import register_completed_proposal_request
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_protocol import POLICY_VERSION
from vnext_consuming_suite_fixture import consuming_suite
from vnext_fixtures import STAMP
from test_vnext_proposal_requests import Client
import test_vnext_proposal_admission as admission_tests
import test_vnext_semantic_protocol as protocol_tests


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local kernel targets macOS/APFS')
class SemanticAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        admission_tests.ProposalAdmissionTests.setUpClass()

    def fixture(self, factory=protocol_tests.semantic_suite):
        fixture = admission_tests.ProposalAdmissionTests()
        with patch.object(admission_tests, 'consuming_suite', factory):
            fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        client = Client()
        fixture.run_request(client)
        event = register_completed_proposal_request(fixture.store, round_number=1,
            load_inputs=fixture.admission.load_inputs, validate_authority=fixture.admission.validate_authority,
            created_at=STAMP)
        return fixture, event, client

    def test_registered_context_is_reproduced_without_new_client_or_authority_writes(self):
        fixture, event, client = self.fixture()
        before = {path.relative_to(fixture.root): path.read_bytes() for path in fixture.root.rglob('*') if path.is_file()}
        context = load_registered_semantic_context(fixture.store, admission=fixture.admission, candidate_id=event['candidate_id'])
        self.assertEqual(context.packet['creation'], event)
        self.assertEqual(context.packet['job']['semantic_verifier_policy_version'], POLICY_VERSION)
        self.assertEqual(context.packet['base_pointer'], fixture.f.pointer_ref)
        self.assertEqual(client.calls, 1)
        after = {path.relative_to(fixture.root): path.read_bytes() for path in fixture.root.rglob('*') if path.is_file()}
        self.assertEqual(after, before)
        repeated = load_registered_semantic_context(fixture.store, admission=fixture.admission, candidate_id=event['candidate_id'])
        self.assertEqual(context.raw, repeated.raw)

    def test_registered_proposal_suite_cannot_infer_semantic_support_from_installed_files(self):
        fixture, event, client = self.fixture(consuming_suite)
        with self.assertRaisesRegex(ValueError, 'unsupported semantic verifier policy'):
            load_registered_semantic_context(fixture.store, admission=fixture.admission, candidate_id=event['candidate_id'])
        self.assertEqual(client.calls, 1)

    def test_semantic_policy_without_consuming_algorithm_or_schema_refuses(self):
        def missing_algorithms(test, directory):
            return consuming_suite(test, directory,
                additional_schemas=('semantic_verification_client_v2', 'semantic_verification_client_v2.codex',
                                    'semantic_verification_v2', 'vnext_semantic_authority_request_v1', 'vnext_semantic_obligations_v1'),
                algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})
        def missing_schemas(test, directory):
            return consuming_suite(test, directory, algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})
        for factory, reason in ((missing_algorithms, 'consumer algorithm'), (missing_schemas, 'consumer schema')):
            with self.subTest(reason=reason):
                fixture, event, client = self.fixture(factory)
                with self.assertRaisesRegex(ValueError, reason):
                    load_registered_semantic_context(fixture.store, admission=fixture.admission, candidate_id=event['candidate_id'])
                self.assertEqual(client.calls, 1)

    def test_foreign_candidate_and_tampered_report_refuse_without_repair(self):
        fixture, event, client = self.fixture()
        with self.assertRaisesRegex(ValueError, 'exact committed registration'):
            load_registered_semantic_context(fixture.store, admission=fixture.admission, candidate_id='can_' + 'f' * 64)
        path = event['candidate_path'].rsplit('/', 1)[0] + '/preservation_report.json'
        original = fixture.store.read
        report = decode_json(original(path))
        altered = deepcopy(report)
        altered['unit_changes'] = []
        def tampered(name):
            return canonical_json_bytes(altered) if name == path else original(name)
        with patch.object(fixture.store, 'read', side_effect=tampered):
            with self.assertRaisesRegex(ValueError, 'differs from independent replay'):
                load_registered_semantic_context(fixture.store, admission=fixture.admission, candidate_id=event['candidate_id'])
        self.assertEqual(decode_json(original(path)), report)
        self.assertEqual(client.calls, 1)


if __name__ == '__main__':
    unittest.main()
