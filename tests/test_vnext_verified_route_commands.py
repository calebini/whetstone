"""Finite Q1 route qualification through real CLI owners and scripted clients."""
import json
import sys
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_run import open_verified_run
from test_vnext_proposal_requests import Client as Editor
from test_vnext_verified_selected_execution import accepting_verifier
from vnext_q1_command_fixtures import CommandCase


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires macOS/APFS')
class RouteCommands(CommandCase):
    def configure(self, *, mode='horizontal', focused=None, versioned=False, workflow='standard'):
        review = self.f.original.review
        review.update(review_mode=mode, workflow=workflow, profiles=[
            dict(name='structural_integrity', budget=2), dict(name='determinism', budget=2)])
        if focused:
            review.update(schema_version='review-configuration-v2',
                          phase1_selection=dict(kind='focused', profile=focused))
        self.f.original.review_ref = self.f.save('inputs/review.json', review)
        self.f.job['review_configuration_hash'] = self.f.original.review_ref['hash']
        if versioned:
            self.f.base = self.f.base.replace(b'# Queue\n', b'# Queue 0.17\nStatus: Accepted v0.17\n')
        self.f.rebind()
        self.fixture.package.update(job_descriptor=self.f.job_ref, review_configuration=self.f.original.review_ref)
        self.fixture.package['mutation_constraints'] = self.f.save(self.fixture.constraint_ref['path'],
            dict(schema_version='vnext-mutation-constraints-v1', constraints=self.f.constraints))
        self.fixture.save_package()
        self.config['vnext_input_package']['hash'] = sha256_bytes((self.fixture.source/'proposal_package.json').read_bytes())
        self.save_config()
        self.qualify()
        self.patch('whetstone.live_phase2.LivePhase2Runner', side_effect=AssertionError('legacy executor'))
        self.patch('whetstone.cli.LivePhase2Runner', side_effect=AssertionError('legacy CLI executor'))

    def stage_target(self, phase='final', mode='strict', review_mode='horizontal'):
        self.stage_phase2()
        with open_verified_run(self.root) as run:
            packet = json.loads(run.store.read(self.config['vnext_phase2_configuration']['path']))
            packet.update(target_phase=phase, target_mode=mode, review_mode=review_mode)
            raw = canonical_json_bytes(packet)
            path = 'inputs/phase2/route-configuration.json'
            with run.store.locked(run._history().validate_authority) as token:
                run.store.publish(token, path, raw)
        self.config['vnext_phase2_configuration'] = dict(path=path, hash=sha256_bytes(raw))
        self.save_config()

    def converges(self, *, phase2_calls, ordinal):
        code, result = self.call('live-phase2'); self.assertEqual(code, 0, result)
        self.assertTrue(result.get('phase_complete') or result.get('gate') == 'phase2_complete', result)
        state = self.inspect_readonly(); self.assertEqual(state['gate'], 'phase2_complete')
        self.assertEqual(self.phase2_reviewer.calls, phase2_calls)
        with open_verified_run(self.root) as run:
            self.assertEqual(run.inspect().current_pointer['promotion_ordinal'], ordinal)
            self.assertEqual(run.phase2_closeout()['packet']['terminal_state'], 'CONVERGED')
        before = self.files(); calls = (self.reviewer.calls, self.phase2_reviewer.calls)
        code, result = self.call('live-phase2'); self.assertEqual(code, 0, result)
        self.assertEqual(self.files(), before)
        self.assertEqual((self.reviewer.calls, self.phase2_reviewer.calls), calls)

    def horizontal_target(self, phase, mode):
        self.configure()
        code, result = self.call('live-phase1'); self.assertEqual(code, 0, result)
        self.stage_target(phase, mode)
        self.converges(phase2_calls=1, ordinal=0)
        entry = json.loads((self.root/'rounds/phase2/entry.json').read_bytes())
        self.assertFalse(entry['version']['changed'])

    def test_horizontal_mid_permissive(self):
        self.horizontal_target('mid', 'permissive')

    def test_horizontal_mid_strict(self):
        self.horizontal_target('mid', 'strict')

    def test_horizontal_final_permissive(self):
        self.horizontal_target('final', 'permissive')

    def test_versioned_final_strict_convergence(self):
        self.configure(versioned=True)
        code, result = self.call('live-phase1'); self.assertEqual(code, 0, result)
        self.stage_target()
        verifiers = accepting_verifier(self)
        self.converges(phase2_calls=2, ordinal=1)
        entry = json.loads((self.root/'rounds/phase2/entry.json').read_bytes())
        self.assertEqual(entry['version'], dict(before='0.17', after='1.0', changed=True))
        self.assertEqual(sum(c.calls for c in verifiers), 1)
        self.assertEqual((self.root/'spec.history.md').read_bytes().count(b'`0.17` -> `1.0`'), 1)

    def test_vertical_consolidation_rereview_and_final_strict_convergence(self):
        self.configure(mode='vertical')
        code, result = self.call('vnext-admit'); self.assertEqual(code, 0, result)
        def response(packet):
            pointer = json.loads((self.root/'rounds/current_verified.json').read_bytes())
            packet['feedback']['draft_hash'] = pointer['verified_draft_hash']
            return canonical_json_bytes(packet) if self.reviewer.calls <= 2 else self.clean(packet)
        self.reviewer.callback = response
        editor = Editor(); self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient', return_value=editor)
        verifiers = accepting_verifier(self)
        code, result = self.call('live-phase1'); self.assertEqual(code, 0, result)
        self.assertEqual(result['gate'], 'phase1_complete')
        self.assertEqual((self.reviewer.calls, editor.calls, sum(c.calls for c in verifiers)), (4, 1, 1))
        self.assertEqual(len(list(self.root.glob('rounds/round-*/vertical_merge.json'))), 1)
        self.stage_target(review_mode='vertical')
        self.converges(phase2_calls=2, ordinal=1)
        request = json.loads((self.root/'rounds/phase2/review_requests/first/request.json').read_bytes())
        self.assertEqual(request['round_number'], 6)
        self.assertEqual((editor.calls, sum(c.calls for c in verifiers)), (1, 1))

    def test_focused_pins_cleanliness_and_no_phase2_admission(self):
        self.configure(focused='determinism')
        self.refuses('live-focused-phase1', '--profile', 'structural_integrity')
        self.refuses('live-focused-phase1', '--profile', 'determinism', '--budget', '3')
        self.assertFalse(self.root.exists()); self.assertEqual(self.reviewer.calls, 0)
        code, result = self.call('live-focused-phase1', '--profile', 'determinism')
        self.assertEqual(code, 0, result)
        self.assertFalse(result['operator']['accepted'])
        state = json.loads((self.root/'rounds/run_state.json').read_bytes())
        self.assertEqual(state['terminal_state'], 'FOCUSED_PROFILE_STABLE')
        self.assertFalse(state['ready_for_phase_2']); self.assertEqual(self.reviewer.calls, 1)
        self.assertEqual(state['review_profile_budgets']['determinism'], 2)
        profile = json.loads((self.root/'rounds/round-1/profile_used.yaml').read_bytes())
        self.assertEqual(profile['profile'], 'determinism')
        self.stage_target()
        self.refuses('promote-phase2'); self.refuses('live-phase2')
        self.assertFalse((self.root/'rounds/phase2/entry_request.json').exists())
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())
        self.assertEqual(self.phase2_reviewer.calls, 0)

    def test_vertical_sensitive_consolidation_stops_before_editor(self):
        self.configure(mode='vertical')
        def sensitive(packet):
            packet['classifications'][0]['requested_effects'] = ['weaken']
            return canonical_json_bytes(packet)
        self.reviewer.callback = sensitive
        code, result = self.call('live-phase1'); self.assertEqual(code, 2, result)
        self.assertEqual(result['gate'], 'finding_admission')
        self.assertTrue(any(row['classification'] not in {'editor_fixable', 'deferable'}
                            for row in result['operator']['findings']))
        self.assertEqual(self.reviewer.calls, 2)
        self.assertTrue((self.root/'rounds/round-3/vertical_merge.json').exists())
        self.assertFalse((self.root/'rounds/round-3/proposal_input.json').exists())
        self.assertEqual(json.loads((self.root/'rounds/current_verified.json').read_bytes())['promotion_ordinal'], 0)
        before = self.files()
        code, result = self.call('vnext-decisions'); self.assertEqual(code, 0, result)
        self.assertEqual(result['round_number'], 3)
        self.assertEqual(self.files(), before)

    def test_unsupported_vertical_target_refuses_before_binding(self):
        self.configure(mode='vertical')
        code, result = self.call('live-phase1'); self.assertEqual(code, 0, result)
        self.stage_target('mid', 'permissive', 'vertical')
        result = self.refuses('live-phase2')
        self.assertIn('vertical Phase 2 supports final/strict only', result['reason'])
        self.assertEqual(self.phase2_reviewer.calls, 0)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())


if __name__ == '__main__': unittest.main()
