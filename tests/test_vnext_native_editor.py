from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_native_editor import NativePatchProposalClient, PROVIDER_SCHEMA, native_output_schema
from whetstone.vnext_unit_protocol import ProposalShapeError, decode_unit_response, exercise_unit_proposal
import test_vnext_unit_preflight as preflight_tests


class NativeEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):preflight_tests.UnitPreflightTests.setUpClass()
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.fixture=preflight_tests.UnitPreflightTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def client(self,name,raw,*,exit_code=0,delay=0,timeout=5):
        command=self.root/'native-client';record=self.root/'arguments.json'
        command.write_text(f'''#!{sys.executable}
import json,sys,time
from pathlib import Path
args=sys.argv[1:]
schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text()) if '--output-schema' in args else json.loads(args[args.index('--json-schema')+1])
Path({str(record)!r}).write_text(json.dumps({{'args':args,'schema':schema,'cwd':str(Path.cwd())}}))
time.sleep({delay!r})
raw={raw!r}
if '--output-last-message' in args:
    sys.stdin.read()
    Path(args[args.index('--output-last-message')+1]).write_bytes(raw)
    print('tokens used\\n23')
else:
    sys.stdout.buffer.write(raw)
sys.exit({exit_code!r})
''')
        command.chmod(0o700)
        review=deepcopy(self.fixture.c.f.original.review);review['editor']={'name':name,'version':'scripted-1','model':'pinned-model'}
        return NativePatchProposalClient(review=review,command=str(command),cwd=self.root,timeout_seconds=timeout)

    def test_codex_receives_read_only_arguments_and_preserves_exact_response(self):
        raw=b'{ "schema_version": "vnext-proposal-response-v2" }\r\n'
        client=self.client('codex',raw)
        self.assertEqual(client.propose('exact prompt'),raw)
        captured=json.loads((self.root/'arguments.json').read_text());args=captured['args']
        self.assertEqual(args[args.index('--sandbox')+1],'read-only')
        self.assertEqual(args[args.index('--model')+1],'pinned-model')
        self.assertIn('web_search="disabled"',args);self.assertIn('--ephemeral',args)
        self.assertEqual(captured['schema'],native_output_schema())
        self.assertEqual(client.last_telemetry['usage']['total_tokens'],23)

    def test_claude_has_no_tools_or_session_and_preserves_structured_token_span(self):
        body=b'{ "schema_version" : "vnext-proposal-response-v2", "patch": {} }'
        raw=b'{"type":"result","is_error":false,"structured_output":'+body+b',"usage":{"input_tokens":2,"output_tokens":3}}'
        client=self.client('claude-code',raw)
        self.assertEqual(client.propose('exact prompt'),body)
        captured=json.loads((self.root/'arguments.json').read_text());args=captured['args']
        self.assertEqual(args[args.index('--tools')+1],'');self.assertIn('--no-session-persistence',args)
        self.assertEqual(Path(captured['cwd']).resolve(),self.root.resolve())
        self.assertEqual(client.last_telemetry['usage']['total_tokens'],5)

    def test_timeout_nonzero_exit_and_provider_error_stay_transport_failures(self):
        client=self.client('codex',b'{}',delay=2,timeout=1)
        with self.assertRaises(TimeoutError):client.propose('prompt')
        self.assertTrue(client.last_telemetry['timed_out'])
        client=self.client('codex',b'{}',exit_code=4)
        with self.assertRaises(RuntimeError):client.propose('prompt')
        self.assertEqual(client.last_telemetry['exit_code'],4)
        client=self.client('claude-code',b'{"type":"result","is_error":true,"result":"authentication failed"}')
        with self.assertRaisesRegex(RuntimeError,'provider/process'):client.propose('prompt')
        self.assertTrue(client.last_telemetry['raw_envelope']['is_error'])

    def test_contract_drift_is_detected_before_any_process_invocation(self):
        provider=self.root/PROVIDER_SCHEMA;provider.write_text(json.dumps(native_output_schema()))
        with patch('whetstone.vnext_native_editor.SCHEMA_DIR',self.root):
            client=self.client('codex',b'{}');provider.write_text('{}')
            with self.assertRaisesRegex(ValueError,'schema changed'):client.propose('prompt')
        self.assertFalse((self.root/'arguments.json').exists())

    def test_native_process_connects_to_pinned_preflight_and_retains_telemetry(self):
        client=self.client('codex',b'{}');f=self.fixture.c.f
        f.original.review['editor']=deepcopy(client.identity)
        f.job['review_configuration_hash']=sha256_bytes(canonical_json_bytes(f.original.review));f.rebind()
        preflight=preflight_tests.prepare_unit_preflight(**self.fixture.inputs())
        response=json.loads(preflight_tests.Client().propose(preflight.prompt));response['patch']['editor']=client.identity
        client=self.client('codex',canonical_json_bytes(response))
        _,proposal,_=exercise_unit_proposal(self.fixture.directory,load_inputs=self.fixture.inputs,client=client)
        self.assertEqual(proposal.patch['editor'],client.identity)
        telemetry=json.loads((self.fixture.directory/'attempts/telemetry-1.json').read_bytes())
        self.assertEqual(telemetry['usage']['total_tokens'],23)
        self.assertFalse((self.fixture.directory/'attempts/invocation-2.json').exists())

    def test_provider_hint_is_structural_and_canonical_validator_retains_value_rules(self):
        schema=native_output_schema();encoded=json.dumps(schema)
        self.assertNotIn('"$ref"',encoded);self.assertNotIn('"x-whetstone"',encoded)
        self.assertNotIn('"uniqueItems"',encoded)
        def check(node):
            if not isinstance(node,dict):return
            if node.get('type')=='object':
                self.assertFalse(node['additionalProperties']);self.assertEqual(set(node['required']),set(node['properties']))
            for value in node.values():
                if isinstance(value,dict):
                    check(value)
                    for item in value.values():check(item)
                if isinstance(value,list):
                    for item in value:check(item)
        check(schema)
        preflight=preflight_tests.prepare_unit_preflight(**self.fixture.inputs())
        arguments=dict(base=self.fixture.c.f.base,section_map=self.fixture.c.f.mapping,editor=self.fixture.c.f.original.review['editor'])
        for raw in (b'not JSON',b'{}',b'{"schema_version":"wrong"}'):
            with self.subTest(raw=raw),self.assertRaises(ProposalShapeError):decode_unit_response(raw,preflight,**arguments)
        response=json.loads(preflight_tests.Client().propose(preflight.prompt))
        response['patch']['base_draft_hash']='f'*64
        with self.assertRaises(ValueError) as caught:decode_unit_response(canonical_json_bytes(response),preflight,**arguments)
        self.assertNotIsInstance(caught.exception,ProposalShapeError)
        response['patch']['base_draft_hash']='not-a-hash'
        with self.assertRaises(ValueError) as caught:decode_unit_response(canonical_json_bytes(response),preflight,**arguments)
        self.assertNotIsInstance(caught.exception,ProposalShapeError)
        for field,value in [('path','../escape.md'),('path','.'),('hash','bad-hash')]:
            response=json.loads(preflight_tests.Client().propose(preflight.prompt))
            response['patch']['operations'][0]['payload'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError) as caught:
                decode_unit_response(canonical_json_bytes(response),preflight,**arguments)
            self.assertNotIsInstance(caught.exception,ProposalShapeError)
        response=json.loads(preflight_tests.Client().propose(preflight.prompt));response['payloads']*=2
        with self.assertRaises(ValueError) as caught:decode_unit_response(canonical_json_bytes(response),preflight,**arguments)
        self.assertNotIsInstance(caught.exception,ProposalShapeError)


if __name__=='__main__':unittest.main()
