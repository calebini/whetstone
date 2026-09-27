"""Whole extension journeys retain original requests, authority and terminal history."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase1_budget import DIRECTORY
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime
from test_vnext_verified_phase1_status import clean_response
import test_vnext_verified_vertical_phase1 as vertical_tests


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class BudgetTests(unittest.TestCase):
    setUpClass = runtime.VerifiedReviewTests.setUpClass
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    promote = runtime.VerifiedReviewTests.promote
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def exhausted(self, *, vertical=False, focused=False, **options):
        profiles = [{'name':'structural_integrity','budget':1}]
        if vertical: profiles.append({'name':'determinism','budget':1})
        f, client = self.start(budget_contract=True, status_contract=True, mode='vertical' if vertical else 'horizontal',
            vertical_contract=vertical, focused_contract=focused,
            focused_profile='structural_integrity' if focused else None, profiles=profiles, **options)
        if vertical:
            vertical_tests.VerticalPhase1Tests.cycle(self, f, client)
            f.run.admit_reviewed_round()
            vertical_tests.VerticalPhase1Tests.promote(self, f)
        else:
            self.review(f, client); self.promote(f)
        self.assertEqual(f.run.phase1_status().review_gate, 'budget_exhausted')
        old = f.run.finish_phase1()
        f.run.reconcile_phase1_state()
        return f, client, old

    def test_horizontal_vertical_and_focused_extensions_finish_without_replaying_prior_work(self):
        for vertical, focused in [(False,False),(True,False),(False,True)]:
            with self.subTest(vertical=vertical, focused=focused):
                f, client, old = self.exhausted(vertical=vertical, focused=focused)
                config = f.store.read(f.run._record['review_configuration']['path'])
                preserved = {p:raw for p,raw in self.files(f).items() if p.startswith('rounds/round-')}
                grant = f.run.extend_phase1_budget(added_rounds_per_profile=1, generated_at=STAMP)
                self.assertEqual(grant['outcome'], 'budget_extended')
                self.assertEqual(f.run.extend_phase1_budget(added_rounds_per_profile=1)['reference'], grant['reference'])
                state = json.loads(f.store.read(STATE_PATH))
                self.assertEqual(len(state['budget_extensions']),1)
                self.assertIsNone(state['terminal_state'])
                self.assertFalse(state['ready_for_phase_2'])
                self.assertEqual([p.round_budget for p in f.run.phase1_status().profiles], [2]*(2 if vertical else 1))
                self.reopen(f); client.callback = clean_response
                for _ in range(2 if vertical else 1): self.assertEqual(f.run.review_next(client=client).status,'complete')
                result = f.run.finish_phase1(); f.run.reconcile_phase1_state()
                self.assertEqual(result.report['terminal_state'], 'FOCUSED_PROFILE_STABLE' if focused else 'PHASE_1_STABLE')
                self.assertEqual(result.accepted, not focused)
                self.assertEqual(result.evidence['budget_extensions'], [grant['reference']])
                self.assertEqual(f.store.read(old.evidence_ref['path']), canonical_json_bytes(old.evidence))
                self.assertEqual(f.store.read(f.run._record['review_configuration']['path']),config)
                self.assertTrue(all(f.store.read(p)==raw for p,raw in preserved.items()))
                self.assertEqual(client.calls,4 if vertical else 2)
                self.assertEqual(f.editor.calls,1)
                with self.assertRaisesRegex(ValueError,'exhausted closeout'): f.run.extend_phase1_budget(added_rounds_per_profile=1)
                if not vertical and not focused:
                    from whetstone.vnext_verified_phase1_budget import event_id
                    path=f.root/grant['reference']['path'];original=path.read_bytes();changed=json.loads(original)
                    changed['event']['added_rounds_per_profile']=99
                    changed['event']['new_review_profile_budgets']['structural_integrity']=100
                    changed['event']['event_id']=event_id(changed['event'],1)
                    path.write_bytes(canonical_json_bytes(changed))
                    with self.assertRaises(ValueError):f.run.phase1_status()
                    path.write_bytes(original)

    def test_grant_commit_and_state_acknowledgement_recover_once_before_any_client(self):
        for boundary in ('before_grant','after_grant','before_state','after_state'):
            with self.subTest(boundary=boundary):
                f, client, _ = self.exhausted()
                publish, materialize = f.store.publish, f.store.materialize
                path = DIRECTORY+'/extension-1.json'
                def stop_grant(token, target, value):
                    if target != path: return publish(token,target,value)
                    if boundary == 'after_grant': publish(token,target,value)
                    raise OSError('grant interrupted')
                def stop_state(token, target, raw, **kwargs):
                    if target != STATE_PATH: return materialize(token,target,raw,**kwargs)
                    if boundary == 'after_state': materialize(token,target,raw,**kwargs)
                    raise OSError('grant interrupted')
                method, callback = ('publish',stop_grant) if 'grant' in boundary else ('materialize',stop_state)
                with patch.object(f.store,method,side_effect=callback):
                    with self.assertRaisesRegex(OSError,'grant interrupted'):
                        f.run.extend_phase1_budget(added_rounds_per_profile=1,generated_at=STAMP)
                self.reopen(f)
                if boundary in {'after_grant','before_state'}:
                    with self.assertRaisesRegex(ValueError,'state recovery required'): f.run.review_next(client=client)
                recovered = f.run.extend_phase1_budget(added_rounds_per_profile=1,generated_at=STAMP)
                self.assertEqual(recovered['outcome'],'budget_extended' if boundary=='before_grant' else 'budget_extension_recovered')
                self.assertEqual(len(json.loads(f.store.read(STATE_PATH))['budget_extensions']),1)
                self.assertEqual(client.calls,1)
                self.assertEqual(f.editor.calls,1)

    def test_pending_timeout_reuses_grant_and_retained_attempt_without_reset(self):
        f, client, _ = self.exhausted(vertical=True)
        grant = f.run.extend_phase1_budget(added_rounds_per_profile=1)
        def timeout(packet): raise TimeoutError('bounded timeout')
        client.callback=timeout
        self.assertEqual(f.run.review_next(client=client).status,'timeout')
        self.reopen(f)
        self.assertEqual(f.run.extend_phase1_budget(added_rounds_per_profile=1)['reference'],grant['reference'])
        self.assertEqual(f.run.review_next(client=client).status,'continuation_required')
        client.callback=clean_response
        self.assertEqual(f.run.review_next(client=client,continuation=True).status,'complete')
        self.assertEqual(f.run.review_next(client=client).status,'complete')
        self.assertEqual(f.run.finish_phase1().report['terminal_state'],'PHASE_1_STABLE')
        self.assertEqual(client.calls,5)

    def test_source_drift_invalid_amounts_and_unpublished_closeout_refuse_without_grant(self):
        f, client, old = self.exhausted()
        for value in (0,-1,True,1.5):
            with self.assertRaises(ValueError): f.run.extend_phase1_budget(added_rounds_per_profile=value)
        spec=f.root/'spec.md';original=spec.read_bytes();spec.write_bytes(original+b'\nmanual drift\n')
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertEqual(self.files(f),before);spec.write_bytes(original)
        path = f.root/old.evidence_ref['path']; raw=path.read_bytes();path.write_bytes(b'{}')
        before=self.files(f)
        with self.assertRaises(ValueError): f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertEqual(self.files(f),before);path.write_bytes(raw)
        state=json.loads(f.store.read(STATE_PATH));state.pop('vnext_phase1_closeout')
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        with self.assertRaisesRegex(ValueError,'current state'):f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertFalse((f.root/DIRECTORY).exists())

    def test_second_vertical_grant_preserves_both_exhaustion_reports_and_two_promotions(self):
        f,client,first = self.exhausted(vertical=True)
        f.run.extend_phase1_budget(added_rounds_per_profile=1)
        vertical_tests.VerticalPhase1Tests.cycle(self,f,client)
        f.run.admit_reviewed_round();vertical_tests.VerticalPhase1Tests.promote(self,f,number=6,ordinal=2)
        second=f.run.finish_phase1();f.run.reconcile_phase1_state()
        self.assertNotEqual(first.technical_failure_ref,second.technical_failure_ref)
        second_grant=f.run.extend_phase1_budget(added_rounds_per_profile=2)
        event=second_grant['extension']['event']
        self.assertEqual(event['previous_current_round'],6)
        self.assertEqual(set(event['new_review_profile_budgets'].values()),{4})
        self.reopen(f);client.callback=clean_response
        vertical_tests.VerticalPhase1Tests.cycle(self,f,client)
        f.run.finish_phase1();f.run.reconcile_phase1_state()
        state=json.loads(f.store.read(STATE_PATH))
        self.assertEqual(len(state['budget_extensions']),2)
        self.assertEqual(state['terminal_state'],'PHASE_1_STABLE')
        self.assertEqual(state['current_round'],8)
        for closeout in (first,second):
            self.assertEqual(f.store.read(closeout.technical_failure_ref['path']),canonical_json_bytes(closeout.technical_failure))
        self.assertEqual((client.calls,f.editor.calls),(6,2))

    def test_extension_preserves_shape_allowance_and_recovers_retained_review_without_client(self):
        f,client,_=self.exhausted()
        f.run.extend_phase1_budget(added_rounds_per_profile=1)
        client.callback=lambda packet:b'{'
        self.assertEqual(f.run.review_next(client=client).status,'attempts_exhausted')
        self.reopen(f)
        f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertEqual(f.run.review_next(continuation=True).status,'attempts_exhausted')
        self.assertEqual(client.calls,3)
        g,other,_=self.exhausted()
        g.run.extend_phase1_budget(added_rounds_per_profile=1)
        other.callback=clean_response
        publish=g.store.publish
        def stop(token,path,value):
            result=publish(token,path,value)
            if other.calls == 2 and path.endswith('/attempts/1/response.json'):raise OSError('retained grant review')
            return result
        with patch.object(g.store,'publish',side_effect=stop):
            with self.assertRaisesRegex(OSError,'retained grant review'):g.run.review_next(client=other)
        self.reopen(g)
        g.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertEqual(g.run.review_next(continuation=True).status,'complete')
        self.assertEqual(g.run.finish_phase1().report['terminal_state'],'PHASE_1_STABLE')
        self.assertEqual(other.calls,2)

    def test_dependency_flush_and_lost_ownership_block_then_recover_without_duplicate_grant(self):
        from whetstone.vnext_local_storage import OwnershipLost
        f,client,old=self.exhausted()
        sync=f.store.synchronize_existing
        def stop(token,path,**options):
            if path==old.evidence_ref['path']:raise OSError('exhaustion source barrier')
            return sync(token,path,**options)
        with patch.object(f.store,'synchronize_existing',side_effect=stop):
            with self.assertRaisesRegex(OSError,'source barrier'):f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertFalse((f.root/DIRECTORY).exists())
        config=f.root/f.run._record['review_configuration']['path'];original=config.read_bytes()
        def drift(token,path,**options):
            result=sync(token,path,**options)
            if path==old.evidence_ref['path']:config.write_bytes(b'{}')
            return result
        with patch.object(f.store,'synchronize_existing',side_effect=drift):
            with self.assertRaises(ValueError):f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertFalse((f.root/DIRECTORY).exists());config.write_bytes(original)
        materialize=f.store.materialize
        def lose(token,path,raw,**options):
            result=materialize(token,path,raw,**options)
            if path==STATE_PATH:f.store._invalidate()
            return result
        with patch.object(f.store,'materialize',side_effect=lose):
            with self.assertRaises(OwnershipLost):f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.reopen(f)
        self.assertEqual(f.run.extend_phase1_budget(added_rounds_per_profile=1)['outcome'],'budget_extension_recovered')
        self.assertEqual(len(json.loads(f.store.read(STATE_PATH))['budget_extensions']),1)
        self.assertEqual(client.calls,1)

    def test_appended_review_state_failure_recovers_without_another_review(self):
        f,client,_=self.exhausted()
        f.run.extend_phase1_budget(added_rounds_per_profile=1)
        client.callback=clean_response
        materialize=f.store.materialize
        def stop(token,path,raw,**options):
            if path==STATE_PATH:raise OSError('round projection interrupted')
            return materialize(token,path,raw,**options)
        with patch.object(f.store,'materialize',side_effect=stop):
            with self.assertRaisesRegex(OSError,'round projection'):f.run.review_next(client=client)
        self.reopen(f)
        self.assertEqual(f.run.phase1_status().review_gate,'review_complete')
        with self.assertRaisesRegex(ValueError,'round state recovery'):f.run.review_next(client=client)
        f.run.reconcile_phase1_state()
        self.assertEqual(json.loads(f.store.read(STATE_PATH))['current_round'],2)
        f.run.finish_phase1();f.run.reconcile_phase1_state()
        self.assertEqual(client.calls,2)

    def test_pending_work_and_old_suite_cannot_acquire_capacity(self):
        f,client=self.start(budget_contract=True,status_contract=True)
        f.run.review_next(client=client)
        before=self.files(f)
        with self.assertRaises(ValueError):f.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertEqual(self.files(f),before)
        self.assertEqual(client.calls,1)
        g,other=self.start(operator_status_contract=True)
        before=self.files(g)
        with self.assertRaises(ValueError):g.run.extend_phase1_budget(added_rounds_per_profile=1)
        self.assertEqual(self.files(g),before)
        self.assertEqual(other.calls,0)


if __name__ == '__main__': unittest.main()
