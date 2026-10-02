"""The rubric envelope retains the complete Phase 2 native review shape."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_vnext_native_editor import NativeEditorTests
from whetstone.vnext_contracts import CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes, sha256_bytes
from whetstone.vnext_native_phase2_reviewer import NativePhase2ReviewerClient, phase2_output_schema


class NativePhase2ReviewerTests(unittest.TestCase):
    setUpClass = NativeEditorTests.setUpClass
    setUp = NativeEditorTests.setUp

    def test_both_transports_are_read_only_raw_and_bind_canonical_response(self):
        for name, runner in [('codex','_run_codex_exec'),('claude-code','_run_claude_print')]:
            review = deepcopy(self.fixture.c.f.original.review)
            review['reviewer'] = dict(name=name,version='fixture',model='fixture')
            client = NativePhase2ReviewerClient(review=review,cwd=self.root)
            packet = dict(review=dict(round_number=1,profile='convergence_strict_check',
                reviewer=review['reviewer'],draft_hash='a'*64,feedback=[]),rubric_findings=[],classifications=[])
            VNextSchemaRegistry().validate(packet, 'vnext_phase2_rubric_response_v2')
            raw = canonical_json_bytes(packet)
            with patch('whetstone.vnext_native_editor.'+runner,
                       return_value=SimpleNamespace(raw_response=raw,telemetry={})) as call:
                self.assertEqual(client.review('fixture prompt'), raw)
                self.assertTrue(call.call_args.kwargs['raw'])
                self.assertEqual(call.call_count,1)
            self.assertEqual(client.transport_binding['output_schema_hash'],sha256_bytes(
                (CONTRACT_ROOT/'schemas/vnext_phase2_rubric_response_v2.schema.json').read_bytes()))
        shape = phase2_output_schema()['properties']['review']
        self.assertEqual(phase2_output_schema(), json.loads(
            (CONTRACT_ROOT/'schemas/vnext_phase2_rubric_response_v2.codex.schema.json').read_bytes()))
        self.assertIn('classifications', phase2_output_schema()['required'])
        self.assertIn('feedback',shape['required'])
        self.assertFalse(shape['additionalProperties'])
        self.assertIn('oscillation_key',shape['properties']['feedback']['items']['properties'])

    def test_timeout_is_one_attempt_owned_by_the_journal(self):
        review = deepcopy(self.fixture.c.f.original.review)
        review['reviewer'] = dict(name='codex',version='fixture',model='fixture')
        client = NativePhase2ReviewerClient(review=review,cwd=self.root)
        with patch('whetstone.vnext_native_editor._run_codex_exec',side_effect=TimeoutError('fixture')) as call:
            with self.assertRaises(TimeoutError):client.review('fixture prompt')
        self.assertEqual(call.call_count,1)
