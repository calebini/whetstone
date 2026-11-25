"""Public CLI coverage for the shipping shared-policy suite and the held predecessor."""
from copy import deepcopy
import json
import sys
import unittest

from whetstone import vnext_registry
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vocabulary import PROFILE_SETS
import test_vnext_verified_cli as old
from test_vnext_phase1_policy import scope_packet


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class PolicyCLIFixture(unittest.TestCase):
    suite_version = "vnext-verified-consumer-3"
    setUpClass = old.VerifiedCLITests.setUpClass
    patch = old.VerifiedCLITests.patch
    clean = staticmethod(old.VerifiedCLITests.clean)
    invoke = old.VerifiedCLITests.invoke
    save_config = old.VerifiedCLITests.save_config
    files = old.VerifiedCLITests.files

    def setUp(self):
        old.VerifiedCLITests.setUp(self)
        self.suite=validate_contract_suite(CONTRACT_ROOT/'suites'/f'{self.suite_version}.json')
        self.f.suite=self.suite
        self.configure()

    def configure(self, workflow='mvp', profile_set='utility_mvp', mode='horizontal', *, scope=True):
        self.f.job.update(contract_suite_version=self.suite.version, **vnext_registry.SUITE_ALGORITHM_VERSIONS[self.suite.version])
        self.f.original.review.update(schema_version='review-configuration-v3', completion_policy='scope-aware-phase1-v1',
            workflow=workflow, profile_set=profile_set, review_mode=mode,
            profiles=[dict(name=p,budget=1) for p in PROFILE_SETS[profile_set].phase_1_profiles])
        self.f.original.review_ref=self.f.save('inputs/review.json',self.f.original.review)
        self.f.job['review_configuration_hash']=self.f.original.review_ref['hash']
        self.f.scope=scope_packet() if scope else None
        if scope:self.f.hint['scope_surface_ids']=[self.f.scope['scope_surfaces'][0]['id']]
        else:self.f.job.update(scope_contract_path=None,scope_contract_hash=None)
        self.f.rebind()
        self.fixture.package.update(job_descriptor=self.f.job_ref, review_configuration=self.f.original.review_ref)
        self.fixture.save_package()
        self.config=dict(editing_mode='verified_promotion',contract_suite_version=self.suite.version,
            vnext_input_package=dict(path=str(self.fixture.source/'proposal_package.json'),
                hash=sha256_bytes((self.fixture.source/'proposal_package.json').read_bytes())))
        self.save_config()


class HeldSuiteCLITests(PolicyCLIFixture):
    suite_version = "vnext-verified-consumer-2"

    def test_registration_does_not_activate_unqualified_suite(self):
        code,result=self.invoke('vnext-admit')
        self.assertEqual(code,2,result)
        self.assertEqual(result['reason_code'],'vnext_mode_unavailable')
        self.assertFalse(self.root.exists())


class PolicyCLITests(PolicyCLIFixture):
    def test_coherent_admission_matrix_and_scope_required(self):
        for workflow in ('standard','mvp'):
            for profile_set in ('stateful_system','balanced_mvp','utility_mvp'):
                for mode in ('horizontal','vertical'):
                    with self.subTest(workflow=workflow,profile_set=profile_set,mode=mode):
                        self.configure(workflow,profile_set,mode)
                        code,result=self.invoke('vnext-admit','--dry-run')
                        self.assertEqual(code,0,result)
                        self.assertFalse(self.root.exists())
        self.configure(scope=False)
        code,result=self.invoke('vnext-admit','--dry-run')
        self.assertEqual(code,2,result);self.assertFalse(self.root.exists())
        self.assertEqual(self.reviewer.calls,0)

    def test_mvp_utility_horizontal_public_completion_and_phase2_refusal(self):
        code,result=self.invoke('live-phase1')
        self.assertEqual(code,0,result)
        self.assertEqual(result['gate'],'phase1_complete')
        self.assertEqual(self.reviewer.calls,4)
        self.assertFalse(json.loads((self.root/'rounds/run_state.json').read_bytes())['ready_for_phase_2'])
        calls=self.reviewer.calls
        code,result=self.invoke('live-phase1')
        self.assertEqual(code,0,result);self.assertEqual(self.reviewer.calls,calls)
        before=self.files()
        code,result=self.invoke('promote-phase2')
        self.assertEqual(code,2,result);self.assertEqual(self.files(),before)
        self.assertFalse((self.root/'rounds/phase2/entry.json').exists())

    def test_mvp_balanced_vertical_public_completion(self):
        self.configure(profile_set='balanced_mvp',mode='vertical')
        code,result=self.invoke('live-phase1')
        self.assertEqual(code,0,result)
        self.assertEqual(result['gate'],'phase1_complete')
        self.assertEqual(self.reviewer.calls,3)
        self.assertFalse(json.loads((self.root/'rounds/run_state.json').read_bytes())['ready_for_phase_2'])

    def test_mvp_balanced_horizontal_public_completion(self):
        self.configure(profile_set='balanced_mvp')
        code,result=self.invoke('live-phase1')
        self.assertEqual(code,0,result)
        self.assertEqual(result['gate'],'phase1_complete')
        self.assertEqual(self.reviewer.calls,3)
        self.assertFalse(json.loads((self.root/'rounds/run_state.json').read_bytes())['ready_for_phase_2'])

    def test_registered_mvp_suite_edits_verifies_promotes_and_rereviews(self):
        from whetstone.vnext_verified_run import open_verified_run
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        from test_vnext_proposal_requests import Client as Editor
        from test_vnext_semantic_requests import Client as Verifier
        from vnext_fixtures import STAMP
        for row in self.f.original.review['profiles']:row['budget']=2
        self.f.original.review_ref=self.f.save('inputs/review.json',self.f.original.review)
        self.f.job['review_configuration_hash']=self.f.original.review_ref['hash'];self.f.rebind()
        self.fixture.package.update(job_descriptor=self.f.job_ref,review_configuration=self.f.original.review_ref)
        self.fixture.save_package()
        self.config['vnext_input_package']['hash']=sha256_bytes((self.fixture.source/'proposal_package.json').read_bytes())
        self.save_config()
        code,result=self.invoke('vnext-admit');self.assertEqual(code,0,result)
        self.reviewer.callback=canonical_json_bytes
        original=self.reviewer.review
        def current(prompt):
            response=json.loads(original(prompt));request=json.loads(prompt.splitlines()[-1])
            response['feedback']['draft_hash']=request['base_draft_hash']
            return canonical_json_bytes(response)
        self.reviewer.review=current
        editor=Editor()
        with open_verified_run(self.root) as run:
            self.assertEqual(run.review_next(client=self.reviewer).status,'complete')
            run.admit_reviewed_round()
            self.assertEqual(run.request(round_number=1,client=editor).value.status,'complete')
            candidate=run.register(round_number=1,created_at=STAMP).value
            context=load_registered_semantic_context(run.store,admission=run._history(),candidate_id=candidate['candidate_id'])
            verifier=Verifier(context)
            self.assertTrue(run.verify(client=verifier,decided_at=STAMP).value.decision['promotion_permitted'])
            self.assertEqual(run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'],1)
            self.assertFalse(run.phase1_closeout().accepted)
            self.reviewer.callback=self.clean
            for _ in range(4):self.assertEqual(run.review_next(client=self.reviewer).status,'complete')
            self.assertTrue(run.finish_phase1().accepted)
        self.assertEqual((self.reviewer.calls,editor.calls,verifier.calls),(5,1,1))
        code,result=self.invoke('live-phase1')
        self.assertEqual(code,0,result);self.assertEqual(result['gate'],'phase1_complete')
        self.assertEqual(self.reviewer.calls,5)

    def test_mvp_focused_public_completion_does_not_accept_full_phase(self):
        self.f.original.review['phase1_selection']=dict(kind='focused',profile='buildability')
        self.f.original.review_ref=self.f.save('inputs/review.json',self.f.original.review)
        self.f.job['review_configuration_hash']=self.f.original.review_ref['hash'];self.f.rebind()
        self.fixture.package.update(job_descriptor=self.f.job_ref,review_configuration=self.f.original.review_ref)
        self.fixture.save_package()
        self.config['vnext_input_package']['hash']=sha256_bytes((self.fixture.source/'proposal_package.json').read_bytes())
        self.save_config()
        code,result=self.invoke('live-focused-phase1','--profile','buildability')
        self.assertEqual(code,0,result)
        self.assertEqual(result['operator']['terminal_report']['terminal_state'],'FOCUSED_PROFILE_STABLE')
        self.assertFalse(result['operator']['accepted'])
        self.assertEqual(self.reviewer.calls,1)

class CloseoutSeverityCLITests(PolicyCLIFixture):

    def use_nit_reviewer(self, classification):
        def respond(packet):
            item = packet['feedback']['feedback'][0]
            item.update(baseline_severity='nit', authority_impact=None, determinism_impact=None,
                        rubric_impact=None, in_scope=False)
            packet['classifications'][0].update(classification=classification,
                                                scope_surface_ids=['future-hardening'])
            return canonical_json_bytes(packet)

        self.reviewer.callback = respond

    def test_approved_deferred_nits_close_and_replay(self):
        code, result = self.invoke('vnext-admit', '--dry-run')
        self.assertEqual(code, 0, result)
        self.assertFalse(self.root.exists())
        self.use_nit_reviewer('deferable')
        code, result = self.invoke('live-phase1')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['gate'], 'phase1_complete')
        operator = result['operator']
        self.assertEqual(operator['terminal_report']['terminal_state'], 'PHASE_1_STABLE')
        self.assertTrue(operator['accepted'])
        self.assertFalse(operator['phase2_permitted'])
        ref = operator['closeout_ref']
        raw = (self.root / ref['path']).read_bytes()
        self.assertEqual(sha256_bytes(raw), ref['hash'])
        evidence = json.loads(raw)
        self.assertEqual(evidence['schema_version'], 'vnext-verified-phase1-closeout-v6')
        self.assertEqual(evidence['global_blocking_findings'], [])
        self.assertEqual(evidence['scope_contract_hash'], self.f.job['scope_contract_hash'])
        rows = evidence['deferred_findings']
        profiles = PROFILE_SETS['utility_mvp'].phase_1_profiles
        self.assertCountEqual([row['profile'] for row in rows], profiles)
        for row in rows:
            self.assertEqual((row['severity'], row['scope_surface_ids']), ('nit', ['future-hardening']))
        code, replay = self.invoke('live-phase1')
        self.assertEqual(code, 0, replay)
        self.assertTrue(replay['operator']['accepted'])
        self.assertEqual(replay['operator']['closeout_ref'], ref)
        self.assertEqual((self.root / ref['path']).read_bytes(), raw)
        self.assertEqual(self.reviewer.calls, len(profiles))

    def test_decision_nit_blocks_on_deferred_surface_and_reentry(self):
        self.use_nit_reviewer('operator_decision_required')
        for _ in range(2):
            code, result = self.invoke('live-phase1')
            self.assertEqual((code, result['gate']), (2, 'finding_admission'))
            self.assertFalse(result['operator']['phase_complete'])
            self.assertEqual(result['operator']['findings'][0]['classification'],
                             'operator_decision_required')
            row = result['review']['review']['feedback']['feedback'][0]
            self.assertEqual(row['normalized_severity'], 'nit')
            self.assertEqual(self.reviewer.calls, 1)
            self.assertFalse(list((self.root / 'rounds/phase1_closeouts').glob('**/closeout.json')))
