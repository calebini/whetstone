"""Focused V scheduling uses real journals and injected local clients."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class FocusedPhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    promote = runtime.VerifiedReviewTests.promote
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def focused(self, *, profile='structural_integrity', budget=2, **options):
        return self.start(focused_profile=profile, focused_contract=True,
            status_contract=True, phase2_entry_contract=True, profiles=[
                {'name': 'structural_integrity', 'budget': budget},
                {'name': 'determinism', 'budget': 3}], **options)

    def test_selected_profile_cleanliness_is_never_full_phase1_or_phase2_entry(self):
        f, client = self.focused(profile='determinism')
        self.assertEqual(f.run.review_status().profile, 'determinism')
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        view = f.run.phase1_status()
        self.assertEqual(view.focused_profile, 'determinism')
        self.assertEqual([p.profile for p in view.profiles], ['determinism'])
        self.assertFalse(view.all_profiles_clean)
        self.assertTrue(view.focused_profile_clean)
        self.assertEqual(json.loads(f.store.read('rounds/round-1/profile_used.yaml'))['profile'], 'determinism')
        self.assertEqual(f.store.read('rounds/round-1/draft_before.md'), f.store.read('rounds/round-1/draft_after.md'))
        self.assertEqual(json.loads(f.store.read('rounds/round-1/editor_summary.json'))['resolved_issue_ids'], [])
        result = f.run.finish_phase1()
        self.assertEqual(result.report['terminal_state'], 'FOCUSED_PROFILE_STABLE')
        self.assertFalse(result.accepted)
        f.run.reconcile_phase1_state()
        state = json.loads(f.store.read('rounds/run_state.json'))
        self.assertFalse(state['ready_for_phase_2'])
        self.assertEqual(state['terminal_state'], 'FOCUSED_PROFILE_STABLE')
        eligible = f.run.phase2_eligibility()
        self.assertFalse(eligible.phase1_prerequisites_met)
        self.assertIn('focused_profile_is_not_full_phase1', eligible.phase1_blockers)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'complete Phase 1 prerequisites'):
            f.run.bind_phase2_entry({})
        self.assertEqual(self.files(f), before)
        self.reopen(f)
        self.assertEqual(f.run.finish_phase1(), result)
        self.assertEqual(client.calls, 1)

    def test_verified_promotion_requires_selected_profile_rereview_and_retains_history(self):
        f, client = self.focused()
        original = f.store.read('spec.md')
        self.review(f, client)
        self.assertFalse(f.run.phase1_closeout().accepted)
        verifier = self.promote(f)
        self.reopen(f)
        status = f.run.phase1_status()
        self.assertFalse(status.focused_profile_clean)
        self.assertEqual(status.profiles[0].rounds_used, 1)
        self.assertEqual(status.selected_profile, 'structural_integrity')
        self.assertEqual(f.store.read('rounds/round-1/draft_before.md'), original)
        self.assertEqual(f.store.read('rounds/round-1/draft_after.md'), f.store.read('spec.md'))
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client).status, 'complete')
        final = f.run.finish_phase1()
        self.assertEqual(final.report['terminal_state'], 'FOCUSED_PROFILE_STABLE')
        self.assertEqual(final.report['latest_candidate']['disposition'], 'CANDIDATE_PROMOTED')
        self.assertFalse(final.accepted)
        self.assertEqual((client.calls, f.editor.calls, verifier.calls), (2, 1, 1))
        self.assertEqual(f.run.review_next(client=client).status, 'review_complete')
        self.assertEqual(client.calls, 2)

    def test_exhaustion_after_promotion_reports_only_focused_debt_and_recovers_state(self):
        f, client = self.focused(budget=1)
        self.review(f, client)
        self.promote(f)
        expected = f.run.phase1_closeout()
        publish = f.store.publish
        def lose_report(token, path, value):
            result = publish(token, path, value)
            if path == expected.technical_failure_ref['path']: raise OSError('focused report acknowledgement lost')
            return result
        with patch.object(f.store, 'publish', side_effect=lose_report):
            with self.assertRaisesRegex(OSError, 'report acknowledgement lost'): f.run.finish_phase1()
        self.reopen(f)
        result = f.run.finish_phase1()
        self.assertEqual(result.report['terminal_state'], 'PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS')
        report = result.technical_failure
        self.assertFalse(report['ready_for_phase_2'])
        self.assertEqual(report['profile_status']['unverified_profiles'], ['structural_integrity'])
        self.assertEqual([p['profile'] for p in report['profile_status']['profiles']], ['structural_integrity'])
        self.assertFalse((f.root/'rounds/technical_failure_report.json').exists())
        mirror = f.root/'rounds/technical_failure_report.json'
        mirror.write_bytes(b'unowned report')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'unowned focused failure'):
            f.run.reconcile_phase1_state()
        self.assertEqual(self.files(f), before)
        mirror.unlink()
        state_path = 'rounds/run_state.json'
        materialize = f.store.materialize
        def lose_ack(token, path, raw, **options):
            result = materialize(token, path, raw, **options)
            if path == state_path: raise OSError('focused final state acknowledgement lost')
            return result
        with patch.object(f.store, 'materialize', side_effect=lose_ack):
            with self.assertRaisesRegex(OSError, 'acknowledgement lost'): f.run.reconcile_phase1_state()
        self.reopen(f)
        self.assertTrue(f.run.reconcile_phase1_state().value.state_current)
        self.assertEqual(json.loads(f.store.read('rounds/technical_failure_report.json')), report)
        self.assertEqual(f.run.finish_phase1(), result)
        self.assertFalse(f.run.phase2_eligibility().phase1_prerequisites_met)
        self.assertEqual(f.run.review_next(client=client).status, 'budget_exhausted')
        self.assertEqual(client.calls, 1)
        # A committed fixed-path closeout cannot silently select a rewritten report.
        altered = dict(report, generated_at='2025-01-01T00:00:00Z')
        (f.root/result.technical_failure_ref['path']).write_bytes(canonical_json_bytes(altered))
        with self.assertRaisesRegex(ValueError, 'evidence conflicts'): f.run.operator_status()

    def test_closeout_publication_and_round_receipt_lost_ack_are_client_free_recovery(self):
        f, client = self.focused()
        client.callback = clean_response
        publish = f.store.publish
        def lose_receipt(token, path, value):
            result = publish(token, path, value)
            if path.endswith('/result.json'): raise OSError('receipt acknowledgement lost')
            return result
        with patch.object(f.store, 'publish', side_effect=lose_receipt):
            with self.assertRaisesRegex(OSError, 'receipt acknowledgement lost'): f.run.review_next(client=client)
        self.reopen(f)
        self.assertEqual(f.run.review_next().status, 'review_complete')
        expected = f.run.phase1_closeout()
        publish = f.store.publish
        def lose_closeout(token, path, value):
            result = publish(token, path, value)
            if path == expected.evidence_ref['path']: raise OSError('closeout acknowledgement lost')
            return result
        with patch.object(f.store, 'publish', side_effect=lose_closeout):
            with self.assertRaisesRegex(OSError, 'closeout acknowledgement lost'): f.run.finish_phase1()
        self.reopen(f)
        self.assertTrue(f.run.finish_phase1().materialized)
        f.run.reconcile_phase1_state()
        self.assertEqual(client.calls, 1)

    def test_timeout_and_shape_retry_keep_request_budget_across_reopen(self):
        f, client = self.focused()
        def timeout(_): raise TimeoutError('focused Reviewer timeout')
        client.callback = timeout
        self.assertEqual(f.run.review_next(client=client).status, 'timeout')
        self.assertEqual(client.calls, 1)
        self.assertEqual(f.run.phase1_status().profiles[0].rounds_used, 0)
        self.reopen(f)
        self.assertEqual(f.run.review_next(client=client).status, 'continuation_required')
        client.callback = lambda _: b'{}'
        self.assertEqual(f.run.review_next(client=client, continuation=True).status, 'attempts_exhausted')
        self.reopen(f)
        client.callback = clean_response
        self.assertEqual(f.run.review_next(client=client, continuation=True).status, 'attempts_exhausted')
        self.assertEqual(client.calls, 2)
        self.assertFalse(f.run.phase2_eligibility().phase1_prerequisites_met)
        g, other = self.focused()
        other.callback = lambda p: b'{}' if other.calls == 1 else clean_response(p)
        self.assertEqual(g.run.review_next(client=other).status, 'complete')
        self.assertEqual(other.calls, 2)
        self.assertEqual(g.run.phase1_status().profiles[0].rounds_used, 1)

    def test_source_drift_and_round_artifact_tampering_refuse_without_new_authority(self):
        f, client = self.focused()
        ref = f.run._record['review_configuration']
        source = f.root/ref['path']; original = source.read_bytes()
        def drift(packet):
            source.write_bytes(original+b' ')
            return clean_response(packet)
        client.callback = drift
        with self.assertRaises(ValueError): f.run.review_next(client=client)
        self.assertFalse(list(f.root.glob('rounds/client_requests/*/result.json')))
        source.write_bytes(original)
        self.reopen(f)
        self.assertEqual(f.run.review_next(continuation=True).status, 'complete')
        self.assertEqual(client.calls, 1)
        path = f.root/'rounds/round-1/profile_used.yaml'
        path.write_bytes(b'{}')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'focused round evidence'): f.run.finish_phase1()
        self.assertEqual(self.files(f), before)

    def test_single_profile_configuration_still_cannot_grant_phase2_and_unselected_request_refuses(self):
        f, client = self.start(focused_profile='structural_integrity', focused_contract=True,
            status_contract=True, phase2_entry_contract=True)
        client.callback = clean_response
        f.run.review_next(client=client)
        f.run.finish_phase1(); f.run.reconcile_phase1_state()
        self.assertFalse(f.run.phase2_eligibility().phase1_prerequisites_met)
        g, _ = self.focused()
        from whetstone.vnext_verified_review_requests import _ReviewInputs, _VerifiedReviewRequest
        proof = g.run._history()._prove(g.store.read)
        before = self.files(g)
        with self.assertRaisesRegex(ValueError, 'immutable focused selection'):
            _VerifiedReviewRequest(_ReviewInputs(proof.store, proof, proof.latest), 1, 'determinism')
        self.assertEqual(self.files(g), before)

    def test_missing_pin_and_invalid_selection_refuse_before_runtime_work(self):
        with self.assertRaisesRegex(ValueError, 'focused Phase 1 contract'):
            self.start(focused_profile='structural_integrity')
        with self.assertRaisesRegex(ValueError, 'exactly one configured profile'):
            self.start(focused_profile='not_a_profile', focused_contract=True)
        with self.assertRaisesRegex(ValueError, 'standard horizontal'):
            self.start(focused_profile='structural_integrity', focused_contract=True, mode='vertical')
        with self.assertRaisesRegex(ValueError, 'must be a Phase 1 profile'):
            self.start(focused_profile='convergence_strict_check', focused_contract=True,
                profiles=[dict(name='convergence_strict_check', budget=1)])


    def test_out_of_focus_major_remains_global_debt_without_falsifying_focused_cleanliness(self):
        f, client = self.focused()
        def outside(packet):
            packet['feedback']['feedback'][0]['in_scope'] = False
            packet['classifications'][0]['classification'] = 'deferable'
            return canonical_json_bytes(packet)
        client.callback = outside
        f.run.review_next(client=client)
        final = f.run.finish_phase1()
        self.assertEqual(final.report['terminal_state'], 'FOCUSED_PROFILE_STABLE')
        self.assertFalse(final.accepted)
        self.assertTrue(final.global_blocking_findings)
        self.assertFalse(f.run.phase2_eligibility().phase1_prerequisites_met)

    def test_final_ownership_loss_and_source_barriers_cannot_report_success(self):
        from whetstone.vnext_local_storage import OwnershipLost
        f, client = self.focused()
        client.callback = clean_response
        f.run.review_next(client=client)
        closeout = f.run.phase1_closeout()
        receipt = closeout.evidence['review_receipts'][0]['receipt']['path']
        publish = f.store.publish
        def block_source(token, path, value):
            if path == receipt: raise OSError('focused source barrier')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=block_source):
            with self.assertRaisesRegex(OSError, 'source barrier'): f.run.finish_phase1()
        self.assertFalse((f.root/closeout.evidence_ref['path']).exists())
        f.run.finish_phase1()
        materialize = f.store.materialize
        def lose_owner(token, path, raw, **options):
            result = materialize(token, path, raw, **options)
            if path == 'rounds/run_state.json': f.store._invalidate()
            return result
        with patch.object(f.store, 'materialize', side_effect=lose_owner):
            with self.assertRaises(OwnershipLost): f.run.reconcile_phase1_state()
        self.reopen(f)
        self.assertTrue(f.run.reconcile_phase1_state().value.state_current)
        self.assertEqual(client.calls, 1)


class ReviewConfigurationTests(unittest.TestCase):
    def test_malformed_version_dispatch_has_a_contract_error(self):
        from whetstone.vnext_review_configuration import schema
        for value in (None, [], {}, {'schema_version': 2}, {'schema_version': []}, {'schema_version': 'future'}):
            with self.subTest(value=value), self.assertRaises(ValueError): schema(value)

    def test_v1_cannot_silently_gain_selection_and_v2_requires_valid_phase1_selection(self):
        from whetstone.vnext_contracts import VNextSchemaRegistry
        from whetstone.vnext_review_configuration import validate
        role = dict(name='fictional', version='1', model='fixture')
        original = dict(schema_version='review-configuration-v1', workflow='standard', review_mode='horizontal',
            profile_set='stateful_system', profiles=[dict(name='structural_integrity', budget=1)],
            reviewer=role, editor=role, verifier=role)
        registry = VNextSchemaRegistry()
        self.assertEqual(validate(original, registry), original)
        selected = dict(original, phase1_selection=dict(kind='focused', profile='structural_integrity'))
        with self.assertRaises(ValueError): validate(selected, registry)
        selected['schema_version'] = 'review-configuration-v2'
        self.assertEqual(validate(selected, registry), selected)
