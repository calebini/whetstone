"""Untrusted Phase 2 advice: exact binding, conservative guards and recovery."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_phase2_advice import ADVICE_PATH, BINDING_PATH
from whetstone.vnext_verified_phase2_consumption import PATH as CONSUMPTION_PATH
from whetstone.vnext_verified_phase2_review import INPUT_PATH
import test_vnext_verified_phase2_client as clients


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class Phase2AdviceTests(unittest.TestCase):
    setUpClass = clients.VerifiedPhase2ClientTests.setUpClass
    fixture = clients.VerifiedPhase2ClientTests.fixture
    files = clients.VerifiedPhase2ClientTests.files
    reopen = clients.VerifiedPhase2ClientTests.reopen
    config = clients.VerifiedPhase2ClientTests.config
    ready = clients.VerifiedPhase2ClientTests.ready

    def start(self, **kwargs):
        kwargs['phase2_advice_contract'] = True
        return clients.VerifiedPhase2ClientTests.start(self, **kwargs)

    def reviewed(self, *, consume=True):
        f, client, config = self.ready()
        result = f.run.run_phase2_review(client=client)
        inputs = json.loads(f.store.read(INPUT_PATH))
        job = inputs['job']
        mutable = next(row for row in inputs['authority']['bindings'] if row['role'] == 'mutable_target')
        advice = dict(schema_version='vnext-finding-advice-v1', job_id=job['job_id'],
            base_draft_hash=result.review['feedback']['draft_hash'], feedback=deepcopy(result.receipt['feedback']),
            authority_map_hash=job['authority_map_hash'], scope_contract_hash=job['scope_contract_hash'],
            protected_invariants_hash=job['protected_invariants_hash'], findings=[dict(
                feedback_id=row['feedback_id'], classification='editor_fixable',
                authority_scope_ids=mutable['authority_scopes'], source_authority_binding_ids=[mutable['binding_id']],
                scope_surface_ids=[], compatibility_change='none', requested_effects=['clarification'])
                for row in result.review['feedback']['feedback']])
        if consume: f.run.consume_phase2_result()
        return f, client, config, advice

    def test_binding_is_read_only_to_prepare_and_does_not_grant_round_or_authority(self):
        f, client, _, advice = self.reviewed()
        before = self.files(f)
        with patch.object(f.store, 'locked', side_effect=AssertionError('preparation took lock')):
            self.assertEqual(f.run.prepare_phase2_advice()['status'], 'advice_required')
            view = f.run.prepare_phase2_advice(advice)
        self.assertEqual(self.files(f), before)
        self.assertEqual(view['pending_paths'], (ADVICE_PATH, BINDING_PATH))
        self.assertEqual(view['binding']['findings'][0]['classification'], 'editor_fixable')
        with self.assertRaisesRegex(ValueError, 'explicit advisory input'): f.run.bind_phase2_advice()
        bound = f.run.bind_phase2_advice(advice)
        self.assertEqual(bound['status'], 'bound')
        for key in ('candidate_authorized', 'next_review_authorized', 'phase_complete'):
            self.assertIs(bound['binding'][key], False)
        self.assertEqual(bound['binding']['next_gate'], 'canonical_round_admission_not_implemented')
        after = self.files(f)
        self.assertEqual(set(after)-set(before), {ADVICE_PATH, BINDING_PATH})
        for path, raw in before.items(): self.assertEqual(after[path], raw)
        # Historical no-advice accounting is not rewritten by later advice.
        self.assertEqual(json.loads(after[CONSUMPTION_PATH])['findings'][0]['classification'], 'operator_decision_required')
        advice['findings'].clear();bound['binding']['findings'].clear()
        self.reopen(f)
        self.assertTrue(f.run.bind_phase2_advice()['binding']['findings'])
        self.assertEqual(self.files(f), after)
        self.assertEqual(client.calls, 1)

    def test_exact_bindings_coverage_and_deterministic_authority_guards(self):
        f, _, _, advice = self.reviewed(consume=False)
        with self.assertRaisesRegex(ValueError, 'committed result consumption'): f.run.bind_phase2_advice(advice)
        self.assertFalse((f.root/ADVICE_PATH).exists())
        f.run.consume_phase2_result()
        before = self.files(f)
        variants = []
        for key in ('job_id', 'base_draft_hash', 'authority_map_hash', 'protected_invariants_hash', 'scope_contract_hash'):
            bad = deepcopy(advice);bad[key] = ('job_' if key == 'job_id' else '')+'f'*64;variants.append(bad)
        bad = deepcopy(advice);bad['feedback']['path'] = 'inputs/unrelated.json';variants.append(bad)
        bad = deepcopy(advice);bad['findings'] = [];variants.append(bad)
        bad = deepcopy(advice);bad['findings'] *= 2;variants.append(bad)
        bad = deepcopy(advice);bad['findings'][0]['source_authority_binding_ids'] = ['missing'];variants.append(bad)
        bad = deepcopy(advice);bad['plan'] = {};variants.append(bad)
        for bad in variants:
            with self.subTest(advice=bad):
                with self.assertRaises(ValueError): f.run.bind_phase2_advice(bad)
                self.assertEqual(self.files(f), before)
        for field, value, expected in (
            ('requested_effects', ['weaken'], 'operator_decision_required'),
            ('requested_effects', [], 'operator_decision_required'),
            ('authority_scope_ids', ['outside'], 'authority_conflict'),
            ('compatibility_change', 'introduce', 'authority_conflict')):
            bad = deepcopy(advice);bad['findings'][0][field] = value
            view = f.run.prepare_phase2_advice(bad)
            self.assertEqual(view['binding']['findings'][0]['classification'], expected)
            self.assertFalse(view['binding']['candidate_authorized'])
        self.assertEqual(self.files(f), before)

    def test_interrupted_attachment_conflict_barriers_and_missing_committed_dependency(self):
        f, client, config, advice = self.reviewed()
        synchronize = f.store.synchronize_existing
        def barrier(token, path, **kwargs):
            if path == CONSUMPTION_PATH: raise OSError('consumption barrier')
            return synchronize(token, path, **kwargs)
        with patch.object(f.store, 'synchronize_existing', side_effect=barrier):
            with self.assertRaisesRegex(OSError, 'consumption barrier'): f.run.bind_phase2_advice(advice)
        self.assertFalse((f.root/ADVICE_PATH).exists())
        publish = f.store.publish
        def lose(path_to_fail):
            def uncertain(token, path, packet):
                result = publish(token, path, packet)
                if path == path_to_fail:
                    f.store._check_owner(token)
                    raise OSError('lost acknowledgement')
                return result
            return uncertain
        with patch.object(f.store, 'publish', side_effect=lose(ADVICE_PATH)):
            with self.assertRaises(OSError): f.run.bind_phase2_advice(advice)
        self.assertFalse((f.root/BINDING_PATH).exists())
        self.reopen(f)
        bad = deepcopy(advice);bad['findings'][0]['classification'] = 'deferable'
        with self.assertRaisesRegex(ValueError, 'immutable attachment'): f.run.bind_phase2_advice(bad)
        self.assertEqual(f.run.prepare_phase2_advice()['pending_paths'], (BINDING_PATH,))
        publish = f.store.publish
        with patch.object(f.store, 'publish', side_effect=lose(BINDING_PATH)):
            with self.assertRaises(OSError): f.run.bind_phase2_advice()
        self.reopen(f)
        bound = f.run.bind_phase2_advice()
        self.assertEqual(bound['status'], 'bound')
        synchronize = f.store.synchronize_existing
        with patch.object(f.store, 'synchronize_existing', side_effect=barrier):
            with self.assertRaises(OSError): f.run.bind_phase2_advice()
        rubric = f.root/config['rubric']['artifact']['path'];raw = rubric.read_bytes()
        rubric.write_bytes(raw+b'drift')
        with self.assertRaises(ValueError): f.run.bind_phase2_advice()
        rubric.write_bytes(raw)
        (f.root/'spec.md').unlink()
        self.assertEqual(f.run.bind_phase2_advice().outcome, 'materialization_recovered')
        binding_raw = (f.root/BINDING_PATH).read_bytes()
        changed = deepcopy(bound['binding']);changed['findings'][0]['classification'] = 'deferable'
        (f.root/BINDING_PATH).write_bytes(canonical_json_bytes(changed))
        with self.assertRaisesRegex(ValueError, 'classification replay'): f.run.prepare_phase2_advice()
        (f.root/BINDING_PATH).write_bytes(binding_raw)
        (f.root/ADVICE_PATH).unlink()
        with self.assertRaisesRegex(ValueError, 'missing its advice'): f.run.bind_phase2_advice(advice)
        self.assertFalse((f.root/ADVICE_PATH).exists())
        self.assertEqual(client.calls, 1)


    def test_unpinned_owner_refuses_without_writes(self):
        with patch.object(self, 'start', side_effect=lambda **kw: clients.VerifiedPhase2ClientTests.start(self, **kw)):
            f, _, _ = self.ready()
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'outside supported suite'): f.run.prepare_phase2_advice()
        with self.assertRaisesRegex(ValueError, 'outside supported suite'): f.run.bind_phase2_advice()
        self.assertEqual(self.files(f), before)


if __name__ == '__main__': unittest.main()
