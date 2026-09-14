from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_decisions import derived_task
from whetstone.vnext_identity import response_id
from whetstone.vnext_local_storage import Publication, StorageWriteError
from whetstone.vnext_semantic_admission import SEMANTIC_ALGORITHMS, SEMANTIC_SCHEMAS
from whetstone.vnext_semantic_answers import (
    ANSWER_SCHEMAS, SemanticAnswerSource, inspect_semantic_answers, prepare_answer,
    read_semantic_answer, submit_semantic_answer, validate_answer_response,
)
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from whetstone.vnext_semantic_protocol import POLICY_VERSION, RULES
from whetstone.vnext_semantic_requests import REQUEST_SCHEMAS
from whetstone.vnext_proposal_requests import run_proposal_request
from whetstone.vnext_proposal_handoff import register_completed_proposal_request
from whetstone.clients import canonicalize_reviewer_input
from vnext_consuming_suite_fixture import consuming_suite
from vnext_fixtures import STAMP
import test_vnext_semantic_requests as requests


def answer_suite(test, directory):
    return consuming_suite(test, directory, additional_schemas=SEMANTIC_SCHEMAS | REQUEST_SCHEMAS | ANSWER_SCHEMAS,
        additional_algorithms=(*SEMANTIC_ALGORITHMS, 'vnext_semantic_requests_v1',
                              'vnext_semantic_decisions_v1', 'vnext_semantic_answers_v1'),
        algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})


def subject_for(test, *, reject=False):
    helper = requests.SemanticOperatorRequestTests()
    test.addCleanup(helper.doCleanups)
    with patch.object(requests, 'request_suite', answer_suite):
        subject = helper.make_subject()
    if reject:
        response = json.loads(subject.client.responses[0])
        response.update(verdict='reject', lost_or_weakened_semantics='uncertain')
        response['uncertainty_resolutions'].append(dict(field_path='lost_or_weakened_semantics',
            policy_rule_id=RULES['lost_or_weakened_semantics'],disposition='reject',decision_id=None))
        subject.client.responses = [canonical_json_bytes(response)]
    subject.run_request()
    SemanticDecisionJournal(subject.registry, admission=subject.admission).commit_semantic(subject.identifier, decided_at=STAMP)
    return subject


def input_for(source):
    return {'schema_version':'vnext-semantic-answer-input-v1', 'job_id':source.request['job_id'],
        'candidate_id':source.request['candidate_id'], 'request':deepcopy(source.request_ref),
        'candidate_verification':deepcopy(source.decision_ref), 'action':'select',
        'selected_authority_binding_id':source.request['choice']['alternatives'][0]['authority_binding_id'],
        'rationale':'Use the explicitly selected interpretation in separately admitted work.',
        'decided_by':'fixture-operator', 'decided_at':STAMP}


def files(subject):
    return {p.relative_to(subject.fixture.root).as_posix():p.read_bytes()
            for p in subject.fixture.root.rglob('*') if p.is_file()}


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticAnswerBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests.SemanticRequestTests.setUpClass()
        # One physically admitted, immutable context suffices for pure binding tests.
        owner = unittest.TestCase()
        cls.addClassCleanup(owner.doCleanups)
        cls.subject = subject_for(owner)
        cls.source = SemanticAnswerSource(cls.subject.store, admission=cls.subject.admission,
                                         candidate_id=cls.subject.identifier)

    def prepare(self, packet):
        source = self.source
        return prepare_answer(packet, request=source.request, context=source.context,
                              request_ref=source.request_ref, decision_ref=source.decision_ref, suite=source.suite)

    def test_explicit_selection_and_decline_never_grant_effects(self):
        packet = input_for(self.source)
        for decline in (False, True):
            with self.subTest(decline=decline):
                if decline: packet.update(action='decline', selected_authority_binding_id=None)
                response = self.prepare(packet)
                self.assertEqual(response['selected_option_id'], 'decline' if decline else packet['selected_authority_binding_id'])
                self.assertEqual(response['authorized_effects'], [])
                self.assertEqual(response['authorized_deletion_unit_ids'], [])
                with self.assertRaisesRegex(ValueError, 'cannot create editing work'):
                    derived_task({}, response, self.source.request)

    def test_stale_sources_unknown_options_and_contradictory_actions_refuse(self):
        for field,value in [('job_id','job_'+'f'*64), ('candidate_id','can_'+'f'*64),
                            ('request',{'path':'other.json','hash':'f'*64}),
                            ('candidate_verification',{'path':'other.json','hash':'f'*64}),
                            ('selected_authority_binding_id','bind_'+'f'*64),
                            ('selected_authority_binding_id',None), ('action','decline'),
                            ('rationale','  '), ('decided_by','\t')]:
            with self.subTest(field=field,value=value):
                packet = input_for(self.source);packet[field] = value
                with self.assertRaises(ValueError): self.prepare(packet)

    def test_recomputed_identity_cannot_add_effects_or_change_question_binding(self):
        for field,value in [('authorized_effects',['strengthen']),
                            ('decision_request_hash','f'*64), ('selected_option_id','unknown')]:
            with self.subTest(field=field):
                response = self.prepare(input_for(self.source));response[field] = value
                response['response_id'] = response_id(response)
                with self.assertRaises(ValueError):
                    validate_answer_response(response, request=self.source.request,
                                             context=self.source.context,suite=self.source.suite)

    def test_timestamp_is_not_identity_but_is_part_of_immutable_bytes(self):
        packet = input_for(self.source)
        first = self.prepare(packet)
        packet['decided_at'] = '2031-01-01T00:00:00Z'
        second = self.prepare(packet)
        self.assertEqual(first['response_id'],second['response_id'])
        self.assertNotEqual(canonical_json_bytes(first),canonical_json_bytes(second))


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticAnswerStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests.SemanticRequestTests.setUpClass()

    def setup_source(self, *, reject=False):
        self.subject = subject_for(self,reject=reject)
        self.source = SemanticAnswerSource(self.subject.store,admission=self.subject.admission,
                                          candidate_id=self.subject.identifier)
        self.packet = input_for(self.source)

    def submit(self, **options):
        return submit_semantic_answer(self.subject.store,admission=self.subject.admission,
                                      packet=self.packet,**options)

    def inspect(self):
        return inspect_semantic_answers(self.subject.store,admission=self.subject.admission,
                                        candidate_id=self.subject.identifier)

    def read(self, reference):
        return read_semantic_answer(self.subject.store,admission=self.subject.admission,
                                    candidate_id=self.subject.identifier,reference=reference)

    def test_dry_run_and_readback_preserve_original_evidence_and_multiple_answers_have_no_default(self):
        self.setup_source()
        original = files(self.subject)
        preview = self.submit(dry_run=True)
        self.assertEqual(self.inspect()['answers'],[])
        self.assertEqual(files(self.subject),original)
        first = self.submit()
        self.assertEqual(first,preview)
        self.assertEqual(self.read(first['reference'])['response'],first['response'])
        self.packet.update(action='decline',selected_authority_binding_id=None,rationale='Defer further work.')
        second = self.submit()
        status = self.inspect()
        self.assertEqual(len(status['answers']),2)
        self.assertEqual({row['action'] for row in status['answers']},{'select','decline'})
        self.assertTrue(all(row['receipt'] for row in status['answers']))
        self.assertNotIn('selected_response',status)
        self.assertEqual(self.read(second['reference'])['response']['authorized_effects'],[])
        after = files(self.subject)
        self.assertTrue(all(after.get(path) == raw for path,raw in original.items()))
        self.assertEqual((self.subject.client.calls,self.subject.editor.calls),(1,1))
        self.inspect();self.read(first['reference'])
        self.assertEqual(files(self.subject),after)

    def test_response_prefix_requires_receipt_and_exact_reentry_finishes_without_clients(self):
        self.setup_source()
        expected = self.submit(dry_run=True)
        original = self.subject.store.publish
        target = expected['receipt']['response']['path']
        def stop(token,path,value):
            result = original(token,path,value)
            if path == target: raise OSError('scripted answer interruption')
            return result
        with patch.object(self.subject.store,'publish',side_effect=stop):
            with self.assertRaisesRegex(OSError,'answer interruption'): self.submit()
        rows = self.inspect()['answers']
        self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['receipt'])
        with self.assertRaisesRegex(ValueError,'missing or stale'): self.read(expected['reference'])
        self.assertEqual(self.submit(),expected)
        self.assertEqual(self.submit(),expected)
        self.assertEqual((self.subject.client.calls,self.subject.editor.calls),(1,1))
        self.packet['decided_at'] = '2031-01-01T00:00:00Z'
        before = files(self.subject)
        with self.assertRaisesRegex(ValueError,'different bytes'): self.submit()
        self.assertEqual(files(self.subject),before)

    def test_receipt_acknowledgement_loss_and_tampered_response_refuse_without_hidden_repair(self):
        self.setup_source()
        expected = self.submit(dry_run=True)
        original = self.subject.store._tree.write
        def stop(path,raw,**options):
            result = original(path,raw,**options)
            if path == expected['reference']['path']:
                raise StorageWriteError(Publication('outcome_requires_reconciliation',path,result.hash),
                                        'scripted lost receipt acknowledgement')
            return result
        with patch.object(self.subject.store._tree,'write',side_effect=stop):
            with self.assertRaises(StorageWriteError): self.submit()
        self.assertIsNone(self.subject.store._token)
        self.assertEqual(self.read(expected['reference'])['receipt'],expected['receipt'])
        self.assertEqual(self.submit(),expected)
        response_path = self.subject.fixture.root/expected['receipt']['response']['path']
        value = json.loads(response_path.read_bytes());value['decided_at'] = '2031-01-01T00:00:00Z'
        response_path.write_bytes(canonical_json_bytes(value))
        before = files(self.subject)
        with self.assertRaisesRegex(ValueError,'missing or changed sources'): self.inspect()
        with self.assertRaises(ValueError): self.submit()
        self.assertEqual(files(self.subject),before)
        self.assertEqual((self.subject.client.calls,self.subject.editor.calls),(1,1))

    def test_unknown_artifacts_and_missing_or_changed_sources_refuse_without_writes(self):
        self.setup_source()
        answer = self.submit()
        root = self.subject.fixture.root
        for extra in (self.source.directory+'/unexpected.json',
                      self.source.directory.rsplit('/',1)[0]+'/unknown-question/request.json'):
            path = root/extra
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'{}')
            before = files(self.subject)
            with self.assertRaises(ValueError): self.inspect()
            with self.assertRaises(ValueError): self.submit()
            self.assertEqual(files(self.subject),before)
            path.unlink()
            if 'unknown-question' in extra: path.parent.rmdir()
        for reference in (self.source.request_ref,self.source.decision_ref,answer['receipt']['response']):
            path = root/reference['path'];raw = path.read_bytes()
            for missing in (False,True):
                with self.subTest(path=reference['path'],missing=missing):
                    if missing: path.unlink()
                    else: path.write_bytes(raw+b' ')
                    before = files(self.subject)
                    with self.assertRaises((ValueError,FileNotFoundError)): self.read(answer['reference'])
                    self.assertEqual(files(self.subject),before)
                    path.write_bytes(raw)
        self.assertEqual((self.subject.client.calls,self.subject.editor.calls),(1,1))

    def test_reject_dominance_remains_final_after_answer_and_receipt_must_be_explicit(self):
        self.setup_source(reject=True)
        decision = deepcopy(self.source.view.decision)
        self.assertEqual(decision['semantic_result'],'reject')
        answer = self.submit()
        for reference in (None,{}, {'path':[],'hash':'f'*64},
                          {'path':answer['reference']['path'],'hash':'f'*64}):
            with self.subTest(reference=reference):
                with self.assertRaises(ValueError): self.read(reference)
        final = self.source.journal.inspect(self.subject.identifier)
        self.assertEqual(final.decision,decision)
        self.assertEqual(self.source.journal.terminal()['terminal_state'],'TARGET_NOT_REACHED')
        self.assertEqual(self.subject.client.calls,1)

    def test_historical_receipt_remains_readable_but_superseded_candidate_cannot_receive_answers(self):
        self.setup_source()
        answer = self.submit()
        original = files(self.subject)
        fixture = self.subject.fixture
        feedback = deepcopy(fixture.f.feedback)
        feedback['round_number'] = 2
        feedback['feedback'][0]['claim'] += ' Independent second fixture review.'
        canonicalize_reviewer_input(feedback)
        feedback_ref = fixture.save_input('inputs/feedback-2.json',feedback)
        advice_ref = fixture.save_input('inputs/advice-2.json',{**deepcopy(fixture.f.advice),'feedback':feedback_ref})
        record = {**deepcopy(fixture.record),'round_number':2,'feedback':feedback_ref,'advice':advice_ref}
        reference = fixture.save_input('inputs/round-2.json',record)
        admission = fixture.make_admission(round_refs={**fixture.admission._refs['rounds'],2:reference})
        # A separate genuine fixture review makes candidate 1 historical. This
        # does not stand in for the still-unimplemented answer-driven bridge.
        client = requests.admission_tests.Client()
        run_proposal_request(fixture.store,load_inputs=lambda read:admission.load_inputs(read,2),
                             validate_authority=admission.validate_authority,client=client)
        second = register_completed_proposal_request(fixture.store,round_number=2,load_inputs=admission.load_inputs,
                                                     validate_authority=admission.validate_authority,created_at=STAMP)
        self.assertNotEqual(second['candidate_id'],self.subject.identifier)
        self.subject.admission = admission
        self.assertFalse(self.inspect()['submission_permitted'])
        self.assertEqual(self.read(answer['reference'])['receipt'],answer['receipt'])
        before = files(self.subject)
        with self.assertRaisesRegex(ValueError,'requires the current candidate'): self.submit()
        self.assertEqual(files(self.subject),before)
        self.assertTrue(all(before.get(path) == raw for path,raw in original.items()))
        self.assertEqual((client.calls,self.subject.client.calls,self.subject.editor.calls),(1,1,1))


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticAnswerAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests.SemanticRequestTests.setUpClass()

    def test_installed_answer_files_do_not_infer_schema_or_algorithm_support(self):
        for absent in ('algorithm','schemas'):
            with self.subTest(absent=absent):
                def factory(test,directory):
                    algorithms = (*SEMANTIC_ALGORITHMS,'vnext_semantic_requests_v1','vnext_semantic_decisions_v1')
                    if absent != 'algorithm': algorithms += ('vnext_semantic_answers_v1',)
                    schemas = SEMANTIC_SCHEMAS | REQUEST_SCHEMAS
                    if absent != 'schemas': schemas |= ANSWER_SCHEMAS
                    return consuming_suite(test,directory,additional_schemas=schemas,additional_algorithms=algorithms,
                        algorithm_overrides={'semantic_verifier_policy_version':POLICY_VERSION})
                owner = requests.SemanticRequestTests()
                self.addCleanup(owner.doCleanups)
                with patch.object(requests,'request_suite',factory): owner.setUp()
                before = files(owner)
                with self.assertRaisesRegex(ValueError,'semantic answer '+absent):
                    inspect_semantic_answers(owner.store,admission=owner.admission,candidate_id=owner.identifier)
                self.assertEqual(files(owner),before)
                self.assertEqual(owner.client.calls,0)
                # Restore suite registration before starting a different fixture.
                owner.doCleanups()


if __name__ == '__main__':
    unittest.main()
