"""Bounded no-version-change entry with genuine V journals and publication faults."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_phase2_binding import REQUEST_PATH
from whetstone.vnext_verified_phase2_entry import ENTRY_PATH, STATE_FIELD
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_work import VerifiedWorkView
import test_vnext_verified_review as runtime
import test_vnext_verified_phase2_binding as binding_tests
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedPhase2EntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    promote = runtime.VerifiedReviewTests.promote
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files
    config = binding_tests.VerifiedPhase2BindingTests.config

    def ready(self, *, heading=None, status=None, bind=True):
        original = runtime.unit.UnitPreflightTests.setUp
        def setup(owner):
            original(owner)
            f = owner.c.f
            if heading is not None: f.base = f.base.replace(b'# Queue\n', heading.encode()+b'\n')
            if status is not None: f.base += status.encode()+b'\n'
            f.rebind()
        with patch.object(runtime.unit.UnitPreflightTests, 'setUp', setup):
            f, client = self.start(phase2_entry_contract=True)
        client.callback = clean_response
        f.run.review_next(client=client)
        f.run.finish_phase1()
        f.run.reconcile_phase1_state()
        config = self.config(f)
        if bind: f.run.bind_phase2_entry(config)
        return f, client, config

    def inspect(self, f):
        before = self.files(f)
        with patch.object(f.store, 'locked', side_effect=AssertionError('read acquired mutation fence')):
            view = f.run.phase2_state()
        self.assertEqual(self.files(f), before)
        if not isinstance(view, VerifiedWorkView):
            self.assertFalse(view.execution_permitted)
            self.assertFalse(view.resume_permitted)
            self.assertFalse(view.apply_back_permitted)
        return view

    def test_entry_commit_is_distinct_preserves_authority_and_reentry_only_synchronizes(self):
        f, client, config = self.ready()
        state = json.loads(f.store.read(STATE_PATH))
        state.update(custom={'retain':[1,2]}, phase='legacy-phase', terminal_state='LEGACY_VALUE')
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        before = self.files(f)
        view = self.inspect(f)
        self.assertFalse(view.committed)
        self.assertEqual(view.outcome, 'entry_required')
        self.assertNotEqual(view.entry_ref['path'], REQUEST_PATH)
        with (patch('whetstone.live_phase2.LivePhase2Runner', side_effect=AssertionError('legacy executor')),
              patch('whetstone.versioning.promote_spec_file_for_phase2', side_effect=AssertionError('legacy stamper'))):
            result = f.run.enter_phase2()
        self.assertEqual(result.outcome, 'phase2_entered')
        self.assertTrue(result.committed and result.state_current)
        self.assertEqual(result.entry['phase'], 'phase_2')
        self.assertEqual(result.entry['version'], dict(before='',after='',changed=False))
        self.assertEqual(json.loads(f.store.read(STATE_PATH)), {**state,STATE_FIELD:result.entry_ref})
        after = self.files(f)
        self.assertEqual(set(after)-set(before), {ENTRY_PATH})
        self.assertTrue(all(after[p]==raw for p,raw in before.items() if p!=STATE_PATH))
        for field in ('entry_request','configuration','current_verified_pointer','current_verified_draft','current_verified_map','phase1_closeout'):
            reference = result.entry[field]
            self.assertEqual(reference['hash'], sha256_bytes(f.store.read(reference['path'])))
        self.reopen(f)
        self.assertEqual(self.inspect(f).outcome, 'entered')
        self.assertEqual(f.run.enter_phase2().outcome, 'phase2_entry_recovered')
        self.assertEqual(self.files(f), after)
        self.assertEqual(client.calls, 1)

    def test_whole_major_noop_enters_but_required_version_changes_refuse_without_writes(self):
        f, client, _ = self.ready(heading='# Queue 2.0')
        before = f.store.read('spec.md')
        result = f.run.enter_phase2()
        self.assertEqual(result.entry['version'], dict(before='2.0',after='2.0',changed=False))
        self.assertEqual(f.store.read('spec.md'), before)
        self.assertEqual(client.calls, 1)
        for options in ({'heading':'# Queue 0.17'}, {'heading':'# Queue 2'}, {'status':'Status: Draft v0.1.1'}):
            with self.subTest(options=options):
                f, client, _ = self.ready(**options)
                before = self.files(f)
                with self.assertRaisesRegex(ValueError, 'version maintenance requires the V candidate protocol'):
                    f.run.enter_phase2()
                with self.assertRaisesRegex(ValueError, 'unchanged entry only'): f.run.phase2_state()
                self.assertEqual(self.files(f), before)
                self.assertEqual(client.calls, 1)

    def test_missing_request_or_configuration_prefix_is_not_automatically_bound_or_entered(self):
        f, client, config = self.ready(bind=False)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'committed immutable request'): f.run.enter_phase2()
        self.assertEqual(self.files(f), before)
        publish = f.store.publish
        def stop(token, path, value):
            if path == REQUEST_PATH: raise OSError('request not committed')
            return publish(token,path,value)
        with patch.object(f.store,'publish',side_effect=stop):
            with self.assertRaisesRegex(OSError,'not committed'): f.run.bind_phase2_entry(config)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'committed immutable request'): f.run.enter_phase2()
        with self.assertRaisesRegex(ValueError, 'committed immutable request'): f.run.phase2_state()
        self.assertEqual(self.files(f), before)
        self.assertEqual(client.calls, 1)

    def test_entry_and_final_state_interruptions_recover_exactly_without_advancing_work(self):
        for boundary in ('before_entry','after_entry','before_state','after_state'):
            with self.subTest(boundary=boundary):
                f, client, _ = self.ready()
                expected = self.inspect(f)
                publish, materialize = f.store.publish, f.store.materialize
                def entry_stop(token,path,value):
                    if path != ENTRY_PATH: return publish(token,path,value)
                    if boundary == 'after_entry': publish(token,path,value)
                    raise OSError('entry interrupted')
                def state_stop(token,path,raw,**options):
                    if path != STATE_PATH: return materialize(token,path,raw,**options)
                    if boundary == 'after_state': materialize(token,path,raw,**options)
                    raise OSError('entry interrupted')
                method, callback = ('publish',entry_stop) if 'entry' in boundary else ('materialize',state_stop)
                with patch.object(f.store,method,side_effect=callback):
                    with self.assertRaisesRegex(OSError,'entry interrupted'): f.run.enter_phase2()
                self.reopen(f)
                visible = self.inspect(f)
                self.assertEqual(visible.committed, boundary!='before_entry')
                self.assertEqual(visible.state_current, boundary=='after_state')
                if visible.committed:
                    # Even fully visible state cannot skip the entry barrier on reentry.
                    publish = f.store.publish
                    with patch.object(f.store,'publish',side_effect=entry_stop):
                        with self.assertRaisesRegex(OSError,'entry interrupted'): f.run.enter_phase2()
                result = f.run.enter_phase2()
                self.assertEqual(result.entry, expected.entry)
                self.assertEqual(result.outcome, 'phase2_entered' if boundary=='before_entry' else 'phase2_entry_recovered')
                self.assertTrue(result.state_current)
                self.assertEqual(client.calls, 1)

    def test_review_and_bound_source_barriers_precede_entry_and_repeat_on_recovery(self):
        f, client, config = self.ready()
        closeout = f.run.phase1_closeout()
        binding = f.run.phase2_entry_status()
        publish = f.store.publish
        receipt = closeout.evidence['review_receipts'][0]['receipt']['path']
        def stop(token,path,value):
            if path == receipt: raise OSError('review barrier')
            return publish(token,path,value)
        before = self.files(f)
        with patch.object(f.store,'publish',side_effect=stop):
            with self.assertRaisesRegex(OSError,'review barrier'): f.run.enter_phase2()
        self.assertEqual(self.files(f),before)
        sync = f.store.synchronize_existing
        for path in (REQUEST_PATH, binding.configuration_ref['path'], config['rubric']['artifact']['path'],
                     closeout.evidence_ref['path'], binding.request['current_verified_map']['path']):
            def fail(token,target,**options):
                if target == path: raise OSError('source flush')
                return sync(token,target,**options)
            with patch.object(f.store,'synchronize_existing',side_effect=fail):
                with self.assertRaisesRegex(OSError,'source flush'): f.run.enter_phase2()
            self.assertEqual(self.files(f),before)
        f.run.enter_phase2()
        # A matching final state still requires its barrier after entry publication.
        entry_seen = []
        def observe(token,path,value):
            result=publish(token,path,value)
            if path == ENTRY_PATH: entry_seen.append(path)
            return result
        def final_fail(token,path,**options):
            if path == STATE_PATH and entry_seen: raise OSError('final state barrier')
            return sync(token,path,**options)
        before=self.files(f)
        with patch.object(f.store,'publish',side_effect=observe), patch.object(f.store,'synchronize_existing',side_effect=final_fail):
            with self.assertRaisesRegex(OSError,'final state barrier'): f.run.enter_phase2()
        self.assertEqual(self.files(f),before)
        self.assertEqual(f.run.enter_phase2().outcome,'phase2_entry_recovered')
        self.assertEqual(client.calls,1)

    def test_corrupt_committed_sources_entry_or_missing_commit_refuse_without_reconstruction(self):
        f, client, config = self.ready()
        result=f.run.enter_phase2()
        binding=f.run.phase2_entry_status()
        for path in (ENTRY_PATH,REQUEST_PATH,binding.configuration_ref['path'],config['rubric']['artifact']['path'],
                     binding.request['current_verified_map']['path'],binding.request['phase1_closeout']['path'],
                     'rounds/current_verified.json'):
            target=f.root/path;raw=target.read_bytes();target.write_bytes(b'{}')
            before=self.files(f)
            with self.subTest(path=path):
                with self.assertRaises(ValueError): f.run.phase2_state()
                with self.assertRaises(ValueError): f.run.enter_phase2()
                self.assertEqual(self.files(f),before)
            target.write_bytes(raw)
        (f.root/ENTRY_PATH).unlink()
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'missing entry commit'): f.run.enter_phase2()
        self.assertEqual(self.files(f),before)
        self.assertEqual(client.calls,1)

    def test_mirror_and_phase1_state_recovery_end_before_entry_state_repair(self):
        f, client, _ = self.ready()
        result=f.run.enter_phase2()
        state=json.loads(f.store.read(STATE_PATH));state.pop(STATE_FIELD)
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        (f.root/'spec.md').unlink()
        self.assertEqual(self.inspect(f).outcome,'materialization_required')
        self.assertEqual(f.run.enter_phase2().outcome,'materialization_recovered')
        self.assertNotIn(STATE_FIELD,json.loads(f.store.read(STATE_PATH)))
        self.assertEqual(self.inspect(f).outcome,'entry_state_recovery_required')
        self.assertEqual(f.run.enter_phase2().outcome,'phase2_entry_recovered')
        state=json.loads(f.store.read(STATE_PATH));state.pop('vnext_phase1_closeout')
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'phase1_state_recovery_required'): f.run.enter_phase2()
        self.assertEqual(self.files(f),before)
        f.run.reconcile_phase1_state()
        self.assertEqual(f.run.enter_phase2().outcome,'phase2_entry_recovered')
        self.assertEqual(client.calls,1)

    def test_missing_entry_pin_refuses_before_writes(self):
        f, client=self.start(phase2_binding_contract=True)
        before=self.files(f)
        for method in (f.run.enter_phase2,f.run.phase2_state):
            with self.assertRaisesRegex(ValueError,'Phase 2 entry contracts'): method()
            self.assertEqual(self.files(f),before)
        self.assertEqual(client.calls,0)
