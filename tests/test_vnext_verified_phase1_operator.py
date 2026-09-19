"""Internal operator status/state integration with real V journals and scripted clients."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_phase1_operator import STATE_FIELD, STATE_PATH
import test_vnext_verified_review as runtime
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedPhase1OperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    promote = runtime.VerifiedReviewTests.promote
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def inspect(self, f):
        before = self.files(f)
        result = f.run.operator_status()
        self.assertEqual(self.files(f), before)
        self.assertFalse(result.phase2_permitted)
        self.assertFalse(result.apply_back_permitted)
        self.assertFalse(result.resume_permitted)
        return result

    def state(self, f, **extra):
        value = json.loads(f.store.read(STATE_PATH))
        value.update(extra)
        (f.root / STATE_PATH).write_bytes(canonical_json_bytes(value))
        return value

    def clean(self):
        f, client = self.start(operator_status_contract=True)
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        return f, client

    def test_only_committed_closeout_selects_terminal_and_projection_preserves_legacy_fields(self):
        f, client = self.clean()
        original = self.state(f, terminal_state='OLD_TERMINAL', ready_for_phase_2=True,
                              custom={'retain': [1, 2]}, last_accepted_draft_hash='old')
        authority = f.store.read('rounds/current_verified.json')
        status = self.inspect(f)
        self.assertIsNone(status.terminal_report)
        self.assertEqual(status.next_action, 'finish_phase1')
        expected = f.run.phase1_closeout()
        publish = f.store.publish
        def interrupt(token, path, value):
            if path == expected.evidence_ref['path']: raise OSError('evidence not committed')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'not committed'): f.run.finish_phase1()
        self.assertIsNone(self.inspect(f).terminal_report)
        before = self.files(f)
        self.assertEqual(f.run.reconcile_phase1_state().outcome, 'phase1_state_synchronized')
        self.assertEqual(self.files(f), before)  # State recovery cannot finish closeout.
        final = f.run.finish_phase1()
        status = self.inspect(f)
        self.assertEqual(status.terminal_report, final.report)
        self.assertFalse(status.state_current)
        self.assertEqual(status.next_action, 'reconcile_phase1_state')
        recovered = f.run.reconcile_phase1_state()
        self.assertEqual(recovered.outcome, 'phase1_state_synchronized')
        self.assertTrue(recovered.value.state_current)
        self.assertEqual(json.loads(f.store.read(STATE_PATH)), {**original, STATE_FIELD: final.evidence_ref})
        self.assertEqual(self.inspect(f).next_action, 'phase1_complete')
        before = self.files(f)
        self.reopen(f)
        self.assertTrue(f.run.reconcile_phase1_state().value.state_current)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.store.read('rounds/current_verified.json'), authority)
        self.assertEqual(client.calls, 1)

    def test_stale_cached_success_and_newest_report_cannot_close_an_unreviewed_run(self):
        f, client = self.start(operator_status_contract=True)
        path = 'rounds/terminal_reports/zzzz-stale-success.json'
        (f.root / path).parent.mkdir(parents=True, exist_ok=True)
        (f.root / path).write_bytes(b'{"terminal_state":"PHASE_1_STABLE"}')
        original = self.state(f, **{STATE_FIELD: {'path': path, 'hash': '0' * 64},
                                   'terminal_state': 'PHASE_1_STABLE', 'ready_for_phase_2': True})
        view = self.inspect(f)
        self.assertIsNone(view.terminal_report)
        self.assertFalse(view.accepted)
        self.assertTrue(view.stale_state)
        self.assertEqual(view.next_action, 'reconcile_phase1_state')
        before = self.files(f)
        recovered = f.run.reconcile_phase1_state()
        self.assertEqual(recovered.value.next_action, 'review')
        original.pop(STATE_FIELD)
        self.assertEqual(json.loads(f.store.read(STATE_PATH)), original)
        after = self.files(f)
        self.assertEqual({k:v for k,v in before.items() if k != STATE_PATH},
                         {k:v for k,v in after.items() if k != STATE_PATH})
        self.assertEqual(client.calls, 0)

    def test_promoted_budget_failure_overrides_stale_success_and_preserves_report_history(self):
        f, client = self.start(operator_status_contract=True, budget=1)
        self.review(f, client)
        verifier = self.promote(f)
        self.state(f, **{STATE_FIELD: {'path': 'rounds/phase1_closeouts/stale.json', 'hash': '0' * 64},
                        'terminal_state': 'PHASE_1_STABLE'})
        final = f.run.finish_phase1()
        before = self.files(f)
        view = self.inspect(f)
        self.assertEqual(view.terminal_report['terminal_state'], 'TARGET_NOT_REACHED')
        self.assertEqual(view.terminal_report['latest_candidate']['disposition'], 'CANDIDATE_PROMOTED')
        self.assertEqual(view.closeout_ref, final.evidence_ref)
        self.assertTrue(view.stale_state)
        f.run.reconcile_phase1_state()
        after = self.files(f)
        self.assertEqual({k:v for k,v in before.items() if k != STATE_PATH},
                         {k:v for k,v in after.items() if k != STATE_PATH})
        self.assertEqual((client.calls, f.editor.calls, verifier.calls), (1, 1, 1))

    def test_final_state_interruption_and_visible_lost_ack_require_full_barrier_replay(self):
        for after_write in (False, True):
            with self.subTest(after_write=after_write):
                f, client = self.clean()
                final = f.run.finish_phase1()
                materialize = f.store.materialize
                def stop(token, path, raw, **options):
                    if path != STATE_PATH: return materialize(token, path, raw, **options)
                    if after_write: materialize(token, path, raw, **options)
                    raise OSError('state interruption')
                with patch.object(f.store, 'materialize', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'state interruption'): f.run.reconcile_phase1_state()
                self.reopen(f)
                self.assertEqual(self.inspect(f).state_current, after_write)
                sync = f.store.synchronize_existing
                observed = []
                def fail_evidence(token, path, **options):
                    observed.append(path)
                    if path == final.evidence_ref['path']: raise OSError('evidence barrier')
                    return sync(token, path, **options)
                with patch.object(f.store, 'synchronize_existing', side_effect=fail_evidence):
                    with self.assertRaisesRegex(OSError, 'evidence barrier'): f.run.reconcile_phase1_state()
                self.assertIn(final.report_ref['path'], observed)
                # A matching state must also synchronize after the source/evidence barriers.
                observed.clear()
                def fail_final_state(token, path, **options):
                    if path == STATE_PATH and final.evidence_ref['path'] in observed:
                        raise OSError('final state barrier')
                    observed.append(path)
                    return sync(token, path, **options)
                if after_write:
                    with patch.object(f.store, 'synchronize_existing', side_effect=fail_final_state):
                        with self.assertRaisesRegex(OSError, 'final state barrier'): f.run.reconcile_phase1_state()
                self.assertTrue(f.run.reconcile_phase1_state().value.state_current)
                self.assertEqual(client.calls, 1)

    def test_source_barrier_failure_and_damaged_committed_artifacts_refuse_without_state_write(self):
        f, client = self.clean()
        final = f.run.finish_phase1()
        receipt = final.evidence['review_receipts'][0]['receipt']['path']
        publish = f.store.publish
        def stop(token, path, value):
            if path == receipt: raise OSError('source barrier')
            return publish(token, path, value)
        before = self.files(f)
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'source barrier'): f.run.reconcile_phase1_state()
        self.assertEqual(self.files(f), before)
        f.run.reconcile_phase1_state()
        for reference in (final.report_ref, final.evidence_ref):
            path = f.root / reference['path']
            raw = path.read_bytes()
            path.write_bytes(b'{}')
            before = self.files(f)
            with self.assertRaises(ValueError): f.run.operator_status()
            with self.assertRaises(ValueError): f.run.reconcile_phase1_state()
            self.assertEqual(self.files(f), before)
            path.write_bytes(raw)
        (f.root / final.report_ref['path']).unlink()
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'missing its report'): f.run.reconcile_phase1_state()
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 1)

    def test_mirror_recovery_precedes_projection_and_ends_invocation(self):
        f, client = self.clean()
        final = f.run.finish_phase1()
        (f.root / STATE_PATH).unlink()
        view = self.inspect(f)
        self.assertEqual(view.work_outcome, 'materialization_required')
        self.assertIsNone(view.terminal_report)
        self.assertIsNone(view.accepted)
        self.assertIsNone(view.state_current)
        self.assertEqual(f.run.reconcile_phase1_state().outcome, 'materialization_recovered')
        self.assertNotIn(STATE_FIELD, json.loads(f.store.read(STATE_PATH)))
        self.assertEqual(self.inspect(f).closeout_ref, final.evidence_ref)
        self.assertTrue(f.run.reconcile_phase1_state().value.state_current)
        self.assertEqual(client.calls, 1)

    def test_missing_pin_and_malformed_state_refuse_before_writes(self):
        f, client = self.start(closeout_contract=True)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'operator status contract'): f.run.operator_status()
        with self.assertRaisesRegex(ValueError, 'operator status contract'): f.run.reconcile_phase1_state()
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 0)
        f, client = self.start(operator_status_contract=True)
        (f.root / STATE_PATH).write_bytes(b'[]')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'JSON object'): f.run.operator_status()
        with self.assertRaisesRegex(ValueError, 'JSON object'): f.run.reconcile_phase1_state()
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 0)
