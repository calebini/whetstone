"""First Phase 2 request bindings and replay; no external client execution."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_phase2_review import INPUT_PATH, PROMPT_PATH, REQUEST_PATH, RESPONSE_SCHEMA, VOCABULARY_HASH
from whetstone.vnext_verified_phase2_entry import ENTRY_PATH, STATE_FIELD
from whetstone.vnext_verified_materialization import STATE_PATH
import test_vnext_verified_review as runtime
import test_vnext_verified_phase2_binding as binding
from test_vnext_verified_phase1_status import clean_response


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedPhase2ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files
    config = binding.VerifiedPhase2BindingTests.config

    def ready(self, *, enter=True):
        f, client = self.start(phase2_review_contract=True)
        client.callback = clean_response
        f.run.review_next(client=client)
        f.run.finish_phase1()
        f.run.reconcile_phase1_state()
        config = self.config(f)
        f.run.bind_phase2_entry(config)
        if enter: f.run.enter_phase2()
        transport = deepcopy(client.transport_binding)
        transport['output_schema_hash'] = sha256_bytes((CONTRACT_ROOT/'schemas'/ (RESPONSE_SCHEMA+'.schema.json')).read_bytes())
        return f, client, config, transport

    def test_exact_first_step_prompt_transport_and_detached_replay(self):
        f, client, config, transport = self.ready()
        before = self.files(f)
        with patch.object(f.store, 'locked', side_effect=AssertionError('read took fence')):
            preview = f.run.prepare_phase2_review(transport)
        self.assertEqual(self.files(f), before)
        self.assertEqual(preview.pending_paths, (INPUT_PATH, PROMPT_PATH, REQUEST_PATH))
        self.assertFalse(preview.committed or preview.execution_permitted or preview.resume_permitted or preview.apply_back_permitted)
        self.assertEqual(preview.request['round_number'], 2)
        self.assertEqual(preview.request['step'], dict(index=1, profile='convergence_strict_check', round_budget=1, rounds_used=0, pass_number=1))
        self.assertEqual(preview.inputs['configuration']['profiles'], config['profiles'])
        self.assertEqual([r['budget'] for r in config['profiles']], [1,2,3])
        self.assertEqual(sha256_bytes(canonical_json_bytes(preview.inputs['vocabulary'])), VOCABULARY_HASH)
        self.assertEqual(preview.inputs['draft'].encode(), f.store.read('spec.md'))
        self.assertIn('Phase: phase_2', preview.prompt)
        self.assertIn('Phase 2 oscillation classification is mandatory', preview.prompt)
        self.assertIn(preview.inputs['rubric'], preview.prompt)
        self.assertNotIn('Context files:', preview.prompt)
        self.assertIsNone(preview.inputs['declaration'])
        with patch('whetstone.live_phase2.LivePhase2Runner', side_effect=AssertionError('legacy runner')):
            final = f.run.bind_phase2_review(transport)
        self.assertTrue(final.committed)
        self.assertEqual(final.request, preview.request)
        after = self.files(f)
        self.assertEqual(set(after)-set(before), {INPUT_PATH, PROMPT_PATH, REQUEST_PATH})
        self.assertTrue(all(after[p] == raw for p,raw in before.items()))
        for key in ('entry','configuration','base_pointer','inputs','prompt'):
            ref=final.request[key];self.assertEqual(sha256_bytes(f.store.read(ref['path'])),ref['hash'])
        final.inputs['configuration']['profiles'][0]['budget'] = 99
        final.request['transport']['reviewer']['model'] = 'tampered'
        final.inputs['sources'][0]['hash'] = '0'*64
        final.inputs['sources'][1]['hash'] = '0'*64
        self.assertEqual(f.run.prepare_phase2_review(transport).request, preview.request)
        self.reopen(f)
        self.assertEqual(f.run.bind_phase2_review(transport).request, preview.request)
        self.assertEqual(self.files(f), after)
        self.assertEqual(client.calls, 1)

    def test_all_publication_prefixes_and_final_lost_ack_replay_without_new_request(self):
        for stop_path in (INPUT_PATH, PROMPT_PATH, REQUEST_PATH):
            for after_write in (False, True):
                with self.subTest(path=stop_path, after=after_write):
                    f, client, _, transport = self.ready()
                    expected = f.run.prepare_phase2_review(transport)
                    publish = f.store.publish
                    def stop(token,path,value):
                        if path != stop_path: return publish(token,path,value)
                        if after_write: publish(token,path,value)
                        raise OSError('lost acknowledgement')
                    with patch.object(f.store,'publish',side_effect=stop):
                        with self.assertRaisesRegex(OSError,'lost acknowledgement'): f.run.bind_phase2_review(transport)
                    self.reopen(f)
                    self.assertEqual(f.run.prepare_phase2_review(transport).committed, stop_path==REQUEST_PATH and after_write)
                    recovered = f.run.bind_phase2_review(transport)
                    self.assertEqual(recovered.request, expected.request)
                    # Even a fully visible commit must repeat its final barrier.
                    publish = f.store.publish
                    def fail_commit(token,path,value):
                        if path == REQUEST_PATH: raise OSError('commit barrier')
                        return publish(token,path,value)
                    with patch.object(f.store,'publish',side_effect=fail_commit):
                        with self.assertRaisesRegex(OSError,'commit barrier'): f.run.bind_phase2_review(transport)
                    self.assertEqual(client.calls,1)

    def test_entry_and_state_recovery_are_separate_and_mirror_recovery_ends_call(self):
        f, client, _, transport = self.ready(enter=False)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError,'committed entry'): f.run.bind_phase2_review(transport)
        self.assertEqual(self.files(f),before)
        f.run.enter_phase2()
        state=json.loads(f.store.read(STATE_PATH));state.pop(STATE_FIELD)
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'recovered state'): f.run.bind_phase2_review(transport)
        self.assertEqual(self.files(f),before)
        f.run.enter_phase2()
        (f.root/'spec.md').unlink()
        self.assertEqual(f.run.bind_phase2_review(transport).outcome,'materialization_recovered')
        self.assertFalse((f.root/REQUEST_PATH).exists())
        self.assertTrue(f.run.bind_phase2_review(transport).committed)
        self.assertEqual(client.calls,1)

    def test_changed_transport_corrupt_sources_and_missing_committed_dependencies_refuse(self):
        f, client, config, transport = self.ready()
        result=f.run.bind_phase2_review(transport)
        for key,value in (('reviewer',dict(name='other',version='1',model='other')), ('output_schema_hash','0'*64),
                          ('timeout_seconds',10), ('command','other-command')):
            altered={**transport,key:value};before=self.files(f)
            with self.subTest(key=key):
                with self.assertRaises(ValueError): f.run.bind_phase2_review(altered)
                self.assertEqual(self.files(f),before)
        for path in (INPUT_PATH,PROMPT_PATH,REQUEST_PATH,ENTRY_PATH,config['rubric']['artifact']['path'],
                     result.request['configuration']['path'],'rounds/current_verified.json'):
            target=f.root/path;raw=target.read_bytes();target.write_bytes(b'{}')
            before=self.files(f)
            with self.subTest(path=path):
                with self.assertRaises(ValueError): f.run.bind_phase2_review(transport)
                self.assertEqual(self.files(f),before)
            target.write_bytes(raw)
        for path in (INPUT_PATH,PROMPT_PATH):
            target=f.root/path;raw=target.read_bytes();target.unlink()
            before=self.files(f)
            with self.assertRaisesRegex(ValueError,'missing its dependencies'): f.run.bind_phase2_review(transport)
            self.assertEqual(self.files(f),before);target.write_bytes(raw)
        self.assertEqual(client.calls,1)

    def test_source_barriers_and_drift_prevent_request_commit(self):
        f, client, config, transport = self.ready()
        preview=f.run.prepare_phase2_review(transport)
        sync=f.store.synchronize_existing
        for target in (ENTRY_PATH,config['rubric']['artifact']['path'], preview.inputs['sources'][1]['path'], STATE_PATH):
            def fail(token,path,**options):
                if path == target: raise OSError('source barrier')
                return sync(token,path,**options)
            with patch.object(f.store,'synchronize_existing',side_effect=fail):
                with self.assertRaisesRegex(OSError,'source barrier'): f.run.bind_phase2_review(transport)
            self.assertFalse((f.root/INPUT_PATH).exists())
        publish=f.store.publish
        def drift(token,path,value):
            result=publish(token,path,value)
            if path==PROMPT_PATH: (f.root/config['rubric']['artifact']['path']).write_bytes(b'changed rubric')
            return result
        with patch.object(f.store,'publish',side_effect=drift):
            with self.assertRaises(ValueError): f.run.bind_phase2_review(transport)
        self.assertFalse((f.root/REQUEST_PATH).exists())
        self.assertEqual(client.calls,1)

    def test_missing_pin_and_vocabulary_drift_refuse_before_publication(self):
        f, client=self.start(phase2_entry_contract=True)
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'Reviewer request contracts'): f.run.bind_phase2_review(client.transport_binding)
        self.assertEqual(self.files(f),before)
        f, client, _, transport=self.ready()
        from whetstone.vocabulary import controlled_vocabulary_packet
        vocabulary=controlled_vocabulary_packet();vocabulary['vocabulary_version']='changed'
        before=self.files(f)
        with patch('whetstone.vnext_verified_phase2_review.controlled_vocabulary_packet',return_value=vocabulary):
            with self.assertRaisesRegex(ValueError,'vocabulary differs'): f.run.bind_phase2_review(transport)
        self.assertEqual(self.files(f),before)
