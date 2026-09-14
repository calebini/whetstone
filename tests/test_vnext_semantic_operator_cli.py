from contextlib import redirect_stdout
from io import StringIO
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone.cli import main
from whetstone import vnext_proposal_cli as routing
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_proposal_run import open_proposal_run
import test_vnext_semantic_followup_workflow as workflow


class SemanticOperatorCommandBoundaryTests(unittest.TestCase):
    def test_commands_on_absent_root_refuse_before_clients_or_root_creation(self):
        from pathlib import Path
        with TemporaryDirectory() as directory:
            root = Path(directory)/'absent'
            cases = [('vnext-semantic-answers', []),
                ('vnext-semantic-answer', ['--input', str(root/'answer.json')]),
                ('vnext-semantic-followup', ['--answer-receipt', 'receipt.json', '--answer-hash', 'f'*64])]
            with patch.object(routing, '_client', side_effect=AssertionError('No clients')) as client:
                for command, options in cases:
                    out = StringIO()
                    with self.subTest(command=command), redirect_stdout(out):
                        code = main([command, '--root', str(root), '--candidate', 'can_'+'f'*64, *options])
                    self.assertEqual(code, 2)
                    self.assertEqual(json.loads(out.getvalue())['vnext']['reason_code'], 'vnext_root_incompatible')
                    self.assertFalse(root.exists())
                client.assert_not_called()


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class SemanticOperatorCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow.SemanticFollowupWorkflowTests.setUpClass()

    def setUp(self):
        factory = workflow.workflow_suite
        def cli_suite(test, directory):
            original = workflow.consuming_suite
            def extended(*args, **options):
                options['additional_algorithms'] += ('vnext_semantic_operator_cli_v1',)
                return original(*args, **options)
            with patch.object(workflow, 'consuming_suite', extended):
                return factory(test, directory)
        owner = workflow.SemanticFollowupWorkflowTests()
        self.addCleanup(owner.doCleanups)
        with patch.object(workflow, 'workflow_suite', cli_suite):
            owner.setUp()
        self.owner = owner
        self.subject = owner.subject
        self.root = self.subject.fixture.root
        suite = self.subject.fixture.suite
        for mapping in (routing.QUALIFIED_PROPOSAL_SUITES, routing.QUALIFIED_SEMANTIC_SUITES,
                        routing.QUALIFIED_SEMANTIC_FOLLOWUP_SUITES):
            p = patch.dict(mapping, {suite.version: suite.digest});p.start();self.addCleanup(p.stop)
        p = patch.object(routing, 'open_proposal_run',
                         side_effect=lambda root: open_proposal_run(root, suite_path=self.subject.fixture.path))
        p.start();self.addCleanup(p.stop)
        p = patch.object(routing, '_client', side_effect=AssertionError('Operator commands must not construct clients'))
        self.clients = p.start();self.addCleanup(p.stop)

    def invoke(self, command, *args):
        out = StringIO()
        with redirect_stdout(out):
            code = main([command, '--root', str(self.root), '--candidate', self.subject.identifier,
                         '--vnext-round', '1', *args])
        return code, json.loads(out.getvalue())

    def test_qualified_commands_keep_answers_separate_from_selection_and_invoke_no_clients(self):
        before = self.owner.files()
        with patch.dict(routing.QUALIFIED_SEMANTIC_FOLLOWUP_SUITES, {}, clear=True):
            code, packet = self.invoke('vnext-semantic-answers')
        self.assertEqual((code, packet['vnext']['reason_code']), (2, 'vnext_gate_unavailable'))
        self.assertEqual(self.owner.files(), before)
        code, packet = self.invoke('vnext-semantic-answers')
        self.assertEqual(code, 0, packet)
        self.assertEqual(len(packet['semantic_answers']['answers']), 1)
        self.assertEqual(self.owner.files(), before)
        source = workflow.SemanticAnswerSource(self.owner.store, admission=self.owner.run.router,
                                              candidate_id=self.subject.identifier)
        answer = workflow.admission.answers.input_for(source)
        answer['rationale'] = 'A second explicit answer does not select a transaction.'
        path = self.root.parent/'command-answer.json'
        path.write_bytes(canonical_json_bytes(answer))
        code, preview = self.invoke('vnext-semantic-answer', '--input', str(path), '--dry-run')
        self.assertEqual(code, 0, preview)
        self.assertEqual(self.owner.files(), before)
        code, submitted = self.invoke('vnext-semantic-answer', '--input', str(path))
        self.assertEqual(code, 0, submitted)
        self.assertEqual(submitted['semantic_answer'], preview['semantic_answer'])
        self.assertIsNone(self.owner.run.committed_selection(self.owner.store.read, 1))
        reference = submitted['semantic_answer']['reference']
        before = self.owner.files()
        code, packet = self.invoke('vnext-semantic-followup', '--answer-receipt', reference['path'],
                                   '--answer-hash', 'f'*64)
        self.assertEqual(code, 2)
        self.assertEqual(self.owner.files(), before)
        code, packet = self.invoke('vnext-semantic-answers', '--vnext-round', '2')
        self.assertEqual(code, 2)
        self.assertEqual(self.owner.files(), before)
        code, packet = self.invoke('vnext-semantic-followup', '--answer-receipt', reference['path'],
                                   '--answer-hash', reference['hash'])
        self.assertEqual(code, 0, packet)
        self.assertEqual(packet['proposal_status']['processing_gate'], 'proposal')
        self.assertEqual(packet['proposal_status']['request_status'], 'not_started')
        self.assertEqual(self.owner.run.committed_selection(self.owner.store.read, 1), packet['semantic_followup'])
        self.clients.assert_not_called()
        self.assertEqual((self.subject.editor.calls, self.subject.client.calls), (1, 1))


if __name__ == '__main__':
    unittest.main()
