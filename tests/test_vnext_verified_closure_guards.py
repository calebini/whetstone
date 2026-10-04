"""Q1 closure regressions: CLI intent and failure-publication fences."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

import test_vnext_local_storage as storage
from vnext_q1_command_fixtures import CommandCase
from whetstone.vnext_verified_commands import phase1, SelectionChanged, recovery_invocation
from whetstone.vnext_verified_phase2_commands import execute_phase2
from whetstone.vnext_verified_run import VerifiedRun


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class ClosureControlTests(CommandCase):
    def test_legacy_phase2_controls_cannot_silently_enter_verified_execution(self):
        self.qualify()
        code,result=self.invoke('vnext-admit');self.assertEqual(code,0,result)
        before=self.files()
        with patch('whetstone.vnext_verified_commands.execute',side_effect=AssertionError('ignored CLI intent')):
            for args in [('--closeout-existing',),('--workflow','custom'),('--rubric','custom.md'),
                         ('--rubric-label','custom')]:
                with self.subTest(args=args):
                    code,result=self.invoke('live-phase2',*args)
                    self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before);self.assertEqual(self.reviewer.calls,0)

    def test_matching_phase2_selectors_only_corroborate_the_pins(self):
        self.qualify()
        code,result=self.invoke('vnext-admit');self.assertEqual(code,0,result)
        before=self.files()
        with patch('whetstone.vnext_verified_commands.execute',return_value={'gate':'entry_required'}) as execute:
            code,result=self.invoke('live-phase2','--workflow','standard','--rubric','standard-v1')
        self.assertEqual(code,2,result);execute.assert_called_once()
        self.assertEqual(self.files(),before);self.assertEqual(self.reviewer.calls,0)


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class FailureFenceTests(unittest.TestCase):
    setUp=storage.LocalStorageTests.setUp
    open_store=storage.LocalStorageTests.open_store

    def scenario(self,phase, *, race=None):
        result=SimpleNamespace(status='timeout',round_number=1,profile='structural_integrity',
            request_id='req_failure',attempts=1,receipt=None,last_outcome={'classification':'timeout'})
        initial=dict(gate='review' if phase==1 else 'proposal',phase='phase_'+str(phase),
                     recovery=None,continuation=None,round_number=1,request_status='not_started')
        family='phase1' if phase==1 else 'correction_failure'
        pending=dict(initial,gate=family+'_publication',recovery=family+'_publication')
        projected=dict(initial,gate=family+'_projection',recovery=family+'_projection')
        stopped=dict(initial,gate='stopped',recovery=None,continuation='reviewer' if phase==1 else 'unsupported_phase2_continuation')
        run=Mock(spec=VerifiedRun)
        run.store=self.store;run.state=deepcopy(initial);run.calls=[];run.result=result
        report={'committed':True}
        if phase==2:
            for state in (initial,pending,projected,stopped):state['sequence']={'current_pointer':{'path':'head','hash':'a'*64}}
            pending['report']={'committed':False};projected['report']=report
            run.state=deepcopy(initial)
        def request(**kwargs):
            with self.store.locked(lambda read:None):
                run.calls.append('client');run.state=deepcopy(pending)
            return result if phase==1 else SimpleNamespace(value=result,current_pointer={'path':'head','hash':'a'*64})
        def publish():
            if race=='publication':run.state['gate']='peer_changed'
            with self.store.locked(lambda read:run.calls.append('publish')) as token:
                self.store.publish(token,'outcome/report.json',report);run.state=deepcopy(projected)
            return report
        def project():
            if race=='projection':run.state['gate']='peer_changed'
            with self.store.locked(lambda read:run.calls.append('project')) as token:
                self.store.publish(token,'outcome/state.json',report);run.state=deepcopy(stopped)
            return report
        run.review_next=request;run.request=request;run.review_status=lambda:run.result
        run.finish_phase1=publish;run.reconcile_phase1_state=project
        run.publish_phase2_correction_failure=publish;run.reconcile_phase2_correction_failure_state=project
        proof=SimpleNamespace(latest={'path':'snapshot','hash':'b'*64},
            pointers=[{'path':'head','hash':'a'*64}],inspect_registry=lambda:None)
        run._operator=lambda:SimpleNamespace(_proof=lambda read:proof)
        run.proposal=dict(request_id=result.request_id,attempts=result.attempts)
        return run

    def invoke(self,run,phase):
        with (patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda r:deepcopy(r.state)),
              patch('whetstone.vnext_verified_phase2_commands.inspect_command',side_effect=lambda r:deepcopy(r.state)),
              patch('whetstone.vnext_verified_phase2_commands.optional',return_value=b'entry'),
              patch('whetstone.vnext_verified_command_state.proposal_state',side_effect=lambda *a,**kw:run.proposal),
              patch('whetstone.vnext_verified_commands._client',return_value=object()),
              patch('whetstone.vnext_verified_phase2_commands._client',return_value=object())):
            return (phase1 if phase==1 else execute_phase2)(run,SimpleNamespace(),{}, {})

    def test_failure_reporting_retains_normal_publication_and_projection(self):
        for phase in (1,2):
            with self.subTest(phase=phase):
                run=self.scenario(phase);self.invoke(run,phase)
                self.assertEqual(run.calls,['client','publish','project'])

    def test_peer_change_at_failure_publication_fence_stops_before_write(self):
        for phase in (1,2):
            with self.subTest(phase=phase):
                run=self.scenario(phase,race='publication')
                with self.assertRaises(SelectionChanged):self.invoke(run,phase)
                self.assertEqual(run.calls,['client'])

    def test_peer_change_at_failure_projection_fence_preserves_selected_report(self):
        for phase in (1,2):
            with self.subTest(phase=phase):
                run=self.scenario(phase,race='projection')
                with self.assertRaises(SelectionChanged):self.invoke(run,phase)
                self.assertEqual(run.calls,['client','publish'])

    def test_replaced_request_outcome_refuses_before_reporting(self):
        for phase in (1,2):
            with self.subTest(phase=phase):
                run=self.scenario(phase)
                request=run.review_next if phase==1 else run.request
                def raced(**kwargs):
                    result=request(**kwargs)
                    if phase==1:
                        run.result=deepcopy(run.result);run.result.attempts+=1
                    else:run.proposal['attempts']+=1
                    return result
                if phase==1:run.review_next=raced
                else:run.request=raced
                with self.assertRaisesRegex(ValueError,'outcome changed'):self.invoke(run,phase)
                self.assertEqual(run.calls,['client'])


class RecoveryInvocationTests(unittest.TestCase):
    def invoke(self, *, row=None, role=None, number=None):
        run=SimpleNamespace(store=SimpleNamespace(root='/isolated run'))
        args=SimpleNamespace(config='/outside/config.yaml')
        return recovery_invocation(run,args,dict(recovery=row,continuation=role,round_number=number))

    def test_selected_rows_describe_exact_bounded_resume(self):
        for row in ('materialization','promotion','phase1_publication','phase1_projection','entry',
                    'failure_publication','failure_projection','correction_failure_publication',
                    'correction_failure_projection','resolution_publication','resolution_projection',
                    'signal_publication','signal_projection','closeout_publication','closeout_projection',
                    'findings_publication','advice'):
            with self.subTest(row=row):
                self.assertEqual(self.invoke(row=row,role='unsupported_phase2_continuation'),
                    ['whetstone','resume','--root','/isolated run','--config','/outside/config.yaml'])
        for role in ('reviewer','phase2_reviewer'):
            self.assertEqual(self.invoke(role=role)[1],'resume')

    def test_required_rounds_are_explicit_and_unsupported_actions_have_no_invocation(self):
        for selector in ({'row':'registration'},{'row':'verification'},{'role':'editor'},{'role':'verifier'}):
            self.assertIsNone(self.invoke(**selector))
            self.assertEqual(self.invoke(**selector,number=3)[-2:],['--vnext-round','3'])
        for selector in ({},{'role':'unsupported_phase2_continuation'},{'row':'unknown','role':'reviewer'}):
            self.assertIsNone(self.invoke(**selector))


if __name__=='__main__':unittest.main()
