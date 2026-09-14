from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_verified_history import _VerifiedAnswerSource
from whetstone.vnext_verified_operator import VerifiedOperator
from whetstone.vnext_local_storage import OwnershipLost
from vnext_fixtures import STAMP
import test_vnext_verified_history as history
import test_vnext_verified_work as work


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedOperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): history.VerifiedHistoryTests.setUpClass()
    files = work.VerifiedWorkTests.files
    owner = work.VerifiedWorkTests.owner
    ready = work.VerifiedWorkTests.ready
    run_request = work.VerifiedWorkTests.run_request
    materialize_seed = work.VerifiedWorkTests.materialize_seed
    service = work.VerifiedWorkTests.service
    followup_fixture = work.VerifiedWorkTests.followup_fixture
    verifier = work.VerifiedWorkTests.verifier
    later_candidate = work.VerifiedWorkTests.later_candidate

    def fixture(self, *, operator_contract=True):
        algorithms = ('vnext_verified_materialization_v1', 'vnext_verified_promotion_v1', 'vnext_verified_work_v1')
        if operator_contract: algorithms += ('vnext_verified_operator_v1',)
        return history.VerifiedHistoryTests.fixture(self, extra_algorithms=algorithms)

    def operator(self, f): return VerifiedOperator(f.store, history=self.owner(f))

    def question(self):
        f, _, _ = self.followup_fixture(publish_selection=False)
        self.materialize_seed(f)
        source = _VerifiedAnswerSource(f.store, admission=self.owner(f), candidate_id=f.identifier, require_current=True)
        f.answer = history.answers.input_for(source)
        return f

    def test_actual_question_answer_selection_child_and_promotion_preserve_parent(self):
        f = self.question()
        parent = f.identifier
        operator = self.operator(f)
        before = self.files(f)
        self.assertEqual(operator.answers(candidate_id=parent).value['answers'], [])
        preview = operator.submit_answer(packet=f.answer, dry_run=True)
        self.assertEqual(preview.outcome, 'answer_preview')
        self.assertEqual(self.files(f), before)
        answer = operator.submit_answer(packet=f.answer)
        self.assertEqual(answer.outcome, 'answer_recorded')
        self.assertEqual(answer.value, preview.value)
        self.assertEqual(answer.value['response']['authorized_effects'], [])
        self.assertFalse(list(f.root.rglob('followup_transaction.json')))
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))
        selected = operator.select_followup(candidate_id=parent, answer_reference=answer.value['reference'])
        self.assertEqual(selected.outcome, 'followup_selected')
        self.assertEqual(operator.select_followup(candidate_id=parent, answer_reference=answer.value['reference']).value,
                         selected.value)
        before_child = self.files(f)
        f.editor = history.verified.fixtures.Client()
        self.assertEqual(operator.request(round_number=1, client=f.editor, selected_ref=selected.value).value.status, 'complete')
        f.creation = operator.register(round_number=1, created_at=STAMP, selected_ref=selected.value).value
        f.identifier = f.creation['candidate_id']
        self.assertNotEqual(f.identifier, parent)
        self.assertFalse(operator.answers(candidate_id=parent).value['submission_permitted'])
        child_verifier = self.verifier(f)
        result = operator.verify(client=child_verifier, decided_at=STAMP)
        self.assertTrue(result.value.decision['promotion_permitted'])
        result = self.service(f).promote(prepared_at=STAMP)
        self.assertEqual(result.candidate_id, f.identifier)
        for path, raw in before_child.items():
            if path not in {'rounds/current_verified.json', 'spec.md', 'rounds/run_state.json'}:
                self.assertEqual(f.store.read(path), raw, path)
        self.assertEqual((f.editor.calls, child_verifier.calls), (1, 1))

    def test_response_and_receipt_prefixes_recover_exact_answer_without_clients(self):
        for family in ('/responses/', '/receipts/'):
            for after in (False, True):
                with self.subTest(family=family, after=after):
                    f = self.question()
                    operator = self.operator(f)
                    publish = f.store.publish
                    def stop(token, path, value):
                        if family in path and not after: raise OSError('operator prefix')
                        result = publish(token, path, value)
                        if family in path and after: raise OSError('operator prefix')
                        return result
                    with patch.object(f.store, 'publish', side_effect=stop):
                        with self.assertRaisesRegex(OSError, 'operator prefix'): operator.submit_answer(packet=f.answer)
                    before = self.files(f)
                    operator.answers(candidate_id=f.identifier)
                    operator.submit_answer(packet=f.answer, dry_run=True)
                    self.assertEqual(self.files(f), before)
                    result = operator.submit_answer(packet=f.answer)
                    self.assertEqual(result.outcome, 'answer_recorded')
                    self.assertEqual(operator.submit_answer(packet=f.answer).value, result.value)
                    self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def test_admission_and_selection_prefixes_recover_exact_child_without_clients(self):
        for suffix in ('/admission.json', '/followup_transaction.json'):
            for after in (False, True):
                with self.subTest(suffix=suffix, after=after):
                    f = self.question()
                    operator = self.operator(f)
                    reference = operator.submit_answer(packet=f.answer).value['reference']
                    publish = f.store.publish
                    def stop(token, path, value):
                        if path.endswith(suffix) and not after: raise OSError('selection prefix')
                        result = publish(token, path, value)
                        if path.endswith(suffix) and after: raise OSError('selection prefix')
                        return result
                    with patch.object(f.store, 'publish', side_effect=stop):
                        with self.assertRaisesRegex(OSError, 'selection prefix'):
                            operator.select_followup(candidate_id=f.identifier, answer_reference=reference)
                    result = operator.select_followup(candidate_id=f.identifier, answer_reference=reference)
                    self.assertEqual(result.outcome, 'followup_selected')
                    self.assertEqual(operator.select_followup(candidate_id=f.identifier, answer_reference=reference).value,
                                     result.value)
                    self.assertEqual((f.editor.calls, f.client.calls), (1, 1))
                    self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'], 0)

    def test_decline_stale_bindings_and_different_receipt_cannot_select_child(self):
        f = self.question()
        operator = self.operator(f)
        bad = deepcopy(f.answer)
        bad['request']['hash'] = 'f' * 64
        before = self.files(f)
        with self.assertRaises(ValueError): operator.submit_answer(packet=bad)
        self.assertEqual(self.files(f), before)
        declined = {**f.answer, 'action': 'decline', 'selected_authority_binding_id': None}
        receipt = operator.submit_answer(packet=declined).value['reference']
        before = self.files(f)
        with self.assertRaises(ValueError): operator.select_followup(candidate_id=f.identifier, answer_reference=receipt)
        self.assertEqual(self.files(f), before)
        selected = operator.submit_answer(packet=f.answer).value['reference']
        operator.select_followup(candidate_id=f.identifier, answer_reference=selected)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'different follow-up'):
            operator.select_followup(candidate_id=f.identifier, answer_reference=receipt)
        self.assertEqual(self.files(f), before)

    def test_missing_contract_refuses_before_materialization_or_operator_writes(self):
        f = self.fixture(operator_contract=False)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'verified operator algorithm is outside supported suite'):
            self.operator(f).answers(candidate_id=f.identifier)
        self.assertEqual(self.files(f), before)

    def test_superseded_source_and_changed_raw_verifier_evidence_refuse_operator_writes(self):
        f = self.question()
        parent = f.identifier
        answer = deepcopy(f.answer)
        self.later_candidate(f, reject=True)
        operator = self.operator(f)
        before = self.files(f)
        self.assertFalse(operator.answers(candidate_id=parent).value['submission_permitted'])
        with self.assertRaisesRegex(ValueError, 'latest candidate and exact current base'):
            operator.submit_answer(packet=answer)
        self.assertEqual(self.files(f), before)

        g = self.question()
        self.operator(g).answers(candidate_id=g.identifier)
        request = next(path for path in g.root.glob('rounds/client_requests/*/request.json')
                       if json.loads(path.read_bytes())['role'] == 'verifier')
        raw = request.parent / 'attempts/1/response.json'
        raw.write_bytes(raw.read_bytes() + b' ')
        before = self.files(g)
        with self.assertRaises(ValueError): self.operator(g).submit_answer(packet=g.answer)
        self.assertEqual(self.files(g), before)

    def test_operator_dry_run_never_repairs_and_mutating_recovery_ends_before_answer(self):
        f = self.question()
        (f.root / 'spec.md').unlink()
        operator = self.operator(f)
        before = self.files(f)
        self.assertEqual(operator.submit_answer(packet=f.answer, dry_run=True).outcome, 'materialization_required')
        self.assertEqual(operator.answers(candidate_id=f.identifier).outcome, 'materialization_required')
        self.assertEqual(self.files(f), before)
        self.assertEqual(operator.submit_answer(packet=f.answer).outcome, 'materialization_recovered')
        self.assertFalse(list(f.root.rglob('operator_answers')))
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))

    def test_fence_loss_after_response_leaves_receipt_for_exact_recovery(self):
        f = self.question()
        operator = self.operator(f)
        before = self.files(f)
        publish = f.store.publish
        def lose(token, path, value):
            result = publish(token, path, value)
            if '/responses/' in path: f.store._invalidate()
            return result
        with patch.object(f.store, 'publish', side_effect=lose):
            with self.assertRaises(OwnershipLost): operator.submit_answer(packet=f.answer)
        self.assertFalse(list(f.root.rglob('answer-*.json')))
        result = self.operator(f).submit_answer(packet=f.answer)
        self.assertEqual(result.outcome, 'answer_recorded')
        self.assertEqual(f.store.read('rounds/current_verified.json'), before['rounds/current_verified.json'])
        self.assertEqual((f.editor.calls, f.client.calls), (1, 1))


if __name__ == '__main__': unittest.main()
