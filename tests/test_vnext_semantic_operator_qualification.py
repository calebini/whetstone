from copy import deepcopy
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from whetstone.vnext_semantic_operator_cli import validate_operator_cli
from whetstone import vnext_proposal_cli as routing
import test_vnext_semantic_cli as semantic_cli
import test_vnext_semantic_followup_workflow as workflow


class SemanticOperatorQualificationTests(unittest.TestCase):
    def test_every_followup_consumer_contract_is_required(self):
        original = workflow.consuming_suite
        def extended(*args, **options):
            options['additional_algorithms'] += ('vnext_semantic_operator_cli_v1',)
            return original(*args, **options)
        with TemporaryDirectory() as directory, patch.object(workflow, 'consuming_suite', extended):
            suite, _, _ = workflow.workflow_suite(self, directory)
            validate_operator_cli(suite)
            for family, path in [('algorithms','algorithms/vnext_semantic_operator_cli_v1.md'),
                    ('algorithms','algorithms/vnext_semantic_followup_workflow_v1.md'),
                    ('algorithms','algorithms/vnext_semantic_followup_admission_v1.md'),
                    ('schemas','schemas/vnext_semantic_followup_input_v1.schema.json'),
                    ('schemas','schemas/vnext_semantic_followup_selection_v1.schema.json')]:
                manifest = deepcopy(suite.manifest)
                manifest[family] = [row for row in manifest[family] if row['path'] != path]
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'outside supported suite'):
                    validate_operator_cli(SimpleNamespace(manifest=manifest))

    def test_qualified_but_incomplete_suite_refuses_before_fresh_root_or_adapters(self):
        semantic_cli.cli_tests.ProposalCLITests.setUpClass()
        subject = semantic_cli.fixture(self)
        with patch.dict(routing.QUALIFIED_SEMANTIC_FOLLOWUP_SUITES,
                        {subject.suite.version:subject.suite.digest}), \
                patch.object(routing, '_client', side_effect=AssertionError('No adapter before contract validation')) as client:
            code, packet = subject.invoke('vnext-admit', package=True)
        self.assertEqual(code, 2)
        self.assertFalse(subject.root.exists())
        self.assertEqual(packet['terminal_state'], 'CONFIG_INVALID')
        client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
