"""Declaration-stage corrections retain ordinary budget and verified lineage."""
from copy import deepcopy
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_closeout as closeout
import test_vnext_verified_phase2_signals as signals
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_phase2_source_correction import source_findings
from vnext_fixtures import STAMP


class SourceRulesTests(unittest.TestCase):
    def test_only_whole_source_findings_can_enter_correction(self):
        packet = signals.SignalRulesTests.feedback(self)
        row = packet['feedback'][0]
        row.update(in_scope=True, normalized_severity='major', authority_impact=None,
                   determinism_impact=None, invariant_violated=None, rubric_impact=None)
        row['affected_sections'] = ['source']
        bound = SimpleNamespace(inputs={'base_map': {'sections': [{'canonical_section_id': 'source'}]}})
        self.assertTrue(source_findings(bound, {'feedback': packet}))
        variants = [dict(affected_sections=[]), dict(affected_sections=['convergence_declaration.md']),
                    dict(affected_sections=['source', 'convergence_declaration.md']),
                    dict(rubric_impact='gap'), dict(invariant_violated='INV-1'),
                    dict(normalized_severity='minor'), dict(in_scope=False)]
        for change in variants:
            changed = deepcopy(packet);changed['feedback'][0].update(change)
            with self.subTest(change=change):
                self.assertFalse(source_findings(bound, {'feedback': changed}))


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class SourceCorrectionTests(unittest.TestCase):
    setUpClass = closeout.Phase2CloseoutTests.setUpClass
    fixture = closeout.Phase2CloseoutTests.fixture
    files = closeout.Phase2CloseoutTests.files
    reopen = closeout.Phase2CloseoutTests.reopen
    ready = closeout.Phase2CloseoutTests.ready
    reviewed = closeout.Phase2CloseoutTests.reviewed
    review = closeout.Phase2CloseoutTests.review
    promote = closeout.Phase2CloseoutTests.promote
    admitted = closeout.Phase2CloseoutTests.admitted
    candidate = closeout.Phase2CloseoutTests.candidate
    next_client = closeout.Phase2CloseoutTests.next_client
    advance = closeout.Phase2CloseoutTests.advance
    advice = closeout.Phase2CloseoutTests.advice
    clean_start = closeout.Phase2CloseoutTests.clean_start
    final_ready = closeout.Phase2CloseoutTests.final_ready
    lose = staticmethod(closeout.Phase2CloseoutTests.lose)

    def start(self, **kwargs):
        return closeout.Phase2CloseoutTests.start(self, phase2_source_correction_contract=True, **kwargs)

    def config(self, f):
        config = closeout.Phase2CloseoutTests.config(self, f)
        config['profiles'][2]['budget'] = 2
        return config

    def source_review(self):
        f, reviewer, client, package = self.final_ready()
        client.callback = signals.SignalRuntimeTests.response(self, 'clarify', 'major')
        bound, result, consumed = self.advance(f, client)
        return f, reviewer, client, package, bound, result, consumed

    def test_source_correction_regenerates_declaration_and_requires_current_profile_reviews(self):
        f, reviewer, client, old, bound, result, consumed = self.source_review()
        self.assertEqual(bound.request['schema_version'], 'vnext-phase2-review-request-v4')
        self.assertEqual(consumed['schema_version'], 'vnext-phase2-consumption-v4')
        self.assertEqual(f.run.phase2_sequence_status()['gate'], 'operator_or_advice_required')
        old_bytes = {ref['path']: f.store.read(ref['path']) for ref in
                     [old['reference'], old['declaration']['declaration']]}
        f.run.continue_phase2_pass(3, action='advice', advice=self.advice(bound, result))
        ref = f.run.continue_phase2_pass(3, action='admit')
        self.assertEqual(json.loads(f.store.read(ref['path']))['base_pointer'], bound.request['base_pointer'])
        _, verifier = self.candidate(f, bound.request['round_number'])
        self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        f.run.promote(prepared_at=STAMP)
        self.assertEqual(f.run.phase2_sequence_status()['gate'], 'resolution_publication_required')
        f.run.publish_phase2_resolutions()
        self.reopen(f)
        new = f.run.prepare_phase2_declaration()
        self.assertNotEqual(new['reference'], old['reference'])
        self.assertNotEqual(new['declaration']['current_verified_pointer'], old['declaration']['current_verified_pointer'])
        self.assertEqual(new['declaration']['counts'], {'blockers': 0, 'major_issues': 0, 'rubric_gaps': 0})
        clean = self.next_client(reviewer)
        following, _, _ = self.advance(f, clean)
        self.assertEqual(following.request['step']['rounds_used'], 1)
        self.assertEqual(following.request['declaration'], new['reference'])
        self.assertEqual(f.run.phase2_sequence_status()['clean_profiles'], ['convergence_strict_check'])
        blocked = f.run.phase2_closeout()
        self.assertFalse(blocked['phase_complete'])
        self.assertIn('current_profile_verification_missing', blocked['blockers'])
        for path, raw in old_bytes.items(): self.assertEqual(f.store.read(path), raw)
        self.assertEqual((reviewer.calls, client.calls, clean.calls, f.editor.calls, verifier.calls), (1, 2, 1, 1, 1))

    def test_declaration_disagreement_cannot_be_admitted_as_source(self):
        f, reviewer, client, _ = self.final_ready()
        callback = signals.SignalRuntimeTests.response(self, 'clarify', 'major')
        def response(owner, packet):
            packet = json.loads(callback(owner, packet))
            packet['feedback'][0]['affected_sections'].append('convergence_declaration.md')
            return canonical_json_bytes(packet)
        client.callback = response
        self.advance(f, client)
        before = self.files(f)
        self.assertEqual(f.run.phase2_sequence_status()['gate'], 'declaration_closeout_required')
        for action in ('advice', 'admit'):
            with self.assertRaisesRegex(ValueError, 'wholly source correction'):
                f.run.continue_phase2_pass(3, action=action)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.editor.calls, 0)
