from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_native_editor import NativePatchProposalClient, structural_output_schema
from whetstone.vnext_native_verifier import NativeSemanticVerifierClient
from whetstone.vnext_semantic_context import prepare_semantic_context
from whetstone.vnext_semantic_protocol import decode_semantic_response, semantic_verifier_prompt
import test_vnext_proposal_admission as admission_tests
import test_vnext_semantic_context as context_tests
import test_vnext_semantic_protocol as protocol_tests


@unittest.skipUnless(sys.platform == 'darwin', 'Registered fixture uses proposed macOS/APFS kernel')
class NativeVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original = admission_tests.fixtures.UnitPreflightTests.setUp
        def with_native_verifier(test):
            original(test)
            fixture = test.c.f
            fixture.original.review['verifier'] = {'name': 'codex', 'version': 'scripted-1', 'model': 'pinned-verifier'}
            fixture.original.review_ref = fixture.save('inputs/review.json', fixture.original.review)
            fixture.job['review_configuration_hash'] = fixture.original.review_ref['hash']
            fixture.rebind()
        with patch.object(admission_tests.fixtures.UnitPreflightTests, 'setUp', with_native_verifier), \
                patch.object(admission_tests, 'consuming_suite', protocol_tests.semantic_suite):
            context_tests.SemanticContextTests.setUpClass()
        cls.addClassCleanup(context_tests.SemanticContextTests.doClassCleanups)
        cls.context = prepare_semantic_context(**context_tests.SemanticContextTests.arguments)

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def client(self, raw, *, name='codex', timeout=5, delay=0, exit_code=0):
        command = self.root / 'scripted-native'
        record = self.root / 'calls.json'
        command.write_text(f'''#!{sys.executable}
import json,os,sys,time
from pathlib import Path
args=sys.argv[1:]
codex='--output-schema' in args
schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text()) if codex else json.loads(args[args.index('--json-schema')+1])
prompt=sys.stdin.read() if codex else args[args.index('--print')+1]
record=Path({str(record)!r})
calls=json.loads(record.read_text()) if record.exists() else []
calls.append(dict(pid=os.getpid(),args=args,schema=schema,prompt=prompt))
record.write_text(json.dumps(calls))
time.sleep({delay!r})
raw={raw!r}
if codex:
    Path(args[args.index('--output-last-message')+1]).write_bytes(raw)
    print('tokens used\\n17')
else:
    sys.stdout.buffer.write(raw)
sys.exit({exit_code!r})
''')
        command.chmod(0o700)
        review = deepcopy(self.context.packet['review_configuration'])
        review['verifier']['name'] = name
        return NativeSemanticVerifierClient(review=review, command=str(command), cwd=self.root, timeout_seconds=timeout)

    def test_real_scripted_codex_process_verifies_exact_registered_context_without_authority_change(self):
        fixture = context_tests.SemanticContextTests.fixture
        before = {path.relative_to(fixture.root): path.read_bytes() for path in fixture.root.rglob('*') if path.is_file()}
        helper = protocol_tests.SemanticProtocolTests()
        helper.context = self.context
        raw = canonical_json_bytes(helper.response())
        client = self.client(raw)
        self.assertEqual(client.identity, self.context.packet['review_configuration']['verifier'])
        returned = client.verify(semantic_verifier_prompt(self.context))
        result = decode_semantic_response(returned, self.context)
        self.assertEqual(returned, raw)
        self.assertEqual(result.verification['verdict'], 'pass')
        calls = json.loads((self.root / 'calls.json').read_text())
        self.assertEqual(len(calls), 1)
        args = calls[0]['args']
        self.assertEqual(args[args.index('--sandbox') + 1], 'read-only')
        self.assertEqual(args[args.index('--model') + 1], 'pinned-verifier')
        self.assertIn('web_search="disabled"', args)
        self.assertIn('--ephemeral', args)
        self.assertEqual(client.last_telemetry['usage']['total_tokens'], 17)
        after = {path.relative_to(fixture.root): path.read_bytes() for path in fixture.root.rglob('*') if path.is_file()}
        self.assertEqual(after, before)

    def test_editor_and_verifier_with_same_model_use_distinct_processes_prompts_and_schemas(self):
        verifier = self.client(b'{}')
        review = deepcopy(self.context.packet['review_configuration'])
        review['editor'] = deepcopy(review['verifier'])
        editor = NativePatchProposalClient(review=review, command=verifier.command, cwd=self.root)
        editor.propose('Scripted Editor prompt')
        verifier.verify(semantic_verifier_prompt(self.context))
        first, second = json.loads((self.root / 'calls.json').read_text())
        self.assertNotEqual(first['pid'], second['pid'])
        self.assertNotEqual(first['prompt'], second['prompt'])
        self.assertNotEqual(first['schema'], second['schema'])
        self.assertEqual(verifier.transport_binding['verifier'], review['verifier'])
        self.assertNotIn('editor', verifier.transport_binding)

    def test_claude_receives_no_tools_or_session_and_preserves_exact_structured_span(self):
        body = b'{ "schema_version" : "semantic-verification-v2" }'
        client = self.client(b'{"type":"result","is_error":false,"structured_output":' + body + b'}', name='claude-code')
        self.assertEqual(client.verify('Read-only verifier prompt'), body)
        args = json.loads((self.root / 'calls.json').read_text())[0]['args']
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertIn('--no-session-persistence', args)

    def test_timeout_nonzero_and_provider_errors_remain_transport_failures_without_retry(self):
        client = self.client(b'{}', timeout=1, delay=2)
        with self.assertRaises(TimeoutError): client.verify('prompt')
        self.assertTrue(client.last_telemetry['timed_out'])
        self.assertEqual(len(json.loads((self.root / 'calls.json').read_text())), 1)
        client = self.client(b'{}', exit_code=3)
        with self.assertRaises(RuntimeError): client.verify('prompt')
        client = self.client(b'{"type":"result","is_error":true,"result":"scripted error"}', name='claude-code')
        with self.assertRaisesRegex(RuntimeError, 'provider/process'): client.verify('prompt')
        self.assertEqual(len(json.loads((self.root / 'calls.json').read_text())), 3)

    def test_provider_schema_drift_refuses_before_invocation(self):
        provider = self.root / NativeSemanticVerifierClient.provider_schema
        provider.write_text(json.dumps(structural_output_schema(NativeSemanticVerifierClient.canonical_schema,
                                                               NativeSemanticVerifierClient.schema_title)))
        with patch('whetstone.vnext_native_editor.SCHEMA_DIR', self.root):
            client = self.client(b'{}')
            provider.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'schema changed'): client.verify('prompt')
        self.assertFalse((self.root / 'calls.json').exists())


if __name__ == '__main__':
    unittest.main()
