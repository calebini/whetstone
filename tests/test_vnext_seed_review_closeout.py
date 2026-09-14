from copy import deepcopy
from dataclasses import replace
import json,subprocess,sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_proposal_run import open_proposal_run
from whetstone.vnext_seed_review_closeout import inspect_seed_review_closeout
from test_vnext_review_requests import Reviewer
import test_vnext_review_requests as fixtures


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class SeedReviewCloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.SeedReviewTests.setUpClass()
    def setUp(self):
        self.f=fixtures.SeedReviewTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.run=self.f.run;self.client=self.f.client
    def clean(self,packet):
        packet['feedback']['feedback']=[];packet['classifications']=[]
        return canonical_json_bytes(packet)
    def phase(self,continuation=False,client=None):
        return self.run.review_phase(client=client or self.client,continuation=continuation)
    def reopen(self):
        self.run.close();self.run=open_proposal_run(self.f.root,suite_path=self.f.f.path);self.addCleanup(self.run.close)
    def files(self):return self.f.files()

    def test_full_configured_clean_review_finishes_without_candidate_or_phase2(self):
        self.f.configure_profiles('vertical');self.run=self.f.run;self.client=self.f.client
        self.client.callback=self.clean;before=self.run.store.read('rounds/current_verified.json')
        result=self.phase();report=result.terminal_report
        self.assertEqual((report['terminal_state'],self.client.calls),('PHASE_1_STABLE',2))
        self.assertTrue(all(value is None for value in report['latest_candidate'].values()))
        self.assertFalse(report['apply_back_permitted']);self.assertFalse(report['resume']['permitted'])
        self.assertEqual(self.run.store.read('rounds/current_verified.json'),before)
        self.assertEqual(self.run.status(round_number=2)['processing_gate'],'complete')
        self.assertEqual(self.phase().terminal_report,report);self.assertEqual(self.client.calls,2)
        with self.assertRaisesRegex(ValueError,'not technically resumable'):self.phase(True)
        self.assertFalse((self.f.root/'rounds/candidate_index').exists())

    def test_budget_exhaustion_retains_unresolved_deferred_findings(self):
        def deferred(packet):packet['classifications'][0]['classification']='deferable';return canonical_json_bytes(packet)
        self.client.callback=deferred;result=self.phase()
        self.assertEqual(result.terminal_report['terminal_state'],'TARGET_NOT_REACHED')
        self.assertEqual(result.terminal_report['resume']['reason'],'vnext_review_budget_exhausted')
        self.assertEqual(result.review.review['findings'][0]['classification'],'deferable')
        self.assertEqual(self.client.calls,1);self.assertFalse(result.terminal_report['resume']['permitted'])

    def test_findings_stop_before_editor_or_terminal_claim(self):
        result=self.phase();self.assertEqual(result.review.status,'finding_admission')
        self.assertIsNone(result.terminal_report);self.assertIsNone(result.terminal_report_ref)
        self.assertFalse((self.f.root/'rounds/terminal_reports').exists())
        self.assertFalse((self.f.root/'rounds/round-1/proposal_input.json').exists())
        self.assertEqual(self.phase().review,result.review);self.assertEqual(self.client.calls,1)
        with self.assertRaisesRegex(ValueError,'not technical continuation'):self.phase(True)

    def test_sensitive_findings_do_not_become_automatic_operator_choices(self):
        def sensitive(packet):packet['classifications'][0]['requested_effects']=['weaken'];return canonical_json_bytes(packet)
        self.client.callback=sensitive;result=self.phase()
        self.assertEqual(result.review.review['findings'][0]['classification'],'operator_decision_required')
        self.assertIsNone(result.terminal_report);self.assertEqual(self.client.calls,1)
        self.assertFalse((self.f.root/'rounds/round-1/proposal_input.json').exists())

    def test_missing_terminal_recovery_ends_without_repeating_review(self):
        self.client.callback=self.clean;original=self.run.store.publish
        def fail(token,path,value):
            if path.startswith('rounds/terminal_reports/'):raise OSError('fictional missing terminal')
            return original(token,path,value)
        with patch.object(self.run.store,'publish',side_effect=fail):
            with self.assertRaises(OSError):self.phase()
        before=self.files();status=self.run.status(round_number=1)
        self.assertEqual(status['processing_gate'],'materialization');self.assertTrue(status['resume']['permitted'])
        self.assertEqual(status['terminal_report']['terminal_state'],'PHASE_1_STABLE');self.assertEqual(self.files(),before)
        with self.assertRaisesRegex(ValueError,'requires explicit continuation'):self.phase()
        self.assertEqual(self.files(),before);self.reopen()
        client=Reviewer(self.f.f.f);result=self.phase(True,client)
        self.assertEqual(result.terminal_report['terminal_state'],'PHASE_1_STABLE');self.assertEqual(client.calls,0)
        self.assertEqual(self.run.status(round_number=1)['terminal_materialization'],'present')

    def test_lost_terminal_acknowledgement_reuses_durable_result(self):
        self.client.callback=self.clean;original=self.run.store.publish
        def fail(token,path,value):
            result=original(token,path,value)
            if path.startswith('rounds/terminal_reports/'):raise OSError('fictional lost acknowledgement')
            return result
        with patch.object(self.run.store,'publish',side_effect=fail):
            with self.assertRaises(OSError):self.phase()
        self.assertEqual(self.run.status(round_number=1)['processing_gate'],'complete')
        self.assertEqual(self.phase().terminal_report['terminal_state'],'PHASE_1_STABLE')
        self.assertEqual(self.client.calls,1)

    def test_timeout_can_continue_and_old_report_cannot_override_clean_completion(self):
        def timeout(packet):raise TimeoutError('fictional seed deadline')
        self.client.callback=timeout;first=self.phase()
        self.assertEqual(first.terminal_report['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        self.assertTrue(first.terminal_report['resume']['permitted']);before=self.files()
        with self.assertRaisesRegex(ValueError,'requires explicit continuation'):self.phase()
        self.assertEqual(self.files(),before)
        self.reopen();client=Reviewer(self.f.f.f,callback=self.clean);result=self.phase(True,client)
        self.assertEqual(result.terminal_report['terminal_state'],'PHASE_1_STABLE');self.assertEqual(client.calls,1)
        self.assertEqual(self.run.status(round_number=1)['terminal_report'],result.terminal_report)
        self.assertTrue((self.f.root/first.terminal_report_ref['path']).is_file())

    def test_exhausted_timeout_keeps_cause_and_refuses_more_calls(self):
        def timeout(packet):raise TimeoutError('fictional seed deadline')
        self.client.callback=timeout;self.phase();result=self.phase(True)
        self.assertEqual(result.terminal_report['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        self.assertFalse(result.terminal_report['resume']['permitted'])
        self.assertIn('fictional seed deadline',result.terminal_report['resume']['reason'])
        with self.assertRaisesRegex(ValueError,'not technically resumable'):self.phase(True)
        self.assertEqual(self.phase().terminal_report,result.terminal_report);self.assertEqual(self.client.calls,2)

    def test_bad_shape_exhaustion_is_final_without_candidate(self):
        self.client.callback=lambda packet:b'{}';result=self.phase()
        self.assertEqual(result.terminal_report['terminal_state'],'HALTED_ARTIFACT_INVALID')
        self.assertFalse(result.terminal_report['resume']['permitted']);self.assertEqual(self.client.calls,2)
        self.assertTrue(all(value is None for value in result.terminal_report['latest_candidate'].values()))

    def test_rehashed_or_supplied_clean_claim_cannot_replace_actual_review_evidence(self):
        self.f.step();review=self.run.review_status()
        with self.assertRaisesRegex(ValueError,'selection changed'):
            inspect_seed_review_closeout(self.run,replace(review,status='phase_1_stable'))
        self.assertIsNone(inspect_seed_review_closeout(self.run))

    def test_current_terminal_corruption_refuses_readback_and_repair(self):
        self.client.callback=self.clean;result=self.phase();target=self.f.root/result.terminal_report_ref['path']
        packet=deepcopy(result.terminal_report);packet['terminal_state']='CONVERGED'
        target.write_bytes(canonical_json_bytes(packet));before=self.files()
        with self.assertRaisesRegex(ValueError,'materialization conflicts'):self.run.status(round_number=1)
        with self.assertRaisesRegex(ValueError,'materialization conflicts'):self.phase()
        self.assertEqual(self.files(),before);self.assertEqual(self.client.calls,1)

    def test_missing_bound_review_result_prevents_final_report_from_claiming_success(self):
        self.client.callback=self.clean;result=self.phase()
        directory=self.f.directory(result.review);(directory/'result.json').unlink()
        status=self.run.status(round_number=1)
        self.assertEqual(status['request_status'],'valid_response');self.assertIsNone(status['terminal_report'])
        self.assertTrue(status['resume']['permitted'])
        self.assertEqual(self.phase(True).terminal_report['terminal_state'],'PHASE_1_STABLE');self.assertEqual(self.client.calls,1)

    def test_fresh_process_derives_closed_phase_without_clients(self):
        self.client.callback=self.clean;result=self.phase();self.run.close()
        from whetstone import vnext_registry
        suite=self.f.f.suite;algorithms=deepcopy(vnext_registry.SUITE_ALGORITHM_VERSIONS[suite.version])
        script=f'''
import json
from whetstone import vnext_registry
from whetstone.vnext_proposal_run import open_proposal_run
vnext_registry.SUPPORTED_SUITES[{suite.version!r}]={suite.digest!r}
vnext_registry.SUITE_ALGORITHM_VERSIONS[{suite.version!r}]={algorithms!r}
with open_proposal_run({str(self.f.root)!r},suite_path={str(self.f.f.path)!r}) as run:
    print(json.dumps(run.status(round_number=1)))
'''
        completed=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=60)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['terminal_report'],result.terminal_report)
