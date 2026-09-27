"""Bound rubric requirements reach both candidate roles and survive replay."""
import json
import sys
import unittest

import test_vnext_verified_phase2_source_correction as source
import test_vnext_verified_phase2_signals as signals
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RubricRuntimeTests(unittest.TestCase):
    setUpClass = source.SourceCorrectionTests.setUpClass
    fixture = source.SourceCorrectionTests.fixture
    files = source.SourceCorrectionTests.files
    reopen = source.SourceCorrectionTests.reopen
    review = source.SourceCorrectionTests.review
    promote = source.SourceCorrectionTests.promote
    config = source.SourceCorrectionTests.config
    candidate = source.SourceCorrectionTests.candidate
    advice = source.SourceCorrectionTests.advice
    advance = source.SourceCorrectionTests.advance

    def start(self, **kwargs):
        return source.SourceCorrectionTests.start(self, phase2_rubric_contract=True, **kwargs)

    def ready(self):
        f, client, config = source.SourceCorrectionTests.ready(self, bind=False)
        client.transport_binding['output_schema_hash'] = sha256_bytes((CONTRACT_ROOT/'schemas/vnext_phase2_rubric_response_v1.schema.json').read_bytes())
        f.run.bind_phase2_review(client.transport_binding)
        return f, client, config

    def response(self, *, gaps=True, invalid=False):
        base = signals.SignalRuntimeTests.response(self, 'clarify', 'major', empty=not gaps)
        def callback(client,packet):
            packet = json.loads(base(client,packet))
            inputs = json.loads(client.prompts[-1].splitlines()[-1]);annotations=[]
            if gaps:
                packet['feedback'][0]['rubric_impact']='major'
                requirement=next(row for row in inputs['rubric_catalogue'] if row['text'].startswith('- Required artifacts lack'))
                annotations=[dict(feedback_id=packet['feedback'][0]['feedback_id'],rubric_anchor=requirement['rubric_anchor'],
                                  requirement_hash='0'*64 if invalid else requirement['requirement_hash'])]
            return canonical_json_bytes(dict(review=packet,rubric_findings=annotations))
        return callback

    def test_gap_resolves_only_after_verified_promotion_and_resolution_receipt(self):
        f, client, _ = self.ready();client.callback=self.response()
        result=f.run.run_phase2_review(client=client);self.assertEqual(result.status,'complete')
        f.run.consume_phase2_result()
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        f.run.bind_phase2_advice(self.advice(bound,result));ref=f.run.admit_phase2_round()
        number=json.loads(f.store.read(ref['path']))['round_number']
        creation,verifier=self.candidate(f,number)
        context=load_registered_semantic_context(f.store,admission=f.run._history(),candidate_id=creation['candidate_id'])
        self.assertEqual(context.packet['phase2']['rubric']['findings'],result.review['rubric_findings'])
        handoff=f.run._history().load_inputs(f.store.read,number)['phase2']
        self.assertEqual(handoff['rubric']['findings'],result.review['rubric_findings'])
        f.run.verify(client=verifier,decided_at=STAMP);f.run.promote(prepared_at=STAMP)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'resolution_publication_required')
        f.run.publish_phase2_resolutions();self.reopen(f)
        f.run.bind_phase2_next_review(client.transport_binding)
        def timeout(owner,packet):raise TimeoutError('bounded post-resolution timeout')
        client.callback=timeout
        self.assertEqual(f.run.continue_phase2_pass(2,action='execute',client=client).status,'timeout')
        failure=f.run.phase2_failure_status()
        self.assertEqual(failure['terminal_state'],'HALTED_CLIENT_TIMEOUT')
        f.run.reconcile_phase2_failure_state()
        report=json.loads(f.store.read('rounds/convergence_failure_report.json'))
        self.assertEqual(report['unresolved_rubric_gaps'],[])
        client.callback=self.response(gaps=False)
        self.assertEqual(f.run.continue_phase2_pass(2,action='execute',client=client,continuation=True).status,'complete')
        f.run.continue_phase2_pass(2,action='consume')
        f.run.reconcile_phase2_failure_state()
        self.advance(f,client)
        package=f.run.prepare_phase2_declaration()
        gaps=json.loads(f.store.read(package['declaration']['rubric_gaps']['path']))['rubric_gaps']
        self.assertEqual(len(gaps),1);self.assertEqual(gaps[0]['status'],'resolved')
        self.assertFalse(gaps[0]['blocking_convergence']);self.assertEqual(package['declaration']['counts']['rubric_gaps'],0)
        self.advance(f,client);f.run.reconcile_phase2_findings()
        self.assertEqual(f.run.finish_phase2()['packet']['terminal_state'],'CONVERGED')
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.assertEqual((client.calls,f.editor.calls,verifier.calls),(5,1,1))

    def test_invalid_requirement_is_bounded_invalid_output_without_candidate(self):
        f,client,_=self.ready();client.callback=self.response(invalid=True)
        head=f.store.read('rounds/current_verified.json')
        result=f.run.run_phase2_review(client=client)
        self.assertEqual(result.status,'attempts_exhausted')
        self.assertEqual(client.calls,2)
        self.assertEqual(f.store.read('rounds/current_verified.json'),head)
        self.assertEqual(f.editor.calls,0)

    def test_editor_failure_reports_retained_gap_without_waiving_it(self):
        f,client,_=self.ready();client.callback=self.response()
        result=f.run.run_phase2_review(client=client);f.run.consume_phase2_result()
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        bound=SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        f.run.bind_phase2_advice(self.advice(bound,result));ref=f.run.admit_phase2_round()
        number=json.loads(f.store.read(ref['path']))['round_number']
        def timeout(packet):raise TimeoutError('bounded Editor timeout')
        f.editor.callback=timeout
        pointer=f.store.read('rounds/current_verified.json')
        self.assertEqual(f.run.request(round_number=number,client=f.editor).value.status,'timeout')
        report=f.run.publish_phase2_correction_failure()
        packet=json.loads(f.store.read(report['active']['path']))
        failure=json.loads(f.store.read(packet['failure']['path']))
        self.assertEqual(len(failure['unresolved_rubric_gaps']),1)
        self.assertTrue(failure['unresolved_major_issues'])
        f.run.reconcile_phase2_correction_failure_state();self.reopen(f)
        f.run.reconcile_phase2_correction_failure_state()
        self.assertEqual(f.store.read('rounds/current_verified.json'),pointer)
        self.assertEqual((client.calls,f.editor.calls),(1,1))
