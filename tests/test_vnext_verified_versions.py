"""Pinned V round journeys with genuine journals and scripted clients."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_version_operations import ASSEMBLER
from whetstone.vnext_contracts import canonical_json_bytes
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime
import test_vnext_verified_semantics as semantic_tests
from test_vnext_verified_phase1_status import clean_response
import test_vnext_verified_phase2_rubric as rubric_tests


@unittest.skipUnless(sys.platform=='darwin','D8 local storage requires macOS/APFS')
class VerifiedVersionTests(unittest.TestCase):
    setUpClass=runtime.VerifiedReviewTests.setUpClass
    start=runtime.VerifiedReviewTests.start
    review=runtime.VerifiedReviewTests.review
    promote=runtime.VerifiedReviewTests.promote
    reopen=runtime.VerifiedReviewTests.reopen
    files=runtime.VerifiedReviewTests.files

    def fixture(self, **options):
        original=semantic_tests.consuming_suite
        def suite(*args, **kwargs):
            kwargs['additional_algorithms']=(*kwargs.get('additional_algorithms',()),'vnext_version_operations_v1','vnext_version_entry_v1')
            kwargs['additional_schemas']=set(kwargs.get('additional_schemas',()))|{'mutation_plan_v4','vnext_version_operation_v1','vnext_version_admission_v1','vnext_phase2_entry_v2','vnext_system_entry_request_v1'}
            kwargs['algorithm_overrides']={**kwargs.get('algorithm_overrides',{}),'assembler_version':ASSEMBLER}
            return original(*args,**kwargs)
        setup=runtime.unit.UnitPreflightTests.setUp
        def seed(owner):
            setup(owner)
            title=getattr(self,'versioned_title',b'# Queue 0.17\nStatus: Accepted v0.17\n')
            owner.c.f.base=owner.c.f.base.replace(b'# Queue\n',title)
            owner.c.f.rebind()
        with patch.object(semantic_tests,'consuming_suite',side_effect=suite),patch.object(runtime.unit.UnitPreflightTests,'setUp',seed):
            return runtime.VerifiedReviewTests.fixture(self,**options)

    def test_round_promotes_final_version_once_and_reopens_for_clean_review(self):
        f,client=self.start(status_contract=True)
        self.review(f,client)
        self.assertEqual(f.run.request(round_number=1,client=f.editor).outcome,'proposal_result')
        creation=f.run.register(round_number=1,created_at=STAMP).value
        candidate=f.store.read(creation['candidate_path'])
        self.assertIn(b'# Queue 0.18',candidate);self.assertIn(b'Status: Draft v0.18',candidate)
        self.assertIn(b'# Queue 0.17',f.store.read('spec.md'))
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        context=load_registered_semantic_context(f.store,admission=f.run._history(),candidate_id=creation['candidate_id'])
        verifier=runtime.history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=verifier,decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'],1)
        self.assertEqual(f.store.read('spec.md'),candidate)
        self.reopen(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome,'not_eligible')
        client.callback=clean_response
        self.assertEqual(f.run.review_next(client=client).status,'complete')
        self.assertEqual(f.store.read('spec.md'),candidate)
        operation=json.loads(f.store.read(creation['candidate_path'].rsplit('/',1)[0]+'/version_operation.json'))
        self.assertEqual((operation['before'],operation['after']),('0.17','0.18'))
        self.assertEqual(f.editor.calls,1)
        self.assertIn(b'`0.17` -> `0.18`',f.store.read('spec.history.md'))

    def test_clean_versioned_entry_has_no_editor_or_invented_review_and_distinct_commit(self):
        import test_vnext_verified_phase2_binding as binding_tests
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        f,client=self.start(phase2_entry_contract=True)
        client.callback=clean_response
        f.run.review_next(client=client);f.run.finish_phase1();f.run.reconcile_phase1_state()
        config=binding_tests.VerifiedPhase2BindingTests.config(self,f)
        f.run.bind_phase2_entry(config)
        synchronize=f.store.synchronize_existing
        def fail_rubric_barrier(token,path,**options):
            if path==config['rubric']['artifact']['path']: raise OSError('rubric barrier lost')
            return synchronize(token,path,**options)
        with patch.object(f.store,'synchronize_existing',side_effect=fail_rubric_barrier):
            with self.assertRaisesRegex(OSError,'rubric barrier lost'):f.run.prepare_phase2_version(created_at=STAMP)
        self.assertFalse((f.root/'rounds/phase2/version_admission.json').exists())
        publish=f.store.publish
        def stop_creation(token,path,value):
            if path=='rounds/candidate_index/creation-1.json': raise OSError('creation not committed')
            return publish(token,path,value)
        with patch.object(f.store,'publish',side_effect=stop_creation):
            with self.assertRaisesRegex(OSError,'creation not committed'):f.run.prepare_phase2_version(created_at=STAMP)
        self.reopen(f)
        self.assertEqual(f.run.prepare_phase2_version(created_at=STAMP).outcome,'registration_recovery_required')
        self.assertEqual(f.run.recover_registration().outcome,'registration_recovered')
        creation=json.loads(f.store.read('rounds/candidate_index/creation-1.json'))
        self.assertEqual(creation['round_number'],1)
        self.assertEqual(f.run.prepare_phase2_version(created_at=STAMP),creation)
        self.assertFalse((f.root/'rounds/phase2/entry.json').exists())
        context=load_registered_semantic_context(f.store,admission=f.run._history(),candidate_id=creation['candidate_id'])
        self.assertEqual(context.packet['admitted_findings'],[])
        self.assertIn('system_entry',context.packet)
        verifier=runtime.history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=verifier,decided_at=STAMP).value.decision['promotion_permitted'])
        materialize=f.store.materialize
        def lose_history_ack(token,path,raw,**options):
            result=materialize(token,path,raw,**options)
            if path=='spec.history.md': raise OSError('history acknowledgement lost')
            return result
        with patch.object(f.store,'materialize',side_effect=lose_history_ack):
            with self.assertRaisesRegex(OSError,'history acknowledgement lost'):
                f.run.promote(prepared_at=STAMP)
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'],1)
        self.reopen(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome,'materialization_recovered')
        self.assertFalse((f.root/'rounds/phase2/entry.json').exists())
        self.assertIn(b'# Queue 1.0',f.store.read('spec.md'))
        self.reopen(f)
        state_path=f.root/'rounds/run_state.json';saved=state_path.read_bytes()
        state=json.loads(saved);state.pop('vnext_phase1_closeout')
        state_path.write_bytes(canonical_json_bytes(state))
        try:
            with self.assertRaisesRegex(ValueError,'current Phase 1 state'):f.run.enter_phase2()
            self.assertFalse((f.root/'rounds/phase2/entry.json').exists())
        finally:state_path.write_bytes(saved)
        materialize=f.store.materialize
        def lose_entry_ack(token,path,raw,**options):
            result=materialize(token,path,raw,**options)
            if path=='rounds/run_state.json': raise OSError('entry state acknowledgement lost')
            return result
        with patch.object(f.store,'materialize',side_effect=lose_entry_ack):
            with self.assertRaisesRegex(OSError,'entry state acknowledgement lost'):f.run.enter_phase2()
        self.reopen(f)
        result=f.run.enter_phase2()
        self.assertTrue(result.committed and result.state_current)
        self.assertEqual(result.entry['version'],dict(before='0.17',after='1.0',changed=True))
        self.assertEqual(f.run.enter_phase2().outcome,'phase2_entry_recovered')
        self.assertEqual((client.calls,f.editor.calls,verifier.calls),(1,0,1))
        self.assertFalse((f.root/'rounds/round-2/reviewer_feedback.json').exists())
        self.assertEqual(f.store.read('rounds/round-2/draft_before.md'),f.store.read('spec.md'))
        directory=next((f.root/'rounds/system_requests').iterdir())
        (directory/'base_inventory.json').write_bytes(b'{}\n')
        with self.assertRaisesRegex(ValueError,'system entry source changed'):f.run.phase2_state()

    def test_rejected_version_candidate_retains_authority_and_finality(self):
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        f,client=self.start(status_contract=True);self.review(f,client)
        base=f.store.read('spec.md');head=f.store.read('rounds/current_verified.json')
        f.run.request(round_number=1,client=f.editor)
        creation=f.run.register(round_number=1,created_at=STAMP).value
        context=load_registered_semantic_context(f.store,admission=f.run._history(),candidate_id=creation['candidate_id'])
        verifier=runtime.history.verified.semantic.Client(context)
        response=json.loads(verifier.valid);response.update(verdict='reject',unrelated_semantic_change='detected')
        verifier.responses=[canonical_json_bytes(response)]
        final=f.run.verify(client=verifier,decided_at=STAMP).value.decision
        self.assertEqual(final['candidate_disposition'],'CANDIDATE_REJECTED')
        self.reopen(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome,'not_eligible')
        self.assertEqual(f.run.verify(client=object(),decided_at=STAMP).value.decision,final)
        self.assertEqual(f.store.read('spec.md'),base)
        self.assertEqual(f.store.read('rounds/current_verified.json'),head)
        self.assertNotIn(b'`0.17` -> `0.18`',f.store.read('spec.history.md'))
        self.assertEqual(verifier.calls,1)

    def test_editor_noop_candidate_keeps_version_and_status(self):
        from whetstone.vnext_contracts import sha256_bytes
        f,client=self.start(status_contract=True);self.review(f,client)
        def unchanged(packet):
            text='Queue always waits.\n';packet['payloads'][0]['content']=text
            packet['patch']['operations'][0]['payload']['hash']=sha256_bytes(text.encode())
            return canonical_json_bytes(packet)
        f.editor.callback=unchanged
        f.run.request(round_number=1,client=f.editor)
        creation=f.run.register(round_number=1,created_at=STAMP).value
        self.assertEqual(f.store.read(creation['candidate_path']),f.store.read('spec.md'))
        record=json.loads(f.store.read(creation['candidate_path'].rsplit('/',1)[0]+'/version_operation.json'))
        self.assertEqual(record['edits'],[])
        self.assertEqual((record['before'],record['after']),('0.17','0.17'))

    def test_unversioned_new_consumer_enters_without_candidate(self):
        import test_vnext_verified_phase2_binding as binding_tests
        self.versioned_title=b'# Queue\n'
        f,client=self.start(phase2_entry_contract=True);client.callback=clean_response
        f.run.review_next(client=client);f.run.finish_phase1();f.run.reconcile_phase1_state()
        f.run.bind_phase2_entry(binding_tests.VerifiedPhase2BindingTests.config(self,f))
        result=f.run.enter_phase2()
        self.assertEqual(result.entry['schema_version'],'vnext-phase2-entry-v1')
        self.assertFalse(result.entry['version']['changed'])
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'],0)
        self.assertEqual(f.editor.calls,0)
        self.assertEqual(f.run.enter_phase2().outcome,'phase2_entry_recovered')


@unittest.skipUnless(sys.platform=='darwin','D8 local storage requires macOS/APFS')
class VersionRouteTests(unittest.TestCase):
    setUpClass=VerifiedVersionTests.setUpClass
    start=VerifiedVersionTests.start
    reopen=VerifiedVersionTests.reopen
    files=VerifiedVersionTests.files
    review=VerifiedVersionTests.review

    def fixture(self,**options):
        self.current=VerifiedVersionTests.fixture(self,**options)
        return self.current

    def test_focused_version_promotion_retains_restricted_acceptance(self):
        from test_vnext_verified_focused_phase1 import FocusedPhase1Tests as Cases
        self.focused=lambda **kw:Cases.focused(self,**kw)
        self.promote=lambda f:Cases.promote(self,f)
        Cases.test_verified_promotion_requires_selected_profile_rereview_and_retains_history(self)
        self.assertIn(b'# Queue 0.18',self.current.store.read('spec.md'))

    def test_vertical_version_promotion_retains_profile_budgets_and_full_rereview(self):
        from test_vnext_verified_vertical_phase1 import VerticalPhase1Tests as Cases
        self.vertical=lambda **kw:Cases.vertical(self,**kw)
        self.cycle=lambda f,c:Cases.cycle(self,f,c)
        self.promote=lambda f:Cases.promote(self,f)
        Cases.test_consolidated_promotion_preserves_provenance_and_requires_full_rereview(self)
        self.assertIn(b'# Queue 0.18',self.current.store.read('spec.md'))


@unittest.skipUnless(sys.platform=='darwin','D8 local storage requires macOS/APFS')
class VersionPhase2Tests(unittest.TestCase):
    setUpClass=VerifiedVersionTests.setUpClass
    fixture=VerifiedVersionTests.fixture
    start=runtime.VerifiedReviewTests.start
    files=VerifiedVersionTests.files
    reopen=VerifiedVersionTests.reopen
    config=rubric_tests.RubricRuntimeTests.config
    advice=rubric_tests.RubricRuntimeTests.advice
    advance=rubric_tests.RubricRuntimeTests.advance
    response=rubric_tests.RubricRuntimeTests.response

    def ready(self):
        from copy import deepcopy
        import test_vnext_verified_phase2_client as clients
        from whetstone.vnext_contracts import CONTRACT_ROOT,sha256_bytes
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        f,prior=self.start(phase2_rubric_contract=True)
        prior.callback=clean_response
        f.run.review_next(client=prior);f.run.finish_phase1();f.run.reconcile_phase1_state()
        config=self.config(f);f.run.bind_phase2_entry(config)
        creation=f.run.prepare_phase2_version(created_at=STAMP)
        context=load_registered_semantic_context(f.store,admission=f.run._history(),candidate_id=creation['candidate_id'])
        verifier=runtime.history.verified.semantic.Client(context)
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP);f.run.enter_phase2()
        transport=deepcopy(prior.transport_binding)
        transport['output_schema_hash']=sha256_bytes((CONTRACT_ROOT/'schemas/vnext_phase2_rubric_response_v1.schema.json').read_bytes())
        f.run.bind_phase2_review(transport)
        self.finished=f
        return f,clients.Client(transport,prior.feedback),config

    def candidate(self,f,number):
        self.assertIn(b'# Queue 1.0',f.store.read('spec.md'))
        creation,verifier=rubric_tests.RubricRuntimeTests.candidate(self,f,number)
        self.assertIn(b'# Queue 1.1',f.store.read(creation['candidate_path']))
        self.assertIn(b'# Queue 1.0',f.store.read('spec.md'))
        return creation,verifier

    def test_entry_and_post_entry_correction_promote_exact_history(self):
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        with patch('whetstone.live_phase2.LivePhase2Runner',side_effect=AssertionError('legacy executor')):
            f,client,_=self.ready();client.callback=self.response()
            result=f.run.run_phase2_review(client=client)
            self.assertEqual(result.status,'complete');f.run.consume_phase2_result()
            bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
            f.run.bind_phase2_advice(self.advice(bound,result));ref=f.run.admit_phase2_round()
            number=json.loads(f.store.read(ref['path']))['round_number']
            creation,verifier=self.candidate(f,number)
            self.assertTrue(f.run.verify(client=verifier,decided_at=STAMP).value.decision['promotion_permitted'])
            self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'],2)
            self.reopen(f)
            self.assertEqual(f.run._history().inspect().pointers[-1]['promotion_ordinal'],2)
        self.assertEqual(f.store.read('spec.md'),f.store.read(creation['candidate_path']))
        self.assertIn(b'# Queue 1.1',f.store.read('spec.md'))
        history=f.store.read('spec.history.md')
        self.assertEqual(history.count(b'`0.17` -> `1.0`'),1)
        self.assertEqual(history.count(b'`1.0` -> `1.1`'),1)
        self.assertEqual((client.calls,f.editor.calls,verifier.calls),(1,1,1))

    def test_declaration_and_clean_convergence_never_stamp_again(self):
        with patch('whetstone.live_phase2.LivePhase2Runner',side_effect=AssertionError('legacy executor')):
            f,client,_=self.ready();client.callback=self.response(gaps=False)
            head=f.store.read('rounds/current_verified.json');draft=f.store.read('spec.md')
            history=f.store.read('spec.history.md')
            self.assertEqual(f.run.run_phase2_review(client=client).status,'complete')
            f.run.consume_phase2_result();self.advance(f,client)
            f.run.prepare_phase2_declaration();self.advance(f,client)
            f.run.reconcile_phase2_findings()
            self.assertEqual(f.run.finish_phase2()['packet']['terminal_state'],'CONVERGED')
            self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual(f.store.read('rounds/current_verified.json'),head)
        self.assertEqual(f.store.read('spec.md'),draft)
        self.assertEqual(f.store.read('spec.history.md'),history)
        self.assertEqual((client.calls,f.editor.calls),(3,0))


if __name__=='__main__':unittest.main()
