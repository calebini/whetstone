import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_proposal_run import RUN_INPUT_PATH, run_input_record
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_answers import SemanticAnswerSource, submit_semantic_answer
from whetstone.vnext_semantic_followup_admission import admit_semantic_followup
from whetstone.vnext_semantic_followup_workflow import SemanticFollowupRun
from vnext_consuming_suite_fixture import consuming_suite
from vnext_fixtures import STAMP
import test_vnext_semantic_followup_admission as admission


def workflow_suite(test, directory):
    def extended(*args, **options):
        options['additional_algorithms'] += ('vnext_semantic_run_v1',
            'vnext_semantic_workflow_v1', 'vnext_semantic_followup_workflow_v1')
        return consuming_suite(*args, **options)
    with patch.object(admission, 'consuming_suite', extended):
        return admission.admission_suite(test, directory)


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class SemanticFollowupWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        admission.answers.requests.SemanticRequestTests.setUpClass()

    def setUp(self):
        fixture_class = admission.answers.requests.admission_tests.admission_tests.ProposalAdmissionTests
        original_setup = fixture_class.setUp

        def setup_with_run(fixture):
            original_setup(fixture)
            record = run_input_record(fixture.f.job, dict(descriptor_ref=fixture.f.job_ref,
                review_ref=fixture.f.original.review_ref, seed_map_ref=fixture.f.map_ref,
                round_refs={1: fixture.record_ref}))
            # The selectors exist before the first Editor invocation. This is
            # fresh-root fixture setup, never an upgrade of an existing run.
            with fixture.store.locked(fixture.admission.validate_authority) as token:
                fixture.store.publish(token, RUN_INPUT_PATH, record)

        with patch.object(admission.answers, 'answer_suite', workflow_suite), \
                patch.object(fixture_class, 'setUp', setup_with_run):
            self.subject = admission.answers.subject_for(self)
        self.store = self.subject.store
        self.run = SemanticFollowupRun(self.store, suite_path=self.subject.fixture.path)
        source = SemanticAnswerSource(self.store, admission=self.run.original,
                                      candidate_id=self.subject.identifier)
        self.answer = submit_semantic_answer(self.store, admission=self.run.original,
                                            packet=admission.answers.input_for(source))

    def files(self):
        return admission.answers.files(self.subject)

    def test_explicit_selection_routes_normal_commands_and_reopens_completed_child(self):
        before = self.files()
        stale = self.run.command_view(1)
        self.assertIsNone(stale.reference)  # An answer alone never selects work.
        self.assertEqual(self.files(), before)
        reference = admit_semantic_followup(self.store, original=self.run.original,
            candidate_id=self.subject.identifier, answer_reference=self.answer['reference'])
        before = self.files()
        editor = admission.proposals.Client()
        with self.assertRaisesRegex(ValueError, 'selection changed'):
            stale.run_round(round_number=1, client=editor, decided_at=STAMP)
        self.assertEqual(self.files(), before)
        self.assertEqual(editor.calls, 0)
        self.assertEqual(self.run.admit_followup(candidate_id=self.subject.identifier,
            answer_reference=self.answer['reference']), reference)
        status = self.run.status(round_number=1)
        self.assertEqual(status['request_status'], 'not_started')
        print('normal follow-up selection and stale-command refusal passed', flush=True)
        self.run.run_round(round_number=1, client=editor, decided_at=STAMP)
        status = self.run.semantic_status(round_number=1)
        self.assertEqual(status['processing_gate'], 'semantic_verification')
        creation = self.run.router.registry().inspect().events[-1]
        self.assertEqual(creation['candidate_creation_ordinal'], 2)
        context = load_registered_semantic_context(self.store,
            admission=self.run.command_view(1), candidate_id=creation['candidate_id'])
        verifier = admission.answers.requests.Client(context)
        print('normal follow-up Editor closeout passed', flush=True)
        report, _ = self.run.verify_round(round_number=1, client=verifier, decided_at=STAMP)
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_VERIFIED')
        reopened = SemanticFollowupRun(self.store, suite_path=self.subject.fixture.path)
        before = self.files()
        self.assertEqual(reopened.semantic_status(round_number=1)['processing_gate'], 'complete')
        self.assertEqual(reopened.verify_round(round_number=1, client=object(), decided_at=STAMP)[0], report)
        self.assertEqual(self.files(), before)
        self.assertEqual((editor.calls, verifier.calls, self.subject.editor.calls, self.subject.client.calls),
                         (1, 1, 1, 1))


if __name__ == '__main__':
    unittest.main()
