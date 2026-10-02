"""The Q1 command consumer hands Reviewer evidence directly to existing owners."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_run import VerifiedRun, open_verified_run
from whetstone.vnext_local_storage import LocalAuthorityStore
import test_vnext_verified_cli as cli


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class ReviewerHandoffTests(unittest.TestCase):
    setUpClass = cli.VerifiedCLITests.setUpClass
    setUp = cli.VerifiedCLITests.setUp
    patch = cli.VerifiedCLITests.patch
    qualify = cli.VerifiedCLITests.qualify
    save_config = cli.VerifiedCLITests.save_config
    clean = staticmethod(cli.VerifiedCLITests.clean)
    invoke = cli.VerifiedCLITests.invoke
    files = cli.VerifiedCLITests.files
    stage_phase2 = cli.VerifiedCLITests.stage_phase2

    def ready(self, *, effect='clarification', finding_pass=1):
        self.qualify()
        code,result=self.invoke('live-phase1');self.assertEqual(code,0,result)
        self.stage_phase2()
        def respond(client,packet):
            inputs=json.loads(client.prompts[-1].splitlines()[-1])
            packet['draft_hash']=sha256_bytes(inputs['draft'].encode())
            hints=[]
            if client.calls == finding_pass:
                mutable=next(r for r in inputs['authority']['bindings'] if r['role']=='mutable_target')
                hints=[dict(feedback_id=row['feedback_id'],classification='editor_fixable',
                    authority_scope_ids=mutable['authority_scopes'],source_authority_binding_ids=[mutable['binding_id']],
                    scope_surface_ids=[],compatibility_change='none',requested_effects=[effect]) for row in packet['feedback']]
            else:packet['feedback']=[]
            return canonical_json_bytes(dict(review=packet,rubric_findings=[],classifications=hints))
        self.phase2_reviewer.callback=respond

    def test_product_decision_stops_with_bound_advice_before_editor(self):
        self.ready(effect='weaken')
        code,result=self.invoke('live-phase2')
        self.assertEqual(code,2,result)
        self.assertEqual(result['gate'],'operator_or_advice_required',result)
        self.assertIn('operator',result)
        self.assertEqual(self.phase2_reviewer.calls,1)
        with open_verified_run(self.root) as run:
            view=run.prepare_phase2_advice()
            self.assertEqual(view['status'],'bound')
            self.assertEqual(view['binding']['findings'][0]['classification'],'operator_decision_required')
            advice=json.loads(run.store.read(view['binding']['advice']['path']))
            advice['findings'][0]['requested_effects']=['clarification']
            before=self.files()
            with self.assertRaisesRegex(ValueError,'exact Reviewer response'):run.bind_phase2_advice(advice)
            self.assertEqual(self.files(),before)
        before=self.files()
        code,result=self.invoke('status','--format','json');self.assertEqual(code,0,result)
        self.assertEqual(self.files(),before)
        code,result=self.invoke('live-phase2');self.assertEqual(code,2,result)
        self.assertEqual(self.phase2_reviewer.calls,1)

    def test_later_pass_interrupted_handoff_recovers_only_attachment(self):
        self.ready(finding_pass=2)
        publish=LocalAuthorityStore.publish
        def uncertain(store,token,path,packet):
            result=publish(store,token,path,packet)
            if path.endswith('/finding_advice.json') and '/pass-2/' in path:
                raise OSError('fixture lost advice acknowledgement')
            return result
        with patch.object(LocalAuthorityStore,'publish',uncertain):
            code,result=self.invoke('live-phase2')
        self.assertEqual(code,2,result)
        self.assertEqual(self.phase2_reviewer.calls,2)
        code,result=self.invoke('status','--format','json');self.assertEqual(code,0,result)
        self.assertEqual(result['recovery'],'advice',result)
        before=self.files()
        code,result=self.invoke('resume','--dry-run');self.assertEqual(code,0,result)
        self.assertEqual(self.files(),before)
        code,result=self.invoke('resume');self.assertEqual(code,0,result)
        self.assertEqual(self.phase2_reviewer.calls,2)
        code,result=self.invoke('status','--format','json');self.assertEqual(code,0,result)
        self.assertEqual(result['gate'],'correction_required',result)
        self.assertFalse(list(self.root.rglob('candidate_unverified.md')))

    def test_correction_flows_through_editor_verifier_and_promotion(self):
        from test_vnext_proposal_requests import Client as Editor
        from test_vnext_semantic_requests import Client as Verifier
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        self.ready()
        editor=Editor();verifiers=[]
        self.patch('whetstone.vnext_proposal_cli.NativePatchProposalClient',return_value=editor)
        def verifier(**kwargs):
            with open_verified_run(self.root) as run:
                history=run._history()
                creation=history.inspect().creations[-1]
                context=load_registered_semantic_context(run.store,admission=history,candidate_id=creation['candidate_id'])
            client=Verifier(context);verifiers.append(client);return client
        self.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient',side_effect=verifier)
        request=VerifiedRun.request
        def request_after_readonly_status(run, **options):
            from whetstone.vnext_verified_command_state import inspect_command
            before=self.files()
            with patch.object(run.store,'locked',side_effect=AssertionError('status acquired writer fence')):
                self.assertEqual(inspect_command(run)['gate'],'proposal')
            self.assertEqual(self.files(),before)
            result=request(run, **options)
            self.assertEqual(result.value.status,'complete',result)
            print('  Editor response retained',file=sys.stderr,flush=True)
            return result
        # This case ends at the promotion boundary; clean convergence has its
        # own command test. No later Reviewer call is needed to prove handoff.
        class PromotionReached(Exception): pass
        promote=VerifiedRun.promote
        def stop_after_promotion(run, **options):
            promote(run, **options)
            raise PromotionReached()
        with patch.object(VerifiedRun,'request',request_after_readonly_status), \
                patch.object(VerifiedRun,'promote',stop_after_promotion), self.assertRaises(PromotionReached):
            code,result=self.invoke('live-phase2')
            self.fail(f'Command stopped before promotion: {code}, {result}; Editor calls={editor.calls}, '
                      f'Verifier calls={sum(c.calls for c in verifiers)}')
        self.assertEqual(editor.calls,1)
        self.assertEqual(sum(c.calls for c in verifiers),1)
        with open_verified_run(self.root) as run:
            self.assertEqual(run.inspect().current_pointer['promotion_ordinal'],1)
