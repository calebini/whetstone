"""Real advice, repair and gap inputs, including retained-publication recovery."""
from copy import deepcopy
import json
import sys
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_run import open_verified_run,VerifiedRun
from whetstone.vnext_verified_phase2_advice import ADVICE_PATH
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from test_vnext_proposal_requests import Client as Editor
from test_vnext_semantic_requests import Client as Verifier
from vnext_fixtures import STAMP
from vnext_q1_command_fixtures import Phase2CommandCase


class OperatorBoundaryCommands(Phase2CommandCase):
    def setUp(self):
        if sys.platform!='darwin':self.skipTest('D8 requires macOS/APFS')
        super().setUp()

    def test_exact_advice_and_repair_publication_stop_before_child_execution(self):
        review=self.consumed_review(mixed=True)
        advice=review.review['advice']
        path=self.config_path.parent/'advice.json';path.write_bytes(canonical_json_bytes(advice))
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('preview took fence')):
            code,result=self.call('vnext-decisions','--advice',str(path),'--dry-run')
        self.assertEqual(code,0,result);self.assertEqual(self.files(),before)
        bad=deepcopy(advice);bad['findings'][0]['requested_effects']=['weaken'];path.write_bytes(canonical_json_bytes(bad))
        self.refuses('vnext-decisions','--advice',str(path));path.write_bytes(canonical_json_bytes(advice))
        with self.lost_publication(lambda p:p==ADVICE_PATH):
            code,result=self.call('vnext-decisions','--advice',str(path))
        self.assertEqual(code,2,result)
        self.assertEqual(self.inspect_readonly()['recovery'],'advice')
        code,result=self.call('resume');self.assertEqual(code,0,result)
        self.assertEqual(self.phase2_reviewer.calls,1)
        editor=Editor()
        with open_verified_run(self.root) as run:
            selected=run.admit_phase2_round();number=json.loads(run.store.read(selected['path']))['round_number']
            self.assertEqual(run.request(round_number=number,client=editor).value.status,'complete')
            parent=run.register(round_number=number,created_at=STAMP).value
            context=load_registered_semantic_context(run.store,admission=run._history(),candidate_id=parent['candidate_id'])
            verifier=Verifier(context);response=json.loads(verifier.valid)
            response['verdict']='reject';response['finding_results'][0]['disposition']='partially_resolved'
            verifier.responses=[canonical_json_bytes(response)]
            self.assertFalse(run.verify(client=verifier,decided_at=STAMP).value.decision['promotion_permitted'])
            run.publish_phase2_correction_failure();run.reconcile_phase2_correction_failure_state()
            context=run.phase2_repair_context(candidate_id=parent['candidate_id'])
        packet=dict(schema_version='vnext-phase2-repair-request-v1',
            **{k:context[k] for k in ('job_id','round_number','base_pointer','source_creation','source_verification')},
            operation_ids=[r['operation_id'] for r in context['operations']],
            finding_ids=[r['finding_id'] for r in context['findings'] if r['disposition']!='resolved'],
            limits={**context['limits'],'max_operations':1},decided_by='fixture operator',decided_at=STAMP,
            rationale='Repair the failed operation without expanding its effects.')
        path=self.config_path.parent/'repair.json';path.write_bytes(canonical_json_bytes(packet))
        before=self.files()
        code,preview=self.call('vnext-decide','--repair-request',str(path),'--dry-run')
        self.assertEqual(code,0,preview);self.assertEqual(self.files(),before)
        bad=deepcopy(packet);bad['base_pointer']['hash']='f'*64;path.write_bytes(canonical_json_bytes(bad))
        self.refuses('vnext-decide','--repair-request',str(path));path.write_bytes(canonical_json_bytes(packet))
        for suffix in ('/admission.json','/followup_transaction.json'):
            with self.lost_publication(lambda p:p.endswith(suffix)):
                code,result=self.call('vnext-decide','--repair-request',str(path))
            self.assertEqual(code,2,result)
        code,result=self.call('vnext-decide','--repair-request',str(path));self.assertEqual(code,0,result)
        self.assertEqual(result['reference'],preview['reference'])
        self.assertEqual((self.phase2_reviewer.calls,editor.calls,verifier.calls),(1,1,1))
        with open_verified_run(self.root) as run:self.assertEqual(len(run._history().inspect().creations),1)
        for name,raw in before.items():self.assertEqual((self.root/name).read_bytes(),raw,name)

    def test_gap_acceptance_and_later_declaration_interruption_do_not_resume_or_converge(self):
        self.consumed_review(gap=True)
        with open_verified_run(self.root) as run:context=run.phase2_gap_acceptance_context()
        packet=dict(context['bindings'],gaps=sorted([r['selection'] for r in context['gaps']],key=lambda r:r['gap_id']),
            decided_by='fixture operator',decided_at=STAMP,rationale='Accept these exact minor gaps for this draft.')
        self.assertTrue(packet['gaps'])
        path=self.config_path.parent/'gaps.json';path.write_bytes(canonical_json_bytes(packet))
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('preview took fence')):
            code,preview=self.call('vnext-decide','--gap-acceptance',str(path),'--dry-run')
        self.assertEqual(code,0,preview);self.assertFalse(preview['committed']);self.assertEqual(self.files(),before)
        bad=deepcopy(packet);bad['gaps']*=2;path.write_bytes(canonical_json_bytes(bad))
        self.refuses('vnext-decide','--gap-acceptance',str(path));path.write_bytes(canonical_json_bytes(packet))
        with self.lost_publication(lambda p:'/gap_acceptances/' in p):
            code,result=self.call('vnext-decide','--gap-acceptance',str(path))
        self.assertEqual(code,2,result)
        code,result=self.call('vnext-decide','--gap-acceptance',str(path));self.assertEqual(code,0,result)
        self.assertTrue(result['committed']);self.assertEqual(self.phase2_reviewer.calls,1)
        with open_verified_run(self.root) as run:self.assertFalse(run.phase2_closeout()['phase_complete'])
        self.assertEqual(self.inspect_readonly()['gate'],'review')
        self.refuses('resume')
        # The accepted gap requires the ordinary adversarial pass before the
        # later declaration. Reach that fixture boundary through its real owner.
        def clean(client,packet):
            inputs=json.loads(client.prompts[-1].splitlines()[-1])
            packet.update(feedback=[],draft_hash=sha256_bytes(inputs['draft'].encode()))
            return canonical_json_bytes(dict(review=packet,rubric_findings=[],classifications=[]))
        self.phase2_reviewer.callback=clean
        with open_verified_run(self.root) as run:
            run.bind_phase2_next_review(self.phase2_reviewer.transport_binding)
            result=run.continue_phase2_pass(2,action='execute',client=self.phase2_reviewer)
            self.assertEqual(result.status,'complete');run.continue_phase2_pass(2,action='consume')
        self.assertEqual(self.phase2_reviewer.calls,2)
        state=self.inspect_readonly();self.assertEqual(state['gate'],'declaration_maintenance_required')
        asset=state['declaration']['packet']['rubric_manifest']['path']
        with self.lost_publication(lambda p:p==asset):code,result=self.call('live-phase2')
        self.assertEqual(code,2,result);state=self.inspect_readonly()
        self.assertEqual(state['gate'],'declaration_maintenance_required');self.assertIsNone(state['recovery'])
        self.assertEqual(self.phase2_reviewer.calls,2)
        self.refuses('resume');self.refuses('resume','--dry-run')
        class Prepared(Exception):pass
        prepare=VerifiedRun.prepare_phase2_declaration
        def stop(run):
            value=prepare(run);self.assertTrue(value['committed']);raise Prepared()
        with patch.object(VerifiedRun,'prepare_phase2_declaration',stop),self.assertRaises(Prepared):self.call('live-phase2')
        self.assertEqual(self.phase2_reviewer.calls,2)
        self.assertFalse((self.root/'rounds/candidate_index/creation-1.json').exists())
        with open_verified_run(self.root) as run:
            self.assertFalse(run.phase2_closeout()['phase_complete'])
            self.assertEqual(run.inspect().current_pointer['promotion_ordinal'],0)
