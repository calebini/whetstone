"""Exact body retention without invoking live clients."""
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone.clients import (
    ClientInvocationResult, CodexEditorClient, ClaudeCodeEditorClient, ProcessEditorClient,
    _claude_response_bytes, _run_codex_exec,
)
from whetstone.config import parse_preservation_bridge, load_config, OrchestratorConfig
from whetstone.contracts import SchemaValidationError
from whetstone.preservation_runtime import readback, guard_consumer
from whetstone.preservation_contracts import BridgeContractError


class RawClientTests(unittest.TestCase):
    def test_adapters_return_malformed_body_without_normalization(self):
        raw=b'{ "draft_after_content": "body", "draft_after_hash": "incorrect" }\r\n'
        for client, transport in ((CodexEditorClient(),'_run_codex_exec'),(ClaudeCodeEditorClient(),'_run_claude_print')):
            with patch('whetstone.clients.'+transport,return_value=ClientInvocationResult({}, {}, raw)) as call:
                self.assertEqual(client.revise_raw('fixture'),raw)
                self.assertTrue(call.call_args.kwargs['raw'])
                self.assertEqual(call.call_count,1)

    def test_codex_output_file_retains_invalid_utf8_and_crlf(self):
        raw=b'{invalid\xff\r\n'
        def process(args, **kwargs):
            Path(args[args.index('--output-last-message')+1]).write_bytes(raw)
            return subprocess.CompletedProcess(args,0,'','')
        with patch('whetstone.clients._run_client_process',side_effect=process):
            result=_run_codex_exec(command='fixture',prompt='fixture',cwd=Path('.'),schema_path=Path('unused'),model=None,raw=True)
        self.assertEqual(result.raw_response,raw)

    def test_claude_structured_token_span_is_not_reserialized(self):
        body='{ "draft_after_content" : "é\\r\\n", "draft_after_hash":"wrong" }'
        envelope='{"usage":{}, "structured_output": '+body+'}\r\n'
        self.assertEqual(_claude_response_bytes(envelope),body.encode())
        decoded=' {malformed response\r\n'
        self.assertEqual(_claude_response_bytes(json.dumps({'result':decoded})),decoded.encode())
        for invalid in (envelope+'junk',b'\xff', '{"structured_output":{},"structured_output":{}}'):
            self.assertEqual(_claude_response_bytes(invalid),invalid if isinstance(invalid,bytes) else invalid.encode())

    def test_process_adapter_uses_binary_body(self):
        body=b'broken\xff\r\n'
        with patch('whetstone.clients.subprocess.run',return_value=subprocess.CompletedProcess([],0,body,b'')) as process:
            self.assertEqual(ProcessEditorClient('fixture').revise_raw('prompt'),body)
            self.assertEqual(process.call_args.kwargs['input'],b'prompt')


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.value={'mode':'enforce','capability_version':'preservation-bridge-v1',
                    'allowed_change_surface':{'path':'surface.json','sha256':'a'*64}}

    def test_closed_ref_and_version_grammar(self):
        self.assertEqual(parse_preservation_bridge(self.value).allowed_change_surface,self.value['allowed_change_surface'])
        invalid=[{**self.value,'bypass':True},{**self.value,'mode':'report_only'},
                 {**self.value,'capability_version':'vNext'},{**self.value,'allowed_change_surface':{'path':'../escape','sha256':'a'*64}},
                 {**self.value,'allowed_change_surface':{'path':'surface.json','sha256':'wrong'}}]
        for value in invalid:
            with self.assertRaises((ValueError,SchemaValidationError)):parse_preservation_bridge(value)

    def test_missing_marker_cannot_downgrade_enforced_state(self):
        rounds=self.root/'rounds';rounds.mkdir()
        (rounds/'run_state.json').write_text(json.dumps({'preservation_bridge':{'mode':'enforce'}}))
        with self.assertRaisesRegex(ValueError,'CONFIG_INVALID'):load_config(self.root/'orchestrator_config.yaml')
        with self.assertRaises(BridgeContractError):guard_consumer(self.root)

    def test_public_config_remains_unavailable_until_full_qualification(self):
        config=self.root/'orchestrator_config.yaml'
        config.write_text('preservation_bridge:\n  mode: enforce\n  capability_version: preservation-bridge-v1\n')
        with self.assertRaisesRegex(ValueError,'qualification is incomplete'):load_config(config)


if __name__=='__main__':unittest.main()
