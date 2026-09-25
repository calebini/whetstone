"""Declaration-aware budgeted reviews and evidence-derived Phase 2 closeout."""
from copy import deepcopy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_sequence as sequence_tests
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_closeout import STATE_FIELD, MIRROR
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class Phase2CloseoutTests(unittest.TestCase):
    setUpClass=sequence_tests.Phase2SequenceTests.setUpClass
    fixture=sequence_tests.Phase2SequenceTests.fixture
    files=sequence_tests.Phase2SequenceTests.files
    reopen=sequence_tests.Phase2SequenceTests.reopen
    ready=sequence_tests.Phase2SequenceTests.ready
    reviewed=sequence_tests.Phase2SequenceTests.reviewed
    review=sequence_tests.Phase2SequenceTests.review
    promote=sequence_tests.Phase2SequenceTests.promote
    admitted=sequence_tests.Phase2SequenceTests.admitted
    candidate=sequence_tests.Phase2SequenceTests.candidate
    config=sequence_tests.Phase2SequenceTests.config
    next_client=sequence_tests.Phase2SequenceTests.next_client
    advance=sequence_tests.Phase2SequenceTests.advance
    advice=sequence_tests.Phase2SequenceTests.advice
    clean_start=sequence_tests.Phase2SequenceTests.clean_start

    def start(self,**kwargs):
        kwargs['phase2_closeout_contract']=True
        return sequence_tests.Phase2SequenceTests.start(self,**kwargs)

    def final_ready(self):
        f,reviewer,client=self.clean_start()
        self.advance(f,client)  # adversarial uses the existing request format/budget
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'committed declaration package'):
            f.run.bind_phase2_next_review(client.transport_binding)
        self.assertEqual(self.files(f),before)
        prepared=f.run.prepare_phase2_declaration()
        return f,reviewer,client,prepared

    def test_scheduled_final_review_converges_only_after_evidence_and_state_recovery(self):
        f,reviewer,client,prepared=self.final_ready()
        authority=f.store.read('rounds/current_verified.json');draft=f.store.read('spec.md')
        bound,result,consumed=self.advance(f,client)
        self.assertEqual(bound.request['schema_version'],'vnext-phase2-review-request-v3')
        self.assertEqual(bound.request['declaration'],prepared['reference'])
        self.assertIn('\n- convergence_declaration.md\n',bound.prompt)
        inputs=json.loads(client.prompts[-1].splitlines()[-1])
        self.assertEqual(set(inputs['declaration']['artifacts']),{'declaration','rubric_manifest','unresolved_issues','rubric_gaps'})
        self.assertEqual(consumed['accepted_passes'],3)
        before=self.files(f)
        with patch.object(f.store,'locked',side_effect=AssertionError('status took lock')):
            view=f.run.phase2_closeout()
        self.assertFalse(view['committed']);self.assertFalse(view['phase_complete'])
        self.assertEqual(view['packet']['terminal_state'],'CONVERGED')
        self.assertEqual(self.files(f),before)
        finished=f.run.finish_phase2()
        self.assertTrue(finished['committed']);self.assertFalse(finished['phase_complete'])
        self.assertFalse((f.root/MIRROR).exists())
        final=f.run.reconcile_phase2_state()
        self.assertTrue(final['phase_complete'])
        self.assertEqual(final['gate'],'phase2_state_recovered')
        self.assertEqual(json.loads(f.store.read(STATE_PATH))[STATE_FIELD],final['reference'])
        text=f.store.read(MIRROR).decode()
        self.assertIn('declaration_status: accepted',text)
        self.assertIn('final_draft_sha256:',text)
        after=self.files(f);self.reopen(f)
        self.assertTrue(f.run.phase2_closeout()['phase_complete'])
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual(self.files(f),after)
        self.assertEqual(f.store.read('rounds/current_verified.json'),authority)
        self.assertEqual(f.store.read('spec.md'),draft)
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))
        self.assertEqual(f.run.bind_phase2_next_review(client.transport_binding)['gate'],'declaration_closeout_required')

        script = """import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path=sys.argv[1:];manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(run.phase2_closeout()))
"""
        child=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path)],
                             capture_output=True,timeout=180)
        self.assertEqual(child.returncode,0,child.stderr.decode())
        self.assertTrue(json.loads(child.stdout)['phase_complete'])
        self.assertEqual(self.files(f),after)

    @staticmethod
    def lose(original,suffix):
        def publish(token,path,value):
            result=original(token,path,value)
            if path.endswith(suffix):raise OSError('lost acknowledgement')
            return result
        return publish

    def test_package_prefixes_recover_and_sources_are_barriers_before_request(self):
        f,reviewer,client=self.clean_start()
        self.advance(f,client)
        for suffix in ('/rubric_manifest.json','/unresolved_issues.json','/rubric_gaps.json',
                       '/convergence_declaration.md','/commit.json'):
            with self.subTest(suffix=suffix):
                with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,suffix)):
                    with self.assertRaisesRegex(OSError,'lost acknowledgement'):f.run.prepare_phase2_declaration()
                self.reopen(f)
        package=f.run.prepare_phase2_declaration()
        before=self.files(f)
        sync=f.store.synchronize_existing
        def fail(token,path,**options):
            if path==package['reference']['path']:raise OSError('declaration barrier')
            return sync(token,path,**options)
        with patch.object(f.store,'synchronize_existing',side_effect=fail):
            with self.assertRaisesRegex(OSError,'declaration barrier'):
                f.run.bind_phase2_next_review(client.transport_binding)
        self.assertEqual(self.files(f),before)
        for key in ('declaration','rubric_manifest','unresolved_issues','rubric_gaps'):
            path=f.root/package['declaration'][key]['path'];raw=path.read_bytes();path.unlink()
            with self.assertRaisesRegex(ValueError,'lacks dependencies'):f.run.prepare_phase2_declaration()
            path.write_bytes(raw)
        self.assertTrue(f.run.bind_phase2_next_review(client.transport_binding).committed)
        self.assertEqual((reviewer.calls,client.calls),(1,1))

    def test_final_review_and_closeout_lost_writes_recover_without_duplicate_credit(self):
        f,reviewer,client,prepared=self.final_ready()
        for suffix in ('/inputs.json','/prompt.txt','/request.json'):
            with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,suffix)):
                with self.assertRaises(OSError):f.run.bind_phase2_next_review(client.transport_binding)
            self.reopen(f)
        bound=f.run.bind_phase2_next_review(client.transport_binding)
        for suffix in ('/response.json','/result.json'):
            with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,suffix)):
                with self.assertRaises(OSError):
                    f.run.continue_phase2_pass(3,action='execute',client=client,continuation=suffix=='/result.json')
            self.reopen(f)
            if suffix=='/response.json':
                self.assertEqual(f.run.continue_phase2_pass(3,action='execute').status,'continuation_required')
        self.assertEqual(f.run.continue_phase2_pass(3,action='execute').status,'complete')
        with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,'/consumption.json')):
            with self.assertRaises(OSError):f.run.continue_phase2_pass(3,action='consume')
        self.reopen(f)
        self.assertEqual(f.run.continue_phase2_pass(3,action='consume')['accepted_passes'],3)
        for suffix in ('/convergence_declaration.md','/terminal_report.json','/commit.json'):
            with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,suffix)):
                with self.assertRaises(OSError):f.run.finish_phase2()
            self.reopen(f)
        view=f.run.finish_phase2()
        self.assertFalse(view['phase_complete'])
        with patch.object(f.store,'publish',side_effect=self.lose(f.store.publish,MIRROR)):
            with self.assertRaises(OSError):f.run.reconcile_phase2_state()
        self.reopen(f)
        self.assertNotIn(STATE_FIELD,json.loads(f.store.read(STATE_PATH)))
        materialize=f.store.materialize
        def lose_state(token,path,raw,**options):
            result=materialize(token,path,raw,**options)
            if path==STATE_PATH:raise OSError('state acknowledgement')
            return result
        with patch.object(f.store,'materialize',side_effect=lose_state):
            with self.assertRaisesRegex(OSError,'state acknowledgement'):f.run.reconcile_phase2_state()
        self.reopen(f)
        sync=f.store.synchronize_existing
        def fail_state(token,path,**options):
            if path==STATE_PATH:raise OSError('state barrier')
            return sync(token,path,**options)
        with patch.object(f.store,'synchronize_existing',side_effect=fail_state):
            with self.assertRaisesRegex(OSError,'state barrier'):f.run.reconcile_phase2_state()
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))
        self.assertFalse((f.root/'rounds/phase2/review_requests/pass-4').exists())

    def test_final_findings_remain_blocked_work_not_terminal_or_edit_permission(self):
        for severity in ('major','minor'):
            with self.subTest(severity=severity):
                f,reviewer,client,prepared=self.final_ready()
                def feedback(owner,packet):
                    for row in packet['feedback']:
                        row.update(normalized_severity=severity,baseline_severity=severity,
                                   authority_impact=None,determinism_impact=None,rubric_impact=None)
                        row['affected_sections']=['convergence_declaration.md']
                        row['oscillation_key']['section_id']='convergence_declaration.md'
                    return canonical_json_bytes(packet)
                client.callback=feedback
                bound,result,consumed=self.advance(f,client)
                self.assertEqual(result.review['feedback']['feedback'][0]['normalized_severity'],severity)
                before=self.files(f)
                view=f.run.phase2_closeout()
                self.assertEqual(view['gate'],'declaration_reconciliation_required')
                self.assertIn('final_findings_require_reconciliation',view['blockers'])
                self.assertFalse(view['committed']);self.assertFalse(view['phase_complete'])
                with self.assertRaisesRegex(ValueError,'no terminal'):f.run.finish_phase2()
                with self.assertRaisesRegex(ValueError,'read-only'):
                    f.run.continue_phase2_pass(3,action='admit')
                self.assertEqual(self.files(f),before)
                self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))

    def test_stale_evidence_and_unowned_mirrors_cannot_confer_completion(self):
        f,reviewer,client,prepared=self.final_ready()
        bound,_,_=self.advance(f,client)
        paths=[prepared['reference']['path'],prepared['declaration']['declaration']['path'],
               bound.request['configuration']['path'],bound.inputs['configuration']['rubric']['artifact']['path'],
               'rounds/current_verified.json',bound.request_ref['path'].replace('request.json','execution/attempts/1/response.json')]
        for relative in paths:
            path=f.root/relative;raw=path.read_bytes();path.write_bytes(raw+b' ')
            before=self.files(f)
            with self.subTest(path=relative):
                with self.assertRaises(ValueError):f.run.finish_phase2()
                self.assertEqual(self.files(f),before)
            path.write_bytes(raw)
        state=json.loads(f.store.read(STATE_PATH));state[STATE_FIELD]={'path':'fake','hash':'0'*64}
        (f.root/STATE_PATH).write_bytes(canonical_json_bytes(state))
        self.assertFalse(f.run.phase2_closeout()['committed'])
        finished=f.run.finish_phase2()
        (f.root/MIRROR).write_text('operator-owned declaration\n')
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'root declaration conflicts'):f.run.reconcile_phase2_state()
        self.assertEqual(self.files(f),before)
        (f.root/MIRROR).unlink()
        recovered=f.run.reconcile_phase2_state()
        self.assertTrue(recovered['phase_complete'])
        self.assertEqual(json.loads(f.store.read(STATE_PATH))[STATE_FIELD],finished['reference'])
        for key in ('final_declaration','terminal_report'):
            path=f.root/finished['packet'][key]['path'];raw=path.read_bytes();path.unlink()
            with self.assertRaisesRegex(ValueError,'lacks dependencies'):f.run.finish_phase2()
            path.write_bytes(raw)

    def test_declaration_regeneration_after_verified_correction_retains_old_package(self):
        f,reviewer,client=self.clean_start()
        old=f.run.prepare_phase2_declaration()
        old_bytes={ref['path']:f.store.read(ref['path']) for key,ref in old['declaration'].items()
                   if key in {'declaration','rubric_manifest','unresolved_issues','rubric_gaps'}}
        client=self.next_client(reviewer,clean=False)
        bound,result,_=self.advance(f,client)
        f.run.continue_phase2_pass(2,action='advice',advice=self.advice(bound,result))
        f.run.continue_phase2_pass(2,action='admit')
        _,verifier=self.candidate(f,bound.request['round_number'])
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        self.reopen(f)
        changed=f.run.prepare_phase2_declaration()
        self.assertNotEqual(changed['declaration']['current_verified_pointer'],old['declaration']['current_verified_pointer'])
        self.assertNotEqual(changed['declaration']['final_draft_sha256'],old['declaration']['final_draft_sha256'])
        client=self.next_client(reviewer)
        self.advance(f,client)  # clean adversarial verification of promoted draft
        final=f.run.prepare_phase2_declaration()
        bound,_,consumed=self.advance(f,client)  # final strict verification
        self.assertEqual(bound.request['declaration'],final['reference'])
        self.assertEqual(consumed['accepted_passes'],4)
        self.assertTrue(f.run.finish_phase2()['committed'])
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        for path,raw in old_bytes.items():self.assertEqual(f.store.read(path),raw)
        self.assertEqual((f.editor.calls,verifier.calls),(1,1))

    def test_unpinned_completed_sequence_cannot_invent_declaration_review(self):
        with patch.object(self,'start',side_effect=lambda **kw: sequence_tests.Phase2SequenceTests.start(self,**kw)):
            f,reviewer,client=self.clean_start()
        self.advance(f,client);self.advance(f,client)
        before=self.files(f)
        for operation in (f.run.prepare_phase2_declaration,f.run.phase2_closeout,f.run.finish_phase2,f.run.reconcile_phase2_state):
            with self.assertRaisesRegex(ValueError,'outside supported suite'):operation()
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'closeout_required')
        self.assertEqual(self.files(f),before)
