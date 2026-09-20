"""Immutable Phase 2 request bindings through genuine V journals; no Phase 2 clients."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_phase2_binding import REQUEST_PATH, PROFILE_ORDER
from whetstone.vnext_verified_phase2_eligibility import Phase2Eligibility
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedPhase2BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    promote = runtime.VerifiedReviewTests.promote
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def config(self, f):
        rubric = (CONTRACT_ROOT.parent/'rubrics/standard-v1.md').read_bytes()
        path = 'inputs/phase2/rubric.md'
        with f.store.locked(f.run._history().validate_authority) as token:
            f.store.publish(token, path, rubric)
        review = json.loads(f.store.read(f.run._record['review_configuration']['path']))
        return dict(schema_version='vnext-phase2-configuration-v1', job_id=json.loads(f.store.read_descriptor())['job_id'],
            review_configuration=deepcopy(f.run._record['review_configuration']), workflow='standard',
            review_mode='horizontal', profile_set='stateful_system', target_phase='final', target_mode='strict',
            rubric=dict(profile='standard-v1', source='builtin', artifact=dict(path=path, hash=sha256_bytes(rubric))),
            profiles=[dict(name=name, budget=n) for n,name in enumerate(PROFILE_ORDER, 1)],
            **{role:review[role] for role in ('reviewer','editor','verifier')})

    def ready(self):
        f, client = self.start(phase2_binding_contract=True)
        client.callback = clean_response
        f.run.review_next(client=client)
        f.run.finish_phase1()
        f.run.reconcile_phase1_state()
        return f, client, self.config(f)

    def inspect(self, f):
        before = self.files(f)
        view = f.run.phase2_entry_status()
        self.assertEqual(self.files(f), before)
        self.assertFalse(view.entry_permitted)
        self.assertFalse(view.resume_permitted)
        self.assertFalse(view.apply_back_permitted)
        return view

    def test_explicit_ordered_inputs_bind_exact_current_evidence_and_reopen_without_phase_entry(self):
        f, client, config = self.ready()
        self.assertIsInstance(self.inspect(f), Phase2Eligibility)
        before = self.files(f)
        with patch.object(f.store, 'locked', side_effect=AssertionError('read acquired fence')):
            preview = f.run.prepare_phase2_entry(config)
        self.assertEqual(self.files(f), before)
        self.assertFalse(preview.materialized)
        self.assertIn('phase2_request_unpublished', preview.phase2_blockers)
        self.assertEqual([p['budget'] for p in preview.configuration['profiles']], [1, 2, 3])
        self.assertEqual([p['name'] for p in preview.configuration['profiles']], list(PROFILE_ORDER))
        final = f.run.bind_phase2_entry(config)
        self.assertTrue(final.materialized)
        self.assertEqual(final.request, preview.request)
        for field in ('configuration', 'current_verified_pointer', 'current_verified_draft', 'current_verified_map',
                      'phase1_closeout', 'phase1_terminal_report', 'job_descriptor', 'review_configuration'):
            reference = final.request[field]
            self.assertEqual(reference['hash'], sha256_bytes(f.store.read(reference['path'])))
        added = {final.configuration_ref['path'], REQUEST_PATH}
        after = self.files(f)
        self.assertEqual(set(after)-set(before), added)
        self.assertTrue(all(after[p] == raw for p,raw in before.items()))
        self.reopen(f)
        self.assertEqual(self.inspect(f), final)
        self.assertEqual(f.run.bind_phase2_entry(config), final)
        self.assertEqual(self.files(f), after)
        preview.configuration['profiles'][0]['budget'] = 99
        self.assertNotEqual(preview.configuration, self.inspect(f).configuration)
        self.assertEqual(client.calls, 1)

    def test_unsupported_missing_or_cross_job_configuration_refuses_without_publication(self):
        f, client, config = self.ready()
        bad = []
        for key,value in (('job_id','job_'+'0'*64), ('target_mode','permissive'), ('target_phase','mid'),
                          ('workflow','custom'), ('profile_set','utility_mvp'), ('review_mode','vertical')):
            packet = deepcopy(config); packet[key] = value; bad.append(packet)
        for budget in (0, -1, True):
            packet = deepcopy(config); packet['profiles'][0]['budget'] = budget; bad.append(packet)
        packet = deepcopy(config); packet['profiles'] = packet['profiles'][:2]; bad.append(packet)
        packet = deepcopy(config); packet['profiles'].reverse(); packet['profiles'][1]['name']='convergence_strict_check'; bad.append(packet)
        packet = deepcopy(config); packet['reviewer']['model']='changed-model'; bad.append(packet)
        packet = deepcopy(config); packet['review_configuration']['hash']='0'*64; bad.append(packet)
        packet = deepcopy(config); del packet['target_mode']; bad.append(packet)
        packet = deepcopy(config); packet['allow_legacy_defaults']=True; bad.append(packet)
        packet = deepcopy(config); packet['rubric']['artifact']['path']='inputs/phase2/../../spec.md'; bad.append(packet)
        before = self.files(f)
        for packet in bad:
            with self.subTest(packet=packet), self.assertRaises(ValueError): f.run.bind_phase2_entry(packet)
            self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 1)

    def test_promoted_request_rejects_stale_pointer_cross_job_and_changed_selection(self):
        f, client = self.start(phase2_binding_contract=True, budget=2)
        seed = f.run.phase2_eligibility().current_pointer
        self.review(f, client)
        verifier = self.promote(f)
        client.callback = clean_response
        f.run.review_next(client=client)
        f.run.finish_phase1(); f.run.reconcile_phase1_state()
        config = self.config(f)
        final = f.run.bind_phase2_entry(config)
        self.assertNotEqual(final.request['current_verified_pointer'], seed)
        for field,value in (('current_verified_pointer', seed), ('job_id','job_'+'0'*64),
                            ('phase1_closeout', final.request['phase1_terminal_report'])):
            packet = deepcopy(final.request); packet[field] = value
            (f.root/REQUEST_PATH).write_bytes(canonical_json_bytes(packet))
            before = self.files(f)
            with self.assertRaisesRegex(ValueError, 'stale|another job'): f.run.phase2_entry_status()
            with self.assertRaisesRegex(ValueError, 'stale|another job'): f.run.bind_phase2_entry(config)
            self.assertEqual(self.files(f), before)
        (f.root/REQUEST_PATH).write_bytes(canonical_json_bytes(final.request))
        changed = deepcopy(config); changed['profiles'][0]['budget'] += 1
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'another configuration'): f.run.bind_phase2_entry(changed)
        self.assertEqual(self.files(f), before)
        self.assertEqual((client.calls,f.editor.calls,verifier.calls),(2,1,1))

    def test_publication_prefixes_and_lost_request_ack_repeat_exact_binding_without_clients(self):
        for boundary in ('configuration', 'request', 'after_request'):
            with self.subTest(boundary=boundary):
                f, client, config = self.ready()
                preview = f.run.prepare_phase2_entry(config)
                path = preview.configuration_ref['path'] if boundary == 'configuration' else REQUEST_PATH
                publish = f.store.publish
                def stop(token, target, value):
                    if target != path: return publish(token, target, value)
                    if boundary == 'after_request': publish(token, target, value)
                    raise OSError('binding interrupted')
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'binding interrupted'): f.run.bind_phase2_entry(config)
                self.reopen(f)
                view = self.inspect(f)
                self.assertEqual(isinstance(view, Phase2Eligibility), boundary != 'after_request')
                if boundary == 'after_request':
                    self.assertTrue(view.materialized)
                    publish = f.store.publish
                    with patch.object(f.store, 'publish', side_effect=stop):
                        with self.assertRaisesRegex(OSError, 'binding interrupted'): f.run.bind_phase2_entry(config)
                final = f.run.bind_phase2_entry(config)
                self.assertTrue(final.materialized)
                self.assertEqual(final.request, preview.request)
                self.assertEqual(client.calls, 1)

    def test_source_and_rubric_barriers_fail_before_binding_even_after_visible_commit(self):
        f, client, config = self.ready()
        closeout = f.run.phase1_closeout()
        before = self.files(f)
        publish = f.store.publish
        receipt_path = closeout.evidence['review_receipts'][0]['receipt']['path']
        def stop(token, path, value):
            if path == receipt_path: raise OSError('review source barrier')
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'review source barrier'): f.run.bind_phase2_entry(config)
        self.assertEqual(self.files(f), before)
        final = f.run.bind_phase2_entry(config)
        before = self.files(f)
        sync = f.store.synchronize_existing
        for failing_path in (closeout.evidence_ref['path'], config['rubric']['artifact']['path']):
            def fail(token, path, **options):
                if path == failing_path: raise OSError('binding source flush')
                return sync(token, path, **options)
            with patch.object(f.store, 'synchronize_existing', side_effect=fail):
                with self.assertRaisesRegex(OSError, 'binding source flush'): f.run.bind_phase2_entry(config)
            self.assertEqual(self.files(f), before)
        self.assertEqual(f.run.bind_phase2_entry(config), final)
        self.assertEqual(client.calls, 1)

    def test_missing_committed_configuration_and_changed_rubric_are_not_reconstructed(self):
        f, client, config = self.ready()
        final = f.run.bind_phase2_entry(config)
        path = f.root/final.configuration_ref['path']; raw = path.read_bytes(); path.unlink()
        before = self.files(f)
        with self.assertRaises(FileNotFoundError): f.run.phase2_entry_status()
        with self.assertRaisesRegex(ValueError, 'missing its configuration'): f.run.bind_phase2_entry(config)
        self.assertEqual(self.files(f), before)
        path.write_bytes(raw)
        rubric_path = f.root/config['rubric']['artifact']['path']
        rubric_path.write_bytes(rubric_path.read_bytes()+b'\n')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): f.run.phase2_entry_status()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): f.run.bind_phase2_entry(config)
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 1)

    def test_phase1_debt_and_separate_mirror_or_state_recovery_cannot_publish_request(self):
        f, client = self.start(phase2_binding_contract=True)
        config = self.config(f)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'Phase 1 prerequisites'): f.run.bind_phase2_entry(config)
        self.assertEqual(self.files(f), before)
        client.callback = clean_response
        f.run.review_next(client=client); f.run.finish_phase1()
        with self.assertRaisesRegex(ValueError, 'phase1_state_recovery_required'): f.run.bind_phase2_entry(config)
        f.run.reconcile_phase1_state()
        (f.root/'spec.md').unlink()
        self.assertEqual(f.run.bind_phase2_entry(config).outcome, 'materialization_recovered')
        self.assertFalse((f.root/REQUEST_PATH).exists())
        self.assertTrue(f.run.bind_phase2_entry(config).materialized)
        self.assertEqual(client.calls, 1)

    def test_missing_binding_pin_refuses_before_any_publication(self):
        f, client = self.start(phase2_eligibility_contract=True)
        before = self.files(f)
        for method,args in ((f.run.prepare_phase2_entry,({},)), (f.run.bind_phase2_entry,({},)), (f.run.phase2_entry_status,())):
            with self.assertRaisesRegex(ValueError, 'binding contracts'): method(*args)
            self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 0)
