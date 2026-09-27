"""Bounded closeout after a final scheduled source correction."""
import json
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_source_correction as source
import test_vnext_verified_phase2_signals as signals
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class ReviewOnlyTests(unittest.TestCase):
    setUpClass = source.SourceCorrectionTests.setUpClass
    fixture = source.SourceCorrectionTests.fixture
    files = source.SourceCorrectionTests.files
    reopen = source.SourceCorrectionTests.reopen
    ready = source.SourceCorrectionTests.ready
    reviewed = source.SourceCorrectionTests.reviewed
    review = source.SourceCorrectionTests.review
    promote = source.SourceCorrectionTests.promote
    admitted = source.SourceCorrectionTests.admitted
    candidate = source.SourceCorrectionTests.candidate
    next_client = source.SourceCorrectionTests.next_client
    advance = source.SourceCorrectionTests.advance
    advice = source.SourceCorrectionTests.advice
    clean_start = source.SourceCorrectionTests.clean_start
    final_ready = source.SourceCorrectionTests.final_ready
    config = source.SourceCorrectionTests.config
    source_review = source.SourceCorrectionTests.source_review
    lose = staticmethod(source.SourceCorrectionTests.lose)

    def start(self, **kwargs):
        return source.SourceCorrectionTests.start(self, phase2_review_only_contract=True, **kwargs)

    def corrected(self):
        f, reviewer, client, old, bound, result, consumed = self.source_review()
        f.run.continue_phase2_pass(3, action='advice', advice=self.advice(bound, result))
        f.run.continue_phase2_pass(3, action='admit')
        _, verifier = self.candidate(f, bound.request['round_number'])
        f.run.verify(client=verifier, decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        f.run.publish_phase2_resolutions()
        declaration = f.run.prepare_phase2_declaration()
        clean = self.next_client(reviewer)
        self.advance(f, clean)
        self.assertEqual(f.run.phase2_sequence_status()['gate'], 'review')
        return f, reviewer, client, verifier, clean, declaration

    def test_late_correction_closeout_converges_with_no_editor_or_budget_extension(self):
        f, reviewer, client, verifier, clean, declaration = self.corrected()
        authority = f.store.read('rounds/current_verified.json');draft = f.store.read('spec.md')
        before = f.run.phase2_sequence_status()['profiles']
        bound = f.run.bind_phase2_next_review(clean.transport_binding)
        self.assertEqual(bound.request['schema_version'], 'vnext-phase2-review-request-v5')
        self.assertEqual(bound.request['review_only']['profiles'], ['adversarial'])
        self.assertEqual(bound.request['declaration'], declaration['reference'])
        for action in ('advice', 'admit'):
            with self.assertRaisesRegex(ValueError, 'review-only'):
                f.run.continue_phase2_pass(5, action=action)
        result = f.run.continue_phase2_pass(5, action='execute', client=clean)
        self.assertEqual(result.status, 'complete')
        with patch.object(f.store, 'publish', side_effect=self.lose(f.store.publish, '/consumption.json')):
            with self.assertRaises(OSError):f.run.continue_phase2_pass(5, action='consume')
        self.reopen(f)
        receipt = f.run.continue_phase2_pass(5, action='consume')
        self.assertEqual(receipt['accepted_passes'], 5)
        self.assertEqual(f.run.phase2_sequence_status()['profiles'], before)
        number = bound.request['round_number']
        directory = f'rounds/round-{number}'
        self.assertEqual(json.loads(f.store.read(directory+'/profile_used.yaml'))['round_kind'], 'review_only')
        self.assertEqual(f.store.read(directory+'/draft_before.md'), f.store.read(directory+'/draft_after.md'))
        f.run.reconcile_phase2_findings()
        self.assertEqual(f.run.finish_phase2()['packet']['terminal_state'], 'CONVERGED')
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual(f.store.read('rounds/current_verified.json'), authority)
        self.assertEqual(f.store.read('spec.md'), draft)
        self.assertEqual((reviewer.calls, client.calls, clean.calls, f.editor.calls, verifier.calls), (1, 2, 2, 1, 1))
        self.assertFalse((f.root/'rounds/phase2/review_requests/pass-6').exists())

    def test_closeout_source_finding_halts_and_cannot_select_more_work(self):
        f, reviewer, client, verifier, clean, declaration = self.corrected()
        clean.callback = signals.SignalRuntimeTests.response(self, 'clarify', 'major')
        bound, result, consumed = self.advance(f, clean)
        f.run.reconcile_phase2_findings()
        failure = f.run.finish_phase2()
        self.assertEqual(failure['packet']['terminal_state'], 'TARGET_NOT_REACHED')
        self.assertFalse(failure['phase_complete'])
        self.assertTrue(f.run.reconcile_phase2_state()['halt_complete'])
        report = json.loads(f.store.read(failure['packet']['failure_report']['path']))
        self.assertEqual(report['exit_reason'], 'vnext_phase2_review_only_verification_debt')
        self.assertTrue(report['unresolved_major_issues'])
        before = self.files(f)
        self.assertEqual(f.run.bind_phase2_next_review(clean.transport_binding)['gate'], 'declaration_closeout_required')
        with self.assertRaisesRegex(ValueError, 'review-only'):
            f.run.continue_phase2_pass(5, action='admit')
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.editor.calls, 1)
